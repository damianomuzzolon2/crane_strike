"""
excel_io.py
-----------
Lettura della definizione di una linea da un file Excel, generazione del file
modello da cui partire, e scrittura dei risultati in un secondo file Excel.

Il file ha quattro fogli:

  Vasche     id della vasca, posizione lungo la rotaia [mm], numero di posti
  Percorso   sequenza di vasche attraversate dal pezzo, con le permanenze
  Parametri  takt time, cinematiche, ingombri, tempi verticali, opzioni
  Zone       (facoltativo) suddivisione manuale delle mosse fra i carroponti
  Ciclogramma (facoltativo) il ciclogramma gia' composto, per riprenderlo

Per creare il modello da compilare:

    python excel_io.py linea.xlsx

Gli errori di compilazione vengono raccolti TUTTI e riportati insieme, con
foglio e cella: correggere il file una volta sola invece di scoprire un
problema alla volta.
"""

from __future__ import annotations

import dataclasses
import sys
from dataclasses import dataclass
from typing import Optional

from kinematics import Kinematics
from model import (
    HoistZone,
    ProblemData,
    SostaIntermedia,
    StationSpec,
    Tank,
    ZonaCambioQuota,
)

FOGLIO_ISTRUZIONI = "Istruzioni"
FOGLIO_VASCHE = "Vasche"
FOGLIO_PERCORSO = "Percorso"
FOGLIO_PARAMETRI = "Parametri"
FOGLIO_ZONE = "Zone"
FOGLIO_CAMBIO_QUOTA = "CambioQuota"
FOGLIO_CICLOGRAMMA = "Ciclogramma"

# Le due zone di cambio quota, nell'ordine in cui compaiono sul foglio.
# L'etichetta e' quella che l'utente scrive nella prima colonna.
_VERSI_CAMBIO_QUOTA = ("carico", "scarico")

