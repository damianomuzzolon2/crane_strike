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
    python test_simulazione.py
"""

from __future__ import annotations

import tkinter as tk

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
    tanks = {
        nome: Tank(nome, pos, 1, lift_height=corsa, drain_time=scolo)
        for nome, pos, corsa, scolo in VASCHE
    }
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
        empty_hook_travels_low=gancio_basso,
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


def test_gancio_resta_giu(d: ProblemData):
    """Il gancio scarico non risale: trasla basso e alla vasca dopo ci arriva
    gia' in fondo. E' lo standard, e cambia i tempi -- non solo il disegno."""
    print("\n[11] il gancio scarico resta calato")
    sol, dati = proposta_semplice(d)
    sim = Simulazione(dati, sol)

    risalite, alto = 0, 0
    for _, ist in campioni(sim):
        for c in ist.carri:
            if c.con_pezzo or c.corsa <= 0:
                continue  # col telaio in mano il gancio sta in alto, e deve
            alto += 1
            if c.z > -0.5 * c.corsa:
                risalite += 1
    check(alto > 0, f"il gancio passa {alto} istanti scarico sopra una vasca")
    check(
        risalite == 0,
        f"e non lo si vede mai tornare in alto a vuoto ({risalite} istanti)",
    )

    # Anche traslando: e' li' che si vedeva risalire per niente.
    in_viaggio = [
        c
        for _, ist in campioni(sim, 400)
        for c in ist.carri
        if c.fase == "rientro a vuoto"
    ]
    check(
        in_viaggio and all(c.z < -0.5 * c.corsa for c in in_viaggio if c.corsa > 0),
        f"nemmeno mentre trasla da una vasca all'altra ({len(in_viaggio)} istanti)",
    )

    # E i tempi lo seguono: senza le due corse a vuoto, presa e rilascio si
    # accorciano di quel tanto, e il pezzo resta in bagno di meno.
    alto_d = dati_prova(gancio_basso=False)
    check(
        d.empty_leg_seconds(1, 2) < alto_d.empty_leg_seconds(1, 2)
        and d.bath_extra_seconds(1) == alto_d.bath_extra_seconds(1),
        f"il rientro costa {alto_d.empty_leg_seconds(1, 2):.1f} s invece di "
        f"{d.empty_leg_seconds(1, 2):.1f}, e il bagno non cambia",
    )

    # Sull'impianto in cui il gancio DEVE risalire resta il caso in cui non
    # avrebbe senso farlo: quando aspetta sulla stessa vasca per riprendere.
    from simulazione import _tratti_col_gancio_giu

    sol_a, dati_a = proposta_semplice(alto_d)
    sim_a = Simulazione(dati_a, sol_a)
    check(
        any(c.giu for c in sim_a._carri),
        f"e li' l'attesa sulla stessa vasca si fa comunque col gancio calato "
        f"({[c.giu for c in sim_a._carri]})",
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
    test_gancio_resta_giu(d)
    test_cambio_quota()
    try:
        test_finestra(d)
        test_disegno_casi_limite()
    except tk.TclError as e:
        print(f"  --   ambiente grafico non disponibile, salto la finestra ({e})")
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
