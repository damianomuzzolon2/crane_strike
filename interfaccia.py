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
import os
import queue
import sys
import threading
import traceback

import matplotlib

matplotlib.use("TkAgg")

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
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
from plotting import plot_cyclogram
from verify import verify_solution

TITOLO = "Ciclogrammi carroponti"

# colori delle righe del report, per gravita'
_COLORI_GRAVITA = {
    "error": "#f4cccc",
    "warning": "#fce5cd",
    "info": "#efefef",
}
_ETICHETTE_GRAVITA = {"error": "ERRORE", "warning": "avviso", "info": "nota"}


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
            text="Parti da una proposta semplice",
            command=self._crea_proposta,
        )
        self.btn_proposta.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Separator(barra, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=12
        )

        self.btn_salva = ttk.Button(
            barra, text="Salva risultati...", command=self._salva
        )
        self.btn_salva.pack(side=tk.LEFT)

        self.etichetta_file = ttk.Label(barra, text="Nessuna linea caricata")
        self.etichetta_file.pack(side=tk.RIGHT)

        # -- corpo: grafico a sinistra, pannello a destra -------------------
        corpo = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        corpo.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        cornice_grafico = ttk.Frame(corpo)
        corpo.add(cornice_grafico, weight=3)
        self.figura = Figure(figsize=(9, 6), dpi=100)
        self.assi = self.figura.add_subplot(111)
        self._grafico_vuoto()
        self.tela = FigureCanvasTkAgg(self.figura, master=cornice_grafico)
        self.tela.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.tela.mpl_connect("button_press_event", self._su_pressione)
        self.tela.mpl_connect("motion_notify_event", self._su_movimento)
        self.tela.mpl_connect("button_release_event", self._su_rilascio)

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
            text="Ricalcola da qui",
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
        self.percorso_file = percorso
        self.dati = None
        self.soluzione = None
        self.report = None
        d = self.config_linea.data
        self.etichetta_file.configure(text=os.path.basename(percorso))
        self._scrivi_riepilogo(
            f"Linea: {os.path.basename(percorso)}\n"
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
        self._carica_stato_modificabile()
        self._mostra_risultato()
        self._aggiorna_stato_pulsanti()

    # ------------------------------------------------------------------
    # Presentazione del risultato
    # ------------------------------------------------------------------

    def _mostra_risultato(self):
        sol, dati, rep = self.soluzione, self.dati, self.report
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
        self.schede.tab(2, text=f"Verifica ({len(rep.violations)})")

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
        if self._trascinamento is None or evento.xdata is None:
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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    file_iniziale = argv[0] if argv else None
    app = Applicazione(file_iniziale)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
