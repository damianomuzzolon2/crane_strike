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
from matplotlib.transforms import offset_copy

from avvio import Avvio, trova_avvio
from kinematics import position_profile
from model import ProblemData, Solution, Segment

# Il colore dice UNA cosa sola: di quale carroponte e' la linea. Un colore per
# ogni tipo di tratto (carico, vuoto, attesa, presa, rilascio) piu' un colore
# per carroponte faceva un arcobaleno in cui non si seguiva piu' nessuna
# traiettoria. L'unica altra distinzione utile e' se il pezzo e' appeso o no,
# ed e' affidata al tratteggio; lo spessore e' uguale per tutti.
_LARGHEZZA = 2.2
# Il pezzo fermo in vasca: spesso come le traiettorie, ma GRIGIO. Col colore
# del carroponte che ce l'aveva lasciato, nelle vasche di confine un pezzo
# lasciato da un carro e ripreso dall'altro aveva il colore di uno solo dei
# due, e le righe colorate si confondevano con le traiettorie. Il grigio non
# e' quello del pettine (#9a9a9a), che nella vista Modifica vuol dire "ancora
# da assegnare", e nemmeno quello delle righe delle vasche (#dddddd).
_COLORE_PEZZO = "#b8b8b8"

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


def inizio_sgocciolamento(
    data: ProblemData, stazione: int, inizio_presa: float
) -> tuple[float, float] | None:
    """Quando e dove finisce il sollevamento del telaio e comincia lo
    sgocciolamento, nella presa alla stazione data. None se la vasca non
    sgocciola: il punto cadrebbe sulla partenza, o a meta' di una salita.

    La posizione e' quella della fase: con una zona di cambio quota il telaio
    sgocciola sopra la stazione, non sul punto di cambio quota."""
    t = inizio_presa
    for f in data.pick_phases(stazione):
        if f.name == "sgocciolamento":
            if f.duration <= 0:
                return None
            x = f.x_start if f.x_start is not None else data.station_position(stazione)
            return t, x
        t += f.duration
    return None


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


def corse_verticali(
    data: ProblemData, segs: list[Segment]
) -> list[tuple[float, float, bool]]:
    """Dove il gancio sale o scende, sulla traiettoria di UN carroponte.

    Una tupla per corsa: (istante a meta' corsa, posizione, sale). Sono tre
    le fonti, e in tutte il verso e' un DATO, non una deduzione:

      - la PRESA e il RILASCIO di ogni mossa: le fasi (`pick_phases`,
        `release_phases`) dicono quota iniziale e finale di ciascun movimento.
        Il sollevamento del telaio sale, l'immersione scende; con una zona di
        cambio quota ci sono anche le salite e le discese intermedie, e la
        posizione e' quella della fase -- il punto di cambio quota, non la
        vasca;
      - le corse a vuoto sugli SVINCOLI: i tratti 'lift_empty', che il verso
        lo portano scritto (`Segment.sale`).

    I tempi della presa si contano dall'inizio, ricavato dal tratto a carico
    come per `eventi_del_trasporto`, e quelli del rilascio dall'arrivo: il
    tratto a carico c'e' sempre ed e' uno per mossa, mentre presa e rilascio
    possono essere spezzati da una zona di cambio quota.

    Le fasi senza durata o senza dislivello -- aggancio, sgancio,
    sgocciolamento, o una vasca senza corsa -- non sono corse, e non ci
    sono."""
    fuori = []
    for seg in segs:
        if seg.kind == "loaded" and seg.move is not None:
            k = seg.move
            for fasi, t, stazione in (
                (data.pick_phases(k), seg.t_start - data.pick_time_at(k), k),
                (data.release_phases(k + 1), seg.t_end, k + 1),
            ):
                for f in fasi:
                    if f.duration > 0 and f.z_end != f.z_start:
                        x = (
                            f.x_start
                            if f.x_start is not None
                            else data.station_position(stazione)
                        )
                        fuori.append((t + f.duration / 2, x, f.z_end > f.z_start))
                    t += f.duration
        elif seg.kind == "lift_empty" and seg.sale is not None:
            fuori.append(((seg.t_start + seg.t_end) / 2, seg.x_start, seg.sale))
    return fuori


