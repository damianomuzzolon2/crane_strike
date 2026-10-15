"""
test_simulazione.py
-------------------
Test della simulazione (simulazione.py).

NON richiede OR-Tools: il ciclogramma di riferimento e' quello di
`proposta_semplice`, che e' costruibile per definizione e quindi FISICAMENTE
COERENTE -- ed e' su quello che si puo' pretendere la proprieta' che conta:
ogni pezzo appeso deve stare esattamente dove sta il gancio di un carroponte
che lo tiene, e viceversa. Se la simulazione e le traiettorie del ciclogramma
raccontassero due storie diverse, una delle due sarebbe sbagliata.

Le vasche hanno CORSE VERTICALI DIVERSE una dall'altra apposta: con corse tutte
uguali un errore di attribuzione (prendere la corsa della vasca sbagliata)
darebbe comunque il risultato giusto e non si vedrebbe.

Per eseguirlo:
    python test/test_simulazione.py
"""

from __future__ import annotations

import os
import sys
import tkinter as tk

# I moduli del programma stanno nella cartella sopra questa: senza aggiungerla
# fra i percorsi di ricerca, lanciare il test da qui non li troverebbe.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib

matplotlib.use("TkAgg")

from kinematics import Kinematics
import manuale
from model import ProblemData, StationSpec, Tank, proposta_semplice
from simulazione import Simulazione

KIN_EMPTY = Kinematics(v_max=1600, a_max=900)
KIN_LOADED = Kinematics(v_max=1000, a_max=400)
KIN_LIFT_EMPTY = Kinematics(v_max=500, a_max=800)
KIN_LIFT_LOADED = Kinematics(v_max=300, a_max=500)

