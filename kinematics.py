"""
kinematics.py
-------------
Funzioni per calcolare tempo di percorrenza e profilo di posizione di un
carroponte che si muove con un profilo trapezoidale (accelerazione costante,
velocita' di crociera, decelerazione costante) oppure triangolare se la
distanza e' troppo breve per raggiungere la velocita' massima.

Accelerazione e decelerazione sono due numeri distinti. Su un carroponte non
sono quasi mai uguali -- si frena piu' forte di quanto si acceleri, e col
carico appeso il vincolo in frenata e' il pendolo, non il motore -- e usare
l'accelerazione anche per frenare sbagliava ogni trasporto di quanto le due
grandezze differiscono. Chi non ha il dato non deve fare niente: lasciando
`d_max` a None si decelera con `a_max`, che e' il comportamento di prima.

Sul SOLLEVAMENTO c'e' una cosa in piu': la zona di AVVICINAMENTO (`Approach`).
Vicino al punto in cui il telaio viene preso o posato la velocita' non e'
limitata dal motore ma dalla precisione, e la si tiene bassa per un tratto
fisso di corsa. Il profilo smette allora di essere un solo trapezio e diventa
una successione di trapezi, uno per ogni pezzo di corsa a limite di velocita'
diverso.

La zona NON e' pianificata: e' un finecorsa. Il carroponte non sa di doverci
entrare e non anticipa niente -- frena come se dovesse fermarsi in fondo alla
corsa, esattamente come se la zona non ci fosse -- e solo quando il finecorsa
scatta il drive impone la velocita' di avvicinamento, A GRADINO. Il gradino
c'e' percio' solo dove il limite SCENDE, cioe' entrando nella zona scendendo a
posare: in salita la zona sta in partenza e all'uscita il limite RISALE, e da
li' si accelera normalmente, che e' l'unica cosa che un motore sappia fare.

Il gradino e' un'idealizzazione: un drive vero ci mette la sua rampa. E' pero'
l'idealizzazione giusta, perche' frenare dal finecorsa con la decelerazione
NOMINALE non darebbe affatto un tratto lento -- si arriverebbe a terra prima
di averla raggiunta, e la zona non costerebbe niente. Chi taglia la velocita'
all'ingresso della zona e' una rampa molto piu' ripida di quella nominale, e
il gradino e' il suo limite.

Per non avere due motori di calcolo -- uno per il caso semplice e uno per
quello con avvicinamento, destinati a divergere -- il modulo ne ha uno solo:
la corsa viene spezzata in pezzi a limite di velocita' costante e risolta
pezzo per pezzo. Senza avvicinamento il pezzo e' uno, e i conti che ne escono
sono ESATTAMENTE le formule del trapezio di sempre.

Tutte le funzioni lavorano nelle unita' del progetto (millimetri, mm/s, mm/s^2,
secondi). La conversione in "tick" interi per CP-SAT avviene altrove.
"""

from __future__ import annotations
import functools
import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Approach:
    """Zona di AVVICINAMENTO: il tratto di corsa adiacente al punto in cui il
    telaio viene preso o posato, che si percorre a velocita' ridotta.

    Sono millimetri, non una frazione della corsa: il motivo per andare piano
    e' la precisione dell'accoppiamento fra telaio e gancio, e quella non sa
    nulla di quanto sia profonda la vasca.

    `at_end` dice a quale capo della corsa sta la zona, ed e' una proprieta'
    del MOVIMENTO, non del carroponte:

      - si SCENDE a depositare -> la zona sta in fondo (True): si viaggia
        normalmente -- frenata compresa, puntando a fermarsi in fondo alla
        corsa, come se la zona non ci fosse -- finche' mancano `distance`
        millimetri; li' la velocita' cade A GRADINO a `speed`, ci si resta, e
        si frena solo all'ultimo;
      - si SALE a prelevare    -> la zona sta in testa (False): si parte piano,
        si resta a `speed` per `distance` millimetri e solo dopo si accelera
        verso la velocita' massima.

    E' per questo che la stessa cinematica genera due oggetti diversi nei due
    versi, e che a costruirli e' chi conosce il verso (model.py) e non chi
    legge il file Excel."""

    speed: float  # [mm/s] velocita' di avvicinamento
    distance: float  # [mm] quanta corsa si percorre a quella velocita'
    at_end: bool  # True = zona in fondo alla corsa (discesa), False = in testa

    def __post_init__(self):
        if self.speed <= 0:
            raise ValueError("la velocita' di avvicinamento deve essere > 0")
        if self.distance <= 0:
            raise ValueError("la distanza di avvicinamento deve essere > 0")


