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
import time
import traceback
from typing import Optional

import matplotlib
import numpy as np

matplotlib.use("TkAgg")

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from allinea_avvio import allinea_avvio, descrivi
from avvio import righe_di_riepilogo, trova_avvii
from excel_io import leggi_problema, scrivi_modello, scrivi_risultati
from model import (
    TEMPO_RIDUCI_SOSTE_S,
    Interruzione,
    diagnosi_zone,
    errore_pesato,
    rifinisci_soluzione,
    solve_auto_hoists,
    solve_auto_zones,
)
import manuale
from plotting import (
    _HOIST_COLORS,
    _sample_segment,
    disegna_avvio,
    eventi_del_trasporto,
    lettura_coordinate,
    plot_cyclogram,
)
from simulazione import FinestraSimulazione
from verify import verify_solution

TITOLO = "CraneStrike"

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


def _durata_leggibile(secondi: float) -> str:
    """Una durata scritta come la direbbe una persona.

    Sotto il minuto si danno i decimi, perche' fra 2 e 12 secondi la
    differenza si sente; sopra, i decimi non dicono piu' niente e i minuti
    si leggono a colpo d'occhio. Il secondo si scrive sempre, anche a zero:
    "2 min" e "2 min 0 s" sembrano due precisioni diverse, e chi confronta
    due calcoli vuole leggere lo stesso formato tutte le volte."""
    if secondi < 60.0:
        return f"{secondi:.1f} s".replace(".", ",")
    minuti, resto = divmod(int(round(secondi)), 60)
    return f"{minuti} min {resto} s"


