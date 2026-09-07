"""
simulazione.py
--------------
La linea vista DI FRONTE, in movimento: i carroponti che scorrono sulla
rotaia, calano il gancio in una vasca, tirano su il telaio, lo portano alla
vasca successiva e ce lo immergono.

E' lo stesso ciclogramma di sempre, letto in un altro modo. Il ciclogramma e'
un diagramma tempo-posizione: dice tutto, ma bisogna saperlo leggere, e un
errore di composizione ci si nasconde bene. Qui invece si guarda la linea come
la si guarderebbe dal capannone -- e un carroponte che passa attraverso un
altro, o un pezzo che resta appeso mentre nessuno lo tiene, si vede senza
doverlo cercare.

Non calcola niente di nuovo e non decide niente: legge la soluzione che c'e'.
Tutto quello che mostra viene da `Solution.segments_per_hoist` (i carroponti) e
da `Solution.actual_time` (i pezzi), cioe' esattamente gli oggetti che
disegnano il ciclogramma. Se i due disegni dicessero cose diverse, sarebbe un
guasto.

Il modulo e' diviso in due:
  - `Simulazione`, che dato un istante dice dove sta ogni cosa. Non importa
    tkinter, quindi si prova senza finestre;
  - `FinestraSimulazione`, la finestra che la anima.
"""

from __future__ import annotations

import bisect
import math
import warnings
from dataclasses import dataclass
from typing import Optional

import tkinter as tk
from tkinter import ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.path import Path
from matplotlib.text import Text

from kinematics import Kinematics, position_profile
from model import ProblemData, Solution
from plotting import _HOIST_COLORS

# Colori del disegno. Il colore dei carroponti e' lo stesso del ciclogramma
# (_HOIST_COLORS): la simulazione e il grafico si guardano uno accanto
# all'altro, e il carroponte 1 deve essere rosso in tutti e due.
_SFONDO = "#fbfcfd"
_COLORE_VASCA = "#eef4f8"
_BORDO_VASCA = "#5f7d99"
_COLORE_PAVIMENTO = "#e4e4e2"
_BORDO_PAVIMENTO = "#b9b9b4"
_COLORE_ACCIAIO = "#6f7b85"
_COLORE_ROTAIA = "#9aa3ab"
_BORDO_ROTAIA = "#5c666e"
_COLORE_PEZZO = "#8fa0b0"
_BORDO_PEZZO = "#4a5a68"

# Il bagno, uguale in tutte le vasche. Una tinta diversa per vasca si era
# provata: distingue bene, ma sembra dire qualcosa sulla chimica -- che il
# programma non conosce -- e riempie di colore un disegno in cui i colori
# devono voler dire una cosa sola, di quale carroponte si tratta.
_COLORE_BAGNO = "#c9dfee"

# Corsa verticale di riferimento quando nessuna vasca ne dichiara una: serve
# solo a dare un'altezza al disegno. Senza, il grafico avrebbe altezza zero.
_CORSA_PREDEFINITA = 1000.0


# --------------------------------------------------------------------------
# Lo stato della linea a un dato istante
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class StatoCarro:
    """Dove sta un carroponte e cosa sta facendo."""

    carro: int  # numero da mostrare (0-based), non l'indice della zona
    x: float  # [mm] posizione del gancio lungo la rotaia
    z: float  # [mm] quota del gancio: 0 = quota di trasporto, negativa = giu'
    con_pezzo: bool
    fase: str  # etichetta leggibile
    vasca: Optional[str]  # sopra quale vasca, se e' fermo su una
    corsia: float = 0.0  # su quale POSTO della vasca sta lavorando (vedi _corsia)
    # Corsa verticale a cui la quota `z` si riferisce. Serve al disegno, che
    # non mostra i millimetri ma il punto a cui e' arrivata la discesa: senza,
    # bisognerebbe risalire alla vasca dal nome, e mentre il carroponte trasla
    # a gancio basso non e' sopra nessuna vasca.
    corsa: float = 0.0


@dataclass(frozen=True)
class StatoPezzo:
    """Dove sta un pezzo. `indice` e' il numero d'ordine con cui e' entrato in
    linea: lo 0 e' quello entrato all'istante zero, quelli prima hanno indice
    negativo. Serve a distinguerli fra loro, non a fare gerarchie -- fanno
    tutti lo stesso percorso, sfasati di un takt time l'uno dall'altro."""

    indice: int
    x: float
    z: float
    appeso: bool  # in mano a un carroponte (altrimenti e' fermo in vasca)
    vasca: Optional[str]
    corsia: float = 0.0  # in quale POSTO della vasca sta (vedi _corsia)
    corsa: float = 0.0  # corsa verticale a cui `z` si riferisce


@dataclass(frozen=True)
class Istantanea:
    t: float
    carri: list[StatoCarro]
    pezzi: list[StatoPezzo]


@dataclass(frozen=True)
class _Fase:
    """Un tratto della vita di un pezzo: fra t0 e t1 la posizione va da x0 a x1
    e la quota da z0 a z1, ciascuna col proprio profilo."""

    t0: float
    t1: float
    x0: float
    x1: float
    kin_x: Optional[Kinematics]
    z0: float
    z1: float
    kin_z: Optional[Kinematics]
    appeso: bool
    vasca: Optional[str]
    # Da quale tappa a quale tappa. Coincidono in tutte le fasi tranne la
    # traslazione: servono a sapere di quale vasca e' il posto occupato.
    st_da: int
    st_a: int


@dataclass
class _Traiettoria:
    """Il giro di un carroponte, pronto da interrogare a qualunque istante."""

    numero: int  # quale carroponte mostrare
    segmenti: list  # ordinati per istante di inizio
    inizi: list[float]  # i loro t_start, per la ricerca binaria
    t0: float  # da dove parte il ciclo di QUESTO carroponte
    inizi_mossa: dict[int, float]  # mossa -> quando la comincia
    # Gli IMPEGNI: (inizio, fine, mossa) degli intervalli in cui il telaio e'
    # appeso al gancio. Solo li' il carroponte deve stare sul posto del pezzo;
    # fuori e' libero di spostarsi di lato, e lo fa con calma invece di
    # scattare. Ordinati per istante.
    impegni: list[tuple[float, float, int]]
    # Il tempo passato MUOVENDOSI, cumulato lungo il giro: istanti e valore.
    # Serve a spostare il carrello di lato mentre gia' si muove invece che
    # durante le soste (vedi `_corsia_carro`). Le attese non lo fanno crescere.
    mobile_t: list[float]
    mobile_c: list[float]
    # tratto -> (frazione di discesa all'inizio, alla fine, corsa di
    # riferimento), per attese e rientri a vuoto. Vedi `_quote_a_vuoto`.
    quote: dict[int, tuple[float, float, float]]


def _quote_a_vuoto(
    data: ProblemData, segs: list
) -> dict[int, tuple[float, float, float]]:
    """Per attese e rientri a vuoto: la frazione di discesa del gancio
    all'inizio e alla fine del tratto, e la corsa a cui riferirla.

    LA REGOLA: mentre il carroponte TRASLA la quota non cambia. Tutto quello
    che sale o scende avviene da fermi -- ed e' la stessa cosa che racconta il
    ciclogramma, dove un tratto obliquo e' uno spostamento e un tratto piatto e'
    tutto il resto. Una discesa disegnata in mezzo a una traslazione fa dire
    alle due viste due cose diverse, e chi le confronta non ci si ritrova.

    Serve solo con la traslazione a GANCIO BASSO: li' il modello non da' nessun
    tempo alle corse verticali a vuoto, e il dislivello fra due stazioni con
    corse diverse va messo da qualche parte. Senza, i tratti `lift_empty` ci
    sono davvero e la quota la dice il modello.

    Le quote agli estremi si leggono dalle FASI, non dalla quota di riposo del
    telaio: su una zona di cambio quota sono due cose diverse -- il telaio
    riposa a meta' corsa, il gancio ci arriva dal fondo."""

    def stazione_in(x: float):
        for st in range(data.n_stations):
            if abs(data.approach_position(st) - x) < 1e-6:
                return st
        return None

    def corsa_in(x: float) -> float:
        st = stazione_in(x)
        return 0.0 if st is None else data.corsa_verticale(st)

    def frazione(x: float, quale: str) -> float:
        """Dove sta il gancio arrivando a una stazione (prima di una presa) o
        lasciandola (dopo un rilascio), in frazione della corsa."""
        st = stazione_in(x)
        if st is None:
            return 0.0
        corsa = data.corsa_verticale(st)
        if corsa <= 0:
            return 0.0  # niente corsa: il gancio sta alla quota di trasporto
        fasi = data.pick_phases(st) if quale == "arrivo" else data.release_phases(st)
        z = fasi[0].z_start if quale == "arrivo" else fasi[-1].z_end
        return min(1.0, max(0.0, -z / corsa))

    n = len(segs)
    # (frazione all'inizio, alla fine, corsa) dei tratti che NON sono attese
    fisse: dict[int, tuple[float, float, float]] = {}
    for i, s in enumerate(segs):
        if s.kind == "loaded":
            fisse[i] = (0.0, 0.0, 0.0)
        elif s.kind == "release":
            # comincia alla quota di trasporto e finisce dove lascia il gancio
            fisse[i] = (0.0, frazione(s.x_end, "partenza"), corsa_in(s.x_end))
        elif s.kind in ("pick", "quota"):
            # comincia dove il gancio e' arrivato e finisce col telaio in alto
            fisse[i] = (frazione(s.x_start, "arrivo"), 0.0, corsa_in(s.x_start))

    for i, s in enumerate(segs):
        if s.kind != "empty":
            continue
        # Che tratta e', lo dicono gli ESTREMI. Un rientro che deve passare
        # alto e' spezzato in tre traslazioni: una bassa che esce dalla vasca
        # verso lo svincolo, una alta fra i due svincoli, una bassa che entra
        # nella vasca d'arrivo. Gli svincoli non sono posizioni di stazione,
        # quindi si riconoscono per esclusione.
        parte_da_stazione = stazione_in(s.x_start) is not None
        arriva_a_stazione = stazione_in(s.x_end) is not None
        if not parte_da_stazione and not arriva_a_stazione:
            fisse[i] = (0.0, 0.0, 0.0)  # la tratta alta, fra due svincoli
            continue
        if not arriva_a_stazione:  # esce dalla vasca verso lo svincolo
            f = frazione(s.x_start, "partenza")
            fisse[i] = (f, f, corsa_in(s.x_start))
            continue
        if not parte_da_stazione:  # scende dallo svincolo dentro la vasca
            f = frazione(s.x_end, "arrivo")
            fisse[i] = (f, f, corsa_in(s.x_end))
            continue
        # da stazione a stazione: il rientro resta basso tutto il tempo
        partenza = frazione(s.x_start, "partenza")
        arrivo = frazione(s.x_end, "arrivo")
        corsa = max(corsa_in(s.x_start), corsa_in(s.x_end))
        if abs(arrivo - partenza) < 1e-9:
            fisse[i] = (arrivo, arrivo, corsa_in(s.x_end) or corsa)
            continue
        # Le due stazioni vogliono il gancio a quote diverse, e il dislivello
        # va messo da qualche parte. Si preferisce una SOSTA, che nel
        # ciclogramma e' un tratto piatto e quindi e' li' che l'occhio si
        # aspetta un movimento verticale; se non ce n'e' nessuna, non resta
        # che farlo durante la traslazione.
        if segs[(i - 1) % n].kind == "wait":
            fisse[i] = (arrivo, arrivo, corsa)
        elif segs[(i + 1) % n].kind == "wait":
            fisse[i] = (partenza, partenza, corsa)
        else:
            fisse[i] = (partenza, arrivo, corsa)

    def vicino(i: int, verso: int) -> tuple[float, float]:
        """Del primo tratto non di attesa che si incontra andando in `verso`:
        la frazione dal lato che tocca l'attesa, e la sua corsa. Si gira in
        tondo perche' il giro si richiude."""
        j = i
        for _ in range(n):
            j = (j + verso) % n
            if j in fisse:
                f0, f1, corsa = fisse[j]
                return (f1 if verso < 0 else f0), corsa
        return 0.0, 0.0

    # Le corse verticali del gancio scarico: la quota va da quella del tratto
    # prima a quella del tratto dopo. Non serve sapere se sale o se scende --
    # lo dicono i due vicini, e dedurlo da una macchina a stati sui tipi di
    # tratto e' proprio l'errore che sbagliava tutto sulle postazioni senza
    # corsa.
    for i, s in enumerate(segs):
        if s.kind == "lift_empty":
            (f0, c0), (f1, c1) = vicino(i, -1), vicino(i, +1)
            fisse[i] = (f0, f1, max(c0, c1, corsa_in(s.x_start)))

    fuori: dict[int, tuple[float, float, float]] = {}
    for i, s in enumerate(segs):
        if s.kind in ("empty", "lift_empty"):
            fuori[i] = fisse[i]
        elif s.kind == "wait":
            (f0, c0), (f1, c1) = vicino(i, -1), vicino(i, +1)
            # La corsa di riferimento deve reggere TUTTE E DUE le quote: su una
            # postazione senza corsa non ci sarebbe niente contro cui misurare
            # la discesa, e la rampa non si vedrebbe.
            fuori[i] = (f0, f1, max(c0, c1, corsa_in(s.x_start)))
    return fuori


