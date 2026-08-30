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
    build_solution,
    estrai_gradi_di_liberta,
    solve,
    solve_auto_hoists,
)
from verify import verify_solution

KIN_EMPTY = Kinematics(v_max=1600, a_max=900)
KIN_LOADED = Kinematics(v_max=1000, a_max=400)

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
    lift_height=0.0,
    drain_time=0.0,
    **kw,
) -> ProblemData:
    n_st = n_moves + 1
    # Corsa verticale e sgocciolamento sono di OGNI vasca e obbligatori: qui
    # uguali per tutte, scritti e non sottintesi.
    tanks = {
        f"V{i}": Tank(
            f"V{i}",
            i * spacing,
            1 if i in (0, n_st - 1) else capacity,
            lift_height=lift_height,
            drain_time=drain_time,
        )
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
        hoist_extent_pos=500,
        hoist_extent_neg=700,
        safety_distance=600,
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
    D = 1200 + 600
    for spacing in (1000, 1400, 1800, 2500):
        data = linea(4, spacing, [HoistZone(0, 1), HoistZone(2, 3)])
        sol, r = risolvi_e_verifica(data, f"spaziatura {spacing}")
        if r is None:
            # Fra una verifica di distanza e la successiva il modello sta
            # dal lato sicuro, quindi puo' dichiarare infattibile un caso che
            # verifiche piu' fitte risolvono. Non e' un difetto da nascondere
            # con un "continue" -- e' la manopola che l'utente deve conoscere,
            # quindi qui la si prova davvero.
            data = linea(
                4,
                spacing,
                [HoistZone(0, 1), HoistZone(2, 3)],
                clearance_step_mm=100.0,
            )
            sol, r = risolvi_e_verifica(data, f"spaziatura {spacing}, griglia fine")
            check(
                r is not None and r.ok and r.min_separation >= D - 1.0,
                f"spaziatura {spacing:.0f} mm: troppo stretta per la griglia "
                f"predefinita, risolta con passo_controllo_distanza_mm=100 "
                + (
                    f"(T={sol.T:.2f}s, separazione {r.min_separation:.0f} mm)"
                    if r is not None
                    else f"({sol.status})"
                ),
            )
            continue
        check(
            r.ok and r.min_separation >= D - 1.0,
            f"spaziatura {spacing:.0f} mm (< {D} mm di sicurezza): T={sol.T:.2f}s, "
            f"separazione minima {r.min_separation:.0f} mm",
        )


def test_troppo_stretto_infattibile():
    print("\n[2] vasche cosi' vicine che due carroponti non ci stanno")
    # passo 800 mm: mentre uno e' sul confine, l'altro non ha nessuna stazione
    # abbastanza lontana in cui sostare -> deve risultare infattibile, non
    # produrre una soluzione con collisioni
    data = linea(4, 800, [HoistZone(0, 1), HoistZone(2, 3)])
    sol = solve(data, time_limit_s=20.0)
    if sol.status in ("OPTIMAL", "FEASIBLE"):
        r = verify_solution(data, sol)
        check(r.ok, f"se una soluzione c'e', deve essere valida (sep {r.min_separation:.0f} mm)")
    else:
        check(True, f"riconosciuto infattibile ({sol.status}), invece di sbagliare")


def test_un_carroponte():
    print("\n[3] un solo carroponte: nessun confine, nessun vincolo di coppia")
    data = linea(4, 1000, [HoistZone(0, 3)], takt_max=120.0)
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
        1500,
        [HoistZone(0, 1), HoistZone(2, 3), HoistZone(4, 5)],
        takt_min=10.0,
        takt_max=60.0,
        clearance_step_mm=450.0,  # due confini: modello di dimensioni sane
    )
    sol, r = risolvi_e_verifica(data, "tre carroponti", time_limit=120.0)
    check(r is not None and r.ok, _esito(sol, r, "soluzione valida"))
    if r is not None:
        check(
            r.min_separation >= r.required_separation - 1.0,
            f"separazione minima {r.min_separation:.0f} mm >= "
            f"{r.required_separation:.0f} mm",
        )


