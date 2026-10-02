"""
avvio.py
--------
Il PUNTO DI AVVIO del ciclogramma: l'istante del ciclo in cui la linea si puo'
mettere in marcia (o fermare) senza dover inventare nessuna manovra.

Un ciclogramma e' periodico e non ha un inizio: il calcolo lo scrive a partire
da un'origine qualsiasi -- il prelievo della prima mossa del primo carroponte --
che non vuol dire niente per chi deve far partire l'impianto. Chi lo avvia ha
invece bisogno di UNO istante preciso, perche' in quell'istante i carroponti
devono essere portati a mano nella posizione da cui il ciclo riparte, e quella
posizione deve essere una in cui si possano lasciare:

  - FERMI: nessuna traslazione in corso, nessuna corsa del gancio;
  - IN POSIZIONE BASSA: il gancio in fondo alla corsa della vasca su cui stanno,
    cioe' dove lo lascia un rilascio e dove lo trova una presa. E' la quota in
    cui il carroponte non scavalca niente e non tiene niente sospeso;
  - NE' AL CARICO NE' ALLO SCARICO: le due stazioni agli estremi sono quelle
    presidiate, dove il pezzo viene appeso e staccato, e lasciarci un carroponte
    fermo vuol dire tenere occupato il posto dell'operatore.

Non sempre un istante cosi' esiste: basta un carroponte che nel suo giro non
stia mai fermo in basso nello stesso momento degli altri. Allora non si rinuncia
-- un punto di avvio serve comunque -- e si prende il MENO SBAGLIATO: quello in
cui la somma di quanto manca a ciascun carroponte, in secondi, e' minima. Il
numero che ne esce si legge come "per avviare da qui bisogna spostare a mano i
carroponti di tanti secondi di percorso".

A quell'errore -- che di solito e' zero -- ci arriva quasi sempre PIU' DI UN
tratto del ciclo, e sono tratti lontani fra loro. Sono equivalenti, e sceglierne
uno non e' una decisione che questo modulo abbia gli elementi per prendere:
quale convenga dipende dall'impianto. `trova_avvii` li restituisce tutti, in
ordine di tempo, e nella finestra si scorrono col pulsante "Avvio";
`trova_avvio` da' il primo, che e' quello che si scrive dove non c'e' nessuno a
scegliere.

Il modulo non decide niente sul ciclogramma e non lo cambia: legge i segmenti
che ci sono gia' -- gli stessi che disegnano il grafico e che muovono la
simulazione -- e ne ricava un istante.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from kinematics import position_profile
from model import ProblemData, Segment, Solution

# Tolleranza su una coincidenza di POSIZIONI [mm]. Le posizioni dei segmenti
# vengono dalle vasche, non da un conto: o coincidono o sono lontane metri.
_TOL_X = 1e-6

# Tolleranza su una coincidenza di TEMPI [s]. I tempi invece sono ricalcolati in
# virgola mobile da durate arrotondate al tick, e due istanti che il modello
# considera uguali possono differire di qualche frazione di millisecondo.
_TOL_T = 1e-6


@dataclass(frozen=True)
class Riposo:
    """Una finestra in cui un carroponte sta fermo, col gancio in fondo, su una
    vasca che non e' ne' il carico ne' lo scarico.

    I due istanti sono nella scala del ciclo del carroponte, la stessa dei
    segmenti: possono essere negativi o superare il takt time, e vanno letti
    modulo T."""

    t_inizio: float
    t_fine: float
    x: float  # [mm] dove sta, lungo la rotaia
    stazione: int  # la tappa del percorso su cui e' fermo


@dataclass(frozen=True)
class PosizioneAvvio:
    """Dove sta un carroponte all'istante di avvio, e quanto gli manca per
    essere a riposo."""

    carro: int  # indice della zona (0-based); +1 per il numero da mostrare
    x: float  # [mm] posizione lungo la rotaia all'istante di avvio
    vasca: Optional[str]  # sopra quale vasca si trova, None se e' per strada
    # [s] quanto manca perche' sia fermo in posizione bassa fuori dal carico e
    # dallo scarico. Zero vuol dire che ci e' gia'; il valore e' la distanza nel
    # tempo dalla finestra di riposo piu' vicina, avanti o indietro.
    errore: float
    # Il carroponte non ha NESSUNA finestra di riposo in tutto il giro: non c'e'
    # un istante che lo accontenti, e il suo errore non entra nel confronto fra
    # istanti perche' sarebbe lo stesso per tutti.
    mai: bool = False

    @property
    def a_riposo(self) -> bool:
        return not self.mai and self.errore <= _TOL_T


@dataclass(frozen=True)
class Avvio:
    """L'istante di avvio scelto, e lo stato della linea in quell'istante.

    `indice` e `totale` dicono che posto occupa fra gli istanti EQUIVALENTI --
    quelli che sbagliano esattamente quanto lui -- perche' quasi sempre ce n'e'
    piu' d'uno e non c'e' nessuna ragione tecnica per preferirne uno: la
    ragione la sa chi conosce l'impianto. Vedi `trova_avvii`."""

    t: float  # [s] dentro il ciclo, in [0, T)
    posizioni: list[PosizioneAvvio]
    indice: int = 0  # 0-based, in ordine di tempo crescente
    totale: int = 1

    @property
    def errore(self) -> float:
        """[s] la somma di quanto manca ai carroponti. Zero = punto di avvio
        esatto."""
        return sum(p.errore for p in self.posizioni if not p.mai)

    @property
    def esatto(self) -> bool:
        """Se in questo istante TUTTI i carroponti sono davvero a riposo."""
        return bool(self.posizioni) and all(p.a_riposo for p in self.posizioni)


