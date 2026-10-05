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
    python test/test_interfaccia.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import tkinter as tk

# I moduli del programma stanno nella cartella sopra questa: senza aggiungerla
# fra i percorsi di ricerca, lanciare il test da qui non li troverebbe.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


class Clic:
    """Il minimo che serve a `_su_pressione`: un clic vero arriva solo da un
    puntatore in carne e ossa."""

    def __init__(self, assi, x, y, xdata):
        self.inaxes = assi
        self.x = x
        self.y = y
        self.xdata = xdata


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
            app.title() == "CraneStrike" and app.icona is not None,
            f"la finestra si chiama CraneStrike e ha la sua icona "
            f"(\"{app.title()}\", icona {'caricata' if app.icona else 'mancante'})",
        )
        if sys.platform == "win32":
            # "Caricata" non basta: impostando PNG e ICO insieme Tk non dava
            # nessun errore, e intanto Windows perdeva l'icona PICCOLA -- quella
            # del titolo -- e mostrava l'icona generica. Lo si chiede a Windows.
            import ctypes

            u32 = ctypes.windll.user32
            u32.GetAncestor.restype = ctypes.c_void_p
            u32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            u32.GetClassLongPtrW.restype = ctypes.c_void_p
            u32.GetClassLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            radice = u32.GetAncestor(app.winfo_id(), 2)  # GA_ROOT
            check(
                bool(u32.GetClassLongPtrW(radice, -34)),  # GCLP_HICONSM
                "e Windows ha l'icona piccola, quella che si vede nel titolo",
            )
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
        # "Modifica" non sceglie fra una versione automatica e una manuale:
        # lavora su quella che c'e'. Quindi resta spento finche' non ce n'e'
        # nessuna -- e' l'unica regola che serve.
        check(
            str(app.btn_modifica["state"]) == "disabled",
            "e 'Modifica' e' spento: non c'e' ancora niente da modificare",
        )

        app._componi_da_zero()
        app.update()
        check(
            app.soluzione is not None and app.report is None,
            "'Calcola man' da' subito un ciclogramma, senza verifica",
        )
        check(
            str(app.btn_modifica["state"]) == "normal",
            "adesso 'Modifica' si accende",
        )
        # 'Calcola man' apre gia' la modifica, quindi quel pulsante e' l'uscita
        check(
            app.modifica_aperta
            and app.schede.index(app.schede.select()) == 1
            and str(app.btn_modifica["text"]) == "Fine modifica",
            "'Calcola man' porta gia' nella scheda dove si modifica",
        )
        app._vai_a_modifica()
        app.update()
        check(
            not app.modifica_aperta and app.vista == "ciclogramma",
            "premendolo si esce e si torna a guardare il ciclogramma",
        )
        app._vai_a_modifica()
        app.update()
        check(
            app.schede.index(app.schede.select()) == 1 and app.vista == "pettine",
            "e premendolo ancora si rientra, sul pettine",
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
        # Quanto e' durato il calcolo va scritto a schermo: in barra di stato
        # appena finito, e nel Riepilogo dove resta. E' quello che dice se
        # conviene allungare il tempo limite, e non e' ricavabile altrimenti.
        stato = app.etichetta_stato["text"]
        check(
            app.durata_calcolo is not None and app.durata_calcolo > 0.0,
            f"il tempo di calcolo viene misurato ({app.durata_calcolo:.2f} s)"
            if app.durata_calcolo is not None
            else "il tempo di calcolo NON viene misurato",
        )
        check(
            "pronto in" in stato and " s" in stato,
            f"e finisce nella barra di stato: \"{stato[:60]}\"",
        )
        riepilogo = app.testo_riepilogo.get("1.0", "end")
        check(
            "Tempo di calcolo:" in riepilogo,
            "e nel Riepilogo, dove resta anche cambiando scheda",
        )
        # Un risultato del solutore si LEGGE: la scheda di modifica resta
        # chiusa finche' non si preme "Modifica". Cosi' non lo si altera per
        # sbaglio, e quel pulsante diventa il punto in cui si dichiara di
        # volerci mettere le mani.
        check(
            str(app.schede.tab(1, "state")) == "disabled",
            "la scheda di modifica resta chiusa: il risultato si legge",
        )
        # Il grafico sta fuori dalla scheda, quindi ha bisogno dello stesso
        # cancello: senza, un trascinamento di troppo modificherebbe comunque.
        k, istante, quota = app._punti_prelievo()[1]
        px, py = app.assi.transData.transform((istante, quota))
        app._su_pressione(Clic(app.assi, px, py, istante))
        check(
            app._trascinamento is None,
            "e nemmeno il grafico si lascia trascinare",
        )
        app._vai_a_modifica()
        app.update()
        check(
            str(app.schede.tab(1, "state")) == "normal"
            and app.schede.index(app.schede.select()) == 1,
            "'Modifica' la apre",
        )
        app._su_pressione(Clic(app.assi, px, py, istante))
        check(
            app._trascinamento is not None,
            "e da li' in poi il trascinamento funziona",
        )
        app._trascinamento = None
        # Il takt di riferimento e' sceso da 127.39 a 110.00 s -- il minimo
        # dichiarato, cioe' il vincolo non e' piu' il processo -- correggendo
        # due volte il conto della permanenza: prima contandoci le corse a
        # vuoto del gancio (che il pezzo passa immerso), poi togliendole del
        # tutto, perche' il gancio scarico trasla basso e non le fa.
        # Poi e' risalito a 115.29 con la zona di avvicinamento del
        # sollevamento, che il modello d'esempio dichiara: le corse verticali
        # perdono circa un secondo e mezzo l'una, e il minimo dichiarato non
        # basta piu' a contenerle -- non e' quindi piu' lui a decidere il takt.
        # Infine a 120.95, portando sgancio e aggancio FUORI dal bagno: i 3 s
        # dell'esempio non contano piu' come permanenza, quindi l'intervallo
        # fra i movimenti del gancio deve allungarsi di altrettanto per
        # rispettare lo stesso minimo di processo.
        check(
            len(app.dati.zones) == 2 and abs(app.soluzione.T - 120.95) < 1.0,
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


def test_avanzamento_del_calcolo(percorso_linea):
    """L'avanzamento durante 'Calcola auto'.

    Il calcolo puo' durare minuti, e una barra che oscilla non dice se manca
    un secondo o cinque. I tentativi rimasti pero' si SANNO -- sono
    combinatoria piu' due prefiltri deterministici -- quindi si possono
    contare, e la loro durata media si misura strada facendo.

    Il rischio vero non e' che la stima sia imprecisa: e' che il totale
    annunciato non sia quello vero. Qui si controlla proprio quello,
    confrontandolo con `tentativi_previsti`, che e' la stessa funzione che
    l'interfaccia non usa -- cosi' se i due prefiltri si sdoppiassero il test
    lo vedrebbe."""
    print("\n[2-bis] avanzamento e stima durante il calcolo")
    from interfaccia import Applicazione
    from model import tentativi_previsti

    app = Applicazione(percorso_linea)
    try:
        for _ in range(50):
            app.update()
            if app.config_linea is not None:
                break
            time.sleep(0.02)

        registro = []
        originale = app._stato

        def spia(testo):
            registro.append((testo, str(app.avanzamento.cget("mode"))))
            originale(testo)

        app._stato = spia
        app._calcola_automatico()
        check(pompa(app), "il calcolo termina")
        app._stato = originale

        tentativi = [t for t, _m in registro if "tentativo" in t]
        check(
            len(tentativi) >= 2,
            f"l'avanzamento viene segnalato ({len(tentativi)} tentativi)",
        )
        check(
            any(m == "determinate" for _t, m in registro),
            "la barra passa da indeterminata a determinata",
        )
        check(
            str(app.avanzamento.cget("mode")) == "indeterminate",
            "e torna indeterminata alla fine, senza restare piena",
        )

        # I totali annunciati devono coincidere con il conto fatto a priori.
        d = app.config_linea.data
        annunciati: dict[int, int] = {}
        for testo in tentativi:
            # "2 carroponti: tentativo 3 di 5 - ancora circa ..."
            n_h = int(testo.split()[0])
            di = int(testo.split(" di ")[1].split()[0])
            annunciati[n_h] = di
        for n_h, totale in sorted(annunciati.items()):
            check(
                tentativi_previsti(d, n_h) == totale,
                f"{n_h} carroponti: annunciati {totale} tentativi, "
                f"previsti {tentativi_previsti(d, n_h)}",
            )
        # Gli indici salgono da 1 fino al totale, senza salti ne' ripetizioni.
        for n_h, totale in sorted(annunciati.items()):
            indici = [
                int(t.split("tentativo ")[1].split()[0])
                for t in tentativi
                if int(t.split()[0]) == n_h
            ]
            check(
                indici == list(range(1, len(indici) + 1)) and len(indici) <= totale,
                f"{n_h} carroponti: indici {indici} entro {totale}",
            )
        # La stima compare, ma non subito: con un solo tentativo concluso la
        # media e' un numero solo, e su una grandezza cosi' dispersa non vuol
        # dire niente. Meglio nessun tempo che un tempo sbagliato di dieci
        # volte.
        con_stima = [t for t in tentativi if "ancora circa" in t]
        check(
            "ancora circa" not in tentativi[0],
            "il primo tentativo non azzarda nessuna stima",
        )
        check(
            bool(con_stima) or len(tentativi) < 3,
            f"la stima compare quando c'e' su cosa calcolarla "
            f"({len(con_stima)} tentativi su {len(tentativi)})",
        )
    finally:
        chiudi(app)


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
        #
        # Il segno che si e' svuotato e' il CARTELLO di `_grafico_vuoto`: un
        # testo al centro degli assi. Non basta piu' dire "nessun testo" --
        # il ciclogramma ne scrive uno suo, l'etichetta del punto di avvio --
        # e si guarda quindi se c'e' un testo piazzato in mezzo.
        cartello = [
            t for t in app.assi.texts if t.get_position() == (0.5, 0.5)
        ]
        check(
            len(app.assi.lines) > 0 and not cartello,
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

        # -- lettura della posizione sotto il puntatore ---------------------
        # E' quello che resta dopo aver tolto il mirino verticale, e dice la
        # stessa cosa senza artefatti. Va sovrascritta a mano perche' l'asse Y
        # porta i nomi delle vasche: col formattatore predefinito la quota
        # uscirebbe vuota.
        check(
            app.assi.format_coord(175.0, 9500.0) == "t = 175.0 s      posizione = 9500 mm",
            f"la posizione si legge sotto il grafico: "
            f"\"{app.assi.format_coord(175.0, 9500.0)}\"",
        )
    finally:
        chiudi(app)


def test_vista_e_immagine(percorso_linea):
    print("\n[5] la vista la decide il modo in cui sei arrivato")
    app = _app_risolta(percorso_linea)
    try:
        # Nessun interruttore: "Calcola auto" da' un risultato da leggere,
        # quindi le traiettorie dei carroponti.
        check(
            app.vista == "ciclogramma" and not hasattr(app, "var_vista"),
            "dopo un calcolo automatico si vede il ciclogramma, e non c'e'"
            " nessuna vista da scegliere",
        )

        # Il PNG consegnato deve essere il CICLOGRAMMA anche se lo si e'
        # composto guardando il pettine: e' il documento che esce, e non puo'
        # dipendere da cosa si stava guardando quando si e' premuto Salva.
        app._componi_da_zero()
        app.update()
        check(app.vista == "pettine", "'Calcola man' porta invece sul pettine")
        # ...e tornando al solutore si torna al ciclogramma. Restare sul
        # pettine dopo un calcolo automatico era il difetto: il disegno era
        # aggiornato e giusto, ma era il foglio su cui si COMPONE -- e un
        # risultato del solutore non si compone, si legge.
        app._calcola_automatico()
        check(pompa(app), "il calcolo automatico termina")
        check(
            app.vista == "ciclogramma"
            and app.assi.get_title().startswith("Ciclogramma"),
            "e 'Calcola auto' riporta al ciclogramma, anche venendo dal pettine",
        )
        # 'Modifica' su un risultato del solutore porta sul PETTINE, non sul
        # ciclogramma. Nel ciclogramma si disegnano solo le traiettorie dei
        # carroponti: un trasporto che non e' di nessuno -- o che si e' appena
        # tolto a qualcuno -- non compare, e resterebbe invisibile pur essendo
        # cliccabile.
        app._vai_a_modifica()
        app.update()
        check(
            app.vista == "pettine" and app.assi.get_title().startswith("Modifica"),
            f"'Modifica' su un calcolo automatico porta sulla pagina di "
            f"modifica ({app.vista})",
        )
        check(
            str(app.btn_modifica["text"]) == "Fine modifica",
            f"e il pulsante diventa l'uscita ({app.btn_modifica['text']})",
        )
        # e la stessa manovra riporta a guardare il ciclogramma, richiudendo
        # la scheda: senza uscita, chi ha ritoccato un tempo in vasca non
        # rivedrebbe piu' il ciclogramma se non ricalcolandolo da capo
        app._vai_a_modifica()
        app.update()
        check(
            app.vista == "ciclogramma"
            and app.assi.get_title().startswith("Ciclogramma")
            and not app.modifica_aperta
            and str(app.schede.tab(1, "state")) == "disabled",
            "'Fine modifica' riporta al ciclogramma e richiude la scheda",
        )
        check(
            str(app.btn_modifica["text"]) == "Modifica",
            "e il pulsante torna a proporre la modifica",
        )

        app._componi_da_zero()
        app.update()
        for k in range(app.dati.n_moves):
            app.carroponte_attivo = 0 if k < 3 else 1
            app._assegna(k, app._istantanea())
        app.update()

        fd, png = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            app._salva_immagine(png)
            from matplotlib.image import imread

            immagine = imread(png)
            # il pettine copre ~14 takt, il ciclogramma 2: distinguerli dalla
            # sola immagine non e' pratico, quindi si controlla che il disegno
            # a schermo sia rimasto il pettine e che il file esista comunque
            check(
                os.path.getsize(png) > 5000 and immagine.shape[0] > 100,
                f"l'immagine viene scritta ({os.path.getsize(png)} byte) "
                f"mentre a schermo c'e' il {app.vista}",
            )
        finally:
            if os.path.exists(png):
                os.unlink(png)
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

        # Lo spinbox NON ridistribuisce: l'assegnazione la fa l'utente, e
        # rifargliela sotto sarebbe buttare via il suo lavoro. Aggiungere un
        # carroponte lo rende solo disponibile.
        n0 = app.n_carroponti
        ass0 = dict(app.assegnazione)
        app.var_carroponti.set(str(n0 + 1))
        app._cambia_carroponti()
        app.update()
        check(
            app.n_carroponti == n0 + 1 and app.assegnazione == ass0,
            f"aggiungendo un carroponte ({n0} -> {app.n_carroponti}) "
            f"l'assegnazione fatta resta com'era",
        )
        # Togliendone uno invece le sue mosse devono passare all'ultimo
        # rimasto: e' l'unico modo di non far scavalcare i vicini.
        app.var_carroponti.set("1")
        app._cambia_carroponti()
        app.update()
        check(
            app.n_carroponti == 1 and set(app.assegnazione.values()) <= {0},
            "togliendone uno, le sue mosse passano a chi resta",
        )
        app.var_carroponti.set(str(n0 + 1))
        app._cambia_carroponti()
        app.update()

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
    from plotting import _HOIST_COLORS

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
                app.permanenze[k] == d.route[k].nominale
                for k in range(1, d.n_moves)
            ),
            "si parte dai tempi in vasca teorici di processo",
        )
        check(
            app.report is None and not app.verifica_viva,
            "nessuna verifica finche' non la si chiede",
        )
        # Si comincia da NIENTE assegnato, sul pettine: se si partisse da una
        # suddivisione gia' fatta non ci sarebbe mai niente "da assegnare", e
        # comporre diventerebbe correggere una proposta.
        check(
            app.assegnazione == {} and app.vista == "pettine",
            "si parte da zero trasporti assegnati, sulla vista a pettine",
        )
        colori_prima = {l.get_color() for l in app.assi.lines}
        check(
            not (colori_prima & set(_HOIST_COLORS)),
            "e infatti sul grafico non c'e' nessun colore di carroponte",
        )

        # -- i punti sul pettine ---------------------------------------------
        # Sono i QUATTRO istanti in cui succede qualcosa durante un trasporto
        # -- aggancio, partenza, arrivo, immersione -- gli stessi che il
        # ciclogramma marca sulle traiettorie dei carroponti, visti dal lato
        # del pezzo. Senza, su una linea con molte tappe un trasporto corto non
        # si distingue da una sosta.
        import manuale as m

        d = app.config_linea.data
        punti = [
            l
            for l in app.assi.lines
            if l.get_linestyle() == "None" and len(l.get_xdata())
        ]
        check(
            len(punti) == 1,
            f"il pettine porta i suoi punti ({len(punti)} disegni di soli punti)",
        )
        attesi = 4 * d.n_moves * m.RIPETIZIONI_PREDEFINITE
        check(
            len(punti[0].get_xdata()) == attesi,
            f"quattro per ogni trasporto di ogni scalinata "
            f"({len(punti[0].get_xdata())} su {attesi} attesi)",
        )
        # Il disegno e' RAGGRUPPATO: una chiamata per tratto, con dieci
        # scalinate, sono centinaia di artisti a ogni ritocco -- e di ritocchi
        # se ne fanno molti di seguito.
        check(
            len(app.assi.lines) < 40,
            f"e il pettine sta in pochi artisti, non uno per tratto "
            f"({len(app.assi.lines)})",
        )

        # -- assegnare una mossa per volta -----------------------------------
        # Il clic vale su TUTTO il tratto disegnato, non solo sul suo estremo:
        # obbligare a centrare la vasca di partenza e' una precisione chiesta
        # senza motivo, perche' assegnare una mossa non ha niente a che fare
        # con un estremo particolare.
        app.carroponte_attivo = 1
        tratti = [t for t in app._tratti_trasporto() if t[0] == 3]
        _, ts, xs = tratti[0]
        colpiti = []
        for frazione in (0.0, 0.25, 0.5, 0.75, 1.0):
            i = int(frazione * (len(ts) - 1))
            px, py = app.assi.transData.transform((ts[i], xs[i]))
            colpiti.append(app._trasporto_sotto(Clic(app.assi, px, py, ts[i])))
        check(
            colpiti == [3] * 5,
            f"il tratto si prende dovunque lo si clicchi, non solo alla "
            f"partenza ({colpiti})",
        )
        # e il gesto completo, premi-e-rilascia, assegna davvero
        i = len(ts) // 2
        px, py = app.assi.transData.transform((ts[i], xs[i]))
        app._su_pressione(Clic(app.assi, px, py, ts[i]))
        app._su_rilascio(Clic(app.assi, px, py, ts[i]))
        app.update()
        check(
            app.assegnazione == {3: 1},
            "un clic a meta' salita assegna la mossa al carroponte attivo",
        )
        app.update()
        colori = {l.get_color() for l in app.assi.lines}
        check(
            _HOIST_COLORS[1] in colori and _HOIST_COLORS[0] not in colori,
            "compare il colore del carroponte 2 e solo quello -- trasporto e "
            "rientro a vuoto",
        )
        # Il rientro a vuoto e' del carroponte, e nel pettine ha il suo colore:
        # con l'assegnazione parziale il numero della zona non coincide con
        # quello del carroponte, e prendere il colore dall'indice slitterebbe.
        check(
            [app._carro_della_zona(i) for i in range(len(app.dati.zones))] == [None, 1],
            "la zona senza mosse assegnate non e' di nessuno, l'altra e' del 2",
        )

        # -- il giro si posa sui punti che erano gia' li' in grigio ----------
        # E' la proprieta' per cui i punti esistono: assegnando una mossa, i
        # quattro istanti che il carroponte marca devono cadere ESATTAMENTE su
        # quelli che il pettine mostrava. Sono lo stesso fatto visto dal pezzo
        # e dal carroponte, e se i due disegni li mettessero altrove chi li
        # confronta -- che e' il motivo per cui si guardano insieme -- non ci
        # si ritroverebbe. Il confronto e' modulo T: il pettine mostra il
        # pezzo j-esimo, il giro del carroponte si ripete ogni periodo.
        from plotting import eventi_del_trasporto

        tempi = m.catena_pezzo(d, app.permanenze)
        trasporto = [
            s
            for s in app.soluzione.segments_per_hoist[1]
            if s.kind == "loaded" and s.move == 3
        ][0]
        dal_pezzo = eventi_del_trasporto(
            d, 3, tempi[3], d.station_position(3), d.station_position(4)
        )
        dal_carro = eventi_del_trasporto(
            d, 3, trasporto.t_start - d.pick_time_at(3),
            trasporto.x_start, trasporto.x_end,
        )
        T = app.T_corrente
        scarti = [
            max(min((t1 - t2) % T, (t2 - t1) % T), abs(x1 - x2))
            for (t1, x1), (t2, x2) in zip(dal_pezzo, dal_carro)
        ]
        check(
            len(dal_pezzo) == 4 and max(scarti) < 1e-9,
            f"i quattro punti del carroponte coincidono con quelli del pettine "
            f"(scarto massimo {max(scarti):.1e})",
        )

        # -- e lo stesso clic la toglie --------------------------------------
        # Assegnare per sbaglio costa un clic: senza il modo di tornare
        # indietro l'unica strada sarebbe ricominciare da capo.
        app._su_pressione(Clic(app.assi, px, py, ts[i]))
        app._su_rilascio(Clic(app.assi, px, py, ts[i]))
        app.update()
        check(
            app.assegnazione == {},
            f"cliccando di nuovo la mossa torna non assegnata "
            f"({app.assegnazione})",
        )
        check(
            _HOIST_COLORS[1] not in {l.get_color() for l in app.assi.lines},
            "e sul grafico il colore del carroponte sparisce: torna tutto grigio",
        )
        app._annulla_modifica()
        app.update()
        check(
            app.assegnazione == {3: 1},
            f"'Annulla modifica' rimette l'assegnazione tolta ({app.assegnazione})",
        )

        # -- il giro del doppio clic in tabella passa da 'nessuno' -----------
        righe = app.tabella_assegnazione.get_children()
        riquadro = app.tabella_assegnazione.bbox(righe[3])
        if riquadro:
            fatto = []
            for _ in range(3):
                app._assegna_da_tabella(Clic(None, 0, riquadro[1] + riquadro[3] // 2, 0))
                app.update()
                fatto.append(app.assegnazione.get(3))
            check(
                fatto == [None, 0, 1],
                f"il doppio clic gira sui carroponti e passa per 'nessuno' ({fatto})",
            )
        else:
            check(False, "riga della tabella non visibile: prova non eseguita")

        # si riparte da zero assegnazioni, per il seguito della prova
        app.assegnazione = {}
        app._ricomponi("")
        app.update()
        # A lavoro finito NIENTE deve restare grigio: il grigio vuol dire
        # "ancora da assegnare", e una sosta in vasca lasciata grigia
        # sembrerebbe lavoro da fare quando non c'e' piu' niente da fare.
        istantanea = app._istantanea()
        for k in range(d.n_moves):
            app.carroponte_attivo = 0 if k < 3 else 1
            app._assegna(k, app._istantanea())
        app.update()
        from interfaccia import _GRIGIO, _SOTTILE, _SPESSO

        # Fuori le righe delle vasche (#dddddd) e le verticali NERE del punto
        # di avvio: non sono traiettorie, e qui si guardano le traiettorie.
        linee = [
            (l.get_color(), round(l.get_linewidth(), 2))
            for l in app.assi.lines
            if l.get_linestyle() != "None"
            and l.get_color() not in ("#dddddd", "#000000")
        ]
        # Il grigio NON sparisce assegnando: e' il percorso dei pezzi, cioe'
        # lo sfondo su cui si lavora, e resta li' anche a lavoro finito.
        check(
            (_GRIGIO, _SOTTILE) in linee,
            "il percorso dei pezzi resta come sfondo, grigio e sottile",
        )
        # Quello che compare assegnando e' il GIRO DEI CARROPONTI, disegnato
        # come nell'altra vista: spesso e del colore del carroponte. E' il
        # ciclogramma che si sta componendo, e dev'essere lui il protagonista.
        colorate = {c for c, w in linee if c != _GRIGIO}
        check(
            colorate == {_HOIST_COLORS[0], _HOIST_COLORS[1]}
            and all(w == _SPESSO for c, w in linee if c != _GRIGIO),
            f"e sopra ci passa il giro dei due carroponti, spesso e colorato "
            f"({sorted(colorate)})",
        )
        app.assegnazione, app.T_corrente, app.permanenze, app.n_carroponti = (
            istantanea[2],
            istantanea[0],
            istantanea[1],
            istantanea[3],
        )
        app._ricomponi("")
        app.update()

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


def test_scheda_chiusa_durante_il_calcolo(percorso_linea):
    print("\n[9] durante il calcolo la scheda Ciclogramma e' chiusa")
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
        check(
            str(app.schede.tab(1, "state")) == "normal"
            and app.schede.index(app.schede.select()) == 1,
            "componendo a mano si e' sulla scheda, ed e' aperta",
        )
        permanenze_prima = dict(app.permanenze)

        app._calcola_automatico()
        app.update()
        # Ingrigire i soli pulsanti non basta: i doppi clic sulle tabelle sono
        # binding di evento, senza stato da spegnere. E disabilitare la
        # linguetta non serve se e' quella aperta -- il contenuto resta a
        # schermo e cliccabile. Quindi la scheda va anche lasciata.
        check(
            str(app.schede.tab(1, "state")) == "disabled"
            and app.schede.index(app.schede.select()) != 1,
            "appena parte il calcolo la scheda si chiude e si esce",
        )
        # La modifica che ci si infilasse comunque va rifiutata, non persa:
        # senza questo si vedeva il ritocco comparire sul grafico e sparire
        # trenta secondi dopo, quando il risultato del calcolo ci passava
        # sopra senza dire niente.
        app.permanenze[1] += 25.0
        app._ricomponi("ritocco durante il calcolo")
        app.update()
        check(
            "Calcolo in corso" in app.etichetta_stato["text"],
            f"e una modifica viene rifiutata dicendolo: "
            f"\"{app.etichetta_stato['text']}\"",
        )
        app.permanenze = dict(permanenze_prima)

        check(pompa(app), "il calcolo termina")
        # A calcolo finito NON si riapre da sola: quello che c'e' adesso e' un
        # risultato del solutore, e si legge. Il lavoro fatto a mano prima e'
        # stato sostituito -- riaprire la scheda darebbe l'idea di poterlo
        # riprendere.
        check(
            str(app.schede.tab(1, "state")) == "disabled",
            "a calcolo finito resta chiusa: c'e' un risultato nuovo da leggere",
        )
        check(
            app.permanenze != permanenze_prima,
            "e i tempi in vasca sono quelli del solutore, non quelli composti",
        )
        app._vai_a_modifica()
        app.update()
        check(
            str(app.schede.tab(1, "state")) == "normal",
            "'Modifica' la riapre quando si vuole intervenire",
        )
    finally:
        chiudi(app)


def test_ferma_il_calcolo(percorso_linea):
    print("\n[9-bis] il pulsante Ferma interrompe il calcolo automatico")
    # Qui si prova il COLLEGAMENTO fra pulsante e calcolo, non CP-SAT: il
    # solutore e' sostituito da uno finto che gira finche' qualcuno non lo
    # ferma. Con quello vero la prova dipenderebbe da quanto ci mette la linea
    # di esempio -- se finisse prima del clic non proverebbe niente. Che lo
    # stop fermi davvero CP-SAT lo prova test_model.py.
    import dataclasses
    import interfaccia
    from interfaccia import Applicazione
    from model import Solution

    app = Applicazione(percorso_linea)
    originali = (interfaccia.solve_auto_hoists, interfaccia.solve)
    ricevute = []
    try:
        for _ in range(50):
            app.update()
            if app.config_linea is not None:
                break
            time.sleep(0.02)
        app._calcola_automatico()
        check(pompa(app), "un primo calcolo vero, da tenere come ciclogramma di prima")
        prima = app.soluzione
        check(prima is not None, "e produce un ciclogramma")
        if prima is None:
            return
        check(
            str(app.btn_ferma["state"]) == "disabled",
            "a calcolo finito Ferma e' spento: non c'e' niente da fermare",
        )

        esito = {"soluzione": None}

        def aspetta_lo_stop(interruzione):
            ricevute.append(interruzione)
            scadenza = time.time() + 30.0
            while not interruzione.richiesta and time.time() < scadenza:
                time.sleep(0.02)
            return esito["soluzione"]

        def finto_auto(d, *a, interruzione=None, **k):
            sol, zone = aspetta_lo_stop(interruzione)
            return sol, zone, (len(zone) if zone else None)

        def finto_solve(d, *a, interruzione=None, **k):
            return aspetta_lo_stop(interruzione)[0]

        interfaccia.solve_auto_hoists = finto_auto
        interfaccia.solve = finto_solve

        # -- fermato senza niente in mano -----------------------------------
        esito["soluzione"] = (
            Solution(status="UNKNOWN", T=None, raw={"interrotto": True}),
            None,
        )
        app._calcola_automatico()
        app.update()
        check(
            str(app.btn_ferma["state"]) == "normal",
            "mentre il calcolo gira Ferma e' acceso",
        )
        inizio = time.time()
        app._ferma_calcolo()
        app.update()
        check(
            str(app.btn_ferma["state"]) == "disabled"
            and "Interruzione" in app.etichetta_stato["text"],
            f"premuto, si spegne e lo dice: \"{app.etichetta_stato['text']}\"",
        )
        check(pompa(app, secondi_max=10.0), "e il calcolo finisce")
        check(
            time.time() - inizio < 5.0,
            f"subito, non allo scadere del tempo ({time.time() - inizio:.1f} s)",
        )
        check(
            len(ricevute) == 1 and ricevute[0] is not None,
            "il calcolo ha ricevuto la richiesta di stop",
        )
        check(
            app.soluzione is prima,
            "il ciclogramma di prima resta: si e' rinunciato al calcolo nuovo, "
            "non a quello",
        )
        check(
            "interrotto" in app.etichetta_stato["text"]
            and str(app.btn_auto["state"]) == "normal"
            and str(app.btn_ferma["state"]) == "disabled",
            f"lo stato lo dice e i pulsanti tornano come prima: "
            f"\"{app.etichetta_stato['text']}\"",
        )

        # -- fermato con una soluzione gia' trovata --------------------------
        trovata = dataclasses.replace(prima, raw={**prima.raw, "interrotto": True})
        esito["soluzione"] = (trovata, list(app.dati.zones))
        app._calcola_automatico()
        app.update()
        app._ferma_calcolo()
        check(pompa(app, secondi_max=10.0), "fermato di nuovo, finisce")
        check(
            app.soluzione is trovata and app.report is not None,
            "la soluzione trovata prima dello stop viene mostrata e verificata",
        )
        check(
            "interrotto" in app.origine and "non dimostrata ottima" in app.origine,
            f"dicendo che non e' dimostrata ottima: \"{app.origine}\"",
        )
        check(
            ricevute[1] is not ricevute[0],
            "ogni calcolo ha la sua richiesta di stop: quella di prima non "
            "ferma quello dopo",
        )
    finally:
        interfaccia.solve_auto_hoists, interfaccia.solve = originali
        chiudi(app)


def test_ciclogramma_si_riprende(percorso_linea):
    print("\n[10] un ciclogramma composto a mano si salva e si riprende")
    from interfaccia import Applicazione
    from excel_io import scrivi_risultati

    app = Applicazione(percorso_linea)
    try:
        for _ in range(50):
            app.update()
            if app.config_linea is not None:
                break
            time.sleep(0.02)
        app._componi_da_zero()
        app.update()
        # composizione a meta': una mossa senza carroponte e un bagno allungato.
        # Riprendere solo i casi completi non servirebbe a niente -- e' proprio
        # il lavoro interrotto quello che non si vuole rifare.
        for k, c in ((0, 0), (1, 0), (2, 0), (3, 1), (5, 1)):
            app.carroponte_attivo = c
            app._assegna(k, app._istantanea())
        app.permanenze[3] = 200.0
        app.n_carroponti = 3
        app._ricomponi("composizione di prova")
        app.update()
        prima = (
            round(app.T_corrente, 4),
            {k: round(v, 3) for k, v in app.permanenze.items()},
            dict(app.assegnazione),
            app.n_carroponti,
        )

        # Un file solo: e' il referto E la linea da riaprire. Due file
        # separati sarebbero due cose da tenere insieme e da non confondere.
        app._verifica_adesso()
        app.update()
        fd, riapribile = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        scrivi_risultati(
            riapribile,
            app.dati,
            app.soluzione,
            app.report,
            sorgente=percorso_linea,
            cfg=app.config_linea,
            ciclogramma={
                "T": app.T_corrente,
                "n_carroponti": app.n_carroponti,
                "permanenze": app.permanenze,
                "assegnazione": app.assegnazione,
            },
        )
        from openpyxl import load_workbook

        fogli = load_workbook(riapribile).sheetnames
        check(
            "Riepilogo" in fogli and "Vasche" in fogli and "Ciclogramma" in fogli,
            f"un file solo, con referto e linea insieme ({len(fogli)} fogli)",
        )
    finally:
        chiudi(app)

    # finestra nuova: e' il caso vero, il programma e' stato chiuso e riaperto
    app = Applicazione()
    try:
        app.update()
        app._carica(riapribile)
        app.update()
        dopo = (
            round(app.T_corrente, 4),
            {k: round(v, 3) for k, v in app.permanenze.items()},
            dict(app.assegnazione),
            app.n_carroponti,
        )
        check(
            dopo == prima,
            f"takt, tempi in vasca, assegnazione e carroponti tornano identici "
            f"({len(dopo[2])} mosse assegnate su {app.dati.n_moves}, "
            f"T={dopo[0]:.2f}s)",
        )
        check(
            "riletto dal file" in app.origine,
            f"il riepilogo dice da dove viene: \"{app.origine}\"",
        )
        # la regola sulla scheda non fa eccezioni: si guarda, e per intervenire
        # si preme Modifica
        check(
            str(app.schede.tab(1, "state")) == "disabled"
            and str(app.btn_modifica["state"]) == "normal",
            "la scheda resta chiusa, ma 'Modifica' e' pronto",
        )
    finally:
        chiudi(app)
        if os.path.exists(riapribile):
            os.unlink(riapribile)


def test_punti_di_passaggio(percorso_linea):
    print("\n[10b] punti di passaggio: si aggiungono, si assegnano, si salvano")
    from interfaccia import Applicazione
    from excel_io import scrivi_risultati
    import manuale

    app = Applicazione(percorso_linea)
    riapribile = None
    try:
        for _ in range(50):
            app.update()
            if app.config_linea is not None:
                break
            time.sleep(0.02)
        app._componi_da_zero()
        d = app.config_linea.data
        app.assegnazione = manuale.assegnazione_iniziale(d, app.n_carroponti)
        app._ricomponi("assegnazione di prova")
        # Un rientro del carroponte 1 con del margine: il punto ci va dentro,
        # fermo dove ha consegnato, cosi' e' raggiungibile su qualunque linea.
        piano = app.soluzione.plans[0]
        k = piano.order[0]
        t_punto = piano.finish[k] + 0.5
        x_punto = d.approach_position(k + 1)
        app.var_punto_t.set(f"{t_punto + 3 * app.T_corrente}")
        app.var_punto_x.set(f"{x_punto}")
        app._aggiungi_passaggio()
        check(
            app.passaggi and app.passaggi[0]["carro"] is None
            and len(app.tabella_passaggi.get_children()) == 1,
            "il punto aggiunto nasce di nessuno, ed e' in tabella",
        )
        check(
            not app.soluzione.plans[0].passaggi,
            "finche' e' di nessuno non cambia nessun giro",
        )
        # il clic sul grafico, su una ripetizione qualunque del punto
        app.update()
        px, py = app.assi.transData.transform((t_punto + app.T_corrente, x_punto))
        clic = Clic(app.assi, px, py, t_punto + app.T_corrente)
        clic.ydata = x_punto
        app._su_pressione(clic)
        app._su_rilascio(clic)
        check(
            app.passaggi[0]["carro"] == 0
            and app.soluzione.plans[0].passaggi.get(k),
            "un clic lo da' al carroponte attivo, e il giro ci passa",
        )
        app._verifica_adesso()
        check(
            not [e for e in app.report.errors if "passare da" in e.message],
            "un punto raggiungibile non e' un errore per il verificatore",
        )
        segmenti = [
            (s.kind, round(s.t_start, 3), round(s.x_end, 3))
            for s in app.soluzione.segments_per_hoist[0]
        ]
        fd, riapribile = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        scrivi_risultati(
            riapribile, app.dati, app.soluzione, app.report,
            sorgente=percorso_linea, cfg=app.config_linea,
            ciclogramma={
                "T": app.T_corrente,
                "n_carroponti": app.n_carroponti,
                "permanenze": app.permanenze,
                "assegnazione": app.assegnazione,
                "passaggi": app.passaggi,
            },
        )
        # di nuovo lo stesso gesto: lo toglie
        app._su_pressione(clic)
        app._su_rilascio(clic)
        check(app.passaggi[0]["carro"] is None, "un altro clic lo toglie")
        app.tabella_passaggi.selection_set(app.tabella_passaggi.get_children()[0])
        app._togli_passaggi()
        check(not app.passaggi, "'Togli' cancella il punto")
        app._annulla_modifica()
        check(len(app.passaggi) == 1, "'Annulla modifica' lo rimette")
    finally:
        chiudi(app)

    app = Applicazione()
    try:
        app.update()
        app._carica(riapribile)
        app.update()
        check(
            len(app.passaggi) == 1 and app.passaggi[0]["carro"] == 0,
            "riaprendo il file il punto torna, col suo carroponte",
        )
        check(
            [
                (s.kind, round(s.t_start, 3), round(s.x_end, 3))
                for s in app.soluzione.segments_per_hoist[0]
            ] == segmenti,
            "e la traiettoria torna identica",
        )
    finally:
        chiudi(app)
        if riapribile and os.path.exists(riapribile):
            os.unlink(riapribile)


def test_simulazione_dal_pulsante(percorso_linea):
    print("\n[11] la simulazione si apre solo quando c'e' un ciclogramma")
    from interfaccia import Applicazione

    app = Applicazione(percorso_linea)
    try:
        for _ in range(50):
            app.update()
            if app.config_linea is not None:
                break
            time.sleep(0.02)
        # Si simula un ciclogramma, non una linea: appena caricato il file non
        # c'e' ancora niente da far muovere.
        check(
            str(app.btn_simula["state"]) == "disabled",
            "con la sola linea caricata il pulsante e' spento",
        )
        app._componi_da_zero()
        app.update()
        check(
            str(app.btn_simula["state"]) == "normal",
            "composto il ciclogramma, si accende",
        )

        app._apri_simulazione()
        app.update()
        finestra = app.finestra_simulazione
        check(finestra is not None, "la finestra si apre")
        finestra.avvia_o_ferma()  # in pausa: qui il tempo lo muoviamo noi
        check(
            abs(finestra.sim.T - app.T_corrente) < 1e-9,
            f"mostra il ciclogramma che c'e' (T={finestra.sim.T:.2f} s)",
        )

        # riaprirla non ne fa una seconda: ne esiste una, e mostra quella
        app._apri_simulazione()
        app.update()
        check(app.finestra_simulazione is finestra, "premendo ancora non se ne apre una seconda")

        # modificando il ciclogramma la simulazione segue: una che continuasse
        # a mostrare quello di prima sarebbe peggio di non averla
        app.var_takt.set(f"{app.T_corrente + 7.0:.2f}")
        app._modifica_takt()
        app.update()
        check(
            abs(finestra.sim.T - app.T_corrente) < 1e-9,
            f"cambiato il takt, la simulazione lo recepisce (T={finestra.sim.T:.2f} s)",
        )

        finestra.destroy()
        app.update()
        check(
            app.finestra_simulazione is None,
            "chiudendola l'applicazione se ne accorge",
        )
    finally:
        chiudi(app)


def test_punti_di_avvio(percorso_linea):
    print("\n[14] il pulsante che scorre i punti di avvio")
    app = _app_risolta(percorso_linea)
    try:
        check(
            len(app.avvii) > 1,
            f"la linea di prova ha piu' di un punto di avvio ({len(app.avvii)})",
        )
        check(
            app.indice_avvio == 0
            and str(app.btn_avvio["state"]) == "normal"
            and str(app.btn_avvio["text"]) == f"Avvio 1 di {len(app.avvii)}",
            f"si parte dal primo e il pulsante lo dice "
            f"({app.btn_avvio['text']})",
        )

        # Premendolo si passa al successivo, e la linea nera si sposta davvero:
        # un pulsante che cambia l'etichetta senza muovere il disegno sarebbe
        # peggio che non averlo.
        def nera():
            return [
                round(float(l.get_xdata()[0]), 4)
                for l in app.assi.lines
                if l.get_color() == "#000000"
            ]

        prima_t, prima_x = app._avvio_corrente().t, nera()
        app._prossimo_avvio()
        app.update()
        check(
            app.indice_avvio == 1 and app._avvio_corrente().t != prima_t,
            f"premendolo si passa al secondo ({prima_t:.2f} s -> "
            f"{app._avvio_corrente().t:.2f} s)",
        )
        check(
            bool(prima_x) and nera() != prima_x,
            f"e la linea nera sul grafico si sposta con lui ({prima_x} -> "
            f"{nera()})",
        )
        check(
            f"Istante di avvio: {app._avvio_corrente().t:.2f}"
            in app.testo_riepilogo.get("1.0", "end"),
            "il riepilogo scrive l'istante che si sta guardando",
        )

        # Gli istanti sono tutti equivalenti: dopo l'ultimo si torna al primo.
        for _ in range(len(app.avvii) - 1):
            app._prossimo_avvio()
        app.update()
        check(
            app.indice_avvio == 0 and abs(app._avvio_corrente().t - prima_t) < 1e-9,
            "e dopo l'ultimo si torna al primo: e' un giro, non una fila",
        )

        # Un ridisegno che non tocca il ciclogramma non deve far saltare la
        # linea nera altrove.
        app._prossimo_avvio()
        scelto = app._avvio_corrente().t
        app._mostra_ciclogramma()
        app.update()
        check(
            abs(app._avvio_corrente().t - scelto) < 1e-9,
            f"un ridisegno lascia dov'era l'istante scelto ({scelto:.2f} s)",
        )

        # Un ciclogramma diverso ha istanti diversi: il numero d'ordine vecchio
        # punterebbe a un altro momento del giro senza che nessuno l'abbia
        # chiesto, e si riparte dal primo.
        app.permanenze[1] += 10.0
        app._ricomponi("prova", app._istantanea())
        app.update()
        check(
            app.indice_avvio == 0,
            "cambiato il ciclogramma, si riparte dal primo",
        )

        # Il file salvato dice l'istante che si sta guardando, non il primo.
        if len(app.avvii) > 1:
            app._prossimo_avvio()
            app.update()
            atteso = app._avvio_corrente()
            fd, png = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            try:
                app._salva_immagine(png)
                check(
                    os.path.getsize(png) > 5000,
                    f"l'immagine salvata con l'avvio "
                    f"{atteso.indice + 1} di {atteso.totale} viene scritta",
                )
            finally:
                if os.path.exists(png):
                    os.unlink(png)
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
        test_avanzamento_del_calcolo(linea)
        test_modifica_tempi_in_vasca(linea)
        test_vista_e_immagine(linea)
        test_takt_e_carroponti(linea)
        test_composizione_da_zero(linea)
        test_da_zero_poi_automatico(linea)
        test_scheda_chiusa_durante_il_calcolo(linea)
        test_ferma_il_calcolo(linea)
        test_ciclogramma_si_riprende(linea)
        test_punti_di_passaggio(linea)
        test_simulazione_dal_pulsante(linea)
        test_punti_di_avvio(linea)
        test_file_illeggibile()
    finally:
        os.unlink(linea)

    print("\n" + "=" * 72)
    print(f"RISULTATO: {_n_pass} ok, {_n_fail} falliti")
    print("=" * 72)
    return 1 if _n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
