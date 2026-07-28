"""
esempio.py
----------
Esempio d'uso completo: definizione di una linea con 6 stazioni (carico,
4 vasche di processo, scarico) servita da 2 carroponti, con le ZONE scelte
automaticamente, risoluzione del ciclogramma con CP-SAT e visualizzazione
del risultato.

Per eseguirlo:
    pip install ortools matplotlib
    python esempio.py
"""

import matplotlib

matplotlib.use("Agg")  # rimuovi questa riga se lavori in un ambiente interattivo
import matplotlib.pyplot as plt

from kinematics import Kinematics
from model import Tank, StationSpec, HoistZone, ProblemData, solve, solve_auto_zones
from plotting import plot_cyclogram


def main():
    # ---------------------------------------------------------------
    # 1) Vasche: id -> posizione [m] lungo la rotaia
    # ---------------------------------------------------------------
    tanks = {
        "CARICO": Tank("CARICO", 0.0),
        "SGRASSO": Tank("SGRASSO", 2.5),
        "RISCIACQUO_1": Tank("RISCIACQUO_1", 5.5),
        "ZINCATURA": Tank("ZINCATURA", 9.5),
        "RISCIACQUO_2": Tank("RISCIACQUO_2", 13.0),
        "PASSIVAZIONE": Tank("PASSIVAZIONE", 16.5),
        "SCARICO": Tank("SCARICO", 20.0),
    }

    # ---------------------------------------------------------------
    # 2) Percorso del pezzo: sequenza di stazioni con tempo di
    #    permanenza [min,max] in secondi (tolleranza di processo)
    # ---------------------------------------------------------------
    route = [
        StationSpec("CARICO", 0, 0),
        StationSpec("SGRASSO", 60, 90),
        StationSpec("RISCIACQUO_1", 20, 40),
        StationSpec("ZINCATURA", 180, 220),
        StationSpec("RISCIACQUO_2", 20, 40),
        StationSpec("PASSIVAZIONE", 30, 45),
        StationSpec("SCARICO", 0, 0),
    ]

    # ---------------------------------------------------------------
    # 3) Cinematica dei carroponti (vuoto / carico)
    # ---------------------------------------------------------------
    kin_empty = Kinematics(v_max=1.6, a_max=0.9)  # piu' veloce senza pezzo
    kin_loaded = Kinematics(v_max=1.0, a_max=0.4)  # piu' lento/dolce con il pezzo

    # ---------------------------------------------------------------
    # 4) Takt time target con tolleranza, ingombro carroponte, sicurezza
    # ---------------------------------------------------------------
    takt_nominale = 130.0  # [s]
    takt_tolleranza = 20.0  # [s]  -> range ammesso [110, 150] s

    hoist_length = 1.2  # [m] ingombro del carrello lungo la rotaia
    safety_distance = 0.6  # [m] distanza minima aggiuntiva fra due carroponti

    # ---------------------------------------------------------------
    # 5) Numero di carroponti: resta un INPUT (hard-coded). Le ZONE
    #    (quali vasche assegnare a quale carroponte) sono invece scelte
    #    automaticamente da solve_auto_zones: passiamo zones=None.
    # ---------------------------------------------------------------
    n_hoists = 2

    data = ProblemData(
        tanks=tanks,
        route=route,
        takt_min=takt_nominale - takt_tolleranza,
        takt_max=takt_nominale + takt_tolleranza,
        kin_empty=kin_empty,
        kin_loaded=kin_loaded,
        hoist_length=hoist_length,
        safety_distance=safety_distance,
        zones=None,  # <-- da scegliere automaticamente
        time_scale=100,  # risoluzione: centesimi di secondo
    )

    print(
        f"Stazioni: {data.n_stations}  |  Mosse: {data.n_moves}  |  Carroponti: {n_hoists}"
    )
    print(f"Takt time ammesso: [{data.takt_min:.1f}, {data.takt_max:.1f}] s")

    # ---------------------------------------------------------------
    # 6) Risoluzione: prova tutte le suddivisioni contigue delle mosse in
    #    n_hoists zone e tiene quella con il takt time minore.
    # ---------------------------------------------------------------
    print("Provo automaticamente le suddivisioni in zone possibili...")
    solution, zones = solve_auto_zones(
        data, n_hoists=n_hoists, time_limit_per_candidate=15.0, log_progress=True
    )
    print(
        f"Stato: {solution.status}  "
        f"(suddivisioni tentate: {solution.raw.get('n_tried', '?')}, "
        f"scartate a priori: {solution.raw.get('n_skipped', '?')})"
    )

    if solution.status not in ("OPTIMAL", "FEASIBLE"):
        print("Nessuna suddivisione in zone e' risultata fattibile entro la")
        print("tolleranza di takt time data. Prova ad aumentare la tolleranza")
        print("o il numero di carroponti.")
        return

    print(f"Zone scelte automaticamente: {[(z.lo, z.hi) for z in zones]}")
    print(f"Takt time trovato: {solution.T:.2f} s")

    # data.zones e' rimasto None: per il grafico serve la versione con le
    # zone effettivamente usate dalla soluzione trovata.
    import dataclasses

    data_final = dataclasses.replace(data, zones=zones)

    # ---------------------------------------------------------------
    # 7) Grafico del ciclogramma (2 cicli per mostrare la periodicita')
    # ---------------------------------------------------------------
    plot_cyclogram(
        data_final,
        solution,
        n_cycles=2,
        title="Ciclogramma linea di zincatura",
        save_path="ciclogramma.png",
    )
    print("Grafico salvato in ciclogramma.png")


if __name__ == "__main__":
    main()
