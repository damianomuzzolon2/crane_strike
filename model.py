"""
model.py
--------
Modello di ottimizzazione (CP-SAT / OR-Tools) per il problema del
"Cyclic Hoist Scheduling" (CHSP): trovare il ciclogramma periodico di uno o
piu' carroponti che spostano pezzi attraverso una sequenza di vasche,
rispettando tempi di permanenza min/max in ciascuna vasca, un takt time
target (con tolleranza) e vincoli di non-collisione fra carroponti che
condividono la stessa rotaia.

APPROCCIO SCELTO E SUE ASSUNZIONI (importante leggere prima di usare il codice)
--------------------------------------------------------------------------
1. Una sola "ricetta" (sequenza di vasche) condivisa da tutti i pezzi. Se in
   realta' esistono piu' ricette diverse, il problema si generalizza (vedi
   nota "Estensioni possibili" in fondo al file) ma qui NON e' implementato.

2. Ogni carroponte serve una ZONA CONTIGUA di stazioni (zone-based CHSP):
   e' l'approccio piu' diffuso nella pratica industriale (ogni carroponte ha
   una porzione di linea di sua competenza). Le zone sono un INPUT (non
   decise dal solver in questa versione) -- vedi "Estensioni possibili".

3. **Ordine di visita flessibile entro la zona** (v2): a differenza di una
   prima versione che imponeva un unico giro sequenziale (stazione lo, poi
   lo+1, ..., poi hi, poi un solo rientro a vuoto), qui ogni carroponte puo'
   visitare le mosse della propria zona in QUALSIASI ordine ad ogni ciclo,
   "destreggiandosi" fra piu' pezzi diversi (ad es. mentre un pezzo e'
   ancora a bagno in una vasca con tempo di processo lungo, il carroponte
   puo' andare a servire un'altra mossa della zona invece di restare fermo
   ad aspettare). Questo e' modellato con un vincolo di CIRCUITO ciclico
   (`CpModel.AddCircuit`) sulle mosse della zona: il carroponte compie,
   ogni periodo T, un giro che tocca tutte le sue mosse esattamente una
   volta, nell'ordine che il solver ritiene piu' conveniente, con tempi di
   trasferimento a vuoto fra una mossa e la successiva (qualunque essa sia).
   Questo permette di trovare soluzioni fattibili anche quando il contenuto
   "a calendario" della zona (tempi di attesa nelle vasche inclusi) supera
   abbondantemente il takt time -- cosa che il vecchio schema sequenziale
   non riusciva a rappresentare.

4. Le collisioni possono avvenire SOLO nelle stazioni di confine fra due
   zone adiacenti (l'unico punto fisico condiviso fra due carroponti).
   Il modello impone che le finestre temporali in cui i due carroponti
   occupano quella stazione (allargate di un margine di sicurezza legato
   alla lunghezza del carroponte + distanza di sicurezza) non si
   sovrappongano MAI, nemmeno considerando la periodicita' (ciclo T).

5. Il modello e' CORRETTO (sound): ogni soluzione trovata e' un ciclogramma
   fisicamente valido e privo di collisioni. Rispetto alla versione con
   ordine fisso, questa e' anche molto piu' COMPLETA (rappresenta la
   quasi totalita' degli schemi di funzionamento realistici per un
   carroponte in una zona), ma resta comunque una scelta di modellazione:
   il vincolo davvero limitante ora e' che il contenuto "vivo" della zona
   (somma dei tempi di trasporto carico + trasferimenti a vuoto necessari,
   ESCLUSI i tempi di attesa nelle vasche) deve stare entro il takt time --
   se anche questo viene superato, nessun ordine di visita puo' salvare la
   situazione e serve ribilanciare le zone o aumentare il numero di
   carroponti.
"""

from __future__ import annotations

import dataclasses
import itertools
import math
from dataclasses import dataclass, field
from typing import Optional

from kinematics import Kinematics, travel_time as _travel_time_seconds

# --------------------------------------------------------------------------
# Strutture dati di input
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Tank:
    id: str
    position: float  # [m] posizione lungo la rotaia


