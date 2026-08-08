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

from matplotlib.backend_bases import MouseEvent

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


class Rotella:
    """Il minimo che serve a `_su_rotella` per fingere una rotellata: gli
    eventi veri di matplotlib arrivano solo da un puntatore in carne e ossa."""

    def __init__(self, assi, direzione, x, y, tasto=None):
        self.inaxes = assi
        self.button = direzione  # 'up' oppure 'down'
        self.key = tasto
        self.xdata = x
        self.ydata = y


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
        # Percorso intero, non il solo nome: serve a distinguere fra copie
        # dello stesso file in cartelle diverse.
        atteso = os.path.normpath(os.path.abspath(percorso_linea))
        check(
            str(app.etichetta_file["text"]) == atteso
            and app.title().endswith(atteso)
            and atteso in app.testo_riepilogo.get("1.0", "end"),
            f"percorso completo in barra, titolo e riepilogo ({atteso})",
        )
        check(
            str(app.btn_auto["state"]) == "normal"
            and str(app.btn_salva["state"]) == "disabled",
            "ora si puo' calcolare, ma non ancora salvare",
        )

        app._componi_da_zero()
        app.update()
        check(
            app.soluzione is not None and app.report is None,
            "'Componi da zero' da' subito un ciclogramma, senza verifica",
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
            len(app.dati.zones) == 2 and abs(app.soluzione.T - 127.39) < 1.0,
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


def test_modifica_tempi_in_vasca(percorso_linea):
    print("\n[4] modifica dei tempi in vasca su un ciclogramma calcolato")
    app = _app_risolta(percorso_linea)
    try:
        d = app.config_linea.data
        # Il punto della pagina unica: la soluzione del solutore si rilegge nei
        # termini in cui la si modifica a mano. Se questa lettura fosse
        # approssimata, la prima modifica sposterebbe anche cose non toccate.
        check(
            len(app.permanenze) == d.n_moves - 1
            and len(app.assegnazione) == d.n_moves
            and app.T_corrente is not None,
            f"il ciclogramma calcolato si legge come {len(app.permanenze)} tempi "
            f"in vasca + {len(app.assegnazione)} assegnazioni",
        )
        check(
            len(app.tabella_permanenze.get_children()) == d.n_moves - 1
            and len(app.tabella_assegnazione.get_children()) == d.n_moves,
            "le stesse tabelle del disegno a mano, gia' compilate",
        )

        def permanenze_disegnate():
            s = app.soluzione
            return [
                round(
                    s.actual_time[k]
                    - (s.actual_time[k - 1] + app.dati.loaded_leg_seconds(k - 1)),
                    2,
                )
                for k in range(1, app.dati.n_moves)
            ]

        # Ricomporre senza cambiare niente deve dare lo stesso ciclogramma: e'
        # la condizione che rende lecito avere una pagina sola.
        atteso = [round(app.permanenze[k], 2) for k in range(1, d.n_moves)]
        T_prima, ok_prima = app.soluzione.T, app.report.ok
        app._ricomponi("")
        app.update()
        check(
            permanenze_disegnate() == atteso
            and abs(app.soluzione.T - T_prima) < 1e-9
            and app.report.ok == ok_prima
            and not app.incoerenze,
            f"ricomporlo da li' restituisce lo stesso ciclogramma (T={T_prima:.2f}s, "
            f"verifica {'superata' if ok_prima else 'fallita'})",
        )

        prima_ok = app.report.ok
        permanenze_prima = permanenze_disegnate()
        istantanea = app._istantanea()
        app.permanenze[1] += 10.0
        app._ricomponi("prova", istantanea)
        app.update()
        check(
            permanenze_disegnate() != permanenze_prima,
            f"allungando un bagno di 10 s il ciclogramma cambia davvero: "
            f"{permanenze_prima} -> {permanenze_disegnate()}",
        )
        check(
            app.report is not None
            and len(app.tabella.get_children()) == len(app.report.violations),
            "e la verifica, gia' viva, si aggiorna da sola",
        )
        # Il ciclogramma ricomposto ha stato "MANUALE": va disegnato come
        # qualunque altro. Se il grafico si svuota, modificarlo non serve piu'
        # a niente -- e' proprio quello che si vuole vedere.
        check(
            len(app.assi.lines) > 0 and not app.assi.texts,
            f"il grafico continua a mostrare il ciclogramma "
            f"({len(app.assi.lines)} linee, stato {app.soluzione.status})",
        )

        # Niente viene mai rifiutato: anche una modifica impossibile si compone
        # e si guarda. E' il verificatore a dire che non va.
        istantanea2 = app._istantanea()
        app.permanenze = {k: 0.0 for k in range(1, d.n_moves)}
        app._ricomponi("prova impossibile", istantanea2)
        app.update()
        check(
            app.soluzione is not None and len(app.report.errors) > 0,
            f"una modifica impossibile si disegna lo stesso, e la verifica "
            f"segnala {len(app.report.errors)} errori",
        )

        app._annulla_modifica()
        app.update()
        app._annulla_modifica()
        app.update()
        check(
            permanenze_disegnate() == permanenze_prima and app.report.ok == prima_ok,
            "due annullamenti riportano esattamente alla soluzione calcolata",
        )

        # -- zoom ----------------------------------------------------------
        # Zoomare e poi vedersi resettare la vista al primo ritocco renderebbe
        # lo zoom inutile proprio quando serve: si ingrandisce per lavorare
        # sul dettaglio, e il ritocco arriva subito dopo.
        larghezza = lambda: app.assi.get_xlim()[1] - app.assi.get_xlim()[0]
        prima = larghezza()
        app._su_rotella(Rotella(app.assi, "up", 60.0, 5.0))
        app.update()
        check(
            larghezza() < prima * 0.95,
            f"la rotella zooma ({prima:.0f} -> {larghezza():.0f} s)",
        )

        zoomata = app.assi.get_xlim()
        app.permanenze[1] += 5.0
        app._ricomponi("prova zoom", app._istantanea())
        app.update()
        check(
            abs(app.assi.get_xlim()[0] - zoomata[0]) < 1e-6
            and abs(app.assi.get_xlim()[1] - zoomata[1]) < 1e-6,
            "e la vista ingrandita sopravvive al ridisegno",
        )

        app.barra_grafico.home()
        app.update()
        check(not app._zoom_utente, "'vista intera' rimette il grafico com'era")

        # -- mirino --------------------------------------------------------
        # La linea del mirino sta dentro gli assi, e ogni ridisegno comincia
        # con assi.clear(). Se non viene ricreata, il cursore funziona finche'
        # non si tocca niente e poi smette in silenzio: si prova DOPO una
        # modifica, non prima.
        def punta(t_secondi, y_metri):
            px, py = app.assi.transData.transform((t_secondi, y_metri))
            app.tela.callbacks.process(
                "motion_notify_event",
                MouseEvent("motion_notify_event", app.tela, px, py),
            )
            app.update()

        punta(80.0, 10.0)
        check(
            app._cursore is not None
            and app._cursore.linev.get_visible()
            and abs(app._cursore.linev.get_xdata()[0] - 80.0) < 0.5,
            "il mirino segue il puntatore",
        )
        app.permanenze[1] += 3.0
        app._ricomponi("prova mirino", app._istantanea())
        punta(150.0, 10.0)
        check(
            abs(app._cursore.linev.get_xdata()[0] - 150.0) < 0.5,
            "e continua a seguirlo dopo un ridisegno",
        )
    finally:
        chiudi(app)


def test_due_viste(percorso_linea):
    print("\n[5] due viste dello stesso ciclogramma, stessi comandi")
    app = _app_risolta(percorso_linea)
    try:
        d = app.config_linea.data
        check(app.vista == "ciclogramma", "si parte dal ciclogramma")
        linee_ciclogramma = len(app.assi.lines)
        titolo_ciclogramma = app.assi.get_title()

        app.var_vista.set("pettine")
        app._cambia_vista()
        app.update()
        check(
            app.vista == "pettine"
            and "Pettine" in app.assi.get_title()
            and len(app.assi.lines) > linee_ciclogramma,
            f"il pettine mostra i 10 pezzi ({len(app.assi.lines)} linee contro "
            f"{linee_ciclogramma})",
        )
        # I comandi non cambiano con la vista: e' tutto il punto della pagina
        # unica. Una modifica fatta guardando il pettine e' la stessa modifica.
        istantanea = app._istantanea()
        app.permanenze[1] += 20.0
        app._ricomponi("prova dal pettine", istantanea)
        app.update()
        check(
            app.soluzione is not None and app.vista == "pettine",
            "si modifica dal pettine con gli stessi comandi",
        )
        app.var_vista.set("ciclogramma")
        app._cambia_vista()
        app.update()
        check(
            app.vista == "ciclogramma"
            and app.assi.get_title() == titolo_ciclogramma,
            "e tornando al ciclogramma la modifica c'e'",
        )
        app._annulla_modifica()
        app.update()
    finally:
        chiudi(app)


def test_takt_e_carroponti(percorso_linea):
    print("\n[6] takt time, numero di carroponti, riottimizzazione")
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

        # Lo spinbox ridistribuisce subito, senza risolvere: deve vedersi.
        n0 = app.n_carroponti
        app.var_carroponti.set(str(n0 + 1))
        app._cambia_carroponti()
        app.update()
        check(
            app.n_carroponti == n0 + 1
            and len(set(app.assegnazione.values())) == n0 + 1,
            f"lo spinbox ridistribuisce subito le mosse su {app.n_carroponti} "
            f"carroponti, senza risolvere",
        )

        # Il pulsante invece fa lavorare il solutore su quel numero.
        app._modifica_numero_carroponti()
        check(pompa(app), "'Ottimizza con questi carroponti' termina")
        check(
            len(app.dati.zones) == n0 + 1 and app.report.ok,
            f"suddivisione ottimizzata per {len(app.dati.zones)} carroponti, "
            f"verificata (T={app.soluzione.T:.2f}s)",
        )
    finally:
        chiudi(app)


def test_composizione_da_zero(percorso_linea):
    print("\n[7] composizione da zero: stessa pagina, verifica su richiesta")
    from interfaccia import Applicazione
    import manuale as m

    app = Applicazione(percorso_linea)
    try:
        for _ in range(50):
            app.update()
            if app.config_linea is not None:
                break
            time.sleep(0.02)
        app._componi_da_zero()
        app.update()
        d = app.config_linea.data

        check(
            len(app.permanenze) == d.n_moves - 1
            and all(
                app.permanenze[k] == d.route[k].dwell_min
                for k in range(1, d.n_moves)
            ),
            "si parte dai tempi in vasca minimi di processo",
        )
        check(
            app.report is None and not app.verifica_viva,
            "nessuna verifica finche' non la si chiede",
        )

        pettine = m.pettine(d, app.T_corrente, app.permanenze)
        check(len(pettine) == 10, f"il pettine ha {len(pettine)} scalinate")
        scarti = {
            round(pettine[p + 1][0].t_start - pettine[p][0].t_start, 6)
            for p in range(len(pettine) - 1)
        }
        check(
            scarti == {round(app.T_corrente, 6)},
            f"distanziate di un takt time esatto ({app.T_corrente:.2f} s)",
        )

        # -- cambiare un tempo in vasca sposta le scalinate ------------------
        prima = m.catena_pezzo(d, app.permanenze)
        app.permanenze[1] += 40.0
        app._ricomponi("prova")
        app.update()
        dopo = m.catena_pezzo(d, app.permanenze)
        check(
            abs(dopo[2] - prima[2] - 40.0) < 1e-6 and dopo[0] == prima[0],
            f"allungando il bagno di 40 s la scalinata si sposta da quel punto "
            f"in poi ({prima[2]:.1f} -> {dopo[2]:.1f} s)",
        )

        # -- un'assegnazione che farebbe scavalcare i carroponti -------------
        prova = dict(app.assegnazione)
        prova[0] = 1
        prova[d.n_moves - 1] = 0
        motivo = m.perche_non_va(d, prova)
        check(
            motivo is not None and "scavalcarsi" in motivo,
            f"scavalcamento riconosciuto: \"{(motivo or '')[:70]}...\"",
        )

        # -- una composizione impossibile non blocca: la si vede -------------
        for k in range(d.n_moves):
            app.assegnazione[k] = 0
        app.permanenze = {k: 0.0 for k in range(1, d.n_moves)}
        app._ricomponi("prova impossibile")
        app.update()
        check(
            app.soluzione is not None and len(app.incoerenze) > 0,
            f"con un solo carroponte e nessuna sosta il disegno esiste comunque, "
            f"con {len(app.incoerenze)} incoerenze descritte",
        )
        check(app.report is None, "e ancora nessuna verifica: non l'ho chiesta")

        # -- il report arriva quando lo si chiede, e poi resta vivo ----------
        app._verifica_adesso()
        app.update()
        check(
            app.report is not None and len(app.report.errors) > 0,
            f"'Verifica adesso' produce il report ({len(app.report.errors)} errori)",
        )
        n_errori = len(app.report.errors)
        app.permanenze[1] = d.route[1].dwell_min
        app._ricomponi("dopo la verifica")
        app.update()
        check(
            app.report is not None and len(app.report.errors) != n_errori,
            "e da li' in poi si aggiorna da sola a ogni modifica "
            f"({n_errori} -> {len(app.report.errors)} errori)",
        )
    finally:
        chiudi(app)


def test_da_zero_poi_automatico(percorso_linea):
    print("\n[8] dalla composizione a mano si torna al calcolo automatico")
    from interfaccia import Applicazione

    app = Applicazione(percorso_linea)
    try:
        for _ in range(50):
            app.update()
            if app.config_linea is not None:
                break
            time.sleep(0.02)
        app._componi_da_zero()
        app.update()
        check(app.origine == "composto da zero", "composizione da zero avviata")
        app._calcola_automatico()
        check(pompa(app), "il calcolo automatico parte e termina")
        check(
            app.report is not None and app.report.ok,
            "e la soluzione automatica e' verificata",
        )
        check(
            not app.modificato and app.origine.startswith("calcolo automatico"),
            f"il riepilogo dice da dove viene: \"{app.origine}\"",
        )
        check(len(app.incoerenze) == 0, "nessuna incoerenza residua")
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
        test_modifica_tempi_in_vasca(linea)
        test_due_viste(linea)
        test_takt_e_carroponti(linea)
        test_composizione_da_zero(linea)
        test_da_zero_poi_automatico(linea)
        test_file_illeggibile()
    finally:
        os.unlink(linea)

    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