@dataclass(frozen=True)
class Kinematics:
    """Limiti cinematici di un carroponte in una data condizione (vuoto o carico)."""

    v_max: float  # mm/s
    a_max: float  # mm/s^2, in accelerazione
    # mm/s^2, in frenata. None significa "come in accelerazione": e' il caso
    # di chi non ha il dato, e di tutti i file compilati prima che questo
    # parametro esistesse.
    d_max: Optional[float] = None
    # Zona di avvicinamento, se questo movimento ne ha una. None e' il caso
    # normale -- traslazione orizzontale, e sollevamento di chi non ha
    # dichiarato i due parametri -- e riporta il profilo al trapezio di sempre.
    approach: Optional[Approach] = None

    def __post_init__(self):
        if self.v_max <= 0 or self.a_max <= 0:
            raise ValueError("v_max e a_max devono essere > 0")
        if self.d_max is not None and self.d_max <= 0:
            raise ValueError("d_max, se indicata, deve essere > 0")

    @property
    def decel(self) -> float:
        """La decelerazione da usare davvero. Tutto il resto del modulo passa
        di qui: cosi' il caso simmetrico non e' un ramo a parte, ma lo stesso
        conto con due numeri uguali."""
        return self.a_max if self.d_max is None else self.d_max

    def avvicinandosi(
        self,
        speed: Optional[float],
        distance: Optional[float],
        *,
        scendendo: bool,
    ) -> "Kinematics":
        """La stessa cinematica, con in piu' la zona di avvicinamento orientata
        nel verso dato. Restituisce se stessa se i due dati non ci sono.

        E' l'unico modo previsto per mettere un `Approach` dentro una
        `Kinematics`: cosi' il verso lo decide chi conosce il movimento, e non
        puo' restare per distrazione quello del movimento precedente."""
        if speed is None or distance is None:
            return self
        return Kinematics(
            v_max=self.v_max,
            a_max=self.a_max,
            d_max=self.d_max,
            approach=Approach(speed, distance, at_end=scendendo),
        )


# --------------------------------------------------------------------------
# Il motore: la corsa spezzata in tratti ad accelerazione costante
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Tratto:
    """Un pezzo di profilo ad accelerazione COSTANTE: dura `dt`, comincia a
    velocita' `v0` e prosegue con accelerazione `a` (negativa in frenata, nulla
    in crociera).

    Fra i suoi estremi la posizione e' un polinomio di grado <= 2 in t. E' da
    qui che discende la garanzia di `profile_breakpoints`: gli spigoli del
    profilo sono esattamente i confini fra un tratto e il successivo."""

    dt: float  # [s]
    v0: float  # [mm/s]
    a: float  # [mm/s^2], col segno


def _limiti(d: float, kin: Kinematics) -> tuple[tuple[float, float], ...]:
    """La corsa spezzata in pezzi a limite di velocita' costante:
    `((lunghezza, v_cap), ...)` nell'ordine in cui si percorrono.

    Senza avvicinamento il pezzo e' uno solo e vale tutta la corsa: e' da qui
    che il caso di sempre rientra nel caso generale senza costare niente."""
    app = kin.approach
    if app is None:
        return ((d, kin.v_max),)
    # Una velocita' di avvicinamento piu' alta della massima non e' un dato,
    # e' un refuso: non vincola niente, e si ignora prendendo la piu' bassa.
    v_app = min(app.speed, kin.v_max)
    # Una zona piu' lunga della corsa non e' un errore: vuol dire che la corsa
    # sta tutta dentro la zona, e allora si fa tutta piano.
    lenta = min(app.distance, d)
    if lenta >= d:
        return ((d, v_app),)
    veloce = d - lenta
    return (
        ((veloce, kin.v_max), (lenta, v_app))
        if app.at_end
        else ((lenta, v_app), (veloce, kin.v_max))
    )


