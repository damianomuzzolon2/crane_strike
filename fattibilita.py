"""
fattibilita.py
--------------
Prima di lanciare il calcolo: la linea puo' stare nel takt time richiesto?

Il solutore, quando non trova niente, ci mette tutto il tempo che gli si
concede -- prova ogni suddivisione in zone per ogni numero di carroponti -- e
una linea impossibile e' proprio il caso in cui si aspetta di piu'. Qui si
calcolano invece dei LIMITI INFERIORI del takt time, in pochi millisecondi:
numeri sotto i quali nessun ciclogramma puo' scendere, qualunque siano zone,
attese e numero di carroponti.

Due famiglie di limiti:

- **le vasche**: una vasca a un posto non riceve il pezzo nuovo finche' il
  vecchio non e' uscito e il carro che porta il nuovo non e' arrivato. Fra un
  pezzo e il successivo passano almeno la permanenza minima, la presa e
  l'arrivo del successivo -- e se la vasca precedente e' piu' vicina della
  distanza fra due ganci, chi porta il pezzo nuovo non puo' nemmeno prenderlo
  finche' l'altro carro non si e' allontanato;
- **i carroponti**: ogni carro, in un periodo, fa tutte le mosse a carico
  della sua zona e almeno un rientro a vuoto da un capo all'altro.

E' una condizione NECESSARIA, non sufficiente: se il limite supera il takt
richiesto la linea e' certamente impossibile e il calcolo si puo' risparmiare;
se non lo supera, la linea PUO' essere fattibile, e lo dice solo il solutore.
Quanto il limite e' vicino al takt richiesto dice quanto ci si gioca.

Non importa ortools e non tocca niente: legge `ProblemData` e basta.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from model import HoistZone, ProblemData


@dataclass
class LimiteVasca:
    """Il takt minimo imposto da una vasca, e da dove viene."""

    vasca: str
    posti: int
    occupazione_s: float  # posto occupato per periodo: rilascio+bagno min+presa
    # cambio pezzo: dalla presa del vecchio al rilascio del nuovo, permanenza
    # minima compresa. None se non si calcola (piu' posti, piu' passaggi,
    # vasche fuori ordine lungo la rotaia)
    cambio_s: Optional[float]
    limite_s: float


@dataclass
class LimiteCarri:
    """Il takt minimo imposto dal lavoro dei carri, con `n` carroponti."""

    n: int
    limite_s: float
    zone: list[HoistZone]


@dataclass
class Fattibilita:
    takt_richiesto_min: float
    takt_richiesto_max: float
    takt_fisso: bool
    max_carroponti: int
    vasche: list[LimiteVasca] = field(default_factory=list)
    carri: list[LimiteCarri] = field(default_factory=list)

    @property
    def vasca_critica(self) -> LimiteVasca:
        return max(self.vasche, key=lambda v: v.limite_s)

    @property
    def limite_vasche(self) -> float:
        return self.vasca_critica.limite_s if self.vasche else 0.0

    @property
    def limite_carri(self) -> float:
        """Il migliore dei limiti dei carri, cioe' col numero di carroponti
        piu' favorevole fra quelli ammessi."""
        return min(c.limite_s for c in self.carri) if self.carri else 0.0

    @property
    def takt_minimo(self) -> float:
        """Sotto questo takt time la linea non funziona, con nessun numero di
        carroponti fino a `max_carroponti`."""
        return max(self.limite_vasche, self.limite_carri)

    @property
    def impossibile(self) -> bool:
        return self.takt_minimo > self.takt_richiesto_max + 1e-6

    @property
    def carri_minimi(self) -> Optional[int]:
        """Il numero minimo di carroponti che il lavoro dei carri non esclude
        al takt richiesto. None se nessuno fino a `max_carroponti`."""
        for c in self.carri:
            if c.limite_s <= self.takt_richiesto_max + 1e-6:
                return c.n
        return None