# --------------------------------------------------------------------------
# Le finestre di riposo di un carroponte
# --------------------------------------------------------------------------


def stazione_di_riposo(data: ProblemData, x: float) -> Optional[int]:
    """La tappa su cui un carroponte fermo in `x` si puo' lasciare, se c'e'.

    None quando in `x` non c'e' nessuna tappa -- il carroponte e' per strada o
    su uno svincolo -- e anche quando quella posizione e' il CARICO o lo
    SCARICO: quelle due sono escluse per posizione e non per indice, perche' se
    la ricetta ci ripassa a meta' percorso resta comunque la vasca presidiata,
    e un carroponte fermo la' da' lo stesso fastidio."""
    vietate = (
        data.approach_position(0),
        data.approach_position(data.n_stations - 1),
    )
    if any(abs(x - v) <= _TOL_X for v in vietate):
        return None
    for s in range(1, data.n_stations - 1):
        if abs(data.approach_position(s) - x) <= _TOL_X:
            return s
    return None


def _coda_ferma_in_basso(
    data: ProblemData, fasi: list, stazione: int, *, dalla_fine: bool
) -> float:
    """Quanti secondi, agli estremi di una presa o di un rilascio, il carroponte
    e' gia' (o e' ancora) fermo col gancio in fondo alla corsa.

    Sono l'AGGANCIO in testa alla presa e lo SGANCIO in coda al rilascio: il
    gancio e' in fondo, non si muove ne' in su ne' di lato, e il telaio sta
    appoggiato in vasca. Contarli allarga la finestra di riposo oltre l'attesa
    che sta li' accanto, ed e' tempo di riposo vero -- su un impianto quello e'
    il momento in cui il carroponte e' piu' fermo di tutto il giro.

    Le fasi si guardano una per una e si smette alla prima che non va: una fase
    che alza il gancio, che trasla, o che lo tiene a una quota diversa dal fondo
    chiude la finestra."""
    fondo = -data.corsa_verticale(stazione)
    quanto = 0.0
    for f in reversed(fasi) if dalla_fine else fasi:
        if f.trasla or f.z_start != f.z_end or abs(f.z_start - fondo) > _TOL_X:
            break
        quanto += f.duration
    return quanto