def _cumulato_mobile(segs: list) -> tuple[list[float], list[float]]:
    """Quanto tempo il carroponte ha passato MUOVENDOSI, istante per istante.

    Un'attesa non lo fa crescere, tutto il resto si'. Serve a distribuire lo
    spostamento di lato del carrello sui momenti in cui gia' si muove: farlo
    scorrere di fianco per un minuto mentre e' fermo sopra una vasca e'
    innaturale, e la sosta e' proprio quando non dovrebbe muoversi affatto."""
    tempi = [segs[0].t_start]
    cumulato = [0.0]
    quanto = 0.0
    for s in segs:
        if s.kind != "wait":
            quanto += s.t_end - s.t_start
        tempi.append(s.t_end)
        cumulato.append(quanto)
    return tempi, cumulato


def _fino_al_carico(fasi) -> float:
    """Dall'inizio della presa a quando il telaio e' sul gancio: le fasi che
    vengono prima della prima con il telaio appeso."""
    quanto = 0.0
    for f in fasi:
        if f.loaded:
            break
        quanto += f.duration
    return quanto


def _finche_c_e_il_carico(fasi) -> float:
    """Dall'inizio del rilascio a quando il telaio lascia il gancio: fino alla
    fine dell'ultima fase con il telaio appeso."""
    quanto, ultimo = 0.0, 0.0
    for f in fasi:
        quanto += f.duration
        if f.loaded:
            ultimo = quanto
    return ultimo


def _valuta(
    t: float, t0: float, t1: float, v0: float, v1: float, kin: Optional[Kinematics]
) -> float:
    """Valore all'istante t di una grandezza che va da v0 a v1 fra t0 e t1.

    Con una cinematica si usa il profilo vero (accelerazione, crociera,
    decelerazione), che e' quello che rende credibile il movimento: un
    carroponte che parte e si ferma di scatto si vede subito, e non e' quello
    che il calcolo ha previsto."""
    if v1 == v0:
        return v0
    if t1 <= t0:
        return v1
    if kin is None:
        return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    d = v1 - v0
    segno = 1.0 if d >= 0 else -1.0
    # position_profile clampa da sola il tempo fuori intervallo
    return v0 + segno * position_profile(t - t0, abs(d), kin)


