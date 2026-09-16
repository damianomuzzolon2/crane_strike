"""
Il testo dei documenti di interfaccia.py.

Settantasei fra funzioni e metodi in una classe sola. Divisi non per posizione
nel file ma per GESTO dell'utente: costruire la finestra, calcolare, comporre a
mano, guardare.
"""

from __future__ import annotations

# ==========================================================================
# Documento 1 -- la finestra
# ==========================================================================

FINESTRA = [
    ("h1", "interfaccia.py (1) -- la finestra e i suoi tre stati"),
    ("p",
     "Primo dei quattro documenti su interfaccia.py, il programma che usa un "
     "utente normale. Qui c'e' come e' fatta la finestra e -- soprattutto -- "
     "quali stati puo' avere, che e' la cosa da capire prima di tutto il "
     "resto."),

    # ==================================================================
    ("h2", "Tre stati, non due piu' una scorciatoia"),
    ("p",
     "La decisione che governa tutta l'interfaccia sta in tre righe di "
     "__init__ e nei commenti che le accompagnano. L'utente puo' trovarsi in "
     "uno di tre stati, e sono tre gesti diversi:"),
    ("t", [
        ["stato", "ci si arriva con", "cosa si vede", "si puo' modificare"],
        ["leggere", "Calcola auto", "le traiettorie dei carroponti", "no"],
        ["comporre", "Calcola man", "il pettine dei pezzi", "si"],
        ["modificare", "Modifica", "il pettine dei pezzi", "si"],
    ]),
    ("q",
     "PERCHE' NON SI PUO' MODIFICARE SUBITO. Il commento in __init__ lo dice: "
     "dopo un calcolo automatico si sta LEGGENDO un risultato, e per metterci "
     "le mani bisogna dirlo premendo 'Modifica'. Cosi' i tre pulsanti sono tre "
     "stati veri invece di due piu' una scorciatoia, e un ciclogramma "
     "calcolato non si altera per sbaglio con un trascinamento di troppo. E' "
     "una frizione aggiunta apposta, ed e' quella che rende sicuro il resto."),
    ("p",
     "La VISTA -- ciclogramma o pettine -- non e' invece una scelta "
     "dell'utente: la decide il modo in cui ci e' arrivato. Un interruttore "
     "fra i due c'e' stato ed e' stato tolto, perche' le tabelle della scheda "
     "Ciclogramma permettono di modificare tutto senza cambiare disegno: "
     "restava un comando che chiedeva una decisione senza darne il motivo."),

    ("h3", "Le costanti"),
    ("c", "interfaccia", "_COLORI_GRAVITA", "def _durata_leggibile"),
    ("p",
     "Il commento sui tre valori del disegno manuale enuncia una disciplina: "
     "un solo grigio per tutto cio' che l'utente non ha ancora deciso, e due "
     "soli spessori. Il colore compare SOLO dove si e' assegnato un trasporto "
     "a un carroponte, e li' vuol dire quello e nient'altro. E' la stessa "
     "regola di plotting.py e della simulazione: il colore dice una cosa "
     "sola."),
    ("c", "interfaccia._durata_leggibile"),
    ("p",
     "Una durata come la direbbe una persona. Il docstring argomenta la "
     "soglia -- sotto il minuto i decimi si sentono, sopra non dicono piu' "
     "niente -- e un dettaglio che sembra pedanteria e non lo e': il secondo "
     "si scrive sempre, anche a zero, perche' '2 min' e '2 min 0 s' sembrano "
     "due precisioni diverse, e chi confronta due calcoli vuole leggere lo "
     "stesso formato tutte le volte."),

    # ==================================================================
    ("h2", "1. La barra del grafico"),
    ("c", "interfaccia._BarraGrafico", None, "    def __init__"),
    ("q",
     "PERCHE' AVVISARE L'APPLICAZIONE. Il docstring: il grafico viene "
     "ridisegnato da zero a ogni modifica, e senza sapere che l'utente ha "
     "ingrandito una zona, ogni clic gli farebbe saltare la vista al punto di "
     "partenza -- proprio mentre sta lavorando sul dettaglio per cui aveva "
     "ingrandito. E' un difetto che rende inutilizzabile un editor grafico, e "
     "si risolve solo intercettando i comandi della barra."),
    ("p",
     "`toolitems` ridichiara le voci con le descrizioni in italiano, e ne "
     "TOGLIE una: 'Configure subplots', che regola i margini. Il commento dice "
     "perche': qui i margini vengono comunque ricalcolati da tight_layout a "
     "ogni ridisegno, quindi quel comando non farebbe altro che sfasare il "
     "grafico."),
    ("p",
     "I nomi in prima colonna restano in INGLESE, ed e' un vincolo tecnico "
     "dichiarato nel commento: la barra ci cerca dentro 'Back' e 'Forward' per "
     "abilitarli. Tradurli spegnerebbe i due pulsanti senza nessun errore."),
    ("c", "interfaccia._BarraGrafico", "    def __init__", None),
    ("p",
     "Cinque metodi che chiamano il corrispondente di matplotlib e poi "
     "avvisano. `home` avvisa PRIMA, gli altri dopo: tornare alla vista intera "
     "significa che l'utente rinuncia alla sua inquadratura, e l'applicazione "
     "deve saperlo prima che la vista cambi."),

    # ==================================================================
    ("h2", "2. Lo stato dell'applicazione"),
    ("c", "interfaccia.Applicazione.__init__"),
    ("p",
     "Non costruisce quasi niente: dichiara lo stato. E' la parte piu' utile "
     "da leggere di tutto il modulo, perche' ogni campo porta con se' il "
     "motivo per cui esiste."),
    ("q",
     "IL CICLOGRAMMA E' TRE NUMERI. Il blocco di commento piu' lungo: un "
     "ciclogramma ha pochissimi gradi di liberta' reali, e sono gli stessi che "
     "si usano tracciandolo a mano su carta -- il takt time, il tempo in vasca "
     "di ogni tappa, e quale carroponte fa ogni trasporto. E vale IDENTICO per "
     "un ciclogramma calcolato dal solutore e per uno composto da zero: sono "
     "lo stesso oggetto. Il solutore ne produce uno, e i suoi tempi in vasca "
     "si rileggono dalla catena dei prelievi. E' per questo che si modificano "
     "allo stesso modo, in una pagina sola invece di due."),
    ("p",
     "`durata_calcolo` e' None quando il ciclogramma non viene da un calcolo. "
     "Il commento dice a cosa serve il numero: a sapere se conviene allargare "
     "il tempo limite, e a capire se una linea e' pesante da risolvere -- 'le "
     "due domande che ci si pone davanti a un risultato che non piace'."),
    ("p",
     "`verifica_viva` regola quando il verdetto compare. Non parte da sola, e "
     "il commento ne da' la ragione: comporre da zero vuol dire passare per "
     "stati dichiaratamente sbagliati, e un muro di errori rossi mentre si "
     "sceglie la prima mossa non informa nessuno. Una volta chiesta, pero', si "
     "tiene aggiornata da sola."),
    ("p",
     "`finestra_simulazione` non e' una scheda, ed e' voluto: la si guarda "
     "ACCANTO al ciclogramma, non al posto suo, e cosi' si puo' modificare da "
     "una parte e vedere l'effetto dall'altra."),

    ("h3", "La costruzione"),
    ("c", "interfaccia.Applicazione._costruisci_interfaccia"),
    ("p",
     "La finestra e' divisa in tre: la barra dei comandi in alto, il grafico a "
     "sinistra, e a destra un verdetto sempre in vista con sotto tre schede. "
     "In basso una barra di stato."),
    ("p",
     "Il grafico sta FUORI dalle schede, e non e' un dettaglio di "
     "impaginazione: e' la ragione per cui _su_pressione deve rifare da solo "
     "il controllo su `modifica_aperta`. Una scheda chiusa nasconde i suoi "
     "campi; il grafico resta li' e resta cliccabile."),
    ("c", "interfaccia.Applicazione._grafico_vuoto"),
    ("p",
     "Il riquadro con un messaggio al centro, per quando non c'e' niente da "
     "disegnare. Serve piu' di quanto sembri: un'area bianca senza scritte si "
     "legge come un programma che non ha capito il comando."),

    # ==================================================================
    ("h2", "3. Le utilita' di servizio"),
    ("c", "interfaccia.Applicazione._stato"),
    ("c", "interfaccia.Applicazione._errore"),
    ("c", "interfaccia.Applicazione._scrivi_riepilogo"),
    ("c", "interfaccia.Applicazione._svuota_tabella"),
    ("c", "interfaccia.Applicazione._mostra_percorso"),
    ("p",
     "Cinque metodi brevi. `_mostra_percorso` fa comparire il percorso "
     "completo del file: il titolo mostra solo il nome, che su un PC con venti "
     "linee in cartelle diverse non basta a sapere quale si sta guardando."),
    ("c", "interfaccia.Applicazione.destroy"),
    ("p",
     "La chiusura deve fare tre cose in ordine: chiudere la finestra della "
     "simulazione se e' aperta, fermare i timer, liberare la figura. Una "
     "finestra figlia che sopravvive al genitore resta a schermo senza piu' "
     "nessuno che la aggiorni."),

    # ==================================================================
    ("h2", "4. L'autotest e l'avvio"),
    ("p",
     "In fondo si lascia andare anche self.icona, per la stessa ragione delle "
     "icone della barra del grafico: un'immagine di Tk che sopravvive alla "
     "finestra viene cancellata dal garbage collector su un interprete che "
     "non c'e' piu', e stampa un traceback innocuo che sembra un guasto."),
    ("c", "interfaccia.autotest"),
    ("p",
     "Prova l'installazione da cima a fondo senza intervento umano: crea un "
     "modello Excel, lo legge, calcola, verifica, salva i risultati e "
     "l'immagine, e scrive un resoconto. E' quello che si lancia sul PC di "
     "stabilimento dopo aver copiato la cartella dell'eseguibile."),
    ("q",
     "LA FINESTRA VIENE APERTA DAVVERO. Non e' una prova delle sole funzioni "
     "di calcolo: costruisce l'Applicazione e ne pilota i metodi, facendo "
     "girare il ciclo degli eventi con update() invece di mainloop(). E' "
     "l'unico modo per accorgersi che manca una libreria grafica, che il "
     "backend di matplotlib non parte, o che un pulsante resta disabilitato -- "
     "cose che su un PC di stabilimento capitano, e che una prova del solo "
     "motore non vedrebbe."),
    ("h3", "Il nome e l'icona"),
    ("c", "interfaccia._applica_icona"),
    ("p",
     "Mette l'icona di CraneStrike sulla finestra principale e, con il primo "
     "argomento di iconphoto a True, su tutte quelle che si apriranno dopo: "
     "la simulazione la eredita senza doverlo ripetere."),
    ("p",
     "I file sono due, e se ne usa UNO SOLO. Su Windows l'ICO, che contiene "
     "le misure piccole gia' pronte: nel titolo l'icona e' di 16 pixel, e il "
     "PNG rimpicciolito da Tk viene seghettato. Sugli altri sistemi il PNG, "
     "che Tk legge ovunque."),
    ("q",
     "MAI TUTTI E DUE. La prima versione impostava il PNG con iconphoto e poi "
     "l'ICO con iconbitmap, per prudenza. Nessun errore, il test diceva "
     "'icona caricata', e nel titolo compariva l'icona generica di Windows. "
     "Chiedendolo a Windows (GetClassLongPtr, GCLP_HICONSM) si e' visto "
     "perche': la seconda chiamata toglie alla finestra l'icona PICCOLA, che "
     "e' proprio quella del titolo. Con uno solo dei due file l'icona c'e'. "
     "Il test dell'interfaccia ora controlla quel dato, non il caricamento."),
    ("p",
     "La cartella si cerca in sys._MEIPASS quando il programma e' "
     "impacchettato -- e' li' che PyInstaller mette i file dichiarati in "
     "`datas` -- e accanto al modulo altrimenti. Tutto sta in un try: "
     "un'icona che manca non e' un motivo per non aprire il programma."),
    ("p",
     "Quello che restituisce va TENUTO: __init__ lo mette in self.icona. Su "
     "Windows e' solo il percorso dell'ICO, ma altrove e' una PhotoImage, e "
     "Tk non conserva un riferimento alle immagini: raccolta dal garbage "
     "collector, la finestra tornerebbe all'icona predefinita."),
    ("c", "interfaccia._identita_windows"),
    ("p",
     "Il problema che risolve si vede solo lanciando da CraneStrike.bat o da "
     "python: il processo e' pythonw.exe, e Windows raggruppa la finestra "
     "sotto l'icona di Python sulla barra delle applicazioni, qualunque icona "
     "abbia la finestra. Un AppUserModelID proprio la separa. Va chiamata "
     "prima di creare la finestra, e per questo la chiama main e non "
     "__init__."),
    ("c", "interfaccia.main"),
    ("p",
     "`multiprocessing.freeze_support()` e' la prima riga, e serve solo "
     "all'eseguibile impacchettato: su Windows un processo figlio reimporta il "
     "modulo principale, e senza quella chiamata PyInstaller riaprirebbe la "
     "finestra invece di eseguire il figlio. Un difetto che si manifesta solo "
     "nella versione impacchettata, cioe' proprio dove e' piu' scomodo "
     "diagnosticarlo."),
]


