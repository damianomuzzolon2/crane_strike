"""
test_excel_io.py
----------------
Test della lettura del file Excel. Non richiede OR-Tools (non risolve nulla),
ma richiede openpyxl.

L'attenzione e' quasi tutta sugli ERRORI di compilazione: un file di input
riempito a mano sbaglia spesso, e il messaggio deve dire foglio, cella e cosa
c'e' che non va -- altrimenti il file Excel diventa piu' scomodo del codice
che sostituisce.

Per eseguirlo:
    python test/test_excel_io.py
"""

from __future__ import annotations

import os
import sys
import tempfile

# I moduli del programma stanno nella cartella sopra questa: senza aggiungerla
# fra i percorsi di ricerca, lanciare il test da qui non li troverebbe.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from excel_io import (
    FOGLIO_PARAMETRI,
    FOGLIO_PERCORSO,
    FOGLIO_VASCHE,
    FOGLIO_ZONE,
    FOGLIO_CAMBIO_QUOTA,
    leggi_problema,
    scrivi_modello,
)

_n_pass = 0
_n_fail = 0


def check(condition: bool, description: str):
    global _n_pass, _n_fail
    if condition:
        _n_pass += 1
        print(f"  ok   {description}")
    else:
        _n_fail += 1
        print(f"  FAIL {description}")


def modello_temporaneo() -> str:
    fd, percorso = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    scrivi_modello(percorso)
    return percorso


def modifica(percorso: str, foglio: str, cella: str, valore):
    from openpyxl import load_workbook

    wb = load_workbook(percorso)
    wb[foglio][cella] = valore
    wb.save(percorso)


def valore(percorso: str, foglio: str, cella: str):
    """Il contenuto grezzo di una cella, per controllare COME una cosa e'
    scritta e non solo che si rilegga."""
    from openpyxl import load_workbook

    return load_workbook(percorso)[foglio][cella].value


def cella_ciclogramma(percorso: str, titolo: str, mossa: int) -> str:
    """L'indirizzo della cella del foglio Ciclogramma che tiene `titolo` per la
    mossa data, cercando la colonna per NOME nella riga dei titoli.

    I test non devono sapere a che lettera sta una colonna. Quando il tempo
    teorico e' finito in mezzo alla tabella -- accanto al tempo vero, che e'
    l'unico posto in cui serve -- le prove scritte con 'F5' hanno smesso di
    puntare a quello che intendevano, e una di loro ha continuato a passare
    controllando una cella che il programma non legge nemmeno."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    from excel_io import (
        FOGLIO_CICLOGRAMMA,
        _PRIMA_RIGA_CICLOGRAMMA,
        _RIGA_TITOLI_CICLOGRAMMA,
    )

    ws = load_workbook(percorso)[FOGLIO_CICLOGRAMMA]
    for col in range(1, ws.max_column + 1):
        if _testo_cella(ws.cell(_RIGA_TITOLI_CICLOGRAMMA, col).value) == titolo:
            return f"{get_column_letter(col)}{_PRIMA_RIGA_CICLOGRAMMA + mossa}"
    raise AssertionError(f"colonna '{titolo}' non trovata nel foglio Ciclogramma")


def _testo_cella(valore) -> str:
    return "" if valore is None else str(valore).strip()


def errore_leggendo(percorso: str) -> str:
    """Restituisce il messaggio d'errore, o '' se il file e' valido."""
    try:
        leggi_problema(percorso)
        return ""
    except ValueError as e:
        return str(e)


# --------------------------------------------------------------------------


def test_andata_e_ritorno():
    print("\n[1] il file modello si rilegge e riproduce la linea di esempio")
    p = modello_temporaneo()
    try:
        cfg = leggi_problema(p)
        d = cfg.data
        check(len(d.tanks) == 7 and d.n_stations == 7, "7 vasche e 7 stazioni")
        check(d.tanks["ZINCATURA"].capacity == 2, "ZINCATURA a 2 posti")
        check(
            (d.takt_nominale, d.takt_delta_neg, d.takt_delta_pos)
            == (130.0, 20.0, 20.0),
            "takt time 130 s teorici con 20 s di tolleranza per parte",
        )
        check(
            (d.takt_min, d.takt_max) == (110.0, 150.0),
            "e la banda che ne esce e' 110-150 s",
        )
        check(
            (d.kin_empty.v_max, d.kin_loaded.a_max) == (1600, 400),
            "cinematiche vuoto e carico",
        )
        check(
            (d.engage_time, d.disengage_time) == (2.0, 1.0),
            "tempi di aggancio/sgancio",
        )
        check(
            (d.kin_lift_empty.v_max, d.kin_lift_loaded.a_max) == (500, 500),
            "cinematiche di sollevamento",
        )
        # Corsa e sgocciolamento sono di ogni vasca e obbligatori: nessun
        # valore generale da cui ereditare, e nessun None possibile.
        check(
            d.tanks["ZINCATURA"].lift_height == 1100
            and d.tanks["SGRASSO"].lift_height == 800
            and d.tanks["CARICO"].lift_height == 0,
            "corsa verticale dichiarata vasca per vasca",
        )
        check(
            d.tanks["ZINCATURA"].drain_time == 8
            and d.tanks["SGRASSO"].drain_time == 2
            and d.tanks["CARICO"].drain_time == 0,
            "sgocciolamento dichiarato vasca per vasca",
        )
        check(
            d.pick_time_at(3) > d.pick_time_at(1),
            f"la vasca piu' profonda ha presa piu' lunga "
            f"({d.pick_time_at(3):.2f} s contro {d.pick_time_at(1):.2f} s)",
        )
        check(d.zones is None, "foglio Zone vuoto -> scelta automatica")
        check(
            (cfg.max_carroponti, cfg.tempo_limite_s) == (4, 15.0),
            "opzioni di risoluzione",
        )
    finally:
        os.unlink(p)


def _senza_colonne(percorso: str, titoli) -> str:
    """Una copia del file con quelle colonne del foglio Ciclogramma TOLTE, come
    sarebbe stato scritto prima che esistessero. Restituisce il nuovo percorso.
    """
    from openpyxl import load_workbook

    from excel_io import FOGLIO_CICLOGRAMMA, _RIGA_TITOLI_CICLOGRAMMA

    wb = load_workbook(percorso)
    ws = wb[FOGLIO_CICLOGRAMMA]
    da_togliere = sorted(
        (
            col
            for col in range(1, ws.max_column + 1)
            if _testo_cella(ws.cell(_RIGA_TITOLI_CICLOGRAMMA, col).value) in titoli
        ),
        reverse=True,  # dall'ultima, se no le altre si spostano sotto i piedi
    )
    for col in da_togliere:
        ws.delete_cols(col)
    fd, fuori = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    wb.save(fuori)
    return fuori


def _senza_titoli(percorso: str) -> str:
    """Una copia del file con la riga dei titoli del foglio Ciclogramma
    svuotata: e' il caso di chi ha ripulito il foglio a mano."""
    from openpyxl import load_workbook

    from excel_io import FOGLIO_CICLOGRAMMA, _RIGA_TITOLI_CICLOGRAMMA

    wb = load_workbook(percorso)
    ws = wb[FOGLIO_CICLOGRAMMA]
    for col in range(1, ws.max_column + 1):
        ws.cell(_RIGA_TITOLI_CICLOGRAMMA, col).value = None
    fd, fuori = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    wb.save(fuori)
    return fuori


