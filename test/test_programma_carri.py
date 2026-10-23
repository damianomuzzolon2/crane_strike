"""
test_programma_carri.py
-----------------------
Test del programma dei carri: il ciclogramma tradotto nei passi del PLC
(Lifting, Transfer, Dripping, Pause, External Request, Crane Syncro,
End Program). Non richiede OR-Tools: le soluzioni si costruiscono a mano, come
in test_verify.py.

Per eseguirlo:
    python test/test_programma_carri.py
"""

from __future__ import annotations

import dataclasses
import os
import sys
import tempfile

# I moduli del programma stanno nella cartella sopra questa: senza aggiungerla
# fra i percorsi di ricerca, lanciare il test da qui non li troverebbe.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from avvio import Avvio, finestre_di_riposo, trova_avvio
from model import HoistZone, ZonaCambioQuota, build_solution
from programma_carri import (
    CRANE_SYNCRO,
    DRIPPING,
    END_PROGRAM,
    EXTERNAL_REQUEST,
    LIFTING,
    PAUSE,
    TRANSFER,
    TRANSFER_INLET,
    TRANSFER_OUTLET,
    TRASFERIMENTI,
    programma_carri,
)
from test_verify import (
    KIN_LIFT_EMPTY,
    KIN_LIFT_LOADED,
    _con_ostacoli,
    make_data,
    reference_case,
)
from verify import verify_solution

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


# --------------------------------------------------------------------------
# Casi
# --------------------------------------------------------------------------


def caso_interbloccato():
    """Il caso di riferimento di test_verify con l'interblocco acceso, e il
    carroponte 2 che aspetta in V4 invece che sulla vasca comune: e' la
    variante che l'interblocco lo rispetta (vedi `test_interblocco` la')."""
    data, sol = reference_case()
    con = dataclasses.replace(data, interblocco=True)
    p2 = sol.plans[1]
    attesa = p2.local_pick[2] + sol.T - con.empty_leg_seconds(4, 2) - p2.finish[3]
    giusta = build_solution(
        con,
        sol.T,
        local_pick={**sol.plans[0].local_pick, **p2.local_pick},
        status="OPTIMAL",
        attese={**sol.plans[0].attese, 3: attesa},
    )
    return con, giusta


def giro_unico(data):
    """Un carroponte solo che fa tutte le mosse di fila, 40 s in ogni vasca,
    e torna al carico: un giro sempre possibile, qualunque sia la linea."""
    lp = {0: 0.0}
    for k in range(1, data.n_moves):
        lp[k] = lp[k - 1] + data.loaded_leg_seconds(k - 1) + 40.0
    ultima = data.n_moves - 1
    T = (
        lp[ultima]
        + data.loaded_leg_seconds(ultima)
        + data.empty_leg_seconds(data.n_stations - 1, 0)
        + 10.0
    )
    return build_solution(data, T, local_pick=lp, status="OPTIMAL")


def linea_verticale(**kw):
    """Tre vasche di processo con corsa verticale e sgocciolamento fra carico
    e scarico, che non ne hanno; un carroponte."""
    data = make_data(
        positions=[0, 5000, 10000, 15000, 20000],
        dwells=[(0, 0), (30, 90), (30, 90), (30, 90), (0, 0)],
        zones=[HoistZone(0, 3)],
        lift_height=1000,
        drain_time=5,
        kin_lift_loaded=KIN_LIFT_LOADED,
        kin_lift_empty=KIN_LIFT_EMPTY,
        **kw,
    )
    tanks = dict(data.tanks)
    for v in ("V0", "V4"):
        tanks[v] = dataclasses.replace(tanks[v], lift_height=0, drain_time=0)
    return dataclasses.replace(data, tanks=tanks)


def comandi(passi) -> list[str]:
    return [p.comando for p in passi]


def prima_di(passi, i: int):
    """I comandi che precedono il passo i (0-based) fino al movimento prima."""
    out = []
    j = i - 1
    while j >= 0 and passi[j].comando in (EXTERNAL_REQUEST, CRANE_SYNCRO):
        out.append(passi[j])
        j -= 1
    return out[::-1]


# --------------------------------------------------------------------------
# Test
# --------------------------------------------------------------------------