# nome parametro -> (unita', obbligatorio, default, descrizione)
_PARAMETRI = {
    "takt_min_s": ("s", True, None, "takt time minimo accettabile"),
    "takt_max_s": ("s", True, None, "takt time massimo accettabile"),
    "v_max_vuoto_mm_s": ("mm/s", True, None, "velocita' max del carroponte scarico"),
    "a_max_vuoto_mm_s2": ("mm/s^2", True, None, "accelerazione max del carroponte scarico"),
    "d_max_vuoto_mm_s2": (
        "mm/s^2",
        False,
        None,
        "decelerazione max del carroponte scarico; vuoto = come l'accelerazione",
    ),
    "v_max_carico_mm_s": ("mm/s", True, None, "velocita' max del carroponte col pezzo"),
    "a_max_carico_mm_s2": ("mm/s^2", True, None, "accelerazione max col pezzo"),
    "d_max_carico_mm_s2": (
        "mm/s^2",
        False,
        None,
        "decelerazione max col pezzo; vuoto = come l'accelerazione",
    ),
    "ingombro_lato_positivo_mm": (
        "mm",
        True,
        None,
        "quanto sporge il carrello dal gancio verso le posizioni crescenti",
    ),
    "ingombro_lato_negativo_mm": (
        "mm",
        True,
        None,
        "quanto sporge il carrello dal gancio verso le posizioni decrescenti",
    ),
    "distanza_sicurezza_mm": (
        "mm",
        True,
        None,
        "margine minimo aggiuntivo fra due carroponti",
    ),
    "v_max_sollevamento_vuoto_mm_s": (
        "mm/s",
        False,
        None,
        "velocita' max di sollevamento a gancio scarico",
    ),
    "a_max_sollevamento_vuoto_mm_s2": (
        "mm/s^2",
        False,
        None,
        "accelerazione max di sollevamento a gancio scarico",
    ),
    "d_max_sollevamento_vuoto_mm_s2": (
        "mm/s^2",
        False,
        None,
        "decelerazione max di sollevamento a gancio scarico; vuoto = come "
        "l'accelerazione",
    ),
    "v_max_sollevamento_carico_mm_s": (
        "mm/s",
        False,
        None,
        "velocita' max di sollevamento col telaio",
    ),
    "a_max_sollevamento_carico_mm_s2": (
        "mm/s^2",
        False,
        None,
        "accelerazione max di sollevamento col telaio",
    ),
    "d_max_sollevamento_carico_mm_s2": (
        "mm/s^2",
        False,
        None,
        "decelerazione max di sollevamento col telaio; vuoto = come "
        "l'accelerazione",
    ),
    "v_approach_sollevamento_mm_s": (
        "mm/s",
        False,
        None,
        "velocita' di avvicinamento del sollevamento, vicino al punto di "
        "presa/deposito; vuoto = nessun avvicinamento",
    ),
    "d_approach_sollevamento_mm": (
        "mm",
        False,
        None,
        "quanta corsa si percorre alla velocita' di avvicinamento; va "
        "dichiarata insieme alla velocita'",
    ),
    "tempo_aggancio_s": (
        "s",
        False,
        0.0,
        "aggancio del telaio, prima del sollevamento (si somma alla presa)",
    ),
    "tempo_sgancio_s": (
        "s",
        False,
        0.0,
        "sgancio, dopo l'immersione (si somma al rilascio)",
    ),
    "risoluzione_tick_per_s": (
        "tick/s",
        False,
        100,
        "risoluzione temporale interna del solutore",
    ),
    "passo_controllo_distanza_mm": (
        "mm",
        False,
        200.0,
        "ogni quanti mm viene verificata la distanza fra due carroponti "
        "attorno al confine fra le loro zone. Fra una verifica e l'altra il "
        "calcolo sta dal lato sicuro, quindi puo' pretendere fino a questi mm "
        "in piu' del dovuto. NON e' un margine di sicurezza (quello e' "
        "distanza_sicurezza_mm): la distanza garantita non cambia mai. "
        "Infittirlo (100, 50) se una linea con vasche vicine esce INFEASIBLE "
        "o il takt time sembra troppo alto; costa solo tempo di calcolo",
    ),
    "larghezza_pezzo_mm": (
        "mm",
        False,
        None,
        "quanto e' largo il pezzo appeso al telaio. SOLO PER LA SIMULAZIONE: "
        "non entra in nessun calcolo, serve a disegnarlo in proporzione alle "
        "vasche invece che di una misura convenzionale. Vuoto = come prima",
    ),
    "altezza_pezzo_mm": (
        "mm",
        False,
        None,
        "quanto e' alto il pezzo appeso al telaio. Solo per la simulazione, "
        "come larghezza_pezzo_mm: insieme all'altezza delle vasche dice "
        "quanto il pezzo le riempie",
    ),
    "max_soste_intermedie": (
        "-",
        False,
        1,
        "quante vasche IN MEZZO il calcolo automatico puo' valutare come posto "
        "dove far sostare un carroponte durante uno spostamento a vuoto, per "
        "tenerlo lontano dal vicino. 0 = nessuna, il carro aspetta solo dove "
        "ha consegnato o dove deve andare (come prima che questa colonna "
        "esistesse). 1 (il default) da' al solutore il posto piu' al riparo, "
        "ed e' quello che costa meno. Ogni candidato in piu' allarga il "
        "modello parecchio -- su una linea da 14 mosse e 4 carroponti il "
        "secondo candidato triplica i vincoli di non collisione: se il calcolo "
        "diventa lento, o se il takt time PEGGIORA dopo averlo alzato, alza "
        "tempo_limite_per_tentativo_s oppure riporta questo a 1 o a 0",
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

_INTERI = {"risoluzione_tick_per_s", "max_carroponti", "max_soste_intermedie"}

# Come si chiamavano gli stessi parametri quando il progetto lavorava in metri.
# Servono solo a riconoscere un file vecchio e dirlo chiaramente: leggerlo
# com'e' vorrebbe dire interpretare 9.5 m come 9.5 mm.
_NOMI_IN_METRI = {
    nome.replace("_mm", "_m"): nome for nome in _PARAMETRI if "_mm" in nome
}

# Parametri sostituiti da altri che vogliono dire una cosa diversa: qui non
# basta dire il nome nuovo, va detto anche come si converte il valore.
_NOMI_SOSTITUITI = {
    "passi_fascia_sicurezza": (
        "'passi_fascia_sicurezza' non esiste piu': diceva la stessa cosa in "
        "modo indiretto. Adesso si dichiara 'passo_controllo_distanza_mm', "
        "cioe' ogni quanti mm viene verificata la distanza fra i carroponti. "
        "Si converte con (ingombro + distanza_sicurezza) / passi: con i valori "
        "d'esempio 6 passi -> 300 mm. Il predefinito e' 200"
    ),
    "traslazione_con_gancio_basso": (
        "'traslazione_con_gancio_basso' non sta piu' fra i Parametri: non e' "
        "una proprieta' della linea ma della singola VASCA -- di solito un "
        "impianto ne ha una o due che il gancio calato non puo' scavalcare, e "
        "tutte le altre libere. Va scritta nell'omonima colonna del foglio "
        "Vasche, una riga per vasca; vuoto vale 1. Se prima avevi 0, mettilo "
        "sulle vasche che sono davvero un ostacolo -- e solo su quelle: i "
        "rientri che non le scavalcano non pagheranno piu' salita e discesa"
    ),
    "altezza_sollevamento_mm": (
        "'altezza_sollevamento_mm' non sta piu' fra i Parametri: la corsa "
        "verticale e' una proprieta' della singola vasca (quanto e' profonda), "
        "non del carroponte. Va scritta nella colonna 'corsa_verticale_mm' del "
        "foglio Vasche, una riga per vasca, obbligatoria: 0 dove non c'e' "
        "movimentazione verticale"
    ),
    "tempo_sgocciolamento_s": (
        "'tempo_sgocciolamento_s' non sta piu' fra i Parametri: lo "
        "sgocciolamento dipende dal bagno, non dal carroponte. Va scritto "
        "nella colonna 'sgocciolamento_s' del foglio Vasche, una riga per "
        "vasca, obbligatorio: 0 dove non serve"
    ),
    "margine_calcolo_percento": (
        "'margine_calcolo_percento' non esiste piu': la stessa cosa si dichiara "
        "adesso in millimetri invece che in percentuale, come "
        "'passo_controllo_distanza_mm'. Si converte moltiplicando per "
        "(ingombro + distanza_sicurezza)/100: con i valori d'esempio 15% -> "
        "270 mm. Il predefinito e' 200"
    ),
}


@dataclass
class Configurazione:
    """Tutto quello che serve per risolvere, letto dal file Excel."""

    data: ProblemData
    max_carroponti: int
    tempo_limite_s: float
    zone_manuali: Optional[list[HoistZone]]
    percorso_file: str
    # Ciclogramma gia' composto, se il file lo porta con se': un dizionario con
    # `T`, `permanenze` (stazione -> secondi) e `assegnazione` (mossa ->
    # carroponte 0-based). None = il file descrive solo la linea.
    ciclogramma: Optional[dict] = None


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
    cambio_quota = (
        _leggi_cambio_quota(wb[FOGLIO_CAMBIO_QUOTA], errori)
        if FOGLIO_CAMBIO_QUOTA in wb.sheetnames
        else {v: None for v in _VERSI_CAMBIO_QUOTA}
    )
    ciclogramma = (
        _leggi_ciclogramma(wb[FOGLIO_CICLOGRAMMA], route, errori)
        if FOGLIO_CICLOGRAMMA in wb.sheetnames
        else None
    )
    errori.solleva_se_presenti()

    def _kin_sollevamento(prefisso: str) -> Optional[Kinematics]:
        v = par.get(f"v_max_sollevamento_{prefisso}_mm_s")
        a = par.get(f"a_max_sollevamento_{prefisso}_mm_s2")
        if v is None or a is None:
            return None
        # la decelerazione resta facoltativa anche dove il sollevamento c'e':
        # None vuol dire "frena come accelera", non "niente sollevamento"
        return Kinematics(
            v_max=v, a_max=a, d_max=par.get(f"d_max_sollevamento_{prefisso}_mm_s2")
        )

    try:
        data = ProblemData(
            tanks=tanks,
            route=route,
            takt_min=par["takt_min_s"],
            takt_max=par["takt_max_s"],
            kin_empty=Kinematics(
                v_max=par["v_max_vuoto_mm_s"],
                a_max=par["a_max_vuoto_mm_s2"],
                d_max=par["d_max_vuoto_mm_s2"],
            ),
            kin_loaded=Kinematics(
                v_max=par["v_max_carico_mm_s"],
                a_max=par["a_max_carico_mm_s2"],
                d_max=par["d_max_carico_mm_s2"],
            ),
            hoist_extent_pos=par["ingombro_lato_positivo_mm"],
            hoist_extent_neg=par["ingombro_lato_negativo_mm"],
            safety_distance=par["distanza_sicurezza_mm"],
            zones=zone,
            time_scale=par["risoluzione_tick_per_s"],

            kin_lift_empty=_kin_sollevamento("vuoto"),
            kin_lift_loaded=_kin_sollevamento("carico"),
            v_approach_lift=par.get("v_approach_sollevamento_mm_s"),
            d_approach_lift=par.get("d_approach_sollevamento_mm"),
            engage_time=par["tempo_aggancio_s"],
            disengage_time=par["tempo_sgancio_s"],

            clearance_step_mm=par["passo_controllo_distanza_mm"],
            max_soste_intermedie=par["max_soste_intermedie"],
            cambio_quota_carico=cambio_quota["carico"],
            cambio_quota_scarico=cambio_quota["scarico"],
            larghezza_pezzo=par["larghezza_pezzo_mm"],
            altezza_pezzo=par["altezza_pezzo_mm"],
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
        ciclogramma=ciclogramma,
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
        # Corsa e sgocciolamento sono OBBLIGATORI, una vasca per volta: non
        # esiste un valore generale da cui ereditare. Dove non serve
        # movimentazione verticale si scrive 0, che e' una dichiarazione --
        # una cella vuota no.
        corsa = _numero(
            ws.cell(riga, 4).value,
            FOGLIO_VASCHE,
            f"D{riga}",
            "corsa verticale",
            errori,
        )
        sgocciolamento = _numero(
            ws.cell(riga, 5).value,
            FOGLIO_VASCHE,
            f"E{riga}",
            "sgocciolamento",
            errori,
        )
        # Gli svincoli sono FACOLTATIVI: servono solo agli impianti in cui il
        # gancio calato non passa fra le vasche, e li' solo dove la vasca e'
        # davvero un ostacolo. Cella vuota = quella vasca non lo e'.
        #
        # L'ordine delle colonne e' NEGATIVO poi POSITIVO, cioe' lo stesso in
        # cui si vedono sulla rotaia guardando il disegno: prima quello a
        # sinistra della vasca, poi quello a destra. Compilando si legge da
        # sinistra a destra, e non si deve invertire niente nella testa.
        svincoli = {}
        for colonna, lettera, verso in ((6, "F", "negativo"), (7, "G", "positivo")):
            cella = ws.cell(riga, colonna).value
            if cella is None or (isinstance(cella, str) and not cella.strip()):
                svincoli[verso] = None
                continue
            svincoli[verso] = _numero(
                cella,
                FOGLIO_VASCHE,
                f"{lettera}{riga}",
                f"svincolo {verso}",
                errori,
            )
        # Un file scritto quando le due colonne erano al contrario si riconosce
        # a colpo d'occhio: lo svincolo "negativo" finisce dopo la vasca e il
        # "positivo" prima. La geometria lo respingerebbe comunque, ma con un
        # messaggio che manda a cercare l'errore nell'impianto invece che nel
        # file -- e chi ha compilato quel file non ha sbagliato niente.
        invertiti = [
            (lettera, verso, valore)
            for lettera, verso, valore, atteso_sotto in (
                ("F", "negativo", svincoli["negativo"], True),
                ("G", "positivo", svincoli["positivo"], False),
            )
            if valore is not None
            and pos is not None
            and (valore > pos) == atteso_sotto
        ]
        if len(invertiti) == 2:
            errori.aggiungi(
                FOGLIO_VASCHE,
                f"F{riga}",
                f"i due svincoli della vasca '{tid}' sembrano scambiati fra "
                f"loro: in F c'e' {invertiti[0][2]:.0f} mm, che sta DOPO la "
                f"vasca ({pos:.0f} mm), e in G c'e' {invertiti[1][2]:.0f} mm, "
                f"che sta prima. Dalla versione in cui le colonne sono state "
                f"messe nell'ordine della rotaia, F e' lo svincolo NEGATIVO "
                f"(prima della vasca) e G il POSITIVO (dopo). Scambia le due "
                f"celle.",
            )
            # NIENTE `continue`: la vasca si registra lo stesso, anche se con
            # valori che non useremo mai -- gli errori si sollevano tutti
            # insieme prima di costruire il problema. Saltandola, il foglio
            # Percorso non la troverebbe piu' e aggiungerebbe un "vasca non
            # definita" che non c'entra niente e che coprirebbe proprio il
            # messaggio utile.
        # Se il gancio SCARICO puo' passare basso sopra questa vasca. Vuoto = 1,
        # che e' come sono fatte quasi tutte: la colonna si compila solo dove
        # c'e' davvero un ostacolo.
        cella = ws.cell(riga, 8).value
        if cella is None or (isinstance(cella, str) and not cella.strip()):
            basso = 1
        else:
            basso = _numero(
                cella,
                FOGLIO_VASCHE,
                f"H{riga}",
                "traslazione con gancio basso",
                errori,
                intero=True,
            )
        # Larghezza e altezza della vasca: FACOLTATIVE, e servono solo alla
        # simulazione, che senza si inventa delle proporzioni. Vuote non sono
        # un difetto -- di parecchie linee non si ha il disegno -- quindi qui
        # non si segnala niente: si legge se c'e'.
        ingombro = {}
        for colonna, lettera, quale in ((9, "I", "larghezza"), (10, "J", "altezza")):
            cella = ws.cell(riga, colonna).value
            if cella is None or (isinstance(cella, str) and not cella.strip()):
                ingombro[quale] = None
                continue
            ingombro[quale] = _numero(
                cella, FOGLIO_VASCHE, f"{lettera}{riga}", f"{quale} della vasca", errori
            )
        if pos is None or posti is None or corsa is None or sgocciolamento is None:
            continue
        if basso is None:
            continue
        tanks[tid] = Tank(
            id=tid,
            position=pos,
            capacity=posti,
            lift_height=corsa,
            drain_time=sgocciolamento,
            svincolo_pos=svincoli["positivo"],
            svincolo_neg=svincoli["negativo"],
            gancio_basso=bool(basso),
            larghezza=ingombro["larghezza"],
            altezza=ingombro["altezza"],
        )
    if not tanks:
        errori.aggiungi(FOGLIO_VASCHE, "A2", "nessuna vasca definita")
    return tanks


def _percorso_vecchio_formato(ws) -> bool:
    """I file compilati prima del passaggio al tempo teorico hanno in C e D
    la permanenza minima e massima. Si riconoscono dall'intestazione, e vanno
    letti lo stesso: chi ha una linea gia' descritta non deve ricompilarla."""
    return "min" in _testo(ws.cell(1, 3).value).lower()


def _leggi_percorso(ws, tanks: dict[str, Tank], errori: _Errori) -> list[StationSpec]:
    route: list[StationSpec] = []
    atteso = 1
    vecchio_formato = _percorso_vecchio_formato(ws)
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
        if vecchio_formato:
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
            continue
        teorico = _numero(
            ws.cell(riga, 3).value,
            FOGLIO_PERCORSO,
            f"C{riga}",
            "permanenza teorica",
            errori,
        )
        dneg = _numero(
            ws.cell(riga, 4).value,
            FOGLIO_PERCORSO,
            f"D{riga}",
            "delta negativo",
            errori,
        )
        dpos = _numero(
            ws.cell(riga, 5).value,
            FOGLIO_PERCORSO,
            f"E{riga}",
            "delta positivo",
            errori,
        )
        if teorico is None or dneg is None or dpos is None:
            continue
        # I due delta sono AMPIEZZE, non estremi: si scrivono positivi tutti e
        # due, e il software li sottrae e li somma. Un delta negativo scritto
        # con il segno meno darebbe una finestra rovesciata senza dirlo.
        fuori = [
            (nome, valore, cella)
            for nome, valore, cella in (
                ("permanenza teorica", teorico, f"C{riga}"),
                ("delta negativo", dneg, f"D{riga}"),
                ("delta positivo", dpos, f"E{riga}"),
            )
            if valore < 0
        ]
        if fuori:
            for nome, valore, cella in fuori:
                errori.aggiungi(
                    FOGLIO_PERCORSO,
                    cella,
                    f"{nome} ({valore}) negativa: i due delta sono ampiezze, "
                    f"si scrivono positivi ed e' il software a sottrarre e "
                    f"sommare",
                )
            continue
        if dneg > teorico:
            errori.aggiungi(
                FOGLIO_PERCORSO,
                f"D{riga}",
                f"delta negativo ({dneg}) maggiore della permanenza teorica "
                f"({teorico}): la soglia minima verrebbe negativa",
            )
            continue
        route.append(StationSpec.da_teorico(tid, teorico, dneg, dpos))
    if len(route) < 2:
        errori.aggiungi(
            FOGLIO_PERCORSO,
            "B2",
            f"il percorso deve avere almeno 2 stazioni, trovate {len(route)}",
        )
    return route


def _stazione_di(route, tank_id: str) -> Optional[int]:
    """La prima tappa del percorso servita dalla vasca data, o None se quella
    vasca non e' nel percorso.

    La PRIMA e non "quella giusta": se la vasca compare piu' volte le sue tappe
    stanno nello stesso punto della rotaia, e per dire dove un carroponte sosta
    sono la stessa cosa."""
    for i, spec in enumerate(route):
        if spec.tank_id == tank_id:
            return i
    return None


def _leggi_ciclogramma(ws, route, errori: _Errori) -> Optional[dict]:
    """Il ciclogramma salvato: takt time, tempi in vasca, assegnazione.

    Foglio facoltativo, e una linea senza ciclogramma e' normale: un foglio
    vuoto vale come assente, non come errore. Se invece c'e' ed e' rotto lo si
    dice, perche' il silenzio farebbe ripartire da zero senza spiegare dove sia
    finito il lavoro di ieri."""
    T = ws["B1"].value
    if T is None or (isinstance(T, str) and not T.strip()):
        # nessun takt time: il foglio c'e' ma non e' compilato
        righe_piene = any(
            _testo(ws.cell(r, 1).value) for r in range(5, ws.max_row + 1)
        )
        if not righe_piene:
            return None
        errori.aggiungi(
            FOGLIO_CICLOGRAMMA, "B1", "takt time mancante: senza non si "
            "puo' ricostruire il ciclogramma"
        )
        return None
    takt = _numero(T, FOGLIO_CICLOGRAMMA, "B1", "takt time", errori)
    if takt is not None and takt <= 0:
        errori.aggiungi(
            FOGLIO_CICLOGRAMMA, "B1", f"takt time deve essere > 0, trovato {takt}"
        )
        takt = None

    n_carroponti = _numero(
        ws["B2"].value, FOGLIO_CICLOGRAMMA, "B2", "carroponti", errori, intero=True
    ) if ws["B2"].value is not None else None

    permanenze: dict[int, float] = {}
    assegnazione: dict[int, int] = {}
    attese: dict[int, float] = {}
    soste: dict[int, SostaIntermedia] = {}
    n_moves = len(route) - 1
    for riga in range(5, ws.max_row + 1):
        cella_k = ws.cell(riga, 1).value
        if cella_k is None or (isinstance(cella_k, str) and not cella_k.strip()):
            continue
        k = _numero(cella_k, FOGLIO_CICLOGRAMMA, f"A{riga}", "mossa", errori,
                    intero=True)
        if k is None:
            continue
        if not 0 <= k < n_moves:
            errori.aggiungi(
                FOGLIO_CICLOGRAMMA,
                f"A{riga}",
                f"mossa {k} fuori dall'intervallo 0..{n_moves - 1}",
            )
            continue
        carro = ws.cell(riga, 4).value
        if carro is not None and not (isinstance(carro, str) and not carro.strip()):
            c = _numero(carro, FOGLIO_CICLOGRAMMA, f"D{riga}", "carroponte",
                        errori, intero=True)
            if c is not None:
                if c < 1:
                    errori.aggiungi(
                        FOGLIO_CICLOGRAMMA,
                        f"D{riga}",
                        f"carroponte numerato da 1, trovato {c}",
                    )
                else:
                    assegnazione[k] = c - 1
        sosta = ws.cell(riga, 5).value
        if sosta is not None and not (isinstance(sosta, str) and not sosta.strip()):
            s = _numero(sosta, FOGLIO_CICLOGRAMMA, f"E{riga}", "tempo in vasca",
                        errori)
            if s is not None:
                if s < 0:
                    errori.aggiungi(
                        FOGLIO_CICLOGRAMMA,
                        f"E{riga}",
                        f"tempo in vasca negativo: {s}",
                    )
                else:
                    permanenze[k] = s
        # Colonna facoltativa: i file scritti prima che esistesse non ce
        # l'hanno, e un ciclogramma composto a mano puo' non averla. Assente
        # vuol dire "decidi tu dove far aspettare il carro", ed e' la regola
        # predefinita a rispondere.
        attesa = ws.cell(riga, 6).value
        if attesa is not None and not (isinstance(attesa, str) and not attesa.strip()):
            a = _numero(attesa, FOGLIO_CICLOGRAMMA, f"F{riga}",
                        "attesa dopo la consegna", errori)
            if a is not None:
                if a < 0:
                    errori.aggiungi(
                        FOGLIO_CICLOGRAMMA,
                        f"F{riga}",
                        f"attesa dopo la consegna negativa: {a}",
                    )
                else:
                    attese[k] = a
        # Le due colonne della sosta per strada: la vasca dove il carroponte si
        # ferma durante il rientro, e per quanto. Vanno insieme -- una da sola
        # non dice niente -- e sono facoltative come l'attesa.
        vasca_sosta = _testo(ws.cell(riga, 7).value)
        secondi_sosta = ws.cell(riga, 8).value
        vuota = secondi_sosta is None or (
            isinstance(secondi_sosta, str) and not secondi_sosta.strip()
        )
        if vasca_sosta and not vuota:
            s = _numero(secondi_sosta, FOGLIO_CICLOGRAMMA, f"H{riga}",
                        "durata della sosta in mezzo", errori)
            stazione = _stazione_di(route, vasca_sosta)
            if stazione is None:
                errori.aggiungi(
                    FOGLIO_CICLOGRAMMA,
                    f"G{riga}",
                    f"la vasca '{vasca_sosta}' dove sostare non e' nel "
                    f"percorso: il carroponte non ci passa",
                )
            elif s is None:
                pass  # il numero era rotto: l'errore l'ha gia' registrato
            elif s < 0:
                errori.aggiungi(
                    FOGLIO_CICLOGRAMMA,
                    f"H{riga}",
                    f"durata della sosta in mezzo negativa: {s}",
                )
            else:
                soste[k] = SostaIntermedia(stazione=stazione, secondi=s)
        elif vasca_sosta or not vuota:
            errori.aggiungi(
                FOGLIO_CICLOGRAMMA,
                f"G{riga}",
                "la sosta in una vasca in mezzo vuole entrambe le colonne: "
                "in quale vasca (G) e per quanti secondi (H). Lasciale "
                "entrambe vuote se il carroponte rientra diritto",
            )
    if takt is None:
        return None
    if not n_carroponti or n_carroponti < 1:
        # non dichiarato: si deduce da chi lavora davvero
        n_carroponti = max(assegnazione.values(), default=0) + 1
    return {
        "T": takt,
        "permanenze": permanenze,
        "assegnazione": assegnazione,
        "n_carroponti": n_carroponti,
        # None (non {}) quando la colonna manca del tutto: un dizionario vuoto
        # direbbe "nessuno aspetta", che e' una scelta, mentre qui la scelta
        # non c'e' proprio e va lasciata fare alla regola predefinita.
        "attese": attese or None,
        # Le soste per strada invece sono l'eccezione, non la regola: un
        # dizionario vuoto e' la risposta giusta -- vuol dire che tutti i
        # rientri sono diritti -- e non c'e' nessuna regola a cui delegare.
        "soste": soste,
    }


def _leggi_parametri(ws, errori: _Errori) -> dict:
    grezzi: dict[str, tuple] = {}
    for riga in range(2, ws.max_row + 1):
        nome = _testo(ws.cell(riga, 1).value)
        if not nome:
            continue
        if nome in _NOMI_IN_METRI:
            # Un file della versione precedente. Va intercettato con un
            # messaggio suo: senza, si leggerebbero venti "parametro non
            # riconosciuto" e nessuno capirebbe che il problema e' l'unita' --
            # con il rischio, peggiore, di ricompilarlo a occhio sbagliando di
            # mille volte.
            errori.aggiungi(
                FOGLIO_PARAMETRI,
                f"A{riga}",
                f"'{nome}' e' un nome della versione in METRI. Adesso si "
                f"lavora in MILLIMETRI: il parametro si chiama "
                f"'{_NOMI_IN_METRI[nome]}' e il valore va moltiplicato per "
                f"1000. Il modo piu' rapido e' rigenerare il file con "
                f"'Nuovo modello Excel...' e ricopiarci i dati",
            )
            continue
        if nome in _NOMI_SOSTITUITI:
            # Rinominati cambiando anche il significato: lasciarli cadere nel
            # generico "non riconosciuto" farebbe ricopiare il vecchio valore
            # sotto il nome nuovo, che qui vuol dire tutt'altro.
            errori.aggiungi(FOGLIO_PARAMETRI, f"A{riga}", _NOMI_SOSTITUITI[nome])
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
        if not obbligatorio and (
            valore is None or (isinstance(valore, str) and not valore.strip())
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


def _leggi_cambio_quota(
    ws, errori: _Errori
) -> dict[str, Optional[ZonaCambioQuota]]:
    """Le due zone di cambio quota, per etichetta ('carico' / 'scarico').

    Il foglio e' facoltativo, e lo sono anche le sue due righe: quasi nessun
    impianto ne ha, e chi non ne ha lascia il foglio vuoto. Una riga scritta a
    meta' invece e' un errore -- servono tutti e quattro i numeri, perche' con
    tre di essi il giro non e' definito."""
    fuori: dict[str, Optional[ZonaCambioQuota]] = {v: None for v in _VERSI_CAMBIO_QUOTA}
    for riga in range(2, ws.max_row + 1):
        etichetta = _testo(ws.cell(riga, 1).value).lower()
        celle = [ws.cell(riga, c).value for c in range(2, 6)]
        vuote = all(
            c is None or (isinstance(c, str) and not c.strip()) for c in celle
        )
        if not etichetta and vuote:
            continue
        if etichetta not in _VERSI_CAMBIO_QUOTA:
            errori.aggiungi(
                FOGLIO_CAMBIO_QUOTA,
                f"A{riga}",
                (
                    "manca il nome della zona"
                    if not etichetta
                    else f"zona '{ws.cell(riga, 1).value}' sconosciuta"
                )
                + ": le zone di cambio quota possono essere solo 'carico' "
                "(fra il carico e la prima vasca) e 'scarico' (fra l'ultima "
                "vasca e lo scarico). Lascia il foglio vuoto se l'impianto "
                "non ne ha.",
            )
            continue
        if fuori[etichetta] is not None:
            errori.aggiungi(
                FOGLIO_CAMBIO_QUOTA, f"A{riga}", f"zona '{etichetta}' ripetuta"
            )
            continue
        valori = [
            _numero(cella, FOGLIO_CAMBIO_QUOTA, f"{lettera}{riga}", nome, errori)
            for cella, lettera, nome in zip(
                celle,
                "BCDE",
                (
                    "posizione",
                    "intermediate1",
                    "intermediate2",
                    "corsa totale",
                ),
            )
        ]
        if any(v is None for v in valori):
            continue
        fuori[etichetta] = ZonaCambioQuota(
            position=valori[0],
            intermediate1=valori[1],
            intermediate2=valori[2],
            corsa_totale=valori[3],
        )
    return fuori


# --------------------------------------------------------------------------
# Generazione del file modello
# --------------------------------------------------------------------------


def _righe_esempio():
    """La linea di zincatura d'esempio, nella forma in cui va scritta sui
    fogli. E' la linea con cui si comincia: si lancia subito e la si modifica
    pezzo per pezzo."""
    # id, posizione, posti, corsa, sgocciolamento, i due svincoli, gancio
    # basso, e infine larghezza e altezza della vasca. Le tre colonne di mezzo
    # restano vuote: la linea d'esempio non ha ostacoli. Larghezza e altezza
    # ci sono perche' servono solo a disegnare, e vederle compilate dice a chi
    # apre il modello che si possono compilare -- carico e scarico no, che non
    # sono vasche.
    vasche = [
        # carico e scarico non sono bagni: nessuna corsa, nessuno scolo
        ("CARICO", 0, 1, 0, 0, None, None, None, None, None),
        ("SGRASSO", 2500, 1, 800, 2, None, None, None, 1800, 1200),
        ("RISCIACQUO_1", 5500, 1, 800, 2, None, None, None, 1800, 1200),
        ("ZINCATURA", 9500, 2, 1100, 8, None, None, None, 2600, 1600),
        ("RISCIACQUO_2", 13000, 1, 800, 2, None, None, None, 1800, 1200),
        ("PASSIVAZIONE", 16500, 1, 800, 3, None, None, None, 1800, 1200),
        ("SCARICO", 20000, 1, 0, 0, None, None, None, None, None),
    ]
    # vasca, tempo teorico, delta negativo, delta positivo: le soglie sono
    # teorico-delta_negativo e teorico+delta_positivo
    percorso = [
        ("CARICO", 0, 0, 0),
        ("SGRASSO", 75, 15, 15),
        ("RISCIACQUO_1", 30, 10, 10),
        ("ZINCATURA", 200, 20, 20),
        ("RISCIACQUO_2", 30, 10, 10),
        ("PASSIVAZIONE", 37, 7, 8),
        ("SCARICO", 0, 0, 0),
    ]
    parametri = {
        "takt_min_s": 110,
        "takt_max_s": 150,
        "v_max_vuoto_mm_s": 1600,
        "a_max_vuoto_mm_s2": 900,
        "d_max_vuoto_mm_s2": 1200,
        "v_max_carico_mm_s": 1000,
        "a_max_carico_mm_s2": 400,
        "d_max_carico_mm_s2": 500,
        "ingombro_lato_positivo_mm": 500,
        "ingombro_lato_negativo_mm": 700,
        "distanza_sicurezza_mm": 600,
        "v_max_sollevamento_vuoto_mm_s": 500,
        "a_max_sollevamento_vuoto_mm_s2": 800,
        "d_max_sollevamento_vuoto_mm_s2": 800,
        "v_max_sollevamento_carico_mm_s": 300,
        "a_max_sollevamento_carico_mm_s2": 500,
        "d_max_sollevamento_carico_mm_s2": 500,
        "v_approach_sollevamento_mm_s": 80,
        "d_approach_sollevamento_mm": 150,
        "tempo_aggancio_s": 2,
        "tempo_sgancio_s": 1,
        "risoluzione_tick_per_s": 100,
        "passo_controllo_distanza_mm": 200,
        "max_soste_intermedie": 1,
        "larghezza_pezzo_mm": 1400,
        "altezza_pezzo_mm": 900,
        "max_carroponti": 4,
        "tempo_limite_per_tentativo_s": 15,
    }
    # La linea d'esempio non ha zone di cambio quota: il foglio nasce vuoto,
    # con le sole intestazioni, cosi' si vede che c'e' e cosa vorrebbe.
    return vasche, percorso, parametri, None, None


def _righe_da_configurazione(cfg: Configurazione):
    """Le stesse righe, ricavate da una linea gia' letta. E' l'inverso esatto
    di `leggi_problema`: quello che esce di qui, riletto, deve ridare la
    stessa linea."""
    d = cfg.data

    def cinematica(kin, campo):
        return None if kin is None else getattr(kin, campo)

    vasche = [
        (
            t.id,
            t.position,
            t.capacity,
            t.lift_height,
            t.drain_time,
            # nell'ordine della rotaia: prima quello a sinistra della vasca
            t.svincolo_neg,
            t.svincolo_pos,
            1 if t.gancio_basso else 0,
            t.larghezza,
            t.altezza,
        )
        for t in d.tanks.values()
    ]
    percorso = [(s.tank_id, s.nominale, s.delta_neg, s.delta_pos) for s in d.route]
    parametri = {
        "takt_min_s": d.takt_min,
        "takt_max_s": d.takt_max,
        "v_max_vuoto_mm_s": d.kin_empty.v_max,
        "a_max_vuoto_mm_s2": d.kin_empty.a_max,
        "d_max_vuoto_mm_s2": d.kin_empty.d_max,
        "v_max_carico_mm_s": d.kin_loaded.v_max,
        "a_max_carico_mm_s2": d.kin_loaded.a_max,
        "d_max_carico_mm_s2": d.kin_loaded.d_max,
        "ingombro_lato_positivo_mm": d.hoist_extent_pos,
        "ingombro_lato_negativo_mm": d.hoist_extent_neg,
        "distanza_sicurezza_mm": d.safety_distance,
        "v_max_sollevamento_vuoto_mm_s": cinematica(d.kin_lift_empty, "v_max"),
        "a_max_sollevamento_vuoto_mm_s2": cinematica(d.kin_lift_empty, "a_max"),
        "d_max_sollevamento_vuoto_mm_s2": cinematica(d.kin_lift_empty, "d_max"),
        "v_max_sollevamento_carico_mm_s": cinematica(d.kin_lift_loaded, "v_max"),
        "a_max_sollevamento_carico_mm_s2": cinematica(d.kin_lift_loaded, "a_max"),
        "d_max_sollevamento_carico_mm_s2": cinematica(d.kin_lift_loaded, "d_max"),
        "v_approach_sollevamento_mm_s": d.v_approach_lift,
        "d_approach_sollevamento_mm": d.d_approach_lift,
        "tempo_aggancio_s": d.engage_time,
        "tempo_sgancio_s": d.disengage_time,
        "risoluzione_tick_per_s": d.time_scale,
        "passo_controllo_distanza_mm": d.clearance_step_mm,
        "max_soste_intermedie": d.max_soste_intermedie,
        "larghezza_pezzo_mm": d.larghezza_pezzo,
        "altezza_pezzo_mm": d.altezza_pezzo,
        "max_carroponti": cfg.max_carroponti,
        "tempo_limite_per_tentativo_s": cfg.tempo_limite_s,
    }
    zone = (
        None
        if cfg.zone_manuali is None
        else [(z.lo, z.hi) for z in cfg.zone_manuali]
    )
    cambio_quota = [
        (verso, z.position, z.intermediate1, z.intermediate2, z.corsa_totale)
        for verso, z in (
            ("carico", d.cambio_quota_carico),
            ("scarico", d.cambio_quota_scarico),
        )
        if z is not None
    ] or None
    return vasche, percorso, parametri, zone, cambio_quota


def scrivi_modello(percorso_file: str) -> str:
    """Crea un file Excel gia' compilato con una linea di esempio, da usare
    come punto di partenza. Restituisce il percorso del file scritto."""
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)  # il foglio vuoto che openpyxl crea da solo
    _aggiungi_fogli_linea(wb, *_righe_esempio())
    wb.save(percorso_file)
    return percorso_file


def scrivi_linea(
    percorso_file: str, cfg: Configurazione, ciclogramma=None
) -> str:
    """Riscrive una linea nel formato di INGRESSO, con dentro il suo
    ciclogramma.

    Serve a non perdere il lavoro: un ciclogramma composto a mano vive solo
    nella memoria del programma, e chiuso il programma andrebbe rifatto. Il
    file dei risultati non basta a riprenderlo -- e' un referto, e per giunta
    non contiene le cinematiche, senza le quali le durate dei trasporti non si
    possono ricalcolare. Un file di ingresso invece descrive gia' tutto: gli
    si aggiunge un foglio e si riapre con "Apri linea...".

    `ciclogramma`: None, oppure un dizionario con `T`, `permanenze`
    (stazione -> secondi) e `assegnazione` (mossa -> carroponte, 0-based)."""
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    _aggiungi_fogli_linea(
        wb, *_righe_da_configurazione(cfg), data=cfg.data, ciclogramma=ciclogramma
    )
    wb.save(percorso_file)
    return percorso_file


def _aggiungi_fogli_linea(
    wb,
    vasche,
    percorso,
    parametri,
    zone=None,
    cambio_quota=None,
    data=None,
    ciclogramma=None,
):
    """Aggiunge a `wb` i fogli del formato di INGRESSO.

    Unico posto da cui esce quel formato: il modello d'esempio, una linea
    risalvata e il file dei risultati passano tutti di qui, quindi non possono
    divergere. Aggiunge invece di creare il file proprio perche' i risultati
    devono poterci stare nello stesso libro -- un file solo che e' insieme il
    referto e la linea da riaprire."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    intestazione = Font(bold=True, color="FFFFFF")
    sfondo = PatternFill("solid", fgColor="4F6228")
    nota = Font(italic=True, color="808080")
    titolo_par = Font(bold=True, size=12)

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
    ws = wb.create_sheet(FOGLIO_ISTRUZIONI)
    ws.column_dimensions["A"].width = 110
    for testo, stile in [
        ("Come compilare questo file", titolo_par),
        ("", None),
        (f"Foglio {FOGLIO_VASCHE}", titolo_par),
        ("Una riga per vasca fisica.", None),
        ("  id            nome della vasca, usato nel foglio Percorso", None),
        ("  posizione_mm  distanza lungo la rotaia, in MILLIMETRI", None),
        (
            "  posti         quanti pezzi ci stanno dentro contemporaneamente "
            "(vuoto = 1)",
            None,
        ),
        (
            "  corsa_verticale_mm  corsa fra quota di trasporto e quota di "
            "immersione, per QUESTA vasca;",
            None,
        ),
        (
            "                obbligatoria. Scrivi 0 dove non c'e' "
            "movimentazione verticale (carico, scarico)",
            None,
        ),
        (
            "  traslazione_con_gancio_basso   1 (o vuoto) se il gancio SCARICO "
            "puo' passare basso sopra",
            None,
        ),
        (
            "                      questa vasca, che e' il caso normale. 0 se "
            "e' un OSTACOLO: li' il gancio",
            None,
        ),
        (
            "                      calato non passa e non cambia quota, e chi "
            "deve scavalcarla sale su",
            None,
        ),
        (
            "                      uno svincolo, viaggia alto e riscende. Un "
            "rientro che non scavalca",
            None,
        ),
        (
            "                      nessun ostacolo resta basso e non paga "
            "nessuna corsa verticale.",
            None,
        ),
        (
            "  svincolo_*_mm       le due posizioni, una per lato, in cui il "
            "gancio SCARICO puo' salire",
            None,
        ),
        (
            "                      e scendere -- MAI sopra il centro di una "
            "vasca. Sono quote assolute",
            None,
        ),
        (
            "                      sulla rotaia, e ciascuna deve cadere fra "
            "questa vasca e quella accanto.",
            None,
        ),
        (
            "                      Stanno nell'ordine della rotaia: prima il "
            "NEGATIVO (a sinistra della",
            None,
        ),
        (
            "                      vasca, quote piu' piccole), poi il POSITIVO "
            "(a destra, quote piu' grandi).",
            None,
        ),
        (
            "                      Se una vasca ne ha uno devono averlo TUTTE "
            "(almeno uno per vasca):",
            None,
        ),
        (
            "                      qualunque vasca puo' essere il capo di un "
            "rientro che deve passare alto.",
            None,
        ),
        (
            "  sgocciolamento_s    quanto il telaio resta sospeso sopra QUESTA "
            "vasca a scolare, dopo l'emersione;",
            None,
        ),
        (
            "                dipende dal bagno, non dal carroponte. "
            "Obbligatorio: scrivi 0 dove non serve",
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
            "  permanenza    tempo EFFETTIVO in bagno, da quando il telaio e' immerso "
            "a quando ricomincia a salire.",
            None,
        ),
        (
            "                Si dichiara come tempo TEORICO piu' due tolleranze: "
            "il software lavora fra",
            None,
        ),
        (
            "                teorico - delta_negativo e teorico + delta_positivo. "
            "I due delta sono ampiezze,",
            None,
        ),
        (
            "                si scrivono POSITIVI tutti e due; delta a zero "
            "significa permanenza rigida.",
            None,
        ),
        (
            "                Comprende le corse a vuoto del gancio: dopo lo sgancio "
            "il gancio risale e il pezzo",
            None,
        ),
        (
            "                resta giu', e per riprenderlo deve ricalare mentre il "
            "pezzo e' ancora immerso.",
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
        (
            "  d_max_...       la DECELERAZIONE, in frenata. E' facoltativa: "
            "lasciata vuota si frena",
            None,
        ),
        (
            "                  con l'accelerazione, com'era prima che questo "
            "parametro esistesse.",
            None,
        ),
        (
            "  v_approach_sollevamento_mm_s e d_approach_sollevamento_mm: la "
            "zona di AVVICINAMENTO.",
            None,
        ),
        (
            "                  Sono gli ultimi millimetri di corsa verso il "
            "punto in cui il telaio",
            None,
        ),
        (
            "                  viene preso o posato, e la velocita' ridotta "
            "con cui si percorrono.",
            None,
        ),
        (
            "                  Scendendo il gancio ci arriva gia' a quella "
            "velocita' e la tiene fino",
            None,
        ),
        (
            "                  all'ultima frenata; salendo riparte piano e "
            "accelera solo dopo.",
            None,
        ),
        (
            "                  Valgono col telaio e a gancio scarico, e NON "
            "sulle stazioni servite",
            None,
        ),
        (
            "                  da una zona di cambio quota. O tutte e due, o "
            "nessuna delle due.",
            None,
        ),
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
        (f"Foglio {FOGLIO_CAMBIO_QUOTA} (facoltativo)", titolo_par),
        (
            "LASCIALO VUOTO se il carroponte puo' salire e scendere dove si "
            "trova: e' il caso normale.",
            None,
        ),
        (
            "Serve agli impianti in cui, sopra il carico e sopra lo scarico, il "
            "carroponte non puo'",
            None,
        ),
        (
            "cambiare quota e deve prima portarsi in un punto dedicato. Al "
            "massimo due righe:",
            None,
        ),
        (
            "  zona          'carico' (fra il carico e la prima vasca) oppure "
            "'scarico' (fra",
            None,
        ),
        ("                l'ultima vasca e lo scarico)", None),
        (
            "  posizione_mm  dove sta il punto di cambio quota sulla rotaia. Deve "
            "cadere FRA la",
            None,
        ),
        ("                stazione servita e quella accanto", None),
        (
            "Le tre quote si misurano DAL BASSO: 0 e' la posizione piu' bassa del "
            "carroponte,",
            None,
        ),
        ("cioe' quella a cui gia' trasla quando viaggia col gancio calato.", None),
        (
            "  intermediate1_mm  quota a cui il gancio arriva alla stazione, e a "
            "cui vi posa il telaio",
            None,
        ),
        (
            "  intermediate2_mm  quota a cui il telaio viene sollevato prima di "
            "lasciare la stazione",
            None,
        ),
        ("  corsa_totale_mm   distanza da 0 fino alla cima", None),
        (
            "Verso il CARICO il carroponte fa: trasla al punto di cambio quota, "
            "sale a intermediate1,",
            None,
        ),
        (
            "va al carico, prende il pezzo salendo a intermediate2, torna al punto "
            "di cambio quota",
            None,
        ),
        (
            "e sale in cima. Verso lo SCARICO fa lo stesso giro al contrario. Il "
            "tempo di tutto il",
            None,
        ),
        ("giro e' contato nella presa (o nel rilascio) di quella stazione.", None),
        (
            "La corsa della vasca di carico e di scarico deve essere 0: li' la "
            "corsa la definisce",
            None,
        ),
        ("questo foglio (il telaio va da intermediate1 a intermediate2).", None),
        ("", None),
        (f"Foglio {FOGLIO_CICLOGRAMMA} (facoltativo)", titolo_par),
        (
            "Lo scrive il programma quando salvi, e serve a RIPRENDERE il lavoro: "
            "riaprendo questo",
            None,
        ),
        (
            "file il ciclogramma e' gia' li', pronto da modificare invece che da "
            "rifare.",
            None,
        ),
        (
            "  takt_time_s   il periodo del ciclo (cella B1)",
            None,
        ),
        (
            "  carroponte    chi fa quel trasporto, numerato da 1. Vuoto = non "
            "ancora assegnato",
            None,
        ),
        (
            "  tempo_in_vasca_s   quanto il pezzo resta nella vasca DA CUI parte "
            "quel trasporto",
            None,
        ),
        (
            "  attesa_dopo_consegna_s   quanto il carroponte resta fermo dove "
            "ha appena consegnato,",
            None,
        ),
        (
            "                prima di ripartire a vuoto. Vuoto = decidilo tu, "
            "e il programma sceglie",
            None,
        ),
        (
            "  sosta_in_vasca / sosta_s   se durante quel rientro a vuoto il "
            "carroponte si ferma in una",
            None,
        ),
        (
            "                vasca IN MEZZO, quale e per quanti secondi. "
            "Vanno insieme: o entrambe o",
            None,
        ),
        (
            "                nessuna. Vuote = rientro diritto, che e' il caso "
            "normale; una sosta per",
            None,
        ),
        (
            "                strada serve a stare lontani dal carroponte "
            "vicino, e costa il tempo di",
            None,
        ),
        (
            "                fermarsi e ripartire.",
            None,
        ),
        (
            "Cancellalo se vuoi ripartire da zero: senza, la linea si apre e basta.",
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
    prepara(
        ws,
        [
            "id",
            "posizione_mm",
            "posti",
            "corsa_verticale_mm",
            "sgocciolamento_s",
            "svincolo_negativo_mm",
            "svincolo_positivo_mm",
            "traslazione_con_gancio_basso",
            "larghezza_mm",
            "altezza_mm",
        ],
        [22, 14, 8, 20, 20, 22, 22, 28, 14, 14],
    )
    for riga in vasche:
        ws.append(list(riga))

    # -- Percorso --------------------------------------------------------
    ws = wb.create_sheet(FOGLIO_PERCORSO)
    prepara(
        ws,
        [
            "n",
            "vasca",
            "permanenza_teorica_s",
            "delta_negativo_s",
            "delta_positivo_s",
        ],
        [6, 22, 22, 20, 20],
    )
    for n, (tid, teorico, dneg, dpos) in enumerate(percorso, start=1):
        ws.append([n, tid, teorico, dneg, dpos])

    # -- Parametri -------------------------------------------------------
    ws = wb.create_sheet(FOGLIO_PARAMETRI)
    prepara(ws, ["parametro", "valore", "unita", "descrizione"], [30, 12, 10, 62])
    for nome, (unita, obbligatorio, default, descr) in _PARAMETRI.items():
        suffisso = "" if obbligatorio else f" (facoltativo, default {default})"
        ws.append([nome, parametri.get(nome), unita, descr + suffisso])

    # -- Zone (facoltativo) ----------------------------------------------
    ws = wb.create_sheet(FOGLIO_ZONE)
    prepara(ws, ["prima_mossa", "ultima_mossa", "", "note"], [16, 16, 4, 80])
    if zone:
        for lo, hi in zone:
            ws.append([lo, hi])
    else:
        # la nota va in colonna D, fuori dalle colonne lette
        ws.cell(2, 4).value = (
            "Vuoto = numero di carroponti e zone scelti automaticamente "
            "(consigliato). Vedi il foglio Istruzioni."
        )
        ws.cell(2, 4).font = nota

    # -- CambioQuota (facoltativo) ---------------------------------------
    ws = wb.create_sheet(FOGLIO_CAMBIO_QUOTA)
    prepara(
        ws,
        [
            "zona",
            "posizione_mm",
            "intermediate1_mm",
            "intermediate2_mm",
            "corsa_totale_mm",
            "",
            "note",
        ],
        [12, 14, 18, 18, 18, 4, 80],
    )
    if cambio_quota:
        for riga in cambio_quota:
            ws.append(list(riga))
    else:
        ws.cell(2, 7).value = (
            "Vuoto = il carroponte sale e scende dove vuole, che e' il caso "
            "normale. Vedi il foglio Istruzioni."
        )
        ws.cell(2, 7).font = nota

    # -- Ciclogramma (facoltativo) ---------------------------------------
    if ciclogramma is not None and data is not None:
        _scrivi_foglio_ciclogramma(
            wb, data, ciclogramma, intestazione, sfondo, nota
        )


def _scrivi_foglio_ciclogramma(wb, data, ciclogramma, intestazione, sfondo, nota):
    """Il ciclogramma nei suoi gradi di liberta': takt time, tempo in vasca di
    ogni tappa, chi fa ogni trasporto, e dove ogni carroponte passa il tempo
    morto del rientro a vuoto.

    Non si scrivono gli istanti di prelievo ne' le traiettorie: sono
    conseguenze, e riscriverle vorrebbe dire poterle rileggere in contrasto
    con quello da cui derivano.

    Le ultime tre colonne sono l'eccezione che conferma la regola. Quanto il
    carroponte resta fermo dove ha consegnato NON e' una conseguenza delle
    fasi: a parita' di takt time, permanenze e assegnazione il carro puo'
    ripartire subito e aspettare a destinazione, oppure restare fermo e
    partire all'ultimo momento. Sono traiettorie diverse, con collisioni
    diverse. Finche' la scelta la faceva una convenzione scritta nel codice
    non c'era niente da salvare; da quando la fa il solutore, non salvarla
    significherebbe riaprire il file e trovarsi un ciclogramma diverso da
    quello che era stato verificato.

    Lo stesso vale, e ancora di piu', per la SOSTA in una vasca in mezzo: li'
    non cambia solo quando il carroponte si muove, cambia dove passa. Senza
    quelle due colonne il rientro si ricostruirebbe diritto -- piu' corto di
    quanto e' -- e non tornerebbero nemmeno i tempi."""
    ws = wb.create_sheet(FOGLIO_CICLOGRAMMA)
    for riga, (nome, valore, spiega) in enumerate(
        (
            ("takt_time_s", round(float(ciclogramma["T"]), 9),
             "il periodo del ciclo, in secondi"),
            ("carroponti", int(ciclogramma.get("n_carroponti") or 1),
             "quanti ne hai a disposizione (anche se non tutti usati)"),
        ),
        start=1,
    ):
        ws.cell(riga, 1).value = nome
        ws.cell(riga, 1).font = intestazione
        ws.cell(riga, 1).fill = sfondo
        ws.cell(riga, 2).value = valore
        ws.cell(riga, 3).value = spiega
        ws.cell(riga, 3).font = nota

    # Le cifre non si tagliano. Sembrano un dettaglio estetico -- chi legge un
    # tempo in vasca non guarda il microsecondo -- ma questi valori vengono
    # RILETTI e la catena dei tempi li somma uno sull'altro: da li' si decide,
    # con un arrotondamento all'insu', quanti periodi interi il pezzo resta in
    # vasca. Un millesimo di troppo su una tappa al limite fa scattare un
    # periodo, e il ciclogramma riaperto non e' piu' quello salvato.
    titoli = ["mossa", "da vasca", "a vasca", "carroponte", "tempo_in_vasca_s",
              "attesa_dopo_consegna_s", "sosta_in_vasca", "sosta_s"]
    for col, (titolo, larghezza) in enumerate(
        zip(titoli, [8, 22, 22, 12, 18, 24, 22, 12]), start=1
    ):
        cella = ws.cell(4, col)
        cella.value = titolo
        cella.font = intestazione
        cella.fill = sfondo
        ws.column_dimensions[chr(ord("A") + col - 1)].width = larghezza

    permanenze = ciclogramma.get("permanenze") or {}
    assegnazione = ciclogramma.get("assegnazione") or {}
    attese = ciclogramma.get("attese") or {}
    soste = ciclogramma.get("soste") or {}
    for k in range(data.n_moves):
        # append() parte dopo l'ultima riga scritta, cioe' dalla 5
        carro = assegnazione.get(k)
        tempo_vasca = permanenze.get(k)
        attesa = attese.get(k)
        # La sosta per strada si scrive con il NOME della vasca, non con
        # l'indice di tappa: e' quello che si legge senza contare le righe del
        # foglio Percorso. Se la stessa vasca compare due volte nella ricetta il
        # nome non dice quale tappa sia, e non serve che lo dica: le due tappe
        # stanno nello stesso punto della rotaia, quindi per una sosta -- che e'
        # solo un posto dove stare fermi -- sono la stessa cosa.
        sosta = soste.get(k)
        ws.append(
            [
                k,
                data.route[k].tank_id,
                data.route[k + 1].tank_id,
                None if carro is None else carro + 1,
                None if tempo_vasca is None else round(float(tempo_vasca), 9),
                None if attesa is None else round(float(attesa), 9),
                None if sosta is None else data.route[sosta.stazione].tank_id,
                None if sosta is None else round(float(sosta.secondi), 9),
            ]
        )


# --------------------------------------------------------------------------
# Scrittura dei risultati
# --------------------------------------------------------------------------

# etichette leggibili per i tipi di segmento
# Attenzione ai nomi: "presa" e "rilascio" NON sono la sola corsa verticale.
# Chiamarli "emersione" e "immersione" -- come si e' fatto per un po' -- fa
# cercare in quella durata solo il tempo di salita, non trovarcelo, e sospettare
# un errore di calcolo. Comprendono anche la corsa a vuoto del gancio, i tempi
# morti di aggancio e sgancio, e per la presa lo sgocciolamento: cosa c'e'
# dentro lo dice la nota in fondo al foglio.
_FASI = {
    "pick": "presa dalla vasca",
    "loaded": "trasporto con pezzo",
    "release": "rilascio nella vasca",
    "empty": "spostamento a vuoto",
    "wait": "attesa",
    "lift_empty": "corsa verticale a vuoto",
    "quota": "traslazione di cambio quota",
}
_FASI_IN_MOVIMENTO = {"loaded", "empty", "quota"}

_SEVERITA = {"error": "ERRORE", "warning": "avviso", "info": "nota"}


def _mosse_dei_segmenti(segs: list) -> list[int]:
    """Per ogni segmento, l'indice (dentro l'ordine di visita) della mossa a
    cui appartiene. Un segmento di presa appartiene alla mossa che sta per
    iniziare; tutti gli altri all'ultima mossa cominciata."""
    indici_loaded = [j for j, s in enumerate(segs) if s.kind == "loaded"]
    out = []
    i = -1
    prossimo = 0
    for j, s in enumerate(segs):
        if s.kind == "loaded":
            i += 1
            prossimo = i + 1
            out.append(i)
        elif s.kind == "pick" or (
            # una traslazione di cambio quota PRIMA del trasporto fa parte
            # della presa, e quindi della mossa che sta per iniziare; quella
            # dopo fa parte del rilascio, come tutto il resto
            s.kind == "quota"
            and prossimo < len(indici_loaded)
            and j < indici_loaded[prossimo]
        ):
            out.append(min(prossimo, len(indici_loaded) - 1))
        else:
            out.append(max(i, 0))
    return out


def _stazione_in_posizione(data: ProblemData, x: float, altrimenti: int) -> int:
    """La tappa che sta in quel punto della rotaia, o `altrimenti` se li' non
    c'e' nessuna tappa (e' il caso degli svincoli)."""
    for i in range(data.n_stations):
        if abs(data.approach_position(i) - x) < 1e-6:
            return i
    return altrimenti


def _righe_movimenti(data: ProblemData, solution) -> list[list]:
    """Tabella degli spostamenti: una riga per tratto, per carroponte."""
    righe = []
    for h, (plan, segs) in enumerate(
        zip(solution.plans, solution.segments_per_hoist)
    ):
        ordine = plan.order
        n = len(ordine)
        appartenenza = _mosse_dei_segmenti(segs)
        # dove sta, nella lista, il trasporto di ciascuna mossa: separa le
        # traslazioni di cambio quota della presa da quelle del rilascio
        indice_loaded = {s.move: j for j, s in enumerate(segs) if s.kind == "loaded"}
        for j, seg in enumerate(segs):
            i = appartenenza[j]
            k = ordine[i]
            if seg.kind == "pick":
                st_da = st_a = k
            elif seg.kind == "loaded":
                st_da, st_a = k, k + 1
            elif seg.kind == "release":
                st_da = st_a = k + 1
            elif seg.kind == "quota":
                j_trasporto = indice_loaded.get(seg.move)
                st_da = st_a = (
                    k if j_trasporto is not None and j < j_trasporto else k + 1
                )
            elif seg.kind == "empty":
                # Di norma il tratto va dalla vasca di consegna a quella del
                # prelievo dopo. Con una sosta per strada no: allora una delle
                # due estremita' e' la vasca dove il carroponte si e' fermato, e
                # la si riconosce dalla POSIZIONE. Gli svincoli, che non sono
                # stazioni, non si riconoscono e restano attribuiti agli estremi
                # dell'arco -- che e' quello che si vuole.
                st_da = _stazione_in_posizione(data, seg.x_start, k + 1)
                st_a = _stazione_in_posizione(
                    data, seg.x_end, ordine[(i + 1) % n]
                )
            else:  # attesa: fermo su una stazione, o prima o dopo il rientro
                # Prima i due estremi del rientro, che sono il caso normale;
                # poi TUTTE le stazioni, perche' il carroponte puo' essersi
                # fermato in una vasca in mezzo. Senza il secondo giro quella
                # sosta verrebbe attribuita alla vasca di consegna, cioe'
                # scritta nel posto sbagliato.
                candidate = (k + 1, ordine[(i + 1) % n])
                st_da = st_a = next(
                    (
                        c
                        for c in (*candidate, *range(data.n_stations))
                        if abs(data.station_position(c) - seg.x_start) < 1e-6
                    ),
                    candidate[0],
                )
            righe.append(
                [
                    h + 1,
                    _FASI.get(seg.kind, seg.kind),
                    data.route[st_da].tank_id,
                    data.route[st_a].tank_id,
                    round(seg.t_start, 2),
                    round(seg.t_end, 2),
                    round(seg.t_end - seg.t_start, 2),
                    round(seg.x_start, 1),
                    round(seg.x_end, 1),
                ]
            )
    return righe


def _utilizzo_carroponti(solution, T: float) -> list[float]:
    """Frazione del ciclo in cui ciascun carroponte e' effettivamente in
    movimento (il resto e' attesa o movimentazione verticale)."""
    out = []
    for segs in solution.segments_per_hoist:
        moto = sum(
            s.t_end - s.t_start for s in segs if s.kind in _FASI_IN_MOVIMENTO
        )
        out.append(moto / T if T else 0.0)
    return out


# Le due meta' del file dei risultati. I colori finiscono sulla linguetta, che
# e' l'unico posto in cui si guarda quando si cerca un foglio.
_COLORE_INGRESSO = "4F81BD"  # blu
_COLORE_REFERTO = "6AA84F"  # verde


# Una riga per foglio, da mettere nel cartello del suo gruppo.
_COSA_CONTIENE = {
    FOGLIO_ISTRUZIONI: "come si compila il file, foglio per foglio",
    FOGLIO_VASCHE: "le vasche: posizione, posti, corsa verticale, sgocciolamento",
    FOGLIO_PERCORSO: "la ricetta: in che ordine il pezzo visita le vasche, e per quanto",
    FOGLIO_PARAMETRI: "carroponti, tolleranze, distanze di sicurezza",
    FOGLIO_ZONE: "quale carroponte serve quale tratto di linea (facoltativo)",
    FOGLIO_CAMBIO_QUOTA: (
        "dove il carroponte cambia quota agli estremi della linea (facoltativo)"
    ),
    FOGLIO_CICLOGRAMMA: "il ciclogramma nei suoi tre gradi di liberta', per riprenderlo",
    "Riepilogo": "takt time, produttivita', carroponti, esito della verifica",
    "Movimenti": "ogni tratto di ogni carroponte: quando, da dove, a dove",
    "TempiVerticali": "dove va il tempo di presa e di rilascio, vasca per vasca",
    "FlussoPezzo": "il percorso di un pezzo, vasca per vasca",
    "Verifica": "i rilievi del verificatore indipendente, divisi per gravita'",
}


def _cartello(wb, titolo: str, colore: str, sottotitolo: str, da: int):
    """Mette un cartello davanti al gruppo di fogli che comincia in posizione
    `da`, ed elenca cosa c'e' dentro.

    Il file dei risultati e' due cose insieme -- la linea da riaprire e il
    referto da leggere -- e con dodici linguette di fila non si capisce dove
    finisce una e comincia l'altra. Il cartello non contiene dati: dice cosa
    viene dopo, e la sua linguetta colorata si vede senza leggere niente.

    L'elenco NON e' scritto a mano: si ricava dai fogli che ci sono davvero in
    quel momento. Un elenco fisso resterebbe indietro il giorno che si
    aggiunge o si toglie un foglio, e un indice che mente e' peggio di nessun
    indice."""
    from openpyxl.styles import Font, PatternFill

    gruppo = list(wb.sheetnames[da:])
    ws = wb.create_sheet(titolo)
    ws.sheet_properties.tabColor = colore
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 96
    ws.append([titolo.upper()])
    ws.cell(1, 1).font = Font(bold=True, size=18, color=colore)
    ws.append([sottotitolo])
    ws.cell(2, 1).font = Font(italic=True, color="808080")
    ws.append([])
    ws.append(["foglio", "cosa contiene"])
    for col in (1, 2):
        ws.cell(4, col).font = Font(bold=True, color="FFFFFF")
        ws.cell(4, col).fill = PatternFill("solid", fgColor=colore)
    for nome in gruppo:
        ws.append([nome, _COSA_CONTIENE.get(nome, "")])
        ws.cell(ws.max_row, 1).font = Font(bold=True)
    # nasce in coda al gruppo e lo si porta davanti
    wb.move_sheet(ws, offset=-len(gruppo))
    return ws


def scrivi_risultati(
    percorso_file: str,
    data: ProblemData,
    solution,
    report,
    sorgente: Optional[str] = None,
    cfg: Optional[Configurazione] = None,
    ciclogramma: Optional[dict] = None,
) -> str:
    """Scrive UN file Excel che e' due cose insieme.

    Prima la linea nel formato di INGRESSO col ciclogramma dentro -- se si
    passano `cfg` e `ciclogramma` -- cosi' lo stesso file si riapre con "Apri
    linea..." e il lavoro riprende da dov'era. Poi il REFERTO: Riepilogo,
    Movimenti, FlussoPezzo, Verifica, da leggere e da consegnare.

    I due gruppi sono separati da un cartello colorato, `Input` e `Output`, e
    stanno in quest'ordine perche' e' quello in cui le cose sono successe: si
    parte da una linea e se ne ricava un risultato. Il file si apre comunque
    sul Riepilogo, che e' quello che si va a leggere.

    Due file separati sarebbero due cose da tenere insieme e da non
    confondere; `leggi_problema` cerca i fogli per nome e ignora gli altri,
    quindi non c'e' ragione di dividerli."""
    from datetime import datetime

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    intestazione = Font(bold=True, color="FFFFFF")
    sfondo = PatternFill("solid", fgColor="4F6228")
    grassetto = Font(bold=True)
    rosso = PatternFill("solid", fgColor="F4CCCC")
    arancio = PatternFill("solid", fgColor="FCE5CD")
    grigio = PatternFill("solid", fgColor="EFEFEF")

    T = solution.T
    wb = Workbook()
    wb.remove(wb.active)  # il foglio vuoto che openpyxl crea da solo

    # -- prima la linea, cosi' com'e' entrata ------------------------------
    # I fogli si creano nell'ordine in cui devono comparire, non riordinandoli
    # alla fine: chi legge il codice vede la stessa sequenza che vedra' nel
    # file. I cartelli si mettono dopo il loro gruppo e si spostano davanti,
    # cosi' possono elencare i fogli che ci sono davvero.
    if cfg is not None:
        _aggiungi_fogli_linea(
            wb,
            *_righe_da_configurazione(dataclasses.replace(cfg, data=data)),
            data=data,
            ciclogramma=ciclogramma,
        )
        _cartello(
            wb,
            "Input",
            _COLORE_INGRESSO,
            "I fogli che seguono sono la LINEA, nello stesso formato del file di "
            "ingresso: questo file si riapre con 'Apri linea...' e il lavoro "
            "riprende da dov'era.",
            da=0,
        )
    inizio_referto = len(wb.sheetnames)

    def tabella(ws, titoli, larghezze, righe, formati=None):
        ws.append(titoli)
        for col, larghezza in enumerate(larghezze, start=1):
            cella = ws.cell(1, col)
            cella.font = intestazione
            cella.fill = sfondo
            cella.alignment = Alignment(horizontal="center")
            ws.column_dimensions[get_column_letter(col)].width = larghezza
        for riga in righe:
            ws.append(riga)
        if formati:
            for col, fmt in formati.items():
                for r in range(2, ws.max_row + 1):
                    ws.cell(r, col).number_format = fmt
        ws.freeze_panes = "A2"

    # -- Riepilogo -------------------------------------------------------
    ws = wb.create_sheet("Riepilogo")
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 46

    def voce(etichetta, valore, nota="", formato=None):
        ws.append([etichetta, valore, nota])
        if formato:
            ws.cell(ws.max_row, 2).number_format = formato
        elif isinstance(valore, float):
            ws.cell(ws.max_row, 2).number_format = "0.00"

    def sezione(titolo):
        ws.append([])
        ws.append([titolo])
        ws.cell(ws.max_row, 1).font = grassetto

    ws.append(["Ciclogramma carroponti - risultati"])
    ws.cell(1, 1).font = Font(bold=True, size=13)
    ws.append([])
    voce("File di origine", sorgente or "-")
    voce("Calcolato il", datetime.now().strftime("%d/%m/%Y %H:%M"))
    voce("Stato della risoluzione", solution.status)

    sezione("Produzione")
    voce("Takt time", round(T, 2), "s fra un pezzo e il successivo")
    voce("Produttivita'", round(3600.0 / T, 1) if T else "-", "pezzi/ora", "0.0")
    voce("Numero di carroponti", len(data.zones))

    sezione("Sicurezza")
    voce(
        "Distanza minima fra carroponti",
        round(report.min_separation, 1) if report.min_separation != float("inf") else "-",
        "mm, misurata campionando le posizioni reali",
        "0.0",
    )
    voce("Distanza richiesta", round(report.required_separation, 1), "mm", "0.0")
    if report.min_separation != float("inf"):
        voce(
            "Margine residuo",
            round(report.min_separation - report.required_separation, 1),
            f"mm, all'istante {report.min_separation_t:.2f} s",
            "0.0",
        )

    sezione("Movimentazione verticale")
    corse = {round(data.lift_height_at(s), 1) for s in range(1, data.n_moves)}
    voce(
        "Corsa verticale",
        min(corse) if corse else 0.0,
        "mm"
        + ("" if len(corse) <= 1 else f" (fino a {max(corse):.0f} mm, varia per vasca)"),
        "0.0",
    )
    presa = {round(data.pick_time_at(s), 2) for s in range(1, data.n_moves)}
    rilascio = {round(data.release_time_at(s), 2) for s in range(1, data.n_moves)}
    voce(
        "Tempo di presa",
        min(presa) if presa else 0.0,
        "s" + ("" if len(presa) <= 1 else f" (fino a {max(presa):.2f} s, varia per vasca)"),
    )
    voce(
        "Tempo di rilascio",
        min(rilascio) if rilascio else 0.0,
        "s"
        + ("" if len(rilascio) <= 1 else f" (fino a {max(rilascio):.2f} s, varia per vasca)"),
    )

    sezione("Verifica indipendente")
    voce("Esito", "SUPERATA" if report.ok else "NON SUPERATA")
    voce("Errori", len(report.errors))
    voce("Avvisi", len(report.warnings))
    voce("Note", len(report.infos))

    sezione("Carroponti")
    ws.append(
        ["carroponte", "mosse servite", "da vasca", "a vasca", "tratto rotaia [mm]", "utilizzo"]
    )
    for col in range(1, 7):
        ws.cell(ws.max_row, col).font = grassetto
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 20
    ws.column_dimensions["F"].width = 12
    utilizzo = _utilizzo_carroponti(solution, T)
    for h, z in enumerate(data.zones):
        xs = [data.station_position(i) for i in range(z.lo, z.hi + 2)]
        ws.append(
            [
                h + 1,
                f"{z.lo}-{z.hi}",
                data.route[z.lo].tank_id,
                data.route[z.hi + 1].tank_id,
                f"{min(xs):.2f} - {max(xs):.2f}",
                round(utilizzo[h], 3),
            ]
        )
        ws.cell(ws.max_row, 6).number_format = "0.0%"

    # Le soste in una vasca IN MEZZO. Si vedono nel foglio Movimenti come
    # un'attesa sopra una vasca che non e' ne' la partenza ne' l'arrivo del
    # rientro, ma li' bisogna saperle cercare: elencate qui dicono anche perche'
    # ci sono.
    soste = [
        (h, k, s)
        for h, plan in enumerate(solution.plans)
        for k, s in sorted(plan.soste_intermedie.items())
    ]
    if soste:
        sezione("Soste durante il rientro a vuoto")
        ws.append(
            ["carroponte", "dopo il trasporto", "in vasca", "durata [s]"]
        )
        for col in range(1, 5):
            ws.cell(ws.max_row, col).font = grassetto
        for h, k, sosta in soste:
            ws.append(
                [h + 1, k, data.route[sosta.stazione].tank_id,
                 round(sosta.secondi, 2)]
            )
            ws.cell(ws.max_row, 4).number_format = "0.00"
        ws.append([])
        ws.append([
            "Il carroponte si ferma in una vasca in mezzo invece che a un "
            "estremo del viaggio: serve a stare lontano dal vicino quando "
            "entrambi gli estremi sono vasche di confine."
        ])
        ws.cell(ws.max_row, 1).font = Font(italic=True, color="666666")

    # -- Movimenti -------------------------------------------------------
    ws = wb.create_sheet("Movimenti")
    tabella(
        ws,
        [
            "carroponte",
            "fase",
            "da vasca",
            "a vasca",
            "inizio [s]",
            "fine [s]",
            "durata [s]",
            "da [mm]",
            "a [mm]",
        ],
        [12, 24, 20, 20, 12, 12, 12, 10, 10],
        _righe_movimenti(data, solution),
        formati={5: "0.00", 6: "0.00", 7: "0.00", 8: "0.000", 9: "0.000"},
    )
    ws.append([])
    for testo in (
        f"Tempi in secondi dall'origine del ciclo. Il ciclo si ripete "
        f"identico ogni {T:.2f} s.",
        "La 'presa dalla vasca' non e' la sola emersione: comprende la discesa "
        "del gancio a vuoto, l'aggancio, il sollevamento del telaio e lo "
        "sgocciolamento sopra la vasca. Il 'rilascio nella vasca' comprende "
        "l'immersione, lo sgancio e la risalita del gancio a vuoto. Sono quindi "
        "sempre piu' lunghi della sola corsa verticale: il dettaglio per vasca "
        "e' nel foglio TempiVerticali.",
    ):
        ws.append([testo])
        ws.cell(ws.max_row, 1).font = Font(italic=True, color="808080")

    # -- Tempi verticali -------------------------------------------------
    # Dove va a finire il tempo di presa e di rilascio, vasca per vasca. Senza,
    # una presa da 26 secondi su una corsa da un metro e mezzo sembra un errore
    # di calcolo -- e non c'e' modo di scoprire che dieci di quei secondi sono
    # lo sgocciolamento che si e' dichiarato.
    ws = wb.create_sheet("TempiVerticali")
    righe = []
    viste = set()
    for s in range(data.n_stations):
        tid = data.route[s].tank_id
        if tid in viste:
            continue  # stessa vasca, stessi tempi: non si ripete
        viste.add(tid)
        presa = data.pick_phases(s)
        rilascio = data.release_phases(s)
        # Le colonne si prendono per NOME e non per posizione: con la
        # traslazione a gancio basso -- il caso normale -- le corse a vuoto non
        # ci sono affatto, e contarle per indice farebbe slittare tutto il
        # foglio di una colonna senza dirlo.
        durate = {f.name: round(f.duration, 3) for f in presa + rilascio}

        def quanto(nome):
            return durate.get(nome, 0.0)

        tot_presa = round(sum(f.duration for f in presa), 3)
        tot_rilascio = round(sum(f.duration for f in rilascio), 3)
        # Quello che non sta in nessuna colonna con un nome: le salite, le
        # discese e le due traslazioni del giro di CAMBIO QUOTA. Si ricava per
        # differenza, e non elencando altre quattro colonne che sarebbero
        # vuote su ogni linea normale. Cosi' la colonna in maiuscolo resta la
        # somma di quelle alla sua sinistra -- che e' la sola cosa che chi
        # legge questo foglio verifica a occhio.
        nominate_presa = sum(
            quanto(n)
            for n in ("discesa del gancio", "aggancio", "sollevamento del telaio",
                      "sgocciolamento")
        )
        nominate_rilascio = sum(
            quanto(n)
            for n in ("immersione del telaio", "sgancio", "risalita del gancio")
        )
        righe.append(
            [
                tid,
                round(data.corsa_verticale(s), 1),
                quanto("discesa del gancio"),
                quanto("aggancio"),
                quanto("sollevamento del telaio"),
                quanto("sgocciolamento"),
                round(tot_presa - nominate_presa, 3),
                tot_presa,
                quanto("immersione del telaio"),
                quanto("sgancio"),
                quanto("risalita del gancio"),
                round(tot_rilascio - nominate_rilascio, 3),
                tot_rilascio,
            ]
        )
    tabella(
        ws,
        [
            "vasca",
            "corsa [mm]",
            "discesa gancio [s]",
            "aggancio [s]",
            "sollevamento [s]",
            "sgocciolamento [s]",
            "cambio quota [s]",
            "PRESA totale [s]",
            "immersione [s]",
            "sgancio [s]",
            "risalita gancio [s]",
            "cambio quota [s]",
            "RILASCIO totale [s]",
        ],
        [20, 12, 18, 13, 17, 18, 17, 17, 15, 12, 18, 17, 19],
        righe,
        formati={c: "0.00" for c in range(2, 14)},
    )
    ws.append([])
    ws.append(
        [
            "I tempi verticali non si dichiarano: si ricavano dalla corsa della "
            "vasca e dalle cinematiche di sollevamento, con lo stesso profilo "
            "trapezoidale del moto orizzontale. Le colonne in maiuscolo sono la "
            "somma di quelle alla loro sinistra, e sono le durate che compaiono "
            "nel foglio Movimenti."
        ]
    )
    ws.append(
        [
            "La colonna 'cambio quota' e' zero ovunque, tranne sul carico e "
            "sullo scarico di un impianto che ha una zona di cambio quota: li' "
            "raccoglie le salite, le discese e le due traslazioni del giro."
        ]
    )
    ws.cell(ws.max_row, 1).font = Font(italic=True, color="808080")
    ws.cell(ws.max_row, 1).font = Font(italic=True, color="808080")

    # -- Flusso del pezzo ------------------------------------------------
    ws = wb.create_sheet("FlussoPezzo")
    righe = []
    at = solution.actual_time
    for s in range(data.n_stations):
        spec = data.route[s]
        cap = data.tanks[spec.tank_id].capacity
        if s == 0:
            arrivo, partenza, permanenza = 0.0, at[0] if at else 0.0, 0.0
        elif s < data.n_moves:
            # `arrivo` e `partenza` sono gli istanti in cui il PEZZO entra e
            # esce dal bagno, non quelli in cui il gancio finisce e ricomincia
            # a muoversi: il telaio e' immerso da quando tocca il fondo -- e
            # il gancio deve ancora sganciare -- a quando ricomincia a salire,
            # cioe' dopo che quello nuovo ha agganciato. I limiti di processo
            # valgono su questa permanenza.
            #
            # E' ESATTAMENTE il bagno del modello: l'intervallo fra la fine
            # del rilascio e l'inizio della presa, allargato dei due soli
            # tempi morti che il telaio passa in fondo alla vasca. Vedi
            # `ProblemData.bath_extra_seconds`, che vale `disengage + engage`
            # e da' la stessa differenza che si ottiene qui.
            #
            # LE CORSE A VUOTO DEL GANCIO NON SI AGGIUNGONO. Il telaio e'
            # davvero ancora giu' mentre il gancio che l'ha deposto risale e
            # mentre quello che verra' a riprenderlo ricala -- ma quelle corse
            # cadono DENTRO l'intervallo fra i due istanti, e sono gia'
            # contate li'. Sommarle di nuovo gonfiava la permanenza di una
            # decina di secondi: abbastanza da far leggere uno sforamento del
            # massimo di processo su un ciclogramma che il verificatore
            # dichiara valido, e da nascondere le vasche che il solutore ha
            # portato esattamente sul minimo. Su una linea a gancio basso,
            # dove quelle corse non le fa nessuno, era tempo inventato.
            fine_rilascio = at[s - 1] + data.loaded_leg_seconds(s - 1)
            arrivo = fine_rilascio - data.disengage_time
            partenza = at[s] + data.engage_time
            permanenza = partenza - arrivo
        else:
            arrivo = at[s - 1] + data.loaded_leg_seconds(s - 1) if at else 0.0
            partenza = arrivo
            permanenza = 0.0
        righe.append(
            [
                s,
                spec.tank_id,
                round(data.station_position(s), 1),
                round(arrivo, 2),
                round(partenza, 2),
                round(permanenza, 2),
                round(spec.nominale, 2),
                round(spec.dwell_min, 2),
                round(spec.dwell_max, 2),
                round(permanenza - spec.dwell_min, 2) if 0 < s < data.n_moves else "",
                round(spec.dwell_max - permanenza, 2) if 0 < s < data.n_moves else "",
                report.tank_occupancy.get(spec.tank_id, 1),
                cap,
                round(data.lift_height_at(s), 1),
                round(data.drain_time_at(s), 2),
                round(data.pick_time_at(s), 2),
                round(data.release_time_at(s), 2),
            ]
        )
    tabella(
        ws,
        [
            "n",
            "vasca",
            "posizione [mm]",
            "ingresso [s]",
            "uscita [s]",
            "permanenza [s]",
            "teorico [s]",
            "min [s]",
            "max [s]",
            "margine sul min [s]",
            "margine sul max [s]",
            "posti usati",
            "posti disponibili",
            "corsa verticale [mm]",
            "sgocciolamento [s]",
            "presa [s]",
            "rilascio [s]",
        ],
        [5, 20, 14, 13, 12, 15, 12, 10, 10, 19, 19, 12, 17, 19, 19, 11, 13],
        righe,
        formati={
            4: "0.00",
            5: "0.00",
            6: "0.00",
            7: "0.00",
            14: "0.000",
            15: "0.00",
            16: "0.00",
            17: "0.00",
        },
    )
    ws.append([])
    ws.append(
        [
            "Tempi assoluti di UN pezzo lungo tutta la linea: possono superare il "
            "takt time, perche' piu' pezzi sono in lavorazione insieme. Ingresso e "
            "uscita sono quelli del PEZZO, non del gancio: il telaio entra in bagno "
            "quando tocca il fondo, e il gancio deve ancora sganciare; ne esce "
            "quando ricomincia a salire, dopo che il gancio nuovo ha agganciato. "
            "Tutto quello che il gancio fa nel frattempo -- risalire, traslare, "
            "ricalare -- e' gia' dentro questa permanenza, ed e' su questa che "
            "valgono i limiti di processo."
        ]
    )
    ws.cell(ws.max_row, 1).font = Font(italic=True, color="808080")

    # -- Verifica --------------------------------------------------------
    ws = wb.create_sheet("Verifica")
    righe = []
    for v in report.violations:
        righe.append(
            [
                _SEVERITA.get(v.severity, v.severity),
                v.kind,
                "/".join(str(h + 1) for h in v.hoists) if v.hoists else "",
                "" if v.move is None else v.move,
                "" if v.station is None else v.station,
                "" if v.t is None else round(v.t, 2),
                "" if v.value is None else round(v.value, 3),
                "" if v.bound is None else round(v.bound, 3),
                "" if v.slack is None else round(v.slack, 3),
                v.message,
            ]
        )
    tabella(
        ws,
        [
            "severita'",
            "tipo",
            "carroponti",
            "mossa",
            "stazione",
            "istante [s]",
            "valore",
            "limite",
            "margine",
            "descrizione",
        ],
        [12, 18, 12, 8, 10, 12, 10, 10, 10, 100],
        righe,
    )
    for r in range(2, ws.max_row + 1):
        sev = ws.cell(r, 1).value
        colore = {"ERRORE": rosso, "avviso": arancio, "nota": grigio}.get(sev)
        if colore:
            for c in range(1, 11):
                ws.cell(r, c).fill = colore
    if not righe:
        ws.append(["", "", "", "", "", "", "", "", "", "Nessun rilievo."])

    # -- dettagli tecnici in coda al riepilogo ---------------------------
    ws = wb["Riepilogo"]
    sezione("Dettagli del calcolo")
    voce("Campionamento della verifica", f"{report.sampling_dt * 1000:.0f}", "ms")
    voce("Istanti verificati", report.n_samples)
    voce(
        "Errore max del campionamento",
        round(report.sampling_error_bound * 1000, 4),
        "mm (limite rigoroso)",
    )
    voce("Tempo di calcolo", round(solution.raw.get("wall_time", 0.0), 2), "s")
    passo = data.clearance_step_mm
    richiesta = data.hoist_length + data.safety_distance
    voce(
        "Passo di controllo della distanza",
        round(passo, 1),
        f"mm fra una verifica e l'altra: il calcolo puo' pretendere fino a "
        f"{passo / richiesta * 100:.0f}% in piu' della distanza richiesta "
        f"(non e' un margine di sicurezza)"
        if richiesta > 0
        else "mm fra una verifica e l'altra",
        "0.0",
    )
    voce("Risoluzione temporale", data.time_scale, "tick al secondo")

    if cfg is not None:
        _cartello(
            wb,
            "Output",
            _COLORE_REFERTO,
            "I fogli che seguono sono il RISULTATO del calcolo: si leggono e si "
            "consegnano. Riaprendo il file, 'Apri linea...' non li guarda.",
            da=inizio_referto,
        )
    # Si apre sul Riepilogo, che e' quello che si va a leggere -- non sul
    # primo foglio, che adesso e' il cartello dell'ingresso.
    wb.active = wb.sheetnames.index("Riepilogo")

    wb.save(percorso_file)
    return percorso_file


if __name__ == "__main__":
    destinazione = sys.argv[1] if len(sys.argv) > 1 else "linea.xlsx"
    scrivi_modello(destinazione)
    print(f"File modello scritto in {destinazione}")
    print("Compilalo e poi lancia la risoluzione.")