def test_foglio_ciclogramma():
    print("\n[1-bis] il ciclogramma va e torna dal foglio Ciclogramma")
    from excel_io import FOGLIO_CICLOGRAMMA, scrivi_linea
    from model import SostaIntermedia

    p = modello_temporaneo()
    try:
        cfg = leggi_problema(p)
        check(
            cfg.ciclogramma is None,
            "il modello d'esempio descrive la linea e basta: nessun ciclogramma",
        )
        # Assegnazione volutamente INCOMPLETA: e' il lavoro interrotto quello
        # che non si vuole rifare, non solo quello finito.
        ciclo = {
            "T": 123.45,
            "n_carroponti": 3,
            "permanenze": {1: 70.0, 2: 40.0, 3: 215.0, 4: 20.0, 5: 30.0},
            "assegnazione": {0: 0, 1: 0, 2: 0, 3: 1, 5: 1},
            # chi non dichiara dove far sostare i carri se lo ritrova a None,
            # cioe' "decidi tu": e' come si comportano i file scritti prima
            # che la colonna esistesse
            "attese": None,
            # le soste in una vasca in mezzo invece sono l'eccezione: vuoto
            # vuol dire "nessuna", non "decidi tu", perche' nessuna regola le
            # inventa
            "soste": {},
        }
        fd, con_ciclo = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            scrivi_linea(con_ciclo, cfg, ciclo)
            riletto = leggi_problema(con_ciclo)
            check(
                riletto.ciclogramma == ciclo,
                "takt, carroponti, tempi in vasca e assegnazione tornano identici",
            )
            check(
                4 not in riletto.ciclogramma["assegnazione"],
                "e la mossa lasciata senza carroponte resta senza",
            )
            # La linea deve tornare identica anche lei: scrivere il ciclogramma
            # non deve alterare la descrizione dell'impianto.
            check(
                riletto.data == cfg.data
                and riletto.max_carroponti == cfg.max_carroponti
                and riletto.tempo_limite_s == cfg.tempo_limite_s,
                "e la linea riscritta e' identica all'originale",
            )
            # Le soste non sono una conseguenza delle fasi: se non tornassero
            # indietro identiche, il ciclogramma riaperto sarebbe una
            # traiettoria diversa da quella che era stata verificata.
            con_soste = dict(ciclo, attese={0: 0.0, 1: 12.5, 2: 3.25, 3: 40.0})
            scrivi_linea(con_ciclo, cfg, con_soste)
            check(
                leggi_problema(con_ciclo).ciclogramma == con_soste,
                "anche le soste dopo la consegna vanno e tornano identiche",
            )
            # zero non e' "non so": vuol dire riparti subito, ed e' una scelta
            check(
                leggi_problema(con_ciclo).ciclogramma["attese"][0] == 0.0,
                "una sosta di zero secondi resta zero, non diventa 'non detto'",
            )
            attesa_0 = cella_ciclogramma(
                con_ciclo, "attesa_dopo_consegna_s", 0
            )
            modifica(con_ciclo, FOGLIO_CICLOGRAMMA, attesa_0, -3.0)
            msg = errore_leggendo(con_ciclo)
            check(
                f"{FOGLIO_CICLOGRAMMA}!{attesa_0}" in msg and "negativa" in msg,
                f"una sosta negativa viene respinta: \"{msg.splitlines()[-1][:60]}\"",
            )
            scrivi_linea(con_ciclo, cfg, ciclo)

            # La SOSTA IN UNA VASCA IN MEZZO: cambia il percorso, non solo i
            # tempi, e va e torna come gli altri gradi di liberta'. Si scrive
            # col nome della vasca, perche' e' quello che si legge senza
            # contare le righe del foglio Percorso.
            in_mezzo = dict(
                ciclo,
                attese={0: 0.0, 1: 5.0},
                soste={1: SostaIntermedia(stazione=2, secondi=8.25)},
            )
            scrivi_linea(con_ciclo, cfg, in_mezzo)
            riletto = leggi_problema(con_ciclo).ciclogramma
            check(
                riletto == in_mezzo,
                "la sosta in una vasca in mezzo va e torna identica "
                f"({riletto['soste']})",
            )
            vasca = cfg.data.route[2].tank_id
            dove_vasca = cella_ciclogramma(con_ciclo, "sosta_in_vasca", 1)
            dove_secondi = cella_ciclogramma(con_ciclo, "sosta_s", 1)
            check(
                valore(con_ciclo, FOGLIO_CICLOGRAMMA, dove_vasca) == vasca,
                f"e sul foglio si legge il NOME della vasca ('{vasca}'), "
                f"non il numero della tappa",
            )
            # Mezza sosta non e' una sosta: dire dove senza dire per quanto (o
            # viceversa) e' un dato incompleto, e passarlo in silenzio vorrebbe
            # dire disegnare un rientro che nessuno ha chiesto.
            modifica(con_ciclo, FOGLIO_CICLOGRAMMA, dove_secondi, None)
            msg = errore_leggendo(con_ciclo)
            check(
                f"{FOGLIO_CICLOGRAMMA}!{dove_vasca}" in msg and "entrambe" in msg,
                f"una sosta a meta' viene respinta: \"{msg.splitlines()[-1][:60]}\"",
            )
            scrivi_linea(con_ciclo, cfg, in_mezzo)
            # Una vasca fuori dal percorso non e' un posto dove sostare.
            modifica(con_ciclo, FOGLIO_CICLOGRAMMA, dove_vasca, "NON_ESISTE")
            msg = errore_leggendo(con_ciclo)
            check(
                f"{FOGLIO_CICLOGRAMMA}!{dove_vasca}" in msg and "percorso" in msg,
                f"una vasca inesistente viene respinta: "
                f"\"{msg.splitlines()[-1][:60]}\"",
            )
            scrivi_linea(con_ciclo, cfg, ciclo)

            # Un foglio rotto non deve passare in silenzio: senza takt time il
            # ciclogramma non si ricostruisce, e ripartire da zero senza dirlo
            # sarebbe il modo peggiore di perdere il lavoro di ieri.
            modifica(con_ciclo, FOGLIO_CICLOGRAMMA, "B1", None)
            msg = errore_leggendo(con_ciclo)
            check(
                f"{FOGLIO_CICLOGRAMMA}!B1" in msg and "takt time" in msg,
                f"un foglio senza takt time viene segnalato: \"{msg.splitlines()[-1][:60]}\"",
            )

            # -- il tempo TEORICO accanto a quello vero --------------------
            # Serve a vedere a colpo d'occhio di quanto il ciclogramma si e'
            # allontanato dalla ricetta. Non e' un grado di liberta': lo detta
            # il foglio Percorso, e questo foglio lo ricopia soltanto.
            scrivi_linea(con_ciclo, cfg, ciclo)
            teorici, scarti = True, True
            for k in range(cfg.data.n_moves):
                letto = valore(
                    con_ciclo,
                    FOGLIO_CICLOGRAMMA,
                    cella_ciclogramma(con_ciclo, "tempo_teorico_s", k),
                )
                atteso = None if k == 0 else cfg.data.route[k].nominale
                if atteso is None:
                    if letto is not None:
                        teorici = False
                elif letto is None or abs(letto - atteso) > 1e-9:
                    teorici = False
                formula = valore(
                    con_ciclo,
                    FOGLIO_CICLOGRAMMA,
                    cella_ciclogramma(con_ciclo, "scarto_s", k),
                )
                if k == 0:
                    if formula is not None:
                        scarti = False
                else:
                    vero = cella_ciclogramma(con_ciclo, "tempo_in_vasca_s", k)
                    teo = cella_ciclogramma(con_ciclo, "tempo_teorico_s", k)
                    if formula != f"={vero}-{teo}":
                        scarti = False
            check(
                teorici,
                "il tempo teorico e' quello della vasca DA CUI parte il "
                "trasporto, e alla mossa 0 -- il carico -- non c'e'",
            )
            check(
                scarti,
                "lo scarto e' una FORMULA fra le due celle, cosi' si aggiorna "
                "ritoccando il tempo in vasca dentro Excel",
            )

            # Le due colonne non si rileggono: il teorico ha una sola fonte, e
            # un valore scritto a mano qui dentro non deve poterla contraddire.
            prima = leggi_problema(con_ciclo)
            modifica(
                con_ciclo,
                FOGLIO_CICLOGRAMMA,
                cella_ciclogramma(con_ciclo, "tempo_teorico_s", 1),
                999.0,
            )
            dopo = leggi_problema(con_ciclo)
            check(
                dopo.ciclogramma == prima.ciclogramma
                and dopo.data == prima.data,
                "il tempo teorico scritto a mano nel foglio Ciclogramma viene "
                "ignorato: lo dice il foglio Percorso",
            )

            # -- le colonne si cercano per NOME ----------------------------
            # Un file scritto prima che il teorico esistesse ha otto colonne, e
            # la sosta sta in G/H invece che in I/J. Leggerlo contando le
            # posizioni vorrebbe dire prendere lo scarto per l'attesa.
            scrivi_linea(con_ciclo, cfg, in_mezzo)
            vecchio = _senza_colonne(
                con_ciclo, ("tempo_teorico_s", "scarto_s")
            )
            try:
                check(
                    leggi_problema(vecchio).ciclogramma == in_mezzo,
                    "un file col vecchio ordine di colonne si rilegge identico",
                )
                # Cancellata la riga dei titoli non resta nome da cercare, e
                # l'unico ordine noto senza leggerlo e' quello storico.
                senza_titoli = _senza_titoli(vecchio)
                try:
                    check(
                        leggi_problema(senza_titoli).ciclogramma == in_mezzo,
                        "e anche uno a cui e' stata cancellata la riga dei "
                        "titoli, ricadendo sull'ordine storico",
                    )
                finally:
                    os.unlink(senza_titoli)
            finally:
                os.unlink(vecchio)
        finally:
            if os.path.exists(con_ciclo):
                os.unlink(con_ciclo)
    finally:
        os.unlink(p)


def test_valori_mancanti_e_sbagliati():
    print("\n[2] valori mancanti o non numerici")
    casi = [
        (FOGLIO_VASCHE, "B3", None, "Vasche!B3", "posizione mancante"),
        (FOGLIO_VASCHE, "B3", "due metri", "Vasche!B3", "posizione non numerica"),
        (FOGLIO_VASCHE, "C3", 2.5, "Vasche!C3", "posti non intero"),
        (FOGLIO_PERCORSO, "C3", None, "Percorso!C3", "permanenza teorica mancante"),
        (FOGLIO_PERCORSO, "D3", None, "Percorso!D3", "delta negativo mancante"),
        (FOGLIO_PERCORSO, "E3", None, "Percorso!E3", "delta positivo mancante"),
        (FOGLIO_PARAMETRI, "B2", "abc", "Parametri!B2", "parametro non numerico"),
    ]
    for foglio, cella, valore, atteso, descrizione in casi:
        p = modello_temporaneo()
        try:
            modifica(p, foglio, cella, valore)
            msg = errore_leggendo(p)
            check(atteso in msg, f"{descrizione}: segnalato in {atteso}")
        finally:
            os.unlink(p)


def test_corsa_e_scolo_obbligatori():
    print("\n[2-bis] corsa verticale e sgocciolamento: uno per vasca, obbligatori")
    # Sono proprieta' della vasca, e non esiste piu' un valore generale da cui
    # ereditare. Una cella vuota deve essere un errore: se passasse per "usa il
    # default" si calcolerebbe con un numero che nessuno ha scelto per quella
    # vasca, e nessuno se ne accorgerebbe.
    for cella, atteso in (("D5", "corsa verticale"), ("E5", "sgocciolamento")):
        p = modello_temporaneo()
        try:
            modifica(p, FOGLIO_VASCHE, cella, None)
            msg = errore_leggendo(p)
            check(
                f"Vasche!{cella}" in msg and atteso in msg,
                f"{atteso} lasciato vuoto: segnalato in Vasche!{cella}",
            )
        finally:
            os.unlink(p)

    # e i due parametri "generali" non esistono piu': chi li ha nel file
    # vecchio deve sentirsi dire dove sono finiti, non "non riconosciuto"
    for vecchio, dove in (
        ("altezza_sollevamento_mm", "corsa_verticale_mm"),
        ("tempo_sgocciolamento_s", "sgocciolamento_s"),
    ):
        p = modello_temporaneo()
        try:
            modifica(p, FOGLIO_PARAMETRI, "A20", vecchio)
            msg = errore_leggendo(p)
            check(
                dove in msg and FOGLIO_VASCHE in msg,
                f"'{vecchio}' nei Parametri: rimanda a {dove} nel foglio Vasche",
            )
        finally:
            os.unlink(p)