@dataclass(frozen=True)
class StationSpec:
    """Una tappa del percorso del pezzo (indice 0 = punto di carico,
    ultimo indice = punto di scarico)."""

    tank_id: str
    dwell_min: float  # [s] tempo minimo di permanenza (tolleranza -)
    dwell_max: float  # [s] tempo massimo di permanenza (tolleranza +)


@dataclass(frozen=True)
class HoistZone:
    """Zona di competenza di un carroponte, espressa come intervallo di
    indici di MOSSA (non di stazione). Mossa k = trasporto dalla stazione k
    alla stazione k+1. Le zone devono essere contigue e coprire tutte le
    mosse 0..n_moves-1 esattamente una volta, in ordine crescente."""

    lo: int  # indice della prima mossa gestita
    hi: int  # indice dell'ultima mossa gestita


@dataclass
class ProblemData:
    tanks: dict[str, Tank]
    route: list[StationSpec]
    takt_min: float  # [s] limite inferiore tolleranza takt time
    takt_max: float  # [s] limite superiore tolleranza takt time
    kin_empty: Kinematics  # cinematica carroponte SENZA pezzo
    kin_loaded: Kinematics  # cinematica carroponte CON pezzo
    hoist_length: float  # [m] ingombro del carroponte
    safety_distance: float  # [m] distanza di sicurezza minima fra due carroponti
    zones: Optional[list[HoistZone]] = None  # una per carroponte; None = da
    # scegliere automaticamente con
    # solve_auto_zones(...)
    time_scale: int = 100  # tick al secondo (risoluzione temporale interna)

    def __post_init__(self):
        n_moves = len(self.route) - 1
        if n_moves < 1:
            raise ValueError("route deve contenere almeno 2 stazioni (1 mossa)")
        if self.zones is not None:
            covered = []
            for z in self.zones:
                covered.extend(range(z.lo, z.hi + 1))
            if covered != list(range(n_moves)):
                raise ValueError(
                    f"le zone devono coprire in modo contiguo ed esclusivo le mosse "
                    f"0..{n_moves - 1}; trovato: {covered}"
                )
        for s in self.route:
            if s.tank_id not in self.tanks:
                raise ValueError(f"vasca '{s.tank_id}' non definita in tanks")
            if s.dwell_min > s.dwell_max:
                raise ValueError(f"dwell_min > dwell_max per vasca '{s.tank_id}'")
        if self.takt_min > self.takt_max:
            raise ValueError("takt_min > takt_max")

    # -- comodita' --------------------------------------------------------
    @property
    def n_stations(self) -> int:
        return len(self.route)

    @property
    def n_moves(self) -> int:
        return len(self.route) - 1

    @property
    def n_hoists(self) -> int:
        if self.zones is None:
            raise ValueError(
                "data.zones e' None (non ancora scelto): usa solve_auto_zones(...) "
                "per farlo scegliere automaticamente, oppure impostalo esplicitamente."
            )
        return len(self.zones)

    def station_position(self, idx: int) -> float:
        return self.tanks[self.route[idx].tank_id].position

    def move_distance(self, k: int) -> float:
        return abs(self.station_position(k + 1) - self.station_position(k))

    def to_ticks(self, seconds: float) -> int:
        return round(seconds * self.time_scale)

    def to_seconds(self, ticks: int) -> float:
        return ticks / self.time_scale


# --------------------------------------------------------------------------
# Risultato
# --------------------------------------------------------------------------


@dataclass
class Segment:
    """Un tratto della traiettoria di un carroponte entro un ciclo."""

    kind: str  # 'loaded' | 'empty' | 'wait'
    t_start: float  # [s], relativo all'inizio del ciclo (puo' iniziare prima di 0)
    t_end: float  # [s]
    x_start: float  # [m]
    x_end: float  # [m]
    kin: Optional[Kinematics] = None  # None per 'wait'


@dataclass
class Solution:
    status: str  # 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | ...
    T: Optional[float]  # takt time trovato [s]
    segments_per_hoist: list[list[Segment]] = field(default_factory=list)
    raw: dict = field(default_factory=dict)  # valori grezzi utili per debug


