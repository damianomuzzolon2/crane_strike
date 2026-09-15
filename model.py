"""
model.py
--------
Modello di ottimizzazione (CP-SAT / OR-Tools) per il problema del
"Cyclic Hoist Scheduling" (CHSP): trovare il ciclogramma periodico di uno o
piu' carroponti che spostano pezzi attraverso una sequenza di vasche,
rispettando tempi di permanenza min/max in ciascuna vasca, un takt time
target (con tolleranza) e vincoli di non-collisione fra carroponti che
condividono la stessa rotaia.

APPROCCIO SCELTO E SUE ASSUNZIONI (importante leggere prima di usare il codice)
--------------------------------------------------------------------------
1. Una sola "ricetta" (sequenza di vasche) condivisa da tutti i pezzi. Se in
   realta' esistono piu' ricette diverse, il problema si generalizza (vedi
   nota "Estensioni possibili" in fondo al file) ma qui NON e' implementato.

2. Ogni carroponte serve una ZONA CONTIGUA di stazioni (zone-based CHSP):
   e' l'approccio piu' diffuso nella pratica industriale (ogni carroponte ha
   una porzione di linea di sua competenza). Le zone sono un INPUT (non
   decise dal solver in questa versione) -- vedi "Estensioni possibili".

3. **Ordine di visita flessibile entro la zona** (v2): a differenza di una
   prima versione che imponeva un unico giro sequenziale (stazione lo, poi
   lo+1, ..., poi hi, poi un solo rientro a vuoto), qui ogni carroponte puo'
   visitare le mosse della propria zona in QUALSIASI ordine ad ogni ciclo,
   "destreggiandosi" fra piu' pezzi diversi (ad es. mentre un pezzo e'
   ancora a bagno in una vasca con tempo di processo lungo, il carroponte
   puo' andare a servire un'altra mossa della zona invece di restare fermo
   ad aspettare). Questo e' modellato con un vincolo di CIRCUITO ciclico
   (`CpModel.AddCircuit`) sulle mosse della zona: il carroponte compie,
   ogni periodo T, un giro che tocca tutte le sue mosse esattamente una
   volta, nell'ordine che il solver ritiene piu' conveniente, con tempi di
   trasferimento a vuoto fra una mossa e la successiva (qualunque essa sia).
   Questo permette di trovare soluzioni fattibili anche quando il contenuto
   "a calendario" della zona (tempi di attesa nelle vasche inclusi) supera
   abbondantemente il takt time -- cosa che il vecchio schema sequenziale
   non riusciva a rappresentare.

3-bis. **Anche il punto in cui il giro si richiude e' libero.** Il giro e' un
   ciclo: uno dei suoi archi attraversa la fine del periodo, e a quello -- e
   solo a quello -- si somma un T. Per un tratto il modello dava per scontato
   che fosse l'arco entrante nella mossa di confine basso, e ne seguiva
   (perche' su tutti gli altri archi le fasi dovevano crescere) che QUELLA
   mossa fosse per forza la piu' anticipata del carroponte. Era una
   restrizione non dichiarata e non voluta: i ciclogrammi in cui un
   carroponte comincia il giro da un'altra mossa non stavano nello spazio di
   ricerca, e il solutore li dichiarava INFEASIBLE senza averli considerati.
   Adesso quale arco richiuda il periodo lo sceglie il solutore
   (`inizio[k]`), e il modello e' completo rispetto a questa dimensione.

4. Non collisione: attorno a ogni stazione di confine fra due zone adiacenti
   il modello impone che i due carroponti restino sempre ad almeno
   hoist_length + safety_distance l'uno dall'altro, tenendo conto della
   posizione REALE nel tempo -- soste comprese, non solo sulla stazione di
   confine ma su qualunque stazione cada abbastanza vicino. Funziona quindi
   anche con vasche molto ravvicinate. Il vincolo e' costruito su una
   griglia di verifiche piazzate ogni clearance_step_mm lungo la rotaia:
   la distanza garantita e' sempre quella richiesta D, mentre il modello puo'
   arrivare a pretendere D + clearance_step_mm -- infittire le verifiche
   avvicina le due cose. L'unica geometria non rappresentabile e' quella patologica (vasche
   non ordinate lungo la rotaia, zone che si scavalcano): la rileva
   zone_layout_conflicts() e la rifiuta solve().

4-bis. Ogni vasca FISICA ha un numero dichiarato di POSTI (`Tank.capacity`,
   default 1). Poiche' i pezzi entrano ogni T secondi e ciascuno occupa un
   posto per (immersione + bagno + emersione), per una vasca usata una sola
   volta nella ricetta basta imporre occupazione <= capacity * T, che equivale
   a "i pezzi contemporaneamente presenti non superano i posti". Se la stessa
   vasca compare piu' volte, i pezzi delle diverse tappe si contendono gli
   stessi posti e serve un vincolo CUMULATIVO (esatto: tiene conto del fatto
   che le tappe possono essere sfasate fra loro). Vale solo per le stazioni
   intermedie: carico e scarico sono fuori dalla catena delle permanenze.

5. Anche la movimentazione VERTICALE del pezzo segue il profilo cinematico di
   kinematics.py: presa e rilascio si CALCOLANO dalla corsa (`lift_height`,
   con eventuale valore per vasca) e dalle cinematiche di sollevamento a
   gancio scarico e col telaio, piu' i tempi morti di aggancio e sgancio.
   Lo spostamento a vuoto non paga nulla: sarebbe doppio conteggio.
   I tempi di permanenza restano il tempo EFFETTIVO in bagno.

6. Il modello e' CORRETTO (sound) entro le assunzioni sopra: ogni soluzione
   trovata e' un ciclogramma fisicamente valido. Rispetto alla versione con
   ordine fisso, questa e' anche molto piu' COMPLETA (rappresenta la
   quasi totalita' degli schemi di funzionamento realistici per un
   carroponte in una zona), ma resta comunque una scelta di modellazione:
   il vincolo davvero limitante ora e' che il contenuto "vivo" della zona
   (somma dei tempi di trasporto carico + trasferimenti a vuoto necessari,
   ESCLUSI i tempi di attesa nelle vasche) deve stare entro il takt time --
   se anche questo viene superato, nessun ordine di visita puo' salvare la
   situazione e serve ribilanciare le zone o aumentare il numero di
   carroponti.
"""

from __future__ import annotations

import dataclasses
import itertools
import math
from dataclasses import dataclass, field
from typing import Optional

from kinematics import Kinematics, travel_time as _travel_time_seconds

# --------------------------------------------------------------------------
# Strutture dati di input
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Tank:
    id: str
    position: float  # [mm] posizione lungo la rotaia
    # Posti simultanei nella vasca. E' una proprieta' della VASCA FISICA, non
    # della singola tappa del percorso: se la ricetta passa due volte dalla
    # stessa vasca, i pezzi delle due tappe si contendono gli stessi posti.
    capacity: int = 1
    # Corsa verticale [mm] fra la quota di trasporto e quella di immersione, e
    # sgocciolamento [s], cioe' quanto il telaio resta sospeso SOPRA questa
    # vasca a lasciar scolare il bagno prima di traslare.
    #
    # Sono proprieta' della VASCA -- la sua profondita', la sua chimica -- non
    # del carroponte, quindi si dichiarano una per vasca e sono OBBLIGATORIE.
    # Un valore "generale" con le vasche come eccezione sarebbe un default
    # silenzioso: chi dimentica una riga non se ne accorgerebbe, e il calcolo
    # userebbe un numero che nessuno ha scelto per quella vasca. Meglio
    # scrivere 0 dove non serve niente, che e' una dichiarazione.
    #
    # Sono keyword-only apposta: cosi' una chiamata posizionale scritta per la
    # versione precedente non puo' finire per assegnarli di nascosto.
    lift_height: float = field(kw_only=True)
    drain_time: float = field(kw_only=True)
    # Posizioni di SVINCOLO [mm]: i due punti, uno per lato, in cui il gancio
    # SCARICO puo' salire e scendere. Le corse verticali a vuoto avvengono
    # SEMPRE E SOLO li', mai sopra il centro di una vasca: il carroponte che ha
    # appena deposto un telaio non tira su il gancio dov'e', si porta prima su
    # uno svincolo. (Il sollevamento COL PEZZO invece e' sempre al centro: e'
    # li' che sta il telaio.)
    #
    # Sono quote assolute sulla rotaia, non scostamenti, come tutte le altre
    # posizioni del progetto. Ciascuna deve cadere fra questa vasca e quella
    # accanto -- la positiva dopo, la negativa prima -- e il programma lo
    # controlla: cosi' il tratto che il gancio percorre basso non scavalca mai
    # un'altra vasca, e non serve nessun controllo di percorso.
    #
    # Nessuna delle due dichiarata vuol dire che li' il gancio sale e scende
    # dov'e', e ci trasla sotto liberamente: quella vasca non e' un ostacolo.
    svincolo_pos: Optional[float] = field(default=None, kw_only=True)
    svincolo_neg: Optional[float] = field(default=None, kw_only=True)
    # Se il gancio SCARICO puo' passare basso sopra questa vasca. E' come sono
    # fatte quasi tutte -- da qui il valore predefinito -- e una vasca a `False`
    # e' un OSTACOLO: sopra di lei il gancio calato non passa, e nemmeno cambia
    # quota. Per uscire dalla sua campata bisogna portarsi su uno svincolo e
    # salire; per arrivarci, scendere sullo svincolo e traslare bassi al centro.
    #
    # Era un parametro unico per tutta la linea, e obbligava OGNI rientro a
    # pagare salita e discesa anche dove non serviva. Per vasca, un rientro che
    # non scavalca nessun ostacolo resta basso e non paga niente.
    gancio_basso: bool = field(default=True, kw_only=True)


@dataclass(frozen=True)
class StationSpec:
    """Una tappa del percorso del pezzo (indice 0 = punto di carico,
    ultimo indice = punto di scarico)."""

    tank_id: str
    dwell_min: float  # [s] tempo minimo di permanenza (tolleranza -)
    dwell_max: float  # [s] tempo massimo di permanenza (tolleranza +)


@dataclass(frozen=True)
class HoistZone:
    """Zona di competenza di un carroponte, espressa come intervallo di
    indici di MOSSA (non di stazione). Mossa k = trasporto dalla stazione k
    alla stazione k+1. Le zone devono essere contigue e coprire tutte le
    mosse 0..n_moves-1 esattamente una volta, in ordine crescente."""

    lo: int  # indice della prima mossa gestita
    hi: int  # indice dell'ultima mossa gestita


@dataclass(frozen=True)
class ZonaCambioQuota:
    """Il punto della rotaia in cui il carroponte cambia quota, per gli
    impianti in cui non puo' salire e scendere sopra il carico e lo scarico.

    Ce ne possono essere due, una per estremo della linea: fra il CARICO e la
    prima vasca, e fra l'ultima vasca e lo SCARICO. Servono a chi ha un
    passaggio obbligato -- una porta, un tunnel, una struttura -- che il
    carroponte deve attraversare a una quota e non a un'altra.

    LA SCALA VERTICALE E' DICHIARATA DAL BASSO, e non e' quella che il resto
    del modello usa dentro (dove la quota di trasporto vale 0 e si scende in
    negativo). Qui `0` e' la quota piu' bassa del carroponte -- la stessa a cui
    gia' trasla quando viaggia col gancio calato -- e `corsa_totale` e' la
    cima. La conversione e' `z_codice = quota_dichiarata - corsa_totale`, e la
    fa `quota_interna()`: chi compila l'impianto misura da terra, non dalla
    trave.

        corsa_totale --- cima ------------- quota di trasporto  (z = 0)
                     --- intermediate2 ---- il telaio sale fin qui al CARICO
                     --- intermediate1 ---- il gancio scende fin qui per andarci
                   0 --- ----------------- quota piu' bassa  (z = -corsa_totale)
    """

    position: float  # [mm] posizione ORIZZONTALE del punto sulla rotaia
    intermediate1: float  # [mm] quota intermedia bassa, misurata da terra
    intermediate2: float  # [mm] quota intermedia alta, misurata da terra
    corsa_totale: float  # [mm] distanza da 0 alla cima

    def quota_interna(self, quota_dichiarata: float) -> float:
        """Dalla scala dichiarata (0 = piu' bassa) a quella del modello
        (0 = quota di trasporto, negativo verso il basso)."""
        return quota_dichiarata - self.corsa_totale

    @property
    def z_basso(self) -> float:
        return -self.corsa_totale

    @property
    def z_int1(self) -> float:
        return self.quota_interna(self.intermediate1)

    @property
    def z_int2(self) -> float:
        return self.quota_interna(self.intermediate2)

    @property
    def corsa_telaio(self) -> float:
        """Di quanto sale il telaio alla stazione servita da questa zona: dalla
        quota a cui riposa (intermediate1) a quella a cui viene portato via
        (intermediate2)."""
        return self.intermediate2 - self.intermediate1


@dataclass(frozen=True)
class LiftPhase:
    """Un tratto della movimentazione VERTICALE sopra una vasca.

    Le quote sono riferite alla quota di TRASPORTO, che vale 0: il fondo corsa
    (telaio immerso) sta quindi a -lift_height. Un riferimento assoluto sul
    pavimento non servirebbe a niente -- delle vasche si conosce la corsa, non
    la profondita' -- e obbligherebbe a inventare un dato che nessuno ha
    dichiarato."""

    name: str  # etichetta leggibile: si legge nella simulazione
    duration: float  # [s]
    z_start: float  # [mm] quota iniziale del gancio (0 = quota di trasporto)
    z_end: float  # [mm] quota finale
    kin: Optional[Kinematics]  # profilo del moto, None se la quota non cambia
    loaded: bool  # se il telaio e' appeso al gancio durante questa fase
    # Dove sta il carroponte, ORIZZONTALMENTE, durante la fase. Quasi sempre e'
    # fermo sopra la stazione e i due valori restano None: la posizione la
    # conosce gia' chi chiama. Le riempie soltanto una zona di CAMBIO QUOTA,
    # dove la presa e il rilascio comprendono due traslazioni fra il punto di
    # cambio quota e la stazione -- e li' il carroponte, durante la presa, NON
    # e' fermo. Chi campiona le posizioni deve saperlo (vedi `near_boundary`).
    x_start: Optional[float] = field(default=None, kw_only=True)
    x_end: Optional[float] = field(default=None, kw_only=True)
    kin_x: Optional[Kinematics] = field(default=None, kw_only=True)

    @property
    def trasla(self) -> bool:
        """Se la fase comporta uno spostamento orizzontale vero."""
        return (
            self.x_start is not None
            and self.x_end is not None
            and abs(self.x_end - self.x_start) > 1e-9
        )