def test_virgola_decimale():
    print("\n[3] numeri scritti con la virgola decimale")
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_VASCHE, "B3", "2500,5")
        modifica(p, FOGLIO_PARAMETRI, "B5", "1650,5")
        cfg = leggi_problema(p)
        check(cfg.data.tanks["SGRASSO"].position == 2500.5, "'2500,5' letto come 2500.5")
        check(
            cfg.data.kin_empty.v_max == 1650.5,
            "'1650,5' letto come 1650.5 (B5 e' v_max_vuoto_mm_s)",
        )
    finally:
        os.unlink(p)


def test_file_in_metri():
    print("\n[3b] un file della versione in metri viene riconosciuto")
    # E' il caso pericoloso: le colonne si leggono per posizione, non per
    # intestazione, quindi una posizione di 9.5 verrebbe presa per 9.5 mm.
    # Deve fermarsi, e deve dire perche' -- non sommergere di "parametro non
    # riconosciuto" senza mai nominare l'unita'.
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_PARAMETRI, "A4", "v_max_vuoto_m_s")
        modifica(p, FOGLIO_PARAMETRI, "A8", "ingombro_lato_positivo_m")
        msg = errore_leggendo(p)
        check("METRI" in msg and "MILLIMETRI" in msg, "l'unita' viene nominata")
        check(
            "v_max_vuoto_mm_s" in msg and "1000" in msg,
            "dice come si chiama adesso e che va moltiplicato per 1000",
        )
        check(
            msg.count("versione in METRI") == 2,
            "segnala tutti i parametri vecchi, non solo il primo",
        )
    finally:
        os.unlink(p)


def test_parametro_sostituito():
    print("\n[3c] un parametro rinominato cambiando significato")
    # 'passi_fascia_sicurezza' diceva la stessa cosa contando i gradini.
    # Cadere nel generico "non riconosciuto" farebbe ricopiare il 6 sotto il
    # nome nuovo, cioe' un controllo ogni 6 mm: trecento volte piu' fitto del
    # voluto, e un modello ingestibile.
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_PARAMETRI, "A20", "passi_fascia_sicurezza")
        msg = errore_leggendo(p)
        check(
            "passo_controllo_distanza_mm" in msg,
            "indica il parametro che lo sostituisce",
        )
        check("si converte" in msg.lower(), "e dice come si converte il valore")
    finally:
        os.unlink(p)


def test_takt_teorico_e_tolleranze():
    print("\n[3d] il takt time si dichiara come le permanenze: teorico + delta")
    # E' la stessa forma del foglio Percorso, e per lo stesso motivo: quello
    # che il cliente dichiara e' il ciclo a cui la linea e' pensata, non i due
    # estremi di una banda. Le soglie su cui lavora il modello sono derivate,
    # e il file riscritto deve tornare a dire il teorico, non il centro.
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_PARAMETRI, "B2", 120)
        modifica(p, FOGLIO_PARAMETRI, "B3", 10)
        modifica(p, FOGLIO_PARAMETRI, "B4", 30)
        d = leggi_problema(p).data
        check(
            (d.takt_min, d.takt_max) == (110.0, 150.0),
            "teorico 120 con -10/+30 -> banda 110-150 s",
        )
        check(d.takt_nominale == 120.0, "e il teorico resta 120, non il centro (130)")

        # I delta sono AMPIEZZE: scritti col segno meno darebbero una banda
        # rovesciata senza dirlo, quindi vanno respinti nominando la cella.
        modifica(p, FOGLIO_PARAMETRI, "B4", -30)
        msg = errore_leggendo(p)
        check(
            "Parametri!B4" in msg and "ampiezze" in msg,
            "un delta col segno meno viene respinto",
        )

        # Delta a zero = takt time rigido: e' lecito e deve restare leggibile.
        modifica(p, FOGLIO_PARAMETRI, "B3", 0)
        modifica(p, FOGLIO_PARAMETRI, "B4", 0)
        d = leggi_problema(p).data
        check(
            (d.takt_min, d.takt_max, d.takt_nominale) == (120.0, 120.0, 120.0),
            "delta a zero: takt time rigido a 120 s",
        )
    finally:
        os.unlink(p)

    # I nomi vecchi dicevano gli estremi: intercettati con il modo di convertirli
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_PARAMETRI, "A2", "takt_min_s")
        modifica(p, FOGLIO_PARAMETRI, "A3", "takt_max_s")
        msg = errore_leggendo(p)
        check(
            "takt_teorico_s" in msg and "non esistono piu'" in msg,
            "'takt_min_s' e 'takt_max_s' rimandano ai nomi nuovi",
        )
        check("si converte" in msg.lower(), "e il messaggio dice come si converte")
    finally:
        os.unlink(p)


def test_vasca_inesistente():
    print("\n[4] il percorso cita una vasca non definita")
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_PERCORSO, "B3", "SGRASSAGGIO")
        msg = errore_leggendo(p)
        check("Percorso!B3" in msg and "SGRASSAGGIO" in msg, "segnalata la cella")
        check(FOGLIO_VASCHE in msg, "il messaggio dice dove definirla")
    finally:
        os.unlink(p)


def test_vasca_duplicata():
    print("\n[5] due vasche con lo stesso id")
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_VASCHE, "A4", "SGRASSO")
        msg = errore_leggendo(p)
        check("duplicata" in msg and "Vasche!A4" in msg, "duplicato segnalato")
    finally:
        os.unlink(p)


def test_percorso_riordinato():
    print("\n[6] foglio Percorso riordinato per sbaglio")
    p = modello_temporaneo()
    try:
        # la colonna n non torna piu': segnale che le righe sono state mosse
        modifica(p, FOGLIO_PERCORSO, "A3", 5)
        msg = errore_leggendo(p)
        check(
            "Percorso!A3" in msg and "ordinato" in msg,
            "numerazione incoerente intercettata",
        )
    finally:
        os.unlink(p)


def test_parametro_sconosciuto():
    print("\n[7] parametro con il nome sbagliato")
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_PARAMETRI, "A2", "takt_minimo")
        msg = errore_leggendo(p)
        check("non riconosciuto" in msg, "nome non riconosciuto segnalato")
        check("takt_teorico_s" in msg, "il messaggio elenca i nomi ammessi")
        check("obbligatorio" in msg, "e segnala che ne manca uno obbligatorio")
    finally:
        os.unlink(p)


def test_parametro_facoltativo_vuoto():
    print("\n[8] parametri facoltativi lasciati vuoti")
    p = modello_temporaneo()
    try:
        from openpyxl import load_workbook

        wb = load_workbook(p)
        ws = wb[FOGLIO_PARAMETRI]
        for riga in range(2, ws.max_row + 1):
            if ws.cell(riga, 1).value in (
                "tempo_aggancio_s",
                "risoluzione_tick_per_s",
                "max_carroponti",
            ):
                ws.cell(riga, 2).value = None
        wb.save(p)
        cfg = leggi_problema(p)
        check(cfg.data.engage_time == 0.0, "tempo_aggancio_s -> default 0")
        check(cfg.data.time_scale == 100, "risoluzione_tick_per_s -> default 100")
        check(cfg.max_carroponti == 6, "max_carroponti -> default 6")
    finally:
        os.unlink(p)


