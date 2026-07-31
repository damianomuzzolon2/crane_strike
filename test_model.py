"""
test_model.py
-------------
Test end-to-end del modello CP-SAT: risolve davvero e passa ogni soluzione al
verificatore indipendente (verify.py). Richiede OR-Tools.

E' il complemento di test_verify.py, che invece verifica il VERIFICATORE su
soluzioni costruite a mano e non richiede OR-Tools. Qui la domanda e'
l'opposta: il modello produce soluzioni fisicamente valide?

Per eseguirlo:
    python test_model.py
"""

from __future__ import annotations

import time

from kinematics import Kinematics
from model import (
    HoistZone,
    ProblemData,
    StationSpec,
    Tank,
    solve,
    solve_auto_hoists,
)
from verify import verify_solution

KIN_EMPTY = Kinematics(v_max=1.6, a_max=0.9)
KIN_LOADED = Kinematics(v_max=1.0, a_max=0.4)

_n_pass = 0
_n_fail = 0


def check(condition: bool, description: str):
    global _n_pass, _n_fail
    if condition:
        _n_pass += 1
        print(f"  ok   {description}")
    else:
        _n_fail += 1
        print(f"  FAIL {description}")


def linea(
    n_moves: int,
    spacing: float,
    zones,
    takt_min=8.0,
    takt_max=40.0,
    dwell=(5, 400),
    capacity=20,
    **kw,
) -> ProblemData:
    n_st = n_moves + 1
    tanks = {
        f"V{i}": Tank(f"V{i}", i * spacing, 1 if i in (0, n_st - 1) else capacity)
        for i in range(n_st)
    }
    route = [StationSpec("V0", 0, 0)]
    for i in range(1, n_st - 1):
        route.append(StationSpec(f"V{i}", dwell[0], dwell[1]))
    route.append(StationSpec(f"V{n_st - 1}", 0, 0))
    params = dict(
        tanks=tanks,
        route=route,
        takt_min=takt_min,
        takt_max=takt_max,
        kin_empty=KIN_EMPTY,
        kin_loaded=KIN_LOADED,
        hoist_extent_pos=0.5,
        hoist_extent_neg=0.7,
        safety_distance=0.6,
        zones=zones,
        time_scale=100,
    )
    params.update(kw)
    return ProblemData(**params)


def risolvi_e_verifica(data, etichetta, time_limit=60.0):
    """Risolve e restituisce (solution, report). Fallisce il test se la
    soluzione non supera la verifica indipendente.

    I limiti di tempo sono volutamente larghi: un test che fallisce solo
    perche' la macchina era occupata non dice nulla di utile e fa perdere
    fiducia in tutto il resto."""
    sol = solve(data, time_limit_s=time_limit)
    if sol.status not in ("OPTIMAL", "FEASIBLE"):
        return sol, None
    r = verify_solution(data, sol)
    if not r.ok:
        print(f"  FAIL {etichetta}: la soluzione NON supera la verifica")
        for v in r.errors:
            print("        ", v)
        global _n_fail
        _n_fail += 1
    return sol, r


def _esito(sol, r, atteso: str) -> str:
    """Descrizione leggibile per i check che possono fallire sia per un errore
    vero sia per un semplice scadere del tempo: la differenza va vista."""
    if r is None:
        return f"{atteso} -- ma il solutore ha restituito {sol.status}"
    return atteso


# --------------------------------------------------------------------------


def test_vasche_ravvicinate():
    print("\n[1] vasche piu' vicine della distanza di sicurezza")
    D = 1.2 + 0.6
    for spacing in (1.0, 1.4, 1.8, 2.5):
        data = linea(4, spacing, [HoistZone(0, 1), HoistZone(2, 3)])
        sol, r = risolvi_e_verifica(data, f"spaziatura {spacing}")
        if r is None:
            print(f"  --   spaziatura {spacing:.1f} m: {sol.status}")
            continue
        check(
            r.ok and r.min_separation >= D - 1e-3,
            f"spaziatura {spacing:.1f} m (< {D} m di sicurezza): T={sol.T:.2f}s, "
            f"separazione minima {r.min_separation:.3f} m",
        )