def pezzi_in_vasca(
    data: ProblemData, solution: Solution
) -> list[tuple[int, float, float]]:
    """Quando il pezzo sta in ogni vasca intermedia.

    Una tupla per stazione: (stazione, entrata, uscita). L'ENTRATA
    e' l'immersione del trasporto che ce lo porta, l'USCITA l'aggancio di
    quello che lo riprende: gli stessi due pallini che il ciclogramma marca
    sulle traiettorie, calcolati da `eventi_del_trasporto`, cosi' la linea del
    pezzo comincia e finisce esattamente su di loro.

    I tempi vengono da `actual_time`, che e' ASSOLUTO, e non dai segmenti, che
    sono noti solo modulo T: un pezzo che resta in vasca piu' di un takt time
    sarebbe altrimenti indistinguibile da uno che ci resta pochi secondi. Per
    la stessa ragione l'uscita puo' cadere oltre T, o l'intervallo durare piu'
    di un periodo -- tocca a chi disegna ripeterlo.

    Una vasca compare solo se almeno uno dei due trasporti -- quello che ci
    porta il pezzo o quello che lo riprende -- e' di un carroponte. Nel
    ciclogramma di una composizione a mano ancora a meta' i trasporti non
    assegnati non si vedono, e la sosta fra due di loro non deve vedersi
    nemmeno lei: sarebbe un pezzo che nessuno ha portato li'.

    Carico e scarico sono esclusi: li' il pezzo non viene depositato da un
    carroponte, o non viene ripreso."""
    at = solution.actual_time
    if len(at) != data.n_moves:
        return []
    assegnate = {
        seg.move
        for segs in solution.segments_per_hoist
        for seg in segs
        if seg.kind == "loaded" and seg.move is not None
    }
    fuori = []
    for s in range(1, data.n_moves):
        if s - 1 not in assegnate and s not in assegnate:
            continue
        entrata = eventi_del_trasporto(
            data, s - 1, at[s - 1],
            data.station_position(s - 1), data.station_position(s),
        )[3][0]
        uscita = at[s] + _aggancio_dall_inizio_presa(data, s)
        fuori.append((s, entrata, uscita))
    return fuori


def math_sign(v: float) -> float:
    return 1.0 if v >= 0 else -1.0


def lettura_coordinate(t: float, x: float) -> str:
    """Cosa scrivere accanto al puntatore, in basso nella finestra.

    Serve sovrascrivere quella predefinita perche' le etichette dell'asse Y
    sono i nomi delle vasche: matplotlib prova a formattare la quota con lo
    stesso formattatore e, fuori da un nome di vasca, restituisce una stringa
    vuota -- si finisce per leggere "(x, y) = (175.0, )"."""
    return f"t = {t:.1f} s      posizione = {x:.0f} mm"


def disegna_avvio(ax, avvio: Avvio | None, T: float, n_cycles: int = 1):
    """La LINEA NERA del punto di avvio, su assi gia' disegnati.

    E' l'unica cosa del disegno che non racconta il ciclogramma ma dice cosa
    farne: l'istante da cui la linea si mette in marcia, con i carroponti fermi
    in basso dove la linea li incrocia. Nera -- nessuna traiettoria usa quel
    colore -- e continua, per non confondersi con i separatori puntinati fra un
    ciclo e l'altro.

    Si ripete in ogni ciclo disegnato, come tutto il resto: l'istante di avvio
    e' una fase del ciclo, non un momento solo. L'etichetta invece si scrive una
    volta, sul primo: ripeterla non aggiungerebbe niente e coprirebbe il disegno.

    Sta qui e non in `avvio.py` perche' quel modulo legge e basta; ed e' una
    funzione a se' perche' la stessa linea va anche sul PETTINE, che si disegna
    altrove -- e due disegni della stessa cosa prima o poi divergono."""
    if avvio is None:
        return
    for cycle in range(max(1, n_cycles)):
        ax.axvline(avvio.t + cycle * T, color="#000000", linewidth=1.4, zorder=4)
    etichetta = "avvio" if avvio.esatto else "avvio (approssimato)"
    if avvio.totale > 1:
        etichetta += f"  {avvio.indice + 1}/{avvio.totale}"
    ax.annotate(
        etichetta,
        xy=(avvio.t, 1.0),
        xycoords=("data", "axes fraction"),
        xytext=(3, -11),
        textcoords="offset points",
        fontsize=8,
        color="#000000",
    )


