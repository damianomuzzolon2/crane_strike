# -*- mode: python ; coding: utf-8 -*-
"""
Ricetta PyInstaller per produrre l'eseguibile autonomo.

Non si lancia a mano: usare `python strumenti/costruisci_exe.py`, che controlla
le premesse e spiega cosa fare se qualcosa manca.

Scelta della forma: UNA CARTELLA (onedir), non un singolo file. Con OR-Tools e
matplotlib dentro, un onefile pesa oltre 200 MB e a ogni avvio deve scompattarsi
in una cartella temporanea: sono decine di secondi di attesa ogni volta, su un
PC di stabilimento anche di piu'. La cartella si copia tale e quale e parte
subito.
"""

import datetime
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

# SPECPATH lo definisce PyInstaller: e' la cartella di questo file, cioe'
# `strumenti/`. I moduli del progetto stanno nella cartella sopra. Passare
# percorsi assoluti evita di dipendere da dove viene lanciato il comando.
RADICE = os.path.dirname(SPECPATH)  # noqa: F821 -- SPECPATH lo inietta PyInstaller

nascosti = []
dati = []
binari = []

# OR-Tools porta con se' librerie native e file di dati: senza raccoglierli
# esplicitamente l'eseguibile parte e poi fallisce al primo solve.
for pacchetto in ("ortools", "matplotlib", "openpyxl"):
    d, b, n = collect_all(pacchetto)
    dati += d
    binari += b
    nascosti += n

# L'icona: la cartella `risorse/` finisce dentro il pacchetto con lo stesso
# nome, e interfaccia.py la cerca accanto a se' (sys._MEIPASS quando e'
# impacchettato). Senza, l'eseguibile parte lo stesso, ma con la piuma di Tk
# nel titolo della finestra.
dati += [(os.path.join(RADICE, "risorse"), "risorse")]
ICONA = os.path.join(RADICE, "risorse", "icona.ico")

# --------------------------------------------------------------------------
# Di chi e' questo programma
# --------------------------------------------------------------------------
#
# Finisce nelle PROPRIETA' del file .exe: tasto destro -> Proprieta' ->
# Dettagli, ed e' anche la colonna "Descrizione" del Gestione attivita'.
#
# Non protegge niente da solo -- chi copia la cartella se la porta via con
# tutto il copyright dentro -- ma e' la prima cosa che si guarda per sapere di
# chi e' un eseguibile che gira su un PC, ed e' quello che si mostra a chi
# contesta. Un programma senza queste righe sembra di nessuno.
AZIENDA = "Imel S.p.A."
PRODOTTO = "CraneStrike"
DESCRIZIONE = "Ciclogrammi carroponti per linee galvaniche"

# Il numero di versione sta QUI e in nessun altro posto: e' l'unico modo per
# non ritrovarsi due numeri diversi nello stesso file. Si alza a mano quando si
# consegna una versione nuova.
VERSIONE = (1, 0, 0, 0)
VERSIONE_TESTO = ".".join(str(n) for n in VERSIONE[:3])

# L'anno del copyright e' quello in cui si COSTRUISCE, non un numero scritto a
# mano: scritto a mano resta indietro, e un avviso di copyright con l'anno
# sbagliato e' peggio di nessun avviso. Chi ricostruisce il pacchetto l'anno
# prossimo si ritrova l'anno giusto senza doverci pensare.
#
# Fra la ragione sociale e il seguito c'e' un trattino e non un punto: "Imel
# S.p.A." il punto ce l'ha gia' suo, e concatenando se ne leggevano due.
COPYRIGHT = (
    f"Copyright (c) {datetime.date.today().year} {AZIENDA} "
    f"- Tutti i diritti riservati."
)

# La lingua dichiarata e' l'ITALIANO (0x0410), perche' italiane sono le
# stringhe: dichiarare en-US (0x0409) come fanno molti pacchetti funziona lo
# stesso -- Windows mostra comunque l'unica tabella che trova -- ma sarebbe una
# dichiarazione falsa. 1200 e' la codepage Unicode, e la chiave della tabella e'
# la coppia scritta in esadecimale: 0410 + 04B0.
LINGUA = 0x0410
CODEPAGE = 1200

versione_file = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=VERSIONE,
        prodvers=VERSIONE,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,  # VOS_NT_WINDOWS32
        fileType=0x1,  # VFT_APP: un'applicazione, non una libreria
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    f"{LINGUA:04X}{CODEPAGE:04X}",
                    [
                        StringStruct("CompanyName", AZIENDA),
                        StringStruct("FileDescription", DESCRIZIONE),
                        StringStruct("FileVersion", VERSIONE_TESTO),
                        StringStruct("InternalName", PRODOTTO),
                        StringStruct("LegalCopyright", COPYRIGHT),
                        StringStruct("OriginalFilename", f"{PRODOTTO}.exe"),
                        StringStruct("ProductName", PRODOTTO),
                        StringStruct("ProductVersion", VERSIONE_TESTO),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [LINGUA, CODEPAGE])]),
    ],
)

nascosti += collect_submodules("ortools.sat")
nascosti += [
    "matplotlib.backends.backend_tkagg",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.ttk",
]

# I moduli del progetto sono importati per nome dall'interfaccia: elencarli
# esplicitamente evita sorprese se un import diventasse condizionale.
nascosti += [
    "avvio",
    "excel_io",
    "kinematics",
    "manuale",
    "model",
    "plotting",
    "simulazione",
    "verify",
]

analisi = Analysis(
    [os.path.join(RADICE, "interfaccia.py")],
    pathex=[RADICE],
    binaries=binari,
    datas=dati,
    hiddenimports=nascosti,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Alleggerimenti. Attenzione a cosa si toglie: pandas NON va escluso
    # anche se il progetto non lo usa, perche' OR-Tools lo importa dentro
    # cp_model. Escluderlo fa costruire l'eseguibile senza un errore, che poi
    # muore al primo calcolo con "No module named 'pandas'".
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(analisi.pure)

exe = EXE(
    pyz,
    analisi.scripts,
    [],
    exclude_binaries=True,
    name="CraneStrike",
    # l'icona del FILE .exe, quella di Esplora risorse e del collegamento;
    # quella della finestra aperta la mette interfaccia.py da risorse/
    icon=ICONA,
    # azienda, prodotto, versione e copyright nelle proprieta' del file
    version=versione_file,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # nessuna finestra nera: gli errori arrivano da messagebox
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

COLLECT(
    exe,
    analisi.binaries,
    analisi.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CraneStrike",
)