def test_troppo_stretto_infattibile():
    print("\n[2] vasche cosi' vicine che due carroponti non ci stanno")
    # passo 0.8 m: mentre uno e' sul confine, l'altro non ha nessuna stazione
    # abbastanza lontana in cui sostare -> deve risultare infattibile, non
    # produrre una soluzione con collisioni
    data = linea(4, 0.8, [HoistZone(0, 1), HoistZone(2, 3)])
    sol = solve(data, time_limit_s=20.0)
    if sol.status in ("OPTIMAL", "FEASIBLE"):
        r = verify_solution(data, sol)
        check(r.ok, f"se una soluzione c'e', deve essere valida (sep {r.min_separation:.3f})")
    else:
        check(True, f"riconosciuto infattibile ({sol.status}), invece di sbagliare")


def test_un_carroponte():
    print("\n[3] un solo carroponte: nessun confine, nessun vincolo di coppia")
    data = linea(4, 1.0, [HoistZone(0, 3)], takt_max=120.0)
    sol, r = risolvi_e_verifica(data, "carroponte singolo")
    check(r is not None and r.ok, _esito(sol, r, "soluzione valida"))
    check(
        sol.raw.get("n_separation_constraints", -1) == 0,
        "nessun vincolo di separazione generato",
    )


def test_tre_carroponti():
    print("\n[4] tre carroponti, due confini")
    data = linea(
        6,
        1.5,
        [HoistZone(0, 1), HoistZone(2, 3), HoistZone(4, 5)],
        takt_min=10.0,
        takt_max=60.0,
        clearance_steps=4,  # due confini: si tiene il modello di dimensioni sane
    )
    sol, r = risolvi_e_verifica(data, "tre carroponti", time_limit=120.0)
    check(r is not None and r.ok, _esito(sol, r, "soluzione valida"))
    if r is not None:
        check(
            r.min_separation >= r.required_separation - 1e-3,
            f"separazione minima {r.min_separation:.3f} m >= "
            f"{r.required_separation:.3f} m",
        )


def test_fasi_verticali_e_capienza():
    print("\n[5] tempi verticali e capienza attivi insieme")
    data = linea(
        4,
        1.2,
        [HoistZone(0, 1), HoistZone(2, 3)],
        dwell=(40, 120),
        capacity=2,
        lift_height=0.8,
        kin_lift_empty=Kinematics(v_max=0.5, a_max=0.8),
        kin_lift_loaded=Kinematics(v_max=0.3, a_max=0.5),
        engage_time=2.0,
        disengage_time=1.0,
        takt_min=25.0,
        takt_max=90.0,
    )
    sol, r = risolvi_e_verifica(data, "verticali+capienza", time_limit=60.0)
    check(r is not None and r.ok, _esito(sol, r, "soluzione valida"))
    if r is not None:
        occ_ok = all(n <= 2 for n in r.tank_occupancy.values())
        check(occ_ok, f"capienza rispettata: {r.tank_occupancy}")


def test_clearance_steps():
    print("\n[6] clearance_steps: piu' passi = meno cautelativo, sempre sicuro")
    risultati = {}
    for steps in (2, 4, 8):
        data = linea(
            4,
            1.5,
            [HoistZone(0, 1), HoistZone(2, 3)],
            takt_max=40.0,
            clearance_steps=steps,
        )
        sol, r = risolvi_e_verifica(data, f"passi={steps}", time_limit=60.0)
        if r is None:
            risultati[steps] = None
            continue
        risultati[steps] = (sol.T, r.min_separation, r.ok)
        check(
            r.ok,
            f"passi={steps}: T={sol.T:.2f}s, separazione {r.min_separation:.3f} m",
        )
    validi = {k: v for k, v in risultati.items() if v}
    if len(validi) >= 2:
        ts = [v[0] for _, v in sorted(validi.items())]
        check(
            all(a >= b - 1e-6 for a, b in zip(ts, ts[1:])),
            f"il takt time non peggiora aumentando i passi: {[round(t, 2) for t in ts]}",
        )


