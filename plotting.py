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
    # Tutti i tratti sono LINEA CONTINUA, che il carroponte sia carico o
    # scarico. Il tratteggio distingueva le due cose, ed e' stato tolto: da
    # quando ci sono i punti sugli eventi, la traiettoria si legge come una
    # linea sola che passa di vasca in vasca, e spezzarla a meta' del giro
    # faceva sembrare due cose diverse quello che e' il percorso di un carro.
    #
    # Si perde la distinzione fra carico e scarico sul disegno: si ricava dal
    # verso -- il carroponte sale la linea col pezzo e la ridiscende a vuoto --
    # e dal foglio Movimenti, che la scrive tratto per tratto.
    "loaded": dict(linewidth=_LARGHEZZA, zorder=3),
    "pick": dict(linewidth=_LARGHEZZA, solid_capstyle="butt", zorder=3),
    "release": dict(linewidth=_LARGHEZZA, solid_capstyle="butt", zorder=3),
    "empty": dict(linewidth=_LARGHEZZA, zorder=2),
    "wait": dict(linewidth=_LARGHEZZA, zorder=2),
    # salita/discesa del gancio scarico su una posizione di svincolo: il
    # carroponte e' fermo, orizzontalmente non si muove
    "lift_empty": dict(linewidth=_LARGHEZZA, zorder=2),
}
_HOIST_COLORS = ["#c0392b", "#2980b9", "#27ae60", "#8e44ad", "#d35400", "#16a085"]

# I tratti in cui il carroponte trasla davvero lungo la rotaia. Presa,
# rilascio, attesa e corse verticali no: li' e' fermo.
_KINEMATIC_KINDS = {"loaded", "empty"}

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


def _durata_fase(fasi, nome: str) -> float:
    return sum(f.duration for f in fasi if f.name == nome)


def _sollevamento(data: ProblemData, stazione: int) -> float:
    """Quanto dura il sollevamento del telaio nella presa a quella stazione."""
    return _durata_fase(data.pick_phases(stazione), "sollevamento del telaio")


def _immersione(data: ProblemData, stazione: int) -> float:
    """Quanto dura l'immersione del telaio nel rilascio a quella stazione."""
    return _durata_fase(data.release_phases(stazione), "immersione del telaio")


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
    #
    # Sulle traiettorie si marcano gli istanti in cui succede qualcosa:
    # l'AGGANCIO e lo SGANCIO del telaio -- quando il pezzo diventa del
    # carroponte e quando smette di esserlo -- e la PARTENZA e l'ARRIVO di ogni
    # traslazione.
    #
    # Tutti con lo stesso punto, e senza una voce in legenda. Cosa sia ogni
    # punto lo dice gia' la traiettoria: se li' la linea diventa obliqua il
    # carro parte, se resta piatta il telaio cambia mano. Due simboli diversi
    # avrebbero chiesto all'occhio di leggere una differenza che il disegno
    # mostra da solo, e una voce in legenda di spiegare una cosa che si capisce
    # guardandola. Si e' provato: era peggio.
    #
    # Marcare invece OGNI cambio di fase avrebbe riempito la linea di punti --
    # fine discesa, fine aggancio, fine sollevamento, fine sgocciolamento -- e
    # a quel punto non si sarebbe piu' visto niente.
    for h, segs in enumerate(solution.segments_per_hoist):
        color = _HOIST_COLORS[h % len(_HOIST_COLORS)]
        eventi_t, eventi_x = [], []
        for seg in segs:
            if seg.kind == "pick":
                # il telaio si stacca dal fondo quando finisce l'aggancio
                eventi_t.append(
                    seg.t_end
                    - data.drain_time_at(seg.move)
                    - _sollevamento(data, seg.move)
                )
                eventi_x.append(seg.x_start)
            elif seg.kind == "release":
                # e torna alla vasca quando finisce l'immersione
                eventi_t.append(seg.t_start + _immersione(data, seg.move + 1))
                eventi_x.append(seg.x_end)
            elif seg.kind in _KINEMATIC_KINDS and seg.x_end != seg.x_start:
                # una traslazione vera: si parte da una parte e si arriva
                # dall'altra. I tratti di lunghezza nulla non sono partenze.
                eventi_t.extend([seg.t_start, seg.t_end])
                eventi_x.extend([seg.x_start, seg.x_end])
        for cycle in range(n_cycles):
            offset = cycle * T
            for seg in segs:
                ts, xs = _sample_segment(seg)
                ts = ts + offset
                ax.plot(ts, xs, color=color, **_STYLE[seg.kind])
            if eventi_t:
                ax.plot(
                    [t + offset for t in eventi_t],
                    eventi_x,
                    linestyle="none",
                    marker="o",
                    markersize=6.0,
                    markerfacecolor=color,
                    markeredgecolor="white",
                    markeredgewidth=0.9,
                    zorder=5,
                )

    # -- linee verticali di separazione fra cicli ---------------------------
    for cycle in range(n_cycles + 1):
        ax.axvline(cycle * T, color="#999999", linewidth=1, linestyle=":", zorder=0)

    ax.set_xlabel("tempo [s]")
    ax.set_ylabel("posizione lungo la rotaia")
    ax.set_title(f"{title}  —  takt time T = {T:.2f} s")
    ax.set_xlim(0.0, n_cycles * T * 1.01)

    # -- legenda --------------------------------------------------------
    # Solo i carroponti. Le due voci sul tipo di tratto -- "con il pezzo",
    # "senza pezzo" -- descrivevano il tratteggio, che non c'e' piu'.
    legend_elems = []
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
