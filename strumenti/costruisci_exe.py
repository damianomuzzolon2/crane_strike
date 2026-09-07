"""
costruisci_exe.py
-----------------
Produce l'eseguibile autonomo, da usare su PC dove Python non c'e'.

    python strumenti/costruisci_exe.py

Al termine si trova tutto in `dist/Ciclogrammi/`: la cartella va copiata
intera sul PC di destinazione, e si lancia `Ciclogrammi.exe`.

Con `--con-test` esegue prima l'intera suite di test. Non e' obbligatorio, ma
e' l'unico modo per non scoprire un problema in stabilimento.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Questo file sta in `strumenti/`: la radice del progetto e' la cartella sopra.
ATTREZZI = Path(__file__).resolve().parent
RADICE = ATTREZZI.parent
USCITA = RADICE / "dist" / "Ciclogrammi"

TEST = [
    "kinematics.py",  # l'autoverifica della cinematica sta nel modulo stesso
    "test/test_verify.py",
    "test/test_excel_io.py",
    "test/test_model.py",
    "test/test_simulazione.py",
    "test/test_interfaccia.py",
]


def controlla_premesse() -> bool:
    mancanti = []
    for modulo, pacchetto in [
        ("PyInstaller", "pyinstaller"),
        ("ortools", "ortools"),
        ("matplotlib", "matplotlib"),
        ("openpyxl", "openpyxl"),
    ]:
        try:
            __import__(modulo)
        except ImportError:
            mancanti.append(pacchetto)
    if mancanti:
        print("Mancano dei pacchetti. Installali con:")
        print(f"    pip install {' '.join(mancanti)}")
        return False
    return True


def esegui_test() -> bool:
    print("Eseguo i test prima di impacchettare...\n")
    for nome in TEST:
        percorso = RADICE / nome
        if not percorso.exists():
            continue
        esito = subprocess.run(
            [sys.executable, str(percorso)], cwd=RADICE, capture_output=True, text=True
        )
        ultima = [
            r for r in esito.stdout.splitlines() if r.startswith(("RISULTATO", "OK:"))
        ]
        print(f"  {nome:27s} {ultima[-1] if ultima else 'nessun esito'}")
        if esito.returncode != 0:
            print("\nI test non passano: correggi prima di impacchettare.")
            print(esito.stdout[-3000:])
            return False
    print()
    return True


def main() -> int:
    if not controlla_premesse():
        return 2
    if "--con-test" in sys.argv and not esegui_test():
        return 1

    for cartella in (RADICE / "build", RADICE / "dist"):
        if cartella.exists():
            print(f"Pulisco {cartella.name}/ ...")
            shutil.rmtree(cartella, ignore_errors=True)

    print("Impacchetto (ci vogliono alcuni minuti)...\n")
    esito = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(ATTREZZI / "ciclogrammi.spec"),
        ],
        cwd=RADICE,
    )
    if esito.returncode != 0:
        print("\nImpacchettamento fallito.")
        return esito.returncode

    eseguibile = USCITA / "Ciclogrammi.exe"
    if not eseguibile.exists():
        print(f"\nAtteso {eseguibile}, ma non c'e'.")
        return 1

    peso = sum(f.stat().st_size for f in USCITA.rglob("*") if f.is_file())
    print()
    print("=" * 68)
    print(f"Fatto: {eseguibile}")
    print(f"Dimensione della cartella: {peso / 1e6:.0f} MB")
    print()
    print("Copia l'intera cartella dist/Ciclogrammi sul PC di destinazione")
    print("e lancia Ciclogrammi.exe. Non serve installare Python.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
