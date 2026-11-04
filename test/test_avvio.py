"""
test_avvio.py
-------------
Test del punto di avvio (avvio.py).

NON richiede OR-Tools: i ciclogrammi di riferimento sono quelli di
`proposta_semplice` e di `manuale.componi`, che si costruiscono senza
risolvere niente. Quello che si pretende non dipende dal solutore: in
qualunque ciclogramma, nell'istante di avvio ogni carroponte deve stare
davvero dove il riepilogo dice che sta, e deve essere davvero fermo col gancio
in basso.

La linea di prova ha vasche con CORSE VERTICALI DIVERSE e due stazioni di
mezzo: con corse tutte uguali un errore sulla quota di riposo darebbe comunque
il risultato giusto, e senza almeno due vasche di mezzo non ci sarebbe modo di
sbagliare vasca.

Per eseguirlo:
    python test/test_avvio.py
"""

from __future__ import annotations

import os
import sys

# I moduli del programma stanno nella cartella sopra questa: senza aggiungerla
# fra i percorsi di ricerca, lanciare il test da qui non li troverebbe.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from avvio import (
    Avvio,
    PosizioneAvvio,
    finestre_di_riposo,
    posizione_a,
    righe_di_riepilogo,
    stazione_di_riposo,
    trova_avvii,
    trova_avvio,
)
from kinematics import Kinematics
import manuale
from model import ProblemData, StationSpec, Tank, proposta_semplice

KIN_EMPTY = Kinematics(v_max=1600, a_max=900)
KIN_LOADED = Kinematics(v_max=1000, a_max=400)
KIN_LIFT_EMPTY = Kinematics(v_max=500, a_max=800)
KIN_LIFT_LOADED = Kinematics(v_max=300, a_max=500)

# posizione, corsa verticale, sgocciolamento: tutte diverse fra loro
VASCHE = [
    ("CARICO", 0.0, 0.0, 0.0),
    ("SGRASSO", 4000.0, 1200.0, 6.0),
    ("RISCIACQUO", 9000.0, 800.0, 2.0),
    ("PASSIVA", 13000.0, 600.0, 3.0),
    ("SCARICO", 18000.0, 300.0, 0.0),
]

_n_pass = 0
_n_fail = 0


def check(condition: bool, description: str):
    global _n_pass, _n_fail
    if condition:
        _n_pass += 1
        print(f"  ok   {description}")
    else:
        _n_fail += 1
        print(f"  FAIL {description}")


def dati_prova(gancio_basso: bool = True) -> ProblemData:
    """gancio_basso=False: le vasche di mezzo diventano OSTACOLI, con i loro
    svincoli, e il rientro a vuoto passa alto. Le finestre di riposo devono
    restare quelle: il gancio risale sullo svincolo, non sulla vasca."""
    ultima = VASCHE[-1][1]
    tanks = {}
    for nome, pos, corsa, scolo in VASCHE:
        estremo = pos in (0.0, ultima)
        svincoli = (
            {}
            if gancio_basso
            else dict(
                svincolo_neg=pos - 900 if pos > 0 else None,
                svincolo_pos=pos + 900 if pos < ultima else None,
            )
        )
        tanks[nome] = Tank(
            nome,
            pos,
            1,
            lift_height=corsa,
            drain_time=scolo,
            gancio_basso=gancio_basso or estremo,
            **svincoli,
        )
    route = [
        StationSpec("CARICO", 0.0, 0.0),
        StationSpec("SGRASSO", 60.0, 400.0),
        StationSpec("RISCIACQUO", 30.0, 400.0),
        StationSpec("PASSIVA", 45.0, 400.0),
        StationSpec("SCARICO", 0.0, 0.0),
    ]
    return ProblemData(
        tanks=tanks,
        route=route,
        takt_min=40.0,
        takt_max=400.0,
        kin_empty=KIN_EMPTY,
        kin_loaded=KIN_LOADED,
        hoist_extent_pos=500,
        hoist_extent_neg=700,
        safety_distance=600,
        kin_lift_empty=KIN_LIFT_EMPTY,
        kin_lift_loaded=KIN_LIFT_LOADED,
        engage_time=3.0,
        disengage_time=2.0,
    )


def due_carroponti(d: ProblemData, T: float):
    """Un ciclogramma a due carroponti, composto a mano: i primi due trasporti
    al primo carro, gli ultimi due al secondo."""
    perm = manuale.permanenze_iniziali(d)
    sol, dati, _ = manuale.componi(d, T, perm, {0: 0, 1: 0, 2: 1, 3: 1}, 2)
    return sol, dati


# --------------------------------------------------------------------------