def test_formato():
    print("\n[1] i passi sono comandi del PLC, con parametri del PLC")
    data, sol = caso_interbloccato()
    check(verify_solution(data, sol).ok, "il caso di partenza supera la verifica")
    pc = programma_carri(data, sol, trova_avvio(data, sol))
    check(len(pc.programmi) == 2, "un programma per carro")
    noti = {LIFTING, *TRASFERIMENTI, DRIPPING, PAUSE, EXTERNAL_REQUEST, CRANE_SYNCRO, END_PROGRAM}
    for h, passi in enumerate(pc.programmi):
        check(
            comandi(passi).count(END_PROGRAM) == 1 and passi[-1].comando == END_PROGRAM,
            f"carro {h + 1}: End Program una volta sola, in fondo",
        )
        check(set(comandi(passi)) <= noti, f"carro {h + 1}: solo comandi noti")
        check(
            all(p.param2 in (9, 10) for p in passi if p.comando in (LIFTING, *TRASFERIMENTI)),
            f"carro {h + 1}: velocita' 9 o 10 su Lifting e Transfer",
        )
        check(
            all(str(p.param1).startswith("Pos.") for p in passi
                if p.comando in (LIFTING, *TRASFERIMENTI)),
            f"carro {h + 1}: le posizioni si chiamano Pos.<...>",
        )
        check(
            all(isinstance(p.param1, int) and p.param1 > 0 for p in passi
                if p.comando in (PAUSE, DRIPPING)),
            f"carro {h + 1}: pause e sgocciolamenti in secondi interi",
        )
        check(
            all(isinstance(v, (int, str)) for p in passi for v in p.riga()),
            f"carro {h + 1}: nessun numero con la virgola nel foglio",
        )


def test_trasporti_e_tempi():
    print("\n[2] un Transfer carico per mossa, e le pause fanno il tempo che avanza")
    data, sol = caso_interbloccato()
    pc = programma_carri(data, sol)
    for h, (passi, segs, z) in enumerate(
        zip(pc.programmi, sol.segments_per_hoist, data.zones)
    ):
        carichi = [p for p in passi if p.comando == TRANSFER and p.param2 == 9]
        check(
            [p.param1 for p in carichi]
            == [f"Pos.{data.route[k + 1].tank_id}" for k in sol.plans[h].order],
            f"carro {h + 1}: i trasporti col pezzo vanno alle vasche del percorso "
            f"({[p.param1 for p in carichi]})",
        )
        attese = sum(s.t_end - s.t_start for s in segs if s.kind == "wait")
        pause = sum(p.param1 for p in passi if p.comando == PAUSE)
        check(
            abs(pause - attese) <= 1,
            f"carro {h + 1}: le pause arrotondate sommano {pause} s per "
            f"{attese:.2f} s di attese (il resto si riporta)",
        )


def test_external_request():
    print("\n[3] External Request prima di andare al carico e allo scarico")
    data, sol = caso_interbloccato()
    pc = programma_carri(data, sol)
    uno, due = pc.programmi
    i_carico = next(i for i, p in enumerate(uno)
                    if p.comando == TRANSFER and p.param1 == "Pos.V0")
    check(
        EXTERNAL_REQUEST in comandi(prima_di(uno, i_carico)),
        "carro 1: prima di tornare al carico",
    )
    i_scarico = next(i for i, p in enumerate(due)
                     if p.comando == TRANSFER and p.param1 == "Pos.V4")
    check(
        EXTERNAL_REQUEST in comandi(prima_di(due, i_scarico)),
        "carro 2: prima di portare il pezzo allo scarico",
    )
    check(
        comandi(uno).count(EXTERNAL_REQUEST) == 1
        and comandi(due).count(EXTERNAL_REQUEST) == 1,
        "e da nessun'altra parte",
    )
    altri = [
        p for passi in pc.programmi for i, p in enumerate(passi)
        if p.comando == TRANSFER and p.param1 not in ("Pos.V0", "Pos.V4")
        and EXTERNAL_REQUEST in comandi(prima_di(passi, i))
    ]
    check(not altri, "nessuna richiesta davanti alle vasche di processo")


