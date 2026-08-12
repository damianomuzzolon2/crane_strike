"""
interfaccia.py
--------------
Interfaccia grafica: apre una linea da file Excel, calcola il ciclogramma
(automaticamente o partendo da una proposta semplice), lo mostra, lo fa
verificare e salva i risultati. Nessun comando da terminale.

    python interfaccia.py            apre la finestra
    python interfaccia.py linea.xlsx apre la finestra caricando subito il file

Costruita su tkinter (libreria standard di Python) con il grafico matplotlib
incorporato: nessuna dipendenza in piu' rispetto a quelle gia' necessarie, e
nessun server o browser di mezzo -- serve a poter impacchettare tutto in un
eseguibile autonomo.
"""

from __future__ import annotations

import dataclasses
import gc
import multiprocessing
import os
import queue
import sys
import threading
import traceback

import matplotlib

matplotlib.use("TkAgg")

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from excel_io import leggi_problema, scrivi_modello, scrivi_risultati
from model import solve, solve_auto_hoists, solve_auto_zones
import manuale
from plotting import (
    _HOIST_COLORS,
    _sample_segment,
    lettura_coordinate,
    plot_cyclogram,
)
from verify import verify_solution

TITOLO = "Ciclogrammi carroponti"

# colori delle righe del report, per gravita'
_COLORI_GRAVITA = {
    "error": "#f4cccc",
    "warning": "#fce5cd",
    "info": "#efefef",
}
_ETICHETTE_GRAVITA = {"error": "ERRORE", "warning": "avviso", "info": "nota"}

# Disegno manuale: un solo grigio per tutto cio' che l'utente non ha ancora
# deciso, e due soli spessori. Il colore compare solo dove si e' assegnato un
# trasporto a un carroponte, e li' vuol dire quello e nient'altro.
_GRIGIO = "#9a9a9a"
_SOTTILE = 1.2
_SPESSO = 2.6


class _BarraGrafico(NavigationToolbar2Tk):
    """La barra di navigazione di matplotlib (zoom a rettangolo, pan, vista
    intera, salva immagine), che avvisa l'applicazione quando la vista cambia.

    Serve avvisarla perche' il grafico viene ridisegnato da zero a ogni
    modifica: senza sapere che l'utente ha ingrandito una zona, ogni clic gli
    farebbe saltare la vista al punto di partenza -- proprio mentre sta
    lavorando sul dettaglio per cui aveva ingrandito."""

    # Le stesse voci di matplotlib, con le descrizioni in italiano e senza
    # "Configure subplots": regola i margini, che qui vengono comunque
    # ricalcolati da tight_layout a ogni ridisegno, quindi non farebbe altro
    # che sfasare il grafico. I nomi in prima colonna restano in inglese: la
    # barra ci cerca dentro 'Back' e 'Forward' per abilitarli.
    toolitems = (
        ("Home", "Torna a inquadrare tutto", "home", "home"),
        ("Back", "Vista precedente", "back", "back"),
        ("Forward", "Vista successiva", "forward", "forward"),
        (None, None, None, None),
        ("Pan", "Sposta l'inquadratura trascinando", "move", "pan"),
        ("Zoom", "Ingrandisci un rettangolo", "zoom_to_rect", "zoom"),
        (None, None, None, None),
        ("Save", "Salva l'immagine come si vede adesso", "filesave", "save_figure"),
    )

    def __init__(self, tela, cornice, al_cambio, al_ripristino):
        self._al_cambio = al_cambio
        self._al_ripristino = al_ripristino
        super().__init__(tela, cornice, pack_toolbar=False)

    def home(self, *args):
        self._al_ripristino()
        super().home(*args)

    def release_zoom(self, event):
        super().release_zoom(event)
        self._al_cambio()

    def release_pan(self, event):
        super().release_pan(event)
        self._al_cambio()

    def back(self, *args):
        super().back(*args)
        self._al_cambio()

    def forward(self, *args):
        super().forward(*args)
        self._al_cambio()


