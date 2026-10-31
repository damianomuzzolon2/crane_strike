"""
test_fattibilita.py
-------------------
Test del controllo preventivo (fattibilita.py). Richiede OR-Tools: un limite
inferiore si prova contro quello che il solutore riesce davvero a fare.

Quello che si pretende:
  - il limite non supera MAI il takt time che il solutore trova: se lo
    superasse, il pulsante direbbe "impossibile" a una linea che si fa;
  - con la banda tutta sotto il limite, il referto dice impossibile e il
    solutore lo conferma;
  - una vasca a piu' posti divide l'occupazione e non conta il cambio pezzo.

La linea e' quella di test_avvio.

Per eseguirlo:
    python test/test_fattibilita.py
"""

from __future__ import annotations

import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Il solutore in modalita' deterministica (vedi model.configura_solutore): la
# stessa linea da' la stessa soluzione su questo PC e sul runner della CI.
os.environ.setdefault("CRANESTRIKE_DETERMINISTICO", "1")

from fattibilita import testo, valuta
from model import HoistZone, solve
from test_avvio import dati_prova

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


SUDDIVISIONI = [
    [HoistZone(0, 3)],
    [HoistZone(0, 1), HoistZone(2, 3)],
    [HoistZone(0, 1), HoistZone(2, 2), HoistZone(3, 3)],
]


def test_limite_sotto_al_solutore():
    print("\n[1] il limite non supera mai il takt che il solutore trova")
    d = dati_prova()
    for zone in SUDDIVISIONI:
        f = valuta(d, len(zone))
        sol = solve(dataclasses.replace(d, zones=zone), time_limit_s=20)
        if sol.status not in ("OPTIMAL", "FEASIBLE"):
            check(False, f"{len(zone)} carri: il solutore non trova niente ({sol.status})")
            continue
        limite = max(f.limite_vasche, f.carri[-1].limite_s)
        check(
            limite <= sol.T + d.eps_seconds,
            f"{len(zone)} carri: limite {limite:.1f} s <= takt trovato {sol.T:.1f} s",
        )
        check(not f.impossibile, f"{len(zone)} carri: il referto non la esclude")


def test_banda_sotto_al_limite():
    print("\n[2] banda tutta sotto il limite: impossibile, e il solutore conferma")
    d = dati_prova()
    minimo = valuta(d, 3).takt_minimo
    stretta = dataclasses.replace(
        d, takt_min=minimo * 0.8, takt_max=minimo * 0.95, takt_nominal=None
    )
    f = valuta(stretta, 3)
    check(f.impossibile, f"impossibile con takt max {stretta.takt_max:.1f} s")
    check(testo(f).startswith("IMPOSSIBILE"), "e il referto comincia col verdetto")
    for zone in SUDDIVISIONI:
        sol = solve(dataclasses.replace(stretta, zones=zone), time_limit_s=20)
        check(
            sol.status not in ("OPTIMAL", "FEASIBLE"),
            f"{len(zone)} carri: il solutore non trova niente ({sol.status})",
        )


def test_vasca_a_due_posti():
    print("\n[3] una vasca a due posti")
    d = dati_prova()
    tanks = dict(d.tanks)
    tanks["SGRASSO"] = dataclasses.replace(tanks["SGRASSO"], capacity=2)
    d2 = dataclasses.replace(d, tanks=tanks)
    uno = next(v for v in valuta(d, 3).vasche if v.vasca == "SGRASSO")
    due = next(v for v in valuta(d2, 3).vasche if v.vasca == "SGRASSO")
    check(due.cambio_s is None, "il cambio pezzo non si conta")
    check(
        abs(due.limite_s - uno.occupazione_s / 2) < 1e-9,
        f"il limite e' meta' dell'occupazione ({due.limite_s:.1f} s)",
    )


def main():
    test_limite_sotto_al_solutore()
    test_banda_sotto_al_limite()
    test_vasca_a_due_posti()
    print()
    print("=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