def test_stazione_di_riposo(d: ProblemData):
    print("\n[1] carico e scarico non sono posti dove lasciare un carroponte")
    check(
        stazione_di_riposo(d, d.station_position(0)) is None
        and stazione_di_riposo(d, d.station_position(d.n_stations - 1)) is None,
        "il carico e lo scarico sono esclusi",
    )
    check(
        [stazione_di_riposo(d, d.station_position(s)) for s in (1, 2, 3)] == [1, 2, 3],
        "le vasche di mezzo sono ammesse, ciascuna con la sua tappa",
    )
    check(
        stazione_di_riposo(d, 6500.0) is None,
        "a meta' strada fra due vasche non c'e' nessuna tappa",
    )


def test_finestre_sono_di_riposo(d: ProblemData):
    print("\n[2] dentro una finestra il carroponte sta davvero fermo in basso")
    sol, dati = proposta_semplice(d)
    segs = sorted(sol.segments_per_hoist[0], key=lambda s: s.t_start)
    finestre = finestre_di_riposo(dati, segs)
    check(bool(finestre), f"il giro ha {len(finestre)} finestre di riposo")

    # Fermo: in tutta la finestra la posizione non cambia, ed e' quella della
    # vasca dichiarata.
    fermo, giusta = True, True
    for f in finestre:
        quanti = 12
        for i in range(quanti + 1):
            t = f.t_inizio + (f.t_fine - f.t_inizio) * i / quanti
            if abs(posizione_a(segs, t, sol.T) - f.x) > 1e-6:
                fermo = False
        if abs(dati.station_position(f.stazione) - f.x) > 1e-6:
            giusta = False
    check(fermo, "la posizione non cambia per tutta la finestra")
    check(giusta, "la posizione e' quella della vasca dichiarata dalla finestra")

    # In basso: le finestre cadono fra la fine di un rilascio (meno lo sgancio)
    # e l'inizio di una presa (piu' l'aggancio), che sono gli unici due momenti
    # in cui il gancio e' in fondo corsa e non si muove.
    fuori = []
    for s in segs:
        if s.kind == "loaded" and s.move is not None:
            k = s.move
            # il sollevamento del telaio comincia dopo l'aggancio
            fuori.append(s.t_start - dati.pick_time_at(k) + dati.engage_time)
            # l'immersione finisce prima dello sgancio
            fuori.append(
                s.t_end + dati.release_time_at(k + 1) - dati.disengage_time
            )
    dentro = all(
        not any(f.t_inizio + 1e-9 < t < f.t_fine - 1e-9 for t in fuori)
        for f in finestre
    )
    check(dentro, "nessuna finestra contiene una corsa verticale del gancio")

    check(
        all(f.stazione not in (0, dati.n_stations - 1) for f in finestre),
        "nessuna finestra sta sul carico o sullo scarico",
    )


def test_avvio_esatto(d: ProblemData):
    print("\n[3] un istante in cui tutti i carroponti sono a riposo")
    sol, dati = due_carroponti(d, 70.0)
    a = trova_avvio(dati, sol)
    check(a is not None and a.esatto, "l'istante di avvio esiste ed e' esatto")
    check(abs(a.errore) < 1e-9, f"errore nullo ({a.errore:.3f} s)")
    check(0.0 <= a.t < sol.T, f"l'istante sta dentro il ciclo ({a.t:.2f} s)")

    # Ogni carroponte e' dove dice il riepilogo, e quella posizione e' dentro
    # una delle sue finestre di riposo.
    ok_posizione, ok_dentro = True, True
    for p in a.posizioni:
        segs = sol.segments_per_hoist[p.carro]
        if abs(posizione_a(segs, a.t, sol.T) - p.x) > 1e-6:
            ok_posizione = False
        if not any(
            (f.t_inizio - 1e-9) <= a.t + n * sol.T <= (f.t_fine + 1e-9)
            for f in finestre_di_riposo(dati, segs)
            for n in (-1, 0, 1, 2)
        ):
            ok_dentro = False
    check(ok_posizione, "la posizione scritta e' quella che il carro ha davvero")
    check(ok_dentro, "e cade dentro una finestra di riposo di quel carroponte")

    # Il margine: avviare sul bordo di una finestra non lascia scampo, e
    # l'istante scelto deve stare in mezzo. Si controlla che mezzo secondo
    # prima e mezzo secondo dopo i carroponti siano ancora tutti a riposo.
    margine = True
    for scarto in (-0.5, 0.5):
        altro = Avvio(
            t=(a.t + scarto) % sol.T,
            posizioni=[PosizioneAvvio(p.carro, p.x, p.vasca, 0.0) for p in a.posizioni],
        )
        for p in a.posizioni:
            if not any(
                (f.t_inizio - 1e-9) <= altro.t + n * sol.T <= (f.t_fine + 1e-9)
                for f in finestre_di_riposo(dati, sol.segments_per_hoist[p.carro])
                for n in (-1, 0, 1, 2)
            ):
                margine = False
    check(margine, "mezzo secondo prima e mezzo secondo dopo vanno ancora bene")


