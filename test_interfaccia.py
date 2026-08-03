"""
test_interfaccia.py
-------------------
Test funzionale dell'interfaccia grafica. Richiede OR-Tools e un ambiente
grafico (su Windows c'e' sempre).

La finestra viene costruita davvero e pilotata da codice: si premono i
pulsanti chiamando i metodi, e si fa girare il ciclo degli eventi con
`update()` invece di `mainloop()`, cosi' il test resta automatico. E' l'unico
modo per accorgersi che un pulsante e' rimasto disabilitato, che il lavoro in
background non consegna mai il risultato, o che il salvataggio non produce
nulla -- cose che un test sulle sole funzioni di calcolo non vedrebbe.

Per eseguirlo:
    python test_interfaccia.py
"""

from __future__ import annotations

import os
import tempfile
import time
import tkinter as tk

from excel_io import scrivi_modello

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


def pompa(app, secondi_max=180.0):
    """Fa girare il ciclo degli eventi finche' il lavoro in background non e'
    finito (o scade il tempo). Sostituisce mainloop() nei test."""
    scadenza = time.time() + secondi_max
    while app._lavoro_in_corso and time.time() < scadenza:
        app.update()
        time.sleep(0.02)
    app.update()
    return not app._lavoro_in_corso


def chiudi(app):
    """Smonta la finestra nell'ordine giusto. Distruggere la radice senza
    prima liberare la tela di matplotlib lascia in giro immagini Tk che
    vengono raccolte a interprete gia' in chiusura, e stampano un
    'main thread is not in main loop' che sembra un errore e non lo e'."""
    try:
        app.tela.get_tk_widget().destroy()
    except Exception:
        pass
    app.destroy()


def ambiente_grafico_disponibile() -> bool:
    try:
        radice = tk.Tk()
        radice.destroy()
        return True
    except Exception:
        return False


def test_apertura_e_proposta(percorso_linea):
    print("\n[1] apertura della linea e proposta di partenza")
    from interfaccia import Applicazione

    app = Applicazione()
    try:
        app.update()
        check(
            str(app.btn_auto["state"]) == "disabled",
            "senza linea caricata il calcolo e' disabilitato",
        )
        app._carica(percorso_linea)
        app.update()
        check(app.config_linea is not None, "linea caricata")
        check(
            str(app.btn_auto["state"]) == "normal"
            and str(app.btn_salva["state"]) == "disabled",
            "ora si puo' calcolare, ma non ancora salvare",
        )

        app._crea_proposta()
        check(pompa(app), "la proposta viene consegnata dal thread di lavoro")
        check(app.soluzione is not None, "la proposta produce un ciclogramma")
        check(
            app.soluzione.status == "PROPOSTA" and len(app.dati.zones) == 1,
            f"e' una proposta a un carroponte (T={app.soluzione.T:.1f}s)",
        )
        check(
            str(app.btn_salva["state"]) == "normal", "il salvataggio si e' abilitato"
        )
        # la proposta banale non rispetta le tolleranze: e' previsto, e la
        # tabella deve dirlo invece di lasciare l'utente al buio
        check(
            len(app.tabella.get_children()) == len(app.report.violations)
            and len(app.report.errors) > 0,
            f"i {len(app.report.errors)} problemi della proposta sono elencati",
        )
    finally:
        chiudi(app)


def test_calcolo_automatico(percorso_linea):
    print("\n[2] calcolo automatico")
    from interfaccia import Applicazione

    app = Applicazione(percorso_linea)
    try:
        app.update()
        for _ in range(50):  # il caricamento e' schedulato con after()
            app.update()
            if app.config_linea is not None:
                break
            time.sleep(0.02)
        check(app.config_linea is not None, "il file passato all'avvio viene caricato")

        app._calcola_automatico()
        check(pompa(app), "il calcolo termina")
        check(
            app.soluzione is not None
            and app.soluzione.status in ("OPTIMAL", "FEASIBLE"),
            f"soluzione trovata (stato {app.soluzione.status if app.soluzione else '-'})",
        )
        check(app.report.ok, "la soluzione supera la verifica indipendente")
        check(
            len(app.dati.zones) == 2 and abs(app.soluzione.T - 131.88) < 1.0,
            f"{len(app.dati.zones)} carroponti, T={app.soluzione.T:.2f}s "
            f"(come da riga di comando)",
        )

        # salvataggio
        fd, uscita = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        os.unlink(uscita)
        from excel_io import scrivi_risultati

        scrivi_risultati(
            uscita, app.dati, app.soluzione, app.report, sorgente=percorso_linea
        )
        png = os.path.splitext(uscita)[0] + ".png"
        app.figura.savefig(png, dpi=100, bbox_inches="tight")
        check(
            os.path.getsize(uscita) > 5000, f"Excel dei risultati scritto ({uscita})"
        )
        check(os.path.getsize(png) > 5000, "immagine del ciclogramma scritta")
        for f in (uscita, png):
            if os.path.exists(f):
                os.unlink(f)
    finally:
        chiudi(app)