def test_sollevamento_incoerente():
    print("\n[8-bis] corsa verticale senza cinematica di sollevamento")
    p = modello_temporaneo()
    try:
        from openpyxl import load_workbook

        wb = load_workbook(p)
        ws = wb[FOGLIO_PARAMETRI]
        for riga in range(2, ws.max_row + 1):
            if str(ws.cell(riga, 1).value or "").startswith("v_max_sollevamento_carico"):
                ws.cell(riga, 2).value = None
        wb.save(p)
        msg = errore_leggendo(p)
        check(
            "kin_lift_loaded" in msg,
            "corsa dichiarata ma manca il sollevamento a carico: segnalato",
        )
    finally:
        os.unlink(p)

    # Il sollevamento a VUOTO invece non serve: col gancio che trasla basso --
    # lo standard -- quelle corse non le fa nessuno, e pretendere il dato
    # sarebbe chiedere un numero per non usarlo.
    p = modello_temporaneo()
    try:
        from openpyxl import load_workbook

        wb = load_workbook(p)
        ws = wb[FOGLIO_PARAMETRI]
        for riga in range(2, ws.max_row + 1):
            if str(ws.cell(riga, 1).value or "").startswith(
                ("v_max_sollevamento_vuoto", "a_max_sollevamento_vuoto")
            ):
                ws.cell(riga, 2).value = None
        wb.save(p)
        cfg = leggi_problema(p)
        check(
            cfg.data.empty_lift_seconds(1, scendendo=True) == 0.0,
            "senza sollevamento a vuoto la linea si legge lo stesso",
        )
        # ...ma dichiarando una vasca OSTACOLO il gancio deve salire e
        # riscendere sugli svincoli, e allora la cinematica serve
        wb = load_workbook(p)
        ws = wb[FOGLIO_VASCHE]
        for riga in range(2, ws.max_row + 1):
            nome, pos = ws.cell(riga, 1).value, ws.cell(riga, 2).value
            if not nome:
                continue
            ws.cell(riga, 6).value = pos - 900 if pos > 0 else None
            ws.cell(riga, 7).value = pos + 900 if pos < 20000 else None
            if nome == "ZINCATURA":
                ws.cell(riga, 8).value = 0
        wb.save(p)
        msg = errore_leggendo(p)
        check(
            "ZINCATURA" in msg and "kin_lift_empty" in msg,
            f"e li' invece viene chiesto: \"{msg.splitlines()[-1][:70]}...\"",
        )
    finally:
        os.unlink(p)

    # con corsa 0 la cinematica non serve, e i tempi verticali sono nulli
    p = modello_temporaneo()
    try:
        from openpyxl import load_workbook

        wb = load_workbook(p)
        ws = wb[FOGLIO_PARAMETRI]
        for riga in range(2, ws.max_row + 1):
            nome = str(ws.cell(riga, 1).value or "")
            if nome.startswith(("v_max_sollevamento", "a_max_sollevamento")):
                ws.cell(riga, 2).value = None
        # corsa a zero su OGNI vasca: e' una dichiarazione, non una cella
        # lasciata vuota -- quelle adesso sono un errore
        ws2 = wb[FOGLIO_VASCHE]
        for riga in range(2, ws2.max_row + 1):
            if _testo_cella(ws2.cell(riga, 1).value):
                ws2.cell(riga, 4).value = 0
        wb.save(p)
        cfg = leggi_problema(p)
        # niente corsa = nessun moto verticale, ma aggancio e sgancio restano:
        # sono tempi morti, non dipendono da quanto e' lunga la corsa
        check(
            cfg.data.kin_lift_empty is None and cfg.data.kin_lift_loaded is None,
            "corsa nulla: la cinematica di sollevamento non e' richiesta",
        )
        check(
            cfg.data.pick_time_at(1)
            == cfg.data.engage_time + cfg.data.drain_time_at(1)
            and cfg.data.release_time_at(1) == cfg.data.disengage_time,
            f"restano solo i tempi morti: presa {cfg.data.pick_time_at(1)} s "
            f"(aggancio + sgocciolamento), rilascio "
            f"{cfg.data.release_time_at(1)} s (sgancio)",
        )
    finally:
        os.unlink(p)


def test_portate():
    print("\n[9] portate dei carroponti (foglio Zone)")
    from excel_io import scrivi_linea

    p = modello_temporaneo()
    try:
        # sovrapposte su RISCIACQUO_1 e ZINCATURA, e la seconda scritta al
        # contrario: l'ordine delle due vasche non conta
        modifica(p, FOGLIO_ZONE, "A2", "CARICO")
        modifica(p, FOGLIO_ZONE, "B2", "ZINCATURA")
        modifica(p, FOGLIO_ZONE, "A3", "SCARICO")
        modifica(p, FOGLIO_ZONE, "B3", "RISCIACQUO_1")
        cfg = leggi_problema(p)
        d = cfg.data
        check(
            d.portate is not None
            and [(x.vasca_min, x.vasca_max) for x in d.portate]
            == [("CARICO", "ZINCATURA"), ("SCARICO", "RISCIACQUO_1")],
            "portate lette correttamente, anche sovrapposte",
        )
        check(d.zones is None, "le zone restano da scegliere al solutore")
        check(
            d.portata_mm(1) == (5500.0, 20000.0),
            f"il tratto non dipende dall'ordine delle due vasche: {d.portata_mm(1)}",
        )
        check(
            d.raggiunge(0, 3) and not d.raggiunge(0, 4) and d.raggiunge(1, 2),
            "il carroponte 1 arriva fino a ZINCATURA e non oltre; il 2 parte "
            "da RISCIACQUO_1",
        )

        # riscritta, la linea porta con se' le portate
        fd, copia = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            scrivi_linea(copia, cfg)
            check(
                leggi_problema(copia).data.portate == d.portate,
                "riscrivendo la linea le portate si conservano",
            )
        finally:
            os.unlink(copia)
    finally:
        os.unlink(p)

    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_ZONE, "A2", "CARICO")
        modifica(p, FOGLIO_ZONE, "B2", "INESISTENTE")
        modifica(p, FOGLIO_ZONE, "A3", "ZINCATURA")  # manca la massima
        msg = errore_leggendo(p)
        check(
            "INESISTENTE" in msg and f"{FOGLIO_ZONE}!B2" in msg,
            "vasca sconosciuta rilevata, con la cella",
        )
        check(
            f"{FOGLIO_ZONE}!B3" in msg and "mancante" in msg,
            "vasca massima mancante rilevata, con la cella",
        )
    finally:
        os.unlink(p)


def test_errori_multipli():
    print("\n[10] piu' errori insieme, riportati tutti in una volta")
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_VASCHE, "B3", None)
        modifica(p, FOGLIO_PERCORSO, "C4", "venti")
        modifica(p, FOGLIO_PARAMETRI, "B3", None)
        msg = errore_leggendo(p)
        check(
            all(x in msg for x in ("Vasche!B3", "Percorso!C4", "Parametri!B3")),
            "tutti e tre gli errori nello stesso messaggio",
        )
    finally:
        os.unlink(p)


def test_foglio_mancante():
    print("\n[11] foglio obbligatorio assente")
    p = modello_temporaneo()
    try:
        from openpyxl import load_workbook

        wb = load_workbook(p)
        del wb[FOGLIO_PARAMETRI]
        wb.save(p)
        msg = errore_leggendo(p)
        check("foglio mancante" in msg and FOGLIO_PARAMETRI in msg, "assenza rilevata")
    finally:
        os.unlink(p)


def test_dati_incoerenti():
    print("\n[12] dati validi come numeri ma incoerenti fra loro")
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_PARAMETRI, "B3", 200)  # delta negativo > teorico
        msg = errore_leggendo(p)
        check(
            "Parametri!B3" in msg and "non minore del takt time teorico" in msg,
            "delta negativo oltre il teorico, riportato con la cella",
        )
    finally:
        os.unlink(p)

    p = modello_temporaneo()
    try:
        # ZINCATURA a 1 posto non regge una permanenza di 180 s con takt 150 s
        modifica(p, FOGLIO_VASCHE, "C5", 1)
        msg = errore_leggendo(p)
        check("occupa un posto per almeno" in msg, "capienza insufficiente riportata")
    finally:
        os.unlink(p)


# --------------------------------------------------------------------------
# Scrittura dei risultati
# --------------------------------------------------------------------------


def _risultati_su_file():
    """Scrive i risultati di una soluzione costruita a mano (nessun CP-SAT) e
    restituisce (percorso, data, solution, report, workbook)."""
    from openpyxl import load_workbook

    # riusa il caso di riferimento gia' costruito per i test del verificatore
    from test_verify import reference_case
    from verify import verify_solution

    from excel_io import scrivi_risultati

    data, solution = reference_case()
    report = verify_solution(data, solution)
    fd, percorso = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    scrivi_risultati(percorso, data, solution, report, sorgente="prova.xlsx")
    return percorso, data, solution, report, load_workbook(percorso)


def test_risultati_struttura():
    print("\n[13] il file dei risultati ha i fogli attesi")
    percorso, data, solution, report, wb = _risultati_su_file()
    try:
        check(
            wb.sheetnames
            == ["Riepilogo", "Movimenti", "SequenzaCarri", "TempiVerticali", "FlussoPezzo", "Verifica"],
            f"fogli: {wb.sheetnames}",
        )
        testo = "\n".join(
            str(wb["Riepilogo"].cell(r, c).value)
            for r in range(1, wb["Riepilogo"].max_row + 1)
            for c in (1, 2, 3)
        )
        check("prova.xlsx" in testo, "il riepilogo cita il file di origine")
        check("SUPERATA" in testo, "riporta l'esito della verifica")
        ws = wb["Riepilogo"]
        valori = {
            ws.cell(r, 1).value: ws.cell(r, 2).value for r in range(1, ws.max_row + 1)
        }
        check(
            abs(float(valori.get("Takt time", 0)) - solution.T) < 0.01,
            f"riporta il takt time ({valori.get('Takt time')} s)",
        )
        check(
            abs(float(valori.get("Produttivita'", 0)) - 3600.0 / solution.T) < 0.1,
            "riporta la produttivita' in pezzi/ora",
        )
        check(valori.get("Numero di carroponti") == len(data.zones), "numero di carroponti")
    finally:
        os.unlink(percorso)


def test_risultati_utilizzo():
    print("\n[17] utilizzo dei carroponti nel riepilogo")
    percorso, data, solution, report, wb = _risultati_su_file()
    try:
        ws = wb["Riepilogo"]
        riga_int = next(
            r
            for r in range(1, ws.max_row + 1)
            if ws.cell(r, 1).value == "carroponte"
        )
        utilizzi = []
        for r in range(riga_int + 1, ws.max_row + 1):
            if not isinstance(ws.cell(r, 1).value, int):
                break
            utilizzi.append(ws.cell(r, 6).value)
        check(
            len(utilizzi) == len(data.zones),
            f"una riga per carroponte ({len(utilizzi)})",
        )
        check(
            all(0.0 < u < 1.0 for u in utilizzi),
            f"utilizzi plausibili: {[round(u, 3) for u in utilizzi]}",
        )
    finally:
        os.unlink(percorso)


