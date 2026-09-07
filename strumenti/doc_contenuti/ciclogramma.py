"""
Il testo dei documenti di ciclogramma.py.

Due sole funzioni, ma sono la faccia del programma per chi lo usa da
terminale o da uno script: quello che stampano e il codice d'uscita che
restituiscono sono un'interfaccia vera, e cambiarli rompe chi ci si appoggia.
"""

from __future__ import annotations

# --------------------------------------------------------------------------

RIGA_PER_RIGA = [
    ("h1", "ciclogramma.py spiegato riga per riga"),
    ("p",
     "Questo documento accompagna la lettura di ciclogramma.py, il comando da "
     "riga di comando: legge una linea da un file Excel, calcola il "
     "ciclogramma, lo verifica e produce i risultati. Ogni blocco di codice e' "
     "estratto dal sorgente al momento della generazione."),
    ("p",
     "Fa esattamente lo stesso lavoro dell'interfaccia grafica, e lo fa "
     "chiamando le stesse funzioni. Non c'e' un solo calcolo qui dentro: e' "
     "tutto lettura degli argomenti, ordine delle chiamate e messaggi. Ed e' "
     "il motivo per cui vale la pena leggerlo per primo fra i programmi -- si "
     "vede il giro completo in centottanta righe, senza il rumore di una "
     "finestra."),

    # ==================================================================
    ("h2", "Che cosa fa, in una pagina"),
    ("p", "Il giro e' sempre lo stesso, in sei passi:"),
    ("li", "leggere il file Excel e trasformarlo in un ProblemData;"),
    ("li", "decidere i carroponti -- o accettare le zone scritte a mano, o "
           "cercarne numero e suddivisione;"),
    ("li", "risolvere con CP-SAT;"),
    ("li", "far ricontrollare il risultato dal verificatore indipendente;"),
    ("li", "scrivere il file Excel dei risultati;"),
    ("li", "disegnare il ciclogramma in un PNG."),
    ("p",
     "Gli ultimi due si possono saltare (--niente-excel, --niente-grafico). I "
     "primi quattro no: un ciclogramma non verificato non esce da questo "
     "programma."),

    ("q",
     "IL CODICE D'USCITA E' UN'INTERFACCIA. Chi mette questo comando in uno "
     "script guarda il numero che restituisce, non quello che stampa. Sono "
     "quattro, e vogliono dire cose diverse: 0 tutto bene; 1 il calcolo e' "
     "andato ma il risultato non va (nessuna soluzione, oppure una soluzione "
     "che non supera la verifica); 2 non si e' nemmeno partiti (file "
     "inesistente o compilato male). La distinzione fra 1 e 2 e' quella utile: "
     "col 2 si corregge il file, col 1 si cambiano i parametri della linea."),

    # ==================================================================
    ("h2", "1. _argomenti -- la riga di comando"),
    ("c", "ciclogramma._argomenti"),
    ("p",
     "Nient'altro che la dichiarazione delle opzioni ad argparse. Vale la pena "
     "notare due scelte."),
    ("p",
     "La prima: `file` e' un argomento posizionale obbligatorio, e serve anche "
     "in modalita' --modello, dove pero' e' il file da SCRIVERE invece che "
     "quello da leggere. Lo stesso nome significa due cose opposte a seconda "
     "di un'opzione. Non e' elegantissimo, ma e' quello che l'utente si "
     "aspetta: si scrive sempre il nome della linea su cui si sta lavorando."),
    ("p",
     "La seconda: le opzioni sono in italiano (--niente-grafico, --cicli) "
     "mentre i nomi delle funzioni del progetto sono in inglese. E' voluto: i "
     "nomi che vede l'utente sono nella sua lingua, quelli che vede solo il "
     "programmatore restano nella lingua del codice."),
    ("p",
     "argparse converte i trattini in trattini bassi, quindi --niente-grafico "
     "si legge come args.niente_grafico. E' il tipo di dettaglio che fa "
     "perdere dieci minuti la prima volta."),

    # ==================================================================
    ("h2", "2. main -- il giro completo"),

    ("h3", "La modalita' modello"),
    ("c", "ciclogramma.main", None, "    if not os.path.exists"),
    ("p",
     "Se c'e' --modello, il programma non calcola niente: scrive un file Excel "
     "gia' compilato con una linea di esempio e finisce. E' la risposta alla "
     "prima domanda di chi non ha ancora niente in mano -- 'da dove comincio?' "
     "-- e per questo il messaggio non si limita a dire che il file e' stato "
     "scritto: dice da quale foglio partire e stampa il comando successivo, "
     "gia' pronto da copiare."),
    ("p",
     "E' la regola dei messaggi del progetto, e vale in tutti e tre i punti in "
     "cui questa funzione parla all'utente: non dire soltanto cosa e' "
     "successo, dire cosa fare adesso."),

    ("h3", "Le due porte chiuse: file assente, file sbagliato"),
    ("c", "ciclogramma.main", "    if not os.path.exists", "    data = cfg.data"),
    ("p",
     "Due modi di non partire, entrambi con codice 2 e messaggio su stderr -- "
     "cosi' chi reindirizza l'uscita normale in un file vede comunque "
     "l'errore a schermo."),
    ("p",
     "Il file mancante e' quasi sempre un file mai creato, quindi il messaggio "
     "suggerisce --modello con lo stesso nome. Il file illeggibile, invece, "
     "non produce un messaggio scritto qui: leggi_problema solleva un "
     "ValueError che contiene GIA' l'elenco completo degli errori di "
     "compilazione, foglio per foglio e cella per cella. Qui lo si stampa e "
     "basta."),
    ("q",
     "SI STAMPA `e`, NON UN TESTO NUOVO. E' importante che questo blocco non "
     "aggiunga niente di suo: excel_io raccoglie TUTTI gli errori del file e li "
     "presenta insieme, invece di fermarsi al primo. Se qui si scrivesse "
     "'errore nella lettura del file', quel lavoro andrebbe perso e l'utente "
     "correggerebbe una cella alla volta rilanciando ogni volta."),

    ("h3", "La risoluzione, e le due strade"),
    ("c", "ciclogramma.main", "    # -- risoluzione", "    if solution.status not in"),
    ("p",
     "Qui si vede la separazione piu' importante del progetto. Le ZONE -- "
     "quale carroponte esegue quali trasporti -- non fanno parte del modello "
     "CP-SAT: solve() le riceve gia' decise."),
    ("li", "Se il file Excel le dichiara, si chiama direttamente solve()."),
    ("li", "Se non le dichiara, si chiama solve_auto_hoists(), che prova un "
           "numero crescente di carroponti e, per ciascuno, le suddivisioni "
           "possibili, chiamando solve() su ognuna."),
    ("p",
     "Nel secondo caso il costo e' molte risoluzioni invece di una, ed e' per "
     "questo che il limite di tempo si chiama tempo_limite_per_tentativo_s: "
     "vale per ogni tentativo, non per l'insieme. Chi si aspetta che il "
     "comando finisca in quel tempo resta sorpreso."),

    ("h3", "Quando non si trova niente"),
    ("c", "ciclogramma.main", "    if solution.status not in",
     "    data_finale = dataclasses.replace"),
    ("p",
     "Non basta dire che non c'e' soluzione: il messaggio elenca le quattro "
     "leve su cui si puo' agire, in ordine di quanto e' probabile che siano "
     "loro il problema. Poi stampa il registro dei tentativi (hoist_sweep) se "
     "c'e', che dice cosa e' stato provato e con che esito -- utile per capire "
     "se il limite era il numero di carroponti o il takt time."),
    ("q",
     "'UNKNOWN' NON E' 'INFEASIBLE'. Il controllo accetta solo OPTIMAL e "
     "FEASIBLE, e quindi tratta allo stesso modo un problema dimostrato "
     "impossibile e uno su cui il solutore ha solo esaurito il tempo. Sono due "
     "situazioni opposte: nel primo caso bisogna cambiare la linea, nel "
     "secondo basta dare piu' tempo. Lo stato stampato le distingue, ma i "
     "quattro suggerimenti sono gli stessi in entrambi i casi."),

    ("h3", "La verifica indipendente"),
    ("c", "ciclogramma.main", "    # -- verifica indipendente", "    # -- risultati in Excel"),
    ("p",
     "Il solutore ha appena dichiarato OPTIMAL, e nonostante questo la "
     "soluzione viene ricontrollata da capo, in Python puro, senza CP-SAT. La "
     "ragione e' che 'ottimale' vuol dire soltanto 'il migliore fra quelli che "
     "rispettano i vincoli che gli ho scritto': se un vincolo e' formulato "
     "male, il solutore restituisce comunque OPTIMAL e nessuno se ne "
     "accorgerebbe. Il verificatore riparte dai movimenti veri e li "
     "ricontrolla."),
    ("p",
     "Si noti che il programma NON si ferma se la verifica fallisce: scrive "
     "comunque i risultati e il grafico, perche' guardarli e' il modo per "
     "capire cosa non va. Lo dice pero' a chiare lettere, e lo ricorda "
     "nell'ultima riga della funzione con il codice d'uscita 1."),

    ("h3", "Il file dei risultati, che e' anche un file di ingresso"),
    ("c", "ciclogramma.main", "    # -- risultati in Excel", "    # -- grafico"),
    ("p",
     "Il blocco piu' denso della funzione, e non per il salvataggio in se': "
     "per il dizionario `ciclogramma` che gli si passa accanto. Quel "
     "dizionario contiene i TRE GRADI DI LIBERTA' della soluzione, ed e' cio' "
     "che rende il file dei risultati riapribile."),
    ("li", "T -- il takt time;"),
    ("li", "permanenze -- quanto ogni pezzo sta in ciascuna vasca;"),
    ("li", "assegnazione -- quale carroponte esegue quale trasporto."),
    ("p",
     "Da questi tre soli dati build_solution() sa ricostruire l'intero "
     "ciclogramma, traiettorie comprese. Tutto il resto -- istanti di "
     "prelievo, giri a vuoto, profili -- e' conseguenza, e salvarlo sarebbe "
     "sia ridondante sia rischioso, perche' un file modificato a mano potrebbe "
     "contenere dati incoerenti fra loro."),
    ("p",
     "La riga che calcola le permanenze merita attenzione: la permanenza nella "
     "vasca della tappa k e' l'istante in cui il pezzo ne esce meno l'istante "
     "in cui ci e' arrivato, e quest'ultimo e' l'inizio del trasporto "
     "precedente piu' la durata del trasporto stesso. Non e' un dato che il "
     "modello espone: si ricava dagli istanti di prelievo."),
    ("q",
     "IL COMMENTO NEL MEZZO NON E' DECORATIVO. Dice che anche da riga di "
     "comando il file resta riapribile. E' la stessa struttura che produce "
     "l'interfaccia grafica: un solo formato di risultati, non due. Se le due "
     "strade producessero file diversi, un ciclogramma calcolato da terminale "
     "non si potrebbe piu' aprire nell'editor grafico per ritoccarlo."),

    ("h3", "Il grafico, e l'uscita"),
    ("c", "ciclogramma.main", "    # -- grafico", None),
    ("p",
     "matplotlib viene importato QUI, dentro la funzione e dentro l'if, non in "
     "testa al file. Due motivi, entrambi pratici."),
    ("li", "Con --niente-grafico non lo si importa affatto, e l'importazione "
           "di matplotlib e' una delle piu' lente che ci siano: su un comando "
           "che deve solo produrre l'Excel si risparmia parecchio."),
    ("li", "La riga matplotlib.use('Agg') sceglie il motore che disegna su "
           "file senza aprire finestre, e DEVE essere eseguita prima che "
           "pyplot venga importato. Metterla in testa al file la farebbe "
           "valere anche quando questo modulo viene importato da altri, "
           "rubando la scelta del motore a chi invece una finestra la vuole."),
    ("p",
     "L'ultima riga e' il codice d'uscita, e dice una cosa precisa: il "
     "comando riesce solo se la verifica INDIPENDENTE e' passata. Non se il "
     "solutore ha detto OPTIMAL. E' la differenza fra 'il programma ha "
     "funzionato' e 'il ciclogramma e' buono', e per chi automatizza e' quella "
     "che conta."),
]

DOCUMENTI = [
    ("ciclogramma_riga_per_riga.docx", RIGA_PER_RIGA),
]