def _cornice_scorrevole(genitore) -> ttk.Frame:
    """Una cornice che, se il contenuto non ci sta in altezza, si scorre con
    la barra a destra o con la rotellina. Restituisce la cornice INTERNA, in
    cui impacchettare il contenuto come in una cornice qualsiasi.

    Serve perche' il pannello di destra chiede piu' altezza di quella che ha
    una finestra normale, e Tk non scorre da se': taglia. A essere tagliati
    erano i pulsanti in fondo -- Annulla, Verifica, Ottimizza -- cioe' proprio
    quelli che si cercano.

    La cornice interna prende la larghezza della tela (cosi' i fill=X
    funzionano come prima) e almeno la sua altezza (cosi' gli expand=True si
    allargano quando lo spazio c'e', e si scorre solo quando non c'e')."""
    tela = tk.Canvas(
        genitore,
        highlightthickness=0,
        borderwidth=0,
        background=ttk.Style().lookup("TFrame", "background"),
    )
    barra = ttk.Scrollbar(genitore, orient=tk.VERTICAL, command=tela.yview)
    tela.configure(yscrollcommand=barra.set)
    barra.pack(side=tk.RIGHT, fill=tk.Y)
    tela.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    interna = ttk.Frame(tela)
    finestra = tela.create_window(0, 0, window=interna, anchor=tk.NW)

    def adatta(_evento=None):
        altezza = max(interna.winfo_reqheight(), tela.winfo_height())
        tela.itemconfigure(finestra, width=tela.winfo_width(), height=altezza)
        tela.configure(scrollregion=(0, 0, tela.winfo_width(), altezza))

    interna.bind("<Configure>", lambda e: adatta() if e.widget is interna else None)
    tela.bind("<Configure>", adatta)

    def rotella(evento):
        # Legata a "all", quindi arriva da ovunque: si scorre solo se il
        # puntatore sta sopra questa cornice. Le tabelle che hanno righe
        # nascoste si scorrono da sole, e scorrere anche la cornice farebbe
        # muovere due cose insieme.
        sotto = tela.winfo_containing(evento.x_root, evento.y_root)
        if sotto is None or not str(sotto).startswith(str(tela)):
            return
        if isinstance(sotto, ttk.Treeview) and sotto.yview() != (0.0, 1.0):
            return
        if isinstance(sotto, (ttk.Spinbox, ttk.Combobox)):
            return
        if tela.yview() != (0.0, 1.0):
            tela.yview_scroll(-1 if evento.delta > 0 else 1, "units")

    tela.bind_all("<MouseWheel>", rotella, add="+")
    return interna


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
    def __init__(self, file_iniziale: str | None = None, con_splash: bool = False):
        super().__init__()
        self.title(TITOLO)
        # Tenuta in un attributo: fuori da Windows e' un'immagine di Tk, che
        # senza riferimenti viene raccolta dal garbage collector -- e la
        # finestra torna all'icona predefinita.
        self.icona = _applica_icona(self)
        # La schermata di benvenuto sta davanti mentre la finestra si
        # costruisce DIETRO, nascosta: i tre secondi si contano da qui e il
        # tempo della costruzione ci sta dentro, invece di sommarsi.
        self._splash: _Splash | None = None
        if con_splash:
            self.withdraw()
            self._splash = _Splash(self)
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
        # Il modo di fermare il calcolo in corso: esiste solo mentre ce n'e'
        # uno, e ogni calcolo ha la sua -- una richiesta rimasta da quello
        # prima non deve fermare quello dopo appena parte.
        self._interruzione: Interruzione | None = None
        self._inizio_lavoro = 0.0
        # Quanto e' durato il calcolo che ha prodotto il ciclogramma che si sta
        # guardando, in secondi. None quando non viene da un calcolo -- una
        # linea riletta da file, o un ciclogramma composto da zero. Serve a
        # sapere se conviene allargare il tempo limite, e a capire se una linea
        # e' pesante da risolvere: sono le due domande che ci si pone davanti a
        # un risultato che non piace.
        self.durata_calcolo: float | None = None

        # -- i punti di avvio -------------------------------------------------
        # Gli istanti da cui la linea si puo' mettere in marcia: non uno, TUTTI
        # quelli che sbagliano uguale (vedi avvio.trova_avvii). Si tengono qui
        # perche' si rileggono da tre posti -- il grafico, il riepilogo e il
        # salvataggio -- e ricalcolarli in ognuno vorrebbe dire ricalcolarli a
        # ogni ridisegno, e soprattutto poter mostrare a schermo un istante e
        # salvarne un altro.
        #
        # `indice_avvio` e' quello che si sta guardando. Torna a zero appena il
        # ciclogramma cambia: sono istanti nuovi, e tenere il numero d'ordine
        # vecchio vorrebbe dire puntare a un altro momento del giro senza averlo
        # chiesto.
        self.avvii: list = []
        self.indice_avvio = 0

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
        # I punti di passaggio aggiunti a mano: `{"t", "x", "carro"}`, dove il
        # carroponte `carro` deve trovarsi durante un rientro a vuoto (None =
        # punto appoggiato sul grafico, ancora di nessuno). Non sono i punti
        # del pettine -- quelli vengono dalla ricetta e non si tolgono -- ma
        # un grado di liberta' in piu' del giro dei carroponti.
        self.passaggi: list[dict] = []
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
        # La finestra della simulazione, quando e' aperta. Non e' una scheda:
        # la si guarda ACCANTO al ciclogramma, non al posto suo, e cosi' si
        # puo' modificare da una parte e vedere l'effetto dall'altra.
        self.finestra_simulazione: FinestraSimulazione | None = None
        # La verifica, una volta chiesta, si tiene aggiornata da sola. Non
        # parte da sola: comporre da zero vuol dire passare per stati
        # dichiaratamente sbagliati, e un muro di errori rossi mentre si sceglie
        # la prima mossa non informa nessuno.
        self.verifica_viva = False

        self._costruisci_interfaccia()
        self._aggiorna_stato_pulsanti()
        attesa = 0
        if self._splash is not None:
            attesa = self._splash.restante_ms()
            self.after(attesa, self._chiudi_splash)
        if file_iniziale:
            # dopo lo splash: un errore di lettura aprirebbe un messaggio
            # sopra una finestra che ancora non si vede
            self.after(attesa + 100, lambda: self._carica(file_iniziale))

    def _chiudi_splash(self):
        if self._splash is not None:
            self._splash.destroy()
            self._splash = None
        self.deiconify()
        self.lift()
        self.focus_force()

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
        # COSA ottimizza "Calcola auto": il takt time piu' corto, oppure --
        # col takt fisso al teorico -- i tempi in vasca piu' vicini ai teorici.
        # Si legge dal file (parametro takt_fisso) e qui si puo' cambiare al
        # volo: e' una domanda che si fa alla stessa linea, non un'altra linea.
        self.var_takt_fisso = tk.BooleanVar(value=False)
        self.chk_takt_fisso = ttk.Checkbutton(
            barra,
            text="Takt fisso",
            variable=self.var_takt_fisso,
            command=self._cambia_takt_fisso,
        )
        self.chk_takt_fisso.pack(side=tk.LEFT, padx=(6, 0))
        # Accanto a "Calcola auto", perche' e' il suo contrario: una ricerca
        # automatica puo' durare decine di minuti, e prima l'unico modo di
        # rinunciarci era chiudere il programma. Acceso solo mentre si calcola.
        self.btn_ferma = ttk.Button(
            barra, text="Ferma", command=self._ferma_calcolo, state=tk.DISABLED
        )
        self.btn_ferma.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_proposta = ttk.Button(
            barra, text="Calcola man", command=self._componi_da_zero
        )
        self.btn_proposta.pack(side=tk.LEFT, padx=(6, 0))
        # larghezza fissa: l'etichetta cambia in "Fine modifica" quando la
        # modifica e' aperta, e senza non starebbe ferma
        self.btn_modifica = ttk.Button(
            barra, text="Modifica", width=13, command=self._vai_a_modifica
        )
        self.btn_modifica.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(barra, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=12
        )

        # Guardare il ciclogramma muoversi. Non e' un quarto modo di ottenerne
        # uno: e' il ciclogramma che c'e', mostrato come lo si vedrebbe dal
        # capannone. Percio' sta dopo il separatore, con il salvataggio: sono
        # tutte e due cose che si fanno a un ciclogramma gia' fatto.
        self.btn_simula = ttk.Button(
            barra, text="Simulazione", command=self._apri_simulazione
        )
        self.btn_simula.pack(side=tk.LEFT)

        # Scorre i punti di avvio EQUIVALENTI -- quelli che sbagliano uguale --
        # spostando la linea nera sul grafico. Non e' un'impostazione: nessuno
        # di loro e' migliore degli altri, e quale convenga lo sa chi conosce
        # l'impianto. Il pulsante serve a vederli tutti e fermarsi su quello che
        # gli torna.
        #
        # L'etichetta porta il conto ("Avvio 1 di 3"): dice da sola che ce ne
        # sono altri, che altrimenti non si saprebbe. Larghezza fissa, se no
        # ballerebbe passando da "1 di 3" a "1 di 1". Spento quando ce n'e' uno
        # solo: non c'e' niente dove andare.
        self.btn_avvio = ttk.Button(
            barra, text="Avvio", width=13, command=self._prossimo_avvio
        )
        self.btn_avvio.pack(side=tk.LEFT, padx=(6, 0))

        # Quando il punto di avvio e' solo approssimato, sposta di qualche
        # secondo il giro di qualche carroponte perche' diventi esatto (vedi
        # allinea_avvio). Il calcolo automatico lo fa da solo; il pulsante serve
        # ai ciclogrammi riletti da file o composti a mano. Acceso solo quando
        # c'e' qualcosa da allineare.
        self.btn_allinea = ttk.Button(
            barra, text="Allinea avvio", command=self._allinea_avvio
        )
        self.btn_allinea.pack(side=tk.LEFT, padx=(6, 0))

        self.btn_salva = ttk.Button(
            barra, text="Salva risultati...", command=self._salva
        )
        self.btn_salva.pack(side=tk.LEFT, padx=(6, 0))

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
        # Scorrevole: e' la scheda piu' alta, e in fondo ci sono i pulsanti.
        scheda_ciclogramma = ttk.Frame(schede)
        schede.add(scheda_ciclogramma, text="Ciclogramma")
        contenuto = ttk.Frame(_cornice_scorrevole(scheda_ciclogramma), padding=6)
        contenuto.pack(fill=tk.BOTH, expand=True)
        self._costruisci_scheda_ciclogramma(contenuto)

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
            columns=("vasca", "tempo", "teorico", "scarto", "min", "max"),
            show="headings",
            height=7,
        )
        for chiave, titolo, larghezza in [
            ("vasca", "vasca", 130),
            ("tempo", "tempo [s]", 80),
            ("teorico", "teorico", 65),
            ("scarto", "scarto", 60),
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
            "vengono dal teorico piu' o meno i delta: si possono sforare,\n"
            "la verifica lo dira'.",
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
            text="Doppio clic per passare il trasporto al carroponte successivo;\n"
            "dopo l'ultimo torna non assegnato. Sul grafico, clic sul trasporto\n"
            "per darlo al carroponte attivo, e di nuovo per toglierglielo.",
            foreground="#777777",
        ).pack(anchor=tk.W, pady=(2, 0))

        # -- punti di passaggio ---------------------------------------------
        # Si aggiungono scrivendo tempo e posizione, perche' e' cosi' che li
        # si legge su un ciclogramma di carta: "a 40 s deve essere a 4000 mm".
        # Nascono di nessuno, come i trasporti del pettine, e si danno a un
        # carroponte con lo stesso gesto: un clic, e un altro per toglierlo.
        ttk.Label(cornice, text="Punti di passaggio", font=("", 9, "bold")).pack(
            anchor=tk.W, pady=(8, 2)
        )
        riga_punto = ttk.Frame(cornice)
        riga_punto.pack(fill=tk.X)
        ttk.Label(riga_punto, text="tempo [s]:").pack(side=tk.LEFT)
        self.var_punto_t = tk.StringVar()
        campo_t = ttk.Entry(riga_punto, textvariable=self.var_punto_t, width=8)
        campo_t.pack(side=tk.LEFT, padx=(4, 8))
        ttk.Label(riga_punto, text="posizione [mm]:").pack(side=tk.LEFT)
        self.var_punto_x = tk.StringVar()
        campo_x = ttk.Entry(riga_punto, textvariable=self.var_punto_x, width=8)
        campo_x.pack(side=tk.LEFT, padx=(4, 8))
        for campo in (campo_t, campo_x):
            campo.bind("<Return>", lambda e: self._aggiungi_passaggio())
        ttk.Button(
            riga_punto, text="Aggiungi", width=9, command=self._aggiungi_passaggio
        ).pack(side=tk.LEFT)
        cornice_punti = ttk.Frame(cornice)
        cornice_punti.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.tabella_passaggi = ttk.Treeview(
            cornice_punti,
            columns=("tempo", "posizione", "carro"),
            show="headings",
            height=4,
        )
        for chiave, titolo, larghezza in [
            ("tempo", "tempo [s]", 90),
            ("posizione", "posizione [mm]", 110),
            ("carro", "carrop.", 60),
        ]:
            self.tabella_passaggi.heading(chiave, text=titolo)
            self.tabella_passaggi.column(
                chiave, width=larghezza, anchor=tk.W, stretch=(chiave == "posizione")
            )
        self.tabella_passaggi.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tabella_passaggi.bind("<Double-1>", self._passaggio_da_tabella)
        self.tabella_passaggi.bind("<Delete>", lambda e: self._togli_passaggi())
        ttk.Button(
            cornice_punti, text="Togli", width=7, command=self._togli_passaggi
        ).pack(side=tk.LEFT, anchor=tk.N, padx=(6, 0))
        ttk.Label(
            cornice,
            text="Il carroponte passa dal punto all'istante dato, durante un\n"
            "rientro a vuoto; due punti alla stessa posizione sono una sosta.\n"
            "Clic sul punto (o doppio clic qui) per darlo al carroponte attivo,\n"
            "trascinalo per spostarlo. Si tolgono solo i punti aggiunti.",
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
        # In fondo ma PRIMO nell'ordine di pack: pack da' lo spazio nell'ordine
        # in cui i widget sono stati impacchettati, e se il pannello di destra
        # chiede piu' altezza di quella che c'e' l'ultimo resta schiacciato a
        # zero. Era la barra di stato, e con lei la stima del tempo.
        piede.pack(side=tk.BOTTOM, fill=tk.X, before=self.pack_slaves()[0])
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
        # Dove ogni carroponte passa il tempo morto del rientro a vuoto,
        # quando la scelta e' gia' stata fatta da qualcuno (il solutore, o il
        # file da cui si riapre). None = decide la regola predefinita.
        self.attese = None
        # Le soste in una vasca IN MEZZO al rientro a vuoto, mossa per mossa
        # (model.SostaIntermedia). Vuoto = tutti i rientri sono diritti, che e'
        # il caso normale: qui non c'e' nessuna regola predefinita da invocare,
        # una sosta per strada la sa proporre solo il solutore.
        self.soste = {}
        self.passaggi = []
        self.incoerenze = []
        self.origine = ""
        self.durata_calcolo = None
        self.modificato = False
        self.modifica_aperta = False
        self.verifica_viva = False
        self._annulla.clear()
        self._reimposta_grafico()  # altra linea, altre quote: si riparte da tutto
        # La simulazione mostrava la linea di prima: altre vasche, altre
        # distanze. Non e' aggiornabile, va chiusa.
        if self.finestra_simulazione is not None:
            self.finestra_simulazione.destroy()
            self.finestra_simulazione = None
        d = self.config_linea.data
        self.var_takt_fisso.set(d.takt_fisso)
        self._mostra_percorso(percorso)
        self._scrivi_riepilogo(
            f"Linea: {percorso}\n"
            f"Stazioni: {d.n_stations}   Mosse: {d.n_moves}\n"
            f"Takt time teorico: {d.takt_nominale:.1f} s "
            f"(-{d.takt_delta_neg:.1f} / +{d.takt_delta_pos:.1f}), "
            f"ammesso {d.takt_min:.1f} - {d.takt_max:.1f} s\n"
            + (
                "Obiettivo: takt time FISSO al teorico, tempi in vasca il "
                "piu' vicino possibile ai teorici (pesi del foglio Percorso)\n"
                if d.takt_fisso
                else "Obiettivo: takt time piu' corto nella banda ammessa, "
                "poi, a quel takt, i tempi in vasca piu' vicini ai teorici\n"
            )
            + f"Vasche: {', '.join(d.tanks)}\n\n"
            + (
                "Portate dei carroponti (foglio Zone): "
                + ", ".join(
                    f"{h + 1}: {p.vasca_min} - {p.vasca_max}"
                    for h, p in enumerate(d.portate)
                )
                + "\nLe zone le sceglie il programma, dentro le portate\n"
                if d.portate
                else "Zone e numero di carroponti: da scegliere automaticamente\n"
            )
            + "\nScegli come costruire il ciclogramma."
        )
        self._svuota_tabella()
        self._banner_neutro("Nessun ciclogramma")
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
            k: c["permanenze"].get(k, float(d.route[k].nominale))
            for k in range(1, d.n_moves)
        }
        self.assegnazione = dict(c["assegnazione"])
        self.attese = dict(c["attese"]) if c.get("attese") else None
        self.soste = dict(c.get("soste") or {})
        self.passaggi = [dict(p) for p in c.get("passaggi") or []]
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

    def _cambia_takt_fisso(self):
        """Il selettore "Takt fisso": cambia l'obiettivo della linea caricata.

        Non tocca il ciclogramma che c'e': resta valido com'e', e cambia solo
        cosa cerchera' il prossimo "Calcola auto". Il riepilogo pero' si
        rinfresca, perche' dice quale dei due obiettivi e' in vigore."""
        if self.config_linea is None:
            self.var_takt_fisso.set(False)
            return
        fisso = self.var_takt_fisso.get()
        try:
            data = dataclasses.replace(self.config_linea.data, takt_fisso=fisso)
        except ValueError as e:
            # Col takt inchiodato al teorico una vasca puo' non starci piu' coi
            # suoi posti, e ProblemData lo dice subito: meglio qui che come un
            # INFEASIBLE muto dopo minuti di calcolo.
            self.var_takt_fisso.set(not fisso)
            self._errore("Takt fisso non applicabile", str(e))
            return
        self.config_linea = dataclasses.replace(self.config_linea, data=data)
        if self.dati is not None:
            self.dati = dataclasses.replace(self.dati, takt_fisso=fisso)
        self._stato(
            "Calcola auto cerchera' i tempi in vasca piu' vicini ai teorici, "
            f"con il takt time fisso a {data.takt_nominale:.1f} s"
            if fisso
            else "Calcola auto cerchera' il takt time piu' corto nella banda"
        )
        if self.soluzione is not None and self.T_corrente is not None:
            self._aggiorna_banner_e_riepilogo()

    def _calcola_automatico(self):
        if not self._pronto_per_calcolare():
            return
        cfg = self.config_linea
        self._avvia_lavoro(
            "Cerco numero di carroponti e zone migliori...",
            lambda interruzione: self._risolvi(cfg, interruzione),
        )

    def _segnala_tentativo(
        self,
        n_hoists: int,
        indice: int,
        totale: int,
        n_valide: int,
        best_T: Optional[float],
        best_errore: Optional[float] = None,
    ):
        """Chiamata dal solutore PRIMA di ogni tentativo, dal thread di lavoro.

        Non tocca widget: mette il messaggio nella coda, che e' l'unico modo
        sicuro di parlare con la finestra da un altro thread. Chi lo legge e'
        _controlla_coda."""
        self._coda.put(
            ("progresso", (n_hoists, indice, totale, n_valide, best_T, best_errore))
        )

    def _risolvi(self, cfg, interruzione: Interruzione):
        """Gira nel thread di lavoro: niente widget qui dentro."""
        d = cfg.data
        sol, zone, _ = solve_auto_hoists(
            d,
            max_hoists=cfg.max_carroponti,
            time_limit_per_candidate=cfg.tempo_limite_s,
            su_tentativo=self._segnala_tentativo,
            interruzione=interruzione,
        )
        if sol.status not in ("OPTIMAL", "FEASIBLE"):
            if interruzione.richiesta:
                # Niente diagnosi: sono altre risoluzioni, e chi ha premuto
                # Ferma non vuole aspettarne altre. E niente da diagnosticare:
                # la linea non e' stata dimostrata impossibile.
                return ("interrotto", sol, None, None)
            self._diagnostica(d, sol)
            return ("nessuna", sol, None, None)
        dati = dataclasses.replace(d, zones=zone)
        # Le passate sulla soluzione scelta: col takt libero, a takt trovato,
        # i tempi in vasca piu' vicini ai teorici; poi, se CP-SAT e' scaduto
        # prima dell'ottimo, via le soste inutili. Se non ci riescono, la
        # soluzione resta quella di prima.
        if not d.takt_fisso:
            self._coda.put(
                ("stato", "Avvicino i tempi in vasca ai teorici, a takt trovato...")
            )
        elif sol.status == "FEASIBLE" and sol.raw.get("n_soste"):
            self._coda.put(("stato", "Tolgo le soste per strada che non servono..."))
        sol = rifinisci_soluzione(
            dati,
            sol,
            time_limit_s=cfg.tempo_limite_s,
            time_limit_soste_s=min(cfg.tempo_limite_s, TEMPO_RIDUCI_SOSTE_S),
            interruzione=interruzione,
        )
        sol = self._allinea_nel_lavoro(dati, sol, interruzione)
        return ("ok", sol, dati, verify_solution(dati, sol))

    def _allinea_nel_lavoro(self, dati, sol, interruzione: Interruzione):
        """Se il punto di avvio e' solo approssimato, prova a renderlo esatto
        spostando di qualche secondo il giro di qualche carroponte (vedi
        allinea_avvio). Gira nel thread di lavoro; se non ci riesce, o se il
        calcolo e' stato fermato, la soluzione resta quella che era."""
        if sol.raw.get("interrotto") or interruzione.richiesta:
            return sol
        self._coda.put(("stato", "Cerco un punto di avvio esatto..."))
        try:
            allineato = allinea_avvio(dati, sol)
        except Exception:  # un ritocco non deve mai far perdere il calcolo
            return sol
        return sol if allineato is None else allineato.soluzione

    def _diagnostica(self, d, sol):
        """Perche' non si e' trovato niente. Gira nel thread di lavoro.

        Si indaga sulla suddivisione col carico piu' equilibrato fra quelle
        provate con il NUMERO PIU' ALTO di carroponti: e' quella che aveva piu'
        margine, quindi cio' che blocca lei blocca a maggior ragione le altre.

        Costa qualche risoluzione in piu' su un calcolo che e' gia' fallito.
        Sembra molto, e non lo e': l'alternativa e' che l'utente ripeta lo
        stesso calcolo tre volte cambiando un parametro a caso ogni volta."""
        candidata = None
        for voce in sol.raw.get("hoist_sweep") or []:
            if voce.get("status") != "SKIPPED" and voce.get("candidata_tipica"):
                candidata = voce["candidata_tipica"]
        if candidata is None:
            return
        try:
            sol.raw["diagnosi"] = diagnosi_zone(
                d, candidata, time_limit_s=min(20.0, self.config_linea.tempo_limite_s)
            )
        except Exception as e:  # la diagnosi non deve mai far fallire il calcolo
            sol.raw["diagnosi"] = [f"(diagnosi non riuscita: {e})"]

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
                    "attese": self.attese,
                    "soste": self.soste,
                    "passaggi": self.passaggi,
                },
                # quello che si sta guardando, non il primo: se l'utente ha
                # scorso i punti di avvio, il file deve dire quello che ha
                # scelto -- come il PNG che esce insieme
                avvio=self._avvio_corrente(),
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

    # ------------------------------------------------------------------
    # Simulazione
    # ------------------------------------------------------------------

    def _apri_simulazione(self):
        """Mostra il ciclogramma corrente in movimento.

        Non ricalcola niente e non modifica niente: legge la soluzione che c'e'
        e la anima. E' il controllo che nessun diagramma sa dare -- un
        carroponte che attraversa un altro sul ciclogramma e' un incrocio di
        linee da cercare, nella linea in movimento e' evidente."""
        if self.soluzione is None or self.dati is None:
            return
        if self.finestra_simulazione is not None:
            # gia' aperta: la si porta davanti aggiornata, invece di aprirne
            # una seconda che mostrerebbe la stessa cosa
            self._aggiorna_simulazione()
            self.finestra_simulazione.lift()
            self.finestra_simulazione.focus_force()
            return
        try:
            finestra = FinestraSimulazione(
                self,
                self.dati,
                self.soluzione,
                carri=self._carri_delle_zone(),
                titolo_linea=os.path.basename(self.percorso_file or ""),
                avvio_t=self._t_avvio(),
            )
        except Exception as e:
            self._errore("Impossibile simulare", str(e))
            return
        self.finestra_simulazione = finestra
        finestra.bind("<Destroy>", self._simulazione_chiusa)
        self._stato("Simulazione aperta: si aggiorna da sola se modifichi il ciclogramma")

    def _simulazione_chiusa(self, evento):
        # <Destroy> arriva anche per ogni widget interno della finestra: solo
        # quello della finestra stessa vuol dire che e' stata chiusa.
        if evento.widget is self.finestra_simulazione:
            self.finestra_simulazione = None

    def _aggiorna_simulazione(self):
        """Passa alla simulazione il ciclogramma di adesso.

        Si chiama dopo OGNI ricomposizione: una simulazione che continua a
        mostrare il ciclogramma di prima, mentre a fianco se ne modifica un
        altro, sarebbe peggio di non averla."""
        if self.finestra_simulazione is None:
            return
        if self.soluzione is None or self.dati is None:
            return
        try:
            self.finestra_simulazione.aggiorna(
                self.dati,
                self.soluzione,
                carri=self._carri_delle_zone(),
                avvio_t=self._t_avvio(),
            )
        except Exception:
            # un ciclogramma a meta' puo' non essere simulabile (per esempio
            # senza nessuna mossa assegnata): la finestra resta com'e' invece
            # di far cadere la modifica che si stava facendo
            pass

    def _carri_delle_zone(self) -> dict[int, int | None]:
        """Quale carroponte corrisponde a ogni zona: serve alla simulazione per
        colorarli come il ciclogramma. Con un'assegnazione parziale i due
        numeri non coincidono (vedi `_carro_della_zona`)."""
        return {
            h: self._carro_della_zona(h) for h in range(len(self.dati.zones or []))
        }

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
                avvio=self._avvio_corrente(),
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
        """Lancia `funzione(interruzione)` in un thread a parte. L'interruzione
        e' nuova per ogni calcolo, e la riceve la funzione invece di leggerla
        da `self`: il thread non deve dipendere da uno stato della finestra che
        nel frattempo potrebbe cambiare."""
        self._lavoro_in_corso = True
        interruzione = self._interruzione = Interruzione()
        # Si cronometra QUI, e non dentro il solutore: quello che interessa e'
        # quanto ha aspettato chi guarda lo schermo, che comprende tutti i
        # tentativi di solve_auto_hoists e la verifica finale. Il tempo che
        # OR-Tools riporta in solution.raw e' solo l'ultima chiamata, e su una
        # linea che prova quattro numeri di carroponti direbbe una frazione del
        # vero. Orologio monotono: non salta se cambia l'ora di sistema.
        self._inizio_lavoro = time.monotonic()
        # Quanti tentativi il solutore ha gia' AVVIATO. Serve a stimare quanto
        # manca: al momento del tentativo k ne sono conclusi k-1, e il tempo
        # trascorso diviso quelli da' la durata media. Si conta su tutta la
        # ricerca, non sul numero di carroponti in corso: se la ricerca e' gia'
        # ripiegata su un carroponte in piu', anche i tentativi precedenti
        # dicono qualcosa su quanto e' pesante questa linea.
        self._tentativi_avviati = 0
        self._aggiorna_stato_pulsanti()
        self._stato(messaggio)
        # Barra indeterminata finche' non si sa quanti tentativi saranno: il
        # primo `su_tentativo` la fa passare a determinata. I lavori che non
        # passano dalla ricerca non segnalano niente, e la barra resta a
        # oscillare -- ed e' giusto: li' non c'e' un avanzamento da mostrare,
        # c'e' un'unica attesa.
        self.avanzamento.configure(mode="indeterminate")
        self.avanzamento.start(12)

        def involucro():
            try:
                self._coda.put(("fatto", funzione(interruzione)))
            except Exception:
                self._coda.put(("eccezione", traceback.format_exc()))

        threading.Thread(target=involucro, daemon=True).start()
        self.after(80, self._controlla_coda)

    def _ferma_calcolo(self):
        """Pulsante 'Ferma'. Chiede lo stop e basta: il risultato arriva dalla
        coda come quello di un calcolo finito, e lo gestisce _controlla_coda.

        Non e' istantaneo. Se il solutore sta cercando si ferma in una frazione
        di secondo; se si sta ancora costruendo il modello, finisce il pezzo in
        corso. Per questo lo si dice nella barra di stato: un clic che non
        sembra fare niente viene ripetuto."""
        if not self._lavoro_in_corso or self._interruzione is None:
            return
        self._interruzione.ferma()
        self._aggiorna_stato_pulsanti()
        self._stato("Interruzione in corso...")

    def _mostra_avanzamento(
        self,
        n_hoists: int,
        indice: int,
        totale: int,
        n_valide: int,
        best_T: Optional[float],
        best_errore: Optional[float] = None,
    ):
        """A che punto e' la ricerca, quanto manca, e cosa c'e' gia' in mano.

        I TENTATIVI RIMASTI si sanno esattamente: sono combinatoria piu' due
        prefiltri deterministici, e il solutore li ha gia' contati. Quello che
        non si sa e' quanto durera' ciascuno -- va da qualche centesimo a tutto
        il limite di tempo, secondo quanto e' difficile l'istanza -- e allora
        lo si MISURA su quelli gia' fatti.

        La stima resta una stima: i tentativi che finiscono INFEASIBLE sono
        molto piu' rapidi di quelli che trovano una soluzione e devono
        dimostrarla ottima, quindi il numero balla. Sulle linee di prova cade
        entro un fattore due, che basta a rispondere alla sola domanda che ci
        si pone davvero: aspetto, o mi alzo?

        La stima copre i tentativi rimasti CON QUESTO numero di carroponti, non
        l'intera ricerca: se anche l'ultimo fallisce si ricomincia con uno in
        piu' e il conteggio riparte da capo con un totale nuovo. E' una
        limitazione onesta -- quanti carroponti serviranno e' la domanda a cui
        la ricerca sta rispondendo -- e si vede, perche' il testo dice sempre a
        quale numero di carroponti si riferisce.

        Non si stima invece NIENTE prima di cominciare: l'unico numero
        calcolabile a priori sarebbe il limite superiore (tutti i tentativi
        possibili al limite di tempo), e sull'esempio darebbe sei minuti e
        mezzo contro sei secondi e mezzo reali. Un numero sessanta volte
        sbagliato non informa, spaventa.

        LE SOLUZIONI GIA' TROVATE sono l'altra meta' della risposta. Il tempo
        che manca dice quanto costa aspettare; non dice cosa si perde a non
        aspettare. Con "Ferma" si tiene la migliore soluzione trovata fino a
        quel punto, ma finche' non se ne e' trovata nessuna fermarsi vuol dire
        restare a mani vuote -- ed e' una differenza che l'utente non aveva
        modo di conoscere se non fermandosi e scoprendolo. Percio' il
        conteggio si dice sempre, anche e soprattutto quando e' zero.

        Col conteggio va il TAKT TIME della migliore, che e' poi il numero per
        cui si sta facendo tutto questo. Sapere che ci sono tre soluzioni dice
        che fermarsi e' sicuro; sapere che la migliore sta a 118 s dice se vale
        la pena aspettarne una quarta. Chi ha in mente il valore che gli serve
        riconosce da solo quando puo' smettere. Con il takt time FISSO il takt
        e' lo stesso per tutte, e il numero che dice quanto e' buona la
        migliore e' il suo scarto pesato dai tempi teorici."""
        if self.avanzamento.cget("mode") != "determinate":
            self.avanzamento.stop()
            self.avanzamento.configure(mode="determinate", maximum=totale)
        self.avanzamento.configure(maximum=totale, value=indice)

        conclusi = self._tentativi_avviati
        self._tentativi_avviati += 1
        testo = (
            f"{n_hoists} carropont{'e' if n_hoists == 1 else 'i'}: "
            f"tentativo {indice} di {totale}"
        )
        # Con meno di due tentativi conclusi la media e' un numero solo, e su
        # una grandezza cosi' dispersa non vuol dire niente: meglio non dire
        # un tempo che dirne uno sbagliato di dieci volte.
        if conclusi >= 2:
            media = (time.monotonic() - self._inizio_lavoro) / conclusi
            manca = media * (totale - indice + 1)
            testo += f" - ancora circa {_durata_leggibile(manca)}"
        if n_valide == 0:
            testo += " - nessuna soluzione ancora: fermando ora non resta niente"
        else:
            quante = (
                "1 soluzione trovata, T"
                if n_valide == 1
                else f"{n_valide} soluzioni trovate, migliore T"
            )
            # best_T non puo' essere None qui -- si conta valida solo una
            # soluzione che ha un takt time -- ma il formato lo direbbe con un
            # errore in mezzo a un calcolo lungo, e non vale il rischio.
            if best_T is None:
                testo += f" - {n_valide} gia' trovate: fermando ora resta la migliore"
            elif best_errore is not None:
                quante = (
                    "1 soluzione trovata, scarto pesato"
                    if n_valide == 1
                    else f"{n_valide} soluzioni trovate, migliore scarto pesato"
                )
                testo += (
                    f" - {quante} = {best_errore:.2f}: fermando ora resta quella"
                )
            else:
                testo += (
                    f" - {quante} = {best_T:.2f} s: fermando ora resta quella"
                )
        self._stato(testo)

    def _resoconto_fallimento(self, sol, durata: float) -> str:
        """Cosa dire quando non si trova niente.

        'Nessuna soluzione' e' la risposta meno utile che il programma possa
        dare: non dice se manca un secondo o un carroponte. Il registro dei
        tentativi c'e' gia' -- il solutore lo riempie -- e non veniva mostrato:
        e' cosi' che una ricerca che SALTAVA i quattro carroponti senza
        provarli poteva sembrare una linea impossibile.

        Il resoconto ha tre parti: cosa e' stato provato, perche' non riesce
        (se la diagnosi ha concluso qualcosa) e cosa si puo' fare."""
        righe = [
            f"NESSUNA SOLUZIONE TROVATA in {_durata_leggibile(durata)}.",
            "",
            "COSA E' STATO PROVATO",
        ]
        sweep = sol.raw.get("hoist_sweep") or []
        for voce in sweep:
            n = voce.get("n_hoists")
            stato = voce.get("status")
            if stato == "SKIPPED":
                righe.append(
                    f"  {n} carroponti: NON PROVATO - {voce.get('error', '')}"
                )
                continue
            per_stato = voce.get("per_stato") or {}
            dettaglio = ", ".join(
                f"{q} {s.lower()}" for s, q in sorted(per_stato.items())
            )
            scartate = (
                voce.get("n_skipped", 0)
                + voce.get("n_skipped_layout", 0)
                + voce.get("n_skipped_portata", 0)
            )
            riga = f"  {n} carroponti: {voce.get('n_tried', 0)} suddivisioni risolte"
            if dettaglio:
                riga += f" ({dettaglio})"
            if scartate:
                riga += f", {scartate} scartate senza risolverle"
            righe.append(riga)
            if voce.get("n_skipped_portata"):
                righe.append(
                    f"    di cui {voce['n_skipped_portata']} perche' un carroponte "
                    f"andrebbe oltre la portata del foglio Zone, ad esempio:"
                )
                righe.append(f"    {voce.get('portata_example')}")
        if not sweep:
            righe.append("  (nessun registro dei tentativi)")

        # UNKNOWN e INFEASIBLE vogliono due azioni opposte, e vanno separati.
        unknown = sum(
            (v.get("per_stato") or {}).get("UNKNOWN", 0) for v in sweep
        )
        if unknown:
            righe += [
                "",
                f"ATTENZIONE: {unknown} tentativi sono scaduti senza rispondere "
                "(UNKNOWN).",
                "Non sono stati dimostrati impossibili: allunga "
                "tempo_limite_per_tentativo_s",
                "e riprova, perche' fra quelli potrebbe esserci la soluzione.",
            ]

        diagnosi = sol.raw.get("diagnosi")
        if diagnosi:
            righe += ["", "PERCHE' NON RIESCE", *[f"  {r}" for r in diagnosi]]

        righe += [
            "",
            "COSA SI PUO' FARE",
            "  - allargare la tolleranza sul takt time "
            "(takt_delta_negativo_s / takt_delta_positivo_s)",
            *(
                [
                    "  - allargare le portate dei carroponti nel foglio Zone, o "
                    "aggiungere",
                    "    un carroponte (una riga)",
                ]
                if self.config_linea is not None and self.config_linea.data.portate
                else ["  - aumentare max_carroponti"]
            ),
            "  - aumentare i posti delle vasche piu' lente",
            "  - infittire passo_controllo_distanza_mm da 200 a 100: la distanza",
            "    fra i carroponti viene verificata ogni tot mm, e fra una verifica",
            "    e l'altra il calcolo sta dal lato sicuro. Con vasche vicine puo'",
            "    bastare questo. Non e' un margine di sicurezza: quello resta intero",
            "  - allungare tempo_limite_per_tentativo_s",
            "",
            "Oppure premi 'Calcola man' e componilo a mano: il verificatore dira'",
            "esattamente cosa manca, punto per punto.",
        ]
        return "\n".join(righe)

    def _controlla_coda(self):
        # Si svuota la coda invece di leggere un messaggio solo: i messaggi di
        # avanzamento arrivano piu' in fretta di quanto si controlli, e
        # leggerne uno per giro li farebbe accumulare -- la barra resterebbe
        # indietro rispetto al calcolo, che e' peggio di non averla.
        try:
            while True:
                tipo, carico = self._coda.get_nowait()
                if tipo == "stato":
                    # una fase del calcolo che non ha un avanzamento da contare
                    self.avanzamento.configure(mode="indeterminate")
                    self.avanzamento.start()
                    self._stato(carico)
                    continue
                if tipo != "progresso":
                    break
                self._mostra_avanzamento(*carico)
        except queue.Empty:
            self.after(80, self._controlla_coda)
            return

        self.avanzamento.stop()
        self.avanzamento.configure(mode="indeterminate", value=0)
        self._lavoro_in_corso = False
        durata = time.monotonic() - self._inizio_lavoro

        if tipo == "eccezione":
            self._stato("Calcolo fallito")
            self._aggiorna_stato_pulsanti()
            self._errore("Il calcolo si e' interrotto", carico)
            return

        self._interruzione = None
        esito, sol, dati, report = carico
        if esito == "interrotto":
            # Fermato senza niente in mano. Quello che c'era prima RESTA: chi
            # ha premuto Ferma ha rinunciato al calcolo nuovo, non al
            # ciclogramma che stava guardando -- e cancellarlo gli farebbe
            # pagare lo stop con il lavoro di prima.
            self._aggiorna_stato_pulsanti()
            self._stato(
                f"Calcolo interrotto dopo {_durata_leggibile(durata)} - "
                f"nessuna soluzione trovata fino a quel momento"
            )
            return
        if esito == "nessuna":
            self.soluzione = None
            self.report = None
            self.incoerenze = []
            self.verifica_viva = False
            self.durata_calcolo = None
            self._banner_neutro("NESSUNA SOLUZIONE   -   vedi il Riepilogo")
            self._aggiorna_stato_pulsanti()
            # Il tempo si dice anche qui, ed e' il caso in cui serve di piu':
            # se il calcolo ha consumato tutto il limite senza trovare niente,
            # allungarlo e' la prima cosa da provare -- e senza il numero non
            # si sa se il limite e' stato raggiunto o se la linea e' davvero
            # infattibile.
            self._stato(
                f"Nessuna soluzione trovata - "
                f"calcolo durato {_durata_leggibile(durata)}"
            )
            self._grafico_vuoto("Nessuna soluzione")
            self.tela.draw()
            self._scrivi_riepilogo(self._resoconto_fallimento(sol, durata))
            self._svuota_tabella()
            return

        self.soluzione, self.dati, self.report = sol, dati, report
        self.incoerenze = []
        self.durata_calcolo = durata
        interrotto = bool(sol.raw.get("interrotto"))
        if interrotto:
            # Anche se l'ultima risoluzione ha detto OPTIMAL: e' ottima per le
            # zone che ha provato, e le altre non sono state provate.
            self.origine = (
                "calcolo automatico interrotto (la migliore trovata prima "
                "dello stop: valida, non dimostrata ottima)"
            )
        else:
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
        self._stato(
            (
                f"Calcolo interrotto dopo {_durata_leggibile(durata)} - "
                f"migliore trovata finora: "
                if interrotto
                else f"Ciclogramma pronto in {_durata_leggibile(durata)} - "
            )
            + f"T = {sol.T:.2f} s"
            + (
                f", scarto pesato {sol.raw['errore_pesato']:.2f}"
                if sol.raw.get("errore_pesato") is not None
                else ""
            )
            + (
                f" - avvio reso esatto: "
                f"{descrivi(sol.raw['allineamento_avvio'])}"
                if sol.raw.get("allineamento_avvio")
                else ""
            )
            + self._esito_breve()
        )

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
        # Dove il solutore ha deciso di far sostare ciascun carroponte. Senza
        # questo la ricomposizione userebbe la regola predefinita e
        # disegnerebbe una traiettoria DIVERSA da quella appena verificata --
        # con collisioni diverse.
        self.attese = {k: v for p in sol.plans for k, v in p.attese.items()}
        self.soste = {
            k: v for p in sol.plans for k, v in p.soste_intermedie.items()
        }
        self.passaggi = [
            {"t": t, "x": x, "carro": d.zones.index(p.zone)}
            for p in sol.plans
            for punti in p.passaggi.values()
            for t, x in punti
        ]
        self.n_carroponti = len(d.zones)
        self.carroponte_attivo = 0
        self._annulla.clear()
        return True

    def _vai_a_modifica(self):
        """Apre alla modifica il ciclogramma che c'e', o la chiude se e' gia'
        aperta. Non sceglie fra una versione automatica e una manuale -- ce
        n'e' una sola -- ne' cambia niente: e' il momento in cui si dichiara di
        voler mettere le mani su un risultato, che e' diverso dal guardarlo."""
        if self.soluzione is None:
            return
        if self.modifica_aperta:
            self._chiudi_modifica()
            return
        self.modifica_aperta = True
        # Si modifica sul PETTINE, sempre, sia che il ciclogramma venga dal
        # solutore sia che lo si stia componendo. Il ciclogramma disegna le
        # traiettorie dei carroponti, e un trasporto che non e' ancora di
        # nessuno -- o che si e' appena tolto a qualcuno -- li' non compare:
        # resterebbe invisibile e per giunta cliccabile, che e' il peggio.
        # Nel pettine il pezzo passa comunque, grigio finche' nessuno lo porta.
        self.vista = "pettine"
        self._reimposta_grafico()  # altra scala dei tempi: si riparte da tutto
        self._aggiorna_stato_pulsanti()  # prima si sblocca, poi si seleziona
        self.schede.select(1)
        self._mostra_ciclogramma()
        self._stato(
            "Modifica: trascina un prelievo sul grafico, cambia un tempo in "
            "vasca, oppure clicca un trasporto per assegnarlo (e di nuovo per "
            "toglierlo)"
        )

    def _chiudi_modifica(self):
        """Torna a guardare il ciclogramma, e richiude la scheda.

        Serve perche' la modifica porta sul pettine: senza un modo di uscirne,
        chi ha ritoccato un tempo in vasca non rivedrebbe piu' il ciclogramma
        se non ricalcolandolo da capo. Non e' un interruttore fra due viste --
        quello e' stato tolto apposta -- ma l'uscita da uno stato di lavoro:
        chiudendo si torna a leggere, e il ciclogramma non si altera piu' per
        un clic di troppo."""
        self.modifica_aperta = False
        self.vista = "ciclogramma"
        self._reimposta_grafico()
        self._aggiorna_stato_pulsanti()
        self._mostra_ciclogramma()
        self._stato("Modifica chiusa: si guarda il ciclogramma")

    def _componi_da_zero(self):
        """Butta via tutto e riparte dai tempi teorici di processo."""
        if not self._pronto_per_calcolare():
            return
        d = self.config_linea.data
        self._reimposta_grafico()
        self.T_corrente = d.takt_nominale
        self.permanenze = manuale.permanenze_iniziali(d)
        self.n_carroponti = (
            len(d.portate) if d.portate is not None else min(2, d.n_moves)
        )
        # NIENTE assegnato: il pettine parte tutto grigio ed e' l'utente a
        # darlo ai carroponti una mossa per volta, che e' il modo in cui un
        # ciclogramma si traccia. Partire da una suddivisione gia' fatta
        # significava non avere mai niente "da assegnare" -- si restava a
        # correggere una proposta invece di comporre.
        self.assegnazione = {}
        # Dove i carri sostavano era una scelta fatta per il ciclogramma di
        # prima: qui non ce n'e' piu' nemmeno uno. Tenerla vorrebbe dire far
        # aspettare un carro in un posto deciso per un giro che non esiste --
        # e per la sosta in mezzo anche fargli fare una strada diversa.
        self.attese = None
        self.soste = {}
        self.passaggi = []
        self.carroponte_attivo = 0
        self.origine = "composto da zero"
        # non viene da un calcolo: il tempo di quello precedente non c'entra
        self.durata_calcolo = None
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

    def _ricomponi(
        self, descrizione: str = "", prima=None, tieni_rientri: bool = False
    ):
        """Ricostruisce il ciclogramma dallo stato e rimette tutto a schermo.

        Non rifiuta mai niente: `manuale.componi` disegna anche l'impossibile.
        Rifiutare una modifica vorrebbe dire rimettere i controlli proprio
        dove si e' scelto di toglierli -- e il verificatore li fa meglio.

        `tieni_rientri`: la modifica tocca solo i punti di passaggio, quindi
        attese e soste degli altri rientri restano buone e non si buttano. Chi
        sposta una pausa su un rientro non deve vedersi cambiare tutte le
        altre."""
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
        if prima is not None and not tieni_rientri:
            # Le soste erano state scelte per il ciclogramma di PRIMA: con le
            # fasi o l'assegnazione cambiate non descrivono piu' niente di
            # sensato (si aspetterebbe piu' a lungo del tempo disponibile).
            # Si torna alla regola predefinita, che si adatta da sola.
            self.attese = None
            # E le soste per strada se ne vanno con loro: erano il posto giusto
            # per il ciclogramma di prima. Senza attese non c'e' nemmeno da
            # chiedersi quando ci si fermava.
            self.soste = {}
        self.soluzione, self.dati, self.incoerenze = manuale.componi(
            self.config_linea.data,
            self.T_corrente,
            self.permanenze,
            self.assegnazione,
            self.n_carroponti,
            attese=self.attese,
            soste=self.soste,
            passaggi=self.passaggi,
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
            [dict(p) for p in self.passaggi],
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
            self.passaggi,
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
        if d.portate is not None and n != len(d.portate):
            # i carroponti sono quelli del foglio Zone: uno in piu' non ha una
            # portata, e togliendone uno le sue mosse andrebbero a un vicino
            # che magari non ci arriva
            self.var_carroponti.set(str(self.n_carroponti))
            self._stato(
                f"Non si puo': il foglio Zone dichiara {len(d.portate)} "
                f"carroponti. Per cambiarne il numero cambia le righe del foglio."
            )
            return
        if n == self.n_carroponti:
            return
        prima = self._istantanea()
        self.n_carroponti = n
        rimaste = {k: min(c, n - 1) for k, c in self.assegnazione.items()}
        self.assegnazione = rimaste
        # i punti seguono le mosse: quelli dei carroponti tolti all'ultimo
        for pt in self.passaggi:
            if pt["carro"] is not None:
                pt["carro"] = min(pt["carro"], n - 1)
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

        def lavoro(interruzione):
            sol, zone = solve_auto_zones(
                cfg.data,
                n_hoists=n,
                time_limit_per_candidate=cfg.tempo_limite_s,
                su_tentativo=self._segnala_tentativo,
                interruzione=interruzione,
            )
            if sol.status not in ("OPTIMAL", "FEASIBLE"):
                if interruzione.richiesta:
                    return ("interrotto", sol, None, None)
                return ("nessuna", sol, None, None)
            dati = dataclasses.replace(cfg.data, zones=zone)
            sol = self._allinea_nel_lavoro(dati, sol, interruzione)
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
        """Da' la mossa k al carroponte attivo -- o gliela toglie, se era gia'
        sua, e il trasporto torna grigio.

        Lo stesso gesto fa e disfa. Assegnare per sbaglio e' facile quanto un
        clic di troppo, e senza un modo di tornare indietro l'unica strada
        sarebbe ricominciare da capo. Il carroponte a cui si vuole togliere una
        mossa e' quasi sempre quello a cui si sta lavorando, cioe' proprio
        quello attivo: percio' la stessa manovra basta a tutte e due le cose,
        senza inventare un secondo tasto o un altro tipo di clic."""
        d = self.config_linea.data
        if self.assegnazione.get(k) == self.carroponte_attivo:
            prova = dict(self.assegnazione)
            del prova[k]
            self.assegnazione = prova
            # Togliere non puo' mai rendere impossibile una disposizione: i
            # carroponti si scavalcano per quello che FANNO, e una mossa in
            # meno non obbliga nessuno a passare da nessuna parte. Nessun
            # controllo, quindi -- e nessuna manovra che si rifiuta di tornare
            # indietro, che sarebbe la cosa peggiore.
            self._ricomponi(
                f"Mossa {k} ({d.route[k].tank_id} -> {d.route[k + 1].tank_id}) "
                f"tolta al carroponte {self.carroponte_attivo + 1}",
                prima,
            )
            return True
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
        d = self.config_linea.data
        # A ogni doppio clic si passa al carroponte successivo, e dopo l'ultimo
        # si torna a NESSUNO: cosi' il giro comprende anche il togliere, che
        # altrimenti dalla tabella non si potrebbe fare. Se un carroponte
        # scavalcherebbe i vicini si tira dritto al prossimo, quindi il doppio
        # clic propone solo cose possibili.
        giro = list(range(self.n_carroponti)) + [None]
        attuale = self.assegnazione.get(k)
        da = giro.index(attuale) if attuale in giro else len(giro) - 1
        for passo in range(1, len(giro) + 1):
            candidato = giro[(da + passo) % len(giro)]
            prova = dict(self.assegnazione)
            if candidato is None:
                prova.pop(k, None)
            else:
                prova[k] = candidato
            if candidato is None or manuale.perche_non_va(d, prova) is None:
                prima = self._istantanea()
                self.assegnazione = prova
                self._ricomponi(
                    f"Mossa {k} non assegnata"
                    if candidato is None
                    else f"Mossa {k} al carroponte {candidato + 1}",
                    prima,
                )
                return
        self._stato(
            "Nessun altro carroponte puo' fare questa mossa senza scavalcare "
            "i vicini"
        )

    # -- punti di passaggio ---------------------------------------------

    def _aggiungi_passaggio(self):
        """Appoggia sul grafico un punto nuovo, di nessuno: lo si da' a un
        carroponte con un clic, come un trasporto del pettine."""
        if self.config_linea is None or self.T_corrente is None:
            return
        try:
            t = float(self.var_punto_t.get().replace(",", "."))
            x = float(self.var_punto_x.get().replace(",", "."))
        except ValueError:
            self._stato("Tempo e posizione del punto devono essere numeri")
            return
        prima = self._istantanea()
        self.passaggi = sorted(
            self.passaggi + [{"t": t, "x": x, "carro": None}],
            key=lambda p: (p["t"], p["x"]),
        )
        self.var_punto_t.set("")
        self.var_punto_x.set("")
        self._ricomponi(
            f"Punto aggiunto a {t:.1f} s in {x:.0f} mm: fai clic sul grafico "
            f"per darlo al carroponte attivo",
            prima,
            tieni_rientri=True,
        )

    def _togli_passaggi(self):
        """Toglie i punti selezionati nella tabella. Solo quelli aggiunti a
        mano: i punti del pettine non stanno in questa tabella, e non ci
        sono altri modi di toglierli."""
        righe = self.tabella_passaggi.selection()
        if not righe:
            self._stato("Seleziona nella tabella i punti da togliere")
            return
        via = {self.tabella_passaggi.index(r) for r in righe}
        prima = self._istantanea()
        self.passaggi = [p for i, p in enumerate(self.passaggi) if i not in via]
        self._ricomponi(
            f"{len(via)} punt{'o tolto' if len(via) == 1 else 'i tolti'}",
            prima,
            tieni_rientri=True,
        )

    def _passaggio_da_tabella(self, evento):
        riga = self.tabella_passaggi.identify_row(evento.y)
        if riga:
            self._assegna_passaggio(
                self.tabella_passaggi.index(riga), self._istantanea()
            )

    def _assegna_passaggio(self, i: int, prima):
        """Da' il punto i al carroponte attivo, o glielo toglie se era gia'
        suo: lo stesso gesto dei trasporti (vedi `_assegna`)."""
        p = self.passaggi[i]
        if p["carro"] == self.carroponte_attivo:
            p["carro"] = None
            cosa = f"tolto al carroponte {self.carroponte_attivo + 1}"
        else:
            p["carro"] = self.carroponte_attivo
            cosa = f"al carroponte {self.carroponte_attivo + 1}"
        self._ricomponi(
            f"Punto {p['t']:.1f} s / {p['x']:.0f} mm {cosa}",
            prima,
            tieni_rientri=True,
        )

    def _ripetizioni_passaggi(self):
        """(indice, istante, posizione) di ogni punto di passaggio come lo si
        vede sul pettine: ripetuto a ogni takt time, perche' il carroponte ci
        ripassa a ogni giro -- e lo stesso vale per un punto ancora di
        nessuno, che e' periodico quanto quello che diventera'."""
        T = self.T_corrente
        if not T or self.vista != "pettine":
            return []
        n_cicli = manuale.RIPETIZIONI_PREDEFINITE + 4
        return [
            (i, p["t"] % T + c * T, p["x"])
            for i, p in enumerate(self.passaggi)
            for c in range(n_cicli)
        ]

    def _passaggio_sotto(self, evento):
        """Il punto di passaggio sotto al puntatore, o None. In PIXEL, come
        per i trasporti."""
        migliore, distanza_min = None, 1e9
        for i, t, x in self._ripetizioni_passaggi():
            px, py = self.assi.transData.transform((t, x))
            d = ((px - evento.x) ** 2 + (py - evento.y) ** 2) ** 0.5
            if d < distanza_min:
                migliore, distanza_min = i, d
        return migliore if distanza_min <= 9 else None

    # -- presentazione --------------------------------------------------

    def _aggiorna_avvii(self):
        """Ricalcola i punti di avvio del ciclogramma che c'e' adesso.

        Si chiama da un posto solo, prima di ogni ridisegno: il grafico, il
        riepilogo e il salvataggio devono mostrare lo STESSO istante, e tre
        calcoli separati in tre momenti diversi non lo garantirebbero.

        L'istante che si sta guardando si conserva soltanto se i punti di avvio
        non sono cambiati. Un ridisegno che non tocca il ciclogramma -- si passa
        da una vista all'altra, si riapre la simulazione -- non deve far saltare
        la linea nera altrove; un ciclogramma diverso invece ha istanti diversi,
        e il terzo di prima non e' il terzo di adesso."""
        prima = [a.t for a in self.avvii]
        self.avvii = (
            []
            if self.soluzione is None or self.dati is None
            else trova_avvii(self.dati, self.soluzione)
        )
        if [a.t for a in self.avvii] != prima:
            self.indice_avvio = 0
        elif self.avvii:
            self.indice_avvio %= len(self.avvii)

    def _avvio_corrente(self):
        """Il punto di avvio che si sta guardando, o None se non ce n'e'."""
        if not self.avvii:
            return None
        return self.avvii[self.indice_avvio % len(self.avvii)]

    def _t_avvio(self) -> float | None:
        """[s] l'istante del punto di avvio corrente, None se non ce n'e'."""
        a = self._avvio_corrente()
        return None if a is None else a.t

    def _prossimo_avvio(self):
        """Passa al punto di avvio successivo, e torna al primo dopo l'ultimo.

        Sono tutti equivalenti -- stesso errore -- quindi scorrerli in tondo e'
        la cosa giusta: non c'e' un ultimo oltre il quale si e' finito, c'e' un
        giro di istanti fra cui scegliere."""
        if len(self.avvii) < 2:
            return
        self.indice_avvio = (self.indice_avvio + 1) % len(self.avvii)
        a = self._avvio_corrente()
        self._stato(
            f"Punto di avvio {a.indice + 1} di {a.totale}: {a.t:.2f} s"
            + ("" if a.esatto else f"  (errore {a.errore:.2f} s)")
        )
        # Non passa da _mostra_ciclogramma: gli istanti sono gli stessi, cambia
        # solo quale si guarda, e ricalcolarli azzererebbe l'indice appena
        # mosso. La simulazione non va ricostruita -- il punto di avvio non
        # cambia il ciclogramma, dice solo da dove lo si legge -- ma da li'
        # deve ripartire.
        self._aggiorna_pulsante_avvio()
        if self.finestra_simulazione is not None:
            self.finestra_simulazione.imposta_avvio(a.t)
        if self.vista == "pettine":
            self._disegna_pettine()
        else:
            self._disegna_traiettorie()
        self._aggiorna_banner_e_riepilogo()

    def _aggiorna_pulsante_avvio(self):
        """L'etichetta e lo stato del pulsante che scorre i punti di avvio.

        A parte e non dentro `_aggiorna_stato_pulsanti`: quello dipende da cosa
        c'e' caricato e da cosa sta girando, questo da quanti istanti sono
        venuti fuori -- due cose che cambiano in momenti diversi. Chiamato da
        tutti e due, cosi' non resta indietro ne' nell'uno ne' nell'altro
        caso."""
        a = self._avvio_corrente()
        self.btn_avvio.configure(
            text="Avvio" if a is None else f"Avvio {a.indice + 1} di {a.totale}",
            state=tk.NORMAL if len(self.avvii) > 1 else tk.DISABLED,
        )
        self.btn_allinea.configure(
            state=tk.NORMAL
            if a is not None and not a.esatto and not self._lavoro_in_corso
            else tk.DISABLED
        )

    def _allinea_avvio(self):
        """Pulsante 'Allinea avvio': rende esatto il punto di avvio spostando
        rigidamente nel tempo il giro di qualche carroponte.

        Per la finestra e' una modifica come le altre: cambia i tempi in vasca
        delle tappe di confine, si annulla con Annulla, e i punti di passaggio
        si spostano col loro carroponte. Attese e soste restano quelle che
        erano: dentro il giro di un carroponte non cambia niente, quindi sono
        ancora giuste -- e ricadere sulla regola predefinita disegnerebbe
        rientri diversi da quelli appena verificati."""
        if self.soluzione is None or self.dati is None or self._lavoro_in_corso:
            return
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            r = allinea_avvio(self.dati, self.soluzione)
        except Exception as e:
            self._errore("Allineamento non riuscito", str(e))
            return
        finally:
            self.configure(cursor="")
        if r is None:
            self._stato(
                "Nessuno spostamento dei carroponti rende esatto il punto di "
                "avvio restando nelle tolleranze e senza collisioni"
            )
            return
        prima = self._istantanea()
        d = self.dati
        at = r.soluzione.actual_time
        self.permanenze = {
            k: at[k] - (at[k - 1] + d.loaded_leg_seconds(k - 1))
            for k in range(1, d.n_moves)
        }
        per_carro = {
            self.assegnazione[k]: v
            for k, v in r.spostamenti_mosse.items()
            if k in self.assegnazione
        }
        self.passaggi = [
            dict(p, t=p["t"] + per_carro.get(p["carro"], 0.0))
            if p.get("carro") is not None
            else dict(p)
            for p in self.passaggi
        ]
        self.attese = {k: v for p in r.soluzione.plans for k, v in p.attese.items()}
        self.soste = {
            k: v for p in r.soluzione.plans for k, v in p.soste_intermedie.items()
        }
        self._ricomponi(
            f"Avvio reso esatto: {descrivi(r.spostamenti, self._carri_delle_zone())}"
            f" (scarto pesato {r.errore_pesato_prima:.2f}"
            f" -> {r.errore_pesato_dopo:.2f})",
            prima,
            tieni_rientri=True,
        )

    def _mostra_ciclogramma(self):
        if self.soluzione is None or self.dati is None:
            self.avvii = []
            self.indice_avvio = 0
            self._aggiorna_pulsante_avvio()
            self._grafico_vuoto()
            self.tela.draw()
            return
        self._aggiorna_avvii()
        self._aggiorna_pulsante_avvio()
        if self.vista == "pettine":
            self._disegna_pettine()
        else:
            self._disegna_traiettorie()
        self._aggiorna_banner_e_riepilogo()
        # Qui passa ogni ridisegno, quindi ogni modifica: la simulazione
        # aperta si aggiorna da sola senza doverla richiamare da dieci posti.
        self._aggiorna_simulazione()

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
                avvio=self._avvio_corrente(),
            )
        except Exception as e:
            # Il caso normale, non un guasto: senza nessun trasporto assegnato
            # non c'e' nessuna traiettoria di carroponte da tracciare. Dirlo
            # com'e' evita di far leggere un messaggio di errore a chi sta
            # semplicemente cominciando.
            if not self.assegnazione:
                self._grafico_vuoto(
                    "Nessun trasporto assegnato a un carroponte:\n"
                    "il ciclogramma e' ancora vuoto.\n"
                    "Premi 'Modifica' e assegnali sul pettine."
                )
            else:
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

        # -- il pettine: lo SFONDO su cui si lavora ------------------------
        # Tutto grigio, sempre. E' il foglio: dice dove passano i pezzi e da
        # dove a dove va ogni trasporto, ed e' quello su cui si clicca per
        # assegnare. Colorarne i tratti assegnati faceva del FLUSSO DEI PEZZI
        # il disegno dominante, mentre quello che si sta componendo -- e
        # quello che poi si consegna -- e' il giro dei carroponti.
        # I PUNTI sono gli STESSI QUATTRO che il ciclogramma marca su ogni
        # trasporto -- aggancio, partenza, arrivo, immersione -- calcolati da
        # `eventi_del_trasporto`, cioe' dall'unica definizione che hanno.
        # Cambiano solo di lato: qui li si guarda dal pezzo invece che dal
        # carroponte, ma sono lo stesso istante e stanno nello stesso punto.
        # E' cio' che permette di assegnare una mossa e vedere il giro colorato
        # posarsi ESATTAMENTE sui punti che erano gia' li' in grigio.
        #
        # A quale mossa appartiene ogni tratto lo dice `mosse_del_pettine`, non
        # un contatore: la scalinata ha un tratto a carico per mossa, ma
        # dedurlo dall'ordine sarebbe un'ipotesi sulla costruzione invece di
        # una domanda a chi la costruisce.
        #
        # Un disegno solo per tutto il pettine, con i NaN a separare i tratti:
        # con dieci scalinate e diciassette mosse, una chiamata per tratto
        # sono seicento disegni a ogni ritocco.
        scalinate = manuale.pettine(d, T, self.permanenze)
        mosse = manuale.mosse_del_pettine(d, self.permanenze)
        linea_t, linea_x = [], []
        punti_t, punti_x = [], []
        for segs in scalinate:
            for s, k in zip(segs, mosse):
                ts, xs = _sample_segment(s)
                linea_t.extend(list(ts) + [np.nan])
                linea_x.extend(list(xs) + [np.nan])
                if s.kind == "loaded":
                    for t, x in eventi_del_trasporto(
                        d, k, s.t_start - d.pick_time_at(k), s.x_start, s.x_end
                    ):
                        punti_t.append(t)
                        punti_x.append(x)
        self.assi.plot(
            linea_t, linea_x, color=_GRIGIO, linewidth=_SOTTILE, zorder=2
        )
        # Piu' piccoli e senza bordo bianco di quelli dei carroponti: il
        # pettine e' lo sfondo su cui si lavora, e deve restare leggibile
        # SOTTO il giro che si sta componendo, non contendergli l'occhio.
        self.assi.plot(
            punti_t, punti_x, linestyle="none", marker="o", markersize=3.0,
            markerfacecolor=_GRIGIO, markeredgecolor=_GRIGIO, zorder=3,
        )

        # -- il CICLOGRAMMA: il giro di ogni carroponte, ripetuto -----------
        # Disegnato come nell'altra vista -- colore del carroponte, linea
        # continua e spessa, punti sugli istanti in cui succede qualcosa --
        # perche' e' lo stesso oggetto guardato dallo stesso lato. Assegnando
        # una mossa si vede comparire il pezzo di giro che la esegue, che e'
        # esattamente cio' che si sta decidendo.
        #
        # Un disegno solo per carroponte, con i NaN a separare i tratti: qui i
        # cicli ripetuti sono quattordici, e una chiamata per tratto per ciclo
        # farebbe centinaia di disegni per ogni ritocco.
        n_cicli = manuale.RIPETIZIONI_PREDEFINITE + 4
        for h, segs in enumerate(self.soluzione.segments_per_hoist):
            c = self._carro_della_zona(h)
            if c is None or not segs:
                continue  # zona senza mosse assegnate: non e' di nessuno
            colore = _HOIST_COLORS[c % len(_HOIST_COLORS)]
            linea_t, linea_x = [], []
            punti_t, punti_x = [], []
            for s in sorted(segs, key=lambda x: x.t_start):
                ts, xs = _sample_segment(s)
                # Gli stessi quattro istanti del ciclogramma sul trasporto,
                # piu' gli estremi delle traslazioni che non lo sono (il
                # rientro a vuoto). Prima qui si marcavano solo gli estremi,
                # anche del trasporto: assegnando una mossa comparivano due
                # punti dove il pettine ne mostrava quattro, e i due disegni
                # sembravano raccontare due cose diverse.
                if s.kind == "loaded" and s.move is not None:
                    eventi = eventi_del_trasporto(
                        d, s.move, s.t_start - d.pick_time_at(s.move),
                        s.x_start, s.x_end,
                    )
                elif s.kind in ("empty", "quota") and s.x_end != s.x_start:
                    eventi = [(s.t_start, s.x_start), (s.t_end, s.x_end)]
                else:
                    eventi = []
                for ciclo in range(n_cicli):
                    linea_t.extend(list(ts + ciclo * T) + [np.nan])
                    linea_x.extend(list(xs) + [np.nan])
                    for t, x in eventi:
                        punti_t.append(t + ciclo * T)
                        punti_x.append(x)
            self.assi.plot(
                linea_t, linea_x, color=colore, linewidth=_SPESSO, zorder=4
            )
            self.assi.plot(
                punti_t, punti_x, linestyle="none", marker="o", markersize=5.0,
                markerfacecolor=colore, markeredgecolor="white",
                markeredgewidth=0.8, zorder=5,
            )

        # -- i punti di passaggio aggiunti a mano ---------------------------
        # Rombi, per non confonderli con i punti tondi del pettine: quelli
        # vengono dalla ricetta, questi dall'utente, e solo questi si tolgono.
        # Vuoti finche' non sono di nessuno, pieni del colore del carroponte
        # che ci passa.
        ripetizioni = self._ripetizioni_passaggi()
        for i, p in enumerate(self.passaggi):
            ts = [t for j, t, _ in ripetizioni if j == i]
            c = p["carro"]
            colore = (
                _GRIGIO if c is None else _HOIST_COLORS[c % len(_HOIST_COLORS)]
            )
            self.assi.plot(
                ts, [p["x"]] * len(ts), linestyle="none", marker="D",
                markersize=6.5, markeredgewidth=1.2,
                markerfacecolor="white" if c is None else colore,
                markeredgecolor="#333333" if c is None else "black",
                zorder=6,
            )

        fine = manuale.RIPETIZIONI_PREDEFINITE * T + (
            scalinate[0][-1].t_end if scalinate else T
        )
        # La linea nera del punto di avvio anche qui, e per tutte le ripetizioni
        # disegnate: componendo si sposta il ciclogramma, e vedere dove va a
        # finire l'istante di avvio mentre lo si fa e' meta' del motivo per cui
        # esiste. Stessa funzione del ciclogramma, cosi' le due viste non
        # possono metterla in due punti diversi.
        disegna_avvio(
            self.assi, self._avvio_corrente(), T, int(fine / T) + 1
        )

        self.assi.set_xlim(0.0, fine)
        self.assi.set_xlabel("tempo [s]")
        self.assi.set_ylabel("posizione lungo la rotaia")
        self.assi.set_title(
            f"Modifica  —  takt time T = {T:.2f} s  —  "
            f"clic sul percorso grigio per assegnarlo a un carroponte"
        )
        self.assi.grid(axis="x", color="#f0f0f0")
        self.assi.format_coord = lettura_coordinate

        legenda = [
            Line2D([0], [0], color=_GRIGIO, lw=_SOTTILE, label="percorso dei pezzi"),
            Line2D(
                [0], [0], color="#333333", lw=_SPESSO,
                label="giro dei carroponti",
            ),
        ]
        if self.passaggi:
            legenda.append(
                Line2D(
                    [0], [0], linestyle="none", marker="D", markersize=6,
                    markerfacecolor="white", markeredgecolor="#333333",
                    label="punto di passaggio",
                )
            )
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
                    f"{spec.nominale:.0f}",
                    f"{self.permanenze.get(k, 0.0) - spec.nominale:+.1f}",
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
        for r in self.tabella_passaggi.get_children():
            self.tabella_passaggi.delete(r)
        for p in self.passaggi:
            self.tabella_passaggi.insert(
                "",
                tk.END,
                values=(
                    f"{p['t']:.1f}",
                    f"{p['x']:.0f}",
                    "-" if p["carro"] is None else p["carro"] + 1,
                ),
            )

    def _tabella_tempi_in_vasca(self) -> list[str]:
        """Tempo teorico ed effettivo di ogni vasca, come righe di testo
        incolonnate per il Riepilogo, con lo sgocciolamento accanto: e' tempo
        che il telaio passa sopra la vasca DOPO il bagno, e non sta dentro
        l'effettivo.

        La stessa cosa sta nella tabella della scheda Ciclogramma, ma quella si
        apre solo per modificare: qui la si legge accanto al takt time e allo
        scarto pesato, che sono i numeri con cui la si giudica. Le vasche fuori
        dalla tolleranza si segnano, perche' in una colonna di numeri non si
        vedono -- il verdetto lo da' la verifica, il segno dice dove guardare."""
        d = self.config_linea.data
        intermedie = [k for k in range(1, d.n_moves) if k in self.permanenze]
        if not intermedie:
            return []
        larga = max(len("vasca"), *(len(d.route[k].tank_id) for k in intermedie))
        righe = [
            "Tempi in vasca:",
            f"   {'vasca':<{larga}}  {'teorico':>8}  {'effettivo':>9}  "
            f"{'scarto':>7}  {'sgocciolo':>9}",
        ]
        fuori = False
        for k in intermedie:
            spec = d.route[k]
            effettivo = self.permanenze[k]
            segno = ""
            # lo stesso mezzo centesimo di tolleranza dei valori mostrati: un
            # bagno sul minimo, arrotondato, non deve sembrare fuori
            if effettivo < spec.dwell_min - 0.005:
                segno, fuori = "  < min", True
            elif effettivo > spec.dwell_max + 0.005:
                segno, fuori = "  > max", True
            righe.append(
                f"   {spec.tank_id:<{larga}}  {spec.nominale:>8.1f}  "
                f"{effettivo:>9.1f}  {effettivo - spec.nominale:>+7.1f}  "
                f"{d.drain_time_at(k):>9.1f}{segno}"
            )
        if fuori:
            righe.append(
                "   (< min / > max: fuori dalla tolleranza teorico -/+ delta)"
            )
        return righe

    def _scarto_pesato_corrente(self) -> float:
        """Lo scarto pesato dai teorici del ciclogramma che si sta guardando.

        Si calcola dai tempi in vasca e non dalla soluzione del solutore: cosi'
        vale anche per un ciclogramma composto o ritoccato a mano, ed e' il
        numero con cui confrontarlo con quello del calcolo automatico."""
        d = self.config_linea.data
        return errore_pesato(
            d,
            {
                k: self.permanenze[k] - d.route[k].nominale
                for k in range(1, d.n_moves)
                if k in self.permanenze
            },
        )

    def _banner_neutro(self, testo: str):
        """Il banner quando non c'e' un ciclogramma da giudicare. Il verdetto
        di quello di prima non deve sopravvivergli: letto accanto a un'altra
        linea, o a un calcolo fallito, direbbe una cosa falsa."""
        self.banner.configure(
            text=testo, background="#e8e8e8", foreground="#000000"
        )

    def _aggiorna_banner_e_riepilogo(self):
        T, rep = self.T_corrente, self.report
        # Le incoerenze vengono PRIMA di tutto il resto. Sono i punti in cui il
        # ciclogramma non si tiene in piedi -- un carroponte che dovrebbe
        # essere in due posti insieme, o che non fa in tempo -- e il disegno le
        # assorbe come sa: allunga un'attesa e tira dritto. Il risultato e' una
        # riga orizzontale lunghissima che sembra una stranezza del grafico,
        # mentre e' il sintomo. Si calcolavano gia' e non si mostravano: chi
        # riapriva un file rotto vedeva la riga e non sapeva cosa fosse.
        if self.incoerenze:
            self.banner.configure(
                text=f"{len(self.incoerenze)} INCOERENZE   -   il ciclogramma "
                f"non si tiene in piedi, vedi il Riepilogo",
                background="#fce5cd",
                foreground="#b45f06",
            )
            righe = [
                "IL CICLOGRAMMA NON E' REALIZZABILE COSI' COM'E'.",
                "",
                "Il disegno le assorbe allungando le attese: se vedi una riga",
                "orizzontale lunghissima, e' questa la ragione.",
                "",
            ]
            righe += [f"  - {m}" for m in self.incoerenze]
            righe += [
                "",
                "Se hai appena riaperto un file salvato con una versione",
                "precedente del programma, ricalcolalo e risalvalo: i tempi di",
                "presa, rilascio e permanenza sono cambiati, e i valori scritti",
                "allora non vogliono piu' dire la stessa cosa.",
            ]
            self._scrivi_riepilogo("\n".join(righe))
            return
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
        righe = [f"Origine: {origine}"]
        # La barra di stato lo dice appena finito, ma si perde al primo altro
        # messaggio. Qui resta finche' resta il ciclogramma, ed e' il posto in
        # cui lo si va a cercare dopo -- accanto a da dove viene, che e'
        # l'altra meta' della stessa informazione.
        if self.durata_calcolo is not None:
            righe.append(
                f"Tempo di calcolo: {_durata_leggibile(self.durata_calcolo)}"
            )
        righe += [
            "",
            f"Takt time:      {T:.2f} s"
            + ("  (fisso al teorico)" if self.dati.takt_fisso else ""),
            f"Produttivita':  {3600.0 / T:.1f} pezzi/ora",
            f"Scarto pesato dai teorici: {self._scarto_pesato_corrente():.2f}"
            + (
                "  (e' cio' che Calcola auto rende minimo)"
                if self.dati.takt_fisso
                else "  (minimo a parita' di takt)"
                if self.origine.startswith("calcolo") and not self.modificato
                else ""
            ),
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
        righe.append("")
        righe += self._tabella_tempi_in_vasca()
        # Il punto di avvio: la linea nera verticale che si vede sul grafico,
        # scritta in chiaro. Sul disegno si legge QUANDO; qui si legge anche
        # DOVE va portato ogni carroponte, che e' quello che serve a chi sta
        # davanti all'impianto col pulsante in mano.
        righe.append("")
        for etichetta, valore, nota in righe_di_riepilogo(
            self._avvio_corrente(), self._carri_delle_zone()
        ):
            # i secondi con due decimali come nel foglio Riepilogo, dove a
            # darglieli e' il formato della cella: le due scritte si
            # confrontano, e "16.6" accanto a "16,60" fa dubitare
            if isinstance(valore, float):
                valore = f"{valore:.2f}"
            righe.append(f"{etichetta}: {valore}   ({nota})")

        # Le soste in una vasca in mezzo si vedono sul grafico -- un tratto
        # piatto sopra una vasca che non e' ne' la partenza ne' l'arrivo -- ma
        # a chi guarda sembrano una stranezza finche' non gli si dice che sono
        # una scelta, e quale.
        if self.soste:
            righe.append("")
            righe.append(
                f"Soste durante il rientro a vuoto: {len(self.soste)} "
                f"(per stare lontani dal carroponte vicino)"
            )
            for k in sorted(self.soste):
                s = self.soste[k]
                righe.append(
                    f"   dopo il trasporto {k}: "
                    f"{s.secondi:.1f} s in {self.dati.route[s.stazione].tank_id}"
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

    def _tratti_trasporto(self):
        """Per ogni trasporto disegnato: (mossa, istanti, posizioni).

        Sono gli stessi punti che finiscono sul grafico -- presa, traslazione
        e rilascio campionati col profilo vero -- cosi' "clicca sul trasporto"
        vuol dire davvero dove lo vedi, e non solo sul suo estremo."""
        if self.config_linea is None or self.T_corrente is None:
            return []
        d, T = self.config_linea.data, self.T_corrente
        tempi = manuale.catena_pezzo(d, self.permanenze)
        per_mossa: dict[int, list] = {}
        for s, k in zip(
            manuale.segmenti_pezzo(d, tempi), manuale.mosse_del_pettine(d, self.permanenze)
        ):
            if s.kind != "wait":  # la sosta non e' un trasporto da assegnare
                per_mossa.setdefault(k, []).append(s)

        fuori = []
        for k, elenco in per_mossa.items():
            ts, xs = [], []
            for s in elenco:
                a, b = _sample_segment(s)
                ts.extend(a)
                xs.extend(b)
            ts, xs = np.array(ts), np.array(xs)
            if self.vista == "pettine":
                scarti = [p * T for p in range(manuale.RIPETIZIONI_PREDEFINITE)]
            else:
                # il ciclogramma li disegna riportati dentro il periodo
                ts = ts - (tempi[k] // T) * T
                scarti = [c * T for c in range(3)]
            for scarto in scarti:
                fuori.append((k, ts + scarto, xs))
        return fuori

    def _trasporto_sotto(self, evento):
        """La mossa il cui tratto passa sotto al puntatore, o None.

        Si misura in PIXEL: in coordinate dati un secondo e un millimetro non
        sono paragonabili, e la tolleranza sarebbe assurda."""
        migliore, distanza_min = None, 1e9
        for k, ts, xs in self._tratti_trasporto():
            punti = self.assi.transData.transform(np.column_stack([ts, xs]))
            d = np.hypot(punti[:, 0] - evento.x, punti[:, 1] - evento.y).min()
            if d < distanza_min:
                migliore, distanza_min = k, d
        return migliore if distanza_min <= 12 else None

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
        # Un punto di passaggio prima di tutto: e' piccolo e sta spesso sopra
        # un tratto del pettine, e chi lo centra vuole proprio lui.
        punto = self._passaggio_sotto(evento)
        if punto is not None:
            self._trascinamento = {
                "passaggio": punto,
                "x_iniziale": evento.xdata,
                "y_iniziale": evento.ydata,
                "px_iniziale": evento.x,
                "py_iniziale": evento.y,
                "istantanea": self._istantanea(),
            }
            return
        # Due cose diverse, e vanno cercate separatamente.
        #
        # Il PUNTO DI PRELIEVO e' la maniglia per trascinare: il tempo in vasca
        # si allunga da li', quindi il trascinamento ha senso solo prendendolo
        # per quell'estremo. Raggio stretto.
        #
        # Il TRATTO invece si clicca dove lo vedi, per tutta la sua lunghezza:
        # assegnare una mossa a un carroponte non ha niente a che fare con un
        # estremo particolare, e obbligare a centrare la vasca di partenza era
        # una precisione chiesta senza motivo.
        maniglia, distanza_min, istante = None, 1e9, 0.0
        for k, t, y in self._punti_prelievo():
            px, py = self.assi.transData.transform((t, y))
            d = ((px - evento.x) ** 2 + (py - evento.y) ** 2) ** 0.5
            if d < distanza_min:
                maniglia, distanza_min, istante = k, d, t
        if distanza_min > 18:
            maniglia = None
        sotto = self._trasporto_sotto(evento)
        if maniglia is None and sotto is None:
            return
        self._trascinamento = {
            "mossa": maniglia,  # None = qui non si trascina, si puo' solo cliccare
            "mossa_clic": sotto if sotto is not None else maniglia,
            "t_iniziale": istante,
            "x_iniziale": evento.xdata,
            "px_iniziale": evento.x,
            "istantanea": self._istantanea(),
        }

    def _su_movimento(self, evento):
        if self._trascinamento is None or evento.xdata is None:
            return
        if "passaggio" in self._trascinamento:
            p = self.passaggi[self._trascinamento["passaggio"]]
            dt = evento.xdata - self._trascinamento["x_iniziale"]
            dx = evento.ydata - self._trascinamento["y_iniziale"]
            self._stato(
                f"Sposto il punto a {p['t'] + dt:.1f} s, {p['x'] + dx:.0f} mm"
            )
            return
        if self._trascinamento["mossa"] in (None, 0):
            # None: si e' premuto a meta' di un tratto, non su una maniglia.
            # 0: il primo prelievo e' l'origine dei tempi, non si sposta.
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
            self.tela.draw_idle()
        if "passaggio" in trascinamento:
            self._rilascia_passaggio(trascinamento, evento)
            return
        k = trascinamento["mossa"]
        # Clic secco o trascinamento? Si misura in PIXEL: in secondi la soglia
        # dipenderebbe da quanto si e' ingrandito il grafico.
        if evento.x is None or abs(evento.x - trascinamento["px_iniziale"]) < 4:
            self._assegna(trascinamento["mossa_clic"], trascinamento["istantanea"])
            return
        if k is None or evento.xdata is None:
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

    def _rilascia_passaggio(self, trascinamento, evento):
        """Fine di un clic su un punto di passaggio: secco lo da' (o lo
        toglie) al carroponte attivo, trascinato lo sposta."""
        i = trascinamento["passaggio"]
        fermo = evento.x is None or (
            abs(evento.x - trascinamento["px_iniziale"]) < 4
            and abs(evento.y - trascinamento["py_iniziale"]) < 4
        )
        if fermo:
            self._assegna_passaggio(i, trascinamento["istantanea"])
            return
        if evento.xdata is None or evento.ydata is None:
            return
        p = self.passaggi[i]
        p["t"] += evento.xdata - trascinamento["x_iniziale"]
        p["x"] += evento.ydata - trascinamento["y_iniziale"]
        self.passaggi.sort(key=lambda q: (q["t"], q["x"]))
        self._ricomponi(
            f"Punto spostato a {p['t']:.1f} s, {p['x']:.0f} mm",
            trascinamento["istantanea"],
            tieni_rientri=True,
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
        self.chk_takt_fisso.configure(state=stato)
        # Ferma e' acceso solo mentre c'e' un calcolo da fermare, e si spegne
        # appena lo si preme: il calcolo non si ferma all'istante -- finisce la
        # costruzione del modello in corso, o il solutore deve accorgersene --
        # e un pulsante che resta acceso inviterebbe a premerlo ancora.
        in_corso = (
            self._lavoro_in_corso
            and self._interruzione is not None
            and not self._interruzione.richiesta
        )
        self.btn_ferma.configure(state=tk.NORMAL if in_corso else tk.DISABLED)
        self.btn_proposta.configure(state=stato)
        # "Modifica" si abilita quando c'e' qualcosa da modificare, e basta:
        # non ha una sorgente da scegliere, perche' il ciclogramma corrente e'
        # uno solo (da dove venga lo dice il Riepilogo).
        c_e_ciclogramma = self.soluzione is not None and not self._lavoro_in_corso
        self.btn_salva.configure(
            state=tk.NORMAL if c_e_ciclogramma else tk.DISABLED
        )
        # Si simula un ciclogramma, non una linea: finche' non ce n'e' uno --
        # calcolato o composto a mano -- non c'e' niente da far muovere.
        self.btn_simula.configure(
            state=tk.NORMAL if c_e_ciclogramma else tk.DISABLED
        )
        self.btn_modifica.configure(
            state=tk.NORMAL if c_e_ciclogramma else tk.DISABLED,
            text="Fine modifica" if self.modifica_aperta else "Modifica",
        )
        self._aggiorna_pulsante_avvio()
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
        self.schede.tab(2, text="Verifica")

    def _stato(self, testo: str):
        self.etichetta_stato.configure(text=testo)

    def _errore(self, titolo: str, dettaglio: str):
        messagebox.showerror(f"{TITOLO} - {titolo}", dettaglio)
        self._stato(titolo)

    def destroy(self):
        # La simulazione ha un timer che si richiama da solo: va fermata
        # prima, o continua a chiedere ridisegni su una finestra che non c'e'.
        if self.finestra_simulazione is not None:
            finestra, self.finestra_simulazione = self.finestra_simulazione, None
            try:
                finestra.destroy()
            except Exception:
                pass
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
        # Per la stessa ragione l'icona della finestra: si lascia andare ora,
        # finche' c'e' ancora un Tk a cui chiedere di cancellarla.
        self.icona = None
        super().destroy()


def _cartella_risorse() -> str:
    """`risorse/` accanto a questo modulo, o dentro il pacchetto di
    PyInstaller (`sys._MEIPASS`) quando gira l'eseguibile."""
    return os.path.join(
        getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
        "risorse",
    )


def _immagine_ridotta(master, percorso: str, larghezza: int):
    """Un PNG portato a `larghezza` pixel, come immagine di Tk, o None.

    Con Pillow (che c'e' sempre: lo porta matplotlib) il ridimensionamento e'
    filtrato; `subsample` di Tk prende un pixel ogni tanti, e sui bordi dei
    loghi si vede la seghettatura. Resta come ripiego."""
    try:
        from PIL import Image, ImageTk

        with Image.open(percorso) as img:
            altezza = round(img.height * larghezza / img.width)
            ridotta = img.convert("RGBA").resize(
                (larghezza, altezza), Image.LANCZOS
            )
        return ImageTk.PhotoImage(ridotta, master=master)
    except Exception:
        pass
    try:
        img = tk.PhotoImage(master=master, file=percorso)
        fattore = max(1, round(img.width() / larghezza))
        return img.subsample(fattore, fattore)
    except Exception:
        return None


class _Splash(tk.Toplevel):
    """La schermata di benvenuto: logo del programma, nome, logo IMEL.

    Una finestra senza bordi al centro dello schermo, che resta almeno
    `DURATA_MS` -- anche se la finestra principale e' pronta prima -- e non di
    piu' se la costruzione ci mette di piu'. Un'immagine che manca non ferma
    niente: si mostra quello che c'e'."""

    DURATA_MS = 3000
    SFONDO = "#ffffff"

    def __init__(self, master):
        super().__init__(master, bg=self.SFONDO)
        self._inizio = time.monotonic()
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # le misure sono pensate a 96 dpi; su uno schermo scalato crescono
        scala = max(1.0, self.winfo_fpixels("1i") / 96.0)
        cartella = _cartella_risorse()
        # tenute in attributi: senza riferimenti Tk le cancella
        self._logo = _immagine_ridotta(
            self, os.path.join(cartella, "icona.png"), round(160 * scala)
        )
        self._imel = _immagine_ridotta(
            self, os.path.join(cartella, "logo_imel.png"), round(200 * scala)
        )

        cornice = tk.Frame(
            self,
            bg=self.SFONDO,
            highlightthickness=1,
            highlightbackground="#c8c8c8",
            padx=round(48 * scala),
            pady=round(32 * scala),
        )
        cornice.pack(fill="both", expand=True)
        if self._logo is not None:
            tk.Label(cornice, image=self._logo, bg=self.SFONDO).pack()
        tk.Label(
            cornice,
            text=TITOLO,
            bg=self.SFONDO,
            fg="#1f2a36",
            font=("Segoe UI", 28, "bold"),
        ).pack(pady=(round(12 * scala), round(28 * scala)))
        if self._imel is not None:
            tk.Label(
                cornice,
                text="powered by",
                bg=self.SFONDO,
                fg="#7a7a7a",
                font=("Segoe UI", 10),
            ).pack(pady=(0, round(6 * scala)))
            tk.Label(cornice, image=self._imel, bg=self.SFONDO).pack()

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        # disegnata subito: subito dopo la costruzione dell'interfaccia tiene
        # occupato il ciclo degli eventi, e senza questo si vedrebbe vuota
        self.update()

    def restante_ms(self) -> int:
        """Quanto deve restare ancora a schermo per arrivare a `DURATA_MS`."""
        trascorso = (time.monotonic() - self._inizio) * 1000
        return max(0, int(self.DURATA_MS - trascorso))


def _applica_icona(finestra) -> "tk.PhotoImage | str | None":
    """Mette l'icona di CraneStrike sulla finestra, e su tutte quelle che si
    apriranno dopo -- la simulazione compresa. Restituisce quello che ha
    applicato, o None, e va tenuto in un attributo.

    I file stanno in `risorse/`, accanto a questo modulo; nell'eseguibile
    impacchettato stanno nella cartella che PyInstaller indica con
    `sys._MEIPASS`.

    UNO SOLO DEI DUE FILE, MAI TUTTI E DUE. Su Windows l'ICO, che contiene le
    misure piccole gia' pronte: nel titolo l'icona e' di 16 pixel, e il PNG
    rimpicciolito da Tk viene seghettato. Altrove il PNG. Impostarli entrambi
    sembra la scelta prudente ed e' la sbagliata: misurato su Tk 8.6.15 e
    Windows 11, `iconphoto` seguito da `iconbitmap` toglie alla finestra
    l'icona PICCOLA, e nel titolo compare l'icona generica di Windows.

    Un'icona che manca non e' un motivo per non partire: se il file non c'e',
    o Tk non lo legge, la finestra resta con quella predefinita."""
    cartella = _cartella_risorse()
    try:
        if sys.platform == "win32":
            percorso = os.path.join(cartella, "icona.ico")
            finestra.iconbitmap(default=percorso)
            _icona_barra_nitida(finestra, percorso)
            return percorso
        immagine = tk.PhotoImage(
            master=finestra, file=os.path.join(cartella, "icona.png")
        )
        finestra.iconphoto(True, immagine)
        return immagine
    except Exception:
        return None


def _icona_barra_nitida(finestra, percorso: str):
    """Dà alla barra delle applicazioni l'icona della misura che le serve.

    La barra di Windows 11 disegna l'icona GRANDE della classe di finestra, e
    Tk ci mette quella da 32 pixel: la barra, che al 100% ne vuole 24, la
    rimpicciolisce da se', e il disegno -- linee sottili -- esce sfocato.
    Misurato su Windows 11 e Tk 8.6: WM_SETICON sulla finestra non cambia
    niente, cambiare l'icona della CLASSE si'. L'ICO ha gia' la misura giusta
    disegnata a mano, e qui si sceglie quella.

    La misura e' 24 pixel per la scala dello schermo. Il processo non dichiara
    di gestire i dpi, quindi Windows gli risponderebbe sempre 96: la scala vera
    si chiede mettendo per un attimo il thread in modalita' consapevole.

    La classe e' quella delle finestre di primo livello di Tk, comune a tutte:
    basta farlo una volta, ma su una finestra gia' mappata -- prima la cornice
    esterna non esiste -- e per questo si aspetta la prima comparsa."""
    import ctypes
    from ctypes import wintypes

    u = ctypes.windll.user32
    u.LoadImageW.restype = wintypes.HANDLE
    u.LoadImageW.argtypes = [
        wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    u.SetClassLongPtrW.restype = ctypes.c_void_p
    u.SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]

    def dpi_vero() -> int:
        try:
            u.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
            u.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            prima = u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
            try:
                return u.GetDpiForSystem()
            finally:
                u.SetThreadDpiAwarenessContext(prima)
        except Exception:
            return 96

    def applica(_evento=None):
        try:
            finestra.unbind("<Map>", legame)
            lato = round(24 * dpi_vero() / 96)
            icona = u.LoadImageW(None, percorso, 1, lato, lato, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if icona:
                u.SetClassLongPtrW(int(finestra.wm_frame(), 16), -14, icona)  # GCLP_HICON
        except Exception:
            pass  # resta l'icona di Tk: sfocata, ma c'e'

    legame = finestra.bind("<Map>", applica, add="+")


def _identita_windows():
    """Dice a Windows che questo processo e' CraneStrike, non Python.

    Lanciato da `CraneStrike.bat` o da `python interfaccia.py`, il processo e'
    pythonw.exe, e Windows raggruppa la finestra sotto l'icona di Python sulla
    barra delle applicazioni, qualunque icona abbia la finestra. Un
    identificativo proprio la separa. Nell'eseguibile non servirebbe, e non fa
    danni. Deve precedere la creazione della finestra."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "IMEL.CraneStrike"
        )
    except Exception:
        pass


def autotest(cartella: str | None = None) -> int:
    """Prova l'installazione da cima a fondo, senza intervento dell'utente:
    crea un modello, lo rilegge, calcola, verifica, salva.

    Serve soprattutto per l'eseguibile impacchettato: che si costruisca non
    vuol dire che funzioni -- OR-Tools porta librerie native che potrebbero
    non essere finite dentro, e ce ne si accorgerebbe solo al primo calcolo,
    in stabilimento. Da lanciare cosi':

        CraneStrike.exe --autotest

    Scrive un resoconto accanto ai file prodotti e restituisce 0 se tutto
    funziona."""
    import tempfile

    destinazione = cartella or tempfile.mkdtemp(prefix="cranestrike_prova_")
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
    _identita_windows()
    try:
        app = Applicazione(file_iniziale, con_splash=True)
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