class Applicazione(tk.Tk):
    def __init__(self, file_iniziale: str | None = None):
        super().__init__()
        self.title(TITOLO)
        self.geometry("1280x800")
        self.minsize(1000, 640)

        # -- stato ---------------------------------------------------------
        self.percorso_file: str | None = None
        self.config_linea = None  # Configurazione letta dall'Excel
        self.dati = None  # ProblemData con le zone valorizzate
        self.soluzione = None
        self.report = None
        self._coda: queue.Queue = queue.Queue()
        self._lavoro_in_corso = False

        # -- il ciclogramma, nei termini in cui si modifica -------------------
        # Un ciclogramma ha pochissimi gradi di liberta' reali, e sono gli
        # stessi che si usano tracciandolo a mano su carta: il takt time, il
        # TEMPO IN VASCA di ogni tappa, e QUALE CARROPONTE fa ogni trasporto.
        # Istanti di prelievo, traiettorie, rientri a vuoto sono conseguenza.
        #
        # Vale identico per un ciclogramma calcolato dal solutore e per uno
        # composto da zero: sono lo stesso oggetto. Il solutore ne produce
        # uno, e i suoi tempi in vasca si rileggono dalla catena dei prelievi
        # -- ricomporlo da li' restituisce esattamente lo stesso ciclogramma.
        # Per questo si modificano allo stesso modo, in una pagina sola.
        self.T_corrente: float | None = None
        self.permanenze: dict[int, float] = {}
        self.assegnazione: dict[int, int] = {}
        self.n_carroponti = 2
        self.carroponte_attivo = 0
        self.incoerenze: list[str] = []
        # da dove viene il ciclogramma che si sta guardando, per il riepilogo
        self.origine = ""
        self.modificato = False
        self._annulla: list = []  # pila per il ripristino
        self._trascinamento = None
        self._guida = None
        # zoom: vero quando l'inquadratura l'ha scelta l'utente e va
        # conservata attraverso i ridisegni
        self._zoom_utente = False

        # Quale disegno e' a schermo. NON e' una scelta dell'utente: la decide
        # il modo in cui e' arrivato. "Calcola auto" da' un ciclogramma da
        # leggere, quindi le traiettorie dei carroponti; "Calcola man" da' un
        # foglio bianco da riempire, quindi il pettine dei pezzi su cui si
        # clicca. Un interruttore fra i due c'e' stato ed e' stato tolto: le
        # tabelle della scheda Ciclogramma permettono di modificare tutto
        # senza cambiare disegno, quindi restava un comando che chiedeva una
        # decisione senza darne il motivo.
        self.vista = "ciclogramma"  # oppure "pettine"
        # Se la scheda Ciclogramma sia aperta o no. Non e' sempre: dopo un
        # calcolo automatico si sta LEGGENDO un risultato, e per metterci le
        # mani bisogna dirlo premendo "Modifica". Cosi' i tre pulsanti sono tre
        # stati veri -- leggi, componi, modifica -- invece di due piu' una
        # scorciatoia, e un ciclogramma calcolato non si altera per sbaglio
        # con un trascinamento di troppo.
        self.modifica_aperta = False
        # La verifica, una volta chiesta, si tiene aggiornata da sola. Non
        # parte da sola: comporre da zero vuol dire passare per stati
        # dichiaratamente sbagliati, e un muro di errori rossi mentre si sceglie
        # la prima mossa non informa nessuno.
        self.verifica_viva = False

        self._costruisci_interfaccia()
        self._aggiorna_stato_pulsanti()
        if file_iniziale:
            self.after(100, lambda: self._carica(file_iniziale))

    # ------------------------------------------------------------------
    # Costruzione dell'interfaccia
    # ------------------------------------------------------------------

    def _costruisci_interfaccia(self):
        barra = ttk.Frame(self, padding=(10, 8))
        barra.pack(fill=tk.X)

        ttk.Button(barra, text="Apri linea...", command=self._chiedi_file).pack(
            side=tk.LEFT
        )
        ttk.Button(
            barra, text="Nuovo modello Excel...", command=self._crea_modello
        ).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(barra, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=12
        )

        # I tre modi di arrivare a un ciclogramma: fallo fare al solutore,
        # componilo tu, oppure lavora su quello che c'e'. Il terzo non e' un
        # quarto stato del programma: di ciclogramma ne esiste sempre e solo
        # uno, e "Modifica" porta li' -- non sceglie fra una versione
        # automatica e una manuale, che dopo l'unificazione della pagina sono
        # lo stesso oggetto con gli stessi gradi di liberta'.
        self.btn_auto = ttk.Button(
            barra, text="Calcola auto", command=self._calcola_automatico
        )
        self.btn_auto.pack(side=tk.LEFT)
        self.btn_proposta = ttk.Button(
            barra, text="Calcola man", command=self._componi_da_zero
        )
        self.btn_proposta.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_modifica = ttk.Button(
            barra, text="Modifica", command=self._vai_a_modifica
        )
        self.btn_modifica.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(barra, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=12
        )

        self.btn_salva = ttk.Button(
            barra, text="Salva risultati...", command=self._salva
        )
        self.btn_salva.pack(side=tk.LEFT)

        # Percorso completo, non solo il nome: su un PC di stabilimento lo
        # stesso file esiste in piu' copie (scrivania, cartella di commessa,
        # rete) e sapere *quale* si sta guardando conta piu' del nome.
        # expand=True gli lascia tutto lo spazio che avanza dai pulsanti.
        self.etichetta_file = ttk.Label(
            barra, text="Nessuna linea caricata", anchor=tk.E
        )
        self.etichetta_file.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(12, 0))

        # -- corpo: grafico a sinistra, pannello a destra -------------------
        corpo = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        corpo.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        cornice_grafico = ttk.Frame(corpo)
        corpo.add(cornice_grafico, weight=3)

        self.figura = Figure(figsize=(9, 6), dpi=100)
        self.assi = self.figura.add_subplot(111)
        self._grafico_vuoto()
        self.tela = FigureCanvasTkAgg(self.figura, master=cornice_grafico)
        # La barra va impacchettata PRIMA della tela: la tela si prende tutto
        # lo spazio che avanza (expand=True) e altrimenti non ne lascerebbe.
        self.barra_grafico = _BarraGrafico(
            self.tela, cornice_grafico, self._segna_zoom, self._azzera_zoom
        )
        self.barra_grafico.pack(side=tk.BOTTOM, fill=tk.X)
        self.tela.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.tela.mpl_connect("button_press_event", self._su_pressione)
        self.tela.mpl_connect("motion_notify_event", self._su_movimento)
        self.tela.mpl_connect("button_release_event", self._su_rilascio)
        self.tela.mpl_connect("scroll_event", self._su_rotella)

        pannello = ttk.Frame(corpo, width=470)
        corpo.add(pannello, weight=1)

        # -- verdetto sempre in vista: e' l'informazione che conta mentre si
        #    modifica, non deve finire dentro una scheda -------------------
        self.banner = tk.Label(
            pannello,
            text="Nessun ciclogramma",
            font=("", 11, "bold"),
            background="#e8e8e8",
            anchor=tk.W,
            padx=10,
            pady=6,
        )
        self.banner.pack(fill=tk.X, pady=(0, 6))

        schede = ttk.Notebook(pannello)
        schede.pack(fill=tk.BOTH, expand=True)
        self.schede = schede

        # -- scheda: riepilogo ---------------------------------------------
        scheda_riepilogo = ttk.Frame(schede, padding=6)
        schede.add(scheda_riepilogo, text="Riepilogo")
        self.testo_riepilogo = tk.Text(
            scheda_riepilogo, wrap=tk.WORD, relief=tk.FLAT, background="#f7f7f7"
        )
        self.testo_riepilogo.pack(fill=tk.BOTH, expand=True)
        self.testo_riepilogo.configure(state=tk.DISABLED)

        # -- scheda: il ciclogramma ----------------------------------------
        # Una sola, per il calcolato e per il composto a mano: sono lo stesso
        # oggetto con gli stessi gradi di liberta'.
        scheda_ciclogramma = ttk.Frame(schede, padding=6)
        schede.add(scheda_ciclogramma, text="Ciclogramma")
        self._costruisci_scheda_ciclogramma(scheda_ciclogramma)

        # -- scheda: verifica ----------------------------------------------
        scheda_verifica = ttk.Frame(schede, padding=6)
        schede.add(scheda_verifica, text="Verifica")
        self.scheda_verifica = scheda_verifica
        cornice_tabella = ttk.Frame(scheda_verifica)
        cornice_tabella.pack(fill=tk.BOTH, expand=True)
        self.tabella = ttk.Treeview(
            cornice_tabella,
            columns=("gravita", "tipo", "descrizione"),
            show="headings",
        )
        self.tabella.heading("gravita", text="gravita'")
        self.tabella.heading("tipo", text="tipo")
        self.tabella.heading("descrizione", text="descrizione")
        self.tabella.column("gravita", width=64, anchor=tk.W, stretch=False)
        self.tabella.column("tipo", width=104, anchor=tk.W, stretch=False)
        self.tabella.column("descrizione", width=250, anchor=tk.W)
        barra_scorrimento = ttk.Scrollbar(
            cornice_tabella, orient=tk.VERTICAL, command=self.tabella.yview
        )
        self.tabella.configure(yscrollcommand=barra_scorrimento.set)
        self.tabella.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        barra_scorrimento.pack(side=tk.RIGHT, fill=tk.Y)
        for gravita, colore in _COLORI_GRAVITA.items():
            self.tabella.tag_configure(gravita, background=colore)
        self.tabella.bind("<<TreeviewSelect>>", self._mostra_dettaglio)
        ttk.Label(
            scheda_verifica,
            text="Fai clic su una riga per leggerla per intero.",
            foreground="#777777",
        ).pack(anchor=tk.W, pady=(4, 0))

    def _costruisci_scheda_ciclogramma(self, cornice):
        ttk.Label(
            cornice,
            text="Il ciclogramma si regola con tre cose: il takt time, il tempo\n"
            "in vasca di ogni tappa e quale carroponte fa ogni trasporto.\n"
            "Tutto il resto viene da se'. Vale sia per un ciclogramma\n"
            "calcolato sia per uno composto da zero.",
            foreground="#555555",
        ).pack(anchor=tk.W)

        riga = ttk.Frame(cornice)
        riga.pack(fill=tk.X, pady=(8, 2))
        ttk.Label(riga, text="Takt time [s]:").pack(side=tk.LEFT)
        self.var_takt = tk.StringVar()
        campo = ttk.Entry(riga, textvariable=self.var_takt, width=9)
        campo.pack(side=tk.LEFT, padx=(6, 2))
        campo.bind("<Return>", lambda e: self._modifica_takt())
        ttk.Button(riga, text="Applica", width=8, command=self._modifica_takt).pack(
            side=tk.LEFT
        )

        riga2 = ttk.Frame(cornice)
        riga2.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(riga2, text="Carroponti:").pack(side=tk.LEFT)
        self.var_carroponti = tk.StringVar(value="2")
        self.spin_carroponti = ttk.Spinbox(
            riga2,
            from_=1,
            to=8,
            width=4,
            textvariable=self.var_carroponti,
            command=self._cambia_carroponti,
        )
        self.spin_carroponti.pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(riga2, text="attivo:").pack(side=tk.LEFT)
        self.var_carro_attivo = tk.StringVar(value="1")
        self.combo_attivo = ttk.Combobox(
            riga2,
            width=5,
            state="readonly",
            textvariable=self.var_carro_attivo,
            values=["1", "2"],
        )
        self.combo_attivo.pack(side=tk.LEFT, padx=(6, 0))
        self.combo_attivo.bind(
            "<<ComboboxSelected>>",
            lambda e: setattr(
                self, "carroponte_attivo", int(self.var_carro_attivo.get()) - 1
            ),
        )

        ttk.Label(cornice, text="Tempi in vasca", font=("", 9, "bold")).pack(
            anchor=tk.W, pady=(6, 2)
        )
        cornice_perm = ttk.Frame(cornice)
        cornice_perm.pack(fill=tk.BOTH, expand=True)
        self.tabella_permanenze = ttk.Treeview(
            cornice_perm,
            columns=("vasca", "tempo", "min", "max"),
            show="headings",
            height=7,
        )
        for chiave, titolo, larghezza in [
            ("vasca", "vasca", 130),
            ("tempo", "tempo [s]", 80),
            ("min", "min", 55),
            ("max", "max", 55),
        ]:
            self.tabella_permanenze.heading(chiave, text=titolo)
            self.tabella_permanenze.column(
                chiave, width=larghezza, anchor=tk.W, stretch=(chiave == "vasca")
            )
        self.tabella_permanenze.pack(fill=tk.BOTH, expand=True)
        self.tabella_permanenze.bind("<Double-1>", self._modifica_permanenza)
        ttk.Label(
            cornice,
            text="Doppio clic sul tempo per cambiarlo. Il minimo e il massimo\n"
            "sono di processo: si possono sforare, la verifica lo dira'.",
            foreground="#777777",
        ).pack(anchor=tk.W, pady=(2, 0))

        ttk.Label(cornice, text="Assegnazione", font=("", 9, "bold")).pack(
            anchor=tk.W, pady=(8, 2)
        )
        cornice_ass = ttk.Frame(cornice)
        cornice_ass.pack(fill=tk.BOTH, expand=True)
        self.tabella_assegnazione = ttk.Treeview(
            cornice_ass,
            columns=("mossa", "da", "a", "carro"),
            show="headings",
            height=7,
        )
        for chiave, titolo, larghezza in [
            ("mossa", "n", 28),
            ("da", "da vasca", 115),
            ("a", "a vasca", 115),
            ("carro", "carrop.", 60),
        ]:
            self.tabella_assegnazione.heading(chiave, text=titolo)
            self.tabella_assegnazione.column(
                chiave, width=larghezza, anchor=tk.W, stretch=(chiave in ("da", "a"))
            )
        self.tabella_assegnazione.pack(fill=tk.BOTH, expand=True)
        self.tabella_assegnazione.bind("<Double-1>", self._assegna_da_tabella)
        ttk.Label(
            cornice,
            text="Doppio clic per passare il trasporto al carroponte successivo,\n"
            "oppure clic sul trasporto nel grafico per darlo a quello attivo.",
            foreground="#777777",
        ).pack(anchor=tk.W, pady=(2, 0))

        pulsanti = ttk.Frame(cornice)
        pulsanti.pack(fill=tk.X, pady=(8, 0))
        self.btn_annulla = ttk.Button(
            pulsanti, text="Annulla modifica", command=self._annulla_modifica
        )
        self.btn_annulla.pack(side=tk.LEFT)
        self.btn_verifica = ttk.Button(
            pulsanti, text="Verifica adesso", command=self._verifica_adesso
        )
        self.btn_verifica.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_riottimizza = ttk.Button(
            pulsanti,
            # Non "rifai il calcolo": rifa' solo la SUDDIVISIONE, tenendo il
            # numero di carroponti scelto qui sopra. Le modifiche fatte a mano
            # si perdono, e l'etichetta deve dirlo abbastanza.
            text="Ottimizza con questi carroponti",
            command=self._modifica_numero_carroponti,
        )
        self.btn_riottimizza.pack(side=tk.LEFT, padx=(6, 0))

        # -- barra di stato -------------------------------------------------
        piede = ttk.Frame(self, padding=(10, 4))
        piede.pack(fill=tk.X)
        self.etichetta_stato = ttk.Label(piede, text="Pronto")
        self.etichetta_stato.pack(side=tk.LEFT)
        self.avanzamento = ttk.Progressbar(piede, mode="indeterminate", length=180)
        self.avanzamento.pack(side=tk.RIGHT)

    def _grafico_vuoto(self, messaggio="Apri una linea per cominciare"):
        self.assi.clear()
        self.assi.set_xticks([])
        self.assi.set_yticks([])
        for lato in self.assi.spines.values():
            lato.set_visible(False)
        self.assi.text(
            0.5, 0.5, messaggio, ha="center", va="center", color="#999999", fontsize=12
        )

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _chiedi_file(self):
        percorso = filedialog.askopenfilename(
            title="Apri la definizione della linea",
            filetypes=[("File Excel", "*.xlsx"), ("Tutti i file", "*.*")],
        )
        if percorso:
            self._carica(percorso)

    def _carica(self, percorso: str):
        try:
            self.config_linea = leggi_problema(percorso)
        except Exception as e:
            self._errore("Il file non puo' essere letto", str(e))
            return
        # Assoluto e normalizzato: la finestra di dialogo di Tk restituisce le
        # barre al contrario ("C:/..."), e dalla riga di comando puo' arrivare
        # un percorso relativo. Cosi' quello che si legge e' un percorso vero,
        # copiabile e incollabile in Esplora risorse.
        percorso = os.path.normpath(os.path.abspath(percorso))
        self.percorso_file = percorso
        self.dati = None
        self.soluzione = None
        self.report = None
        self.T_corrente = None
        self.permanenze = {}
        self.assegnazione = {}
        self.incoerenze = []
        self.origine = ""
        self.modificato = False
        self.modifica_aperta = False
        self.verifica_viva = False
        self._annulla.clear()
        self._reimposta_grafico()  # altra linea, altre quote: si riparte da tutto
        d = self.config_linea.data
        self._mostra_percorso(percorso)
        self._scrivi_riepilogo(
            f"Linea: {percorso}\n"
            f"Stazioni: {d.n_stations}   Mosse: {d.n_moves}\n"
            f"Takt time ammesso: {d.takt_min:.1f} - {d.takt_max:.1f} s\n"
            f"Vasche: {', '.join(d.tanks)}\n\n"
            + (
                f"Zone indicate a mano: "
                f"{[(z.lo, z.hi) for z in self.config_linea.zone_manuali]}\n"
                if self.config_linea.zone_manuali
                else "Zone e numero di carroponti: da scegliere automaticamente\n"
            )
            + "\nScegli come costruire il ciclogramma."
        )
        self._svuota_tabella()
        self._grafico_vuoto("Nessun ciclogramma calcolato")
        self.tela.draw()
        self._stato("Linea caricata")
        self._aggiorna_stato_pulsanti()
        if self.config_linea.ciclogramma is not None:
            self._riprendi_ciclogramma()

    def _riprendi_ciclogramma(self):
        """Rimette in piedi il ciclogramma che il file si portava dietro.

        Il file di ingresso ne contiene i tre gradi di liberta', non le
        traiettorie: quelle si ricostruiscono, cosi' non possono essere in
        disaccordo con i valori da cui derivano. La scheda resta chiusa come
        sempre -- si guarda, e per intervenire si preme "Modifica"."""
        c = self.config_linea.ciclogramma
        d = self.config_linea.data
        self.T_corrente = c["T"]
        self.n_carroponti = max(1, min(c["n_carroponti"], d.n_moves))
        self.permanenze = {
            k: c["permanenze"].get(k, float(d.route[k].dwell_min))
            for k in range(1, d.n_moves)
        }
        self.assegnazione = dict(c["assegnazione"])
        self.carroponte_attivo = 0
        self.origine = "riletto dal file, gia' composto"
        self.modificato = False
        self.verifica_viva = False
        self.report = None
        self._annulla.clear()
        self.vista = (
            "ciclogramma" if len(self.assegnazione) == d.n_moves else "pettine"
        )
        self._ricomponi(
            "Ciclogramma ripreso dal file: premi Modifica per intervenire"
        )

    def _crea_modello(self):
        percorso = filedialog.asksaveasfilename(
            title="Dove salvare il modello da compilare",
            defaultextension=".xlsx",
            initialfile="linea.xlsx",
            filetypes=[("File Excel", "*.xlsx")],
        )
        if not percorso:
            return
        try:
            scrivi_modello(percorso)
        except Exception as e:
            self._errore("Impossibile scrivere il modello", str(e))
            return
        if messagebox.askyesno(
            TITOLO,
            f"Modello scritto in:\n{percorso}\n\n"
            "E' gia' compilato con una linea di esempio.\nVuoi aprirlo adesso?",
        ):
            self._carica(percorso)

    def _calcola_automatico(self):
        if not self._pronto_per_calcolare():
            return
        cfg = self.config_linea
        self._avvia_lavoro(
            "Cerco numero di carroponti e zone migliori...",
            lambda: self._risolvi(cfg),
        )

    def _risolvi(self, cfg):
        """Gira nel thread di lavoro: niente widget qui dentro."""
        d = cfg.data
        if cfg.zone_manuali is not None:
            sol = solve(d, time_limit_s=cfg.tempo_limite_s)
            zone = cfg.zone_manuali
        else:
            sol, zone, _ = solve_auto_hoists(
                d,
                max_hoists=cfg.max_carroponti,
                time_limit_per_candidate=cfg.tempo_limite_s,
            )
        if sol.status not in ("OPTIMAL", "FEASIBLE"):
            return ("nessuna", sol, None, None)
        dati = dataclasses.replace(d, zones=zone)
        return ("ok", sol, dati, verify_solution(dati, sol))

    def _salva(self):
        if self.soluzione is None:
            return
        if self.report is None:
            self._verifica_adesso()
        if self.report is None:
            return
        radice = os.path.splitext(self.percorso_file or "ciclogramma")[0]
        percorso = filedialog.asksaveasfilename(
            title="Dove salvare i risultati",
            defaultextension=".xlsx",
            initialfile=os.path.basename(radice) + "_risultati.xlsx",
            filetypes=[("File Excel", "*.xlsx")],
        )
        if not percorso:
            return
        try:
            # Un file solo: davanti il referto, dietro la linea col
            # ciclogramma dentro. Cosi' lo stesso file che si consegna e'
            # anche quello da riaprire per riprendere il lavoro, e non ci
            # sono due Excel da tenere insieme e da non confondere.
            scrivi_risultati(
                percorso,
                self.dati,
                self.soluzione,
                self.report,
                sorgente=self.percorso_file,
                cfg=self.config_linea,
                ciclogramma={
                    "T": self.T_corrente,
                    "n_carroponti": self.n_carroponti,
                    "permanenze": self.permanenze,
                    "assegnazione": self.assegnazione,
                },
            )
            png = os.path.splitext(percorso)[0] + ".png"
            self._salva_immagine(png)
        except Exception as e:
            self._errore("Impossibile salvare", str(e))
            return
        self._stato(f"Risultati salvati in {os.path.basename(percorso)}")
        messagebox.showinfo(
            TITOLO,
            f"Salvati:\n{percorso}\n{png}\n\n"
            f"L'Excel contiene anche la linea col ciclogramma: riaprilo con "
            f"'Apri linea...' per riprendere da qui.",
        )

    def _salva_immagine(self, percorso_png: str):
        """Scrive il PNG del CICLOGRAMMA, non di quello che c'e' a schermo.

        Il ciclogramma e' il documento che si consegna, e va consegnato anche
        se lo si e' composto guardando il pettine. Si disegna quindi su una
        figura a parte: fotografare la finestra legherebbe il risultato a cosa
        si stava guardando quando si e' premuto Salva."""
        figura = Figure(figsize=(13, 7), dpi=100)
        assi = figura.add_subplot(111)
        try:
            plot_cyclogram(
                self.dati,
                self.soluzione,
                n_cycles=2,
                title=f"Ciclogramma - {os.path.basename(self.percorso_file or '')}",
                ax=assi,
            )
        except ValueError:
            # niente da disegnare (per esempio nessun trasporto assegnato):
            # meglio l'immagine di quello che si vede che nessuna immagine
            self.figura.savefig(percorso_png, dpi=150, bbox_inches="tight")
            return
        figura.tight_layout()
        figura.savefig(percorso_png, dpi=150)

    # ------------------------------------------------------------------
    # Lavoro in background (il calcolo puo' durare parecchio)
    # ------------------------------------------------------------------

    def _avvia_lavoro(self, messaggio: str, funzione):
        self._lavoro_in_corso = True
        self._aggiorna_stato_pulsanti()
        self._stato(messaggio)
        self.avanzamento.start(12)

        def involucro():
            try:
                self._coda.put(("fatto", funzione()))
            except Exception:
                self._coda.put(("eccezione", traceback.format_exc()))

        threading.Thread(target=involucro, daemon=True).start()
        self.after(80, self._controlla_coda)

    def _controlla_coda(self):
        try:
            tipo, carico = self._coda.get_nowait()
        except queue.Empty:
            self.after(80, self._controlla_coda)
            return

        self.avanzamento.stop()
        self._lavoro_in_corso = False

        if tipo == "eccezione":
            self._stato("Calcolo fallito")
            self._aggiorna_stato_pulsanti()
            self._errore("Il calcolo si e' interrotto", carico)
            return

        esito, sol, dati, report = carico
        if esito == "nessuna":
            self.soluzione = None
            self._aggiorna_stato_pulsanti()
            self._stato("Nessuna soluzione trovata")
            self._grafico_vuoto("Nessuna soluzione")
            self.tela.draw()
            self._scrivi_riepilogo(
                f"Nessuna soluzione trovata (stato: {sol.status}).\n\n"
                "Cosa provare:\n"
                "  - allargare la tolleranza sul takt time\n"
                "  - aumentare il numero massimo di carroponti\n"
                "  - aumentare i posti delle vasche piu' lente\n"
                "  - infittire passo_controllo_distanza_mm da 200 a 100: la\n"
                "    distanza fra i carroponti viene verificata ogni tot mm, e\n"
                "    fra una verifica e l'altra il calcolo sta dal lato sicuro.\n"
                "    Con vasche vicine puo' bastare questo. Non e' un margine\n"
                "    di sicurezza: quello resta intero\n"
                "  - allungare il tempo limite di calcolo\n\n"
                "Oppure premi 'Calcola man' e componilo a mano: "
                "il verificatore dira' esattamente cosa manca."
            )
            self._svuota_tabella()
            return

        self.soluzione, self.dati, self.report = sol, dati, report
        self.incoerenze = []
        self.origine = (
            "calcolo automatico (ottimo)"
            if sol.status == "OPTIMAL"
            else "calcolo automatico (soluzione valida, non dimostrata ottima)"
        )
        self.modificato = False
        # Un risultato del solutore si LEGGE. Per modificarlo si preme
        # "Modifica": cosi' non lo si altera per sbaglio, e quel pulsante
        # smette di essere una scorciatoia per diventare il passaggio in cui
        # si dichiara l'intenzione.
        self.modifica_aperta = False
        # ...e si guarda come ciclogramma, sempre. Arrivando da "Calcola man"
        # la vista era rimasta sul pettine, che e' il foglio su cui si compone:
        # un risultato del solutore non si compone, si legge.
        self.vista = "ciclogramma"
        # Il solutore ha gia' verificato: da qui in poi il verdetto resta vivo.
        self.verifica_viva = True
        self._reimposta_grafico()
        self._stato_da_soluzione()
        self._sincronizza_campi()
        self._popola_tabelle()
        self._popola_verifica()
        self._mostra_ciclogramma()
        self._aggiorna_stato_pulsanti()
        self._stato(f"Ciclogramma pronto - T = {sol.T:.2f} s" + self._esito_breve())

    # ------------------------------------------------------------------
    # Il ciclogramma: comporlo, modificarlo, mostrarlo
    #
    # Tutto passa da _ricomponi(): cambio del takt, dei tempi in vasca,
    # dell'assegnazione, trascinamento sul grafico. Che il ciclogramma venga
    # dal solutore o sia stato composto da zero non fa differenza -- il
    # solutore fornisce solo lo stato di partenza, e da li' in poi e' lo
    # stesso oggetto modificato nello stesso modo.
    # ------------------------------------------------------------------

    def _stato_da_soluzione(self) -> bool:
        """Rilegge dalla soluzione del solutore i tre gradi di liberta' con cui
        la si modifica: takt time, tempi in vasca, assegnazione delle mosse.

        I tempi in vasca sono le differenze della catena dei prelievi meno la
        durata del trasporto. Ricomporre il ciclogramma da questi valori
        restituisce esattamente lo stesso ciclogramma -- verificato: stesso
        takt, stesso esito, nessuna incoerenza. E' il fatto che rende
        possibile una pagina sola invece di due."""
        d, sol = self.dati, self.soluzione
        tempi = list(sol.actual_time)
        if len(tempi) < d.n_moves or not d.zones:
            return False
        self.T_corrente = sol.T
        self.permanenze = {
            k: tempi[k] - (tempi[k - 1] + d.loaded_leg_seconds(k - 1))
            for k in range(1, d.n_moves)
        }
        self.assegnazione = {
            k: h for h, z in enumerate(d.zones) for k in range(z.lo, z.hi + 1)
        }
        self.n_carroponti = len(d.zones)
        self.carroponte_attivo = 0
        self._annulla.clear()
        return True

    def _vai_a_modifica(self):
        """Apre il ciclogramma che c'e' alla modifica.

        Non sceglie fra una versione automatica e una manuale -- ce n'e' una
        sola -- ne' cambia qualcosa: sblocca la scheda e ci porta. E' il
        momento in cui si dichiara di voler mettere le mani su un risultato,
        che e' diverso dal guardarlo."""
        if self.soluzione is None:
            return
        self.modifica_aperta = True
        self._aggiorna_stato_pulsanti()  # prima si sblocca, poi si seleziona
        self.schede.select(1)
        self._stato(
            "Modifica: trascina un prelievo sul grafico, cambia un tempo in "
            "vasca, oppure clicca un trasporto per assegnarlo"
        )

    def _componi_da_zero(self):
        """Butta via tutto e riparte dai tempi minimi di processo."""
        if not self._pronto_per_calcolare():
            return
        d = self.config_linea.data
        self._reimposta_grafico()
        self.T_corrente = d.takt_min
        self.permanenze = manuale.permanenze_iniziali(d)
        self.n_carroponti = min(2, d.n_moves)
        # NIENTE assegnato: il pettine parte tutto grigio ed e' l'utente a
        # darlo ai carroponti una mossa per volta, che e' il modo in cui un
        # ciclogramma si traccia. Partire da una suddivisione gia' fatta
        # significava non avere mai niente "da assegnare" -- si restava a
        # correggere una proposta invece di comporre.
        self.assegnazione = {}
        self.carroponte_attivo = 0
        self.origine = "composto da zero"
        self.modificato = False
        # Si riparte da uno stato dichiaratamente provvisorio: il verdetto
        # arriva quando lo chiedi, non prima.
        self.verifica_viva = False
        self.report = None
        self._annulla.clear()
        # Si compone sul PETTINE: e' li' che stanno i trasporti su cui si fa
        # clic. Il ciclogramma disegna le traiettorie dei carroponti, e senza
        # nessuna mossa assegnata sarebbe un riquadro vuoto.
        self.vista = "pettine"
        self.modifica_aperta = True
        self._ricomponi(
            "Composizione da zero: fai clic sui trasporti per assegnarli"
        )
        self.schede.select(1)

    def _ricomponi(self, descrizione: str = "", prima=None):
        """Ricostruisce il ciclogramma dallo stato e rimette tutto a schermo.

        Non rifiuta mai niente: `manuale.componi` disegna anche l'impossibile.
        Rifiutare una modifica vorrebbe dire rimettere i controlli proprio
        dove si e' scelto di toglierli -- e il verificatore li fa meglio."""
        if self.config_linea is None or self.T_corrente is None:
            return
        if self._lavoro_in_corso:
            # Ultima rete: qui passa OGNI modifica, quindi basta questa riga
            # perche' nessuna possa infilarsi mentre il solutore lavora --
            # anche da una strada che oggi non esiste.
            self._stato("Calcolo in corso: aspetta che finisca per modificare")
            return
        if prima is not None:
            self._annulla.append(prima)
            self.modificato = True
        self.soluzione, self.dati, self.incoerenze = manuale.componi(
            self.config_linea.data,
            self.T_corrente,
            self.permanenze,
            self.assegnazione,
            self.n_carroponti,
        )
        if self.verifica_viva:
            self.report = verify_solution(self.dati, self.soluzione)
            self._popola_verifica()
        else:
            self.report = None
        self._sincronizza_campi()
        self._popola_tabelle()
        self._mostra_ciclogramma()
        self._aggiorna_stato_pulsanti()
        if descrizione:
            self._stato(descrizione + self._esito_breve())

    def _esito_breve(self) -> str:
        if self.report is None:
            return ""
        return " - " + (
            "verifica superata"
            if self.report.ok
            else f"{len(self.report.errors)} errori"
        )

    def _istantanea(self):
        return (
            self.T_corrente,
            dict(self.permanenze),
            dict(self.assegnazione),
            self.n_carroponti,
        )

    def _annulla_modifica(self):
        if not self._annulla:
            self._stato("Niente da annullare")
            return
        (
            self.T_corrente,
            self.permanenze,
            self.assegnazione,
            self.n_carroponti,
        ) = self._annulla.pop()
        self._ricomponi("Modifica annullata")

    # -- i tre gradi di liberta', uno per volta -------------------------

    def _modifica_takt(self):
        if self.T_corrente is None:
            return
        try:
            nuovo = float(self.var_takt.get().replace(",", "."))
        except ValueError:
            self._stato("Il takt time deve essere un numero")
            return
        if nuovo <= 0:
            self._stato("Il takt time deve essere maggiore di zero")
            return
        if abs(nuovo - self.T_corrente) < 1e-9:
            return
        prima = self._istantanea()
        self.T_corrente = nuovo
        self._ricomponi(f"Takt time portato a {nuovo:.2f} s", prima)

    def _cambia_carroponti(self):
        """Spinbox: ridistribuisce le mosse in blocchi contigui.

        Cambiare il numero NON ridistribuisce le mosse: l'assegnazione la fa
        l'utente, e rifargliela sotto sarebbe buttare via il suo lavoro.
        Aggiungere un carroponte lo rende disponibile nel menu `attivo` --
        da li' in poi gli si danno le mosse a mano. Togliendone uno, le sue
        mosse passano all'ultimo rimasto, che e' l'unico modo di non
        scavalcare i vicini.

        Chi vuole una suddivisione gia' fatta ha il pulsante apposta."""
        if self.config_linea is None or self.T_corrente is None:
            return
        try:
            n = int(self.var_carroponti.get())
        except ValueError:
            return
        d = self.config_linea.data
        n = max(1, min(n, d.n_moves))
        if n == self.n_carroponti:
            return
        prima = self._istantanea()
        self.n_carroponti = n
        rimaste = {k: min(c, n - 1) for k, c in self.assegnazione.items()}
        self.assegnazione = rimaste
        if self.carroponte_attivo >= n:
            self.carroponte_attivo = n - 1
        self._ricomponi(f"Carroponti: {n}", prima)

    def _modifica_numero_carroponti(self):
        """Pulsante 'Ottimizza con questi carroponti': fa cercare al solutore
        la miglior suddivisione per il numero di carroponti scelto.

        Non e' una modifica come le altre -- riparte da zero e le modifiche
        fatte a mano si perdono -- e per questo e' un pulsante e non un
        effetto collaterale dello spinbox."""
        if self.config_linea is None or self._lavoro_in_corso:
            return
        n = max(1, min(self.n_carroponti, self.config_linea.data.n_moves))
        cfg = self.config_linea

        def lavoro():
            sol, zone = solve_auto_zones(
                cfg.data, n_hoists=n, time_limit_per_candidate=cfg.tempo_limite_s
            )
            if sol.status not in ("OPTIMAL", "FEASIBLE"):
                return ("nessuna", sol, None, None)
            dati = dataclasses.replace(cfg.data, zones=zone)
            return ("ok", sol, dati, verify_solution(dati, sol))

        self._avvia_lavoro(f"Cerco la miglior soluzione con {n} carroponti...", lavoro)

    def _modifica_permanenza(self, evento):
        riga = self.tabella_permanenze.identify_row(evento.y)
        colonna = self.tabella_permanenze.identify_column(evento.x)
        if not riga or colonna != "#2":
            return
        indice = self.tabella_permanenze.index(riga) + 1
        x, y, larghezza, altezza = self.tabella_permanenze.bbox(riga, colonna)
        editore = ttk.Entry(self.tabella_permanenze)
        editore.place(x=x, y=y, width=larghezza, height=altezza)
        editore.insert(0, f"{self.permanenze[indice]:.1f}")
        editore.select_range(0, tk.END)
        editore.focus_set()

        def conferma(_e=None):
            testo = editore.get()
            editore.destroy()
            prima = self._istantanea()
            try:
                valore = max(0.0, float(testo.replace(",", ".")))
            except ValueError:
                self._stato("Valore non valido")
                return
            self.permanenze[indice] = valore
            nome = self.config_linea.data.route[indice].tank_id
            self._ricomponi(f"{nome}: tempo in vasca {valore:.1f} s", prima)

        editore.bind("<Return>", conferma)
        editore.bind("<FocusOut>", lambda e: editore.destroy())
        editore.bind("<Escape>", lambda e: editore.destroy())

    def _assegna(self, k: int, prima) -> bool:
        """Da' la mossa k al carroponte attivo, se la rotaia lo consente."""
        d = self.config_linea.data
        if self.assegnazione.get(k) == self.carroponte_attivo:
            self._stato(
                f"La mossa {k} e' gia' del carroponte {self.carroponte_attivo + 1}"
            )
            return False
        prova = dict(self.assegnazione)
        prova[k] = self.carroponte_attivo
        motivo = manuale.perche_non_va(d, prova)
        if motivo:
            self._stato(f"Non si puo': {motivo}")
            return False
        self.assegnazione = prova
        self._ricomponi(
            f"Mossa {k} ({d.route[k].tank_id} -> {d.route[k + 1].tank_id}) "
            f"al carroponte {self.carroponte_attivo + 1}",
            prima,
        )
        return True

    def _assegna_da_tabella(self, evento):
        riga = self.tabella_assegnazione.identify_row(evento.y)
        if not riga:
            return
        k = int(self.tabella_assegnazione.item(riga, "values")[0])
        # a ogni doppio clic si passa al carroponte successivo: e' il modo piu'
        # rapido di correggere senza dover cambiare il carroponte attivo
        attuale = self.assegnazione.get(k, -1)
        d = self.config_linea.data
        # si prova il carroponte successivo, e se scavalcherebbe si continua a
        # girare: cosi' il doppio clic propone solo assegnazioni possibili
        for passo in range(1, self.n_carroponti + 1):
            candidato = (attuale + passo) % self.n_carroponti
            prova = dict(self.assegnazione)
            prova[k] = candidato
            if manuale.perche_non_va(d, prova) is None:
                prima = self._istantanea()
                self.assegnazione = prova
                self._ricomponi(
                    f"Mossa {k} al carroponte {candidato + 1}", prima
                )
                return
        self._stato(
            "Nessun altro carroponte puo' fare questa mossa senza scavalcare "
            "i vicini"
        )

    # -- presentazione --------------------------------------------------

    def _mostra_ciclogramma(self):
        if self.soluzione is None or self.dati is None:
            self._grafico_vuoto()
            self.tela.draw()
            return
        if self.vista == "pettine":
            self._disegna_pettine()
        else:
            self._disegna_traiettorie()
        self._aggiorna_banner_e_riepilogo()

    def _disegna_traiettorie(self):
        """Il ciclogramma vero e proprio: le traiettorie dei carroponti,
        ripetute su due cicli perche' si veda che il pattern si richiude."""
        vista = self._vista_corrente()
        self.assi.clear()
        for lato in self.assi.spines.values():
            lato.set_visible(True)
        try:
            plot_cyclogram(
                self.dati,
                self.soluzione,
                n_cycles=2,
                title=f"Ciclogramma - {os.path.basename(self.percorso_file or '')}",
                ax=self.assi,
            )
        except Exception as e:
            self._grafico_vuoto(f"Impossibile disegnare: {e}")
        self.figura.tight_layout()
        self._riapplica_vista(vista)
        self.tela.draw()

    def _disegna_pettine(self):
        d, T = self.config_linea.data, self.T_corrente
        vista = self._vista_corrente()
        self.assi.clear()
        for lato in self.assi.spines.values():
            lato.set_visible(True)

        etichette: dict[float, list[str]] = {}
        for st in d.route:
            y = d.tanks[st.tank_id].position
            etichette.setdefault(y, [])
            if st.tank_id not in etichette[y]:
                etichette[y].append(st.tank_id)
        for y in etichette:
            self.assi.axhline(y, color="#dddddd", linewidth=1, zorder=0)
        quote = sorted(etichette)
        self.assi.set_yticks(quote)
        self.assi.set_yticklabels(
            [f"{' / '.join(etichette[y])}\n{y:.0f} mm" for y in quote], fontsize=8
        )

        # -- il pettine: un pezzo per scalinata ----------------------------
        # Il pettine e' lo SCHELETRO e deve restare il disegno dominante: le
        # linee dei carroponti ci passano sopra, non lo coprono.
        scalinate = manuale.pettine(d, T, self.permanenze)
        for segs in scalinate:
            for s in segs:
                ts, xs = _sample_segment(s)
                k = self._mossa_del_segmento(s) if s.kind != "wait" else None
                c = self.assegnazione.get(k) if k is not None else None
                if c is None:
                    # Scheletro: soste in vasca e trasporti ancora liberi, tutti
                    # dello stesso grigio. Distinguerli servirebbe a niente --
                    # sono entrambi "cose che non ho ancora deciso".
                    self.assi.plot(ts, xs, color=_GRIGIO, linewidth=_SOTTILE, zorder=2)
                else:
                    self.assi.plot(
                        ts,
                        xs,
                        color=_HOIST_COLORS[c % len(_HOIST_COLORS)],
                        linewidth=_SPESSO,
                        zorder=4,
                    )

        # -- i rientri a vuoto dei carroponti, ripetuti su tutto il pettine -
        # Colorati come il carroponte a cui appartengono: assegnando una mossa
        # per volta serve vedere subito di CHI e' il rientro che compare, e
        # dove lo obbliga a passare. Restano sottili e tratteggiati, cosi' non
        # competono con i trasporti assegnati. Le attese non si disegnano
        # affatto: coinciderebbero con le soste del pettine, raddoppiando le
        # linee senza aggiungere niente.
        n_cicli = manuale.RIPETIZIONI_PREDEFINITE + 4
        for h, segs in enumerate(self.soluzione.segments_per_hoist):
            c = self._carro_della_zona(h)
            if c is None:
                continue  # zona senza mosse assegnate: non e' di nessuno
            colore = _HOIST_COLORS[c % len(_HOIST_COLORS)]
            for s in segs:
                if s.kind != "empty":
                    continue
                ts, xs = _sample_segment(s)
                for ciclo in range(n_cicli):
                    self.assi.plot(
                        ts + ciclo * T,
                        xs,
                        color=colore,
                        linewidth=_SOTTILE,
                        linestyle="--",
                        zorder=3,
                    )

        fine = manuale.RIPETIZIONI_PREDEFINITE * T + (
            scalinate[0][-1].t_end if scalinate else T
        )
        self.assi.set_xlim(0.0, fine)
        self.assi.set_xlabel("tempo [s]")
        self.assi.set_ylabel("posizione lungo la rotaia")
        self.assi.set_title(
            f"Pettine dei pezzi  —  takt time T = {T:.2f} s  —  "
            f"{manuale.RIPETIZIONI_PREDEFINITE} pezzi"
        )
        self.assi.grid(axis="x", color="#f0f0f0")
        self.assi.format_coord = lettura_coordinate

        legenda = [
            Line2D([0], [0], color=_GRIGIO, lw=_SOTTILE, label="da assegnare"),
            Line2D(
                [0], [0], color="#333333", lw=_SPESSO,
                label="assegnato a un carroponte",
            ),
            Line2D(
                [0], [0], color="#333333", lw=_SOTTILE, linestyle="--",
                label="il suo rientro a vuoto",
            ),
        ]
        self.assi.legend(
            handles=legenda, loc="upper left", fontsize=7, framealpha=0.9, ncol=3
        )
        self.figura.tight_layout()
        self._riapplica_vista(vista)
        self.tela.draw()

    def _carro_della_zona(self, indice: int) -> int | None:
        """Di quale carroponte e' la zona `indice`, o None se non contiene
        nessuna mossa assegnata.

        Le zone nascono da `manuale.zone_coprenti`, che riempie i buchi
        riportando avanti l'ultimo carroponte: con un'assegnazione parziale il
        numero della zona non e' per forza quello del carroponte, quindi il
        colore va preso dalle mosse che ci stanno dentro davvero."""
        if indice >= len(self.dati.zones):
            return None
        z = self.dati.zones[indice]
        for k in range(z.lo, z.hi + 1):
            if k in self.assegnazione:
                return self.assegnazione[k]
        return None

    def _mossa_del_segmento(self, s) -> int | None:
        """A quale mossa appartiene un tratto del pettine, dalle posizioni."""
        d = self.config_linea.data
        for k in range(d.n_moves):
            x0, x1 = d.station_position(k), d.station_position(k + 1)
            if (
                s.kind == "loaded"
                and abs(s.x_start - x0) < 1e-6
                and abs(s.x_end - x1) < 1e-6
            ):
                return k
            if s.kind == "pick" and abs(s.x_start - x0) < 1e-6:
                return k
            if s.kind == "release" and abs(s.x_start - x1) < 1e-6:
                return k
        return None

    def _sincronizza_campi(self):
        """Riporta nei campi i valori dello stato: dopo un calcolo, un
        annullamento o una modifica fatta dal grafico, i campi devono dire
        quello che il ciclogramma e' davvero."""
        if self.T_corrente is not None:
            self.var_takt.set(f"{self.T_corrente:.2f}")
        self.var_carroponti.set(str(self.n_carroponti))
        valori = [str(i + 1) for i in range(self.n_carroponti)]
        self.combo_attivo.configure(values=valori)
        if self.var_carro_attivo.get() not in valori:
            self.var_carro_attivo.set("1")
            self.carroponte_attivo = 0

    def _popola_tabelle(self):
        d = self.config_linea.data
        for r in self.tabella_permanenze.get_children():
            self.tabella_permanenze.delete(r)
        for k in range(1, d.n_moves):
            spec = d.route[k]
            self.tabella_permanenze.insert(
                "",
                tk.END,
                values=(
                    spec.tank_id,
                    f"{self.permanenze.get(k, 0.0):.1f}",
                    f"{spec.dwell_min:.0f}",
                    f"{spec.dwell_max:.0f}",
                ),
            )
        for r in self.tabella_assegnazione.get_children():
            self.tabella_assegnazione.delete(r)
        for k in range(d.n_moves):
            self.tabella_assegnazione.insert(
                "",
                tk.END,
                values=(
                    k,
                    d.route[k].tank_id,
                    d.route[k + 1].tank_id,
                    self.assegnazione[k] + 1 if k in self.assegnazione else "-",
                ),
            )

    def _aggiorna_banner_e_riepilogo(self):
        T, rep = self.T_corrente, self.report
        if rep is None:
            self.banner.configure(
                text=f"IN COMPOSIZIONE   -   T = {T:.2f} s   -   "
                "premi Verifica adesso per il verdetto",
                background="#d0e0f0",
                foreground="#1c4587",
            )
        elif rep.ok:
            self.banner.configure(
                text=f"VERIFICA SUPERATA   -   T = {T:.2f} s   -   "
                f"{3600.0 / T:.1f} pezzi/ora",
                background="#d9ead3",
                foreground="#274e13",
            )
        else:
            self.banner.configure(
                text=f"{len(rep.errors)} ERRORI   -   vedi la scheda Verifica",
                background="#f4cccc",
                foreground="#990000",
            )

        origine = self.origine + (", poi modificato a mano" if self.modificato else "")
        righe = [
            f"Origine: {origine}",
            "",
            f"Takt time:      {T:.2f} s",
            f"Produttivita':  {3600.0 / T:.1f} pezzi/ora",
            f"Carroponti:     {self.n_carroponti}",
        ]
        for h, z in enumerate(self.dati.zones):
            c = self._carro_della_zona(h)
            if c is None:
                continue  # zona senza mosse assegnate: non e' di nessuno
            righe.append(
                f"   {c + 1}: mosse {z.lo}-{z.hi}  "
                f"({self.dati.route[z.lo].tank_id} -> "
                f"{self.dati.route[z.hi + 1].tank_id})"
            )
        scoperte = [k for k in range(self.dati.n_moves) if k not in self.assegnazione]
        if scoperte:
            righe.append("")
            righe.append(
                f"Ancora da assegnare: {len(scoperte)} trasporti su "
                f"{self.dati.n_moves} (mosse {scoperte})."
            )
            righe.append(
                "Fai clic sul trasporto nel grafico, oppure doppio clic sulla"
            )
            righe.append("riga nella tabella Assegnazione.")
        righe.append("")
        if rep is None:
            righe.append(
                "I controlli sono sospesi finche' non premi 'Verifica adesso'.\n"
                "Da quel momento in poi il verdetto si tiene aggiornato da solo\n"
                "a ogni modifica."
            )
        else:
            if rep.min_separation != float("inf"):
                righe.append(
                    f"Distanza minima fra carroponti: {rep.min_separation:.0f} mm "
                    f"(richiesta {rep.required_separation:.0f} mm)"
                )
            else:
                righe.append("Un solo carroponte: nessuna coppia da controllare.")
            righe.append("")
            righe.append("VERIFICA: " + ("SUPERATA" if rep.ok else "NON SUPERATA"))
            righe.append(
                f"{len(rep.errors)} errori, {len(rep.warnings)} avvisi, "
                f"{len(rep.infos)} note"
            )
        self._scrivi_riepilogo("\n".join(righe))

    # -- verifica -------------------------------------------------------

    def _popola_verifica(self):
        self._svuota_tabella()
        for v in self.report.violations:
            self.tabella.insert(
                "",
                tk.END,
                values=(
                    _ETICHETTE_GRAVITA.get(v.severity, v.severity),
                    v.kind,
                    v.message,
                ),
                tags=(v.severity,),
            )
        self.schede.tab(2, text=f"Verifica ({len(self.report.violations)})")

    def _verifica_adesso(self):
        if self.soluzione is None or self.dati is None:
            return
        try:
            self.report = verify_solution(self.dati, self.soluzione)
        except Exception as e:
            self._errore("Verifica non eseguibile", str(e))
            return
        # da adesso in poi si tiene aggiornata da sola: chi l'ha chiesta una
        # volta la vuole anche dopo la prossima modifica
        self.verifica_viva = True
        self._popola_verifica()
        self.schede.select(2)
        self._aggiorna_banner_e_riepilogo()
        self._aggiorna_stato_pulsanti()
        self._stato("Verifica eseguita" + self._esito_breve())

    # -- clic e trascinamento sul grafico -------------------------------

    def _punti_prelievo(self):
        """(mossa, istante, posizione) di ogni prelievo disegnato.

        Sono gli stessi punti in tutte e due le viste, solo ripetuti in modo
        diverso: nel pettine una volta per pezzo, nel ciclogramma riportati
        dentro il periodo e ripetuti sui cicli visibili."""
        if self.config_linea is None or self.T_corrente is None:
            return []
        d, T = self.config_linea.data, self.T_corrente
        tempi = manuale.catena_pezzo(d, self.permanenze)
        punti = []
        for k in range(d.n_moves):
            y = d.station_position(k)
            if self.vista == "pettine":
                for p in range(manuale.RIPETIZIONI_PREDEFINITE):
                    punti.append((k, tempi[k] + p * T, y))
            else:
                for c in range(3):
                    punti.append((k, tempi[k] % T + c * T, y))
        return punti

    def _su_pressione(self, evento):
        if evento.inaxes is not self.assi or self.soluzione is None:
            return
        if self._lavoro_in_corso or not self.modifica_aperta:
            # Il grafico sta FUORI dalla scheda, quindi il cancello di
            # "Modifica" non lo coprirebbe: trascinare un prelievo su un
            # risultato appena calcolato lo modificherebbe senza che nessuno
            # abbia detto di volerlo.
            return
        if self._navigazione_attiva():
            return  # sta navigando: il clic e' della barra, non nostro
        if evento.xdata is None:
            return
        migliore, distanza_min, istante = None, 1e9, 0.0
        for k, t, y in self._punti_prelievo():
            px, py = self.assi.transData.transform((t, y))
            # in pixel: in coordinate dati un secondo e un metro non sono
            # paragonabili, e la tolleranza sarebbe assurda
            d = ((px - evento.x) ** 2 + (py - evento.y) ** 2) ** 0.5
            if d < distanza_min:
                migliore, distanza_min, istante = k, d, t
        if migliore is None or distanza_min > 30:
            return
        self._trascinamento = {
            "mossa": migliore,
            "t_iniziale": istante,
            "x_iniziale": evento.xdata,
            "px_iniziale": evento.x,
            "istantanea": self._istantanea(),
        }

    def _su_movimento(self, evento):
        if self._trascinamento is None or evento.xdata is None:
            return
        if self._trascinamento["mossa"] == 0:
            return  # il primo prelievo e' l'origine dei tempi: non si sposta
        delta = evento.xdata - self._trascinamento["x_iniziale"]
        nuovo = self._trascinamento["t_iniziale"] + delta
        if self._guida is not None:
            self._guida.remove()
        self._guida = self.assi.axvline(
            nuovo, color="#e67e22", linewidth=1.4, linestyle=":", zorder=10
        )
        self.tela.draw_idle()
        self._stato(f"Sposto di {delta:+.2f} s")

    def _su_rilascio(self, evento):
        if self._trascinamento is None:
            return
        trascinamento = self._trascinamento
        self._trascinamento = None
        if self._guida is not None:
            self._guida.remove()
            self._guida = None
            self.tela.draw_idle()
        k = trascinamento["mossa"]
        # Clic secco o trascinamento? Si misura in PIXEL: in secondi la soglia
        # dipenderebbe da quanto si e' ingrandito il grafico.
        if evento.x is None or abs(evento.x - trascinamento["px_iniziale"]) < 4:
            self._assegna(k, trascinamento["istantanea"])
            return
        if evento.xdata is None:
            return
        if k == 0:
            self._stato(
                "Il primo prelievo fissa l'origine dei tempi: si sposta "
                "cambiando i tempi in vasca a valle"
            )
            return
        delta = evento.xdata - trascinamento["x_iniziale"]
        nuovo = max(0.0, self.permanenze.get(k, 0.0) + delta)
        self.permanenze[k] = nuovo
        nome = self.config_linea.data.route[k].tank_id
        self._ricomponi(
            f"{nome}: tempo in vasca {nuovo:.1f} s ({delta:+.1f})",
            trascinamento["istantanea"],
        )

    def _mostra_dettaglio(self, _evento=None):
        selezione = self.tabella.selection()
        if not selezione:
            return
        valori = self.tabella.item(selezione[0], "values")
        messagebox.showinfo(f"{valori[0]} - {valori[1]}", valori[2])

    # ------------------------------------------------------------------
    # Utilita'
    # ------------------------------------------------------------------

    def _pronto_per_calcolare(self) -> bool:
        if self.config_linea is None:
            self._errore("Nessuna linea", "Apri prima un file Excel con la linea.")
            return False
        return True

    def _aggiorna_stato_pulsanti(self):
        c_e_linea = self.config_linea is not None and not self._lavoro_in_corso
        stato = tk.NORMAL if c_e_linea else tk.DISABLED
        # La scheda Ciclogramma e' aperta solo quando si sta davvero
        # lavorando al ciclogramma: dopo "Calcola man" o dopo "Modifica", e
        # mai mentre il solutore gira.
        #
        # Chiuderla vuol dire chiuderla davvero, non ingrigire i pulsanti che
        # contiene: i doppi clic sulle tabelle sono binding di evento e non
        # hanno uno stato da spegnere. E disabilitare la linguetta non basta
        # se e' quella aperta -- il contenuto resta a schermo e cliccabile --
        # quindi va anche lasciata.
        if self.modifica_aperta and not self._lavoro_in_corso:
            self.schede.tab(1, state=tk.NORMAL)
        else:
            if self.schede.index(self.schede.select()) == 1:
                self.schede.select(0)
            self.schede.tab(1, state=tk.DISABLED)
        self.btn_auto.configure(state=stato)
        self.btn_proposta.configure(state=stato)
        # "Modifica" si abilita quando c'e' qualcosa da modificare, e basta:
        # non ha una sorgente da scegliere, perche' il ciclogramma corrente e'
        # uno solo (da dove venga lo dice il Riepilogo).
        c_e_ciclogramma = self.soluzione is not None and not self._lavoro_in_corso
        self.btn_salva.configure(
            state=tk.NORMAL if c_e_ciclogramma else tk.DISABLED
        )
        self.btn_modifica.configure(
            state=tk.NORMAL if c_e_ciclogramma else tk.DISABLED
        )
        self.btn_verifica.configure(
            state=tk.NORMAL if c_e_ciclogramma else tk.DISABLED
        )
        self.btn_riottimizza.configure(state=stato)
        self.btn_annulla.configure(
            state=tk.NORMAL if (self._annulla and not self._lavoro_in_corso) else tk.DISABLED
        )

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    # C'e' stato un mirino verticale che seguiva il puntatore. E' stato
    # tolto: per essere fluido sul pettine (centinaia di segmenti) usava il
    # blitting, cioe' una copia in cache dello sfondo da ridipingere sotto la
    # linea. Ogni volta che qualcos'altro ridisegnava la tela -- un
    # trascinamento, il pan della barra, il cambio di vista -- la cache
    # restava vecchia e finiva a schermo, lasciando pezzi di grafico
    # precedente sparsi in giro. La posizione del puntatore si legge comunque,
    # in basso sotto il grafico (vedi plotting.lettura_coordinate).

    def _segna_zoom(self):
        """L'utente ha scelto lui l'inquadratura: da qui in poi va rispettata."""
        self._zoom_utente = True

    def _azzera_zoom(self):
        """Si torna a inquadrare tutto (pulsante 'vista intera')."""
        self._zoom_utente = False

    def _reimposta_grafico(self):
        """Il grafico cambia natura -- altra linea, o passaggio fra calcolo
        automatico e disegno manuale. Oltre allo zoom si butta via anche la
        cronologia di navigazione: le viste memorizzate si riferiscono a un
        disegno che non c'e' piu', e 'indietro' porterebbe su una fetta a
        caso di quello nuovo."""
        self._zoom_utente = False
        if getattr(self, "barra_grafico", None) is not None:
            self.barra_grafico.update()

    def _vista_corrente(self):
        """Inquadratura da conservare attraverso il prossimo ridisegno,
        oppure None se va bene quella naturale."""
        if not self._zoom_utente:
            return None
        return self.assi.get_xlim(), self.assi.get_ylim()

    def _riapplica_vista(self, vista):
        if vista is None:
            return
        self.assi.set_xlim(vista[0])
        self.assi.set_ylim(vista[1])

    def _su_rotella(self, evento):
        """Zoom con la rotella, centrato dove sta il puntatore.

        Agisce sul solo asse dei tempi: le vasche sono poche e fisse, mentre
        il tempo e' la direzione in cui si cerca il dettaglio. Con Shift si
        zooma sulle posizioni, con Ctrl su tutti e due."""
        if evento.inaxes is not self.assi:
            return
        fattore = 1 / 1.3 if evento.button == "up" else 1.3
        tasto = evento.key or ""
        if "shift" not in tasto and evento.xdata is not None:
            x0, x1 = self.assi.get_xlim()
            self.assi.set_xlim(
                evento.xdata + (x0 - evento.xdata) * fattore,
                evento.xdata + (x1 - evento.xdata) * fattore,
            )
        if ("shift" in tasto or "control" in tasto) and evento.ydata is not None:
            y0, y1 = self.assi.get_ylim()
            self.assi.set_ylim(
                evento.ydata + (y0 - evento.ydata) * fattore,
                evento.ydata + (y1 - evento.ydata) * fattore,
            )
        self._segna_zoom()
        self.tela.draw_idle()

    def _navigazione_attiva(self) -> bool:
        """Vero quando e' selezionato lo zoom a rettangolo o il pan: in quel
        caso il clic serve a navigare, non a modificare il ciclogramma."""
        return bool(str(getattr(self.barra_grafico, "mode", "")))

    def _mostra_percorso(self, percorso: str | None):
        """Fa comparire il percorso completo del file di ingresso in barra e
        nel titolo della finestra.

        Nel titolo perche' la barra dei comandi ha spazio limitato: se il
        percorso e' lunghissimo li' viene tagliato, mentre il titolo lo mostra
        comunque (e resta leggibile anche con la finestra ridotta a icona)."""
        if not percorso:
            self.etichetta_file.configure(text="Nessuna linea caricata")
            self.title(TITOLO)
            return
        self.etichetta_file.configure(text=percorso)
        self.title(f"{TITOLO} - {percorso}")

    def _scrivi_riepilogo(self, testo: str):
        self.testo_riepilogo.configure(state=tk.NORMAL)
        self.testo_riepilogo.delete("1.0", tk.END)
        self.testo_riepilogo.insert("1.0", testo)
        self.testo_riepilogo.configure(state=tk.DISABLED)

    def _svuota_tabella(self):
        for riga in self.tabella.get_children():
            self.tabella.delete(riga)

    def _stato(self, testo: str):
        self.etichetta_stato.configure(text=testo)

    def _errore(self, titolo: str, dettaglio: str):
        messagebox.showerror(f"{TITOLO} - {titolo}", dettaglio)
        self._stato(titolo)

    def destroy(self):
        # Le icone dei pulsanti della barra del grafico sono immagini di Tk.
        # Se sopravvivono alla finestra, il garbage collector prova a
        # cancellarle su un interprete Tk che non esiste piu' e stampa un
        # traceback ("main thread is not in main loop"): innocuo, ma appare a
        # ogni chiusura e sembra un guasto. Si lasciano andare finche' Tk e'
        # ancora in piedi.
        barra = getattr(self, "barra_grafico", None)
        if barra is not None:
            for pulsante in getattr(barra, "_buttons", {}).values():
                pulsante._ntimage = None
            barra._buttons = {}
            self.barra_grafico = None
            barra.destroy()
            gc.collect()
        super().destroy()