def finestre_di_riposo(data: ProblemData, segs: list[Segment]) -> list[Riposo]:
    """Le finestre di riposo di UN carroponte, in ordine di tempo.

    Si leggono dai suoi segmenti, e sono di due tipi che si saldano fra loro:

      - le ATTESE (`wait`), che sono per definizione il carroponte fermo sopra
        una vasca. Il gancio li' sta in fondo: e' dove lo lascia il rilascio che
        precede l'attesa e dove lo prende la presa che la segue, e lungo un
        rientro a gancio basso non risale mai;
      - l'AGGANCIO e lo SGANCIO, gli istanti fermi in fondo corsa che stanno in
        testa alla presa e in coda al rilascio (vedi `_coda_ferma_in_basso`).

    Le attese sopra il carico e sopra lo scarico non ci sono: li' il carroponte
    non si puo' lasciare. Per la stessa ragione non c'e' niente di cio' che
    avviene su una zona di cambio quota -- che esiste solo a quelle due tappe.

    Una nota per chi confronta con la simulazione: quando due vasche hanno corse
    diverse e il gancio trasla basso fra l'una e l'altra, il dislivello va messo
    da qualche parte, e `simulazione._quote_a_vuoto` lo disegna DENTRO l'attesa.
    E' una convenzione di disegno -- il modello non da' nessun tempo alle corse
    verticali a vuoto -- e non toglie l'attesa dalle finestre: il carroponte e'
    comunque fermo sopra una vasca col gancio calato, che e' la condizione che
    qui si cerca.

    Le finestre adiacenti si fondono in una sola: un rilascio che finisce, lo
    sgancio, e l'attesa che segue sono un unico tratto di tempo in cui il
    carroponte sta fermo, e spezzarlo in tre non vorrebbe dire niente."""
    if not segs:
        return []
    ordinati = sorted(segs, key=lambda s: (s.t_start, s.t_end))
    grezze: list[tuple[float, float, float]] = []  # (inizio, fine, x)

    for s in ordinati:
        if s.kind == "wait":
            grezze.append((s.t_start, s.t_end, s.x_start))
        elif s.kind == "loaded" and s.move is not None:
            # La presa comincia `pick_time_at` secondi prima del tratto a
            # carico e il rilascio finisce altrettanto dopo: e' lo stesso conto
            # che fanno il disegno e la simulazione, e il tratto a carico e'
            # l'unico che c'e' sempre ed e' uno solo per mossa.
            k = s.move
            testa = _coda_ferma_in_basso(
                data, data.pick_phases(k), k, dalla_fine=False
            )
            if testa > 0:
                t0 = s.t_start - data.pick_time_at(k)
                grezze.append((t0, t0 + testa, data.approach_position(k)))
            coda = _coda_ferma_in_basso(
                data, data.release_phases(k + 1), k + 1, dalla_fine=True
            )
            if coda > 0:
                t1 = s.t_end + data.release_time_at(k + 1)
                grezze.append((t1 - coda, t1, data.approach_position(k + 1)))

    fuori: list[Riposo] = []
    for inizio, fine, x in sorted(grezze):
        stazione = stazione_di_riposo(data, x)
        if stazione is None or fine <= inizio + _TOL_T:
            continue
        if (
            fuori
            and abs(fuori[-1].x - x) <= _TOL_X
            and inizio <= fuori[-1].t_fine + _TOL_T
        ):
            ultimo = fuori[-1]
            fuori[-1] = Riposo(
                ultimo.t_inizio, max(ultimo.t_fine, fine), x, stazione
            )
        else:
            fuori.append(Riposo(inizio, fine, x, stazione))
    return fuori


def posizione_a(segs: list[Segment], t: float, T: float) -> float:
    """Dove sta il carroponte, lungo la rotaia, all'istante `t` letto modulo T.

    Serve a dire DOVE va portato ciascun carroponte all'istante di avvio, anche
    quando quell'istante non e' per lui una finestra di riposo. Il profilo e'
    quello vero (accelerazione, crociera, frenata), lo stesso che disegna la
    traiettoria: un'interpolazione lineare darebbe una posizione che il
    carroponte in quell'istante non ha."""
    t0 = segs[0].t_start
    tau = t0 + (t - t0) % T
    for s in segs:
        if s.t_start - _TOL_T <= tau <= s.t_end + _TOL_T:
            if abs(s.x_end - s.x_start) <= _TOL_X or s.t_end <= s.t_start:
                return s.x_start
            if s.kin is None:
                frazione = (tau - s.t_start) / (s.t_end - s.t_start)
                return s.x_start + (s.x_end - s.x_start) * frazione
            d = s.x_end - s.x_start
            segno = 1.0 if d >= 0 else -1.0
            return s.x_start + segno * position_profile(
                tau - s.t_start, abs(d), s.kin
            )
    # Fra due segmenti non ci sono buchi, ma se un arrotondamento ne aprisse
    # uno largo un millisecondo e' meglio dare la posizione del segmento
    # precedente che far saltare il conto.
    return min(segs, key=lambda s: abs(s.t_start - tau)).x_start


