"""
compila_nuitka.py
-----------------
Produce l'eseguibile autonomo COMPILATO, da usare su PC dove Python non c'e'.

    python strumenti/compila_nuitka.py

A differenza di PyInstaller (che impacchetta i .pyc, cioe' bytecode Python che
si puo' decompilare), Nuitka TRADUCE i moduli Python in C e li compila in codice
macchina nativo: dentro la cartella finale non resta nessun sorgente ne' alcun
.pyc del progetto, quindi il codice non e' leggibile ne' copiabile. E' la
protezione del sorgente, ed e' gratuita (Nuitka e' open source), senza la
licenza annuale che servirebbe con PyArmor.

Al termine si trova tutto in `dist/CraneStrike/`: la cartella va copiata intera
sul PC di destinazione, e si lancia `CraneStrike.exe`. Non serve installare
Python.

Con `--con-test` esegue prima l'intera suite di test. Non e' obbligatorio, ma
e' l'unico modo per non scoprire un problema in stabilimento.

La PRIMA compilazione e' lenta (diversi minuti: Nuitka deve compilare il C, e
la prima volta puo' scaricare il compilatore). Le volte successive la cache
rende tutto piu' rapido.
"""

from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
from pathlib import Path

# Questo file sta in `strumenti/`: la radice del progetto e' la cartella sopra.
ATTREZZI = Path(__file__).resolve().parent
RADICE = ATTREZZI.parent

# Nuitka chiama la cartella prodotta `<modulo>.dist`. La costruiamo dentro
# `build/` e alla fine la spostiamo sotto `dist/CraneStrike/`, cosi' il
# risultato finale e' identico a quello di PyInstaller e le istruzioni per lo
# stabilimento non cambiano.
PRODOTTA_DA_NUITKA = RADICE / "build" / "interfaccia.dist"
USCITA = RADICE / "dist" / "CraneStrike"
ESEGUIBILE = USCITA / "CraneStrike.exe"

INGRESSO = RADICE / "interfaccia.py"

# --------------------------------------------------------------------------
# Di chi e' questo programma
# --------------------------------------------------------------------------
#
# Finisce nelle PROPRIETA' del file .exe: tasto destro -> Proprieta' ->
# Dettagli. Non protegge niente da solo, ma e' la prima cosa che si guarda per
# sapere di chi e' un eseguibile che gira su un PC. Le stesse righe stavano
# nello spec di PyInstaller: qui diventano opzioni di Nuitka.
AZIENDA = "Imel S.p.A."
PRODOTTO = "CraneStrike"
DESCRIZIONE = "Ciclogrammi carroponti per linee galvaniche"

# Il numero di versione sta QUI e in nessun altro posto. Si alza a mano quando
# si consegna una versione nuova. Nuitka lo vuole in forma numerica a.b.c.d.
VERSIONE = "1.0.0.0"

# L'anno del copyright e' quello in cui si COMPILA, non un numero scritto a
# mano: scritto a mano resta indietro. Fra la ragione sociale e il seguito c'e'
# un trattino e non un punto perche' "Imel S.p.A." il punto ce l'ha gia' suo.
COPYRIGHT = (
    f"Copyright (c) {datetime.date.today().year} {AZIENDA} "
    f"- Tutti i diritti riservati."
)

ICONA = RADICE / "risorse" / "icona.ico"

TEST = [
    "kinematics.py",  # l'autoverifica della cinematica sta nel modulo stesso
    "test/test_accesso.py",
    "test/test_verify.py",
    "test/test_excel_io.py",
    "test/test_model.py",
    "test/test_simulazione.py",
    "test/test_avvio.py",
    "test/test_interfaccia.py",
]


