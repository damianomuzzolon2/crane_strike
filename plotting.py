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

_STYLE = {
    "loaded": dict(color="#c0392b", linewidth=2.6, zorder=3),
    "empty": dict(color="#2980b9", linewidth=1.6, linestyle="--", zorder=2),
    "wait": dict(color="#7f8c8d", linewidth=1.6, zorder=1),
    # fasi verticali: il carroponte e' fermo sopra la vasca
    "pick": dict(color="#e67e22", linewidth=5.0, solid_capstyle="butt", zorder=4),
    "release": dict(color="#8e44ad", linewidth=5.0, solid_capstyle="butt", zorder=4),
}
# Solo questi tratti vengono ricolorati col colore del carroponte: le fasi
# verticali e le attese mantengono un colore proprio, altrimenti sparirebbero.
_KINEMATIC_KINDS = {"loaded", "empty"}
_HOIST_COLORS = ["#c0392b", "#2980b9", "#27ae60", "#8e44ad", "#d35400", "#16a085"]


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


def plot_cyclogram(
    data: ProblemData,
    solution: Solution,
    n_cycles: int = 2,
    title: str = "Ciclogramma carroponti",
    ax=None,
    save_path: str | None = None,
):
    if solution.status not in ("OPTIMAL", "FEASIBLE"):
        raise ValueError(f"Nessuna soluzione da disegnare (status={solution.status})")

    T = solution.T
    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=(13, 7))

    # -- linee guida orizzontali per ciascuna vasca -------------------------
    for st in data.route:
        y = data.tanks[st.tank_id].position
        ax.axhline(y, color="#dddddd", linewidth=1, zorder=0)
        ax.text(
            -0.015 * n_cycles * T,
            y,
            st.tank_id,
            va="center",
            ha="right",
            fontsize=9,
            color="#555555",
        )

    # -- traiettorie di ciascun carroponte, ripetute su n_cycles periodi ----
    for h, segs in enumerate(solution.segments_per_hoist):
        color = _HOIST_COLORS[h % len(_HOIST_COLORS)]
        for cycle in range(n_cycles):
            offset = cycle * T
            for seg in segs:
                ts, xs = _sample_segment(seg)
                ts = ts + offset
                style = dict(_STYLE[seg.kind])
                if seg.kind in _KINEMATIC_KINDS:
                    style["color"] = color
                ax.plot(ts, xs, **style)

    # -- linee verticali di separazione fra cicli ---------------------------
    for cycle in range(n_cycles + 1):
        ax.axvline(cycle * T, color="#999999", linewidth=1, linestyle=":", zorder=0)

    ax.set_xlabel("tempo [s]")
    ax.set_ylabel("posizione lungo la rotaia [m]")
    ax.set_title(f"{title}  —  takt time T = {T:.2f} s")
    ax.set_xlim(-0.02 * n_cycles * T, n_cycles * T * 1.01)

    # -- legenda --------------------------------------------------------
    legend_elems = [
        Line2D([0], [0], color="#333333", lw=2.6, label="con pezzo (carico)"),
        Line2D(
            [0],
            [0],
            color="#333333",
            lw=1.6,
            linestyle="--",
            label="senza pezzo (vuoto)",
        ),
        Line2D([0], [0], color="#7f8c8d", lw=1.6, label="in attesa"),
    ]
    # le voci sulle fasi verticali compaiono solo se sono davvero in uso
    if any(
        seg.kind == "pick" for segs in solution.segments_per_hoist for seg in segs
    ):
        legend_elems.append(
            Line2D([0], [0], color="#e67e22", lw=5.0, label="presa (emersione)")
        )
    if any(
        seg.kind == "release" for segs in solution.segments_per_hoist for seg in segs
    ):
        legend_elems.append(
            Line2D([0], [0], color="#8e44ad", lw=5.0, label="rilascio (immersione)")
        )
    for h in range(data.n_hoists):
        legend_elems.append(
            Patch(
                color=_HOIST_COLORS[h % len(_HOIST_COLORS)], label=f"Carroponte {h+1}"
            )
        )
    ax.legend(handles=legend_elems, loc="upper right", fontsize=8, framealpha=0.9)

    ax.grid(axis="x", color="#f0f0f0")

    if save_path:
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
    if own_fig:
        return ax.figure
    return ax