def vasca_a(data: ProblemData, x: float) -> Optional[str]:
    """Sopra quale vasca sta un carroponte che si trova in `x`, se e' sopra una.

    Si guardano sia il punto di approccio che la vasca stessa: di norma sono lo
    stesso posto, e differiscono solo al carico e allo scarico serviti da una
    zona di cambio quota -- dove il carroponte parcheggia fuori dal campo delle
    vasche ma durante la presa ci entra."""
    for st in range(data.n_stations):
        if (
            abs(data.approach_position(st) - x) <= _TOL_X
            or abs(data.station_position(st) - x) <= _TOL_X
        ):
            return data.route[st].tank_id
    return None


# --------------------------------------------------------------------------
# La ricerca dell'istante
# --------------------------------------------------------------------------


def _nel_periodo(finestre: list[Riposo], T: float) -> list[tuple[float, float]]:
    """Le finestre portate dentro il periodo e fuse fra loro: `(a, b)` con `a`
    in [0, T) e `b` fino ad `a + T`.

    Un `b` oltre T non e' un errore: e' una finestra A CAVALLO dell'origine, e
    ce n'e' quasi sempre una. Il ciclo di un carroponte comincia con la presa
    della sua prima mossa, cioe' con l'AGGANCIO -- che e' riposo -- e finisce
    con l'attesa che la precede: le due si toccano, e spezzarle in due pezzi
    agli estremi del periodo le farebbe sembrare due finestre corte dove ce n'e'
    una lunga. Tutto il resto del modulo legge le finestre in modo circolare, e
    non ha bisogno che stiano dentro [0, T)."""
    grezze: list[tuple[float, float]] = []
    for f in finestre:
        durata = min(f.t_fine - f.t_inizio, T)
        if durata <= _TOL_T:
            continue
        a = f.t_inizio % T
        grezze.append((a, a + durata))
    if not grezze:
        return []
    grezze.sort()
    unite = [grezze[0]]
    for a, b in grezze[1:]:
        ua, ub = unite[-1]
        if a <= ub + _TOL_T:
            unite[-1] = (ua, max(ub, b))
        else:
            unite.append((a, b))
    # Il periodo si richiude: se l'ultima finestra rientra dentro la prima,
    # sono la stessa finestra vista da due parti.
    if len(unite) > 1:
        a0, b0 = unite[0]
        an, bn = unite[-1]
        if bn - T >= a0 - _TOL_T:
            unite[0] = (an, max(bn, b0 + T))
            unite.pop()
    return [(a, min(b, a + T)) for a, b in unite]


def _distanza(t: float, finestre: list[tuple[float, float]], T: float) -> float:
    """Quanto manca, in secondi, perche' l'istante `t` cada in una finestra.

    E' una distanza CIRCOLARE: il ciclo si richiude, e un carroponte che e' a
    riposo tre secondi dopo la fine del periodo lo e' anche tre secondi dopo
    l'istante zero. Zero quando `t` e' dentro una finestra."""
    migliore = float("inf")
    for a, b in finestre:
        if (t - a) % T <= (b - a) + _TOL_T:
            return 0.0
        migliore = min(migliore, (t - b) % T, (a - t) % T)
    return migliore


def _estensione(
    t: float, finestre: list[tuple[float, float]], T: float
) -> tuple[float, float]:
    """Di quanto si puo' arretrare e di quanto si puo' avanzare partendo da `t`
    senza uscire dalla finestra che lo contiene. (0, 0) se `t` e' fuori da
    tutte.

    E' il MARGINE del carroponte su quell'istante: serve a scegliere, fra tutti
    gli istanti buoni, quello che ne lascia il piu' possibile da entrambe le
    parti."""
    for a, b in finestre:
        dietro = (t - a) % T
        if dietro <= (b - a) + _TOL_T:
            return dietro, (b - a) - dietro
    return 0.0, 0.0