def _velocita_di_confine(
    limiti: tuple[tuple[float, float], ...], kin: Kinematics
) -> tuple[tuple[float, float], ...]:
    """Con che velocita' si ENTRA e si ESCE da ogni pezzo: `((v_in, v_out), ...)`,
    uno per pezzo, nell'ordine in cui si percorrono. Si parte e si arriva
    fermi, quindi il primo v_in e l'ultimo v_out valgono zero.

    Due velocita' per confine e non una sola, perche' dove il limite SCENDE il
    profilo e' discontinuo: si esce dal pezzo veloce alla velocita' che si
    aveva, e si entra in quello lento al suo limite. Il salto e' il gradino del
    finecorsa descritto in cima al modulo.

    Una sola passata in avanti, e tre vincoli sulla velocita' di uscita da ogni
    pezzo:

      1. il limite del pezzo che si sta percorrendo;
      2. quanto l'accelerazione consente di guadagnare entrandoci a v_in;
      3. quanto basta a potersi ancora fermare in fondo ALLA CORSA.

    Il terzo e' quello che e' cambiato, ed e' tutta la differenza fra le due
    semantiche possibili. Guarda la distanza che resta fino alla FINE, non fino
    al confine successivo, e ignora i limiti piu' bassi che incontrera' per
    strada: il carroponte frena per fermarsi a terra, non per entrare piano
    nella zona, perche' della zona non sa niente finche' non ci arriva. La
    versione precedente guardava il confine successivo, e il risultato era una
    frenata anticipata che nessun impianto fa.

    Ignorare i limiti piu' bassi a valle e' lecito proprio perche' scendere di
    colpo si puo': se il limite di un pezzo piu' avanti e' sotto la velocita'
    con cui gli si arriva, non serve rallentare prima, basta il gradino.

    Il vincolo 3 continua pero' a risolvere da solo tutti i casi degeneri --
    zona di avvicinamento piu' corta del proprio spazio di frenata, corsa piu'
    corta della zona -- senza un solo ramo dedicato: li' e' la fine della corsa
    a essere vicina, e la velocita' scende da se' sotto quella di
    avvicinamento.
    """
    # quanta corsa resta dopo ogni confine: `coda[i]` e' la distanza dalla fine
    # all'INIZIO del pezzo i, e coda[n] = 0 e' il fondo corsa
    n = len(limiti)
    coda = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        coda[i] = coda[i + 1] + limiti[i][0]
    out: list[tuple[float, float]] = []
    v_in = 0.0  # si parte fermi
    for i, (lung, v_cap) in enumerate(limiti):
        v_out = min(
            v_cap,
            math.sqrt(v_in**2 + 2 * kin.a_max * lung),
            math.sqrt(2 * kin.decel * coda[i + 1]),
        )
        out.append((v_in, v_out))
        # IL GRADINO: nel pezzo successivo si entra alla velocita' con cui si e'
        # usciti da questo, abbassata di colpo al suo limite se lo supera
        v_in = min(v_out, limiti[i + 1][1]) if i + 1 < n else 0.0
    return tuple(out)


def _distanza_rampe(v_cap: float, v_in: float, v_out: float, kin: Kinematics) -> float:
    """Spazio minimo per salire da `v_in` a `v_cap` e tornare giu' a `v_out`:
    la soglia fra il profilo trapezoidale e quello triangolare.

    Con v_in = v_out = 0 e v_cap = v_max vale v_max^2/(2a) + v_max^2/(2d), cioe'
    esattamente la formula di prima."""
    return (v_cap**2 - v_in**2) / (2 * kin.a_max) + (v_cap**2 - v_out**2) / (
        2 * kin.decel
    )


