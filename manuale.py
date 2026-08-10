"""
manuale.py
----------
Supporto al disegno MANUALE del ciclogramma.

E' il metodo con cui i ciclogrammi si tracciano a mano da sempre: prima si
disegna il "pettine" dei pezzi -- una scalinata per ogni pezzo in lavorazione,
che sale di vasca in vasca e si ferma per il tempo di processo -- e poi si
tirano le linee dei carroponti, decidendo quali trasporti fa ciascuno.

Qui non si verifica e non si rifiuta nulla: l'utente compone come vuole, anche
cose fisicamente impossibili, e le incoerenze vengono descritte invece che
bloccate. La verifica vera si fa alla fine, su richiesta, con verify.py.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

from model import HoistZone, ProblemData, Segment, Solution, build_solution

# Quante scalinate disegnare: sono i pezzi contemporaneamente in lavorazione
# che si vogliono vedere. Dieci bastano a coprire qualunque linea reale e a
# far capire come i cicli si incastrano fra loro.
RIPETIZIONI_PREDEFINITE = 10


def permanenze_iniziali(data: ProblemData) -> dict[int, float]:
    """Tempo in vasca da cui partire: il minimo di processo per ogni vasca.

    E' il pettine piu' "stretto" possibile, cioe' la linea piu' veloce che il
    processo consenta. Da li' l'utente allarga dove serve."""
    return {k: float(data.route[k].dwell_min) for k in range(1, data.n_moves)}


def catena_pezzo(
    data: ProblemData, permanenze: dict[int, float]
) -> list[float]:
    """Istanti di prelievo (assoluti) di UN pezzo lungo tutta la linea, dati i
    tempi in vasca scelti. E' la scalinata: prelievo, trasporto, sosta,
    prelievo, trasporto, sosta..."""
    tempi = [0.0]
    for k in range(1, data.n_moves):
        arrivo = tempi[k - 1] + data.loaded_leg_seconds(k - 1)
        tempi.append(arrivo + float(permanenze.get(k, data.route[k].dwell_min)))
    return tempi


def segmenti_pezzo(data: ProblemData, tempi: list[float]) -> list[Segment]:
    """Il percorso di un pezzo come sequenza di segmenti disegnabili: le soste
    in vasca (orizzontali) e i trasporti (presa, traslazione, rilascio).

    Usa gli stessi tipi di segmento delle traiettorie dei carroponti, cosi' il
    pettine e le linee dei carri si sovrappongono esattamente sugli stessi
    tratti -- che e' il punto: l'utente clicca su un trasporto del pettine e
    quello diventa un pezzo del giro di un carroponte."""
    segs: list[Segment] = []
    for k in range(data.n_moves):
        x0 = data.station_position(k)
        x1 = data.station_position(k + 1)
        t0 = tempi[k]
        t_presa = t0 + data.pick_time_at(k)
        t_arrivo = t_presa + data.horizontal_loaded_seconds(k)
        t_fine = t_arrivo + data.release_time_at(k + 1)
        if t_presa > t0:
            segs.append(Segment("pick", t0, t_presa, x0, x0, None))
        segs.append(Segment("loaded", t_presa, t_arrivo, x0, x1, data.kin_loaded))
        if t_fine > t_arrivo:
            segs.append(Segment("release", t_arrivo, t_fine, x1, x1, None))
        # sosta in vasca fino al prelievo successivo
        if k + 1 < data.n_moves and tempi[k + 1] > t_fine:
            segs.append(Segment("wait", t_fine, tempi[k + 1], x1, x1, None))
    return segs


def assegnazione_iniziale(data: ProblemData, n_carroponti: int) -> dict[int, int]:
    """Suddivisione di partenza: le mosse spartite il piu' uniformemente
    possibile fra i carroponti, in blocchi contigui.

    Non e' quello da cui parte il disegno a mano -- li' si parte da NIENTE
    assegnato, ed e' l'utente a decidere una mossa per volta. Serve a chi
    vuole una suddivisione plausibile su cui ragionare senza passare dal
    solutore."""
    n = max(1, min(n_carroponti, data.n_moves))
    tagli = [round(i * data.n_moves / n) for i in range(n + 1)]
    assegnazione = {}
    for c in range(n):
        for k in range(tagli[c], tagli[c + 1]):
            assegnazione[k] = c
    return assegnazione


def perche_non_va(
    data: ProblemData, assegnazione: dict[int, int]
) -> Optional[str]:
    """Motivo per cui un'assegnazione non e' realizzabile, o None se va bene.

    Non e' un controllo sul ciclogramma -- quelli sono sospesi durante il
    disegno -- ma sulla GEOMETRIA: i carroponti stanno tutti sulla stessa
    rotaia e non possono scavalcarsi. Se il carroponte 2 dovesse servire una
    vasca che sta prima di quelle del carroponte 1, dovrebbe passargli
    attraverso. Non e' una limitazione del calcolo: e' la rotaia.

    Le mosse ancora non assegnate NON sono un motivo: si parte da zero e si
    assegna una mossa per volta, quindi un'assegnazione incompleta e' lo stato
    normale del lavoro in corso. Che manchi qualcosa lo dice `componi()` fra le
    incoerenze, dove serve -- non qui, che deve rispondere solo a "posso dare
    questa mossa a questo carroponte?"."""
    assegnate = [(k, assegnazione[k]) for k in sorted(assegnazione)]
    for (k1, c1), (k2, c2) in zip(assegnate, assegnate[1:]):
        if c2 < c1:
            return (
                f"il carroponte {c2 + 1} dovrebbe fare la mossa "
                f"{k2} ({data.route[k2].tank_id} -> "
                f"{data.route[k2 + 1].tank_id}) mentre il carroponte "
                f"{c1 + 1} lavora piu' avanti sulla linea: sulla "
                f"stessa rotaia dovrebbero scavalcarsi"
            )
    return None


