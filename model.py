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
   decise dal solver in questa v1) -- vedi "Estensioni possibili".
   Poiche' le zone sono contigue, il pickup di una mossa e' sempre nello
   stesso punto del drop-off della mossa precedente della stessa zona:
   quindi ENTRO la zona non serve mai un transito a vuoto, tranne nel
   "rientro ciclico" a fine zona (vedi punto 3).

3. Ogni carroponte, dopo aver consegnato il pezzo alla fine della propria
   zona, deve rientrare A VUOTO all'inizio della propria zona per essere
   pronto al ciclo successivo (T secondi dopo). Questo rientro e' l'unico
   spostamento a vuoto modellato esplicitamente.

4. Le collisioni possono avvenire SOLO nelle stazioni di confine fra due
   zone adiacenti (l'unico punto fisico condiviso fra due carroponti).
   Il modello impone che le finestre temporali in cui i due carroponti
   occupano quella stazione (allargate di un margine di sicurezza legato
   alla lunghezza del carroponte + distanza di sicurezza) non si
   sovrappongano MAI, nemmeno considerando la periodicita' (ciclo T).

5. Il modello e' CORRETTO (sound): ogni soluzione trovata e' un ciclogramma
   fisicamente valido e privo di collisioni. NON e' pero' COMPLETO: se un
   carroponte dovesse "destreggiarsi" fra piu' pezzi diversi all'interno
   della propria zona in un ordine non strettamente sequenziale (necessario
   solo se il contenuto totale della zona, cioe' somma di attese e
   spostamenti, supera il takt time), questo schema non lo rappresenta e il
   solver puo' restituire INFEASIBLE anche se esisterebbe in teoria un
   ciclogramma piu' sofisticato. In quel caso conviene ribilanciare le zone
   o aumentare il numero di carroponti.
"""

from __future__ import annotations

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
    zones: list[HoistZone]  # una per carroponte, in ordine crescente di posizione
    time_scale: int = 100  # tick al secondo (risoluzione temporale interna)

    def __post_init__(self):
        n_moves = len(self.route) - 1
        if n_moves < 1:
            raise ValueError("route deve contenere almeno 2 stazioni (1 mossa)")
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


def solve(
    data: ProblemData, time_limit_s: float = 15.0, log_search: bool = False
) -> Solution:
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

    # -- Orizzonte per i domini delle variabili (limite tecnico, non fisico) --
    horizon = (
        4 * T_max
        + sum(T_(s.dwell_max) for s in data.route)
        + sum(travel_loaded)
        + 10 * scale
    )

    # -- Variabili "actual_time[k]" = istante di inizio della mossa k
    #    (istante di prelievo del pezzo dalla stazione k), per un pezzo di
    #    riferimento che attraversa l'intera linea. Non sono vincolate a
    #    stare dentro [0,T): rappresentano un tempo assoluto di riferimento;
    #    la periodicita' entra in gioco solo nei vincoli di "rientro" e di
    #    non-collisione (vedi sotto). --------------------------------------
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

    # -- Per ogni zona (= carroponte): variabile "depart" (istante in cui
    #    lascia la stazione di confine superiore per rientrare a vuoto
    #    all'inizio della propria zona) e vincolo di rientro entro T. -------
    depart = []
    arrive_back = []
    for h, z in enumerate(data.zones):
        drop_off_time = (
            actual_time[z.hi] + travel_loaded[z.hi]
        )  # arrivo a stazione hi+1
        d = model.NewIntVar(0, horizon, f"depart_{h}")
        model.Add(d >= drop_off_time)
        depart.append(d)

        pos_hi1 = data.station_position(z.hi + 1)
        pos_lo = data.station_position(z.lo)
        t_empty_return = travel_empty_ticks(pos_hi1, pos_lo)
        arr_back = d + t_empty_return
        arrive_back.append(arr_back)

        # deve rientrare in tempo per il prelievo successivo (T secondi dopo
        # l'attuale prelievo alla stazione lo)
        model.Add(arr_back <= actual_time[z.lo] + Tv)

    # -- Vincoli di non collisione alle stazioni di confine fra zone
    #    adiacenti (uniche stazioni fisicamente condivise). -----------------
    # NOTA IMPORTANTE: due eventi periodici di periodo T possono essere
    # sfasati anche di PIU' di un ciclo: ad esempio se una vasca ha un
    # tempo di processo molto piu' lungo del takt time (tipico dei bagni di
    # trattamento superficiale), l'evento "pericoloso" nel confine puo'
    # distare diversi multipli di T. Percio' generiamo un numero di copie
    # traslate sufficiente a coprire l'intero orizzonte del modello, non
    # solo il ciclo immediatamente precedente/successivo.
    n_shifts = math.ceil(horizon / T_min) + 2
    BIG = 10**7  # limite tecnico largo per i domini delle variabili ausiliarie

    def _as_intvar(expr, name):
        """Materializza un'espressione lineare (variabile + costanti, anche
        con coefficienti negativi) in un vero e proprio IntVar, legato
        all'espressione con un vincolo di uguaglianza. Passare sempre
        IntVar "puri" a NewIntervalVar (invece di espressioni composte
        direttamente) e' piu' robusto fra le diverse versioni di OR-Tools."""
        v = model.NewIntVar(-BIG, BIG, name)
        model.Add(v == expr)
        return v

    def add_cyclic_no_overlap(start_a, end_a, start_b, end_b, name):
        """Impone che [start_a,end_a] non si sovrapponga MAI a [start_b,end_b]
        ne' ad alcuna sua traslazione di un multiplo intero di T (positivo o
        negativo), catturando correttamente la periodicita' anche quando i
        due eventi sono sfasati di piu' di un ciclo."""
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
        z_left = data.zones[h]
        z_right = data.zones[h + 1]
        assert z_left.hi + 1 == z_right.lo, "le zone devono essere contigue"

        # occupazione del confine da parte del carroponte di sinistra:
        # da quando consegna (drop-off) a quando riparte (depart), +margine
        drop_off_left = actual_time[z_left.hi] + travel_loaded[z_left.hi]
        occ_left_start = drop_off_left - safety_buffer
        occ_left_end = depart[h] + safety_buffer

        # occupazione del confine da parte del carroponte di destra: come
        # costruito sopra, arrive_back[h+1] e' il rientro che rende il
        # carroponte pronto per il prelievo del GIRO SUCCESSIVO (T secondi
        # dopo l'attuale actual_time[lo]) -- percio' la finestra corretta è
        # da arrive_back fino a (actual_time[lo] + T), non fino a
        # actual_time[lo] stesso.
        occ_right_start = arrive_back[h + 1] - safety_buffer
        occ_right_end = actual_time[z_right.lo] + Tv + safety_buffer

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
    at_values = [data.to_seconds(solver.Value(v)) for v in actual_time]
    depart_values = [data.to_seconds(solver.Value(v)) for v in depart]

    segments_per_hoist = _build_trajectories(data, at_values, depart_values, T_seconds)

    raw = {
        "actual_time": at_values,
        "depart": depart_values,
        "objective": solver.ObjectiveValue(),
        "wall_time": solver.WallTime(),
    }
    return Solution(
        status=status_name, T=T_seconds, segments_per_hoist=segments_per_hoist, raw=raw
    )


