"""
excel_io.py
-----------
Lettura della definizione di una linea da un file Excel, e generazione del
file modello da cui partire.

Il file ha quattro fogli:

  Vasche     id della vasca, posizione lungo la rotaia, numero di posti
  Percorso   sequenza di vasche attraversate dal pezzo, con le permanenze
  Parametri  takt time, cinematiche, ingombri, tempi verticali, opzioni
  Zone       (facoltativo) suddivisione manuale delle mosse fra i carroponti

Per creare il modello da compilare:

    python excel_io.py linea.xlsx

Gli errori di compilazione vengono raccolti TUTTI e riportati insieme, con
foglio e cella: correggere il file una volta sola invece di scoprire un
problema alla volta.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

from kinematics import Kinematics
from model import HoistZone, ProblemData, StationSpec, Tank

FOGLIO_VASCHE = "Vasche"
FOGLIO_PERCORSO = "Percorso"
FOGLIO_PARAMETRI = "Parametri"
FOGLIO_ZONE = "Zone"

# nome parametro -> (unita', obbligatorio, default, descrizione)
_PARAMETRI = {
    "takt_min_s": ("s", True, None, "takt time minimo accettabile"),
    "takt_max_s": ("s", True, None, "takt time massimo accettabile"),
    "v_max_vuoto_m_s": ("m/s", True, None, "velocita' max del carroponte scarico"),
    "a_max_vuoto_m_s2": ("m/s^2", True, None, "accelerazione max del carroponte scarico"),
    "v_max_carico_m_s": ("m/s", True, None, "velocita' max del carroponte col pezzo"),
    "a_max_carico_m_s2": ("m/s^2", True, None, "accelerazione max col pezzo"),
    "ingombro_carroponte_m": ("m", True, None, "lunghezza del carrello lungo la rotaia"),
    "distanza_sicurezza_m": (
        "m",
        True,
        None,
        "margine minimo aggiuntivo fra due carroponti",
    ),
    "tempo_presa_s": (
        "s",
        False,
        0.0,
        "discesa gancio + aggancio + emersione/sgocciolamento",
    ),
    "tempo_rilascio_s": (
        "s",
        False,
        0.0,
        "immersione + sgancio + risalita del gancio a vuoto",
    ),
    "risoluzione_tick_per_s": (
        "tick/s",
        False,
        100,
        "risoluzione temporale interna del solutore",
    ),
    "passi_fascia_sicurezza": (
        "-",
        False,
        6,
        "finezza del vincolo di non collisione: piu' alto = meno cautelativo",
    ),
    "max_carroponti": (
        "-",
        False,
        6,
        "limite superiore alla ricerca automatica del numero di carroponti",
    ),
    "tempo_limite_per_tentativo_s": (
        "s",
        False,
        15.0,
        "quanto puo' durare ogni singola risoluzione CP-SAT",
    ),
}

_INTERI = {"risoluzione_tick_per_s", "passi_fascia_sicurezza", "max_carroponti"}


@dataclass
class Configurazione:
    """Tutto quello che serve per risolvere, letto dal file Excel."""

    data: ProblemData
    max_carroponti: int
    tempo_limite_s: float
    zone_manuali: Optional[list[HoistZone]]
    percorso_file: str


# --------------------------------------------------------------------------
# Raccolta degli errori
# --------------------------------------------------------------------------


class _Errori:
    """Accumula i problemi trovati invece di fermarsi al primo, cosi' chi
    compila il foglio li vede tutti insieme."""

    def __init__(self, percorso_file: str):
        self.percorso_file = percorso_file
        self.voci: list[str] = []

    def aggiungi(self, foglio: str, riferimento: str, messaggio: str):
        self.voci.append(f"[{foglio}!{riferimento}] {messaggio}")

    def solleva_se_presenti(self):
        if self.voci:
            raise ValueError(
                f"Il file '{self.percorso_file}' non e' compilato correttamente:\n  - "
                + "\n  - ".join(self.voci)
            )


def _numero(valore, foglio, cella, nome, errori: _Errori, intero=False):
    """Converte una cella in numero. Accetta anche il testo con la virgola
    decimale, che capita spesso copiando valori da altri documenti."""
    if valore is None or (isinstance(valore, str) and not valore.strip()):
        errori.aggiungi(foglio, cella, f"{nome}: valore mancante")
        return None
    if isinstance(valore, bool):
        errori.aggiungi(foglio, cella, f"{nome}: atteso un numero, trovato un booleano")
        return None
    if isinstance(valore, str):
        try:
            valore = float(valore.strip().replace(",", "."))
        except ValueError:
            errori.aggiungi(
                foglio, cella, f"{nome}: atteso un numero, trovato '{valore}'"
            )
            return None
    if intero:
        if float(valore) != int(valore):
            errori.aggiungi(
                foglio, cella, f"{nome}: atteso un intero, trovato {valore}"
            )
            return None
        return int(valore)
    return float(valore)


def _testo(valore) -> str:
    return "" if valore is None else str(valore).strip()


# --------------------------------------------------------------------------
# Lettura
# --------------------------------------------------------------------------


def leggi_problema(percorso_file: str) -> Configurazione:
    """Legge la definizione della linea da un file Excel.

    Solleva ValueError con l'elenco completo dei problemi se il file non e'
    compilato correttamente."""
    try:
        from openpyxl import load_workbook
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "Per leggere i file Excel serve openpyxl: pip install openpyxl"
        ) from e

    wb = load_workbook(percorso_file, data_only=True)
    errori = _Errori(percorso_file)

    for nome in (FOGLIO_VASCHE, FOGLIO_PERCORSO, FOGLIO_PARAMETRI):
        if nome not in wb.sheetnames:
            errori.aggiungi(
                nome,
                "-",
                f"foglio mancante (i fogli presenti sono: "
                f"{', '.join(wb.sheetnames)})",
            )
    errori.solleva_se_presenti()

    tanks = _leggi_vasche(wb[FOGLIO_VASCHE], errori)
    route = _leggi_percorso(wb[FOGLIO_PERCORSO], tanks, errori)
    par = _leggi_parametri(wb[FOGLIO_PARAMETRI], errori)
    zone = (
        _leggi_zone(wb[FOGLIO_ZONE], len(route) - 1, errori)
        if FOGLIO_ZONE in wb.sheetnames
        else None
    )
    errori.solleva_se_presenti()

    try:
        data = ProblemData(
            tanks=tanks,
            route=route,
            takt_min=par["takt_min_s"],
            takt_max=par["takt_max_s"],
            kin_empty=Kinematics(
                v_max=par["v_max_vuoto_m_s"], a_max=par["a_max_vuoto_m_s2"]
            ),
            kin_loaded=Kinematics(
                v_max=par["v_max_carico_m_s"], a_max=par["a_max_carico_m_s2"]
            ),
            hoist_length=par["ingombro_carroponte_m"],
            safety_distance=par["distanza_sicurezza_m"],
            zones=zone,
            time_scale=par["risoluzione_tick_per_s"],
            pick_time=par["tempo_presa_s"],
            release_time=par["tempo_rilascio_s"],
            clearance_steps=par["passi_fascia_sicurezza"],
        )
    except ValueError as e:
        # le validazioni di ProblemData sono gia' scritte per un umano:
        # basta dire da quale file arrivano i dati
        raise ValueError(f"Dati incoerenti in '{percorso_file}':\n  {e}") from e

    return Configurazione(
        data=data,
        max_carroponti=par["max_carroponti"],
        tempo_limite_s=par["tempo_limite_per_tentativo_s"],
        zone_manuali=zone,
        percorso_file=percorso_file,
    )


def _leggi_vasche(ws, errori: _Errori) -> dict[str, Tank]:
    tanks: dict[str, Tank] = {}
    for riga in range(2, ws.max_row + 1):
        tid = _testo(ws.cell(riga, 1).value)
        if not tid:
            continue  # riga vuota: si salta, cosi' si puo' lasciare spazio
        if tid in tanks:
            errori.aggiungi(FOGLIO_VASCHE, f"A{riga}", f"vasca '{tid}' duplicata")
            continue
        pos = _numero(
            ws.cell(riga, 2).value, FOGLIO_VASCHE, f"B{riga}", "posizione", errori
        )
        posti_cella = ws.cell(riga, 3).value
        if posti_cella is None or (
            isinstance(posti_cella, str) and not posti_cella.strip()
        ):
            posti = 1  # non compilato = vasca a posto singolo
        else:
            posti = _numero(
                posti_cella, FOGLIO_VASCHE, f"C{riga}", "posti", errori, intero=True
            )
        if pos is None or posti is None:
            continue
        tanks[tid] = Tank(id=tid, position=pos, capacity=posti)
    if not tanks:
        errori.aggiungi(FOGLIO_VASCHE, "A2", "nessuna vasca definita")
    return tanks


def _leggi_percorso(ws, tanks: dict[str, Tank], errori: _Errori) -> list[StationSpec]:
    route: list[StationSpec] = []
    atteso = 1
    for riga in range(2, ws.max_row + 1):
        n_cella = ws.cell(riga, 1).value
        tid = _testo(ws.cell(riga, 2).value)
        if not tid:
            continue
        # la colonna "n" non serve a ordinare, ma a intercettare un foglio
        # riordinato per sbaglio: l'ordine vero e' quello delle righe
        if n_cella is not None and _testo(n_cella):
            n = _numero(n_cella, FOGLIO_PERCORSO, f"A{riga}", "n", errori, intero=True)
            if n is not None and n != atteso:
                errori.aggiungi(
                    FOGLIO_PERCORSO,
                    f"A{riga}",
                    f"la numerazione salta o non e' in ordine (atteso {atteso}, "
                    f"trovato {n}): l'ordine delle righe e' la sequenza del "
                    f"percorso, controlla di non aver ordinato il foglio",
                )
        atteso += 1
        if tid not in tanks:
            errori.aggiungi(
                FOGLIO_PERCORSO,
                f"B{riga}",
                f"la vasca '{tid}' non e' definita nel foglio {FOGLIO_VASCHE}",
            )
            continue
        dmin = _numero(
            ws.cell(riga, 3).value,
            FOGLIO_PERCORSO,
            f"C{riga}",
            "permanenza minima",
            errori,
        )
        dmax = _numero(
            ws.cell(riga, 4).value,
            FOGLIO_PERCORSO,
            f"D{riga}",
            "permanenza massima",
            errori,
        )
        if dmin is None or dmax is None:
            continue
        if dmin > dmax:
            errori.aggiungi(
                FOGLIO_PERCORSO,
                f"C{riga}",
                f"permanenza minima ({dmin}) maggiore della massima ({dmax})",
            )
            continue
        route.append(StationSpec(tank_id=tid, dwell_min=dmin, dwell_max=dmax))
    if len(route) < 2:
        errori.aggiungi(
            FOGLIO_PERCORSO,
            "B2",
            f"il percorso deve avere almeno 2 stazioni, trovate {len(route)}",
        )
    return route


def _leggi_parametri(ws, errori: _Errori) -> dict:
    grezzi: dict[str, tuple] = {}
    for riga in range(2, ws.max_row + 1):
        nome = _testo(ws.cell(riga, 1).value)
        if not nome:
            continue
        if nome not in _PARAMETRI:
            errori.aggiungi(
                FOGLIO_PARAMETRI,
                f"A{riga}",
                f"parametro '{nome}' non riconosciuto. Quelli ammessi sono: "
                + ", ".join(sorted(_PARAMETRI)),
            )
            continue
        if nome in grezzi:
            errori.aggiungi(
                FOGLIO_PARAMETRI, f"A{riga}", f"parametro '{nome}' ripetuto"
            )
            continue
        grezzi[nome] = (ws.cell(riga, 2).value, riga)

    par = {}
    for nome, (unita, obbligatorio, default, _descr) in _PARAMETRI.items():
        if nome not in grezzi:
            if obbligatorio:
                errori.aggiungi(
                    FOGLIO_PARAMETRI, "A", f"parametro obbligatorio '{nome}' assente"
                )
            else:
                par[nome] = default
            continue
        valore, riga = grezzi[nome]
        if (
            not obbligatorio
            and default is not None
            and (valore is None or (isinstance(valore, str) and not valore.strip()))
        ):
            par[nome] = default  # riga presente ma lasciata vuota: si usa il default
            continue
        par[nome] = _numero(
            valore,
            FOGLIO_PARAMETRI,
            f"B{riga}",
            nome,
            errori,
            intero=nome in _INTERI,
        )
    return par


def _leggi_zone(ws, n_moves: int, errori: _Errori) -> Optional[list[HoistZone]]:
    zone = []
    for riga in range(2, ws.max_row + 1):
        a = ws.cell(riga, 1).value
        b = ws.cell(riga, 2).value
        if (a is None or not _testo(a)) and (b is None or not _testo(b)):
            continue
        lo = _numero(a, FOGLIO_ZONE, f"A{riga}", "prima mossa", errori, intero=True)
        hi = _numero(b, FOGLIO_ZONE, f"B{riga}", "ultima mossa", errori, intero=True)
        if lo is None or hi is None:
            continue
        zone.append(HoistZone(lo=lo, hi=hi))
    if not zone:
        return None  # foglio presente ma vuoto: zone automatiche
    coperte = []
    for z in zone:
        coperte.extend(range(z.lo, z.hi + 1))
    if coperte != list(range(n_moves)):
        errori.aggiungi(
            FOGLIO_ZONE,
            "A2",
            f"le zone devono coprire in modo contiguo e senza sovrapposizioni "
            f"le mosse da 0 a {n_moves - 1}; con quelle indicate si copre "
            f"{coperte}. Lascia il foglio vuoto per farle scegliere "
            f"automaticamente.",
        )
    return zone


# --------------------------------------------------------------------------
# Generazione del file modello
# --------------------------------------------------------------------------


def scrivi_modello(percorso_file: str) -> str:
    """Crea un file Excel gia' compilato con una linea di esempio, da usare
    come punto di partenza. Restituisce il percorso del file scritto."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    intestazione = Font(bold=True, color="FFFFFF")
    sfondo = PatternFill("solid", fgColor="4F6228")
    nota = Font(italic=True, color="808080")
    titolo_par = Font(bold=True, size=12)

    wb = Workbook()

    def prepara(ws, titoli, larghezze):
        ws.append(titoli)
        for col, (titolo, larghezza) in enumerate(zip(titoli, larghezze), start=1):
            cella = ws.cell(1, col)
            cella.font = intestazione
            cella.fill = sfondo
            cella.alignment = Alignment(horizontal="center")
            ws.column_dimensions[get_column_letter(col)].width = larghezza
        ws.freeze_panes = "A2"

    # -- Istruzioni ------------------------------------------------------
    # Tutte le spiegazioni stanno QUI e non nei fogli dei dati: una nota
    # scritta in una colonna che poi viene letta verrebbe scambiata per un
    # dato, ed e' un errore facilissimo da fare.
    ws = wb.active
    ws.title = "Istruzioni"
    ws.column_dimensions["A"].width = 110
    for testo, stile in [
        ("Come compilare questo file", titolo_par),
        ("", None),
        (f"Foglio {FOGLIO_VASCHE}", titolo_par),
        ("Una riga per vasca fisica.", None),
        ("  id            nome della vasca, usato nel foglio Percorso", None),
        ("  posizione_m   distanza lungo la rotaia, in metri", None),
        (
            "  posti         quanti pezzi ci stanno dentro contemporaneamente "
            "(vuoto = 1)",
            None,
        ),
        ("", None),
        (f"Foglio {FOGLIO_PERCORSO}", titolo_par),
        (
            "Una riga per tappa, NELL'ORDINE in cui il pezzo attraversa la linea: "
            "e' l'ordine",
            None,
        ),
        ("delle righe a definire la sequenza, non la colonna n.", None),
        (
            "  permanenza    tempo EFFETTIVO in bagno, da fine immersione a inizio "
            "emersione:",
            None,
        ),
        (
            "                le fasi verticali si sommano a parte (vedi tempo_presa "
            "e tempo_rilascio).",
            None,
        ),
        (
            "La stessa vasca puo' comparire piu' volte: i pezzi delle diverse tappe "
            "si contendono",
            None,
        ),
        ("gli stessi posti, e il calcolo ne tiene conto.", None),
        ("", None),
        (f"Foglio {FOGLIO_PARAMETRI}", titolo_par),
        (
            "Una riga per parametro. Non cambiare i nomi nella colonna A. I "
            "parametri facoltativi",
            None,
        ),
        ("si possono lasciare vuoti o cancellare del tutto.", None),
        ("", None),
        (f"Foglio {FOGLIO_ZONE}", titolo_par),
        (
            "LASCIALO VUOTO per far scegliere automaticamente sia il numero di "
            "carroponti sia",
            None,
        ),
        ("le zone di competenza: e' il modo consigliato.", None),
        (
            "Se lo compili: una riga per carroponte, con indici di MOSSA. La mossa k "
            "e' il trasporto",
            None,
        ),
        (
            "dalla stazione k alla k+1, quindi con 7 stazioni le mosse vanno da 0 a "
            "5. Le zone devono",
            None,
        ),
        (
            "essere contigue e coprire tutte le mosse esattamente una volta "
            "(es. 0-2 e 3-5).",
            None,
        ),
        ("", None),
        ("Attenzione", titolo_par),
        (
            "Non scrivere note o commenti nelle colonne dei dati: verrebbero letti "
            "come valori.",
            None,
        ),
        ("Usa questo foglio, oppure le colonne a destra di quelle compilate.", None),
    ]:
        ws.append([testo])
        if stile is not None:
            ws.cell(ws.max_row, 1).font = stile
        elif testo.startswith("  ") or testo.startswith("Non ") or testo.startswith("Usa "):
            ws.cell(ws.max_row, 1).font = nota

    # -- Vasche ----------------------------------------------------------
    ws = wb.create_sheet(FOGLIO_VASCHE)
    prepara(ws, ["id", "posizione_m", "posti"], [22, 14, 8])
    for tid, pos, posti in [
        ("CARICO", 0.0, 1),
        ("SGRASSO", 2.5, 1),
        ("RISCIACQUO_1", 5.5, 1),
        ("ZINCATURA", 9.5, 2),
        ("RISCIACQUO_2", 13.0, 1),
        ("PASSIVAZIONE", 16.5, 1),
        ("SCARICO", 20.0, 1),
    ]:
        ws.append([tid, pos, posti])

    # -- Percorso --------------------------------------------------------
    ws = wb.create_sheet(FOGLIO_PERCORSO)
    prepara(
        ws,
        ["n", "vasca", "permanenza_min_s", "permanenza_max_s"],
        [6, 22, 20, 20],
    )
    for n, (tid, dmin, dmax) in enumerate(
        [
            ("CARICO", 0, 0),
            ("SGRASSO", 60, 90),
            ("RISCIACQUO_1", 20, 40),
            ("ZINCATURA", 180, 220),
            ("RISCIACQUO_2", 20, 40),
            ("PASSIVAZIONE", 30, 45),
            ("SCARICO", 0, 0),
        ],
        start=1,
    ):
        ws.append([n, tid, dmin, dmax])

    # -- Parametri -------------------------------------------------------
    ws = wb.create_sheet(FOGLIO_PARAMETRI)
    prepara(ws, ["parametro", "valore", "unita", "descrizione"], [30, 12, 10, 62])
    valori_esempio = {
        "takt_min_s": 110,
        "takt_max_s": 150,
        "v_max_vuoto_m_s": 1.6,
        "a_max_vuoto_m_s2": 0.9,
        "v_max_carico_m_s": 1.0,
        "a_max_carico_m_s2": 0.4,
        "ingombro_carroponte_m": 1.2,
        "distanza_sicurezza_m": 0.6,
        "tempo_presa_s": 6,
        "tempo_rilascio_s": 4,
        "risoluzione_tick_per_s": 100,
        "passi_fascia_sicurezza": 6,
        "max_carroponti": 4,
        "tempo_limite_per_tentativo_s": 15,
    }
    for nome, (unita, obbligatorio, default, descr) in _PARAMETRI.items():
        suffisso = "" if obbligatorio else f" (facoltativo, default {default})"
        ws.append([nome, valori_esempio[nome], unita, descr + suffisso])

    # -- Zone (facoltativo) ----------------------------------------------
    ws = wb.create_sheet(FOGLIO_ZONE)
    prepara(ws, ["prima_mossa", "ultima_mossa", "", "note"], [16, 16, 4, 80])
    # la nota va in colonna D, fuori dalle colonne lette
    ws.cell(2, 4).value = (
        "Vuoto = numero di carroponti e zone scelti automaticamente "
        "(consigliato). Vedi il foglio Istruzioni."
    )
    ws.cell(2, 4).font = nota

    wb.save(percorso_file)
    return percorso_file


if __name__ == "__main__":
    destinazione = sys.argv[1] if len(sys.argv) > 1 else "linea.xlsx"
    scrivi_modello(destinazione)
    print(f"File modello scritto in {destinazione}")
    print("Compilalo e poi lancia la risoluzione.")