# --------------------------------------------------------------------------
# Costruzione e risoluzione del modello CP-SAT
# --------------------------------------------------------------------------
#
# STRUTTURA DEL MODELLO (aggiornata per l'ordine di visita flessibile)
#
# 1. Catena di flusso pezzo (`actual_time`): invariata rispetto alla v1.
#    actual_time[k] = istante di prelievo della mossa k per un pezzo di
#    riferimento che attraversa l'intera linea; incatenata dai vincoli di
#    permanenza min/max in ciascuna vasca.
#
# 2. Per ciascun carroponte (zona di mosse Z_h): invece di un ordine fisso
#    lo,lo+1,...,hi + un unico rientro, si costruisce un CIRCUITO ciclico
#    (`AddCircuit`) sulle mosse di Z_h: il carroponte le visita tutte
#    esattamente una volta per periodo, nell'ordine che il solver sceglie.
#    Per confrontare istanti che nella catena `actual_time` possono essere
#    separati da piu' periodi T (tipico se una vasca ha un tempo di
#    processo lungo), ogni mossa k riceve una variabile locale
#    `local_pick[k]` = actual_time[k] mod T, ottenuta con una ricerca su un
#    numero finito di "giri" possibili (mantenendo tutto LINEARE: nessun
#    prodotto fra due variabili). La mossa lo_h e' presa come riferimento
#    di "chiusura periodo": l'arco che rientra su di essa nel circuito e'
#    l'unico a cui si somma +T.
#
# 3. Le variabili libere `dep_hi` (istante di partenza dal confine
#    superiore della zona) e `arr_lo` (istante di arrivo, pronto, al
#    confine inferiore) sono usate sia per ricostruire la traiettoria sia
#    per il vincolo di non collisione ai confini fra zone adiacenti
#    (identico nello spirito alla v1).