# --------------------------------------------------------------------------
# Costruzione della traiettoria (posizione nel tempo) a partire dai valori
# risolti. Separata dalla risoluzione CP-SAT cosi' da poter essere testata
# anche senza risolvere realmente un modello (es. con valori scelti a mano).
# --------------------------------------------------------------------------


def _build_trajectories(
    data: ProblemData, actual_time: list[float], depart: list[float], T: float
) -> list[list[Segment]]:
    """Costruisce, per ciascun carroponte, la sequenza di segmenti che ne
    descrive la traiettoria entro UN ciclo. Poiche' actual_time[] descrive
    un unico "pezzo di riferimento" che attraversa l'intera linea (e quindi
    puo' avere valori grandi, anche diversi multipli di T, per le zone piu'
    a valle), qui normalizziamo la traiettoria di ogni carroponte in modo
    che il suo primo prelievo cada nell'intervallo [0,T): questo allinea
    visivamente tutti i carroponti sulla stessa finestra 0..T, come e'
    convenzione nei ciclogrammi."""
    segments_per_hoist: list[list[Segment]] = []
    for h, z in enumerate(data.zones):
        segs: list[Segment] = []
        phase = actual_time[z.lo] % T  # fase del prelievo iniziale dentro [0,T)
        lap_offset = actual_time[z.lo] - phase  # multiplo di T da sottrarre a tutto

        def shift_time(t):
            return t - lap_offset

        for k in range(z.lo, z.hi + 1):
            x0 = data.station_position(k)
            x1 = data.station_position(k + 1)
            t0 = shift_time(actual_time[k])
            t1 = t0 + _travel_time_seconds(abs(x1 - x0), data.kin_loaded)
            segs.append(Segment("loaded", t0, t1, x0, x1, data.kin_loaded))
            if k < z.hi:
                t_next = shift_time(actual_time[k + 1])
                if t_next > t1:
                    segs.append(Segment("wait", t1, t_next, x1, x1, None))
        # attesa (eventuale) prima del rientro a vuoto
        last_drop_time = segs[-1].t_end
        d = shift_time(depart[h])
        if d < last_drop_time - 1e-6:
            raise ValueError(
                f"depart[{h}]={d} precede la consegna dell'ultimo pezzo ({last_drop_time}): "
                f"valori incoerenti (nel modello CP-SAT questo e' impedito da un vincolo)."
            )
        if d > last_drop_time:
            segs.append(
                Segment("wait", last_drop_time, d, segs[-1].x_end, segs[-1].x_end, None)
            )
        # rientro a vuoto
        x_hi1 = data.station_position(z.hi + 1)
        x_lo = data.station_position(z.lo)
        t_arrive_back = d + _travel_time_seconds(abs(x_hi1 - x_lo), data.kin_empty)
        segs.append(Segment("empty", d, t_arrive_back, x_hi1, x_lo, data.kin_empty))
        # attesa fino al prossimo ciclo (prelievo successivo)
        next_pickup = shift_time(actual_time[z.lo]) + T
        if next_pickup > t_arrive_back:
            segs.append(Segment("wait", t_arrive_back, next_pickup, x_lo, x_lo, None))
        segments_per_hoist.append(segs)
    return segments_per_hoist