@dataclass
class ProblemData:
    tanks: dict[str, Tank]
    route: list[StationSpec]
    takt_min: float  # [s] limite inferiore tolleranza takt time
    takt_max: float  # [s] limite superiore tolleranza takt time
    kin_empty: Kinematics  # cinematica carroponte SENZA pezzo
    kin_loaded: Kinematics  # cinematica carroponte CON pezzo
    # Ingombro del carroponte lungo la rotaia, misurato dal PUNTO DI
    # RIFERIMENTO (il gancio, che deve stare sopra la vasca). Il carrello non
    # e' detto sia simmetrico rispetto al gancio, quindi i due lati si
    # dichiarano separatamente: `pos` verso le posizioni crescenti, `neg`
    # verso quelle decrescenti.
    hoist_extent_pos: float  # [mm]
    hoist_extent_neg: float  # [mm]
    safety_distance: float  # [mm] distanza di sicurezza minima fra due carroponti
    zones: Optional[list[HoistZone]] = None  # una per carroponte; None = da
    # scegliere automaticamente con
    # solve_auto_zones(...)
    time_scale: int = 100  # tick al secondo (risoluzione temporale interna)
    # -- movimentazione VERTICALE del pezzo (immersione/emersione) ----------
    #
    # Una mossa e': il carroponte arriva a vuoto sopra la vasca k, CALA il
    # gancio scarico, aggancia, SOLLEVA il telaio fuori dal bagno e lo lascia
    # SGOCCIOLARE sopra la vasca -> tempo di PRESA; poi trasla orizzontalmente
    # col pezzo; infine CALA il telaio nella vasca k+1, sgancia e RISALE col
    # gancio scarico -> tempo di RILASCIO. Lo spostamento a vuoto successivo
    # non paga nulla: la corsa del gancio scarico e' gia' contata qui dentro.
    #
    # I tempi non si dichiarano: si ricavano dalla corsa verticale della VASCA
    # (Tank.lift_height) e dalle cinematiche di sollevamento, con lo stesso
    # profilo trapezoidale usato per il moto orizzontale.
    #
    # Qui stanno solo le grandezze del CARROPONTE, uguali su tutta la linea.
    # Corsa e sgocciolamento no: cambiano da vasca a vasca e si dichiarano li'.
    kin_lift_empty: Optional[Kinematics] = None  # sollevamento a gancio scarico
    kin_lift_loaded: Optional[Kinematics] = None  # sollevamento col telaio
    # NOTA: la traslazione a gancio basso NON e' piu' un parametro della linea.
    # E' una proprieta' di ogni VASCA (`Tank.gancio_basso`), perche' un
    # impianto ha di solito qualche vasca che il gancio calato non puo'
    # scavalcare e tutte le altre libere. Un flag unico costringeva ogni
    # rientro a pagare salita e discesa anche dove non serviva.
    engage_time: float = 0.0  # [s] aggancio del telaio, prima del sollevamento
    disengage_time: float = 0.0  # [s] sgancio, dopo l'immersione
    # Ogni quanti millimetri viene verificata la distanza fra due carroponti
    # attorno al confine fra le loro zone. La condizione a(t) + c(t) >= D non
    # e' esprimibile in CP-SAT, e viene coperta con una serie di verifiche
    # piazzate a distanza crescente dal confine: la prima a clearance_step_mm,
    # la seconda al doppio, e cosi' via (vedi solve()).
    #
    # Lo stesso numero si legge in due modi, ed e' la stessa quantita':
    #   - quanto sono fitte le verifiche;
    #   - di quanto il modello puo' essere piu' severo del necessario, perche'
    #     fra una verifica e l'altra non sa distinguere e sta dal lato sicuro.
    #     Il modello puo' arrivare a pretendere D + clearance_step_mm.
    #
    # NON e' un margine di sicurezza: per quello c'e' safety_distance, che
    # entra in D ed e' un requisito dichiarato. Qui la distanza GARANTITA resta
    # D qualunque valore si metta -- infittire puo' solo far accettare
    # soluzioni buone che prima venivano scartate, mai accettarne di
    # pericolose. Costa un modello piu' grande: le verifiche sono D/passo.
    clearance_step_mm: float = 200.0
    # Le due ZONE DI CAMBIO QUOTA, se l'impianto le ha (vedi ZonaCambioQuota).
    # Una serve il CARICO -- la prima tappa del percorso -- e sta fra il carico
    # e la prima vasca; l'altra serve lo SCARICO e sta fra l'ultima vasca e lo
    # scarico. Sono in fondo alla dataclass apposta: aggiungerle in mezzo
    # romperebbe le costruzioni posizionali gia' scritte.
    cambio_quota_carico: Optional[ZonaCambioQuota] = None
    cambio_quota_scarico: Optional[ZonaCambioQuota] = None

    def __post_init__(self):
        n_moves = len(self.route) - 1
        if n_moves < 1:
            raise ValueError("route deve contenere almeno 2 stazioni (1 mossa)")
        if self.zones is not None:
            covered = []
            for z in self.zones:
                covered.extend(range(z.lo, z.hi + 1))
            if covered != list(range(n_moves)):
                raise ValueError(
                    f"le zone devono coprire in modo contiguo ed esclusivo le mosse "
                    f"0..{n_moves - 1}; trovato: {covered}"
                )
        for s in self.route:
            if s.tank_id not in self.tanks:
                raise ValueError(f"vasca '{s.tank_id}' non definita in tanks")
            if s.dwell_min > s.dwell_max:
                raise ValueError(f"dwell_min > dwell_max per vasca '{s.tank_id}'")
        if self.takt_min > self.takt_max:
            raise ValueError("takt_min > takt_max")
        if self.engage_time < 0 or self.disengage_time < 0:
            raise ValueError("engage_time e disengage_time devono essere >= 0")
        for t in self.tanks.values():
            if t.lift_height < 0:
                raise ValueError(
                    f"lift_height della vasca '{t.id}' deve essere >= 0"
                )
            if t.drain_time < 0:
                raise ValueError(
                    f"drain_time della vasca '{t.id}' deve essere >= 0"
                )
        serve_cinematica = any(t.lift_height > 0 for t in self.tanks.values())
        if serve_cinematica and self.kin_lift_loaded is None:
            raise ValueError(
                "almeno una vasca ha una corsa verticale (lift_height) ma manca "
                "kin_lift_loaded: senza non si sa quanto ci mette il telaio a "
                "uscire dal bagno e a rientrarci."
            )
        # Gli svincoli devono stare fra la loro vasca e quella accanto: e' quel
        # che garantisce che il gancio, traslando basso per raggiungerli, non
        # scavalchi mai un'altra vasca. Controllarlo qui evita di dover
        # verificare il percorso a ogni spostamento.
        quote = sorted(t.position for t in self.tanks.values())
        for t in self.tanks.values():
            i = quote.index(t.position)
            dopo = quote[i + 1] if i + 1 < len(quote) else None
            prima = quote[i - 1] if i > 0 else None
            if t.svincolo_pos is not None and not (
                t.position < t.svincolo_pos
                and (dopo is None or t.svincolo_pos < dopo)
            ):
                raise ValueError(
                    f"lo svincolo positivo della vasca '{t.id}' e' a "
                    f"{t.svincolo_pos:.0f} mm: deve stare fra la vasca "
                    f"({t.position:.0f} mm) e la posizione successiva"
                    + (f" ({dopo:.0f} mm)" if dopo is not None else "")
                    + ", altrimenti il gancio basso dovrebbe scavalcare "
                    "un'altra vasca per arrivarci."
                )
            if t.svincolo_neg is not None and not (
                t.svincolo_neg < t.position
                and (prima is None or prima < t.svincolo_neg)
            ):
                raise ValueError(
                    f"lo svincolo negativo della vasca '{t.id}' e' a "
                    f"{t.svincolo_neg:.0f} mm: deve stare fra la posizione "
                    f"precedente"
                    + (f" ({prima:.0f} mm)" if prima is not None else "")
                    + f" e la vasca ({t.position:.0f} mm), altrimenti il "
                    "gancio basso dovrebbe scavalcare un'altra vasca per "
                    "arrivarci."
                )
        # -- zone di cambio quota -------------------------------------------
        #
        # La posizione deve stare FRA la stazione servita e quella accanto, ed
        # e' un vincolo che porta due garanzie, non una:
        #   - il carroponte, per andarci, non scavalca nessun'altra stazione
        #     (lo stesso motivo per cui esiste il controllo sugli svincoli);
        #   - il vai-e-torna dentro la presa si allontana dal resto della
        #     linea, quindi non avvicina il carroponte a nessun confine di zona
        #     piu' di quanto gia' non lo sia il punto di cambio quota.
        # La seconda e' quella che tiene in piedi il vincolo di non collisione:
        # senza, un carroponte si muoverebbe in un intervallo in cui il modello
        # lo crede fermo. Vedi `near_boundary`.
        ultima = len(self.route) - 1
        for zona, stazione, vicina, verso in (
            (self.cambio_quota_carico, 0, 1, "carico"),
            (self.cambio_quota_scarico, ultima, ultima - 1, "scarico"),
        ):
            if zona is None:
                continue
            if zona.corsa_totale <= 0:
                raise ValueError(
                    f"la zona di cambio quota del {verso} ha corsa_totale="
                    f"{zona.corsa_totale:.0f} mm: e' la distanza dalla quota "
                    f"piu' bassa del carroponte fino alla cima, e deve essere "
                    f"maggiore di zero."
                )
            if not (
                0 <= zona.intermediate1 <= zona.intermediate2 <= zona.corsa_totale
            ):
                raise ValueError(
                    f"la zona di cambio quota del {verso} ha quote incoerenti: "
                    f"servono 0 <= intermediate1 <= intermediate2 <= "
                    f"corsa_totale, ma sono intermediate1="
                    f"{zona.intermediate1:.0f}, intermediate2="
                    f"{zona.intermediate2:.0f}, corsa_totale="
                    f"{zona.corsa_totale:.0f} mm. Le quote si misurano dal "
                    f"basso: 0 e' la posizione piu' bassa del carroponte."
                )
            x_st = self.station_position(stazione)
            x_vic = self.station_position(vicina)
            lo, hi = (x_st, x_vic) if x_st <= x_vic else (x_vic, x_st)
            if not (lo < zona.position < hi):
                raise ValueError(
                    f"la zona di cambio quota del {verso} e' a "
                    f"{zona.position:.0f} mm: deve stare fra "
                    f"'{self.route[stazione].tank_id}' ({x_st:.0f} mm) e "
                    f"'{self.route[vicina].tank_id}' ({x_vic:.0f} mm), "
                    f"altrimenti il carroponte dovrebbe scavalcare un'altra "
                    f"stazione per andare a cambiare quota."
                )
            corsa_dichiarata = self.tanks[self.route[stazione].tank_id].lift_height
            if corsa_dichiarata != 0:
                raise ValueError(
                    f"la stazione di {verso} "
                    f"('{self.route[stazione].tank_id}') dichiara una corsa "
                    f"verticale di {corsa_dichiarata:.0f} mm, ma li' la corsa "
                    f"la definisce la zona di cambio quota: il telaio va da "
                    f"intermediate1 a intermediate2, cioe' "
                    f"{zona.corsa_telaio:.0f} mm. Metti 0 nella corsa della "
                    f"vasca '{self.route[stazione].tank_id}'."
                )
            if self.kin_lift_loaded is None or self.kin_lift_empty is None:
                raise ValueError(
                    f"la zona di cambio quota del {verso} fa salire e scendere "
                    f"il carroponte sia col telaio sia a gancio scarico: "
                    f"servono kin_lift_loaded e kin_lift_empty per sapere "
                    f"quanto ci mette."
                )

        # -- svincoli e vasche-ostacolo ---------------------------------------
        ostacoli = [t for t in self.tanks.values() if not t.gancio_basso]
        con_svincolo = [
            t
            for t in self.tanks.values()
            if t.svincolo_pos is not None or t.svincolo_neg is not None
        ]
        # Una vasca ostacolo agli ESTREMI della linea non ha senso: li' il
        # carroponte non deve scavalcare niente, deve solo salire e scendere --
        # ed e' esattamente quello che descrive una zona di cambio quota.
        for stazione, verso in ((0, "carico"), (len(self.route) - 1, "scarico")):
            if not self.tanks[self.route[stazione].tank_id].gancio_basso:
                raise ValueError(
                    f"la stazione di {verso} "
                    f"('{self.route[stazione].tank_id}') e' dichiarata come "
                    f"ostacolo (traslazione_con_gancio_basso = 0), ma sta a un "
                    f"estremo della linea e non c'e' niente da scavalcarci. Se "
                    f"il carroponte li' non puo' cambiare quota dov'e', quello "
                    f"che serve e' una ZONA DI CAMBIO QUOTA (foglio "
                    f"CambioQuota), non un ostacolo."
                )
        # Gli svincoli si dichiarano per tutta la linea o per niente: qualunque
        # vasca puo' essere il capo di un rientro che deve passare alto, e
        # quella senza svincoli non saprebbe dove salire.
        if con_svincolo and len(con_svincolo) != len(self.tanks):
            mancanti = sorted(
                t.id for t in self.tanks.values() if t not in con_svincolo
            )
            raise ValueError(
                f"alcune vasche hanno una posizione di svincolo e altre no: "
                f"senza, {', '.join(mancanti)} non saprebbero dove far salire "
                f"il gancio scarico. Dichiara almeno uno svincolo per OGNI "
                f"vasca, oppure toglili tutti."
            )
        senza = sorted(t.id for t in ostacoli if t not in con_svincolo)
        if senza:
            raise ValueError(
                f"le vasche {', '.join(senza)} sono dichiarate come ostacolo "
                f"(traslazione_con_gancio_basso = 0) ma non hanno nessuna "
                f"posizione di svincolo: il gancio scarico non avrebbe dove "
                f"salire per scavalcarle."
            )
        if ostacoli and self.kin_lift_empty is None:
            raise ValueError(
                f"le vasche {', '.join(sorted(t.id for t in ostacoli))} non si "
                f"possono scavalcare col gancio calato, quindi il gancio "
                f"scarico deve salire e riscendere sugli svincoli: serve "
                f"kin_lift_empty per sapere quanto ci mette."
            )
        if self.clearance_step_mm <= 0:
            raise ValueError(
                "clearance_step_mm deve essere > 0: e' ogni quanti millimetri "
                "viene verificata la distanza fra i carroponti, e a zero "
                "servirebbero infinite verifiche"
            )
        if self.hoist_extent_pos < 0 or self.hoist_extent_neg < 0:
            raise ValueError(
                "hoist_extent_pos e hoist_extent_neg devono essere >= 0"
            )
        if self.safety_distance < 0:
            raise ValueError("safety_distance deve essere >= 0")
        for t in self.tanks.values():
            if t.capacity < 1:
                raise ValueError(
                    f"capacity deve essere >= 1 per la vasca '{t.id}', "
                    f"trovato {t.capacity}"
                )
        # Capienza palesemente insufficiente: il problema e' infattibile
        # qualunque siano zone, numero di carroponti e ordine di visita.
        # Meglio dirlo subito e chiaramente che restituire un INFEASIBLE muto.
        # (Condizione necessaria valutata su una tappa alla volta: se la stessa
        # vasca compare piu' volte nella ricetta il vincolo vero e' ancora piu'
        # stretto, ma lo impone il modello.)
        for s_idx in range(1, len(self.route) - 1):
            spec = self.route[s_idx]
            cap = self.tank_capacity(s_idx)
            # Bagno inevitabile: anche prelevando il pezzo appena il gancio che
            # lo ha deposto si e' tolto di mezzo, resta immerso per le due
            # corse a vuoto e i tempi morti. Se il processo non lo tollera, la
            # linea e' irrealizzabile e va detto adesso -- non con un
            # INFEASIBLE muto, che manderebbe a cercare la causa dove non c'e'.
            minimo_fisico = self.bath_extra_seconds(s_idx)
            if spec.dwell_max < minimo_fisico - 1e-9:
                raise ValueError(
                    f"vasca '{spec.tank_id}' (stazione {s_idx}): il pezzo resta "
                    f"in bagno almeno {minimo_fisico:.1f}s -- il gancio deve "
                    f"risalire dopo averlo deposto e ricalare per riprenderlo, "
                    f"e il pezzo e' immerso tutto il tempo -- ma la permanenza "
                    f"massima dichiarata e' {spec.dwell_max:.1f}s. Alza la "
                    f"permanenza massima, oppure velocizza il sollevamento a "
                    f"vuoto o riduci la corsa verticale della vasca."
                )
            occ_min = self.slot_occupancy_seconds(
                s_idx, max(spec.dwell_min, minimo_fisico)
            )
            if occ_min > cap * self.takt_max:
                raise ValueError(
                    f"vasca '{spec.tank_id}' (stazione {s_idx}): un pezzo occupa "
                    f"un posto per almeno {occ_min:.1f}s, ma con capacity="
                    f"{cap} e takt_max={self.takt_max:.1f}s il limite "
                    f"e' {cap * self.takt_max:.1f}s. Aumenta la capacity della "
                    f"vasca (multi-posto), riduci dwell_min, o alza takt_max."
                )

    # -- comodita' --------------------------------------------------------
    @property
    def hoist_length(self) -> float:
        """Ingombro totale del carroponte lungo la rotaia.

        E' l'unica combinazione dei due ingombri che conta per la distanza fra
        due carroponti: se quello di sinistra ha il gancio in p e quello di
        destra in q, il bordo destro del primo e' in p + pos e il bordo
        sinistro del secondo in q - neg, quindi lo spazio libero fra i due vale
        q - p - (pos + neg). Dove sia il gancio dentro il carrello non cambia
        nulla: conta solo la somma."""
        return self.hoist_extent_pos + self.hoist_extent_neg

    @property
    def n_stations(self) -> int:
        return len(self.route)

    @property
    def n_moves(self) -> int:
        return len(self.route) - 1

    @property
    def n_hoists(self) -> int:
        if self.zones is None:
            raise ValueError(
                "data.zones e' None (non ancora scelto): usa solve_auto_zones(...) "
                "per farlo scegliere automaticamente, oppure impostalo esplicitamente."
            )
        return len(self.zones)

    def station_position(self, idx: int) -> float:
        return self.tanks[self.route[idx].tank_id].position

    def zona_cambio_quota(self, station_idx: int) -> Optional[ZonaCambioQuota]:
        """La zona di cambio quota che serve la tappa data, se c'e'.

        Solo la PRIMA e l'ULTIMA tappa possono averne una: sono le uniche due
        che stanno agli estremi della linea, dove il carroponte esce dal
        campo delle vasche. Se la stessa vasca ricompare a meta' percorso non
        c'entra nulla -- li' e' una vasca come le altre."""
        if station_idx == 0:
            return self.cambio_quota_carico
        if station_idx == len(self.route) - 1:
            return self.cambio_quota_scarico
        return None

    def approach_position(self, station_idx: int) -> float:
        """Dove sta il carroponte, ORIZZONTALMENTE, prima di cominciare la
        presa e dopo aver finito il rilascio alla tappa data.

        Di norma e' la stazione stessa. Con una zona di cambio quota e' il
        punto di cambio quota: li' finiscono i rientri a vuoto e li' comincia
        la traslazione col pezzo, perche' l'andata alla stazione e il ritorno
        sono dentro la presa (o il rilascio).

        E' QUESTA, non `station_position`, la posizione da usare per le
        distanze fra tratte del giro."""
        zona = self.zona_cambio_quota(station_idx)
        return self.station_position(station_idx) if zona is None else zona.position

    def quota_di_riposo(self, station_idx: int) -> float:
        """Quota [mm] a cui il telaio riposa alla tappa data, sulla scala del
        modello (0 = quota di trasporto, negativo verso il basso)."""
        zona = self.zona_cambio_quota(station_idx)
        if zona is None:
            return -self.lift_height_at(station_idx)
        return zona.z_int1

    def corsa_verticale(self, station_idx: int) -> float:
        """Di quanto il gancio scende sotto la quota di trasporto alla tappa
        data: la corsa della vasca, oppure -- con una zona di cambio quota --
        l'intera corsa del carroponte, perche' li' arriva fino in fondo."""
        zona = self.zona_cambio_quota(station_idx)
        return (
            self.lift_height_at(station_idx) if zona is None else zona.corsa_totale
        )

    def tank_capacity(self, idx: int) -> int:
        """Posti della vasca usata alla tappa `idx` del percorso."""
        return self.tanks[self.route[idx].tank_id].capacity

    def steps_by_tank(self) -> dict[str, list[int]]:
        """Vasca -> tappe del percorso che la usano, escluse carico e scarico
        (fuori dalla catena delle permanenze). Se una vasca compare piu' volte
        i pezzi delle diverse tappe si contendono gli stessi posti."""
        out: dict[str, list[int]] = {}
        for idx in range(1, len(self.route) - 1):
            out.setdefault(self.route[idx].tank_id, []).append(idx)
        return out

    def move_distance(self, k: int) -> float:
        """Quanta rotaia percorre il carroponte col pezzo appeso, nella mossa k.

        Fra i due punti di APPROCCIO, non fra le due vasche: con una zona di
        cambio quota il tratto col pezzo comincia (o finisce) sul punto di
        cambio quota, perche' l'ultimo pezzo di strada fino alla stazione lo fa
        la presa (o il rilascio)."""
        return abs(self.approach_position(k + 1) - self.approach_position(k))

    def to_ticks(self, seconds: float) -> int:
        return round(seconds * self.time_scale)

    def to_seconds(self, ticks: int) -> float:
        return ticks / self.time_scale

    @property
    def eps_seconds(self) -> float:
        """Tolleranza numerica coerente con la risoluzione dei tick. Il modello
        CP-SAT arrotonda ogni durata al tick; chi ricalcola le stesse durate in
        virgola mobile deve accettare uno scarto di questo ordine."""
        return max(10.0 / self.time_scale, 1e-6)

    # -- durate delle tratte (unico punto in cui sono definite) -------------
    #
    # Tutto il resto del codice (modello CP-SAT, ricostruzione traiettoria,
    # pre-filtro delle zone, verificatore) DEVE passare da qui: cosi' una
    # modifica alla definizione di "durata di una mossa" si propaga ovunque
    # senza rischio di disallineamenti.

    def lift_height_at(self, station_idx: int) -> float:
        """Corsa verticale [mm] alla stazione data, cioe' quella della vasca."""
        return self.tanks[self.route[station_idx].tank_id].lift_height

    def _lift_seconds(self, height: float, kin: Optional[Kinematics]) -> float:
        if height <= 0 or kin is None:
            return 0.0
        return _travel_time_seconds(height, kin)

    def drain_time_at(self, station_idx: int) -> float:
        """Sgocciolamento [s] sopra la vasca della tappa data."""
        return self.tanks[self.route[station_idx].tank_id].drain_time

    def pick_phases(self, station_idx: int) -> list["LiftPhase"]:
        """La PRESA scomposta nei suoi movimenti verticali, in ordine.

        Il ciclogramma ha bisogno della sola durata totale, ma chi deve
        MOSTRARE la presa -- la simulazione -- ha bisogno di sapere dove sta il
        gancio istante per istante. Le fasi sono la definizione, e la durata e'
        la loro somma: cosi' i due usi non possono divergere.

        La discesa del gancio scarico non c'e' MAI qui dentro: o l'impianto
        lascia traslare il gancio basso, e allora il carroponte arriva con il
        gancio gia' in fondo, oppure il gancio scende su una posizione di
        svincolo -- e quella e' parte del rientro a vuoto, non della presa
        (vedi `empty_leg_seconds`)."""
        zona = self.zona_cambio_quota(station_idx)
        if zona is not None:
            return self._pick_phases_cambio_quota(station_idx, zona)
        h = self.lift_height_at(station_idx)
        return [
            LiftPhase("aggancio", self.engage_time, -h, -h, None, False),
            LiftPhase(
                "sollevamento del telaio",
                self._lift_seconds(h, self.kin_lift_loaded),
                -h,
                0.0,
                self.kin_lift_loaded,
                True,
            ),
            LiftPhase(
                "sgocciolamento", self.drain_time_at(station_idx), 0.0, 0.0, None, True
            ),
        ]

    def release_phases(self, station_idx: int) -> list["LiftPhase"]:
        """Il RILASCIO scomposto nei suoi movimenti verticali, in ordine.

        La risalita del gancio scarico non c'e' MAI qui dentro: o il gancio
        trasla basso e non risale affatto, oppure risale da una posizione di
        svincolo -- e quella e' parte del rientro a vuoto."""
        zona = self.zona_cambio_quota(station_idx)
        if zona is not None:
            return self._release_phases_cambio_quota(station_idx, zona)
        h = self.lift_height_at(station_idx)
        return [
            LiftPhase(
                "immersione del telaio",
                self._lift_seconds(h, self.kin_lift_loaded),
                0.0,
                -h,
                self.kin_lift_loaded,
                True,
            ),
            LiftPhase("sgancio", self.disengage_time, -h, -h, None, True),
        ]

    def _pick_phases_cambio_quota(
        self, station_idx: int, zona: ZonaCambioQuota
    ) -> list["LiftPhase"]:
        """La presa su una stazione servita da una zona di CAMBIO QUOTA.

        Il carroponte ci arriva fermo sul punto di cambio quota, alla sua quota
        piu' bassa, e fa il giro:

            sale a intermediate1 -> trasla alla stazione -> aggancia ->
            solleva il telaio a intermediate2 -> torna al punto di cambio
            quota -> sale in cima

        Le due traslazioni stanno QUI dentro, e non sono un dettaglio di
        disegno: sono tempo di presa a tutti gli effetti, ed e' per questo che
        durante la presa il carroponte non e' fermo. Chi campiona le posizioni
        deve leggerle dalle fasi (`LiftPhase.x_start`/`x_end`)."""
        p = zona.position
        q = self.station_position(station_idx)
        h = zona.corsa_telaio
        return [
            LiftPhase(
                "salita alla quota intermedia bassa",
                self._lift_seconds(zona.intermediate1, self.kin_lift_empty),
                zona.z_basso,
                zona.z_int1,
                self.kin_lift_empty,
                False,
                x_start=p,
                x_end=p,
            ),
            LiftPhase(
                "traslazione alla stazione",
                _travel_time_seconds(abs(q - p), self.kin_empty),
                zona.z_int1,
                zona.z_int1,
                None,
                False,
                x_start=p,
                x_end=q,
                kin_x=self.kin_empty,
            ),
            LiftPhase(
                "aggancio", self.engage_time, zona.z_int1, zona.z_int1, None, False,
                x_start=q, x_end=q,
            ),
            LiftPhase(
                "sollevamento del telaio",
                self._lift_seconds(h, self.kin_lift_loaded),
                zona.z_int1,
                zona.z_int2,
                self.kin_lift_loaded,
                True,
                x_start=q,
                x_end=q,
            ),
            LiftPhase(
                "sgocciolamento",
                self.drain_time_at(station_idx),
                zona.z_int2,
                zona.z_int2,
                None,
                True,
                x_start=q,
                x_end=q,
            ),
            LiftPhase(
                "traslazione al cambio quota",
                _travel_time_seconds(abs(p - q), self.kin_loaded),
                zona.z_int2,
                zona.z_int2,
                None,
                True,
                x_start=q,
                x_end=p,
                kin_x=self.kin_loaded,
            ),
            LiftPhase(
                "salita alla quota di trasporto",
                self._lift_seconds(
                    zona.corsa_totale - zona.intermediate2, self.kin_lift_loaded
                ),
                zona.z_int2,
                0.0,
                self.kin_lift_loaded,
                True,
                x_start=p,
                x_end=p,
            ),
        ]

    def _release_phases_cambio_quota(
        self, station_idx: int, zona: ZonaCambioQuota
    ) -> list["LiftPhase"]:
        """Il rilascio su una stazione servita da una zona di CAMBIO QUOTA:
        lo stesso giro della presa, percorso al contrario.

        Il carroponte arriva col pezzo sul punto di cambio quota, alla quota di
        trasporto, scende a intermediate2, va alla stazione, posa il telaio a
        intermediate1, torna indietro e scende fino in fondo -- pronto per il
        rientro a vuoto, che riparte da li'."""
        p = zona.position
        q = self.station_position(station_idx)
        h = zona.corsa_telaio
        return [
            LiftPhase(
                "discesa alla quota intermedia alta",
                self._lift_seconds(
                    zona.corsa_totale - zona.intermediate2, self.kin_lift_loaded
                ),
                0.0,
                zona.z_int2,
                self.kin_lift_loaded,
                True,
                x_start=p,
                x_end=p,
            ),
            LiftPhase(
                "traslazione alla stazione",
                _travel_time_seconds(abs(q - p), self.kin_loaded),
                zona.z_int2,
                zona.z_int2,
                None,
                True,
                x_start=p,
                x_end=q,
                kin_x=self.kin_loaded,
            ),
            LiftPhase(
                "immersione del telaio",
                self._lift_seconds(h, self.kin_lift_loaded),
                zona.z_int2,
                zona.z_int1,
                self.kin_lift_loaded,
                True,
                x_start=q,
                x_end=q,
            ),
            LiftPhase(
                "sgancio", self.disengage_time, zona.z_int1, zona.z_int1, None, True,
                x_start=q, x_end=q,
            ),
            LiftPhase(
                "traslazione al cambio quota",
                _travel_time_seconds(abs(p - q), self.kin_empty),
                zona.z_int1,
                zona.z_int1,
                None,
                False,
                x_start=q,
                x_end=p,
                kin_x=self.kin_empty,
            ),
            LiftPhase(
                "discesa alla quota bassa",
                self._lift_seconds(zona.intermediate1, self.kin_lift_empty),
                zona.z_int1,
                zona.z_basso,
                self.kin_lift_empty,
                False,
                x_start=p,
                x_end=p,
            ),
        ]

    def pick_time_at(self, station_idx: int) -> float:
        """Tempo di PRESA [s] alla stazione data: aggancio, sollevamento col
        telaio, sgocciolamento. Il gancio scarico ci arriva gia' in fondo."""
        return sum(f.duration for f in self.pick_phases(station_idx))

    def release_time_at(self, station_idx: int) -> float:
        """Tempo di RILASCIO [s] alla stazione data: immersione col telaio e
        sgancio. Il gancio resta in fondo: se poi debba risalire, e da dove, e'
        cosa del rientro a vuoto."""
        return sum(f.duration for f in self.release_phases(station_idx))

    def bath_extra_seconds(self, station_idx: int) -> float:
        """Quanto il pezzo resta in bagno OLTRE l'intervallo fra i movimenti
        del gancio, alla stazione data.

        Il gancio che ha appena sganciato deve risalire, e quello che verra' a
        riprendere il pezzo deve ricalare: due corse a vuoto che avvengono
        mentre il pezzo e' gia' -- o ancora -- immerso. Piu' i tempi morti di
        sgancio e aggancio, che il telaio passa anch'essi in fondo alla vasca.

        Sono secondi di bagno a tutti gli effetti, e non contarli era un
        errore vero: su una linea con corsa 1500 mm fanno oltre quindici
        secondi, abbastanza da sforare il massimo di processo senza che
        nessuno lo dicesse. Il tempo in bagno e' quindi

            bagno = (istante del prelievo - istante in cui il rilascio finisce)
                    + bath_extra_seconds

        e sono i limiti del PROCESSO -- `dwell_min` e `dwell_max` -- ad
        applicarsi al bagno, non all'intervallo fra i movimenti.

        Sono i soli tempi morti: tutto il resto di quello che il gancio fa fra
        un rilascio e la presa successiva -- traslare, salire, riscendere --
        cade nell'intervallo, e li' e' gia' contato."""
        return self.disengage_time + self.engage_time

    def empty_lift_seconds(self, station_idx: int) -> float:
        """Durata [s] di UNA corsa verticale a gancio scarico, alla stazione
        data: quella che il gancio fa per risalire dopo lo sgancio, e di nuovo
        per ricalare prima dell'aggancio.

        Non e' detto che qualcuno la faccia: dipende dal rientro, e lo decide
        `serve_alto`. Qui c'e' solo quanto costerebbe.

        Su una stazione servita da una zona di cambio quota la corsa non e'
        quella della vasca ma l'INTERA corsa del carroponte: li' il gancio
        arriva fino in fondo, ed e' da li' che deve ripartire."""
        return self._lift_seconds(
            self.corsa_verticale(station_idx), self.kin_lift_empty
        )

    def serve_alto(self, station_a: int, station_b: int) -> bool:
        """Se il rientro a vuoto da `a` a `b` deve passare ALTO.

        Succede in tre casi, e sono tre facce della stessa cosa -- il gancio
        calato non puo' stare nella campata di una vasca ostacolo se non per
        raggiungerne il centro dal proprio svincolo:

        - si PARTE da un ostacolo: il gancio e' calato al suo centro, e per
          uscire dalla sua campata deve prima salire sullo svincolo;
        - si ARRIVA a un ostacolo: ci si deve calare sullo svincolo e poi
          traslare bassi fino al centro;
        - fra i due punti di approccio ne cade uno: va scavalcato.

        Se non succede nessuno dei tre, il rientro resta basso da capo a fondo
        e non paga nessuna corsa verticale."""
        if station_a == station_b:
            return False
        for stazione in (station_a, station_b):
            if not self.tanks[self.route[stazione].tank_id].gancio_basso:
                return True
        pos_a = self.approach_position(station_a)
        pos_b = self.approach_position(station_b)
        lo, hi = (pos_a, pos_b) if pos_a <= pos_b else (pos_b, pos_a)
        # tutte le vasche dell'impianto, non solo quelle della ricetta: una
        # vasca fuori percorso sta comunque sulla rotaia e fa comunque ostacolo
        return any(
            not t.gancio_basso and lo < t.position < hi
            for t in self.tanks.values()
        )

    def slot_occupancy_seconds(self, station_idx: int, bath: float) -> float:
        """Per quanto tempo [s] un pezzo tiene occupato un POSTO nella vasca
        `station_idx`, dato il suo tempo in bagno.

        Non coincide col bagno: il telaio ingombra il posto da quando comincia
        a calare a quando ha finito di emergere e di sgocciolare. E' questa la
        grandezza da confrontare con `capacity * T`."""
        return (
            self.release_time_at(station_idx)
            + (bath - self.bath_extra_seconds(station_idx))
            + self.pick_time_at(station_idx)
        )

    def loaded_leg_seconds(self, k: int) -> float:
        """Durata TOTALE [s] della mossa k: presa dalla vasca k, traslazione
        orizzontale, rilascio nella vasca k+1."""
        return (
            self.pick_time_at(k)
            + _travel_time_seconds(self.move_distance(k), self.kin_loaded)
            + self.release_time_at(k + 1)
        )

    def horizontal_loaded_seconds(self, k: int) -> float:
        """Sola traslazione orizzontale [s] della mossa k, senza le fasi
        verticali. Serve a chi deve disegnare o campionare il moto."""
        return _travel_time_seconds(self.move_distance(k), self.kin_loaded)

    def horizontal_empty_seconds(self, pos_a: float, pos_b: float) -> float:
        """Durata [s] di una traslazione orizzontale a gancio scarico, e basta.

        E' la singola tratta, non il giro: il rientro fra due vasche puo'
        essere fatto di piu' tratte, con in mezzo la salita e la discesa sugli
        svincoli (vedi `empty_leg_seconds`)."""
        return _travel_time_seconds(abs(pos_b - pos_a), self.kin_empty)

    def svincolo_verso(self, station_idx: int, verso_pos: float) -> float:
        """Da dove il gancio scarico sale (o dove scende) lasciando la stazione
        data per andare verso `verso_pos`.

        Si sceglie lo svincolo dalla parte in cui si deve andare: cosi' il
        tratto percorso basso e' il piu' corto e non si torna indietro. Se da
        quella parte non ce n'e' si prende l'altro; se non ce n'e' nessuno, li'
        il gancio sale e scende dov'e', perche' quella vasca non e' un
        ostacolo.

        Su una stazione con una zona di cambio quota lo svincolo e' il punto di
        cambio quota stesso: e' li', e solo li', che il carroponte puo'
        cambiare quota -- che il gancio sia carico o vuoto."""
        zona = self.zona_cambio_quota(station_idx)
        if zona is not None:
            return zona.position
        t = self.tanks[self.route[station_idx].tank_id]
        avanti = verso_pos >= t.position
        primo, secondo = (
            (t.svincolo_pos, t.svincolo_neg) if avanti else (t.svincolo_neg, t.svincolo_pos)
        )
        for s in (primo, secondo):
            if s is not None:
                return s
        return t.position

    def empty_leg_seconds(self, station_a: int, station_b: int) -> float:
        """Durata [s] del rientro a vuoto dalla stazione `a` alla `b`, dal
        momento in cui il telaio e' sganciato a quando il gancio e' pronto ad
        agganciare quello dopo.

        Col gancio che trasla basso -- lo standard -- e' la sola traslazione
        orizzontale: nessun tempo verticale, perche' il gancio non sale e non
        scende mai da scarico.

        Sull'impianto in cui il gancio calato non passa fra le vasche il giro
        e' piu' lungo, e sta tutto QUI: traslata bassa fino allo svincolo,
        salita, traslata in alto, discesa sullo svincolo di arrivo, traslata
        bassa fino alla vasca. Sta qui e non dentro presa e rilascio perche' e'
        un movimento che avviene FRA due mosse, e chi lo paga e' lo
        spostamento -- non il pezzo, che nel frattempo e' in bagno."""
        return sum(
            durata for _, _, durata in tratte_rientro(self, station_a, station_b)
        )


