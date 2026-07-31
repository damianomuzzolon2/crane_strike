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
    python test_excel_io.py
"""

from __future__ import annotations

import os
import tempfile

from excel_io import (
    FOGLIO_PARAMETRI,
    FOGLIO_PERCORSO,
    FOGLIO_VASCHE,
    FOGLIO_ZONE,
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
            (d.takt_min, d.takt_max) == (110.0, 150.0), "banda di takt time 110-150 s"
        )
        check(
            (d.kin_empty.v_max, d.kin_loaded.a_max) == (1.6, 0.4),
            "cinematiche vuoto e carico",
        )
        check(
            (d.pick_time, d.release_time) == (6.0, 4.0), "tempi di presa e rilascio"
        )
        check(d.zones is None, "foglio Zone vuoto -> scelta automatica")
        check(
            (cfg.max_carroponti, cfg.tempo_limite_s) == (4, 15.0),
            "opzioni di risoluzione",
        )
    finally:
        os.unlink(p)


def test_valori_mancanti_e_sbagliati():
    print("\n[2] valori mancanti o non numerici")
    casi = [
        (FOGLIO_VASCHE, "B3", None, "Vasche!B3", "posizione mancante"),
        (FOGLIO_VASCHE, "B3", "due metri", "Vasche!B3", "posizione non numerica"),
        (FOGLIO_VASCHE, "C3", 2.5, "Vasche!C3", "posti non intero"),
        (FOGLIO_PERCORSO, "C3", None, "Percorso!C3", "permanenza minima mancante"),
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


def test_virgola_decimale():
    print("\n[3] numeri scritti con la virgola decimale")
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_VASCHE, "B3", "2,5")
        modifica(p, FOGLIO_PARAMETRI, "B4", "0,9")
        cfg = leggi_problema(p)
        check(cfg.data.tanks["SGRASSO"].position == 2.5, "'2,5' letto come 2.5")
        check(cfg.data.kin_empty.a_max == 0.9, "'0,9' letto come 0.9")
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
        check("takt_min_s" in msg, "il messaggio elenca i nomi ammessi")
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
                "tempo_presa_s",
                "risoluzione_tick_per_s",
                "max_carroponti",
            ):
                ws.cell(riga, 2).value = None
        wb.save(p)
        cfg = leggi_problema(p)
        check(cfg.data.pick_time == 0.0, "tempo_presa_s -> default 0")
        check(cfg.data.time_scale == 100, "risoluzione_tick_per_s -> default 100")
        check(cfg.max_carroponti == 6, "max_carroponti -> default 6")
    finally:
        os.unlink(p)


def test_zone_manuali():
    print("\n[9] zone indicate a mano")
    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_ZONE, "A2", 0)
        modifica(p, FOGLIO_ZONE, "B2", 2)
        modifica(p, FOGLIO_ZONE, "A3", 3)
        modifica(p, FOGLIO_ZONE, "B3", 5)
        cfg = leggi_problema(p)
        check(
            cfg.data.zones is not None
            and [(z.lo, z.hi) for z in cfg.data.zones] == [(0, 2), (3, 5)],
            "zone lette correttamente",
        )
    finally:
        os.unlink(p)

    p = modello_temporaneo()
    try:
        modifica(p, FOGLIO_ZONE, "A2", 0)
        modifica(p, FOGLIO_ZONE, "B2", 2)  # manca la seconda zona
        msg = errore_leggendo(p)
        check("contigu" in msg and FOGLIO_ZONE in msg, "copertura incompleta rilevata")
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
        modifica(p, FOGLIO_PARAMETRI, "B2", 200)  # takt_min > takt_max
        msg = errore_leggendo(p)
        check("takt_min > takt_max" in msg, "incoerenza dal modello, riportata")
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


def main():
    print("=" * 72)
    print("TEST DELLA LETTURA DA EXCEL (richiede openpyxl, non OR-Tools)")
    print("=" * 72)
    test_andata_e_ritorno()
    test_valori_mancanti_e_sbagliati()
    test_virgola_decimale()
    test_vasca_inesistente()
    test_vasca_duplicata()
    test_percorso_riordinato()
    test_parametro_sconosciuto()
    test_parametro_facoltativo_vuoto()
    test_zone_manuali()
    test_errori_multipli()
    test_foglio_mancante()
    test_dati_incoerenti()
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