def trova_avvii(data: ProblemData, solution: Solution) -> list[Avvio]:
    """TUTTI gli istanti di avvio equivalenti, in ordine di tempo crescente.

    Si guardano gli istanti CANDIDATI, che sono gli estremi delle finestre di
    riposo: fra due estremi consecutivi la somma degli errori e' lineare in `t`,
    quindi un minimo non puo' nascondersi nel mezzo -- nel mezzo di un buco ci
    sta il massimo, non il minimo. Si tiene l'errore piu' piccolo.

    A quell'errore ci arriva quasi sempre PIU' DI UN TRATTO del ciclo, e sono
    tratti lontani fra loro: con due carroponti che si incrociano, per dire, c'e'
    il momento in cui tutti e due stanno fermi in basso nella prima meta' del
    giro e quello in cui ci stanno nella seconda. Sono buoni uguali, e sceglierne
    uno sarebbe una decisione che questo modulo non ha gli elementi per prendere:
    quale convenga davvero lo sa chi conosce l'impianto -- da dove si entra, dove
    si vuole il pezzo quando si riparte. Si restituiscono quindi tutti, e chi
    guarda li scorre.

    Due candidati consecutivi che stanno tutti e due al minimo delimitano un
    tratto in cui l'errore RESTA al minimo: fra loro e' lineare, e una funzione
    lineare che vale lo stesso ai due estremi e' costante. I tratti si formano
    cosi', e si spezzano al primo candidato che sta piu' in alto.

    Di ogni tratto si restituisce UN istante:

      - se l'errore e' zero, il PUNTO DI MEZZO -- il primo estremo e' l'istante
        in cui l'ultimo carroponte si e' appena fermato, e avviare esattamente
        li' vuol dire non avere nessun margine ne' prima ne' dopo;
      - altrimenti il PRIMO, perche' a pari errore si tiene il primo.

    Lista vuota se non c'e' niente da leggere."""
    T = solution.T
    if not T or T <= 0 or not solution.segments_per_hoist:
        return []

    carri: list[tuple[int, list[Segment], list[tuple[float, float]]]] = []
    for h, segs in enumerate(solution.segments_per_hoist):
        if not segs:
            continue  # zona senza nessuna mossa assegnata: non e' di nessuno
        carri.append((h, segs, _nel_periodo(finestre_di_riposo(data, segs), T)))
    if not carri:
        return []

    # I candidati: tutti gli SPIGOLI della somma degli errori, cioe' gli istanti
    # in cui una delle distanze cambia pendenza. Sono di due specie, e servono
    # tutte e due:
    #
    #   - gli ESTREMI delle finestre, dove una distanza entra o esce dallo zero.
    #     Sono gli unici in cui il minimo si puo' trovare;
    #   - i COLMI DEI BUCHI, a meta' fra la fine di una finestra e l'inizio
    #     della successiva, dove la distanza smette di crescere e comincia a
    #     calare. Li' un minimo non c'e' mai -- la pendenza della somma scende
    #     di due, quindi se stava calando continua a calare -- ma senza di loro
    #     non si saprebbe che l'errore, fra due candidati che stanno tutti e due
    #     al minimo, nel mezzo e' RISALITO: ed e' proprio cosi' che due tratti
    #     buoni distinti verrebbero scambiati per uno solo.
    #
    # Piu' l'istante zero, che serve quando un carroponte e' a riposo per tutto
    # il periodo e quindi non ha nessun estremo da offrire.
    candidati_s = {0.0}
    for _, _, finestre in carri:
        for i, (a, b) in enumerate(finestre):
            candidati_s.add(a % T)
            candidati_s.add(b % T)
            a_dopo = finestre[(i + 1) % len(finestre)][0]
            candidati_s.add((b + ((a_dopo - b) % T) / 2.0) % T)
    candidati = sorted(candidati_s)
    con_finestre = [f for _, _, f in carri if f]

    def errore(t: float) -> float:
        return sum(_distanza(t, f, T) for f in con_finestre)

    errori = [errore(t) for t in candidati]
    minimo = min(errori)
    soglia = minimo + _TOL_T * max(1, len(con_finestre))

    tratti: list[list[float]] = []
    aperto = False
    for t, e in zip(candidati, errori):
        if e > soglia:
            aperto = False
        elif aperto:
            tratti[-1].append(t)
        else:
            tratti.append([t])
            aperto = True
    # Il periodo si richiude: fra l'ultimo candidato e il primo (che e' lo zero)
    # non ci sono estremi, quindi li' l'errore e' lineare. Se stanno al minimo
    # tutti e due, il tratto che finisce in fondo e quello che comincia da capo
    # sono lo stesso tratto, visto da due parti.
    if len(tratti) > 1 and errori[0] <= soglia and errori[-1] <= soglia:
        tratti[0] = tratti.pop() + tratti[0]

    esatto = minimo <= _TOL_T * max(1, len(con_finestre))
    istanti = []
    for tratto in tratti:
        t = tratto[0]
        if esatto and con_finestre:
            # Il margine lo misura ogni carroponte sulla finestra che contiene
            # l'istante, e quello che vale per tutti e' il piu' stretto. Si
            # misura dal primo estremo del tratto, ma il risultato non dipende
            # da quale punto del tratto si parta: e' sempre il suo centro.
            margini = [_estensione(t, f, T) for f in con_finestre]
            dietro = min(d for d, _ in margini)
            avanti = min(a for _, a in margini)
            t += (avanti - dietro) / 2.0
        istanti.append(t % T)

    fuori = []
    for i, t in enumerate(sorted(istanti)):
        posizioni = []
        for h, segs, finestre in carri:
            x = posizione_a(segs, t, T)
            posizioni.append(
                PosizioneAvvio(
                    carro=h,
                    x=x,
                    vasca=vasca_a(data, x),
                    errore=0.0 if not finestre else _distanza(t, finestre, T),
                    mai=not finestre,
                )
            )
        fuori.append(
            Avvio(t=t, posizioni=posizioni, indice=i, totale=len(istanti))
        )
    return fuori