def test_avvio_approssimato(d: ProblemData):
    print("\n[4] quando nessun istante accontenta tutti, si sbaglia il meno")
    sol, dati = due_carroponti(d, 45.0)
    a = trova_avvio(dati, sol)
    check(a is not None and not a.esatto, f"l'avvio e' approssimato ({a.errore:.2f} s)")

    # L'errore e' il minimo: nessun altro istante del ciclo fa meglio. Si
    # campiona fitto invece di fidarsi dei soli candidati, che e' proprio
    # l'ipotesi da controllare.
    # Il giro di un carroponte non comincia all'istante zero, e le sue finestre
    # possono stare parecchi periodi piu' in la': si confronta `t` con tutte le
    # sue ripetizioni, da ben prima a ben dopo.
    giri = range(-2, int(max(s.t_end for s in sol.segments_per_hoist[-1]) / sol.T) + 3)

    def errore_a(t: float) -> float:
        totale = 0.0
        for segs in sol.segments_per_hoist:
            finestre = finestre_di_riposo(dati, segs)
            if not finestre:
                continue
            totale += min(
                max(f.t_inizio - (t + n * sol.T), (t + n * sol.T) - f.t_fine, 0.0)
                for f in finestre
                for n in giri
            )
        return totale

    passo = sol.T / 4000.0
    migliore = min(errore_a(i * passo) for i in range(4001))
    check(
        a.errore <= migliore + 1e-6,
        f"e' il minimo: {a.errore:.3f} s contro {migliore:.3f} s campionando",
    )
    check(
        any(p.errore > 0 for p in a.posizioni)
        and abs(a.errore - sum(p.errore for p in a.posizioni)) < 1e-9,
        "l'errore totale e' la somma di quelli dei singoli carroponti",
    )


def test_gancio_alto(d: ProblemData):
    print("\n[5] con il rientro a vuoto che passa alto le finestre non cambiano")
    alto = dati_prova(gancio_basso=False)
    sol_b, dati_b = due_carroponti(d, 70.0)
    sol_a, dati_a = due_carroponti(alto, 70.0)
    uguali = True
    for basso, su in zip(sol_b.segments_per_hoist, sol_a.segments_per_hoist):
        f_b = finestre_di_riposo(dati_b, basso)
        f_a = finestre_di_riposo(dati_a, su)
        if [r.stazione for r in f_b] != [r.stazione for r in f_a]:
            uguali = False
    check(uguali, "il riposo avviene sulle stesse vasche nei due impianti")
    check(
        all(
            r.stazione not in (0, dati_a.n_stations - 1)
            for segs in sol_a.segments_per_hoist
            for r in finestre_di_riposo(dati_a, segs)
        ),
        "nemmeno con gli svincoli si riposa sul carico o sullo scarico",
    )


def test_carro_senza_riposo(d: ProblemData):
    print("\n[6] un carroponte che non si ferma mai non blocca il calcolo")
    sol, dati = due_carroponti(d, 70.0)
    # Si toglie al primo carroponte ogni istante di riposo: le attese
    # diventano traslazioni di lunghezza nulla, e i tratti a carico perdono la
    # loro mossa, cosi' non ci sono piu' ne' l'aggancio ne' lo sgancio. Non
    # basterebbe azzerarne i tempi: un aggancio di 0 s e' comunque un istante
    # fermo in basso, e conta. E' un caso che un impianto vero non da', ma il
    # programma non deve ne' sbagliare ne' fermarsi se ci capita.
    import dataclasses

    def spento(s):
        if s.kind == "wait":
            return dataclasses.replace(s, kind="empty")
        if s.kind == "loaded":
            return dataclasses.replace(s, move=None)
        return s

    senza = [spento(s) for s in sol.segments_per_hoist[0]]
    muto = dati
    sol2 = dataclasses.replace(
        sol, segments_per_hoist=[senza, sol.segments_per_hoist[1]]
    )
    check(
        not finestre_di_riposo(muto, senza),
        "il carroponte cosi' conciato non ha nessuna finestra di riposo",
    )
    a = trova_avvio(muto, sol2)
    check(a is not None, "l'istante di avvio si trova lo stesso")
    check(
        any(p.mai for p in a.posizioni) and not a.esatto,
        "il carroponte senza riposo e' segnalato, e l'avvio non e' esatto",
    )
    check(
        all(p.errore == 0.0 for p in a.posizioni if p.mai),
        "e non pesa sull'errore: nessun istante lo accontenterebbe",
    )


