"""
test_verify.py
--------------
Test del verificatore indipendente (verify.py).

NON richiede OR-Tools: le soluzioni sono costruite a mano, sia corrette sia
rotte di proposito. Serve a rispondere alla domanda "chi verifica il
verificatore?": un controllore che non segnala mai nulla e' inutile, quindi
per ogni controllo c'e' un caso che DEVE farlo scattare.

Per eseguirlo:
    python test_verify.py
"""

from __future__ import annotations

import dataclasses

from kinematics import Kinematics
from model import (
    HoistPlan,
    HoistZone,
    ProblemData,
    Segment,
    Solution,
    StationSpec,
    Tank,
    _build_zone_trajectory,
    solve,
    zone_layout_conflicts,
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


def kinds(report, kind: str, severity: str | None = None) -> list:
    return [
        v
        for v in report.violations
        if v.kind == kind and (severity is None or v.severity == severity)
    ]


# --------------------------------------------------------------------------
# Costruzione di un caso di riferimento CORRETTO, senza CP-SAT
# --------------------------------------------------------------------------


def make_data(positions, dwells, zones, **kw) -> ProblemData:
    """dwells: lista di (dwell_min, dwell_max) oppure (dwell_min, dwell_max,
    capacity) per stazione. Qui ogni vasca compare una volta sola nel
    percorso, quindi la capacity della tappa e' quella della vasca."""
    caps = [spec[2] if len(spec) > 2 else 1 for spec in dwells]
    tanks = {f"V{i}": Tank(f"V{i}", p, caps[i]) for i, p in enumerate(positions)}
    route = [StationSpec(f"V{i}", spec[0], spec[1]) for i, spec in enumerate(dwells)]
    params = dict(
        tanks=tanks,
        route=route,
        takt_min=50.0,
        takt_max=200.0,
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


def build_solution(
    data: ProblemData,
    T: float,
    local_picks: list[dict],
    extra_periods: dict[int, int] | None = None,
) -> Solution:
    """Costruisce una Solution coerente a partire dalle sole fasi di prelievo,
    lasciando che sia _build_zone_trajectory a generare i segmenti (la stessa
    funzione usata dal solver, cosi' il test verifica il verificatore e non una
    seconda implementazione).

    extra_periods[k]: periodi in piu' da aggiungere al tempo assoluto della
    mossa k. Non cambia la fase locale (quindi nemmeno le traiettorie), ma
    allunga la permanenza nella vasca k di altrettanti takt: serve a costruire
    i casi in cui piu' pezzi stanno nella stessa vasca."""
    extra_periods = extra_periods or {}
    segments_per_hoist = []
    plans = []

    # tempi assoluti: catena di flusso del pezzo, ricavata dalle fasi locali
    # salendo al primo istante compatibile con l'arrivo del pezzo
    actual_time = [0.0] * data.n_moves
    for lp in local_picks:
        for k, v in lp.items():
            actual_time[k] = v
    for k in range(1, data.n_moves):
        arrivo = actual_time[k - 1] + data.loaded_leg_seconds(k - 1)
        while actual_time[k] < arrivo:
            actual_time[k] += T
        actual_time[k] += extra_periods.get(k, 0) * T

    for z, lp in zip(data.zones, local_picks):
        order = sorted(lp, key=lambda k: lp[k])
        order = order[order.index(z.lo) :] + order[: order.index(z.lo)]
        finish = {k: lp[k] + data.loaded_leg_seconds(k) for k in lp}
        # convenzione "parte appena possibile": dal confine alto si riparte
        # subito dopo la consegna, e si arriva al confine basso dopo il solo
        # tempo di percorrenza (l'eventuale margine diventa un'attesa)
        dep_hi = finish[z.hi]
        prev = order[-1]
        arr_lo = finish[prev] + data.empty_leg_seconds(
            data.station_position(prev + 1), data.station_position(z.lo)
        )
        segs = _build_zone_trajectory(data, z, order, lp, dep_hi, arr_lo, T)
        segments_per_hoist.append(segs)
        plans.append(HoistPlan(z, order, lp, finish, dep_hi, arr_lo))

    return Solution(
        status="OPTIMAL",
        T=T,
        segments_per_hoist=segments_per_hoist,
        raw={},
        plans=plans,
        actual_time=actual_time,
    )


def reference_case():
    """Due carroponti su 4 mosse, vasche ben distanziate, tutto regolare."""
    data = make_data(
        positions=[0.0, 5.0, 10.0, 15.0, 20.0],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
    )
    T = 100.0
    d0 = data.loaded_leg_seconds(0)
    lp = [
        {0: 0.0, 1: d0 + 40.0},
        {2: 10.0, 3: 55.0},
    ]
    return data, build_solution(data, T, lp)


# --------------------------------------------------------------------------
# Test
# --------------------------------------------------------------------------


def test_caso_corretto():
    print("\n[1] caso di riferimento corretto")
    data, sol = reference_case()
    r = verify_solution(data, sol)
    check(r.ok, "nessun errore su una soluzione valida")
    check(
        r.min_separation >= r.required_separation,
        f"separazione minima {r.min_separation:.3f}m >= "
        f"{r.required_separation:.3f}m richiesti",
    )
    check(r.n_samples > 1000, f"campionamento fitto ({r.n_samples} istanti)")
    check(
        r.sampling_error_bound < 1e-3,
        f"errore di campionamento trascurabile ({r.sampling_error_bound:.2e} m)",
    )


def test_collisione_reale():
    print("\n[2] collisione vera: due carroponti nello stesso punto")
    data, sol = reference_case()
    # sposto la traiettoria del secondo carroponte sopra quella del primo
    rotto = dataclasses.replace(sol)
    rotto.segments_per_hoist = [
        sol.segments_per_hoist[0],
        [
            dataclasses.replace(s, x_start=s.x_start - 10.0, x_end=s.x_end - 10.0)
            for s in sol.segments_per_hoist[1]
        ],
    ]
    r = verify_solution(data, rotto)
    check(not r.ok, "la soluzione viene respinta")
    check(len(kinds(r, "collision", "error")) == 1, "segnalata una collisione")
    check(
        r.min_separation < r.required_separation,
        f"separazione minima misurata {r.min_separation:.3f}m sotto il minimo",
    )


def test_collisione_solo_in_transito():
    print("\n[3] collisione che si vede SOLO campionando dentro il movimento")
    # I due carroponti stanno sempre a >= 1.8 m se si guardano solo gli
    # estremi dei segmenti, ma si incrociano a meta' di uno spostamento.
    data = make_data(
        positions=[0.0, 5.0, 10.0, 15.0, 20.0],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
    )
    T = 100.0
    segs_a = [
        Segment("empty", 0.0, 20.0, 0.0, 10.0, KIN_EMPTY),
        Segment("wait", 20.0, 100.0, 10.0, 10.0, None),
    ]
    segs_b = [
        Segment("wait", 0.0, 10.0, 12.0, 12.0, None),
        Segment("empty", 10.0, 30.0, 12.0, 2.0, KIN_EMPTY),
        Segment("wait", 30.0, 100.0, 2.0, 2.0, None),
    ]
    # agli estremi dei segmenti la distanza e' sempre >= 2 m; a meta' i due si
    # incrociano davvero
    sol = Solution(status="OPTIMAL", T=T, segments_per_hoist=[segs_a, segs_b])
    r = verify_solution(data, sol)
    check(len(kinds(r, "collision", "error")) >= 1, "l'incrocio in transito viene visto")
    check(
        r.min_separation < 0.5,
        f"separazione minima {r.min_separation:.3f}m (i due si attraversano)",
    )
    check(
        0.0 < r.min_separation_t < T,
        f"l'istante critico {r.min_separation_t:.2f}s cade dentro il movimento",
    )


def test_permanenza_fuori_range():
    print("\n[4] permanenze fuori tolleranza")
    data, sol = reference_case()

    troppo_corta = dataclasses.replace(sol)
    troppo_corta.actual_time = list(sol.actual_time)
    troppo_corta.actual_time[1] -= 60.0  # dwell in vasca 1 scende sotto il minimo
    r = verify_solution(data, troppo_corta)
    check(len(kinds(r, "dwell_min", "error")) >= 1, "permanenza troppo breve segnalata")

    troppo_lunga = dataclasses.replace(sol)
    troppo_lunga.actual_time = list(sol.actual_time)
    troppo_lunga.actual_time[1] += 100.0
    r = verify_solution(data, troppo_lunga)
    check(len(kinds(r, "dwell_max", "error")) >= 1, "permanenza troppo lunga segnalata")


def test_periodicita_rotta():
    print("\n[5] periodicita': actual_time non congruo a local_pick modulo T")
    data, sol = reference_case()
    rotto = dataclasses.replace(sol)
    rotto.actual_time = list(sol.actual_time)
    rotto.actual_time[2] += 7.0  # non piu' un multiplo intero di T
    r = verify_solution(data, rotto)
    check(
        len(kinds(r, "periodicity", "error")) >= 1,
        "lo scarto non multiplo di T viene visto",
    )


def test_ciclo_di_durata_sbagliata():
    print("\n[6] il ciclo non dura T")
    data, sol = reference_case()
    rotto = dataclasses.replace(sol)
    segs = list(sol.segments_per_hoist[0])
    segs[-1] = dataclasses.replace(segs[-1], t_end=segs[-1].t_end - 5.0)
    rotto.segments_per_hoist = [segs, sol.segments_per_hoist[1]]
    r = verify_solution(data, rotto)
    check(len(kinds(r, "periodicity", "error")) >= 1, "durata del ciclo != T segnalata")


def test_discontinuita():
    print("\n[7] discontinuita' nella traiettoria")
    data, sol = reference_case()
    rotto = dataclasses.replace(sol)
    segs = list(sol.segments_per_hoist[0])
    segs[0] = dataclasses.replace(segs[0], x_end=segs[0].x_end + 2.0)
    rotto.segments_per_hoist = [segs, sol.segments_per_hoist[1]]
    r = verify_solution(data, rotto)
    check(
        len(kinds(r, "continuity", "error")) >= 1
        or len(kinds(r, "segment_duration", "error")) >= 1,
        "il salto di posizione viene visto",
    )


def test_durata_tratta_sbagliata():
    print("\n[8] tratta piu' veloce di quanto la cinematica consenta")
    data, sol = reference_case()
    rotto = dataclasses.replace(sol)
    segs = list(sol.segments_per_hoist[0])
    i = next(i for i, s in enumerate(segs) if s.kind == "loaded")
    segs[i] = dataclasses.replace(segs[i], t_end=segs[i].t_end - 3.0)
    rotto.segments_per_hoist = [segs, sol.segments_per_hoist[1]]
    r = verify_solution(data, rotto)
    check(
        len(kinds(r, "segment_duration", "error")) >= 1,
        "la durata impossibile viene vista",
    )


def test_layout_stretto():
    print("\n[9] vasche ravvicinate: gestite, non rifiutate")
    # 10.0 e 11.0 distano 1.0 m, meno di hoist_length + safety_distance = 1.8:
    # una geometria che il vecchio modello non sapeva rappresentare e che ora
    # e' coperta dal vincolo a fascia
    data = make_data(
        positions=[0.0, 5.0, 10.0, 11.0, 20.0],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
    )
    check(
        zone_layout_conflicts(data, data.zones) == [],
        "la geometria non viene piu' segnalata come irrappresentabile",
    )
    T = 100.0
    d0 = data.loaded_leg_seconds(0)
    sol = build_solution(data, T, [{0: 0.0, 1: d0 + 40.0}, {2: 10.0, 3: 55.0}])
    r = verify_solution(data, sol)
    check(
        not kinds(r, "layout", "warning"),
        "nessun avviso di layout sulla sola vicinanza",
    )
    # questa soluzione, costruita a mano, e' comunque insicura: la collisione
    # deve essere trovata dal controllo che conta davvero
    check(
        len(kinds(r, "collision", "error")) >= 1,
        f"la collisione reale viene trovata (sep_min={r.min_separation:.3f} m)",
    )


def test_layout_patologico():
    print("\n[10] geometrie che restano irrappresentabili")
    # zone adiacenti che NON stanno su lati opposti del confine: le posizioni
    # delle vasche non seguono l'ordine del percorso
    data_lati = make_data(
        positions=[0.0, 10.0, 5.0, 15.0, 20.0],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
    )
    problemi = zone_layout_conflicts(data_lati, data_lati.zones)
    check(
        any("lati opposti" in p for p in problemi),
        "zone a cavallo del proprio confine: individuate",
    )
    try:
        solve(data_lati, time_limit_s=1.0)
        check(False, "solve() doveva rifiutare la geometria")
    except ValueError as e:
        check(
            "non e' rappresentabile in modo sicuro" in str(e),
            "solve() la rifiuta con un messaggio esplicito",
        )

    # zone NON adiacenti che si sovrappongono nello spazio: il vincolo a
    # fascia e' costruito per coppie adiacenti, quindi non le copre
    data_nm = make_data(
        positions=[0.0, 6.0, 12.0, 1.0, 7.0, 13.0],
        dwells=[(0, 0)] + [(30, 90)] * 4 + [(0, 0)],
        zones=[HoistZone(0, 0), HoistZone(1, 2), HoistZone(3, 4)],
    )
    check(
        any(
            "non sono adiacenti" in p
            for p in zone_layout_conflicts(data_nm, data_nm.zones)
        ),
        "sovrapposizione fra zone non adiacenti individuata",
    )

    # una linea ordinata e ravvicinata non deve dare falsi allarmi
    data_ok = make_data(
        positions=[i * 1.0 for i in range(5)],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
    )
    check(
        zone_layout_conflicts(data_ok, data_ok.zones) == [],
        "linea ordinata a 1 m di passo: nessun problema di geometria",
    )


def test_ingombro_asimmetrico():
    print("\n[11] ingombro asimmetrico: conta solo la somma dei due lati")
    posizioni = [0.0, 5.0, 10.0, 15.0, 20.0]
    dwells = [(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)]
    zone = [HoistZone(0, 1), HoistZone(2, 3)]

    def richiesta(pos, neg):
        d = make_data(
            positions=posizioni,
            dwells=dwells,
            zones=zone,
            hoist_extent_pos=pos,
            hoist_extent_neg=neg,
        )
        d0 = d.loaded_leg_seconds(0)
        sol = build_solution(d, 100.0, [{0: 0.0, 1: d0 + 40.0}, {2: 10.0, 3: 55.0}])
        return d.hoist_length, verify_solution(d, sol).required_separation

    # il bordo destro del carroponte di sinistra sta in p+pos, il bordo
    # sinistro di quello di destra in q-neg: lo spazio libero vale
    # q-p-(pos+neg), quindi dove sta il gancio dentro il carrello non conta
    valori = [richiesta(0.6, 0.6), richiesta(0.2, 1.0), richiesta(1.1, 0.1)]
    check(
        all(abs(v[0] - 1.2) < 1e-9 for v in valori),
        "ingombro totale sempre 1.20 m, comunque ripartito",
    )
    check(
        len({round(v[1], 9) for v in valori}) == 1,
        f"distanza richiesta identica nei tre casi: {valori[0][1]:.3f} m",
    )
    check(
        abs(valori[0][1] - (1.2 + 0.6)) < 1e-9,
        "distanza richiesta = ingombro totale + distanza di sicurezza",
    )

    d = make_data(
        positions=posizioni,
        dwells=dwells,
        zones=zone,
        hoist_extent_pos=0.0,
        hoist_extent_neg=0.0,
    )
    check(d.hoist_length == 0.0, "ingombro nullo ammesso (carroponte puntiforme)")
    for pos, neg in ((-0.1, 0.5), (0.5, -0.1)):
        try:
            make_data(
                positions=posizioni,
                dwells=dwells,
                zones=zone,
                hoist_extent_pos=pos,
                hoist_extent_neg=neg,
            )
            check(False, f"ingombro negativo ({pos}, {neg}) doveva essere respinto")
        except ValueError:
            check(True, f"ingombro negativo ({pos}, {neg}) respinto")


def test_takt_fuori_banda():
    print("\n[12] takt time fuori dalla banda dichiarata")
    data, sol = reference_case()
    stretto = dataclasses.replace(data, takt_min=110.0, takt_max=150.0)
    r = verify_solution(stretto, sol)
    check(len(kinds(r, "takt_range", "error")) >= 1, "T fuori banda segnalato")


def test_capienza_vasca():
    print("\n[13] capienza della vasca (posti simultanei)")
    positions = [0.0, 5.0, 10.0, 15.0, 20.0]
    zones = [HoistZone(0, 1), HoistZone(2, 3)]
    T = 100.0

    def caso(cap):
        data = make_data(
            positions=positions,
            dwells=[(0, 0), (30, 90), (150, 300, cap), (30, 90), (0, 0)],
            zones=zones,
        )
        d0 = data.loaded_leg_seconds(0)
        # +2 periodi sulla mossa 2: il pezzo resta in V2 per oltre due takt,
        # quindi ce ne sono sempre 3 dentro contemporaneamente
        sol = build_solution(
            data, T, [{0: 0.0, 1: d0 + 40.0}, {2: 10.0, 3: 55.0}], extra_periods={2: 2}
        )
        return data, verify_solution(data, sol)

    _, r1 = caso(1)
    check(
        r1.tank_occupancy.get("V2", 1) == 3,
        f"conteggio posti richiesti in V2 = {r1.tank_occupancy.get('V2')} (atteso 3)",
    )
    check(
        len(kinds(r1, "tank_capacity", "error")) == 1 and not r1.ok,
        "con capacity=1 e' un ERRORE",
    )
    _, r3 = caso(3)
    check(
        r3.ok and len(kinds(r3, "tank_capacity", "info")) == 1,
        "con capacity=3 e' solo una nota informativa",
    )

    # l'occupazione di un posto comprende anche le fasi verticali
    data_v = make_data(
        positions=positions,
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=zones,
        pick_time=6.0,
        release_time=4.0,
    )
    check(
        abs(data_v.slot_occupancy_seconds(2, 50.0) - 60.0) < 1e-9,
        "occupazione posto = rilascio + bagno + presa",
    )


def test_capienza_validazione():
    print("\n[14] validazione della capienza in ProblemData")
    base = dict(
        positions=[0.0, 5.0, 10.0],
        zones=[HoistZone(0, 1)],
    )
    try:
        make_data(dwells=[(0, 0), (30, 90, 0), (0, 0)], **base)
        check(False, "capacity=0 doveva essere respinta")
    except ValueError as e:
        check("capacity deve essere >= 1" in str(e), f"capacity=0 respinta: {e}")

    # capienza palesemente insufficiente: infattibile qualunque sia il resto
    try:
        make_data(
            dwells=[(0, 0), (300, 400), (0, 0)],
            takt_min=50.0,
            takt_max=200.0,
            **base,
        )
        check(False, "capienza impossibile doveva essere respinta")
    except ValueError as e:
        check(
            "occupa un posto per almeno" in str(e),
            "capienza impossibile respinta con messaggio esplicito",
        )
    # con 2 posti la stessa configurazione passa
    d = make_data(
        dwells=[(0, 0), (300, 400, 2), (0, 0)],
        takt_min=50.0,
        takt_max=200.0,
        **base,
    )
    check(d.tank_capacity(1) == 2, "con capacity=2 la stessa linea e' accettata")


def _linea_vasca_ripetuta(cap_lav: int, dwell=(20, 90)) -> ProblemData:
    """Il pezzo torna DUE volte nella stessa vasca fisica LAV."""
    return ProblemData(
        tanks={
            "CAR": Tank("CAR", 0.0),
            "LAV": Tank("LAV", 5.0, capacity=cap_lav),
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
        takt_min=50.0,
        takt_max=200.0,
        kin_empty=KIN_EMPTY,
        kin_loaded=KIN_LOADED,
        hoist_extent_pos=0.5,
        hoist_extent_neg=0.7,
        safety_distance=0.6,
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
        time_scale=100,
    )


def test_vasca_ripetuta():
    print("\n[15] stessa vasca fisica usata in piu' tappe del percorso")
    T = 100.0

    # (a) le due permanenze in LAV sono SFASATE fra loro: un posto solo basta,
    #     anche se ciascuna tappa ne userebbe uno. Sommare i massimi darebbe 2
    #     e scarterebbe una soluzione valida.
    data = _linea_vasca_ripetuta(cap_lav=1)
    d0 = data.loaded_leg_seconds(0)
    sol = build_solution(data, T, [{0: 0.0, 1: d0 + 20.0}, {2: 40.0, 3: 70.0}])
    r = verify_solution(data, sol)
    n = r.tank_occupancy.get("LAV")
    check(
        n == 1,
        f"tappe sfasate: LAV richiede {n} posto/i (non la somma delle tappe)",
    )
    check(not kinds(r, "tank_capacity", "error"), "con capacity=1 nessun errore")

    # (b) permanenze lunghe: i pezzi delle due tappe convivono davvero
    data2 = _linea_vasca_ripetuta(cap_lav=1, dwell=(150, 300))
    sol2 = build_solution(
        data2, T, [{0: 0.0, 1: 10.0}, {2: 40.0, 3: 70.0}], extra_periods={1: 1, 3: 1}
    )
    r2 = verify_solution(data2, sol2)
    n2 = r2.tank_occupancy.get("LAV")
    check(n2 >= 3, f"permanenze lunghe: LAV richiede {n2} posti")
    check(
        len(kinds(r2, "tank_capacity", "error")) == 1 and not r2.ok,
        "con capacity=1 e' un ERRORE",
    )


def test_fasi_verticali():
    print("\n[16] tempi di presa/rilascio (immersione verticale)")
    data = make_data(
        positions=[0.0, 5.0, 10.0, 15.0, 20.0],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
        pick_time=6.0,
        release_time=4.0,
    )
    check(
        abs(data.loaded_leg_seconds(0) - (6.0 + data.horizontal_loaded_seconds(0) + 4.0))
        < 1e-9,
        "la durata della mossa comprende presa e rilascio",
    )
    check(
        abs(data.empty_leg_seconds(0.0, 5.0) - data.empty_leg_seconds(5.0, 0.0)) < 1e-9
        and abs(data.empty_leg_seconds(0.0, 0.0)) < 1e-9,
        "lo spostamento a vuoto non paga tempo verticale",
    )

    T = 130.0
    d0 = data.loaded_leg_seconds(0)
    sol = build_solution(data, T, [{0: 0.0, 1: d0 + 40.0}, {2: 10.0, 3: 65.0}])
    r = verify_solution(data, sol)
    check(r.ok, "soluzione con fasi verticali verificata senza errori")

    segs = sol.segments_per_hoist[0]
    check(
        any(s.kind == "pick" for s in segs) and any(s.kind == "release" for s in segs),
        "vengono emessi segmenti 'pick' e 'release'",
    )
    for s in segs:
        if s.kind in ("pick", "release"):
            check(
                s.x_start == s.x_end and s.kin is None,
                f"il segmento '{s.kind}' e' fermo sopra la vasca",
            )
            break

    # una fase verticale allungata a mano deve far scattare il controllo
    rotto = dataclasses.replace(sol)
    lista = list(segs)
    i = next(i for i, s in enumerate(lista) if s.kind == "pick")
    lista[i] = dataclasses.replace(lista[i], t_end=lista[i].t_end + 3.0)
    lista[i + 1] = dataclasses.replace(lista[i + 1], t_start=lista[i + 1].t_start + 3.0)
    rotto.segments_per_hoist = [lista, sol.segments_per_hoist[1]]
    r = verify_solution(data, rotto)
    check(
        len(kinds(r, "segment_duration", "error")) >= 1,
        "una presa piu' lunga del dichiarato viene vista",
    )


def test_zero_verticale_non_regressione():
    print("\n[17] con tempi verticali nulli non cambia nulla")
    data_zero = make_data(
        positions=[0.0, 5.0, 10.0, 15.0, 20.0],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
        pick_time=0.0,
        release_time=0.0,
    )
    _, sol_rif = reference_case()
    d0 = data_zero.loaded_leg_seconds(0)
    sol_zero = build_solution(
        data_zero, 100.0, [{0: 0.0, 1: d0 + 40.0}, {2: 10.0, 3: 55.0}]
    )
    uguali = all(
        len(a) == len(b)
        and all(
            x.kind == y.kind
            and abs(x.t_start - y.t_start) < 1e-12
            and abs(x.t_end - y.t_end) < 1e-12
            for x, y in zip(a, b)
        )
        for a, b in zip(sol_rif.segments_per_hoist, sol_zero.segments_per_hoist)
    )
    check(uguali, "segmenti identici al caso senza fasi verticali")
    check(
        not any(
            s.kind in ("pick", "release")
            for segs in sol_zero.segments_per_hoist
            for s in segs
        ),
        "nessun segmento verticale di durata nulla viene emesso",
    )


def test_stazione_condivisa():
    print("\n[18] due mosse consecutive che partono dalla stessa stazione")
    # il carroponte consegna in V2 e riparte subito da V2: non c'e' nessuno
    # spostamento a vuoto, e non deve comparire un segmento degenere
    data = make_data(
        positions=[0.0, 5.0, 10.0, 15.0],
        dwells=[(0, 0), (30, 90), (0, 90), (0, 0)],
        zones=[HoistZone(0, 0), HoistZone(1, 2)],
        pick_time=2.0,
        release_time=2.0,
    )
    T = 120.0
    lp1 = 20.0
    sol = build_solution(
        data,
        T,
        [{0: 0.0}, {1: lp1, 2: lp1 + data.loaded_leg_seconds(1)}],
    )
    segs = sol.segments_per_hoist[1]
    check(
        not any(s.t_end - s.t_start < 1e-9 for s in segs),
        "nessun segmento di durata nulla",
    )
    r = verify_solution(data, sol)
    check(
        not kinds(r, "continuity", "error"),
        "traiettoria continua nonostante la stazione condivisa",
    )
    check(
        not kinds(r, "segment_duration", "error"),
        "durata della mossa riconosciuta correttamente",
    )


def test_input_malformato():
    print("\n[19] input malformato: eccezione, non report")
    data, sol = reference_case()
    for descr, arg_data, arg_sol in [
        ("status infattibile", data, dataclasses.replace(sol, status="INFEASIBLE")),
        ("T mancante", data, dataclasses.replace(sol, T=None)),
        ("zone non definite", dataclasses.replace(data, zones=None), sol),
    ]:
        try:
            verify_solution(arg_data, arg_sol)
            check(False, f"{descr}: doveva sollevare ValueError")
        except ValueError:
            check(True, f"{descr}: ValueError come previsto")


def test_senza_valori_risolti():
    print("\n[20] degrado gentile senza solution.plans")
    data, sol = reference_case()
    ridotta = Solution(
        status=sol.status, T=sol.T, segments_per_hoist=sol.segments_per_hoist
    )
    r = verify_solution(data, ridotta)
    check(r.ok, "la verifica gira comunque")
    check(
        any(v.kind == "dwell" and v.severity == "info" for v in r.violations),
        "avvisa che le permanenze non sono verificabili",
    )
    check(
        r.min_separation >= r.required_separation,
        "il controllo collisioni resta pienamente attivo",
    )


def main():
    print("=" * 72)
    print("TEST DEL VERIFICATORE (verify.py) -- non richiede OR-Tools")
    print("=" * 72)
    test_caso_corretto()
    test_collisione_reale()
    test_collisione_solo_in_transito()
    test_permanenza_fuori_range()
    test_periodicita_rotta()
    test_ciclo_di_durata_sbagliata()
    test_discontinuita()
    test_durata_tratta_sbagliata()
    test_layout_stretto()
    test_layout_patologico()
    test_ingombro_asimmetrico()
    test_takt_fuori_banda()
    test_capienza_vasca()
    test_capienza_validazione()
    test_vasca_ripetuta()
    test_fasi_verticali()
    test_zero_verticale_non_regressione()
    test_stazione_condivisa()
    test_input_malformato()
    test_senza_valori_risolti()
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