def plot_cyclogram(
    data: ProblemData,
    solution: Solution,
    n_cycles: int = 2,
    title: str = "Ciclogramma carroponti",
    ax=None,
    save_path: str | None = None,
    avvio: Avvio | None = None,
):
    """`avvio`: quale dei punti di avvio equivalenti segnare. Assente = il
    primo, che e' quello che si scrive anche nel file dei risultati. La finestra
    passa quello che l'utente sta guardando: il PNG che esce da li' deve essere
    quello che ha davanti, non un altro."""
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
    # fine discesa, fine aggancio, fine sgocciolamento -- e a quel punto non si
    # sarebbe piu' visto niente. L'unica eccezione e' la FINE DEL SOLLEVAMENTO:
    # sul tratto piatto della presa separa la salita (quella con la freccia)
    # dallo sgocciolamento, che altrimenti non si distinguerebbero.
    sopra = offset_copy(ax.transData, fig=ax.figure, y=9.0, units="points")
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
                inizio_presa = seg.t_start - data.pick_time_at(k)
                for t, x in eventi_del_trasporto(
                    data,
                    k,
                    inizio_presa,
                    seg.x_start,
                    seg.x_end,
                ):
                    eventi_t.append(t)
                    eventi_x.append(x)
                sgocciolamento = inizio_sgocciolamento(data, k, inizio_presa)
                if sgocciolamento is not None:
                    eventi_t.append(sgocciolamento[0])
                    eventi_x.append(sgocciolamento[1])
            elif seg.kind in _KINEMATIC_KINDS and seg.x_end != seg.x_start:
                # una traslazione vera che non sia il trasporto -- il rientro a
                # vuoto, o un vai-e-torna di cambio quota: si parte da una parte
                # e si arriva dall'altra. I tratti di lunghezza nulla non sono
                # partenze.
                eventi_t.extend([seg.t_start, seg.t_end])
                eventi_x.extend([seg.x_start, seg.x_end])
        # Le corse verticali: una freccetta APPENA SOPRA il tratto piatto in
        # cui il gancio sale o scende, a meta' della corsa. Sul disegno quei
        # tratti sono piatti come un'attesa -- il carroponte e' fermo lungo la
        # rotaia -- e senza la freccia non si distingue un gancio che lavora da
        # un carro che aspetta. Sopra la linea e non sopra il punto, spostata
        # di qualche punto tipografico: a qualunque ingrandimento resta
        # attaccata al tratto senza coprirlo.
        corse = corse_verticali(data, segs)
        frecce = {
            simbolo: (
                [t for t, _, sale in corse if sale is verso],
                [x for _, x, sale in corse if sale is verso],
            )
            for simbolo, verso in ((r"$\uparrow$", True), (r"$\downarrow$", False))
        }
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
            for simbolo, (frecce_t, frecce_x) in frecce.items():
                if frecce_t:
                    ax.plot(
                        [t + offset for t in frecce_t],
                        frecce_x,
                        linestyle="none",
                        marker=simbolo,
                        markersize=8.0,
                        color=color,
                        transform=sopra,
                        zorder=5,
                    )

    # -- i pezzi in vasca ---------------------------------------------------
    # Una linea grigia, spessa come le traiettorie, dal pallino
    # dell'immersione a quello dell'aggancio. Dice dove sta il pezzo mentre
    # nessun carro lo tiene, che dalle sole traiettorie non si vede: il carro
    # se ne va, e la vasca resta una riga come tutte le altre.
    #
    # Grigia e non del colore di un carroponte: il colore dice di chi e' una
    # traiettoria, e il pezzo in vasca non e' di nessuno -- nelle vasche di
    # confine lo lascia un carro e lo riprende l'altro.
    #
    # Sotto le traiettorie: quando il carro resta fermo sopra la vasca la sua
    # linea copre quella del pezzo, ed e' giusto cosi' -- li' si guarda il
    # carro.
    #
    # L'intervallo si ripete ogni T. Se dura piu' di un periodo le copie si
    # accavallano sulla stessa riga: sono pezzi diversi nella stessa vasca a
    # capienza multipla, e la riga piena dice proprio che la vasca non si
    # svuota mai. Un disegno solo, con i NaN a separare i tratti, tagliato alla
    # fine dell'ultimo ciclo, dove finiscono le traiettorie.
    fine = n_cycles * T
    linea_t, linea_x = [], []
    for s, entrata, uscita in pezzi_in_vasca(data, solution):
        y = data.station_position(s)
        m = int(np.floor(-uscita / T))
        while entrata + m * T < fine:
            a, b = max(entrata + m * T, 0.0), min(uscita + m * T, fine)
            if b > a:
                linea_t.extend([a, b, np.nan])
                linea_x.extend([y, y, np.nan])
            m += 1
    if linea_t:
        ax.plot(
            linea_t,
            linea_x,
            color=_COLORE_PEZZO,
            linewidth=_LARGHEZZA,
            solid_capstyle="butt",
            zorder=1,
        )

    # -- linee verticali di separazione fra cicli ---------------------------
    for cycle in range(n_cycles + 1):
        ax.axvline(cycle * T, color="#999999", linewidth=1, linestyle=":", zorder=0)

    # -- il punto di avvio --------------------------------------------------
    disegna_avvio(
        ax, trova_avvio(data, solution) if avvio is None else avvio, T, n_cycles
    )

    ax.set_xlabel("tempo [s]")
    ax.set_ylabel("posizione lungo la rotaia")
    ax.set_title(f"{title}  —  takt time T = {T:.2f} s")
    ax.set_xlim(0.0, n_cycles * T * 1.01)

    # -- legenda --------------------------------------------------------
    # I carroponti, e la linea grigia del pezzo. Le due voci sul tipo di
    # tratto -- "con il pezzo", "senza pezzo" -- descrivevano il tratteggio,
    # che non c'e' piu'. Quella del pezzo invece resta: una riga di vasca
    # grigia non si spiega da sola come un pallino su una traiettoria.
    legend_elems = []
    for h in range(data.n_hoists):
        legend_elems.append(
            Patch(
                color=_HOIST_COLORS[h % len(_HOIST_COLORS)], label=f"Carroponte {h+1}"
            )
        )
    if linea_t:
        legend_elems.append(
            Line2D(
                [0], [0], color=_COLORE_PEZZO, linewidth=_LARGHEZZA,
                label="pezzo in vasca",
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
