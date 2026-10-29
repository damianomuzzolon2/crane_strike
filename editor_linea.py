"""
editor_linea.py
---------------
La finestra "Dati linea": le stesse tabelle del file Excel di ingresso --
Vasche, Percorso, Parametri, Zone, CambioQuota -- da guardare, compilare e
modificare senza uscire dal programma.

Non e' un secondo formato e non ha controlli suoi. Le tabelle sono le colonne
LETTE dei fogli (excel_io.COLONNE_*), e "Applica" le fa leggere a
`excel_io.leggi_righe`, che le scrive in un libro in memoria e le passa al
lettore dei file: stessi controlli, stessi messaggi, con foglio e cella. Dalla
cella si risale alla riga della tabella, ed e' cosi' che la finestra colora le
righe sbagliate e ci porta con un clic.

Il file Excel resta il modo di conservare una linea: "Salva come Excel..."
scrive le tabelle nello stesso formato di "Nuovo modello Excel...", e si
riapre con "Apri linea...".

Sta sopra excel_io e sotto interfaccia: la usa solo la finestra principale,
che le passa due funzioni -- cosa fare per applicare e cosa fare dopo un
salvataggio -- invece di farsi importare.
"""

from __future__ import annotations

import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

from excel_io import (
    COLONNE_CAMBIO_QUOTA,
    COLONNE_PERCORSO,
    COLONNE_VASCHE,
    COLONNE_ZONE,
    FOGLIO_CAMBIO_QUOTA,
    FOGLIO_PARAMETRI,
    FOGLIO_PERCORSO,
    FOGLIO_VASCHE,
    FOGLIO_ZONE,
    PARAMETRI,
    VERSI_CAMBIO_QUOTA,
    RigheLinea,
    scrivi_righe,
)

_ROSSO = "#f4cccc"
# Arancione: la cella corrente sta sempre nella riga selezionata, che e' blu,
# e una cornice blu ci sparirebbe dentro.
_CURSORE = "#f57c00"

# "  - [Vasche!B3] posizione: valore mancante": foglio, colonna, riga, testo.
_RIGA_ERRORE = re.compile(r"^\s*-\s*\[([^!\]]+)!([A-Z]*)(\d*)\]\s*(.*)$")


def testo_cella(valore) -> str:
    """Come si mostra una cella: i numeri senza decimali inutili (2500, non
    2500.0) e senza perdere quelli che ci sono (repr e' il piu' corto che
    rilegge lo stesso numero)."""
    if valore is None:
        return ""
    if isinstance(valore, bool):
        return "1" if valore else "0"
    if isinstance(valore, float):
        if valore.is_integer() and abs(valore) < 1e15:
            return str(int(valore))
        return repr(valore)
    return str(valore).strip()


# --------------------------------------------------------------------------
# Una tabella modificabile
# --------------------------------------------------------------------------


