"""
test_model.py
-------------
Test end-to-end del modello CP-SAT: risolve davvero e passa ogni soluzione al
verificatore indipendente (verify.py). Richiede OR-Tools.

E' il complemento di test_verify.py, che invece verifica il VERIFICATORE su
soluzioni costruite a mano e non richiede OR-Tools. Qui la domanda e'
l'opposta: il modello produce soluzioni fisicamente valide?

Per eseguirlo:
    python test/test_model.py
"""

from __future__ import annotations

import os
import sys
import time

# I moduli del programma stanno nella cartella sopra questa: senza aggiungerla
# fra i percorsi di ricerca, lanciare il test da qui non li troverebbe.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def con_ostacoli(data, svincolo=1200.0):
    """La linea con le vasche di MEZZO dichiarate ostacolo e i loro svincoli.

    E' come si dice adesso, col flag per vasca, quello che prima era
    `empty_hook_travels_low=False`. Carico e scarico restano liberi: qui si
    prova la linea con gli ostacoli in mezzo (che carico e scarico possano
    esserlo lo prova test_verify.py).
    """
    import dataclasses

    quote = sorted(t.position for t in data.tanks.values())
    tanks = {}
    for nome, t in data.tanks.items():
        estremo = t.position in (quote[0], quote[-1])
        tanks[nome] = dataclasses.replace(
            t,
            gancio_basso=estremo,
            svincolo_pos=t.position + svincolo if t.position < quote[-1] else None,
            svincolo_neg=t.position - svincolo if t.position > quote[0] else None,
        )
    return dataclasses.replace(data, tanks=tanks)


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
    )
    con = con_ostacoli(base, svincolo=1200.0)

    senza_sol, senza_r = risolvi_e_verifica(base, "senza ostacoli", time_limit=60.0)
    con_sol, con_r = risolvi_e_verifica(con, "con ostacoli", time_limit=60.0)
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

    for etichetta, svincoli in (("senza ostacoli", False), ("con ostacoli", True)):
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
            )
        if svincoli:
            data = con_ostacoli(data, svincolo=1800.0)
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