def trova_avvio(data: ProblemData, solution: Solution) -> Optional[Avvio]:
    """Il PRIMO degli istanti di avvio, o None se non ce n'e' nessuno.

    E' quello che si scrive quando non c'e' nessuno a scegliere: il file dei
    risultati, il grafico salvato da riga di comando. Gli altri, altrettanto
    buoni, li da' `trova_avvii`, e nella finestra si scorrono col pulsante."""
    avvii = trova_avvii(data, solution)
    return avvii[0] if avvii else None


def righe_di_riepilogo(
    avvio: Optional[Avvio], carri: Optional[dict] = None
) -> list[tuple[str, object, str]]:
    """Il punto di avvio come righe `(etichetta, valore, nota)`, da scrivere sia
    nel foglio Riepilogo che nel pannello della finestra.

    Una definizione sola per i due posti: il Riepilogo dell'Excel e quello a
    schermo devono dire la stessa cosa con le stesse parole, altrimenti chi
    confronta il file con lo schermo si chiede quale dei due abbia ragione. Le
    tre colonne sono quelle del Riepilogo dell'Excel (`voce`); a schermo si
    scrivono una dietro l'altra.

    `carri` traduce l'indice di zona nel numero di carroponte da mostrare, come
    nella simulazione: in un ciclogramma composto a meta' i due numeri non
    coincidono."""
    if avvio is None:
        return [
            (
                "Istante di avvio",
                "-",
                "non calcolabile: manca il takt time o le traiettorie",
            )
        ]

    def numero(h: int) -> int:
        n = h if carri is None else carri.get(h, h)
        return (h if n is None else n) + 1

    # Che ce ne siano altri va detto QUI e non solo sul pulsante che li scorre:
    # chi legge il foglio dei risultati il pulsante non ce l'ha, e senza questa
    # riga crederebbe che l'istante scritto sia l'unico possibile.
    nota = "s dall'origine del ciclo: da qui la linea si mette in marcia"
    if avvio.totale > 1:
        nota += (
            f" (il {avvio.indice + 1}o di {avvio.totale} istanti equivalenti; "
            f"nella finestra si scorrono col pulsante 'Avvio')"
        )
    righe: list[tuple[str, object, str]] = [
        ("Istante di avvio", round(avvio.t, 2), nota)
    ]
    if avvio.esatto:
        righe.append(
            (
                "Stato all'avvio",
                "esatto",
                "tutti i carroponti fermi in posizione bassa, "
                "fuori dal carico e dallo scarico",
            )
        )
    else:
        righe.append(
            (
                "Stato all'avvio",
                "approssimato",
                f"nessun istante accontenta tutti i carroponti: "
                f"errore totale {avvio.errore:.2f} s, il minore possibile",
            )
        )
    for p in sorted(avvio.posizioni, key=lambda p: numero(p.carro)):
        if p.mai:
            nota = f"a {p.x:.0f} mm - mai fermo in posizione bassa nel suo giro"
        elif p.errore > _TOL_T:
            nota = (
                f"a {p.x:.0f} mm - gli mancano {p.errore:.2f} s "
                f"per essere a riposo"
            )
        else:
            nota = f"fermo a {p.x:.0f} mm, gancio in basso"
        righe.append(
            (f"   Carroponte {numero(p.carro)}", p.vasca or "in transito", nota)
        )
    return righe