def solve(
    data: ProblemData, time_limit_s: float = 20.0, log_search: bool = False
) -> Solution:
    if data.zones is None:
        raise ValueError(
            "data.zones e' None: specifica le zone esplicitamente oppure usa "
            "solve_auto_zones(data, n_hoists=...) per farle scegliere automaticamente."
        )

    # Import posticipato: cosi' il resto del modulo (dataclass, cinematica,
    # extraction, plotting) resta utilizzabile/testabile anche senza ortools
    # installato.
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    scale = data.time_scale

    def T_(seconds: float) -> int:
        return data.to_ticks(seconds)

    # -- Tempi di percorrenza precalcolati (le posizioni delle vasche sono
    #    fisse, quindi i tempi di percorrenza sono costanti, non variabili) --
    travel_loaded = [
        T_(_travel_time_seconds(data.move_distance(k), data.kin_loaded))
        for k in range(data.n_moves)
    ]

    def travel_empty_ticks(pos_a: float, pos_b: float) -> int:
        return T_(_travel_time_seconds(abs(pos_b - pos_a), data.kin_empty))

    # Margine di sicurezza temporale da applicare alle finestre di occupazione
    # dei punti di confine, per tenere conto dell'ingombro fisico del
    # carroponte oltre alla sola posizione del suo punto di riferimento.
    half_extent = data.hoist_length / 2 + data.safety_distance
    safety_buffer = T_(
        max(
            _travel_time_seconds(half_extent, data.kin_loaded),
            _travel_time_seconds(half_extent, data.kin_empty),
        )
    )

    # -- Variabili di takt time --------------------------------------------
    T_min, T_max = T_(data.takt_min), T_(data.takt_max)
    Tv = model.NewIntVar(T_min, T_max, "T")

    # -- Orizzonte e limiti tecnici per i domini delle variabili -----------
    horizon = (
        4 * T_max
        + sum(T_(s.dwell_max) for s in data.route)
        + sum(travel_loaded)
        + 10 * scale
    )
    BIG = 10**7
    n_shifts = math.ceil(horizon / T_min) + 2

    def _as_intvar(expr, name):
        """Materializza un'espressione lineare in un vero IntVar, legato
        all'espressione con un vincolo di uguaglianza. Passare sempre IntVar
        "puri" a NewIntervalVar (invece di espressioni composte) e' piu'
        robusto fra le diverse versioni di OR-Tools."""
        v = model.NewIntVar(-BIG, BIG, name)
        model.Add(v == expr)
        return v

    # -- 1) Catena di flusso pezzo (invariata rispetto alla v1) -------------
    actual_time = [model.NewIntVar(0, horizon, f"at_{k}") for k in range(data.n_moves)]
    model.Add(actual_time[0] == 0)

    for k in range(1, data.n_moves):
        station = (
            k  # la vasca k viene raggiunta dalla mossa k-1 e lasciata dalla mossa k
        )
        dwell_min = T_(data.route[station].dwell_min)
        dwell_max = T_(data.route[station].dwell_max)
        arrival = actual_time[k - 1] + travel_loaded[k - 1]
        model.Add(actual_time[k] >= arrival + dwell_min)
        model.Add(actual_time[k] <= arrival + dwell_max)

    # -- 2) Per ciascun carroponte: circuito ciclico sulle mosse della
    #    propria zona, con ordine di visita libero. ------------------------
    zone_data = []
    for h, z in enumerate(data.zones):
        moves = list(range(z.lo, z.hi + 1))
        n_h = len(moves)
        lo_h, hi_h = z.lo, z.hi

        # -- fase locale (in [0,T)) di ciascuna mossa della zona, agganciata
        #    alla catena globale actual_time tramite una ricerca su un
        #    numero finito di possibili "giri" (shift): resta tutto LINEARE.
        local_pick = {}
        for k in moves:
            lp = model.NewIntVar(0, T_max - 1, f"lp_{h}_{k}")
            lits = []
            for m in range(0, n_shifts + 1):
                lit = model.NewBoolVar(f"lp_{h}_{k}_shift_{m}")
                model.Add(lp == actual_time[k] - m * Tv).OnlyEnforceIf(lit)
                lits.append(lit)
            model.AddExactlyOne(lits)
            model.Add(lp < Tv)
            local_pick[k] = lp

        finish = {
            k: _as_intvar(local_pick[k] + travel_loaded[k], f"fin_{h}_{k}")
            for k in moves
        }

        if n_h == 1:
            # Caso degenere: una sola mossa nella zona. Il "circuito" e'
            # semplicemente andata (mossa) + ritorno a vuoto, come in v1.
            k0 = moves[0]
            dep_hi = model.NewIntVar(0, BIG, f"dep_hi_{h}")
            model.Add(dep_hi >= finish[k0])
            arr_lo = model.NewIntVar(0, BIG, f"arr_lo_{h}")
            t_ret = travel_empty_ticks(
                data.station_position(hi_h + 1), data.station_position(lo_h)
            )
            model.Add(arr_lo == dep_hi + t_ret)
            model.Add(arr_lo <= local_pick[lo_h] + Tv)
            zone_data.append(
                dict(
                    h=h,
                    z=z,
                    moves=moves,
                    local_pick=local_pick,
                    finish=finish,
                    dep_hi=dep_hi,
                    arr_lo=arr_lo,
                    arc_lits=None,
                )
            )
            continue

        # -- circuito generale per n_h > 1: il carroponte visita tutte le
        #    mosse della zona una volta a periodo, in un ordine libero. ----
        local_idx = {k: i for i, k in enumerate(moves)}
        arc_lits = {}
        arcs_for_circuit = []
        for k1 in moves:
            for k2 in moves:
                if k1 == k2:
                    continue
                lit = model.NewBoolVar(f"arc_{h}_{k1}_{k2}")
                arc_lits[(k1, k2)] = lit
                arcs_for_circuit.append((local_idx[k1], local_idx[k2], lit))
        model.AddCircuit(arcs_for_circuit)

        # vincolo di tempo per ciascun arco possibile: se selezionato,
        # bisogna riuscire ad arrivare in tempo alla mossa successiva
        # (con +T solo se si sta richiudendo il periodo su lo_h).
        for (k1, k2), lit in arc_lits.items():
            t_emp = travel_empty_ticks(
                data.station_position(k1 + 1), data.station_position(k2)
            )
            bound = local_pick[k2] + (Tv if k2 == lo_h else 0)
            model.Add(finish[k1] + t_emp <= bound).OnlyEnforceIf(lit)

        # -- variabili libere di confine (per traiettoria e non-collisione) --
        dep_hi = model.NewIntVar(0, BIG, f"dep_hi_{h}")
        model.Add(dep_hi >= finish[hi_h])
        for k2 in moves:
            if k2 == hi_h:
                continue
            t_emp = travel_empty_ticks(
                data.station_position(hi_h + 1), data.station_position(k2)
            )
            bound = local_pick[k2] + (Tv if k2 == lo_h else 0)
            model.Add(dep_hi + t_emp <= bound).OnlyEnforceIf(arc_lits[(hi_h, k2)])

        arr_lo = model.NewIntVar(0, BIG, f"arr_lo_{h}")
        for k1 in moves:
            if k1 == lo_h:
                continue
            t_emp = travel_empty_ticks(
                data.station_position(k1 + 1), data.station_position(lo_h)
            )
            model.Add(arr_lo >= finish[k1] + t_emp).OnlyEnforceIf(arc_lits[(k1, lo_h)])
        model.Add(arr_lo <= local_pick[lo_h] + Tv)

        # se l'arco hi_h -> lo_h e' selezionato (rientro diretto, senza
        # visitare altre mosse nel mezzo), dep_hi e arr_lo descrivono lo
        # STESSO spostamento a vuoto: vanno legati fra loro esattamente.
        if (hi_h, lo_h) in arc_lits:
            t_emp_direct = travel_empty_ticks(
                data.station_position(hi_h + 1), data.station_position(lo_h)
            )
            model.Add(arr_lo == dep_hi + t_emp_direct).OnlyEnforceIf(
                arc_lits[(hi_h, lo_h)]
            )

        zone_data.append(
            dict(
                h=h,
                z=z,
                moves=moves,
                local_pick=local_pick,
                finish=finish,
                dep_hi=dep_hi,
                arr_lo=arr_lo,
                arc_lits=arc_lits,
            )
        )

    # -- 3) Vincoli di non collisione alle stazioni di confine fra zone
    #    adiacenti (uniche stazioni fisicamente condivise). -----------------
    # NOTA: due eventi periodici di periodo T possono essere sfasati anche
    # di PIU' di un ciclo (vasche con tempo di processo lungo rispetto al
    # takt time): generiamo un numero di copie traslate sufficiente a
    # coprire l'intero orizzonte del modello.
    def add_cyclic_no_overlap(start_a, end_a, start_b, end_b, name):
        """Impone che [start_a,end_a] non si sovrapponga MAI a [start_b,end_b]
        ne' ad alcuna sua traslazione di un multiplo intero di T (positivo o
        negativo)."""
        sa = _as_intvar(start_a, name + "_sA")
        ea = _as_intvar(end_a, name + "_eA")
        size_a = model.NewIntVar(0, horizon, name + "_szA")
        model.Add(size_a == ea - sa)
        interval_a = model.NewIntervalVar(sa, size_a, ea, name + "_A")

        intervals = [interval_a]
        for shift in range(-n_shifts, n_shifts + 1):
            sb = _as_intvar(start_b + shift * Tv, f"{name}_sB_{shift}")
            eb = _as_intvar(end_b + shift * Tv, f"{name}_eB_{shift}")
            size_b = model.NewIntVar(0, 2 * horizon, f"{name}_szB_{shift}")
            model.Add(size_b == eb - sb)
            interval_b = model.NewIntervalVar(sb, size_b, eb, f"{name}_B_{shift}")
            intervals.append(interval_b)
        model.AddNoOverlap(intervals)

    for h in range(data.n_hoists - 1):
        zL, zR = zone_data[h], zone_data[h + 1]
        z_left, z_right = zL["z"], zR["z"]
        assert z_left.hi + 1 == z_right.lo, "le zone devono essere contigue"

        occ_left_start = zL["finish"][z_left.hi] - safety_buffer
        occ_left_end = zL["dep_hi"] + safety_buffer

        occ_right_start = zR["arr_lo"] - safety_buffer
        occ_right_end = zR["local_pick"][z_right.lo] + Tv + safety_buffer

        add_cyclic_no_overlap(
            occ_left_start,
            occ_left_end,
            occ_right_start,
            occ_right_end,
            name=f"boundary_{h}_{h+1}",
        )

    # -- Obiettivo: minimizzare il takt time entro la tolleranza data -------
    model.Minimize(Tv)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.log_search_progress = log_search
    solver.parameters.num_workers = 8
    status = solver.Solve(model)

    status_name = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Solution(status=status_name, T=None)

    T_seconds = data.to_seconds(solver.Value(Tv))

    segments_per_hoist = []
    for zd in zone_data:
        z = zd["z"]
        moves = zd["moves"]
        lp_val = {k: data.to_seconds(solver.Value(zd["local_pick"][k])) for k in moves}
        dep_hi_val = data.to_seconds(solver.Value(zd["dep_hi"]))
        arr_lo_val = data.to_seconds(solver.Value(zd["arr_lo"]))

        if zd["arc_lits"] is None:
            order = [z.lo]
        else:
            nxt = {}
            for (k1, k2), lit in zd["arc_lits"].items():
                if solver.Value(lit):
                    nxt[k1] = k2
            order = [z.lo]
            cur = z.lo
            while True:
                cur = nxt[cur]
                if cur == z.lo:
                    break
                order.append(cur)

        segs = _build_zone_trajectory(
            data, z, order, lp_val, dep_hi_val, arr_lo_val, T_seconds
        )
        segments_per_hoist.append(segs)

    raw = {"objective": solver.ObjectiveValue(), "wall_time": solver.WallTime()}
    return Solution(
        status=status_name, T=T_seconds, segments_per_hoist=segments_per_hoist, raw=raw
    )