def test_crane_syncro():
    print("\n[4] Crane Syncro prima di entrare nella vasca comune")
    data, sol = caso_interbloccato()
    pc = programma_carri(data, sol, trova_avvio(data, sol))
    check(not pc.note, f"nessuna nota su un ciclogramma che rispetta l'interblocco {pc.note}")
    for h, passi in enumerate(pc.programmi):
        altro = pc.programmi[1 - h]
        verso_v2 = [i for i, p in enumerate(passi)
                    if p.comando == TRANSFER and p.param1 == "Pos.V2"]
        check(len(verso_v2) == 1, f"carro {h + 1}: entra in V2 una volta per giro")
        sync = [p for p in prima_di(passi, verso_v2[0]) if p.comando == CRANE_SYNCRO]
        check(
            len(sync) == 1 and sync[0].param1 == 2 - h,
            f"carro {h + 1}: prima aspetta il carro {2 - h}",
        )
        if not sync:
            continue
        n = sync[0].param2
        arrivo = altro[n - 2] if n > 1 else [p for p in altro if p.comando == TRANSFER][-1]
        check(
            arrivo.comando == TRANSFER and arrivo.param1 != "Pos.V2",
            f"carro {h + 1}: il passo {n} del carro {2 - h} viene subito dopo "
            f"il suo arrivo su un'altra vasca ({arrivo.comando} {arrivo.param1})",
        )
        # e quel passo il carro vicino lo raggiunge davvero PRIMA che questo
        # parta: il Crane Syncro e' gia' soddisfatto dal ciclogramma
        T = sol.T
        t_partenza = passi[verso_v2[0]].t
        t_uscita = arrivo.t + arrivo.durata
        check(
            0 <= (t_partenza - t_uscita) % T < T / 2,
            f"carro {h + 1}: il vicino e' uscito {(t_partenza - t_uscita) % T:.1f} s "
            f"prima che parta",
        )
    tot = sum(comandi(p).count(CRANE_SYNCRO) for p in pc.programmi)
    check(tot == 2, f"due Crane Syncro in tutto, uno per carro ({tot})")

    # senza interblocco non ci sono passi a cui sincronizzarsi, e lo si dice
    spento = dataclasses.replace(data, interblocco=False)
    pc = programma_carri(spento, sol)
    check(
        all(CRANE_SYNCRO not in comandi(p) for p in pc.programmi),
        "interblocco spento: nessun Crane Syncro",
    )
    check(
        any("Interblocco" in n for n in pc.note),
        "e una nota lo spiega",
    )

    # un ciclogramma che l'interblocco lo viola: il Crane Syncro c'e' lo
    # stesso, ma la nota avverte che il PLC fara' aspettare
    rotto_data, rotto = reference_case()
    rotto_data = dataclasses.replace(rotto_data, interblocco=True)
    pc = programma_carri(rotto_data, rotto)
    check(
        any("non rispetta l'interblocco" in n for n in pc.note),
        f"ciclogramma che viola l'interblocco: segnalato ({len(pc.note)} note)",
    )


def _comincia_da(passi, t: float, T: float) -> bool:
    """Se il programma comincia all'istante `t`: con un'attesa che parte
    proprio li', o col primo passo che viene dopo."""
    primo = passi[0]
    if primo.comando == PAUSE:
        scarto = (primo.t - t) % T
        return scarto < 0.01 or scarto > T - 0.01
    dopo = [(p.t - t) % T for p in passi[:-1] if p.comando != PAUSE]
    return abs((primo.t - t) % T - min(dopo)) < 1e-9


def _a_riposo(data, segs, t: float, T: float) -> bool:
    return any(
        (t - f.t_inizio) % T <= f.t_fine - f.t_inizio
        for f in finestre_di_riposo(data, segs)
    )


