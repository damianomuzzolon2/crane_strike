"""
ciclogramma.py
--------------
Comando principale: legge la definizione di una linea da un file Excel, calcola
il ciclogramma, lo verifica e produce i risultati.

    python ciclogramma.py --modello linea.xlsx    crea il file da compilare
    python ciclogramma.py linea.xlsx              calcola il ciclogramma

Produce, accanto al file di ingresso:
    linea_risultati.xlsx   riepilogo, movimenti, flusso del pezzo, verifica
    linea.png              il ciclogramma disegnato

Opzioni utili:
    --risultati FILE.xlsx dove salvare i risultati
    --grafico FILE.png    dove salvare il ciclogramma
    --cicli N             quanti periodi disegnare (default 2)
    --niente-grafico      salta il disegno
    --niente-excel        salta il file dei risultati
    --log                 mostra i tentativi della ricerca automatica
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys

from allinea_avvio import allinea_avvio, descrivi
from avvio import righe_di_riepilogo, trova_avvio
from excel_io import leggi_problema, scrivi_modello, scrivi_risultati
from model import (
    TEMPO_RIDUCI_SOSTE_S,
    rifinisci_soluzione,
    solve,
    solve_auto_hoists,
)
from verify import verify_solution


def _argomenti(argv=None):
    p = argparse.ArgumentParser(
        prog="ciclogramma",
        description="Calcola il ciclogramma dei carroponti di una linea "
        "galvanica descritta in un file Excel.",
    )
    p.add_argument("file", help="file Excel con la definizione della linea")
    p.add_argument(
        "--modello",
        action="store_true",
        help="invece di calcolare, scrive in FILE un modello da compilare",
    )
    p.add_argument(
        "--risultati", metavar="FILE.xlsx", help="dove salvare i risultati in Excel"
    )
    p.add_argument("--grafico", metavar="FILE.png", help="dove salvare il ciclogramma")
    p.add_argument(
        "--cicli", type=int, default=2, help="periodi da disegnare (default 2)"
    )
    p.add_argument(
        "--niente-grafico", action="store_true", help="non disegnare il ciclogramma"
    )
    p.add_argument(
        "--niente-excel", action="store_true", help="non scrivere il file dei risultati"
    )
    p.add_argument(
        "--log", action="store_true", help="mostra i tentativi della ricerca automatica"
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _argomenti(argv)

    if args.modello:
        scrivi_modello(args.file)
        print(f"Modello scritto in {args.file}")
        print("Compilalo (parti dal foglio Istruzioni) e poi rilancia:")
        print(f"    python ciclogramma.py {args.file}")
        return 0

    if not os.path.exists(args.file):
        print(f"File non trovato: {args.file}", file=sys.stderr)
        print(
            f"Per crearne uno da compilare: "
            f"python ciclogramma.py --modello {args.file}",
            file=sys.stderr,
        )
        return 2

    try:
        cfg = leggi_problema(args.file)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2

    data = cfg.data
    print(f"Linea letta da {args.file}")
    print(f"  stazioni: {data.n_stations}   mosse: {data.n_moves}")
    print(
        f"  takt time: {data.takt_nominale:.1f} s teorici "
        f"(-{data.takt_delta_neg:.1f} / +{data.takt_delta_pos:.1f}), "
        f"cioe' fra {data.takt_min:.1f} e {data.takt_max:.1f} s"
    )

    # -- risoluzione -------------------------------------------------------
    if cfg.zone_manuali is not None:
        print(
            f"  zone indicate a mano: "
            f"{[(z.lo, z.hi) for z in cfg.zone_manuali]}"
        )
        solution = solve(data, time_limit_s=cfg.tempo_limite_s, log_search=args.log)
        zones = cfg.zone_manuali
        n_hoists = len(zones)
    else:
        print("  cerco numero di carroponti e zone migliori...")
        solution, zones, n_hoists = solve_auto_hoists(
            data,
            max_hoists=cfg.max_carroponti,
            time_limit_per_candidate=cfg.tempo_limite_s,
            log_progress=args.log,
        )

    if solution.status not in ("OPTIMAL", "FEASIBLE"):
        print()
        print(f"Nessuna soluzione trovata (stato: {solution.status}).")
        print("Cosa provare:")
        print(
            "  - allargare la tolleranza sul takt time "
            "(takt_delta_negativo_s / takt_delta_positivo_s)"
        )
        print("  - aumentare max_carroponti")
        print("  - aumentare i posti delle vasche piu' lente")
        print("  - allungare tempo_limite_per_tentativo_s")
        for voce in solution.raw.get("hoist_sweep", []):
            print(f"      {voce}")
        return 1

    data_finale = dataclasses.replace(data, zones=zones)
    # col takt libero, a takt trovato, i tempi in vasca piu' vicini ai
    # teorici; poi le soste inutili rimaste se CP-SAT e' scaduto prima
    # dell'ottimo
    solution = rifinisci_soluzione(
        data_finale,
        solution,
        time_limit_s=cfg.tempo_limite_s,
        time_limit_soste_s=min(cfg.tempo_limite_s, TEMPO_RIDUCI_SOSTE_S),
    )
    if solution.raw.get("errore_pesato_prima") is not None:
        print(
            f"  scarto pesato dai teorici: {solution.raw['errore_pesato_prima']:.2f}"
            f" -> {solution.raw['errore_pesato']:.2f}"
        )
    if solution.raw.get("soste_tolte"):
        print(f"  tolte {solution.raw['soste_tolte']} soste per strada che non servivano")
    # se il punto di avvio e' solo approssimato, si prova a renderlo esatto
    # spostando di qualche secondo il giro di qualche carroponte
    allineato = allinea_avvio(data_finale, solution)
    if allineato is not None:
        solution = allineato.soluzione
        print(
            f"  punto di avvio reso esatto: {descrivi(allineato.spostamenti)} "
            f"(scarto pesato {allineato.errore_pesato_prima:.2f}"
            f" -> {allineato.errore_pesato_dopo:.2f})"
        )
    print()
    print(f"Carroponti: {n_hoists}   zone: {[(z.lo, z.hi) for z in zones]}")
    print(f"Takt time: {solution.T:.2f} s")

    # -- il punto di avvio -------------------------------------------------
    # Lo stesso che finisce nel Riepilogo e sul grafico: qui si stampa perche'
    # chi lancia il comando da terminale non apre necessariamente ne' l'uno ne'
    # l'altro, e questo e' il dato con cui si va all'impianto.
    print()
    for etichetta, valore, nota in righe_di_riepilogo(
        trova_avvio(data_finale, solution)
    ):
        if isinstance(valore, float):
            valore = f"{valore:.2f}"  # due decimali come nel foglio Riepilogo
        print(f"{etichetta}: {valore}   ({nota})")

    # -- verifica indipendente --------------------------------------------
    report = verify_solution(data_finale, solution)
    print()
    print(report.summary())
    if not report.ok:
        print("ATTENZIONE: la soluzione NON supera la verifica indipendente.")
        print("Le violazioni elencate sopra vanno esaminate prima di usare")
        print("questo ciclogramma su un impianto reale.")

    # -- risultati in Excel ------------------------------------------------
    radice = os.path.splitext(args.file)[0]
    if not args.niente_excel:
        destinazione = args.risultati or (radice + "_risultati.xlsx")
        at = solution.actual_time
        scrivi_risultati(
            destinazione,
            data_finale,
            solution,
            report,
            sorgente=args.file,
            # anche da riga di comando il file resta riapribile: e' lo stesso
            # Excel, con la linea e il ciclogramma nei fogli in coda
            cfg=cfg,
            ciclogramma={
                "T": solution.T,
                "n_carroponti": len(data_finale.zones),
                "permanenze": {
                    k: at[k] - (at[k - 1] + data_finale.loaded_leg_seconds(k - 1))
                    for k in range(1, data_finale.n_moves)
                },
                "assegnazione": {
                    k: h
                    for h, z in enumerate(data_finale.zones)
                    for k in range(z.lo, z.hi + 1)
                },
                # dove il solutore ha fatto sostare i carri: senza, il file
                # riaperto sarebbe un ciclogramma diverso da questo
                "attese": {
                    k: v for p in solution.plans for k, v in p.attese.items()
                },
                # e dove si sono fermati per strada, quando l'hanno fatto: li'
                # cambia anche il percorso, non solo quando si muovono
                "soste": {
                    k: v
                    for p in solution.plans
                    for k, v in p.soste_intermedie.items()
                },
            },
        )
        print(f"Risultati salvati in {destinazione}")

    # -- grafico -----------------------------------------------------------
    if not args.niente_grafico:
        import matplotlib

        matplotlib.use("Agg")
        from plotting import plot_cyclogram

        destinazione = args.grafico or (radice + ".png")
        plot_cyclogram(
            data_finale,
            solution,
            n_cycles=args.cicli,
            title=f"Ciclogramma - {os.path.basename(args.file)}",
            save_path=destinazione,
        )
        print(f"Grafico salvato in {destinazione}")

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