def _picco_triangolare(
    lung: float, v_in: float, v_out: float, kin: Kinematics
) -> float:
    """Velocita' massima raggiunta quando la lunghezza non basta alla crociera:
    si accelera fino a v_p e da li' si frena, senza tratto piatto.

    (v_p^2 - v_in^2)/(2a) + (v_p^2 - v_out^2)/(2d) = lunghezza, da cui la radice
    qui sotto. I vincoli di `_velocita_di_confine` garantiscono che il
    risultato non stia mai sotto v_in ne' sotto v_out: il max e' li' solo per
    il pelo di errore numerico."""
    v_p = math.sqrt(
        (lung + v_in**2 / (2 * kin.a_max) + v_out**2 / (2 * kin.decel))
        * 2
        * kin.a_max
        * kin.decel
        / (kin.a_max + kin.decel)
    )
    return max(v_p, v_in, v_out)


def _tratti_di_pezzo(
    lung: float, v_cap: float, v_in: float, v_out: float, kin: Kinematics
) -> tuple[_Tratto, ...]:
    """I tratti ad accelerazione costante con cui si percorre UN pezzo a limite
    di velocita' costante, entrandoci a `v_in` e uscendone a `v_out`."""
    if lung <= 0:
        return ()
    d_rampe = _distanza_rampe(v_cap, v_in, v_out, kin)
    if lung >= d_rampe:
        # trapezoidale
        v_p = v_cap
        t_cruise = (lung - d_rampe) / v_cap
    else:
        # triangolare (non si raggiunge il limite di velocita')
        v_p = _picco_triangolare(lung, v_in, v_out, kin)
        t_cruise = 0.0
    out = []
    if v_p > v_in:
        out.append(_Tratto((v_p - v_in) / kin.a_max, v_in, kin.a_max))
    if t_cruise > 0:
        out.append(_Tratto(t_cruise, v_p, 0.0))
    if v_p > v_out:
        out.append(_Tratto((v_p - v_out) / kin.decel, v_p, -kin.decel))
    return tuple(out)


# La cache non e' un'ottimizzazione di comodo: il verificatore campiona la
# stessa tratta centinaia di volte, e ogni campione rifarebbe da capo lo stesso
# profilo. La chiave e' (distanza, cinematica), ed e' per poterla usare come
# chiave che `Kinematics` e `Approach` sono congelate.
@functools.lru_cache(maxsize=8192)
def _tratti(d: float, kin: Kinematics) -> tuple[_Tratto, ...]:
    """Il profilo completo della corsa `d`, tratto per tratto."""
    if d <= 0:
        return ()
    limiti = _limiti(d, kin)
    confini = _velocita_di_confine(limiti, kin)
    out: list[_Tratto] = []
    for (lung, v_cap), (v_in, v_out) in zip(limiti, confini):
        out.extend(_tratti_di_pezzo(lung, v_cap, v_in, v_out, kin))
    return tuple(out)


# --------------------------------------------------------------------------
# Le tre funzioni pubbliche
# --------------------------------------------------------------------------


def travel_time(distance: float, kin: Kinematics) -> float:
    """Tempo minimo [s] per percorrere `distance` [m] rispettando v_max, a_max,
    la decelerazione e -- dove c'e' -- la zona di avvicinamento.

    - Se la distanza e' sufficiente a raggiungere v_max, il profilo e'
      trapezoidale: accelerazione, tratto a velocita' costante, decelerazione.
    - Altrimenti il profilo e' triangolare: si accelera e poi si decelera
      subito, senza mai raggiungere v_max.
    - Con una zona di avvicinamento i profili diventano due, uno per pezzo di
      corsa, e il tempo e' la somma: il confine fra i due NON e' un punto di
      arresto. Lo si attraversa alla velocita' che si aveva, e se il pezzo
      successivo ha un limite piu' basso -- la zona in cui si scende a posare
      -- la velocita' ci cade sopra a gradino.

    Le rampe hanno pendenze diverse, quindi durate diverse: non si puo'
    contarne una e moltiplicarla per due.
    """
    d = abs(distance)
    if d == 0:
        return 0.0
    return sum(tr.dt for tr in _tratti(d, kin))