# --------------------------------------------------------------------------
# Risultato
# --------------------------------------------------------------------------


def tratte_rientro(
    data: "ProblemData", stazione_a: int, stazione_b: int
) -> list[tuple[float, float, float]]:
    """Il rientro a vuoto come sequenza di tratte `(da, a, durata [s])`.

    E' L'UNICA DEFINIZIONE del rientro, e da qui discendono tutte e tre le
    cose che se ne devono sapere:

      - quanto dura           -> `empty_leg_seconds`, che ne somma le durate;
      - che aspetto ha        -> `_segmenti_rientro`, che ne fa dei Segment;
      - dove passa e quando   -> `near_boundary`, che ne ricava le finestre del
                                 vincolo di non collisione.

    Averne una sola non e' eleganza: e' quello che impedisce al vincolo di
    protegger un percorso diverso da quello che il carroponte fa davvero.

    Una tratta con `da == a` e' una corsa VERTICALE del gancio scarico: lungo
    la rotaia il carroponte e' FERMO. Chi ne campiona le posizioni deve
    trattarla come tale -- crederla un movimento e' l'errore che ha gia'
    prodotto due carroponti nello stesso punto con stato OPTIMAL.

    Il percorso NON e' detto sia monotono: se da una parte lo svincolo non e'
    dichiarato si esce dall'altra, e allora il carroponte torna indietro prima
    di ripartire. E' proprio per questo che le tratte vanno guardate una per
    una, invece di dedurre tutto dai due estremi."""
    pos_a = data.approach_position(stazione_a)
    pos_b = data.approach_position(stazione_b)
    if not data.serve_alto(stazione_a, stazione_b):
        # niente da scavalcare: il gancio resta calato da capo a fondo, e non
        # paga nessuna corsa verticale
        return [(pos_a, pos_b, data.horizontal_empty_seconds(pos_a, pos_b))]
    sv_a = data.svincolo_verso(stazione_a, pos_b)
    sv_b = data.svincolo_verso(stazione_b, pos_a)
    return [
        (pos_a, sv_a, data.horizontal_empty_seconds(pos_a, sv_a)),
        (sv_a, sv_a, data.empty_lift_seconds(stazione_a)),
        (sv_a, sv_b, data.horizontal_empty_seconds(sv_a, sv_b)),
        (sv_b, sv_b, data.empty_lift_seconds(stazione_b)),
        (sv_b, pos_b, data.horizontal_empty_seconds(sv_b, pos_b)),
    ]


@dataclass
class Segment:
    """Un tratto della traiettoria di un carroponte entro un ciclo."""

    # 'quota': traslazione fra il punto di cambio quota e la stazione, dentro
    # una presa o un rilascio. E' l'unico tratto in cui il carroponte si muove
    # senza che il tratto appartenga ne' al trasporto ne' al rientro a vuoto.
    kind: str  # 'pick'|'loaded'|'release'|'empty'|'wait'|'lift_empty'|'quota'
    t_start: float  # [s], relativo all'inizio del ciclo (puo' iniziare prima di 0)
    t_end: float  # [s]
    x_start: float  # [m]
    x_end: float  # [m]
    kin: Optional[Kinematics] = None  # None per 'wait'
    # A quale MOSSA appartiene il tratto, per i soli tratti che ne fanno parte:
    # presa, traslazione a carico, rilascio. E' None per attesa e rientro a
    # vuoto, che non sono di nessuna mossa -- stanno FRA due mosse, e
    # attribuirli all'una o all'altra sarebbe una convenzione arbitraria.
    #
    # Serve a chi deve risalire dalla traiettoria alla VASCA: la presa della
    # mossa k avviene sulla stazione k, il rilascio sulla k+1, e da li' si
    # ricavano corsa verticale e sgocciolamento. Dedurlo dalla posizione
    # sbaglierebbe appena due vasche stessero alla stessa quota.
    move: Optional[int] = None
    # Per i soli tratti 'lift_empty': True se il gancio SALE sullo svincolo,
    # False se scende. Lo sa solo chi costruisce il rientro -- la prima corsa
    # verticale e' la salita, la seconda la discesa -- e dedurlo dopo dai
    # tratti vicini ha casi ambigui: se una delle due corse manca perche' la
    # vasca non ne ha, quella che resta non dice da sola da che parte va.
    sale: Optional[bool] = None


@dataclass
class HoistPlan:
    """Valori risolti per un carroponte, cosi' come li ha decisi il solver.

    Serve al verificatore indipendente (verify.py): dai soli Segment non si
    potrebbero ricostruire i tempi ASSOLUTI (`actual_time`), perche' le fasi
    locali sono note solo modulo T. Senza questi valori il controllo delle
    permanenze sarebbe ambiguo per multipli interi del takt time."""

    zone: HoistZone
    order: list[int]  # indici di mossa, nell'ordine di esecuzione, da zone.lo
    local_pick: dict[int, float]  # [s] istante di prelievo, in [0,T)
    finish: dict[int, float]  # [s] istante di consegna
    dep_hi: float  # [s] partenza dal confine superiore
    arr_lo: float  # [s] arrivo al confine inferiore
    # [s] quanto il carroponte resta fermo DOVE HA CONSEGNATO la mossa k,
    # prima di cominciare il viaggio a vuoto verso la mossa dopo. E' il
    # QUARTO grado di liberta' del ciclogramma: non discende dalle fasi, e
    # se non lo si porta dietro la traiettoria non si ricostruisce uguale.
    attese: dict[int, float] = field(default_factory=dict)


@dataclass
class Solution:
    status: str  # 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | ...
    T: Optional[float]  # takt time trovato [s]
    segments_per_hoist: list[list[Segment]] = field(default_factory=list)
    raw: dict = field(default_factory=dict)  # valori grezzi utili per debug
    plans: list[HoistPlan] = field(default_factory=list)  # uno per carroponte
    actual_time: list[float] = field(default_factory=list)  # [s], una per mossa


# --------------------------------------------------------------------------
# Costruzione e risoluzione del modello CP-SAT
# --------------------------------------------------------------------------
#
# STRUTTURA DEL MODELLO (aggiornata per l'ordine di visita flessibile)
#
# 1. Catena di flusso pezzo (`actual_time`): invariata rispetto alla v1.
#    actual_time[k] = istante di prelievo della mossa k per un pezzo di
#    riferimento che attraversa l'intera linea; incatenata dai vincoli di
#    permanenza min/max in ciascuna vasca.
#
# 2. Per ciascun carroponte (zona di mosse Z_h): invece di un ordine fisso
#    lo,lo+1,...,hi + un unico rientro, si costruisce un CIRCUITO ciclico
#    (`AddCircuit`) sulle mosse di Z_h: il carroponte le visita tutte
#    esattamente una volta per periodo, nell'ordine che il solver sceglie.
#    Per confrontare istanti che nella catena `actual_time` possono essere
#    separati da piu' periodi T (tipico se una vasca ha un tempo di
#    processo lungo), ogni mossa k riceve una variabile locale
#    `local_pick[k]` = actual_time[k] mod T, ottenuta con una ricerca su un
#    numero finito di "giri" possibili (mantenendo tutto LINEARE: nessun
#    prodotto fra due variabili). La mossa lo_h e' presa come riferimento
#    di "chiusura periodo": l'arco che rientra su di essa nel circuito e'
#    l'unico a cui si somma +T.
#
# 3. Le variabili libere `dep_hi` (istante di partenza dal confine
#    superiore della zona) e `arr_lo` (istante di arrivo, pronto, al
#    confine inferiore) sono usate sia per ricostruire la traiettoria sia
#    per il vincolo di non collisione ai confini fra zone adiacenti
#    (identico nello spirito alla v1).


