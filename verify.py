"""
verify.py
---------
Verificatore INDIPENDENTE della soluzione prodotta da model.solve().

Questo modulo non usa CP-SAT: ricontrolla in Python puro, partendo dai
segmenti e dai valori risolti, che la soluzione sia davvero fisicamente
valida. Serve come rete di sicurezza contro eventuali errori nella
formulazione CP-SAT stessa: se il modello ha un vincolo sbagliato o mancante,
il solver restituisce comunque una soluzione "ottima" e nulla se ne
accorgerebbe.

Cosa controlla:
  1. struttura (status, takt time nella banda, zone contigue e coprenti)
  2. layout: vicinanze fra stazioni che il modello NON vincola
  3. coerenza dei segmenti di ciascun carroponte (continuita', periodo T)
  4. copertura delle mosse e durate delle tratte
  5. coerenza di fase (la linearizzazione modulo T del modello)
  6. permanenze min/max in vasca
  7. fattibilita' dei trasferimenti a vuoto
  8. COLLISIONI REALI: distanza fra ogni coppia di carroponti campionata
     finemente nel tempo con il profilo cinematico vero (position_profile)
  9. capienza delle vasche (quanti pezzi ci stanno contemporaneamente)

ATTENZIONE - il controllo 8 e' piu' STRETTO di quello che il modello impone:
  - il modello riserva l'intera finestra di sosta alla stazione di CONFINE fra
    due zone, gonfiata di un buffer temporale ricavato da mezzo ingombro
    (hoist_length/2 + safety_distance);
  - qui si richiede |x_i(t) - x_j(t)| >= hoist_length + safety_distance per
    OGNI coppia e OGNI istante, ovunque sulla rotaia.
Nella pratica il vincolo di confine e' sano (vedi README), ma questo
verificatore intercetta il caso in cui una stazione vicina a un confine cada
dentro la zona di esclusione: li' il modello non ha alcun vincolo.

Uso tipico:
    from verify import verify_solution
    report = verify_solution(data, solution)
    print(report.summary())
    if not report.ok:
        ...
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import Optional

from kinematics import position_profile, profile_breakpoints
from model import HoistPlan, ProblemData, Segment, Solution, zone_layout_conflicts

# Tipi di segmento in cui il carroponte e' fermo orizzontalmente: l'attesa, le
# fasi verticali di presa e rilascio, e la corsa del gancio scarico su uno
# svincolo. Tenuto come insieme, e non come confronto == "wait", perche' i tipi
# fermi sono cresciuti nel tempo e cresceranno ancora.
_STATIONARY_KINDS = {"wait", "pick", "release", "lift_empty"}
# Tipi di segmento che descrivono una traslazione orizzontale vera. 'quota' e'
# l'andata (o il ritorno) fra il punto di cambio quota e la stazione, dentro
# una presa o un rilascio: e' dentro la presa, ma il carroponte si muove.
_MOVING_KINDS = {"loaded", "empty", "quota"}
# Stati che dichiarano esplicitamente l'assenza di una soluzione.
_STATI_SENZA_SOLUZIONE = {"INFEASIBLE", "MODEL_INVALID", "UNKNOWN", "NOT_SOLVED"}


# --------------------------------------------------------------------------
# Risultato della verifica
# --------------------------------------------------------------------------


@dataclass
class Violation:
    """Una singola anomalia riscontrata. `slack` < 0 indica di quanto il
    vincolo e' violato (nelle unita' naturali del vincolo: s oppure m)."""

    kind: str  # 'collision'|'dwell_min'|'dwell_max'|'periodicity'|'phase'|
    # 'segment_duration'|'continuity'|'zone_bounds'|'order'|
    # 'takt_range'|'layout'|'transfer'|'tank_capacity'
    severity: str  # 'error' | 'warning' | 'info'
    message: str
    hoists: tuple[int, ...] = ()
    move: Optional[int] = None
    station: Optional[int] = None
    t: Optional[float] = None
    value: Optional[float] = None  # valore misurato
    bound: Optional[float] = None  # valore richiesto
    slack: Optional[float] = None  # value - bound (< 0 = violazione)

    def __str__(self) -> str:
        where = []
        if self.hoists:
            where.append("carroponte " + "/".join(str(h + 1) for h in self.hoists))
        if self.move is not None:
            where.append(f"mossa {self.move}")
        if self.station is not None:
            where.append(f"stazione {self.station}")
        if self.t is not None:
            where.append(f"t={self.t:.2f}s")
        loc = f" [{', '.join(where)}]" if where else ""
        return f"{self.severity.upper():7s} {self.kind:16s}{loc} {self.message}"


@dataclass
class VerificationReport:
    ok: bool  # nessuna violazione di severita' 'error'
    violations: list[Violation]
    T: float
    required_separation: float  # [m] hoist_length + safety_distance
    min_separation: float  # [m] minimo su tutte le coppie e tutti gli istanti
    min_separation_t: float  # [s] istante in cui si verifica
    min_separation_pair: Optional[tuple[int, int]]
    sampling_dt: float  # [s] passo della griglia uniforme
    sampling_error_bound: float  # [m] errore massimo del campionamento
    n_samples: int
    dwell_slack: dict[int, tuple[float, float]] = field(default_factory=dict)
    tank_occupancy: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warnings(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == "warning"]

    @property
    def infos(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == "info"]

    def summary(self) -> str:
        lines = []
        lines.append("=" * 72)
        verdetto = "SUPERATA" if self.ok else "NON SUPERATA"
        lines.append(f"VERIFICA INDIPENDENTE DELLA SOLUZIONE: {verdetto}")
        lines.append("=" * 72)
        lines.append(f"  takt time T                : {self.T:.2f} s")
        if self.min_separation_pair is not None:
            i, j = self.min_separation_pair
            lines.append(
                f"  separazione minima         : {self.min_separation:.0f} mm "
                f"(richiesta {self.required_separation:.0f} mm) "
                f"fra carroponti {i + 1} e {j + 1} a t={self.min_separation_t:.2f} s"
            )
            lines.append(
                f"  margine spaziale residuo   : "
                f"{self.min_separation - self.required_separation:+.0f} mm"
            )
        else:
            lines.append(
                "  separazione minima         : n/d (un solo carroponte, "
                "nessuna coppia da controllare)"
            )
        lines.append(
            f"  campionamento              : dt={self.sampling_dt * 1000:.0f} ms, "
            f"{self.n_samples} istanti, errore <= {self.sampling_error_bound:.4f} mm"
        )
        if self.dwell_slack:
            st, (smin, smax) = min(
                self.dwell_slack.items(), key=lambda kv: min(kv[1])
            )
            lines.append(
                f"  permanenza piu' stretta    : stazione {st}, "
                f"margine {smin:+.1f} s sul minimo / {smax:+.1f} s sul massimo"
            )
        if self.tank_occupancy:
            occ = ", ".join(
                f"{tid}={n}" for tid, n in self.tank_occupancy.items() if n > 1
            )
            if occ:
                lines.append(f"  pezzi contemporanei in vasca: {occ}")
        lines.append(
            f"  esito                      : {len(self.errors)} errori, "
            f"{len(self.warnings)} avvisi, {len(self.infos)} note"
        )
        if self.violations:
            lines.append("-" * 72)
            for v in self.violations:
                lines.append("  " + str(v))
        lines.append("=" * 72)
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Traiettoria periodica campionabile
# --------------------------------------------------------------------------


class _Trajectory:
    """Traiettoria di un carroponte su un periodo, valutabile a qualunque t
    (la si estende per periodicita' con un wrap modulo T).

    I segmenti di un carroponte NON partono da t=0 ma da local_pick[zone.lo],
    che e' diverso per ogni carroponte: il wrap va quindi fatto rispetto a
    quell'origine, non rispetto a 0."""

    def __init__(self, segments: list[Segment], T: float):
        if not segments:
            raise ValueError("traiettoria senza segmenti")
        self.T = T
        self.segs = sorted(segments, key=lambda s: (s.t_start, s.t_end))
        self.t0 = self.segs[0].t_start
        self.starts = [s.t_start for s in self.segs]

    def position(self, t: float) -> float:
        # il modulo di un float con divisore positivo cade sempre in [0, T)
        tau = self.t0 + (t - self.t0) % self.T
        i = max(0, bisect.bisect_right(self.starts, tau) - 1)
        s = self.segs[i]
        if s.kin is None or s.x_end == s.x_start:
            return s.x_start
        d = s.x_end - s.x_start
        sign = 1.0 if d >= 0 else -1.0
        # position_profile clampa t internamente: assorbe da sola le micro
        # sovrapposizioni fra segmenti lasciate dagli arrotondamenti.
        return s.x_start + sign * position_profile(tau - s.t_start, abs(d), s.kin)

    def breakpoints(self) -> list[float]:
        """Istanti notevoli ASSOLUTI (estremi di segmento + spigoli del
        profilo cinematico interno a ogni segmento)."""
        out = []
        for s in self.segs:
            out.append(s.t_start)
            out.append(s.t_end)
            if s.kin is not None and s.x_end != s.x_start:
                for b in profile_breakpoints(abs(s.x_end - s.x_start), s.kin):
                    out.append(s.t_start + b)
        return out

    def max_accel(self) -> float:
        """Accelerazione massima presente nella traiettoria, per il calcolo
        rigoroso dell'errore di campionamento."""
        return max(
            (s.kin.a_max for s in self.segs if s.kin is not None),
            default=0.0,
        )


# --------------------------------------------------------------------------
# Verifica
# --------------------------------------------------------------------------


def verify_solution(
    data: ProblemData,
    solution: Solution,
    dt: Optional[float] = None,
    time_tol: Optional[float] = None,
    space_tol: float = 1.0,
    warn_margin: float = 0.0,
) -> VerificationReport:
    """Ricontrolla la soluzione senza passare da CP-SAT.

    dt          passo della griglia temporale di campionamento [s]
                (default: un tick, cioe' 1/data.time_scale)
    time_tol    tolleranza sui confronti temporali [s]
                (default: data.eps_seconds, la stessa usata dal modello)
    space_tol   tolleranza assoluta sui confronti di distanza [mm]
    warn_margin se > 0, segnala come avviso anche le separazioni che superano
                il minimo richiesto per meno di questo margine [m]

    Non solleva eccezioni per le violazioni: le raccoglie nel report. Solleva
    ValueError solo se l'input e' malformato (soluzione non fattibile, zone
    non definite, ecc.).
    """
    # -- validazione dell'input (qui si', si solleva) -----------------------
    # Lo status non e' una lista chiusa: oltre a quelli del solutore ci sono i
    # ciclogrammi composti a mano ("MANUALE", "PROPOSTA"). Si rifiuta solo cio'
    # che dichiara di NON contenere una soluzione.
    if solution.status in _STATI_SENZA_SOLUZIONE:
        raise ValueError(
            f"Non c'e' nulla da verificare (status={solution.status})"
        )
    if not solution.segments_per_hoist:
        raise ValueError("la soluzione non contiene nessuna traiettoria")
    if solution.T is None:
        raise ValueError("solution.T e' None: soluzione incompleta")
    if data.zones is None:
        raise ValueError(
            "data.zones e' None: passa la ProblemData con le zone effettivamente "
            "usate (es. dataclasses.replace(data, zones=zones))"
        )
    if len(solution.segments_per_hoist) != len(data.zones):
        raise ValueError(
            f"disallineamento: {len(solution.segments_per_hoist)} traiettorie "
            f"per {len(data.zones)} zone"
        )

    T = solution.T
    dt = dt if dt is not None else 1.0 / data.time_scale
    time_tol = time_tol if time_tol is not None else data.eps_seconds
    required = data.hoist_length + data.safety_distance

    V: list[Violation] = []

    def add(kind, severity, message, **kw):
        V.append(Violation(kind=kind, severity=severity, message=message, **kw))

    plans = _resolve_plans(data, solution, T, V)

    _check_structure(data, solution, T, time_tol, add)
    _check_layout(data, required, add)
    trajectories = _check_per_hoist(data, solution, plans, T, time_tol, add)
    _check_phase_and_dwell(data, solution, plans, T, time_tol, add)
    _check_transfers(data, plans, T, time_tol, add)
    dwell_slack = _compute_dwell_slack(data, solution, T)
    tank_occupancy = _check_tank_capacity(data, solution, T, add)
    sep = _check_collisions(
        data, trajectories, T, dt, required, space_tol, warn_margin, add
    )

    violations = sorted(
        V, key=lambda v: {"error": 0, "warning": 1, "info": 2}[v.severity]
    )
    return VerificationReport(
        ok=not any(v.severity == "error" for v in violations),
        violations=violations,
        T=T,
        required_separation=required,
        min_separation=sep["min_sep"],
        min_separation_t=sep["min_t"],
        min_separation_pair=sep["min_pair"],
        sampling_dt=dt,
        sampling_error_bound=sep["err_bound"],
        n_samples=sep["n_samples"],
        dwell_slack=dwell_slack,
        tank_occupancy=tank_occupancy,
    )


# --------------------------------------------------------------------------
# Ricostruzione dei piani quando il solver non li ha esportati
# --------------------------------------------------------------------------


def _resolve_plans(
    data: ProblemData, solution: Solution, T: float, V: list[Violation]
) -> list[HoistPlan]:
    """Restituisce i piani risolti. Se la soluzione non li porta con se'
    (soluzioni vecchie o costruite a mano) li ricostruisce dai segmenti: da li'
    si recuperano `order`, `local_pick` e `finish`, ma NON i tempi assoluti
    `actual_time`, che restano noti solo modulo T."""
    if solution.plans:
        return solution.plans

    V.append(
        Violation(
            kind="dwell",
            severity="info",
            message=(
                "la soluzione non contiene i valori risolti (solution.plans): "
                "le permanenze sono verificabili solo modulo T"
            ),
        )
    )
    plans = []
    for h, (zone, segs) in enumerate(zip(data.zones, solution.segments_per_hoist)):
        order = []
        local_pick: dict[int, float] = {}
        finish: dict[int, float] = {}
        for s in segs:
            if s.kind != "loaded":
                continue
            k = _move_of_loaded_segment(data, zone, s)
            if k is None:
                continue
            order.append(k)
            local_pick[k] = s.t_start % T
            finish[k] = s.t_end
        # dep_hi / arr_lo: partenza dal confine alto e arrivo al confine basso
        dep_hi = next(
            (s.t_start for s in segs if s.kind == "empty" and _at(
                s.x_start, data.approach_position(zone.hi + 1))),
            float("nan"),
        )
        arr_lo = next(
            (s.t_end for s in segs if s.kind == "empty" and _at(
                s.x_end, data.approach_position(zone.lo))),
            float("nan"),
        )
        plans.append(HoistPlan(zone, order, local_pick, finish, dep_hi, arr_lo))
    return plans


def _at(x: float, target: float, tol: float = 1e-6) -> bool:
    return abs(x - target) <= tol


def _move_of_loaded_segment(
    data: ProblemData, zone, seg: Segment, tol: float = 1e-6
) -> Optional[int]:
    """A quale mossa appartiene un tratto a carico, riconosciuto dai suoi
    estremi. Sono i punti di APPROCCIO: con una zona di cambio quota il tratto
    col pezzo parte (o finisce) sul punto di cambio quota, non sulla stazione.

    Si riconosce dalla geometria e non da `seg.move` apposta: il verificatore
    deve poter controllare anche una traiettoria che il modello non ha
    prodotto, dove `move` potrebbe essere sbagliato o assente."""
    for k in range(zone.lo, zone.hi + 1):
        if _at(seg.x_start, data.approach_position(k), tol) and _at(
            seg.x_end, data.approach_position(k + 1), tol
        ):
            return k
    return None


# --------------------------------------------------------------------------
# Controlli
# --------------------------------------------------------------------------


def _check_structure(data, solution, T, time_tol, add):
    """1) Struttura: takt nella banda dichiarata, zone contigue e coprenti."""
    if T < data.takt_min - time_tol or T > data.takt_max + time_tol:
        add(
            "takt_range",
            "error",
            f"T={T:.3f}s fuori dalla banda ammessa "
            f"[{data.takt_min:.1f}, {data.takt_max:.1f}]",
            value=T,
            bound=data.takt_max,
        )
    covered = []
    for z in data.zones:
        if z.lo > z.hi:
            add("zone_bounds", "error", f"zona degenere lo={z.lo} > hi={z.hi}")
        covered.extend(range(z.lo, z.hi + 1))
    if covered != list(range(data.n_moves)):
        add(
            "zone_bounds",
            "error",
            f"le zone non coprono in modo contiguo ed esclusivo le mosse "
            f"0..{data.n_moves - 1}: {covered}",
        )
    if solution.plans and len(solution.plans) != len(data.zones):
        add(
            "zone_bounds",
            "error",
            f"{len(solution.plans)} piani risolti per {len(data.zones)} zone",
        )


def _check_layout(data, required, add):
    """2) Layout: individua le vicinanze che il modello NON vincola.

    Usa la stessa funzione con cui `solve()` rifiuta le suddivisioni non
    rappresentabili (model.zone_layout_conflicts), cosi' le due analisi non
    possono divergere. Qui pero' e' solo un avviso: una soluzione costruita a
    mano, o prodotta con allow_unsafe_layout=True, va comunque verificata --
    ed e' il controllo 8 (collisioni) a dire se il rischio si e' davvero
    concretizzato."""
    for problema in zone_layout_conflicts(data, data.zones):
        add(
            "layout",
            "warning",
            problema + " -- il modello non vincola questa vicinanza",
            bound=required,
        )


def _check_per_hoist(data, solution, plans, T, time_tol, add) -> list[_Trajectory]:
    """3) e 4) Coerenza dei segmenti e copertura delle mosse."""
    trajectories = []
    for h, (zone, segs) in enumerate(zip(data.zones, solution.segments_per_hoist)):
        if not segs:
            add("continuity", "error", "traiettoria vuota", hoists=(h,))
            continue
        segs = sorted(segs, key=lambda s: (s.t_start, s.t_end))

        # -- continuita' nel tempo e nello spazio --
        for a, b in zip(segs, segs[1:]):
            gap = b.t_start - a.t_end
            if abs(gap) > time_tol:
                add(
                    "continuity",
                    "error",
                    f"discontinuita' temporale di {gap:+.3f}s fra due segmenti",
                    hoists=(h,),
                    t=a.t_end,
                    value=gap,
                    bound=0.0,
                )
            dx = b.x_start - a.x_end
            if abs(dx) > 1e-6:
                add(
                    "continuity",
                    "error",
                    f"salto di posizione di {dx:+.3f}m fra due segmenti",
                    hoists=(h,),
                    t=a.t_end,
                    value=dx,
                    bound=0.0,
                )
        for s in segs:
            if s.t_end < s.t_start - 1e-9:
                add(
                    "continuity",
                    "error",
                    f"segmento '{s.kind}' con durata negativa",
                    hoists=(h,),
                    t=s.t_start,
                )

        # -- il ciclo deve durare esattamente T --
        span = segs[-1].t_end - segs[0].t_start
        if abs(span - T) > time_tol:
            add(
                "periodicity",
                "error",
                f"il ciclo dura {span:.3f}s invece di T={T:.3f}s",
                hoists=(h,),
                value=span,
                bound=T,
                slack=span - T,
            )
        # -- la traiettoria deve richiudersi su se stessa --
        if abs(segs[-1].x_end - segs[0].x_start) > 1e-6:
            add(
                "periodicity",
                "error",
                f"il carroponte non torna al punto di partenza "
                f"({segs[0].x_start:.0f} -> {segs[-1].x_end:.0f} mm)",
                hoists=(h,),
            )

        # -- confini spaziali della zona --
        xs = [data.station_position(i) for i in range(zone.lo, zone.hi + 2)]
        x_lo, x_hi = min(xs), max(xs)
        for s in segs:
            for x in (s.x_start, s.x_end):
                if x < x_lo - 1e-6 or x > x_hi + 1e-6:
                    add(
                        "zone_bounds",
                        "error",
                        f"posizione {x:.3f}m fuori dall'intervallo della zona "
                        f"[{x_lo:.3f},{x_hi:.3f}]",
                        hoists=(h,),
                        t=s.t_start,
                    )
                    break

        # -- copertura delle mosse e durate delle tratte --
        seen: dict[int, int] = {}
        for i_seg, s in enumerate(segs):
            if s.kind == "loaded":
                k = _move_of_loaded_segment(data, zone, s)
                if k is None:
                    add(
                        "order",
                        "error",
                        f"tratto a carico da {s.x_start:.0f} a {s.x_end:.0f} mm "
                        f"che non corrisponde a nessuna mossa della zona",
                        hoists=(h,),
                        t=s.t_start,
                    )
                    continue
                seen[k] = seen.get(k, 0) + 1
                # Due controlli distinti, e servono entrambi: la sola
                # traslazione orizzontale deve rispettare la cinematica, e la
                # mossa nel suo insieme (con le fasi verticali adiacenti) deve
                # durare quanto dichiarato. Controllare solo il totale
                # lascerebbe passare una traslazione impossibile compensata da
                # una presa piu' lunga.
                atteso_h = data.horizontal_loaded_seconds(k)
                durata_h = s.t_end - s.t_start
                if abs(durata_h - atteso_h) > time_tol:
                    add(
                        "segment_duration",
                        "error",
                        f"la traslazione a carico dura {durata_h:.3f}s invece "
                        f"di {atteso_h:.3f}s",
                        hoists=(h,),
                        move=k,
                        t=s.t_start,
                        value=durata_h,
                        bound=atteso_h,
                        slack=durata_h - atteso_h,
                    )
                atteso = data.loaded_leg_seconds(k)
                durata = _leg_duration(segs, i_seg)
                if abs(durata - atteso) > time_tol:
                    add(
                        "segment_duration",
                        "error",
                        f"la mossa (presa + traslazione + rilascio) dura "
                        f"{durata:.3f}s invece di {atteso:.3f}s",
                        hoists=(h,),
                        move=k,
                        t=s.t_start,
                        value=durata,
                        bound=atteso,
                        slack=durata - atteso,
                    )
            elif s.kind == "empty":
                # la singola tratta orizzontale, non il giro: fra due vasche il
                # rientro puo' essere spezzato dalla salita e dalla discesa
                # sugli svincoli
                atteso = data.horizontal_empty_seconds(s.x_start, s.x_end)
                durata = s.t_end - s.t_start
                if abs(durata - atteso) > time_tol:
                    add(
                        "segment_duration",
                        "error",
                        f"lo spostamento a vuoto da {s.x_start:.2f} a "
                        f"{s.x_end:.2f}m dura {durata:.3f}s invece di {atteso:.3f}s",
                        hoists=(h,),
                        t=s.t_start,
                        value=durata,
                        bound=atteso,
                        slack=durata - atteso,
                    )
            elif s.kind == "quota":
                atteso = _durata_traslazione_di_quota(data, s)
                durata = s.t_end - s.t_start
                if atteso is None:
                    add(
                        "segment_duration",
                        "error",
                        f"traslazione di cambio quota da {s.x_start:.0f} a "
                        f"{s.x_end:.0f} mm che non corrisponde a nessuna fase "
                        f"di presa o di rilascio",
                        hoists=(h,),
                        t=s.t_start,
                    )
                elif abs(durata - atteso) > time_tol:
                    add(
                        "segment_duration",
                        "error",
                        f"la traslazione di cambio quota da {s.x_start:.0f} a "
                        f"{s.x_end:.0f} mm dura {durata:.3f}s invece di "
                        f"{atteso:.3f}s",
                        hoists=(h,),
                        move=s.move,
                        t=s.t_start,
                        value=durata,
                        bound=atteso,
                        slack=durata - atteso,
                    )
            elif s.kind not in _STATIONARY_KINDS:
                add(
                    "continuity",
                    "error",
                    f"tipo di segmento sconosciuto: '{s.kind}'",
                    hoists=(h,),
                    t=s.t_start,
                )

        for k in range(zone.lo, zone.hi + 1):
            n = seen.get(k, 0)
            if n != 1:
                add(
                    "order",
                    "error",
                    f"la mossa compare {n} volte nel ciclo invece di 1",
                    hoists=(h,),
                    move=k,
                )

        # -- l'ordine risolto deve essere una permutazione delle mosse --
        plan = plans[h] if h < len(plans) else None
        if plan is not None:
            if sorted(plan.order) != list(range(zone.lo, zone.hi + 1)):
                add(
                    "order",
                    "error",
                    f"order={plan.order} non e' una permutazione delle mosse "
                    f"{zone.lo}..{zone.hi}",
                    hoists=(h,),
                )
            elif plan.order[0] != zone.lo:
                add(
                    "order",
                    "error",
                    f"order deve iniziare dalla mossa di confine basso "
                    f"{zone.lo}, non da {plan.order[0]}",
                    hoists=(h,),
                )

        trajectories.append(_Trajectory(segs, T))
    return trajectories


def _leg_duration(segs: list[Segment], i: int) -> float:
    """Durata totale della mossa il cui tratto a carico e' segs[i]: comprende
    le fasi verticali immediatamente adiacenti (presa prima del trasporto,
    rilascio dopo) e, dove c'e' una zona di cambio quota, anche le traslazioni
    che stanno DENTRO la presa e dentro il rilascio.

    Ci si allarga finche' i tratti dichiarano la stessa mossa: e' l'unico
    criterio che regge quando presa e rilascio sono spezzati in piu' tratti.
    Attesa e rientro a vuoto non dichiarano nessuna mossa, quindi fermano da
    soli l'allargamento."""
    k = segs[i].move
    if k is None:
        return segs[i].t_end - segs[i].t_start
    a = i
    while a > 0 and segs[a - 1].move == k and segs[a - 1].kind in ("pick", "quota"):
        a -= 1
    b = i
    while (
        b + 1 < len(segs)
        and segs[b + 1].move == k
        and segs[b + 1].kind in ("release", "quota")
    ):
        b += 1
    return segs[b].t_end - segs[a].t_start


def _durata_traslazione_di_quota(data: ProblemData, seg: Segment) -> Optional[float]:
    """Quanto deve durare una traslazione fatta dentro una presa o un
    rilascio, cercandola fra le fasi della stazione in base agli estremi.

    Si guarda la FASE e non la cinematica scritta nel segmento: quella e' uno
    dei dati che il verificatore deve controllare, non uno su cui appoggiarsi."""
    if seg.move is None:
        return None
    for fasi in (
        data.pick_phases(seg.move),
        data.release_phases(seg.move + 1),
    ):
        for f in fasi:
            if f.trasla and _at(f.x_start, seg.x_start) and _at(f.x_end, seg.x_end):
                return f.duration
    return None


def _check_phase_and_dwell(data, solution, plans, T, time_tol, add):
    """5) Coerenza di fase (linearizzazione modulo T) e 6) permanenze."""
    if not plans:
        return
    for h, plan in enumerate(plans):
        for k, lp in plan.local_pick.items():
            if lp < -time_tol or lp >= T + time_tol:
                add(
                    "phase",
                    "error",
                    f"local_pick={lp:.3f}s fuori da [0,T)",
                    hoists=(h,),
                    move=k,
                    value=lp,
                    bound=T,
                )
            atteso = lp + data.loaded_leg_seconds(k)
            if abs(plan.finish[k] - atteso) > time_tol:
                add(
                    "phase",
                    "error",
                    f"finish={plan.finish[k]:.3f}s incoerente con "
                    f"local_pick+durata={atteso:.3f}s",
                    hoists=(h,),
                    move=k,
                    value=plan.finish[k],
                    bound=atteso,
                    slack=plan.finish[k] - atteso,
                )

    if not solution.actual_time:
        return  # tempi assoluti non disponibili: gia' segnalato come 'info'

    at = solution.actual_time
    if len(at) != data.n_moves:
        add(
            "phase",
            "error",
            f"actual_time ha {len(at)} elementi invece di {data.n_moves}",
        )
        return

    # 5) la fase locale deve essere il tempo assoluto ridotto modulo T
    for h, plan in enumerate(plans):
        for k, lp in plan.local_pick.items():
            resto = (at[k] - lp) % T
            scarto = min(resto, T - resto)
            if scarto > time_tol:
                add(
                    "periodicity",
                    "error",
                    f"actual_time={at[k]:.3f}s e local_pick={lp:.3f}s non "
                    f"differiscono di un multiplo intero di T (scarto "
                    f"{scarto:.3f}s)",
                    hoists=(h,),
                    move=k,
                    value=scarto,
                    bound=0.0,
                )

    # 6) permanenze min/max, dai tempi assoluti
    #
    # Si controlla il BAGNO, non l'intervallo fra i movimenti del gancio: il
    # pezzo e' immerso anche mentre il gancio che lo ha deposto risale e mentre
    # quello che verra' a riprenderlo ricala. Il verificatore ha condiviso per
    # un po' la definizione del modello, ed e' cosi' che una linea con sei
    # vasche su dieci fuori tolleranza e' passata con "VERIFICA SUPERATA": un
    # controllore che misura la stessa cosa del controllato non controlla
    # niente.
    for k in range(1, data.n_moves):
        station = k
        arrivo = at[k - 1] + data.loaded_leg_seconds(k - 1)
        extra = data.bath_extra_seconds(station)
        bagno = at[k] - arrivo + extra
        spec = data.route[station]
        dettaglio = (
            f" (di cui {extra:.1f}s con il gancio in movimento a vuoto)"
            if extra > 0
            else ""
        )
        if bagno < spec.dwell_min - time_tol:
            add(
                "dwell_min",
                "error",
                f"permanenza {bagno:.2f}s in '{spec.tank_id}' sotto il minimo "
                f"di {spec.dwell_min:.1f}s{dettaglio}",
                station=station,
                move=k,
                value=bagno,
                bound=spec.dwell_min,
                slack=bagno - spec.dwell_min,
            )
        if bagno > spec.dwell_max + time_tol:
            add(
                "dwell_max",
                "error",
                f"permanenza {bagno:.2f}s in '{spec.tank_id}' sopra il massimo "
                f"di {spec.dwell_max:.1f}s{dettaglio}",
                station=station,
                move=k,
                value=bagno,
                bound=spec.dwell_max,
                slack=spec.dwell_max - bagno,
            )


def _compute_dwell_slack(data, solution, T) -> dict[int, tuple[float, float]]:
    """Margine residuo di ciascuna permanenza: (quanto sopra il minimo,
    quanto sotto il massimo), in secondi."""
    out: dict[int, tuple[float, float]] = {}
    if not solution.actual_time or len(solution.actual_time) != data.n_moves:
        return out
    at = solution.actual_time
    for k in range(1, data.n_moves):
        spec = data.route[k]
        if spec.dwell_max <= spec.dwell_min:
            continue  # permanenza rigida: nessun margine da riportare
        bagno = (
            at[k]
            - (at[k - 1] + data.loaded_leg_seconds(k - 1))
            + data.bath_extra_seconds(k)
        )
        out[k] = (bagno - spec.dwell_min, spec.dwell_max - bagno)
    return out


def _check_transfers(data, plans, T, time_tol, add):
    """7) Fattibilita' degli spostamenti a vuoto fra mosse consecutive."""
    for h, plan in enumerate(plans):
        z = plan.zone
        order = plan.order
        if not order or not plan.finish:
            continue
        for i, k1 in enumerate(order):
            k2 = order[(i + 1) % len(order)]
            if k1 not in plan.finish or k2 not in plan.local_pick:
                continue
            t_emp = data.empty_leg_seconds(k1 + 1, k2)
            arrivo = plan.finish[k1] + t_emp
            target = plan.local_pick[k2] + (T if k2 == z.lo else 0.0)
            if arrivo > target + time_tol:
                add(
                    "transfer",
                    "error",
                    f"il carroponte {h + 1} non arriva in tempo dalla mossa "
                    f"{k1} (finisce in {data.route[k1 + 1].tank_id}) alla "
                    f"mossa {k2} (parte da {data.route[k2].tank_id}): "
                    f"pronto a {arrivo:.2f}s, prelievo a {target:.2f}s",
                    hoists=(h,),
                    move=k2,
                    value=arrivo,
                    bound=target,
                    slack=target - arrivo,
                )


def _check_tank_capacity(data, solution, T, add) -> dict[str, int]:
    """9) Quanti pezzi stanno contemporaneamente in ciascuna VASCA FISICA.

    Un pezzo tiene occupato un posto dall'istante in cui finisce l'immersione a
    quello in cui finisce l'emersione, e la scena si ripete ogni T. Il massimo
    numero di posti occupati contemporaneamente si calcola contando le
    sovrapposizioni degli intervalli, replicati su abbastanza periodi -- niente
    formule approssimate: se la stessa vasca compare in piu' tappe del
    percorso, gli intervalli delle diverse tappe possono benissimo essere
    sfasati, e sommare i massimi darebbe un numero troppo alto."""
    occupancy: dict[str, int] = {}
    if not solution.actual_time or len(solution.actual_time) != data.n_moves:
        return occupancy
    at = solution.actual_time

    for tank_id, steps in data.steps_by_tank().items():
        cap = data.tanks[tank_id].capacity
        # intervalli di occupazione di un posto, riportati in fase [0, T)
        intervalli = []
        dettagli = []
        for s in steps:
            bagno = (
                at[s]
                - (at[s - 1] + data.loaded_leg_seconds(s - 1))
                + data.bath_extra_seconds(s)
            )
            occ = data.slot_occupancy_seconds(s, bagno)
            fine = (at[s] + data.pick_time_at(s)) % T
            intervalli.append((fine - occ, fine))
            dettagli.append(
                f"tappa {s}: bagno {bagno:.0f}s + fasi verticali "
                f"{occ - bagno:.0f}s = {occ:.0f}s"
            )
        n = _max_sovrapposizioni(intervalli, T)
        occupancy[tank_id] = n
        dettaglio = f"takt {T:.0f}s; " + "; ".join(dettagli)
        if n > cap:
            add(
                "tank_capacity",
                "error",
                f"nella vasca '{tank_id}' servono {n} posti ma capacity={cap} "
                f"({dettaglio})",
                station=steps[0],
                value=float(n),
                bound=float(cap),
                slack=float(cap - n),
            )
        elif n > 1:
            add(
                "tank_capacity",
                "info",
                f"nella vasca '{tank_id}' ci sono sempre {n} pezzi "
                f"contemporaneamente su {cap} posti dichiarati ({dettaglio})",
                station=steps[0],
                value=float(n),
                bound=float(cap),
                slack=float(cap - n),
            )
    return occupancy


def _max_sovrapposizioni(intervalli: list[tuple[float, float]], T: float) -> int:
    """Massimo numero di intervalli sovrapposti, sapendo che ciascuno si
    ripete ogni T. Si replicano su abbastanza periodi da coprire per intero
    una finestra centrale, e si contano gli attraversamenti."""
    if not intervalli:
        return 0
    durata_max = max(fine - inizio for inizio, fine in intervalli)
    n_rip = int(math.ceil(durata_max / T)) + 2
    eventi = []
    for inizio, fine in intervalli:
        for k in range(-n_rip, n_rip + 1):
            eventi.append((inizio + k * T, 1))
            eventi.append((fine + k * T, -1))
    # a parita' di istante prima le uscite: un posto liberato nello stesso
    # istante in cui ne serve un altro puo' essere riusato
    eventi.sort(key=lambda e: (e[0], e[1]))
    corrente = 0
    massimo = 0
    for t, delta in eventi:
        corrente += delta
        # conta solo la finestra centrale, dove la copertura e' completa
        if 0.0 <= t < T:
            massimo = max(massimo, corrente)
    return max(1, massimo)


def _dove(data, x: float) -> str:
    """Traduce una quota della rotaia in un riferimento che si riconosce
    sull'impianto.

    "a 11200 mm" non dice niente a chi legge: il ciclogramma si ragiona per
    vasche. Se la quota e' praticamente quella di una vasca si nomina quella,
    altrimenti si dice fra quali due si trova."""
    quote = sorted({(t.position, tid) for tid, t in data.tanks.items()})
    if not quote:
        return f"{x:.0f} mm"
    piu_vicina = min(quote, key=lambda q: abs(q[0] - x))
    if abs(piu_vicina[0] - x) < 150.0:
        return f"sopra {piu_vicina[1]} ({x:.0f} mm)"
    prima = [q for q in quote if q[0] <= x]
    dopo = [q for q in quote if q[0] >= x]
    if prima and dopo:
        return f"fra {prima[-1][1]} e {dopo[0][1]} ({x:.0f} mm)"
    return f"a {x:.0f} mm, vicino a {piu_vicina[1]}"


def _chi_e_dove(data, i: int, j: int, t: float, xi: float, xj: float) -> str:
    """Frase che apre ogni rilievo di collisione: chi, quando, dove.

    Senza questa, il report dice solo che due carroponti sono troppo vicini --
    vero ma inservibile: per rimediare bisogna sapere QUALI e in che punto
    della linea, altrimenti tocca ricostruirlo a mano dal grafico."""
    return (
        f"carroponti {i + 1} e {j + 1} a t={t:.1f}s: "
        f"il {i + 1} e' {_dove(data, xi)}, il {j + 1} e' {_dove(data, xj)}"
    )


def _check_collisions(
    data, trajectories, T, dt, required, space_tol, warn_margin, add
) -> dict:
    """8) Collisioni: distanza fra ogni coppia di carroponti, campionata
    finemente con il profilo cinematico reale.

    Fra due spigoli del profilo la posizione e' un polinomio di grado <= 2,
    quindi anche la differenza fra due carroponti lo e'. Campionando TUTTI gli
    spigoli piu' una griglia uniforme di passo dt, il minimo campionato
    sovrastima quello vero di al piu' (a_i + a_j)/2 * (dt/2)^2."""
    n = len(trajectories)
    if n < 2:
        return dict(
            min_sep=float("inf"),
            min_t=0.0,
            min_pair=None,
            err_bound=0.0,
            n_samples=0,
        )

    # -- insieme dei campioni: spigoli (riportati in [0,T)) + griglia --------
    samples = {0.0, T}
    for tr in trajectories:
        for b in tr.breakpoints():
            samples.add((b - tr.t0) % T + tr.t0)
            samples.add(b % T)
    n_grid = max(1, int(math.ceil(T / dt)))
    for i in range(n_grid + 1):
        samples.add(min(i * dt, T))
    times = sorted(t for t in samples if 0.0 <= t <= T)

    # -- errore massimo del campionamento -----------------------------------
    accels = sorted((tr.max_accel() for tr in trajectories), reverse=True)
    a_sum = accels[0] + accels[1]
    err_bound = 0.5 * a_sum * (dt / 2.0) ** 2

    # -- posizioni di tutti i carroponti a ogni istante ---------------------
    pos = [[tr.position(t) for t in times] for tr in trajectories]

    min_sep = float("inf")
    min_t = 0.0
    min_pair: Optional[tuple[int, int]] = None
    # una sola violazione riportata per coppia (la peggiore), per non
    # sommergere il report con migliaia di righe quasi identiche
    # per ogni coppia: (distanza, istante, posizione di i, posizione di j).
    # Le due posizioni servono a dire DOVE succede, non solo quanto.
    worst: dict[tuple[int, int], tuple[float, float, float, float]] = {}

    for i in range(n):
        for j in range(i + 1, n):
            pi, pj = pos[i], pos[j]
            best = float("inf")
            best_t = 0.0
            best_xi = best_xj = 0.0
            for idx, t in enumerate(times):
                sep = abs(pi[idx] - pj[idx])
                if sep < best:
                    best, best_t = sep, t
                    best_xi, best_xj = pi[idx], pj[idx]
            worst[(i, j)] = (best, best_t, best_xi, best_xj)
            if best < min_sep:
                min_sep, min_t, min_pair = best, best_t, (i, j)

    for (i, j), (sep, t, xi, xj) in worst.items():
        chi_e_dove = _chi_e_dove(data, i, j, t, xi, xj)
        if sep < required - err_bound - space_tol:
            add(
                "collision",
                "error",
                f"COLLISIONE fra {chi_e_dove} -- restano {sep:.0f} mm contro i "
                f"{required:.0f} mm richiesti (ingombro "
                f"{data.hoist_extent_neg:.0f}+{data.hoist_extent_pos:.0f}"
                f" + sicurezza {data.safety_distance:.0f})",
                hoists=(i, j),
                t=t,
                value=sep,
                bound=required,
                slack=sep - required,
            )
        elif sep < required:
            add(
                "collision",
                "warning",
                f"{chi_e_dove} -- distanza {sep:.0f} mm, appena sotto i "
                f"{required:.0f} mm richiesti ma entro la tolleranza di calcolo "
                f"({err_bound + space_tol:.2f} mm)",
                hoists=(i, j),
                t=t,
                value=sep,
                bound=required,
                slack=sep - required,
            )
        elif warn_margin > 0 and sep < required + warn_margin:
            add(
                "collision",
                "warning",
                f"{chi_e_dove} -- distanza {sep:.0f} mm, al limite: solo "
                f"{sep - required:.0f} mm di margine oltre il minimo richiesto",
                hoists=(i, j),
                t=t,
                value=sep,
                bound=required,
                slack=sep - required,
            )

    return dict(
        min_sep=min_sep,
        min_t=min_t,
        min_pair=min_pair,
        err_bound=err_bound,
        n_samples=len(times),
    )