# ==========================================================================
# Documento 2 -- caricare, calcolare, salvare
# ==========================================================================

CALCOLO = [
    ("h1", "interfaccia.py (2) -- caricare, calcolare, salvare"),
    ("p",
     "Secondo dei quattro documenti su interfaccia.py: il giro che l'utente fa "
     "quando ha un file e vuole un risultato."),

    # ==================================================================
    ("h2", "1. Aprire una linea"),
    ("c", "interfaccia.Applicazione._chiedi_file"),
    ("c", "interfaccia.Applicazione._carica"),
    ("p",
     "Legge il file e ne ricava una Configurazione. Gli errori di compilazione "
     "arrivano gia' pronti da excel_io -- tutti insieme, con foglio e cella -- "
     "e qui si mostrano e basta, senza riscriverli."),
    ("c", "interfaccia.Applicazione._riprendi_ciclogramma"),
    ("p",
     "Se il file porta con se' un ciclogramma, lo si rimette in piedi. E' la "
     "controparte del foglio Ciclogramma di excel_io: takt time, tempi in "
     "vasca, assegnazione, e da quei tre valori build_solution ricostruisce "
     "tutto."),
    ("q",
     "RIAPRIRE DEVE DARE LO STESSO CICLOGRAMMA. E' la proprieta' che "
     "test_interfaccia verifica esplicitamente, ed e' anche quella che ha "
     "fatto scoprire due difetti raccontati altrove: il salto di un periodo "
     "quando un istante cade appena sotto un multiplo esatto di T "
     "(_fase_nel_periodo), e le cifre tagliate nel salvataggio. Un formato "
     "compatto vale solo se il giro di andata e ritorno e' esatto."),
    ("c", "interfaccia.Applicazione._crea_modello"),
    ("p",
     "'Nuovo modello Excel...': crea un file gia' compilato con la linea "
     "d'esempio. E' la risposta alla prima domanda di chi non ha ancora "
     "niente."),

    # ==================================================================
    ("h2", "2. Il calcolo in background"),
    ("p",
     "Un calcolo puo' durare minuti. Farlo nel thread della finestra la "
     "congelerebbe: niente si ridisegna, il puntatore diventa una clessidra, e "
     "Windows dopo qualche secondo propone di chiudere il programma che 'non "
     "risponde'. Va quindi fatto altrove, e il risultato riportato indietro."),
    ("c", "interfaccia.Applicazione._calcola_automatico"),
    ("c", "interfaccia.Applicazione._risolvi"),
    ("p",
     "`_risolvi` gira nel thread di lavoro, e il suo docstring e' un "
     "avvertimento in tre parole: niente widget qui dentro. Tkinter non e' "
     "sicuro da usare da piu' thread, e toccare un widget da qui produce "
     "blocchi e sparizioni che non si riproducono mai due volte uguali."),
    ("c", "interfaccia.Applicazione._avvia_lavoro"),
    ("p",
     "Il meccanismo e' una CODA: il thread ci mette dentro il risultato, e la "
     "finestra la controlla ogni 80 ms con `after`. E' il modo canonico di far "
     "parlare un thread con tkinter, ed e' l'unico che non richiede lock."),
    ("p",
     "L'involucro cattura QUALUNQUE eccezione e la mette in coda come testo. "
     "Un'eccezione non catturata in un thread secondario sparisce senza "
     "traccia: il programma resterebbe con la barra di avanzamento che gira "
     "per sempre, senza nessun messaggio."),
    ("q",
     "SI CRONOMETRA QUI, NON DENTRO IL SOLUTORE. Il commento argomenta: "
     "interessa quanto ha aspettato CHI GUARDA LO SCHERMO, e quello comprende "
     "tutti i tentativi di solve_auto_hoists piu' la verifica finale. Il tempo "
     "che OR-Tools riporta in solution.raw e' solo l'ultima chiamata, e su una "
     "linea che prova quattro numeri di carroponti direbbe una frazione del "
     "vero. L'orologio e' MONOTONO, cosi' non salta se cambia l'ora di "
     "sistema."),
    ("p",
     "Ogni lavoro riceve un'Interruzione NUOVA, passata come argomento alla "
     "funzione invece di essere letta da self nel thread: una richiesta di "
     "stop rimasta dal calcolo precedente non deve fermare quello nuovo appena "
     "parte, e il thread non deve dipendere da uno stato della finestra che "
     "nel frattempo potrebbe cambiare."),

    ("h3", "Fermare il calcolo"),
    ("c", "interfaccia.Applicazione._ferma_calcolo"),
    ("p",
     "Il pulsante Ferma chiede lo stop e basta. Non tocca la soluzione, non "
     "chiude niente e non aspetta: il thread di lavoro, fermato, restituisce "
     "il suo risultato nella coda come un calcolo finito, e lo gestisce "
     "_controlla_coda. Cosi' c'e' un solo percorso per la fine di un calcolo, "
     "e non due da tenere d'accordo."),
    ("p",
     "Quel risultato puo' essere di due tipi. Se al momento dello stop c'era "
     "gia' una soluzione valida, la si mostra e la si verifica come le altre, "
     "ma l'origine lo dice: 'la migliore trovata prima dello stop: valida, non "
     "dimostrata ottima' -- anche se l'ultima risoluzione aveva detto OPTIMAL, "
     "perche' e' ottima per le zone provate e le altre non lo sono state. Se "
     "non c'era niente, l'esito e' 'interrotto' e il ciclogramma che si stava "
     "guardando RESTA: chi ferma rinuncia al calcolo nuovo, non al lavoro di "
     "prima. _risolvi in quel caso salta anche la diagnosi, che sarebbero "
     "altre risoluzioni da aspettare su una linea che nessuno ha dimostrato "
     "impossibile."),
    ("p",
     "Lo stop non e' istantaneo -- misurato, fra 0,1 e 0,5 secondi -- e per "
     "questo il pulsante si spegne subito e la barra scrive 'Interruzione in "
     "corso...': un clic che non sembra fare niente viene ripetuto."),

    ("h3", "L'avanzamento: quanto manca"),
    ("p",
     "Un calcolo puo' durare minuti, e una barra che oscilla non dice se manca "
     "un secondo o cinque. Il tempo pero' si scompone in due fattori, e solo "
     "uno dei due e' imprevedibile."),
    ("t", [
        ["fattore", "si sa prima?", "perche'"],
        ["quanti tentativi", "SI', esattamente",
         "combinatoria piu' due prefiltri deterministici"],
        ["quanto dura ognuno", "no",
         "da qualche centesimo a tutto il limite di tempo"],
        ["a quanti carroponti si ferma", "no",
         "e' l'informazione che la ricerca sta cercando"],
    ]),
    ("c", "interfaccia.Applicazione._segnala_tentativo"),
    ("p",
     "Il solutore la chiama prima di ogni tentativo, DAL THREAD DI LAVORO. Non "
     "tocca widget: mette il messaggio nella coda, che e' l'unico modo sicuro "
     "di parlare con la finestra da un altro thread. E' la stessa coda che "
     "porta indietro il risultato, usata per un secondo tipo di messaggio."),
    ("c", "interfaccia.Applicazione._mostra_avanzamento"),
    ("p",
     "I tentativi rimasti si sanno esattamente; quanto durera' ciascuno lo si "
     "MISURA su quelli gia' fatti. Al tentativo k ne sono conclusi k-1, e il "
     "tempo trascorso diviso quelli da' la durata media."),
    ("q",
     "LA STIMA NON COMPARE SUBITO. Con meno di due tentativi conclusi la media "
     "e' un numero solo, e su una grandezza cosi' dispersa non vuol dire "
     "niente: meglio non dire un tempo che dirne uno sbagliato di dieci volte. "
     "Anche dopo resta una stima -- i tentativi che finiscono INFEASIBLE sono "
     "molto piu' rapidi di quelli che trovano una soluzione e devono "
     "dimostrarla ottima -- ma sulle linee di prova cade entro un fattore due, "
     "che basta a rispondere alla sola domanda che ci si pone davvero: "
     "aspetto, o mi alzo?"),
    ("q",
     "E COPRE SOLO QUESTO NUMERO DI CARROPONTI. Se anche l'ultimo tentativo "
     "fallisce, la ricerca ricomincia con un carroponte in piu' e il "
     "conteggio riparte da capo con un totale nuovo. E' una limitazione "
     "onesta, e si vede: il testo dice sempre a quale numero di carroponti si "
     "riferisce. Prima di cominciare non si stima invece niente -- l'unico "
     "numero calcolabile a priori sarebbe il caso peggiore, e sull'esempio "
     "darebbe sei minuti e mezzo contro sei secondi e mezzo reali. Un numero "
     "sessanta volte sbagliato non informa, spaventa."),
    ("p",
     "La barra parte INDETERMINATA e passa a determinata al primo tentativo "
     "segnalato. Con le zone dichiarate a mano nel file Excel il solutore fa "
     "una chiamata sola e non segnala niente, quindi resta a oscillare -- ed "
     "e' giusto: li' non c'e' un avanzamento da mostrare, c'e' un'unica "
     "attesa."),

    ("h3", "Il ritorno del risultato"),
    ("c", "interfaccia.Applicazione._controlla_coda", None,
     "        esito, sol, dati, report = carico"),
    ("p",
     "Si prova a leggere senza bloccare; se la coda e' vuota ci si riarma. Un "
     "'eccezione' produce un messaggio con la traccia completa: e' un difetto "
     "del programma, e nasconderla renderebbe impossibile capirlo."),
    ("q",
     "SI SVUOTA LA CODA, NON SI LEGGE UN MESSAGGIO SOLO. Il commento ne da' la "
     "ragione: i messaggi di avanzamento arrivano piu' in fretta di quanto si "
     "controlli, e leggerne uno per giro li farebbe accumulare. La barra "
     "resterebbe indietro rispetto al calcolo, che e' peggio di non averla. Il "
     "ciclo consuma tutti i 'progresso' e si ferma al primo messaggio di "
     "esito, che e' quello che chiude il lavoro."),
    ("c", "interfaccia.Applicazione._controlla_coda",
     "        esito, sol, dati, report = carico",
     "        self.soluzione, self.dati, self.report = sol, dati, report"),
    ("q",
     "IL CASO PIU' CURATO E' QUELLO IN CUI NON SI TROVA NIENTE. Sei "
     "suggerimenti in ordine di quanto e' probabile che siano loro il "
     "problema, e uno di essi -- infittire passo_controllo_distanza_mm -- si "
     "porta dietro la spiegazione di cosa sia, perche' e' il piu' oscuro e "
     "perche' e' facile scambiarlo per un margine di sicurezza. L'ultima riga "
     "offre la via d'uscita vera: comporlo a mano, e lasciare che il "
     "verificatore dica esattamente cosa manca."),
    ("p",
     "Il tempo di calcolo si dice ANCHE qui, e il commento spiega perche' e' "
     "il caso in cui serve di piu': se il calcolo ha consumato tutto il limite "
     "senza trovare niente, allungarlo e' la prima cosa da provare -- e senza "
     "il numero non si sa se il limite e' stato raggiunto o se la linea e' "
     "davvero infattibile."),
    ("h3", "Quando non si trova niente"),
    ("c", "interfaccia.Applicazione._resoconto_fallimento"),
    ("q",
     "IL REGISTRO C'ERA GIA', E NON VENIVA MOSTRATO. E' il difetto che questo "
     "metodo corregge, e non era innocuo: la ricerca automatica SALTA i numeri "
     "di carroponti per cui le suddivisioni da provare superano il limite, e "
     "senza il registro quel salto era invisibile. Una linea risolvibile con "
     "quattro carroponti poteva sembrare impossibile perche' nessuno aveva "
     "provato con quattro."),
    ("p", "Il resoconto ha tre parti, e ciascuna risponde a una domanda diversa."),
    ("li", "COSA E' STATO PROVATO -- per ogni numero di carroponti: quante "
           "suddivisioni risolte, con quale esito, quante scartate senza "
           "risolverle, e quali non sono state provate affatto;"),
    ("li", "PERCHE' NON RIESCE -- la diagnosi, se ha concluso qualcosa;"),
    ("li", "COSA SI PUO' FARE -- le leve, in ordine di quanto e' probabile che "
           "siano loro."),
    ("q",
     "UNKNOWN E INFEASIBLE VOGLIONO DUE AZIONI OPPOSTE. Il conteggio per stato "
     "e' li' per questo: INFEASIBLE e' una dimostrazione, e allora va cambiata "
     "la linea; UNKNOWN vuol dire solo che il tempo e' scaduto, e allora basta "
     "darne di piu' -- fra quei tentativi potrebbe esserci la soluzione. "
     "Confonderli manda a rifare il lavoro sbagliato, e il messaggio li separa "
     "con un avviso a parte."),
    ("c", "interfaccia.Applicazione._diagnostica"),
    ("p",
     "Gira nel thread di lavoro, subito dopo un calcolo fallito, e indaga "
     "sulla suddivisione col carico piu' equilibrato fra quelle provate con il "
     "numero PIU' ALTO di carroponti: e' quella che aveva piu' margine."),
    ("p",
     "Costa qualche risoluzione in piu' su un calcolo che e' gia' fallito. "
     "Sembra molto e non lo e': l'alternativa e' che l'utente ripeta lo stesso "
     "calcolo tre volte cambiando un parametro a caso ogni volta."),
    ("p",
     "L'except cattura tutto: una diagnosi che fallisce non deve mai portarsi "
     "dietro il risultato del calcolo, che a quel punto e' l'unica cosa che "
     "l'utente ha."),

    ("c", "interfaccia.Applicazione._controlla_coda",
     "        self.soluzione, self.dati, self.report = sol, dati, report", None),
    ("p",
     "Riuscendo, si rimettono a posto tre cose che i commenti difendono una "
     "per una: `modifica_aperta` torna falsa (un risultato del solutore si "
     "LEGGE), la vista torna al ciclogramma (arrivando da 'Calcola man' era "
     "rimasta sul pettine, che e' il foglio su cui si compone), e "
     "`verifica_viva` diventa vera (il solutore ha gia' verificato, quindi da "
     "qui in poi il verdetto resta vivo)."),
    ("p",
     "L'`origine` distingue OPTIMAL da FEASIBLE con parole, non con la sigla: "
     "'ottimo' contro 'soluzione valida, non dimostrata ottima'. E' una "
     "differenza che conta per chi deve decidere se fidarsi del numero."),

    # ==================================================================
    ("h2", "3. Quali pulsanti sono accesi"),
    ("c", "interfaccia.Applicazione._pronto_per_calcolare"),
    ("c", "interfaccia.Applicazione._aggiorna_stato_pulsanti"),
    ("p",
     "Un metodo solo che decide lo stato di tutti i comandi, richiamato dopo "
     "ogni cambiamento. E' la scelta giusta: distribuire le abilitazioni nei "
     "punti in cui lo stato cambia porta inevitabilmente a un pulsante che "
     "resta acceso quando non dovrebbe, e quel difetto non da' nessun errore "
     "-- solo un comando che poi non funziona."),
    ("p",
     "E' anche il metodo che i test dell'interfaccia interrogano di piu': "
     "verificare che un pulsante si accenda al momento giusto e' verificare "
     "che gli stati siano coerenti."),

    # ==================================================================
    ("h2", "4. Salvare"),
    ("c", "interfaccia.Applicazione._salva"),
    ("p",
     "Scrive il file dei risultati, che e' anche un file di ingresso: gli si "
     "passano `cfg` e il dizionario del ciclogramma, e cosi' lo stesso file si "
     "riapre con 'Apri linea...'. E' lo stesso formato che produce il comando "
     "da terminale -- uno solo, non due."),
    ("c", "interfaccia.Applicazione._salva_immagine"),
    ("q",
     "SI SALVA IL CICLOGRAMMA, NON QUELLO CHE E' A SCHERMO. Il docstring lo "
     "dice in maiuscolo. Se l'utente sta componendo, a schermo c'e' il "
     "PETTINE: salvarlo darebbe un'immagine che non e' il ciclogramma e che "
     "nessuno saprebbe leggere fuori dal programma. L'immagine si costruisce "
     "quindi da capo, sempre come traiettorie dei carroponti. E' una delle "
     "poche volte in cui il programma NON fa quello che sembra -- e la scelta "
     "e' giusta, perche' quello che si consegna e' il ciclogramma."),
]