def test_riepilogo(d: ProblemData):
    print("\n[7] il riepilogo dice le stesse cose dell'oggetto")
    sol, dati = due_carroponti(d, 70.0)
    a = trova_avvio(dati, sol)
    righe = righe_di_riepilogo(a)
    check(
        all(len(r) == 3 for r in righe),
        "ogni riga ha etichetta, valore e nota, come il foglio Riepilogo",
    )
    check(
        righe[0][0] == "Istante di avvio" and abs(righe[0][1] - a.t) < 0.005,
        f"la prima riga e' l'istante ({righe[0][1]})",
    )
    check(
        sum(1 for r in righe if r[0].strip().startswith("Carroponte"))
        == len(a.posizioni),
        "c'e' una riga per carroponte",
    )
    check(
        righe_di_riepilogo(None)[0][0] == "Istante di avvio",
        "senza avvio il riepilogo lo dice invece di saltare la riga",
    )
    # i numeri mostrati possono non essere gli indici delle zone
    rinominati = righe_di_riepilogo(a, {0: 1, 1: 0})
    check(
        [r[1] for r in rinominati if r[0].strip().startswith("Carroponte")]
        != [r[1] for r in righe if r[0].strip().startswith("Carroponte")],
        "la traduzione zona -> numero di carroponte viene rispettata",
    )


def _errore_campionato(dati: ProblemData, sol, t: float) -> float:
    """L'errore all'istante `t`, calcolato senza passare da `avvio.py`.

    Serve ai due test che devono confrontare il risultato con qualcosa di
    indipendente: rifare il conto con le stesse funzioni non proverebbe
    niente."""
    giri = range(-2, int(max(s.t_end for s in sol.segments_per_hoist[-1]) / sol.T) + 3)
    totale = 0.0
    for segs in sol.segments_per_hoist:
        finestre = finestre_di_riposo(dati, segs)
        if not finestre:
            continue
        totale += min(
            max(f.t_inizio - (t + n * sol.T), (t + n * sol.T) - f.t_fine, 0.0)
            for f in finestre
            for n in giri
        )
    return totale


def test_tutti_gli_istanti(d: ProblemData):
    print("\n[8] tutti gli istanti equivalenti, non solo il primo")
    # T=50 ha DUE tratti buoni separati da un buco stretto: e' il caso che
    # smaschera chi cerca i soli estremi delle finestre e non i colmi dei
    # buchi, e li fonde in un tratto unico restituendo un istante solo.
    sol, dati = due_carroponti(d, 50.0)
    avvii = trova_avvii(dati, sol)
    check(len(avvii) > 1, f"ne trova piu' d'uno ({len(avvii)})")
    check(
        [a.t for a in avvii] == sorted(a.t for a in avvii),
        "sono in ordine di tempo crescente",
    )
    check(
        all(a.indice == i and a.totale == len(avvii) for i, a in enumerate(avvii)),
        "ciascuno sa che posto occupa e quanti sono",
    )
    check(
        len({round(a.errore, 6) for a in avvii}) == 1,
        f"sbagliano tutti uguale ({avvii[0].errore:.3f} s)",
    )
    primo = trova_avvio(dati, sol)
    check(
        primo is not None and primo.t == avvii[0].t,
        "trova_avvio da' il primo della lista, non un terzo valore",
    )

    # QUANTI sono: si campiona tutto il ciclo e si contano i tratti staccati in
    # cui l'errore sta al minimo. E' il controllo che il bug dei colmi non
    # torni: li' i tratti erano due e ne veniva fuori uno.
    n = 6000
    minimo = min(_errore_campionato(dati, sol, i * sol.T / n) for i in range(n))
    dentro = [
        _errore_campionato(dati, sol, i * sol.T / n) <= minimo + 1e-6
        for i in range(n)
    ]
    tratti = sum(
        1 for i in range(n) if dentro[i] and not dentro[(i - 1) % n]
    )  # circolare: il ciclo si richiude
    check(
        tratti == len(avvii),
        f"tanti quanti i tratti al minimo campionando il ciclo "
        f"({tratti} tratti, {len(avvii)} istanti)",
    )

    # Ogni istante deve stare in un tratto DIVERSO: due istanti nello stesso
    # tratto sarebbero lo stesso punto di avvio scritto due volte.
    def quale(t: float) -> int:
        i = int(round(t / sol.T * n)) % n
        while dentro[(i - 1) % n]:
            i = (i - 1) % n
        return i

    check(
        len({quale(a.t) for a in avvii}) == len(avvii),
        "e ciascuno sta in un tratto diverso",
    )
    check(
        all(_errore_campionato(dati, sol, a.t) <= minimo + 1e-6 for a in avvii),
        "ognuno di loro e' davvero al minimo",
    )


def main() -> int:
    d = dati_prova()
    test_stazione_di_riposo(d)
    test_finestre_sono_di_riposo(d)
    test_avvio_esatto(d)
    test_avvio_approssimato(d)
    test_gancio_alto(d)
    test_carro_senza_riposo(d)
    test_riepilogo(d)
    test_tutti_gli_istanti(d)
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
