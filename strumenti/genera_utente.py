"""
genera_utente.py
----------------
Crea la voce da incollare in `accesso.UTENTI` per abilitare una persona.

    python strumenti/genera_utente.py

Chiede nome utente e password (la password due volte, senza mostrarla) e
stampa la riga da copiare. La password non viene scritta da nessuna parte:
nel codice finisce solo l'impronta. Dopo aver incollato la riga si ricompila
l'eseguibile (strumenti/compila_nuitka.py).
"""

from __future__ import annotations

import datetime
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from accesso import nuova_voce, verifica  # noqa: E402

LUNGHEZZA_MINIMA = 8


def main() -> int:
    utente = input("Nome utente: ").strip()
    if not utente:
        print("Il nome utente non puo' essere vuoto.")
        return 1
    password = getpass.getpass("Password: ")
    if len(password) < LUNGHEZZA_MINIMA:
        print(f"La password deve avere almeno {LUNGHEZZA_MINIMA} caratteri.")
        return 1
    if getpass.getpass("Ripeti la password: ") != password:
        print("Le due password non coincidono.")
        return 1

    sale, impronta = nuova_voce(utente, password)
    assert verifica(utente, password, [(sale, impronta)])

    oggi = datetime.date.today().isoformat()
    print()
    print("Incolla queste righe nell'elenco UTENTI di accesso.py")
    print("(cambia il commento come preferisci, ma non metterci la password):")
    print()
    print(f"    # <descrizione> - creato il {oggi}")
    print("    (")
    print(f'        "{sale}",')
    print(f'        "{impronta}",')
    print("    ),")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