class Simulazione:
    """Dato un istante, dice dove sta ogni carroponte e ogni pezzo.

    `carri` traduce l'indice di ZONA nel numero di CARROPONTE da mostrare. Di
    norma coincidono, ma in un ciclogramma composto a meta' le zone vengono
    riempite per continuita' e i due numeri divergono: chi chiama sa quale sia
    quello giusto, e le zone senza nessuna mossa assegnata si omettono
    passando None."""

    def __init__(
        self,
        data: ProblemData,
        solution: Solution,
        carri: Optional[dict[int, Optional[int]]] = None,
    ):
        if solution.T is None or solution.T <= 0:
            raise ValueError("la simulazione richiede un takt time positivo")
        if not solution.actual_time:
            raise ValueError("la simulazione richiede la catena dei tempi del pezzo")
        self.data = data
        self.soluzione = solution
        self.T = float(solution.T)

        # -- i carroponti: le traiettorie del ciclogramma, ripetute ---------
        self._carri: list[_Traiettoria] = []
        for h, segs in enumerate(solution.segments_per_hoist):
            numero = h if carri is None else carri.get(h, h)
            if not segs or numero is None:
                continue  # zona senza mosse assegnate: non e' di nessuno
            ordinati = sorted(segs, key=lambda s: (s.t_start, s.t_end))
            # Quando comincia ogni mossa dentro il ciclo. Serve a sapere QUALE
            # pezzo il carroponte sta servendo: dall'avanzamento dentro la
            # mossa si risale all'istante assoluto in cui l'ha cominciata, e da
            # li' al numero d'ordine del pezzo.
            inizi_mossa: dict[int, float] = {}
            for s in ordinati:
                if s.move is not None:
                    inizi_mossa[s.move] = min(
                        inizi_mossa.get(s.move, s.t_start), s.t_start
                    )
            self._carri.append(
                _Traiettoria(
                    numero, ordinati, [s.t_start for s in ordinati],
                    ordinati[0].t_start, inizi_mossa,
                    sorted(
                        (
                            inizio + _fino_al_carico(data.pick_phases(k)),
                            inizio
                            + data.pick_time_at(k)
                            + data.horizontal_loaded_seconds(k)
                            + _finche_c_e_il_carico(data.release_phases(k + 1)),
                            k,
                        )
                        for k, inizio in inizi_mossa.items()
                    ),
                    *_cumulato_mobile(ordinati),
                    _quote_a_vuoto(data, ordinati),
                )
            )

        # -- i pezzi: la catena dei tempi, un pezzo ogni takt time ----------
        self._tempi = list(solution.actual_time)
        self._fasi = _fasi_pezzo(data, list(solution.actual_time))
        self._inizi_fasi = [f.t0 for f in self._fasi]
        self.inizio_pezzo = self._fasi[0].t0
        self.fine_pezzo = self._fasi[-1].t1
        # Quanto dura la simulazione prima di ripetersi. Un solo periodo
        # basterebbe -- in regime tutto si ripete ogni T -- ma non si potrebbe
        # seguire un pezzo dall'ingresso all'uscita, che e' proprio quello che
        # si vuole guardare. Si arrotonda a un numero intero di periodi, cosi'
        # il ritorno a zero e' impercettibile: la linea e' identica a se stessa.
        vita = self.fine_pezzo - self.inizio_pezzo
        self.periodi = max(1, math.ceil(vita / self.T - 1e-9))
        self.durata = self.periodi * self.T

        self._prepara_posti()

    def _prepara_posti(self):
        """Quanti pezzi stanno insieme in ogni vasca, e su quale posto ciascuno.

        Il numero NON e' la capienza dichiarata (`Tank.capacity`) ma quella che
        il ciclogramma usa davvero: un pezzo occupa un posto per quanto dura la
        sua sosta piu' le fasi verticali, e ne arriva uno ogni takt time.
        Contare i posti dichiarati sarebbe sbagliato in tutti e due i versi --
        con tre posti e un pezzo solo lo si disegnerebbe fuori centro, e con un
        ciclogramma che sfora la capienza i pezzi di troppo finirebbero uno
        sopra l'altro, nascondendo proprio l'errore che si vuole vedere.

        Le vasche si contano per VASCA e non per tappa: se la ricetta ci passa
        due volte, i pezzi delle due tappe si contendono lo stesso spazio."""
        tempo_in: dict[int, float] = {}
        for f in self._fasi:
            if f.st_da == f.st_a:
                tempo_in[f.st_da] = tempo_in.get(f.st_da, 0.0) + (f.t1 - f.t0)
        self._posti = {
            s: max(1, math.ceil(tempo_in.get(s, 0.0) / self.T - 1e-9))
            for s in range(self.data.n_stations)
        }
        # i posti si mettono in fila: prima quelli della prima tappa che usa
        # la vasca, poi quelli della seconda, e cosi' via
        self._primo_posto: dict[int, int] = {}
        occupati: dict[str, int] = {}
        for s in range(self.data.n_stations):
            vasca = self.data.route[s].tank_id
            self._primo_posto[s] = occupati.get(vasca, 0)
            occupati[vasca] = self._primo_posto[s] + self._posti[s]
        self._posti_vasca = occupati

    # -- interrogazione --------------------------------------------------

    def numeri_carri(self) -> list[int]:
        """I carroponti che compaiono, nell'ordine in cui li si disegna."""
        return [c.numero for c in self._carri]

    def _corsia(self, pezzo: int, stazione: int) -> float:
        """Su quale POSTO della vasca sta il pezzo `pezzo`, contato dal centro.

        Una vasca che tiene dentro piu' pezzi insieme li mostrava tutti nello
        stesso punto, e sembravano uno solo -- proprio nelle vasche lente, che
        sono quelle per cui i posti in piu' si comprano.

        I pezzi che stanno insieme in una tappa hanno numeri d'ordine
        CONSECUTIVI -- ne entra uno ogni takt time -- quindi `pezzo % posti`
        basta a dare a ciascuno il suo, senza tenere nessuno stato. Con un
        posto solo il conto fa sempre zero, e per una vasca normale il disegno
        non cambia."""
        posti = self._posti[stazione]
        totale = self._posti_vasca[self.data.route[stazione].tank_id]
        return (
            self._primo_posto[stazione] + (pezzo % posti) - (totale - 1) / 2.0
        )

    def _corsia_fra(
        self, pezzo: int, st_da: int, st_a: int, frazione: float
    ) -> float:
        """La corsia durante una traslazione: si passa dal posto di partenza a
        quello di arrivo mentre il carroponte trasla, invece di scattarci."""
        a = self._corsia(pezzo, st_da)
        if st_da == st_a:
            return a
        return a + (self._corsia(pezzo, st_a) - a) * frazione

    def mosse_scoperte(self) -> list[int]:
        """Le mosse che nessun carroponte esegue.

        In un ciclogramma finito e' vuota. Durante la composizione a mano no, e
        allora nella simulazione si vedono pezzi che si spostano da soli: e'
        esatto, ed e' bene che si veda."""
        fatte = {
            s.move
            for segs in self.soluzione.segments_per_hoist
            for s in segs
            if s.kind == "loaded" and s.move is not None
        }
        return [k for k in range(self.data.n_moves) if k not in fatte]

    def istantanea(self, t: float) -> Istantanea:
        return Istantanea(t=t, carri=self._stato_carri(t), pezzi=self._stato_pezzi(t))

    def _stato_carri(self, t: float) -> list[StatoCarro]:
        fuori = []
        for c in self._carri:
            # il modulo di un float con divisore positivo cade sempre in [0,T)
            tau = c.t0 + (t - c.t0) % self.T
            i = max(0, bisect.bisect_right(c.inizi, tau) - 1)
            s = c.segmenti[i]
            x = _valuta(tau, s.t_start, s.t_end, s.x_start, s.x_end, s.kin)
            gruppo = self._gruppo_verticale(c, s)
            z, con_pezzo, fase, vasca, corsa = self._fase_verticale(
                s, tau, gruppo, c.quote.get(i)
            )
            fuori.append(
                StatoCarro(
                    carro=c.numero,
                    x=x,
                    z=z,
                    con_pezzo=con_pezzo,
                    fase=fase,
                    vasca=vasca,
                    corsia=self._corsia_carro(c, tau, t),
                    corsa=corsa,
                )
            )
        return fuori

    def _corsia_carro(self, c: "_Traiettoria", tau: float, t: float) -> float:
        """Su quale posto della vasca sta il carroponte.

        LA REGOLA E' UNA SOLA: mentre il telaio e' appeso al gancio il
        carroponte sta sul posto di quel pezzo -- altrimenti il telaio si
        staccherebbe dal bilancino -- e in tutto il resto del giro si sposta di
        lato con calma, da dove l'ha lasciato l'ultimo pezzo a dove lo vuole il
        prossimo.

        Prima la corsia era legata al TRATTO invece che al telaio, e fuori dai
        tratti di una mossa valeva zero, cioe' il centro della vasca. Su una
        vasca a un posto solo non si vedeva -- il centro E' il posto -- ma su
        una vasca a piu' posti il carrello scattava di lato: appena finito un
        rilascio, e di nuovo passando da un pezzo al successivo nella stessa
        vasca, dove fra i due non c'e' nemmeno un istante di attesa.

        Che lo spostamento di lato si veda e' giusto: il carroponte deve
        davvero mettersi sopra il posto in cui lavorera'. E' QUANDO lo fa che
        il modello non dice, perche' li' la vasca e' un punto solo. Lo si
        distribuisce sul tempo in cui il carroponte gia' SI MUOVE -- il rientro
        a vuoto, la discesa del gancio, l'aggancio -- e non sulle attese:
        spalmarlo su tutto l'intervallo libero faceva scivolare il carrello di
        fianco per un minuto mentre stava fermo sopra una vasca, che e'
        peggio dello scatto che sostituiva."""
        if not c.impegni:
            return 0.0
        for inizio, fine, k in c.impegni:
            if inizio - 1e-9 <= tau <= fine + 1e-9:
                return self._corsia_impegno(c, k, tau, tau, t)
        # libero: fra la fine di un impegno e l'inizio del prossimo. Il giro si
        # richiude, quindi se da una parte non se ne trova si prende quello
        # dall'altro capo della lista, spostato di un periodo.
        prima = max(
            ((fine, k, 0.0) for _, fine, k in c.impegni if fine <= tau), default=None
        )
        if prima is None:
            _, fine, k = c.impegni[-1]
            prima = (fine - self.T, k, -self.T)
        dopo = min(
            ((inizio, k, 0.0) for inizio, _, k in c.impegni if inizio >= tau),
            default=None,
        )
        if dopo is None:
            inizio, _, k = c.impegni[0]
            dopo = (inizio + self.T, k, +self.T)
        corsia0 = self._corsia_impegno(c, prima[1], prima[0], tau, t, prima[2])
        corsia1 = self._corsia_impegno(c, dopo[1], dopo[0], tau, t, dopo[2])
        if dopo[0] <= prima[0]:
            return corsia1
        m0, m1 = self._mobile_a(c, prima[0]), self._mobile_a(c, dopo[0])
        if m1 > m0:
            f = (self._mobile_a(c, tau) - m0) / (m1 - m0)
        else:
            # tutto attesa: non c'e' nessun momento in cui si muove gia', e
            # allora si spalma sull'intervallo -- meglio scivolare che saltare
            f = (tau - prima[0]) / (dopo[0] - prima[0])
        return corsia0 + (corsia1 - corsia0) * min(1.0, max(0.0, f))

    def _mobile_a(self, c: "_Traiettoria", istante: float) -> float:
        """Quanto tempo il carroponte ha passato muovendosi, da inizio giro
        fino a `istante`. Cresce anche oltre il periodo: l'istante puo' cadere
        nel giro prima o in quello dopo, e serve che resti monotono."""
        origine = c.mobile_t[0]
        giri = math.floor((istante - origine) / self.T)
        x = istante - giri * self.T
        i = min(
            len(c.mobile_t) - 2, max(0, bisect.bisect_right(c.mobile_t, x) - 1)
        )
        t0, t1 = c.mobile_t[i], c.mobile_t[i + 1]
        m0, m1 = c.mobile_c[i], c.mobile_c[i + 1]
        dentro = m0 if t1 <= t0 else m0 + (m1 - m0) * (x - t0) / (t1 - t0)
        return giri * c.mobile_c[-1] + dentro

    def _corsia_impegno(
        self,
        c: "_Traiettoria",
        k: int,
        istante: float,
        tau: float,
        t: float,
        scarto: float = 0.0,
    ) -> float:
        """La corsia del carroponte mentre porta il pezzo della mossa k: quella
        della stazione di partenza, poi quella di arrivo, passando dall'una
        all'altra durante la traslazione col pezzo.

        `istante` e' il punto del giro da valutare e `tau` quello in cui si
        trova adesso: sono diversi quando si chiede la corsia agli estremi di
        un impegno vicino, per interpolare. Il PEZZO servito si ricava sempre
        da `tau`, perche' e' quello del giro corrente."""
        d = self.data
        pezzo = self._pezzo_servito(c, k, tau, t, scarto)
        avanzamento = istante - (c.inizi_mossa[k] + scarto)
        presa = d.pick_time_at(k)
        orizzontale = d.horizontal_loaded_seconds(k)
        if avanzamento <= presa or orizzontale <= 0:
            return self._corsia(pezzo, k)
        if avanzamento >= presa + orizzontale:
            return self._corsia(pezzo, k + 1)
        return self._corsia_fra(
            pezzo, k, k + 1, (avanzamento - presa) / orizzontale
        )

    def _pezzo_servito(
        self, c: "_Traiettoria", k: int, tau: float, t: float, scarto: float = 0.0
    ) -> int:
        """Il numero d'ordine del pezzo che il carroponte serve nella mossa k.

        Lo dice l'aritmetica: il carroponte ha cominciato quella mossa a
        `t - avanzamento`, e la mossa comincia per il pezzo j all'istante
        `catena[k] + j*T`. `scarto` sposta il riferimento di un periodo, per le
        mosse che stanno dall'altra parte della fine del ciclo."""
        avanzamento = tau - (c.inizi_mossa[k] + scarto)
        return round((t - avanzamento - self._tempi[k]) / self.T)

    def _gruppo_verticale(self, c: "_Traiettoria", s):
        """A quale PRESA o RILASCIO appartiene il tratto, su quale stazione, e
        quando quel gruppo e' cominciato. None se il tratto non fa parte di
        nessuno dei due.

        Serve perche' con una zona di cambio quota la presa non e' piu' un
        tratto solo: e' sosta, traslazione, sosta, traslazione, sosta. Il
        `t_start` del singolo tratto non dice piu' a che punto della presa si
        e' arrivati -- lo dice l'inizio del gruppo, che e' l'unico riferimento
        rispetto a cui le fasi si susseguono."""
        k = s.move
        if (
            k is None
            or k not in c.inizi_mossa
            or s.kind not in ("pick", "release", "quota")
        ):
            return None
        d = self.data
        t_presa = c.inizi_mossa[k]
        t_rilascio = (
            t_presa + d.pick_time_at(k) + d.horizontal_loaded_seconds(k)
        )
        # una traslazione di cambio quota sta nella presa o nel rilascio a
        # seconda di quando cade: il trasporto separa le due
        if s.kind == "release" or (
            s.kind == "quota" and s.t_start > t_rilascio - 1e-9
        ):
            return "release", k + 1, t_rilascio
        return "pick", k, t_presa

    def _fase_verticale(self, s, tau: float, gruppo=None, quote=None):
        """Quota del gancio, se ha il pezzo, cosa sta facendo e sopra cosa.

        La stazione NON si indovina dalla posizione: la dice il segmento
        (`Segment.move`), perche' la stessa vasca puo' comparire due volte
        nella ricetta e due vasche possono stare vicine quanto si vuole.

        ASPETTANDO SOPRA UNA VASCA IL GANCIO STA IN FONDO. Vale sia dopo aver
        deposto un telaio sia arrivando in anticipo per prelevarne uno, e non
        c'e' niente da correggere: le corse a vuoto del gancio non stanno in
        presa e rilascio -- stanno nel rientro, che e' dove avvengono -- quindi
        le fasi lo lasciano gia' dov'e'.

        Per un periodo il gancio si staccava di un dito dal telaio durante
        l'attesa, per far vedere che non lo teneva piu'. Era una cosa che il
        carroponte non fa, e si e' tolta: la macchina non ha nessun motivo di
        alzarsi per poi riabbassarsi, e il disegno non deve inventargliene uno."""
        d = self.data
        if s.kind == "loaded":
            return 0.0, True, "trasporto", None, 0.0
        if s.kind in ("empty", "wait", "lift_empty"):
            # Tutto quello che il gancio SCARICO fa: aspettare, traslare, salire
            # o scendere su uno svincolo. Le quote sono precalcolate una volta
            # sola (`_quote_a_vuoto`) perche' dipendono dai tratti vicini, e non
            # dal tipo del tratto: dedurle da una macchina a stati sbagliava
            # tutto sulle postazioni senza corsa, dove "calato" e "in alto" sono
            # la stessa quota.
            f0, f1, corsa = quote if quote is not None else (0.0, 0.0, 0.0)
            if s.kind == "lift_empty":
                etichetta = (
                    "risalita del gancio" if f1 < f0 else "discesa del gancio"
                )
                kin = d.kin_lift_empty
            else:
                etichetta = "rientro a vuoto" if s.kind == "empty" else "attesa"
                kin = None
            if corsa <= 0:
                return 0.0, False, etichetta, self._vasca_a(s.x_start), 0.0
            # Le due quote si riportano sulla STESSA corsa di riferimento e poi
            # si interpola in millimetri: e' cosi' che il profilo cinematico
            # della corsa verticale viene giusto -- `position_profile` misura
            # una distanza, e dandogli una frazione fra 0 e 1 esaurirebbe tutta
            # la corsa nel primo millisecondo.
            #
            # La frazione resta il riferimento perche' e' quella che si
            # disegna: due quote diverse su corse diverse possono benissimo
            # essere tutte e due "in fondo". Su una traslazione f0 e f1
            # coincidono -- traslando la quota non cambia -- e la rampa sta
            # nella sosta o nella corsa verticale accanto.
            z = _valuta(tau, s.t_start, s.t_end, -f0 * corsa, -f1 * corsa, kin)
            vasca = self._vasca_a(s.x_start) if s.kind != "empty" else None
            return z, False, etichetta, vasca, corsa
        if gruppo is not None:
            tipo, stazione, inizio = gruppo
            fasi = (
                d.pick_phases(stazione)
                if tipo == "pick"
                else d.release_phases(stazione)
            )
        else:
            # attesa sopra una vasca: il gancio e' in alto, vuoto
            return 0.0, False, "attesa", self._vasca_a(s.x_start), 0.0
        vasca = d.route[stazione].tank_id
        corsa = d.corsa_verticale(stazione)
        # dall'inizio del GRUPPO, non del singolo tratto: una presa con cambio
        # quota e' spezzata in piu' tratti, e le fasi si contano da capo
        dt = tau - inizio
        for f in fasi:
            if dt <= f.duration or f is fasi[-1]:
                z = _valuta(dt, 0.0, f.duration, f.z_start, f.z_end, f.kin)
                return z, f.loaded, f.name, vasca, corsa
            dt -= f.duration
        return 0.0, False, s.kind, vasca, corsa

    def _vasca_a(self, x: float) -> Optional[str]:
        for st in self.data.route:
            if abs(self.data.tanks[st.tank_id].position - x) < 1e-6:
                return st.tank_id
        return None

    def _corsa_vicina(self, x: float) -> float:
        """Corsa verticale della postazione piu' vicina a `x`.

        Serve sugli SVINCOLI, che non sono posizioni di vasca ma stanno per
        costruzione fra una vasca e quella accanto: la piu' vicina e' la
        propria. Un punto di CAMBIO QUOTA e' invece esso stesso il punto di
        approccio della sua stazione, e li' la corsa e' quella intera del
        carroponte: si guarda prima se la quota corrisponde esattamente a
        un punto di approccio, che e' una risposta certa, e solo dopo si
        ripiega sulla piu' vicina."""
        esatta = self._corsa_a(x)
        if esatta > 0:
            return esatta
        migliore, distanza = 0.0, None
        for i in range(self.data.n_stations):
            dist = abs(self.data.approach_position(i) - x)
            if distanza is None or dist < distanza:
                migliore, distanza = self.data.corsa_verticale(i), dist
        return migliore

    def _riposo_a(self, x: float) -> tuple[float, float]:
        """(quota a cui il telaio riposa, corsa verticale) della postazione che
        sta in `x`, e (0, 0) se li' non ce n'e' nessuna.

        Le due cose vanno insieme perche' quello che si disegna e' il loro
        rapporto: la stessa quota su corse diverse e' un gancio piu' o meno
        calato."""
        for i in range(self.data.n_stations):
            if abs(self.data.approach_position(i) - x) < 1e-6:
                return self.data.quota_di_riposo(i), self.data.corsa_verticale(i)
        return 0.0, 0.0

    def _corsa_a(self, x: float) -> float:
        """Corsa verticale della postazione che sta in `x`, o zero se li' non
        ce n'e' nessuna.

        Si guardano i punti di APPROCCIO: e' li' che il gancio si trova quando
        comincia un rientro a vuoto, e su una stazione con cambio quota il
        punto di approccio non e' la vasca ma il punto di cambio quota."""
        for i in range(self.data.n_stations):
            if abs(self.data.approach_position(i) - x) < 1e-6:
                return self.data.corsa_verticale(i)
        return 0.0

    def _stato_pezzi(self, t: float) -> list[StatoPezzo]:
        # quali pezzi sono in linea adesso: quelli entrati fra t-vita e t
        primo = math.ceil((t - self.fine_pezzo) / self.T)
        ultimo = math.floor((t - self.inizio_pezzo) / self.T)
        fuori = []
        for j in range(primo, ultimo + 1):
            stato = self._pezzo(t - j * self.T, j)
            if stato is not None:
                fuori.append(stato)
        return fuori

    def _pezzo(self, tau: float, indice: int) -> Optional[StatoPezzo]:
        if tau < self.inizio_pezzo or tau > self.fine_pezzo:
            return None
        i = max(0, bisect.bisect_right(self._inizi_fasi, tau) - 1)
        f = self._fasi[i]
        frazione = (tau - f.t0) / (f.t1 - f.t0) if f.t1 > f.t0 else 1.0
        return StatoPezzo(
            indice=indice,
            x=_valuta(tau, f.t0, f.t1, f.x0, f.x1, f.kin_x),
            z=_valuta(tau, f.t0, f.t1, f.z0, f.z1, f.kin_z),
            appeso=f.appeso,
            vasca=f.vasca,
            corsia=self._corsia_fra(indice, f.st_da, f.st_a, frazione),
            corsa=self.data.corsa_verticale(
                f.st_da if f.st_da == f.st_a else f.st_a
            ),
        )