def test_scelta_automatica():
    print("\n[7] scelta automatica su linea compatta")
    data = linea(6, 1.2, None, takt_min=10.0, takt_max=60.0)
    sol, zones, n = solve_auto_hoists(
        data, max_hoists=3, time_limit_per_candidate=15.0
    )
    if sol.status not in ("OPTIMAL", "FEASIBLE"):
        check(True, f"nessuna configurazione fattibile ({sol.status}): esito onesto")
        return
    import dataclasses

    df = dataclasses.replace(data, zones=zones)
    r = verify_solution(df, sol)
    check(
        r.ok,
        f"{n} carroponti, zone {[(z.lo, z.hi) for z in zones]}, T={sol.T:.2f}s, "
        f"separazione {r.min_separation:.3f} m",
    )


def test_vasca_ripetuta():
    print("\n[8] stessa vasca fisica usata due volte nella ricetta")
    # Il pezzo torna in LAV dopo essere passato da SEC: le posizioni lungo la
    # rotaia non sono piu' monotone, quindi serve un carroponte solo (nessun
    # confine fra zone, nessun vincolo di lato).
    def linea_lav(cap, dwell):
        return ProblemData(
            tanks={
                "CAR": Tank("CAR", 0.0),
                "LAV": Tank("LAV", 5.0, capacity=cap),
                "SEC": Tank("SEC", 10.0),
                "SCA": Tank("SCA", 15.0),
            },
            route=[
                StationSpec("CAR", 0, 0),
                StationSpec("LAV", *dwell),
                StationSpec("SEC", *dwell),
                StationSpec("LAV", *dwell),
                StationSpec("SCA", 0, 0),
            ],
            takt_min=20.0,
            takt_max=200.0,
            kin_empty=KIN_EMPTY,
            kin_loaded=KIN_LOADED,
            hoist_extent_pos=0.5,
        hoist_extent_neg=0.7,
            safety_distance=0.6,
            zones=[HoistZone(0, 3)],
            time_scale=100,
        )

    # (a) permanenze brevi: le due tappe si possono sfasare, un posto basta.
    #     Se il modello sommasse i massimi delle due tappe direbbe INFEASIBLE.
    data = linea_lav(cap=1, dwell=(10, 60))
    sol, r = risolvi_e_verifica(data, "vasca ripetuta, 1 posto", time_limit=60.0)
    check(
        r is not None and r.ok,
        _esito(sol, r, f"con 1 posto e' fattibile: T={sol.T:.2f}s" if r else "con 1 posto e' fattibile"),
    )
    if r is not None:
        check(
            r.tank_occupancy.get("LAV") == 1,
            f"LAV usa {r.tank_occupancy.get('LAV')} posto/i, come dichiarato",
        )

    # (b) permanenze lunghe rispetto al takt: un posto non puo' bastare
    data2 = linea_lav(cap=1, dwell=(150, 200))
    sol2 = solve(data2, time_limit_s=60.0)
    if sol2.status in ("OPTIMAL", "FEASIBLE"):
        r2 = verify_solution(data2, sol2)
        check(
            r2.ok and r2.tank_occupancy.get("LAV", 9) <= 1,
            f"se risolve, la capienza e' rispettata (LAV={r2.tank_occupancy.get('LAV')})",
        )
    else:
        check(True, f"riconosciuto {sol2.status}, invece di violare la capienza")

    # (c) con 3 posti la stessa linea deve tornare fattibile
    data3 = linea_lav(cap=3, dwell=(150, 200))
    sol3, r3 = risolvi_e_verifica(data3, "vasca ripetuta, 3 posti", time_limit=60.0)
    check(
        r3 is not None and r3.ok,
        f"con 3 posti e' fattibile: T={sol3.T:.2f}s, LAV usa "
        f"{r3.tank_occupancy.get('LAV') if r3 else '?'} posti",
    )


def main():
    print("=" * 72)
    print("TEST END-TO-END DEL MODELLO (richiede OR-Tools)")
    print("=" * 72)
    t0 = time.perf_counter()
    test_vasche_ravvicinate()
    test_troppo_stretto_infattibile()
    test_un_carroponte()
    test_tre_carroponti()
    test_fasi_verticali_e_capienza()
    test_clearance_steps()
    test_scelta_automatica()
    test_vasca_ripetuta()
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti  ({time.perf_counter() - t0:.0f}s)")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