class _Griglia(ttk.Frame):
    """Una tabella con le celle modificabili, costruita su un Treeview.

    Tk non ha una griglia modificabile: il Treeview mostra le righe, e per
    modificare una cella ci si appoggia sopra un campo di testo (o un elenco a
    discesa, dove i valori ammessi sono pochi) delle stesse dimensioni.

    I dati veri stanno in `self._righe`, liste di stringhe: il Treeview e' solo
    come si vedono. La cella corrente -- quella che Invio modifica e Canc
    svuota -- e' la riga col fuoco piu' `self._colonna`, ed e' segnata da una
    cornice colorata: il Treeview da solo sa evidenziare solo righe intere."""

    def __init__(
        self,
        master,
        colonne: list[str],
        larghezze: list[int],
        al_cambio: Callable[[], None],
        numerazione: Optional[str] = None,
        modificabili: Optional[set[int]] = None,
        scelte: Optional[Callable[[int, int], Optional[list[str]]]] = None,
        righe_fisse: bool = False,
        alla_selezione: Optional[Callable[[Optional[int]], None]] = None,
    ):
        super().__init__(master)
        self.colonne = colonne
        self.n = len(colonne)
        self._al_cambio = al_cambio
        self._numerazione = numerazione
        self._modificabili = set(range(self.n)) if modificabili is None else modificabili
        self._scelte = scelte or (lambda _r, _c: None)
        self._righe_fisse = righe_fisse
        self._alla_selezione = alla_selezione
        self._righe: list[list[str]] = []
        self._colonna = min(self._modificabili) if self._modificabili else 0
        self._editor: Optional[tk.Widget] = None
        self._in_modifica: Optional[tuple[int, int]] = None
        self._errori: set[int] = set()
        self._etichette: dict[str, set[int]] = {}

        if not righe_fisse:
            comandi = ttk.Frame(self)
            comandi.pack(fill=tk.X, pady=(0, 4))
            for testo, azione in (
                ("Aggiungi riga", self.aggiungi_riga),
                ("Inserisci sopra", self.inserisci_riga),
                ("Elimina righe", self.elimina_righe),
                ("Su", lambda: self.sposta_righe(-1)),
                ("Giu'", lambda: self.sposta_righe(1)),
            ):
                ttk.Button(comandi, text=testo, command=azione).pack(
                    side=tk.LEFT, padx=(0, 4)
                )

        cornice = ttk.Frame(self)
        cornice.pack(fill=tk.BOTH, expand=True)
        self.albero = ttk.Treeview(
            cornice,
            columns=[f"c{i}" for i in range(self.n)],
            show="tree headings" if numerazione else "headings",
            selectmode="extended",
        )
        if numerazione:
            self.albero.heading("#0", text=numerazione)
            self.albero.column("#0", width=70, stretch=False, anchor=tk.E)
        for i, (titolo, larghezza) in enumerate(zip(colonne, larghezze)):
            self.albero.heading(f"c{i}", text=titolo)
            # stretch=False: con le colonne elastiche Tk le stringe tutte per
            # starci, e la barra orizzontale non servirebbe mai
            self.albero.column(f"c{i}", width=larghezza, stretch=False, anchor=tk.W)
        self.albero.tag_configure("errore", background=_ROSSO)
        verticale = ttk.Scrollbar(cornice, orient=tk.VERTICAL, command=self.albero.yview)
        orizzontale = ttk.Scrollbar(
            cornice, orient=tk.HORIZONTAL, command=self.albero.xview
        )
        self.albero.configure(
            yscrollcommand=self._scorri(verticale),
            xscrollcommand=self._scorri(orizzontale),
        )
        self.albero.grid(row=0, column=0, sticky="nsew")
        verticale.grid(row=0, column=1, sticky="ns")
        orizzontale.grid(row=1, column=0, sticky="ew")
        cornice.rowconfigure(0, weight=1)
        cornice.columnconfigure(0, weight=1)

        # la cornice della cella corrente: quattro bordi sottili, perche' un
        # riquadro pieno coprirebbe il testo
        self._bordi = [
            tk.Frame(self.albero, background=_CURSORE) for _ in range(4)
        ]

        a = self.albero
        a.bind("<Button-1>", self._su_clic)
        a.bind("<Double-1>", self._su_doppio_clic)
        a.bind("<Return>", lambda e: self._inizia_modifica())
        a.bind("<F2>", lambda e: self._inizia_modifica())
        a.bind("<Left>", lambda e: self._cambia_colonna(-1))
        a.bind("<Right>", lambda e: self._cambia_colonna(1))
        a.bind("<Delete>", lambda e: self._svuota_celle())
        a.bind("<BackSpace>", lambda e: self._svuota_celle())
        a.bind("<Control-c>", lambda e: self.copia())
        a.bind("<Control-C>", lambda e: self.copia())
        a.bind("<Control-v>", lambda e: self.incolla())
        a.bind("<Control-V>", lambda e: self.incolla())
        a.bind("<Key>", self._su_tasto)
        a.bind("<<TreeviewSelect>>", self._su_selezione)
        a.bind("<Configure>", lambda e: self.after_idle(self._mostra_cursore))

    # -- dati --------------------------------------------------------------

    def imposta(self, righe):
        self._termina_modifica(salva=False)
        self._righe = [self._normale(r) for r in righe]
        self._errori = set()
        self._ridisegna()

    def righe(self) -> list[list[str]]:
        self._termina_modifica(salva=True)
        return [list(r) for r in self._righe]

    def imposta_cella(self, riga: int, colonna: int, testo: str):
        self._righe[riga][colonna] = testo
        self._aggiorna_riga(riga)

    def _normale(self, riga) -> list[str]:
        celle = [testo_cella(v) for v in list(riga)[: self.n]]
        return celle + [""] * (self.n - len(celle))

    # -- aspetto -----------------------------------------------------------

    def segna_errori(self, righe: set[int]):
        self._errori = {r for r in righe if 0 <= r < len(self._righe)}
        for r in range(len(self._righe)):
            self._aggiorna_riga(r)

    def etichetta(self, nome: str, righe: set[int], **stile):
        """Un aspetto per alcune righe (i parametri obbligatori in grassetto)."""
        self.albero.tag_configure(nome, **stile)
        self._etichette[nome] = set(righe)
        for r in range(len(self._righe)):
            self._aggiorna_riga(r)

    def _tag(self, r: int) -> tuple:
        tag = [nome for nome, righe in self._etichette.items() if r in righe]
        if r in self._errori:
            tag.append("errore")
        return tuple(tag)

    def _ridisegna(self):
        fuoco = self._riga_corrente()
        self.albero.delete(*self.albero.get_children())
        for r, riga in enumerate(self._righe):
            self.albero.insert(
                "", tk.END, iid=str(r), text=str(r + 1), values=riga, tags=self._tag(r)
            )
        if self._righe:
            self.vai_a(min(fuoco or 0, len(self._righe) - 1), self._colonna, vedi=False)
        else:
            self._mostra_cursore()

    def _aggiorna_riga(self, r: int):
        if self.albero.exists(str(r)):
            self.albero.item(str(r), values=self._righe[r], tags=self._tag(r))

    def _riga_corrente(self) -> Optional[int]:
        fuoco = self.albero.focus()
        return int(fuoco) if fuoco else None

    def vai_a(self, riga: int, colonna: Optional[int] = None, vedi: bool = True):
        if not (0 <= riga < len(self._righe)):
            return
        if colonna is not None and 0 <= colonna < self.n:
            self._colonna = colonna
        iid = str(riga)
        self.albero.focus(iid)
        self.albero.selection_set(iid)
        if vedi:
            self.albero.see(iid)
            self.albero.focus_set()
        self.after_idle(self._mostra_cursore)

    def _scorri(self, barra):
        def scorri(primo, ultimo):
            barra.set(primo, ultimo)
            # una cella in modifica non segue lo scorrimento: la si chiude
            self._termina_modifica(salva=True)
            self.after_idle(self._mostra_cursore)

        return scorri

    def _mostra_cursore(self):
        if not self.winfo_exists():
            return
        r = self._riga_corrente()
        riquadro = (
            self.albero.bbox(str(r), f"c{self._colonna}") if r is not None else ""
        )
        if not riquadro:
            for b in self._bordi:
                b.place_forget()
            return
        x, y, l, h = riquadro
        for b, (bx, by, bl, bh) in zip(
            self._bordi,
            ((x, y, l, 2), (x, y + h - 2, l, 2), (x, y, 2, h), (x + l - 2, y, 2, h)),
        ):
            b.place(x=bx, y=by, width=bl, height=bh)

    # -- tastiera e mouse --------------------------------------------------

    def _colonna_sotto(self, x: int) -> Optional[int]:
        voce = self.albero.identify_column(x)  # "#0" e' la numerazione
        indice = int(voce[1:]) - 1 if voce.startswith("#") else -1
        return indice if 0 <= indice < self.n else None

    def _su_clic(self, evento):
        colonna = self._colonna_sotto(evento.x)
        if colonna is not None:
            self._colonna = colonna
        self.after_idle(self._mostra_cursore)

    def _su_doppio_clic(self, evento):
        if self.albero.identify_region(evento.x, evento.y) != "cell":
            return
        riga = self.albero.identify_row(evento.y)
        colonna = self._colonna_sotto(evento.x)
        if not riga or colonna is None:
            return
        self.vai_a(int(riga), colonna)
        self._inizia_modifica()
        return "break"

    def _su_selezione(self, _evento=None):
        self._mostra_cursore()
        if self._alla_selezione is not None:
            self._alla_selezione(self._riga_corrente())

    def _su_tasto(self, evento):
        # un carattere scritto su una cella la modifica, come in Excel: si
        # comincia a scrivere senza doppio clic, e il vecchio valore si perde
        controllo = evento.state & 0x4
        if evento.char and evento.char.isprintable() and not controllo:
            self._inizia_modifica(evento.char)
            return "break"

    def _cambia_colonna(self, passo: int):
        self._colonna = max(0, min(self.n - 1, self._colonna + passo))
        self._mostra_cursore()
        return "break"

    def _svuota_celle(self):
        if self._colonna not in self._modificabili:
            return "break"
        cambiate = False
        for iid in self.albero.selection():
            r = int(iid)
            if self._righe[r][self._colonna]:
                self._righe[r][self._colonna] = ""
                self._aggiorna_riga(r)
                cambiate = True
        if cambiate:
            self._al_cambio()
        return "break"

    # -- modifica di una cella --------------------------------------------

    def _inizia_modifica(self, testo_iniziale: Optional[str] = None):
        self._termina_modifica(salva=True)
        r = self._riga_corrente()
        c = self._colonna
        if r is None or c not in self._modificabili:
            return "break"
        self.albero.see(str(r))
        self.albero.update_idletasks()
        riquadro = self.albero.bbox(str(r), f"c{c}")
        if not riquadro:
            return "break"
        valori = self._scelte(r, c)
        if valori is not None:
            campo = ttk.Combobox(self.albero, values=valori)
            campo.bind("<<ComboboxSelected>>", lambda e: self._termina_modifica(True))
        else:
            campo = ttk.Entry(self.albero)
        campo.insert(0, self._righe[r][c] if testo_iniziale is None else testo_iniziale)
        if testo_iniziale is None:
            campo.select_range(0, tk.END)
        campo.icursor(tk.END)
        x, y, l, h = riquadro
        campo.place(x=x, y=y, width=max(l, 60), height=h)
        campo.focus_set()
        campo.bind("<Return>", lambda e: self._conferma_e_vai(1, 0))
        campo.bind("<KP_Enter>", lambda e: self._conferma_e_vai(1, 0))
        campo.bind("<Tab>", lambda e: self._conferma_e_vai(0, 1))
        campo.bind("<Shift-Tab>", lambda e: self._conferma_e_vai(0, -1))
        campo.bind("<Escape>", lambda e: self._annulla_modifica())
        campo.bind("<FocusOut>", self._su_uscita)
        self._editor = campo
        self._in_modifica = (r, c)
        return "break"

    def _su_uscita(self, _evento):
        # L'elenco a discesa di un Combobox prende il fuoco quando si apre: non
        # e' un'uscita dalla cella. Tkinter non conosce quella finestra e
        # focus_get() lo dice sollevando KeyError.
        def controlla():
            try:
                dove = self.focus_get()
            except (KeyError, tk.TclError):  # TclError: finestra gia' chiusa
                return
            if self._editor is not None and dove is not self._editor:
                self._termina_modifica(salva=True)

        self.after(1, controlla)

    def _conferma_e_vai(self, righe: int, colonne: int):
        r, c = self._in_modifica or (self._riga_corrente() or 0, self._colonna)
        self._termina_modifica(salva=True)
        r = max(0, min(len(self._righe) - 1, r + righe))
        c = max(0, min(self.n - 1, c + colonne))
        self.vai_a(r, c)
        return "break"

    def _annulla_modifica(self):
        self._termina_modifica(salva=False)
        self.albero.focus_set()
        return "break"

    def _termina_modifica(self, salva: bool):
        campo, dove = self._editor, self._in_modifica
        if campo is None:
            return
        self._editor = None
        self._in_modifica = None
        testo = campo.get().strip()
        campo.destroy()
        if not salva or dove is None:
            return
        r, c = dove
        if r < len(self._righe) and self._righe[r][c] != testo:
            self._righe[r][c] = testo
            self._aggiorna_riga(r)
            self._al_cambio()

    # -- righe -------------------------------------------------------------

    def _selezionate(self) -> list[int]:
        return sorted(int(i) for i in self.albero.selection())

    def aggiungi_riga(self):
        self._termina_modifica(salva=True)
        self._righe.append([""] * self.n)
        self._ridisegna()
        self.vai_a(len(self._righe) - 1, min(self._modificabili))
        self._al_cambio()

    def inserisci_riga(self):
        self._termina_modifica(salva=True)
        dove = (self._selezionate() or [len(self._righe)])[0]
        self._righe.insert(dove, [""] * self.n)
        self._ridisegna()
        self.vai_a(dove, min(self._modificabili))
        self._al_cambio()

    def elimina_righe(self):
        self._termina_modifica(salva=True)
        via = self._selezionate()
        if not via:
            return
        for r in reversed(via):
            del self._righe[r]
        self._errori = set()
        self._ridisegna()
        if self._righe:
            self.vai_a(min(via[0], len(self._righe) - 1))
        self._al_cambio()

    def sposta_righe(self, passo: int):
        """Su o giu' di una posizione: nel Percorso e nelle Zone l'ordine
        delle righe E' il dato."""
        self._termina_modifica(salva=True)
        scelte = self._selezionate()
        if not scelte:
            return
        if scelte[0] + passo < 0 or scelte[-1] + passo >= len(self._righe):
            return
        for r in scelte if passo < 0 else reversed(scelte):
            self._righe[r], self._righe[r + passo] = self._righe[r + passo], self._righe[r]
        self._errori = set()
        self._ridisegna()
        self.albero.selection_set([str(r + passo) for r in scelte])
        self.albero.focus(str(scelte[0] + passo))
        self.after_idle(self._mostra_cursore)
        self._al_cambio()

    # -- appunti -----------------------------------------------------------

    def copia(self):
        """Le righe selezionate, separate da tabulazioni: si incollano in Excel
        cella per cella."""
        scelte = self._selezionate()
        if not scelte:
            return "break"
        self.clipboard_clear()
        self.clipboard_append(
            "\n".join("\t".join(self._righe[r]) for r in scelte)
        )
        return "break"

    def incolla(self):
        """Incolla un blocco copiato da Excel (o da qui) a partire dalla cella
        corrente, aggiungendo le righe che mancano. E' il modo di riportare
        dentro una tabella gia' scritta altrove senza ricopiarla a mano."""
        self._termina_modifica(salva=True)
        try:
            testo = self.clipboard_get()
        except tk.TclError:
            return "break"
        blocco = [riga.split("\t") for riga in testo.rstrip("\r\n").splitlines()]
        if not blocco:
            return "break"
        inizio = self._riga_corrente()
        if inizio is None:
            inizio = len(self._righe) if not self._righe_fisse else 0
        cambiate = False
        for i, valori in enumerate(blocco):
            r = inizio + i
            if r >= len(self._righe):
                if self._righe_fisse:
                    break
                self._righe.append([""] * self.n)
            for j, valore in enumerate(valori):
                c = self._colonna + j
                if c < self.n and c in self._modificabili:
                    self._righe[r][c] = valore.strip()
                    cambiate = True
        self._ridisegna()
        self.vai_a(inizio)
        if cambiate:
            self._al_cambio()
        return "break"