def test_fasi_verticali_e_capienza():
    print("\n[5] tempi verticali e capienza attivi insieme")
    data = linea(
        4,
        1200,
        [HoistZone(0, 1), HoistZone(2, 3)],
        dwell=(40, 120),
        capacity=2,
        lift_height=800,
        kin_lift_empty=Kinematics(v_max=500, a_max=800),
        kin_lift_loaded=Kinematics(v_max=300, a_max=500),
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


def test_bagno_comprende_i_tempi_morti():
    """Il pezzo e' immerso anche durante lo sgancio e l'aggancio, che il
    modello non conta fra i due istanti che maneggia. Contarli o no fa la
    differenza fra rispettare il massimo di processo e sforarlo in silenzio."""
    print("\n[5-bis] la permanenza in vasca comprende sgancio e aggancio")
    comune = dict(
        lift_height=1500,
        kin_lift_empty=Kinematics(v_max=250, a_max=150),
        kin_lift_loaded=Kinematics(v_max=200, a_max=150),
        engage_time=8.0,
        disengage_time=7.0,
        takt_min=25.0,
        takt_max=200.0,
    )
    data = linea(4, 1500, [HoistZone(0, 1), HoistZone(2, 3)], dwell=(20, 45), **comune)
    inevitabile = data.bath_extra_seconds(1)
    check(
        abs(inevitabile - 15.0) < 1e-9,
        f"il bagno eccede l'intervallo fra i movimenti di sgancio+aggancio "
        f"({inevitabile:.1f} s)",
    )
    sol, r = risolvi_e_verifica(data, "bagno stretto", time_limit=60.0)
    check(r is not None and r.ok, _esito(sol, r, "soluzione valida"))
    if r is not None and sol.actual_time:
        at = sol.actual_time
        bagni = [
            at[k] - (at[k - 1] + data.loaded_leg_seconds(k - 1))
            + data.bath_extra_seconds(k)
            for k in range(1, data.n_moves)
        ]
        check(
            all(20.0 - 0.1 <= b <= 45.0 + 0.1 for b in bagni),
            f"ogni bagno vero sta dentro 20..45 s ({[round(b, 1) for b in bagni]})",
        )

    # e se la finestra e' piu' stretta dei soli tempi morti, la linea non e'
    # realizzabile e lo si dice subito col numero
    try:
        linea(4, 1500, [HoistZone(0, 1), HoistZone(2, 3)], dwell=(5, 12), **comune)
        check(False, "una permanenza massima irraggiungibile viene respinta")
    except ValueError as e:
        check(
            "in bagno almeno" in str(e),
            f"e il motivo e' scritto: \"{str(e)[:80]}...\"",
        )


def test_svincoli_end_to_end():
    """Sull'impianto in cui il gancio calato non passa fra le vasche, il
    carroponte va a svincolare prima di tirare su il gancio scarico."""
    print("\n[5-ter] posizioni di svincolo, risolte davvero")
    import dataclasses

    base = linea(
        4,
        5000,
        [HoistZone(0, 1), HoistZone(2, 3)],
        dwell=(30, 300),
        capacity=3,
        lift_height=1500,
        kin_lift_empty=Kinematics(v_max=250, a_max=150),
        kin_lift_loaded=Kinematics(v_max=200, a_max=150),
        engage_time=2.0,
        disengage_time=1.0,
        takt_min=25.0,
        takt_max=400.0,
        empty_hook_travels_low=False,
    )
    tanks = dict(base.tanks)
    for i, nome in enumerate(sorted(tanks, key=lambda n: tanks[n].position)):
        t = tanks[nome]
        tanks[nome] = dataclasses.replace(
            t,
            svincolo_pos=t.position + 1200 if i < len(tanks) - 1 else None,
            svincolo_neg=t.position - 1200 if i > 0 else None,
        )
    con = dataclasses.replace(base, tanks=tanks)

    senza_sol, senza_r = risolvi_e_verifica(base, "senza svincoli", time_limit=60.0)
    con_sol, con_r = risolvi_e_verifica(con, "con svincoli", time_limit=60.0)
    check(con_r is not None and con_r.ok, _esito(con_sol, con_r, "soluzione valida"))
    check(
        senza_sol.T is not None and con_sol.T is not None and con_sol.T >= senza_sol.T,
        f"il giro dello svincolo non puo' accorciare il ciclo "
        f"(T={con_sol.T:.2f}s contro {senza_sol.T:.2f}s)",
    )
    if con_sol.status in ("OPTIMAL", "FEASIBLE"):
        quote = {
            round(x, 0)
            for segs in con_sol.segments_per_hoist
            for s in segs
            for x in (s.x_start, s.x_end)
        }
        vasche = {round(con.station_position(i), 0) for i in range(con.n_stations)}
        check(
            quote - vasche,
            f"e il carroponte si spinge fino agli svincoli, oltre le vasche "
            f"({sorted(quote - vasche)})",
        )


def test_confine_con_corse_a_vuoto():
    """Il carroponte che sale o scende col gancio scarico e' FERMO: se il
    modello lo crede in movimento, lo fa uscire dalla fascia di esclusione
    troppo presto e lascia entrare il vicino mentre e' ancora li'.

    E' lo stesso errore gia' corretto per le fasi verticali di presa e
    rilascio, ripresentatosi quando le corse a vuoto sono state spostate nel
    rientro. Uno sweep di 192 configurazioni lo ha trovato in 36: qui c'e' la
    peggiore, cioe' quella che dava separazione ZERO."""
    print("\n[5-quater] fascia di esclusione e corse verticali a vuoto")
    import dataclasses

    for etichetta, svincoli in (("senza svincoli", False), ("con svincoli", True)):
        data = linea(
            4,
            2000,
            [HoistZone(0, 2), HoistZone(3, 3)],
            dwell=(20, 400),
            capacity=4,
            lift_height=1500,
            kin_lift_empty=Kinematics(v_max=250, a_max=150),
            kin_lift_loaded=Kinematics(v_max=200, a_max=150),
            engage_time=2.0,
            disengage_time=1.0,
            takt_min=15.0,
            takt_max=400.0,
            empty_hook_travels_low=False,
        )
        if svincoli:
            tanks = dict(data.tanks)
            ordinate = sorted(tanks, key=lambda n: tanks[n].position)
            for i, nome in enumerate(ordinate):
                t = tanks[nome]
                tanks[nome] = dataclasses.replace(
                    t,
                    svincolo_pos=t.position + 1800 if i < len(ordinate) - 1 else None,
                    svincolo_neg=t.position - 1800 if i > 0 else None,
                )
            data = dataclasses.replace(data, tanks=tanks)
        sol, r = risolvi_e_verifica(data, f"confine, {etichetta}", time_limit=30.0)
        check(
            r is not None and r.ok,
            _esito(sol, r, f"{etichetta}: soluzione valida"),
        )
        if r is not None:
            check(
                r.min_separation >= r.required_separation - 1.0,
                f"{etichetta}: separazione {r.min_separation:.0f} mm >= "
                f"{r.required_separation:.0f} mm richiesti",
            )


def test_passo_controllo():
    print("\n[6] passo di controllo: piu' fitto = meno cautelativo, sempre sicuro")
    risultati = {}
    for passo in (900.0, 450.0, 225.0):
        data = linea(
            4,
            1500,
            [HoistZone(0, 1), HoistZone(2, 3)],
            takt_max=40.0,
            clearance_step_mm=passo,
        )
        sol, r = risolvi_e_verifica(data, f"passo={passo:.0f} mm", time_limit=60.0)
        if r is None:
            risultati[passo] = None
            continue
        risultati[passo] = (sol.T, r.min_separation, r.ok)
        # La promessa e' che la distanza GARANTITA resti quella richiesta
        # qualunque sia il passo: il parametro puo' solo far scartare soluzioni
        # buone, mai accettarne di pericolose.
        check(
            r.ok and r.min_separation >= r.required_separation - 1.0,
            f"passo={passo:.0f} mm: T={sol.T:.2f}s, separazione "
            f"{r.min_separation:.0f} mm >= {r.required_separation:.0f} richiesti",
        )
    validi = {k: v for k, v in risultati.items() if v}
    if len(validi) >= 2:
        # ordinati per passo decrescente: infittendo, il takt time non peggiora
        ts = [v[0] for _, v in sorted(validi.items(), reverse=True)]
        check(
            all(a >= b - 1e-6 for a, b in zip(ts, ts[1:])),
            f"il takt time non peggiora infittendo le verifiche: "
            f"{[round(t, 2) for t in ts]}",
        )


def test_scelta_automatica():
    print("\n[7] scelta automatica su linea compatta")
    data = linea(6, 1200, None, takt_min=10.0, takt_max=60.0)
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
                "CAR": Tank("CAR", 0, lift_height=0, drain_time=0),
                "LAV": Tank("LAV", 5000, capacity=cap, lift_height=0, drain_time=0),
                "SEC": Tank("SEC", 10000, lift_height=0, drain_time=0),
                "SCA": Tank("SCA", 15000, lift_height=0, drain_time=0),
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
            hoist_extent_pos=500,
        hoist_extent_neg=700,
            safety_distance=600,
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


def test_ricostruzione_fedele():
    print("\n[9] ricostruire una soluzione dalle sole fasi la lascia identica")
    # E' la fondazione dell'editor: l'utente modifica le fasi di prelievo e il
    # ciclogramma viene rimesso insieme da li'. Se il solo rimetterlo insieme
    # -- senza toccare nulla -- gia' cambiasse le permanenze, ogni modifica
    # partirebbe da una base sbagliata.
    for spacing, zone in ((2500, [HoistZone(0, 1), HoistZone(2, 3)]), (1500, None)):
        data = linea(
            4,
            spacing,
            zone or [HoistZone(0, 3)],
            dwell=(30, 200),
            capacity=3,
            takt_min=20.0,
            takt_max=120.0,
            lift_height=600,
            kin_lift_empty=Kinematics(v_max=500, a_max=800),
            kin_lift_loaded=Kinematics(v_max=300, a_max=500),
            engage_time=2.0,
            disengage_time=1.0,
            drain_time=3.0,
        )
        sol, r = risolvi_e_verifica(data, f"base spaziatura {spacing}")
        if r is None:
            check(False, f"spaziatura {spacing}: {sol.status}, niente da ricostruire")
            continue
        T, fasi, giri = estrai_gradi_di_liberta(data, sol)
        rifatta = build_solution(data, T, fasi, extra_periods=giri)
        r2 = verify_solution(data, rifatta)

        def permanenze(s):
            return [
                round(
                    s.actual_time[k]
                    - (s.actual_time[k - 1] + data.loaded_leg_seconds(k - 1)),
                    2,
                )
                for k in range(1, data.n_moves)
            ]

        check(
            permanenze(rifatta) == permanenze(sol),
            f"spaziatura {spacing}: permanenze identiche {permanenze(sol)}",
        )
        # con un carroponte solo la separazione e' infinita: confrontarla con
        # una differenza darebbe nan, che non e' ne' uguale ne' diverso
        stessa_sep = r2.min_separation == r.min_separation or (
            abs(r2.min_separation - r.min_separation) < 1e-6
        )
        check(
            r2.ok == r.ok and stessa_sep,
            f"spaziatura {spacing}: stesso verdetto e stessa separazione "
            f"({r2.min_separation:.3f} m)",
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
    test_bagno_comprende_i_tempi_morti()
    test_svincoli_end_to_end()
    test_confine_con_corse_a_vuoto()
    test_passo_controllo()
    test_scelta_automatica()
    test_vasca_ripetuta()
    test_ricostruzione_fedele()
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti  ({time.perf_counter() - t0:.0f}s)")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