def _app_risolta(percorso_linea):
    """Finestra con la linea gia' risolta automaticamente, pronta per le
    prove di modifica."""
    from interfaccia import Applicazione

    app = Applicazione(percorso_linea)
    for _ in range(50):
        app.update()
        if app.config_linea is not None:
            break
        time.sleep(0.02)
    app._calcola_automatico()
    pompa(app)
    return app


def test_modifica_prelievo(percorso_linea):
    print("\n[4] modifica di un punto di prelievo")
    app = _app_risolta(percorso_linea)
    try:
        check(
            len(app.fasi) == app.dati.n_moves and app.T_corrente is not None,
            f"lo stato modificabile e' stato estratto ({len(app.fasi)} fasi)",
        )
        check(
            len(app.tabella_mosse.get_children()) == app.dati.n_moves,
            "la tabella delle mosse elenca tutte le mosse",
        )
        def permanenze():
            s, d = app.soluzione, app.dati
            return [
                round(
                    s.actual_time[k]
                    - (s.actual_time[k - 1] + d.loaded_leg_seconds(k - 1)),
                    2,
                )
                for k in range(1, d.n_moves)
            ]

        prima_ok = app.report.ok
        permanenze_prima = permanenze()
        fase_prima = app.fasi[1]
        istantanea = app._istantanea()

        # 10 s stanno dentro il margine di questa linea: la modifica deve
        # essere accettata, ma le permanenze devono cambiare davvero -- se
        # restassero identiche vorrebbe dire che il ciclogramma non e' stato
        # ricostruito e la verifica sta guardando i dati vecchi
        app.fasi[1] = (fase_prima + 10.0) % app.T_corrente
        applicata = app._applica("prova", istantanea)
        app.update()
        check(applicata, "lo spostamento di 10 s viene accettato")
        check(
            permanenze() != permanenze_prima,
            f"le permanenze sono state ricalcolate: {permanenze_prima} -> "
            f"{permanenze()}",
        )
        check(
            len(app.tabella.get_children()) == len(app.report.violations),
            "l'elenco dei rilievi si e' aggiornato",
        )

        # uno spostamento grande invece non e' realizzabile: il carroponte non
        # farebbe in tempo. Deve essere rifiutato, non prodotto e basta.
        istantanea2 = app._istantanea()
        app.fasi[1] = (app.fasi[1] + 30.0) % app.T_corrente
        check(
            not app._applica("prova grande", istantanea2),
            "uno spostamento troppo grande viene rifiutato",
        )

        app._annulla_modifica()
        app.update()
        check(
            abs(app.fasi[1] - fase_prima) < 1e-6
            and app.report.ok == prima_ok
            and permanenze() == permanenze_prima,
            "l'annullamento riporta esattamente alla soluzione di prima",
        )
    finally:
        chiudi(app)