def zone_da_assegnazione(
    assegnazione: dict[int, int], n_carroponti: int
) -> list[HoistZone]:
    """Zone corrispondenti all'assegnazione, che qui e' gia' stata verificata
    contigua e ordinata da perche_non_va()."""
    zone = []
    for c in range(n_carroponti):
        mosse = [k for k, v in assegnazione.items() if v == c]
        if mosse:
            zone.append(HoistZone(min(mosse), max(mosse)))
    return zone


def componi(
    data: ProblemData,
    T: float,
    permanenze: dict[int, float],
    assegnazione: dict[int, int],
    n_carroponti: int,
) -> tuple[Solution, ProblemData, list[str]]:
    """Costruisce il ciclogramma dal disegno manuale.

    Non rifiuta nulla: se il risultato e' fisicamente impossibile lo disegna
    ugualmente e restituisce l'elenco delle incoerenze, perche' l'utente possa
    vederle sul grafico e correggerle. Restituisce (soluzione, dati con le
    zone, incoerenze)."""
    tempi = catena_pezzo(data, permanenze)
    dati = dataclasses.replace(data, zones=zone_coprenti(data, assegnazione))
    sol = build_solution(
        dati,
        T,
        actual_time=tempi,
        status="MANUALE",
        tollerante=True,
        mosse_attive=set(assegnazione),
    )
    incoerenze = list(sol.raw.get("incoerenze", []))
    scoperte = [k for k in range(data.n_moves) if k not in assegnazione]
    if scoperte:
        incoerenze.insert(
            0,
            f"le mosse {scoperte} non sono ancora assegnate a nessun carroponte",
        )
    return sol, dati, incoerenze


def zone_coprenti(
    data: ProblemData, assegnazione: dict[int, int]
) -> list[HoistZone]:
    """Zone che coprono TUTTE le mosse, anche quelle non ancora assegnate: le
    strutture dati pretendono una copertura completa. Le mosse scoperte
    vengono accorpate al carroponte precedente ai soli fini della struttura --
    non compaiono in nessun giro, e vengono segnalate come mancanti."""
    corrente = 0
    pieno = []
    for k in range(data.n_moves):
        corrente = assegnazione.get(k, corrente)
        pieno.append(corrente)
    zone = []
    inizio = 0
    for k in range(1, data.n_moves + 1):
        if k == data.n_moves or pieno[k] != pieno[inizio]:
            zone.append(HoistZone(inizio, k - 1))
            inizio = k
    return zone


def pettine(
    data: ProblemData,
    T: float,
    permanenze: dict[int, float],
    ripetizioni: int = RIPETIZIONI_PREDEFINITE,
) -> list[list[Segment]]:
    """Il pettine: `ripetizioni` scalinate identiche, sfasate di un takt time
    l'una dall'altra. Ogni scalinata e' un pezzo in lavorazione."""
    tempi = catena_pezzo(data, permanenze)
    base = segmenti_pezzo(data, tempi)
    fuori = []
    for p in range(ripetizioni):
        scarto = p * T
        fuori.append(
            [
                dataclasses.replace(
                    s, t_start=s.t_start + scarto, t_end=s.t_end + scarto
                )
                for s in base
            ]
        )
    return fuori


def trasporti_cliccabili(
    data: ProblemData,
    T: float,
    permanenze: dict[int, float],
    ripetizioni: int = RIPETIZIONI_PREDEFINITE,
) -> list[tuple[int, float, float, float, float]]:
    """Per ogni trasporto disegnato nel pettine: (mossa, t_inizio, t_fine,
    x_inizio, x_fine). Serve a capire su quale trasporto ha cliccato l'utente.
    """
    tempi = catena_pezzo(data, permanenze)
    fuori = []
    for p in range(ripetizioni):
        scarto = p * T
        for k in range(data.n_moves):
            t0 = tempi[k] + scarto
            fuori.append(
                (
                    k,
                    t0,
                    t0 + data.loaded_leg_seconds(k),
                    data.station_position(k),
                    data.station_position(k + 1),
                )
            )
    return fuori