def test_risultati_movimenti():
    print("\n[14] foglio Movimenti: una riga per tratto, con le vasche giuste")
    percorso, data, solution, report, wb = _risultati_su_file()
    try:
        ws = wb["Movimenti"]
        attese = sum(len(s) for s in solution.segments_per_hoist)
        righe = [
            [ws.cell(r, c).value for c in range(1, 10)]
            for r in range(2, ws.max_row + 1)
            if isinstance(ws.cell(r, 1).value, int)
        ]
        check(len(righe) == attese, f"{len(righe)} righe per {attese} tratti")

        # ogni tratto a carico deve andare da una vasca alla successiva del
        # percorso, e la somma delle durate di un carroponte deve fare T
        carichi = [r for r in righe if r[1].startswith("trasporto")]
        check(
            len(carichi) == data.n_moves,
            f"{len(carichi)} trasporti a carico per {data.n_moves} mosse",
        )
        ok_vasche = all(
            r[2] != r[3] and abs(r[8] - r[7]) > 0 for r in carichi
        )
        check(ok_vasche, "ogni trasporto collega due vasche diverse")

        for h in (1, 2):
            durata = sum(r[6] for r in righe if r[0] == h)
            check(
                abs(durata - solution.T) < 0.05,
                f"carroponte {h}: le durate sommano a {durata:.2f} s (T={solution.T})",
            )
    finally:
        os.unlink(percorso)


def test_risultati_flusso_pezzo():
    print("\n[15] foglio FlussoPezzo: una riga per stazione, permanenze coerenti")
    percorso, data, solution, report, wb = _risultati_su_file()
    try:
        ws = wb["FlussoPezzo"]
        righe = [
            [ws.cell(r, c).value for c in range(1, 13)]
            for r in range(2, ws.max_row + 1)
            if isinstance(ws.cell(r, 1).value, int)
        ]
        check(
            len(righe) == data.n_stations,
            f"{len(righe)} righe per {data.n_stations} stazioni",
        )
        for r in righe[1:-1]:
            _, vasca, _, ingresso, uscita, permanenza = r[:6]
            if abs((uscita - ingresso) - permanenza) > 0.01:
                check(False, f"{vasca}: uscita - ingresso != permanenza")
                break
            spec = next(s for s in data.route if s.tank_id == vasca)
            if not (spec.dwell_min - 0.01 <= permanenza <= spec.dwell_max + 0.01):
                check(False, f"{vasca}: permanenza {permanenza} fuori tolleranza")
                break
        else:
            check(True, "permanenze coerenti e dentro la tolleranza dichiarata")
    finally:
        os.unlink(percorso)

    # La permanenza scritta deve essere ESATTAMENTE il bagno del modello, e
    # per accorgersene serve una linea con le corse verticali vere: il caso di
    # riferimento le ha a zero, e con quelle a zero ogni definizione sbagliata
    # da' comunque il numero giusto.
    import shutil

    from excel_io import scrivi_modello, scrivi_risultati
    from model import proposta_semplice
    from verify import verify_solution

    from openpyxl import load_workbook

    cartella = tempfile.mkdtemp()
    try:
        linea = os.path.join(cartella, "linea.xlsx")
        scrivi_modello(linea)
        cfg = leggi_problema(linea)
        solution, data = proposta_semplice(cfg.data)
        risultati = os.path.join(cartella, "risultati.xlsx")
        scrivi_risultati(risultati, data, solution, verify_solution(data, solution))
        ws = load_workbook(risultati)["FlussoPezzo"]
        righe = [
            [ws.cell(r, c).value for c in range(1, 7)]
            for r in range(2, ws.max_row + 1)
            if isinstance(ws.cell(r, 1).value, int)
        ]
        at = solution.actual_time
        scarti = []
        for s_idx, vasca, _, ingresso, uscita, permanenza in righe[1:-1]:
            atteso = at[s_idx] - (
                at[s_idx - 1] + data.loaded_leg_seconds(s_idx - 1)
            )
            if abs(permanenza - atteso) > 0.01:
                scarti.append((vasca, permanenza, round(atteso, 2)))
        check(
            not scarti,
            f"la permanenza scritta e' il bagno del modello, corse verticali "
            f"comprese ({scarti if scarti else 'tutte e ' + str(len(righe) - 2)})",
        )
        # Il controllo di sopra passerebbe anche sommando zero due volte: qui
        # si accerta che le corse a vuoto ci siano davvero, cioe' che
        # sommarle una seconda volta -- com'era -- si vedrebbe.
        a_vuoto = data.empty_lift_seconds(1, scendendo=False)
        check(
            a_vuoto > 1.0,
            f"e su questa linea una corsa a vuoto dura {a_vuoto:.2f} s: "
            f"contarla due volte non passerebbe inosservato",
        )
    finally:
        shutil.rmtree(cartella, ignore_errors=True)


def test_risultati_scarto_pesato():
    print("\n[15-bis] scarto pesato dai teorici nel Riepilogo e in FlussoPezzo")
    percorso, data, solution, report, wb = _risultati_su_file()
    try:
        ws = wb["FlussoPezzo"]
        titoli = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        col = {t: i + 1 for i, t in enumerate(titoli)}
        check(
            all(
                t in col
                for t in ("scarto [s]", "peso sotto", "peso sopra", "scarto pesato")
            ),
            "FlussoPezzo ha scarto, pesi e scarto pesato",
        )
        righe = [
            r
            for r in range(2, ws.max_row + 1)
            if isinstance(ws.cell(r, 1).value, int)
            and isinstance(ws.cell(r, col["scarto pesato"]).value, (int, float))
        ]
        somma = sum(ws.cell(r, col["scarto pesato"]).value for r in righe)
        coerenti = all(
            abs(
                ws.cell(r, col["scarto [s]"]).value
                - (
                    ws.cell(r, col["permanenza [s]"]).value
                    - ws.cell(r, col["teorico [s]"]).value
                )
            )
            < 0.02
            for r in righe
        )
        check(coerenti, "scarto = permanenza - teorico su ogni riga")
        ws = wb["Riepilogo"]
        valori = {
            ws.cell(r, 1).value: ws.cell(r, 2).value for r in range(1, ws.max_row + 1)
        }
        check(
            valori.get("Obiettivo del calcolo")
            == "takt time minimo, poi scarto minimo",
            "il Riepilogo dice l'obiettivo del calcolo",
        )
        totale = valori.get("Scarto pesato dai teorici")
        check(
            totale is not None and abs(totale - somma) < 0.05,
            f"e lo scarto pesato totale ({totale}) e' la somma delle righe "
            f"({somma:.2f})",
        )
    finally:
        os.unlink(percorso)


def test_risultati_verifica():
    print("\n[16] foglio Verifica: elenca i rilievi del verificatore")
    from verify import verify_solution

    from excel_io import scrivi_risultati
    from test_verify import reference_case

    import dataclasses

    from openpyxl import load_workbook

    data, solution = reference_case()
    # rompo la soluzione: il secondo carroponte finisce addosso al primo
    rotto = dataclasses.replace(solution)
    rotto.segments_per_hoist = [
        solution.segments_per_hoist[0],
        [
            dataclasses.replace(s, x_start=s.x_start - 10000, x_end=s.x_end - 10000)
            for s in solution.segments_per_hoist[1]
        ],
    ]
    report = verify_solution(data, rotto)
    fd, percorso = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        scrivi_risultati(percorso, data, rotto, report)
        wb = load_workbook(percorso)
        ws = wb["Verifica"]
        righe = [
            [ws.cell(r, c).value for c in range(1, 11)]
            for r in range(2, ws.max_row + 1)
        ]
        check(len(righe) == len(report.violations), "una riga per rilievo")
        check(
            any(r[0] == "ERRORE" and r[1] == "collision" for r in righe),
            "la collisione compare come ERRORE",
        )
        testo = "\n".join(
            str(wb["Riepilogo"].cell(r, c).value)
            for r in range(1, wb["Riepilogo"].max_row + 1)
            for c in (1, 2)
        )
        check("NON SUPERATA" in testo, "il riepilogo dice che la verifica fallisce")
    finally:
        os.unlink(percorso)