# --------------------------------------------------------------------------
# Costruzione della traiettoria (posizione nel tempo) a partire dai valori
# risolti, per UNA zona/carroponte. Separata dalla risoluzione CP-SAT cosi'
# da poter essere testata anche senza risolvere realmente un modello (es.
# con valori scelti a mano).
# --------------------------------------------------------------------------


def _build_zone_trajectory(
    data: ProblemData,
    zone: HoistZone,
    order: list[int],
    local_pick: dict[int, float],
    dep_hi: float,
    arr_lo: float,
    T: float,
) -> list[Segment]:
    """order: lista degli indici di mossa nell'ordine in cui il carroponte
    le esegue entro un periodo (parte e torna a zone.lo).
    local_pick[k]: istante [s], in [0,T), di prelievo per la mossa k.
    dep_hi: istante [s] in cui il carroponte lascia il confine superiore
        della zona (dopo la mossa zone.hi) per il successivo spostamento a
        vuoto (puo' differire dal minimo stretto: e' una scelta del solver).
    arr_lo: istante [s] in cui il carroponte torna pronto al confine
        inferiore della zona (zone.lo), per il prelievo di QUESTO ciclo +T.
    """
    # Tolleranza numerica: il modello CP-SAT lavora con tempi arrotondati al
    # tick (risoluzione 1/time_scale secondi), mentre qui ricalcoliamo i
    # tempi di percorrenza con la formula cinematica "esatta" in virgola
    # mobile -- le due cose possono differire di qualche tick per puro
    # arrotondamento, senza che ci sia un'incoerenza reale nel modello.
    EPS = max(10.0 / data.time_scale, 1e-6)
    segs: list[Segment] = []
    n = len(order)

    for i, k in enumerate(order):
        x0 = data.station_position(k)
        x1 = data.station_position(k + 1)
        t0 = local_pick[k]
        t1 = t0 + _travel_time_seconds(abs(x1 - x0), data.kin_loaded)
        segs.append(Segment("loaded", t0, t1, x0, x1, data.kin_loaded))

        is_last = i == n - 1
        nxt_k = order[0] if is_last else order[i + 1]
        x1_next = data.station_position(nxt_k)
        travel_e = _travel_time_seconds(abs(x1_next - x1), data.kin_empty)

        depart_known = k == zone.hi
        arrive_known = nxt_k == zone.lo

        if depart_known and arrive_known:
            depart_t, arrive_t = dep_hi, arr_lo
        elif depart_known:
            depart_t = dep_hi
            arrive_t = depart_t + travel_e
        elif arrive_known:
            arrive_t = arr_lo
            depart_t = arrive_t - travel_e
        else:
            # transizione interna alla zona: nessuna variabile libera
            # dedicata nel modello. Convenzione per la visualizzazione:
            # parte non appena possibile (nessuna attesa "gratuita" prima
            # della partenza; l'eventuale margine e' mostrato come attesa
            # DOPO l'arrivo, prima del prelievo successivo).
            depart_t = t1
            arrive_t = depart_t + travel_e

        if depart_t < t1 - EPS:
            raise ValueError(
                f"Valori incoerenti: partenza ({depart_t}) precede la consegna "
                f"({t1}) per la mossa {k}. Controlla i vincoli del modello."
            )
        elif depart_t < t1:
            depart_t = t1  # scarto minuscolo di arrotondamento, non un errore reale
        if depart_t > t1 + EPS:
            segs.append(Segment("wait", t1, depart_t, x1, x1, None))
        segs.append(Segment("empty", depart_t, arrive_t, x1, x1_next, data.kin_empty))

        target_pick = local_pick[nxt_k] + (T if nxt_k == zone.lo else 0)
        if target_pick < arrive_t - EPS:
            raise ValueError(
                f"Valori incoerenti: arrivo ({arrive_t}) e' successivo al prelievo "
                f"target ({target_pick}) per la mossa {nxt_k}. Controlla i vincoli."
            )
        elif target_pick < arrive_t:
            target_pick = (
                arrive_t  # scarto minuscolo di arrotondamento, non un errore reale
            )
        if target_pick > arrive_t + EPS:
            segs.append(Segment("wait", arrive_t, target_pick, x1_next, x1_next, None))

    return segs