def zone_layout_conflicts(
    data: ProblemData, zones: list[HoistZone]
) -> list[str]:
    """Verifica che la GEOMETRIA delle zone sia compatibile con l'unico
    meccanismo di non-collisione che il modello possiede. Restituisce la lista
    (vuota se tutto a posto) dei problemi trovati, gia' in forma leggibile.

    PERCHE' SERVE
    Il vincolo di non collisione (vedi solve()) e' costruito attorno a ogni
    stazione di CONFINE, assumendo che la zona di sinistra stia interamente
    da un lato e quella di destra dall'altro. Su questa base sa gestire
    qualunque spaziatura fra le vasche, anche compatta. Quello che NON sa
    gestire e' la geometria patologica: nulla obbliga le posizioni delle
    vasche a essere monotone lungo la rotaia (move_distance usa abs()),
    quindi una zona potrebbe scavalcare il proprio confine, o due zone
    lontane nell'ordine delle mosse potrebbero sovrapporsi nello spazio.
    """
    required = data.hoist_length + data.safety_distance
    problemi: list[str] = []

    for h in range(len(zones) - 1):
        b = zones[h].hi + 1  # stazione di confine fra la zona h e la h+1
        x_b = data.station_position(b)
        # la zona di sinistra deve stare tutta da una parte del confine e
        # quella di destra tutta dall'altra, altrimenti "sinistra"/"destra"
        # non hanno piu' senso e il vincolo di fascia non e' applicabile
        xs_l = [data.station_position(s) for s in range(zones[h].lo, zones[h].hi + 2)]
        xs_r = [
            data.station_position(s) for s in range(zones[h + 1].lo, zones[h + 1].hi + 2)
        ]
        lato = 1 if max(xs_r) >= x_b else -1
        if any(lato * (x - x_b) > 1e-9 for x in xs_l) or any(
            lato * (x - x_b) < -1e-9 for x in xs_r
        ):
            problemi.append(
                f"attorno alla stazione di confine {b} "
                f"('{data.route[b].tank_id}', a {x_b:.0f} mm) le due zone non "
                f"stanno su lati opposti: la zona {h + 1} occupa "
                f"[{min(xs_l):.2f},{max(xs_l):.2f}] e la zona {h + 2} occupa "
                f"[{min(xs_r):.2f},{max(xs_r):.2f}]. Serve che le posizioni "
                f"delle vasche siano ordinate lungo la rotaia."
            )

    spans = []
    for z in zones:
        xs = [data.station_position(i) for i in range(z.lo, z.hi + 2)]
        spans.append((min(xs), max(xs)))
    for i in range(len(spans)):
        for j in range(i + 2, len(spans)):
            lo_i, hi_i = spans[i]
            lo_j, hi_j = spans[j]
            gap = max(0.0, max(lo_i, lo_j) - min(hi_i, hi_j))
            if gap < required:
                problemi.append(
                    f"le zone {i + 1} e {j + 1} non sono adiacenti ma i loro "
                    f"tratti di rotaia [{lo_i:.2f},{hi_i:.2f}] e "
                    f"[{lo_j:.0f},{hi_j:.0f}] distano solo {gap:.0f} mm "
                    f"(servono {required:.0f} mm): il modello non le vincola "
                    f"fra loro"
                )
    return problemi