# --------------------------------------------------------------------------
# Estensioni possibili (v2 e oltre) -- non implementate in questo file
# --------------------------------------------------------------------------
# 1. Zone decise dal solver: invece di passare `zones` come input fisso,
#    introdurre variabili intere "boundary_h" (posizione di confine fra
#    carroponte h e h+1) e ricostruire i vincoli sopra parametricamente.
#    Aumenta la qualita' delle soluzioni ma anche la complessita' del
#    modello (i coefficienti travel_loaded/travel_empty smettono di essere
#    costanti se dipendono da confini variabili... in realta' restano
#    costanti per-mossa, cambia solo *quale* mossa appartiene a quale
#    carroponte: percio' e' fattibile con variabili booleane is_h_k, in
#    modo analogo a quanto discusso nella progettazione).
#
# 2. Assegnazione non contigua / instradamento generale: un carroponte che
#    "salta" fra mosse non consecutive (utile se il contenuto di una zona
#    supera il takt time). Richiede una formulazione a circuito (vedi
#    `model.AddCircuit` / `AddMultipleCircuit` di OR-Tools) o una
#    formulazione a job-shop con intervalli opzionali per ogni coppia
#    (mossa, carroponte) e vincoli di NoOverlap generalizzati.
#
# 3. Piu' ricette (prodotti diversi che seguono percorsi diversi fra le
#    vasche): si generalizza duplicando la catena actual_time per ciascuna
#    ricetta, con un takt time complessivo che tiene conto del mix
#    produttivo, e condividendo le vasche/i carroponti fra le ricette con
#    ulteriori vincoli di non-sovrapposizione.
#
# 4. Collisione modellata in modo meno conservativo: invece di riservare
#    l'intera finestra [arrivo, partenza] a una stazione di confine, usare
#    il profilo di posizione reale (position_profile in kinematics.py) per
#    calcolare l'intervallo temporale esatto in cui il carroponte e'
#    entro `safety_distance` dal confine, invece dell'intera sosta.
#
# 5. Tempo di presa/rilascio pezzo (immersione/emersione verticale) come
#    costante aggiuntiva su ogni travel_loaded/travel_empty.
