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

from excel_io import leggi_problema, scrivi_modello, scrivi_risultati
from model import (
    HoistZone,
    build_solution,
    estrai_gradi_di_liberta,
    proposta_semplice,
    solve,
    solve_auto_hoists,
    solve_auto_zones,
)
import manuale
from plotting import _HOIST_COLORS, _sample_segment, plot_cyclogram
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

        # -- stato modificabile del ciclogramma -----------------------------
        # Sono i soli gradi di liberta' che esistano: takt time, fase di
        # prelievo di ogni mossa, periodi di attesa in piu' per vasca, e
        # suddivisione delle mosse fra i carroponti. Tutto il resto e'
        # derivato, quindi non ha senso permettere di modificarlo.
        self.T_corrente: float | None = None
        self.fasi: dict[int, float] = {}
        self.giri_extra: dict[int, int] = {}
        self.zone_correnti: list = []
        self._annulla: list = []  # pila per il ripristino
        self._trascinamento = None
        self._guida = None
        # zoom: vero quando l'inquadratura l'ha scelta l'utente e va
        # conservata attraverso i ridisegni
        self._zoom_utente = False

        # -- disegno manuale ------------------------------------------------
        self.modo = "automatico"  # oppure "manuale"
        self.permanenze: dict[int, float] = {}
        self.assegnazione: dict[int, int] = {}
        self.n_carroponti_manuale = 2
        self.carroponte_attivo = 0
        self.incoerenze: list[str] = []

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

        self.btn_auto = ttk.Button(
            barra, text="Calcola automaticamente", command=self._calcola_automatico
        )
        self.btn_auto.pack(side=tk.LEFT)
        self.btn_proposta = ttk.Button(
            barra,
            text="Disegna a mano",
            command=self._avvia_manuale,
        )
        self.btn_proposta.pack(side=tk.LEFT, padx=(6, 0))

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

        # -- scheda: modifica ----------------------------------------------
        scheda_modifica = ttk.Frame(schede, padding=6)
        schede.add(scheda_modifica, text="Modifica")
        self._costruisci_scheda_modifica(scheda_modifica)

        # -- scheda: disegno manuale ---------------------------------------
        scheda_disegno = ttk.Frame(schede, padding=6)
        schede.add(scheda_disegno, text="Disegno")
        self._costruisci_scheda_disegno(scheda_disegno)

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

    def _costruisci_scheda_modifica(self, cornice):
        intestazione = ttk.Frame(cornice)
        intestazione.pack(fill=tk.X)
        ttk.Label(
            intestazione,
            text="Trascina i punti di prelievo sul grafico, oppure modifica\n"
            "i valori qui sotto. La verifica si aggiorna a ogni modifica.",
            foreground="#555555",
        ).pack(anchor=tk.W)

        riga = ttk.Frame(cornice)
        riga.pack(fill=tk.X, pady=(8, 4))
        ttk.Label(riga, text="Takt time [s]:").pack(side=tk.LEFT)
        self.var_takt = tk.StringVar()
        campo = ttk.Entry(riga, textvariable=self.var_takt, width=10)
        campo.pack(side=tk.LEFT, padx=(6, 2))
        campo.bind("<Return>", lambda e: self._modifica_takt())
        ttk.Button(riga, text="Applica", width=8, command=self._modifica_takt).pack(
            side=tk.LEFT
        )
        ttk.Label(riga, text="Carroponti:").pack(side=tk.LEFT, padx=(16, 4))
        self.var_carroponti = tk.StringVar()
        self.spin_carroponti = ttk.Spinbox(
            riga,
            from_=1,
            to=8,
            width=4,
            textvariable=self.var_carroponti,
            command=self._modifica_numero_carroponti,
        )
        self.spin_carroponti.pack(side=tk.LEFT)

        ttk.Label(cornice, text="Mosse", font=("", 9, "bold")).pack(
            anchor=tk.W, pady=(10, 2)
        )
        cornice_mosse = ttk.Frame(cornice)
        cornice_mosse.pack(fill=tk.BOTH, expand=True)
        self.tabella_mosse = ttk.Treeview(
            cornice_mosse,
            columns=("mossa", "da", "a", "carro", "prelievo", "giri"),
            show="headings",
        )
        for chiave, titolo, larghezza in [
            ("mossa", "n", 30),
            ("da", "da vasca", 100),
            ("a", "a vasca", 100),
            ("carro", "carrop.", 55),
            ("prelievo", "prelievo [s]", 80),
            ("giri", "giri", 40),
        ]:
            self.tabella_mosse.heading(chiave, text=titolo)
            self.tabella_mosse.column(
                chiave, width=larghezza, anchor=tk.W, stretch=(chiave in ("da", "a"))
            )
        scorri = ttk.Scrollbar(
            cornice_mosse, orient=tk.VERTICAL, command=self.tabella_mosse.yview
        )
        self.tabella_mosse.configure(yscrollcommand=scorri.set)
        self.tabella_mosse.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scorri.pack(side=tk.RIGHT, fill=tk.Y)
        self.tabella_mosse.bind("<Double-1>", self._modifica_cella)

        ttk.Label(
            cornice,
            text="Doppio clic su 'prelievo' o 'giri' per cambiarli.\n"
            "'giri' = periodi di attesa in vasca oltre il minimo.",
            foreground="#777777",
        ).pack(anchor=tk.W, pady=(4, 0))

        pulsanti = ttk.Frame(cornice)
        pulsanti.pack(fill=tk.X, pady=(8, 0))
        self.btn_annulla = ttk.Button(
            pulsanti, text="Annulla modifica", command=self._annulla_modifica
        )
        self.btn_annulla.pack(side=tk.LEFT)
        self.btn_riottimizza = ttk.Button(
            pulsanti,
            # non "da qui": il solutore riparte da zero e le modifiche fatte a
            # mano vengono perse. L'etichetta deve dirlo.
            text="Rifai il calcolo automatico",
            command=self._calcola_automatico,
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

    def _costruisci_scheda_disegno(self, cornice):
        ttk.Label(
            cornice,
            text="Le scalinate grigie sono i pezzi in lavorazione: una sosta\n"
            "per ogni vasca, ripetute a un takt time di distanza.\n"
            "Fai clic su un trasporto per assegnarlo al carroponte attivo:\n"
            "prende il suo colore e diventa piu' spesso.",
            foreground="#555555",
        ).pack(anchor=tk.W)

        riga = ttk.Frame(cornice)
        riga.pack(fill=tk.X, pady=(8, 2))
        ttk.Label(riga, text="Takt time [s]:").pack(side=tk.LEFT)
        self.var_takt_manuale = tk.StringVar()
        campo = ttk.Entry(riga, textvariable=self.var_takt_manuale, width=9)
        campo.pack(side=tk.LEFT, padx=(6, 2))
        campo.bind("<Return>", lambda e: self._ricomponi_manuale())
        ttk.Button(riga, text="Applica", width=8, command=self._ricomponi_manuale).pack(
            side=tk.LEFT
        )

        riga2 = ttk.Frame(cornice)
        riga2.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(riga2, text="Carroponti:").pack(side=tk.LEFT)
        self.var_n_carro_manuale = tk.StringVar(value="2")
        ttk.Spinbox(
            riga2,
            from_=1,
            to=8,
            width=4,
            textvariable=self.var_n_carro_manuale,
            command=self._cambia_carroponti_manuale,
        ).pack(side=tk.LEFT, padx=(6, 16))
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
            text="Doppio clic sul tempo per cambiarlo: le scalinate si spostano.",
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

        pulsanti = ttk.Frame(cornice)
        pulsanti.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            pulsanti, text="Verifica adesso", command=self._verifica_adesso
        ).pack(side=tk.LEFT)
        ttk.Button(
            pulsanti, text="Torna all'automatico", command=self._calcola_automatico
        ).pack(side=tk.LEFT, padx=(6, 0))

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

    def _crea_proposta(self):
        if not self._pronto_per_calcolare():
            return
        cfg = self.config_linea

        def lavoro():
            sol, dati = proposta_semplice(cfg.data)
            return ("ok", sol, dati, verify_solution(dati, sol))

        self._avvia_lavoro("Costruisco la proposta di partenza...", lavoro)

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
            scrivi_risultati(
                percorso,
                self.dati,
                self.soluzione,
                self.report,
                sorgente=self.percorso_file,
            )
            png = os.path.splitext(percorso)[0] + ".png"
            self.figura.savefig(png, dpi=150, bbox_inches="tight")
        except Exception as e:
            self._errore("Impossibile salvare", str(e))
            return
        self._stato(f"Risultati salvati in {os.path.basename(percorso)}")
        messagebox.showinfo(
            TITOLO,
            f"Salvati:\n{percorso}\n{png}",
        )

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
                "  - allungare il tempo limite di calcolo\n\n"
                "Oppure parti da una proposta semplice e aggiustala a mano: "
                "il verificatore dira' esattamente cosa manca."
            )
            self._svuota_tabella()
            if self.zone_correnti:
                self.var_carroponti.set(str(len(self.zone_correnti)))
            return

        self.soluzione, self.dati, self.report = sol, dati, report
        if self.modo != "automatico":
            self._reimposta_grafico()  # si torna dal pettine al ciclogramma
        self.modo = "automatico"
        self.incoerenze = []
        self._carica_stato_modificabile()
        self._mostra_risultato()
        self._aggiorna_stato_pulsanti()

    # ------------------------------------------------------------------
    # Presentazione del risultato
    # ------------------------------------------------------------------

    def _mostra_risultato(self):
        sol, dati, rep = self.soluzione, self.dati, self.report
        vista = self._vista_corrente()
        self.assi.clear()
        for lato in self.assi.spines.values():
            lato.set_visible(True)
        try:
            plot_cyclogram(
                dati,
                sol,
                n_cycles=2,
                title=f"Ciclogramma - {os.path.basename(self.percorso_file or '')}",
                ax=self.assi,
            )
        except Exception as e:
            self._grafico_vuoto(f"Impossibile disegnare: {e}")
        self.figura.tight_layout()
        self._riapplica_vista(vista)
        self.tela.draw()

        origine = {
            "OPTIMAL": "calcolo automatico (ottimo)",
            "FEASIBLE": "calcolo automatico (soluzione valida, non dimostrata ottima)",
            "PROPOSTA": "proposta di partenza, da aggiustare",
            "MANUALE": "composto a mano",
        }.get(sol.status, sol.status)

        righe = [
            f"Origine: {origine}",
            "",
            f"Takt time:      {sol.T:.2f} s",
            f"Produttivita':  {3600.0 / sol.T:.1f} pezzi/ora",
            f"Carroponti:     {len(dati.zones)}",
        ]
        for h, z in enumerate(dati.zones):
            righe.append(
                f"   {h + 1}: mosse {z.lo}-{z.hi}  "
                f"({dati.route[z.lo].tank_id} -> {dati.route[z.hi + 1].tank_id})"
            )
        righe.append("")
        if rep.min_separation != float("inf"):
            righe.append(
                f"Distanza minima fra carroponti: {rep.min_separation:.3f} m "
                f"(richiesta {rep.required_separation:.3f} m)"
            )
        else:
            righe.append("Un solo carroponte: nessuna coppia da controllare.")
        righe.append("")
        righe.append(
            "VERIFICA: " + ("SUPERATA" if rep.ok else "NON SUPERATA")
        )
        righe.append(
            f"{len(rep.errors)} errori, {len(rep.warnings)} avvisi, "
            f"{len(rep.infos)} note"
        )
        self._scrivi_riepilogo("\n".join(righe))

        self._svuota_tabella()
        for v in rep.violations:
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
        self.schede.tab(3, text=f"Verifica ({len(rep.violations)})")

        if rep.ok:
            self.banner.configure(
                text=f"VERIFICA SUPERATA   -   T = {sol.T:.2f} s   -   "
                f"{3600.0 / sol.T:.1f} pezzi/ora",
                background="#d9ead3",
                foreground="#274e13",
            )
        else:
            self.banner.configure(
                text=f"{len(rep.errors)} ERRORI   -   T = {sol.T:.2f} s   -   "
                f"vedi la scheda Verifica",
                background="#f4cccc",
                foreground="#990000",
            )
        self._popola_tabella_mosse()
        self._stato(
            f"Ciclogramma pronto - T = {sol.T:.2f} s - "
            + ("verifica superata" if rep.ok else "VERIFICA NON SUPERATA")
        )

    # ------------------------------------------------------------------
    # Disegno manuale
    # ------------------------------------------------------------------

    def _avvia_manuale(self):
        if not self._pronto_per_calcolare():
            return
        d = self.config_linea.data
        # dal ciclogramma (2 cicli) al pettine (14): un'inquadratura scelta
        # sull'uno non vuol dire piu' niente sull'altro
        self._reimposta_grafico()
        self.modo = "manuale"
        self.permanenze = manuale.permanenze_iniziali(d)
        self.T_corrente = d.takt_min
        self.n_carroponti_manuale = min(2, d.n_moves)
        self.assegnazione = manuale.assegnazione_iniziale(
            d, self.n_carroponti_manuale
        )
        self.carroponte_attivo = 0
        self.var_takt_manuale.set(f"{self.T_corrente:.2f}")
        self.var_n_carro_manuale.set(str(self.n_carroponti_manuale))
        self._aggiorna_elenco_carroponti()
        self.schede.select(2)
        self._ricomponi_manuale()

    def _aggiorna_elenco_carroponti(self):
        valori = [str(i + 1) for i in range(self.n_carroponti_manuale)]
        self.combo_attivo.configure(values=valori)
        if self.var_carro_attivo.get() not in valori:
            self.var_carro_attivo.set("1")
            self.carroponte_attivo = 0

    def _cambia_carroponti_manuale(self):
        try:
            n = int(self.var_n_carro_manuale.get())
        except ValueError:
            return
        d = self.config_linea.data
        self.n_carroponti_manuale = max(1, min(n, d.n_moves))
        # le mosse assegnate a carroponti che non esistono piu' tornano al primo
        for k, c in list(self.assegnazione.items()):
            if c >= self.n_carroponti_manuale:
                self.assegnazione[k] = self.n_carroponti_manuale - 1
        self._aggiorna_elenco_carroponti()
        self._ricomponi_manuale()

    def _ricomponi_manuale(self):
        """Ricostruisce il disegno. Nessuna verifica: qui l'utente compone
        liberamente, e anche un ciclogramma impossibile va mostrato."""
        d = self.config_linea.data
        try:
            T = float(self.var_takt_manuale.get().replace(",", "."))
            if T <= 0:
                raise ValueError
        except ValueError:
            self._stato("Il takt time deve essere un numero maggiore di zero")
            return
        self.T_corrente = T
        self.soluzione, self.dati, self.incoerenze = manuale.componi(
            d, T, self.permanenze, self.assegnazione, self.n_carroponti_manuale
        )
        self.zone_correnti = list(self.dati.zones)
        self.report = None
        self._disegna_pettine()
        self._popola_tabelle_disegno()
        self._banner_disegno()
        self._aggiorna_stato_pulsanti()

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
            [f"{' / '.join(etichette[y])}\n{y:.2f} m" for y in quote], fontsize=8
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
        # Restano grigi come lo scheletro: il colore in questo disegno vuol
        # dire "l'ho assegnato io", e il rientro non si assegna, viene da se'.
        # Quale carroponte lo faccia si legge dai trasporti colorati che
        # collega. Le attese non si disegnano affatto: coinciderebbero con le
        # soste del pettine, raddoppiando le linee senza aggiungere niente.
        n_cicli = manuale.RIPETIZIONI_PREDEFINITE + 4
        for segs in self.soluzione.segments_per_hoist:
            for s in segs:
                if s.kind != "empty":
                    continue
                ts, xs = _sample_segment(s)
                for ciclo in range(n_cicli):
                    self.assi.plot(
                        ts + ciclo * T,
                        xs,
                        color=_GRIGIO,
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
            f"Disegno manuale  —  takt time T = {T:.2f} s  —  "
            f"{manuale.RIPETIZIONI_PREDEFINITE} pezzi"
        )
        self.assi.grid(axis="x", color="#f0f0f0")
        from matplotlib.lines import Line2D

        legenda = [
            Line2D(
                [0], [0], color=_GRIGIO, lw=_SOTTILE, label="da assegnare"
            ),
            Line2D(
                [0], [0], color=_GRIGIO, lw=_SOTTILE, linestyle="--",
                label="rientro a vuoto",
            ),
            Line2D(
                [0], [0], color="#333333", lw=_SPESSO,
                label="assegnato a un carroponte",
            ),
        ]
        self.assi.legend(
            handles=legenda, loc="upper left", fontsize=7, framealpha=0.9, ncol=3
        )
        self.figura.tight_layout()
        self._riapplica_vista(vista)
        self.tela.draw()

    def _mossa_del_segmento(self, s) -> int | None:
        """A quale mossa appartiene un tratto del pettine, dalle posizioni."""
        d = self.config_linea.data
        for k in range(d.n_moves):
            x0, x1 = d.station_position(k), d.station_position(k + 1)
            if s.kind == "loaded" and abs(s.x_start - x0) < 1e-6 and abs(s.x_end - x1) < 1e-6:
                return k
            if s.kind == "pick" and abs(s.x_start - x0) < 1e-6:
                return k
            if s.kind == "release" and abs(s.x_start - x1) < 1e-6:
                return k
        return None

    def _clic_manuale(self, evento):
        """Assegna al carroponte attivo il trasporto piu' vicino al clic."""
        if evento.xdata is None or self.config_linea is None:
            return
        d = self.config_linea.data
        candidati = manuale.trasporti_cliccabili(d, self.T_corrente, self.permanenze)
        clic = (evento.x, evento.y)
        migliore, distanza_min = None, 1e9
        for k, t0, t1, x0, x1 in candidati:
            # distanza in pixel dal punto medio del trasporto
            px, py = self.assi.transData.transform(((t0 + t1) / 2, (x0 + x1) / 2))
            dist = ((px - clic[0]) ** 2 + (py - clic[1]) ** 2) ** 0.5
            if dist < distanza_min:
                migliore, distanza_min = k, dist
        if migliore is None or distanza_min > 30:
            return
        prima = self.assegnazione.get(migliore)
        self.assegnazione[migliore] = self.carroponte_attivo
        motivo = manuale.perche_non_va(d, self.assegnazione)
        if motivo:
            if prima is None:
                self.assegnazione.pop(migliore, None)
            else:
                self.assegnazione[migliore] = prima
            self._stato(f"Non si puo': {motivo}")
            return
        self._stato(
            f"Mossa {migliore} "
            f"({d.route[migliore].tank_id} -> {d.route[migliore + 1].tank_id}) "
            f"assegnata al carroponte {self.carroponte_attivo + 1}"
        )
        self._ricomponi_manuale()

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
            try:
                self.permanenze[indice] = max(0.0, float(testo.replace(",", ".")))
            except ValueError:
                self._stato("Valore non valido")
                return
            self._ricomponi_manuale()

        editore.bind("<Return>", conferma)
        editore.bind("<FocusOut>", lambda e: editore.destroy())
        editore.bind("<Escape>", lambda e: editore.destroy())

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
        for passo in range(1, self.n_carroponti_manuale + 1):
            candidato = (attuale + passo) % self.n_carroponti_manuale
            prova = dict(self.assegnazione)
            prova[k] = candidato
            if manuale.perche_non_va(d, prova) is None:
                self.assegnazione = prova
                self._ricomponi_manuale()
                return
        self._stato(
            "Nessun altro carroponte puo' fare questa mossa senza scavalcare "
            "i vicini"
        )

    def _popola_tabelle_disegno(self):
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
                    f"{self.permanenze[k]:.1f}",
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
                    self.assegnazione.get(k, "-") + 1
                    if k in self.assegnazione
                    else "-",
                ),
            )

    def _banner_disegno(self):
        # Nessun allarme mentre si disegna. I controlli sono sospesi per
        # scelta: segnalare i tratti impossibili a ogni clic vorrebbe dire
        # rimetterli, e a meta' -- perche' il giudizio serio (collisioni,
        # permanenze, capienze) lo da' solo 'Verifica adesso'.
        self.banner.configure(
            text=f"DISEGNO IN CORSO   -   T = {self.T_corrente:.2f} s   -   "
            "premi Verifica adesso per il report",
            background="#d0e0f0",
            foreground="#1c4587",
        )
        testo = [
            "Disegno manuale.",
            "",
            "Le scalinate grigie sono i pezzi: uno ogni takt time.",
            "Fai clic su un trasporto per assegnarlo al carroponte attivo:",
            "diventa colorato e piu' spesso.",
            "Le linee tratteggiate sono gli spostamenti a vuoto dei carroponti.",
            "",
            f"Takt time: {self.T_corrente:.2f} s",
            f"Carroponti: {self.n_carroponti_manuale}",
            "",
            "I controlli sono sospesi: componi come vuoi, poi premi "
            "'Verifica adesso' per il report completo.",
        ]
        self._scrivi_riepilogo("\n".join(testo))

    def _verifica_adesso(self):
        if self.soluzione is None or self.dati is None:
            return
        try:
            self.report = verify_solution(self.dati, self.soluzione)
        except Exception as e:
            self._errore("Verifica non eseguibile", str(e))
            return
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
        self.schede.tab(3, text=f"Verifica ({len(self.report.violations)})")
        self.schede.select(3)
        if self.report.ok and not self.incoerenze:
            self.banner.configure(
                text=f"VERIFICA SUPERATA   -   T = {self.T_corrente:.2f} s",
                background="#d9ead3",
                foreground="#274e13",
            )
        else:
            n = len(self.report.errors)
            self.banner.configure(
                # Il conteggio dei tratti impossibili non compare piu': durante
                # il disegno non si mostrano, e qui li ha gia' contati il
                # verificatore fra i propri errori.
                text=(
                    f"{n} ERRORI   -   vedi la scheda Verifica"
                    if n
                    else "IL DISEGNO NON TORNA   -   vedi la scheda Verifica"
                ),
                background="#f4cccc",
                foreground="#990000",
            )
        self._stato(
            "Verifica eseguita: "
            + ("superata" if self.report.ok else f"{len(self.report.errors)} errori")
        )
        self._aggiorna_stato_pulsanti()

    # ------------------------------------------------------------------
    # Modifica del ciclogramma
    # ------------------------------------------------------------------

    def _carica_stato_modificabile(self):
        """Estrae dalla soluzione corrente i suoi gradi di liberta'."""
        try:
            T, fasi, giri = estrai_gradi_di_liberta(self.dati, self.soluzione)
        except ValueError:
            self.T_corrente, self.fasi, self.giri_extra = None, {}, {}
            return
        self.T_corrente, self.fasi, self.giri_extra = T, fasi, giri
        self.zone_correnti = list(self.dati.zones)
        self._annulla.clear()

    def _istantanea(self):
        return (
            self.T_corrente,
            dict(self.fasi),
            dict(self.giri_extra),
            list(self.zone_correnti),
        )

    def _applica(self, descrizione: str, prima):
        """Ricostruisce il ciclogramma dallo stato modificabile e lo verifica.
        Se la disposizione non e' realizzabile, torna indietro: meglio un
        messaggio che un grafico che sparisce."""
        try:
            dati = dataclasses.replace(self.dati, zones=self.zone_correnti)
            sol = build_solution(
                dati, self.T_corrente, self.fasi, extra_periods=self.giri_extra
            )
            rep = verify_solution(dati, sol)
        except Exception as e:
            (
                self.T_corrente,
                self.fasi,
                self.giri_extra,
                self.zone_correnti,
            ) = prima
            self._stato(f"Modifica non applicabile: {e}")
            self._popola_tabella_mosse()
            return False
        self._annulla.append(prima)
        self.dati, self.soluzione, self.report = dati, sol, rep
        self._mostra_risultato()
        self._stato(
            f"{descrizione} - T = {sol.T:.2f} s - "
            + ("verifica superata" if rep.ok else f"{len(rep.errors)} errori")
        )
        return True

    def _modifica_takt(self):
        if self.soluzione is None:
            return
        try:
            nuovo = float(self.var_takt.get().replace(",", "."))
        except ValueError:
            self._stato("Il takt time deve essere un numero")
            return
        if nuovo <= 0:
            self._stato("Il takt time deve essere maggiore di zero")
            return
        prima = self._istantanea()
        self.T_corrente = nuovo
        # le fasi vivono in [0,T): accorciando il periodo vanno riportate dentro
        self.fasi = {k: v % nuovo for k, v in self.fasi.items()}
        self._applica(f"Takt time portato a {nuovo:.2f} s", prima)

    def _modifica_numero_carroponti(self):
        """Cambiare il numero di carroponti NON e' una modifica delle fasi: le
        fasi attuali sono state scelte per un'altra suddivisione e quasi mai
        restano realizzabili con una diversa. Si ricalcola quindi la migliore
        suddivisione per quel numero di carroponti, e da li' si riprende a
        modificare."""
        if self.config_linea is None or self._lavoro_in_corso:
            return
        try:
            n = int(self.var_carroponti.get())
        except ValueError:
            return
        n = max(1, min(n, self.config_linea.data.n_moves))
        if self.zone_correnti and n == len(self.zone_correnti):
            return
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

    def _modifica_cella(self, evento):
        if self.soluzione is None:
            return
        riga = self.tabella_mosse.identify_row(evento.y)
        colonna = self.tabella_mosse.identify_column(evento.x)
        if not riga or colonna not in ("#5", "#6"):
            return
        k = int(self.tabella_mosse.item(riga, "values")[0])
        campo = "prelievo" if colonna == "#5" else "giri"
        attuale = (
            f"{self.fasi[k]:.2f}"
            if campo == "prelievo"
            else str(self.giri_extra.get(k, 0))
        )
        x, y, larghezza, altezza = self.tabella_mosse.bbox(riga, colonna)
        editore = ttk.Entry(self.tabella_mosse)
        editore.place(x=x, y=y, width=larghezza, height=altezza)
        editore.insert(0, attuale)
        editore.select_range(0, tk.END)
        editore.focus_set()

        def conferma(_e=None):
            testo = editore.get()
            editore.destroy()
            prima = self._istantanea()
            try:
                if campo == "prelievo":
                    self.fasi[k] = float(testo.replace(",", ".")) % self.T_corrente
                else:
                    n = max(0, int(testo))
                    if n:
                        self.giri_extra[k] = n
                    else:
                        self.giri_extra.pop(k, None)
            except ValueError:
                self._stato("Valore non valido")
                return
            self._applica(f"Mossa {k}: {campo} aggiornato", prima)

        editore.bind("<Return>", conferma)
        editore.bind("<FocusOut>", lambda e: editore.destroy())
        editore.bind("<Escape>", lambda e: editore.destroy())

    def _annulla_modifica(self):
        if not self._annulla:
            self._stato("Niente da annullare")
            return
        (
            self.T_corrente,
            self.fasi,
            self.giri_extra,
            self.zone_correnti,
        ) = self._annulla.pop()
        dati = dataclasses.replace(self.dati, zones=self.zone_correnti)
        sol = build_solution(
            dati, self.T_corrente, self.fasi, extra_periods=self.giri_extra
        )
        self.dati, self.soluzione = dati, sol
        self.report = verify_solution(dati, sol)
        self._mostra_risultato()
        self._stato("Modifica annullata")

    # -- trascinamento dei punti sul grafico ---------------------------

    def _punti_prelievo(self):
        """(mossa, tempo, posizione) di ogni prelievo disegnato, ripetuto su
        tutti i cicli visibili."""
        if not self.fasi or self.T_corrente is None:
            return []
        punti = []
        for k, fase in self.fasi.items():
            y = self.dati.station_position(k)
            for ciclo in range(3):
                punti.append((k, fase + ciclo * self.T_corrente, y))
        return punti

    def _su_pressione(self, evento):
        if evento.inaxes is not self.assi or self.soluzione is None:
            return
        if self._navigazione_attiva():
            return  # sta navigando: il clic e' della barra, non nostro
        if self.modo == "manuale":
            self._clic_manuale(evento)
            return
        if not self.fasi:
            return
        # il confronto va fatto in PIXEL: in coordinate dati un secondo e un
        # metro non sono paragonabili, e la tolleranza sarebbe assurda
        clic = (evento.x, evento.y)
        migliore, distanza_min = None, 1e9
        for k, t, y in self._punti_prelievo():
            px, py = self.assi.transData.transform((t, y))
            d = ((px - clic[0]) ** 2 + (py - clic[1]) ** 2) ** 0.5
            if d < distanza_min:
                migliore, distanza_min = (k, t), d
        if migliore is None or distanza_min > 18:
            return
        k, t = migliore
        self._trascinamento = {
            "mossa": k,
            "t_iniziale": t,
            "x_iniziale": evento.xdata,
            "fase_iniziale": self.fasi[k],
            "istantanea": self._istantanea(),
        }
        self._stato(
            f"Trascino il prelievo della mossa {k} "
            f"({self.dati.route[k].tank_id} -> {self.dati.route[k + 1].tank_id})"
        )

    def _su_movimento(self, evento):
        if self.modo == "manuale" or self._trascinamento is None:
            return
        if evento.xdata is None:
            return
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
        if evento.xdata is None:
            self.tela.draw_idle()
            return
        delta = evento.xdata - trascinamento["x_iniziale"]
        if abs(delta) < 1e-6:
            self.tela.draw_idle()
            return
        k = trascinamento["mossa"]
        self.fasi[k] = (trascinamento["fase_iniziale"] + delta) % self.T_corrente
        self._applica(
            f"Mossa {k} spostata di {delta:+.2f} s", trascinamento["istantanea"]
        )

    def _popola_tabella_mosse(self):
        for riga in self.tabella_mosse.get_children():
            self.tabella_mosse.delete(riga)
        if not self.fasi:
            return
        carro_di = {}
        for h, z in enumerate(self.zone_correnti):
            for k in range(z.lo, z.hi + 1):
                carro_di[k] = h + 1
        for k in sorted(self.fasi):
            self.tabella_mosse.insert(
                "",
                tk.END,
                values=(
                    k,
                    self.dati.route[k].tank_id,
                    self.dati.route[k + 1].tank_id,
                    carro_di.get(k, "?"),
                    f"{self.fasi[k]:.2f}",
                    self.giri_extra.get(k, 0),
                ),
            )
        if self.T_corrente is not None:
            self.var_takt.set(f"{self.T_corrente:.2f}")
            self.var_carroponti.set(str(len(self.zone_correnti)))

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
        self.btn_auto.configure(state=stato)
        self.btn_proposta.configure(state=stato)
        self.btn_salva.configure(
            state=tk.NORMAL
            if (self.soluzione is not None and not self._lavoro_in_corso)
            else tk.DISABLED
        )

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

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