def solve(
    data: ProblemData,
    time_limit_s: float = 20.0,
    log_search: bool = False,
    allow_unsafe_layout: bool = False,
) -> Solution:
    """allow_unsafe_layout: se True salta il controllo di geometria delle zone.
    Serve solo per studio/debug: le soluzioni prodotte possono contenere
    collisioni reali che il modello non e' in grado di vedere (verify.py le
    segnala)."""
    if data.zones is None:
        raise ValueError(
            "data.zones e' None: specifica le zone esplicitamente oppure usa "
            "solve_auto_zones(data, n_hoists=...) per farle scegliere automaticamente."
        )

    if not allow_unsafe_layout:
        problemi = zone_layout_conflicts(data, data.zones)
        if problemi:
            raise ValueError(
                "Questa suddivisione in zone non e' rappresentabile in modo sicuro "
                "dal modello:\n  - "
                + "\n  - ".join(problemi)
                + "\nIl vincolo di non collisione assume che le zone adiacenti "
                "stiano su lati opposti del proprio confine e che zone lontane "
                "non si sovrappongano nello spazio.\n"
                "Cosa fare: ordina le vasche lungo la rotaia in modo coerente con "
                "la sequenza del percorso, oppure sposta il confine fra le zone "
                "(solve_auto_zones scarta da solo le suddivisioni non valide)."
            )

    # Import posticipato: cosi' il resto del modulo (dataclass, cinematica,
    # extraction, plotting) resta utilizzabile/testabile anche senza ortools
    # installato.
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    scale = data.time_scale

    def T_(seconds: float) -> int:
        return data.to_ticks(seconds)

    # -- Tempi di percorrenza precalcolati (le posizioni delle vasche sono
    #    fisse, quindi i tempi di percorrenza sono costanti, non variabili) --
    travel_loaded = [T_(data.loaded_leg_seconds(k)) for k in range(data.n_moves)]

    def travel_empty_ticks(stazione_a: int, stazione_b: int) -> int:
        return T_(data.empty_leg_seconds(stazione_a, stazione_b))

    # Distanza minima che deve sempre separare due carroponti, misurata fra i
    # loro punti di riferimento: l'ingombro pieno piu' il margine di sicurezza.
    required_sep = data.hoist_length + data.safety_distance

    def escape_ticks(x: float) -> int:
        """Limite SUPERIORE al tempo che serve a un carroponte per coprire i
        primi (o gli ultimi) `x` millimetri di uno spostamento che parte da fermo a
        una stazione. Il caso peggiore e' uno spostamento lungo esattamente x,
        che deve anche decelerare: piu' lento di un tratto iniziale di uno
        spostamento piu' lungo, dove il carroponte accelera e basta. Si prende
        la piu' lenta fra le due cinematiche."""
        if x <= 0:
            return 0
        return T_(
            max(
                _travel_time_seconds(x, data.kin_loaded),
                _travel_time_seconds(x, data.kin_empty),
            )
        )

    max_escape = escape_ticks(required_sep * 2)

    # -- Variabili di takt time --------------------------------------------
    T_min, T_max = T_(data.takt_min), T_(data.takt_max)
    Tv = model.NewIntVar(T_min, T_max, "T")

    # -- Orizzonte e limiti tecnici per i domini delle variabili -----------
    horizon = (
        4 * T_max
        + sum(T_(s.dwell_max) for s in data.route)
        + sum(travel_loaded)
        + 10 * scale
    )
    BIG = 10**7
    n_shifts = math.ceil(horizon / T_min) + 2
    # dep_hi/arr_lo sono comunque limitati dai vincoli del modello
    # (arr_lo <= local_pick + T e dep_hi + t_emp <= local_pick + T, con
    # local_pick < T <= T_max, quindi entrambi <= 2*T_max). Dichiararlo nel
    # dominio invece di lasciarli a BIG serve a tenere piccolo il numero di
    # traslazioni da generare nel vincolo di non collisione.
    DEP_MAX = 2 * T_max + max(travel_loaded)

    def _as_intvar(expr, name):
        """Materializza un'espressione lineare in un vero IntVar, legato
        all'espressione con un vincolo di uguaglianza. Passare sempre IntVar
        "puri" a NewIntervalVar (invece di espressioni composte) e' piu'
        robusto fra le diverse versioni di OR-Tools."""
        v = model.NewIntVar(-BIG, BIG, name)
        model.Add(v == expr)
        return v

    # -- 1) Catena di flusso pezzo (invariata rispetto alla v1) -------------
    actual_time = [model.NewIntVar(0, horizon, f"at_{k}") for k in range(data.n_moves)]
    model.Add(actual_time[0] == 0)

    occupancy = {}  # tappa -> espressione "per quanto tiene occupato un posto"
    for k in range(1, data.n_moves):
        station = (
            k  # la vasca k viene raggiunta dalla mossa k-1 e lasciata dalla mossa k
        )
        spec = data.route[station]
        # I limiti di processo valgono sul BAGNO, e il bagno comprende anche
        # le corse a vuoto del gancio che vanno e vengono col pezzo gia'
        # immerso (vedi `bath_extra_seconds`). Fra i due istanti che il
        # modello maneggia -- fine del rilascio e inizio della presa -- resta
        # quindi una finestra piu' stretta, di una costante nota in anticipo:
        # il vincolo si sposta e basta, non cambia forma.
        extra = T_(data.bath_extra_seconds(station))
        # Il gancio che deposita si toglie di mezzo prima che arrivi quello
        # che preleva: la finestra non puo' diventare negativa, per corta che
        # la faccia un bagno minimo piccolo.
        dwell_min = max(0, T_(spec.dwell_min) - extra)
        dwell_max = T_(spec.dwell_max) - extra
        arrival = actual_time[k - 1] + travel_loaded[k - 1]
        model.Add(actual_time[k] >= arrival + dwell_min)
        model.Add(actual_time[k] <= arrival + dwell_max)

        # -- 1-bis) Capienza della vasca -------------------------------------
        # I pezzi entrano nella vasca ogni T secondi e ciascuno tiene occupato
        # un posto per `slot_occupancy` secondi (immersione + bagno +
        # emersione), quindi i pezzi di QUESTA tappa contemporaneamente
        # presenti sono ceil(occupazione / T). Imporre occupazione <=
        # capacity * T e' esattamente equivalente a ceil(...) <= capacity.
        # `capacity` e' una costante intera e Tv una variabile: il prodotto
        # resta LINEARE, quindi il vincolo non costa praticamente nulla.
        # Se la stessa vasca compare in piu' tappe serve altro: vedi 1-ter.
        occ_extra = T_(data.release_time_at(station)) + T_(data.pick_time_at(station))
        occupancy[station] = actual_time[k] - arrival + occ_extra
        model.Add(occupancy[station] <= data.tank_capacity(station) * Tv)

    # -- 2) Per ciascun carroponte: circuito ciclico sulle mosse della
    #    propria zona, con ordine di visita libero. ------------------------
    zone_data = []
    for h, z in enumerate(data.zones):
        moves = list(range(z.lo, z.hi + 1))
        n_h = len(moves)
        lo_h, hi_h = z.lo, z.hi

        # -- fase locale (in [0,T)) di ciascuna mossa della zona, agganciata
        #    alla catena globale actual_time tramite una ricerca su un
        #    numero finito di possibili "giri" (shift): resta tutto LINEARE.
        local_pick = {}
        for k in moves:
            lp = model.NewIntVar(0, T_max - 1, f"lp_{h}_{k}")
            lits = []
            for m in range(0, n_shifts + 1):
                lit = model.NewBoolVar(f"lp_{h}_{k}_shift_{m}")
                model.Add(lp == actual_time[k] - m * Tv).OnlyEnforceIf(lit)
                lits.append(lit)
            model.AddExactlyOne(lits)
            model.Add(lp < Tv)
            local_pick[k] = lp

        finish = {
            k: _as_intvar(local_pick[k] + travel_loaded[k], f"fin_{h}_{k}")
            for k in moves
        }

        if n_h == 1:
            # Caso degenere: una sola mossa nella zona. Il "circuito" e'
            # semplicemente andata (mossa) + ritorno a vuoto, come in v1.
            k0 = moves[0]
            dep_hi = model.NewIntVar(0, DEP_MAX, f"dep_hi_{h}")
            model.Add(dep_hi >= finish[k0])
            arr_lo = model.NewIntVar(0, DEP_MAX, f"arr_lo_{h}")
            t_ret = travel_empty_ticks(hi_h + 1, lo_h)
            model.Add(arr_lo == dep_hi + t_ret)
            model.Add(arr_lo <= local_pick[lo_h] + Tv)
            zone_data.append(
                dict(
                    h=h,
                    z=z,
                    moves=moves,
                    local_pick=local_pick,
                    finish=finish,
                    dep_hi=dep_hi,
                    arr_lo=arr_lo,
                    arc_lits=None,
                    # con una sola mossa il giro si richiude per forza su di
                    # lei: non c'e' niente da scegliere
                    inizio=None,
                    # l'unico rientro parte dal confine alto, e li' la
                    # partenza libera e' gia' dep_hi
                    partenze={},
                    # unico "arco": andata (gia' nella mossa) + rientro a vuoto
                    arcs=[
                        dict(
                            k1=k0,
                            k2=k0,
                            lit=None,
                            span_start=finish[k0],
                            depart=dep_hi,
                            arrive=arr_lo,
                            span_end=local_pick[k0] + Tv,
                        )
                    ],
                )
            )
            continue

        # -- circuito generale per n_h > 1: il carroponte visita tutte le
        #    mosse della zona una volta a periodo, in un ordine libero. ----
        local_idx = {k: i for i, k in enumerate(moves)}
        arc_lits = {}
        arcs_for_circuit = []
        for k1 in moves:
            for k2 in moves:
                if k1 == k2:
                    continue
                lit = model.NewBoolVar(f"arc_{h}_{k1}_{k2}")
                arc_lits[(k1, k2)] = lit
                arcs_for_circuit.append((local_idx[k1], local_idx[k2], lit))
        model.AddCircuit(arcs_for_circuit)

        # -- da quale mossa comincia il giro ---------------------------------
        #
        # Il giro e' un CICLO: uno dei suoi archi attraversa la fine del
        # periodo, e a quello -- e solo a quello -- si somma un T, perche' il
        # prelievo a cui porta appartiene al ciclo dopo. Quale sia lo decide il
        # solutore: `inizio[k]` vale 1 sulla mossa a cui il periodo si
        # richiude, cioe' la prima del giro.
        #
        # PRIMA ERA FISSATO SU lo_h, e non era una convenzione innocua. Per
        # ogni arco che NON portava a lo_h il vincolo era
        # `finish[k1] + t_vuoto <= local_pick[k2]`, e poiche' finish[k1] e'
        # maggiore di local_pick[k1] ne seguiva local_pick[k2] > local_pick[k1]:
        # lungo il giro le fasi dovevano crescere, e partendo da lo_h questo
        # OBBLIGAVA lo_h a essere la mossa piu' anticipata del carroponte.
        # Ciclogrammi perfettamente realizzabili in cui il carroponte comincia
        # il giro da un'altra mossa non stavano nello spazio di ricerca: il
        # solutore li dichiarava INFEASIBLE senza averli mai considerati.
        inizio = {k: model.NewBoolVar(f"inizio_{h}_{k}") for k in moves}
        model.AddExactlyOne(list(inizio.values()))

        # `bersaglio[k]` e' l'istante ENTRO CUI bisogna essere pronti per il
        # prelievo della mossa k: la sua fase, piu' un periodo se e' li' che il
        # giro si richiude. Materializzarlo in una variabile costa un IntVar e
        # due vincoli per mossa, e in cambio tutto quello che segue resta
        # scritto una volta sola.
        #
        # La prima stesura invece condizionava OGNI vincolo e OGNI intervallo
        # su `inizio[k2]`, raddoppiandoli: il modello ci metteva piu' del
        # doppio a risolvere, e sulle linee grandi i tentativi cominciavano a
        # scadere. La differenza non e' di stile -- e' che una scelta che
        # riguarda la MOSSA veniva ripetuta su ogni ARCO che ci arriva.
        bersaglio = {}
        for k in moves:
            b = model.NewIntVar(0, 2 * T_max, f"bersaglio_{h}_{k}")
            model.Add(b == local_pick[k] + Tv).OnlyEnforceIf(inizio[k])
            model.Add(b == local_pick[k]).OnlyEnforceIf(inizio[k].Not())
            bersaglio[k] = b

        # vincolo di tempo per ciascun arco possibile: se selezionato,
        # bisogna riuscire ad arrivare in tempo alla mossa successiva
        for (k1, k2), lit in arc_lits.items():
            t_emp = travel_empty_ticks(k1 + 1, k2)
            model.Add(finish[k1] + t_emp <= bersaglio[k2]).OnlyEnforceIf(lit)

        # -- variabili libere di confine (per traiettoria e non-collisione) --
        dep_hi = model.NewIntVar(0, DEP_MAX, f"dep_hi_{h}")
        model.Add(dep_hi >= finish[hi_h])
        for k2 in moves:
            if k2 == hi_h:
                continue
            t_emp = travel_empty_ticks(hi_h + 1, k2)
            model.Add(dep_hi + t_emp <= bersaglio[k2]).OnlyEnforceIf(
                arc_lits[(hi_h, k2)]
            )

        arr_lo = model.NewIntVar(0, DEP_MAX, f"arr_lo_{h}")
        for k1 in moves:
            if k1 == lo_h:
                continue
            t_emp = travel_empty_ticks(k1 + 1, lo_h)
            model.Add(arr_lo >= finish[k1] + t_emp).OnlyEnforceIf(arc_lits[(k1, lo_h)])
        # arr_lo e' l'arrivo al confine BASSO, e il prelievo di lo_h appartiene
        # al ciclo dopo solo se e' li' che il periodo si richiude: e' proprio
        # quello che `bersaglio` dice.
        model.Add(arr_lo <= bersaglio[lo_h])

        # se l'arco hi_h -> lo_h e' selezionato (rientro diretto, senza
        # visitare altre mosse nel mezzo), dep_hi e arr_lo descrivono lo
        # STESSO spostamento a vuoto: vanno legati fra loro esattamente.
        if (hi_h, lo_h) in arc_lits:
            t_emp_direct = travel_empty_ticks(hi_h + 1, lo_h)
            model.Add(arr_lo == dep_hi + t_emp_direct).OnlyEnforceIf(
                arc_lits[(hi_h, lo_h)]
            )

        # Istanti di partenza/arrivo di ciascun trasferimento a vuoto, usati
        # dal vincolo di non collisione. Le convenzioni devono essere IDENTICHE
        # a quelle di _build_zone_trajectory, altrimenti il vincolo
        # proteggerebbe una traiettoria diversa da quella poi disegnata.
        arcs = []
        partenze = {}
        for (k1, k2), lit in arc_lits.items():
            t_emp = travel_empty_ticks(k1 + 1, k2)
            if k1 == hi_h:
                depart = dep_hi
            elif k2 == lo_h:
                depart = arr_lo - t_emp
            else:
                # DOVE il carroponte passa il tempo che gli avanza lo sceglie
                # il solutore, non una convenzione: `depart` e' libera fra la
                # consegna e l'ultimo istante utile per arrivare in tempo.
                # Partire subito significa aspettare a destinazione, partire
                # tardi significa aspettare dove si e' consegnato, e ogni via
                # di mezzo e' ammessa. Sui due archi di confine la stessa
                # liberta' ce l'hanno gia' dep_hi e arr_lo.
                #
                # Questa scelta NON discende dalle fasi: va salvata insieme
                # al ciclogramma, altrimenti riaprendo il file si
                # ricostruirebbe una traiettoria diversa da quella verificata.
                depart = model.NewIntVar(0, DEP_MAX, f"part_{h}_{k1}_{k2}")
                model.Add(depart >= finish[k1]).OnlyEnforceIf(lit)
                model.Add(depart + t_emp <= bersaglio[k2]).OnlyEnforceIf(lit)
                partenze[(k1, k2)] = depart
            arrive = arr_lo if k2 == lo_h else depart + t_emp
            # L'attesa DOPO l'arrivo finisce al prelievo successivo, che sta
            # nel ciclo dopo solo se e' qui che il periodo si richiude: e'
            # esattamente quello che dice `bersaglio`.
            arcs.append(
                dict(
                    k1=k1,
                    k2=k2,
                    lit=lit,
                    span_start=finish[k1],
                    depart=depart,
                    arrive=arrive,
                    span_end=bersaglio[k2],
                )
            )

        zone_data.append(
            dict(
                h=h,
                z=z,
                moves=moves,
                local_pick=local_pick,
                finish=finish,
                dep_hi=dep_hi,
                arr_lo=arr_lo,
                arc_lits=arc_lits,
                inizio=inizio,
                arcs=arcs,
                partenze=partenze,
            )
        )

    # -- 2-bis) Capienza delle vasche usate PIU' VOLTE nella ricetta --------
    #
    # Il vincolo 1-bis limita i pezzi di una singola tappa. Se pero' la stessa
    # vasca fisica compare in due o piu' tappe del percorso, i loro pezzi si
    # contendono gli stessi posti e i conteggi si sommano. Sommare i massimi
    # sarebbe cautelativo (le due tappe potrebbero essere sfasate fra loro), e
    # per una vasca a posto singolo scarterebbe soluzioni valide.
    #
    # La formulazione esatta e' un vincolo CUMULATIVO: ogni pezzo occupa un
    # posto per l'intervallo [fine immersione ... fine emersione], gli
    # intervalli si ripetono ogni T, e in nessun istante se ne possono
    # sovrapporre piu' di `capacity`. Basta replicare ogni intervallo su
    # abbastanza periodi perche' la finestra centrale sia coperta per intero:
    # ai bordi il vincolo risulta solo piu' debole, mai piu' forte.
    local_pick_of = {}
    for zd in zone_data:
        local_pick_of.update(zd["local_pick"])

    for tank_id, steps in data.steps_by_tank().items():
        if len(steps) < 2:
            continue  # gia' coperta esattamente dal vincolo 1-bis
        cap = data.tanks[tank_id].capacity
        k_lo = -(math.ceil((T_max + max(travel_loaded)) / T_min) + 1)
        k_hi = math.ceil(((cap + 1) * T_max + max(travel_loaded)) / T_min) + 1
        intervals = []
        for station in steps:
            # fine dell'emersione: il telaio lascia libero il posto
            end_expr = local_pick_of[station] + T_(data.pick_time_at(station))
            occ_expr = occupancy[station]
            for sh in range(k_lo, k_hi + 1):
                st = _as_intvar(end_expr - occ_expr + sh * Tv, f"cap_{tank_id}_{station}_{sh}_s")
                en = _as_intvar(end_expr + sh * Tv, f"cap_{tank_id}_{station}_{sh}_e")
                sz = model.NewIntVar(0, horizon, f"cap_{tank_id}_{station}_{sh}_sz")
                model.Add(sz == en - st)
                intervals.append(
                    model.NewIntervalVar(st, sz, en, f"cap_{tank_id}_{station}_{sh}")
                )
        model.AddCumulative(intervals, [1] * len(intervals), cap)

    # -- 3) Non collisione: fascia di esclusione attorno a ogni confine -----
    #
    # IDEA. Attorno alla stazione di confine b fra due zone adiacenti, siano
    # a(t) la distanza del carroponte di sinistra da b e c(t) quella del
    # carroponte di destra. Poiche' le due zone stanno su lati opposti, la
    # distanza fra i due carroponti vale esattamente a(t) + c(t), e serve
    #
    #     a(t) + c(t) >= D          con D = hoist_length + safety_distance
    #
    # Per ogni soglia r si puo' imporre una condizione LOCALE e lineare:
    #
    #     "mai contemporaneamente a(t) < r e c(t) <= D - r"
    #
    # che vieta solo configurazioni con a + c < D, quindi non taglia mai
    # nulla di sicuro. Imponendola su una griglia di soglie fitta abbastanza
    # si copre tutta la condizione: se a + c < D basta una soglia
    # nell'intervallo (a, D - c], lungo piu' del passo della griglia. Usando
    # passo delta = clearance_step_mm e portando il bersaglio a D + delta, la
    # distanza GARANTITA torna esattamente D, e delta e' tutto e solo l'eccesso
    # di severita' -- cioe' lo stesso passo, letto dall'altro lato.
    #
    # "a(t) < r" e' un'unione di intervalli temporali calcolabile: il
    # carroponte e' entro r da b mentre sosta su una stazione a distanza < r,
    # e per i tratti di percorso che entrano nella fascia -- con un margine
    # costante escape_ticks() perche' i tempi di percorrenza sono costanti
    # (le vasche sono in posizioni fisse).
    #
    # Questo generalizza (e sostituisce) il vecchio vincolo, che riservava
    # l'intera sosta sulla SOLA stazione di confine: quello era sano solo se
    # nessun'altra stazione cadeva entro D dal confine, ed e' anche piu'
    # cautelativo di quanto serva.

    def _make_interval(start, end, lit, name):
        """Intervallo CP-SAT, opzionale se `lit` non e' None. Con lit falso
        start/end restano liberi: le espressioni che li definiscono hanno
        senso solo se l'arco corrispondente e' effettivamente scelto."""
        s = model.NewIntVar(-BIG, BIG, name + "_s")
        e = model.NewIntVar(-BIG, BIG, name + "_e")
        sz = model.NewIntVar(0, 4 * horizon, name + "_sz")
        if lit is None:
            model.Add(s == start)
            model.Add(e == end)
            return model.NewIntervalVar(s, sz, e, name)
        model.Add(s == start).OnlyEnforceIf(lit)
        model.Add(e == end).OnlyEnforceIf(lit)
        return model.NewOptionalIntervalVar(s, sz, e, lit, name)

    def near_boundary(zd, x_b: float, radius: float):
        """Intervalli (start, end, lit) in cui il carroponte della zona `zd`
        puo' trovarsi a meno di `radius` millimetri dalla stazione in x_b.

        Il giro di un periodo si scompone in TRATTE elementari, ciascuna delle
        quali e' o una sosta (il carroponte sta fermo in un punto, o si muove
        dentro un intervallo noto) o una traslazione monotona fra due punti. Su
        una tratta monotona la distanza dal confine e' monotona, quindi bastano
        i due estremi; su una sosta si guarda tutto l'intervallo occupato.

        Non si fanno stime: le tratte del rientro a vuoto vengono da
        `tratte_rientro`, cioe' dalla stessa definizione che il disegno usa per
        farne dei segmenti. Il vincolo protegge quindi il percorso vero, corse
        verticali comprese -- ed e' proprio dimenticarsene che ha gia' prodotto
        due volte due carroponti nello stesso punto."""
        lp, fin = zd["local_pick"], zd["finish"]
        out = []

        def fermo(t_a, t_b, a: float, b: float, lit):
            """Un tratto in cui il carroponte resta dentro l'intervallo [a,b],
            senza percorrerlo in un verso solo: una sosta sopra una stazione
            (a == b), la corsa verticale del gancio su uno svincolo, oppure il
            vai-e-torna della presa su una zona di CAMBIO QUOTA.

            Se quell'intervallo tocca la fascia, ci si sta dentro tutto il
            tempo. Stimare quando si entra e quando si esce vorrebbe dire
            modellare il vai-e-torna, e per guadagnare qualche decimo su una
            sosta corta non vale la pena rischiare di sbagliarlo."""
            lo, hi = (a, b) if a <= b else (b, a)
            dentro = lo - x_b if x_b < lo else (x_b - hi if x_b > hi else 0.0)
            if dentro < radius:
                out.append((t_a, t_b, lit))

        def traslazione(t_a, t_b, xa: float, xb: float, lit):
            """Una traslazione monotona da xa a xb, fra gli istanti dati. Parte
            e arriva da ferma, quindi `escape_ticks` ne limita davvero il tempo
            speso dentro la fascia."""
            da, db = abs(xa - x_b), abs(xb - x_b)
            if da < radius and db < radius:
                out.append((t_a, t_b, lit))
            elif da < radius:
                # si esce dalla fascia durante la traslazione
                out.append((t_a, t_a + escape_ticks(radius - da), lit))
            elif db < radius:
                # si entra nella fascia durante la traslazione
                out.append((t_b - escape_ticks(radius - db), t_b, lit))
            # entrambi fuori: la distanza e' monotona, non si entra mai

        def fasi_verticali(fasi, t_inizio, x_default, lit):
            """Le finestre di una PRESA o di un RILASCIO, fase per fase.

            Su una stazione normale tutte le fasi sono ferme sullo stesso
            punto e ne esce una finestra sola, identica a quella che si
            otteneva trattando la presa come un blocco unico. Su una zona di
            CAMBIO QUOTA no: li' in mezzo ci sono due traslazioni, e il
            carroponte per un buon pezzo della presa sta lontano dalla
            stazione. Trattare tutto il giro come una sosta sarebbe sicuro ma
            sprecone -- venti secondi bloccati per una vicinanza che dura un
            istante -- e basterebbe a rendere infattibili linee che non lo
            sono.

            Le fasi ferme consecutive sullo stesso punto si accorpano: e' cio'
            che tiene il modello della stessa dimensione di prima sulle linee
            senza cambio quota."""
            secondi, prec = 0.0, 0
            da, punto = None, None  # la corsa di fasi ferme in accumulo
            for f in fasi:
                xa = x_default if f.x_start is None else f.x_start
                xb = x_default if f.x_end is None else f.x_end
                secondi += f.duration
                adesso = T_(secondi)
                if xa == xb:
                    if da is None:
                        da, punto = prec, xa
                    elif punto != xa:
                        fermo(t_inizio + da, t_inizio + prec, punto, punto, lit)
                        da, punto = prec, xa
                else:
                    if da is not None and prec > da:
                        fermo(t_inizio + da, t_inizio + prec, punto, punto, lit)
                    da = None
                    if adesso > prec:
                        traslazione(
                            t_inizio + prec, t_inizio + adesso, xa, xb, lit
                        )
                prec = adesso
            if da is not None and prec > da:
                fermo(t_inizio + da, t_inizio + prec, punto, punto, lit)

        for k in zd["moves"]:
            # La mossa in tre pezzi: presa, traslazione col pezzo, rilascio.
            t_presa = lp[k] + T_(data.pick_time_at(k))
            t_arrivo = fin[k] - T_(data.release_time_at(k + 1))
            fasi_verticali(
                data.pick_phases(k), lp[k], data.station_position(k), None
            )
            traslazione(
                t_presa, t_arrivo,
                data.approach_position(k), data.approach_position(k + 1), None,
            )
            fasi_verticali(
                data.release_phases(k + 1),
                t_arrivo,
                data.station_position(k + 1),
                None,
            )

        for arc in zd["arcs"]:
            u, v = arc["k1"] + 1, arc["k2"]
            depart, lit = arc["depart"], arc["lit"]
            tratte = tratte_rientro(data, u, v)
            # l'attesa prima di partire, e quella dopo essere arrivato
            fermo(arc["span_start"], depart, tratte[0][0], tratte[0][0], lit)
            fermo(arc["arrive"], arc["span_end"], tratte[-1][1], tratte[-1][1], lit)
            # Le tratte del rientro, una per una. I confini si convertono in
            # tick sul tempo CUMULATO e non tratta per tratta: cosi' l'ultimo
            # coincide con T_(empty_leg_seconds), che e' quello che il modello
            # ha usato per legare `arrive` a `depart`, e fra le tratte non si
            # aprono buchi da arrotondamento.
            secondi, prec = 0.0, 0
            for xa, xb, durata in tratte:
                secondi += durata
                adesso = T_(secondi)
                if adesso > prec:
                    if xa == xb:
                        fermo(depart + prec, depart + adesso, xa, xa, lit)
                    else:
                        traslazione(depart + prec, depart + adesso, xa, xb, lit)
                prec = adesso
        return out

    # Quante traslazioni di T servono perche' due blocchi possano incontrarsi.
    # Tutti gli istanti in gioco (local_pick, finish, dep_hi, arr_lo, span_end,
    # piu' i margini di ingresso/uscita dalla fascia) stanno in questa
    # finestra; oltre, le copie traslate non possono piu' sovrapporsi.
    # NOTA: il conto e' fatto sul caso peggiore T = takt_min. Una banda di
    # takt time molto larga (takt_max >> takt_min) fa quindi crescere parecchio
    # il numero di vincoli generati: se il modello diventa lento, stringere la
    # tolleranza sul takt time e' la prima cosa da provare.
    span_tot = 2 * T_max + max(travel_loaded) + 2 * max_escape
    n_shifts_sep = math.ceil(span_tot / T_min) + 1

    n_sep_constraints = 0
    for h in range(data.n_hoists - 1):
        zL, zR = zone_data[h], zone_data[h + 1]
        z_left, z_right = zL["z"], zR["z"]
        assert z_left.hi + 1 == z_right.lo, "le zone devono essere contigue"
        x_b = data.station_position(z_right.lo)

        # delta e' la distanza fra una verifica e la successiva, dichiarata in
        # millimetri: il numero di verifiche e' una conseguenza, non un
        # ingresso. Al contrario (numero dichiarato, delta derivato) la
        # grandezza che si capisce -- ogni quanto si controlla, e quindi di
        # quanto si puo' sbagliare per eccesso -- resterebbe implicita.
        delta = data.clearance_step_mm
        target = required_sep + delta  # cosi' la garanzia netta torna a D
        # Servono soglie fino a `target`: qualunque punto con a + c < D cade
        # allora in un intervallo aperto lungo piu' di delta, che una griglia
        # di passo delta non puo' mancare.
        n_soglie = math.ceil(required_sep / delta) + 1
        for i in range(1, n_soglie + 1):
            r_left = i * delta
            r_right = target - r_left
            if r_right < 0:
                continue
            A = near_boundary(zL, x_b, r_left)
            # a destra la condizione e' "<= r_right": un epsilon di un tick
            # basta a trasformarla in un confronto stretto
            B = near_boundary(zR, x_b, r_right + 1e-9)
            if not A or not B:
                continue
            nome = f"sep_{h}_{i}"
            a_ivs = [
                _make_interval(s, e, lit, f"{nome}_a{j}")
                for j, (s, e, lit) in enumerate(A)
            ]
            b_ivs = []
            for sh in range(-n_shifts_sep, n_shifts_sep + 1):
                for j, (s, e, lit) in enumerate(B):
                    b_ivs.append(
                        _make_interval(
                            s + sh * Tv, e + sh * Tv, lit, f"{nome}_b{j}_{sh}"
                        )
                    )
            # a coppie, e non tutti in un unico AddNoOverlap: gli intervalli
            # di uno stesso carroponte POSSONO sovrapporsi fra loro (i margini
            # di ingresso/uscita dalla fascia sconfinano nel blocco vicino), e
            # metterli insieme li renderebbe mutuamente esclusivi, rendendo il
            # modello infattibile per un motivo inesistente.
            for a_iv in a_ivs:
                for b_iv in b_ivs:
                    model.AddNoOverlap([a_iv, b_iv])
                    n_sep_constraints += 1

    # -- Obiettivo: minimizzare il takt time entro la tolleranza data -------
    model.Minimize(Tv)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.log_search_progress = log_search
    solver.parameters.num_workers = 8
    status = solver.Solve(model)

    status_name = solver.StatusName(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Solution(status=status_name, T=None)

    T_seconds = data.to_seconds(solver.Value(Tv))

    segments_per_hoist = []
    plans: list[HoistPlan] = []
    for zd in zone_data:
        z = zd["z"]
        moves = zd["moves"]
        lp_val = {k: data.to_seconds(solver.Value(zd["local_pick"][k])) for k in moves}
        fin_val = {k: data.to_seconds(solver.Value(zd["finish"][k])) for k in moves}
        dep_hi_val = data.to_seconds(solver.Value(zd["dep_hi"]))
        arr_lo_val = data.to_seconds(solver.Value(zd["arr_lo"]))

        if zd["arc_lits"] is None:
            order = [z.lo]
        else:
            nxt = {}
            for (k1, k2), lit in zd["arc_lits"].items():
                if solver.Value(lit):
                    nxt[k1] = k2
            # Il giro si racconta a partire dalla mossa su cui il periodo si
            # richiude, che il solutore ha scelto: NON e' detto sia quella di
            # confine basso. Partire comunque da z.lo darebbe un elenco con le
            # fasi fuori ordine, e chi lo legge -- il disegno, il verificatore
            # -- metterebbe il +T sull'arco sbagliato.
            partenza = next(
                k for k in moves if solver.Value(zd["inizio"][k])
            )
            order = [partenza]
            cur = partenza
            while True:
                cur = nxt[cur]
                if cur == partenza:
                    break
                order.append(cur)

        # Quanto il carroponte e' rimasto fermo dove ha consegnato, arco per
        # arco del giro scelto. E' l'unica parte della traiettoria che non
        # discende dalle fasi: si legge qui e si porta dietro nel piano.
        attese = {}
        for i, k1 in enumerate(order):
            k2 = order[(i + 1) % len(order)]
            t_emp = data.empty_leg_seconds(k1 + 1, k2)
            if k1 == z.hi:
                partenza_val = dep_hi_val
            elif k2 == z.lo:
                partenza_val = arr_lo_val - t_emp
            else:
                partenza_val = data.to_seconds(
                    solver.Value(zd["partenze"][(k1, k2)])
                )
            attese[k1] = max(0.0, partenza_val - fin_val[k1])

        segs = _build_zone_trajectory(
            data, z, order, lp_val, dep_hi_val, arr_lo_val, T_seconds,
            attese=attese,
        )
        segments_per_hoist.append(segs)
        plans.append(
            HoistPlan(
                zone=z,
                order=order,
                local_pick=lp_val,
                finish=fin_val,
                dep_hi=dep_hi_val,
                arr_lo=arr_lo_val,
                attese=attese,
            )
        )

    raw = {
        "objective": solver.ObjectiveValue(),
        "wall_time": solver.WallTime(),
        "T_ticks": solver.Value(Tv),
        "required_separation_m": required_sep,
        "clearance_step_mm": data.clearance_step_mm,
        "n_separation_constraints": n_sep_constraints,
    }
    return Solution(
        status=status_name,
        T=T_seconds,
        segments_per_hoist=segments_per_hoist,
        raw=raw,
        plans=plans,
        actual_time=[data.to_seconds(solver.Value(v)) for v in actual_time],
    )


# --------------------------------------------------------------------------
# Costruzione di un ciclogramma a partire dai suoi GRADI DI LIBERTA'
# --------------------------------------------------------------------------


def build_solution(
    data: ProblemData,
    T: float,
    local_pick: Optional[dict[int, float]] = None,
    extra_periods: Optional[dict[int, int]] = None,
    status: str = "MANUALE",
    actual_time: Optional[list[float]] = None,
    tollerante: bool = False,
    mosse_attive: Optional[set] = None,
    attese: Optional[dict[int, float]] = None,
) -> Solution:
    """Costruisce una Solution completa dai soli gradi di liberta' di un
    ciclogramma: il takt time e l'istante di prelievo (fase, in [0,T)) di
    ciascuna mossa. Tutto il resto -- ordine di visita, tempi assoluti,
    traiettorie -- e' derivato.

    Non risolve e non verifica nulla: serve a comporre un ciclogramma a mano,
    o a rimetterne insieme uno modificato dall'utente, per poi passarlo al
    verificatore esattamente come si fa con una soluzione del solutore.

    Convenzioni (le stesse usate nella ricostruzione delle traiettorie):
    - il carroponte visita le mosse della propria zona nell'ordine dei loro
      istanti di prelievo;
    - il pezzo viene prelevato al primo istante compatibile con la fase
      scelta che rispetti la permanenza minima; `extra_periods[k]` aggiunge
      altri periodi interi, allungando la permanenza nella vasca k;
    - dove il carroponte passa il tempo morto del rientro a vuoto lo dice
      `attese[k]` (secondi fermo dove ha consegnato la mossa k). E' il quarto
      grado di liberta': non discende dalle fasi, quindi o arriva da fuori --
      dal solutore, o dal file in cui era stato salvato -- oppure si ripiega
      sulla regola predefinita, che e' aspettare dove si e' consegnato tranne
      che sulle vasche di confine.

    Solleva ValueError se la disposizione non e' realizzabile (per esempio se
    un carroponte dovrebbe essere in due posti insieme).
    """
    if data.zones is None:
        raise ValueError("build_solution richiede data.zones valorizzato")
    if T <= 0:
        raise ValueError("il takt time deve essere > 0")
    incoerenze: Optional[list[str]] = [] if tollerante else None

    # Due modi di dire la stessa cosa: o si danno le fasi e la catena dei
    # tempi assoluti viene dedotta (modifica di un ciclogramma esistente), o si
    # danno direttamente i tempi assoluti del pezzo e le fasi ne discendono
    # (disegno manuale, dove a essere scelti sono i tempi in vasca).
    if actual_time is not None:
        if len(actual_time) != data.n_moves:
            raise ValueError(
                f"actual_time deve avere {data.n_moves} valori, "
                f"ne ha {len(actual_time)}"
            )
        actual_time = [float(v) for v in actual_time]
        # `mosse_attive` serve al disegno manuale: finche' l'utente non ha
        # assegnato tutte le mosse a un carroponte, quelle scoperte non fanno
        # parte di nessun giro e non vanno disegnate. Il verificatore le
        # segnalera' come mancanti, che e' esatto.
        chiavi = (
            range(data.n_moves)
            if mosse_attive is None
            else sorted(mosse_attive)
        )
        local_pick = {k: _fase_nel_periodo(actual_time[k], T, data) for k in chiavi}
        return _assembla(
            data, T, local_pick, actual_time, status, incoerenze, attese
        )

    if local_pick is None:
        raise ValueError("servono le fasi di prelievo oppure i tempi assoluti")
    mancanti = [k for k in range(data.n_moves) if k not in local_pick]
    if mancanti:
        raise ValueError(f"manca l'istante di prelievo per le mosse {mancanti}")
    extra_periods = extra_periods or {}

    # -- tempi assoluti: catena di flusso del pezzo -------------------------
    actual_time = [float(local_pick[k]) for k in range(data.n_moves)]
    for k in range(1, data.n_moves):
        arrivo = actual_time[k - 1] + data.loaded_leg_seconds(k - 1)
        # il minimo di processo vale sul BAGNO, che comprende le corse a vuoto
        # del gancio: fra i due istanti maneggiati qui resta di meno
        minimo = arrivo + max(
            0.0, data.route[k].dwell_min - data.bath_extra_seconds(k)
        )
        # Si sale di periodi interi: la FASE resta quella scelta dall'utente.
        # La tolleranza sul ceil non e' un dettaglio. Quando la permanenza
        # cade esattamente sul minimo -- il caso tipico di una soluzione
        # ottima -- basta uno scarto infinitesimo per far scattare un periodo
        # di troppo, e la permanenza salta di T secondi interi. Lo scarto c'e'
        # sempre: le fasi che arrivano dal solutore sono arrotondate al tick,
        # mentre qui i tempi di percorrenza sono ricalcolati in virgola
        # mobile. La tolleranza e' quindi quella del progetto (eps_seconds),
        # non un epsilon numerico.
        giri = (minimo - actual_time[k]) / T
        n_giri = max(0, math.ceil(giri - data.eps_seconds / T))
        actual_time[k] += (n_giri + extra_periods.get(k, 0)) * T

    return _assembla(
        data, T, local_pick, actual_time, status, incoerenze, attese
    )


def _fase_nel_periodo(istante: float, T: float, data: ProblemData) -> float:
    """La fase di un istante dentro il periodo, cioe' `istante % T` -- ma senza
    la trappola del multiplo esatto.

    Il resto di un multiplo esatto di T vale zero, e un capello meno di quel
    multiplo vale quasi T: fra i due c'e' un salto di un periodo intero. La
    catena dei tempi si ricostruisce sommando una permanenza dopo l'altra in
    virgola mobile, quindi un istante che dovrebbe cadere esattamente su 2T ci
    cade appena sotto -- e il carroponte si ritrova a cominciare il giro un
    periodo dopo, senza piu' fare in tempo ad arrivare da nessuna parte.

    Succedeva riaprendo un file: il ciclogramma appena calcolato era pulito,
    quello riletto pieno di attese lunghe un takt. La tolleranza e' quella del
    progetto (`eps_seconds`), la stessa con cui si decide quanti periodi interi
    un pezzo resta in vasca."""
    resto = istante % T
    return 0.0 if T - resto <= data.eps_seconds else resto


def _assembla(
    data: ProblemData,
    T: float,
    local_pick: dict[int, float],
    actual_time: list[float],
    status: str,
    incoerenze: Optional[list[str]],
    attese: Optional[dict[int, float]] = None,
) -> Solution:
    """Da fasi e tempi assoluti alle traiettorie di ciascun carroponte."""
    segments_per_hoist = []
    plans = []
    for z in data.zones:
        moves = [k for k in range(z.lo, z.hi + 1) if k in local_pick]
        if not moves:
            segments_per_hoist.append([])
            continue
        # Il giro si racconta in ordine di PRELIEVO, e comincia dalla mossa che
        # il carroponte serve per prima dentro il periodo.
        #
        # Prima lo si ruotava per farlo cominciare dalla mossa di indice piu'
        # basso, che e' la convenzione del solutore -- ma li' regge perche' il
        # modello COSTRINGE quella mossa a essere anche la prima in ordine di
        # tempo (lungo il giro le fasi crescono, e il giro parte da lei).
        # Componendo a mano nessuno lo costringe: se il carroponte serve prima
        # la mossa 6 e poi la 5, la rotazione produce il giro [5, 6] e pretende
        # che dalla 5 si arrivi alla 6 SENZA cambiare periodo -- cioe' indietro
        # nel tempo. Ne usciva un "non arriva in tempo" su un giro che invece
        # sta benissimo in piedi, e una traiettoria disegnata a pezzi
        # scambiati.
        order = sorted(moves, key=lambda k: local_pick[k])
        riferimento = order[0]
        lp = {k: float(local_pick[k]) for k in moves}
        finish = {k: lp[k] + data.loaded_leg_seconds(k) for k in moves}
        # I due istanti di confine si calcolano con la STESSA regola che usa il
        # disegno (`_aspetta_dove_ha_consegnato`), altrimenti descriverebbero
        # una traiettoria diversa da quella che si vede.
        def quando(k1: int, k2: int) -> tuple[float, float]:
            """(partenza, arrivo) del rientro a vuoto dalla mossa k1 alla k2."""
            vuoto = data.empty_leg_seconds(k1 + 1, k2)
            if attese is not None:
                # c'e' una scelta gia' fatta -- dal solutore, o salvata nel
                # file -- e si usa quella: e' l'unico modo perche' il
                # ciclogramma riaperto sia quello che era stato verificato
                partenza = finish[k1] + attese.get(k1, 0.0)
                return partenza, partenza + vuoto
            bersaglio = lp[k2] + (T if k2 == riferimento else 0.0)
            if _aspetta_dove_ha_consegnato(z, k1, k2):
                arrivo = max(bersaglio, finish[k1] + vuoto)
                return arrivo - vuoto, arrivo
            return finish[k1], finish[k1] + vuoto

        # I due istanti di confine riguardano le STAZIONI agli estremi della
        # zona, non il giro: si prendono gli archi che le toccano davvero.
        # Con un'assegnazione parziale quegli estremi possono non essere fra
        # le mosse assegnate, e allora si ripiega su quelle che ci sono.
        dopo = {k: order[(i + 1) % len(order)] for i, k in enumerate(order)}
        prima = {v: k for k, v in dopo.items()}
        basso = z.lo if z.lo in lp else riferimento
        alto = z.hi if z.hi in lp else max(moves)
        arr_lo = quando(prima[basso], basso)[1]
        dep_hi = quando(alto, dopo[alto])[0]
        # Le attese di QUESTA zona, o dal valore ricevuto o dalla regola
        # predefinita. Nel piano ci finiscono comunque, cosi' chi salva il
        # ciclogramma ha sempre il quarto grado di liberta' da scrivere.
        att = {
            k: quando(k, dopo[k])[0] - finish[k] for k in moves
        }
        segments_per_hoist.append(
            _build_zone_trajectory(
                data, z, order, lp, dep_hi, arr_lo, T, incoerenze,
                attesa_alla_partenza=attese is None,
                attese=None if attese is None else att,
            )
        )
        plans.append(HoistPlan(z, order, lp, finish, dep_hi, arr_lo, att))

    raw = {"origine": "costruita da build_solution"}
    if incoerenze is not None:
        raw["incoerenze"] = incoerenze
    return Solution(
        status=status,
        T=float(T),
        segments_per_hoist=segments_per_hoist,
        raw=raw,
        plans=plans,
        actual_time=actual_time,
    )


def estrai_gradi_di_liberta(
    data: ProblemData, solution: Solution
) -> tuple[float, dict[int, float], dict[int, int], dict[int, float]]:
    """Estrae da una soluzione i soli valori che servono a ricostruirla: takt
    time, fase di prelievo di ogni mossa, periodi in piu' rispetto al minimo
    trascorsi in ciascuna vasca, e quanto ogni carroponte resta fermo dove ha
    consegnato.

    Nessuno dei due ultimi e' deducibile dalle fasi, ed e' proprio per questo
    che stanno qui.

    I periodi in piu': il solutore puo' benissimo lasciare il pezzo in vasca un
    takt in piu' del necessario, e la fase resta la stessa. Senza, la
    ricostruzione tornerebbe al minimo e cambierebbe le permanenze.

    Le soste: a parita' di tutto il resto il carroponte puo' ripartire subito e
    aspettare a destinazione, oppure restare fermo dove ha consegnato e partire
    all'ultimo momento. Sono traiettorie diverse, con collisioni diverse.
    Ricostruire senza questo valore ha prodotto, su 50 soluzioni verificate
    pulite, 14 ciclogrammi che collidevano -- uno con i carri sovrapposti.

    Il risultato e' pensato per essere passato a build_solution: e' lo stato
    modificabile di un ciclogramma.
    """
    if not solution.plans or not solution.actual_time:
        raise ValueError(
            "la soluzione non porta con se' i valori risolti: impossibile "
            "estrarne i gradi di liberta'"
        )
    T = solution.T
    local_pick = {k: v for p in solution.plans for k, v in p.local_pick.items()}
    at = solution.actual_time
    extra: dict[int, int] = {}
    for k in range(1, data.n_moves):
        arrivo = at[k - 1] + data.loaded_leg_seconds(k - 1)
        minimo = arrivo + max(
            0.0, data.route[k].dwell_min - data.bath_extra_seconds(k)
        )
        base = local_pick[k]
        n_min = max(0, math.ceil((minimo - base) / T - data.eps_seconds / T))
        n_reale = round((at[k] - base) / T)
        if n_reale > n_min:
            extra[k] = n_reale - n_min
    attese = {k: v for p in solution.plans for k, v in p.attese.items()}
    return T, local_pick, extra, attese


def proposta_semplice(
    data: ProblemData, T: Optional[float] = None
) -> tuple[Solution, ProblemData]:
    """Ciclogramma di partenza, banale ma sempre COSTRUIBILE: un carroponte
    solo che percorre la linea da un capo all'altro, eseguendo le mosse una
    dopo l'altra senza pause, e poi torna indietro a vuoto.

    Il giro si compone dal punto di vista del CARROPONTE, non del pezzo: e'
    l'unico modo per essere certi che la traiettoria esista. Le permanenze
    vengono di conseguenza -- ogni vasca trattiene il pezzo per un numero
    intero di periodi, il minimo che rispetti la permanenza minima -- e non e'
    detto che rientrino nelle tolleranze di processo: se non ci rientrano, lo
    dice il verificatore.

    Serve come punto di partenza per comporre un ciclogramma a mano: meglio
    partire da qualcosa di concreto e verificabile che da un foglio bianco.
    Restituisce (soluzione, dati con la zona unica valorizzata).
    """
    d = dataclasses.replace(data, zones=[HoistZone(0, data.n_moves - 1)])

    # il carroponte incatena le mosse: finita la k-1 e' gia' sulla stazione da
    # cui parte la k, quindi non c'e' nessuno spostamento a vuoto nel mezzo
    local_pick = {0: 0.0}
    for k in range(1, d.n_moves):
        local_pick[k] = local_pick[k - 1] + d.loaded_leg_seconds(k - 1)
    fine_giro = local_pick[d.n_moves - 1] + d.loaded_leg_seconds(d.n_moves - 1)
    rientro = d.empty_leg_seconds(d.n_moves, 0)
    ciclo_minimo = fine_giro + rientro

    if T is None:
        # dentro la banda dichiarata se ci sta; altrimenti il minimo possibile,
        # e sara' il verificatore a segnalare che il takt time non e' rispettato
        T = min(max(ciclo_minimo, d.takt_min), d.takt_max)
        if ciclo_minimo > d.takt_max:
            T = ciclo_minimo
    return build_solution(d, T, local_pick, status="PROPOSTA"), d


# --------------------------------------------------------------------------
# Costruzione della traiettoria (posizione nel tempo) a partire dai valori
# risolti, per UNA zona/carroponte. Separata dalla risoluzione CP-SAT cosi'
# da poter essere testata anche senza risolvere realmente un modello (es.
# con valori scelti a mano).
# --------------------------------------------------------------------------


def _segmenti_rientro(
    data: ProblemData, stazione_a: int, stazione_b: int, t0: float, t1: float
) -> list[Segment]:
    """Il rientro a vuoto dalla stazione `a` alla `b`, come tratti disegnabili.

    Col gancio che trasla basso e' un tratto solo, da vasca a vasca. Sull'
    impianto in cui il gancio calato non passa fra le vasche sono cinque: si
    trasla bassi fino allo svincolo, si sale, si trasla in alto fino allo
    svincolo di arrivo, si scende, e si trasla bassi fino alla vasca.

    Vanno emessi tutti e cinque, non riassunti in uno: il carroponte durante il
    giro si spinge FINO ALLO SVINCOLO, che sta oltre la vasca, ed e' li' che
    puo' incontrare il vicino. Un tratto unico da vasca a vasca nasconderebbe
    proprio le posizioni in cui la collisione e' piu' probabile."""
    tratte = tratte_rientro(data, stazione_a, stazione_b)
    if len(tratte) == 1:
        xa, xb, _ = tratte[0]
        return [Segment("empty", t0, t1, xa, xb, data.kin_empty)]

    segs, t = [], t0
    for i, (xa, xb, durata) in enumerate(tratte):
        if durata <= 0:
            continue
        fine = t + durata
        # Salita e discesa sono verticali: orizzontalmente il carroponte sta
        # fermo, e va detto con un tratto fermo -- un 'empty' di lunghezza nulla
        # verrebbe campionato come un movimento che non c'e'.
        # 'lift_empty': il gancio scarico sale o scende sullo svincolo.
        # Orizzontalmente e' fermo, come un'attesa, ma va distinto -- e' un
        # movimento, e la simulazione deve poterlo mostrare per quello che e'.
        # Il verso lo dice la posizione nella sequenza di `tratte_rientro`:
        # la tratta 1 sale sullo svincolo di partenza, la 3 scende su quello
        # di arrivo.
        segs.append(
            Segment("lift_empty", t, fine, xa, xb, None, sale=(i == 1))
            if xa == xb
            else Segment("empty", t, fine, xa, xb, data.kin_empty)
        )
        t = fine
    return segs


def _segmenti_fasi(
    data: ProblemData,
    fasi: list[LiftPhase],
    kind: str,
    t0: float,
    x_fermo: float,
    move: int,
) -> list[Segment]:
    """I tratti disegnabili di una PRESA o di un RILASCIO.

    Di norma e' un tratto solo: il carroponte sta fermo sopra la stazione e
    tutto quello che succede e' verticale. Con una zona di CAMBIO QUOTA no --
    dentro la presa ci sono due traslazioni fra il punto di cambio quota e la
    stazione -- e allora le fasi vanno emesse per quello che sono: le soste
    con il loro `kind`, le traslazioni con `kind='quota'`.

    Un tratto unico nasconderebbe un movimento vero, e chi campiona le
    posizioni -- il verificatore, la simulazione -- lo crederebbe fermo."""
    if not any(f.trasla for f in fasi):
        durata = sum(f.duration for f in fasi)
        if durata <= 0:
            return []
        return [Segment(kind, t0, t0 + durata, x_fermo, x_fermo, None, move=move)]

    segs: list[Segment] = []
    t = t0
    x = fasi[0].x_start if fasi[0].x_start is not None else x_fermo
    fermo_inizio: Optional[float] = None
    for f in fasi:
        if f.trasla:
            if fermo_inizio is not None and t > fermo_inizio:
                segs.append(Segment(kind, fermo_inizio, t, x, x, None, move=move))
            fermo_inizio = None
            segs.append(
                Segment(
                    "quota", t, t + f.duration, f.x_start, f.x_end, f.kin_x, move=move
                )
            )
            x = f.x_end
        elif fermo_inizio is None:
            fermo_inizio = t
        t += f.duration
    if fermo_inizio is not None and t > fermo_inizio:
        segs.append(Segment(kind, fermo_inizio, t, x, x, None, move=move))
    return segs


def _aspetta_dove_ha_consegnato(zone: HoistZone, k: int, nxt_k: int) -> bool:
    """Dove conviene che il carroponte passi il tempo che gli avanza fra due
    mosse: dove ha appena consegnato (True) o dove deve andare (False).

    La regola e' una sola: NON SOSTARE SU UNA VASCA DI CONFINE. Le stazioni
    agli estremi della zona -- `zone.lo` e `zone.hi + 1` -- sono quelle che il
    carroponte CONDIVIDE con il vicino: e' li' che uno consegna e l'altro
    viene a prendere. Restarci fermi per un minuto quando si potrebbe stare
    altrove e' il modo piu' facile di fabbricare una collisione che non c'era
    bisogno di avere.

    Quindi si aspetta all'estremo che NON e' un confine. Se lo sono tutti e
    due -- succede a un carroponte con poche mosse, dove partenza e arrivo
    sono entrambi condivisi -- non c'e' una scelta migliore dell'altra e si
    tiene quella predefinita, partire subito: almeno il tratto in mezzo lo si
    percorre presto e non si resta fermi in mezzo alla rotaia."""
    confini = {zone.lo, zone.hi + 1}
    return nxt_k in confini and (k + 1) not in confini


def _build_zone_trajectory(
    data: ProblemData,
    zone: HoistZone,
    order: list[int],
    local_pick: dict[int, float],
    dep_hi: float,
    arr_lo: float,
    T: float,
    incoerenze: Optional[list[str]] = None,
    attesa_alla_partenza: bool = False,
    attese: Optional[dict[int, float]] = None,
) -> list[Segment]:
    """incoerenze: se e' una lista, i valori impossibili non sollevano piu'
    un'eccezione ma vengono descritti li' dentro e la traiettoria viene
    disegnata lo stesso. Serve al disegno manuale, dove l'utente compone
    liberamente e vuole VEDERE cosa non torna invece di essere bloccato.

    order: lista degli indici di mossa nell'ordine in cui il carroponte
    le esegue entro un periodo, per fase di prelievo crescente.
    local_pick[k]: istante [s], in [0,T), di prelievo per la mossa k.
    dep_hi: istante [s] in cui il carroponte lascia il confine superiore
        della zona (dopo la mossa zone.hi) per il successivo spostamento a
        vuoto (puo' differire dal minimo stretto: e' una scelta del solver).
    arr_lo: istante [s] in cui il carroponte torna pronto alla PRIMA mossa
        del giro, per il prelievo di QUESTO ciclo +T.

    attese[k]: quanto il carroponte resta fermo dove ha consegnato la mossa
        k, prima di partire a vuoto. Quando c'e', decide da sola dove passa
        il tempo morto e le due alternative qui sotto non si guardano: e' il
        valore SCELTO dal solutore, e ricostruire la traiettoria con una
        convenzione al posto suo darebbe un disegno diverso da quello
        verificato. E' anche il motivo per cui va salvato nel file.

    attesa_alla_partenza: usato solo quando `attese` non c'e'. Dove il
        carroponte passa il tempo che gli avanza sul rientro a vuoto. False
        (predefinito) = parte appena consegnato e aspetta a destinazione;
        True = aspetta dove ha consegnato e parte all'ultimo momento utile.
        La traslazione e' a velocita' piena in entrambi i casi -- cambia
        QUANDO avviene, non quanto dura.

        NON e' una preferenza estetica. Il solutore deve tenere il valore
        predefinito, perche' il vincolo di non collisione e' costruito su
        quella convenzione (`solve`, blocco `arcs`) e protegge quella
        traiettoria: disegnarne un'altra vorrebbe dire garantire una cosa e
        mostrarne un'altra. Il disegno manuale invece non ha nessun vincolo
        da rispettare -- e' il verificatore a controllare cio' che si vede --
        e li' aspettare alla partenza evita di piazzare il carroponte in
        anticipo sulla vasca dove deve andare, che spesso e' verso il vicino.
    """
    # Tolleranza numerica: il modello CP-SAT lavora con tempi arrotondati al
    # tick (risoluzione 1/time_scale secondi), mentre qui ricalcoliamo i
    # tempi di percorrenza con la formula cinematica "esatta" in virgola
    # mobile -- le due cose possono differire di qualche tick per puro
    # arrotondamento, senza che ci sia un'incoerenza reale nel modello.
    EPS = data.eps_seconds
    segs: list[Segment] = []
    n = len(order)

    for i, k in enumerate(order):
        # I punti di APPROCCIO, non le vasche: con una zona di cambio quota la
        # traslazione col pezzo comincia (o finisce) sul punto di cambio quota,
        # e il tratto fino alla stazione sta dentro la presa o il rilascio.
        x0 = data.approach_position(k)
        x1 = data.approach_position(k + 1)
        t0 = local_pick[k]
        # La mossa si scompone in tre fasi: presa (fermi sopra la vasca k),
        # traslazione orizzontale col pezzo, rilascio (fermi sopra la vasca
        # k+1). Le fasi verticali sono segmenti separati e non gonfiano il
        # tratto 'loaded': altrimenti il profilo cinematico verrebbe disegnato
        # e campionato nel posto sbagliato.
        t_pick_end = t0 + data.pick_time_at(k)
        t_arrive = t_pick_end + data.horizontal_loaded_seconds(k)
        t1 = t_arrive + data.release_time_at(k + 1)
        segs.extend(_segmenti_fasi(data, data.pick_phases(k), "pick", t0, x0, k))
        segs.append(
            Segment("loaded", t_pick_end, t_arrive, x0, x1, data.kin_loaded, move=k)
        )
        segs.extend(
            _segmenti_fasi(
                data, data.release_phases(k + 1), "release", t_arrive, x1, k
            )
        )

        is_last = i == n - 1
        nxt_k = order[0] if is_last else order[i + 1]
        x1_next = data.approach_position(nxt_k)
        travel_e = data.empty_leg_seconds(k + 1, nxt_k)

        # `dep_hi` e `arr_lo` sono i due istanti di CONFINE della zona -- la
        # partenza dall'estremo alto e l'arrivo a quello basso -- e sono legati
        # alle stazioni, non al giro: e' su quelle che il modello costruisce il
        # vincolo di non collisione. Il +T invece riguarda il PERIODO, e sta
        # sull'arco che si richiude su order[0]. Due cose diverse che per un
        # po' hanno condiviso la stessa condizione, perche' il modello
        # obbligava order[0] a coincidere con zone.lo.
        depart_known = k == zone.hi
        arrive_known = nxt_k == zone.lo
        # dove il carroponte passa il tempo che avanza sul rientro a vuoto:
        # fermo dove ha appena consegnato, oppure fermo dove deve andare
        target_pick = local_pick[nxt_k] + (T if nxt_k == order[0] else 0)

        if attese is not None:
            # la scelta del solutore, letta e basta. Vale anche sugli archi di
            # confine: dep_hi e arr_lo dicono la stessa cosa, ma non finiscono
            # nel file salvato, e la traiettoria deve venire uguale anche
            # quando si ricostruisce da quello che il file porta davvero.
            depart_t = t1 + attese.get(k, 0.0)
            arrive_t = depart_t + travel_e
        elif attesa_alla_partenza:
            # Il disegno manuale non deve combaciare con nessun vincolo del
            # modello, quindi qui si sceglie ARCO PER ARCO dove far passare il
            # tempo morto, con la regola di `_aspetta_dove_ha_consegnato`. Gli
            # istanti di confine dep_hi/arr_lo non si guardano: li decide la
            # stessa regola, e chi li ha calcolati (`_assembla`) l'ha usata.
            #
            # La traslazione resta a VELOCITA' PIENA in tutti i casi: cambia
            # quando avviene, non quanto dura.
            if _aspetta_dove_ha_consegnato(zone, k, nxt_k):
                arrive_t = max(target_pick, t1 + travel_e)
                depart_t = arrive_t - travel_e
            else:
                depart_t = t1
                arrive_t = depart_t + travel_e
        elif depart_known and arrive_known:
            depart_t, arrive_t = dep_hi, arr_lo
        elif depart_known:
            depart_t = dep_hi
            arrive_t = depart_t + travel_e
        elif arrive_known:
            arrive_t = arr_lo
            depart_t = arrive_t - travel_e
        else:
            # transizione interna alla zona: nessuna variabile libera
            # dedicata nel modello. Convenzione per la visualizzazione:
            # parte non appena possibile (nessuna attesa "gratuita" prima
            # della partenza; l'eventuale margine e' mostrato come attesa
            # DOPO l'arrivo, prima del prelievo successivo).
            depart_t = t1
            arrive_t = depart_t + travel_e

        if depart_t < t1 - EPS:
            messaggio = (
                f"il carroponte lascia la stazione "
                f"{data.route[k + 1].tank_id} a {depart_t:.1f} s, prima di aver "
                f"finito la consegna della mossa {k} ({t1:.1f} s): "
                f"mancano {t1 - depart_t:.1f} s"
            )
            if incoerenze is None:
                raise ValueError(
                    f"Valori incoerenti: partenza ({depart_t}) precede la consegna "
                    f"({t1}) per la mossa {k}. Controlla i vincoli del modello."
                )
            incoerenze.append(messaggio)
            depart_t = t1  # si disegna comunque, a partire da quando e' libero
        elif depart_t < t1:
            depart_t = t1  # scarto minuscolo di arrotondamento, non un errore reale
        if depart_t > t1 + EPS:
            segs.append(Segment("wait", t1, depart_t, x1, x1, None))
        if abs(x1_next - x1) > 1e-9:
            segs.extend(
                _segmenti_rientro(data, k + 1, nxt_k, depart_t, arrive_t)
            )
        elif arrive_t > depart_t + EPS:
            # stessa stazione: non c'e' nessuno spostamento a vuoto, il
            # carroponte resta fermo. Emettere un 'empty' di lunghezza nulla
            # creerebbe un segmento degenere che, con lo scarto di
            # arrotondamento sui tick, si ordina male rispetto ai vicini e
            # spezza la traiettoria.
            segs.append(Segment("wait", depart_t, arrive_t, x1, x1, None))

        # `target_pick` e' calcolato sopra, prima di scegliere quando partire:
        # con l'attesa alla partenza serve gia' li'. Il +T sta sull'arco che
        # CHIUDE il periodo, cioe' quello che riporta alla prima mossa del
        # giro -- quel prelievo appartiene al ciclo dopo. Metterlo sull'arco
        # che entra in zone.lo funziona solo finche' le due mosse coincidono:
        # vale per il solutore, non per un giro composto a mano che cominci
        # da un'altra mossa.
        if target_pick < arrive_t - EPS:
            if incoerenze is None:
                raise ValueError(
                    f"Valori incoerenti: arrivo ({arrive_t}) e' successivo al prelievo "
                    f"target ({target_pick}) per la mossa {nxt_k}. Controlla i vincoli."
                )
            incoerenze.append(
                f"dalla mossa {k} non si fa in tempo ad arrivare alla mossa "
                f"{nxt_k}: il carroponte sarebbe pronto a {arrive_t:.1f} s ma "
                f"il prelievo e' a {target_pick:.1f} s, {arrive_t - target_pick:.1f} s "
                f"troppo tardi"
            )
        elif target_pick < arrive_t:
            target_pick = (
                arrive_t  # scarto minuscolo di arrotondamento, non un errore reale
            )
        if target_pick > arrive_t + EPS:
            segs.append(Segment("wait", arrive_t, target_pick, x1_next, x1_next, None))

    return segs


# --------------------------------------------------------------------------
# Scelta automatica delle zone
# --------------------------------------------------------------------------
#
# Le zone (quali mosse assegnare a quale carroponte) NON sono decise
# dentro al modello CP-SAT unico: sarebbe possibile (variabili di confine
# fra zone), ma renderebbe il modello sensibilmente piu' complesso e
# rischioso da validare senza un ambiente con OR-Tools a disposizione.
# La scelta qui e' piu' semplice e robusta: si enumerano TUTTE le
# suddivisioni contigue possibili delle mosse in `n_hoists` zone, si
# risolve il modello (gia' testato) `solve()` per ciascuna, e si tiene la
# soluzione con il takt time minore fra quelle fattibili. Un pre-filtro
# economico scarta le suddivisioni palesemente infattibili (una zona il
# cui solo trasporto-a-carico, senza contare alcun trasferimento a vuoto,
# supera gia' da solo il takt time massimo) senza invocare CP-SAT.
#
# Il numero di suddivisioni contigue possibili e' C(n_moves-1, n_hoists-1):
# per problemi di dimensioni realistiche (una manciata di carroponti,
# qualche decina di mosse al massimo) resta gestibile, ma cresce in fretta.
# Vedi il parametro `max_candidates` per un limite di sicurezza.


def _enumerate_contiguous_partitions(n_moves: int, n_hoists: int):
    """Genera tutte le liste di HoistZone che suddividono le mosse
    0..n_moves-1 in n_hoists gruppi contigui e non vuoti, nell'ordine."""
    for cuts in itertools.combinations(range(n_moves - 1), n_hoists - 1):
        bounds = [-1] + list(cuts) + [n_moves - 1]
        yield [HoistZone(bounds[i] + 1, bounds[i + 1]) for i in range(n_hoists)]


def _scarto_prefiltro(
    data: ProblemData, zones: list[HoistZone], carichi: list[float]
) -> Optional[tuple[str, str]]:
    """None se questa suddivisione va provata col solutore, altrimenti
    (motivo, spiegazione) per cui si scarta senza nemmeno costruire il modello.

    I due prefiltri stanno QUI e non dentro solve_auto_zones perche' servono a
    due cose: scartare, e CONTARE quante risoluzioni si faranno prima di
    cominciare (vedi `tentativi_previsti`). Duplicarli vorrebbe dire che il
    conteggio e la ricerca possono dire numeri diversi.

    Sono entrambi economici -- una somma e un confronto fra intervalli -- e
    tolgono di mezzo moltissimo: su una linea di dieci vasche con il takt time
    stretto, 176 suddivisioni diventano 10.
    """
    # 1) una zona il cui solo trasporto-a-carico (senza nemmeno contare i
    # trasferimenti a vuoto) supera gia' il takt time massimo e' certamente
    # infattibile, qualunque sia l'ordine di visita.
    for z in zones:
        if sum(carichi[k] for k in range(z.lo, z.hi + 1)) > data.takt_max:
            return ("carico", f"la zona [{z.lo}-{z.hi}] non ci sta nel takt time")
    # 2) geometria patologica (vasche non ordinate lungo la rotaia, zone che si
    # scavalcano). Scartarla qui, invece di lasciar fallire solve(), fa si' che
    # la scelta automatica trovi da sola una suddivisione valida quando esiste.
    problemi = zone_layout_conflicts(data, zones)
    if problemi:
        return ("geometria", problemi[0])
    return None


def tentativi_previsti(data: ProblemData, n_hoists: int) -> int:
    """Quante risoluzioni CP-SAT servirebbero per provare tutte le suddivisioni
    in `n_hoists` zone.

    E' noto PRIMA di risolvere, e costa millisecondi: il numero di suddivisioni
    e' combinatoria pura, e i due prefiltri sono deterministici. Serve a dare
    un avanzamento vero invece di una barra che oscilla.

    Quello che NON si sa in anticipo e' a quale numero di carroponti la ricerca
    si fermera' -- e' proprio l'informazione che si sta cercando -- ne' quanto
    durera' ciascuna risoluzione, che dipende da quanto e' difficile
    l'istanza."""
    if n_hoists < 1 or n_hoists > data.n_moves:
        return 0
    carichi = [data.loaded_leg_seconds(k) for k in range(data.n_moves)]
    return sum(
        1
        for zones in _enumerate_contiguous_partitions(data.n_moves, n_hoists)
        if _scarto_prefiltro(data, zones, carichi) is None
    )


def solve_auto_zones(
    data: ProblemData,
    n_hoists: int,
    time_limit_per_candidate: float = 8.0,
    max_candidates: int = 5000,
    log_progress: bool = False,
    su_tentativo=None,
) -> tuple[Solution, Optional[list[HoistZone]]]:
    """Prova automaticamente tutte le suddivisioni contigue delle mosse in
    `n_hoists` zone (una per carroponte) e restituisce la soluzione con il
    takt time minore fra quelle trovate fattibili, insieme alle zone che
    l'hanno generata.

    `data.zones` puo' essere None (verra' ignorato/sovrascritto per ogni
    tentativo). Restituisce (Solution, zones) -- se nessuna suddivisione e'
    fattibile, Solution.status sara' "INFEASIBLE" e zones sara' None.

    `su_tentativo(n_hoists, indice, totale)` viene chiamata PRIMA di ogni
    risoluzione, con l'indice contato da 1 e il totale gia' al netto dei
    prefiltri. Serve a chi mostra un avanzamento; gira nel thread del
    chiamante, quindi non deve toccare widget.
    """
    n_moves = data.n_moves
    if n_hoists < 1:
        raise ValueError("n_hoists deve essere >= 1")
    if n_hoists > n_moves:
        raise ValueError(
            f"n_hoists ({n_hoists}) non puo' superare il numero di mosse ({n_moves}): "
            f"ogni carroponte deve avere almeno una mossa."
        )

    travel_loaded_seconds = [data.loaded_leg_seconds(k) for k in range(n_moves)]

    best_solution: Optional[Solution] = None
    best_zones: Optional[list[HoistZone]] = None
    n_tried = 0
    n_skipped = 0
    n_skipped_layout = 0
    esempio_layout: Optional[str] = None

    # Prima si applicano i prefiltri a TUTTE le suddivisioni, poi si risolve.
    # Farlo in due tempi costa una lista di poche decine di elementi e in
    # cambio da' il totale esatto delle risoluzioni da fare: senza, un
    # avanzamento potrebbe solo dire quante ne sono state fatte, non quante ne
    # mancano.
    da_provare: list[list[HoistZone]] = []
    for zones in _enumerate_contiguous_partitions(n_moves, n_hoists):
        scarto = _scarto_prefiltro(data, zones, travel_loaded_seconds)
        if scarto is None:
            da_provare.append(zones)
            continue
        motivo, spiegazione = scarto
        if motivo == "carico":
            n_skipped += 1
            continue
        n_skipped_layout += 1
        if esempio_layout is None:
            esempio_layout = spiegazione
        if log_progress:
            zone_str = ", ".join(f"[{z.lo}-{z.hi}]" for z in zones)
            print(f"  zone {zone_str}: scartata (geometria irrappresentabile)")

    # Il tetto si applica a quello che si RISOLVE, non alle combinazioni sulla
    # carta. La differenza non e' accademica: su una linea di diciassette mosse
    # con quattro carroponti le combinazioni sono 560 e le suddivisioni che
    # arrivano al solutore 336. Contando le prime, la ricerca veniva saltata
    # per intero -- e con lei tutti i numeri di carroponti superiori, perche'
    # crescono. Il risultato era che una linea risolvibile con quattro
    # carroponti veniva dichiarata impossibile senza che nessuno ci avesse
    # provato.
    #
    # Il valore predefinito e' alto (5000) di proposito: saltare una ricerca e'
    # un danno molto peggiore di farla durare. Una ricerca lunga si vede -- la
    # barra dice a che tentativo e' e quanto manca -- e si puo' interrompere;
    # una saltata produce un "nessuna soluzione" che sembra un verdetto sulla
    # linea e non lo e'. Quello che resta e' una rete contro il caso
    # veramente fuori scala, dove aspettare non avrebbe comunque senso.
    if len(da_provare) > max_candidates:
        raise ValueError(
            f"Con {n_hoists} carroponti restano {len(da_provare)} suddivisioni "
            f"da provare (su {math.comb(n_moves - 1, n_hoists - 1)} possibili) "
            f"e il limite e' {max_candidates}. Alza max_candidates se accetti "
            f"di aspettare -- al peggio {len(da_provare)} risoluzioni -- "
            f"oppure indica tu le zone nel foglio Zone e usa solve()."
        )

    # Quante volte ciascun esito. Serve a distinguere due situazioni che
    # 'nessuna soluzione' confonde: INFEASIBLE e' una DIMOSTRAZIONE che con
    # quelle zone non si puo' fare, e allora va cambiata la linea; UNKNOWN
    # vuol dire solo che il tempo e' scaduto, e allora basta darne di piu'.
    # Sono due azioni opposte, e senza questo conteggio l'utente non ha modo
    # di sapere quale delle due gli tocca.
    per_stato: dict[str, int] = {}

    for indice, zones in enumerate(da_provare, start=1):
        if su_tentativo is not None:
            su_tentativo(n_hoists, indice, len(da_provare))
        candidate_data = dataclasses.replace(data, zones=zones)
        n_tried += 1
        sol = solve(candidate_data, time_limit_s=time_limit_per_candidate)
        per_stato[sol.status] = per_stato.get(sol.status, 0) + 1
        if log_progress:
            zone_str = ", ".join(f"[{z.lo}-{z.hi}]" for z in zones)
            info = f"T={sol.T:.2f}s" if sol.T is not None else sol.status
            print(f"  zone {zone_str}: {info}")
        if sol.status in ("OPTIMAL", "FEASIBLE") and sol.T is not None:
            if best_solution is None or sol.T < best_solution.T:
                best_solution = sol
                best_zones = zones

    conti = {
        "n_tried": n_tried,
        "n_skipped": n_skipped,
        "n_skipped_layout": n_skipped_layout,
        "layout_example": esempio_layout,
        "per_stato": per_stato,
        # la suddivisione col carico piu' equilibrato: e' quella su cui ha
        # senso indagare quando nessuna funziona (vedi `diagnosi_zone`)
        "candidata_tipica": _piu_equilibrata(da_provare, travel_loaded_seconds),
    }

    if best_solution is None:
        return Solution(status="INFEASIBLE", T=None, raw=conti), None

    best_solution.raw.update(conti)
    best_solution.raw["zones"] = best_zones
    return best_solution, best_zones


def _piu_equilibrata(
    candidate: list[list[HoistZone]], carichi: list[float]
) -> Optional[list[HoistZone]]:
    """La suddivisione in cui il carico e' distribuito meglio fra i carroponti.

    Quando NESSUNA suddivisione funziona bisogna sceglierne una su cui
    indagare, e questa e' la meno arbitraria: se il problema fosse il carico,
    sarebbe l'ultima a soffrirne, quindi quello che la blocca blocca anche
    tutte le altre."""
    if not candidate:
        return None
    return min(
        candidate,
        key=lambda zone: max(
            sum(carichi[k] for k in range(z.lo, z.hi + 1)) for z in zone
        ),
    )


# --------------------------------------------------------------------------
# Perche' non si riesce
# --------------------------------------------------------------------------
#
# "Nessuna soluzione" e' la risposta meno utile che un programma possa dare:
# non dice se manca un secondo o un carroponte. Il solutore non lo dice perche'
# non lo sa -- dimostra che i vincoli insieme sono incompatibili, non quale sia
# di troppo.
#
# Lo si scopre RILASSANDO un vincolo per volta e riprovando: se togliendo il
# limite sui tempi di processo la linea diventa risolvibile, sono quelli a
# bloccare; se serve toglierne due, il problema e' piu' profondo. E' un metodo
# grezzo e costa qualche risoluzione, ma risponde alla domanda giusta -- dove
# metto le mani -- invece di elencare tutto quello che si potrebbe cambiare.


def _prova(data, zones, limite: float) -> tuple[str, Optional[float]]:
    """Esito di una variante rilassata: ("si", T) | ("no", None) | ("boh", None).

    LA DISTINZIONE FRA "no" E "boh" E' TUTTA LA DIFFERENZA. "no" e' INFEASIBLE,
    cioe' una dimostrazione: nemmeno rilassando quel vincolo si riesce, quindi
    non e' lui a bloccare. "boh" e' UNKNOWN, cioe' tempo scaduto: non si sa
    niente. Confonderli fa dire alla diagnosi che un vincolo e' innocente
    quando invece non e' stato esaminato -- ed e' il modo piu' efficace di
    mandare qualcuno a cercare nel posto sbagliato.

    Non e' un rischio teorico: allargare la banda del takt time INGRANDISCE il
    modello (le traslazioni da generare vanno come orizzonte/takt minimo), e
    proprio la prova piu' utile e' quella che scade piu' facilmente.

    Una variante puo' anche non passare le validazioni di ProblemData: li' si
    sta esplorando, non costruendo una linea, quindi vale come "no"."""
    try:
        sol = solve(dataclasses.replace(data, zones=zones), time_limit_s=limite)
    except ValueError:
        return ("no", None)
    if sol.status in ("OPTIMAL", "FEASIBLE") and sol.T is not None:
        return ("si", sol.T)
    return ("no", None) if sol.status == "INFEASIBLE" else ("boh", None)


def diagnosi_zone(
    data: ProblemData,
    zones: list[HoistZone],
    time_limit_s: float = 15.0,
    dettaglio_vasche: bool = True,
) -> list[str]:
    """Perche' questa suddivisione non e' risolvibile: righe gia' leggibili.

    Si rilassa un vincolo per volta e si guarda quale rilassamento fa passare
    la linea. Quando il rilassamento e' una GRANDEZZA -- il takt time, un tempo
    massimo di processo -- non ci si ferma al si'/no: si cerca per bisezione il
    valore minimo che basta, cosi' la risposta e' 'mancano 12 s su ED' invece
    di 'i tempi di processo sono stretti'.

    Costa una manciata di risoluzioni piu' una per vasca se
    `dettaglio_vasche`. Non e' un'analisi esatta di infattibilita': se a
    bloccare sono DUE vincoli insieme, nessun rilassamento singolo basta e la
    diagnosi lo dice -- che e' comunque un'informazione."""
    fuori: list[str] = []
    incerti: list[str] = []
    intermedie = list(range(1, data.n_stations - 1))

    # -- 0) c'e' davvero qualcosa da diagnosticare? ------------------------
    #
    # Ogni prova qui sotto rilassa un vincolo e guarda se la linea passa. Su
    # una suddivisione che passava GIA', tutte le prove riescono, e la prima
    # verrebbe scambiata per la causa. Chiedersi prima se il paziente sta male
    # costa una risoluzione ed evita una diagnosi inventata.
    esito, t = _prova(data, zones, time_limit_s)
    if esito == "si":
        return [
            f"Questa suddivisione FUNZIONA (T = {t:.0f} s): non c'e' niente da "
            f"diagnosticare. Se la ricerca automatica non l'ha trovata, non e' "
            f"perche' la linea non regge -- guarda il registro dei tentativi."
        ]
    if esito == "boh":
        return [
            "Il solutore non ha concluso nel tempo concesso su questa "
            "suddivisione: non e' stato dimostrato che sia impossibile, e "
            "quindi non c'e' ancora niente da spiegare. Rilancia con un "
            "limite di tempo piu' alto."
        ]

    # -- 1) il takt time --------------------------------------------------
    #
    # Non si allarga la banda: la si SPOSTA, tenendola stretta. Allargarla
    # ingrandisce il modello -- il numero di traslazioni da generare va come
    # orizzonte diviso takt minimo -- e la prova scade prima di dire qualcosa.
    # Una banda stretta piazzata piu' in alto costa quanto l'originale e
    # risponde alla stessa domanda: con un ciclo piu' lungo, si riesce?
    precedente = data.takt_max  # l'ultimo valore per cui si e' visto che NON va
    for fattore in (1.25, 1.5, 2.0, 3.0):
        basso = data.takt_max * fattore
        esito, t = _prova(
            dataclasses.replace(data, takt_min=basso, takt_max=basso * 1.1),
            zones, time_limit_s,
        )
        if esito == "si":
            # Si e' trovato un ciclo che basta, non il piu' corto che basti:
            # il minimo sta fra l'ultimo scalino fallito e questo. Dirlo come
            # intervallo e' l'unica forma onesta -- annunciare `t` come "il
            # minimo" farebbe alzare takt_max_s piu' del necessario.
            fuori.append(
                f"IL TAKT TIME E' TROPPO STRETTO: con un ciclo di {t:.0f} s "
                f"queste zone funzionano, mentre il massimo dichiarato e' "
                f"{data.takt_max:.0f} s. Il minimo che basta sta fra "
                f"{precedente:.0f} e {t:.0f} s, cioe' servono da "
                f"{max(0.0, precedente - data.takt_max):.0f} a "
                f"{t - data.takt_max:.0f} s in piu'. Alza takt_max_s, oppure "
                f"aggiungi un carroponte per accorciare i giri."
            )
            return fuori
        if esito == "boh":
            incerti.append(f"takt time attorno a {basso:.0f} s")
        else:
            precedente = basso * 1.1

    # Anche il limite INFERIORE puo' bloccare, e sorprende: un ciclo piu' lungo
    # tiene i pezzi in vasca piu' a lungo, e se il processo non lo tollera la
    # linea non sta in piedi. Si prova a dimezzarlo.
    esito, t = _prova(
        dataclasses.replace(
            data,
            takt_min=max(1.0, data.takt_min / 2),
            takt_max=data.takt_min,
        ),
        zones, time_limit_s,
    )
    if esito == "si":
        fuori.append(
            f"IL TAKT TIME MINIMO E' TROPPO ALTO: con un ciclo di {t:.0f} s -- "
            f"piu' corto del minimo dichiarato ({data.takt_min:.0f} s) -- la "
            f"linea si risolve. Un ciclo lungo tiene i pezzi in vasca oltre il "
            f"tempo di processo: abbassa takt_min_s."
        )
        return fuori
    if esito == "boh":
        incerti.append(f"takt time sotto {data.takt_min:.0f} s")

    # -- 2) la non collisione fra carroponti ------------------------------
    senza_urti = dataclasses.replace(
        data, hoist_extent_pos=0.0, hoist_extent_neg=0.0, safety_distance=0.0
    )
    esito, _t = _prova(senza_urti, zones, time_limit_s)
    if esito == "boh":
        incerti.append("non collisione")
    if esito == "si":
        confini = [
            f"{data.route[zones[h].hi + 1].tank_id} "
            f"(fra il carroponte {h + 1} e il {h + 2})"
            for h in range(len(zones) - 1)
        ]
        fuori.append(
            f"E' LA NON COLLISIONE: facendo passare i carroponti uno "
            f"attraverso l'altro la linea si risolve, quindi a bloccare e' lo "
            f"spazio che devono lasciarsi. Servono "
            f"{data.hoist_length + data.safety_distance:.0f} mm fra due ganci "
            f"(ingombro {data.hoist_extent_neg:.0f}+{data.hoist_extent_pos:.0f} "
            f"+ sicurezza {data.safety_distance:.0f}). I confini in gioco: "
            + "; ".join(confini)
            + ". Sposta un confine di zona su una vasca piu' isolata, riduci "
            "distanza_sicurezza_mm, oppure infittisci "
            "passo_controllo_distanza_mm (il calcolo sta dal lato sicuro fra "
            "una verifica e l'altra)."
        )
        return fuori

    # -- 3) i tempi massimi di processo -----------------------------------
    largo = dataclasses.replace(
        data,
        route=[
            dataclasses.replace(s, dwell_max=s.dwell_max * 10 + 1000.0)
            if 0 < i < data.n_stations - 1
            else s
            for i, s in enumerate(data.route)
        ],
    )
    esito, _t = _prova(largo, zones, time_limit_s)
    if esito == "boh":
        incerti.append("tempi massimi di processo")
    if esito == "si":
        fuori.append(
            "SONO I TEMPI MASSIMI DI PROCESSO: allargandoli la linea si "
            "risolve. Il pezzo dovrebbe restare in vasca piu' di quanto la "
            "ricetta consenta."
        )
        if dettaglio_vasche:
            fuori.extend(
                _vasche_che_bloccano(data, zones, time_limit_s, intermedie)
            )
        return fuori

    # -- 4) la capienza delle vasche --------------------------------------
    capienti = dataclasses.replace(
        data,
        tanks={
            tid: dataclasses.replace(t, capacity=t.capacity + 2)
            for tid, t in data.tanks.items()
        },
    )
    esito, _t = _prova(capienti, zones, time_limit_s)
    if esito == "boh":
        incerti.append("capienza delle vasche")
    if esito == "si":
        fuori.append(
            "E' LA CAPIENZA DELLE VASCHE: dando due posti in piu' a ciascuna "
            "la linea si risolve. Guarda il foglio Vasche, colonna 'posti': "
            "sono i pezzi che ci stanno dentro contemporaneamente, e su un "
            "bagno lungo ne servono piu' di uno."
        )
        return fuori

    # -- niente di tutto questo -------------------------------------------
    #
    # Qui bisogna stare attenti a cosa si afferma. Se tutte le prove hanno
    # DIMOSTRATO l'infattibilita', si puo' dire che nessun vincolo da solo
    # basta. Se qualcuna e' scaduta, non si sa: dirlo comunque manderebbe a
    # cercare altrove un problema che magari era proprio li'.
    if incerti:
        fuori.append(
            "NON SI RIESCE A DIRLO nel tempo concesso. Queste prove sono "
            "scadute senza rispondere: "
            + ", ".join(incerti)
            + ". Non vuol dire che quei vincoli siano innocenti -- vuol dire "
            "che non sono stati esaminati. Rilancia la diagnosi con un limite "
            "di tempo piu' alto."
        )
        return fuori
    fuori.append(
        "Nessun vincolo preso DA SOLO spiega il rifiuto: e' stato DIMOSTRATO "
        "che allargando il takt time, togliendo le collisioni, allungando i "
        "tempi di processo o aggiungendo posti in vasca questa suddivisione "
        "resta irrisolvibile. A bloccare sono piu' vincoli insieme, e la "
        "strada e' aggiungere un carroponte -- oppure comporre il ciclogramma "
        "a mano e leggere cosa segnala il verificatore, che indica il punto "
        "esatto invece della causa."
    )
    return fuori


def _vasche_che_bloccano(
    data: ProblemData,
    zones: list[HoistZone],
    time_limit_s: float,
    intermedie: list[int],
) -> list[str]:
    """Quali vasche, da sole, sbloccano la linea se si allunga il loro tempo
    massimo -- e di quanto.

    E' la domanda che si pone chi ha la ricetta davanti: non 'i tempi sono
    stretti' ma 'quale allungo, e di quanto'. Per ogni vasca si allarga solo
    lei; se basta, si cerca per bisezione il minimo che serve."""
    fuori: list[str] = []
    for i in intermedie:
        spec = data.route[i]

        def con(valore: float):
            return dataclasses.replace(
                data,
                route=[
                    dataclasses.replace(s, dwell_max=valore) if j == i else s
                    for j, s in enumerate(data.route)
                ],
            )

        molto = spec.dwell_max * 10 + 1000.0
        if _prova(con(molto), zones, time_limit_s)[0] != "si":
            continue  # questa vasca da sola non basta a sbloccare
        # bisezione sul valore minimo che serve: otto passi bastano a
        # scendere sotto l'1% dell'intervallo, ed e' molto piu' preciso di
        # quanto serva a chi deve decidere se ritoccare una ricetta.
        # Un esito incerto si tratta come un no: cosi' l'intervallo si
        # stringe dal lato prudente e il valore riportato non promette meno
        # di quanto serva davvero.
        basso, alto = spec.dwell_max, molto
        for _ in range(8):
            mezzo = (basso + alto) / 2
            if _prova(con(mezzo), zones, time_limit_s)[0] == "si":
                alto = mezzo
            else:
                basso = mezzo
        fuori.append(
            f"  - basta la vasca '{spec.tank_id}' (stazione {i}): portando il "
            f"suo tempo massimo da {spec.dwell_max:.0f} a circa {alto:.0f} s "
            f"(+{alto - spec.dwell_max:.0f}) la linea si risolve."
        )
    if not fuori:
        fuori.append(
            "  - nessuna vasca da sola basta: vanno allargate piu' ricette "
            "insieme, oppure serve un carroponte in piu'."
        )
    return fuori


# --------------------------------------------------------------------------
# Scelta automatica ANCHE del numero di carroponti
# --------------------------------------------------------------------------
#
# Piu' carroponti possono solo ampliare (mai restringere) cio' che e'
# fattibile: se una linea ce la fa con N carroponti, aggiungerne un altro
# (spezzando ulteriormente le zone) non puo' peggiorare le cose. Percio' la
# ricerca del numero minimo di carroponti e' un semplice sweep crescente
# N=1,2,3,... che si ferma al primo N per cui `solve_auto_zones` trova una
# suddivisione in zone fattibile entro la tolleranza di takt time data.


def solve_auto_hoists(
    data: ProblemData,
    max_hoists: int = 6,
    min_hoists: int = 1,
    time_limit_per_candidate: float = 8.0,
    max_candidates_per_hoist_count: int = 5000,
    log_progress: bool = False,
    su_tentativo=None,
) -> tuple[Solution, Optional[list[HoistZone]], Optional[int]]:
    """Cerca automaticamente sia il numero minimo di carroponti necessario
    sia le zone di ciascuno: prova n_hoists = min_hoists, min_hoists+1, ...,
    max_hoists in ordine crescente e si ferma al primo valore per cui
    esiste una suddivisione in zone fattibile entro la tolleranza di takt
    time data (`data.takt_min`/`data.takt_max`).

    Restituisce (Solution, zones, n_hoists). Se nessun numero di
    carroponti fino a max_hoists risulta fattibile, Solution.status sara'
    "INFEASIBLE" e zones/n_hoists saranno None -- in tal caso prova ad
    aumentare max_hoists o la tolleranza sul takt time.

    `su_tentativo(n_hoists, indice, totale)` viene passata a solve_auto_zones:
    vedi li'. Il totale riguarda il numero di carroponti in corso, non l'intera
    ricerca -- quanti carroponti serviranno non si sa finche' non si trova.
    """
    n_moves = data.n_moves
    max_hoists = min(max_hoists, n_moves)
    if min_hoists < 1:
        raise ValueError("min_hoists deve essere >= 1")
    if min_hoists > max_hoists:
        raise ValueError(
            f"min_hoists ({min_hoists}) supera max_hoists effettivo ({max_hoists}, "
            f"limitato al numero di mosse)."
        )

    sweep = []
    for n_hoists in range(min_hoists, max_hoists + 1):
        if log_progress:
            print(f"--- Provo con {n_hoists} carroponte/i ---")
        try:
            sol, zones = solve_auto_zones(
                data,
                n_hoists,
                time_limit_per_candidate=time_limit_per_candidate,
                max_candidates=max_candidates_per_hoist_count,
                log_progress=log_progress,
                su_tentativo=su_tentativo,
            )
        except ValueError as e:
            # troppe suddivisioni possibili per questo n_hoists: lo segnalo
            # e provo comunque il numero di carroponti successivo, invece
            # di far fallire l'intera ricerca.
            sweep.append({"n_hoists": n_hoists, "status": "SKIPPED", "error": str(e)})
            if log_progress:
                print(f"  saltato: {e}")
            continue

        voce = {
            "n_hoists": n_hoists,
            "status": sol.status,
            "T": sol.T,
            # quante suddivisioni sono state davvero risolte e con che esito,
            # piu' una su cui indagare se non si trova niente: e' cio' che
            # permette di spiegare un fallimento invece di annunciarlo
            "n_tried": sol.raw.get("n_tried", 0),
            "n_skipped": sol.raw.get("n_skipped", 0),
            "per_stato": sol.raw.get("per_stato", {}),
            "candidata_tipica": sol.raw.get("candidata_tipica"),
        }
        n_layout = sol.raw.get("n_skipped_layout", 0)
        if n_layout:
            voce["n_skipped_layout"] = n_layout
            voce["layout_example"] = sol.raw.get("layout_example")
            if log_progress and sol.status not in ("OPTIMAL", "FEASIBLE"):
                print(
                    f"  {n_layout} suddivisioni scartate perche' il modello non "
                    f"sa garantire la distanza di sicurezza con questa "
                    f"geometria. Esempio: {sol.raw.get('layout_example')}"
                )
        sweep.append(voce)
        if sol.status in ("OPTIMAL", "FEASIBLE"):
            sol.raw["hoist_sweep"] = sweep
            sol.raw["n_hoists"] = n_hoists
            return sol, zones, n_hoists

    return Solution(status="INFEASIBLE", T=None, raw={"hoist_sweep": sweep}), None, None


# --------------------------------------------------------------------------
# Estensioni possibili -- non implementate in questo file
# --------------------------------------------------------------------------
#
# 1. Assegnazione non contigua fra zone (un carroponte che sconfina
#    occasionalmente nel territorio del vicino): richiederebbe estendere
#    il circuito e la logica di confine a insiemi di mosse non fissi.
#
# 2. Piu' ricette (prodotti diversi che seguono percorsi diversi fra le
#    vasche): si generalizza duplicando la catena actual_time per ciascuna
#    ricetta, con un takt time complessivo che tiene conto del mix
#    produttivo, e condividendo le vasche/i carroponti fra le ricette con
#    ulteriori vincoli di non-sovrapposizione.
#
# 3. Collisione modellata in modo meno conservativo: invece di riservare
#    l'intera finestra [arrivo, partenza] a una stazione di confine, usare
#    il profilo di posizione reale (position_profile in kinematics.py) per
#    calcolare l'intervallo temporale esatto in cui il carroponte e'
#    entro `safety_distance` dal confine, invece dell'intera sosta.
#
# 4. Vasche non ordinate lungo la rotaia (percorso che torna indietro nello
#    spazio): il vincolo di non collisione assume che le zone adiacenti
#    stiano su lati opposti del proprio confine. Toglierlo richiederebbe di
#    confrontare le posizioni di TUTTE le coppie di carroponti su tutto il
#    percorso, non solo attorno ai confini.
#
# 5. Posizione di parcheggio scelta dal solver: oggi, per convenzione, un
#    carroponte che ha consegnato riparte subito e attende alla stazione
#    della mossa successiva. Poterlo far attendere altrove darebbe piu'
#    liberta' per allontanarsi dal vicino, a parita' di tutto il resto.
#
# GIA' IMPLEMENTATI (erano punti di questo elenco):
# - tempo di presa e rilascio del pezzo (`pick_time`/`release_time`): NON si
#   somma allo spostamento a vuoto, sarebbe doppio conteggio -- vedi il
#   commento su `empty_leg_seconds`;
# - capienza delle vasche (`StationSpec.capacity`);
# - collisione basata sulla posizione reale nel tempo invece che sulla sola
#   finestra di occupazione della stazione di confine;
# - verifica indipendente della soluzione (verify.py).