# posizione, corsa verticale, sgocciolamento: tutte diverse fra loro
VASCHE = [
    ("CARICO", 0.0, 0.0, 0.0),
    ("SGRASSO", 4000.0, 1200.0, 6.0),
    ("RISCIACQUO", 9000.0, 800.0, 2.0),
    ("SCARICO", 15000.0, 300.0, 0.0),
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
    svincoli. Carico e scarico restano liberi: qui si provano gli ostacoli in
    mezzo alla linea (che carico e scarico possano esserlo lo prova
    test_verify.py)."""
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


def campioni(sim: Simulazione, n=1500):
    passo = sim.durata / n
    for i in range(n + 1):
        t = i * passo
        yield t, sim.istantanea(t)


# --------------------------------------------------------------------------


def test_fasi_verticali(d: ProblemData):
    print("\n[1] le fasi verticali e i tempi di presa/rilascio sono la stessa cosa")
    ok_somma, ok_catena, ok_estremi = True, True, True
    for i in range(d.n_stations):
        h = d.lift_height_at(i)
        for fasi, atteso in (
            (d.pick_phases(i), d.pick_time_at(i)),
            (d.release_phases(i), d.release_time_at(i)),
        ):
            if abs(sum(f.duration for f in fasi) - atteso) > 1e-12:
                ok_somma = False
            # la quota non salta: dove finisce una fase comincia la successiva
            for a, b in zip(fasi, fasi[1:]):
                if abs(a.z_end - b.z_start) > 1e-9:
                    ok_catena = False
            if h > 0 and min(f.z_end for f in fasi) != -h:
                ok_estremi = False
    check(ok_somma, "la durata di presa e rilascio e' la somma delle loro fasi")
    check(ok_catena, "le fasi si attaccano una all'altra senza salti di quota")
    check(ok_estremi, "si passa sempre dal fondo corsa")

    # Col gancio che trasla basso -- lo standard -- la presa comincia da giu'
    # e il rilascio finisce giu': le due corse a vuoto non le fa nessuno.
    presa, rilascio = d.pick_phases(1), d.release_phases(1)
    h = d.lift_height_at(1)
    check(
        [f.name for f in presa] == ["aggancio", "sollevamento del telaio", "sgocciolamento"]
        and abs(presa[0].z_start + h) < 1e-9,
        f"la presa comincia col gancio gia' in fondo ({[f.name for f in presa]})",
    )
    check(
        [f.name for f in rilascio] == ["immersione del telaio", "sgancio"]
        and abs(rilascio[-1].z_end + h) < 1e-9,
        f"e il rilascio finisce li', senza risalire ({[f.name for f in rilascio]})",
    )
    # una fase si riconosce da chi tiene il telaio: e' l'unica cosa che
    # distingue il pezzo dal gancio, ed e' quella che la simulazione usa
    check(
        [f.loaded for f in presa] == [False, True, True],
        "nella presa il telaio e' appeso solo dopo l'aggancio",
    )
    check(
        [f.loaded for f in rilascio] == [True, True],
        "nel rilascio il telaio resta appeso fino allo sgancio",
    )

    # Le corse a vuoto non tornano MAI qui dentro, nemmeno sull'impianto che
    # obbliga il gancio a risalire: la' avvengono fra due mosse, sullo
    # svincolo, e le paga il rientro a vuoto.
    alto = dati_prova(gancio_basso=False)
    check(
        alto.pick_phases(1) == presa
        and alto.release_phases(1) == rilascio
        and alto.empty_leg_seconds(1, 2) > d.empty_leg_seconds(1, 2),
        f"presa e rilascio non cambiano: le corse a vuoto le paga il rientro "
        f"({alto.empty_leg_seconds(1, 2):.1f} s contro "
        f"{d.empty_leg_seconds(1, 2):.1f})",
    )


def test_segmenti_e_mosse(d: ProblemData):
    print("\n[2] ogni tratto sa a quale mossa appartiene")
    sol, dati = proposta_semplice(d)
    segs = [s for lista in sol.segments_per_hoist for s in lista]
    check(
        all(s.move is not None for s in segs if s.kind in ("pick", "loaded", "release")),
        "presa, trasporto e rilascio dichiarano la loro mossa",
    )
    check(
        all(s.move is None for s in segs if s.kind in ("wait", "empty")),
        "attesa e rientro a vuoto non sono di nessuna mossa: stanno fra due",
    )
    giuste = all(
        abs(s.x_start - dati.station_position(s.move)) < 1e-9
        for s in segs
        if s.kind == "pick"
    ) and all(
        abs(s.x_start - dati.station_position(s.move + 1)) < 1e-9
        for s in segs
        if s.kind == "release"
    )
    check(giuste, "la presa sta sulla vasca k della mossa, il rilascio sulla k+1")


def test_carro_e_pezzo(d: ProblemData):
    print("\n[3] carroponte e pezzo dicono la stessa cosa")
    sol, dati = proposta_semplice(d)
    sim = Simulazione(dati, sol)

    orfani, fantasmi, scarto = 0, 0, 0.0
    for _, ist in campioni(sim):
        appesi = [p for p in ist.pezzi if p.appeso]
        portanti = [c for c in ist.carri if c.con_pezzo]
        for p in appesi:
            vicino = min(
                (
                    abs(c.x - p.x) + abs(c.z - p.z) + abs(c.corsia - p.corsia)
                    for c in portanti
                ),
                default=None,
            )
            if vicino is None:
                orfani += 1
            else:
                scarto = max(scarto, vicino)
        for c in portanti:
            if not any(
                abs(p.x - c.x) < 1e-6
                and abs(p.z - c.z) < 1e-6
                and abs(p.corsia - c.corsia) < 1e-9
                for p in appesi
            ):
                fantasmi += 1
    check(orfani == 0, f"nessun pezzo appeso al nulla ({orfani} casi)")
    check(fantasmi == 0, f"nessun carroponte che tiene un pezzo che non c'e' ({fantasmi})")
    check(
        scarto < 1e-9,
        f"il telaio sta esattamente dove sta il gancio (scarto max {scarto:.2e} mm)",
    )


def test_corse_per_vasca(d: ProblemData):
    print("\n[4] ogni vasca ha la SUA corsa verticale")
    sol, dati = proposta_semplice(d)
    sim = Simulazione(dati, sol)

    fondo: dict[str, float] = {}
    fuori_corsa = 0
    for _, ist in campioni(sim):
        for c in ist.carri:
            if c.z > 1e-9 or c.z < -1200.0 - 1e-9:
                fuori_corsa += 1
            if c.vasca is not None:
                fondo[c.vasca] = min(fondo.get(c.vasca, 0.0), c.z)
    check(fuori_corsa == 0, "il gancio non sale sopra la quota di trasporto ne'")
    atteso = {nome: -corsa for nome, _, corsa, _ in VASCHE}
    sbagliate = {
        v: (z, atteso[v]) for v, z in fondo.items() if abs(z - atteso[v]) > 1e-6
    }
    check(
        not sbagliate,
        f"il gancio scende fino al fondo di quella vasca e non di un'altra "
        f"({sbagliate or 'tutte giuste'})",
    )


def test_periodicita(d: ProblemData):
    print("\n[5] la linea si ripete ogni takt time")
    sol, dati = proposta_semplice(d)
    sim = Simulazione(dati, sol)
    uguali = True
    for frazione in (0.0, 0.17, 0.41, 0.73, 0.95):
        t = frazione * sim.T
        a, b = sim.istantanea(t), sim.istantanea(t + sim.T)
        if [(c.carro, round(c.x, 9), round(c.z, 9)) for c in a.carri] != [
            (c.carro, round(c.x, 9), round(c.z, 9)) for c in b.carri
        ]:
            uguali = False
        if sorted((round(p.x, 9), round(p.z, 9)) for p in a.pezzi) != sorted(
            (round(p.x, 9), round(p.z, 9)) for p in b.pezzi
        ):
            uguali = False
    check(uguali, "a t e a t+T carroponti e pezzi stanno negli stessi posti")
    # e' quello che rende il ritorno a capo invisibile: la durata e' un numero
    # intero di takt, quindi la fine combacia col principio
    check(
        abs(sim.durata - sim.periodi * sim.T) < 1e-9 and sim.periodi >= 1,
        f"la durata e' un numero intero di takt ({sim.periodi} x {sim.T:.2f} s)",
    )
    check(
        sim.durata >= sim.fine_pezzo - sim.inizio_pezzo - 1e-9,
        "la durata copre la vita intera di un pezzo, dal carico allo scarico",
    )


def test_pezzo_da_seguire(d: ProblemData):
    print("\n[6] un pezzo attraversa tutta la linea")
    sol, dati = proposta_semplice(d)
    sim = Simulazione(dati, sol)
    visitate = set()
    for _, ist in campioni(sim):
        for p in ist.pezzi:
            if p.indice == 0 and p.vasca is not None:
                visitate.add(p.vasca)
    check(
        visitate == {nome for nome, *_ in VASCHE},
        f"lo stesso pezzo passa per tutte le vasche, una per una "
        f"({sorted(visitate)})",
    )
    presenti = [len(ist.pezzi) for _, ist in campioni(sim, 200)]
    check(
        min(presenti) >= 1 and max(presenti) >= 2,
        f"in linea ci sono piu' pezzi insieme ({min(presenti)}-{max(presenti)})",
    )


def test_assegnazione_parziale(d: ProblemData):
    print("\n[7] ciclogramma composto a meta'")
    T = 200.0
    perm = manuale.permanenze_iniziali(d)
    sol, dati, _ = manuale.componi(d, T, perm, {0: 0, 1: 0}, 2)
    sim = Simulazione(dati, sol)
    check(
        sim.mosse_scoperte() == [2],
        f"dice quali trasporti non fa nessuno ({sim.mosse_scoperte()})",
    )
    ist = sim.istantanea(sim.durata * 0.5)
    check(len(ist.pezzi) >= 1, "i pezzi si muovono lo stesso: si vede cosa manca")
    # i numeri dei carroponti li decide chi chiama: con un'assegnazione
    # parziale le zone vengono riempite per continuita' e non coincidono
    sim2 = Simulazione(dati, sol, carri={0: 3, 1: None})
    check(
        sim2.numeri_carri() == [3],
        f"il numero del carroponte lo detta chi chiama ({sim2.numeri_carri()})",
    )


def test_finestra(d: ProblemData):
    """La finestra viene aperta davvero e pilotata da codice.

    Si mette subito in pausa: lasciandola andare, il test starebbe li' a
    guardarla per il tempo della simulazione, e chi lo lancia si troverebbe una
    finestra viva sullo schermo -- che poi magari chiude, facendo fallire tutto
    quello che viene dopo per un motivo che non e' un difetto del programma.
    Con la pausa il tempo lo si fa avanzare un passo per volta, e in mezzo
    secondo e' finita."""
    print("\n[8] la finestra si apre, va, si ferma e si chiude")
    from simulazione import FinestraSimulazione

    sol, dati = proposta_semplice(d)
    radice = tk.Tk()
    radice.geometry("200x100")
    try:
        f = FinestraSimulazione(radice, dati, sol, titolo_linea="prova")
        radice.update()
        check(f._in_moto, "parte da sola: e' quello che si e' chiesto guardandola")
        f.avvia_o_ferma()  # da qui in poi il tempo lo muoviamo noi
        radice.update()
        check(not f._in_moto and f._lavoro is None, "il pulsante la mette in pausa")

        fermo = f.t
        f._passo()
        check(f.t == fermo, "in pausa non si muove nemmeno a insistere")

        # La finestra si apre a tempo reale: un takt time dura quanto dura,
        # altrimenti la prima impressione di quanto sia lento l'impianto e'
        # sbagliata.
        check(
            f.var_velocita.get() == "1x",
            f"la simulazione si apre a tempo reale ({f.var_velocita.get()})",
        )
        # La velocita' si mette a mano invece di contare su quella iniziale:
        # cosi' il conto qui sotto prova il MECCANISMO e non il valore
        # predefinito, che e' una scelta e puo' cambiare.
        f.var_velocita.set("5x")
        f._in_moto = True
        prima = f.t
        for _ in range(10):
            f._passo()
        atteso = prima + 10 * 5.0 * FinestraSimulazione.PASSO_MS / 1000.0
        check(
            abs(f.t - atteso) < 1e-9,
            f"dieci passi a 5x fanno {10 * 5.0 * f.PASSO_MS / 1000.0:.1f} s "
            f"({prima:.2f} -> {f.t:.2f} s)",
        )
        f.var_velocita.set("1x")
        # una sola catena di timer: chiamarlo a mano non ne fa partire un'altra
        f._passo()
        f._passo()
        check(f._lavoro is not None, "resta un solo timer in giro, non uno per passo")
        f._in_moto = False
        f._passo()

        # Le quote NON si disegnano in millimetri: un telaio immerso si mette
        # sempre alla stessa altezza, qualunque sia la corsa della vasca. Il
        # rimappaggio deve valere identico per il gancio e per il telaio,
        # altrimenti il pezzo si stacca dal bilancino -- e sarebbe un difetto
        # del solo disegno, invisibile ai controlli sulle quote vere.
        staccati, appesi = 0, 0
        for i in range(200):
            ist = f.sim.istantanea(i * f.sim.durata / 200.0)
            portanti = [(c.x, f._quota(c)) for c in ist.carri if c.con_pezzo]
            for p in ist.pezzi:
                if not p.appeso:
                    continue
                appesi += 1
                q = f._quota(p)
                if not portanti or min(
                    abs(a - p.x) + abs(b - q) for a, b in portanti
                ) > 1e-6:
                    staccati += 1
        check(
            appesi > 0 and staccati == 0,
            f"il telaio resta appeso al bilancino anche dopo il rimappaggio "
            f"delle quote ({appesi} campioni, {staccati} staccati)",
        )
        quote_in_vasca = {
            round(f._quota(p), 6)
            for i in range(200)
            for p in f.sim.istantanea(i * f.sim.durata / 200.0).pezzi
            if p.vasca is not None and not p.appeso and p.z < 0
        }
        check(
            len(quote_in_vasca) <= 1,
            f"i pezzi fermi in vasca stanno tutti alla stessa altezza "
            f"({sorted(quote_in_vasca)})",
        )

        meta = f.sim.durata / 3.0
        f.var_t.set(meta)
        f._trascinato(None)
        check(abs(f.t - meta) < 1e-9, "il cursore porta dove lo si trascina")

        # -- un fotogramma per volta, avanti e indietro ---------------------
        passo = f._fotogramma()
        f.avanti()
        f.avanti()
        check(
            abs(f.t - (meta + 2 * passo)) < 1e-9,
            f"due passi avanti fanno due fotogrammi ({2 * passo:.2f} s)",
        )
        f.indietro()
        check(
            abs(f.t - (meta + passo)) < 1e-9, "e uno indietro ne torna esattamente uno"
        )
        # il passo a mano dev'essere lo STESSO salto dell'andatura normale,
        # altrimenti le due sequenze mostrerebbero istanti diversi
        f.t = meta
        f._in_moto = True
        f._passo()
        f._in_moto = False
        f._passo()
        da_solo = f.t
        f.t = meta
        f.avanti()
        check(
            abs(f.t - da_solo) < 1e-9,
            f"e coincide con quello che fa da sola ({f.t:.3f} vs {da_solo:.3f} s)",
        )
        # -- tenendo premuto, la raffica ------------------------------------
        # Un clic secco vale un passo e basta: se `command` fosse rimasto
        # attaccato al pulsante, alla fine di ogni raffica ne farebbe uno in
        # piu' -- e un pulsante che a volte fa un passo e a volte due non si
        # controlla.
        f.t = meta
        f._inizia_raffica(+1)
        check(
            abs(f.t - (meta + passo)) < 1e-9 and f._raffica is not None,
            "premuto: un passo subito, e il timer della raffica in attesa",
        )
        f._ferma_raffica()
        check(
            abs(f.t - (meta + passo)) < 1e-9 and f._raffica is None,
            "rilasciato subito: resta un passo solo",
        )
        radice.update_idletasks()
        pendenti = set(radice.tk.call("after", "info"))
        f._inizia_raffica(-1)
        for _ in range(5):
            f._continua_raffica(-1)
        check(
            abs(f.t - (meta - 5 * passo)) < 1e-9,
            f"tenuto premuto indietro: un passo per volta, senza saltare "
            f"({f.t:.2f} s)",
        )
        f._ferma_raffica()
        radice.update_idletasks()
        orfani = set(radice.tk.call("after", "info")) - pendenti
        check(
            not orfani,
            f"e la raffica lascia UN timer solo, non uno per passo ({len(orfani)} "
            f"rimasti in giro)",
        )
        prima_del_rilascio = f.t
        radice.update()
        check(
            f._raffica is None and f.t == prima_del_rilascio,
            "e al rilascio si ferma li'",
        )

        # il giro si richiude anche all'indietro
        f.t = 0.0
        f.indietro()
        check(
            abs(f.t - (f.sim.durata - passo)) < 1e-9,
            f"indietro dall'inizio si finisce in fondo ({f.t:.2f} s)",
        )
        # e premere Avanti mentre va la mette in pausa
        f.t = meta
        f._in_moto = True
        f.btn_avvia.configure(text="Pausa")
        f.avanti()
        check(
            not f._in_moto and abs(f.t - (meta + passo)) < 1e-9,
            "premuto mentre va, il passo la ferma invece di sommarsi",
        )

        # il giro si richiude: oltre la durata si riparte da capo
        f.t = f.sim.durata - 0.01
        f._in_moto = True
        f._passo()
        f._in_moto = False
        f._passo()
        check(f.t < f.sim.durata, f"arrivato in fondo ricomincia ({f.t:.2f} s)")

        # cambiare ciclogramma mentre la finestra e' aperta
        sol2, dati2, _ = manuale.componi(
            d, 200.0, manuale.permanenze_iniziali(d), {0: 0, 1: 0}, 2
        )
        f.aggiorna(dati2, sol2)
        radice.update()
        check(
            abs(f.sim.T - 200.0) < 1e-9,
            f"rilegge il ciclogramma modificato senza riaprirsi (T={f.sim.T:.2f} s)",
        )
        check(
            "non sono assegnati" in f.avviso["text"],
            "e avvisa che un trasporto non lo fa nessuno",
        )
        # chiusa mentre un pulsante e' ancora premuto: il timer della raffica
        # continuerebbe a chiedere ridisegni su una finestra che non c'e' piu'
        f._inizia_raffica(+1)
        f.destroy()
        radice.update()
        check(
            f._lavoro is None and f._raffica is None and not f.winfo_exists(),
            "si chiude senza lasciare timer in giro, raffica compresa",
        )
    finally:
        try:
            radice.destroy()
        except Exception:
            pass


def test_vasca_a_piu_posti():
    """Una vasca a piu' posti tiene dentro piu' pezzi insieme. Disegnarli tutti
    nello stesso punto li faceva sembrare uno solo -- e succedeva proprio nelle
    vasche lente, che sono quelle per cui i posti in piu' si comprano."""
    print("\n[10] due pezzi nella stessa vasca si vedono come due")
    tanks = {
        nome: Tank(
            nome,
            pos,
            3 if nome == "SGRASSO" else 1,
            lift_height=corsa,
            drain_time=scolo,
        )
        for nome, pos, corsa, scolo in VASCHE
    }
    d = ProblemData(
        tanks=tanks,
        route=[
            StationSpec("CARICO", 0.0, 0.0),
            StationSpec("SGRASSO", 50.0, 400.0),  # lungo: ci sta piu' di un pezzo
            StationSpec("RISCIACQUO", 10.0, 400.0),
            StationSpec("SCARICO", 0.0, 0.0),
        ],
        takt_min=20.0,
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
    sol, dati = proposta_semplice(d)
    sim = Simulazione(dati, sol)

    insieme, sovrapposti, staccati = 0, 0, 0
    for _, ist in campioni(sim):
        per_vasca: dict[str, list] = {}
        for p in ist.pezzi:
            if p.vasca is not None and not p.appeso:
                per_vasca.setdefault(p.vasca, []).append(p)
        insieme = max(insieme, max((len(v) for v in per_vasca.values()), default=0))
        for pezzi in per_vasca.values():
            posti = {round(p.corsia, 9) for p in pezzi}
            if len(posti) != len(pezzi):
                sovrapposti += 1
        portanti = [c for c in ist.carri if c.con_pezzo]
        for p in ist.pezzi:
            if p.appeso and not any(
                abs(c.x - p.x) < 1e-6 and abs(c.corsia - p.corsia) < 1e-9
                for c in portanti
            ):
                staccati += 1
    check(insieme >= 2, f"la prova serve a qualcosa: fino a {insieme} pezzi in vasca")
    check(sovrapposti == 0, f"ognuno sul suo posto, mai uno sopra l'altro ({sovrapposti})")
    check(
        staccati == 0,
        f"e il carroponte si mette sul posto del pezzo che serve, altrimenti il "
        f"telaio si staccherebbe dal bilancino ({staccati})",
    )
    # I posti li detta il CICLOGRAMMA, non la capienza dichiarata: la vasca
    # qui sopra ne dichiara tre ma il ciclogramma ne usa due, e disegnare tre
    # corsie terrebbe i pezzi fuori centro per un posto che nessuno occupa.
    check(
        sim._posti[1] == 2 and dati.tank_capacity(1) == 3,
        f"i posti disegnati sono quelli usati ({sim._posti[1]}), non quelli "
        f"dichiarati ({dati.tank_capacity(1)})",
    )
    solo = [sim._corsia(j, 0) for j in range(4)]
    doppia = [sim._corsia(j, 1) for j in range(4)]
    check(solo == [0.0] * 4, f"dove il pezzo e' uno solo sta in mezzo ({solo})")
    check(
        doppia == [-0.5, 0.5, -0.5, 0.5],
        f"dove sono due si alternano sui due posti ({doppia})",
    )

    # -- il carroponte non salta da un posto all'altro --------------------
    # Il carrello sta sul posto del pezzo solo MENTRE lo tiene; fuori si sposta
    # di lato con calma. Legandolo al TRATTO invece che al telaio, fuori dalle
    # mosse valeva zero -- il centro della vasca -- e il carrello scattava:
    # appena finito un rilascio, e di nuovo passando da un pezzo al successivo
    # nella stessa vasca, dove fra i due non c'e' un istante di attesa in cui
    # spostarsi. Su una vasca a un posto solo non si vedrebbe, perche' li' il
    # centro E' il posto: e' un difetto che si vede solo qui.
    N = 4000
    passo = sim.durata / N
    peggio, quando = 0.0, 0.0
    precedente: dict[int, float] = {}
    for i in range(N + 1):
        istante = sim.durata * i / N
        for c in sim.istantanea(istante).carri:
            prima = precedente.get(c.carro)
            if prima is not None and abs(c.corsia - prima) > peggio:
                peggio, quando = abs(c.corsia - prima), istante
            precedente[c.carro] = c.corsia
    check(
        peggio < 0.1,
        f"e il carroponte non scatta da un posto all'altro: al massimo "
        f"{peggio:.3f} posti in {passo * 1000:.0f} ms (a t={quando:.1f} s)",
    )


def test_quota_continua():
    """La QUOTA DISEGNATA del gancio non salta mai.

    E' la proprieta' che mancava, e il difetto che nascondeva era grosso: il
    gancio compariva di colpo a fondo corsa all'inizio di un aggancio, dopo
    essere arrivato li' disegnato in alto. Nasce dalle postazioni SENZA CORSA
    -- il carico e lo scarico di quasi tutte le linee -- dove "il gancio e'
    calato" e "il gancio e' in alto" sono la stessa quota: chi teneva il conto
    a stati (dopo un rilascio e' giu', dopo una salita e' su) da li' in poi
    diceva il contrario del vero.

    Si guarda la FRAZIONE di discesa, cioe' quello che finisce sullo schermo, e
    non i millimetri: due quote diverse su corse diverse possono essere tutte e
    due "in fondo", e sono i millimetri a saltare senza che si veda niente."""
    print("\n[12] la quota del gancio non salta")
    for etichetta, linea in (
        ("gancio basso", dati_prova()),
        ("gancio alto", dati_prova(gancio_basso=False)),
    ):
        sol, dati = proposta_semplice(linea)
        sim = Simulazione(dati, sol)
        N = 5000
        passo = sim.durata / N
        peggio, quando, fasi = 0.0, 0.0, ("", "")
        prec: dict[int, tuple[float, str]] = {}
        for i in range(N + 1):
            istante = sim.durata * i / N
            for c in sim.istantanea(istante).carri:
                frazione = (
                    0.0
                    if c.corsa <= 0 or c.z >= 0
                    else min(1.0, -c.z / c.corsa)
                )
                prima = prec.get(c.carro)
                if prima is not None and abs(frazione - prima[0]) > peggio:
                    peggio = abs(frazione - prima[0])
                    quando, fasi = istante, (prima[1], c.fase)
                prec[c.carro] = (frazione, c.fase)
        # in un fotogramma il gancio non puo' fare tutta la corsa: un salto
        # vicino a 1 e' il difetto, il moto normale sta molto sotto
        check(
            peggio < 0.15,
            f"{etichetta}: al massimo {peggio:.3f} di corsa in "
            f"{passo * 1000:.0f} ms (a t={quando:.1f} s, {fasi[0]!r} -> "
            f"{fasi[1]!r})",
        )


def test_quota_solo_da_fermi():
    """Mentre il carroponte TRASLA la quota del gancio non cambia.

    E' la regola che tiene insieme la simulazione e il ciclogramma. Nel
    ciclogramma un tratto obliquo e' uno spostamento e un tratto piatto e'
    tutto il resto: se la simulazione facesse scendere il gancio in mezzo a una
    traslazione, chi guarda le due viste vedrebbe due macchine diverse.

    Il caso che lo mette alla prova e' una postazione SENZA CORSA -- il carico,
    lo scarico -- da cui si riparte verso una vasca che la corsa ce l'ha: il
    gancio deve scendere, e il modello non gli da' nemmeno un secondo perche'
    con la traslazione a gancio basso quelle corse sono gratis. Va messo in una
    SOSTA, che e' dove il ciclogramma mostra un tratto piatto."""
    print("\n[13] la quota cambia solo da fermi")
    from model import Segment
    from simulazione import _quote_a_vuoto

    d = dati_prova()  # CARICO a 0 senza corsa, RISCIACQUO a 9000 con 800 mm

    def giro(con_attesa: bool):
        segs = [Segment("release", 0.0, 2.0, 0.0, 0.0, None, move=0)]
        if con_attesa:
            segs.append(Segment("wait", 2.0, 3.0, 0.0, 0.0, None))
        t = segs[-1].t_end
        segs.append(Segment("empty", t, t + 7.0, 0.0, 9000.0, d.kin_empty))
        segs.append(
            Segment("pick", t + 7.0, t + 10.0, 9000.0, 9000.0, None, move=2)
        )
        quote = _quote_a_vuoto(d, segs)
        i_empty = next(i for i, s in enumerate(segs) if s.kind == "empty")
        return segs, quote, quote[i_empty]

    segs, quote, rientro = giro(con_attesa=True)
    check(
        abs(rientro[0] - rientro[1]) < 1e-9 and abs(rientro[0] - 1.0) < 1e-9,
        f"col tempo per farlo, il rientro trasla a quota costante "
        f"({rientro[0]:.3f} -> {rientro[1]:.3f})",
    )
    attesa = quote[1]
    check(
        abs(attesa[0]) < 1e-9 and abs(attesa[1] - 1.0) < 1e-9 and attesa[2] > 0,
        f"e la discesa sta tutta nella sosta ({attesa[0]:.3f} -> "
        f"{attesa[1]:.3f} su corsa {attesa[2]:.0f})",
    )

    # Senza nessuna sosta il dislivello non ha dove stare, e allora si fa
    # durante la traslazione: e' un ripiego, e va saputo.
    _, _, rientro = giro(con_attesa=False)
    check(
        abs(rientro[0]) < 1e-9 and abs(rientro[1] - 1.0) < 1e-9,
        f"senza nessuna sosta non resta che farlo traslando "
        f"({rientro[0]:.3f} -> {rientro[1]:.3f})",
    )


def test_gancio_resta_giu(d: ProblemData):
    """Il gancio scarico non risale: trasla basso e alla vasca dopo ci arriva
    gia' in fondo. E' lo standard, e cambia i tempi -- non solo il disegno."""
    print("\n[11] il gancio scarico resta calato")
    sol, dati = proposta_semplice(d)
    sim = Simulazione(dati, sol)

    # Col gancio che trasla basso non esiste NESSUNA corsa verticale a vuoto:
    # non e' una questione di disegno, e' che quei tratti il modello non li
    # emette proprio.
    tratti = [s for lista in sol.segments_per_hoist for s in lista]
    check(
        not [s for s in tratti if s.kind == "lift_empty"],
        f"nessuna corsa verticale a vuoto nel giro ({len(tratti)} tratti in "
        f"tutto)",
    )

    # E nel disegno il gancio non si alza MAI piu' di quanto serva.
    #
    # Attenzione al criterio: "mai in alto" sarebbe sbagliato. Andando verso
    # una postazione SENZA CORSA -- il carico, lo scarico -- il telaio si
    # prende alla quota di trasporto, e li' il gancio deve stare in alto per
    # forza. Il criterio giusto e' che durante un rientro la quota resti
    # compresa fra quelle dei due capi: ne' piu' in alto di quanto chieda
    # l'arrivo, ne' piu' in basso di quanto dia la partenza.
    def frazione_a_riposo(stazione: int) -> float:
        corsa = dati.corsa_verticale(stazione)
        if corsa <= 0:
            return 0.0
        return min(1.0, -dati.quota_di_riposo(stazione) / corsa)

    def stazione_in(x: float):
        for i in range(dati.n_stations):
            if abs(dati.approach_position(i) - x) < 1e-6:
                return i
        return None

    import bisect

    traiettoria = sim._carri[0]
    guardati, fuori, peggiore = 0, 0, ""
    for istante, ist in campioni(sim, 3000):
        stato = ist.carri[0]
        if stato.con_pezzo:
            continue
        tau = traiettoria.t0 + (istante - traiettoria.t0) % sim.T
        i = max(0, bisect.bisect_right(traiettoria.inizi, tau) - 1)
        s = traiettoria.segmenti[i]
        if s.kind != "empty":
            continue
        da, a = stazione_in(s.x_start), stazione_in(s.x_end)
        if da is None or a is None:
            continue
        basso = min(frazione_a_riposo(da), frazione_a_riposo(a))
        alto = max(frazione_a_riposo(da), frazione_a_riposo(a))
        f = (
            0.0
            if stato.corsa <= 0 or stato.z >= 0
            else min(1.0, -stato.z / stato.corsa)
        )
        guardati += 1
        if not (basso - 1e-6 <= f <= alto + 1e-6):
            fuori += 1
            peggiore = (
                f"a t={istante:.1f} frazione {f:.3f} fuori da "
                f"[{basso:.3f}, {alto:.3f}]"
            )
    check(
        guardati > 0 and fuori == 0,
        f"e traslando a vuoto non si alza mai piu' del necessario "
        f"({guardati} istanti guardati, {fuori} fuori posto"
        + (f": {peggiore}" if peggiore else "")
        + ")",
    )

    # E i tempi lo seguono: senza le due corse a vuoto, presa e rilascio si
    # accorciano di quel tanto, e il pezzo resta in bagno di meno.
    alto_d = dati_prova(gancio_basso=False)
    check(
        d.empty_leg_seconds(1, 2) < alto_d.empty_leg_seconds(1, 2)
        and d.slot_occupancy_seconds(1, 50.0)
        == alto_d.slot_occupancy_seconds(1, 50.0),
        f"il rientro costa {alto_d.empty_leg_seconds(1, 2):.1f} s invece di "
        f"{d.empty_leg_seconds(1, 2):.1f}, e il posto occupato non cambia",
    )

    # ASPETTANDO SOPRA UNA VASCA IL GANCIO STA IN FONDO, e vale anche
    # sull'impianto in cui il gancio DEVE risalire per traslare: fermo li' non
    # ha nessun motivo di alzarsi. Si controlla la PROPRIETA' e non il
    # meccanismo che la produce -- per un periodo c'era un correttivo apposta,
    # poi le corse a vuoto sono passate nel rientro e il correttivo e' rimasto
    # solo a staccare il gancio di un dito dal telaio, cosa che il carroponte
    # non fa. Scritto cosi', il test regge a tutte e due le versioni.
    for etichetta, linea in (("gancio basso", d), ("gancio alto", alto_d)):
        sol_x, dati_x = proposta_semplice(linea)
        sim_x = Simulazione(dati_x, sol_x)
        alzate = []
        for _, ist in campioni(sim_x, 2000):
            for c in ist.carri:
                # solo l'attesa FERMO SOPRA UNA VASCA, col gancio scarico
                if c.con_pezzo or c.corsa <= 0 or c.vasca is None:
                    continue
                if c.fase.startswith("attesa") and c.z > -c.corsa + 1e-6:
                    alzate.append((c.fase, round(c.z / c.corsa, 3)))
        check(
            not alzate,
            f"{etichetta}: aspettando sopra una vasca il gancio resta a fondo "
            f"corsa ({len(alzate)} istanti alzato"
            + (f", es. {alzate[0]}" if alzate else "")
            + ")",
        )


def test_disegno_casi_limite():
    """Il disegno ha una geometria tutta sua -- profondita' delle vasche,
    altezza della trave, larghezza del carrello -- ricavata dai dati. Su una
    linea normale funziona; il momento in cui si rompe e' quando un dato che
    fa da divisore o da massimo vale zero, e sono tutti casi ammessi."""
    print("\n[9] linee che il disegno potrebbe non digerire")
    from simulazione import FinestraSimulazione

    radice = tk.Tk()
    radice.geometry("200x100")
    try:
        # nessuna corsa verticale da nessuna parte: nessuna vasca vera, solo
        # postazioni, e nessuna quota da cui ricavare l'altezza del disegno
        piatta = ProblemData(
            tanks={
                nome: Tank(nome, pos, 1, lift_height=0.0, drain_time=0.0)
                for nome, pos, _, _ in VASCHE
            },
            route=[
                StationSpec("CARICO", 0.0, 0.0),
                StationSpec("SGRASSO", 60.0, 400.0),
                StationSpec("SCARICO", 0.0, 0.0),
            ],
            takt_min=40.0,
            takt_max=400.0,
            kin_empty=KIN_EMPTY,
            kin_loaded=KIN_LOADED,
            hoist_extent_pos=0.0,  # e nemmeno un ingombro da disegnare
            hoist_extent_neg=0.0,
            safety_distance=0.0,
        )
        sol, dati = proposta_semplice(piatta)
        f = FinestraSimulazione(radice, dati, sol)
        f.avvia_o_ferma()
        radice.update()
        check(True, "corse verticali e ingombri tutti a zero: si disegna lo stesso")
        f.destroy()

        # tutte le tappe sulla stessa posizione: non c'e' una spaziatura da
        # cui ricavare la larghezza delle vasche
        ferma = ProblemData(
            tanks={"UNICA": Tank("UNICA", 5000.0, 3, lift_height=900.0, drain_time=1.0)},
            route=[
                StationSpec("UNICA", 0.0, 0.0),
                StationSpec("UNICA", 30.0, 400.0),
                StationSpec("UNICA", 0.0, 0.0),
            ],
            takt_min=40.0,
            takt_max=400.0,
            kin_empty=KIN_EMPTY,
            kin_loaded=KIN_LOADED,
            hoist_extent_pos=500.0,
            hoist_extent_neg=700.0,
            safety_distance=600.0,
            kin_lift_empty=KIN_LIFT_EMPTY,
            kin_lift_loaded=KIN_LIFT_LOADED,
        )
        sol, dati = proposta_semplice(ferma)
        f = FinestraSimulazione(radice, dati, sol)
        f.avvia_o_ferma()
        radice.update()
        check(True, "tutte le tappe nella stessa vasca: si disegna lo stesso")
        f.destroy()
        radice.update()
    finally:
        try:
            radice.destroy()
        except Exception:
            pass


def test_cambio_quota():
    """Con una zona di CAMBIO QUOTA il carroponte, durante la presa, non sta
    fermo: esce dal punto di cambio quota, va alla stazione e torna. La
    simulazione lo deve mostrare -- ed e' il caso in cui il telaio rischia di
    staccarsi dal bilancino, perche' adesso si sposta anche lui."""
    print("\n[10] zone di cambio quota")
    import dataclasses

    from model import ZonaCambioQuota

    base = dati_prova()
    tanks = dict(base.tanks)
    for nome in ("CARICO", "SCARICO"):
        tanks[nome] = dataclasses.replace(tanks[nome], lift_height=0.0, drain_time=0.0)
    d = dataclasses.replace(
        base,
        tanks=tanks,
        cambio_quota_carico=ZonaCambioQuota(2000.0, 500.0, 1700.0, 2600.0),
        cambio_quota_scarico=ZonaCambioQuota(12000.0, 300.0, 1500.0, 2600.0),
    )
    sol, dati = proposta_semplice(d)
    sim = Simulazione(dati, sol)

    # -- il carroponte ci va davvero, e ci torna -------------------------
    x_min, x_max, quote_carico = None, None, []
    fasi = set()
    orfani, scarto = 0, 0.0
    for _, ist in campioni(sim, 2000):
        for c in ist.carri:
            fasi.add(c.fase)
            if x_min is None or c.x < x_min:
                x_min = c.x
            if x_max is None or c.x > x_max:
                x_max = c.x
            if abs(c.x) < 1e-6:
                quote_carico.append(c.z)
        appesi = [p for p in ist.pezzi if p.appeso]
        portanti = [c for c in ist.carri if c.con_pezzo]
        for p in appesi:
            vicino = min(
                (
                    abs(c.x - p.x) + abs(c.z - p.z) + abs(c.corsia - p.corsia)
                    for c in portanti
                ),
                default=None,
            )
            if vicino is None:
                orfani += 1
            else:
                scarto = max(scarto, vicino)

    check(
        abs(x_min) < 1e-6 and abs(x_max - 15000.0) < 1e-6,
        f"il carroponte arriva fino al carico e allo scarico "
        f"({x_min:.0f} - {x_max:.0f} mm), non si ferma ai punti di cambio quota",
    )
    check(
        {"traslazione alla stazione", "traslazione al cambio quota"} <= fasi,
        f"e le due traslazioni del giro si vedono per quello che sono ({sorted(fasi & {'traslazione alla stazione', 'traslazione al cambio quota'})})",
    )
    # sopra il carico il gancio sta fra le due quote intermedie, mai in cima
    # e mai in fondo: e' li' che il giro serve
    z = d.cambio_quota_carico
    check(
        quote_carico
        and min(quote_carico) >= z.z_int1 - 1e-6
        and max(quote_carico) <= z.z_int2 + 1e-6,
        f"sopra il carico il gancio resta fra intermediate1 e intermediate2 "
        f"({min(quote_carico):.0f} .. {max(quote_carico):.0f} mm su "
        f"{z.z_int1:.0f} .. {z.z_int2:.0f})",
    )

    # -- e il telaio resta appeso al gancio anche mentre traslano insieme --
    check(orfani == 0, f"nessun pezzo appeso al nulla ({orfani} casi)")
    check(
        scarto < 1e-9,
        f"il telaio sta esattamente dove sta il gancio, giro compreso "
        f"(scarto max {scarto:.2e} mm)",
    )

    # -- il piano di carico sta dove il telaio ci viene posato -------------
    # Con una zona di cambio quota il telaio si posa a intermediate1, non alla
    # quota di trasporto. Un piano lasciato in alto lo faceva sembrare infilato
    # dentro alla postazione, con le funi del carroponte che ci passavano
    # attraverso. Si controlla sulle COORDINATE DISEGNATE, che e' dove il
    # difetto si vedeva: sulle quote vere non c'era niente di sbagliato.
    radice = tk.Tk()
    radice.withdraw()
    try:
        from simulazione import FinestraSimulazione

        f = FinestraSimulazione(radice, dati, sol)
        f.update()
        for verso, stazione, zona in (
            ("carico", 0, d.cambio_quota_carico),
            ("scarico", d.n_stations - 1, d.cambio_quota_scarico),
        ):
            y = d.station_position(stazione)
            piano = f.quote_postazioni.get(y)
            posa = f._quota_disegnata(zona.z_int1, zona.corsa_totale)
            check(
                piano is not None and piano < -1e-9,
                f"il piano di {verso} non e' piu' alla quota di trasporto "
                f"({piano if piano is None else round(piano, 1)})",
            )
            check(
                piano is not None and abs(piano - (posa - f.altezza_telaio)) < 1e-9,
                f"e sta giusto sotto al telaio posato "
                f"(piano {piano:.1f}, telaio {posa:.1f})",
            )
        f.destroy()

        # Senza zone di cambio quota il telaio si posa alla quota di trasporto,
        # e il piano gli sta giusto sotto: la regola e' la stessa, cambia solo
        # dove il telaio viene posato.
        sol_n, dati_n = proposta_semplice(dati_prova())
        g = FinestraSimulazione(radice, dati_n, sol_n)
        g.update()
        y0 = dati_n.station_position(0)
        check(
            abs(g.quote_postazioni.get(y0, 9e9) + g.altezza_telaio) < 1e-9,
            f"senza cambio quota il piano sta sotto al telaio posato alla "
            f"quota di trasporto ({g.quote_postazioni.get(y0)})",
        )
        g.destroy()

        # CARICO e SCARICO non sono bagni nemmeno quando hanno una corsa
        # verticale -- e ce l'hanno, su parecchi impianti: il telaio scende su
        # una rulliera, su un cavalletto, dentro una fossa. Il discriminante
        # era la sola corsa, e li' disegnava una vasca piena di bagno.
        import dataclasses as _dc

        tanks = dict(dati_n.tanks)
        for nome in ("CARICO", "SCARICO"):
            tanks[nome] = _dc.replace(tanks[nome], lift_height=600.0)
        con_corsa = _dc.replace(dati_n, tanks=tanks)
        sol_c, dati_c = proposta_semplice(con_corsa)
        h = FinestraSimulazione(radice, dati_c, sol_c)
        h.update()
        estremi = [dati_c.station_position(0), dati_c.station_position(-1)]
        check(
            all(y in h.quote_postazioni for y in estremi),
            f"carico e scarico con una corsa restano POSTAZIONI, non vasche "
            f"({sorted(h.quote_postazioni)})",
        )
        # e il loro piano scende dove il telaio viene posato davvero
        atteso = h._quota_disegnata(
            dati_c.quota_di_riposo(0), dati_c.corsa_verticale(0)
        )
        check(
            abs(h.quote_postazioni[estremi[0]] - (atteso - h.altezza_telaio)) < 1e-9
            and h.quote_postazioni[estremi[0]] < -h.altezza_telaio,
            f"e il piano li segue in basso ({h.quote_postazioni[estremi[0]]:.0f} "
            f"su telaio {atteso:.0f})",
        )
        h.destroy()
    except tk.TclError as e:
        print(f"  --   ambiente grafico non disponibile, salto il disegno ({e})")
    finally:
        radice.destroy()


def test_misure_dichiarate():
    """Larghezza e altezza di vasche e pezzo non servono a calcolare niente:
    servono a disegnare. Il controllo e' che finiscano DAVVERO nel disegno --
    in millimetri veri dove l'asse e' in millimetri, e come rapporto dove non
    lo e' -- e che senza di loro non cambi niente rispetto a prima."""
    print("\n[14] le misure dichiarate finiscono nel disegno")
    import dataclasses

    from simulazione import FinestraSimulazione

    base = dati_prova()
    # Larghezze DIVERSE fra loro: con misure tutte uguali, prendere la vasca
    # sbagliata darebbe comunque il risultato giusto.
    # Larghe abbastanza da tenere dentro i due pezzi che il ciclogramma ci
    # mette: in una vasca troppo stretta i pezzi si sovrappongono e sporgono,
    # ed e' giusto cosi' -- e' quello che dicono i dati -- ma non e' quello che
    # si sta provando qui.
    misure = {"SGRASSO": (2400.0, 1500.0), "RISCIACQUO": (2800.0, 1000.0)}
    tanks = {
        nome: (
            dataclasses.replace(t, larghezza=misure[nome][0], altezza=misure[nome][1])
            if nome in misure
            else t
        )
        for nome, t in base.tanks.items()
    }
    con = dataclasses.replace(
        base, tanks=tanks, larghezza_pezzo=1200.0, altezza_pezzo=750.0
    )
    radice = tk.Tk()
    radice.withdraw()
    try:
        sol, dati = proposta_semplice(con)
        f = FinestraSimulazione(radice, dati, sol)
        # Ferma, come in tutti gli altri test: la finestra parte animandosi da
        # sola, e con due finestre aperte che si ridisegnano ogni pochi
        # millisecondi la coda degli eventi non si svuota mai -- `update()`
        # non torna piu' e la suite resta appesa, con la simulazione che
        # ricomincia da capo all'infinito. E' successo, proprio qui.
        if f._in_moto:
            f.avvia_o_ferma()
        f.update()
        larghezze = {
            dati.tanks[n].position: round(f.larghezze[dati.tanks[n].position])
            for n in misure
        }
        check(
            larghezze == {dati.tanks[n].position: round(misure[n][0]) for n in misure},
            f"ogni vasca e' larga quanto dichiara ({larghezze})",
        )
        # I pezzi devono restare DENTRO la vasca che li contiene. Lo
        # spostamento fra i posti e' comandato dalla vasca apposta: legandolo
        # alla larghezza del pezzo, i telai uscivano dalle vasche.
        fuori = []
        for passo in range(60):
            istante = f.sim.istantanea(f.sim.durata * passo / 59.0)
            for p in istante.pezzi:
                if p.appeso or p.vasca not in misure:
                    continue
                centro = dati.tanks[p.vasca].position
                scarto = abs(f._ascissa(p) - centro) + 1200.0 / 2
                if scarto > misure[p.vasca][0] / 2 + 1e-6:
                    fuori.append((p.vasca, round(scarto - misure[p.vasca][0] / 2)))
        check(
            not fuori,
            f"nessun pezzo esce dalla vasca in cui sta ({fuori[:3]})",
        )
        # E lo spostamento lo comanda la VASCA: un pezzo piu' largo non allarga
        # lo spazio disponibile. Legandolo al pezzo, i telai uscivano dalle
        # vasche -- il difetto che il controllo qui sopra ha trovato.
        largo = dataclasses.replace(con, larghezza_pezzo=2000.0)
        sol_l, dati_l = proposta_semplice(largo)
        q = FinestraSimulazione(radice, dati_l, sol_l)
        if q._in_moto:
            q.avvia_o_ferma()
        q.update()
        check(
            abs(q.passo_corsia - f.passo_corsia) < 1e-9,
            f"lo spostamento fra i posti non cambia col pezzo, perche' lo "
            f"decide la vasca ({q.passo_corsia:.0f} contro {f.passo_corsia:.0f} mm)",
        )
        q.destroy()
        # In verticale conta il RAPPORTO: il pezzo riempie la vasca sul disegno
        # quanto la riempie davvero.
        profonda = f.bordo_vasca - f.fondo_vasca
        check(
            abs(f.altezza_telaio / profonda - 750.0 / 1500.0) < 1e-9,
            f"il telaio riempie la vasca quanto il pezzo riempie la sua "
            f"({f.altezza_telaio / profonda:.3f} contro {750.0 / 1500.0:.3f})",
        )
        # e il simbolo disegnato, riportato in millimetri, e' il pezzo vero.
        # Si misura come lo disegna matplotlib, normalizzazione del simbolo
        # compresa: ricalcolandolo a mano senza, il test passava mentre sullo
        # schermo il telaio usciva rimpicciolito.
        import numpy as np
        from matplotlib.markers import MarkerStyle

        def misura_disegnata(finestra):
            punti_per_pixel = 72.0 / finestra.figura.get_dpi()
            (x0, y0), (x1, y1) = finestra.assi.transData.transform(
                [(0.0, 0.0), (1.0, 1.0)]
            )
            stile = MarkerStyle(finestra.pezzi_disegnati.get_marker())
            vertici = stile.get_transform().transform(stile.get_path().vertices)
            vertici = vertici * finestra.pezzi_disegnati.get_markersize()
            larghezza = np.ptp(vertici[:, 0]) / (abs(x1 - x0) * punti_per_pixel)
            altezza = np.ptp(vertici[:, 1]) / (abs(y1 - y0) * punti_per_pixel)
            return larghezza, altezza

        # Due inquadrature: la linea intera, dove il telaio sullo schermo e'
        # piu' alto che largo, e uno zoom stretto, dove e' piu' largo che alto.
        # Il difetto stava in una sola delle due.
        sinistra, destra = f.assi.get_xlim()
        for nome, limiti in (
            ("linea intera", (sinistra, destra)),
            ("zoom", (dati.tanks["SGRASSO"].position - 1500.0,
                      dati.tanks["SGRASSO"].position + 1500.0)),
        ):
            f.assi.set_xlim(*limiti)
            f._misura_il_pezzo()
            larghezza_mm, altezza_mm = misura_disegnata(f)
            check(
                abs(larghezza_mm - 1200.0) < 1.0
                and abs(altezza_mm - f.altezza_telaio) < 1.0,
                f"{nome}: il simbolo del telaio misura quanto il pezzo "
                f"({larghezza_mm:.0f} mm di larghezza, {altezza_mm:.0f} di altezza)",
            )
        f.assi.set_xlim(sinistra, destra)
        f.destroy()

        # -- e senza le misure si torna alle convenzioni di prima -----------
        sol_s, dati_s = proposta_semplice(base)
        g = FinestraSimulazione(radice, dati_s, sol_s)
        if g._in_moto:
            g.avvia_o_ferma()
        g.update()
        corse =[dati_s.lift_height_at(i) for i in range(dati_s.n_stations)]
        check(
            len(set(round(v, 6) for v in g.larghezze.values())) == 1
            and abs(g.altezza_telaio - 0.11 * max(corse)) < 1e-9
            and g.pezzi_disegnati.get_markersize() == 22,
            f"senza misure: vasche tutte uguali, telaio convenzionale "
            f"({sorted({round(v) for v in g.larghezze.values()})}, "
            f"{g.altezza_telaio:.0f})",
        )
        g.destroy()
    finally:
        radice.destroy()


def test_vasca_fuori_percorso():
    """Una vasca dichiarata ma che il percorso salta sta comunque sulla linea:
    si disegna, ma sbiadita, e senza il pelo mosso del bagno."""
    print("\n[15] vasche fuori dal percorso")
    from simulazione import _ALFA_FUORI_PERCORSO, FinestraSimulazione

    base = dati_prova()
    dati_f = ProblemData(
        tanks=base.tanks,
        route=[s for s in base.route if s.tank_id != "RISCIACQUO"],
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
    pos = base.tanks["RISCIACQUO"].position
    radice = tk.Tk()
    radice.geometry("200x100")
    try:
        sol, dati = proposta_semplice(dati_f)
        f = FinestraSimulazione(radice, dati, sol)
        f.update()
        check(
            f.posizioni_fuori_percorso == {pos},
            f"la vasca saltata e' riconosciuta ({f.posizioni_fuori_percorso})",
        )
        sbiadite = [
            p for p in f.assi.patches
            if p.get_alpha() == _ALFA_FUORI_PERCORSO
            and abs(p.get_x() + p.get_width() / 2 - pos) < 1e-6
        ]
        check(len(sbiadite) == 2, f"vasca e bagno disegnati sbiaditi ({len(sbiadite)})")
        etichette = [t.get_text() for t in f.assi.get_xticklabels()]
        check("RISCIACQUO" in etichette, "la vasca ha la sua etichetta")
        f.destroy()
    finally:
        radice.destroy()


def main() -> int:
    d = dati_prova()
    test_fasi_verticali(d)
    test_segmenti_e_mosse(d)
    test_carro_e_pezzo(d)
    test_corse_per_vasca(d)
    test_periodicita(d)
    test_pezzo_da_seguire(d)
    test_assegnazione_parziale(d)
    test_vasca_a_piu_posti()
    test_quota_continua()
    test_quota_solo_da_fermi()
    test_gancio_resta_giu(d)
    test_cambio_quota()
    try:
        test_finestra(d)
        test_disegno_casi_limite()
        test_misure_dichiarate()
        test_vasca_fuori_percorso()
    except tk.TclError as e:
        print(f"  --   ambiente grafico non disponibile, salto la finestra ({e})")
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