def test_risultati_due_meta():
    """Il file dei risultati e' due cose insieme, e si vede: prima la linea
    com'e' entrata, poi il referto, ciascuno dietro il suo cartello."""
    print("\n[18] il file dei risultati e' diviso in Input e Output")
    from openpyxl import load_workbook

    from excel_io import (
        FOGLIO_CICLOGRAMMA,
        FOGLIO_PARAMETRI,
        FOGLIO_PERCORSO,
        FOGLIO_VASCHE,
        FOGLIO_ZONE,
        leggi_problema,
        scrivi_modello,
        scrivi_risultati,
    )
    from model import proposta_semplice
    from verify import verify_solution

    cartella = tempfile.mkdtemp()
    linea = os.path.join(cartella, "linea.xlsx")
    scrivi_modello(linea)
    cfg = leggi_problema(linea)
    sol, dati = proposta_semplice(cfg.data)
    risultati = os.path.join(cartella, "risultati.xlsx")
    scrivi_risultati(
        risultati,
        dati,
        sol,
        verify_solution(dati, sol),
        sorgente=linea,
        cfg=cfg,
        ciclogramma={
            "T": sol.T,
            "n_carroponti": 1,
            "permanenze": {},
            "assegnazione": {k: 0 for k in range(dati.n_moves)},
        },
    )
    wb = load_workbook(risultati)
    atteso = [
        "Input",
        "Istruzioni",
        FOGLIO_VASCHE,
        FOGLIO_PERCORSO,
        FOGLIO_PARAMETRI,
        FOGLIO_ZONE,
        FOGLIO_CAMBIO_QUOTA,
        FOGLIO_CICLOGRAMMA,
        "Output",
        "Riepilogo",
        "Movimenti",
        "SequenzaCarri",
        "TempiVerticali",
        "FlussoPezzo",
        "Verifica",
    ]
    check(wb.sheetnames == atteso, f"prima l'ingresso, poi il referto: {wb.sheetnames}")
    colori = {
        n: (wb[n].sheet_properties.tabColor.rgb if wb[n].sheet_properties.tabColor else None)
        for n in wb.sheetnames
    }
    check(
        colori["Input"] is not None
        and colori["Output"] is not None
        and colori["Input"] != colori["Output"],
        f"i due cartelli hanno la linguetta colorata, di due colori diversi "
        f"({colori['Input']}, {colori['Output']})",
    )
    check(
        all(colori[n] is None for n in wb.sheetnames if n not in ("Input", "Output")),
        "e gli altri fogli no: il colore serve a trovare la divisione",
    )
    check(wb.active.title == "Riepilogo", f"si apre sul Riepilogo ({wb.active.title})")

    # L'elenco dentro un cartello deve dire i fogli che vengono davvero dopo:
    # un indice scritto a mano resterebbe indietro alla prima aggiunta, e un
    # indice che mente e' peggio di nessun indice.
    def elencati(nome):
        ws = wb[nome]
        return [ws.cell(r, 1).value for r in range(5, ws.max_row + 1)]

    taglio = atteso.index("Output")
    check(
        elencati("Input") == atteso[1:taglio],
        f"il cartello Input elenca i fogli che seguono ({elencati('Input')})",
    )
    check(
        elencati("Output") == atteso[taglio + 1 :],
        f"il cartello Output elenca i fogli che seguono ({elencati('Output')})",
    )
    check(
        all(bool(wb[n].cell(r, 2).value) for n in ("Input", "Output")
            for r in range(5, wb[n].max_row + 1)),
        "e ogni voce ha la sua descrizione, non solo il nome",
    )

    # I cartelli non devono disturbare la rilettura: leggi_problema cerca i
    # fogli per nome e ignora gli altri.
    riletto = leggi_problema(risultati)
    check(
        riletto.data.n_stations == cfg.data.n_stations
        and riletto.ciclogramma is not None,
        "e il file resta riapribile con i cartelli dentro",
    )

    # Senza la linea non c'e' niente da separare: il file e' solo il referto.
    solo = os.path.join(cartella, "solo_referto.xlsx")
    scrivi_risultati(solo, dati, sol, verify_solution(dati, sol))
    check(
        load_workbook(solo).sheetnames
        == ["Riepilogo", "Movimenti", "SequenzaCarri", "TempiVerticali", "FlussoPezzo", "Verifica"],
        "senza la linea dentro, nessun cartello: non dividerebbe niente",
    )


def test_tempi_verticali():
    """Una presa da 26 secondi su una corsa da un metro e mezzo sembra un
    errore di calcolo, finche' non si vede che dieci di quei secondi sono lo
    sgocciolamento dichiarato. Il foglio deve dirlo."""
    print("\n[19] foglio TempiVerticali: dove va il tempo di presa e rilascio")
    from openpyxl import load_workbook

    from excel_io import leggi_problema, scrivi_modello, scrivi_risultati
    from model import proposta_semplice
    from verify import verify_solution

    # Serve una linea con le corse verticali vere: il caso di riferimento dei
    # test del verificatore le ha a zero, e senza corsa non c'e' nessuna presa
    # da spiegare.
    cartella = tempfile.mkdtemp()
    linea = os.path.join(cartella, "linea.xlsx")
    scrivi_modello(linea)
    cfg = leggi_problema(linea)
    solution, data = proposta_semplice(cfg.data)
    percorso = os.path.join(cartella, "risultati.xlsx")
    scrivi_risultati(percorso, data, solution, verify_solution(data, solution))
    wb = load_workbook(percorso)
    try:
        ws = wb["TempiVerticali"]
        righe = [
            [ws.cell(r, c).value for c in range(1, 14)]
            for r in range(2, ws.max_row + 1)
            if isinstance(ws.cell(r, 2).value, (int, float))
        ]
        vasche = {r[0] for r in righe}
        check(
            vasche == set(data.tanks),
            f"una riga per vasca, senza ripetere ({len(righe)} righe)",
        )
        # Le colonne di dettaglio devono sommare ai totali: sono la stessa
        # cosa detta due volte, e se divergessero il foglio mentirebbe proprio
        # dove serve a chiarire.
        somme = all(
            abs(sum(r[2:7]) - r[7]) < 5e-3 and abs(sum(r[8:12]) - r[12]) < 5e-3
            for r in righe
        )
        check(somme, "il dettaglio somma ai totali di presa e rilascio")

        # ...e i totali devono essere le durate che compaiono nei Movimenti,
        # che e' la domanda da cui si parte: perche' quella riga dura tanto?
        mov = wb["Movimenti"]
        durate = {}
        for r in range(2, mov.max_row + 1):
            fase, vasca, durata = (
                mov.cell(r, 2).value,
                mov.cell(r, 3).value,
                mov.cell(r, 7).value,
            )
            if fase in ("presa dalla vasca", "rilascio nella vasca"):
                durate.setdefault((fase, vasca), set()).add(round(durata, 2))
        totali = {r[0]: (round(r[7], 2), round(r[12], 2)) for r in righe}
        coerenti = all(
            valori == {totali[vasca][0 if fase.startswith("presa") else 1]}
            for (fase, vasca), valori in durate.items()
        )
        check(
            coerenti and durate,
            f"e coincidono con le durate del foglio Movimenti ({len(durate)} "
            f"combinazioni fase/vasca)",
        )
    finally:
        os.unlink(percorso)


def test_cambio_quota():
    print("\n[20] foglio CambioQuota: va e torna, e gli errori si vedono")
    import dataclasses

    from excel_io import scrivi_linea
    from model import ZonaCambioQuota

    p = modello_temporaneo()
    try:
        cfg = leggi_problema(p)
        check(
            cfg.data.cambio_quota_carico is None
            and cfg.data.cambio_quota_scarico is None,
            "il modello d'esempio non ha zone di cambio quota: foglio vuoto",
        )
        # CARICO e' a 0 con SGRASSO a 2500; SCARICO a 20000 con PASSIVAZIONE a
        # 16500: le due zone devono cadere dentro quegli intervalli.
        con = dataclasses.replace(
            cfg,
            data=dataclasses.replace(
                cfg.data,
                cambio_quota_carico=ZonaCambioQuota(1200, 350, 1650, 2400),
                cambio_quota_scarico=ZonaCambioQuota(18000, 350, 1650, 2400),
            ),
        )
        fd, con_zone = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            scrivi_linea(con_zone, con)
            riletto = leggi_problema(con_zone)
            check(
                riletto.data.cambio_quota_carico == con.data.cambio_quota_carico
                and riletto.data.cambio_quota_scarico
                == con.data.cambio_quota_scarico,
                "le due zone tornano identiche dal file",
            )
            check(riletto.data == con.data, "e con loro tutto il resto della linea")

            # Una riga a meta' non deve passare: con tre numeri su quattro il
            # giro non e' definito, e indovinare il quarto sarebbe peggio.
            modifica(con_zone, FOGLIO_CAMBIO_QUOTA, "D2", None)
            msg = errore_leggendo(con_zone)
            check(
                f"{FOGLIO_CAMBIO_QUOTA}!D2" in msg,
                f"riga incompleta: segnalata in {FOGLIO_CAMBIO_QUOTA}!D2",
            )

            # Un'etichetta sbagliata: le zone possono essere solo due, e dire
            # quali evita di far cercare l'errore altrove.
            modifica(con_zone, FOGLIO_CAMBIO_QUOTA, "D2", 1650)
            modifica(con_zone, FOGLIO_CAMBIO_QUOTA, "A2", "centro")
            msg = errore_leggendo(con_zone)
            check(
                f"{FOGLIO_CAMBIO_QUOTA}!A2" in msg and "'carico'" in msg,
                f"etichetta sconosciuta: segnalata, e dice quali sono ammesse",
            )

            # Punto di cambio quota oltre la vasca accanto: e' un errore di
            # geometria dell'impianto, e va detto leggendo il file.
            modifica(con_zone, FOGLIO_CAMBIO_QUOTA, "A2", "carico")
            modifica(con_zone, FOGLIO_CAMBIO_QUOTA, "B2", 9000)
            msg = errore_leggendo(con_zone)
            check(
                "cambio quota" in msg and "SGRASSO" in msg,
                f"punto fuori posto: segnalato con le due stazioni fra cui deve "
                f"stare",
            )
        finally:
            if os.path.exists(con_zone):
                os.unlink(con_zone)
    finally:
        os.unlink(p)


def test_ordine_svincoli():
    print("\n[21] gli svincoli stanno nell'ordine della rotaia")
    from openpyxl import load_workbook

    from excel_io import scrivi_linea

    p = modello_temporaneo()
    try:
        wb = load_workbook(p)
        intestazioni = [wb[FOGLIO_VASCHE].cell(1, c).value for c in (6, 7)]
        check(
            intestazioni == ["svincolo_negativo_mm", "svincolo_positivo_mm"],
            f"prima il negativo, poi il positivo ({intestazioni})",
        )
        # Gli svincoli si dichiarano per tutte le vasche o per nessuna: qui
        # servono solo a leggere le colonne, ma il file deve stare in piedi.
        ws = wb[FOGLIO_VASCHE]
        for riga in range(2, ws.max_row + 1):
            pos = ws.cell(riga, 2).value
            if not ws.cell(riga, 1).value:
                continue
            ws.cell(riga, 6).value = pos - 900 if pos > 0 else None
            ws.cell(riga, 7).value = pos + 900 if pos < 20000 else None
        wb.save(p)
        # SGRASSO sta a 2500: il negativo prima, il positivo dopo
        modifica(p, FOGLIO_VASCHE, "F3", 1800)
        modifica(p, FOGLIO_VASCHE, "G3", 3200)
        cfg = leggi_problema(p)
        t = cfg.data.tanks["SGRASSO"]
        check(
            (t.svincolo_neg, t.svincolo_pos) == (1800.0, 3200.0),
            f"letti dalla colonna giusta (neg {t.svincolo_neg}, pos {t.svincolo_pos})",
        )
        # Riscrivendo la linea le due colonne devono tornare nello stesso
        # ordine: altrimenti salvare e riaprire scambierebbe i valori a ogni
        # giro, e nessuno se ne accorgerebbe finche' la geometria non lo
        # respinge.
        fd, rifatto = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            scrivi_linea(rifatto, cfg)
            t2 = leggi_problema(rifatto).data.tanks["SGRASSO"]
            check(
                (t2.svincolo_neg, t2.svincolo_pos) == (1800.0, 3200.0),
                "e salvando e riaprendo restano dov'erano",
            )
        finally:
            if os.path.exists(rifatto):
                os.unlink(rifatto)

        # Un file scritto quando le colonne erano al contrario: va riconosciuto
        # per quello che e', non respinto per una geometria impossibile -- chi
        # lo ha compilato non ha sbagliato niente.
        modifica(p, FOGLIO_VASCHE, "F3", 3200)
        modifica(p, FOGLIO_VASCHE, "G3", 1800)
        msg = errore_leggendo(p)
        check(
            f"{FOGLIO_VASCHE}!F3" in msg and "scambiati" in msg,
            f"le colonne invertite di un file vecchio vengono riconosciute",
        )
        check(
            "non e' definita" not in msg,
            "e il messaggio resta uno solo, senza errori a cascata",
        )
    finally:
        os.unlink(p)


