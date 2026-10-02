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

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

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