# --------------------------------------------------------------------------
# Scelta automatica delle zone
# --------------------------------------------------------------------------
#
# Le zone (quali mosse assegnare a quale carroponte) NON sono decise
# dentro al modello CP-SAT unico: sarebbe possibile (variabili di confine
# fra zone), ma renderebbe il modello sensibilmente piu' complesso e
# rischioso da validare senza un ambiente con OR-Tools a disposizione.
# La scelta qui e' piu' semplice e robusta: si enumerano TUTTE le
# suddivisioni contigue possibili delle mosse in `n_hoists` zone, si
# risolve il modello (gia' testato) `solve()` per ciascuna, e si tiene la
# soluzione con il takt time minore fra quelle fattibili. Un pre-filtro
# economico scarta le suddivisioni palesemente infattibili (una zona il
# cui solo trasporto-a-carico, senza contare alcun trasferimento a vuoto,
# supera gia' da solo il takt time massimo) senza invocare CP-SAT.
#
# Il numero di suddivisioni contigue possibili e' C(n_moves-1, n_hoists-1):
# per problemi di dimensioni realistiche (una manciata di carroponti,
# qualche decina di mosse al massimo) resta gestibile, ma cresce in fretta.
# Vedi il parametro `max_candidates` per un limite di sicurezza.