def position_profile(t: float, distance: float, kin: Kinematics) -> float:
    """Spazio percorso [m] al tempo `t` [s] dall'inizio del movimento
    (0 <= t <= travel_time(distance, kin)). Il segno di `distance` non conta:
    restituisce sempre uno spostamento positivo, e' compito del chiamante
    orientarlo nella direzione giusta (posizione_iniziale +/- risultato).

    Il VERSO del movimento, dove serve saperlo, sta nella cinematica e non qui:
    e' `Approach.at_end` a dire a quale capo della corsa cade la zona lenta.
    """
    d = abs(distance)
    if d == 0:
        return 0.0
    s = 0.0
    rimasto = t
    for tr in _tratti(d, kin):
        if rimasto <= 0:
            break
        dt = tr.dt if rimasto >= tr.dt else rimasto
        s += tr.v0 * dt + 0.5 * tr.a * dt * dt
        rimasto -= dt
    # Il clamp e' la stessa cortesia di prima verso chi chiede un istante fuori
    # intervallo -- lo faceva il vecchio `min(t, t_total)` -- piu' la difesa
    # dall'ultimo bit di errore accumulato sommando i tratti.
    return min(max(s, 0.0), d)


def profile_breakpoints(distance: float, kin: Kinematics) -> tuple[float, ...]:
    """Istanti [s], relativi all'inizio del movimento, in cui il profilo di
    posizione cambia tratto (gli "spigoli" della curva).

    - profilo trapezoidale: (0, t_su, t_su + t_cruise, t_total)
    - profilo triangolare:  (0, t_su, t_total)
    - distanza nulla:       (0.0,)
    - con avvicinamento:    gli spigoli di un pezzo di seguito a quelli
                            dell'altro, confine compreso

    Lo spigolo del triangolo NON e' a meta' durata: con due rampe di pendenza
    diversa il picco cade dove finisce l'accelerazione, e prenderlo a
    t_total/2 metterebbe il campione nel posto sbagliato -- che e' proprio il
    caso in cui la stima rigorosa dell'errore smetterebbe di essere rigorosa.

    Fra due spigoli consecutivi la posizione e' un polinomio di grado <= 2 in
    t. Campionando anche tutti gli spigoli si puo' quindi limitare in modo
    RIGOROSO l'errore commesso cercando un minimo su una griglia finita.

    Vale anche dove la velocita' fa un gradino: li' la posizione resta
    continua, cambia solo pendenza, e l'istante del salto e' per costruzione la
    fine dei tratti di un pezzo e l'inizio di quelli del successivo -- cioe' e'
    gia' uno spigolo, e la garanzia regge senza doverlo aggiungere a mano.
    """
    d = abs(distance)
    if d == 0:
        return (0.0,)
    out = [0.0]
    for tr in _tratti(d, kin):
        out.append(out[-1] + tr.dt)
    return tuple(out)


