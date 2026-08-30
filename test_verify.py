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
from kinematics import travel_time as kinematics_travel_time
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
from model import build_solution as costruisci
from verify import verify_solution

KIN_EMPTY = Kinematics(v_max=1600, a_max=900)
KIN_LOADED = Kinematics(v_max=1000, a_max=400)
KIN_LIFT_EMPTY = Kinematics(v_max=500, a_max=800)
KIN_LIFT_LOADED = Kinematics(v_max=300, a_max=500)

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
    # Corsa verticale e sgocciolamento sono di OGNI vasca e obbligatori. Qui si
    # applicano uguali a tutte: e' una linea legittima, e va scritta invece che
    # sottintesa da un valore generale.
    corsa = kw.pop("lift_height", 0.0)
    scolo = kw.pop("drain_time", 0.0)
    tanks = {
        f"V{i}": Tank(f"V{i}", p, caps[i], lift_height=corsa, drain_time=scolo)
        for i, p in enumerate(positions)
    }
    route = [StationSpec(f"V{i}", spec[0], spec[1]) for i, spec in enumerate(dwells)]
    params = dict(
        tanks=tanks,
        route=route,
        takt_min=50.0,
        takt_max=200.0,
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


def build_solution(
    data: ProblemData,
    T: float,
    local_picks: list[dict],
    extra_periods: dict[int, int] | None = None,
) -> Solution:
    """Comodita' per i test: accetta le fasi di prelievo raggruppate per
    carroponte (com'e' naturale scriverle qui) e delega la costruzione vera a
    model.build_solution, che e' la stessa funzione usata dall'interfaccia.
    Una sola implementazione, cosi' i test non verificano una copia."""
    unite: dict[int, float] = {}
    for lp in local_picks:
        unite.update(lp)
    return costruisci(
        data, T, unite, extra_periods=extra_periods, status="OPTIMAL"
    )


def reference_case():
    """Due carroponti su 4 mosse, vasche ben distanziate, tutto regolare."""
    data = make_data(
        positions=[0, 5000, 10000, 15000, 20000],
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
        f"separazione minima {r.min_separation:.0f}mm >= "
        f"{r.required_separation:.0f}mm richiesti",
    )
    check(r.n_samples > 1000, f"campionamento fitto ({r.n_samples} istanti)")
    check(
        r.sampling_error_bound < 1.0,
        f"errore di campionamento trascurabile ({r.sampling_error_bound:.2e} mm)",
    )


def test_collisione_reale():
    print("\n[2] collisione vera: due carroponti nello stesso punto")
    data, sol = reference_case()
    # sposto la traiettoria del secondo carroponte sopra quella del primo
    rotto = dataclasses.replace(sol)
    rotto.segments_per_hoist = [
        sol.segments_per_hoist[0],
        [
            dataclasses.replace(s, x_start=s.x_start - 10000, x_end=s.x_end - 10000)
            for s in sol.segments_per_hoist[1]
        ],
    ]
    r = verify_solution(data, rotto)
    check(not r.ok, "la soluzione viene respinta")
    check(len(kinds(r, "collision", "error")) == 1, "segnalata una collisione")
    # Dire "c'e' una collisione" non basta a rimediarla: servono i carri e il
    # punto della linea, dentro il messaggio, perche' e' l'unica cosa che
    # l'interfaccia mostra.
    msg = kinds(r, "collision", "error")[0].message
    check(
        "carroponti 1 e 2" in msg and "V0" in msg and "t=" in msg,
        f"il messaggio dice chi, dove e quando: \"{msg[:70]}...\"",
    )
    check(
        r.min_separation < r.required_separation,
        f"separazione minima misurata {r.min_separation:.0f}mm sotto il minimo",
    )


def test_collisione_solo_in_transito():
    print("\n[3] collisione che si vede SOLO campionando dentro il movimento")
    # I due carroponti stanno sempre a >= 1800 mm se si guardano solo gli
    # estremi dei segmenti, ma si incrociano a meta' di uno spostamento.
    data = make_data(
        positions=[0, 5000, 10000, 15000, 20000],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
    )
    T = 100.0
    segs_a = [
        Segment("empty", 0.0, 20.0, 0, 10000, KIN_EMPTY),
        Segment("wait", 20.0, 100.0, 10000, 10000, None),
    ]
    segs_b = [
        Segment("wait", 0.0, 10.0, 12000, 12000, None),
        Segment("empty", 10.0, 30.0, 12000, 2000, KIN_EMPTY),
        Segment("wait", 30.0, 100.0, 2000, 2000, None),
    ]
    # agli estremi dei segmenti la distanza e' sempre >= 2000 mm; a meta' i due si
    # incrociano davvero
    sol = Solution(status="OPTIMAL", T=T, segments_per_hoist=[segs_a, segs_b])
    r = verify_solution(data, sol)
    check(len(kinds(r, "collision", "error")) >= 1, "l'incrocio in transito viene visto")
    check(
        r.min_separation < 500,
        f"separazione minima {r.min_separation:.0f}mm (i due si attraversano)",
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
    segs[0] = dataclasses.replace(segs[0], x_end=segs[0].x_end + 2000)
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
    # 10000 e 11000 distano 1000 mm, meno di hoist_length + safety_distance = 1800:
    # una geometria che il vecchio modello non sapeva rappresentare e che ora
    # e' coperta dal vincolo a fascia
    data = make_data(
        positions=[0, 5000, 10000, 11000, 20000],
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
        f"la collisione reale viene trovata (sep_min={r.min_separation:.0f} mm)",
    )


def test_layout_patologico():
    print("\n[10] geometrie che restano irrappresentabili")
    # zone adiacenti che NON stanno su lati opposti del confine: le posizioni
    # delle vasche non seguono l'ordine del percorso
    data_lati = make_data(
        positions=[0, 10000, 5000, 15000, 20000],
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
        positions=[0, 6000, 12000, 1000, 7000, 13000],
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
        positions=[i * 1000.0 for i in range(5)],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
    )
    check(
        zone_layout_conflicts(data_ok, data_ok.zones) == [],
        "linea ordinata a 1 m di passo: nessun problema di geometria",
    )


def test_ingombro_asimmetrico():
    print("\n[11] ingombro asimmetrico: conta solo la somma dei due lati")
    posizioni = [0, 5000, 10000, 15000, 20000]
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
    valori = [richiesta(600, 600), richiesta(200, 1000), richiesta(1100, 100)]
    check(
        all(abs(v[0] - 1200) < 1e-9 for v in valori),
        "ingombro totale sempre 1200 mm, comunque ripartito",
    )
    check(
        len({round(v[1], 9) for v in valori}) == 1,
        f"distanza richiesta identica nei tre casi: {valori[0][1]:.0f} mm",
    )
    check(
        abs(valori[0][1] - (1200 + 600)) < 1e-9,
        "distanza richiesta = ingombro totale + distanza di sicurezza",
    )

    d = make_data(
        positions=posizioni,
        dwells=dwells,
        zones=zone,
        hoist_extent_pos=0,
        hoist_extent_neg=0,
    )
    check(d.hoist_length == 0.0, "ingombro nullo ammesso (carroponte puntiforme)")
    for pos, neg in ((-100, 500), (500, -100)):
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
    positions = [0, 5000, 10000, 15000, 20000]
    zones = [HoistZone(0, 1), HoistZone(2, 3)]
    T = 100.0

    def caso(cap):
        # finestre di permanenza larghe: qui si vuole isolare la CAPIENZA,
        # non farsi disturbare da violazioni di processo
        data = make_data(
            positions=positions,
            dwells=[(0, 0), (30, 200), (150, 500, cap), (30, 200), (0, 0)],
            zones=zones,
        )
        d0 = data.loaded_leg_seconds(0)
        # +2 periodi sulla mossa 2: il pezzo resta in V2 per piu' takt di
        # seguito, quindi ce ne sono diversi dentro contemporaneamente
        sol = build_solution(
            data, T, [{0: 0.0, 1: d0 + 40.0}, {2: 10.0, 3: 55.0}], extra_periods={2: 2}
        )
        return data, verify_solution(data, sol)

    _, r1 = caso(1)
    n = r1.tank_occupancy.get("V2", 1)
    check(n >= 3, f"in V2 servono {n} posti (permanenza su piu' takt)")
    check(
        len(kinds(r1, "tank_capacity", "error")) == 1 and not r1.ok,
        "con capacity=1 e' un ERRORE",
    )
    _, rn = caso(n)
    check(
        rn.ok and len(kinds(rn, "tank_capacity", "info")) == 1,
        f"con capacity={n} e' solo una nota informativa",
    )
    _, rm = caso(n - 1)
    check(
        len(kinds(rm, "tank_capacity", "error")) == 1,
        f"con capacity={n - 1}, cioe' uno in meno del necessario, e' un ERRORE",
    )

    # l'occupazione di un posto comprende anche le fasi verticali
    data_v = make_data(
        positions=positions,
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=zones,
        lift_height=800,
        kin_lift_empty=KIN_LIFT_EMPTY,
        kin_lift_loaded=KIN_LIFT_LOADED,
        engage_time=2.0,
        disengage_time=1.0,
    )
    # Il posto e' occupato da quando il telaio comincia a calare a quando ha
    # finito di emergere e di sgocciolare. Le corse a VUOTO del gancio non
    # contano: quelle stanno gia' dentro il bagno, e sommarle di nuovo qui
    # sarebbe doppio conteggio.
    # le fasi si prendono per nome: col gancio che trasla basso le corse a
    # vuoto non ci sono, e per indice si prenderebbe quella sbagliata
    durate = {
        f.name: f.duration
        for f in data_v.pick_phases(2) + data_v.release_phases(2)
    }
    atteso = (
        durate["immersione del telaio"]
        + 50.0
        + durate["sollevamento del telaio"]
        + durate["sgocciolamento"]
    )
    check(
        abs(data_v.slot_occupancy_seconds(2, 50.0) - atteso) < 1e-9,
        f"occupazione posto = immersione + bagno + emersione + sgocciolamento "
        f"({atteso:.2f} s)",
    )
    # Col gancio che trasla basso -- lo standard -- il bagno eccede l'intervallo
    # fra i movimenti dei soli tempi morti: le corse a vuoto non le fa nessuno.
    check(
        abs(data_v.bath_extra_seconds(2) - 3.0) < 1e-9
        and "discesa del gancio" not in durate,
        f"col gancio che trasla basso il bagno eccede di soli sgancio+aggancio "
        f"({data_v.bath_extra_seconds(2):.2f} s)",
    )
    # ...e resta cosi' anche sull'impianto che obbliga il gancio a risalire:
    # li' le corse a vuoto ci sono, ma cadono nel RIENTRO fra due mosse, e il
    # rientro sta gia' tutto dentro l'intervallo fra i movimenti.
    alto = dataclasses.replace(data_v, empty_hook_travels_low=False)
    check(
        abs(alto.bath_extra_seconds(2) - 3.0) < 1e-9
        and alto.empty_leg_seconds(1, 2) > data_v.empty_leg_seconds(1, 2),
        f"e le corse a vuoto pesano sul rientro, non sul bagno "
        f"({alto.empty_leg_seconds(1, 2):.2f} s contro "
        f"{data_v.empty_leg_seconds(1, 2):.2f})",
    )


def test_capienza_validazione():
    print("\n[14] validazione della capienza in ProblemData")
    base = dict(
        positions=[0, 5000, 10000],
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


def _linea_vasca_ripetuta(cap_lav: int, dwell=(20, 200)) -> ProblemData:
    """Il pezzo torna DUE volte nella stessa vasca fisica LAV.

    Un carroponte solo: tornare indietro rende le posizioni non monotone lungo
    la rotaia, e con due carroponti il caso si sporcherebbe di collisioni che
    qui non c'entrano nulla. SEC ha posti in abbondanza per lo stesso motivo:
    l'unica capienza sotto esame e' quella di LAV."""
    return ProblemData(
        tanks={
            "CAR": Tank("CAR", 0, lift_height=0, drain_time=0),
            "LAV": Tank("LAV", 5000, capacity=cap_lav, lift_height=0, drain_time=0),
            "SEC": Tank("SEC", 10000, capacity=20, lift_height=0, drain_time=0),
            "SCA": Tank("SCA", 15000, lift_height=0, drain_time=0),
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
        hoist_extent_pos=500,
        hoist_extent_neg=700,
        safety_distance=600,
        zones=[HoistZone(0, 3)],
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
    check(
        not kinds(r, "tank_capacity", "error"),
        "con capacity=1 nessun errore di capienza",
    )

    # (b) permanenze lunghe: i pezzi delle due tappe convivono davvero
    data2 = _linea_vasca_ripetuta(cap_lav=1, dwell=(150, 600))
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
        positions=[0, 5000, 10000, 15000, 20000],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
        lift_height=800,
        kin_lift_empty=KIN_LIFT_EMPTY,
        kin_lift_loaded=KIN_LIFT_LOADED,
        engage_time=2.0,
        disengage_time=1.0,
        drain_time=4.0,
    )
    # i tempi verticali non sono dichiarati: si ricavano dalla corsa e dalle
    # cinematiche di sollevamento (una tratta a vuoto + una a carico)
    t_vuoto = kinematics_travel_time(800, KIN_LIFT_EMPTY)
    t_carico = kinematics_travel_time(800, KIN_LIFT_LOADED)
    # Col gancio che trasla basso -- lo standard -- il gancio scarico non si
    # muove mai in verticale: e' arrivato gia' in fondo e riparte da li'.
    check(
        abs(data.pick_time_at(0) - (2.0 + t_carico + 4.0)) < 1e-9,
        f"presa = aggancio + risalita a carico + sgocciolamento "
        f"({data.pick_time_at(0):.2f} s)",
    )
    check(
        abs(data.release_time_at(1) - (t_carico + 1.0)) < 1e-9,
        f"rilascio = discesa a carico + sgancio ({data.release_time_at(1):.2f} s) "
        f"-- nessuno sgocciolamento e nessuna risalita",
    )
    # Presa e rilascio non cambiano nemmeno sull'impianto in cui il gancio
    # calato non passa fra le vasche: li' le corse a vuoto ci sono, ma le paga
    # il RIENTRO, che e' quando avvengono davvero.
    alto = dataclasses.replace(data, empty_hook_travels_low=False)
    check(
        alto.pick_time_at(0) == data.pick_time_at(0)
        and alto.release_time_at(1) == data.release_time_at(1)
        and abs(
            alto.empty_leg_seconds(1, 2)
            - (data.empty_leg_seconds(1, 2) + 2 * t_vuoto)
        )
        < 1e-9,
        f"senza traslazione bassa le corse a vuoto le paga il rientro "
        f"(+{2 * t_vuoto:.2f} s)",
    )
    check(
        abs((data.pick_time_at(0) - data.release_time_at(0)) - (2.0 + 4.0 - 1.0))
        < 1e-9,
        "presa e rilascio differiscono solo per i tempi morti",
    )
    check(
        abs(
            data.loaded_leg_seconds(0)
            - (
                data.pick_time_at(0)
                + data.horizontal_loaded_seconds(0)
                + data.release_time_at(1)
            )
        )
        < 1e-9,
        "la durata della mossa comprende presa e rilascio",
    )
    check(
        abs(data.empty_leg_seconds(0, 2) - data.empty_leg_seconds(2, 0)) < 1e-9
        and abs(data.empty_leg_seconds(1, 1)) < 1e-9,
        "il rientro a vuoto e' simmetrico, e nullo verso se stessi",
    )

    # corsa piu' lunga -> tempi piu' lunghi, ma solo per quella vasca
    profonda = dataclasses.replace(
        data,
        tanks={
            k: (dataclasses.replace(v, lift_height=1600) if k == "V2" else v)
            for k, v in data.tanks.items()
        },
    )
    check(
        profonda.pick_time_at(2) > profonda.pick_time_at(1)
        and profonda.pick_time_at(1) == data.pick_time_at(1),
        f"corsa per vasca: V2 {profonda.pick_time_at(2):.2f} s contro "
        f"{profonda.pick_time_at(1):.2f} s delle altre",
    )

    # lo sgocciolamento dipende dal bagno: si dichiara per vasca
    lenta = dataclasses.replace(
        data,
        tanks={
            k: (dataclasses.replace(v, drain_time=20.0) if k == "V2" else v)
            for k, v in data.tanks.items()
        },
    )
    check(
        abs((lenta.pick_time_at(2) - data.pick_time_at(2)) - (20.0 - 4.0)) < 1e-9,
        f"sgocciolamento per vasca: V2 sale a {lenta.pick_time_at(2):.2f} s",
    )
    check(
        lenta.release_time_at(2) == data.release_time_at(2),
        "lo sgocciolamento non tocca il rilascio: si scola in uscita, non in entrata",
    )

    T = 130.0
    d0 = data.loaded_leg_seconds(0)
    d2 = data.loaded_leg_seconds(2)
    sol = build_solution(
        data, T, [{0: 0.0, 1: d0 + 40.0}, {2: 10.0, 3: 10.0 + d2 + 35.0}]
    )
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
        positions=[0, 5000, 10000, 15000, 20000],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 1), HoistZone(2, 3)],
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
        positions=[0, 5000, 10000, 15000],
        dwells=[(0, 0), (30, 90), (0, 90), (0, 0)],
        zones=[HoistZone(0, 0), HoistZone(1, 2)],
        lift_height=400,
        kin_lift_empty=KIN_LIFT_EMPTY,
        kin_lift_loaded=KIN_LIFT_LOADED,
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


def test_svincoli():
    """Sull'impianto in cui il gancio calato non passa fra le vasche, il
    carroponte deve portarsi su una posizione di SVINCOLO prima di tirare su
    il gancio scarico -- e ridiscenderlo su un'altra prima di agganciare."""
    print("\n[22] posizioni di svincolo")
    from model import proposta_semplice

    def linea(sv=True):
        d = make_data(
            positions=[0, 5000, 10000, 15000],
            dwells=[(0, 0), (30, 300, 2), (30, 300, 2), (0, 0)],
            zones=[HoistZone(0, 2)],
            lift_height=1500,
            kin_lift_empty=Kinematics(v_max=250, a_max=150),
            kin_lift_loaded=Kinematics(v_max=200, a_max=150),
            engage_time=2.0,
            disengage_time=1.0,
            takt_max=400.0,
            empty_hook_travels_low=False,
        )
        if not sv:
            return d
        tanks = dict(d.tanks)
        for i, nome in enumerate(("V0", "V1", "V2", "V3")):
            t = tanks[nome]
            tanks[nome] = dataclasses.replace(
                t,
                svincolo_pos=t.position + 900 if i < 3 else None,
                svincolo_neg=t.position - 900 if i > 0 else None,
            )
        return dataclasses.replace(d, tanks=tanks)

    senza, con = linea(sv=False), linea(sv=True)
    # Si esce dallo svincolo dalla parte in cui si deve andare: e' il tratto
    # basso piu' corto, e non fa tornare indietro il carroponte.
    check(
        con.svincolo_verso(1, 10000.0) == 5900.0
        and con.svincolo_verso(1, 0.0) == 4100.0,
        f"si sceglie lo svincolo dalla parte del viaggio "
        f"({con.svincolo_verso(1, 10000.0):.0f} andando avanti, "
        f"{con.svincolo_verso(1, 0.0):.0f} tornando indietro)",
    )
    check(
        con.empty_leg_seconds(1, 2) > senza.empty_leg_seconds(1, 2),
        f"il giro dello svincolo allunga il rientro "
        f"({con.empty_leg_seconds(1, 2):.2f} s contro "
        f"{senza.empty_leg_seconds(1, 2):.2f})",
    )
    # ...e non tocca ne' la presa ne' il bagno: quelle sono cose del pezzo
    check(
        con.pick_time_at(1) == senza.pick_time_at(1)
        and con.bath_extra_seconds(1) == senza.bath_extra_seconds(1),
        "e non tocca ne' la presa ne' il tempo in bagno",
    )

    # La traiettoria disegnata deve farcelo vedere: il carroponte si spinge
    # FINO allo svincolo, che sta oltre la vasca. Riassumerlo in un tratto solo
    # nasconderebbe proprio le posizioni in cui puo' incontrare il vicino.
    sol, dati = proposta_semplice(con)
    segs = sorted(sol.segments_per_hoist[0], key=lambda s: s.t_start)
    check(
        any(s.kind == "lift_empty" for s in segs),
        f"la traiettoria contiene le salite e le discese sugli svincoli "
        f"({sum(1 for s in segs if s.kind == 'lift_empty')} tratti)",
    )
    quote = {round(s.x_start, 1) for s in segs} | {round(s.x_end, 1) for s in segs}
    # gli svincoli toccati sono quelli del rientro, e stanno OLTRE le vasche:
    # e' proprio quello che un tratto unico da vasca a vasca nasconderebbe
    svincoli = quote - {con.station_position(i) for i in range(con.n_stations)}
    check(
        svincoli == {900.0, 14100.0},
        f"e il carroponte ci arriva davvero, oltre le vasche ({sorted(svincoli)})",
    )
    r = verify_solution(con, sol)
    check(
        r.ok,
        "il ciclogramma che ne esce supera la verifica"
        + ("" if r.ok else f": {r.errors[0].message[:60]}"),
    )

    # La posizione dello svincolo e' vincolata: deve stare fra la sua vasca e
    # quella accanto, altrimenti il gancio basso dovrebbe scavalcarne un'altra.
    for nome, sp, sn, atteso in (
        ("troppo avanti", 11000.0, None, "positivo"),
        ("dalla parte sbagliata", None, 6000.0, "negativo"),
    ):
        tanks = dict(con.tanks)
        t = tanks["V1"]
        tanks["V1"] = dataclasses.replace(t, svincolo_pos=sp, svincolo_neg=sn)
        try:
            dataclasses.replace(con, tanks=tanks)
            check(False, f"svincolo {nome}: respinto")
        except ValueError as e:
            check(
                atteso in str(e) and "scavalcare" in str(e),
                f'svincolo {nome}: respinto col motivo ("{str(e)[:60]}...")',
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
    test_svincoli()
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