def test_misure_di_disegno():
    print("\n[27] larghezza e altezza di vasche e pezzo: facoltative, e solo "
          "per il disegno")

    def riga_parametro(percorso: str, nome: str) -> int:
        from openpyxl import load_workbook

        ws = load_workbook(percorso)[FOGLIO_PARAMETRI]
        for riga in range(2, ws.max_row + 1):
            if _testo_cella(ws.cell(riga, 1).value) == nome:
                return riga
        raise AssertionError(f"parametro '{nome}' non trovato nel modello")

    p = modello_temporaneo()
    try:
        d = leggi_problema(p).data
        z = d.tanks["ZINCATURA"]
        check(
            (z.larghezza, z.altezza) == (2600.0, 1600.0)
            and (d.larghezza_pezzo, d.altezza_pezzo) == (1400.0, 900.0),
            f"le misure del modello si rileggono (vasca {z.larghezza:.0f}x"
            f"{z.altezza:.0f}, pezzo {d.larghezza_pezzo:.0f}x{d.altezza_pezzo:.0f})",
        )
        # Vuoto vuol dire "non lo so", non zero: carico e scarico non sono
        # vasche e nel modello restano in bianco.
        check(
            d.tanks["CARICO"].larghezza is None and d.tanks["CARICO"].altezza is None,
            "una cella vuota resta None, e non diventa un rettangolo alto zero",
        )
        # Sono FACOLTATIVE: svuotandole tutte il file resta valido, e la linea
        # e' la stessa -- il calcolo non le guarda.
        for cella in ("I3", "J3"):
            modifica(p, FOGLIO_VASCHE, cella, None)
        for nome in ("larghezza_pezzo_mm", "altezza_pezzo_mm"):
            modifica(p, FOGLIO_PARAMETRI, f"B{riga_parametro(p, nome)}", None)
        msg = errore_leggendo(p)
        vuoto = leggi_problema(p).data if not msg else None
        check(
            not msg
            and vuoto.tanks["SGRASSO"].larghezza is None
            and vuoto.larghezza_pezzo is None
            and vuoto.pick_time_at(1) == d.pick_time_at(1),
            f"lasciandole vuote il file vale lo stesso, e i tempi non cambiano "
            f"({msg[:60]})",
        )

        # Sbagliate invece si dicono: una vasca larga -100 non e' un disegno
        # diverso, e' una cella sbagliata.
        modifica(p, FOGLIO_VASCHE, "I3", -100)
        msg = errore_leggendo(p)
        check(
            "larghezza" in msg and "SGRASSO" in msg,
            f"una larghezza negativa viene respinta dicendo quale vasca: "
            f"\"{msg[:90]}\"",
        )
        modifica(p, FOGLIO_VASCHE, "I3", "due metri")
        msg = errore_leggendo(p)
        check(
            f"{FOGLIO_VASCHE}!I3" in msg,
            f"e un testo al posto del numero dice la cella: \"{msg[:70]}\"",
        )
    finally:
        os.unlink(p)


def test_interblocco():
    print("\n[27-bis] interblocco: un parametro per tutta la linea")
    from excel_io import scrivi_linea

    def riga_parametro(percorso: str, nome: str) -> int:
        from openpyxl import load_workbook

        ws = load_workbook(percorso)[FOGLIO_PARAMETRI]
        for riga in range(2, ws.max_row + 1):
            if _testo_cella(ws.cell(riga, 1).value) == nome:
                return riga
        raise AssertionError(f"parametro '{nome}' non trovato nel modello")

    p = modello_temporaneo()
    rifatto = None
    try:
        check(leggi_problema(p).data.interblocco, "nel modello e' acceso")
        check(
            valore(p, FOGLIO_VASCHE, "K1") is None,
            "il foglio Vasche non ha colonne per l'interblocco",
        )
        riga = riga_parametro(p, "interblocco_vasche")
        modifica(p, FOGLIO_PARAMETRI, f"B{riga}", 0)
        cfg = leggi_problema(p)
        check(not cfg.data.interblocco, "interblocco_vasche = 0 lo spegne")
        # si rilegge com'era: il file riscritto porta la stessa scelta
        fd, rifatto = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        scrivi_linea(rifatto, cfg)
        check(
            not leggi_problema(rifatto).data.interblocco,
            "riscrivendo la linea resta spento",
        )
        modifica(p, FOGLIO_PARAMETRI, f"B{riga}", None)
        check(leggi_problema(p).data.interblocco, "vuoto vale 1")
        modifica(p, FOGLIO_PARAMETRI, f"B{riga}", 2)
        msg = errore_leggendo(p)
        check(
            "interblocco_vasche" in msg and "0 oppure 1" in msg,
            f"un valore diverso da 0 e 1 viene respinto: \"{msg[-60:]}\"",
        )
    finally:
        os.unlink(p)
        if rifatto:
            os.unlink(rifatto)


def test_decelerazione_separata():
    """La frenata ha i suoi numeri, e si vedono nei tempi."""
    print("\n[28] decelerazione distinta dall'accelerazione")
    from openpyxl import load_workbook

    def scrivi_parametri(percorso, valori: dict):
        wb = load_workbook(percorso)
        ws = wb[FOGLIO_PARAMETRI]
        for riga in range(2, ws.max_row + 1):
            nome = ws.cell(riga, 1).value
            if nome in valori:
                ws.cell(riga, 2).value = valori[nome]
        wb.save(percorso)

    p = modello_temporaneo()
    try:
        cfg = leggi_problema(p)
        check(
            cfg.data.kin_empty.d_max == 1200 and cfg.data.kin_loaded.d_max == 500,
            f"le quattro decelerazioni si leggono "
            f"(vuoto {cfg.data.kin_empty.d_max}, carico {cfg.data.kin_loaded.d_max})",
        )
        check(
            cfg.data.kin_lift_empty.d_max == 800
            and cfg.data.kin_lift_loaded.d_max == 500,
            "anche quelle del sollevamento",
        )
        # la leva vera: a parita' di tutto il resto, frenare piu' forte
        # accorcia il trasporto. Se il codice usasse ancora l'accelerazione
        # in frenata, questi due numeri sarebbero identici.
        t_base = cfg.data.loaded_leg_seconds(0)
        scrivi_parametri(p, {"d_max_carico_mm_s2": 2000})
        t_frena = leggi_problema(p).data.loaded_leg_seconds(0)
        check(
            t_frena < t_base - 1e-6,
            f"frenando piu' forte il trasporto si accorcia "
            f"({t_base:.3f} s -> {t_frena:.3f} s)",
        )
    finally:
        os.unlink(p)

    # cella vuota: si frena come si accelera, cioe' come prima che il
    # parametro esistesse. E' quello che rende leggibili i file gia' compilati.
    p = modello_temporaneo()
    try:
        scrivi_parametri(
            p,
            {
                "d_max_vuoto_mm_s2": None,
                "d_max_carico_mm_s2": None,
                "d_max_sollevamento_vuoto_mm_s2": None,
                "d_max_sollevamento_carico_mm_s2": None,
            },
        )
        cfg = leggi_problema(p)
        check(
            cfg.data.kin_empty.d_max is None
            and cfg.data.kin_empty.decel == cfg.data.kin_empty.a_max,
            f"lasciata vuota, si frena con l'accelerazione "
            f"({cfg.data.kin_empty.decel} mm/s^2)",
        )
        check(
            cfg.data.kin_lift_empty is not None,
            "e il sollevamento resta attivo: manca la frenata, non la cinematica",
        )
    finally:
        os.unlink(p)

    # una decelerazione a zero non e' un valore mancante: e' un assurdo
    p = modello_temporaneo()
    try:
        scrivi_parametri(p, {"d_max_carico_mm_s2": 0})
        msg = errore_leggendo(p)
        check("d_max" in msg, f"una frenata a zero viene respinta: \"{msg[:70]}\"")
    finally:
        os.unlink(p)


