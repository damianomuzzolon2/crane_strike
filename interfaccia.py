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
from model import proposta_semplice, solve, solve_auto_hoists
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

        pannello = ttk.Frame(corpo, width=430)
        corpo.add(pannello, weight=1)

        ttk.Label(pannello, text="Riepilogo", font=("", 10, "bold")).pack(
            anchor=tk.W, pady=(0, 4)
        )
        self.testo_riepilogo = tk.Text(
            pannello, height=13, width=52, wrap=tk.WORD, relief=tk.FLAT,
            background="#f7f7f7",
        )
        self.testo_riepilogo.pack(fill=tk.X)
        self.testo_riepilogo.configure(state=tk.DISABLED)

        ttk.Label(pannello, text="Verifica indipendente", font=("", 10, "bold")).pack(
            anchor=tk.W, pady=(12, 4)
        )
        cornice_tabella = ttk.Frame(pannello)
        cornice_tabella.pack(fill=tk.BOTH, expand=True)
        self.tabella = ttk.Treeview(
            cornice_tabella,
            columns=("gravita", "tipo", "descrizione"),
            show="headings",
            height=12,
        )
        self.tabella.heading("gravita", text="gravita'")
        self.tabella.heading("tipo", text="tipo")
        self.tabella.heading("descrizione", text="descrizione")
        self.tabella.column("gravita", width=70, anchor=tk.W, stretch=False)
        self.tabella.column("tipo", width=110, anchor=tk.W, stretch=False)
        self.tabella.column("descrizione", width=240, anchor=tk.W)
        barra_scorrimento = ttk.Scrollbar(
            cornice_tabella, orient=tk.VERTICAL, command=self.tabella.yview
        )
        self.tabella.configure(yscrollcommand=barra_scorrimento.set)
        self.tabella.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        barra_scorrimento.pack(side=tk.RIGHT, fill=tk.Y)
        for gravita, colore in _COLORI_GRAVITA.items():
            self.tabella.tag_configure(gravita, background=colore)
        self.tabella.bind("<<TreeviewSelect>>", self._mostra_dettaglio)

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
            return

        self.soluzione, self.dati, self.report = sol, dati, report
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
        self._stato(
            f"Ciclogramma pronto - T = {sol.T:.2f} s - "
            + ("verifica superata" if rep.ok else "VERIFICA NON SUPERATA")
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
