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
        test_file_illeggibile()
    finally:
        os.unlink(linea)

    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