def test_cambio_quota_end_to_end():
    """Le ZONE DI CAMBIO QUOTA, risolte davvero.

    Il punto delicato non e' il tempo in piu': e' che durante la presa il
    carroponte NON e' fermo -- fa due traslazioni fra il punto di cambio quota
    e la stazione. Qui il punto di cambio quota sta a 600 mm dal confine fra le
    due zone, cioe' esattamente alla distanza minima richiesta: la vicinanza e'
    reale e il modello la deve rappresentare per quella che e'."""
    print("\n[5-quinquies] zone di cambio quota, risolte davvero")
    import dataclasses

    from model import ZonaCambioQuota

    base = linea(
        4,
        3000,
        [HoistZone(0, 0), HoistZone(1, 3)],
        dwell=(20, 400),
        capacity=4,
        lift_height=800,
        drain_time=3.0,
        kin_lift_empty=Kinematics(v_max=500, a_max=800),
        kin_lift_loaded=Kinematics(v_max=300, a_max=500),
        engage_time=2.0,
        disengage_time=1.0,
        takt_min=15.0,
        takt_max=400.0,
        # carroponti piccoli: cosi' la linea resta risolvibile con la prima
        # zona ridotta a una sola mossa, che e' la disposizione in cui il giro
        # di cambio quota pesa di piu' sul ciclo
        hoist_extent_pos=200,
        hoist_extent_neg=200,
        safety_distance=200,
    )
    # carico e scarico senza corsa: li' la definisce la zona di cambio quota
    tanks = dict(base.tanks)
    for nome in ("V0", "V4"):
        tanks[nome] = dataclasses.replace(
            tanks[nome], lift_height=0.0, drain_time=0.0
        )
    senza = dataclasses.replace(base, tanks=tanks)
    # Il punto di cambio quota del carico sta a 2400 mm, cioe' a 600 mm dalla
    # vasca V1 che e' il CONFINE fra la zona 1 e la zona 2: il carroponte 1 va
    # avanti e indietro proprio sotto il naso del carroponte 2.
    con = dataclasses.replace(
        senza,
        cambio_quota_carico=ZonaCambioQuota(2400, 400, 1400, 2200),
        cambio_quota_scarico=ZonaCambioQuota(9600, 400, 1400, 2200),
    )

    senza_sol, senza_r = risolvi_e_verifica(senza, "senza cambio quota", 60.0)
    con_sol, con_r = risolvi_e_verifica(con, "con cambio quota", 60.0)
    check(
        con_r is not None and con_r.ok,
        _esito(con_sol, con_r, "con cambio quota: soluzione valida"),
    )
    check(
        senza_sol.T is not None
        and con_sol.T is not None
        and con_sol.T >= senza_sol.T - 1e-9,
        f"il giro di cambio quota non puo' accorciare il ciclo "
        f"(T={con_sol.T:.2f}s contro {senza_sol.T:.2f}s)"
        if con_sol.T and senza_sol.T
        else f"stati: {con_sol.status} / {senza_sol.status}",
    )
    if con_r is not None:
        check(
            con_r.min_separation >= con_r.required_separation - 1.0,
            f"separazione {con_r.min_separation:.0f} mm >= "
            f"{con_r.required_separation:.0f} mm richiesti, col punto di cambio "
            f"quota a 600 mm dal confine",
        )
    if con_sol.T is not None:
        tratti = [s for segs in con_sol.segments_per_hoist for s in segs]
        check(
            any(abs(s.x_end) < 1e-9 for s in tratti),
            "il carroponte arriva fino al carico (0 mm), oltre il punto di "
            "cambio quota",
        )
        check(
            all(
                abs(s.x_start - con.approach_position(s.move)) < 1e-6
                and abs(s.x_end - con.approach_position(s.move + 1)) < 1e-6
                for s in tratti
                if s.kind == "loaded"
            ),
            "e i tratti col pezzo vanno da punto di approccio a punto di "
            "approccio",
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


def test_tentativi_previsti():
    """Il conto fatto PRIMA deve coincidere con le risoluzioni fatte DOPO.

    E' l'unica proprieta' che rende utile un avanzamento: se il totale
    annunciato non fosse quello vero, la barra arriverebbe in fondo prima
    della fine, o si fermerebbe prima. Il rischio concreto e' che i due
    prefiltri si sdoppino -- uno nel conteggio, uno nella ricerca -- e allora
    divergono in silenzio."""
    print("\n[7-bis] i tentativi previsti coincidono con quelli fatti")
    from model import tentativi_previsti

    data = linea(6, 1200, None, takt_min=10.0, takt_max=60.0)
    visti: list[tuple[int, int, int, int, object]] = []
    solve_auto_hoists(
        data,
        max_hoists=3,
        time_limit_per_candidate=15.0,
        su_tentativo=lambda h, i, t, v, bt: visti.append((h, i, t, v, bt)),
    )
    fatti: dict[int, int] = {}
    for h, _i, _t, _v, _bt in visti:
        fatti[h] = fatti.get(h, 0) + 1
    check(
        bool(visti), f"il solutore ha segnalato {len(visti)} tentativi"
    )
    for h, quanti in sorted(fatti.items()):
        check(
            tentativi_previsti(data, h) == quanti,
            f"{h} carroponti: previsti {tentativi_previsti(data, h)}, "
            f"fatti {quanti}",
        )
    # il totale annunciato deve essere lo stesso a ogni segnalazione dello
    # stesso numero di carroponti, e gli indici devono salire da 1 senza salti
    for h, quanti in sorted(fatti.items()):
        indici = [i for hh, i, _t, _v, _bt in visti if hh == h]
        totali = {t for hh, _i, t, _v, _bt in visti if hh == h}
        check(
            indici == list(range(1, quanti + 1)) and totali == {quanti},
            f"{h} carroponti: indici {indici} su totale {totali}",
        )
        # Il conteggio delle soluzioni gia' trovate e' quello che dice
        # all'utente se fermarsi ora gli lascia qualcosa: parte da zero e non
        # puo' che salire, di uno alla volta e mai piu' dei tentativi fatti.
        valide = [v for hh, _i, _t, v, _bt in visti if hh == h]
        check(
            valide[0] == 0
            and all(0 <= b - a <= 1 for a, b in zip(valide, valide[1:]))
            and valide[-1] < quanti + 1,
            f"{h} carroponti: soluzioni trovate lungo la ricerca {valide}",
        )
        # Il takt time della migliore accompagna il conteggio: manca finche'
        # non c'e' niente, c'e' appena il conteggio sale, e non puo' che
        # MIGLIORARE -- si tiene la piu' veloce fra quelle provate.
        coppie = [(v, bt) for hh, _i, _t, v, bt in visti if hh == h]
        migliori = [bt for v, bt in coppie if v > 0]
        check(
            all((bt is None) == (v == 0) for v, bt in coppie)
            and all(b <= a + 1e-9 for a, b in zip(migliori, migliori[1:])),
            f"{h} carroponti: miglior takt lungo la ricerca "
            f"{[None if bt is None else round(bt, 2) for _v, bt in coppie]}",
        )


def test_giro_che_non_parte_dal_confine():
    """Il solutore deve poter far cominciare il giro da una mossa qualsiasi.

    Il giro di un carroponte e' un CICLO: uno dei suoi archi attraversa la fine
    del periodo, e a quello -- e solo a quello -- si somma un T. Per un lungo
    tratto il modello dava per scontato che fosse l'arco che entra nella mossa
    di CONFINE BASSO, e non era una convenzione innocua: implicava che le fasi
    crescessero lungo il giro a partire da li', cioe' OBBLIGAVA la mossa di
    confine a essere la piu' anticipata del carroponte.

    Ciclogrammi perfettamente realizzabili in cui il carroponte comincia il
    giro da un'altra mossa non stavano nello spazio di ricerca: il solutore li
    dichiarava INFEASIBLE senza averli mai considerati. Su una linea vera di
    diciassette mosse questo ha fatto dichiarare impossibile con quattro
    carroponti una linea che con quattro carroponti si fa."""
    print("\n[7-ter] il giro puo' cominciare da una mossa qualsiasi")
    zone = [HoistZone(0, 0), HoistZone(1, 2)]
    # takt fissato e permanenze rigide: la catena del pezzo porta la mossa 2 a
    # cadere PRIMA della 1 dentro il periodo, e non c'e' modo di evitarlo
    data = linea(
        3, 2500.0, zone, takt_min=100.0, takt_max=100.0, dwell=(150.0, 150.0)
    )
    sol = solve(data, time_limit_s=30.0)
    check(
        sol.status in ("OPTIMAL", "FEASIBLE"),
        f"il solutore trova la soluzione ({sol.status})",
    )
    if sol.status not in ("OPTIMAL", "FEASIBLE"):
        return
    p = sol.plans[1]
    check(
        p.order[0] != p.zone.lo,
        f"e il giro comincia dalla mossa {p.order[0]}, non da quella di "
        f"confine basso ({p.zone.lo})",
    )
    fasi = [p.local_pick[k] for k in p.order]
    check(
        fasi == sorted(fasi),
        f"le fasi crescono lungo il giro ({[round(f) for f in fasi]})",
    )
    check(verify_solution(data, sol).ok, "la soluzione supera la verifica")

    # Un controllo che non segnala mai nulla e' inutile: si rifa' il conto
    # sull'arco che chiude il periodo con la convenzione VECCHIA -- il +T solo
    # entrando nella mossa di confine basso -- e ci si aspetta che quella
    # fallisca. Se non fallisse, questo caso non proverebbe niente.
    k1, k2 = p.order[-1], p.order[0]
    pronto = p.finish[k1] + data.empty_leg_seconds(k1 + 1, k2)
    vecchia = p.local_pick[k2] + (sol.T if k2 == p.zone.lo else 0.0)
    check(
        pronto > vecchia,
        f"con la vecchia convenzione questo giro era impossibile "
        f"(pronto a {pronto:.0f}s contro un prelievo a {vecchia:.0f}s)",
    )
    check(
        pronto <= p.local_pick[k2] + sol.T,
        f"e con quella giusta ci sta, di {p.local_pick[k2] + sol.T - pronto:.0f}s",
    )


def test_diagnosi():
    """La diagnosi di un rifiuto deve dire QUALE vincolo blocca.

    Si costruiscono tre casi in cui la causa e' nota per costruzione, e si
    pretende che la diagnosi la nomini. Il caso piu' importante e' il terzo:
    su una linea che FUNZIONA la diagnosi non deve inventare una causa --
    ogni rilassamento riesce, e la prima prova verrebbe scambiata per il
    colpevole."""
    print("\n[8-bis] diagnosi di un rifiuto")
    from model import diagnosi_zone

    import dataclasses

    zone = [HoistZone(0, 2), HoistZone(3, 5)]

    # Caso di partenza che si risolve, per sapere qual e' il ciclo piu' veloce
    # possibile: da li' si costruisce il caso rotto abbassando il tetto SOTTO
    # quel valore, cosi' la causa e' nota per costruzione e non c'e' altro che
    # possa spiegare il rifiuto.
    base = linea(6, 2500, zone, takt_min=15.0, takt_max=25.0, dwell=(5, 40))
    riferimento = solve(base, time_limit_s=20.0)
    check(
        riferimento.status in ("OPTIMAL", "FEASIBLE"),
        f"il caso di partenza si risolve (T={riferimento.T:.1f}s)",
    )

    # 1) su una linea che FUNZIONA la diagnosi non deve inventare una causa
    righe = diagnosi_zone(base, zone, time_limit_s=20.0)
    check(
        any("FUNZIONA" in r for r in righe),
        f'su una linea che regge non inventa cause: "{righe[0][:60]}..."',
    )

    # 2) takt time troppo stretto: la linea regge, ma non a quel ritmo
    stretta = dataclasses.replace(base, takt_max=riferimento.T - 3.0)
    check(
        solve(stretta, time_limit_s=20.0).status == "INFEASIBLE",
        f"col tetto a {riferimento.T - 3.0:.1f}s il caso e' davvero rifiutato",
    )
    righe = diagnosi_zone(stretta, zone, time_limit_s=20.0)
    check(
        any("TAKT TIME E' TROPPO STRETTO" in r for r in righe),
        f'riconosce il takt time troppo stretto: "{righe[0][:75]}..."',
    )
    # e deve dire di QUANTO, come intervallo: annunciare un minimo esatto che
    # non e' stato cercato farebbe alzare il parametro piu' del necessario
    check(
        any("Il minimo che basta sta fra" in r for r in righe),
        "e dice fra quali valori sta il minimo, senza spacciarlo per esatto",
    )

    # 3) la diagnosi non deve mai restare muta: qualcosa dice sempre, anche
    #    quando la conclusione e' 'non sono riuscito a stabilirlo'
    check(
        all(isinstance(r, str) and r.strip() for r in righe) and bool(righe),
        f"il referto e' sempre non vuoto ({len(righe)} righe)",
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
        T, fasi, giri, soste = estrai_gradi_di_liberta(data, sol)
        rifatta = build_solution(data, T, fasi, extra_periods=giri, attese=soste)
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


def test_dove_sosta_il_carro():
    print()
    print("[9-bis] dove il carroponte passa il tempo morto e' un dato,"
          " non una regola")
    # A parita' di takt time, permanenze e assegnazione il carroponte puo'
    # ripartire subito e aspettare a destinazione, oppure restare fermo dove
    # ha consegnato. Sono traiettorie DIVERSE, con collisioni diverse.
    # Finche' la scelta la faceva una convenzione scritta nel codice non
    # c'era niente da salvare; da quando la fa il solutore, ricostruire senza
    # quel valore ha prodotto -- su 50 soluzioni verificate pulite -- 14
    # ciclogrammi che collidevano, uno con i due carri sovrapposti.
    data = linea(
        4, 2500, [HoistZone(0, 1), HoistZone(2, 3)],
        # Il takt time minimo e' tenuto ALTO di proposito: il solutore
        # minimizza T, e con un takt stretto spreme via ogni attesa -- non
        # resterebbe tempo morto da collocare, e la prova non proverebbe
        # niente. Qui invece i carri hanno del tempo che avanza, ed e'
        # esattamente la situazione in cui scegliere dove passarlo conta.
        dwell=(30, 400), capacity=3, takt_min=150.0, takt_max=200.0,
        lift_height=600, drain_time=3.0,
        kin_lift_empty=Kinematics(v_max=500, a_max=800),
        kin_lift_loaded=Kinematics(v_max=300, a_max=500),
        engage_time=2.0, disengage_time=1.0,
    )
    sol, r = risolvi_e_verifica(data, "linea a due carroponti")
    if r is None:
        check(False, sol.status + ": niente da ricostruire")
        return
    T, fasi, giri, soste = estrai_gradi_di_liberta(data, sol)
    check(
        set(soste) == set(range(data.n_moves)),
        f"ogni mossa porta con se' la sua sosta ({len(soste)} su {data.n_moves})",
    )

    def dopo_la_consegna(soluzione, h, k):
        """(istante di partenza, margine disponibile) per il rientro a vuoto
        che segue la mossa k, letti dai segmenti DISEGNATI: quello che si
        vede, non quello che si spera.

        La partenza e' l'inizio del tratto a vuoto. Dove il carroponte abbia
        aspettato si vede SOLO se quel tratto esiste: quando consegna e
        riprende alla stessa vasca non si sposta, e le due attese -- prima e
        dopo -- sono lo stesso posto. Quei casi si riconoscono da margine
        disponibile senza tratto a vuoto, e non servono a questa prova."""
        segs = sorted(soluzione.segments_per_hoist[h], key=lambda sg: sg.t_start)
        i_rel = max(
            j for j, sg in enumerate(segs)
            if sg.kind == "release" and sg.move == k
        )
        parte, margine = None, 0.0
        for sg in segs[i_rel + 1:]:
            if sg.kind == "pick":
                break
            if sg.kind == "wait":
                margine += sg.t_end - sg.t_start
            elif sg.kind == "empty" and parte is None:
                parte = sg.t_start
        return parte, margine

    # La mossa su cui provare non si sceglie a priori: si prende quella che
    # ha davvero del tempo morto da collocare. Su un'altra il controllo
    # direbbe "nessuna differenza" solo perche' non c'era niente da spostare.
    zero = {j: 0.0 for j in soste}
    disegno = build_solution(data, T, fasi, extra_periods=giri, attese=zero)
    margini = {
        (h, k): dopo_la_consegna(disegno, h, k)
        for h, p in enumerate(sol.plans)
        for k in p.order
    }
    utili = {hk: m for hk, (parte, m) in margini.items() if parte is not None}
    check(bool(utili), "c'e' almeno un rientro a vuoto su cui misurare")
    if not utili:
        return
    (h, k), margine = max(utili.items(), key=lambda v: v[1])
    base = margini[(h, k)][0]
    check(
        margine > 1.0,
        f"il carroponte {h + 1} dopo la mossa {k} ha {margine:.1f} s di "
        f"tempo morto da collocare",
    )

    # Una sosta imposta si deve vedere nel disegno, al centesimo di secondo.
    for frazione in (0.25, 0.75):
        quanto = round(margine * frazione, 3)
        rifatta = build_solution(
            data, T, fasi, extra_periods=giri,
            attese={**zero, k: quanto},
        )
        ritardo = dopo_la_consegna(rifatta, h, k)[0] - base
        check(
            abs(ritardo - quanto) < 1e-6,
            f"sosta di {quanto:.1f} s dopo la mossa {k}: il carro parte "
            f"{ritardo:.2f} s piu' tardi",
        )

    # E la soluzione del solutore si ricostruisce identica con le sue soste.
    con = verify_solution(
        data, build_solution(data, T, fasi, extra_periods=giri, attese=soste)
    )
    check(
        abs(con.min_separation - r.min_separation) < 1e-6 and con.ok == r.ok,
        f"con le soste salvate la separazione torna identica "
        f"({con.min_separation:.3f})",
    )


def test_pezzo_in_vasca():
    print()
    print("[9-ter] la linea grigia del pezzo in vasca")
    # Sul ciclogramma il pezzo fermo in vasca e' una linea grigia, spessa come
    # le traiettorie, dall'immersione all'aggancio. Deve
    # cominciare e finire ESATTAMENTE sui pallini delle traiettorie, e deve
    # reggere un pezzo che resta in vasca piu' di un takt time: dai soli
    # segmenti, noti modulo T, quel caso non si distinguerebbe da una sosta
    # di pochi secondi.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from plotting import (
        _COLORE_PEZZO,
        _HOIST_COLORS,
        eventi_del_trasporto,
        pezzi_in_vasca,
        plot_cyclogram,
    )

    data = linea(
        4, 2500, [HoistZone(0, 1), HoistZone(2, 3)],
        # permanenza minima piu' lunga del takt time massimo: in ogni vasca
        # c'e' sempre piu' di un pezzo, ed e' il caso che il modulo T sbaglia
        dwell=(130, 400), capacity=4, takt_min=20.0, takt_max=120.0,
    )
    sol, r = risolvi_e_verifica(data, "linea con permanenze lunghe")
    if r is None:
        check(False, sol.status + ": niente da disegnare")
        return
    T = sol.T
    pezzi = pezzi_in_vasca(data, sol)
    check(
        [s for s, _, _ in pezzi] == list(range(1, data.n_moves)),
        f"una linea per ogni vasca intermedia, carico e scarico esclusi "
        f"({[s for s, _, _ in pezzi]})",
    )
    if not pezzi:
        return
    check(
        all(u - e > T for _, e, u in pezzi),
        f"e ognuna dura piu' di un takt time, come le permanenze "
        f"(T = {T:.1f} s, durate {[round(u - e, 1) for _, e, u in pezzi]})",
    )

    # comincia e finisce sui pallini delle traiettorie, modulo T
    trasporto = {
        s.move: s
        for segs in sol.segments_per_hoist
        for s in segs
        if s.kind == "loaded" and s.move is not None
    }

    def dal_carro(k):
        s = trasporto[k]
        return eventi_del_trasporto(
            data, k, s.t_start - data.pick_time_at(k), s.x_start, s.x_end
        )

    def modulo(a, b):
        return min((a - b) % T, (b - a) % T)

    scarti = [
        max(modulo(e, dal_carro(s - 1)[3][0]), modulo(u, dal_carro(s)[0][0]))
        for s, e, u in pezzi
    ]
    check(
        max(scarti) < 1e-6,
        f"la linea parte dall'immersione e arriva all'aggancio "
        f"(scarto massimo {max(scarti):.1e} s)",
    )
    # Il grigio esiste per non confondersi: con nessun carroponte, con le
    # righe delle vasche, e con il grigio che nella vista Modifica vuol dire
    # "ancora da assegnare".
    from interfaccia import _GRIGIO

    check(
        _COLORE_PEZZO not in set(_HOIST_COLORS) | {"#dddddd", _GRIGIO},
        f"il grigio del pezzo ({_COLORE_PEZZO}) non e' il colore di nient'altro",
    )

    # e il disegno la mostra davvero, a ogni periodo
    fig = plot_cyclogram(data, sol, n_cycles=2)
    grigie = [l for l in fig.axes[0].lines if l.get_color() == _COLORE_PEZZO]

    def coperto(y, t):
        for l in grigie:
            xs, ys = l.get_xdata(), l.get_ydata()
            for i in range(0, len(xs) - 1, 3):
                if ys[i] == y and xs[i] <= t <= xs[i + 1]:
                    return True
        return False

    mancanti = [
        (s, round(t, 1))
        for s, e, u in pezzi
        for t in np.linspace(0.0, 2 * T, 41)
        if (t - e) % T <= (u - e) - 1e-6
        and not coperto(data.station_position(s), t)
    ]
    plt.close(fig)
    check(
        not mancanti,
        f"su due cicli la linea copre ogni istante in cui il pezzo e' in vasca "
        f"(scoperti: {mancanti[:5]})",
    )


def test_frecce_delle_corse_verticali():
    print()
    print("[9-quater] le frecce su e giu' delle corse verticali")
    # Sul ciclogramma i tratti in cui il gancio sale o scende sono piatti come
    # un'attesa: la freccetta sopra dice che li' il gancio lavora, e in che
    # verso. Il verso dev'essere quello VERO, e c'e' un modo di saperlo senza
    # fidarsi di chi l'ha calcolato: il gancio di un carroponte non puo' salire
    # due volte di fila senza essere sceso nel mezzo. Su una linea senza zone
    # di cambio quota -- dove la presa ha una salita sola e il rilascio una
    # discesa sola -- le frecce di ogni giro devono ALTERNARSI.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from plotting import corse_verticali, plot_cyclogram

    base = linea(
        4, 5000, [HoistZone(0, 1), HoistZone(2, 3)],
        dwell=(30, 300), capacity=3, lift_height=1500,
        kin_lift_empty=Kinematics(v_max=250, a_max=150),
        kin_lift_loaded=Kinematics(v_max=200, a_max=150),
        engage_time=2.0, disengage_time=1.0, takt_min=25.0, takt_max=400.0,
    )
    # con gli svincoli, cosi' ci sono anche le corse a vuoto
    data = con_ostacoli(base, svincolo=1200.0)
    sol, r = risolvi_e_verifica(data, "linea con svincoli")
    if r is None:
        check(False, sol.status + ": niente da disegnare")
        return

    tutte = []
    for h, segs in enumerate(sol.segments_per_hoist):
        corse = sorted(corse_verticali(data, segs))
        tutte.append(corse)
        versi = [sale for _, _, sale in corse]
        alterna = bool(versi) and all(
            versi[i] != versi[(i + 1) % len(versi)] for i in range(len(versi))
        )
        check(
            alterna,
            f"carroponte {h + 1}: su e giu' si alternano per tutto il giro "
            f"({''.join('^' if v else 'v' for v in versi)})",
        )

        # ogni freccia sta sopra un tratto fermo in cui il gancio lavora
        fuori_posto = [
            (round(t, 1), x)
            for t, x, _ in corse
            if not any(
                s.kind in ("pick", "release", "lift_empty")
                and s.t_start - 1e-6 <= t <= s.t_end + 1e-6
                and abs(s.x_start - x) < 1e-6
                for s in segs
            )
        ]
        check(
            not fuori_posto,
            f"carroponte {h + 1}: ogni freccia cade su una presa, un rilascio o "
            f"una corsa a vuoto (fuori posto: {fuori_posto[:3]})",
        )

    # Il test deve passare davvero dagli svincoli, o l'alternanza non avrebbe
    # provato il verso dei tratti 'lift_empty'.
    a_vuoto = [
        s.sale
        for segs in sol.segments_per_hoist
        for s in segs
        if s.kind == "lift_empty"
    ]
    check(
        True in a_vuoto and False in a_vuoto,
        f"fra le frecce ci sono corse a vuoto in salita e in discesa "
        f"({a_vuoto.count(True)} su, {a_vuoto.count(False)} giu')",
    )

    # e il disegno le mostra tutte, a ogni ciclo, del colore del carro
    fig = plot_cyclogram(data, sol, n_cycles=2)
    disegnate = sum(
        len(l.get_xdata())
        for l in fig.axes[0].lines
        if l.get_marker() in (r"$\uparrow$", r"$\downarrow$")
    )
    plt.close(fig)
    attese = 2 * sum(len(c) for c in tutte)
    check(
        disegnate == attese,
        f"sul ciclogramma ci sono tutte le frecce, due cicli per due "
        f"({disegnate} su {attese})",
    )


def test_ferma_il_calcolo():
    print()
    print("[9-quinquies] un calcolo si puo' fermare")
    # Una ricerca automatica puo' durare decine di minuti. Fermarla deve
    # essere questione di un attimo, sia mentre CP-SAT cerca -- codice nativo,
    # che si ferma solo con StopSearch -- sia fra un tentativo e l'altro. E
    # l'esito di uno stop NON deve sembrare un verdetto: UNKNOWN, mai
    # INFEASIBLE.
    import threading

    from model import Interruzione, solve_auto_zones

    # Una linea su cui CP-SAT non chiude in pochi secondi: dieci mosse con
    # gli svincoli. Misurata: con 30 s di limite restituisce UNKNOWN.
    n = 10
    base = linea(
        n, 2000, [HoistZone(0, n // 2 - 1), HoistZone(n // 2, n - 1)],
        dwell=(30, 300), capacity=3, lift_height=1500,
        kin_lift_empty=Kinematics(v_max=250, a_max=150),
        kin_lift_loaded=Kinematics(v_max=200, a_max=150),
        engage_time=2.0, disengage_time=1.0, takt_min=25.0, takt_max=400.0,
    )
    data = con_ostacoli(base, svincolo=700.0)

    # -- mentre CP-SAT cerca ------------------------------------------------
    fermata = Interruzione()
    ritardo = 4.0  # oltre la costruzione del modello, che dura ~2 s
    timer = threading.Timer(ritardo, fermata.ferma)
    timer.start()
    t0 = time.perf_counter()
    sol = solve(data, time_limit_s=120.0, interruzione=fermata)
    durata = time.perf_counter() - t0
    timer.cancel()
    check(
        ritardo <= durata < ritardo + 3.0,
        f"fermato a {ritardo:.0f} s su un limite di 120, risponde dopo "
        f"{durata:.1f} s",
    )
    check(
        sol.raw.get("interrotto") is True and sol.status in ("UNKNOWN", "FEASIBLE"),
        f"e dice di essere stato interrotto, senza dichiarare niente di "
        f"impossibile ({sol.status})",
    )
    if sol.status == "FEASIBLE":
        # se CP-SAT aveva gia' una soluzione la restituisce, e dev'essere buona
        r = verify_solution(data, sol)
        check(r.ok, "la soluzione trovata prima dello stop supera la verifica")

    # -- fermato prima ancora di partire ------------------------------------
    gia_fermata = Interruzione()
    gia_fermata.ferma()
    t0 = time.perf_counter()
    sol = solve(data, time_limit_s=120.0, interruzione=gia_fermata)
    check(
        sol.status == "UNKNOWN" and sol.raw.get("interrotto")
        and time.perf_counter() - t0 < 0.5,
        "una richiesta gia' fatta non lascia nemmeno costruire il modello",
    )
    tentativi = []
    sol, zone, n_car = solve_auto_hoists(
        data, max_hoists=3, time_limit_per_candidate=5.0,
        su_tentativo=lambda *a: tentativi.append(a), interruzione=gia_fermata,
    )
    check(
        sol.status == "UNKNOWN" and sol.raw.get("interrotto")
        and zone is None and not tentativi
        and len(sol.raw.get("hoist_sweep", [])) == 1,
        f"la ricerca automatica non prova niente e non passa a un carroponte "
        f"in piu' ({len(tentativi)} tentativi, "
        f"{len(sol.raw.get('hoist_sweep', []))} numeri di carroponti)",
    )

    # -- fra un tentativo e l'altro -----------------------------------------
    # Lo stop arriva all'inizio del secondo tentativo: quello non deve
    # risolvere niente, e il terzo non deve nemmeno cominciare.
    piccola = linea(4, 2500, None, takt_max=120.0)
    fermata = Interruzione()

    def al_secondo(n_h, indice, totale, n_valide, best_T):
        tentativi_zone.append(indice)
        if indice == 2:
            fermata.ferma()

    tentativi_zone = []
    sol, zone = solve_auto_zones(
        piccola, n_hoists=2, time_limit_per_candidate=10.0,
        su_tentativo=al_secondo, interruzione=fermata,
    )
    check(
        tentativi_zone == [1, 2] and sol.raw.get("n_tried") == 2,
        f"fermata al secondo tentativo, il terzo non parte "
        f"(avviati {tentativi_zone})",
    )
    check(
        sol.raw.get("interrotto") is True
        and (sol.status != "INFEASIBLE"),
        f"e l'esito non e' un verdetto di impossibilita' ({sol.status})",
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
    test_cambio_quota_end_to_end()
    test_passo_controllo()
    test_scelta_automatica()
    test_tentativi_previsti()
    test_giro_che_non_parte_dal_confine()
    test_diagnosi()
    test_vasca_ripetuta()
    test_ricostruzione_fedele()
    test_dove_sosta_il_carro()
    test_pezzo_in_vasca()
    test_frecce_delle_corse_verticali()
    test_ferma_il_calcolo()
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti  ({time.perf_counter() - t0:.0f}s)")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