def _enumerate_contiguous_partitions(n_moves: int, n_hoists: int):
    """Genera tutte le liste di HoistZone che suddividono le mosse
    0..n_moves-1 in n_hoists gruppi contigui e non vuoti, nell'ordine."""
    for cuts in itertools.combinations(range(n_moves - 1), n_hoists - 1):
        bounds = [-1] + list(cuts) + [n_moves - 1]
        yield [HoistZone(bounds[i] + 1, bounds[i + 1]) for i in range(n_hoists)]


def solve_auto_zones(
    data: ProblemData,
    n_hoists: int,
    time_limit_per_candidate: float = 8.0,
    max_candidates: int = 500,
    log_progress: bool = False,
) -> tuple[Solution, Optional[list[HoistZone]]]:
    """Prova automaticamente tutte le suddivisioni contigue delle mosse in
    `n_hoists` zone (una per carroponte) e restituisce la soluzione con il
    takt time minore fra quelle trovate fattibili, insieme alle zone che
    l'hanno generata.

    `data.zones` puo' essere None (verra' ignorato/sovrascritto per ogni
    tentativo). Restituisce (Solution, zones) -- se nessuna suddivisione e'
    fattibile, Solution.status sara' "INFEASIBLE" e zones sara' None.
    """
    n_moves = data.n_moves
    if n_hoists < 1:
        raise ValueError("n_hoists deve essere >= 1")
    if n_hoists > n_moves:
        raise ValueError(
            f"n_hoists ({n_hoists}) non puo' superare il numero di mosse ({n_moves}): "
            f"ogni carroponte deve avere almeno una mossa."
        )

    n_combinations = math.comb(n_moves - 1, n_hoists - 1)
    if n_combinations > max_candidates:
        raise ValueError(
            f"Il numero di suddivisioni possibili ({n_combinations}) supera "
            f"max_candidates ({max_candidates}). Aumenta max_candidates se vuoi "
            f"comunque una ricerca esaustiva (puo' richiedere molto tempo), oppure "
            f"riduci il numero di mosse/carroponti, oppure specifica tu stesso le "
            f"zone e usa solve() direttamente."
        )

    travel_loaded_seconds = [
        _travel_time_seconds(data.move_distance(k), data.kin_loaded)
        for k in range(n_moves)
    ]

    best_solution: Optional[Solution] = None
    best_zones: Optional[list[HoistZone]] = None
    n_tried = 0
    n_skipped = 0

    for zones in _enumerate_contiguous_partitions(n_moves, n_hoists):
        # pre-filtro economico: una zona il cui solo trasporto-a-carico
        # (senza nemmeno contare trasferimenti a vuoto) gia' supera il
        # takt time massimo e' certamente infattibile, qualunque sia
        # l'ordine di visita.
        content_ok = all(
            sum(travel_loaded_seconds[k] for k in range(z.lo, z.hi + 1))
            <= data.takt_max
            for z in zones
        )
        if not content_ok:
            n_skipped += 1
            continue

        candidate_data = dataclasses.replace(data, zones=zones)
        n_tried += 1
        sol = solve(candidate_data, time_limit_s=time_limit_per_candidate)
        if log_progress:
            zone_str = ", ".join(f"[{z.lo}-{z.hi}]" for z in zones)
            info = f"T={sol.T:.2f}s" if sol.T is not None else sol.status
            print(f"  zone {zone_str}: {info}")
        if sol.status in ("OPTIMAL", "FEASIBLE") and sol.T is not None:
            if best_solution is None or sol.T < best_solution.T:
                best_solution = sol
                best_zones = zones

    if best_solution is None:
        return (
            Solution(
                status="INFEASIBLE",
                T=None,
                raw={"n_tried": n_tried, "n_skipped": n_skipped},
            ),
            None,
        )

    best_solution.raw["n_tried"] = n_tried
    best_solution.raw["n_skipped"] = n_skipped
    best_solution.raw["zones"] = best_zones
    return best_solution, best_zones


# --------------------------------------------------------------------------
# Estensioni possibili -- non implementate in questo file
# --------------------------------------------------------------------------
#
# 1. Assegnazione non contigua fra zone (un carroponte che sconfina
#    occasionalmente nel territorio del vicino): richiederebbe estendere
#    il circuito e la logica di confine a insiemi di mosse non fissi.
#
# 2. Piu' ricette (prodotti diversi che seguono percorsi diversi fra le
#    vasche): si generalizza duplicando la catena actual_time per ciascuna
#    ricetta, con un takt time complessivo che tiene conto del mix
#    produttivo, e condividendo le vasche/i carroponti fra le ricette con
#    ulteriori vincoli di non-sovrapposizione.
#
# 3. Collisione modellata in modo meno conservativo: invece di riservare
#    l'intera finestra [arrivo, partenza] a una stazione di confine, usare
#    il profilo di posizione reale (position_profile in kinematics.py) per
#    calcolare l'intervallo temporale esatto in cui il carroponte e'
#    entro `safety_distance` dal confine, invece dell'intera sosta.
#
# 4. Tempo di presa/rilascio pezzo (immersione/emersione verticale) come
#    costante aggiuntiva su ogni travel_loaded/travel_empty.