def test_avvio():
    print("\n[5] il passo 1: l'istante di avvio, o il primo riposo dopo")
    data, sol = caso_interbloccato()
    avvio = trova_avvio(data, sol)
    check(avvio.esatto, "nel caso di prova l'avvio e' esatto: tutti a riposo")
    senza = programma_carri(data, sol)
    con = programma_carri(data, sol, avvio)
    T = sol.T
    for h, (a, b) in enumerate(zip(senza.programmi, con.programmi)):
        movimenti_a = [(p.comando, p.param1) for p in a if p.comando not in (PAUSE, CRANE_SYNCRO)]
        movimenti_b = [(p.comando, p.param1) for p in b if p.comando not in (PAUSE, CRANE_SYNCRO)]
        check(
            sorted(map(str, movimenti_a)) == sorted(map(str, movimenti_b)),
            f"carro {h + 1}: gli stessi passi, in un altro ordine",
        )
        check(
            _comincia_da(b, avvio.t, T),
            f"carro {h + 1}: a riposo all'avvio, comincia da {avvio.t:.2f} s "
            f"({b[0].comando} {b[0].param1})",
        )
        check(
            abs(sum(p.param1 for p in a if p.comando == PAUSE)
                - sum(p.param1 for p in b if p.comando == PAUSE)) <= 1,
            f"carro {h + 1}: un'attesa spezzata dall'avvio non perde tempo",
        )

    # Un istante in cui il carro 1 sta viaggiando col pezzo: il suo programma
    # comincia dal primo riposo dopo. Ogni carro si guarda per conto suo: chi
    # in quell'istante e' fermo comincia li', chi no dal suo riposo dopo.
    trasporto = next(s for s in sol.segments_per_hoist[0] if s.kind == "loaded")
    t = (trasporto.t_start + trasporto.t_end) / 2 % T
    in_moto = programma_carri(data, sol, Avvio(t, []))
    check(
        not _a_riposo(data, sol.segments_per_hoist[0], t, T),
        f"a {t:.2f} s il carro 1 sta trasportando il pezzo",
    )
    for h, (passi, segs) in enumerate(zip(in_moto.programmi, sol.segments_per_hoist)):
        if _a_riposo(data, segs, t, T):
            check(_comincia_da(passi, t, T), f"carro {h + 1}: fermo a {t:.2f} s, comincia li'")
            continue
        finestre = finestre_di_riposo(data, segs)
        prossima = min(finestre, key=lambda f: (f.t_inizio - t) % T)
        check(
            _comincia_da(passi, prossima.t_inizio, T),
            f"carro {h + 1}: in moto a {t:.2f} s, comincia dal primo riposo dopo "
            f"({prossima.t_inizio % T:.2f} s, {passi[0].comando} {passi[0].param1})",
        )


def test_svincoli():
    print("\n[6] rientro che passa alto: svincoli e corse a vuoto")
    # Le corse a vuoto si fanno sugli svincoli delle vasche di partenza e di
    # arrivo del rientro, cioe' scarico e carico: qui serve che li' la corsa ci
    # sia, altrimenti non c'e' niente da salire e da scendere.
    data = _con_ostacoli(linea_verticale())
    tanks = dict(data.tanks)
    for v in ("V0", "V4"):
        tanks[v] = dataclasses.replace(tanks[v], lift_height=1000)
    data = dataclasses.replace(data, tanks=tanks)
    sol = giro_unico(data)
    (passi,) = programma_carri(data, sol).programmi
    righe = [(p.comando, p.param1, p.param2) for p in passi]
    i = righe.index((TRANSFER_INLET, "Pos.V4", 10))
    check(
        righe[i : i + 5]
        == [
            (TRANSFER_INLET, "Pos.V4", 10),
            (LIFTING, "Pos.Top", 10),
            (TRANSFER_OUTLET, "Pos.V0", 10),
            (LIFTING, "Pos.Btm", 10),
            (TRANSFER, "Pos.V0", 10),
        ],
        f"il rientro dallo scarico al carico passa dallo svincolo negativo di V4 "
        f"(Inlet) e da quello positivo di V0 (Outlet) ({righe[i:i + 5]})",
    )
    vuoti = [(p.param1, p.param2) for p in passi if p.comando == LIFTING and p.param2 == 10]
    check(
        vuoti == [("Pos.Top", 10), ("Pos.Btm", 10)],
        f"il gancio scarico sale e riscende sugli svincoli, a velocita' 10 ({vuoti})",
    )
    carichi = [(p.param1, p.param2) for p in passi if p.comando == LIFTING and p.param2 == 9]
    check(
        carichi.count(("Pos.Top", 9)) == 4 and carichi.count(("Pos.Btm", 9)) == 4,
        "sollevamento e immersione col pezzo, una per presa e una per rilascio, "
        "a velocita' 9",
    )
    check(
        [p.param1 for p in passi if p.comando == DRIPPING] == [5, 5, 5],
        "uno sgocciolamento per vasca di processo, in secondi",
    )
    check(
        EXTERNAL_REQUEST in comandi(prima_di(passi, i)),
        "la richiesta al carico sta prima di cominciare il rientro, non alla fine",
    )


