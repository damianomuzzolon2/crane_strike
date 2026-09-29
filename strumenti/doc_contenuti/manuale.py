"""
Il testo dei documenti di manuale.py.

Dodici funzioni, tutte piccole, ma il modulo regge una scelta di fondo del
programma: durante il disegno a mano NON si rifiuta niente. Quasi tutti i
docstring del file spiegano un controllo che si e' deciso di non fare, ed e'
quella la parte che questo documento riprende.
"""

from __future__ import annotations

# --------------------------------------------------------------------------

RIGA_PER_RIGA = [
    ("h1", "manuale.py spiegato riga per riga"),
    ("p",
     "Questo documento accompagna la lettura di manuale.py, il modulo che "
     "sostiene il disegno a mano del ciclogramma. Ogni blocco di codice e' "
     "estratto dal sorgente al momento della generazione."),
    ("p",
     "E' il modulo che rende il programma qualcosa di piu' di un risolutore. "
     "Senza di lui l'utente potrebbe solo premere 'calcola' e accettare quello "
     "che esce; con lui puo' comporre il ciclogramma come ha sempre fatto su "
     "carta, e usare il solutore come una seconda opinione invece che come un "
     "oracolo."),

    # ==================================================================
    ("h2", "Il pettine, e perche' si disegna cosi'"),
    ("p",
     "I ciclogrammi si tracciano a mano da molto prima che esistessero i "
     "solutori, e il metodo e' sempre lo stesso. Prima si disegna il PETTINE: "
     "una scalinata per ogni pezzo in lavorazione, che sale di vasca in vasca "
     "e si ferma per il tempo di processo. Le scalinate sono tutte identiche, "
     "sfasate di un takt time l'una dall'altra -- da cui il nome, perche' il "
     "disegno somiglia ai denti di un pettine."),
    ("p",
     "Poi si tirano le linee dei carroponti: si guarda il pettine, si decide "
     "quali trasporti fa ciascun carroponte, e si controlla che riesca ad "
     "arrivare in tempo da uno all'altro. Il pettine dice COSA va fatto e "
     "quando; l'assegnazione dice CHI lo fa."),
    ("p",
     "Il modulo riproduce esattamente questi due passi, ed e' per questo che "
     "il pettine e le traiettorie dei carroponti usano gli STESSI tipi di "
     "segmento: l'utente clicca su un trasporto del pettine e quel tratto "
     "diventa un pezzo del giro di un carroponte, senza conversioni."),

    ("q",
     "QUI NON SI RIFIUTA NIENTE. E' la regola del modulo, scritta "
     "nell'intestazione del file e ripetuta in quasi tutti i docstring. "
     "L'utente compone come vuole, anche cose fisicamente impossibili, e le "
     "incoerenze vengono DESCRITTE invece che bloccate. Il motivo e' pratico: "
     "un ciclogramma a meta' e' quasi sempre incoerente -- mancano trasporti, "
     "i tempi non tornano -- e un programma che si rifiutasse di disegnarlo "
     "renderebbe impossibile il lavoro in corso. La verifica vera si fa alla "
     "fine, su richiesta, con verify.py."),

    ("c", "manuale", "RIPETIZIONI_PREDEFINITE", "def permanenze_iniziali"),
    ("p",
     "Dieci scalinate. Non e' un limite del calcolo ma una scelta di leggibilita': "
     "sono i pezzi contemporaneamente in lavorazione che si vogliono VEDERE. "
     "Dieci bastano a coprire qualunque linea reale e a far capire come i "
     "cicli si incastrano fra loro; molte di piu' riempirebbero il disegno "
     "senza aggiungere informazione."),

    # ==================================================================
    ("h2", "1. La scalinata di un pezzo"),

    ("h3", "permanenze_iniziali -- da dove si parte"),
    ("c", "manuale.permanenze_iniziali"),
    ("p",
     "Il punto di partenza e' il pettine che la RICETTA descrive: ogni pezzo "
     "sta in ogni vasca il suo tempo teorico. E' quasi certamente "
     "irrealizzabile cosi' com'e', perche' i carroponti non ce la faranno, e "
     "va benissimo: da li' l'utente sposta dove serve, e ogni spostamento e' "
     "una decisione consapevole."),
    ("p",
     "Partire dal teorico invece che dal minimo non e' indifferente. Il "
     "teorico e' l'unico valore che qualcuno ha scelto davvero; il minimo e' "
     "un estremo di tolleranza, e partire di li' voleva dire cominciare con "
     "ogni vasca gia' appiccicata al limite basso -- tutto il margine da una "
     "parte sola, e ogni ritocco possibile in una direzione soltanto. Dal "
     "teorico il margine c'e' in tutti e due i versi, e si spende dove il "
     "ciclogramma lo chiede."),
    ("p",
     "Si noti che l'intervallo parte da 1, non da 0: la stazione 0 e' il "
     "carico, dove il pezzo non 'sta' -- ci viene messo. Le permanenze sono "
     "n_moves - 1, una per ogni vasca intermedia."),

    ("h3", "catena_pezzo -- gli istanti di prelievo"),
    ("c", "manuale.catena_pezzo"),
    ("p",
     "Cinque righe che sono la spina dorsale del modulo. Dati i tempi in "
     "vasca, restituiscono gli istanti in cui UN pezzo viene prelevato da "
     "ciascuna stazione. Il primo prelievo e' l'origine dei tempi, e ogni "
     "successivo e' il precedente piu' la durata del trasporto piu' la "
     "permanenza nella vasca in cui si arriva."),
    ("p",
     "loaded_leg_seconds(k - 1) e' la durata COMPLETA del trasporto: presa, "
     "traslazione e rilascio. Non solo la traslazione. E' il motivo per cui "
     "la scalinata di un pezzo ha gradini piu' lunghi di quanto suggerirebbe "
     "la sola distanza fra le vasche."),
    ("p",
     "Il `permanenze.get(k, ...)` con il valore di ripiego permette di passare "
     "un dizionario incompleto: le vasche non specificate prendono il minimo "
     "di processo. Serve mentre l'utente sta ancora componendo."),

    ("h3", "_segmenti_e_mosse -- dove sta il lavoro vero"),
    ("c", "manuale._segmenti_e_mosse"),
    ("p",
     "Trasforma la scalinata in segmenti disegnabili, e a ciascuno attacca il "
     "numero della mossa a cui appartiene. Per ogni trasporto produce fino a "
     "quattro tratti: presa, traslazione a carico, rilascio, e la sosta in "
     "vasca fino al prelievo successivo."),
    ("p",
     "Presa e rilascio vengono aggiunti solo se durano davvero (t_presa > t0). "
     "Su una stazione senza corsa verticale la presa e' istantanea, e un "
     "segmento di durata zero non e' un tratto: e' un punto che confonderebbe "
     "chi lo cerca cliccando."),
    ("q",
     "LA SOSTA APPARTIENE ALLA MOSSA SUCCESSIVA. E' la riga meno ovvia del "
     "modulo, e il commento nel codice la difende. Il pezzo sta fermo in "
     "vasca dopo essere stato lasciato dalla mossa k, quindi l'istinto dice "
     "che la sosta sia 'della mossa k'. Ma quello che l'utente ASSEGNA sono i "
     "trasporti, e la sosta serve a colorare il tratto in funzione di chi "
     "verra' a prendere il pezzo: e' un vincolo per il carroponte della mossa "
     "k+1, che deve arrivare li' entro quel momento. Attribuirla alla mossa k "
     "colorerebbe l'attesa col carroponte che se n'e' gia' andato."),

    ("h3", "segmenti_pezzo e mosse_del_pettine -- le due meta' dello stesso conto"),
    ("c", "manuale.segmenti_pezzo"),
    ("c", "manuale.mosse_del_pettine"),
    ("p",
     "Due funzioni di una riga che prendono, della stessa costruzione, la "
     "prima o la seconda meta' di ogni coppia. Sarebbe stato possibile "
     "esporre direttamente _segmenti_e_mosse; averle separate rende chiaro nei "
     "punti di chiamata se si sta disegnando o se si sta colorando."),
    ("q",
     "PERCHE' LA MOSSA NON SI INDOVINA DALLE COORDINATE. Il docstring di "
     "mosse_del_pettine lo dice a chiare lettere: la mossa si ricava dalla "
     "COSTRUZIONE, non dalla posizione del segmento. Dedurla dalle coordinate "
     "-- 'questo tratto sta all'altezza della vasca 4, quindi e' la mossa 4' -- "
     "funziona finche' ogni vasca compare una volta sola nella ricetta, e "
     "sbaglia appena una vasca ci compare due volte. Che e' un caso ammesso, e "
     "sulle linee vere frequente: un'immersione ripetuta, un risciacquo che "
     "torna."),

    # ==================================================================
    ("h2", "2. Chi fa cosa: l'assegnazione"),

    ("h3", "perche_non_va -- il solo divieto del modulo"),
    ("c", "manuale.perche_non_va"),
    ("p",
     "In un modulo che non rifiuta niente, questa e' l'unica funzione che dice "
     "di no. E il suo docstring spiega esattamente perche' questo caso e' "
     "diverso da tutti gli altri: non e' un controllo sul CICLOGRAMMA -- quelli "
     "sono sospesi durante il disegno -- ma sulla GEOMETRIA."),
    ("p",
     "I carroponti stanno tutti sulla stessa rotaia e non possono scavalcarsi. "
     "Se il carroponte 2 dovesse servire una vasca che sta prima di quelle del "
     "carroponte 1, dovrebbe passargli attraverso. Non e' una limitazione del "
     "calcolo che si possa allentare dando piu' tempo o piu' tolleranza: e' la "
     "rotaia. Un ciclogramma cosi' non e' 'difficile', e' impossibile da "
     "costruire, e disegnarlo non aiuterebbe l'utente a capire niente."),
    ("p",
     "Il controllo e' semplicissimo: scorre le mosse in ordine e verifica che "
     "il numero di carroponte non torni mai indietro. Il messaggio pero' non "
     "si limita a dire che c'e' un incrocio: nomina i due carroponti, la mossa "
     "e le due vasche coinvolte, perche' l'utente possa vedere sul disegno di "
     "cosa si sta parlando."),
    ("q",
     "LE MOSSE NON ASSEGNATE NON SONO UN ERRORE. Il secondo paragrafo del "
     "docstring difende un'assenza. Si parte da niente assegnato e si assegna "
     "una mossa per volta: un'assegnazione incompleta e' lo stato NORMALE del "
     "lavoro in corso, non un difetto. Se questa funzione la segnalasse, "
     "l'utente vedrebbe un errore rosso dal primo clic all'ultimo. Che manchi "
     "qualcosa lo dice componi() fra le incoerenze, dove serve. Questa "
     "funzione risponde a una domanda sola: 'posso dare questa mossa a questo "
     "carroponte?'."),

    ("h3", "zone_coprenti -- riempire i buchi per le strutture dati"),
    ("c", "manuale.zone_coprenti"),
    ("p",
     "Le strutture dati del modello pretendono che le zone coprano TUTTE le "
     "mosse: una HoistZone e' un intervallo, e l'insieme delle zone deve "
     "essere una partizione. Ma durante il disegno a mano le mosse assegnate "
     "sono quasi sempre un sottoinsieme."),
    ("p",
     "La funzione risolve il conflitto propagando in avanti l'ultimo "
     "carroponte visto: una mossa scoperta viene accorpata a quello che l'ha "
     "preceduta. E' una finzione, e il docstring la dichiara tale -- 'ai soli "
     "fini della struttura'. Quelle mosse non compaiono in nessun giro, "
     "perche' componi() passa a build_solution l'insieme delle mosse "
     "REALMENTE attive; e vengono segnalate all'utente come mancanti."),
    ("p",
     "Il secondo ciclo comprime la lista dei carroponti in intervalli, "
     "chiudendo una zona ogni volta che il numero cambia. La condizione "
     "`k == data.n_moves` chiude l'ultima."),

    # ==================================================================
    ("h2", "3. Comporre e disegnare"),

    ("h3", "componi -- dal disegno al ciclogramma"),
    ("c", "manuale.componi"),
    ("p",
     "E' la funzione che chiude il giro. Prende i gradi di liberta' -- takt "
     "time, permanenze, assegnazione, e le soste se qualcuno le ha gia' "
     "scelte -- e ne ricava una Solution vera, con le traiettorie "
     "ricostruite, chiamando lo stesso build_solution che usa il solutore."),
    ("p", "Tre argomenti di quella chiamata meritano attenzione:"),
    ("li", "status='MANUALE' -- la soluzione si dichiara per quello che e'. "
           "Non e' una decorazione: plotting.py e verify.py filtrano sugli "
           "stati, e MANUALE deve essere disegnabile e verificabile come le "
           "altre;"),
    ("li", "tollerante=True -- e' l'interruttore che spegne i rifiuti. Con "
           "questo, build_solution costruisce anche cio' che non sta in piedi "
           "e raccoglie le incoerenze invece di sollevare un'eccezione;"),
    ("li", "mosse_attive -- l'insieme delle mosse davvero assegnate, che "
           "annulla la finzione di zone_coprenti."),
    ("p",
     "Le incoerenze arrivano da build_solution, e a queste la funzione "
     "aggiunge in TESTA -- non in coda -- l'elenco delle mosse non ancora "
     "assegnate. In testa perche' e' l'incoerenza piu' facile da correggere e "
     "quella che spiega quasi sempre tutte le altre: un ciclogramma con dei "
     "buchi ha i tempi che non tornano ovunque, e mettere quel messaggio in "
     "fondo a venti righe lo renderebbe invisibile."),

    ("h3", "pettine -- le dieci scalinate"),
    ("c", "manuale.pettine"),
    ("p",
     "La scalinata viene costruita UNA volta sola e poi ricopiata sfasata di "
     "un takt time. Non e' solo un risparmio: e' la garanzia che le scalinate "
     "siano davvero identiche. Ricalcolarle una per una lascerebbe aperta la "
     "possibilita' che, per un arrotondamento, la settima venga leggermente "
     "diversa dalla prima -- e il pettine serve proprio a far vedere che sono "
     "uguali."),
    ("p",
     "dataclasses.replace crea copie con i tempi traslati invece di modificare "
     "gli originali. Segment e' immutabile e i segmenti di base vengono "
     "riusati a ogni ripetizione: modificarli sul posto sposterebbe anche le "
     "scalinate gia' prodotte."),

    # ==================================================================
    ("h2", "4. Tre funzioni che nessuno chiama"),
    ("p",
     "L'albero delle chiamate, generato leggendo i sorgenti, dice che tre "
     "funzioni di questo modulo non sono chiamate da nessun punto del "
     "progetto. Vale la pena distinguerle, perche' non sono lo stesso caso."),
    ("t", [
        ["funzione", "situazione"],
        ["assegnazione_iniziale", "mai chiamata, ma dichiaratamente pubblica"],
        ["zone_da_assegnazione", "sostituita da zone_coprenti"],
        ["trasporti_cliccabili", "sostituita dal giro segmenti_pezzo + "
                                 "mosse_del_pettine"],
    ]),

    ("h3", "assegnazione_iniziale"),
    ("c", "manuale.assegnazione_iniziale"),
    ("p",
     "Spartisce le mosse il piu' uniformemente possibile fra i carroponti, in "
     "blocchi contigui. Il docstring dichiara da se' che non e' quello da cui "
     "parte il disegno a mano -- li' si parte da NIENTE assegnato -- e che "
     "serve a chi vuole una suddivisione plausibile su cui ragionare senza "
     "passare dal solutore. E' quindi un'offerta a chi usa il modulo come "
     "libreria, non codice morto: il fatto che l'interfaccia non la usi e' "
     "coerente con quanto scritto."),
    ("p",
     "Il calcolo dei tagli con round(i * n_moves / n) distribuisce il resto "
     "invece di ammucchiarlo sull'ultimo carroponte: con 7 mosse e 3 "
     "carroponti da' 2, 3, 2 e non 2, 2, 3."),

    ("h3", "zone_da_assegnazione"),
    ("c", "manuale.zone_da_assegnazione"),
    ("p",
     "Somiglia molto a zone_coprenti, ma fa una cosa diversa: costruisce una "
     "zona solo per i carroponti che hanno almeno una mossa, e salta i buchi. "
     "Il docstring dice che l'assegnazione 'e' gia' stata verificata contigua "
     "e ordinata da perche_non_va()' -- ma perche_non_va, come si e' visto, "
     "verifica soltanto l'ordine, non la contiguita', proprio perche' le mosse "
     "scoperte sono ammesse."),
    ("q",
     "IL PRESUPPOSTO NON REGGE PIU'. E' con ogni probabilita' la funzione da "
     "cui si e' partiti, prima di accorgersi che le mosse non assegnate "
     "andavano gestite: zone_coprenti e' la risposta a quel problema, e da "
     "allora componi() usa quella. Questa non e' chiamata da nessuno, e "
     "chiamarla oggi con un'assegnazione incompleta produrrebbe zone che non "
     "coprono tutte le mosse -- esattamente cio' che le strutture dati non "
     "accettano. Va tolta, o va corretto il docstring."),

    ("h3", "trasporti_cliccabili"),
    ("c", "manuale.trasporti_cliccabili"),
    ("p",
     "Restituisce, per ogni trasporto disegnato, il rettangolo che occupa: "
     "serve -- servirebbe -- a capire su quale trasporto ha cliccato "
     "l'utente. L'interfaccia pero' risolve la stessa domanda per un'altra "
     "strada, combinando segmenti_pezzo e mosse_del_pettine, che ha il "
     "vantaggio di lavorare sugli stessi segmenti che sono stati disegnati."),
    ("p",
     "Si noti anche che qui il tratto va da tempi[k] a tempi[k] + "
     "loaded_leg_seconds(k), cioe' comprende presa e rilascio in un rettangolo "
     "solo, mentre il disegno li tiene separati. Una zona cliccabile che non "
     "coincide con quello che si vede e' una fonte di attriti: si clicca "
     "sull'attesa e si seleziona il trasporto."),
    ("p",
     "Nessuna delle due va rimossa alla leggera -- il modulo e' pensato anche "
     "come libreria -- ma vanno decise: o si aggiornano, o si tolgono. Una "
     "funzione mai chiamata non viene provata da nessun test, e continua a "
     "sembrare corretta finche' qualcuno non la usa."),
]

DOCUMENTI = [
    ("manuale_riga_per_riga.docx", RIGA_PER_RIGA),
]