# ==========================================================================
# Documento 3 -- comporre e modificare
# ==========================================================================

MODIFICA = [
    ("h1", "interfaccia.py (3) -- comporre e modificare a mano"),
    ("p",
     "Terzo dei quattro documenti su interfaccia.py. E' la parte che rende il "
     "programma qualcosa di piu' di un risolutore: si compone un ciclogramma "
     "come si e' sempre fatto su carta, e il solutore diventa una seconda "
     "opinione invece che un oracolo."),

    # ==================================================================
    ("h2", "Il principio: tutto passa da _ricomponi"),
    ("c", "interfaccia", "# Il ciclogramma: comporlo", "    def _stato_da_soluzione"),
    ("p",
     "Il commento di sezione enuncia la regola: cambio del takt, dei tempi in "
     "vasca, dell'assegnazione, trascinamento sul grafico -- tutto passa da "
     "_ricomponi(). E che il ciclogramma venga dal solutore o sia stato "
     "composto da zero non fa differenza: il solutore fornisce solo lo stato "
     "di partenza, e da li' in poi e' lo stesso oggetto modificato nello "
     "stesso modo."),
    ("c", "interfaccia.Applicazione._stato_da_soluzione"),
    ("q",
     "E' IL FATTO CHE RENDE POSSIBILE UNA PAGINA SOLA. Il docstring lo "
     "dichiara: i tempi in vasca sono le differenze della catena dei prelievi "
     "meno la durata del trasporto, e ricomporre il ciclogramma da quei valori "
     "restituisce ESATTAMENTE lo stesso ciclogramma -- stesso takt, stesso "
     "esito, nessuna incoerenza. Senza questa proprieta' ci sarebbero due "
     "editor, uno per i risultati del solutore e uno per i ciclogrammi "
     "manuali, e il primo sarebbe di sola lettura."),
    ("c", "interfaccia.Applicazione._ricomponi"),
    ("q",
     "NON RIFIUTA MAI NIENTE. Il docstring: manuale.componi disegna anche "
     "l'impossibile, e rifiutare una modifica vorrebbe dire rimettere i "
     "controlli proprio dove si e' scelto di toglierli -- e il verificatore li "
     "fa meglio. E' la stessa filosofia di manuale.py, applicata "
     "all'interfaccia: si mostra cosa non torna invece di impedirlo."),

    # ==================================================================
    ("h2", "1. Entrare e uscire dalla modifica"),
    ("c", "interfaccia.Applicazione._vai_a_modifica"),
    ("p",
     "Il docstring chiarisce cosa NON fa: non sceglie fra una versione "
     "automatica e una manuale -- ce n'e' una sola -- ne' cambia niente. E' il "
     "momento in cui si dichiara di voler mettere le mani su un risultato, che "
     "e' diverso dal guardarlo."),
    ("q",
     "SI MODIFICA SEMPRE SUL PETTINE. Anche un ciclogramma appena calcolato. "
     "Il commento ne da' la ragione: il ciclogramma disegna le traiettorie dei "
     "CARROPONTI, e un trasporto che non e' ancora di nessuno -- o che si e' "
     "appena tolto a qualcuno -- li' non compare. Resterebbe invisibile e per "
     "giunta cliccabile, 'che e' il peggio'. Nel pettine il pezzo passa "
     "comunque, grigio finche' nessuno lo porta."),
    ("p",
     "L'ordine delle ultime chiamate non e' indifferente: prima si sblocca la "
     "scheda con _aggiorna_stato_pulsanti, poi la si seleziona. Selezionare "
     "una scheda disabilitata non fa niente e non da' errore."),
    ("c", "interfaccia.Applicazione._chiudi_modifica"),
    ("p",
     "Il docstring spiega perche' serve un'uscita: la modifica porta sul "
     "pettine, e senza un modo di uscirne chi ha ritoccato un tempo in vasca "
     "non rivedrebbe piu' il ciclogramma se non ricalcolandolo da capo. E "
     "precisa che non e' l'interruttore fra due viste che era stato tolto: e' "
     "l'uscita da uno stato di lavoro."),
    ("c", "interfaccia.Applicazione._componi_da_zero"),
    ("q",
     "SI PARTE DA NIENTE ASSEGNATO. Il commento difende la scelta contro "
     "l'alternativa apparentemente piu' gentile: partire da una suddivisione "
     "gia' fatta 'significava non avere mai niente da assegnare -- si restava "
     "a correggere una proposta invece di comporre'. Il pettine parte tutto "
     "grigio ed e' l'utente a darlo ai carroponti una mossa per volta, che e' "
     "il modo in cui un ciclogramma si traccia."),
    ("p",
     "`verifica_viva` resta falsa: si riparte da uno stato dichiaratamente "
     "provvisorio, e il verdetto arriva quando lo si chiede."),

    # ==================================================================
    ("h2", "2. La scheda, e i campi"),
    ("c", "interfaccia.Applicazione._costruisci_scheda_ciclogramma"),
    ("p",
     "La pagina unica in cui il ciclogramma si modifica: takt time, numero di "
     "carroponti, la tabella dei tempi in vasca e quella dell'assegnazione. "
     "Gli stessi tre gradi di liberta', in forma di campi."),
    ("c", "interfaccia.Applicazione._sincronizza_campi"),
    ("p",
     "Riporta nei campi i valori dello stato. Serve dopo ogni modifica fatta "
     "ALTROVE -- un trascinamento sul grafico, un annullamento -- perche' i "
     "campi e il grafico sono due viste dello stesso stato e devono restare "
     "d'accordo."),
    ("c", "interfaccia.Applicazione._popola_tabelle"),
    ("c", "interfaccia.Applicazione._carro_della_zona"),

    # ==================================================================
    ("h2", "3. I quattro modi di cambiare qualcosa"),
    ("c", "interfaccia.Applicazione._modifica_takt"),
    ("c", "interfaccia.Applicazione._modifica_permanenza"),
    ("c", "interfaccia.Applicazione._cambia_carroponti"),
    ("p",
     "Lo spinbox dei carroponti ridistribuisce le mosse in blocchi contigui. "
     "E' l'unico comando che tocca l'assegnazione tutta insieme, e lo fa "
     "perche' cambiare il numero di carroponti senza ridistribuire lascerebbe "
     "mosse assegnate a un carroponte che non esiste piu'."),
    ("c", "interfaccia.Applicazione._modifica_numero_carroponti"),
    ("p",
     "'Ottimizza con questi carroponti': rifa' il calcolo tenendo fisso il "
     "numero e lasciando scegliere le zone. E' la via di mezzo fra il calcolo "
     "completamente automatico e la composizione a mano -- si sa quanti "
     "carroponti si hanno, non come dividerli."),
    ("c", "interfaccia.Applicazione._assegna"),
    ("q",
     "LO STESSO GESTO ASSEGNA E TOGLIE. Il docstring: si da' la mossa al "
     "carroponte attivo, o gliela si toglie se era gia' sua. E' la scelta che "
     "rende la composizione un lavoro fluido: non serve un comando 'togli', "
     "non serve selezionare prima. Si clicca finche' il disegno non e' quello "
     "che si vuole."),
    ("p",
     "Prima di assegnare si chiede a manuale.perche_non_va se l'assegnazione "
     "sarebbe geometricamente impossibile -- due carroponti che dovrebbero "
     "scavalcarsi sulla stessa rotaia. E' l'unico rifiuto di tutta la "
     "composizione, e il messaggio spiega quali carroponti e quali vasche."),
    ("c", "interfaccia.Applicazione._assegna_da_tabella"),
    ("p",
     "Lo stesso, dalla tabella invece che dal grafico. Due strade per lo "
     "stesso gesto: il grafico e' piu' rapido, la tabella e' piu' precisa "
     "quando i trasporti sono fitti."),

    # ==================================================================
    ("h2", "4. Annullare"),
    ("c", "interfaccia.Applicazione._istantanea"),
    ("c", "interfaccia.Applicazione._annulla_modifica"),
    ("p",
     "L'annullamento e' una pila di ISTANTANEE dello stato -- takt, "
     "permanenze, assegnazione -- non di comandi inversi. E' molto piu' "
     "semplice da rendere corretto: uno stato ripristinato e' esattamente "
     "quello di prima, mentre un comando inverso puo' sempre avere un caso "
     "che non copre."),
    ("p",
     "Costa memoria, e qui non e' un problema: lo stato sono tre dizionari "
     "piccoli, e le modifiche in una sessione sono decine, non milioni."),

    # ==================================================================
    ("h2", "5. Il verdetto"),
    ("c", "interfaccia.Applicazione._verifica_adesso"),
    ("c", "interfaccia.Applicazione._popola_verifica"),
    ("c", "interfaccia.Applicazione._esito_breve"),
    ("c", "interfaccia.Applicazione._aggiorna_banner_e_riepilogo"),
    ("p",
     "Il verdetto sta sempre in vista, sopra le schede, e cambia colore con la "
     "gravita' peggiore trovata. E' la scelta che rende la composizione a mano "
     "praticabile: si vede subito se l'ultima modifica ha risolto o rotto "
     "qualcosa, senza dover andare a cercare."),
    ("p",
     "Il riepilogo raccoglie tutto quello che si vorrebbe sapere di un "
     "ciclogramma: takt, produttivita', carroponti, separazione minima, "
     "permanenza piu' stretta, tempo di calcolo, e da dove viene il "
     "ciclogramma che si sta guardando. E' anche il testo che finisce nel "
     "foglio Riepilogo del file dei risultati."),
]