# --------------------------------------------------------------------------
# La finestra
# --------------------------------------------------------------------------


# Le schede: (foglio, titolo della scheda, spiegazione). Il foglio e' quello
# che compare nei messaggi d'errore, ed e' cosi' che un errore trova la sua.
_SCHEDE = [
    (
        FOGLIO_VASCHE,
        "Vasche",
        "Una riga per vasca fisica. Posizione lungo la rotaia in mm. Corsa "
        "verticale e sgocciolamento sono obbligatori: 0 dove non servono "
        "(carico, scarico). Posti vuoto = 1; svincoli, gancio basso, larghezza "
        "e altezza si possono lasciare vuoti.",
    ),
    (
        FOGLIO_PERCORSO,
        "Percorso",
        "Una riga per tappa, NELL'ORDINE in cui il pezzo attraversa la linea "
        "(Su / Giu' per riordinare). Permanenza teorica in secondi, piu' due "
        "delta: ampiezze, positive tutte e due. Pesi vuoti = 1.",
    ),
    (
        FOGLIO_PARAMETRI,
        "Parametri",
        "Un valore per parametro. In grassetto gli obbligatori; gli altri, "
        "lasciati vuoti, prendono il valore della colonna 'se vuoto'. "
        "Seleziona una riga per leggere cosa vuol dire.",
    ),
    (
        FOGLIO_ZONE,
        "Zone",
        "Facoltativo. Una riga per carroponte, nell'ordine della linea: la "
        "vasca minima e la massima che puo' raggiungere. Vuoto = numero di "
        "carroponti e zone scelti automaticamente.",
    ),
    (
        FOGLIO_CAMBIO_QUOTA,
        "Cambio quota",
        "Facoltativo. Al piu' una riga 'carico' (fra il carico e la prima "
        "vasca) e una 'scarico' (fra l'ultima vasca e lo scarico). Vuoto = "
        "nessuna zona di cambio quota, che e' il caso normale.",
    ),
]