def _fasi_pezzo(data: ProblemData, tempi: list[float]) -> list[_Fase]:
    """La vita di UN pezzo, dal primo prelievo all'ultima immersione.

    Il pezzo non segue il gancio dappertutto: mentre il gancio scende vuoto a
    prenderlo, o risale vuoto dopo averlo sganciato, il pezzo sta fermo in
    fondo alla vasca. E' quello che distingue le fasi `loaded` dalle altre."""
    fasi: list[_Fase] = []

    def fase_appesa(t: float, f, x_riposo: float, riposo: float, vasca, st):
        """Una fase verticale vista DAL PEZZO.

        Se il telaio e' appeso segue il gancio dappertutto, traslazioni
        comprese: su una zona di cambio quota il pezzo fa avanti e indietro
        insieme al carroponte. Se non e' appeso resta dov'e', in fondo alla
        vasca, e il gancio va per conto suo."""
        if f.loaded:
            xa = f.x_start if f.x_start is not None else x_riposo
            xb = f.x_end if f.x_end is not None else x_riposo
            return _Fase(
                t, t + f.duration, xa, xb, f.kin_x,
                f.z_start, f.z_end, f.kin, True, vasca, st, st,
            )
        return _Fase(
            t, t + f.duration, x_riposo, x_riposo, None,
            riposo, riposo, None, False, vasca, st, st,
        )

    for k in range(data.n_moves):
        # dove il pezzo aspetta (la stazione) e dove il carroponte lo prende in
        # consegna (il punto di approccio): coincidono, tranne che su una zona
        # di cambio quota
        x0 = data.station_position(k)
        x1 = data.station_position(k + 1)
        app0 = data.approach_position(k)
        app1 = data.approach_position(k + 1)
        v0 = data.route[k].tank_id
        v1 = data.route[k + 1].tank_id
        riposo0 = data.quota_di_riposo(k)
        riposo1 = data.quota_di_riposo(k + 1)

        t = tempi[k]
        for f in data.pick_phases(k):
            if f.duration <= 0:
                continue
            fasi.append(fase_appesa(t, f, x0, riposo0, v0, k))
            t += f.duration

        durata = data.horizontal_loaded_seconds(k)
        fasi.append(
            _Fase(
                t, t + durata, app0, app1, data.kin_loaded, 0.0, 0.0, None, True,
                None, k, k + 1,
            )
        )
        t += durata

        for f in data.release_phases(k + 1):
            if f.duration <= 0:
                continue
            fasi.append(fase_appesa(t, f, x1, riposo1, v1, k + 1))
            t += f.duration

        # sosta in vasca fino al prelievo successivo. Dopo l'ultima mossa non
        # c'e': il pezzo e' scaricato ed esce dalla linea.
        if k + 1 < data.n_moves and tempi[k + 1] > t:
            fasi.append(
                _Fase(
                    t, tempi[k + 1], x1, x1, None, riposo1, riposo1, None, False,
                    v1, k + 1, k + 1,
                )
            )
    return fasi


