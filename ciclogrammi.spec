# -*- mode: python ; coding: utf-8 -*-
"""
Ricetta PyInstaller per produrre l'eseguibile autonomo.

Non si lancia a mano: usare `python costruisci_exe.py`, che controlla le
premesse e spiega cosa fare se qualcosa manca.

Scelta della forma: UNA CARTELLA (onedir), non un singolo file. Con OR-Tools e
matplotlib dentro, un onefile pesa oltre 200 MB e a ogni avvio deve scompattarsi
in una cartella temporanea: sono decine di secondi di attesa ogni volta, su un
PC di stabilimento anche di piu'. La cartella si copia tale e quale e parte
subito.
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

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
    "excel_io",
    "kinematics",
    "manuale",
    "model",
    "plotting",
    "verify",
]

analisi = Analysis(
    ["interfaccia.py"],
    pathex=["."],
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
    name="Ciclogrammi",
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
    name="Ciclogrammi",
)
