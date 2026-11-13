"""
cattura_schermate.py
--------------------
Apre davvero l'interfaccia sulla linea d'esempio (dati/linea.xlsx), la pilota
da codice e fotografa ogni pagina per il manuale operatore:

    python strumenti/cattura_schermate.py
    python strumenti/genera_manuale_operatore.py

Le immagini finiscono in doc/manuale_operatore/img/, insieme a regioni.json (le
posizioni dei pulsanti, per le figure annotate). Durante la cattura non toccare
mouse e tastiera: le finestre devono restare in primo piano. Serve Windows
(la cornice della finestra si legge con le API di Windows) e OR-Tools: il
calcolo automatico della linea d'esempio dura qualche secondo.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time

ctypes.windll.shcore.SetProcessDpiAwareness(2)

PROGETTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USCITA = os.path.join(PROGETTO, "doc", "manuale_operatore", "img")
sys.path.insert(0, PROGETTO)
os.makedirs(USCITA, exist_ok=True)

import tkinter as tk  # noqa: E402
from tkinter import messagebox  # noqa: E402

from PIL import ImageGrab  # noqa: E402

import interfaccia  # noqa: E402
from interfaccia import Applicazione  # noqa: E402

REGIONI = {}


def cornice(win):
    """Rettangolo della finestra intera (barra del titolo compresa)."""
    win.update()
    hwnd = int(win.wm_frame(), 16)
    r = wt.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wt.HWND(hwnd), 9, ctypes.byref(r), ctypes.sizeof(r)
    )
    return r.left, r.top, r.right, r.bottom


def porta_davanti(win):
    win.deiconify()
    win.lift()
    win.attributes("-topmost", True)
    win.update()
    win.attributes("-topmost", False)


def scatta(win, nome, widget_da_segnare=None, attesa=0.6):
    porta_davanti(win)
    fine = time.time() + attesa
    while time.time() < fine:
        win.update()
        time.sleep(0.03)
    l, t, r, b = cornice(win)
    img = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
    img.save(os.path.join(USCITA, nome + ".png"))
    if widget_da_segnare:
        reg = {}
        for chiave, w in widget_da_segnare.items():
            x, y = w.winfo_rootx() - l, w.winfo_rooty() - t
            reg[chiave] = [x, y, x + w.winfo_width(), y + w.winfo_height()]
        REGIONI[nome] = reg
    print("scattata", nome, img.size)


def pompa(app, secondi_max=600.0):
    scad = time.time() + secondi_max
    while app._lavoro_in_corso and time.time() < scad:
        app.update()
        time.sleep(0.02)
    app.update()


def aspetta(app, secondi):
    fine = time.time() + secondi
    while time.time() < fine:
        app.update()
        time.sleep(0.02)


# -- 1. accesso -------------------------------------------------------------
import accesso  # noqa: E402

_mainloop = tk.Tk.mainloop


def finto_mainloop(self, n=0):
    """La finestra di accesso aspetta l'utente nel suo mainloop: qui invece
    la si fotografa e la si chiude."""
    scatta(self, "01_accesso")
    self.destroy()


tk.Tk.mainloop = finto_mainloop
accesso.chiedi_accesso("CraneStrike", interfaccia._applica_icona)
tk.Tk.mainloop = _mainloop

# niente dialoghi bloccanti
messagebox.askyesno = lambda *a, **k: True
messagebox.askyesnocancel = lambda *a, **k: False
messagebox.showinfo = lambda *a, **k: None

# -- 2. splash + finestra vuota ---------------------------------------------
app = Applicazione(con_splash=True)
app.geometry("1400x880+20+20")
app.update()
sp = app._splash
if sp is not None:
    sp.lift()
    sp.update()
    l, t = sp.winfo_rootx(), sp.winfo_rooty()
    ImageGrab.grab(
        bbox=(l, t, l + sp.winfo_width(), t + sp.winfo_height()), all_screens=True
    ).save(os.path.join(USCITA, "02_splash.png"))
    print("scattata splash")
aspetta(app, 3.3)

# i pulsanti della barra, nell'ordine in cui stanno
pulsanti_barra = [
    w for w in app.pack_slaves()[1].winfo_children()
    if w.winfo_class() == "TButton"
]
etichette = [w.cget("text") for w in pulsanti_barra]
print(etichette)
segni = {w.cget("text"): w for w in pulsanti_barra}
segni["percorso"] = app.etichetta_file
segni["grafico"] = app.tela.get_tk_widget()
segni["barra_grafico"] = app.barra_grafico
segni["verdetto"] = app.banner
segni["schede"] = app.schede
segni["stato"] = app.etichetta_stato
segni["avanzamento"] = app.avanzamento
scatta(app, "03_finestra_vuota", segni)

# -- 3. linea caricata --------------------------------------------------------
linea = os.path.abspath(os.path.join(PROGETTO, "dati", "linea.xlsx"))
app._carica(linea)
aspetta(app, 0.5)
scatta(app, "04_linea_caricata", segni)

# -- 4. Dati linea --------------------------------------------------------------
app._apri_dati_linea()
f = app.finestra_dati
f.geometry("1250x700+60+60")
scatta(f, "05_dati_linea_vasche")
for i, nome in enumerate(f.schede.tabs()):
    titolo = f.schede.tab(nome, "text")
    print("scheda dati", i, titolo)
    if i == 0:
        continue
    f.schede.select(nome)
    scatta(f, f"05_dati_linea_{i}_{titolo.lower().replace(' ', '_')}")
f.destroy()
app.update()

# -- 5. Fattibilita' --------------------------------------------------------
app._mostra_fattibilita()
app.update()
fatt = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
fatt.geometry("+80+60")
scatta(fatt, "06_fattibilita")
fatt.destroy()

# -- 6. calcolo in corso -------------------------------------------------------
app._calcola_automatico()
t0 = time.time()
presa = False
while app._lavoro_in_corso:
    app.update()
    time.sleep(0.02)
    testo = app.etichetta_stato.cget("text")
    if not presa and "tentativo" in testo and ("trovata" in testo or time.time() - t0 > 20):
        scatta(app, "07_calcolo_in_corso", segni, attesa=0.05)
        presa = True
pompa(app)
print("durata calcolo", time.time() - t0)
if not presa:
    print("ATTENZIONE: calcolo troppo rapido per la schermata in corso")
app.schede.select(0)
scatta(app, "08_calcolo_auto_riepilogo", segni)
app.schede.select(2)
kids = app.tabella.get_children()
if kids:
    app.tabella.selection_set(kids[0])
scatta(app, "09_verifica", segni)
app.schede.select(0)

# -- 7. Modifica -----------------------------------------------------------------
app._vai_a_modifica()
app.update()
app.schede.select(1)
scatta(app, "10_modifica", segni)
# scorri la scheda in basso
scheda = app.schede.nametowidget(app.schede.tabs()[1])
canvas = [w for w in scheda.winfo_children() if w.winfo_class() == "Canvas"]
if canvas:
    canvas[0].yview_moveto(1.0)
scatta(app, "11_modifica_in_fondo", segni)
if canvas:
    canvas[0].yview_moveto(0.0)
# una modifica che sfora: ZINCATURA fuori dal massimo
trovato = False
d0 = app.config_linea.data
for k in range(1, d0.n_moves):
    for delta in (+4.0, -4.0, +8.0, -8.0, +15.0, -15.0):
        prima = app._istantanea()
        vecchio = app.permanenze[k]
        app.permanenze[k] = vecchio + delta
        app._ricomponi(f"{d0.route[k].tank_id}: tempo in vasca {vecchio + delta:.1f} s", prima)
        app.update()
        if not app.incoerenze and app.report is not None and not app.report.ok:
            trovato = True
            print("errore con", k, delta)
            break
        app._annulla_modifica()
        app.update()
    if trovato:
        break
app.schede.select(2)
kids = app.tabella.get_children()
if kids:
    app.tabella.selection_set(kids[0])
scatta(app, "15_modifica_con_errori", segni)
app._annulla_modifica()
app.update()
print("dopo annulla:", app.banner.cget("text"))

# -- 8. Simulazione ------------------------------------------------------------
app._chiudi_modifica()
app.update()
app._apri_simulazione()
sim = app.finestra_simulazione
sim.geometry("1300x700+60+60")
aspetta(app, 4.0)
if sim._in_moto:
    sim.avvia_o_ferma()
scatta(sim, "12_simulazione")
sim.destroy()
app.update()

# -- 9. Avvio ---------------------------------------------------------------------
print("avvio:", app.btn_avvio.cget("text"), app.btn_avvio["state"])

app._prossimo_avvio()
app.update()
scatta(app, "14_avvio_2", segni)

# -- 5b. Calcola man ---------------------------------------------------------------
import copy
salvate = copy.deepcopy((app.permanenze, app.assegnazione, app.n_carroponti))
app._componi_da_zero()
app.update()
app.schede.select(0)
scatta(app, "13a_calcola_man_riepilogo", segni)
app.schede.select(1)
scatta(app, "13b_calcola_man", segni)
for k in range(3):
    app.carroponte_attivo = 0 if k < 2 else 1
    app.var_carro_attivo.set(str(app.carroponte_attivo + 1))
    ok = app._assegna(k, app._istantanea())
    app.update()
    print("assegna", k, ok, app.etichetta_stato.cget("text"))
    if k == 2:
        scatta(app, "13c_calcola_man_parziale", segni)
app.permanenze, app.assegnazione, app.n_carroponti = copy.deepcopy(salvate)
app._ricomponi("Tempi in vasca e assegnazione ricopiati")
app.update()
print("banner composizione:", app.banner.cget("text"))
scatta(app, "13d_in_composizione", segni)
app._verifica_adesso()
app.update()
scatta(app, "13e_composizione_verificata", segni)


json.dump(REGIONI, open(os.path.join(USCITA, "regioni.json"), "w"), indent=1)
try:
    app.tela.get_tk_widget().destroy()
except Exception:
    pass
app.destroy()
print("fine")