def _tempo_per_sgomberare(dist: float, kin) -> float:
    """Il tempo minimo per allontanarsi di `dist` mm partendo da fermo, senza
    contare la frenata: il carro che sgombera sta andando altrove e passa di
    li' lanciato. Sottostimarlo e' dal lato giusto per un limite inferiore."""
    if dist <= 0:
        return 0.0
    s_acc = kin.v_max**2 / (2 * kin.a_max)
    if dist <= s_acc:
        return math.sqrt(2 * dist / kin.a_max)
    return kin.v_max / kin.a_max + (dist - s_acc) / kin.v_max


def _limiti_vasche(d: ProblemData) -> list[LimiteVasca]:
    passaggi = d.steps_by_tank()
    distanza_ganci = d.hoist_length + d.safety_distance
    out = []
    for tank_id, stazioni in passaggi.items():
        stazioni = [j for j in stazioni if 0 < j < d.n_stations - 1]
        if not stazioni:
            continue
        posti = d.tank_capacity(stazioni[0])
        occ = sum(
            d.slot_occupancy_seconds(j, d.route[j].dwell_min) for j in stazioni
        )
        cambio = None
        if posti == 1 and len(stazioni) == 1:
            j = stazioni[0]
            x_prec = d.station_position(j - 1)
            x = d.station_position(j)
            x_succ = d.station_position(j + 1)
            if x_prec < x < x_succ:
                pmin = d.route[j].dwell_min
                entra = d.loaded_leg_seconds(j - 1)
                # lo stesso carro porta via il vecchio e porta il nuovo: deve
                # consegnare, tornare a vuoto alla vasca prima e riportare
                stesso = (
                    pmin
                    + d.loaded_leg_seconds(j)
                    + d.empty_leg_seconds(j + 1, j - 1)
                    + entra
                )
                # due carri: chi porta il nuovo comincia la mossa a carico
                # sopra la vasca prima, e non ci puo' stare finche' l'altro non
                # si e' allontanato abbastanza da questa
                sgombero = distanza_ganci - (x - x_prec)
                if sgombero > 0:
                    diversi = (
                        pmin
                        + d.pick_time_at(j)
                        + _tempo_per_sgomberare(sgombero, d.kin_loaded)
                        + entra
                    )
                else:
                    diversi = (
                        pmin
                        + d.pick_time_at(j)
                        + d.horizontal_loaded_seconds(j - 1)
                        + d.release_time_at(j)
                    )
                cambio = min(stesso, diversi)
        limite = max(occ / posti, cambio or 0.0)
        out.append(LimiteVasca(tank_id, posti, occ, cambio, limite))
    # nell'ordine della ricetta, come le legge chi ha compilato il file
    ordine = {d.route[j].tank_id: j for j in range(d.n_stations - 1, -1, -1)}
    out.sort(key=lambda v: ordine[v.vasca])
    return out


def _limiti_carri(d: ProblemData, max_carri: int) -> list[LimiteCarri]:
    """Per ogni numero di carroponti, la suddivisione contigua delle mosse che
    rende minimo il giro piu' lungo. Programmazione dinamica: le suddivisioni
    sono troppe per enumerarle su una linea lunga."""
    n = d.n_moves
    carico = [d.loaded_leg_seconds(k) for k in range(n)]
    pref = [0.0]
    for c in carico:
        pref.append(pref[-1] + c)

    def giro(lo: int, hi: int) -> float:
        return pref[hi + 1] - pref[lo] + d.empty_leg_seconds(hi + 1, lo)

    costo = [[0.0] * n for _ in range(n)]
    for lo in range(n):
        for hi in range(lo, n):
            costo[lo][hi] = giro(lo, hi)

    INF = float("inf")
    # best[h][i]: il miglior "giro piu' lungo" coprendo le mosse 0..i-1 con h
    # carri; scelta[h][i] dove comincia l'ultima zona
    best = [[INF] * (n + 1) for _ in range(max_carri + 1)]
    scelta = [[0] * (n + 1) for _ in range(max_carri + 1)]
    best[0][0] = 0.0
    out = []
    for h in range(1, min(max_carri, n) + 1):
        for i in range(1, n + 1):
            for s in range(h - 1, i):
                v = max(best[h - 1][s], costo[s][i - 1])
                if v < best[h][i]:
                    best[h][i], scelta[h][i] = v, s
        zone, i = [], n
        for hh in range(h, 0, -1):
            s = scelta[hh][i]
            zone.append(HoistZone(s, i - 1))
            i = s
        out.append(LimiteCarri(h, best[h][n], zone[::-1]))
    return out


