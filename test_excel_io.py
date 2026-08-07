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
            (d.kin_empty.v_max, d.kin_loaded.a_max) == (1600, 400),
            "cinematiche vuoto e carico",
        )
        check(
            (d.lift_height, d.engage_time, d.disengage_time) == (800, 2.0, 1.0),
            "corsa verticale e tempi di aggancio/sgancio",
        )
        check(
            (d.kin_lift_empty.v_max, d.kin_lift_loaded.a_max) == (500, 500),
            "cinematiche di sollevamento",
        )
        check(
            d.tanks["ZINCATURA"].lift_height == 1100
            and d.tanks["SGRASSO"].lift_height is None,
            "corsa verticale per vasca solo dove indicata",
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
        modifica(p, FOGLIO_VASCHE, "B3", "2500,5")
        modifica(p, FOGLIO_PARAMETRI, "B4", "1650,5")
        cfg = leggi_problema(p)
        check(cfg.data.tanks["SGRASSO"].position == 2500.5, "'2500,5' letto come 2500.5")
        check(
            cfg.data.kin_empty.v_max == 1650.5,
            "'1650,5' letto come 1650.5 (B4 e' v_max_vuoto_mm_s)",
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
            if str(ws.cell(riga, 1).value or "").startswith("v_max_sollevamento"):
                ws.cell(riga, 2).value = None
        wb.save(p)
        msg = errore_leggendo(p)
        check(
            "cinematiche di sollevamento" in msg,
            "corsa dichiarata ma cinematica mancante: segnalato",
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
            elif nome == "altezza_sollevamento_mm":
                ws.cell(riga, 2).value = 0
        ws2 = wb[FOGLIO_VASCHE]
        for riga in range(2, ws2.max_row + 1):
            ws2.cell(riga, 4).value = None
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
            wb.sheetnames == ["Riepilogo", "Movimenti", "FlussoPezzo", "Verifica"],
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


def main():
    print("=" * 72)
    print("TEST DI LETTURA E SCRITTURA EXCEL (richiede openpyxl, non OR-Tools)")
    print("=" * 72)
    test_andata_e_ritorno()
    test_valori_mancanti_e_sbagliati()
    test_virgola_decimale()
    test_file_in_metri()
    test_parametro_sostituito()
    test_vasca_inesistente()
    test_vasca_duplicata()
    test_percorso_riordinato()
    test_parametro_sconosciuto()
    test_parametro_facoltativo_vuoto()
    test_sollevamento_incoerente()
    test_zone_manuali()
    test_errori_multipli()
    test_foglio_mancante()
    test_dati_incoerenti()
    test_risultati_struttura()
    test_risultati_utilizzo()
    test_risultati_movimenti()
    test_risultati_flusso_pezzo()
    test_risultati_verifica()
    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
