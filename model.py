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
        if serve_cinematica and (
            self.kin_lift_empty is None or self.kin_lift_loaded is None
        ):
            raise ValueError(
                "almeno una vasca ha una corsa verticale (lift_height) ma "
                "mancano le cinematiche di sollevamento: servono sia "
                "kin_lift_empty sia kin_lift_loaded per calcolare i tempi di "
                "presa e rilascio."
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
            occ_min = self.slot_occupancy_seconds(s_idx, spec.dwell_min)
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
        return abs(self.station_position(k + 1) - self.station_position(k))

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
        la loro somma: cosi' i due usi non possono divergere."""
        h = self.lift_height_at(station_idx)
        return [
            LiftPhase(
                "discesa del gancio",
                self._lift_seconds(h, self.kin_lift_empty),
                0.0,
                -h,
                self.kin_lift_empty,
                False,
            ),
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
        """Il RILASCIO scomposto nei suoi movimenti verticali, in ordine."""
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
            LiftPhase(
                "risalita del gancio",
                self._lift_seconds(h, self.kin_lift_empty),
                -h,
                0.0,
                self.kin_lift_empty,
                False,
            ),
        ]

    def pick_time_at(self, station_idx: int) -> float:
        """Tempo di PRESA [s] alla stazione data: discesa del gancio scarico,
        aggancio, risalita col telaio, sgocciolamento sopra la vasca."""
        return sum(f.duration for f in self.pick_phases(station_idx))

    def release_time_at(self, station_idx: int) -> float:
        """Tempo di RILASCIO [s] alla stazione data: discesa col telaio,
        sgancio, risalita del gancio scarico.

        Nota: a parita' di corsa, presa e rilascio percorrono le stesse due
        tratte (una a vuoto e una a carico) in ordine invertito, quindi
        differiscono solo per i tempi morti -- aggancio e sgocciolamento da una
        parte, sgancio dall'altra."""
        return sum(f.duration for f in self.release_phases(station_idx))

    def slot_occupancy_seconds(self, station_idx: int, dwell: float) -> float:
        """Per quanto tempo [s] un pezzo tiene occupato un POSTO nella vasca
        `station_idx`, dato il suo tempo in bagno `dwell`.

        Non coincide col dwell: il telaio ingombra il posto dall'inizio
        dell'immersione fino alla fine dell'emersione, quindi va aggiunto il
        rilascio in entrata e la presa in uscita. E' questa la grandezza da
        confrontare con `capacity * T`, non il solo tempo in bagno."""
        return (
            self.release_time_at(station_idx) + dwell + self.pick_time_at(station_idx)
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

    def empty_leg_seconds(self, pos_a: float, pos_b: float) -> float:
        """Durata [s] di uno spostamento a vuoto fra due posizioni.

        NON comprende alcun tempo verticale: il gancio scarico e' gia' in alto
        (lo ha portato su `release_time`) e ridiscendera' dentro `pick_time`
        della mossa successiva. Sommarlo anche qui sarebbe doppio conteggio."""
        return _travel_time_seconds(abs(pos_b - pos_a), self.kin_empty)


# --------------------------------------------------------------------------
# Risultato
# --------------------------------------------------------------------------


@dataclass
class Segment:
    """Un tratto della traiettoria di un carroponte entro un ciclo."""

    kind: str  # 'pick' | 'loaded' | 'release' | 'empty' | 'wait'
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

    def travel_empty_ticks(pos_a: float, pos_b: float) -> int:
        return T_(data.empty_leg_seconds(pos_a, pos_b))

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
        dwell_min = T_(spec.dwell_min)
        dwell_max = T_(spec.dwell_max)
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
            t_ret = travel_empty_ticks(
                data.station_position(hi_h + 1), data.station_position(lo_h)
            )
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

        # vincolo di tempo per ciascun arco possibile: se selezionato,
        # bisogna riuscire ad arrivare in tempo alla mossa successiva
        # (con +T solo se si sta richiudendo il periodo su lo_h).
        for (k1, k2), lit in arc_lits.items():
            t_emp = travel_empty_ticks(
                data.station_position(k1 + 1), data.station_position(k2)
            )
            bound = local_pick[k2] + (Tv if k2 == lo_h else 0)
            model.Add(finish[k1] + t_emp <= bound).OnlyEnforceIf(lit)

        # -- variabili libere di confine (per traiettoria e non-collisione) --
        dep_hi = model.NewIntVar(0, DEP_MAX, f"dep_hi_{h}")
        model.Add(dep_hi >= finish[hi_h])
        for k2 in moves:
            if k2 == hi_h:
                continue
            t_emp = travel_empty_ticks(
                data.station_position(hi_h + 1), data.station_position(k2)
            )
            bound = local_pick[k2] + (Tv if k2 == lo_h else 0)
            model.Add(dep_hi + t_emp <= bound).OnlyEnforceIf(arc_lits[(hi_h, k2)])

        arr_lo = model.NewIntVar(0, DEP_MAX, f"arr_lo_{h}")
        for k1 in moves:
            if k1 == lo_h:
                continue
            t_emp = travel_empty_ticks(
                data.station_position(k1 + 1), data.station_position(lo_h)
            )
            model.Add(arr_lo >= finish[k1] + t_emp).OnlyEnforceIf(arc_lits[(k1, lo_h)])
        model.Add(arr_lo <= local_pick[lo_h] + Tv)

        # se l'arco hi_h -> lo_h e' selezionato (rientro diretto, senza
        # visitare altre mosse nel mezzo), dep_hi e arr_lo descrivono lo
        # STESSO spostamento a vuoto: vanno legati fra loro esattamente.
        if (hi_h, lo_h) in arc_lits:
            t_emp_direct = travel_empty_ticks(
                data.station_position(hi_h + 1), data.station_position(lo_h)
            )
            model.Add(arr_lo == dep_hi + t_emp_direct).OnlyEnforceIf(
                arc_lits[(hi_h, lo_h)]
            )

        # Istanti di partenza/arrivo di ciascun trasferimento a vuoto, usati
        # dal vincolo di non collisione. Le convenzioni devono essere IDENTICHE
        # a quelle di _build_zone_trajectory, altrimenti il vincolo
        # proteggerebbe una traiettoria diversa da quella poi disegnata.
        arcs = []
        for (k1, k2), lit in arc_lits.items():
            t_emp = travel_empty_ticks(
                data.station_position(k1 + 1), data.station_position(k2)
            )
            if k1 == hi_h:
                depart = dep_hi
            elif k2 == lo_h:
                depart = arr_lo - t_emp
            else:
                depart = finish[k1]  # convenzione: riparte appena consegnato
            arrive = arr_lo if k2 == lo_h else depart + t_emp
            arcs.append(
                dict(
                    k1=k1,
                    k2=k2,
                    lit=lit,
                    span_start=finish[k1],
                    depart=depart,
                    arrive=arrive,
                    span_end=local_pick[k2] + (Tv if k2 == lo_h else 0),
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
                arcs=arcs,
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

        La traiettoria di un periodo e' partizionata in blocchi: una mossa
        (sosta di presa, traslazione a carico, sosta di rilascio) e un
        trasferimento a vuoto (sosta, traslazione, sosta). Dentro un blocco il
        carroponte va da una stazione u a una stazione v senza inversioni,
        quindi la distanza da b e' monotona fra d(u) e d(v)."""
        lp, fin = zd["local_pick"], zd["finish"]
        out = []

        def dist(station_idx: int) -> float:
            return abs(data.station_position(station_idx) - x_b)

        def blocco(u, v, span_start, leave_u, reach_v, span_end, lit):
            du, dv = dist(u), dist(v)
            if du < radius and dv < radius:
                # tutto il blocco e' dentro la fascia
                out.append((span_start, span_end, lit))
            elif du < radius:
                # si esce dalla fascia durante la traslazione
                out.append((span_start, leave_u + escape_ticks(radius - du), lit))
            elif dv < radius:
                # si entra nella fascia durante la traslazione
                out.append((reach_v - escape_ticks(radius - dv), span_end, lit))
            # se entrambe le stazioni sono fuori, il tratto non entra mai
            # nella fascia (la distanza da b e' monotona lungo il blocco)

        for k in zd["moves"]:
            blocco(
                u=k,
                v=k + 1,
                span_start=lp[k],
                leave_u=lp[k] + T_(data.pick_time_at(k)),
                reach_v=fin[k] - T_(data.release_time_at(k + 1)),
                span_end=fin[k],
                lit=None,
            )
        for arc in zd["arcs"]:
            blocco(
                u=arc["k1"] + 1,
                v=arc["k2"],
                span_start=arc["span_start"],
                leave_u=arc["depart"],
                reach_v=arc["arrive"],
                span_end=arc["span_end"],
                lit=arc["lit"],
            )
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
            order = [z.lo]
            cur = z.lo
            while True:
                cur = nxt[cur]
                if cur == z.lo:
                    break
                order.append(cur)

        segs = _build_zone_trajectory(
            data, z, order, lp_val, dep_hi_val, arr_lo_val, T_seconds
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
    - dal confine alto si riparte appena consegnato, e l'eventuale margine
      diventa attesa all'arrivo.

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
        local_pick = {k: actual_time[k] % T for k in chiavi}
        return _assembla(data, T, local_pick, actual_time, status, incoerenze)

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
        minimo = arrivo + data.route[k].dwell_min
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

    return _assembla(data, T, local_pick, actual_time, status, incoerenze)


def _assembla(
    data: ProblemData,
    T: float,
    local_pick: dict[int, float],
    actual_time: list[float],
    status: str,
    incoerenze: Optional[list[str]],
) -> Solution:
    """Da fasi e tempi assoluti alle traiettorie di ciascun carroponte."""
    segments_per_hoist = []
    plans = []
    for z in data.zones:
        moves = [k for k in range(z.lo, z.hi + 1) if k in local_pick]
        if not moves:
            segments_per_hoist.append([])
            continue
        order = sorted(moves, key=lambda k: local_pick[k])
        riferimento = min(moves)
        i0 = order.index(riferimento)
        order = order[i0:] + order[:i0]
        lp = {k: float(local_pick[k]) for k in moves}
        finish = {k: lp[k] + data.loaded_leg_seconds(k) for k in moves}
        # "parte appena consegnato": la stessa convenzione che usa il modello
        dep_hi = finish[max(moves)]
        prev = order[-1]
        arr_lo = finish[prev] + data.empty_leg_seconds(
            data.station_position(prev + 1), data.station_position(riferimento)
        )
        segments_per_hoist.append(
            _build_zone_trajectory(
                data, z, order, lp, dep_hi, arr_lo, T, incoerenze
            )
        )
        plans.append(HoistPlan(z, order, lp, finish, dep_hi, arr_lo))

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
) -> tuple[float, dict[int, float], dict[int, int]]:
    """Estrae da una soluzione i tre soli valori che servono a ricostruirla:
    takt time, fase di prelievo di ogni mossa, e periodi in piu' rispetto al
    minimo trascorsi in ciascuna vasca.

    I periodi in piu' NON sono deducibili dalle fasi: il solutore puo'
    benissimo scegliere di lasciare il pezzo in vasca un takt in piu' del
    necessario, e la fase resta la stessa. Senza questo terzo valore, la
    ricostruzione tornerebbe al minimo e cambierebbe le permanenze.

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
        minimo = arrivo + data.route[k].dwell_min
        base = local_pick[k]
        n_min = max(0, math.ceil((minimo - base) / T - data.eps_seconds / T))
        n_reale = round((at[k] - base) / T)
        if n_reale > n_min:
            extra[k] = n_reale - n_min
    return T, local_pick, extra


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
    rientro = d.empty_leg_seconds(
        d.station_position(d.n_moves), d.station_position(0)
    )
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


def _build_zone_trajectory(
    data: ProblemData,
    zone: HoistZone,
    order: list[int],
    local_pick: dict[int, float],
    dep_hi: float,
    arr_lo: float,
    T: float,
    incoerenze: Optional[list[str]] = None,
) -> list[Segment]:
    """incoerenze: se e' una lista, i valori impossibili non sollevano piu'
    un'eccezione ma vengono descritti li' dentro e la traiettoria viene
    disegnata lo stesso. Serve al disegno manuale, dove l'utente compone
    liberamente e vuole VEDERE cosa non torna invece di essere bloccato.

    order: lista degli indici di mossa nell'ordine in cui il carroponte
    le esegue entro un periodo (parte e torna a zone.lo).
    local_pick[k]: istante [s], in [0,T), di prelievo per la mossa k.
    dep_hi: istante [s] in cui il carroponte lascia il confine superiore
        della zona (dopo la mossa zone.hi) per il successivo spostamento a
        vuoto (puo' differire dal minimo stretto: e' una scelta del solver).
    arr_lo: istante [s] in cui il carroponte torna pronto al confine
        inferiore della zona (zone.lo), per il prelievo di QUESTO ciclo +T.
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
        x0 = data.station_position(k)
        x1 = data.station_position(k + 1)
        t0 = local_pick[k]
        # La mossa si scompone in tre fasi: presa (fermi sopra la vasca k),
        # traslazione orizzontale col pezzo, rilascio (fermi sopra la vasca
        # k+1). Le fasi verticali sono segmenti separati e non gonfiano il
        # tratto 'loaded': altrimenti il profilo cinematico verrebbe disegnato
        # e campionato nel posto sbagliato.
        t_pick_end = t0 + data.pick_time_at(k)
        t_arrive = t_pick_end + data.horizontal_loaded_seconds(k)
        t1 = t_arrive + data.release_time_at(k + 1)
        if t_pick_end > t0:
            segs.append(Segment("pick", t0, t_pick_end, x0, x0, None, move=k))
        segs.append(
            Segment("loaded", t_pick_end, t_arrive, x0, x1, data.kin_loaded, move=k)
        )
        if t1 > t_arrive:
            segs.append(Segment("release", t_arrive, t1, x1, x1, None, move=k))

        is_last = i == n - 1
        nxt_k = order[0] if is_last else order[i + 1]
        x1_next = data.station_position(nxt_k)
        travel_e = data.empty_leg_seconds(x1, x1_next)

        depart_known = k == zone.hi
        arrive_known = nxt_k == zone.lo

        if depart_known and arrive_known:
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
            segs.append(
                Segment("empty", depart_t, arrive_t, x1, x1_next, data.kin_empty)
            )
        elif arrive_t > depart_t + EPS:
            # stessa stazione: non c'e' nessuno spostamento a vuoto, il
            # carroponte resta fermo. Emettere un 'empty' di lunghezza nulla
            # creerebbe un segmento degenere che, con lo scarto di
            # arrotondamento sui tick, si ordina male rispetto ai vicini e
            # spezza la traiettoria.
            segs.append(Segment("wait", depart_t, arrive_t, x1, x1, None))

        target_pick = local_pick[nxt_k] + (T if nxt_k == zone.lo else 0)
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


def solve_auto_zones(
    data: ProblemData,
    n_hoists: int,
    time_limit_per_candidate: float = 8.0,
    max_candidates: int = 500,
    log_progress: bool = False,
) -> tuple[Solution, Optional[list[HoistZone]]]:
    """Prova automaticamente tutte le suddivisioni contigue delle mosse in
    `n_hoists` zone (una per carroponte) e restituisce la soluzione con il
    takt time minore fra quelle trovate fattibili, insieme alle zone che
    l'hanno generata.

    `data.zones` puo' essere None (verra' ignorato/sovrascritto per ogni
    tentativo). Restituisce (Solution, zones) -- se nessuna suddivisione e'
    fattibile, Solution.status sara' "INFEASIBLE" e zones sara' None.
    """
    n_moves = data.n_moves
    if n_hoists < 1:
        raise ValueError("n_hoists deve essere >= 1")
    if n_hoists > n_moves:
        raise ValueError(
            f"n_hoists ({n_hoists}) non puo' superare il numero di mosse ({n_moves}): "
            f"ogni carroponte deve avere almeno una mossa."
        )

    n_combinations = math.comb(n_moves - 1, n_hoists - 1)
    if n_combinations > max_candidates:
        raise ValueError(
            f"Il numero di suddivisioni possibili ({n_combinations}) supera "
            f"max_candidates ({max_candidates}). Aumenta max_candidates se vuoi "
            f"comunque una ricerca esaustiva (puo' richiedere molto tempo), oppure "
            f"riduci il numero di mosse/carroponti, oppure specifica tu stesso le "
            f"zone e usa solve() direttamente."
        )

    travel_loaded_seconds = [data.loaded_leg_seconds(k) for k in range(n_moves)]

    best_solution: Optional[Solution] = None
    best_zones: Optional[list[HoistZone]] = None
    n_tried = 0
    n_skipped = 0
    n_skipped_layout = 0
    esempio_layout: Optional[str] = None

    for zones in _enumerate_contiguous_partitions(n_moves, n_hoists):
        # pre-filtro 1: una zona il cui solo trasporto-a-carico (senza
        # nemmeno contare trasferimenti a vuoto) gia' supera il takt time
        # massimo e' certamente infattibile, qualunque sia l'ordine di visita.
        content_ok = all(
            sum(travel_loaded_seconds[k] for k in range(z.lo, z.hi + 1))
            <= data.takt_max
            for z in zones
        )
        if not content_ok:
            n_skipped += 1
            continue

        # pre-filtro 2: geometria patologica (vasche non ordinate lungo la
        # rotaia, zone che si scavalcano). Scartarla qui, invece di lasciar
        # fallire solve(), fa si' che la scelta automatica delle zone trovi da
        # sola una suddivisione valida quando esiste.
        problemi = zone_layout_conflicts(data, zones)
        if problemi:
            n_skipped_layout += 1
            if esempio_layout is None:
                esempio_layout = problemi[0]
            if log_progress:
                zone_str = ", ".join(f"[{z.lo}-{z.hi}]" for z in zones)
                print(f"  zone {zone_str}: scartata (geometria irrappresentabile)")
            continue

        candidate_data = dataclasses.replace(data, zones=zones)
        n_tried += 1
        sol = solve(candidate_data, time_limit_s=time_limit_per_candidate)
        if log_progress:
            zone_str = ", ".join(f"[{z.lo}-{z.hi}]" for z in zones)
            info = f"T={sol.T:.2f}s" if sol.T is not None else sol.status
            print(f"  zone {zone_str}: {info}")
        if sol.status in ("OPTIMAL", "FEASIBLE") and sol.T is not None:
            if best_solution is None or sol.T < best_solution.T:
                best_solution = sol
                best_zones = zones

    if best_solution is None:
        return (
            Solution(
                status="INFEASIBLE",
                T=None,
                raw={
                    "n_tried": n_tried,
                    "n_skipped": n_skipped,
                    "n_skipped_layout": n_skipped_layout,
                    "layout_example": esempio_layout,
                },
            ),
            None,
        )

    best_solution.raw["n_tried"] = n_tried
    best_solution.raw["n_skipped"] = n_skipped
    best_solution.raw["n_skipped_layout"] = n_skipped_layout
    best_solution.raw["layout_example"] = esempio_layout
    best_solution.raw["zones"] = best_zones
    return best_solution, best_zones


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
    max_candidates_per_hoist_count: int = 500,
    log_progress: bool = False,
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
            )
        except ValueError as e:
            # troppe suddivisioni possibili per questo n_hoists: lo segnalo
            # e provo comunque il numero di carroponti successivo, invece
            # di far fallire l'intera ricerca.
            sweep.append({"n_hoists": n_hoists, "status": "SKIPPED", "error": str(e)})
            if log_progress:
                print(f"  saltato: {e}")
            continue

        voce = {"n_hoists": n_hoists, "status": sol.status, "T": sol.T}
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