def valuta(d: ProblemData, max_carroponti: int) -> Fattibilita:
    if d.portate is not None:
        max_carroponti = len(d.portate)
    return Fattibilita(
        takt_richiesto_min=d.takt_min_ricerca,
        takt_richiesto_max=d.takt_max_ricerca,
        takt_fisso=d.takt_fisso,
        max_carroponti=max_carroponti,
        vasche=_limiti_vasche(d),
        carri=_limiti_carri(d, max_carroponti),
    )


def testo(f: Fattibilita) -> str:
    """Il referto, gia' leggibile: lo usano la finestra e il terminale."""
    righe = []
    if f.takt_fisso:
        richiesto = f"takt fisso {f.takt_richiesto_max:.0f} s"
    else:
        richiesto = (
            f"takt fra {f.takt_richiesto_min:.0f} e {f.takt_richiesto_max:.0f} s"
        )
    critica = f.vasca_critica if f.vasche else None
    if f.impossibile:
        righe.append(f"IMPOSSIBILE con {richiesto} e al massimo "
                     f"{f.max_carroponti} carroponti.")
        righe.append(f"Il takt time non puo' scendere sotto {f.takt_minimo:.1f} s.")
        righe.append("Il calcolo automatico non troverebbe niente: non serve "
                     "lanciarlo cosi'.")
    else:
        margine = f.takt_richiesto_max - f.takt_minimo
        righe.append(f"NON ESCLUSA con {richiesto}: il limite teorico e' "
                     f"{f.takt_minimo:.1f} s, {margine:.0f} s di margine.")
        righe.append("E' una condizione necessaria, non sufficiente: se si "
                     "riesce davvero lo dice solo il calcolo.")
        if margine < 0.1 * f.takt_richiesto_max:
            righe.append("Il margine e' stretto: il calcolo potrebbe non "
                         "trovare soluzione.")
    righe.append("")
    if critica is not None:
        righe.append(f"Vasche: takt >= {f.limite_vasche:.1f} s "
                     f"(collo di bottiglia: {critica.vasca}).")
    righe.append(f"Carroponti: takt >= {f.limite_carri:.1f} s "
                 f"(con {f.max_carroponti}).")
    cm = f.carri_minimi
    if cm is None:
        righe.append(f"  Nemmeno {f.max_carroponti} carroponti bastano per il "
                     f"lavoro a carico.")
    else:
        righe.append(f"  Servono almeno {cm} carroponti.")
    righe.append("")
    righe.append("Vasche (takt minimo per vasca, dal piu' stretto):")
    for v in sorted(f.vasche, key=lambda v: -v.limite_s)[:6]:
        dettaglio = f"occupazione {v.occupazione_s:.0f} s"
        if v.posti > 1:
            dettaglio += f" su {v.posti} posti"
        if v.cambio_s is not None:
            dettaglio += f", cambio pezzo {v.cambio_s:.0f} s"
        fuori = "  << oltre il takt" if v.limite_s > f.takt_richiesto_max else ""
        righe.append(f"  {v.vasca:<8} {v.limite_s:6.1f} s  ({dettaglio}){fuori}")
    righe.append("")
    righe.append("Carroponti (giro piu' lungo con la zona migliore):")
    for c in f.carri:
        fuori = "  << oltre il takt" if c.limite_s > f.takt_richiesto_max else ""
        righe.append(f"  {c.n} carri: {c.limite_s:6.1f} s{fuori}")
    if critica is not None and f.limite_vasche > f.takt_richiesto_max:
        righe.append("")
        righe.append(f"Per sbloccare {critica.vasca}: allarga il suo "
                     f"delta_negativo_s o dalle un posto in piu'.")
    return "\n".join(righe)


if __name__ == "__main__":
    import sys

    from excel_io import leggi_problema

    for percorso in sys.argv[1:]:
        cfg = leggi_problema(percorso)
        print(f"===== {percorso}")
        print(testo(valuta(cfg.data, cfg.max_carroponti)))
        print()