def test_avvicinamento_sollevamento():
    """La zona di avvicinamento: si legge, costa tempo, e sa da che parte sta."""
    print("\n[29] zona di avvicinamento del sollevamento")
    import dataclasses

    from openpyxl import load_workbook

    def scrivi_parametri(percorso, valori: dict):
        wb = load_workbook(percorso)
        ws = wb[FOGLIO_PARAMETRI]
        for riga in range(2, ws.max_row + 1):
            nome = ws.cell(riga, 1).value
            if nome in valori:
                ws.cell(riga, 2).value = valori[nome]
        wb.save(percorso)

    p = modello_temporaneo()
    try:
        cfg = leggi_problema(p)
        d = cfg.data
        check(
            d.v_approach_lift == 80 and d.d_approach_lift == 150,
            f"i due parametri si leggono ({d.v_approach_lift} mm/s per "
            f"{d.d_approach_lift} mm)",
        )

        # Da che parte sta la zona lo dice il MOVIMENTO, non il file: salendo a
        # prelevare sta in testa alla corsa, scendendo a posare sta in fondo.
        salita = [f for f in d.pick_phases(1) if f.kin is not None][0]
        discesa = [f for f in d.release_phases(1) if f.kin is not None][0]
        check(
            salita.kin.approach is not None
            and not salita.kin.approach.at_end
            and discesa.kin.approach is not None
            and discesa.kin.approach.at_end,
            "salendo la zona e' in testa alla corsa, scendendo e' in fondo",
        )
        check(
            salita.kin.approach.speed == 80
            and salita.kin.approach.distance == 150,
            "e porta i due numeri dichiarati nel file",
        )

        # La leva vera: senza i due parametri le stesse corse durano meno.
        senza = dataclasses.replace(
            d, v_approach_lift=None, d_approach_lift=None
        )
        check(
            d.pick_time_at(1) > senza.pick_time_at(1) + 1e-6
            and d.release_time_at(1) > senza.release_time_at(1) + 1e-6,
            f"presa e rilascio si allungano (presa {senza.pick_time_at(1):.3f} s "
            f"-> {d.pick_time_at(1):.3f} s)",
        )

        # Salita e discesa a gancio scarico smettono di durare uguale appena
        # la frenata e' diversa dall'accelerazione: la zona lenta cade una
        # volta in coda e una volta in testa, e i due conti non si specchiano
        # piu'. (Nel modello d'esempio le due sono uguali, e infatti li' i due
        # versi coincidono: e' il caso di sopra.)
        asimm = dataclasses.replace(
            d,
            kin_lift_empty=dataclasses.replace(d.kin_lift_empty, d_max=2000),
        )
        su = asimm.empty_lift_seconds(1, scendendo=False)
        giu = asimm.empty_lift_seconds(1, scendendo=True)
        check(
            abs(su - giu) > 1e-6,
            f"frenando diversamente, a vuoto salita e discesa si separano "
            f"({su:.3f} s contro {giu:.3f} s)",
        )
        check(
            senza.empty_lift_seconds(1, scendendo=False)
            == senza.empty_lift_seconds(1, scendendo=True),
            "senza avvicinamento tornano identiche, e il verso non conta",
        )

        # Round trip: i due numeri sopravvivono alla scrittura.
        fd, rifatto = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            from excel_io import scrivi_linea

            scrivi_linea(rifatto, cfg)
            check(
                leggi_problema(rifatto).data == d,
                "e la linea riscritta e' identica a quella letta",
            )
        finally:
            os.unlink(rifatto)
    finally:
        os.unlink(p)

    # Su una stazione servita da una zona di cambio quota la zona lenta non
    # c'e': li' le quote sono di transito, non punti di presa.
    p = modello_temporaneo()
    try:
        from excel_io import scrivi_linea
        from model import ZonaCambioQuota

        cfg = leggi_problema(p)
        con = dataclasses.replace(
            cfg,
            data=dataclasses.replace(
                cfg.data, cambio_quota_carico=ZonaCambioQuota(1200, 350, 1650, 2400)
            ),
        )
        d = con.data
        check(
            all(f.kin is None or f.kin.approach is None for f in d.pick_phases(0)),
            "sul carico con cambio quota nessuna fase rallenta",
        )
        check(
            any(
                f.kin is not None and f.kin.approach is not None
                for f in d.pick_phases(1)
            ),
            "mentre sulla vasca accanto, che zona non ne ha, la zona c'e'",
        )
    finally:
        os.unlink(p)

    # I due numeri vanno insieme, e non possono essere assurdi.
    for valori, atteso in (
        ({"d_approach_sollevamento_mm": None}, "insieme"),
        ({"v_approach_sollevamento_mm_s": None}, "insieme"),
        ({"v_approach_sollevamento_mm_s": 0}, "> 0"),
        ({"v_approach_sollevamento_mm_s": 9000}, "supera la velocita'"),
    ):
        p = modello_temporaneo()
        try:
            scrivi_parametri(p, valori)
            msg = errore_leggendo(p)
            check(
                atteso in msg,
                f"{list(valori.items())[0]} respinto: \"{msg[:70]}\"",
            )
        finally:
            os.unlink(p)

    # Celle vuote: tutto come prima che il parametro esistesse.
    p = modello_temporaneo()
    try:
        scrivi_parametri(
            p,
            {
                "v_approach_sollevamento_mm_s": None,
                "d_approach_sollevamento_mm": None,
            },
        )
        d = leggi_problema(p).data
        check(
            d.v_approach_lift is None and d.d_approach_lift is None,
            "lasciati vuoti, il sollevamento resta il trapezio di sempre",
        )
        check(
            all(
                f.kin is None or f.kin.approach is None
                for f in d.pick_phases(1) + d.release_phases(1)
            ),
            "e nessuna fase verticale porta una zona di avvicinamento",
        )
    finally:
        os.unlink(p)


def test_takt_fisso_e_pesi():
    print("\n[22] takt time fisso e pesi dello scarto dal teorico")
    from openpyxl import load_workbook

    from excel_io import scrivi_linea

    def scrivi_parametro(percorso, nome, valore):
        wb = load_workbook(percorso)
        ws = wb[FOGLIO_PARAMETRI]
        for riga in range(2, ws.max_row + 1):
            if ws.cell(riga, 1).value == nome:
                ws.cell(riga, 2).value = valore
        wb.save(percorso)

    p = modello_temporaneo()
    try:
        d = leggi_problema(p).data
        check(not d.takt_fisso, "il modello d'esempio ottimizza il takt time")
        zinc = d.route[3]
        check(
            (zinc.tank_id, zinc.peso_sotto, zinc.peso_sopra) == ("ZINCATURA", 10, 3),
            "i due pesi della tappa si leggono dalle colonne F e G",
        )
    finally:
        os.unlink(p)

    # Pesi lasciati vuoti: valgono 1, cosi' un file senza quelle colonne si
    # legge com'era.
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_PERCORSO, "F5", None)
        modifica(p, FOGLIO_PERCORSO, "G5", "")
        zinc = leggi_problema(p).data.route[3]
        check(
            (zinc.peso_sotto, zinc.peso_sopra) == (1.0, 1.0),
            "pesi vuoti -> 1",
        )
    finally:
        os.unlink(p)

    for cella, valore_scritto, atteso in (
        ("F5", -2, "F5"),
        ("G4", "tanto", "G4"),
        # positivo, ma a due decimali farebbe 0: diventerebbe "indifferente"
        ("F4", 0.001, "F4"),
    ):
        p = modello_temporaneo()
        try:
            modifica(p, FOGLIO_PERCORSO, cella, valore_scritto)
            msg = errore_leggendo(p)
            check(
                f"{FOGLIO_PERCORSO}!{atteso}" in msg,
                f"peso {valore_scritto!r} in {cella} respinto con la cella",
            )
        finally:
            os.unlink(p)

    p = modello_temporaneo()
    try:
        scrivi_parametro(p, "takt_fisso", 2)
        check("takt_fisso" in errore_leggendo(p), "takt_fisso = 2 respinto")
    finally:
        os.unlink(p)

    # Andata e ritorno: la modalita' e i pesi sopravvivono a una riscrittura.
    p = modello_temporaneo()
    fd, riscritto = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        scrivi_parametro(p, "takt_fisso", 1)
        modifica(p, FOGLIO_PERCORSO, "F3", 0.5)
        cfg = leggi_problema(p)
        check(cfg.data.takt_fisso, "takt_fisso = 1 letto")
        scrivi_linea(riscritto, cfg)
        d = leggi_problema(riscritto).data
        check(d.takt_fisso, "e sopravvive alla riscrittura del file")
        check(
            [(s.peso_sotto, s.peso_sopra) for s in d.route]
            == [(s.peso_sotto, s.peso_sopra) for s in cfg.data.route]
            and d.route[1].peso_sotto == 0.5,
            "anche i pesi di tutte le tappe",
        )
    finally:
        os.unlink(p)
        os.unlink(riscritto)


def main():
    print("=" * 72)
    print("TEST DI LETTURA E SCRITTURA EXCEL (richiede openpyxl, non OR-Tools)")
    print("=" * 72)
    test_andata_e_ritorno()
    test_foglio_ciclogramma()
    test_valori_mancanti_e_sbagliati()
    test_corsa_e_scolo_obbligatori()
    test_virgola_decimale()
    test_file_in_metri()
    test_parametro_sostituito()
    test_takt_teorico_e_tolleranze()
    test_vasca_inesistente()
    test_vasca_duplicata()
    test_percorso_riordinato()
    test_parametro_sconosciuto()
    test_parametro_facoltativo_vuoto()
    test_sollevamento_incoerente()
    test_portate()
    test_errori_multipli()
    test_foglio_mancante()
    test_dati_incoerenti()
    test_risultati_struttura()
    test_risultati_utilizzo()
    test_risultati_movimenti()
    test_risultati_flusso_pezzo()
    test_risultati_scarto_pesato()
    test_risultati_verifica()
    test_risultati_due_meta()
    test_tempi_verticali()
    test_cambio_quota()
    test_ordine_svincoli()
    test_misure_di_disegno()
    test_interblocco()
    test_decelerazione_separata()
    test_avvicinamento_sollevamento()
    test_takt_fisso_e_pesi()
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
