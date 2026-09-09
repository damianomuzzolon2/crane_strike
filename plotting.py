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
    # andata e ritorno fra il punto di cambio quota e la stazione, dentro una
    # presa o un rilascio: e' una traslazione vera, e si disegna come tale
    "quota": dict(linewidth=_LARGHEZZA, zorder=3),
}
_HOIST_COLORS = ["#c0392b", "#2980b9", "#27ae60", "#8e44ad", "#d35400", "#16a085"]

# I tratti in cui il carroponte trasla davvero lungo la rotaia. Presa,
# rilascio, attesa e corse verticali no: li' e' fermo.
_KINEMATIC_KINDS = {"loaded", "empty", "quota"}

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


def _aggancio_dall_inizio_presa(data: ProblemData, stazione: int) -> float:
    """Quando il telaio si stacca dal fondo, contato dall'INIZIO della presa.

    Si legge dalle fasi, non sottraendo sgocciolamento e sollevamento dalla
    fine: con una zona di cambio quota la presa contiene anche due traslazioni
    e una seconda salita, e il conto all'indietro metterebbe il punto in un
    istante in cui il carroponte non e' nemmeno sopra la stazione."""
    t = 0.0
    for f in data.pick_phases(stazione):
        if f.name == "sollevamento del telaio":
            break
        t += f.duration
    return t


def _immersione_dall_inizio_rilascio(data: ProblemData, stazione: int) -> float:
    """Quando il telaio torna in vasca, contato dall'INIZIO del rilascio."""
    t = 0.0
    for f in data.release_phases(stazione):
        t += f.duration
        if f.name == "immersione del telaio":
            break
    return t


def eventi_del_trasporto(
    data: ProblemData,
    k: int,
    inizio_presa: float,
    x_partenza: float,
    x_arrivo: float,
) -> list[tuple[float, float]]:
    """I quattro istanti in cui succede qualcosa durante la mossa k, con la
    posizione a cui vanno disegnati.

    Nell'ordine: l'AGGANCIO (il telaio si stacca dal fondo e il pezzo diventa
    del carroponte), la PARTENZA della traslazione, l'ARRIVO, e l'IMMERSIONE
    (il telaio torna in vasca e il pezzo smette di essere del carroponte).

    E' l'unica definizione di 'dove succede qualcosa', e la usano tutti e tre i
    disegni: le traiettorie del ciclogramma, quelle dei carroponti sul pettine,
    e il pettine stesso. Averne una sola non e' pignoleria: sono gli stessi
    istanti visti dal lato del carroponte e dal lato del pezzo, e se i due
    disegni li mettessero in punti diversi, chi li confronta -- che e' il
    motivo per cui il pettine e il ciclogramma si guardano insieme -- non ci si
    ritroverebbe.

    Le due posizioni della traslazione si passano da fuori perche' cambiano
    con il disegno: sul giro del carroponte sono i punti di APPROCCIO, sul
    pettine sono le vasche. Aggancio e immersione invece avvengono sempre
    sopra la stazione, che il carroponte ci arrivi da un punto di cambio quota
    o no."""
    presa = data.pick_time_at(k)
    partenza = inizio_presa + presa
    arrivo = partenza + data.horizontal_loaded_seconds(k)
    return [
        (inizio_presa + _aggancio_dall_inizio_presa(data, k),
         data.station_position(k)),
        (partenza, x_partenza),
        (arrivo, x_arrivo),
        (arrivo + _immersione_dall_inizio_rilascio(data, k + 1),
         data.station_position(k + 1)),
    ]


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
            if seg.kind == "loaded" and seg.move is not None:
                # I quattro istanti della mossa si ricavano dal tratto A
                # CARICO, che c'e' sempre ed e' uno solo per mossa: presa e
                # rilascio invece possono essere spezzati in piu' tratti da una
                # zona di cambio quota, e prenderli uno per uno
                # moltiplicherebbe i punti.
                k = seg.move
                for t, x in eventi_del_trasporto(
                    data,
                    k,
                    seg.t_start - data.pick_time_at(k),
                    seg.x_start,
                    seg.x_end,
                ):
                    eventi_t.append(t)
                    eventi_x.append(x)
            elif seg.kind in _KINEMATIC_KINDS and seg.x_end != seg.x_start:
                # una traslazione vera che non sia il trasporto -- il rientro a
                # vuoto, o un vai-e-torna di cambio quota: si parte da una parte
                # e si arriva dall'altra. I tratti di lunghezza nulla non sono
                # partenze.
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