def autotest(cartella: str | None = None) -> int:
    """Prova l'installazione da cima a fondo, senza intervento dell'utente:
    crea un modello, lo rilegge, calcola, verifica, salva.

    Serve soprattutto per l'eseguibile impacchettato: che si costruisca non
    vuol dire che funzioni -- OR-Tools porta librerie native che potrebbero
    non essere finite dentro, e ce ne si accorgerebbe solo al primo calcolo,
    in stabilimento. Da lanciare cosi':

        Ciclogrammi.exe --autotest

    Scrive un resoconto accanto ai file prodotti e restituisce 0 se tutto
    funziona."""
    import tempfile

    destinazione = cartella or tempfile.mkdtemp(prefix="ciclogrammi_prova_")
    os.makedirs(destinazione, exist_ok=True)
    resoconto = os.path.join(destinazione, "autotest.txt")
    righe = []

    def annota(testo):
        """Scrive subito su file, non alla fine. Se il programma si pianta --
        ed e' proprio quando serve saperlo -- un resoconto accumulato in
        memoria non arriverebbe mai su disco, e non si saprebbe nemmeno a che
        punto si e' fermato."""
        righe.append(testo)
        try:
            with open(resoconto, "w", encoding="utf-8") as f:
                f.write("\n".join(righe) + "\n")
        except Exception:
            pass

    esito = 1
    app = None
    try:
        linea = os.path.join(destinazione, "linea_di_prova.xlsx")
        scrivi_modello(linea)
        annota(f"modello Excel creato: {linea}")

        annota("apro la finestra...")
        app = Applicazione(linea)
        # Senza questo, un errore qualsiasi aprirebbe una finestra modale che
        # resta li' ad aspettare un clic che nessuno dara' mai: l'autotest
        # sembrerebbe piantato invece di dire cosa non va.
        app._errore = lambda titolo, dettaglio: annota(
            f"ERRORE - {titolo}: {dettaglio}"
        )
        annota("finestra aperta")
        for _ in range(200):
            app.update()
            if app.config_linea is not None:
                break
        if app.config_linea is None:
            annota("ERRORE: il file non e' stato caricato")
            raise RuntimeError("caricamento fallito")
        annota(f"linea letta: {app.config_linea.data.n_stations} stazioni")

        annota("avvio il calcolo (OR-Tools)...")
        app._calcola_automatico()
        import time as _t

        scadenza = _t.time() + 300
        while app._lavoro_in_corso and _t.time() < scadenza:
            app.update()
            _t.sleep(0.02)
        app.update()
        if app.soluzione is None:
            annota("ERRORE: nessuna soluzione (OR-Tools non funziona?)")
            raise RuntimeError("calcolo fallito")
        annota(
            f"calcolo riuscito: {len(app.dati.zones)} carroponti, "
            f"T = {app.soluzione.T:.2f} s"
        )
        annota(
            "verifica indipendente: "
            + ("SUPERATA" if app.report.ok else f"{len(app.report.errors)} errori")
        )

        uscita = os.path.join(destinazione, "risultati.xlsx")
        scrivi_risultati(uscita, app.dati, app.soluzione, app.report, sorgente=linea)
        png = os.path.join(destinazione, "ciclogramma.png")
        app.figura.savefig(png, dpi=110, bbox_inches="tight")
        annota(f"risultati salvati: {uscita}")
        annota(f"grafico salvato: {png}")

        if app.report.ok and os.path.getsize(uscita) > 5000:
            annota("")
            annota("ESITO: tutto funziona.")
            esito = 0
        else:
            annota("")
            annota("ESITO: qualcosa non torna, vedi sopra.")
    except Exception:
        annota("")
        annota("ESITO: interrotto da un errore.")
        annota(traceback.format_exc())
    finally:
        if app is not None:
            try:
                app.tela.get_tk_widget().destroy()
            except Exception:
                pass
            try:
                app.destroy()
            except Exception:
                pass

    try:
        print("\n".join(righe))
    except Exception:
        pass  # impacchettato senza console non c'e' nessuno stdout
    return esito


def main(argv=None):
    # Obbligatorio quando il programma e' impacchettato in un eseguibile: senza
    # questa riga ogni processo figlio rilancia l'eseguibile dall'inizio invece
    # di eseguire il proprio compito, e il programma si pianta senza dire nulla.
    multiprocessing.freeze_support()
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--autotest":
        return autotest(argv[1] if len(argv) > 1 else None)
    file_iniziale = argv[0] if argv else None
    try:
        app = Applicazione(file_iniziale)
        app.mainloop()
    except Exception:
        # Impacchettato in eseguibile non c'e' nessuna console: senza questo,
        # un errore all'avvio farebbe sparire il programma senza dire niente.
        dettaglio = traceback.format_exc()
        try:
            radice = tk.Tk()
            radice.withdraw()
            messagebox.showerror(
                f"{TITOLO} - errore imprevisto",
                "Il programma si e' interrotto.\n\n" + dettaglio,
            )
            radice.destroy()
        except Exception:
            print(dettaglio, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
