"""
test_accesso.py
---------------
Test della verifica di utente e password (senza aprire finestre).

Per eseguirlo:
    python test/test_accesso.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import accesso
from accesso import nuova_voce, verifica


def main() -> int:
    errori = []

    def controlla(condizione, descrizione):
        print(f"  {'ok ' if condizione else 'NO '} {descrizione}")
        if not condizione:
            errori.append(descrizione)

    voci = [nuova_voce("Mario", "segreto-123"), nuova_voce("luigi", "altra pass")]

    controlla(verifica("Mario", "segreto-123", voci), "utente e password giusti")
    controlla(verifica("  mario ", "segreto-123", voci), "nome senza maiuscole/spazi")
    controlla(verifica("luigi", "altra pass", voci), "seconda voce")
    controlla(not verifica("Mario", "Segreto-123", voci), "password case-sensitive")
    controlla(not verifica("Mario", "altra pass", voci), "password di un altro")
    controlla(not verifica("Anna", "segreto-123", voci), "utente sconosciuto")
    controlla(not verifica("", "", voci), "campi vuoti")
    controlla(not verifica("Mario", "segreto-123", []), "elenco vuoto")
    controlla(
        not verifica("Mario", "segreto-123", [("zz", "non-esadecimale")]),
        "voce scritta male",
    )
    controlla(
        nuova_voce("Mario", "x")[0] != nuova_voce("Mario", "x")[0],
        "sale diverso a ogni voce",
    )

    # Le voci vere scritte in accesso.py devono essere esadecimali ben formate:
    # una voce rovinata da un copia-incolla chiuderebbe fuori quella persona.
    for sale, impronta in accesso.UTENTI:
        try:
            ben_formata = len(bytes.fromhex(sale)) == 16 and len(bytes.fromhex(impronta)) == 32
        except ValueError:
            ben_formata = False
        controlla(ben_formata, f"voce di UTENTI ben formata ({sale[:8]}...)")
    controlla(len(accesso.UTENTI) > 0, "almeno un utente abilitato")

    print()
    if errori:
        print(f"RISULTATO: {len(errori)} controlli falliti")
        return 1
    print("RISULTATO: tutti i controlli superati")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
