"""
test_allinea_avvio.py
---------------------
Test del ritocco che rende esatto un punto di avvio approssimato
(allinea_avvio.py). Richiede OR-Tools: il ciclogramma di partenza lo trova il
solutore, e la ricerca degli spostamenti e' un piccolo modello CP-SAT.

La linea e' quella di test_avvio. Divisa fra tre carroponti -- mosse 0-1, 2, 3
-- il solutore da' un ciclogramma valido in cui nessun istante trova tutti e tre
fermi in basso: e' il caso da sistemare, e non lo si costruisce a mano.

Quello che si pretende:
  - dopo, il punto di avvio e' esatto e la verifica indipendente passa;
  - il takt time non cambia, e dentro il giro di ciascun carroponte nemmeno:
    ogni giro e' spostato rigidamente, con le sue attese;
  - cambiano soltanto i bagni di CONFINE, e restano nelle tolleranze;
  - quando non serve, o non si puo', non si tocca niente.

Per eseguirlo:
    python test/test_allinea_avvio.py
"""

from __future__ import annotations

import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from allinea_avvio import MARGINE_MINIMO_S, allinea_avvio, descrivi
from avvio import trova_avvio
from model import HoistZone, solve
from test_avvio import dati_prova
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


_risolte: dict = {}


def risolta(zone: list[HoistZone]):
    """La linea di prova risolta con queste zone, UNA volta sola.

    CP-SAT gira su piu' thread e non e' deterministico: due risoluzioni della
    stessa linea possono dare ciclogrammi diversi allo stesso takt, uno con
    l'avvio approssimato e uno con l'avvio gia' esatto. I casi che partono
    dalla stessa linea devono partire dallo STESSO ciclogramma, altrimenti il
    loro presupposto vale o no a seconda della macchina (sul runner della CI
    il secondo calcolo usciva esatto). allinea_avvio non tocca la soluzione
    che riceve, quindi condividerla e' sicuro."""
    chiave = tuple((z.lo, z.hi) for z in zone)
    if chiave not in _risolte:
        d = dataclasses.replace(dati_prova(), zones=zone)
        sol = solve(d, time_limit_s=20)
        assert sol.status in ("OPTIMAL", "FEASIBLE"), sol.status
        _risolte[chiave] = (d, sol)
    return _risolte[chiave]


def bagni(d, at) -> dict[int, float]:
    return {
        k: at[k] - at[k - 1] - d.loaded_leg_seconds(k - 1) for k in range(1, d.n_moves)
    }


def test_avvio_reso_esatto():
    print("\n[1] un avvio approssimato diventa esatto")
    d, sol = risolta([HoistZone(0, 1), HoistZone(2, 2), HoistZone(3, 3)])
    prima = trova_avvio(d, sol)
    check(
        verify_solution(d, sol).ok and not prima.esatto,
        f"si parte da un ciclogramma valido con l'avvio approssimato "
        f"({prima.errore:.2f} s)",
    )
    r = allinea_avvio(d, sol)
    check(r is not None, "uno spostamento si trova")
    if r is None:
        return
    nuova = r.soluzione
    dopo = trova_avvio(d, nuova)
    check(dopo.esatto, f"dopo e' esatto ({dopo.t:.2f} s)")
    check(verify_solution(d, nuova).ok, "e la verifica indipendente lo passa")
    check(abs(nuova.T - sol.T) < 1e-9, "il takt time e' lo stesso")
    check(r.margine >= MARGINE_MINIMO_S - 1e-9, f"con margine {r.margine:.2f} s")
    check(
        nuova.raw.get("allineamento_avvio") == r.spostamenti and r.spostamenti,
        f"gli spostamenti restano scritti nella soluzione ({descrivi(r.spostamenti)})",
    )

    # Ogni giro spostato rigidamente: le mosse di uno stesso carroponte si
    # spostano tutte della stessa quantita', e le sue attese restano quelle.
    proprietario = {k: i for i, p in enumerate(sol.plans) for k in p.order}
    per_carro: dict[int, set] = {}
    for k in range(d.n_moves):
        per_carro.setdefault(proprietario[k], set()).add(
            round(nuova.actual_time[k] - sol.actual_time[k], 6)
        )
    check(
        all(len(v) == 1 for v in per_carro.values()),
        "le mosse di ogni carroponte si spostano insieme",
    )
    check(
        all(
            p.attese.keys() == q.attese.keys()
            and all(abs(p.attese[k] - q.attese[k]) < 1e-6 for k in p.attese)
            for p, q in zip(sol.plans, nuova.plans)
        ),
        "le attese dei rientri sono le stesse",
    )

    b0, b1 = bagni(d, sol.actual_time), bagni(d, nuova.actual_time)
    cambiati = {k for k in b0 if abs(b0[k] - b1[k]) > 1e-6}
    confini = {k for k in b0 if proprietario[k] != proprietario[k - 1]}
    check(
        cambiati and cambiati <= confini,
        f"cambiano solo i bagni di confine (tappe {sorted(cambiati)})",
    )
    check(
        all(
            d.route[k].dwell_min - 1e-6 <= b1[k] <= d.route[k].dwell_max + 1e-6
            for k in cambiati
        ),
        "e restano nelle tolleranze",
    )


def test_gia_esatto():
    print("\n[2] un avvio gia' esatto non si tocca")
    d, sol = risolta([HoistZone(0, 1), HoistZone(2, 3)])
    check(trova_avvio(d, sol).esatto, "il ciclogramma ha gia' un avvio esatto")
    check(allinea_avvio(d, sol) is None, "e non viene ritoccato")


def test_tolleranze_chiuse():
    print("\n[3] senza tolleranze sui bagni di confine non si sposta niente")
    d, sol = risolta([HoistZone(0, 1), HoistZone(2, 2), HoistZone(3, 3)])
    proprietario = {k: i for i, p in enumerate(sol.plans) for k in p.order}
    b = bagni(d, sol.actual_time)
    route = list(d.route)
    for k in range(1, d.n_moves):
        if proprietario[k] != proprietario[k - 1]:
            route[k] = dataclasses.replace(
                route[k], dwell_min=b[k], dwell_max=b[k], dwell_nominal=b[k]
            )
    chiusa = dataclasses.replace(d, route=route)
    check(not trova_avvio(chiusa, sol).esatto, "l'avvio e' approssimato")
    check(
        allinea_avvio(chiusa, sol) is None,
        "e resta com'e': nessun carroponte si puo' spostare",
    )


def main() -> int:
    test_avvio_reso_esatto()
    test_gia_esatto()
    test_tolleranze_chiuse()
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