# --------------------------------------------------------------------------
# Il disegno
# --------------------------------------------------------------------------


def _percorso_telaio() -> Path:
    """Il telaio come lo si vede appeso: una traversa e le barre che scendono.

    E' un simbolo di matplotlib, non un disegno in coordinate della linea: cosi'
    tutti i pezzi in lavorazione stanno in UN oggetto grafico solo, e restano
    leggibili a qualunque ingrandimento. Il riquadro va da y=-1 a y=0 e non da
    -0.5 a 0.5 come al solito, perche' il telaio deve PENDERE dal punto in cui
    lo si mette -- che e' la quota del gancio, non il centro del telaio."""
    verts: list[tuple[float, float]] = []
    codes: list[int] = []

    def rettangolo(x0, x1, y0, y1):
        verts.extend([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
        codes.extend(
            [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO, Path.CLOSEPOLY]
        )

    rettangolo(-0.5, 0.5, -0.26, 0.0)  # la traversa, appesa al gancio
    for a, b in ((-0.42, -0.26), (-0.08, 0.08), (0.26, 0.42)):
        rettangolo(a, b, -1.0, -0.26)  # i pezzi appesi alla traversa
    return Path(verts, codes)


_TELAIO = _percorso_telaio()


# --------------------------------------------------------------------------
# Le icone dei comandi
#
# Disegnate qui, pixel per pixel, e non prese da un font. I simboli media di
# Unicode (U+23F8 e vicini) su Windows si vedono solo se il sistema trova un
# font che li contiene: dove non lo trova compare un quadratino, che e' molto
# peggio della parola che sostituiva. Cosi' invece sono identiche su qualunque
# macchina, eseguibile impacchettato compreso, e non c'e' nessun file da
# portarsi dietro.
# --------------------------------------------------------------------------

_COLORE_ICONA = "#2b2f33"


def _colonna(img, x: int, y0: int, y1: int, colore: str):
    if y1 >= y0:
        img.put(colore, to=(x, y0, x + 1, y1 + 1))


def _triangolo(img, x0: int, x1: int, alto: int, basso: int, verso: int, colore: str):
    """Triangolo pieno fra le colonne x0..x1, con la punta a destra (verso=+1)
    o a sinistra (verso=-1). Riempito per colonne: a questa dimensione i bordi
    obliqui vengono dritti abbastanza."""
    larghezza = max(1, x1 - x0)
    mezzo = (alto + basso) / 2.0
    meta = (basso - alto) / 2.0
    for x in range(x0, x1 + 1):
        f = (x - x0) / larghezza if verso > 0 else (x1 - x) / larghezza
        h = (1.0 - f) * meta
        _colonna(img, x, int(round(mezzo - h)), int(round(mezzo + h)), colore)


def _barra(img, x0: int, x1: int, alto: int, basso: int, colore: str):
    img.put(colore, to=(x0, alto, x1 + 1, basso + 1))


def icona_comando(nome: str, lato: int = 18, colore: str = _COLORE_ICONA):
    """L'icona di un comando, come immagine Tk.

    Un'immagine appena creata e' TRASPARENTE, quindi si disegna solo la figura
    e lo sfondo del pulsante resta quello del tema -- anche quando il tema
    cambia. Chi la usa deve tenerne un riferimento: Tk non lo fa, e
    un'immagine raccolta dal garbage collector lascia il pulsante vuoto."""
    img = tk.PhotoImage(width=lato, height=lato)
    alto, basso = 3, lato - 4
    meta = lato // 2
    if nome == "play":
        _triangolo(img, 5, lato - 5, alto, basso, +1, colore)
    elif nome == "pausa":
        _barra(img, 5, 7, alto, basso, colore)
        _barra(img, lato - 8, lato - 6, alto, basso, colore)
    elif nome == "avanti":
        _triangolo(img, 2, meta - 1, alto, basso, +1, colore)
        _triangolo(img, meta, lato - 3, alto, basso, +1, colore)
    elif nome == "indietro":
        _triangolo(img, 2, meta - 1, alto, basso, -1, colore)
        _triangolo(img, meta, lato - 3, alto, basso, -1, colore)
    elif nome == "da_capo":
        _barra(img, 3, 4, alto, basso, colore)
        _triangolo(img, 6, lato - 3, alto, basso, -1, colore)
    else:
        raise ValueError(f"icona sconosciuta: {nome!r}")
    return img


class _Suggerimento:
    """Il fumetto che compare fermandosi su un pulsante.

    Serve perche' un'icona dice cosa fa il pulsante ma non tutto: che tenendo
    premuto `Avanti` la simulazione scorre, per esempio, non si ricava da un
    triangolo. Con le etichette scritte quell'informazione non c'era comunque,
    quindi qui non si perde niente e si guadagna un posto dove metterla.

    Il timer si annulla uscendo E alla distruzione del widget: un `after` che
    scatta su una finestra gia' chiusa fa apparire "invalid command name" in
    console, ed e' il modo in cui questa finestra ha gia' perso dei timer."""

    RITARDO_MS = 450

    def __init__(self, widget, testo: str):
        self.widget = widget
        self.testo = testo
        self._attesa = None
        self._fumetto = None
        widget.bind("<Enter>", self._entra, add="+")
        widget.bind("<Leave>", self._esce, add="+")
        widget.bind("<ButtonPress>", self._esce, add="+")
        widget.bind("<Destroy>", self._esce, add="+")

    def _entra(self, _evento=None):
        self._annulla()
        self._attesa = self.widget.after(self.RITARDO_MS, self._mostra)

    def _esce(self, _evento=None):
        self._annulla()
        if self._fumetto is not None:
            self._fumetto.destroy()
            self._fumetto = None

    def _annulla(self):
        if self._attesa is not None:
            try:
                self.widget.after_cancel(self._attesa)
            except tk.TclError:
                pass
            self._attesa = None

    def _mostra(self):
        self._attesa = None
        if self._fumetto is not None or not self.widget.winfo_ismapped():
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._fumetto = tk.Toplevel(self.widget)
        self._fumetto.wm_overrideredirect(True)  # niente barra del titolo
        self._fumetto.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._fumetto,
            text=self.testo,
            background="#ffffe0",
            foreground="#333333",
            relief=tk.SOLID,
            borderwidth=1,
            padx=6,
            pady=3,
            justify=tk.LEFT,
        ).pack()


@dataclass
class _Carro:
    """Gli oggetti grafici di un carroponte, creati una volta e poi solo
    spostati. Ricostruirli a ogni immagine vorrebbe dire rifare il grafico
    venticinque volte al secondo."""

    numero: int
    telaio: Rectangle
    corpo: Rectangle
    ruote: Line2D
    tamburo: Rectangle
    funi: Line2D
    bilancino: Line2D
    targa: Text


# --------------------------------------------------------------------------
# La finestra
# --------------------------------------------------------------------------


class FinestraSimulazione(tk.Toplevel):
    """Finestra a se': la simulazione si guarda mentre si tiene d'occhio il
    ciclogramma nella finestra principale, non al posto suo."""

    # Ogni quanti millisecondi si ridisegna. 40 ms sono 25 immagini al
    # secondo: piu' fitto non si distingue, meno fitto si vede scattare.
    PASSO_MS = 40
    VELOCITA = ["0.5x", "1x", "2x", "5x", "10x", "20x"]
    # Quanto va tenuto premuto `Avanti` o `Indietro` prima che parta la
    # raffica. Serve un'attesa: senza, ogni clic un po' lento ne farebbe due,
    # e un pulsante che a volte fa un passo e a volte due non si controlla.
    ATTESA_RAFFICA_MS = 350

    def __init__(self, padre, data, solution, carri=None, titolo_linea=""):
        super().__init__(padre)
        self.title("Simulazione della linea" + (f" - {titolo_linea}" if titolo_linea else ""))
        self.geometry("1180x620")
        self.minsize(820, 480)

        self.sim: Optional[Simulazione] = None
        self.t = 0.0
        self._in_moto = False
        self._lavoro = None  # identificativo del timer di tkinter
        self._raffica = None  # il timer del pulsante tenuto premuto
        self._muovo_io = False  # per non farsi rimbalzare indietro dal cursore

        self.figura = Figure(figsize=(11, 4.6), dpi=100)
        self.assi = self.figura.add_subplot(111)
        self.tela = FigureCanvasTkAgg(self.figura, master=self)
        self.tela.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        comandi = ttk.Frame(self, padding=(10, 6))
        comandi.pack(fill=tk.X)
        # Un fotogramma per volta, avanti e indietro. Guardare la linea in
        # movimento fa vedere cosa succede; per capire ESATTAMENTE quando due
        # carroponti si sfiorano bisogna potersi fermare sull'istante e
        # spostarsi di poco, avanti e indietro, senza rincorrere il cursore.
        # Le immagini vanno tenute qui: Tk non conserva un riferimento suo, e
        # un'icona raccolta dal garbage collector lascia il pulsante vuoto.
        self.icone = {
            n: icona_comando(n)
            for n in ("indietro", "play", "pausa", "avanti", "da_capo")
        }
        self._pulsante_passo(
            comandi,
            "indietro",
            -1,
            "Indietro di un fotogramma\nTienilo premuto per scorrere all'indietro",
        ).pack(side=tk.LEFT)
        self.btn_avvia = ttk.Button(
            comandi, image=self.icone["play"], command=self.avvia_o_ferma
        )
        self.btn_avvia.pack(side=tk.LEFT, padx=(6, 0))
        _Suggerimento(self.btn_avvia, "Avvia / Pausa")
        self._pulsante_passo(
            comandi,
            "avanti",
            +1,
            "Avanti di un fotogramma\nTienilo premuto per scorrere in avanti",
        ).pack(side=tk.LEFT, padx=(6, 0))
        btn_capo = ttk.Button(
            comandi, image=self.icone["da_capo"], command=self.da_capo
        )
        btn_capo.pack(side=tk.LEFT, padx=(6, 0))
        _Suggerimento(btn_capo, "Torna all'inizio")
        ttk.Label(comandi, text="velocita':").pack(side=tk.LEFT, padx=(16, 4))
        # Si apre a TEMPO REALE. Un takt time dura quanto dura davvero, che su
        # una linea vera vuol dire un paio di minuti per un ciclo intero: e'
        # lento, ed e' il punto. Aprendo accelerati si guarda un movimento che
        # non e' quello dell'impianto, e la prima impressione -- quanto tempo
        # un carroponte passa fermo, quanto e' lunga una discesa -- resta
        # sbagliata. Per scorrere in fretta basta cambiare qui: la manopola e'
        # subito a fianco, e regola anche la finezza del passo a passo.
        self.var_velocita = tk.StringVar(value="1x")
        ttk.Combobox(
            comandi,
            width=5,
            state="readonly",
            textvariable=self.var_velocita,
            values=self.VELOCITA,
        ).pack(side=tk.LEFT)
        self.var_t = tk.DoubleVar(value=0.0)
        # takefocus=False perche' anche il cursore risponde alle frecce: se se
        # le prendesse lui, ogni freccia muoverebbe due volte il tempo -- una
        # per il cursore e una per il passo a passo qui sotto.
        self.cursore = ttk.Scale(
            comandi, from_=0.0, to=1.0, variable=self.var_t,
            command=self._trascinato, takefocus=False,
        )
        self.cursore.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(16, 12))
        self.bind("<Left>", lambda e: self.indietro())
        self.bind("<Right>", lambda e: self.avanti())

        self.etichetta = ttk.Label(self, text="", padding=(10, 0, 10, 6), anchor=tk.W)
        self.etichetta.pack(fill=tk.X)
        self.avviso = ttk.Label(
            self, text="", padding=(10, 0, 10, 8), anchor=tk.W, foreground="#990000"
        )
        self.avviso.pack(fill=tk.X)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.aggiorna(data, solution, carri)
        self.avvia_o_ferma()  # parte da sola: e' quello che si e' chiesto

    # -- contenuto -------------------------------------------------------

    def aggiorna(self, data, solution, carri=None):
        """Rilegge il ciclogramma. Si chiama anche mentre la finestra e'
        aperta: modificando il ciclogramma nella finestra principale la
        simulazione deve mostrare quello nuovo, non quello di prima."""
        # prima si costruisce, poi si sostituisce: se il ciclogramma nuovo non
        # e' simulabile, la finestra deve restare su quello di prima invece di
        # trovarsi con i dati nuovi e la simulazione vecchia
        sim = Simulazione(data, solution, carri)
        self.dati, self.sim = data, sim
        self.cursore.configure(to=self.sim.durata)
        if self.t > self.sim.durata:
            self.t = 0.0
        self._prepara_scena()
        scoperte = self.sim.mosse_scoperte()
        self.avviso.configure(
            text=(
                f"{len(scoperte)} trasporti non sono assegnati a nessun carroponte "
                f"(mosse {scoperte}): li vedrai come pezzi che si spostano da soli."
                if scoperte
                else ""
            )
        )
        self._disegna()

    def _prepara_scena(self):
        """Disegna quello che non si muove (capannone, vasche, rotaia) e crea
        una volta sola gli oggetti che si muovono. Ridisegnare tutto a ogni
        immagine costerebbe venticinque ricostruzioni di grafico al secondo."""
        d = self.dati
        self.assi.clear()
        self.assi.set_facecolor(_SFONDO)

        # -- misure del disegno ------------------------------------------
        posizioni: dict[float, list[str]] = {}
        for st in d.route:
            y = d.tanks[st.tank_id].position
            posizioni.setdefault(y, [])
            if st.tank_id not in posizioni[y]:
                posizioni[y].append(st.tank_id)
        quote = sorted(posizioni)

        corse = [d.lift_height_at(i) for i in range(d.n_stations)]
        h_max = max([c for c in corse if c > 0] or [_CORSA_PREDEFINITA])
        if len(quote) > 1:
            passo = min(b - a for a, b in zip(quote, quote[1:]))
        else:
            passo = 2000.0
        larghezza = 0.62 * passo
        margine = max(larghezza, d.hoist_extent_pos, d.hoist_extent_neg)
        sinistra, destra = quote[0] - margine, quote[-1] + margine

        # La trave sta poco sopra la quota di trasporto, non in cima al
        # disegno: quando il telaio viaggia, la fune e' corta. Metterla in alto
        # riempiva mezza figura di funi tese e schiacciava le vasche, che sono
        # la parte da guardare.
        self.z_rotaia = 0.34 * h_max
        self.altezza_rotaia = 0.07 * h_max
        self.raggio_ruota = 0.04 * h_max
        self.altezza_carro = 0.20 * h_max
        self.larghezza_gancio = 0.20 * larghezza
        # bordo_vasca si calcola piu' sotto, quando si sa a che quota finisce
        # il telaio immerso: l'orlo lo segue.
        # Le vasche sono tutte della STESSA profondita', e fonde abbastanza da
        # tenere dentro anche la corsa piu' lunga con dello spazio sotto.
        #
        # La profondita' vera non e' un dato dichiarato: delle vasche si sa
        # solo di quanto sale e scende il telaio. Farla seguire alla corsa
        # avrebbe disegnato un dato che nessuno ha scritto, e per giunta con
        # l'aria di dire qualcosa -- vasche piu' fonde e meno fonde -- che il
        # programma non sa. La corsa si vede lo stesso, e nel modo giusto: da
        # quanto scende il gancio. E il telaio resta SOSPESO nel bagno, che e'
        # dove sta davvero: appoggiato sul fondo non ci va mai.
        self.fondo_vasca = -h_max - 0.34 * h_max
        pavimento = self.fondo_vasca - 0.16 * h_max
        # A che quota si disegna un telaio immerso. E' la STESSA per tutte le
        # vasche: quello che si disegna non e' la quota in millimetri ma il
        # punto a cui e' arrivata la discesa, da zero (quota di trasporto) a
        # uno (in fondo). Il gancio segue la stessa regola, quindi telaio e
        # bilancino restano attaccati.
        #
        # La corsa vera non sparisce, cambia dove la si legge: sta nel TEMPO
        # che la discesa impiega, non nella quota -- che tanto non direbbe
        # niente, visto che la profondita' della vasca nessuno l'ha dichiarata.
        # In cambio i pezzi in vasca stanno tutti in fila alla stessa altezza,
        # e le vasche si confrontano a colpo d'occhio.
        self.quota_immersione = 0.70 * self.fondo_vasca
        # Quanto si spostano di lato i pezzi che dividono la stessa vasca.
        self.passo_corsia = 0.42 * larghezza
        # Quanto e' alto un telaio nel disegno. Non e' un dato dell'impianto --
        # del telaio non si sa nulla -- ma il simbolo con cui lo si disegna e'
        # grande 22 punti e PENDE dal bilancino, quindi occupa questa fetta di
        # disegno sotto la quota che gli si assegna. Serve a posare il telaio
        # SOPRA un piano di carico invece che dentro.
        self.altezza_telaio = 0.11 * h_max
        # L'ORLO SEGUE IL TELAIO. Il fondo resta dov'e' -- la vasca e' fonda,
        # e il telaio ci galleggia dentro senza appoggiarsi -- ma l'orlo scende
        # fin quasi alla quota del telaio immerso, cosi' il pezzo si vede
        # galleggiare A FILO. Tenendolo poco sotto la quota di trasporto, come
        # prima, le vasche diventavano scatoloni alti due terzi del disegno con
        # dentro un telaio piccolo in fondo: tutto bagno vuoto, e le proporzioni
        # non dicevano piu' niente.
        self.bordo_vasca = self.quota_immersione + 0.05 * h_max

        # -- il capannone: pavimento e colonne che reggono la rotaia -----
        self.assi.add_patch(
            Rectangle(
                (sinistra, pavimento),
                destra - sinistra,
                0.10 * h_max,
                facecolor=_COLORE_PAVIMENTO,
                edgecolor=_BORDO_PAVIMENTO,
                linewidth=1.0,
                zorder=0,
            )
        )
        larghezza_colonna = 0.018 * (destra - sinistra)
        for x in (sinistra, destra - larghezza_colonna):
            self.assi.add_patch(
                Rectangle(
                    (x, pavimento + 0.10 * h_max),
                    larghezza_colonna,
                    self.z_rotaia - pavimento - 0.10 * h_max,
                    facecolor="#eef0f2",
                    edgecolor="#cfd4d8",
                    linewidth=1.0,
                    zorder=0,
                )
            )

        # -- vasche e postazioni -----------------------------------------
        # posizione sulla rotaia -> quota di disegno del piano di appoggio
        self.quote_postazioni: dict[float, float] = {}
        pelo_x, pelo_y = [], []
        bordo_x, bordo_y = 0.045 * larghezza, 0.02 * h_max
        livello = self.bordo_vasca - 0.06 * h_max  # pelo libero, sotto il bordo
        for y in quote:
            corsa = max(
                (
                    d.lift_height_at(i)
                    for i in range(d.n_stations)
                    if abs(d.station_position(i) - y) < 1e-6
                ),
                default=0.0,
            )
            if corsa <= 0:
                # Corsa nulla vuol dire che il telaio non scende: non e' una
                # vasca ma una postazione, tipicamente il carico e lo scarico.
                # Disegnarla come una vasca piena di bagno direbbe una cosa
                # falsa, e proprio sulle due tappe che si guardano per prime.
                #
                # A CHE ALTEZZA. Di norma il telaio ci arriva alla quota di
                # trasporto, e il piano sta li'. Con una ZONA DI CAMBIO QUOTA
                # no: li' il telaio viene posato a `intermediate1`, che sta
                # parecchio piu' in basso, e un piano lasciato in alto lo
                # faceva sembrare infilato dentro alla postazione -- col
                # carroponte che ci calava le funi attraverso. Il piano segue
                # quindi la quota a cui il telaio riposa davvero, abbassato di
                # quanto il telaio e' alto perche' ci si appoggi sopra invece
                # di attraversarlo.
                zona = next(
                    (
                        d.zona_cambio_quota(i)
                        for i in range(d.n_stations)
                        if abs(d.station_position(i) - y) < 1e-6
                        and d.zona_cambio_quota(i) is not None
                    ),
                    None,
                )
                if zona is None:
                    cima = 0.0
                else:
                    cima = (
                        self._quota_disegnata(zona.z_int1, zona.corsa_totale)
                        - self.altezza_telaio
                    )
                # a che quota e' finito il piano: e' l'unico numero del disegno
                # che deve tornare con quello dei telai posati, e tenerlo qui
                # permette di controllarlo senza andare a frugare fra le patch
                self.quote_postazioni[y] = cima
                spessore = 0.16 * h_max
                self._appoggio(y, larghezza, cima - spessore, pavimento)
                self.assi.add_patch(
                    Rectangle(
                        (y - larghezza / 2, cima - spessore),
                        larghezza,
                        spessore,
                        facecolor="#dfe4e8",
                        edgecolor="#9aa3ab",
                        linewidth=1.4,
                        zorder=1,
                    )
                )
                continue
            profonda = -self.fondo_vasca
            # la vasca: pareti e fondo, disegnati come un contenitore vuoto
            self.assi.add_patch(
                Rectangle(
                    (y - larghezza / 2, self.fondo_vasca),
                    larghezza,
                    profonda + self.bordo_vasca,
                    facecolor=_COLORE_VASCA,
                    edgecolor=_BORDO_VASCA,
                    linewidth=1.6,
                    zorder=1,
                )
            )
            # il bagno dentro, che arriva poco sotto il bordo
            self.assi.add_patch(
                Rectangle(
                    (y - larghezza / 2 + bordo_x, self.fondo_vasca + bordo_y),
                    larghezza - 2 * bordo_x,
                    livello + profonda - bordo_y,
                    facecolor=_COLORE_BAGNO,
                    edgecolor="none",
                    zorder=2,
                )
            )
            # il pelo libero, appena mosso: e' quello che fa leggere il bagno
            # come un liquido invece che come un rettangolo colorato
            xs = np.linspace(y - larghezza / 2 + bordo_x, y + larghezza / 2 - bordo_x, 24)
            pelo_x.extend(list(xs) + [np.nan])
            pelo_y.extend(
                list(livello + 0.012 * h_max * np.sin(np.linspace(0, 3 * np.pi, 24)))
                + [np.nan]
            )
        if pelo_x:
            self.assi.add_line(
                Line2D(
                    pelo_x, pelo_y, color="#ffffff", linewidth=1.6, alpha=0.85, zorder=3
                )
            )

        # -- la rotaia: una trave, non una riga --------------------------
        self.assi.add_patch(
            Rectangle(
                (sinistra, self.z_rotaia),
                destra - sinistra,
                self.altezza_rotaia,
                facecolor=_COLORE_ROTAIA,
                edgecolor=_BORDO_ROTAIA,
                linewidth=1.2,
                zorder=4,
            )
        )
        # la quota di trasporto: dove viaggia il telaio fra una vasca e l'altra
        self.assi.axhline(
            0.0, color="#b9c2c9", linewidth=1, linestyle=(0, (6, 4)), zorder=1
        )

        # -- carroponti --------------------------------------------------
        # Il carrello si disegna col suo ingombro VERO, quando si vede: cosi'
        # due carroponti vicini mostrano lo spazio che resta fra loro, che e'
        # l'informazione per cui l'ingombro sta nei dati. Sotto una certa
        # dimensione pero' diventa un trattino invisibile, e allora si allarga
        # -- meglio un simbolo che un dato illeggibile.
        ingombro = d.hoist_extent_pos + d.hoist_extent_neg
        minimo = 0.030 * (destra - sinistra)
        if ingombro >= minimo:
            self.larghezza_carro, self.scarto_carro = ingombro, d.hoist_extent_neg
        else:
            self.larghezza_carro, self.scarto_carro = minimo, minimo / 2
        self.carri_disegnati: list[_Carro] = []
        for numero in self.sim.numeri_carri():
            self.carri_disegnati.append(self._crea_carro(numero))

        # -- pezzi -------------------------------------------------------
        self.pezzi_disegnati = Line2D(
            [], [], linestyle="none", marker=_TELAIO, markersize=22,
            markerfacecolor=_COLORE_PEZZO, markeredgecolor=_BORDO_PEZZO,
            markeredgewidth=0.9, zorder=6,
        )
        self.assi.add_line(self.pezzi_disegnati)

        self.assi.set_xlim(sinistra, destra)
        # Sopra la rotaia si lascia aria per la legenda: sovrapposta ai
        # carroponti coprirebbe proprio quello che si sta guardando.
        cima_carro = (
            self.z_rotaia + self.altezza_rotaia + self.raggio_ruota + self.altezza_carro
        )
        self.assi.set_ylim(pavimento, cima_carro + 0.30 * h_max)
        self.assi.set_xticks(quote)
        self.assi.set_xticklabels(
            [" / ".join(posizioni[y]) for y in quote], fontsize=8, rotation=25,
            ha="right", color="#3c4550",
        )
        self.assi.set_yticks([])
        self.assi.tick_params(axis="x", length=0, pad=2)
        for lato in self.assi.spines.values():
            lato.set_visible(False)
        self.assi.set_xlabel("")

        legenda = [
            Line2D([0], [0], linestyle="none", marker=_TELAIO, markersize=11,
                   markerfacecolor=_COLORE_PEZZO, markeredgecolor=_BORDO_PEZZO,
                   label="telaio"),
        ]
        for carro in self.carri_disegnati:
            legenda.append(
                Line2D([0], [0], color=_HOIST_COLORS[carro.numero % len(_HOIST_COLORS)],
                       linewidth=6, label=f"Carroponte {carro.numero + 1}")
            )
        self.assi.legend(
            handles=legenda, loc="upper left", fontsize=7.5,
            ncol=min(len(legenda), 6), framealpha=0.92, edgecolor="#d5d9dd",
            borderpad=0.6, handletextpad=0.6,
        )
        # Il titolo si riscrive a ogni immagine, ma lo spazio va riservato
        # adesso: `tight_layout` gira una volta sola, e senza un titolo gia'
        # presente calcolerebbe i margini senza tenerne conto -- poi quello
        # vero finirebbe tagliato dal bordo della finestra.
        self.assi.set_title(self._titolo(0.0, 0), fontsize=10, color="#2f3640")
        self.figura.set_facecolor("#ffffff")
        # Con la finestra rimpicciolita al minimo i margini non ci stanno e
        # matplotlib lo scrive su stderr. Non c'e' niente da fare e niente da
        # dire: il disegno esce comunque, e appena la finestra torna di una
        # misura ragionevole si risistema da solo. In un eseguibile senza
        # console quell'avviso non lo leggerebbe nessuno, e nei test sarebbe
        # solo rumore in mezzo ai risultati.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.figura.tight_layout()

    def _appoggio(self, x: float, larghezza: float, fondo: float, pavimento: float):
        """Il basamento che regge una postazione, che altrimenti resterebbe
        sospesa per aria: le vasche arrivano a terra da sole, il piano di
        carico e quello di scarico no."""
        if fondo <= pavimento + 1e-9:
            return
        self.assi.add_patch(
            Rectangle(
                (x - larghezza * 0.34, pavimento),
                larghezza * 0.68,
                fondo - pavimento,
                facecolor="#e7e9ea",
                edgecolor="#c6cacd",
                linewidth=1.0,
                zorder=0,
            )
        )

    def _crea_carro(self, numero: int) -> _Carro:
        """Un carroponte: carrello con le ruote sulla trave, argano, due funi e
        il bilancino a cui si appende il telaio.

        Un rettangolo unico bastava a dire dove si trova, ma non a farlo
        riconoscere per quello che e'. Le parti sono quelle vere, e ognuna
        racconta qualcosa: le ruote dicono che corre sulla trave, le funi
        quanto e' calato il gancio, il bilancino dove si aggancia il telaio."""
        colore = _HOIST_COLORS[numero % len(_HOIST_COLORS)]
        scuro = "#2f3640"
        base = self.z_rotaia + self.altezza_rotaia + self.raggio_ruota

        # Due pezzi: il telaio del carrello, in acciaio, che porta le ruote; e
        # sopra la cassa dell'argano, del colore del carroponte. Un blocco
        # unico si legge come un'etichetta colorata, non come una macchina.
        telaio = Rectangle(
            (0, base),
            self.larghezza_carro,
            self.altezza_carro * 0.30,
            facecolor=_COLORE_ACCIAIO,
            edgecolor=scuro,
            linewidth=1.1,
            zorder=6,
        )
        self.assi.add_patch(telaio)
        corpo = Rectangle(
            (0, base + self.altezza_carro * 0.30),
            self.larghezza_carro * 0.78,
            self.altezza_carro * 0.70,
            facecolor=colore,
            edgecolor=scuro,
            linewidth=1.2,
            zorder=6,
        )
        self.assi.add_patch(corpo)
        # Le ruote in punti e non in millimetri: un cerchio in coordinate della
        # linea verrebbe schiacciato, perche' i due assi non hanno la stessa
        # scala (trenta metri in orizzontale contro un metro in verticale).
        ruote = Line2D(
            [], [], linestyle="none", marker="o", markersize=6.0,
            markerfacecolor="#4b545c", markeredgecolor=scuro, markeredgewidth=0.8,
            zorder=7,
        )
        self.assi.add_line(ruote)
        tamburo = Rectangle(
            (0, self.z_rotaia - 0.16 * self.altezza_carro),
            self.larghezza_carro * 0.16,
            0.16 * self.altezza_carro,
            facecolor=_COLORE_ACCIAIO,
            edgecolor=scuro,
            linewidth=0.9,
            zorder=6,
        )
        self.assi.add_patch(tamburo)
        funi = Line2D([], [], color=scuro, linewidth=1.1, zorder=5)
        bilancino = Line2D(
            [], [], color=colore, linewidth=4.0, solid_capstyle="round", zorder=6
        )
        self.assi.add_line(funi)
        self.assi.add_line(bilancino)
        targa = self.assi.text(
            0, 0, str(numero + 1), color="white", fontsize=8, fontweight="bold",
            ha="center", va="center", zorder=8,
        )
        return _Carro(numero, telaio, corpo, ruote, tamburo, funi, bilancino, targa)

    def _posiziona_carro(self, carro: _Carro, x: float, z: float):
        w = self.larghezza_carro
        sinistra = x - self.scarto_carro  # l'ingombro non e' simmetrico
        base = self.z_rotaia + self.altezza_rotaia + self.raggio_ruota
        carro.telaio.set_x(sinistra)
        carro.corpo.set_x(sinistra + w * 0.11)
        carro.ruote.set_data(
            [sinistra + 0.16 * w, sinistra + 0.84 * w],
            [self.z_rotaia + self.altezza_rotaia + self.raggio_ruota * 0.6] * 2,
        )
        carro.tamburo.set_x(x - w * 0.08)
        # due funi, in un oggetto solo: il NaN le separa. Partono da SOTTO la
        # trave, dove sta il tamburo: sopra ci corre il carrello.
        attacco = self.z_rotaia - 0.10 * self.altezza_carro
        a = self.larghezza_gancio * 0.8
        carro.funi.set_data(
            [x - a, x - a, math.nan, x + a, x + a],
            [attacco, z, math.nan, attacco, z],
        )
        carro.bilancino.set_data(
            [x - self.larghezza_gancio, x + self.larghezza_gancio], [z, z]
        )
        carro.targa.set_position(
            (sinistra + w / 2, base + self.altezza_carro * 0.65)
        )

    # -- animazione ------------------------------------------------------

    def avvia_o_ferma(self):
        self._in_moto = not self._in_moto
        self.btn_avvia.configure(
            image=self.icone["pausa" if self._in_moto else "play"]
        )
        if self._in_moto:
            self._lavoro = self.after(self.PASSO_MS, self._passo)
        elif self._lavoro is not None:
            self.after_cancel(self._lavoro)
            self._lavoro = None

    def da_capo(self):
        self.t = 0.0
        self._disegna()

    def _fotogramma(self) -> float:
        """Di quanti secondi di simulazione avanza un fotogramma.

        E' la stessa quantita' che usa l'animazione, e viene di qui apposta:
        "un fotogramma" premendo `Avanti` dev'essere esattamente il salto che
        farebbe andando avanti da sola, altrimenti passo a passo e andatura
        normale mostrerebbero due sequenze diverse.

        Dipende dalla velocita' scelta, e va bene cosi': a 20x un passo e' otto
        decimi di secondo per scorrere il ciclo, a mezza velocita' e' un
        centesimo per fermarsi sull'istante in cui due carri si sfiorano. La
        stessa manopola regola l'andatura e la finezza del passo."""
        return float(self.var_velocita.get().rstrip("x")) * self.PASSO_MS / 1000.0

    def avanti(self):
        self._passo_a_mano(+1)

    def indietro(self):
        self._passo_a_mano(-1)

    def _pulsante_passo(self, cornice, nome_icona: str, verso: int, spiegazione: str):
        """Un pulsante che fa un passo se lo si preme, e continua se lo si
        TIENE premuto.

        Il comando non si attacca a `command` ma a pressione e rilascio: cosi'
        un clic secco vale esattamente un passo, mentre `command` -- che
        scatta al rilascio -- ne farebbe uno in piu' alla fine di ogni raffica.

        Tenendolo premuto la simulazione scorre in quel verso all'andatura
        scelta col menu della velocita': e' la stessa manopola, e per andare
        veloci si mette a 20x. All'indietro non c'e' altro modo di farlo."""
        pulsante = ttk.Button(cornice, image=self.icone[nome_icona])
        pulsante.bind("<ButtonPress-1>", lambda e: self._inizia_raffica(verso))
        pulsante.bind("<ButtonRelease-1>", lambda e: self._ferma_raffica())
        _Suggerimento(pulsante, spiegazione)
        return pulsante

    def _inizia_raffica(self, verso: int):
        self._ferma_raffica()
        self._passo_a_mano(verso)
        self._raffica = self.after(
            self.ATTESA_RAFFICA_MS, lambda: self._continua_raffica(verso)
        )

    def _continua_raffica(self, verso: int):
        # Si adotta il timer in corso invece di affiancarglisi, come fa
        # `_passo`: chiamata da qualcosa che non sia il timer -- una prova, un
        # comando futuro -- questa riga evita di lasciarne uno orfano, che poi
        # scatta su una finestra chiusa e finisce nel gestore degli errori.
        self._ferma_raffica()
        self._passo_a_mano(verso)
        self._raffica = self.after(
            self.PASSO_MS, lambda: self._continua_raffica(verso)
        )

    def _ferma_raffica(self):
        if self._raffica is not None:
            try:
                self.after_cancel(self._raffica)
            except Exception:
                pass
            self._raffica = None

    def _passo_a_mano(self, verso: int):
        if self.sim is None:
            return
        if self._in_moto:
            # Passo a passo e andatura non convivono: chi preme `Avanti`
            # vuole guardare un istante, non inseguirlo.
            self.avvia_o_ferma()
        # il modulo tiene il tempo dentro il giro in tutti e due i versi:
        # indietro dall'inizio si finisce in fondo, che e' lo stesso istante
        self.t = (self.t + verso * self._fotogramma()) % self.sim.durata
        self._disegna()

    def _passo(self):
        # Si adotta il timer in corso invece di affiancarglisi. Senza questa
        # riga ogni chiamata che non venga dal timer -- una prova, un comando
        # futuro -- ne farebbe partire una seconda catena, e le catene si
        # moltiplicherebbero a ogni giro finche' la finestra non sta piu'
        # dietro ai propri ridisegni.
        if self._lavoro is not None:
            try:
                self.after_cancel(self._lavoro)
            except Exception:
                pass
            self._lavoro = None
        if not self._in_moto or self.sim is None:
            return
        self.t += self._fotogramma()
        if self.t >= self.sim.durata:
            # si ricomincia: in regime la linea a t = durata e' identica a
            # quella a t = 0, quindi il salto non si vede
            self.t -= self.sim.durata
        self._disegna()
        self._lavoro = self.after(self.PASSO_MS, self._passo)

    def _trascinato(self, _valore):
        if self._muovo_io or self.sim is None:
            return
        self.t = float(self.var_t.get())
        self._disegna()

    def _disegna(self):
        if self.sim is None:
            return
        istante = self.sim.istantanea(self.t)

        for carro, stato in zip(self.carri_disegnati, istante.carri):
            self._posiziona_carro(carro, self._ascissa(stato), self._quota(stato))

        # il telaio PENDE dal punto in cui lo si mette, e il punto e' la quota
        # del gancio: cosi' si appoggia da solo sul bilancino
        self.pezzi_disegnati.set_data(
            [self._ascissa(p) for p in istante.pezzi],
            [self._quota(p) for p in istante.pezzi],
        )

        self._muovo_io = True
        self.var_t.set(self.t)
        self._muovo_io = False

        self.assi.set_title(self._titolo(self.t, len(istante.pezzi)), fontsize=10)
        self.etichetta.configure(text=self._descrizione(istante))
        self.tela.draw_idle()

    def _ascissa(self, stato) -> float:
        """Dove disegnare un gancio o un telaio lungo la rotaia.

        E' la posizione vera, spostata di quanto serve a mettersi sul proprio
        POSTO quando la vasca ne ha piu' d'uno. Lo spostamento e' un espediente
        di disegno -- il modello tratta la vasca come un punto e non sa dove
        stiano i posti dentro -- e vale solo per far vedere che i pezzi sono
        due. Per le distanze fra carroponti non si guarda qui: si legge la
        separazione minima in millimetri, che la da' il verificatore."""
        return stato.x + stato.corsia * self.passo_corsia

    def _quota(self, stato) -> float:
        """A che altezza disegnare un gancio o un telaio che sta a `stato.z`.

        Non e' la quota in millimetri: e' il punto a cui e' arrivata la
        discesa, riportato sulla profondita' unica del disegno. Vale sia per i
        carroponti sia per i pezzi, ed e' l'unico modo perche' continuino a
        stare nello stesso posto -- la coerenza fra i due la si controlla sulle
        quote VERE, in `Simulazione`, dove nessuno ha rimappato niente."""
        return self._quota_disegnata(stato.z, stato.corsa)

    def _quota_disegnata(self, z: float, corsa: float) -> float:
        """Il rimappaggio delle quote, nudo: quota vera e corsa dentro, altezza
        di disegno fuori.

        Sta a parte perche' non lo usa solo chi disegna cose che si muovono: lo
        usa anche la scena fissa, per mettere il piano di carico all'altezza a
        cui il telaio ci viene davvero posato. Se le due cose usassero due
        formule diverse, il telaio finirebbe accanto al suo appoggio e non
        sopra."""
        if z >= 0.0 or corsa <= 0:
            return 0.0
        return min(1.0, -z / corsa) * self.quota_immersione

    def _titolo(self, t: float, n_pezzi: int) -> str:
        return (
            f"t = {t:6.1f} s   di {self.sim.durata:.1f} s "
            f"({self.sim.periodi} takt da {self.sim.T:.2f} s)   -   "
            f"{n_pezzi} pezzi in linea"
        )

    def _descrizione(self, istante: Istantanea) -> str:
        pezzi = []
        for s in sorted(istante.carri, key=lambda s: s.carro):
            dove = f" in {s.vasca}" if s.vasca else ""
            pezzi.append(f"Carroponte {s.carro + 1}: {s.fase}{dove}")
        return "     |     ".join(pezzi)

    def destroy(self):
        self._ferma_raffica()
        if self._lavoro is not None:
            try:
                self.after_cancel(self._lavoro)
            except Exception:
                pass
            self._lavoro = None
        self._in_moto = False
        # `draw_idle` lascia un ridisegno in coda che scatta appena Tk e'
        # libero. Chiudendo la finestra subito dopo un passo, quel ridisegno
        # si sveglierebbe su una tela che non esiste piu' e finirebbe nel
        # gestore degli errori di sfondo -- invisibile in un eseguibile senza
        # console, ma pur sempre un errore. Lo si lascia finire adesso, che
        # tutto e' ancora in piedi.
        try:
            self.update_idletasks()
        except Exception:
            pass
        try:
            self.tela.get_tk_widget().destroy()
        except Exception:
            pass
        super().destroy()