def controlla_premesse() -> bool:
    mancanti = []
    for modulo, pacchetto in [
        ("nuitka", "nuitka"),
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
    print("Eseguo i test prima di compilare...\n")
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
            print("\nI test non passano: correggi prima di compilare.")
            print(esito.stdout[-3000:])
            return False
    print()
    return True


def comando_nuitka() -> list[str]:
    return [
        sys.executable,
        "-m",
        "nuitka",
        # UNA CARTELLA autonoma (standalone), non un singolo file: con OR-Tools
        # e matplotlib dentro, un onefile deve scompattarsi a ogni avvio, che su
        # un PC di stabilimento sono decine di secondi ogni volta. La cartella
        # si copia tale e quale e parte subito.
        "--standalone",
        # Se manca il compilatore C, Nuitka lo scarica senza fermarsi a chiedere.
        "--assume-yes-for-downloads",
        # Nuitka ricompila solo cio' che e' cambiato: tiene una cache in
        # %LOCALAPPDATA%\\Nuitka. La prima volta e' lenta, poi no.
        # ---- cio' che serve a far girare le librerie ----
        # tkinter porta con se' Tcl/Tk (file di dati, non solo codice).
        "--enable-plugin=tk-inter",
        # matplotlib ha backend e file di dati da raccogliere a parte.
        "--enable-plugin=matplotlib",
        # OR-Tools porta librerie native (.pyd/.dll) e file di dati: senza
        # includere il pacchetto e i suoi dati, l'eseguibile parte e poi fallisce
        # al primo solve. (pandas lo tira dentro OR-Tools da solo: cp_model lo
        # importa, e Nuitka segue l'import.)
        "--include-package=ortools",
        "--include-package-data=ortools",
        # Alleggerimenti. Pacchetti che nessuna parte del progetto usa ma che
        # verrebbero trascinati dentro (li tirano le librerie grosse). Toglierli
        # rende la cartella piu' piccola e la compilazione piu' rapida e stabile.
        # ATTENZIONE: pandas NON si esclude, lo importa OR-Tools (cp_model); e
        # PIL NON si esclude, lo usa interfaccia.py per l'icona (ImageTk).
        "--nofollow-import-to=plotly",
        "--nofollow-import-to=PyQt5",
        "--nofollow-import-to=PyQt6",
        "--nofollow-import-to=PySide2",
        "--nofollow-import-to=PySide6",
        "--nofollow-import-to=IPython",
        "--nofollow-import-to=jupyter",
        "--nofollow-import-to=notebook",
        "--nofollow-import-to=pytest",
        # L'icona della finestra la mette interfaccia.py da risorse/, che qui
        # finisce accanto all'eseguibile con lo stesso nome.
        f"--include-data-dir={RADICE / 'risorse'}=risorse",
        # ---- aspetto e identita' dell'eseguibile ----
        # Nessuna finestra nera: gli errori arrivano da messagebox.
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={ICONA}",
        f"--company-name={AZIENDA}",
        f"--product-name={PRODOTTO}",
        f"--file-description={DESCRIZIONE}",
        f"--file-version={VERSIONE}",
        f"--product-version={VERSIONE}",
        f"--copyright={COPYRIGHT}",
        # ---- dove mettere il risultato ----
        f"--output-dir={RADICE / 'build'}",
        "--output-filename=CraneStrike.exe",
        # Cancella i file intermedi (il C generato): teniamo solo la .dist.
        "--remove-output",
        str(INGRESSO),
    ]


def main() -> int:
    if not controlla_premesse():
        return 2
    if "--con-test" in sys.argv and not esegui_test():
        return 1

    for cartella in (RADICE / "build", RADICE / "dist"):
        if cartella.exists():
            print(f"Pulisco {cartella.name}/ ...")
            shutil.rmtree(cartella, ignore_errors=True)

    print("Compilo (la prima volta ci vogliono diversi minuti)...\n")
    esito = subprocess.run(comando_nuitka(), cwd=RADICE)
    if esito.returncode != 0:
        print("\nCompilazione fallita.")
        return esito.returncode

    if not PRODOTTA_DA_NUITKA.exists():
        print(f"\nAttesa {PRODOTTA_DA_NUITKA}, ma non c'e'.")
        return 1

    # Sposto `build/interfaccia.dist` -> `dist/CraneStrike`, cosi' il risultato
    # finale e la cartella da consegnare sono gli stessi di sempre.
    USCITA.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(PRODOTTA_DA_NUITKA), str(USCITA))

    if not ESEGUIBILE.exists():
        print(f"\nAtteso {ESEGUIBILE}, ma non c'e'.")
        return 1

    peso = sum(f.stat().st_size for f in USCITA.rglob("*") if f.is_file())
    print()
    print("=" * 68)
    print(f"Fatto: {ESEGUIBILE}")
    print(f"Dimensione della cartella: {peso / 1e6:.0f} MB")
    print()
    print("Copia l'intera cartella dist/CraneStrike sul PC di destinazione")
    print("e lancia CraneStrike.exe. Non serve installare Python, e dentro la")
    print("cartella non c'e' nessun sorgente del progetto: solo codice compilato.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
