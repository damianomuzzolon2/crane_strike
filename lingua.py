"""
lingua.py
---------
Le due lingue dell'interfaccia: italiano e inglese.

La chiave di traduzione E' IL TESTO ITALIANO. Non un codice simbolico tipo
`btn.open_line`: cosi' il codice resta leggibile senza saltare a un dizionario
per sapere cosa c'e' scritto su un pulsante, e una stringa non ancora tradotta
non diventa una sigla a schermo -- resta in italiano, che e' comprensibile.
E' lo stesso principio di gettext, senza la macchina di gettext.

    from lingua import L
    ttk.Button(barra, text=L("Apri linea..."))
    self._stato(L("Calcolo fallito"))
    self._stato(L("Ciclogramma pronto - T = {t} s", t=f"{sol.T:.2f}"))

I valori vanno passati per NOME, non interpolati prima: un testo gia' composto
non si puo' tradurre, e un segnaposto numerato si sbaglia a rimontare in una
lingua che mette le parole in un altro ordine.

Aggiungere una lingua e' aggiungere un dizionario a `_TRADUZIONI`. Aggiungere
una stringa e' scriverla in italiano nel codice e, quando c'e' tempo, metterne
la traduzione qui: finche' non c'e', quella riga resta in italiano e tutto il
resto e' gia' tradotto. Non si rompe niente a meta' strada.
"""

from __future__ import annotations

LINGUE = ("it", "en")

# Lingua corrente. Sta qui e non nell'interfaccia perche' la usano anche i
# moduli che disegnano (plotting, simulazione), che dell'interfaccia non sanno
# niente e non devono saperne.
_corrente = "it"


def lingua() -> str:
    return _corrente


def imposta_lingua(codice: str) -> str:
    """Cambia la lingua e restituisce quella impostata. Un codice sconosciuto
    non solleva niente: si torna all'italiano, che e' sempre completo."""
    global _corrente
    _corrente = codice if codice in LINGUE else "it"
    return _corrente


def alterna() -> str:
    """Passa all'altra lingua. Con due lingue e' l'unico comando che serve."""
    return imposta_lingua("en" if _corrente == "it" else "it")


def L(testo: str, **valori) -> str:
    """Il testo nella lingua corrente, con i valori al posto dei segnaposto.

    Se la traduzione manca si usa l'italiano: una stringa dimenticata si legge
    male ma si legge, mentre un errore o una sigla fermerebbero il lavoro per
    una parola."""
    fuori = _TRADUZIONI.get(_corrente, {}).get(testo, testo)
    return fuori.format(**valori) if valori else fuori


# --------------------------------------------------------------------------
# Inglese
# --------------------------------------------------------------------------

