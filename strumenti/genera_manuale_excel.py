"""
genera_manuale_excel.py
-----------------------
Scrive il manuale di compilazione del file Excel di ingresso (la linea):

    python strumenti/genera_manuale_excel.py

Il documento esce in `doc/manuale_excel/manuale_compilazione_excel.docx`, le
figure in `doc/manuale_excel/img/`. Non serve aprire il programma:

  - le immagini dei FOGLI si ricavano dal modello vero, quello che scrive
    `excel_io.scrivi_modello` ("Nuovo modello Excel..."), quindi colonne,
    intestazioni e valori d'esempio sono sempre quelli del programma;
  - gli SCHEMI (rotaia, corse, svincoli, profili di velocita'...) sono
    disegnati qui con matplotlib;
  - il messaggio d'errore d'esempio si ottiene facendo leggere a
    `excel_io.leggi_problema` un file sbagliato apposta.

Le due schermate della finestra "Dati linea" si prendono da quelle del manuale
operatore (strumenti/cattura_schermate.py). L'impaginazione e' la stessa del
manuale operatore: `scrivi_documento` di genera_manuale_operatore.py.

Quando il formato del file cambia (colonne, parametri) si aggiorna il testo in
CONTENUTO e si rilancia.
"""

from __future__ import annotations

import os
import sys
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle  # noqa: E402

ATTREZZI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(ATTREZZI)
sys.path.insert(0, RADICE)
sys.path.insert(0, ATTREZZI)

import excel_io  # noqa: E402
import genera_manuale_operatore as impaginazione  # noqa: E402

CARTELLA = os.path.join(RADICE, "doc", "manuale_excel")
IMG = os.path.join(CARTELLA, "img")
IMG_OPERATORE = os.path.join(RADICE, "doc", "manuale_operatore", "img")
USCITA = os.path.join(CARTELLA, "manuale_compilazione_excel.docx")

DPI = 200
ROSSO = "#c0392b"
BLU = "#1f5fa8"
VERDE = "#3c7d3a"
ARANCIO = "#e08a1e"
GRIGIO = "#7f8c8d"
VASCA = "#cfe3f3"
VASCA_BORDO = "#4a6f8a"
LIQUIDO = "#8fbfe0"
CARRO = "#f2b65c"
TELAIO = "#6d4c41"
VERDE_EXCEL = "#4F6228"

plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans"})


def _salva(fig, nome: str):
    fig.savefig(os.path.join(IMG, nome + ".png"), dpi=DPI, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)


def _quota(ax, x0, x1, y, testo, colore=ROSSO, sopra=True, dimensione=8.5,
           verticale=False, fondo="white", scosta=3):
    """Una quota da disegno tecnico: freccia doppia e testo in mezzo."""
    if verticale:
        ax.annotate("", xy=(y, x0), xytext=(y, x1),
                    arrowprops=dict(arrowstyle="<->", color=colore, lw=1.3,
                                    shrinkA=0, shrinkB=0))
        ax.text(y, (x0 + x1) / 2, " " + testo, color=colore, ha="left",
                va="center", fontsize=dimensione, fontweight="bold",
                bbox=dict(facecolor=fondo, edgecolor="none", pad=1.0))
        return
    ax.annotate("", xy=(x0, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="<->", color=colore, lw=1.3,
                                shrinkA=0, shrinkB=0))
    # il testo sta SCOSTATO dalla freccia, mai sopra: coprirebbe la linea
    ax.annotate(testo, xy=((x0 + x1) / 2, y),
                xytext=(0, scosta if sopra else -scosta), textcoords="offset points",
                color=colore, ha="center", va="bottom" if sopra else "top",
                fontsize=dimensione, fontweight="bold")


def _bollino(ax, x, y, testo, colore=ROSSO, r=10, dimensione=8):
    ax.text(x, y, testo, ha="center", va="center", color="white",
            fontsize=dimensione, fontweight="bold", zorder=10,
            bbox=dict(boxstyle="circle,pad=0.25", facecolor=colore,
                      edgecolor="white", linewidth=1.2))


# ==========================================================================
# 1) I fogli Excel, ricavati dal modello vero
# ==========================================================================


def _libri_esempio(cartella: str):
    """Il modello d'esempio e due varianti: una con Zone e CambioQuota
    compilati, una con gli svincoli e una vasca-ostacolo."""
    from openpyxl import load_workbook

    base = os.path.join(cartella, "modello.xlsx")
    excel_io.scrivi_modello(base)

    wb = load_workbook(base)
    ws = wb[excel_io.FOGLIO_ZONE]
    ws["D2"] = None
    for riga, (a, b) in enumerate([("CARICO", "ZINCATURA"), ("ZINCATURA", "SCARICO")], 2):
        ws.cell(riga, 1, a)
        ws.cell(riga, 2, b)
    ws = wb[excel_io.FOGLIO_CAMBIO_QUOTA]
    ws["G2"] = None
    for col, val in enumerate(["carico", 1200, 600, 1500, 2500], 1):
        ws.cell(2, col, val)
    compilato = os.path.join(cartella, "compilato.xlsx")
    wb.save(compilato)

    wb = load_workbook(base)
    ws = wb[excel_io.FOGLIO_VASCHE]
    posizioni = [ws.cell(r, 2).value for r in range(2, 9)]
    for i, r in enumerate(range(2, 9)):
        if i > 0:
            ws.cell(r, 6, (posizioni[i - 1] + posizioni[i]) / 2)
        if i < 6:
            ws.cell(r, 7, (posizioni[i] + posizioni[i + 1]) / 2)
    ws.cell(5, 8, 0)  # ZINCATURA: ostacolo
    svincoli = os.path.join(cartella, "svincoli.xlsx")
    wb.save(svincoli)

    # Un file sbagliato apposta, per mostrare come escono gli errori
    wb = load_workbook(base)
    wb[excel_io.FOGLIO_PARAMETRI]["B5"] = "500 mm/s"  # v_max_vuoto_mm_s
    wb[excel_io.FOGLIO_PERCORSO]["B5"] = "ZINCATUR"
    wb[excel_io.FOGLIO_PERCORSO]["D3"] = -15
    sbagliato = os.path.join(cartella, "linea.xlsx")
    wb.save(sbagliato)
    try:
        excel_io.leggi_problema(sbagliato)
        messaggio = "(nessun errore: il file d'esempio va aggiornato)"
    except ValueError as e:
        messaggio = str(e).replace(sbagliato, "linea.xlsx")
    return base, compilato, svincoli, messaggio


