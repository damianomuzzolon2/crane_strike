"""
programma_carri.py
------------------
Il ciclogramma tradotto nel PROGRAMMA che ogni carro esegue: una lista di
passi -- comando e tre parametri -- nel formato delle tabelle del PLC.

I comandi sono quelli del PLC:

    Lifting           param1 = quota (Pos.Top, Pos.Btm, e con una zona di
                      cambio quota anche Pos.Int1 e Pos.Int2), param2 = velocita'
    Transfer          param1 = "Pos." + vasca d'arrivo, param2 = velocita'
    Transfer Outlet   come Transfer, verso lo svincolo POSITIVO della vasca, o
                      verso il punto di cambio quota del carico
    Transfer Inlet    come Transfer, verso lo svincolo NEGATIVO della vasca, o
                      verso il punto di cambio quota dello scarico
    Dripping          param1 = secondi di sgocciolamento
    Pause             param1 = secondi di attesa
    External Request  prima di andare al carico o allo scarico
    Crane Syncro      param1 = carro da aspettare, param2 = il passo di quel
                      carro in cui si e' tolto di mezzo
    End Program       chiude il giro, che ricomincia dal passo 1

La velocita' e' `VELOCITA_CARICO` col telaio appeso e `VELOCITA_VUOTO` senza.

Non c'e' niente di nuovo da calcolare: i passi si leggono dai `Segment` del
ciclogramma, e quelli della presa e del rilascio dalle loro FASI
(`pick_phases` / `release_phases`), le stesse che ne danno la durata. Cosi'
il programma e' per costruzione quello che il ciclogramma disegna, e la somma
delle durate dei passi fa il takt time.

Sta sopra `model.py` e `avvio.py` e li legge soltanto: lo usa `excel_io` per
il foglio del file dei risultati.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from avvio import Avvio, finestre_di_riposo
from model import LiftPhase, ProblemData, Segment, Solution, coppie_interblocco

# I due valori di param2 per Lifting e Transfer: sono i codici di velocita'
# del PLC, non mm/s.
VELOCITA_CARICO = 9
VELOCITA_VUOTO = 10

LIFTING = "Lifting"
TRANSFER = "Transfer"
TRANSFER_OUTLET = "Transfer Outlet"
TRANSFER_INLET = "Transfer Inlet"
# Tutti e tre muovono il carro lungo la rotaia: per chi cerca dove arriva e da
# dove parte sono la stessa cosa.
TRASFERIMENTI = (TRANSFER, TRANSFER_OUTLET, TRANSFER_INLET)
DRIPPING = "Dripping"
PAUSE = "Pause"
EXTERNAL_REQUEST = "External Request"
CRANE_SYNCRO = "Crane Syncro"
END_PROGRAM = "End Program"

# Tolleranza [mm] con cui una posizione della rotaia si riconosce come quella
# di una vasca, di uno svincolo o di un punto di cambio quota: e' la stessa
# del verificatore (`verify.prenotazioni`).
_TOLLERANZA_MM = 1.0


@dataclass
class Passo:
    """Un passo del programma di un carro."""

    comando: str
    param1: object = 0
    param2: object = 0
    param3: object = 0
    # [s] quando comincia e quanto dura, sulla scala dei tempi dei Segment.
    # Non finiscono nel foglio: servono a mettere i passi in fila, a decidere
    # da dove parte il programma e a chi riferire le sincronizzazioni.
    t: float = 0.0
    durata: float = 0.0
    # Per i soli Transfer: la vasca del percorso su cui il carro arriva, o
    # None se arriva su uno svincolo o su un punto qualunque della rotaia --
    # li' sta ancora viaggiando, come per l'interblocco (`verify.prenotazioni`).
    vasca: Optional[str] = None
    # Per i soli Crane Syncro: il carro (0-based) da aspettare e il suo
    # Transfer che lo porta fuori dai piedi. Il NUMERO del passo si risolve
    # solo alla fine, quando i programmi di tutti i carri sono completi: ogni
    # passo aggiunto prima lo sposterebbe.
    aspetta: Optional[tuple[int, "Passo"]] = field(default=None, repr=False)

    def riga(self) -> list:
        return [self.comando, self.param1, self.param2, self.param3]


@dataclass
class ProgrammaCarri:
    """I programmi di tutti i carri, uno per zona, e le note su cio' che il
    formato non riesce a dire."""

    programmi: list[list[Passo]]
    note: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Posizioni e quote
# --------------------------------------------------------------------------


def nome_posizione(
    data: ProblemData, x: float
) -> tuple[str, str, Optional[str]]:
    """Come il PLC raggiunge il punto `x` della rotaia: il comando, la
    posizione, e la vasca del percorso che ci sta (None se non e' una vasca).

    Le vasche si raggiungono con Transfer e si chiamano col loro nome. I punti
    che vasche non sono si chiamano col nome della vasca a cui appartengono, e
    a dire QUALE punto e' il comando:

      - Transfer Outlet: lo svincolo positivo, o il punto di cambio quota del
        carico (che sta dalla parte positiva del carico);
      - Transfer Inlet: lo svincolo negativo, o il punto di cambio quota dello
        scarico (che sta dalla parte negativa dello scarico).

    Un punto di passaggio messo a mano in mezzo alla rotaia non ha nome, e si
    scrive in millimetri."""
    del_percorso = {s.tank_id for s in data.route}
    for stazione, zona, comando in (
        (0, data.cambio_quota_carico, TRANSFER_OUTLET),
        (data.n_stations - 1, data.cambio_quota_scarico, TRANSFER_INLET),
    ):
        # il carro sul punto di cambio quota e' gia' al carico (o allo
        # scarico): e' da li' che comincia la presa
        if zona is not None and abs(zona.position - x) < _TOLLERANZA_MM:
            vasca = data.route[stazione].tank_id
            return comando, f"Pos.{vasca}", vasca
    for t in data.tanks.values():
        if abs(t.position - x) < _TOLLERANZA_MM:
            return TRANSFER, f"Pos.{t.id}", (t.id if t.id in del_percorso else None)
    for t in data.tanks.values():
        if t.svincolo_pos is not None and abs(t.svincolo_pos - x) < _TOLLERANZA_MM:
            return TRANSFER_OUTLET, f"Pos.{t.id}", None
        if t.svincolo_neg is not None and abs(t.svincolo_neg - x) < _TOLLERANZA_MM:
            return TRANSFER_INLET, f"Pos.{t.id}", None
    return TRANSFER, f"Pos.X{x:.0f}", None


def nome_quota(data: ProblemData, stazione: int, z: float) -> str:
    """La quota `z` del gancio (0 = quota di trasporto, negativa verso il
    basso) alla tappa data, come la chiama il PLC.

    Cima e fondo si guardano per primi: se una quota intermedia coincide con
    uno dei due -- `intermediate2` uguale alla corsa totale, per esempio -- il
    punto fisico e' quello, e il nome giusto e' il suo."""
    if abs(z) < 1e-6:
        return "Pos.Top"
    zona = data.zona_cambio_quota(stazione)
    if zona is None or abs(z - zona.z_basso) < 1e-6:
        return "Pos.Btm"
    if abs(z - zona.z_int1) < 1e-6:
        return "Pos.Int1"
    if abs(z - zona.z_int2) < 1e-6:
        return "Pos.Int2"
    return "Pos.Btm"


def _velocita(carico: bool) -> int:
    return VELOCITA_CARICO if carico else VELOCITA_VUOTO


# --------------------------------------------------------------------------
# Dai segmenti ai passi
# --------------------------------------------------------------------------


def _passi_fasi(
    data: ProblemData, fasi: list[LiftPhase], stazione: int, t0: float
) -> list[Passo]:
    """I passi di una presa o di un rilascio, fase per fase.

    Aggancio e sgancio non sono comandi: sono tempo di gancio fermo in fondo
    corsa, che il PLC fa da se' dentro il Lifting. Una fase senza movimento e
    senza durata non produce niente -- la presa al carico, dove la corsa e'
    zero, e' un caso normale."""
    passi = []
    t = t0
    riposo = data.quota_di_riposo(stazione)
    for f in fasi:
        if f.duration > 0:
            if f.trasla:
                comando, nome, vasca = nome_posizione(data, f.x_end)
                passi.append(
                    Passo(comando, nome, _velocita(f.loaded), t=t,
                          durata=f.duration, vasca=vasca)
                )
            elif abs(f.z_end - f.z_start) > 1e-9:
                passi.append(
                    Passo(LIFTING, nome_quota(data, stazione, f.z_end),
                          _velocita(f.loaded), t=t, durata=f.duration)
                )
            elif f.loaded and f.z_start > riposo + 1e-9:
                # fermo col telaio appeso, sopra la quota a cui riposa: e' lo
                # sgocciolamento (lo sgancio e' fermo col telaio giu')
                passi.append(
                    Passo(DRIPPING, int(round(f.duration)), t=t, durata=f.duration)
                )
        t += f.duration
    return passi


def _passi_base(data: ProblemData, segs: list[Segment]) -> list[Passo]:
    """I passi di un carro in un periodo, nell'ordine dei suoi segmenti, senza
    ancora le richieste e le sincronizzazioni."""
    passi: list[Passo] = []
    fatti: set[tuple[int, str]] = set()
    trasportati: set[int] = set()
    for s in segs:
        durata = s.t_end - s.t_start
        if s.kind == "loaded":
            trasportati.add(s.move)
            comando, nome, vasca = nome_posizione(data, s.x_end)
            passi.append(
                Passo(comando, nome, VELOCITA_CARICO, t=s.t_start,
                      durata=durata, vasca=vasca)
            )
        elif s.kind in ("pick", "release", "quota") and s.move is not None:
            # Una presa (o un rilascio) con una zona di cambio quota e' fatta
            # di piu' segmenti: i passi si leggono una volta sola dalle FASI,
            # al primo. Una traslazione di cambio quota e' della presa se
            # viene prima del trasporto col pezzo, del rilascio se dopo.
            presa = s.kind == "pick" or (
                s.kind == "quota" and s.move not in trasportati
            )
            chiave = (s.move, "presa" if presa else "rilascio")
            if chiave in fatti:
                continue
            fatti.add(chiave)
            stazione = s.move if presa else s.move + 1
            fasi = data.pick_phases(stazione) if presa else data.release_phases(stazione)
            passi.extend(_passi_fasi(data, fasi, stazione, s.t_start))
        elif s.kind == "empty":
            if abs(s.x_end - s.x_start) < 1e-9:
                continue
            comando, nome, vasca = nome_posizione(data, s.x_end)
            passi.append(
                Passo(comando, nome, VELOCITA_VUOTO, t=s.t_start,
                      durata=durata, vasca=vasca)
            )
        elif s.kind == "lift_empty":
            passi.append(
                Passo(LIFTING, "Pos.Top" if s.sale else "Pos.Btm", VELOCITA_VUOTO,
                      t=s.t_start, durata=durata)
            )
        elif s.kind == "wait":
            if durata <= 0:
                continue
            ultimo = passi[-1] if passi else None
            if (
                ultimo is not None
                and ultimo.comando == PAUSE
                and abs(ultimo.t + ultimo.durata - s.t_start) < 1e-6
            ):
                # due attese di fila sono un'attesa sola
                ultimo.durata += durata
                ultimo.param1 = ultimo.durata
            else:
                passi.append(Passo(PAUSE, durata, t=s.t_start, durata=durata))
    return passi


# --------------------------------------------------------------------------
# Fermate, partenze, sincronizzazioni
# --------------------------------------------------------------------------


@dataclass
class _Fermata:
    vasca: str
    arrivo: float  # [s] fine del Transfer che ce lo porta
    arrivato_con: Optional[Passo]  # quel Transfer (None: e' dove il giro comincia)
    partenza_con: Optional[Passo] = None  # il primo Transfer che lo porta via


def _fermate(passi: list[Passo], vasca_iniziale: Optional[str], T: float) -> list[_Fermata]:
    """Le vasche su cui il carro si ferma, in ordine, con arrivo e partenza.

    E' la definizione dell'interblocco (`model.vasche_in_interblocco`): il
    carro lascia una vasca col primo Transfer che non resta li' -- anche verso
    uno svincolo -- e arriva su un'altra solo quando un Transfer finisce SU
    una vasca. Gli svincoli e i punti di passaggio sono strada. Le traslazioni
    di cambio quota vanno e vengono dalla stessa vasca, e non la lasciano."""
    fermate: list[_Fermata] = []
    corrente = (
        _Fermata(vasca_iniziale, passi[0].t if passi else 0.0, None)
        if vasca_iniziale is not None
        else None
    )
    for p in passi:
        if p.comando not in TRASFERIMENTI:
            continue
        if corrente is not None and p.vasca == corrente.vasca:
            continue
        if corrente is not None and corrente.partenza_con is None:
            corrente.partenza_con = p
            fermate.append(corrente)
            corrente = None
        if p.vasca is not None:
            corrente = _Fermata(p.vasca, p.t + p.durata, p)
    if corrente is not None:
        if fermate and fermate[0].vasca == corrente.vasca and fermate[0].arrivato_con is None:
            # il giro si richiude sulla vasca da cui e' cominciato: e' una
            # fermata sola, a cavallo dell'inizio del periodo
            fermate[0].arrivo = corrente.arrivo - T
            fermate[0].arrivato_con = corrente.arrivato_con
        else:
            fermate.append(corrente)
    return fermate


def _inserisci_prima(passi: list[Passo], riferimento: Passo, nuovi: list[Passo]):
    i = next(j for j, p in enumerate(passi) if p is riferimento)
    for p in nuovi:
        p.t = riferimento.t
    passi[i:i] = nuovi


def _ruota(passi: list[Passo], t_avvio: float, T: float, eps: float) -> list[Passo]:
    """Il programma fatto cominciare dall'istante di avvio: il passo 1 e'
    quello che il carro deve fare per primo quando la linea parte da li'.

    Se l'avvio cade dentro un'attesa, l'attesa si spezza: il resto apre il
    programma, la parte gia' trascorsa lo chiude."""
    if not passi:
        return passi
    t0 = passi[0].t
    ta = t0 + (t_avvio - t0) % T
    for i, p in enumerate(passi):
        if p.comando == PAUSE and p.t + eps < ta < p.t + p.durata - eps:
            resto = Passo(PAUSE, p.t + p.durata - ta, t=ta, durata=p.t + p.durata - ta)
            p.durata = ta - p.t
            p.param1 = p.durata
            return [resto, *passi[i + 1 :], *passi[:i], p]
    for i, p in enumerate(passi):
        if p.t >= ta - eps:
            return passi[i:] + passi[:i]
    return passi


def _inizio_del_programma(
    data: ProblemData, segs: list[Segment], t_avvio: float, T: float
) -> float:
    """Da che istante comincia il programma di un carro: quello di avvio, se
    il carro in quell'istante e' a riposo -- fermo, col gancio in basso --
    altrimenti il primo istante dopo in cui lo e'.

    Le finestre di riposo sono quelle del punto di avvio
    (`avvio.finestre_di_riposo`), quindi "a riposo" vuol dire la stessa cosa
    qui e nel Riepilogo.

    Quelle finestre escludono il carico e lo scarico, dove un carro non si
    lascia. Un carro che si ferma SOLO li' -- il primo, che aspetta il pezzo
    al carico -- non ne ha nessuna: allora valgono le sue attese, che sono
    comunque ferme col gancio in basso. Un carro che non si ferma mai comincia
    all'istante di avvio, perche' un istante migliore non c'e'."""
    finestre = [(f.t_inizio, f.t_fine) for f in finestre_di_riposo(data, segs)]
    if not finestre:
        finestre = [(s.t_start, s.t_end) for s in segs if s.kind == "wait"]
    if not finestre:
        return t_avvio
    eps = data.eps_seconds
    for inizio, fine in finestre:
        if (t_avvio - inizio) % T <= fine - inizio + eps:
            return t_avvio
    return min(finestre, key=lambda f: (f[0] - t_avvio) % T)[0]


def _arrotonda_pause(passi: list[Passo]) -> list[Passo]:
    """Le pause in secondi interi, come le vuole il PLC.

    L'arrotondamento si porta dietro il resto da una pausa all'altra: cosi'
    la somma delle pause del giro resta quella del ciclogramma, invece di
    accumulare mezzo secondo per pausa. Una pausa che arrotonda a zero
    sparisce."""
    fuori = []
    riporto = 0.0
    for p in passi:
        if p.comando == PAUSE:
            esatto = p.durata + riporto
            p.param1 = int(round(esatto))
            riporto = esatto - p.param1
            if p.param1 <= 0:
                continue
        fuori.append(p)
    return fuori


def programma_carri(
    data: ProblemData, solution: Solution, avvio: Optional[Avvio] = None
) -> ProgrammaCarri:
    """Il programma di ogni carro, uno per zona, gia' fatto cominciare
    dall'istante di `avvio` e chiuso da End Program.

    `avvio` assente = l'origine del ciclogramma. Con l'avvio, il passo 1 di
    ogni carro e' quello dell'istante di avvio se in quell'istante il carro e'
    a riposo, altrimenti quello del primo istante dopo in cui lo e'
    (`_inizio_del_programma`). I numeri di passo dei Crane Syncro si contano
    su questi programmi gia' fatti cominciare."""
    T = solution.T
    eps = data.eps_seconds
    note: list[str] = []
    carico = data.route[0].tank_id
    scarico = data.route[-1].tank_id

    basi: list[list[Passo]] = []
    fermate: list[list[_Fermata]] = []
    for segs in solution.segments_per_hoist:
        passi = _passi_base(data, segs)
        basi.append(passi)
        iniziale = nome_posizione(data, segs[0].x_start)[2] if segs else None
        fermate.append(_fermate(passi, iniziale, T))

    # -- chi deve aspettare chi --------------------------------------------
    # Le coppie di vasche in conflitto sono quelle dell'interblocco, e le
    # decide `coppie_interblocco`: e' lo stesso vincolo che il ciclogramma
    # rispetta, quindi ogni Crane Syncro e' gia' soddisfatto dai tempi -- e'
    # una garanzia in piu', non un'attesa in piu'.
    coppie = coppie_interblocco(data, data.zones)

    def in_conflitto(h: int, a: str, k: int, b: str) -> bool:
        if h < k:
            return (a, b) in coppie.get((h, k), ())
        return (b, a) in coppie.get((k, h), ())

    if not data.interblocco and len(basi) > 1:
        note.append(
            "Interblocco delle vasche spento: nessun Crane Syncro. Il "
            "ciclogramma tiene i carri lontani solo con la distanza di "
            "sicurezza, che il PLC non sa sincronizzare a passi."
        )

    inserimenti: list[tuple[int, Passo, list[Passo]]] = []
    for h, ferm in enumerate(fermate):
        if len(ferm) < 2:
            continue
        for i, f in enumerate(ferm):
            verso = ferm[(i + 1) % len(ferm)].vasca
            partenza = f.partenza_con
            if partenza is None:
                continue
            nuovi = []
            if verso in (carico, scarico):
                nuovi.append(Passo(EXTERNAL_REQUEST))
            for k, ferm_k in enumerate(fermate):
                if k == h or not any(in_conflitto(h, verso, k, g.vasca) for g in ferm_k):
                    continue
                # quando il carro k e' uscito dai piedi: arriva su una vasca
                # libera venendo da una in conflitto. Si prende l'ultima volta
                # prima che questo carro parta.
                uscite = [
                    b
                    for a, b in zip(ferm_k, ferm_k[1:] + ferm_k[:1])
                    if in_conflitto(h, verso, k, a.vasca)
                    and not in_conflitto(h, verso, k, b.vasca)
                    and b.arrivato_con is not None
                ]
                if not uscite:
                    note.append(
                        f"Carro {h + 1}, verso {verso}: il carro {k + 1} non "
                        f"lascia mai le vasche in conflitto, e non c'e' un "
                        f"passo a cui sincronizzarsi."
                    )
                    continue
                ultima = min(uscite, key=lambda b: (partenza.t - b.arrivo + eps) % T)
                nuovi.append(Passo(CRANE_SYNCRO, k + 1, aspetta=(k, ultima.arrivato_con)))
                # Se fra quell'uscita e la partenza il carro k e' gia' tornato
                # verso una vasca in conflitto, il ciclogramma non rispetta
                # l'interblocco: il PLC qui fara' aspettare, e i tempi reali
                # non saranno quelli del ciclogramma.
                finestra = (partenza.t - ultima.arrivo + eps) % T
                rientri = [
                    a.partenza_con.t
                    for a, b in zip(ferm_k, ferm_k[1:] + ferm_k[:1])
                    if a.partenza_con is not None
                    and not in_conflitto(h, verso, k, a.vasca)
                    and in_conflitto(h, verso, k, b.vasca)
                ]
                if any(
                    eps < (r - ultima.arrivo) % T < finestra - eps for r in rientri
                ):
                    note.append(
                        f"Carro {h + 1}, verso {verso}: quando parte, il carro "
                        f"{k + 1} e' ancora sulle vasche in conflitto. Il "
                        f"ciclogramma non rispetta l'interblocco (vedi il foglio "
                        f"Verifica), e il Crane Syncro fara' aspettare il carro "
                        f"{h + 1} piu' di quanto il ciclogramma preveda."
                    )
            if nuovi:
                inserimenti.append((h, partenza, nuovi))
    for h, partenza, nuovi in inserimenti:
        _inserisci_prima(basi[h], partenza, nuovi)

    # -- da dove si parte, e i numeri dei passi -----------------------------
    programmi = []
    for passi, segs in zip(basi, solution.segments_per_hoist):
        if avvio is not None and segs:
            inizio = _inizio_del_programma(data, segs, avvio.t, T)
            passi = _ruota(passi, inizio, T, eps)
        passi = _arrotonda_pause(passi)
        passi.append(Passo(END_PROGRAM))
        programmi.append(passi)

    for passi in programmi:
        for p in passi:
            if p.aspetta is None:
                continue
            k, arrivo = p.aspetta
            altro = programmi[k]
            j = next(i for i, q in enumerate(altro) if q is arrivo)
            # il passo DOPO l'arrivo: da li' il carro k e' fuori dai piedi.
            # Se l'arrivo e' l'ultimo passo prima di End Program, e' il passo 1.
            p.param2 = j + 2 if altro[j + 1].comando != END_PROGRAM else 1
    return ProgrammaCarri(programmi, note)