if __name__ == "__main__":
    # Auto-test rapido: il caso simmetrico di sempre, due asimmetrici, e gli
    # stessi tre con una zona di avvicinamento in ciascuno dei due versi.
    base = (
        Kinematics(v_max=1.0, a_max=0.5),
        Kinematics(v_max=1.0, a_max=0.5, d_max=2.0),
        Kinematics(v_max=1.0, a_max=2.0, d_max=0.5),
    )
    tutte = base + tuple(
        b.avvicinandosi(0.2, 3.0, scendendo=giu) for b in base for giu in (True, False)
    )
    for k in tutte:
        app = k.approach
        dove = "-" if app is None else ("in fondo" if app.at_end else "in testa")
        print(
            f"\nv_max={k.v_max}  a_max={k.a_max}  decel={k.decel}  "
            f"approach={'no' if app is None else app.speed} zona={dove}"
        )
        for dist in [0.1, 1.0, 5.0, 20.0]:
            T = travel_time(dist, k)
            # la posizione al tempo T deve combaciare con la distanza totale
            p_end = position_profile(T, dist, k)
            p_mid = position_profile(T / 2, dist, k)
            print(
                f"dist={dist:6.2f}  T={T:6.3f}s  pos(T)={p_end:6.3f}  "
                f"pos(T/2)={p_mid:6.3f}"
            )
            assert (
                abs(p_end - dist) < 1e-6
            ), "la posizione finale deve coincidere con la distanza"
            bps = profile_breakpoints(dist, k)
            assert bps[0] == 0.0 and abs(bps[-1] - T) < 1e-9, "spigoli incoerenti con T"
            assert list(bps) == sorted(bps), "gli spigoli devono essere crescenti"
            # il profilo deve essere monotono: non si torna mai indietro, e
            # nessun tratto puo' superare la velocita' massima
            passo = T / 2000
            campioni = [position_profile(passo * i, dist, k) for i in range(2001)]
            assert all(
                b >= a - 1e-9 for a, b in zip(campioni, campioni[1:])
            ), "il profilo non puo' tornare indietro"
            for a_, b_ in zip(campioni, campioni[1:]):
                v = (b_ - a_) / passo
                assert v <= k.v_max + 1e-6, "velocita' oltre il massimo"
                if app is None or app.distance >= dist:
                    continue
                # dentro la zona di avvicinamento nemmeno la velocita' di
                # avvicinamento puo' essere superata. Si guarda l'estremo del
                # campione PIU' LONTANO dal capo lento: cosi' si controllano
                # solo gli intervalli interamente dentro la zona, e non quello
                # che la attraversa -- li' la media e' legittimamente piu' alta
                da_capo = dist - a_ if app.at_end else b_
                if da_capo <= app.distance:
                    assert (
                        v <= min(app.speed, k.v_max) + 1e-6
                    ), "velocita' oltre quella di avvicinamento dentro la zona"
    # la zona di avvicinamento costa tempo, e non puo' farne guadagnare.
    # Il confronto va fatto fra una cinematica e LA SUA variante con zona: a
    # cinematiche diverse i tempi non sono paragonabili.
    for b in base:
        for giu in (True, False):
            k = b.avvicinandosi(0.2, 3.0, scendendo=giu)
            assert travel_time(20.0, k) > travel_time(
                20.0, b
            ), "l'avvicinamento deve costare"

    # SCENDENDO non si anticipa niente: finche' non scatta il finecorsa il
    # profilo e' identico a quello che si avrebbe senza zona, frenata compresa.
    # E' la differenza fra il gradino e la vecchia frenata anticipata, ed e'
    # l'unico modo di coglierla guardando solo le funzioni pubbliche.
    for b in base:
        k = b.avvicinandosi(0.2, 3.0, scendendo=True)
        dist, x_finecorsa = 20.0, 20.0 - 3.0
        T = travel_time(dist, k)
        for i in range(2001):
            t = T * i / 2000
            s = position_profile(t, dist, k)
            if s >= x_finecorsa:
                break
            assert (
                abs(s - position_profile(t, dist, b)) < 1e-9
            ), "prima del finecorsa il profilo deve essere quello senza zona"

    # SALENDO il gradino non c'e': la zona sta in partenza, si e' fermi, e
    # l'unica cosa che un motore sappia fare e' accelerare.
    for b in base:
        k = b.avvicinandosi(0.2, 3.0, scendendo=False)
        dt = 1e-4
        assert (
            position_profile(dt, 20.0, k) / dt < 0.2
        ), "in salita la velocita' non puo' partire a gradino"

    print("\nOK: kinematics.py funziona correttamente")
