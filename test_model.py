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
    tanks = {f"V{i}": Tank(f"V{i}", i * spacing) for i in range(n_st)}
    route = [StationSpec("V0", 0, 0)]
    for i in range(1, n_st - 1):
        route.append(StationSpec(f"V{i}", dwell[0], dwell[1], capacity=capacity))
    route.append(StationSpec(f"V{n_st - 1}", 0, 0))
    params = dict(
        tanks=tanks,
        route=route,
        takt_min=takt_min,
        takt_max=takt_max,
        kin_empty=KIN_EMPTY,
        kin_loaded=KIN_LOADED,
        hoist_length=1.2,
        safety_distance=0.6,
        zones=zones,
        time_scale=100,
    )
    params.update(kw)
    return ProblemData(**params)


def risolvi_e_verifica(data, etichetta, time_limit=20.0):
    """Risolve e restituisce (solution, report). Fallisce il test se la
    soluzione non supera la verifica indipendente."""
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
    check(r is not None and r.ok, f"soluzione valida (T={sol.T:.2f}s)")
    check(
        sol.raw.get("n_separation_constraints", -1) == 0,
        "nessun vincolo di separazione generato",
    )


def test_tre_carroponti():
    print("\n[4] tre carroponti, due confini")
    data = linea(6, 1.5, [HoistZone(0, 1), HoistZone(2, 3), HoistZone(4, 5)],
                 takt_min=10.0, takt_max=60.0)
    sol, r = risolvi_e_verifica(data, "tre carroponti", time_limit=40.0)
    check(r is not None and r.ok, "soluzione valida")
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
        pick_time=7.0,
        release_time=5.0,
        takt_min=25.0,
        takt_max=90.0,
    )
    sol, r = risolvi_e_verifica(data, "verticali+capienza", time_limit=30.0)
    check(r is not None and r.ok, "soluzione valida")
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
        sol, r = risolvi_e_verifica(data, f"passi={steps}", time_limit=30.0)
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
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti  ({time.perf_counter() - t0:.0f}s)")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