def _testo_cella(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def disegna_foglio(percorso: str, foglio: str, nome: str, colonne=None,
                   ultima_riga=None, larghezze=None, numeri=None, gruppi=None,
                   evidenzia=None):
    """Un foglio come lo si vede in Excel: lettere di colonna, numeri di riga,
    intestazione verde, linguette in basso. `numeri` = {indice colonna: n} per
    i bollini rossi sopra le colonne; `gruppi` = [(riga0, riga1, etichetta)]
    per le graffe a destra; `evidenzia` = {(riga, col): colore}."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    wb = load_workbook(percorso)
    ws = wb[foglio]
    colonne = colonne or list(range(1, ws.max_column + 1))
    ultima_riga = ultima_riga or ws.max_row
    larghezze = larghezze or {}
    numeri = numeri or {}
    evidenzia = evidenzia or {}

    W_NUM = 3.5
    lw = [larghezze.get(c, ws.column_dimensions[get_column_letter(c)].width or 10)
          for c in colonne]
    x = [W_NUM]
    for w in lw:
        x.append(x[-1] + w)
    W = x[-1]
    BANDA = 1.3 if numeri else 0.3
    H_LET = 1.0
    righe = list(range(1, ultima_riga + 1))
    H = BANDA + H_LET + len(righe) + 1.6
    larg_gruppi = 22 if gruppi else 0

    fig, ax = plt.subplots(figsize=((W + larg_gruppi) * 0.085, H * 0.24))
    ax.set_xlim(0, W + larg_gruppi)
    ax.set_ylim(H, 0)
    ax.axis("off")

    y0 = BANDA
    ax.add_patch(Rectangle((0, y0), W, H_LET, facecolor="#e9e9e9", edgecolor="#bdbdbd", lw=0.6))
    for i, c in enumerate(colonne):
        ax.add_patch(Rectangle((x[i], y0), lw[i], H_LET, facecolor="#e9e9e9",
                               edgecolor="#bdbdbd", lw=0.6))
        ax.text((x[i] + x[i + 1]) / 2, y0 + H_LET / 2, get_column_letter(c),
                ha="center", va="center", fontsize=7.5, color="#444")
        if c in numeri:
            _bollino(ax, (x[i] + x[i + 1]) / 2, BANDA / 2 + 0.05, str(numeri[c]))
    for j, r in enumerate(righe):
        yr = y0 + H_LET + j
        ax.add_patch(Rectangle((0, yr), W_NUM, 1, facecolor="#e9e9e9",
                               edgecolor="#bdbdbd", lw=0.6))
        ax.text(W_NUM / 2, yr + 0.5, str(r), ha="center", va="center",
                fontsize=7.5, color="#444")
        for i, c in enumerate(colonne):
            v = ws.cell(r, c).value
            fondo = VERDE_EXCEL if r == 1 and v is not None else "white"
            fondo = evidenzia.get((r, c), fondo)
            ax.add_patch(Rectangle((x[i], yr), lw[i], 1, facecolor=fondo,
                                   edgecolor="#d4d4d4", lw=0.6))
            t = _testo_cella(v)
            if not t:
                continue
            numero = isinstance(v, (int, float))
            if r == 1:
                ax.text((x[i] + x[i + 1]) / 2, yr + 0.5, t, ha="center", va="center",
                        fontsize=7, color="white" if fondo == VERDE_EXCEL else "black",
                        fontweight="bold", clip_on=True)
            else:
                ax.text(x[i + 1] - 0.4 if numero else x[i] + 0.4, yr + 0.5, t,
                        ha="right" if numero else "left", va="center", fontsize=7,
                        clip_on=True)
    # le linguette
    yt = y0 + H_LET + len(righe) + 0.3
    xt = 0.5
    for nome_f in wb.sheetnames:
        lt = len(nome_f) * 0.95 + 2.5
        attivo = nome_f == foglio
        ax.add_patch(Rectangle((xt, yt), lt, 1.1,
                               facecolor="white" if attivo else "#ececec",
                               edgecolor="#9e9e9e", lw=0.6))
        if attivo:
            ax.plot([xt + 0.3, xt + lt - 0.3], [yt + 1.05, yt + 1.05], color=VERDE_EXCEL, lw=2)
        ax.text(xt + lt / 2, yt + 0.55, nome_f, ha="center", va="center", fontsize=7,
                fontweight="bold" if attivo else "normal",
                color=VERDE_EXCEL if attivo else "#555")
        xt += lt + 0.2
    for r0, r1, etichetta in gruppi or []:
        ya = y0 + H_LET + (r0 - 1) + 0.1
        yb = y0 + H_LET + r1 - 0.1
        xg = W + 0.8
        ax.plot([xg, xg + 0.8, xg + 0.8, xg], [ya, ya, yb, yb], color=BLU, lw=1.2)
        ax.text(xg + 1.5, (ya + yb) / 2, etichetta, va="center", ha="left",
                fontsize=7.5, color=BLU, fontweight="bold")
    _salva(fig, nome)


def immagini_fogli(base, compilato, svincoli):
    V = excel_io.FOGLIO_VASCHE
    disegna_foglio(base, V, "foglio_vasche",
                   numeri={i: i for i in range(1, 12)},
                   larghezze={1: 15, 4: 18, 5: 16, 6: 19, 7: 19, 8: 25, 11: 14})
    disegna_foglio(svincoli, V, "foglio_vasche_svincoli", colonne=[1, 2, 6, 7, 8],
                   larghezze={1: 15, 8: 25},
                   evidenzia={(5, 8): "#fde2c4"})
    disegna_foglio(base, excel_io.FOGLIO_PERCORSO, "foglio_percorso",
                   numeri={i: i - 1 for i in range(2, 8)} | {1: "n"})
    # I parametri: solo nome, valore e unita', con i gruppi a destra
    nomi = list(excel_io.PARAMETRI)

    def riga(nome):
        return nomi.index(nome) + 2

    gruppi = [
        (riga("takt_teorico_s"), riga("takt_delta_positivo_s"), "takt time  (§5.1)"),
        (riga("v_max_vuoto_mm_s"), riga("d_max_carico_mm_s2"), "traslazione  (§5.2)"),
        (riga("ingombro_lato_positivo_mm"), riga("distanza_sicurezza_mm"),
         "ingombri e sicurezza  (§5.3)"),
        (riga("v_max_sollevamento_vuoto_mm_s"), riga("d_max_sollevamento_carico_mm_s2"),
         "sollevamento  (§5.4)"),
        (riga("v_approach_sollevamento_mm_s"), riga("d_approach_sollevamento_mm"),
         "avvicinamento  (§5.4)"),
        (riga("tempo_aggancio_s"), riga("tempo_sgancio_s"), "aggancio / sgancio  (§5.5)"),
        (riga("passo_controllo_distanza_mm"), riga("passo_controllo_distanza_mm"),
         "controllo distanze  (§5.3)"),
        (riga("larghezza_pezzo_mm"), riga("altezza_pezzo_mm"), "solo simulazione  (§5.7)"),
        (riga("max_soste_intermedie"), riga("tempo_limite_per_tentativo_s"),
         "opzioni di calcolo  (§5.6)"),
        (riga("takt_fisso"), riga("takt_fisso"), "takt time  (§5.1)"),
        (riga("interblocco_vasche"), riga("interblocco_vasche"), "ingombri e sicurezza  (§5.3)"),
    ]
    disegna_foglio(base, excel_io.FOGLIO_PARAMETRI, "foglio_parametri",
                   colonne=[1, 2, 3], larghezze={1: 34, 2: 10, 3: 8}, gruppi=gruppi)
    disegna_foglio(base, excel_io.FOGLIO_ZONE, "foglio_zone_vuoto",
                   colonne=[1, 2, 3, 4], larghezze={4: 95})
    disegna_foglio(compilato, excel_io.FOGLIO_ZONE, "foglio_zone",
                   colonne=[1, 2], ultima_riga=4, larghezze={1: 16, 2: 16})
    disegna_foglio(compilato, excel_io.FOGLIO_CAMBIO_QUOTA, "foglio_cambio_quota",
                   colonne=[1, 2, 3, 4, 5], ultima_riga=3,
                   numeri={1: 1, 2: 2, 3: 3, 4: 4, 5: 5})


# ==========================================================================
# 2) Gli schemi
# ==========================================================================

# La linea d'esempio (dal modello): id, posizione, posti, corsa, sgocciolamento,
# ..., larghezza, altezza
_VASCHE = excel_io._righe_esempio()[0]


def _vasca(ax, xc, larghezza, altezza, etichetta=None, liquido=True, y_fondo=0.0,
           colore=VASCA, bordo=VASCA_BORDO, dimensione=7.5):
    ax.add_patch(Rectangle((xc - larghezza / 2, y_fondo), larghezza, altezza,
                           facecolor=colore, edgecolor=bordo, lw=1.2, zorder=2))
    if liquido:
        ax.add_patch(Rectangle((xc - larghezza / 2, y_fondo), larghezza, altezza * 0.82,
                               facecolor=LIQUIDO, edgecolor="none", zorder=2.1))
    if etichetta:
        ax.text(xc, y_fondo - altezza * 0.08, etichetta, ha="center", va="top",
                fontsize=dimensione, fontweight="bold", color="#2c3e50")


def _telaio(ax, xc, y_basso, larghezza, altezza, colore=TELAIO, alpha=1.0):
    ax.add_patch(Rectangle((xc - larghezza / 2, y_basso), larghezza, altezza,
                           facecolor="none", edgecolor=colore, lw=1.6, alpha=alpha,
                           hatch="////", zorder=4))


def _carro(ax, xc, y_rotaia, larghezza, altezza, testo=None, colore=CARRO):
    ax.add_patch(FancyBboxPatch((xc - larghezza / 2, y_rotaia), larghezza, altezza,
                                boxstyle="round,pad=0,rounding_size=40",
                                facecolor=colore, edgecolor="#8a5a14", lw=1.2, zorder=5))
    if testo:
        ax.text(xc, y_rotaia + altezza / 2, testo, ha="center", va="center",
                fontsize=8, fontweight="bold", zorder=6)


def fig_struttura_file():
    fig, ax = plt.subplots(figsize=(10, 2.3))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 22)
    ax.axis("off")
    fogli = [
        ("Istruzioni", "#eeeeee", "spiegazioni:\nnon si legge"),
        ("Vasche", "#d8ead2", "OBBLIGATORIO"),
        ("Percorso", "#d8ead2", "OBBLIGATORIO"),
        ("Parametri", "#d8ead2", "OBBLIGATORIO"),
        ("Zone", "#fff2cc", "facoltativo"),
        ("CambioQuota", "#fff2cc", "facoltativo"),
        ("Ciclogramma", "#dbe5f1", "lo scrive\nil programma"),
        ("Passaggi", "#dbe5f1", "lo scrive\nil programma"),
    ]
    x = 1
    for nome, colore, nota in fogli:
        lt = 11.6
        ax.add_patch(FancyBboxPatch((x, 9), lt, 6, boxstyle="round,pad=0,rounding_size=1",
                                    facecolor=colore, edgecolor="#888", lw=1))
        ax.text(x + lt / 2, 12, nome, ha="center", va="center", fontsize=9, fontweight="bold")
        ax.text(x + lt / 2, 6.8, nota, ha="center", va="top", fontsize=7.5, color="#444")
        x += lt + 0.7
    ax.text(1, 19.5, "Le linguette di un file di linea, nell'ordine in cui le crea "
            "\"Nuovo modello Excel...\"", fontsize=9, color="#333")
    _salva(fig, "struttura_file")


def fig_linea():
    """Vista laterale della linea d'esempio: posizione, larghezza, altezza,
    posti."""
    fig, ax = plt.subplots(figsize=(11, 4.2))
    y_rot = 3300
    ax.plot([-800, 21000], [y_rot, y_rot], color="#555", lw=3)
    ax.text(21000, y_rot + 90, "rotaia", ha="right", va="bottom", fontsize=8, color="#555")
    for id_, pos, posti, corsa, _sg, *_resto, larg, alt, _cov in _VASCHE:
        if larg is None:
            ax.add_patch(Rectangle((pos - 500, 0), 1000, 250, facecolor="#e0e0e0",
                                   edgecolor="#777", lw=1.2))
            ax.text(pos, -120, id_, ha="center", va="top", fontsize=7.5,
                    fontweight="bold", color="#2c3e50")
        else:
            _vasca(ax, pos, larg, alt, id_)
        ax.plot([pos, pos], [-700, y_rot], color=GRIGIO, lw=0.8, ls=":")
        ax.text(pos, -620, f"{pos}", ha="center", va="top", fontsize=7.5, color=BLU)
        if posti == 2:
            _telaio(ax, pos - larg / 4.4, 250, larg / 3.3, alt * 0.7)
            _telaio(ax, pos + larg / 4.4, 250, larg / 3.3, alt * 0.7)
            ax.text(pos, alt + 150, "posti = 2", ha="center", fontsize=8, color=TELAIO,
                    fontweight="bold")
    ax.text(-700, -620, "posizione_mm:", ha="right", va="top", fontsize=7.5, color=BLU)
    # origine e verso
    ax.plot(0, y_rot, marker="o", color=BLU, ms=7, zorder=6)
    ax.text(0, y_rot + 180, "0 mm", ha="center", fontsize=8, color=BLU, fontweight="bold")
    ax.annotate("", xy=(4200, y_rot + 520), xytext=(600, y_rot + 520),
                arrowprops=dict(arrowstyle="->", color=BLU, lw=2))
    ax.text(2400, y_rot + 580, "verso POSITIVO (posizioni crescenti)", ha="center",
            va="bottom", fontsize=8, color=BLU)
    # quota della posizione della zincatura
    _quota(ax, 0, 9500, 2500, "posizione_mm = 9500  (al CENTRO della vasca)", colore=BLU)
    # larghezza e altezza della risciacquo_2
    larg, alt = 1800, 1200
    _quota(ax, 13000 - larg / 2, 13000 + larg / 2, alt + 250, "larghezza_mm")
    ax.annotate("", xy=(13000 + larg / 2 + 300, 0), xytext=(13000 + larg / 2 + 300, alt),
                arrowprops=dict(arrowstyle="<->", color=ROSSO, lw=1.3, shrinkA=0, shrinkB=0))
    ax.text(13000 + larg / 2 + 400, alt / 2, "altezza_mm", color=ROSSO, fontsize=8.5,
            fontweight="bold", va="center")
    ax.set_xlim(-3200, 21200)
    ax.set_ylim(-1000, 4300)
    ax.axis("off")
    _salva(fig, "linea_posizioni")


def fig_corsa_verticale():
    """Una vasca vista di lato: quota di trasporto, corsa verticale,
    sgocciolamento."""
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.4), gridspec_kw={"width_ratios": [1.25, 1]})
    for ax in axs:
        ax.set_xlim(-1700, 1900)
        ax.set_ylim(-300, 3500)
        ax.axis("off")
    # -- pannello 1: corsa verticale ------------------------------------
    ax = axs[0]
    # quote di disegno, non in scala: il telaio immerso deve stare DENTRO la
    # vasca e quello sollevato abbastanza sopra da far vedere lo scolo
    y_rot, larg, alt, corsa = 3300, 1800, 1200, 1550
    y_trasp = 1750  # fondo del telaio a quota di trasporto
    ax.plot([-1700, 1900], [y_rot, y_rot], color="#555", lw=3)
    _carro(ax, 0, y_rot, 1100, 250)
    _vasca(ax, 0, larg, alt, "ZINCATURA")
    ax.plot([0, 0], [y_rot, y_trasp + 600], color="#333", lw=1.5, zorder=3)
    _telaio(ax, 0, y_trasp, 700, 600, alpha=0.35)
    _telaio(ax, 0, y_trasp - corsa, 700, 600)
    ax.plot([-1100, 1500], [y_trasp, y_trasp], color=BLU, lw=1, ls="--")
    ax.text(-1650, y_trasp, "quota di\ntrasporto", fontsize=7.5, color=BLU, va="center")
    ax.plot([-1100, 1500], [y_trasp - corsa, y_trasp - corsa], color=BLU, lw=1, ls="--")
    ax.text(-1650, y_trasp - corsa, "quota di\nimmersione", fontsize=7.5, color=BLU,
            va="center")
    ax.annotate("", xy=(1200, y_trasp - corsa), xytext=(1200, y_trasp),
                arrowprops=dict(arrowstyle="<->", color=ROSSO, lw=1.5, shrinkA=0, shrinkB=0))
    ax.text(1260, y_trasp - corsa / 2, "corsa_\nverticale_mm", color=ROSSO,
            fontsize=8.5, fontweight="bold", va="center")
    ax.set_title("corsa_verticale_mm: di quanto scende il telaio\nin QUESTA vasca",
                 fontsize=9)
    # -- pannello 2: sgocciolamento -------------------------------------
    ax = axs[1]
    ax.plot([-1700, 1900], [y_rot, y_rot], color="#555", lw=3)
    _carro(ax, 0, y_rot, 1100, 250)
    _vasca(ax, 0, larg, alt, "ZINCATURA")
    ax.plot([0, 0], [y_rot, y_trasp + 600], color="#333", lw=1.5, zorder=3)
    _telaio(ax, 0, y_trasp, 700, 600)
    for dx, dy in [(-250, 0), (-60, 180), (150, 60), (300, 260), (-180, 330), (40, 420)]:
        ax.plot(dx, y_trasp - 120 - dy, marker="v", color="#2e86c1", ms=5)
    ax.text(0, -250, "sgocciolamento_s: il telaio, appena\nsollevato, resta FERMO qui "
            "sopra\na scolare, poi il carro parte", ha="center", va="top", fontsize=8,
            color=ROSSO, fontweight="bold")
    ax.set_title("sgocciolamento_s: quanto scola sopra\nQUESTA vasca", fontsize=9)
    ax.set_ylim(-900, 3800)
    axs[0].set_ylim(-900, 3800)
    _salva(fig, "corsa_sgocciolamento")


def _profilo(d, v, a, dec=None, v_in=0.0, v_out=0.0, n=60):
    """Profilo trapezoidale (o triangolare) di un tratto lungo d: tempi e
    posizioni, partendo da v_in e arrivando a v_out."""
    import numpy as np

    dec = dec or a
    da = (v * v - v_in * v_in) / (2 * a)
    dd = (v * v - v_out * v_out) / (2 * dec)
    if da + dd > d:  # triangolare
        vp = ((2 * a * dec * d + dec * v_in ** 2 + a * v_out ** 2) / (a + dec)) ** 0.5
        da = (vp * vp - v_in * v_in) / (2 * a)
        dd = (vp * vp - v_out * v_out) / (2 * dec)
        v = vp
    ta, td = (v - v_in) / a, (v - v_out) / dec
    tc = (d - da - dd) / v
    T = ta + tc + td
    t = np.linspace(0, T, n)
    s = np.where(
        t < ta, v_in * t + a * t * t / 2,
        np.where(t < ta + tc, da + v * (t - ta),
                 da + v * tc + v * (t - ta - tc) - dec * (t - ta - tc) ** 2 / 2))
    vel = np.where(t < ta, v_in + a * t, np.where(t < ta + tc, v, v - dec * (t - ta - tc)))
    return t, s, vel, (ta, tc, td)


def fig_profilo_traslazione():
    import numpy as np

    fig, ax = plt.subplots(figsize=(9, 3.6))
    t, _s, v, (ta, tc, td) = _profilo(6000, 500, 200, 120)
    ax.plot(t, v, color=BLU, lw=2.2, label="spostamento lungo: arriva a v_max")
    t2, _s2, v2, _ = _profilo(700, 500, 200, 120)
    ax.plot(t2 + 0.3, v2, color=ARANCIO, lw=2, ls="--",
            label="spostamento corto: frena prima di arrivare a v_max")
    ax.axhline(500, color=GRIGIO, lw=0.8, ls=":")
    ax.text(t[-1] + 0.2, 500, "v_max_..._mm_s", va="center", fontsize=8.5,
            color=ROSSO, fontweight="bold")
    ax.annotate("a_max_..._mm_s2\n(accelerazione)", xy=(ta * 0.5, 250),
                xytext=(ta * 0.5 + 2.5, 120), fontsize=8.5, color=ROSSO,
                fontweight="bold", arrowprops=dict(arrowstyle="->", color=ROSSO))
    ax.annotate("d_max_..._mm_s2\n(decelerazione)", xy=(ta + tc + td * 0.5, 250),
                xytext=(ta + tc + td * 0.5 - 6.0, 120), fontsize=8.5, color=ROSSO,
                fontweight="bold", arrowprops=dict(arrowstyle="->", color=ROSSO))
    ax.set_xlabel("tempo [s]")
    ax.set_ylabel("velocità [mm/s]")
    ax.set_ylim(0, 620)
    ax.set_xlim(0, t[-1] + 3.5)
    ax.legend(loc="upper center", fontsize=8, frameon=False, ncol=1,
              bbox_to_anchor=(0.45, 1.22))
    ax.spines[["top", "right"]].set_visible(False)
    del np
    _salva(fig, "profilo_traslazione")


def fig_profilo_sollevamento():
    """Velocita' del gancio lungo la corsa verticale, con la zona di
    avvicinamento in fondo (discesa) e in testa (salita)."""
    h, v, a, va_, da_ = 1100, 350, 150, 100, 250
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, scendendo in zip(axs, (True, False)):
        # tratto veloce + tratto lento
        _t, s, vel, _ = _profilo(h - da_, v, a, v_in=0 if scendendo else va_,
                                 v_out=va_ if scendendo else 0)
        if scendendo:
            xs = list(s) + [h - da_, h - 15, h]
            vs = list(vel) + [va_, va_, 0]
        else:
            xs = [0, 15, da_] + [da_ + x for x in s]
            vs = [0, va_, va_] + list(vel)
        ax.plot(xs, vs, color=BLU, lw=2.2)
        z0 = h - da_ if scendendo else 0
        ax.axvspan(z0, z0 + da_, color="#fde2c4", alpha=0.8)
        ax.text(z0 + da_ / 2, 385, "d_approach_\nsollevamento_mm", ha="center",
                va="bottom", fontsize=8, color=ROSSO, fontweight="bold")
        ax.axhline(va_, color=ROSSO, lw=0.9, ls=":")
        ax.axhline(v, color=GRIGIO, lw=0.8, ls=":")
        ax.set_xlim(0, h)
        ax.set_ylim(0, 470)
        ax.set_xlabel("corsa percorsa [mm]  (0 = inizio, " + str(h) + " = corsa_verticale_mm)")
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_title("DISCESA: piano negli ultimi mm, verso il fondo vasca" if scendendo
                     else "SALITA: si stacca piano dal fondo, poi accelera",
                     fontsize=9, pad=28)
    axs[0].set_ylabel("velocità del gancio [mm/s]")
    axs[0].text(30, va_ + 10, "v_approach_sollevamento_mm_s", fontsize=8,
                color=ROSSO, fontweight="bold")
    axs[1].text(h - 20, v + 10, "v_max_sollevamento_..._mm_s", fontsize=8, ha="right",
                color="#555", fontweight="bold")
    fig.tight_layout()
    _salva(fig, "profilo_sollevamento")


def fig_fasi_mossa():
    """Un trasporto da una vasca all'altra: posizione orizzontale e quota del
    gancio nel tempo, con le fasi e il confine dei due tempi in vasca."""
    import numpy as np

    h = 800
    fasi = [  # nome, durata, colore
        ("aggancio", 4, "#f5cba7"),
        ("sollevamento", 8, "#d6eaf8"),
        ("sgocciolamento", 5, "#d5f5e3"),
        ("traslazione", 12, "#fcf3cf"),
        ("immersione", 8, "#d6eaf8"),
        ("sgancio", 4, "#f5cba7"),
    ]
    t0 = 6
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.5, 5.6), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1.5]})
    tt, xx, zz = [0, t0], [0, 0], [-h, -h]
    t = t0
    confini = []
    for nome, dur, col in fasi:
        for ax in (ax1, ax2):
            ax.axvspan(t, t + dur, color=col, alpha=0.9, lw=0)
        ax2.text(t + dur / 2, 180, nome, ha="center", va="bottom", fontsize=7.5,
                 rotation=0 if dur > 4 else 90, fontweight="bold", color="#333")
        s = np.linspace(0, 1, 40)
        ts = t + s * dur
        if nome == "sollevamento":
            z = -h + h * (s ** 1.6 if True else s)
            x = np.zeros_like(s)
        elif nome == "immersione":
            z = -h * (1 - (1 - s) ** 1.6)
            x = np.full_like(s, 4000)
        elif nome == "traslazione":
            z = np.zeros_like(s)
            x = 4000 * (3 * s ** 2 - 2 * s ** 3)
        elif nome in ("aggancio",):
            z, x = np.full_like(s, -h), np.zeros_like(s)
        elif nome == "sgancio":
            z, x = np.full_like(s, -h), np.full_like(s, 4000)
        else:
            z, x = np.zeros_like(s), np.zeros_like(s)
        tt += list(ts)
        xx += list(x)
        zz += list(z)
        confini.append(t)
        t += dur
    tt += [t, t + 6]
    xx += [4000, 4000]
    zz += [-h, -h]
    ax1.plot(tt, xx, color=BLU, lw=2.2)
    ax2.plot(tt, zz, color=TELAIO, lw=2.2)
    ax1.set_ylabel("posizione\nsulla rotaia")
    ax1.set_yticks([0, 4000], ["vasca A", "vasca B"])
    ax2.set_ylabel("quota del telaio")
    ax2.set_yticks([0, -h], ["trasporto", "immersione"])
    ax2.set_ylim(-h - 650, 650)
    ax2.set_xlabel("tempo")
    ax2.set_xticks([])
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
    # i due tempi in vasca
    _quota(ax2, 0, t0, -h - 230, "in vasca A", colore=VERDE, sopra=False)
    _quota(ax2, t, t + 6, -h - 230, "in vasca B", colore=VERDE, sopra=False)
    ax2.text(t0 + 0.2, -h - 300, "◄ il tempo in A finisce\n    quando COMINCIA l'aggancio",
             fontsize=7.5, va="top", color=VERDE)
    ax2.text(t - 0.2, -h - 300, "il tempo in B comincia ►\nquando FINISCE lo sgancio",
             fontsize=7.5, va="top", ha="right", color=VERDE)
    etichette = {
        "aggancio": "tempo_aggancio_s",
        "sollevamento": "corsa_verticale_mm (A)\nv/a/d_max_sollevamento_carico",
        "sgocciolamento": "sgocciolamento_s (A)",
        "traslazione": "posizione_mm A → B\nv/a/d_max_carico",
        "immersione": "corsa_verticale_mm (B)",
        "sgancio": "tempo_sgancio_s",
    }
    # su livelli alterni: le fasi corte non hanno spazio per un testo intero
    for i, ((nome, dur, _c), tc) in enumerate(zip(fasi, confini)):
        livello = 4600 + (i % 2) * 1500
        ax1.plot([tc + dur / 2] * 2, [4100, livello], color=ROSSO, lw=0.7)
        ax1.text(tc + dur / 2, livello, etichette[nome], ha="center", va="bottom",
                 fontsize=7, color=ROSSO, fontweight="bold",
                 bbox=dict(facecolor="white", edgecolor="none", pad=0.5))
    ax1.set_ylim(-500, 7300)
    _salva(fig, "fasi_trasporto")


def fig_permanenza():
    import numpy as np

    teo, dneg, dpos, psotto, psopra = 200, 20, 20, 10, 3
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9.5, 4.6), sharex=True,
                                   gridspec_kw={"height_ratios": [1, 1.6]})
    lo, hi = teo - dneg, teo + dpos
    for ax in (ax1, ax2):
        ax.axvspan(150, lo, color="#f5b7b1", alpha=0.5, lw=0)
        ax.axvspan(hi, 250, color="#f5b7b1", alpha=0.5, lw=0)
        ax.axvspan(lo, hi, color="#d5f5e3", lw=0)
        ax.axvline(teo, color=VERDE, lw=1.8)
        ax.spines[["top", "right"]].set_visible(False)
    ax1.set_yticks([])
    ax1.set_ylim(0, 1)
    ax1.text(teo, 0.83, "permanenza_teorica_s = 200", ha="center", fontsize=8.5,
             color=VERDE, fontweight="bold")
    _quota(ax1, lo, teo, 0.45, "delta_negativo_s = 20")
    _quota(ax1, teo, hi, 0.45, "delta_positivo_s = 20")
    ax1.text(165, 0.15, "VIETATO", ha="center", fontsize=8.5, color=ROSSO, fontweight="bold")
    ax1.text(235, 0.15, "VIETATO", ha="center", fontsize=8.5, color=ROSSO, fontweight="bold")
    ax1.text(lo + 1, 0.15, "180", fontsize=8, color="#555")
    ax1.text(hi - 1, 0.15, "220", fontsize=8, color="#555", ha="right")
    x = np.linspace(lo, hi, 200)
    c = np.where(x < teo, psotto * (teo - x), psopra * (x - teo))
    ax2.plot(x, c, color=BLU, lw=2.2)
    ax2.text(190, 235, "peso_sotto = 10\n(pendenza ripida:\nstare sotto costa molto)",
             fontsize=8, color=BLU, ha="center", fontweight="bold")
    ax2.text(214, 85, "peso_sopra = 3\n(pendenza dolce)", fontsize=8, color=BLU,
             ha="center", fontweight="bold")
    ax2.set_ylabel("quanto 'costa'\nlo scarto")
    ax2.set_yticks([])
    ax2.set_xlabel("tempo effettivo nella vasca ZINCATURA [s]")
    ax2.set_xlim(150, 250)
    ax2.set_ylim(0, 300)
    _salva(fig, "permanenza")


def fig_takt():
    fig, axs = plt.subplots(2, 1, figsize=(9.5, 3.2), sharex=True)
    teo, dneg, dpos = 300, 30, 30
    for ax, fisso in zip(axs, (1, 0)):
        ax.axvspan(teo - dneg, teo + dpos, color="#d5f5e3" if not fisso else "#f2f2f2", lw=0)
        ax.axvline(teo, color=VERDE, lw=1.8)
        ax.set_yticks([])
        ax.set_ylim(0, 1)
        ax.spines[["top", "right", "left"]].set_visible(False)
        if fisso:
            ax.plot(teo, 0.45, marker="o", ms=11, color=VERDE)
            ax.text(232, 0.5, "takt_fisso = 1", fontsize=9, fontweight="bold", va="center")
            ax.text(teo + 4, 0.45, "il ciclo è ESATTAMENTE il teorico; il calcolo\n"
                    "ottimizza solo i tempi in vasca", fontsize=8, va="center")
        else:
            _quota(ax, teo - dneg, teo, 0.62, "takt_delta_negativo_s")
            _quota(ax, teo, teo + dpos, 0.62, "takt_delta_positivo_s")
            ax.annotate("", xy=(teo - dneg + 2, 0.22), xytext=(teo + dpos - 2, 0.22),
                        arrowprops=dict(arrowstyle="->", color=VERDE, lw=2))
            ax.text(teo + 12, 0.08, "cerca il ciclo più CORTO possibile nella banda",
                    fontsize=8, color=VERDE, ha="center")
            ax.text(232, 0.5, "takt_fisso = 0", fontsize=9, fontweight="bold", va="center")
    axs[0].text(teo, 1.02, "takt_teorico_s = 300", ha="center", fontsize=8.5,
                color=VERDE, fontweight="bold")
    axs[1].set_xlabel("takt time [s]")
    axs[1].set_xlim(230, 360)
    _salva(fig, "takt")


def fig_percorso():
    fig, axs = plt.subplots(2, 1, figsize=(10.5, 5.0))
    nomi = [v[0] for v in _VASCHE]
    pos = {v[0]: v[1] for v in _VASCHE}
    percorsi = [
        ([v[0] for v in _VASCHE], "Percorso della linea d'esempio: il pezzo va sempre avanti"),
        (["CARICO", "SGRASSO", "RISCIACQUO_1", "ZINCATURA", "RISCIACQUO_1",
          "PASSIVAZIONE", "SCARICO"],
         "Percorso con una vasca usata due volte (RISCIACQUO_1, tappe 3 e 5): "
         "il pezzo può anche tornare indietro"),
    ]
    for ax, (percorso, titolo) in zip(axs, percorsi):
        for n in nomi:
            usata = n in percorso
            ax.add_patch(Rectangle((pos[n] - 800, 0), 1600, 600,
                                   facecolor=VASCA if usata else "#f2f2f2",
                                   edgecolor=VASCA_BORDO if usata else "#bbb", lw=1.1))
            ax.text(pos[n], 300, n, ha="center", va="center", fontsize=6.5,
                    fontweight="bold", color="#2c3e50" if usata else "#aaa")
        for k, (a, b) in enumerate(zip(percorso, percorso[1:]), start=1):
            avanti = pos[b] > pos[a]
            y = 750 if avanti else -150
            # archi della stessa altezza qualunque sia la distanza; quelli che
            # scavalcano piu' vasche piu' alti, per non coprire i vicini
            d = abs(pos[b] - pos[a])
            rad = -min(0.35, (1100 if d <= 5000 else 2000) / d)
            ax.annotate("", xy=(pos[b], y), xytext=(pos[a], y),
                        arrowprops=dict(arrowstyle="->", color=BLU if avanti else ARANCIO,
                                        lw=1.6, connectionstyle=f"arc3,rad={rad}"))
            ym = y + (1 if avanti else -1) * (abs(rad) * d / 2 + (250 if avanti else 100))
            _bollino(ax, (pos[a] + pos[b]) / 2, ym, str(k), BLU if avanti else ARANCIO)
        ax.set_xlim(-1000, 21000)
        ax.set_ylim(-1300, 2500)
        ax.axis("off")
        ax.set_title(titolo, fontsize=9, loc="left")
    _salva(fig, "percorso")


def fig_ingombri():
    fig, ax = plt.subplots(figsize=(10, 3.4))
    pos_d, neg_d, sic = 1660, 620, 450
    x1 = 2500
    x2 = x1 + pos_d + sic + neg_d
    y = 1000
    ax.plot([0, 7500], [y, y], color="#555", lw=3)
    for xc, nome in ((x1, "carroponte 1"), (x2, "carroponte 2")):
        ax.add_patch(FancyBboxPatch((xc - neg_d, y), neg_d + pos_d, 420,
                                    boxstyle="round,pad=0,rounding_size=50",
                                    facecolor=CARRO, edgecolor="#8a5a14", lw=1.2))
        ax.text(xc + (pos_d - neg_d) / 2, y + 210, nome, ha="center", va="center",
                fontsize=8.5, fontweight="bold")
        ax.plot([xc, xc], [y - 600, y], color="#333", lw=2)
        ax.plot(xc, y - 600, marker="v", color="#333", ms=9)
        ax.text(xc, y - 760, "gancio", ha="center", va="top", fontsize=8)
        _quota(ax, xc - neg_d, xc, y + 950, "ingombro_lato_\nnegativo_mm", dimensione=7.5)
        ax.plot([xc - neg_d] * 2, [y, y + 950], color=ROSSO, lw=0.7, ls=":")
        _quota(ax, xc, xc + pos_d, y + 560, "ingombro_lato_positivo_mm", dimensione=7.5)
        ax.plot([xc, xc], [y, y + 950], color=ROSSO, lw=0.7, ls=":")
    ax.plot([x1 + pos_d] * 2, [y, y + 1500], color=BLU, lw=0.7, ls=":")
    ax.plot([x2 - neg_d] * 2, [y, y + 1500], color=BLU, lw=0.7, ls=":")
    _quota(ax, x1 + pos_d, x2 - neg_d, y + 1500, "distanza_\nsicurezza_mm", colore=BLU,
           dimensione=7.5)
    _quota(ax, x1, x2, y - 1150, "distanza minima fra i ganci = ingombro positivo + "
           "ingombro negativo + distanza di sicurezza", colore=VERDE, sopra=False,
           dimensione=8)
    ax.annotate("", xy=(7300, y + 2300), xytext=(5800, y + 2300),
                arrowprops=dict(arrowstyle="->", color=BLU, lw=2))
    ax.text(6550, y + 2360, "verso positivo", ha="center", fontsize=8, color=BLU)
    ax.set_xlim(0, 7600)
    ax.set_ylim(-600, 3700)
    ax.axis("off")
    _salva(fig, "ingombri")


def fig_svincoli():
    """Il gancio scarico che scavalca una vasca-ostacolo passando dagli
    svincoli."""
    fig, ax = plt.subplots(figsize=(11, 4.6))
    vasche = [("A", 1500, False), ("B", 5000, True), ("C", 8500, False), ("D", 12000, False)]
    larg, alt = 1900, 1100
    z_basso, z_alto, y_rot = 1500, 2600, 3200
    ax.plot([0, 13700], [y_rot, y_rot], color="#555", lw=3)
    for nome, x, ostacolo in vasche:
        _vasca(ax, x, larg, alt, f"vasca {nome}",
               colore="#fde2c4" if ostacolo else VASCA,
               bordo=ARANCIO if ostacolo else VASCA_BORDO, dimensione=8.5)
        if ostacolo:
            ax.add_patch(Rectangle((x - 350, alt), 700, z_basso - alt + 300,
                                   facecolor="#bbbbbb", edgecolor="#555", hatch="xx", lw=1))
            ax.text(x, alt * 0.42, "OSTACOLO:\ntraslazione_con_\ngancio_basso = 0",
                    ha="center", va="center", fontsize=7, color=ARANCIO, fontweight="bold",
                    zorder=6, bbox=dict(facecolor="white", edgecolor=ARANCIO, pad=2))
    # svincoli: a meta' fra due vasche
    sv = [(3250, "svincolo_positivo di A\n= svincolo_negativo di B"),
          (6750, "svincolo_positivo di B\n= svincolo_negativo di C"),
          (10250, "svincolo_positivo di C\n= svincolo_negativo di D")]
    for x, testo in sv:
        ax.plot([x, x], [0, y_rot], color=VERDE, lw=1, ls="--")
        ax.plot(x, 80, marker="^", color=VERDE, ms=10)
        ax.text(x, -380, testo, ha="center", va="top", fontsize=7, color=VERDE,
                fontweight="bold")
    ax.plot([0, 13700], [z_basso, z_basso], color=GRIGIO, lw=0.8, ls=":")
    ax.text(13750, z_basso, "gancio\nbasso", va="center", fontsize=7.5, color=GRIGIO)
    ax.plot([0, 13700], [z_alto, z_alto], color=GRIGIO, lw=0.8, ls=":")
    ax.text(13750, z_alto, "gancio\nalto", va="center", fontsize=7.5, color=GRIGIO)
    # rientro a vuoto A -> C: scavalca B
    px = [1500, 3250, 3250, 6750, 6750, 8500]
    pz = [z_basso, z_basso, z_alto, z_alto, z_basso, z_basso]
    ax.plot(px, pz, color=ROSSO, lw=2.4, zorder=8)
    ax.annotate("", xy=(8500, z_basso), xytext=(7800, z_basso),
                arrowprops=dict(arrowstyle="->", color=ROSSO, lw=2.4), zorder=8)
    for (x, z), n in zip([(2400, z_basso), (3250, (z_basso + z_alto) / 2),
                          (5000, z_alto), (6750, (z_basso + z_alto) / 2),
                          (7650, z_basso)], "12345"):
        _bollino(ax, x, z + (160 if n in "135" else 0), n, ROSSO)
    # rientro C -> D: resta basso
    ax.plot([8500, 12000], [z_basso - 200, z_basso - 200], color=BLU, lw=2.2, ls="--")
    ax.annotate("", xy=(12000, z_basso - 200), xytext=(11400, z_basso - 200),
                arrowprops=dict(arrowstyle="->", color=BLU, lw=2.2))
    ax.text(10250, z_basso - 330, "da C a D: nessun ostacolo,\nresta basso", ha="center",
            va="top", fontsize=7.5, color=BLU,
            bbox=dict(facecolor="white", edgecolor="none", pad=1))
    ax.set_xlim(0, 14500)
    ax.set_ylim(-1300, 3500)
    ax.axis("off")
    _salva(fig, "svincoli")


def fig_zone():
    fig, ax = plt.subplots(figsize=(10.5, 3.3))
    for id_, pos, *_ in _VASCHE:
        ax.add_patch(Rectangle((pos - 800, 2), 1600, 1.0, facecolor=VASCA,
                               edgecolor=VASCA_BORDO, lw=1.1))
        ax.text(pos, 2.5, id_, ha="center", va="center", fontsize=6.5, fontweight="bold")
    pos = {v[0]: v[1] for v in _VASCHE}
    righe = [("carroponte 1  (riga 2)", "CARICO", "ZINCATURA", BLU, 1.2),
             ("carroponte 2  (riga 3)", "ZINCATURA", "SCARICO", ARANCIO, 0.3)]
    for nome, a, b, col, y in righe:
        ax.add_patch(Rectangle((pos[a] - 700, y), pos[b] - pos[a] + 1400, 0.55,
                               facecolor=col, alpha=0.75, edgecolor=col))
        ax.text(pos[a] - 650, y + 0.27, f"{nome}:  vasca_min = {a}   vasca_max = {b}",
                va="center", fontsize=7.5, color="white", fontweight="bold")
    ax.add_patch(Rectangle((pos["ZINCATURA"] - 800, 0.15), 1600, 2.95, facecolor="none",
                           edgecolor=VERDE, lw=2, ls="--"))
    ax.text(pos["ZINCATURA"], 3.25, "in comune: la serve l'uno o l'altro,\n"
            "lo sceglie il calcolo", ha="center", va="bottom", fontsize=7.5,
            color=VERDE, fontweight="bold")
    ax.set_xlim(-1000, 21000)
    ax.set_ylim(0, 4.2)
    ax.axis("off")
    _salva(fig, "zone")


def fig_cambio_quota():
    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    p, q, sgr = 1200, 0, 2500
    ct, i1, i2 = 2500, 600, 1500
    ax.add_patch(Rectangle((q - 450, -250), 900, 250, facecolor="#e0e0e0",
                           edgecolor="#777", lw=1.2))
    ax.text(q, -300, "CARICO\n(corsa_verticale_mm = 0)", ha="center", va="top",
            fontsize=7.5, fontweight="bold")
    _vasca(ax, sgr, 1300, 800, "SGRASSO", y_fondo=-1000)
    # struttura che impone il passaggio
    ax.add_patch(Rectangle((p + 250, 300), 260, 1500, facecolor="#bbbbbb",
                           edgecolor="#555", hatch="xx"))
    ax.text(p + 380, 1850, "passaggio\nobbligato", ha="center", va="bottom", fontsize=7,
            color="#555")
    for z, nome in ((0, "0  (quota più bassa)"), (i1, "intermediate1_mm"),
                    (i2, "intermediate2_mm"), (ct, "corsa_totale_mm  (cima)")):
        ax.plot([-700, 3400], [z, z], color=GRIGIO, lw=0.8, ls=":")
        ax.text(3450, z, nome, va="center", fontsize=8,
                color=ROSSO if z else "#555", fontweight="bold")
    ax.plot([p, p], [-1000, ct + 400], color=VERDE, lw=1.2, ls="--")
    ax.text(p, ct + 430, "posizione_mm\n(punto di cambio quota)", ha="center",
            va="bottom", fontsize=8, color=VERDE, fontweight="bold")
    passi = [
        ([2500, p], [0, 0], "1"),
        ([p, p], [0, i1], "2"),
        ([p, q], [i1, i1], "3"),
        ([q, q], [i1, i2], "4"),
        ([q, p], [i2, i2], "5"),
        ([p, p], [i2, ct], "6"),
    ]
    for xs, zs, n in passi:
        ax.annotate("", xy=(xs[1], zs[1]), xytext=(xs[0], zs[0]),
                    arrowprops=dict(arrowstyle="->", color=ROSSO, lw=2.2,
                                    shrinkA=0, shrinkB=0))
        dx = 130 if xs[0] == xs[1] else 0
        dz = 0 if xs[0] == xs[1] else 120
        _bollino(ax, (xs[0] + xs[1]) / 2 + dx, (zs[0] + zs[1]) / 2 + dz, n)
    _telaio(ax, q, i1 - 450 + 450, 500, 380, alpha=0.3)
    ax.set_xlim(-800, 5200)
    ax.set_ylim(-1500, 3400)
    ax.axis("off")
    _salva(fig, "cambio_quota")


def prepara_immagini() -> str:
    os.makedirs(IMG, exist_ok=True)
    with tempfile.TemporaryDirectory() as cartella:
        base, compilato, svincoli, messaggio = _libri_esempio(cartella)
        immagini_fogli(base, compilato, svincoli)
    fig_struttura_file()
    fig_linea()
    fig_corsa_verticale()
    fig_fasi_mossa()
    fig_profilo_traslazione()
    fig_profilo_sollevamento()
    fig_permanenza()
    fig_takt()
    fig_percorso()
    fig_ingombri()
    fig_svincoli()
    fig_zone()
    fig_cambio_quota()
    return messaggio


# ==========================================================================
# 3) Il testo
# ==========================================================================
#
# Stesse voci del manuale operatore (vedi genera_manuale_operatore.py):
#   h1/h2/h3, p, b, n, img, tab, nota, code, pagina


def _tabella_parametri():
    righe = []
    for nome, (unita, obbligatorio, default, descr) in excel_io.PARAMETRI.items():
        righe.append([
            f"**{nome}**" if obbligatorio else nome,
            unita,
            "sì" if obbligatorio else f"no ({default})",
            descr[0].upper() + descr[1:] + ".",
        ])
    return righe


def contenuto(messaggio_errore: str):
    return [
        ("h1", "1. Introduzione"),
        ("p", "CraneStrike legge la descrizione della linea da un **file Excel**: "
              "le vasche, il percorso del pezzo e i parametri dei carroponti. "
              "Questo documento spiega, foglio per foglio e colonna per colonna, "
              "**cosa scrivere in ogni cella e che cosa rappresenta sull'impianto**. "
              "Ogni parametro geometrico o di tempo è accompagnato da uno schema."),
        ("p", "Gli esempi sono quelli della linea d'esempio che il programma "
              "fornisce: sette stazioni, dal carico allo scarico passando per "
              "sgrassatura, risciacqui, zincatura e passivazione."),
        ("h2", "1.1 Da dove si parte"),
        ("p", "Non si crea il file a mano: si parte sempre dal **modello**, che ha già "
              "tutti i fogli, le intestazioni giuste e una linea d'esempio "
              "funzionante da modificare."),
        ("b", "Dall'interfaccia: pulsante `Nuovo modello Excel...`."),
        ("b", "Da riga di comando: `python excel_io.py linea.xlsx`."),
        ("p", "La stessa linea si può anche compilare nella finestra `Dati linea...` "
              "dell'interfaccia: ha **le stesse tabelle con gli stessi nomi di "
              "colonna** e fa gli stessi controlli. Tutto quello che segue vale "
              "per entrambe; con `Salva come Excel...` la finestra scrive un file "
              "identico a quello descritto qui."),
        ("img", "05_dati_linea_vasche", 14.0,
         "La finestra Dati linea: stesse schede e stesse colonne dei fogli Excel."),
        ("h2", "1.2 I fogli del file"),
        ("img", "struttura_file", 16.0, "I fogli di un file di linea."),
        ("tab", ["foglio", "serve?", "contenuto"], [
            ["Istruzioni", "-", "Promemoria di compilazione. Il programma non lo legge."],
            ["Vasche", "obbligatorio", "Una riga per vasca fisica: dove sta, quanti posti, "
             "quanto è profonda, quanto scola. Capitolo 3."],
            ["Percorso", "obbligatorio", "Le tappe del pezzo in ordine, con i tempi di "
             "permanenza. Capitolo 4."],
            ["Parametri", "obbligatorio", "Takt time, velocità, ingombri dei carroponti, "
             "opzioni di calcolo. Capitolo 5."],
            ["Zone", "facoltativo", "Fin dove arriva ogni carroponte. Vuoto = decide il "
             "programma. Capitolo 6."],
            ["CambioQuota", "facoltativo", "Solo per impianti con un punto obbligato di "
             "cambio quota al carico o allo scarico. Capitolo 7."],
            ["Ciclogramma, Passaggi", "scritti dal programma", "Il ciclogramma salvato, "
             "per riprenderlo. Non si compilano a mano. Capitolo 8."],
        ], [3.4, 2.8, 10.4]),
        ("h2", "1.3 Regole generali"),
        ("b", "**Unità di misura**: lunghezze in **millimetri** (mm), tempi in "
              "**secondi** (s), velocità in mm/s, accelerazioni in mm/s². Il nome "
              "della colonna o del parametro finisce sempre con l'unità: "
              "`posizione_mm`, `sgocciolamento_s`, `v_max_vuoto_mm_s`..."),
        ("b", "**Non cambiare** i nomi dei fogli, le intestazioni delle colonne e i nomi "
              "nella colonna A del foglio Parametri: il programma li cerca per nome."),
        ("b", "**Non scrivere note nelle colonne dei dati**: verrebbero lette come "
              "valori. Usa il foglio Istruzioni o le colonne a destra di quelle "
              "compilate."),
        ("b", "Le **righe vuote** si possono lasciare: vengono saltate."),
        ("b", "I numeri con la **virgola decimale** scritti come testo («2,5») sono "
              "accettati."),
        ("b", "Le vasche si richiamano sempre per **id**, esattamente come scritto nel "
              "foglio Vasche (maiuscole comprese)."),
        ("b", "Una cella **vuota** e una cella con **0** non sono la stessa cosa: dove "
              "un valore è obbligatorio, 0 è una dichiarazione («qui non serve»), "
              "il vuoto è un errore."),
        ("h2", "1.4 Il sistema di riferimento"),
        ("p", "Tutte le posizioni orizzontali sono misurate **lungo la rotaia**, in "
              "mm, da uno zero scelto liberamente (di solito il carico). Il verso "
              "delle posizioni crescenti si chiama **positivo**, quello opposto "
              "**negativo**: i parametri «lato positivo / negativo» (svincoli, "
              "ingombri) si riferiscono a questo verso."),
        ("img", "linea_posizioni", 16.5,
         "La linea d'esempio vista di lato. La posizione di ogni vasca è quella del "
         "suo CENTRO, cioè dove il gancio prende e posa il telaio."),

        ("pagina",),
        ("h1", "2. Prima di cominciare: cosa succede in un trasporto"),
        ("p", "Quasi tutti i parametri descrivono un pezzo di questa sequenza. "
              "Conviene averla in mente prima di compilare: il carroponte, sopra la "
              "vasca A, **aggancia** il telaio, lo **solleva** fino alla quota di "
              "trasporto, lo tiene fermo a **sgocciolare**, **trasla** fino alla "
              "vasca B, lo **immerge** e lo **sgancia**. Poi torna a vuoto verso "
              "il trasporto successivo."),
        ("img", "fasi_trasporto", 16.5,
         "Un trasporto dalla vasca A alla vasca B: in alto la posizione sulla rotaia, "
         "in basso la quota del telaio. In rosso i parametri che decidono la "
         "durata di ogni fase."),
        ("p", "Da notare il confine dei **tempi in vasca** (in verde): il tempo nella "
              "vasca A finisce quando comincia l'aggancio, quello in B comincia "
              "quando finisce lo sgancio. Aggancio e sgancio sono tempo del gancio, "
              "non del processo: per questo stanno fra i Parametri e non si "
              "sommano alla permanenza del foglio Percorso."),

        ("pagina",),
        ("h1", "3. Foglio Vasche"),
        ("p", "**Una riga per vasca fisica**, in qualunque ordine. Le stazioni di "
              "carico e scarico sono vasche anche loro (senza corsa e senza "
              "sgocciolamento). Una vasca usata due volte dal percorso si scrive "
              "qui una volta sola."),
        ("img", "foglio_vasche", 16.5,
         "Il foglio Vasche del modello. I numeri rossi rimandano alla tabella."),
        ("tab", ["#", "colonna", "unità", "serve?", "significato"], [
            ["1", "**id**", "-", "sì", "Nome della vasca. Unico; è il nome con cui la "
             "si richiama negli altri fogli."],
            ["2", "**posizione_mm**", "mm", "sì", "Posizione del CENTRO della vasca "
             "lungo la rotaia (§3.1)."],
            ["3", "posti", "-", "no (1)", "Quanti telai ci stanno dentro "
             "contemporaneamente (§3.1)."],
            ["4", "**corsa_verticale_mm**", "mm", "sì", "Di quanto scende il telaio fra "
             "quota di trasporto e immersione, in questa vasca. 0 dove non c'è "
             "movimento verticale (§3.2)."],
            ["5", "**sgocciolamento_s**", "s", "sì", "Quanto il telaio resta fermo sopra "
             "la vasca a scolare dopo il sollevamento. 0 dove non serve (§3.2)."],
            ["6", "svincolo_negativo_mm", "mm", "no", "Posizione assoluta, prima della "
             "vasca, dove il gancio scarico può salire e scendere (§3.3)."],
            ["7", "svincolo_positivo_mm", "mm", "no", "Come sopra, dopo la vasca (§3.3)."],
            ["8", "traslazione_con_gancio_basso", "0/1", "no (1)", "0 = la vasca è un "
             "OSTACOLO che il gancio calato non può scavalcare (§3.3)."],
            ["9", "larghezza_mm", "mm", "no", "Larghezza lungo la rotaia. Solo per la "
             "simulazione (§3.4)."],
            ["10", "altezza_mm", "mm", "no", "Altezza della vasca. Solo per la "
             "simulazione (§3.4)."],
            ["11", "cover_presente", "0/1", "no (0)", "1 = la vasca ha un coperchio "
             "(§3.4)."],
        ], [0.7, 4.6, 1.2, 1.6, 8.5]),
        ("p", "In grassetto le colonne obbligatorie; fra parentesi il valore che vale "
              "una cella lasciata vuota."),
        ("h2", "3.1 Posizione e posti"),
        ("p", "`posizione_mm` è la distanza del **centro** della vasca dallo zero "
              "della rotaia: è il punto in cui il gancio si ferma per prendere o "
              "posare il telaio. Due vasche non possono avere la stessa posizione. "
              "Le distanze fra le posizioni determinano i tempi di traslazione."),
        ("p", "`posti` dice quanti telai la vasca contiene **nello stesso momento**. "
              "Nella linea d'esempio la ZINCATURA ha 2 posti (figura del §1.4): due pezzi "
              "possono essere in bagno insieme, e il programma ne tiene conto per "
              "rispettare tempi lunghi senza allungare il takt time."),
        ("h2", "3.2 Corsa verticale e sgocciolamento"),
        ("img", "corsa_sgocciolamento", 16.0,
         "A sinistra la corsa verticale, a destra lo sgocciolamento."),
        ("p", "`corsa_verticale_mm` è il dislivello che il telaio percorre fra la "
              "quota di trasporto e il fondo, **in quella vasca**: vasche più "
              "profonde hanno corse più lunghe e quindi sollevamenti più lenti. "
              "Per carico e scarico, dove il telaio non si immerge, si scrive **0**."),
        ("p", "`sgocciolamento_s` è il tempo in cui il telaio, appena sollevato, "
              "resta sospeso **sopra quella vasca** prima che il carro parta. "
              "Dipende dal bagno (una zincatura scola più a lungo di un "
              "risciacquo). Si scrive **0** dove non serve."),
        ("h2", "3.3 Svincoli e vasche-ostacolo"),
        ("p", "Queste tre colonne servono **solo** agli impianti in cui il gancio "
              "scarico, calato, non può passare sopra certe vasche (per esempio per "
              "una struttura, una cappa, un coperchio alto). Nella maggior parte "
              "delle linee **si lasciano vuote**: il gancio scarico trasla basso "
              "ovunque e non paga nessuna salita o discesa."),
        ("img", "svincoli", 16.5,
         "Il rientro a vuoto da A a C deve scavalcare l'ostacolo B: (1) trasla basso "
         "fino allo svincolo positivo di A, (2) sale, (3) passa alto sopra B, (4) "
         "scende sullo svincolo negativo di C, (5) trasla basso fino a C. Da C a D "
         "non c'è ostacolo e il gancio resta basso."),
        ("b", "`traslazione_con_gancio_basso` = **0** marca la vasca come ostacolo. "
              "Vuoto o 1 = vasca normale."),
        ("b", "`svincolo_negativo_mm` e `svincolo_positivo_mm` sono le posizioni "
              "**assolute** sulla rotaia (non distanze dalla vasca) in cui il gancio "
              "scarico può cambiare quota: mai sopra il centro di una vasca."),
        ("b", "Lo svincolo **negativo** deve cadere fra la vasca precedente e questa; "
              "il **positivo** fra questa e la successiva. L'ordine delle colonne è "
              "quello della rotaia: prima il negativo (a sinistra), poi il positivo."),
        ("b", "Se una vasca ha uno svincolo, devono averne **almeno uno tutte** le "
              "vasche: qualunque vasca può essere l'inizio o la fine di un rientro "
              "che deve passare alto."),
        ("b", "Una vasca-ostacolo senza svincoli è un errore: il gancio non avrebbe "
              "dove salire."),
        ("img", "foglio_vasche_svincoli", 11.5,
         "La linea d'esempio con gli svincoli a metà fra una vasca e l'altra e la "
         "ZINCATURA marcata come ostacolo (cella evidenziata)."),
        ("h2", "3.4 Colonne solo per la simulazione e coperchi"),
        ("p", "`larghezza_mm` e `altezza_mm` **non entrano in nessun calcolo**: "
              "servono solo a disegnare le vasche in proporzione nella simulazione "
              "(figura del §1.4). Se mancano, la simulazione usa proporzioni "
              "convenzionali."),
        ("p", "`cover_presente` = 1 indica una vasca con coperchio. Non cambia il "
              "ciclogramma: nel foglio SequenzaCarri dei risultati il carro, "
              "arrivato sulla vasca, apre il coperchio prima di scendere e lo "
              "richiude dopo essere risalito."),

        ("pagina",),
        ("h1", "4. Foglio Percorso"),
        ("p", "**Una riga per tappa, nell'ordine in cui il pezzo attraversa la "
              "linea.** È l'ordine delle righe a definire la sequenza: la prima "
              "riga è di solito il CARICO, l'ultima lo SCARICO. Servono almeno "
              "due tappe."),
        ("img", "foglio_percorso", 13.5, "Il foglio Percorso del modello."),
        ("tab", ["#", "colonna", "unità", "serve?", "significato"], [
            ["n", "n", "-", "no", "Numero della tappa. Non decide l'ordine: serve a "
             "scoprire un foglio riordinato per sbaglio (se la numerazione salta, "
             "è un errore)."],
            ["1", "**vasca**", "-", "sì", "L'id della vasca, come nel foglio Vasche."],
            ["2", "**permanenza_teorica_s**", "s", "sì", "Il tempo di bagno voluto dalla "
             "ricetta (§4.2)."],
            ["3", "**delta_negativo_s**", "s", "sì", "Di quanto si può stare MENO del "
             "teorico. Positivo (§4.2)."],
            ["4", "**delta_positivo_s**", "s", "sì", "Di quanto si può stare PIÙ del "
             "teorico. Positivo (§4.2)."],
            ["5", "peso_sotto", "-", "no (1)", "Quanto pesa ogni secondo SOTTO il "
             "teorico (§4.3)."],
            ["6", "peso_sopra", "-", "no (1)", "Quanto pesa ogni secondo SOPRA il "
             "teorico (§4.3)."],
        ], [0.7, 4.6, 1.2, 1.6, 8.5]),
        ("h2", "4.1 L'ordine delle tappe"),
        ("img", "percorso", 16.5,
         "In alto il percorso d'esempio. In basso un percorso in cui RISCIACQUO_1 "
         "compare due volte: le frecce arancioni sono trasporti all'indietro."),
        ("p", "La stessa vasca può comparire **più volte** nel percorso: i pezzi delle "
              "diverse tappe si contendono gli stessi posti, e il calcolo ne tiene "
              "conto. Non ordinare mai il foglio (per esempio alfabeticamente): "
              "cambierebbe il percorso."),
        ("h2", "4.2 Permanenza teorica e tolleranze"),
        ("img", "permanenza", 15.0,
         "In alto: la finestra ammessa per la ZINCATURA d'esempio (200 s, −20/+20). In "
         "basso: come i pesi rendono più o meno «cari» gli scarti dal teorico."),
        ("p", "La permanenza è il tempo **effettivo** in bagno: da quando il telaio è "
              "sganciato in fondo alla vasca a quando comincia l'aggancio "
              "successivo (capitolo 2). Si dichiara come un valore **teorico** più "
              "due tolleranze: il programma lavora sempre fra "
              "**teorico − delta_negativo** e **teorico + delta_positivo**; "
              "fuori da questa finestra non va mai."),
        ("b", "I due delta sono **ampiezze**: si scrivono **positivi** tutti e due "
              "(«20», non «−20»). È il programma a sottrarre e sommare."),
        ("b", "Delta a **0** = permanenza rigida, esattamente il teorico."),
        ("b", "`delta_negativo_s` non può superare la permanenza teorica."),
        ("b", "Per CARICO e SCARICO si scrive in genere 0 / 0 / 0."),
        ("b", "Finestre più larghe danno più libertà al calcolo e permettono takt "
              "time più corti."),
        ("h2", "4.3 I pesi dello scarto"),
        ("p", "Dentro la finestra il programma cerca i tempi **più vicini ai "
              "teorici**. I pesi dicono dove è meglio spendere lo scarto quando non "
              "si può stare sul teorico ovunque:"),
        ("b", "più è alto il peso, più il calcolo cerca di tenere quella tappa sul "
              "teorico;"),
        ("b", "`peso_sotto` e `peso_sopra` distinguono le due direzioni: "
              "nell'esempio la ZINCATURA ha 10 e 3, cioè stare sotto il teorico "
              "è più grave che starci sopra;"),
        ("b", "0 = indifferente; vuoto = 1."),
        ("p", "I pesi non allargano mai la finestra: le soglie restano rigide."),

        ("pagina",),
        ("h1", "5. Foglio Parametri"),
        ("p", "**Una riga per parametro**: nome in colonna A, valore in colonna B. "
              "Unità e descrizione (colonne C e D) sono solo un promemoria. I "
              "parametri facoltativi si possono lasciare vuoti o cancellare: vale "
              "il loro default. L'ordine delle righe non conta."),
        ("img", "foglio_parametri", 15.5,
         "Il foglio Parametri del modello (colonne A–C), con i gruppi trattati nei "
         "paragrafi seguenti."),
        ("h2", "5.1 Takt time"),
        ("p", "Il **takt time** è il periodo del ciclo: ogni quanti secondi un pezzo "
              "esce dalla linea. Si dichiara come le permanenze: un teorico e due "
              "tolleranze positive."),
        ("img", "takt", 15.0, "I parametri del takt time e l'effetto di takt_fisso."),
        ("tab", ["parametro", "significato"], [
            ["**takt_teorico_s**", "Il ciclo a cui la linea è pensata."],
            ["**takt_delta_negativo_s**", "Di quanto il ciclo può scendere sotto il "
             "teorico. Deve essere minore del teorico."],
            ["**takt_delta_positivo_s**", "Di quanto il ciclo può salire sopra il teorico."],
            ["takt_fisso", "1 (default) = il takt resta il teorico e si ottimizzano solo "
             "i tempi in vasca. 0 = si cerca il takt più piccolo nella banda, poi i "
             "tempi in vasca più vicini ai teorici."],
        ], [5.0, 11.6]),
        ("p", "Una banda larga dà più libertà al calcolo ma lo rende più lento: se "
              "il calcolo non conclude, stringerla."),
        ("h2", "5.2 Traslazione del carroponte"),
        ("p", "Sei parametri, tre per il carroponte **vuoto** (rientri) e tre per "
              "il carroponte **col pezzo**: velocità massima, accelerazione e "
              "decelerazione."),
        ("img", "profilo_traslazione", 14.5,
         "Velocità di una traslazione nel tempo: rampa di accelerazione, tratto a "
         "velocità massima, rampa di frenata."),
        ("tab", ["parametro", "unità", "significato"], [
            ["**v_max_vuoto_mm_s**", "mm/s", "Velocità massima a vuoto."],
            ["**a_max_vuoto_mm_s2**", "mm/s²", "Accelerazione a vuoto."],
            ["d_max_vuoto_mm_s2", "mm/s²", "Decelerazione a vuoto. Vuoto = come "
             "l'accelerazione."],
            ["**v_max_carico_mm_s**", "mm/s", "Velocità massima col pezzo."],
            ["**a_max_carico_mm_s2**", "mm/s²", "Accelerazione col pezzo."],
            ["d_max_carico_mm_s2", "mm/s²", "Decelerazione col pezzo. Vuoto = come "
             "l'accelerazione."],
        ], [5.0, 1.6, 10.0]),
        ("p", "Sugli spostamenti brevi il carroponte non fa in tempo ad arrivare alla "
              "velocità massima (curva tratteggiata): per questo conta anche "
              "l'accelerazione, non solo la velocità."),
        ("h2", "5.3 Ingombri, distanza di sicurezza e interblocco"),
        ("p", "Quando sulla stessa rotaia lavorano più carroponti, il programma "
              "garantisce che non si avvicinino mai troppo. La distanza si misura "
              "fra i **ganci**, e il carro sporge dal gancio in modo diverso nei "
              "due versi."),
        ("img", "ingombri", 15.5, "Ingombri del carro e distanza di sicurezza."),
        ("tab", ["parametro", "significato"], [
            ["**ingombro_lato_positivo_mm**", "Quanto sporge il carro dal gancio verso "
             "le posizioni crescenti."],
            ["**ingombro_lato_negativo_mm**", "Quanto sporge il carro dal gancio verso "
             "le posizioni decrescenti."],
            ["**distanza_sicurezza_mm**", "Margine minimo aggiuntivo fra due carri "
             "vicini."],
            ["interblocco_vasche", "1 (default) = un carroponte non parte verso una "
             "vasca condivisa (o a ridosso del confine con il vicino) finché il vicino "
             "non l'ha lasciata. 0 = conta solo la distanza di sicurezza."],
            ["passo_controllo_distanza_mm", "Ogni quanti mm il calcolo controlla la "
             "distanza (default 200). NON è un margine di sicurezza: la distanza "
             "garantita resta la stessa. Abbassarlo (100, 50) se una linea con vasche "
             "vicine esce impossibile o con takt troppo alto; costa solo tempo di "
             "calcolo."],
        ], [5.4, 11.2]),
        ("h2", "5.4 Sollevamento e zona di avvicinamento"),
        ("p", "Come per la traslazione, velocità, accelerazione e decelerazione "
              "**verticali**, separate per gancio scarico e gancio col telaio: "
              "`v_max_sollevamento_vuoto_mm_s`, `a_max_sollevamento_vuoto_mm_s2`, "
              "`d_max_sollevamento_vuoto_mm_s2` e le tre corrispondenti "
              "`..._carico_...`. Le decelerazioni sono facoltative (vuoto = come "
              "l'accelerazione)."),
        ("p", "La **zona di avvicinamento** sono gli ultimi millimetri di corsa vicino "
              "al punto in cui il telaio viene preso o posato, percorsi a velocità "
              "ridotta per non urtare:"),
        ("img", "profilo_sollevamento", 16.0,
         "Velocità del gancio lungo la corsa: la zona di avvicinamento (in arancio) "
         "sta alla fine della discesa e all'inizio della salita."),
        ("b", "`v_approach_sollevamento_mm_s`: la velocità ridotta. Non può superare "
              "le velocità massime di sollevamento."),
        ("b", "`d_approach_sollevamento_mm`: quanti mm di corsa si fanno a quella "
              "velocità."),
        ("b", "Vanno compilati **tutti e due o nessuno** (nessuno = nessun "
              "avvicinamento). Non si applicano alle stazioni servite da una zona "
              "di cambio quota."),
        ("h2", "5.5 Aggancio e sgancio"),
        ("p", "`tempo_aggancio_s` e `tempo_sgancio_s` (default 0) sono i secondi che "
              "servono per agganciare il telaio prima di sollevarlo e per sganciarlo "
              "dopo averlo immerso (capitolo 2). **Non** sono tempo in vasca: il bagno "
              "finisce quando comincia l'aggancio e comincia quando lo sgancio è "
              "finito."),
        ("h2", "5.6 Opzioni di calcolo"),
        ("tab", ["parametro", "default", "significato"], [
            ["max_carroponti", "10", "Limite al numero di carroponti che la ricerca "
             "automatica può provare. Non conta se il foglio Zone è compilato."],
            ["tempo_limite_per_tentativo_s", "120", "Quanti secondi può durare ogni "
             "singolo tentativo del solutore. Alzarlo sulle linee grandi."],
            ["max_soste_intermedie", "2", "Quante vasche intermedie il calcolo può "
             "usare per far aspettare un carro vuoto lontano dal vicino. 0 = nessuna "
             "sosta intermedia. Valori alti rendono il calcolo molto più pesante: se "
             "diventa lento, riportarlo a 1 o 0."],
        ], [5.4, 1.6, 9.6]),
        ("h2", "5.7 Parametri solo per la simulazione"),
        ("p", "`larghezza_pezzo_mm` e `altezza_pezzo_mm` servono solo a disegnare il "
              "pezzo in proporzione alle vasche nella simulazione. Non entrano in "
              "nessun calcolo; vuoti = misura convenzionale."),
        ("h2", "5.8 Tabella riassuntiva"),
        ("p", "Tutti i parametri, nell'ordine del foglio. In grassetto gli "
              "obbligatori; per i facoltativi, fra parentesi, il valore usato se la "
              "cella è vuota («None» = funzione disattivata o, per le decelerazioni, "
              "uguale all'accelerazione)."),
        ("tab", ["parametro", "unità", "obbligatorio", "descrizione"],
         _tabella_parametri(), [5.2, 1.4, 2.0, 8.0]),

        ("pagina",),
        ("h1", "6. Foglio Zone (facoltativo)"),
        ("p", "**Lascialo vuoto** se i carroponti possono arrivare dappertutto: il "
              "numero di carroponti e le zone di competenza li sceglie il "
              "programma. Nel modello il foglio contiene solo una nota in "
              "colonna D, che non viene letta."),
        ("img", "foglio_zone_vuoto", 15.0, "Il foglio Zone del modello: vuoto."),
        ("p", "Si compila quando l'impianto ha carroponti con corse limitate: **una "
              "riga per carroponte, nell'ordine della linea** (il primo è quello "
              "del carico), con l'id della vasca **minima** e **massima** che può "
              "raggiungere. Il numero di righe è il numero di carroponti."),
        ("img", "foglio_zone", 6.0, "Due carroponti: il primo dal carico alla zincatura, "
         "il secondo dalla zincatura allo scarico."),
        ("img", "zone", 16.0, "Le due righe della figura precedente, sulla linea."),
        ("b", "È un **limite**, non un'assegnazione: il programma può far servire a "
              "un carroponte anche solo una parte del suo tratto, ma mai mandarlo "
              "oltre."),
        ("b", "I tratti di carroponti vicini **possono sovrapporsi**: le vasche in "
              "comune le servirà l'uno o l'altro, a scelta del calcolo."),
        ("b", "Ogni riga vuole **tutte e due** le vasche."),

        ("pagina",),
        ("h1", "7. Foglio CambioQuota (facoltativo)"),
        ("p", "**Lascialo vuoto** se il carroponte può salire e scendere dove si "
              "trova: è il caso normale. Serve agli impianti in cui, sopra il "
              "carico o lo scarico, il carroponte non può cambiare quota (una "
              "porta, un tunnel, una struttura) e deve prima portarsi in un punto "
              "dedicato. Al massimo due righe: una per il carico, una per lo "
              "scarico."),
        ("img", "foglio_cambio_quota", 11.0, "Una zona di cambio quota al carico."),
        ("tab", ["#", "colonna", "significato"], [
            ["1", "zona", "«carico» (fra il carico e la prima vasca) oppure «scarico» "
             "(fra l'ultima vasca e lo scarico)."],
            ["2", "posizione_mm", "Dove sta il punto di cambio quota sulla rotaia. Deve "
             "cadere fra la stazione servita e quella accanto."],
            ["3", "intermediate1_mm", "Quota a cui il gancio arriva alla stazione e a cui "
             "vi posa il telaio."],
            ["4", "intermediate2_mm", "Quota a cui il telaio viene sollevato prima di "
             "lasciare la stazione."],
            ["5", "corsa_totale_mm", "Distanza da 0 fino alla cima (quota di trasporto)."],
        ], [0.7, 3.6, 12.3]),
        ("p", "**Le quote si misurano dal basso**: 0 è la quota più bassa del "
              "carroponte, quella a cui trasla col gancio calato."),
        ("img", "cambio_quota", 15.0,
         "Il giro al CARICO con i valori della figura precedente: (1) arriva basso al "
         "punto di cambio quota, (2) sale a intermediate1, (3) trasla al carico, (4) "
         "prende il telaio salendo a intermediate2, (5) torna al punto di cambio "
         "quota, (6) sale in cima. Allo SCARICO il giro è lo stesso al contrario."),
        ("b", "Servono tutti e quattro i numeri: una riga compilata a metà è un "
              "errore."),
        ("b", "Il tempo di tutto il giro è contato nella presa (o nel rilascio) di "
              "quella stazione."),
        ("b", "La `corsa_verticale_mm` del carico e dello scarico nel foglio Vasche "
              "deve restare **0**: lì la corsa è definita da questo foglio."),

        ("h1", "8. Fogli scritti dal programma"),
        ("p", "Quando si salvano i risultati, il programma riscrive la linea nello "
              "stesso file, insieme a due fogli che **non si compilano a mano**:"),
        ("b", "**Ciclogramma**: il ciclogramma calcolato o composto, per riprenderlo "
              "riaprendo il file. Le colonne tempo_teorico_s e scarto_s sono solo "
              "da leggere (si riscrivono a ogni salvataggio): per cambiare un tempo "
              "teorico si modifica il foglio Percorso. Cancellare il foglio per "
              "ripartire da zero."),
        ("b", "**Passaggi**: i punti di passaggio aggiunti a mano sul grafico."),
        ("p", "Il loro uso è descritto nel manuale operatore."),

        ("pagina",),
        ("h1", "9. Errori di compilazione"),
        ("p", "All'apertura il programma controlla tutto il file e riporta **tutti "
              "gli errori insieme**, ognuno con foglio e cella fra parentesi "
              "quadre: si corregge il file una volta sola. Esempio, con tre errori "
              "fatti apposta (velocità scritta con l'unità, id della vasca "
              "sbagliato, delta scritto col segno meno):"),
        ("code", messaggio_errore),
        ("h2", "Gli errori più frequenti"),
        ("tab", ["sintomo", "causa e rimedio"], [
            ["«atteso un numero, trovato ...»", "Nella cella c'è testo o un'unità di "
             "misura («5,5 m»). Scrivere solo il numero, nell'unità del nome di "
             "colonna."],
            ["«valore mancante»", "Una cella obbligatoria è vuota. Se il dato non serve "
             "(per esempio la corsa del carico) scrivere 0."],
            ["«la vasca '...' non è definita nel foglio Vasche»", "Id scritto in modo "
             "diverso nei due fogli (refuso, spazio, maiuscole)."],
            ["«... negativa: i due delta sono ampiezze»", "Togliere il segno meno: i "
             "delta si scrivono positivi."],
            ["«la numerazione salta o non è in ordine»", "Il foglio Percorso è stato "
             "ordinato o una riga spostata. Rimettere le righe nell'ordine del "
             "percorso."],
            ["«parametro '...' non riconosciuto»", "Nome modificato nella colonna A dei "
             "Parametri. Il messaggio elenca i nomi ammessi."],
            ["«... è un nome della versione in METRI»", "File di una versione vecchia: "
             "rigenerare il modello e ricopiare i dati moltiplicando per 1000."],
            ["«i due svincoli ... sembrano scambiati»", "Svincolo negativo e positivo "
             "invertiti: in F va quello PRIMA della vasca, in G quello DOPO."],
            ["«alcune vasche hanno una posizione di svincolo e altre no»", "Se si usano "
             "gli svincoli, ogni vasca ne deve avere almeno uno."],
        ], [6.0, 10.6]),

        ("h1", "10. Lista di controllo"),
        ("n", "Ogni vasca fisica ha una riga in Vasche, con id unico e posizione del "
              "centro in mm."),
        ("n", "Corsa verticale e sgocciolamento sono compilati per tutte le vasche "
              "(0 per carico e scarico)."),
        ("n", "Il Percorso elenca le tappe nell'ordine giusto, con id identici a "
              "quelli delle Vasche."),
        ("n", "Permanenze teoriche e delta sono in secondi e i delta sono positivi."),
        ("n", "Takt time, velocità, accelerazioni e ingombri sono compilati nei "
              "Parametri, in mm e s."),
        ("n", "Zone e CambioQuota sono vuoti, a meno che l'impianto non li richieda."),
        ("n", "Aprendo il file con `Apri linea...` non compare nessun errore."),
    ]


def main() -> int:
    messaggio = prepara_immagini()
    impaginazione.scrivi_documento(
        contenuto=contenuto(messaggio),
        uscita=USCITA,
        sottotitolo="Manuale di compilazione del file Excel della linea",
        descrizione="Fogli, colonne e parametri: cosa scrivere in ogni cella\n"
                    "e che cosa rappresenta sull'impianto.",
        cartelle_img=(IMG, IMG_OPERATORE),
        etichetta_nota="Attenzione  ",
    )
    n = sum(1 for f in os.listdir(IMG) if f.endswith(".png"))
    print(f"Scritto {os.path.relpath(USCITA, RADICE)} ({n} immagini in "
          f"{os.path.relpath(IMG, RADICE)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