class FinestraDatiLinea(tk.Toplevel):
    """Le tabelle della linea in una finestra a se', accanto al grafico: si
    cambia un tempo, si applica, e si ricalcola senza chiuderla.

    `applica(righe, origine)` e' la finestra principale che prova a usare le
    tabelle: restituisce True se le ha prese, False se l'utente ci ha
    ripensato, e solleva ValueError con i messaggi di `leggi_righe` se sono
    sbagliate. `salvato(percorso, righe)` le dice che le tabelle ora stanno
    in quel file."""

    def __init__(
        self,
        padre,
        righe: RigheLinea,
        origine: Optional[str],
        applica: Callable[[RigheLinea, Optional[str]], bool],
        salvato: Callable[[str, RigheLinea], None],
        applicate: bool = True,
        errori: Optional[str] = None,
    ):
        super().__init__(padre)
        self.geometry("1100x640")
        self.minsize(760, 440)
        self._applica = applica
        self._salvato = salvato
        self.origine = origine
        # Le tabelle com'erano l'ultima volta che la linea del programma era
        # proprio questa. None quando non lo e' mai stata (un esempio, un file
        # che non si leggeva): allora "Applica" e' acceso anche senza toccare
        # niente, perche' applicare cambia comunque la linea.
        self._base: Optional[tuple] = None
        self._caricata: tuple = ()

        cima = ttk.Frame(self, padding=(10, 8, 10, 0))
        cima.pack(fill=tk.X)
        self.etichetta_origine = ttk.Label(cima, font=("", 10, "bold"))
        self.etichetta_origine.pack(anchor=tk.W)
        ttk.Label(
            cima,
            text="Doppio clic, Invio o semplicemente scrivere per modificare "
            "una cella; Canc la svuota; Tab e Invio passano alla successiva. "
            "Ctrl+C / Ctrl+V copiano e incollano righe, anche da e verso "
            "Excel.",
            foreground="#666666",
        ).pack(anchor=tk.W)

        # -- in fondo, impacchettato PRIMA del centro: il centro si prende
        #    tutto lo spazio che avanza, e altrimenti non ne lascerebbe -----
        piede = ttk.Frame(self, padding=(10, 6, 10, 10))
        piede.pack(side=tk.BOTTOM, fill=tk.X)
        self.etichetta_stato = ttk.Label(piede, text="")
        self.etichetta_stato.pack(side=tk.LEFT)
        ttk.Button(piede, text="Chiudi", command=self.chiudi).pack(side=tk.RIGHT)
        ttk.Button(
            piede, text="Salva come Excel...", command=self.salva
        ).pack(side=tk.RIGHT, padx=(0, 6))
        self.btn_ripristina = ttk.Button(
            piede, text="Annulla modifiche", command=self.ripristina
        )
        self.btn_ripristina.pack(side=tk.RIGHT, padx=(0, 6))
        self.btn_applica = ttk.Button(
            piede, text="Applica alla linea", command=self.applica
        )
        self.btn_applica.pack(side=tk.RIGHT, padx=(0, 6))

        # gli errori dell'ultimo "Applica": nascosti finche' non ce ne sono
        self.cornice_errori = ttk.LabelFrame(
            self, text="Da correggere", padding=6
        )
        self.lista_errori = ttk.Treeview(
            self.cornice_errori,
            columns=("dove", "messaggio"),
            show="headings",
            height=3,
        )
        self.lista_errori.heading("dove", text="dove")
        self.lista_errori.heading("messaggio", text="cosa non va")
        self.lista_errori.column("dove", width=150, stretch=False)
        self.lista_errori.column("messaggio", width=800)
        self.lista_errori.pack(fill=tk.X)
        self.lista_errori.bind("<<TreeviewSelect>>", self._vai_all_errore)
        self.dettaglio_errore = ttk.Label(
            self.cornice_errori, text="", wraplength=1000, justify=tk.LEFT
        )
        self.dettaglio_errore.pack(fill=tk.X, pady=(4, 0))
        self._errori: list[tuple] = []

        self.schede = ttk.Notebook(self)
        self.schede.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 0))
        self.griglie: dict[str, _Griglia] = {}
        for foglio, titolo, spiegazione in _SCHEDE:
            pagina = ttk.Frame(self.schede, padding=6)
            self.schede.add(pagina, text=titolo)
            ttk.Label(
                pagina, text=spiegazione, foreground="#444444", wraplength=1000,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, pady=(0, 6))
            griglia = self._crea_griglia(foglio, pagina)
            griglia.pack(fill=tk.BOTH, expand=True)
            self.griglie[foglio] = griglia
            if foglio == FOGLIO_PARAMETRI:
                self.descrizione_parametro = ttk.Label(
                    pagina, text="", wraplength=1000, justify=tk.LEFT,
                    foreground="#444444",
                )
                self.descrizione_parametro.pack(fill=tk.X, pady=(6, 0))
        self.griglie[FOGLIO_PARAMETRI].etichetta(
            "obbligatorio",
            {i for i, (_u, obbl, _d, _t) in enumerate(PARAMETRI.values()) if obbl},
            font=("", 9, "bold"),
        )

        self.protocol("WM_DELETE_WINDOW", self.chiudi)
        self.carica(righe, origine, applicate=applicate, errori=errori)

    # -- costruzione -------------------------------------------------------

    def _id_vasche(self, _riga=None, _colonna=None) -> list[str]:
        return [r[0] for r in self.griglie[FOGLIO_VASCHE].righe() if r[0]]

    def _crea_griglia(self, foglio: str, pagina) -> _Griglia:
        if foglio == FOGLIO_VASCHE:
            return _Griglia(
                pagina,
                COLONNE_VASCHE,
                [150, 100, 60, 130, 120, 150, 150, 190, 100, 100],
                self._cambiato,
                numerazione="n",
                scelte=lambda r, c: ["", "1", "0"] if c == 7 else None,
            )
        if foglio == FOGLIO_PERCORSO:
            return _Griglia(
                pagina,
                COLONNE_PERCORSO,
                [170, 150, 130, 130, 100, 100],
                self._cambiato,
                numerazione="n",
                scelte=lambda r, c: self._id_vasche() if c == 0 else None,
            )
        if foglio == FOGLIO_PARAMETRI:
            nomi = list(PARAMETRI)
            return _Griglia(
                pagina,
                ["parametro", "valore", "unita'", "se vuoto"],
                [280, 120, 80, 160],
                self._cambiato,
                modificabili={1},
                righe_fisse=True,
                scelte=lambda r, c: (
                    ["0", "1"]
                    if nomi[r] in ("takt_fisso", "interblocco_vasche")
                    else None
                ),
                alla_selezione=self._descrivi_parametro,
            )
        if foglio == FOGLIO_ZONE:
            return _Griglia(
                pagina,
                COLONNE_ZONE,
                [170, 170],
                self._cambiato,
                numerazione="carroponte",
                scelte=self._id_vasche,
            )
        return _Griglia(
            pagina,
            COLONNE_CAMBIO_QUOTA,
            [100, 120, 140, 140, 140],
            self._cambiato,
            scelte=lambda r, c: list(VERSI_CAMBIO_QUOTA) if c == 0 else None,
        )

    def _descrivi_parametro(self, riga: Optional[int]):
        if riga is None:
            self.descrizione_parametro.configure(text="")
            return
        nome = list(PARAMETRI)[riga]
        unita, obbligatorio, default, descrizione = PARAMETRI[nome]
        quando_vuoto = (
            "obbligatorio"
            if obbligatorio
            else f"facoltativo, vuoto = {testo_cella(default) or 'vedi sotto'}"
        )
        self.descrizione_parametro.configure(
            text=f"{nome} [{unita}] ({quando_vuoto})\n{descrizione}"
        )

    # -- dati --------------------------------------------------------------

    def carica(
        self,
        righe: RigheLinea,
        origine: Optional[str],
        applicate: bool = True,
        errori: Optional[str] = None,
    ):
        """Mette nelle tabelle una linea. `applicate` dice se e' gia' quella
        del programma: allora non c'e' niente da applicare finche' non si
        cambia qualcosa."""
        self.origine = origine
        g = self.griglie
        g[FOGLIO_VASCHE].imposta(righe.vasche)
        g[FOGLIO_PERCORSO].imposta(righe.percorso)
        g[FOGLIO_PARAMETRI].imposta(
            [
                [
                    nome,
                    righe.parametri.get(nome),
                    unita,
                    "obbligatorio" if obbl else testo_cella(default) or "-",
                ]
                for nome, (unita, obbl, default, _d) in PARAMETRI.items()
            ]
        )
        g[FOGLIO_ZONE].imposta(righe.zone)
        g[FOGLIO_CAMBIO_QUOTA].imposta(righe.cambio_quota)
        self._base = self._firma() if applicate else None
        # com'erano appena caricate: per sapere, chiudendo, se c'e' del lavoro
        # da perdere anche quando non sono ancora la linea del programma
        self._caricata = self._firma()
        self._mostra_errori(errori)
        self._aggiorna_intestazione()
        self._cambiato()

    def righe(self) -> RigheLinea:
        """Le tabelle come sono adesso, senza le righe lasciate vuote."""

        def piene(righe):
            return [r for r in righe if any(r)]

        return RigheLinea(
            vasche=piene(self.griglie[FOGLIO_VASCHE].righe()),
            percorso=piene(self.griglie[FOGLIO_PERCORSO].righe()),
            parametri={
                r[0]: r[1] for r in self.griglie[FOGLIO_PARAMETRI].righe()
            },
            zone=piene(self.griglie[FOGLIO_ZONE].righe()),
            cambio_quota=piene(self.griglie[FOGLIO_CAMBIO_QUOTA].righe()),
        )

    def _firma(self) -> tuple:
        r = self.righe()
        return (
            tuple(map(tuple, r.vasche)),
            tuple(map(tuple, r.percorso)),
            tuple(sorted(r.parametri.items())),
            tuple(map(tuple, r.zone)),
            tuple(map(tuple, r.cambio_quota)),
        )

    def da_applicare(self) -> bool:
        return self._base is None or self._firma() != self._base

    def modificata(self) -> bool:
        """Se c'e' del lavoro che chiudendo andrebbe perso: le tabelle non
        sono piu' quelle applicate o, se non lo sono mai state, quelle
        caricate."""
        return self._firma() != (self._base or self._caricata)

    def imposta_parametro(self, nome: str, valore):
        """Cambia un parametro da fuori -- il selettore "Takt fisso" della
        finestra principale -- senza farlo contare come una modifica da
        applicare: la linea del programma ce l'ha gia'."""
        if nome not in PARAMETRI:
            return
        pulita = not self.da_applicare()
        self.griglie[FOGLIO_PARAMETRI].imposta_cella(
            list(PARAMETRI).index(nome), 1, testo_cella(valore)
        )
        if pulita:
            self._base = self._firma()
        self._cambiato()

    # -- stato -------------------------------------------------------------

    def _aggiorna_intestazione(self):
        if self.origine:
            testo = f"Linea: {self.origine}"
        else:
            testo = "Linea nuova, non ancora salvata"
        self.etichetta_origine.configure(text=testo)
        nome = os.path.basename(self.origine) if self.origine else "linea nuova"
        self.title(f"Dati linea - {nome}")

    def _cambiato(self):
        da_applicare = self.da_applicare()
        self.btn_applica.configure(state=tk.NORMAL if da_applicare else tk.DISABLED)
        self.btn_ripristina.configure(
            state=tk.NORMAL if self._base is not None and da_applicare else tk.DISABLED
        )
        if self._base is None:
            testo = "Questi dati non sono ancora la linea del programma: premi Applica"
        elif da_applicare:
            testo = "Modifiche non ancora applicate alla linea"
        else:
            testo = "Questa e' la linea in uso"
        self.etichetta_stato.configure(text=testo)

    # -- errori ------------------------------------------------------------

    def _mostra_errori(self, testo: Optional[str]):
        """Gli errori di `leggi_righe` (o di un file), uno per riga, con le
        righe delle tabelle colorate."""
        self.lista_errori.delete(*self.lista_errori.get_children())
        self._errori = []
        for g in self.griglie.values():
            g.segna_errori(set())
        self.dettaglio_errore.configure(text="")
        if not testo:
            self.cornice_errori.pack_forget()
            return
        da_segnare: dict[str, set[int]] = {}
        sciolte = []
        for linea in testo.splitlines()[1:]:
            m = _RIGA_ERRORE.match(linea)
            if m is None:
                if linea.strip():
                    sciolte.append(linea.strip())
                continue
            foglio, lettera, numero, messaggio = m.groups()
            riga = int(numero) - 2 if numero else None
            colonna = ord(lettera[0]) - ord("A") if lettera else None
            if foglio == FOGLIO_PERCORSO and colonna is not None:
                colonna -= 1  # la colonna "n" del foglio non e' nella tabella
            dove = f"{foglio}" + (f", riga {riga + 1}" if riga is not None else "")
            self._errori.append((foglio, riga, colonna, messaggio))
            if riga is not None:
                da_segnare.setdefault(foglio, set()).add(riga)
            self.lista_errori.insert("", tk.END, values=(dove, messaggio))
        if not self._errori:
            # un errore senza cella: le incoerenze fra fogli che controlla
            # ProblemData. Si mostra intero, che e' gia' scritto per un umano.
            messaggio = " ".join(sciolte) or testo.strip()
            self._errori.append((None, None, None, messaggio))
            self.lista_errori.insert("", tk.END, values=("-", messaggio))
        for foglio, righe in da_segnare.items():
            if foglio in self.griglie:
                self.griglie[foglio].segna_errori(righe)
        self.cornice_errori.pack(
            side=tk.BOTTOM, fill=tk.X, padx=10, pady=(6, 0), before=self.schede
        )
        primo = self.lista_errori.get_children()[0]
        self.lista_errori.selection_set(primo)

    def _vai_all_errore(self, _evento=None):
        scelta = self.lista_errori.selection()
        if not scelta:
            return
        foglio, riga, colonna, messaggio = self._errori[
            self.lista_errori.index(scelta[0])
        ]
        self.dettaglio_errore.configure(text=messaggio)
        if foglio not in self.griglie:
            return
        self.schede.select([f for f, _t, _s in _SCHEDE].index(foglio))
        if riga is not None:
            self.griglie[foglio].vai_a(riga, colonna)

    # -- comandi -----------------------------------------------------------

    def applica(self) -> bool:
        righe = self.righe()
        try:
            presa = self._applica(righe, self.origine)
        except ValueError as e:
            self._mostra_errori(str(e))
            self.etichetta_stato.configure(
                text="Non applicate: correggi i punti segnati in rosso"
            )
            return False
        except Exception as e:  # pragma: no cover - errori imprevisti
            messagebox.showerror("Dati linea", str(e), parent=self)
            return False
        if not presa:
            return False
        self._base = self._firma()
        self._mostra_errori(None)
        self._cambiato()
        return True

    def ripristina(self):
        """Torna alle tabelle della linea in uso."""
        if self._base is None:
            return
        vasche, percorso, parametri, zone, cambio = self._base
        self.carica(
            RigheLinea(
                vasche=[list(r) for r in vasche],
                percorso=[list(r) for r in percorso],
                parametri=dict(parametri),
                zone=[list(r) for r in zone],
                cambio_quota=[list(r) for r in cambio],
            ),
            self.origine,
        )

    def salva(self) -> Optional[str]:
        iniziale = os.path.basename(self.origine) if self.origine else "linea.xlsx"
        cartella = os.path.dirname(self.origine) if self.origine else None
        percorso = filedialog.asksaveasfilename(
            parent=self,
            title="Salva i dati della linea",
            defaultextension=".xlsx",
            initialfile=iniziale,
            initialdir=cartella,
            filetypes=[("File Excel", "*.xlsx")],
        )
        if not percorso:
            return None
        return self.salva_in(percorso)

    def salva_in(self, percorso: str) -> Optional[str]:
        righe = self.righe()
        try:
            scrivi_righe(percorso, righe)
        except Exception as e:
            messagebox.showerror(
                "Dati linea - impossibile salvare", str(e), parent=self
            )
            return None
        self.origine = os.path.normpath(os.path.abspath(percorso))
        self._aggiorna_intestazione()
        self._salvato(self.origine, righe)
        self.etichetta_stato.configure(
            text=f"Salvato in {os.path.basename(percorso)}"
            + (" (non ancora applicato alla linea)" if self.da_applicare() else "")
        )
        return self.origine

    def chiudi(self):
        if self.modificata():
            risposta = messagebox.askyesnocancel(
                "Dati linea",
                "Ci sono modifiche non applicate alla linea.\n\n"
                "Applicarle prima di chiudere?",
                parent=self,
            )
            if risposta is None:
                return
            if risposta and not self.applica():
                return
        self.destroy()