# ==========================================================================
# Documento 4 -- il grafico, il mouse, la simulazione
# ==========================================================================

GRAFICO = [
    ("h1", "interfaccia.py (4) -- il grafico, il mouse, la simulazione"),
    ("p",
     "Quarto e ultimo documento su interfaccia.py: come si disegna, come si "
     "clicca, e come si apre la vista in movimento."),

    # ==================================================================
    ("h2", "1. I due disegni"),
    ("c", "interfaccia.Applicazione._mostra_ciclogramma"),
    ("p",
     "Sceglie quale dei due disegnare secondo `self.vista`, e riapplica "
     "l'inquadratura se l'utente ne aveva scelta una."),
    ("c", "interfaccia.Applicazione._disegna_traiettorie"),
    ("p",
     "Il ciclogramma vero e proprio, delegato a plotting.plot_cyclogram sullo "
     "stesso asse. E' la stessa funzione che produce il PNG e quella che usa "
     "il comando da terminale: un solo disegno, non tre."),
    ("c", "interfaccia.Applicazione._disegna_pettine"),
    ("p",
     "Il foglio su cui si compone: una scalinata per ogni pezzo in "
     "lavorazione, e i trasporti colorati per carroponte. Quello che nessuno "
     "ha ancora preso resta grigio e sottile."),
    ("q",
     "IL GRIGIO NON E' UN COLORE FRA GLI ALTRI. Con la disciplina dichiarata "
     "in testa al modulo -- un solo grigio per cio' che non e' deciso, due "
     "soli spessori -- il disegno risponde a colpo d'occhio alla sola domanda "
     "che conta durante la composizione: cosa manca ancora. Dando un colore "
     "anche ai trasporti liberi, quella domanda richiederebbe di leggere."),
    ("p",
     "Anche il pettine porta i suoi PUNTI, e sono i QUATTRO che il ciclogramma "
     "marca su ogni trasporto -- aggancio, partenza, arrivo, immersione -- "
     "presi da plotting.eventi_del_trasporto, cioe' dall'unica definizione che "
     "hanno. Servono perche' su una linea con molte tappe un trasporto corto "
     "non si distingue da una sosta se non seguendo la pendenza, e la pendenza "
     "su pochi pixel non si vede."),
    ("q",
     "IL GIRO SI POSA SUI PUNTI CHE ERANO GIA' LI'. E' la proprieta' per cui i "
     "punti valgono la pena: assegnando una mossa, i quattro istanti che il "
     "carroponte marca cadono ESATTAMENTE su quelli che il pettine mostrava in "
     "grigio. Sono lo stesso fatto visto dal pezzo e dal carroponte. Prima il "
     "giro ne marcava due -- i soli estremi della traslazione -- e assegnare "
     "sembrava cambiare cio' che il pezzo fa; ora i due disegni si "
     "sovrappongono, e test_interfaccia lo verifica confrontando le due liste "
     "modulo il takt time."),
    ("p",
     "A quale mossa appartiene ogni tratto della scalinata lo dice "
     "manuale.mosse_del_pettine, non un contatore: la scalinata ha un tratto a "
     "carico per mossa, ma dedurlo dall'ordine sarebbe un'ipotesi sulla "
     "costruzione invece di una domanda a chi la costruisce."),
    ("p",
     "Sono piu' piccoli e senza bordo bianco di quelli dei carroponti: il "
     "pettine e' lo sfondo su cui si lavora, e deve restare leggibile SOTTO il "
     "giro che si sta componendo invece di contendergli l'occhio."),
    ("q",
     "UN DISEGNO SOLO, CON I NaN A SEPARARE I TRATTI. Vale per il pettine come "
     "per i carroponti poco piu' sotto: con dieci scalinate e diciassette "
     "mosse, una chiamata di disegno per tratto sono seicento artisti -- e di "
     "ritocchi se ne fanno molti di seguito, ciascuno dei quali ridisegna "
     "tutto da capo. Raggruppando, il pettine intero sta in due chiamate: la "
     "linea e i punti."),

    # ==================================================================
    ("h2", "2. Cliccare e trascinare"),
    ("c", "interfaccia.Applicazione._punti_prelievo"),
    ("c", "interfaccia.Applicazione._tratti_trasporto"),
    ("p",
     "Le due geometrie su cui il mouse lavora: i punti di prelievo (le "
     "maniglie) e i tratti dei trasporti (le zone cliccabili). Si ricavano "
     "dalle stesse funzioni di manuale.py che producono il disegno, non da un "
     "calcolo parallelo -- altrimenti la zona sensibile e quello che si vede "
     "potrebbero non coincidere."),
    ("c", "interfaccia.Applicazione._trasporto_sotto"),
    ("q",
     "SI MISURA IN PIXEL. Il docstring lo argomenta: in coordinate dati un "
     "secondo e un millimetro non sono paragonabili, e la tolleranza sarebbe "
     "assurda. Una soglia di 12 pixel vuol dire la stessa cosa a qualunque "
     "ingrandimento, mentre una soglia in secondi diventerebbe enorme "
     "ingrandendo e microscopica allargando."),
    ("c", "interfaccia.Applicazione._su_pressione"),
    ("q",
     "IL GRAFICO STA FUORI DALLA SCHEDA. Il commento spiega perche' qui si "
     "ricontrolla `modifica_aperta`: il cancello della scheda non copre il "
     "grafico, quindi senza questo controllo trascinare un prelievo su un "
     "risultato appena calcolato lo modificherebbe senza che nessuno abbia "
     "detto di volerlo. E' la stessa difesa che _vai_a_modifica costruisce, "
     "rifatta dove serve."),
    ("p",
     "Il commento lungo distingue DUE bersagli con due raggi diversi, e la "
     "ragione e' nel gesto:"),
    ("li", "il PUNTO DI PRELIEVO e' la maniglia per trascinare -- il tempo in "
           "vasca si allunga da li', quindi il trascinamento ha senso solo "
           "prendendolo per quell'estremo. Raggio stretto, 18 pixel;"),
    ("li", "il TRATTO si clicca dove lo vedi, per tutta la sua lunghezza: "
           "assegnare una mossa a un carroponte non ha niente a che fare con "
           "un estremo particolare, e 'obbligare a centrare la vasca di "
           "partenza era una precisione chiesta senza motivo'."),
    ("p",
     "L'istantanea dello stato viene presa alla PRESSIONE, non al rilascio: "
     "cosi' l'annullamento riporta a prima del gesto, qualunque cosa il gesto "
     "sia risultato essere."),
    ("c", "interfaccia.Applicazione._su_movimento"),
    ("p",
     "Durante il trascinamento si mostra una guida verticale arancione e si "
     "scrive lo spostamento nella barra di stato. Non si ricompone niente: "
     "ricostruire il ciclogramma a ogni pixel sarebbe lento e "
     "illeggibile. Due casi non trascinano affatto -- una pressione a meta' "
     "tratto (nessuna maniglia) e la mossa 0, che e' l'origine dei tempi."),
    ("c", "interfaccia.Applicazione._su_rilascio"),
    ("q",
     "CLIC SECCO O TRASCINAMENTO? SI MISURA IN PIXEL. Il commento: in secondi "
     "la soglia dipenderebbe da quanto si e' ingrandito il grafico. Sotto i 4 "
     "pixel e' un clic, e allora si assegna; sopra e' un trascinamento, e si "
     "cambia il tempo in vasca. E' lo stesso gesto fisico che significa due "
     "cose, e la distinzione deve essere stabile."),
    ("p",
     "Trascinare la mossa 0 non da' un errore: da' una spiegazione. Il primo "
     "prelievo fissa l'origine dei tempi, e per spostarlo si cambiano i tempi "
     "in vasca a valle."),
    ("c", "interfaccia.Applicazione._mostra_dettaglio"),

    # ==================================================================
    ("h2", "3. L'inquadratura"),
    ("c", "interfaccia.Applicazione._segna_zoom"),
    ("c", "interfaccia.Applicazione._azzera_zoom"),
    ("c", "interfaccia.Applicazione._vista_corrente"),
    ("c", "interfaccia.Applicazione._riapplica_vista"),
    ("c", "interfaccia.Applicazione._reimposta_grafico"),
    ("p",
     "Cinque metodi per una sola esigenza: il grafico viene ridisegnato da "
     "zero a ogni modifica, e l'inquadratura scelta dall'utente deve "
     "sopravvivere al ridisegno."),
    ("q",
     "MA NON A TUTTI I RIDISEGNI. _reimposta_grafico esiste per il caso "
     "opposto: quando il grafico cambia NATURA -- un'altra linea, o il "
     "passaggio da ciclogramma a pettine -- l'inquadratura precedente non "
     "vuol piu' dire niente, perche' cambia la scala dei tempi. Conservarla "
     "lascerebbe l'utente a guardare un rettangolo vuoto senza capire "
     "perche'."),
    ("c", "interfaccia.Applicazione._su_rotella"),
    ("p",
     "Zoom con la rotella, centrato dove sta il puntatore. E' il gesto che "
     "tutti si aspettano da un grafico, e senza si e' costretti a passare "
     "dalla barra ogni volta."),
    ("c", "interfaccia.Applicazione._navigazione_attiva"),
    ("p",
     "Vero quando e' selezionato lo zoom a rettangolo o lo spostamento. "
     "Serve a _su_pressione per farsi da parte: in quel momento il clic e' "
     "della barra, non dell'editor. Senza, ingrandire una zona assegnerebbe "
     "anche un trasporto."),

    # ==================================================================
    ("h2", "4. La simulazione"),
    ("c", "interfaccia.Applicazione._apri_simulazione"),
    ("p",
     "Mostra il ciclogramma corrente in movimento, in una finestra a se'. Si "
     "apre solo quando un ciclogramma c'e' davvero -- e' una delle cose che "
     "_aggiorna_stato_pulsanti governa."),
    ("c", "interfaccia.Applicazione._simulazione_chiusa"),
    ("c", "interfaccia.Applicazione._aggiorna_simulazione"),
    ("q",
     "LA SIMULAZIONE SEGUE LE MODIFICHE MENTRE E' APERTA. E' la ragione per "
     "cui e' una finestra separata e non una scheda: si modifica da una parte "
     "e si vede l'effetto dall'altra, senza chiudere e riaprire. Ogni "
     "_ricomponi passa di qui, e la finestra si aggiorna da sola."),
    ("c", "interfaccia.Applicazione._carri_delle_zone"),
    ("p",
     "Quale carroponte corrisponde a ogni zona. Serve perche' durante la "
     "composizione le zone vengono riempite per continuita' -- e' la finzione "
     "di manuale.zone_coprenti -- e l'indice di zona non e' piu' il numero del "
     "carroponte. Le zone senza nessuna mossa assegnata si omettono passando "
     "None, ed e' esattamente il parametro `carri` che Simulazione documenta."),
]


DOCUMENTI = [
    ("interfaccia_1_finestra.docx", FINESTRA),
    ("interfaccia_2_calcolo.docx", CALCOLO),
    ("interfaccia_3_modifica.docx", MODIFICA),
    ("interfaccia_4_grafico.docx", GRAFICO),
]