def test_modifica_takt_e_carroponti(percorso_linea):
    print("\n[5] modifica del takt time e del numero di carroponti")
    app = _app_risolta(percorso_linea)
    try:
        T0 = app.T_corrente
        app.var_takt.set(f"{T0 + 15:.2f}")
        app._modifica_takt()
        app.update()
        check(
            abs(app.soluzione.T - (T0 + 15)) < 1e-6,
            f"takt time portato da {T0:.2f} a {app.soluzione.T:.2f} s",
        )

        app.var_takt.set("non un numero")
        app._modifica_takt()
        app.update()
        check(
            abs(app.soluzione.T - (T0 + 15)) < 1e-6,
            "un valore non numerico non cambia nulla e non schianta",
        )

        n0 = len(app.zone_correnti)
        app.var_carroponti.set(str(n0 + 1))
        app._modifica_numero_carroponti()
        check(pompa(app), "il ricalcolo con piu' carroponti termina")
        check(
            len(app.dati.zones) == n0 + 1,
            f"carroponti portati da {n0} a {len(app.dati.zones)} "
            f"(T={app.soluzione.T:.2f}s)",
        )
        check(app.report.ok, "e la nuova soluzione supera la verifica")
        check(
            len(app.tabella_mosse.get_children()) == app.dati.n_moves,
            "la tabella mostra la nuova assegnazione",
        )
    finally:
        chiudi(app)


def test_modifica_impossibile(percorso_linea):
    print("\n[6] modifica non realizzabile: si torna indietro, non si schianta")
    app = _app_risolta(percorso_linea)
    try:
        stato_prima = (app.T_corrente, dict(app.fasi))
        soluzione_prima = app.soluzione
        # tutti i prelievi nello stesso istante: il carroponte dovrebbe essere
        # in piu' posti insieme, quindi il ciclogramma non esiste
        istantanea = app._istantanea()
        for k in app.fasi:
            app.fasi[k] = 0.0
        applicata = app._applica("prova impossibile", istantanea)
        app.update()
        check(not applicata, "la modifica viene rifiutata")
        check(
            app.soluzione is soluzione_prima
            and app.T_corrente == stato_prima[0]
            and app.fasi == stato_prima[1],
            "lo stato torna esattamente com'era",
        )
        check(
            "non applicabile" in app.etichetta_stato["text"],
            f"l'utente viene avvisato: \"{app.etichetta_stato['text'][:60]}...\"",
        )
    finally:
        chiudi(app)


def test_proposta_modificabile(percorso_linea):
    print("\n[7] anche la proposta di partenza si puo' modificare")
    from interfaccia import Applicazione

    app = Applicazione(percorso_linea)
    try:
        for _ in range(50):
            app.update()
            if app.config_linea is not None:
                break
            time.sleep(0.02)
        app._crea_proposta()
        pompa(app)
        check(len(app.fasi) == app.dati.n_moves, "la proposta e' modificabile")
        errori_prima = len(app.report.errors)
        # da un carroponte a tre: e' la mossa naturale per rendere fattibile
        # una proposta che con un carroponte solo non sta nelle tolleranze
        app.var_carroponti.set("3")
        app._modifica_numero_carroponti()
        check(pompa(app), "il ricalcolo termina")
        check(
            len(app.dati.zones) == 3 and app.report.ok,
            f"da 1 carroponte con {errori_prima} problemi a 3 carroponti "
            f"verificati (T={app.soluzione.T:.2f}s)",
        )
    finally:
        chiudi(app)


def test_file_illeggibile():
    print("\n[3] file non valido: messaggio, non schianto")
    from interfaccia import Applicazione

    app = Applicazione()
    try:
        app.update()
        fd, cattivo = tempfile.mkstemp(suffix=".xlsx")
        os.write(fd, b"questo non e' un file Excel")
        os.close(fd)
        errori = []
        app._errore = lambda titolo, dettaglio: errori.append(titolo)
        app._carica(cattivo)
        app.update()
        check(len(errori) == 1, f"errore segnalato all'utente: {errori}")
        check(app.config_linea is None, "lo stato resta pulito")
        os.unlink(cattivo)
    finally:
        chiudi(app)


def main():
    print("=" * 72)
    print("TEST DELL'INTERFACCIA GRAFICA")
    print("=" * 72)
    if not ambiente_grafico_disponibile():
        print("\nNessun ambiente grafico disponibile: test saltati.")
        return 0

    fd, linea = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    scrivi_modello(linea)
    try:
        test_apertura_e_proposta(linea)
        test_calcolo_automatico(linea)
        test_modifica_prelievo(linea)
        test_modifica_takt_e_carroponti(linea)
        test_modifica_impossibile(linea)
        test_proposta_modificabile(linea)
        test_file_illeggibile()
    finally:
        os.unlink(linea)

    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
