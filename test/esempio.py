"""
esempio.py
----------
Esempio d'uso completo: definizione di una linea con 6 stazioni (carico,
4 vasche di processo, scarico). Sia il NUMERO di carroponti che le loro
ZONE vengono scelti automaticamente (numero minimo che rispetta il takt
time dato), poi si risolve il ciclogramma con CP-SAT e lo si visualizza.

Per eseguirlo:
    pip install ortools matplotlib
    python test/esempio.py
"""

import dataclasses
import os
import sys

# I moduli del programma stanno nella cartella sopra questa: senza aggiungerla
# fra i percorsi di ricerca, lanciare l'esempio da qui non li troverebbe.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib

matplotlib.use("Agg")  # rimuovi questa riga se lavori in un ambiente interattivo
import matplotlib.pyplot as plt

from kinematics import Kinematics
from model import Tank, StationSpec, HoistZone, ProblemData, solve_auto_hoists
from plotting import plot_cyclogram
from verify import verify_solution


def main():
    # ---------------------------------------------------------------
    # 1) Vasche: id -> posizione [m] lungo la rotaia
    # ---------------------------------------------------------------
    #    `capacity` = posti simultanei nella vasca (default 1). ZINCATURA ha
    #    una permanenza di ~190 s con takt time ~110 s: per forza di cose ci
    #    sono sempre 2 pezzi dentro, quindi deve essere una vasca a (almeno)
    #    2 posti. Se fosse a posto singolo il takt time non potrebbe scendere
    #    sotto la permanenza.
    #    `lift_height` (corsa verticale) e `drain_time` (sgocciolamento) si
    #    dichiarano per OGNI vasca: dipendono da quanto e' profonda e da cosa
    #    contiene, non dal carroponte. Non c'e' un valore generale da cui
    #    ereditare -- dove non serve niente si scrive 0, che e' una scelta
    #    esplicita e non una dimenticanza.
    tanks = {
        # carico e scarico non sono bagni: niente corsa, niente scolo
        "CARICO": Tank("CARICO", 0, lift_height=0, drain_time=0),
        "SGRASSO": Tank("SGRASSO", 2500, lift_height=800, drain_time=2.0),
        "RISCIACQUO_1": Tank("RISCIACQUO_1", 5500, lift_height=800, drain_time=2.0),
        # vasca piu' profonda e con sgocciolamento lungo: il bagno di zinco
        # cola parecchio, e lasciarlo cadere fuori dalla vasca e' uno spreco
        "ZINCATURA": Tank(
            "ZINCATURA", 9500, capacity=2, lift_height=1100, drain_time=8.0
        ),
        "RISCIACQUO_2": Tank("RISCIACQUO_2", 13000, lift_height=800, drain_time=2.0),
        "PASSIVAZIONE": Tank("PASSIVAZIONE", 16500, lift_height=800, drain_time=3.0),
        "SCARICO": Tank("SCARICO", 20000, lift_height=0, drain_time=0),
    }

    # ---------------------------------------------------------------
    # 2) Percorso del pezzo: sequenza di stazioni con tempo di
    #    permanenza [min,max] in secondi (tolleranza di processo).
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
    kin_empty = Kinematics(v_max=1600, a_max=900)  # piu' veloce senza pezzo
    kin_loaded = Kinematics(v_max=1000, a_max=400)  # piu' lento/dolce con il pezzo

    # ---------------------------------------------------------------
    # 4) Takt time target con tolleranza, ingombro carroponte, sicurezza
    # ---------------------------------------------------------------
    takt_nominale = 130.0  # [s]
    takt_tolleranza = 20.0  # [s]  -> range ammesso [110, 150] s

    # Ingombro del carrello lungo la rotaia, misurato dal gancio: i due lati
    # si dichiarano separatamente perche' il carrello non e' detto sia
    # simmetrico. Qui il gancio e' spostato verso le posizioni decrescenti.
    hoist_extent_pos = 500  # [mm] verso le posizioni crescenti
    hoist_extent_neg = 700  # [mm] verso le posizioni decrescenti
    safety_distance = 600  # [mm] distanza minima aggiuntiva fra due carroponti

    # ---------------------------------------------------------------
    # 4-bis) Movimentazione verticale del pezzo. Il carroponte non si
    #    limita a traslare: cala il gancio, aggancia, tira su il telaio
    #    (con lo sgocciolamento sopra la vasca), e poi lo immerge nella
    #    vasca successiva e sgancia. I tempi non si dichiarano: si
    #    ricavano dalla corsa verticale e dalla cinematica di
    #    sollevamento, come per il moto orizzontale.
    #    NOTA: i tempi di permanenza dichiarati sopra restano il tempo
    #    EFFETTIVO in bagno, misurato da fine immersione a inizio
    #    emersione; le fasi verticali si sommano a parte.
    # ---------------------------------------------------------------
    kin_lift_empty = Kinematics(v_max=500, a_max=800)  # gancio scarico
    kin_lift_loaded = Kinematics(v_max=300, a_max=500)  # col telaio
    engage_time = 2.0  # [s] aggancio del telaio, prima del sollevamento
    disengage_time = 1.0  # [s] sgancio, dopo l'immersione
    # Corsa verticale e sgocciolamento non stanno qui: sono di ogni vasca,
    # dichiarati sopra insieme alla sua posizione.

    # ---------------------------------------------------------------
    # 5) Numero di carroponti E zone: entrambi scelti automaticamente.
    #    zones=None -> le zone le sceglie solve_auto_zones (chiamata
    #    internamente da solve_auto_hoists per ogni numero di carroponti
    #    tentato). max_hoists e' un limite superiore alla ricerca (per
    #    evitare uno sweep infinito se il problema fosse irrisolvibile).
    # ---------------------------------------------------------------
    data = ProblemData(
        tanks=tanks,
        route=route,
        takt_min=takt_nominale - takt_tolleranza,
        takt_max=takt_nominale + takt_tolleranza,
        takt_nominal=takt_nominale,
        kin_empty=kin_empty,
        kin_loaded=kin_loaded,
        hoist_extent_pos=hoist_extent_pos,
        hoist_extent_neg=hoist_extent_neg,
        safety_distance=safety_distance,
        zones=None,  # <-- zone scelte automaticamente
        time_scale=100,  # risoluzione: centesimi di secondo
        kin_lift_empty=kin_lift_empty,
        kin_lift_loaded=kin_lift_loaded,
        engage_time=engage_time,
        disengage_time=disengage_time,
    )
    print("Fasi verticali calcolate:")
    for s in range(1, data.n_moves):
        print(
            f"  {data.route[s].tank_id:14s} presa {data.pick_time_at(s):5.2f} s "
            f"(di cui sgocciolamento {data.drain_time_at(s):4.1f} s), "
            f"rilascio {data.release_time_at(s):5.2f} s"
        )

    print(f"Stazioni: {data.n_stations}  |  Mosse: {data.n_moves}")
    print(
        f"Takt time: {data.takt_nominale:.1f} s teorici "
        f"(-{data.takt_delta_neg:.1f} / +{data.takt_delta_pos:.1f}), "
        f"cioe' [{data.takt_min:.1f}, {data.takt_max:.1f}] s"
    )

    # ---------------------------------------------------------------
    # 6) Risoluzione: prova 1, 2, 3, ... carroponti (fino a max_hoists) e
    #    per ciascuno tutte le suddivisioni in zone possibili, fermandosi
    #    al primo numero di carroponti che risulta fattibile.
    # ---------------------------------------------------------------
    print("Cerco il numero minimo di carroponti e le zone migliori...")
    solution, zones, n_hoists = solve_auto_hoists(
        data,
        max_hoists=4,
        time_limit_per_candidate=15.0,
        log_progress=True,
    )

    if solution.status not in ("OPTIMAL", "FEASIBLE"):
        print("Nessuna combinazione (numero di carroponti, zone) e' risultata")
        print("fattibile entro la tolleranza di takt time data, fino a")
        print("max_hoists carroponti. Prova ad aumentare max_hoists o la")
        print("tolleranza sul takt time.")
        return

    print(f"Numero di carroponti scelto: {n_hoists}")
    print(f"Zone scelte automaticamente: {[(z.lo, z.hi) for z in zones]}")
    print(f"Takt time trovato: {solution.T:.2f} s")

    # data.zones e' rimasto None: per il grafico serve la versione con le
    # zone effettivamente usate dalla soluzione trovata.
    data_final = dataclasses.replace(data, zones=zones)

    # ---------------------------------------------------------------
    # 7) Verifica indipendente: ricontrolla la soluzione in Python puro,
    #    senza passare da CP-SAT, campionando finemente le posizioni reali
    #    dei carroponti. Serve a intercettare eventuali errori nella
    #    formulazione del modello, che altrimenti nessuno noterebbe.
    #    Non e' bloccante: il grafico va disegnato comunque.
    # ---------------------------------------------------------------
    report = verify_solution(data_final, solution)
    print(report.summary())
    if not report.ok:
        print("ATTENZIONE: la soluzione NON supera la verifica indipendente.")
        print("Le violazioni elencate sopra vanno esaminate prima di usare")
        print("questo ciclogramma su un impianto reale.")

    # ---------------------------------------------------------------
    # 8) Grafico del ciclogramma (2 cicli per mostrare la periodicita')
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
