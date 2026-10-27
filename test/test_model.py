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
    errore_pesato,
    estrai_gradi_di_liberta,
    scarti_dal_teorico,
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


def test_sgancio_e_aggancio_fuori_dal_bagno():
    """Sgancio e aggancio sono tempo di GANCIO, non di processo: stanno in
    coda al rilascio e in testa alla presa, e la permanenza in vasca non li
    vede. Occupano pero' il posto, perche' il telaio e' li' in fondo."""
    print("\n[5-bis] sgancio e aggancio stanno fuori dalla permanenza")
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

    # le due fasi esistono e durano quanto dichiarato, ciascuna dalla sua parte
    durate = {f.name: f.duration for f in data.release_phases(1)}
    check(
        abs(durate.get("sgancio", 0.0) - 7.0) < 1e-9,
        f"lo sgancio e' l'ultima fase del rilascio ({durate.get('sgancio')} s)",
    )
    durate = {f.name: f.duration for f in data.pick_phases(1)}
    check(
        abs(durate.get("aggancio", 0.0) - 8.0) < 1e-9,
        f"l'aggancio e' la prima fase della presa ({durate.get('aggancio')} s)",
    )

    # ma il posto resta occupato lo stesso: i 15 s ci sono dentro, insieme
    # alle corse verticali col telaio e allo sgocciolamento
    occ = data.slot_occupancy_seconds(1, 20.0)
    fasi = occ - 20.0
    check(
        fasi >= 15.0 - 1e-9,
        f"il posto e' occupato anche durante sgancio e aggancio "
        f"({fasi:.1f} s oltre il bagno, di cui 15.0 di tempi morti)",
    )

    sol, r = risolvi_e_verifica(data, "bagno stretto", time_limit=60.0)
    check(r is not None and r.ok, _esito(sol, r, "soluzione valida"))
    if r is not None and sol.actual_time:
        at = sol.actual_time
        bagni = [
            at[k] - (at[k - 1] + data.loaded_leg_seconds(k - 1))
            for k in range(1, data.n_moves)
        ]
        check(
            all(20.0 - 0.1 <= b <= 45.0 + 0.1 for b in bagni),
            f"ogni bagno vero sta dentro 20..45 s ({[round(b, 1) for b in bagni]})",
        )

    # una finestra piu' stretta dei soli tempi morti ora e' realizzabile: quei
    # 15 s sono di gancio, non di bagno, e il processo non li vede
    stretta = linea(
        4, 1500, [HoistZone(0, 1), HoistZone(2, 3)], dwell=(5, 12), **comune
    )
    sol2, r2 = risolvi_e_verifica(
        stretta, "bagno piu' corto dei tempi morti", time_limit=60.0
    )
    check(r2 is not None and r2.ok, _esito(sol2, r2, "soluzione valida"))
    if r2 is not None and sol2.actual_time:
        at = sol2.actual_time
        bagni = [
            at[k] - (at[k - 1] + stretta.loaded_leg_seconds(k - 1))
            for k in range(1, stretta.n_moves)
        ]
        check(
            all(5.0 - 0.1 <= b <= 12.0 + 0.1 for b in bagni),
            f"ogni bagno sta dentro 5..12 s ({[round(b, 1) for b in bagni]})",
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
        su_tentativo=lambda h, i, t, v, bt, be: visti.append((h, i, t, v, bt)),
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
        T, fasi, giri, attese, soste = estrai_gradi_di_liberta(data, sol)
        rifatta = build_solution(
            data, T, fasi, extra_periods=giri, attese=attese, soste=soste
        )
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
    T, fasi, giri, attese, soste = estrai_gradi_di_liberta(data, sol)
    check(
        set(attese) == set(range(data.n_moves)),
        f"ogni mossa porta con se' la sua attesa ({len(attese)} su {data.n_moves})",
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
    zero = {j: 0.0 for j in attese}
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

    # E la soluzione del solutore si ricostruisce identica con le sue attese.
    con = verify_solution(
        data,
        build_solution(
            data, T, fasi, extra_periods=giri, attese=attese, soste=soste
        ),
    )
    check(
        abs(con.min_separation - r.min_separation) < 1e-6 and con.ok == r.ok,
        f"con le attese salvate la separazione torna identica "
        f"({con.min_separation:.3f})",
    )


def test_dove_va_ad_aspettare_il_carro():
    print()
    print("[9-quater] il carroponte puo' andare ad aspettare in un'altra vasca")
    # Il quinto grado di liberta'. Fra la consegna di una mossa e il prelievo
    # della successiva il carroponte puo' andare a fermarsi in un'altra vasca
    # della propria zona: serve quando nessuno dei due estremi e' un buon posto
    # dove stare fermi, perche' tutti e due sono dentro la fascia di un vicino.
    import dataclasses

    from model import SostaIntermedia, soste_candidate

    # -- 1) quali vasche sono candidate, e perche' --------------------------
    #
    # Zona di MEZZO: i suoi due estremi sono confini, quindi il rientro
    # dall'uno all'altro e' esattamente il caso che la sosta serve a
    # risolvere.
    tre = linea(
        5, 2000, [HoistZone(0, 0), HoistZone(1, 3), HoistZone(4, 4)],
        dwell=(20, 400), capacity=10, takt_min=30.0, takt_max=60.0,
        hoist_extent_pos=600, hoist_extent_neg=600, safety_distance=600,
    )
    mezzo = tre.zones[1]
    # `quante` esplicito: il default del progetto e' 1 e questi controlli
    # guardano il criterio, non il default.
    check(
        soste_candidate(tre, mezzo, 4, 1, quante=2) == [2, 3],
        f"fra i due confini si puo' sostare nelle vasche in mezzo "
        f"({soste_candidate(tre, mezzo, 4, 1, quante=2)})",
    )
    # IL CASO CHE CONTA DI PIU': due mosse consecutive che condividono la
    # vasca. Il carroponte consegna e riprende nello stesso posto, quindi non
    # si sposta affatto e non esiste nessun "in mezzo" -- se quella vasca e'
    # sotto il naso del vicino, l'unica via d'uscita e' andarsene e tornare.
    # Pretendere una vasca in mezzo lasciava fuori proprio questo, che sulla
    # linea vera e' quello che produce la collisione.
    stretto = dataclasses.replace(tre, safety_distance=1400)  # D = 2600 > passo
    z_stretto = stretto.zones[1]
    fermo_dove_consegna = soste_candidate(stretto, z_stretto, 2, 2, quante=2)
    check(
        fermo_dove_consegna == [3, 1],
        f"si consegna e si riprende nella stessa vasca: si puo' comunque "
        f"andare ad aspettare altrove ({fermo_dove_consegna}), a cominciare "
        f"dalla meno esposta",
    )
    # E una vasca esposta quanto l'estremo NON si scarta: le due esposizioni
    # possono guardare confini diversi, e spostarsi dall'una all'altra risolve
    # se il vicino di quel lato in quel momento e' altrove.
    check(
        1 in fermo_dove_consegna or 4 in fermo_dove_consegna
        or soste_candidate(stretto, z_stretto, 2, 2, quante=4) == [3, 1, 4],
        f"anche le vasche esposte quanto l'estremo restano candidate "
        f"({soste_candidate(stretto, z_stretto, 2, 2, quante=4)})",
    )
    # Un estremo AL RIPARO (piu' lontano dal confine della distanza di
    # sicurezza) rende la sosta inutile: partendo nello stesso istante il
    # rientro diritto attraversa la fascia negli stessi momenti, e poi aspetta
    # in un punto sicuro invece che in un altro. Solo modello piu' grande.
    larga = linea(
        7, 2000, [HoistZone(0, 4), HoistZone(5, 6)],
        dwell=(20, 400), capacity=10, takt_min=30.0, takt_max=120.0,
        hoist_extent_pos=600, hoist_extent_neg=600, safety_distance=600,
    )
    check(
        soste_candidate(larga, larga.zones[0], 5, 0) == [],
        "se un estremo e' al riparo dal confine non c'e' niente da guadagnare",
    )
    check(
        soste_candidate(tre, tre.zones[1], 4, 1, quante=0) == []
        and soste_candidate(
            dataclasses.replace(tre, zones=[HoistZone(0, 4)]),
            HoistZone(0, 4), 5, 0,
        )
        == [],
        "a zero candidati, e con un carroponte solo, non si sosta mai",
    )

    # -- 2) una sosta imposta si vede nel disegno --------------------------
    #
    # Con un carroponte solo non ci sono collisioni: la sosta non serve a
    # niente, ma e' l'unico modo di provare il DISEGNO senza dipendere da
    # quello che il solutore decidera'. Il giro e' lungo e il takt time
    # larghissimo: di tempo morto da spendere ce n'e' quanto basta.
    solo = linea(
        # takt time tenuto alto di proposito: il solutore lo minimizza, e con
        # un takt stretto non resterebbe tempo morto da spendere in una sosta
        4, 2000, [HoistZone(0, 3)], dwell=(20, 600), capacity=10,
        takt_min=200.0, takt_max=260.0,
        # corsa verticale e tempi morti veri: senza, presa e rilascio durano
        # zero e non ci sono i tratti da cui il controllo qui sotto parte
        lift_height=600, drain_time=3.0,
        kin_lift_empty=Kinematics(v_max=500, a_max=800),
        kin_lift_loaded=Kinematics(v_max=300, a_max=500),
        engage_time=2.0, disengage_time=1.0,
    )
    sol, r = risolvi_e_verifica(solo, "carroponte solo")
    if r is None:
        check(False, sol.status + ": niente su cui imporre una sosta")
        return
    T, fasi, giri, attese, soste = estrai_gradi_di_liberta(solo, sol)
    check(soste == {}, "senza vicini il solutore non fa sostare nessuno")

    # Il rientro a vuoto e' quello che chiude il giro: dall'ultima stazione
    # alla prima. Ci si ferma nella vasca di mezzo.
    ultimo = sol.plans[0].order[-1]
    in_mezzo = 2
    durata = 5.0
    # Le attese si azzerano: il tempo morto va tutto lasciato libero, altrimenti
    # la sosta non avrebbe dove starci e il controllo misurerebbe quello.
    zero = {k: 0.0 for k in attese}
    imposta = build_solution(
        solo, T, fasi, extra_periods=giri, attese=zero,
        soste={ultimo: SostaIntermedia(stazione=in_mezzo, secondi=durata)},
    )
    segs = sorted(imposta.segments_per_hoist[0], key=lambda s: s.t_start)
    # i tratti dopo l'ultimo rilascio e prima della prima presa del giro dopo
    i_rel = max(
        j for j, sg in enumerate(segs)
        if sg.kind == "release" and sg.move == ultimo
    )
    rientro = []
    for sg in segs[i_rel + 1:]:
        if sg.kind == "pick":
            break
        rientro.append(sg)
    x_mezzo = solo.approach_position(in_mezzo)
    ferme = [
        sg for sg in rientro
        if sg.kind == "wait" and abs(sg.x_start - x_mezzo) < 1e-6
    ]
    check(
        len(ferme) == 1 and abs((ferme[0].t_end - ferme[0].t_start) - durata) < 1e-6,
        f"il disegno ha una sosta di {durata:.0f} s sulla vasca "
        f"{solo.route[in_mezzo].tank_id}",
    )
    tratte = [sg for sg in rientro if sg.kind == "empty"]
    check(
        len(tratte) == 2
        and abs(tratte[0].x_end - x_mezzo) < 1e-6
        and abs(tratte[1].x_start - x_mezzo) < 1e-6,
        f"e il rientro e' spezzato in due traslate ({len(tratte)}), "
        f"che si toccano proprio la'",
    )
    check(
        verify_solution(solo, imposta).ok,
        "la traiettoria con la sosta supera la verifica indipendente",
    )
    # Il verificatore deve misurare il percorso VERO: una sosta piu' lunga del
    # tempo morto disponibile non ci sta, e dirlo e' il suo mestiere.
    troppo = build_solution(
        solo, T, fasi, extra_periods=giri, attese=zero, tollerante=True,
        soste={ultimo: SostaIntermedia(stazione=in_mezzo, secondi=2 * T)},
    )
    errori = [v for v in verify_solution(solo, troppo).violations if v.kind == "transfer"]
    check(
        bool(errori),
        "una sosta piu' lunga del tempo disponibile viene segnalata: "
        + (errori[0].message[:60] if errori else "NESSUN ERRORE"),
    )
    # E una sosta fuori dalla zona del carroponte non e' una sosta piu' lunga:
    # e' un carro che entra in casa del vicino.
    fuori = build_solution(
        tre, 60.0, {k: 0.0 for k in range(tre.n_moves)},
        tollerante=True, attese={k: 0.0 for k in range(tre.n_moves)},
        # la mossa 1 e' del carroponte di mezzo, che arriva fino alla stazione
        # 4: la 5 e' del vicino
        soste={1: SostaIntermedia(stazione=5, secondi=1.0)},
    )
    check(
        any("fuori dalla zona" in m for m in fuori.raw.get("incoerenze", [])),
        "una sosta fuori dalla zona viene segnalata come incoerenza",
    )

    # -- 3) e serve: su una linea stretta ABBASSA il takt time -------------
    #
    # Tre carroponti, vasche a 1500 mm e distanza di sicurezza tale che la
    # fascia di esclusione copre la vasca accanto al confine: il carro di mezzo
    # consegna su un confine e va a prelevare sull'altro, e i due estremi sono
    # entrambi posti in cui il vicino deve passare. Potendo fermarsi nella
    # vasca in mezzo il ciclo si chiude piu' corto.
    #
    # Il rientro diritto resta fra le alternative, quindi lo spazio di ricerca
    # solo si allarga: il takt time ottimo non puo' salire. Se sale, qualche
    # vincolo sta guardando il percorso sbagliato.
    stretta = dict(
        takt_min=40.0, takt_max=60.0, dwell=(20, 900), capacity=20,
        hoist_extent_pos=600, hoist_extent_neg=600, safety_distance=900,
        lift_height=400, drain_time=3.0,
        kin_lift_empty=Kinematics(v_max=400, a_max=600),
        kin_lift_loaded=Kinematics(v_max=200, a_max=300),
        engage_time=2.0, disengage_time=1.0, clearance_step_mm=300.0,
        # La sosta in mezzo serve a stare lontani dal vicino per la DISTANZA
        # di sicurezza. Con l'interblocco, su vasche a 1500 mm e ganci a
        # 2100, le vasche attorno al confine sono tutte interbloccate fra loro
        # e fermarsi nell'una o nell'altra non libera niente: qui si prova la
        # sosta, non l'interblocco.
        interblocco=False,
    )
    zone_tre = [HoistZone(0, 1), HoistZone(2, 3), HoistZone(4, 5)]
    # Limite di tempo largo di proposito: la domanda e' quale sia l'OTTIMO, non
    # quanto in fretta lo si trova. Il modello con le soste e' piu' grande, e
    # con un limite stretto si fermerebbe prima -- che e' vero, ed e' scritto
    # nel README, ma non e' quello che si prova qui.
    senza = solve(
        linea(6, 1500, zone_tre, max_soste_intermedie=0, **stretta),
        time_limit_s=120.0,
    )
    d_con = linea(6, 1500, zone_tre, max_soste_intermedie=2, **stretta)
    con = solve(d_con, time_limit_s=120.0)
    if senza.status == "OPTIMAL" and con.status == "OPTIMAL":
        check(
            con.T <= senza.T + 1e-6,
            f"col posto in mezzo il takt time non peggiora "
            f"({con.T:.2f} s contro {senza.T:.2f} s)",
        )
        check(
            con.T < senza.T - 0.5
            and sum(len(p.soste_intermedie) for p in con.plans) > 0,
            f"e su questa linea lo MIGLIORA, fermandosi per strada: "
            f"{con.T:.2f} s contro {senza.T:.2f} s",
        )
        for h, p in enumerate(con.plans):
            if p.soste_intermedie:
                print(
                    f"       carro {h + 1}: "
                    + ", ".join(
                        f"{v.secondi:.1f} s in {d_con.route[v.stazione].tank_id} "
                        f"dopo la mossa {k}"
                        for k, v in sorted(p.soste_intermedie.items())
                    )
                )
    else:
        check(False, f"la linea stretta non si e' risolta "
                     f"({senza.status} / {con.status})")
    if con.plans:
        rep = verify_solution(d_con, con)
        check(rep.ok, _esito(con, rep, "e la soluzione con la sosta e' valida"))

def test_riduci_soste():
    print()
    print("[9-bis-bis] le soste che non servono si tolgono, le altre restano")
    # Quando CP-SAT scade prima dell'ottimo, il criterio delle soste -- il
    # secondo, dopo il takt time -- non e' stato guardato, e restano soste di
    # zero secondi: il carro va in un'altra vasca e torna senza fermarsi.
    # `riduci_soste` risolve di nuovo col takt time inchiodato. Il contratto e'
    # che non peggiora mai: stesso takt time, soste in meno, oppure la
    # soluzione di prima COSI' COM'E'.
    import dataclasses

    from model import riduci_soste

    stretta = dict(
        takt_min=40.0, takt_max=60.0, dwell=(20, 900), capacity=20,
        hoist_extent_pos=600, hoist_extent_neg=600, safety_distance=900,
        lift_height=400, drain_time=3.0,
        kin_lift_empty=Kinematics(v_max=400, a_max=600),
        kin_lift_loaded=Kinematics(v_max=200, a_max=300),
        engage_time=2.0, disengage_time=1.0, clearance_step_mm=300.0,
    )
    zone_tre = [HoistZone(0, 1), HoistZone(2, 3), HoistZone(4, 5)]
    d = linea(6, 1500, zone_tre, max_soste_intermedie=2, **stretta)

    def soste(sol):
        return sum(len(p.soste_intermedie) for p in sol.plans)

    # -- 1) una soluzione OPTIMAL non si tocca ------------------------------
    ottima = solve(d, time_limit_s=120.0)
    if ottima.status != "OPTIMAL":
        check(False, f"la linea stretta non si e' risolta ({ottima.status})")
        return
    check(
        ottima.raw.get("n_soste") == soste(ottima),
        f"il conteggio delle soste corrisponde al piano "
        f"({ottima.raw.get('n_soste')} contro {soste(ottima)})",
    )
    check(
        riduci_soste(d, ottima) is ottima,
        "una soluzione OPTIMAL esce tale e quale: l'ottimo conta gia' le soste",
    )

    # -- 2) senza miglioramento si restituisce la soluzione di prima --------
    # Le soste dell'ottimo servono tutte: fingendola FEASIBLE non c'e' niente
    # da togliere, e quello che torna dev'essere lei, soste comprese.
    finta = dataclasses.replace(ottima, status="FEASIBLE")
    check(
        riduci_soste(d, finta) is finta,
        f"se non si toglie niente torna la soluzione di prima, con le sue "
        f"{soste(finta)} soste",
    )
    check(
        riduci_soste(d, finta, time_limit_s=0.001) is finta,
        "e cosi' se il tempo scade prima di trovare qualcosa",
    )

    # -- 3) da una soluzione trovata di corsa: stesso takt, mai piu' soste ---
    di_corsa = solve(d, time_limit_s=2.0)
    if di_corsa.status != "FEASIBLE" or not di_corsa.raw.get("n_soste"):
        print(
            f"       (in 2 s la soluzione e' {di_corsa.status} con "
            f"{di_corsa.raw.get('n_soste')} soste: niente da ridurre)"
        )
        return
    rifinita = riduci_soste(d, di_corsa)
    check(
        abs(rifinita.T - di_corsa.T) < 1e-9 and rifinita.status == "FEASIBLE",
        f"il takt time resta {di_corsa.T:.2f} s, e lo stato FEASIBLE",
    )
    check(
        soste(rifinita) <= soste(di_corsa)
        and rifinita.raw["n_soste"] == soste(rifinita),
        f"le soste non aumentano ({soste(di_corsa)} -> {soste(rifinita)})",
    )
    rep = verify_solution(d, rifinita)
    check(rep.ok, "e la soluzione rifinita supera la verifica indipendente")



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

    def al_secondo(n_h, indice, totale, n_valide, best_T, best_errore):
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


def test_takt_fisso():
    print("\n[23] takt time fisso: si minimizza lo scarto pesato dai teorici")
    import dataclasses

    # Un carroponte solo, tre vasche da 40 s teorici con 30 s di tolleranza
    # per parte. A 30 s di ciclo il giro non sta dentro senza spostare almeno
    # un bagno: con pesi tutti uguali conviene accorciare di ~3 s la vasca di
    # mezzo, che e' lo scarto piu' piccolo possibile.
    def con_pesi(pesi):
        d = linea(4, 1000, [HoistZone(0, 3)], takt_min=25.0, takt_max=35.0)
        route = (
            [d.route[0]]
            + [
                StationSpec.da_teorico(f"V{i}", 40, 30, 30, *pesi[i - 1])
                for i in range(1, 4)
            ]
            + [d.route[-1]]
        )
        return dataclasses.replace(
            d, route=route, takt_nominal=30.0, takt_fisso=True
        )

    def risolvi(pesi, etichetta):
        d = con_pesi(pesi)
        sol, r = risolvi_e_verifica(d, etichetta)
        if r is None:
            return d, sol, None
        return d, sol, scarti_dal_teorico(d, sol.actual_time)

    d, sol, sc = risolvi([(1, 1)] * 3, "pesi uguali")
    check(sc is not None, _esito(sol, sc, "soluzione trovata"))
    if sc is None:
        return
    check(sol.T == 30.0, f"il takt time resta il teorico ({sol.T} s)")
    check(
        sol.raw["errore_pesato"] > 0 and sc[2] < 0 and abs(sc[1]) + abs(sc[3]) < 0.05,
        f"pesi uguali: si accorcia solo la vasca di mezzo "
        f"({ {k: round(v, 2) for k, v in sc.items()} })",
    )
    check(
        abs(errore_pesato(d, scarti_dal_teorico(d, sol.actual_time)) - sol.raw["errore_pesato"]) < 0.1,
        f"lo scarto ricalcolato dagli istanti ({errore_pesato(d, scarti_dal_teorico(d, sol.actual_time)):.2f})"
        f" torna con quello del solutore ({sol.raw['errore_pesato']:.2f})",
    )
    sotto_uguali = -sc[2]

    # Stare sotto costa dieci volte tanto: la vasca di mezzo si allunga
    # invece di accorciarsi, anche se lo scarto in secondi cresce.
    d, sol, sc = risolvi([(1, 1), (10, 1), (1, 1)], "peso sotto alto")
    check(
        sc is not None and sc[2] > sotto_uguali and abs(sc[1]) + abs(sc[3]) < 0.05,
        "peso sotto alto: la vasca di mezzo sta SOPRA il teorico"
        + ("" if sc is None else f" ({sc[2]:+.2f} s)"),
    )

    # Peso alto da tutti e due i lati: la vasca di mezzo resta sul teorico e
    # lo scarto finisce sulle altre.
    d, sol, sc = risolvi([(1, 1), (10, 10), (1, 1)], "peso alto su V2")
    check(
        sc is not None and abs(sc[2]) < 0.05 and abs(sc[1]) + abs(sc[3]) > 0,
        "peso alto su V2: V2 sul teorico, lo scarto va alle altre"
        + ("" if sc is None else f" ({ {k: round(v, 2) for k, v in sc.items()} })"),
    )

    # Senza takt_fisso lo stesso problema cerca il takt minimo, come sempre.
    d = dataclasses.replace(con_pesi([(1, 1)] * 3), takt_fisso=False)
    sol, r = risolvi_e_verifica(d, "takt libero")
    check(
        r is not None and sol.T < 30.0 and sol.raw["errore_pesato"] is None,
        _esito(sol, r, f"takt libero: si scende sotto il teorico ({sol.T} s)"),
    )


def test_rifinitura_tempi_in_vasca():
    print("\n[25] takt libero: a takt trovato, i tempi in vasca vicini ai teorici")
    import dataclasses

    from model import rifinisci_soluzione

    # La stessa linea di [23]: tre vasche da 40 s teorici, un carroponte. A
    # takt libero il calcolo scende al minimo della banda e dei bagni non si
    # cura: la rifinitura deve tenere QUEL takt e avvicinarli ai teorici.
    d = linea(4, 1000, [HoistZone(0, 3)], takt_min=25.0, takt_max=35.0)
    route = (
        [d.route[0]]
        + [
            StationSpec.da_teorico(f"V{i}", 40, 30, 30, *pesi)
            for i, pesi in enumerate([(1, 1), (10, 1), (1, 1)], start=1)
        ]
        + [d.route[-1]]
    )
    d = dataclasses.replace(d, route=route, takt_nominal=30.0)
    sol, r = risolvi_e_verifica(d, "takt libero")
    if r is None:
        check(False, _esito(sol, r, "soluzione a takt libero"))
        return
    prima = errore_pesato(d, scarti_dal_teorico(d, sol.actual_time))
    rif = rifinisci_soluzione(d, sol, time_limit_s=60.0)
    dopo = errore_pesato(d, scarti_dal_teorico(d, rif.actual_time))
    check(rif.T == sol.T, f"il takt time non cambia ({sol.T} -> {rif.T} s)")
    check(
        dopo <= prima + 1e-6 and abs(rif.raw["errore_pesato"] - dopo) < 1e-6,
        f"lo scarto non peggiora mai, e raw lo riporta ({prima:.2f} -> {dopo:.2f})",
    )
    # E' l'ottimo a quel takt: lo stesso che si trova chiedendo il takt fisso.
    fissa = solve(
        dataclasses.replace(d, takt_fisso=True, takt_nominal=sol.T),
        time_limit_s=60.0,
    )
    check(
        fissa.status == "OPTIMAL"
        and abs(dopo - fissa.raw["errore_pesato"]) < 0.05,
        f"ed e' lo scarto minimo a quel takt ({dopo:.2f}, col takt fisso "
        f"{fissa.raw.get('errore_pesato')})",
    )
    rv = verify_solution(d, rif)
    check(rv.ok, "la soluzione rifinita supera la verifica indipendente")
    check(rif.status == sol.status, "lo stato resta quello del calcolo del takt")
    if rif is not sol and "errore_pesato_prima" in rif.raw:
        check(
            abs(rif.raw["errore_pesato_prima"] - prima) < 1e-6,
            "e raw dice da che scarto si e' partiti",
        )

    # Col takt fisso lo scarto era gia' l'obiettivo: niente seconda passata.
    df = dataclasses.replace(d, takt_fisso=True)
    sf = solve(df, time_limit_s=60.0)
    check(
        rifinisci_soluzione(df, sf, time_limit_s=60.0).raw["errore_pesato"]
        == sf.raw["errore_pesato"],
        "col takt fisso la rifinitura non rifa' il calcolo",
    )


def test_takt_fisso_ricerca_zone():
    print("\n[24] takt time fisso: zone, pre-filtro e diagnosi")
    import dataclasses

    from model import diagnosi_zone, solve_auto_zones, tentativi_previsti

    # Cinque mosse, due carroponti: a 25 s le quattro suddivisioni sono tutte
    # fattibili, con scarti diversi. La migliore NON e' la prima provata:
    # tenere la prima che riesce -- che col takt fisso hanno tutte lo stesso
    # T -- darebbe un risultato a caso.
    def dati(T, **kw):
        d = linea(5, 2000, None, takt_min=T - 10, takt_max=T + 10, **kw)
        route = (
            [d.route[0]]
            + [
                StationSpec.da_teorico(f"V{i}", 40, 30, 30, 1 + i, 1)
                for i in range(1, 5)
            ]
            + [d.route[-1]]
        )
        return dataclasses.replace(
            d, route=route, takt_nominal=float(T), takt_fisso=True
        )

    d = dati(25)
    visti = []
    sol, zone = solve_auto_zones(
        d,
        2,
        time_limit_per_candidate=30.0,
        su_tentativo=lambda h, i, t, v, bt, be: visti.append(be),
    )
    singole = []
    for z in (
        [HoistZone(0, 0), HoistZone(1, 4)],
        [HoistZone(0, 1), HoistZone(2, 4)],
        [HoistZone(0, 2), HoistZone(3, 4)],
        [HoistZone(0, 3), HoistZone(4, 4)],
    ):
        s = solve(dataclasses.replace(d, zones=z), time_limit_s=30.0)
        if s.status in ("OPTIMAL", "FEASIBLE"):
            singole.append(s.raw["errore_pesato"])
    check(
        zone is not None
        and sol.T == 25.0
        and abs(sol.raw["errore_pesato"] - min(singole)) < 0.01,
        f"si tiene la suddivisione con lo scarto minore "
        f"({sol.raw.get('errore_pesato')} fra {singole})",
    )
    check(
        visti[0] is None and all(v is not None for v in visti[1:]),
        "l'avanzamento riporta lo scarto della migliore trovata finora",
    )

    # Il pre-filtro deve usare il takt in cui si CERCA: un carroponte solo,
    # col teorico appena sotto il carico della zona e la banda sopra.
    d1 = dati(25)
    carico = sum(d1.loaded_leg_seconds(k) for k in range(d1.n_moves))
    d1 = dataclasses.replace(
        d1, takt_min=carico - 20, takt_max=carico + 20, takt_nominal=carico - 1
    )
    check(
        tentativi_previsti(d1, 1) == 0
        and tentativi_previsti(dataclasses.replace(d1, takt_fisso=False), 1) == 1,
        "pre-filtro: col takt fisso conta il teorico, non la banda",
    )

    # E la diagnosi deve dire che e' il takt FISSO a essere troppo corto,
    # senza suggerire di allargare i delta del takt, che qui non contano.
    righe = diagnosi_zone(
        d1, [HoistZone(0, d1.n_moves - 1)], time_limit_s=30.0,
        dettaglio_vasche=False,
    )
    testo = " ".join(righe)
    check(
        "TAKT TIME FISSO E' TROPPO CORTO" in testo
        and "takt_delta_positivo_s" not in testo,
        f"diagnosi: '{testo[:70]}...'",
    )


def test_interblocco():
    """L'interblocco delle vasche, dal solutore al verificatore.

    Il caso e' costruito perche' la differenza si veda: la vasca comune V2 ha
    un bagno di al piu' 9 s, e le vasche vicine stanno a 6000 mm. La distanza
    di sicurezza si accontenta di qualche secondo -- uno se ne va mentre
    l'altro arriva -- mentre con l'interblocco il secondo carroponte puo'
    partire solo quando il primo e' arrivato in V1, e i due viaggi in fila
    non ci stanno in 9 s."""
    print("\n[26] interblocco delle vasche")
    import dataclasses

    from model import diagnosi_zone

    zone = [HoistZone(0, 1), HoistZone(2, 3)]

    # 1) una linea normale: il solutore lo rispetta, il verificatore concorda
    larga = linea(4, 6000, zone, dwell=(5, 60), takt_max=60.0)
    sol, r = risolvi_e_verifica(larga, "interblocco su linea larga")
    check(
        r is not None and r.ok and sol.raw["n_interlock_constraints"] > 0,
        _esito(
            sol, r,
            f"con l'interblocco la soluzione passa la verifica "
            f"(T={sol.T}, {sol.raw.get('n_interlock_constraints')} vincoli)",
        ),
    )

    # 2) la vasca comune con il bagno corto
    route = list(larga.route)
    route[2] = StationSpec("V2", 0.5, 9.0)
    corta = dataclasses.replace(larga, route=route)
    check(
        solve(corta, time_limit_s=60.0).status == "INFEASIBLE",
        "con l'interblocco il bagno corto sulla vasca comune non basta",
    )
    sol, r = risolvi_e_verifica(
        dataclasses.replace(corta, interblocco=False), "senza interblocco"
    )
    check(
        r is not None and r.ok,
        _esito(sol, r, "senza interblocco la stessa linea si risolve"),
    )
    # 3) la diagnosi nomina l'interblocco, e la vasca
    righe = diagnosi_zone(corta, zone, time_limit_s=30.0)
    check(
        any("INTERBLOCCO" in riga and "V2" in riga for riga in righe),
        f'la diagnosi lo riconosce: "{righe[0][:70]}..."',
    )


def test_portate():
    """Le portate del foglio Zone: limiti, non zone.

    Linea di cinque vasche ogni 6000 mm. Il carroponte 1 arriva da V0 a V2, il
    2 da V1 a V4: V1 e V2 le possono servire tutti e due. Delle tre
    suddivisioni in due zone, solo quella che manda il carroponte 1 fino a V3
    e' vietata -- le altre due il solutore le deve provare entrambe."""
    print("\n[27] portate dei carroponti")
    import dataclasses

    import manuale
    from model import Portata, solve_auto_zones, tentativi_previsti

    base = linea(4, 6000, None, dwell=(5, 60), takt_max=60.0)
    d = dataclasses.replace(
        base, portate=[Portata("V0", "V2"), Portata("V4", "V1")]
    )
    check(
        tentativi_previsti(base, 2) == 3 and tentativi_previsti(d, 2) == 2,
        f"le portate tolgono solo la suddivisione vietata: "
        f"{tentativi_previsti(base, 2)} -> {tentativi_previsti(d, 2)}",
    )

    # max_hoists=1 non conta: i carroponti sono quelli delle portate
    sol, zone, n = solve_auto_hoists(d, max_hoists=1, time_limit_per_candidate=30.0)
    ammesse = ([(0, 0), (1, 3)], [(0, 1), (2, 3)])
    trovate = [(z.lo, z.hi) for z in zone] if zone else None
    check(
        n == 2 and trovate in ammesse,
        f"la ricerca usa i 2 carroponti dichiarati e una zona ammessa: "
        f"{n} carroponti, zone {trovate}",
    )
    if zone:
        r = verify_solution(dataclasses.replace(d, zones=zone), sol)
        check(r.ok, _esito(sol, r, "e la soluzione passa la verifica"))

        # la stessa soluzione, con una portata che non la contiene: il
        # verificatore guarda la traiettoria e se ne accorge
        stretta = dataclasses.replace(
            d, zones=zone, portate=[Portata("V0", "V0"), Portata("V1", "V4")]
        )
        fuori = [v for v in verify_solution(stretta, sol).violations if v.kind == "reach"]
        check(
            len(fuori) == 1 and fuori[0].hoists == (0,) and fuori[0].severity == "error",
            f"il verificatore segnala il carroponte fuori portata: "
            f"{[str(v) for v in fuori]}",
        )

    try:
        solve(dataclasses.replace(d, zones=[HoistZone(0, 2), HoistZone(3, 3)]))
        check(False, "solve() rifiuta una suddivisione fuori portata")
    except ValueError as e:
        check(
            "portata" in str(e) and "V3" in str(e),
            "solve() rifiuta una suddivisione fuori portata, nominando la vasca",
        )
    try:
        solve_auto_zones(d, n_hoists=3)
        check(False, "con le portate il numero di carroponti e' fissato")
    except ValueError as e:
        check("foglio Zone" in str(e), "con le portate il numero di carroponti e' fissato")
    try:
        dataclasses.replace(base, portate=[Portata("V0", "NESSUNA")])
        check(False, "una portata con una vasca sconosciuta e' rifiutata")
    except ValueError as e:
        check("NESSUNA" in str(e), "una portata con una vasca sconosciuta e' rifiutata")

    # il disegno a mano non lascia dare una mossa fuori portata
    check(
        manuale.perche_non_va(d, {0: 0, 1: 0, 2: 1, 3: 1}) is None,
        "a mano: una suddivisione ammessa passa",
    )
    motivo = manuale.perche_non_va(d, {2: 0})
    check(
        motivo is not None and "portata" in motivo and "V3" in motivo,
        f"a mano: la mossa V2 -> V3 al carroponte 1 e' rifiutata: {motivo}",
    )
    motivo = manuale.perche_non_va(d, {0: 2})
    check(
        motivo is not None and "solo 2" in motivo,
        f"a mano: un carroponte che il foglio non dichiara non esiste: {motivo}",
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
    test_sgancio_e_aggancio_fuori_dal_bagno()
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
    test_dove_va_ad_aspettare_il_carro()
    test_riduci_soste()
    test_pezzo_in_vasca()
    test_frecce_delle_corse_verticali()
    test_ferma_il_calcolo()
    test_takt_fisso()
    test_takt_fisso_ricerca_zone()
    test_rifinitura_tempi_in_vasca()
    test_interblocco()
    test_portate()
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti  ({time.perf_counter() - t0:.0f}s)")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