_EN = {
    # -- barra dei comandi ---------------------------------------------
    "Apri linea...": "Open line...",
    "Nuovo modello Excel...": "New Excel template...",
    "Calcola auto": "Solve",
    "Calcola man": "Compose",
    "Modifica": "Edit",
    "Fine modifica": "Done editing",
    "Simulazione": "Simulation",
    "Salva risultati...": "Save results...",
    "Nessuna linea caricata": "No line loaded",
    "Lingua": "Language",
    # -- schede ---------------------------------------------------------
    "Riepilogo": "Summary",
    "Ciclogramma": "Cyclogram",
    "Verifica": "Check",
    "Verifica ({n})": "Check ({n})",
    "gravita'": "severity",
    "tipo": "type",
    "descrizione": "description",
    "Fai clic su una riga per leggerla per intero.":
        "Click a row to read it in full.",
    "ERRORE": "ERROR",
    "avviso": "warning",
    "nota": "note",
    # -- scheda Ciclogramma ---------------------------------------------
    "Takt time [s]:": "Takt time [s]:",
    "Applica": "Apply",
    "Carroponti:": "Hoists:",
    "attivo:": "active:",
    "Tempi in vasca": "Times in tank",
    "vasca": "tank",
    "tempo [s]": "time [s]",
    "min": "min",
    "max": "max",
    "Assegnazione": "Assignment",
    "n": "n",
    "da vasca": "from tank",
    "a vasca": "to tank",
    "carrop.": "hoist",
    "Annulla modifica": "Undo",
    "Verifica adesso": "Check now",
    "Ottimizza con questi carroponti": "Optimise with these hoists",
    # -- messaggi di stato ----------------------------------------------
    "Pronto": "Ready",
    "Linea caricata": "Line loaded",
    "Calcolo fallito": "Solve failed",
    "Nessuna soluzione trovata": "No solution found",
    "Verifica eseguita": "Check done",
    "Modifica chiusa: si guarda il ciclogramma":
        "Editing closed: back to reading the cyclogram",
    "Cerco numero di carroponti e zone migliori...":
        "Searching for the best number of hoists and zones...",
    "Calcolo in corso: aspetta che finisca per modificare":
        "Solving: wait for it to finish before editing",
    "Ciclogramma pronto - T = {t} s": "Cyclogram ready - T = {t} s",
    "Valore non valido": "Invalid value",
    # -- banner ----------------------------------------------------------
    "Nessun ciclogramma": "No cyclogram",
    "{n} INCOERENZE   -   il ciclogramma non si tiene in piedi, vedi il Riepilogo":
        "{n} INCONSISTENCIES   -   this cyclogram does not hold together, "
        "see the Summary",
    "IN COMPOSIZIONE   -   T = {t} s   -   premi Verifica adesso per il verdetto":
        "BEING COMPOSED   -   T = {t} s   -   press Check now for the verdict",
    "VERIFICA SUPERATA   -   T = {t} s   -   {p} pezzi/ora":
        "CHECK PASSED   -   T = {t} s   -   {p} parts/hour",
    "{n} ERRORI   -   vedi la scheda Verifica":
        "{n} ERRORS   -   see the Check tab",
    # -- grafici ----------------------------------------------------------
    "Ciclogramma - {file}": "Cyclogram - {file}",
    "Ciclogramma carroponti": "Hoist cyclogram",
    "{titolo}  —  takt time T = {t} s": "{titolo}  —  takt time T = {t} s",
    "tempo [s]": "time [s]",
    "posizione lungo la rotaia": "position along the rail",
    "Carroponte {n}": "Hoist {n}",
    "t = {t} s      posizione = {x} mm": "t = {t} s      position = {x} mm",
    "Apri una linea per cominciare": "Open a line to begin",
    "Nessun ciclogramma calcolato": "No cyclogram computed",
    "Nessuna soluzione": "No solution",
    "Modifica  —  takt time T = {t} s  —  clic sul percorso grigio per "
    "assegnarlo a un carroponte":
        "Editing  —  takt time T = {t} s  —  click the grey path to assign it "
        "to a hoist",
    "percorso dei pezzi": "path of the parts",
    "giro dei carroponti": "hoist round trip",
    # -- simulazione ------------------------------------------------------
    "Simulazione della linea": "Line simulation",
    "Simulazione della linea - {file}": "Line simulation - {file}",
    "Avvia": "Play",
    "Pausa": "Pause",
    "Avanti": "Forward",
    "Indietro": "Back",
    "Da capo": "Restart",
    "velocita':": "speed:",
    "telaio": "rack",
    "trasporto": "transfer",
    "rientro a vuoto": "empty return",
    "attesa": "waiting",
    "attesa in vasca": "waiting in the tank",
    "aggancio": "hooking",
    "sgancio": "unhooking",
    "discesa del gancio": "hook going down",
    "risalita del gancio": "hook coming up",
    "sollevamento del telaio": "lifting the rack",
    "immersione del telaio": "lowering the rack",
    "sgocciolamento": "dripping",
    "Carroponte {n}: {fase}": "Hoist {n}: {fase}",
    "Carroponte {n}: {fase} in {vasca}": "Hoist {n}: {fase} in {vasca}",
    "t = {t} s   di {durata} s ({periodi} takt da {T} s)   -   {n} pezzi in linea":
        "t = {t} s   of {durata} s ({periodi} takts of {T} s)   -   {n} parts "
        "in the line",
    "{n} trasporti non sono assegnati a nessun carroponte (mosse {mosse}): li "
    "vedrai come pezzi che si spostano da soli.":
        "{n} transfers are not assigned to any hoist (moves {mosse}): you will "
        "see them as parts moving on their own.",
    # -- riepilogo ---------------------------------------------------------
    "Origine: {origine}": "Source: {origine}",
    "calcolo automatico (ottimo)": "automatic solve (optimal)",
    "calcolo automatico (soluzione valida, non dimostrata ottima)":
        "automatic solve (valid solution, not proven optimal)",
    "composto da zero": "composed from scratch",
    "riletto dal file, gia' composto":
        "read back from the file, already composed",
    ", poi modificato a mano": ", then edited by hand",
    "Takt time:      {t} s": "Takt time:      {t} s",
    "Produttivita':  {p} pezzi/ora": "Throughput:     {p} parts/hour",
    "Carroponti:     {n}": "Hoists:         {n}",
    "Linea: {percorso}": "Line: {percorso}",
    "Stazioni: {n}   Mosse: {m}": "Stations: {n}   Moves: {m}",
    "Takt time ammesso: {a} - {b} s": "Takt time allowed: {a} - {b} s",
    "Vasche: {vasche}": "Tanks: {vasche}",
    "Scegli come costruire il ciclogramma.":
        "Choose how to build the cyclogram.",
    # -- incoerenze ---------------------------------------------------------
    "IL CICLOGRAMMA NON E' REALIZZABILE COSI' COM'E'.":
        "THIS CYCLOGRAM CANNOT BE CARRIED OUT AS IT IS.",
    "Il disegno le assorbe allungando le attese: se vedi una riga "
    "orizzontale lunghissima, e' questa la ragione.":
        "The drawing absorbs them by stretching the waits: if you see a "
        "very long horizontal line, this is the reason.",
    "Se hai appena riaperto un file salvato con una versione precedente "
    "del programma, ricalcolalo e risalvalo: i tempi di presa, rilascio e "
    "permanenza sono cambiati, e i valori scritti allora non vogliono "
    "piu' dire la stessa cosa.":
        "If you have just reopened a file saved with an earlier version "
        "of the program, solve it again and save it again: the pick, "
        "release and dwell times have changed, and the values written "
        "back then no longer mean the same thing.",
    # -- stato ---------------------------------------------------------------
    "Modifica: trascina un prelievo sul grafico, cambia un tempo in vasca, "
    "oppure clicca un trasporto per assegnarlo (e di nuovo per toglierlo)":
        "Editing: drag a pick on the chart, change a time in tank, or "
        "click a transfer to assign it (and click again to remove it)",
    "Composizione da zero: fai clic sui trasporti per assegnarli":
        "Composing from scratch: click the transfers to assign them",
    "Ciclogramma ripreso dal file: premi Modifica per intervenire":
        "Cyclogram resumed from the file: press Edit to work on it",
    "Simulazione aperta: si aggiorna da sola se modifichi il ciclogramma":
        "Simulation open: it follows along if you change the cyclogram",
    "Risultati salvati in {file}": "Results saved to {file}",
    # -- testi d'aiuto (una riga sola: le chiavi multi-riga sono una
    #    trappola, e a capo ci va l'etichetta da sola con wraplength) ------
    "Il ciclogramma si regola con tre cose: il takt time, il tempo in vasca "
    "di ogni tappa e quale carroponte fa ogni trasporto. Tutto il resto "
    "viene da se'. Vale sia per un ciclogramma calcolato sia per uno "
    "composto da zero.":
        "A cyclogram is set by three things: the takt time, the time in "
        "the tank at each step, and which hoist performs each transfer. "
        "Everything else follows. This holds both for a computed cyclogram "
        "and for one composed from scratch.",
    "Doppio clic sul tempo per cambiarlo. Il minimo e il massimo sono di "
    "processo: si possono sforare, la verifica lo dira'.":
        "Double-click a time to change it. The minimum and maximum come "
        "from the process: you may exceed them, the check will say so.",
    "Doppio clic per passare il trasporto al carroponte successivo; dopo "
    "l'ultimo torna non assegnato. Sul grafico, clic sul trasporto per "
    "darlo al carroponte attivo, e di nuovo per toglierglielo.":
        "Double-click to pass the transfer to the next hoist; after the "
        "last one it goes back to unassigned. On the chart, click a "
        "transfer to give it to the active hoist, and click again to take "
        "it away.",
    # -- dettaglio del riepilogo -------------------------------------------
    "   {n}: mosse {lo}-{hi}  ({da} -> {a})":
        "   {n}: moves {lo}-{hi}  ({da} -> {a})",
    "Ancora da assegnare: {n} trasporti su {tot} (mosse {mosse}).":
        "Still to assign: {n} transfers out of {tot} (moves {mosse}).",
    "Fai clic sul trasporto nel grafico, oppure doppio clic sulla riga "
    "nella tabella Assegnazione.":
        "Click the transfer on the chart, or double-click the row in the "
        "Assignment table.",
    "I controlli sono sospesi finche' non premi 'Verifica adesso'. Da quel "
    "momento in poi il verdetto si tiene aggiornato da solo a ogni "
    "modifica.":
        "Checks are on hold until you press 'Check now'. From then on the "
        "verdict keeps itself up to date at every change.",
    # -- errori all'utente -------------------------------------------------
    "Nessuna linea": "No line",
    "Apri prima un file Excel con la linea.":
        "Open an Excel file with the line first.",
    "Il file non puo' essere letto": "The file cannot be read",
    "Impossibile salvare": "Cannot save",
    "Impossibile simulare": "Cannot simulate",
    "Il calcolo si e' interrotto": "The solve was interrupted",
    "Verifica non eseguibile": "Check cannot be run",
}

# Il messaggio del salvataggio contiene degli a capo. Non lo si scrive come
# chiave dentro il dizionario: fra le barre rovesciate ci si perde, e una
# chiave sbagliata di un carattere non si traduce senza che nessuno se ne
# accorga. Si costruisce qui, con un nome, e nel codice si usa quello.
SALVATO = (
    "Salvati:\n{excel}\n{png}\n\nL'Excel contiene anche la linea "
    "col ciclogramma: riaprilo con 'Apri linea...' per riprendere da qui."
)
_EN[SALVATO] = (
    "Saved:\n{excel}\n{png}\n\nThe Excel file also contains the "
    "line with the cyclogram: reopen it with 'Open line...' to carry on "
    "from here."
)

_TRADUZIONI = {"en": _EN}
