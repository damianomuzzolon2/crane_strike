"""
plotting.py
-----------
Disegna il ciclogramma: posizione lungo la rotaia (asse Y) in funzione del
tempo entro il ciclo (asse X), per ciascun carroponte. Il grafico mostra
2 cicli consecutivi affiancati per rendere visivamente evidente che il
pattern e' periodico.
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from kinematics import position_profile
from model import ProblemData, Solution, Segment

# Il colore dice UNA cosa sola: di quale carroponte e' la linea. Un colore per
# ogni tipo di tratto (carico, vuoto, attesa, presa, rilascio) piu' un colore
# per carroponte faceva un arcobaleno in cui non si seguiva piu' nessuna
# traiettoria. L'unica altra distinzione utile e' se il pezzo e' appeso o no,
# ed e' affidata al tratteggio; lo spessore e' uguale per tutti.
_LARGHEZZA = 2.2

_STYLE = {
    # Con il pezzo appeso. La presa e il rilascio sono movimenti verticali:
    # il carroponte sta fermo sopra la vasca, quindi si vedono come le spalle
    # orizzontali agli estremi del trasferimento. Stesso tratto continuo,
    # perche' sono la stessa cosa: il pezzo e' in mano al carroponte.
    "loaded": dict(linewidth=_LARGHEZZA, zorder=3),
    "pick": dict(linewidth=_LARGHEZZA, solid_capstyle="butt", zorder=3),
    "release": dict(linewidth=_LARGHEZZA, solid_capstyle="butt", zorder=3),
    # Senza pezzo: rientro a vuoto e attesa sopra la vasca, tratteggiati.
    "empty": dict(linewidth=_LARGHEZZA, linestyle="--", zorder=2),
    "wait": dict(linewidth=_LARGHEZZA, linestyle="--", zorder=2),
}
_HOIST_COLORS = ["#c0392b", "#2980b9", "#27ae60", "#8e44ad", "#d35400", "#16a085"]

# Stati che dichiarano esplicitamente l'assenza di una soluzione: gli unici
# per cui non c'e' proprio niente da disegnare.
_STATI_SENZA_SOLUZIONE = {"INFEASIBLE", "MODEL_INVALID", "UNKNOWN", "NOT_SOLVED"}


def _sample_segment(seg: Segment, n=25):
    """Restituisce array (t, x) campionati lungo il segmento, usando il
    profilo cinematico reale (accelerazione/decelerazione) per i tratti
    'loaded'/'empty', e una linea piatta per i tratti 'wait'."""
    if seg.kind == "wait" or seg.kin is None:
        return np.array([seg.t_start, seg.t_end]), np.array([seg.x_start, seg.x_end])

    ts = np.linspace(seg.t_start, seg.t_end, n)
    distance = seg.x_end - seg.x_start
    xs = np.array(
        [
            seg.x_start
            + math_sign(distance)
            * position_profile(t - seg.t_start, abs(distance), seg.kin)
            for t in ts
        ]
    )
    return ts, xs


def math_sign(v: float) -> float:
    return 1.0 if v >= 0 else -1.0


def lettura_coordinate(t: float, x: float) -> str:
    """Cosa scrivere accanto al puntatore, in basso nella finestra.

    Serve sovrascrivere quella predefinita perche' le etichette dell'asse Y
    sono i nomi delle vasche: matplotlib prova a formattare la quota con lo
    stesso formattatore e, fuori da un nome di vasca, restituisce una stringa
    vuota -- si finisce per leggere "(x, y) = (175.0, )"."""
    return f"t = {t:.1f} s      posizione = {x:.0f} mm"


def plot_cyclogram(
    data: ProblemData,
    solution: Solution,
    n_cycles: int = 2,
    title: str = "Ciclogramma carroponti",
    ax=None,
    save_path: str | None = None,
):
    # Si disegna tutto cio' che ha dei segmenti, qualunque sia lo stato: una
    # soluzione modificata a mano ("MANUALE") o una proposta di partenza
    # ("PROPOSTA") sono esattamente i casi in cui guardare il ciclogramma
    # serve di piu'. Il filtro va sugli stati che dichiarano di NON avere una
    # soluzione -- stessa convenzione di verify._STATI_SENZA_SOLUZIONE.
    if solution.status in _STATI_SENZA_SOLUZIONE or not solution.segments_per_hoist:
        raise ValueError(f"Nessuna soluzione da disegnare (status={solution.status})")

    T = solution.T
    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=(13, 7))

    # -- linee guida orizzontali, e nomi delle vasche sull'asse -------------
    # I nomi vanno messi COME etichette dell'asse, non come testo accanto:
    # scritti a mano finirebbero sopra i valori numerici, e su una finestra
    # stretta diventano illeggibili. Chi legge un ciclogramma cerca la vasca,
    # non la quota in millimetri.
    etichette: dict[float, list[str]] = {}
    for st in data.route:
        y = data.tanks[st.tank_id].position
        etichette.setdefault(y, [])
        if st.tank_id not in etichette[y]:
            etichette[y].append(st.tank_id)
    for y in etichette:
        ax.axhline(y, color="#dddddd", linewidth=1, zorder=0)
    quote = sorted(etichette)
    ax.set_yticks(quote)
    ax.set_yticklabels(
        [f"{' / '.join(etichette[y])}\n{y:.0f} mm" for y in quote], fontsize=8
    )

    # -- traiettorie di ciascun carroponte, ripetute su n_cycles periodi ----
    for h, segs in enumerate(solution.segments_per_hoist):
        color = _HOIST_COLORS[h % len(_HOIST_COLORS)]
        for cycle in range(n_cycles):
            offset = cycle * T
            for seg in segs:
                ts, xs = _sample_segment(seg)
                ts = ts + offset
                ax.plot(ts, xs, color=color, **_STYLE[seg.kind])

    # -- linee verticali di separazione fra cicli ---------------------------
    for cycle in range(n_cycles + 1):
        ax.axvline(cycle * T, color="#999999", linewidth=1, linestyle=":", zorder=0)

    ax.set_xlabel("tempo [s]")
    ax.set_ylabel("posizione lungo la rotaia")
    ax.set_title(f"{title}  —  takt time T = {T:.2f} s")
    ax.set_xlim(0.0, n_cycles * T * 1.01)

    # -- legenda --------------------------------------------------------
    # Due sole voci sul tipo di tratto, piu' una per carroponte. Il grigio
    # neutro dice che vale per tutti i carroponti: il colore lo si legge sotto.
    legend_elems = [
        Line2D(
            [0],
            [0],
            color="#333333",
            lw=_LARGHEZZA,
            label="con il pezzo (presa, trasferimento, rilascio)",
        ),
        Line2D(
            [0],
            [0],
            color="#333333",
            lw=_LARGHEZZA,
            linestyle="--",
            label="senza pezzo (rientro a vuoto, attesa)",
        ),
    ]
    for h in range(data.n_hoists):
        legend_elems.append(
            Patch(
                color=_HOIST_COLORS[h % len(_HOIST_COLORS)], label=f"Carroponte {h+1}"
            )
        )
    ax.legend(handles=legend_elems, loc="upper right", fontsize=8, framealpha=0.9)

    ax.grid(axis="x", color="#f0f0f0")
    ax.format_coord = lettura_coordinate

    if save_path:
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
    if own_fig:
        return ax.figure
    return ax