def test_cambio_quota():
    print("\n[7] cambio quota: Pos.Int1 e Pos.Int2")
    data = dataclasses.replace(
        linea_verticale(),
        cambio_quota_carico=ZonaCambioQuota(1200, 350, 1650, 2400),
        cambio_quota_scarico=ZonaCambioQuota(18800, 350, 1650, 2400),
    )
    sol = giro_unico(data)
    (passi,) = programma_carri(data, sol).programmi
    righe = [(p.comando, p.param1, p.param2) for p in passi]
    i = righe.index((LIFTING, "Pos.Int1", 10))
    check(
        righe[i : i + 5]
        == [
            (LIFTING, "Pos.Int1", 10),
            (TRANSFER, "Pos.V0", 10),
            (LIFTING, "Pos.Int2", 9),
            (TRANSFER_OUTLET, "Pos.V0", 9),
            (LIFTING, "Pos.Top", 9),
        ],
        f"al carico: sale a Int1, va, solleva a Int2, torna, sale ({righe[i:i + 5]})",
    )
    i = righe.index((TRANSFER_INLET, "Pos.V4", 9))
    check(
        righe[i : i + 6]
        == [
            (TRANSFER_INLET, "Pos.V4", 9),
            (LIFTING, "Pos.Int2", 9),
            (TRANSFER, "Pos.V4", 9),
            (LIFTING, "Pos.Int1", 9),
            (TRANSFER_INLET, "Pos.V4", 10),
            (LIFTING, "Pos.Btm", 10),
        ],
        f"allo scarico lo stesso giro al contrario ({righe[i:i + 6]})",
    )
    check(
        EXTERNAL_REQUEST in comandi(prima_di(passi, i)),
        "la richiesta allo scarico sta prima di andare al punto di cambio quota",
    )
    j = next(k for k, r in enumerate(righe) if r == (TRANSFER_OUTLET, "Pos.V0", 10))
    check(
        EXTERNAL_REQUEST in comandi(prima_di(passi, j)),
        "e quella al carico prima del rientro",
    )


def test_foglio():
    print("\n[8] il foglio SequenzaCarri nel file dei risultati")
    from openpyxl import load_workbook

    from excel_io import FOGLIO_SEQUENZA_CARRI, scrivi_risultati

    data, sol = caso_interbloccato()
    fd, percorso = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        scrivi_risultati(percorso, data, sol, verify_solution(data, sol))
        ws = load_workbook(percorso)[FOGLIO_SEQUENZA_CARRI]
        pc = programma_carri(data, sol, trova_avvio(data, sol))
        check(
            ws["A1"].value == "crane 1" and ws["E1"].value == "crane 2",
            "un blocco per carro, con l'intestazione",
        )
        check(
            [ws.cell(r, 1).value for r in range(2, 7)]
            == ["step[1]", "command", "param1", "param2", "param3"]
            and ws["B2"].value == "UDT PROGRAM STEP"
            and all(ws.cell(r, 2).value == "Int" for r in range(3, 7)),
            "cinque righe per passo, come nelle tabelle del PLC",
        )
        for h, passi in enumerate(pc.programmi):
            c = 3 + 4 * h
            letti = [
                [ws.cell(2 + 5 * i + j, c).value for j in range(1, 5)]
                for i in range(len(passi))
            ]
            check(
                letti == [p.riga() for p in passi],
                f"carro {h + 1}: i {len(passi)} passi scritti tali e quali",
            )
            check(
                ws.cell(2 + 5 * len(passi), c - 2).value is None,
                f"carro {h + 1}: e niente dopo End Program",
            )
    finally:
        os.unlink(percorso)


def main():
    print("=" * 72)
    print("TEST DEL PROGRAMMA DEI CARRI (non richiede OR-Tools)")
    print("=" * 72)
    test_formato()
    test_trasporti_e_tempi()
    test_external_request()
    test_crane_syncro()
    test_avvio()
    test_svincoli()
    test_cambio_quota()
    test_foglio()
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
