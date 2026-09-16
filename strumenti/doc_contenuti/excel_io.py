"""
Il testo dei documenti di excel_io.py.

Ventinove fra funzioni e metodi, in tre documenti: leggere il file, generarlo,
scrivere i risultati. E' il modulo che l'utente tocca davvero -- il resto del
programma lo vede solo attraverso una finestra -- e per questo quasi ogni sua
riga e' una decisione su come parlargli.
"""

from __future__ import annotations

# ==========================================================================
# Documento 1 -- la lettura
# ==========================================================================

LETTURA = [
    ("h1", "excel_io.py (1) -- leggere il file della linea"),
    ("p",
     "Primo dei tre documenti su excel_io.py. Qui si vede come un file Excel "
     "compilato a mano diventa un ProblemData, e soprattutto cosa succede "
     "quando e' compilato male -- che e' il caso normale, non l'eccezione. "
     "Ogni blocco di codice e' estratto dal sorgente al momento della "
     "generazione."),

    # ==================================================================
    ("h2", "La regola che governa tutto il modulo"),
    ("p",
     "Un file di ingresso riempito a mano sbaglia spesso. Una cella vuota, un "
     "numero scritto con la virgola, una vasca che nel Percorso si chiama in "
     "un modo e nelle Vasche in un altro, un foglio riordinato per sbaglio. "
     "Non e' incompetenza di chi compila: e' la natura di un foglio di calcolo "
     "usato come modulo da riempire."),
    ("q",
     "GLI ERRORI SI RACCOLGONO TUTTI, E SI DICONO INSIEME. E' scritto "
     "nell'intestazione del file ed e' la regola che spiega meta' del codice "
     "di lettura. Un lettore che si ferma al primo errore costringe a un giro "
     "completo -- correggi, salva, rilancia, leggi il prossimo errore -- per "
     "OGNI cella sbagliata. Con dieci errori sono dieci giri. Raccogliendoli, "
     "si corregge il file una volta sola. E' anche il motivo per cui quasi "
     "tutte le funzioni di lettura ricevono un oggetto `errori` e non "
     "sollevano niente."),
    ("p",
     "Il secondo principio e' che ogni messaggio dice FOGLIO e CELLA. "
     "'Permanenza minima maggiore della massima' e' inservibile su un foglio "
     "di quaranta righe; '[Percorso!C12]' si trova in un secondo."),

    ("h3", "La tabella dei parametri"),
    ("c", "excel_io", "_PARAMETRI = {", "_INTERI = "),
    ("p",
     "Un dizionario solo, con quattro informazioni per parametro: unita', se e' "
     "obbligatorio, il valore predefinito, la descrizione. Da qui discende "
     "tutto -- la lettura, la validazione, la generazione del foglio "
     "d'esempio e le note nel foglio Istruzioni. Aggiungere un parametro "
     "significa aggiungere una riga qui, e nient'altro."),
    ("p",
     "La descrizione di passo_controllo_distanza_mm e' lunga cinque righe e "
     "vale la pena leggerla: dice cosa fa il parametro, che NON e' un margine "
     "di sicurezza (che e' un altro), e in quale sintomo ci si accorge di "
     "doverlo cambiare -- una linea che esce INFEASIBLE o un takt time troppo "
     "alto. E' la forma che dovrebbe avere ogni descrizione di parametro: non "
     "cosa significa, ma quando toccarlo."),

    ("h3", "I nomi vecchi, e perche' sono ancora qui"),
    ("c", "excel_io", "_INTERI = ", "@dataclass"),
    ("p",
     "Due dizionari che non servono a leggere niente: servono a RICONOSCERE i "
     "file di versioni precedenti e a dirlo con chiarezza."),
    ("p",
     "_NOMI_IN_METRI si costruisce da solo, sostituendo '_mm' con '_m' nei "
     "nomi attuali. Il commento spiega la posta in gioco: leggere un file "
     "vecchio com'e' vorrebbe dire interpretare 9,5 metri come 9,5 millimetri, "
     "cioe' sbagliare di mille volte -- e il programma calcolerebbe "
     "tranquillamente un ciclogramma su una linea lunga nove millimetri."),
    ("q",
     "PERCHE' NON BASTA 'PARAMETRO NON RICONOSCIUTO'. Senza questi due "
     "dizionari, un file della vecchia versione produrrebbe venti messaggi "
     "'parametro non riconosciuto' e nessuno capirebbe che il problema e' "
     "l'unita' di misura. Il rischio peggiore non e' la confusione: e' che "
     "qualcuno ricopi a occhio i valori sotto i nomi nuovi senza moltiplicare "
     "per mille."),
    ("p",
     "_NOMI_SOSTITUITI e' il caso piu' difficile, e i suoi messaggi lo "
     "mostrano. Non sono rinomini: sono parametri che sono stati sostituiti da "
     "altri che vogliono dire una cosa DIVERSA. Dire solo il nome nuovo "
     "farebbe ricopiare il vecchio valore sotto un nome che significa altro, "
     "quindi ogni messaggio spiega anche come si converte -- con la formula e "
     "con un esempio numerico ('6 passi -> 300 mm', '15% -> 270 mm')."),
    ("p",
     "Tre delle cinque voci raccontano lo stesso spostamento concettuale: "
     "altezza_sollevamento_mm, tempo_sgocciolamento_s e "
     "traslazione_con_gancio_basso erano proprieta' della LINEA e sono "
     "diventate proprieta' della singola VASCA. Il messaggio di quest'ultima "
     "dice anche perche' conviene -- 'i rientri che non le scavalcano non "
     "pagheranno piu' salita e discesa' -- perche' un utente che ha appena "
     "perso una riga di configurazione ha diritto di sapere cosa ci guadagna."),

    # ==================================================================
    ("h2", "1. I mattoni"),
    ("c", "excel_io.Configurazione"),
    ("p",
     "Non e' solo il ProblemData: porta anche i due parametri che riguardano "
     "la RICERCA e non il problema (max_carroponti, tempo_limite_s), le zone "
     "manuali se ci sono, il percorso del file, e il ciclogramma gia' composto "
     "se il file lo portava con se'."),
    ("p",
     "La distinzione fra `data` e il resto e' quella fra il problema e come lo "
     "si vuole affrontare: model.py non deve sapere quanto tempo gli si vuole "
     "concedere, e infatti quei due campi non entrano in ProblemData."),
    ("c", "excel_io._Errori"),
    ("p",
     "Tre metodi e nessuna sorpresa: accumula stringhe e, alla fine, le "
     "solleva tutte insieme in un unico ValueError. Il formato di ogni voce e' "
     "'[Foglio!Cella] messaggio', ed e' quello che rende il messaggio finale "
     "leggibile anche quando le voci sono venti."),
    ("p",
     "solleva_se_presenti viene chiamato piu' volte durante la lettura, non "
     "solo alla fine: e' la sola forma di sequenzialita' che il modulo si "
     "concede, e serve dove proseguire non avrebbe senso -- se manca il foglio "
     "Vasche, leggere il Percorso produrrebbe solo 'vasca non definita' per "
     "ogni riga."),
    ("c", "excel_io._numero"),
    ("p",
     "La conversione di una cella in numero, con quattro casi trattati a parte "
     "e ciascuno con il suo messaggio."),
    ("li", "cella vuota: 'valore mancante';"),
    ("li", "booleano: openpyxl restituisce True/False per le celle che Excel "
           "considera logiche, e in Python True vale 1. Senza questo controllo, "
           "una cella con VERO diventerebbe silenziosamente il numero 1;"),
    ("li", "testo: si accetta la VIRGOLA decimale, perche' capita "
           "continuamente incollando valori da altri documenti, e rifiutare "
           "'2,5' sarebbe pedanteria;"),
    ("li", "intero richiesto ma numero con decimali: si dice, invece di "
           "troncare."),
    ("p",
     "In tutti i casi restituisce None e registra l'errore. Il chiamante "
     "controlla il None e prosegue: e' cosi' che la raccolta degli errori "
     "resta possibile senza eccezioni."),
    ("c", "excel_io._testo"),
    ("p",
     "Due righe che compaiono ovunque nella lettura. Fanno tre cose in una: "
     "trasformano None in stringa vuota, convertono in testo qualunque cosa "
     "openpyxl abbia restituito -- un id di vasca scritto come 12 arriva come "
     "numero, non come stringa -- e tolgono gli spazi ai bordi."),
    ("p",
     "L'ultimo punto e' quello che evita il difetto piu' irritante di tutti: "
     "una vasca chiamata 'ZINCATURA ' nel foglio Vasche e 'ZINCATURA' nel "
     "Percorso, con uno spazio invisibile in coda. Senza il rstrip, il "
     "messaggio direbbe che la vasca non e' definita mostrando due nomi che a "
     "schermo sono identici."),

    # ==================================================================
    ("h2", "2. leggi_problema -- il giro della lettura"),
    ("c", "excel_io.leggi_problema", None, "    tanks = _leggi_vasche"),
    ("p",
     "openpyxl viene importato dentro la funzione, con un messaggio che dice "
     "come installarlo. E' l'unica dipendenza del modulo, e chi usa solo il "
     "motore di calcolo non ha motivo di averla."),
    ("p",
     "data_only=True dice a openpyxl di leggere i VALORI delle formule, non le "
     "formule. Un utente che scrive '=2500*2' in una cella si aspetta 5000; "
     "senza quel flag arriverebbe la stringa della formula. L'effetto "
     "collaterale da conoscere: se il file e' stato scritto da un programma e "
     "mai aperto con Excel, i valori delle formule non sono ancora stati "
     "calcolati e risultano None."),
    ("p",
     "Il controllo sui fogli mancanti elenca quelli PRESENTI. E' il modo piu' "
     "rapido per accorgersi di un foglio rinominato o di un file sbagliato, e "
     "costa una riga."),
    ("c", "excel_io.leggi_problema", "    tanks = _leggi_vasche", "    def _kin_sollevamento"),
    ("p",
     "L'ordine e' quello delle dipendenze: le vasche prima del percorso, "
     "perche' il percorso le nomina. I tre fogli facoltativi -- Zone, "
     "CambioQuota, Ciclogramma -- si leggono solo se ci sono, e la loro "
     "assenza non e' un errore."),
    ("p",
     "Poi un solleva_se_presenti: da qui in avanti si costruiscono gli "
     "oggetti, e costruirli con dati mancanti darebbe eccezioni tecniche al "
     "posto dei messaggi utili gia' raccolti."),
    ("c", "excel_io.leggi_problema", "    def _kin_sollevamento", None),
    ("p",
     "_kin_sollevamento restituisce None se manca uno dei due valori. Le "
     "cinematiche di sollevamento sono facoltative: una linea senza "
     "movimentazione verticale non ha motivo di dichiararle, e None e' il modo "
     "in cui ProblemData sa che non ci sono."),
    ("q",
     "L'ULTIMO try/except E' IL PIU' INTERESSANTE. ProblemData ha le sue "
     "validazioni, e sono gia' scritte per un umano. Qui non si riscrive il "
     "messaggio: si aggiunge soltanto da quale FILE arrivano i dati. E' la "
     "scelta giusta -- riformulare quei messaggi significherebbe mantenerne "
     "due versioni, e la seconda invecchierebbe."),

    # ==================================================================
    ("h2", "3. Le vasche"),
    ("c", "excel_io._leggi_vasche", None, "        svincoli = {}"),
    ("p",
     "Una riga per vasca, otto colonne. Le righe senza id si SALTANO: cosi' si "
     "puo' lasciare una riga vuota per separare gruppi di vasche, che e' quello "
     "che si fa naturalmente su un foglio lungo."),
    ("p",
     "I posti hanno un valore predefinito (1); corsa verticale e sgocciolamento "
     "no, e il commento difende la scelta: sono OBBLIGATORI, una vasca per "
     "volta. Non esiste un valore generale da cui ereditare, e dove non serve "
     "movimentazione verticale si scrive 0 -- che e' una dichiarazione. Una "
     "cella vuota non lo e': non distingue 'non c'e' movimento' da 'non ci ho "
     "pensato'."),

    ("h3", "Gli svincoli, e le colonne scambiate"),
    ("c", "excel_io._leggi_vasche", "        svincoli = {}", "        # Se il gancio SCARICO"),
    ("p",
     "L'ordine delle due colonne e' NEGATIVO poi POSITIVO, cioe' lo stesso in "
     "cui si vedono sulla rotaia guardando il disegno: prima quello a sinistra "
     "della vasca, poi quello a destra. Compilando si legge da sinistra a "
     "destra e non si deve invertire niente nella testa."),
    ("q",
     "IL CONTROLLO DELLE COLONNE SCAMBIATE. E' il pezzo di codice piu' "
     "istruttivo del modulo, e non serve a validare: serve a NON INCOLPARE "
     "l'utente sbagliato. In F ci si aspetta un valore prima della vasca e in "
     "G uno dopo; se sono entrambi al contrario, il file e' stato scritto "
     "quando le colonne erano invertite. La geometria lo respingerebbe "
     "comunque, ma con un messaggio che manda a cercare l'errore "
     "nell'IMPIANTO -- e chi ha compilato quel file non ha sbagliato niente. "
     "Il messaggio dice invece cos'e' successo, mostra i due valori, e dice "
     "l'unica cosa da fare: scambia le due celle."),
    ("p",
     "Si richiede che siano scambiati ENTRAMBI (len(invertiti) == 2). Uno solo "
     "fuori posto e' un errore di compilazione vero, non una migrazione, e "
     "merita il messaggio normale."),
    ("p",
     "Il commento sul `continue` mancante racconta un difetto trovato e "
     "corretto: saltando la vasca, il foglio Percorso non l'avrebbe piu' "
     "trovata e avrebbe aggiunto un 'vasca non definita' per ogni riga che la "
     "nomina -- messaggi che non c'entrano niente e che avrebbero sepolto "
     "proprio quello utile. La vasca si registra lo stesso, anche con valori "
     "che non verranno mai usati, perche' tanto gli errori si sollevano tutti "
     "insieme prima di costruire il problema."),
    ("c", "excel_io._leggi_vasche", "        # Se il gancio SCARICO", None),
    ("p",
     "In coda si leggono `larghezza_mm` e `altezza_mm`, le due colonne che "
     "servono solo a disegnare la simulazione. Vuote non sono un difetto e non "
     "producono nessun messaggio: di parecchie linee il disegno non ce l'ha "
     "nessuno, e il calcolo non le usa comunque. Scritte male si': un testo in "
     "quelle celle viene segnalato come in tutte le altre."),
    ("p",
     "L'ultima colonna, con valore predefinito 1: il gancio scarico puo' "
     "passare basso sopra questa vasca. Il commento dice perche' il "
     "predefinito e' quello -- 'e' come sono fatte quasi tutte' -- e quindi la "
     "colonna si compila solo dove c'e' davvero un ostacolo."),
    ("p",
     "I due `continue` finali sono la rete: se anche un solo valore "
     "obbligatorio manca, la vasca non si costruisce. L'errore e' gia' stato "
     "registrato da _numero."),

    # ==================================================================
    ("h2", "4. Il percorso"),
    ("c", "excel_io._leggi_percorso"),
    ("p",
     "La ricetta: in che ordine il pezzo visita le vasche, e per quanto. "
     "L'ordine vero e' quello delle RIGHE, non della colonna 'n'."),
    ("q",
     "A COSA SERVE ALLORA LA COLONNA 'n'. Il commento lo dice: a intercettare "
     "un foglio ORDINATO PER SBAGLIO. E' un incidente frequentissimo -- si "
     "clicca sull'intestazione di una colonna per cercare qualcosa e Excel "
     "riordina tutto -- e il danno e' silenzioso: la ricetta cambia, il "
     "programma calcola un ciclogramma perfetto per una linea che non esiste. "
     "La numerazione che salta e' il solo indizio, e il messaggio nomina "
     "esplicitamente la causa: 'controlla di non aver ordinato il foglio'."),
    ("p",
     "Si noti che `atteso` viene incrementato PRIMA del controllo sulla vasca "
     "sconosciuta: la numerazione riguarda le righe scritte, anche quelle che "
     "poi verranno scartate. Altrimenti una vasca inesistente sfaserebbe il "
     "controllo per tutte le righe successive, aggiungendo errori inventati a "
     "uno vero."),
    ("p",
     "Il controllo dmin > dmax e' l'unico vincolo di coerenza fra due celle di "
     "questo foglio, ed e' quello che intercetta l'inversione piu' comune."),

    # ==================================================================
    ("h2", "5. I parametri"),
    ("c", "excel_io._leggi_parametri"),
    ("p",
     "Due passate distinte, e la separazione conta. La prima legge le righe "
     "scritte e le mette in un dizionario, segnalando i nomi vecchi, i "
     "sostituiti, quelli non riconosciuti e i ripetuti. La seconda scorre "
     "_PARAMETRI -- cioe' i parametri ATTESI -- e per ciascuno decide se c'e', "
     "se e' obbligatorio, se prendere il predefinito."),
    ("p",
     "Fare due passate invece di una permette di distinguere i due difetti "
     "opposti: qualcosa di scritto che non doveva esserci, e qualcosa che "
     "doveva esserci e non e' stato scritto. Una passata sola vedrebbe solo il "
     "primo."),
    ("p",
     "L'ordine dei controlli nella prima passata non e' indifferente: prima i "
     "nomi in metri, poi i sostituiti, poi il generico 'non riconosciuto'. Ogni "
     "caso specifico deve essere intercettato PRIMA di quello generico, "
     "altrimenti il messaggio utile non verrebbe mai emesso."),
    ("p",
     "Da notare la distinzione fra riga assente e riga presente ma vuota: per "
     "un parametro facoltativo valgono entrambe il predefinito, ma il codice le "
     "tratta separatamente perche' per un parametro obbligatorio la prima e' "
     "'assente' e la seconda produce un 'valore mancante' con la cella."),

    # ==================================================================
    ("h2", "6. I tre fogli facoltativi"),
    ("c", "excel_io._leggi_zone"),
    ("p",
     "Un foglio Zone presente ma VUOTO vale come assente: zone automatiche. E' "
     "la scelta giusta, perche' il foglio viene generato sempre dal modello, e "
     "pretendere che l'utente lo cancelli per avere le zone automatiche "
     "sarebbe assurdo."),
    ("p",
     "Se invece qualcosa e' scritto, deve coprire tutte le mosse in modo "
     "contiguo e senza sovrapposizioni -- lo stesso confronto di LISTE che usa "
     "il verificatore. Il messaggio si chiude ricordando la via d'uscita: "
     "'Lascia il foglio vuoto per farle scegliere automaticamente'."),
    ("c", "excel_io._leggi_cambio_quota"),
    ("p",
     "Solo due zone possibili, 'carico' e 'scarico', riconosciute "
     "dall'etichetta in prima colonna. Il docstring stabilisce la regola: il "
     "foglio e' facoltativo e lo sono anche le sue righe, ma una riga scritta "
     "A META' e' un errore -- servono tutti e quattro i numeri, perche' con "
     "tre di essi il giro non e' definito."),
    ("p",
     "La riga completamente vuota (etichetta assente e celle vuote) si salta "
     "in silenzio; una con l'etichetta sbagliata produce un messaggio che "
     "elenca le due ammesse e spiega cosa sono. Il messaggio si chiude anche "
     "qui con la via d'uscita: 'Lascia il foglio vuoto se l'impianto non ne "
     "ha.'"),
    ("c", "excel_io._leggi_ciclogramma"),
    ("p",
     "Il foglio che rende il file RIAPRIBILE: contiene i gradi di liberta' del "
     "ciclogramma -- takt time, tempo in vasca di ogni tappa, chi fa cosa, e "
     "dove ogni carroponte passa il tempo morto -- e da quelli il ciclogramma "
     "si ricostruisce identico."),
    ("q",
     "L'ULTIMA COLONNA E' ARRIVATA DOPO, E SI LEGGE COME UNA CICATRICE. "
     "Quanto il carroponte resta fermo dove ha consegnato non discende dalle "
     "fasi: a parita' di tutto il resto puo' ripartire subito e aspettare a "
     "destinazione, oppure restare fermo e partire all'ultimo momento. Sono "
     "traiettorie diverse, con collisioni diverse. Finche' la scelta la "
     "faceva una convenzione nel codice non c'era niente da salvare; da "
     "quando la fa il solutore, non salvarla significava riaprire il file e "
     "trovarsi un ciclogramma diverso da quello verificato -- misurato: 14 "
     "casi su 50, uno con i due carri sovrapposti."),
    ("q",
     "ED E' FACOLTATIVA, PERCHE' DEVE ESSERLO. I file scritti prima che "
     "esistesse non ce l'hanno, e un ciclogramma composto a mano puo' non "
     "averla: colonna assente vuol dire 'decidi tu', e risponde la regola "
     "predefinita. Notare che assente e' diverso da zero: zero e' una scelta "
     "-- riparti subito -- e per questo la lettura restituisce None, non un "
     "dizionario vuoto."),
    ("q",
     "IL SILENZIO SAREBBE LA COSA PEGGIORE. Il docstring lo dice: un foglio "
     "vuoto vale come assente, e va bene -- una linea senza ciclogramma e' "
     "normale. Ma se il foglio c'e' ed e' rotto, si deve dire, perche' il "
     "silenzio farebbe ripartire da zero senza spiegare dove sia finito il "
     "lavoro di ieri. Il codice distingue i due casi guardando se ci sono "
     "righe piene sotto: takt time mancante con righe scritte e' un errore, "
     "takt time mancante e foglio vuoto e' un foglio non compilato."),
    ("p",
     "Il numero di carroponti, se non dichiarato, si DEDUCE da chi lavora "
     "davvero: il massimo indice assegnato piu' uno. E' un ripiego ragionevole "
     "e ha un limite noto -- un carroponte a cui non e' stata assegnata "
     "nessuna mossa sparisce -- ma il campo si scrive sempre, quindi il caso "
     "riguarda solo i file ritoccati a mano."),
    ("p",
     "I carroponti sono numerati DA 1 nel file e da 0 nel programma. La "
     "conversione avviene qui (c - 1) e il controllo c < 1 intercetta chi ha "
     "scritto 0 pensando alla numerazione interna."),
]


# ==========================================================================
# Documento 2 -- la generazione del file
# ==========================================================================

MODELLO = [
    ("h1", "excel_io.py (2) -- generare il file da compilare"),
    ("p",
     "Secondo dei tre documenti su excel_io.py: come nasce il file Excel che "
     "l'utente compila, e come una linea gia' letta ci torna dentro identica."),

    # ==================================================================
    ("h2", "Il principio: un solo posto da cui esce il formato"),
    ("p",
     "Il formato di ingresso viene prodotto in tre occasioni diverse: il "
     "modello d'esempio ('Nuovo modello Excel...'), una linea risalvata con il "
     "suo ciclogramma, e la prima meta' del file dei risultati. Tre strade, un "
     "solo generatore: _aggiungi_fogli_linea."),
    ("p",
     "Se ce ne fossero tre, divergerebbero. Non forse: sicuramente, alla prima "
     "colonna aggiunta -- e un file salvato da una strada non si riaprirebbe "
     "piu' dall'altra."),

    ("h3", "La linea d'esempio"),
    ("c", "excel_io._righe_esempio"),
    ("p",
     "Una linea di zincatura a sette stazioni, con numeri realistici: carico, "
     "sgrasso, risciacquo, zincatura, risciacquo, passivazione, scarico. Il "
     "docstring dice a cosa serve -- 'si lancia subito e la si modifica pezzo "
     "per pezzo' -- che e' il modo in cui si impara un formato nuovo."),
    ("p",
     "Due dettagli scelti apposta. La zincatura ha DUE posti e un bagno lungo "
     "(180-220 s): e' la vasca che comanda il ciclogramma, e serve a far "
     "vedere subito il caso in cui una vasca ospita piu' pezzi insieme. "
     "Carico e scarico hanno corsa 0 e sgocciolamento 0, col commento che "
     "spiega perche': non sono bagni."),
    ("p",
     "La linea d'esempio non ha zone di cambio quota, e il commento dice che "
     "il foglio nasce comunque, vuoto e con le sole intestazioni, 'cosi' si "
     "vede che c'e' e cosa vorrebbe'. Un foglio facoltativo che non compare "
     "non si scopre mai."),

    ("h3", "L'inverso esatto della lettura"),
    ("c", "excel_io._righe_da_configurazione"),
    ("p",
     "Il docstring dichiara la proprieta' che questa funzione deve avere: "
     "'quello che esce di qui, riletto, deve ridare la stessa linea'. E' una "
     "proprieta' verificabile, ed e' verificata -- test_excel_io prova l'andata "
     "e ritorno."),
    ("q",
     "UNA FUNZIONE DA TENERE ALLINEATA A MANO. Ogni campo aggiunto a Tank o a "
     "ProblemData va aggiunto QUI e nella lettura, e niente lo impone: "
     "dimenticarlo non da' nessun errore, produce solo un file che perde un "
     "dato al primo salvataggio. E' il tipo di difetto che si scopre settimane "
     "dopo, quando qualcuno riapre un file e trova una colonna vuota. Il test "
     "di andata e ritorno e' l'unica difesa, e va esteso insieme al campo."),
    ("p",
     "Si noti l'ordine degli svincoli, con il commento che lo ricorda: "
     "negativo poi positivo, l'ordine della rotaia. E' lo stesso della "
     "lettura, e devono restare d'accordo -- e' esattamente la coppia di punti "
     "in cui e' nato il difetto che il controllo delle colonne scambiate, nel "
     "primo documento, serve a diagnosticare."),

    ("h3", "Le due porte d'ingresso"),
    ("c", "excel_io.scrivi_modello"),
    ("c", "excel_io.scrivi_linea"),
    ("p",
     "Due righe di differenza: la prima parte dall'esempio, la seconda da una "
     "configurazione vera e ci aggiunge il ciclogramma."),
    ("p",
     "Il docstring di scrivi_linea spiega perche' esiste, ed e' un ragionamento "
     "che vale la pena seguire. Un ciclogramma composto a mano vive solo nella "
     "memoria del programma: chiuso il programma, andrebbe rifatto. Il file "
     "dei RISULTATI non basta a riprenderlo -- e' un referto, e per giunta non "
     "contiene le cinematiche, senza le quali le durate dei trasporti non si "
     "possono ricalcolare. Un file di INGRESSO invece descrive gia' tutto: gli "
     "si aggiunge un foglio e si riapre normalmente."),
    ("p",
     "Il `wb.remove(wb.active)` in entrambe toglie il foglio vuoto che "
     "openpyxl crea da solo alla nascita del libro. Senza, ogni file avrebbe "
     "un 'Sheet' vuoto in testa."),

    # ==================================================================
    ("h2", "_aggiungi_fogli_linea"),
    ("c", "excel_io._aggiungi_fogli_linea", None, "    def prepara"),
    ("p",
     "AGGIUNGE a un libro invece di crearne uno, e il docstring dice perche': "
     "i risultati devono poterci stare nello stesso file. Un file solo che e' "
     "insieme il referto e la linea da riaprire."),
    ("p",
     "I due parametri finali -- data e ciclogramma -- sono quelli che "
     "distinguono un modello vuoto da una linea salvata. Il modello d'esempio "
     "non li passa."),
    ("c", "excel_io._aggiungi_fogli_linea", "    def prepara", "    # -- Istruzioni"),
    ("p",
     "`prepara` fa l'intestazione di un foglio: titoli in grassetto bianco su "
     "verde, larghezze delle colonne, e il blocco della prima riga "
     "(freeze_panes). Quest'ultimo e' quello che si nota solo quando manca: su "
     "un foglio Vasche di quaranta righe, scorrendo si perde di vista quale "
     "colonna e' quale."),
    ("c", "excel_io._aggiungi_fogli_linea", "    # -- Istruzioni", "    for testo, stile in ["),
    ("q",
     "LE SPIEGAZIONI STANNO TUTTE NEL FOGLIO ISTRUZIONI. Il commento difende "
     "la scelta con un argomento pratico: una nota scritta in una colonna che "
     "poi viene LETTA verrebbe scambiata per un dato. E' un errore "
     "facilissimo da fare -- si aggiunge una colonna 'note' per aiutare, e il "
     "lettore la legge come un valore. Il foglio Istruzioni e' l'unico posto "
     "in cui si puo' scrivere in italiano senza rischi."),
    ("p",
     "Il resto della funzione -- circa trecento righe -- e' la costruzione dei "
     "sei fogli, foglio per foglio: intestazioni, dati, larghezze, note in "
     "corsivo. E' codice ripetitivo per natura e si legge dall'alto in basso "
     "come si legge il file che produce."),

    ("h3", "Il foglio Ciclogramma"),
    ("c", "excel_io._scrivi_foglio_ciclogramma"),
    ("p",
     "Tre gradi di liberta' e nient'altro. Il docstring lo dice in modo "
     "netto: non si scrivono gli istanti di prelievo ne' le traiettorie, "
     "perche' sono CONSEGUENZE, e riscriverle vorrebbe dire poterle rileggere "
     "in contrasto con quello da cui derivano."),
    ("q",
     "LE CIFRE NON SI TAGLIANO. Il commento nel mezzo sembra un dettaglio "
     "estetico -- chi legge un tempo in vasca non guarda il microsecondo -- e "
     "invece e' un difetto vero, gia' successo. Questi valori vengono RILETTI, "
     "e la catena dei tempi li somma uno sull'altro; da li' si decide, con un "
     "arrotondamento all'insu', quanti periodi interi il pezzo resta in vasca. "
     "Un millesimo di troppo su una tappa al limite fa scattare un periodo in "
     "piu', e il ciclogramma riaperto NON e' piu' quello salvato. Da qui il "
     "round a nove cifre invece delle due che basterebbero a leggerlo."),
    ("p",
     "Le celle vuote hanno un significato: una mossa senza carroponte non e' "
     "ancora assegnata, una senza tempo in vasca prendera' il minimo di "
     "processo. E' cio' che permette di salvare un lavoro lasciato a meta' e "
     "riprenderlo esattamente da li'."),
]


# ==========================================================================
# Documento 3 -- i risultati
# ==========================================================================

RISULTATI = [
    ("h1", "excel_io.py (3) -- il file dei risultati"),
    ("p",
     "Terzo dei tre documenti su excel_io.py: il file che si legge e si "
     "consegna. E' anche, nella sua prima meta', il file che si riapre."),

    # ==================================================================
    ("h2", "Un file, due meta'"),
    ("p",
     "Il file dei risultati contiene dodici fogli in due gruppi. Prima la "
     "LINEA nel formato di ingresso, col ciclogramma dentro, cosi' lo stesso "
     "file si riapre con 'Apri linea...' e il lavoro riprende da dov'era. Poi "
     "il REFERTO: Riepilogo, Movimenti, TempiVerticali, FlussoPezzo, Verifica."),
    ("p",
     "L'ordine e' quello in cui le cose sono successe -- si parte da una linea "
     "e se ne ricava un risultato -- ma il file si APRE sul Riepilogo, che e' "
     "quello che si va a leggere. Due scelte diverse per due domande diverse: "
     "come sono disposte le cose, e cosa si vede per primo."),

    ("h3", "Le etichette dei tipi di segmento"),
    ("c", "excel_io", "# etichette leggibili per i tipi di segmento", "_SEVERITA"),
    ("q",
     "'PRESA' NON E' 'EMERSIONE'. Il commento racconta un nome sbagliato che "
     "e' stato usato per un po'. Chiamare quei tratti 'emersione' e "
     "'immersione' fa cercare in quella durata solo il tempo di salita, non "
     "trovarcelo, e sospettare un errore di calcolo. Comprendono invece anche "
     "la corsa a vuoto del gancio, i tempi morti di aggancio e sgancio, e per "
     "la presa lo sgocciolamento. E' un caso in cui il nome piu' preciso era "
     "quello piu' fuorviante: 'presa' e' vago quanto basta da spingere a "
     "leggere la nota in fondo al foglio, che dice cosa c'e' dentro."),
    ("p",
     "_FASI e' il terzo dei quattro posti da toccare quando si introduce un "
     "tipo di segmento: senza la voce, il foglio Movimenti stampa il nome "
     "interno inglese in mezzo a una tabella in italiano."),

    # ==================================================================
    ("h2", "1. Attribuire ogni tratto alla sua mossa"),
    ("c", "excel_io._mosse_dei_segmenti"),
    ("p",
     "Un giro di carroponte e' una sequenza di tratti, e la tabella dei "
     "movimenti deve dire per ciascuno da quale vasca a quale vasca. Serve "
     "quindi sapere a quale mossa appartiene ogni tratto."),
    ("p",
     "La regola di base e' semplice: il tratto a carico segna l'inizio di una "
     "mossa nuova; una presa appartiene alla mossa che STA PER cominciare; "
     "tutto il resto all'ultima cominciata."),
    ("q",
     "L'ECCEZIONE E' 'quota'. Una traslazione di cambio quota puo' stare "
     "dentro la presa o dentro il rilascio, e le due cose appartengono a mosse "
     "DIVERSE. Il codice le distingue guardando se il tratto viene prima o "
     "dopo il prossimo trasporto a carico -- e' l'unico criterio possibile, "
     "perche' geometricamente i due casi si assomigliano. Sbagliarlo non da' "
     "nessun errore: produce una tabella in cui una riga dice la vasca "
     "sbagliata, e nessuno se ne accorge finche' non prova a seguirla."),

    ("c", "excel_io._righe_movimenti"),
    ("p",
     "Una riga per tratto, con le due stazioni ricavate dal tipo. I casi sono "
     "cinque e ciascuno ha la sua regola: la presa sta sulla stazione di "
     "partenza, il trasporto le collega, il rilascio sta su quella di arrivo, "
     "la traslazione di quota dipende da dove cade rispetto al trasporto, il "
     "rientro a vuoto va dall'arrivo alla partenza della mossa SUCCESSIVA "
     "nell'ordine di visita."),
    ("p",
     "L'ultimo caso -- l'attesa -- e' l'unico risolto guardando la POSIZIONE "
     "invece della struttura: un'attesa puo' stare prima o dopo il rientro, e "
     "si sceglie la stazione la cui posizione coincide con quella del tratto. "
     "Il valore di ripiego, se nessuna coincide, e' la stazione di arrivo "
     "della mossa appena finita."),

    ("c", "excel_io._utilizzo_carroponti"),
    ("p",
     "Una riga che risponde a una domanda che l'utente si pone sempre: quanto "
     "lavora davvero ciascun carroponte. Si contano solo i tratti in cui "
     "trasla -- _FASI_IN_MOVIMENTO -- e si divide per il periodo."),
    ("p",
     "Le corse verticali NON contano come movimento, ed e' una convenzione "
     "discutibile ma dichiarata nel docstring: il carroponte sta lavorando, ma "
     "non sta occupando rotaia, e l'utilizzo serve a capire se c'e' spazio per "
     "dargli piu' trasporti."),

    # ==================================================================
    ("h2", "2. I cartelli"),
    ("c", "excel_io", "# Le due meta' del file", "def _cartello"),
    ("p",
     "Due colori -- blu per l'ingresso, verde per il referto -- che finiscono "
     "sulla LINGUETTA. Il commento dice perche': e' l'unico posto in cui si "
     "guarda quando si cerca un foglio."),
    ("c", "excel_io._cartello"),
    ("p",
     "Un foglio che non contiene dati: dice cosa viene dopo. Con dodici "
     "linguette di fila non si capisce dove finisce la linea e comincia il "
     "referto, e un cartello colorato lo si vede senza leggere niente."),
    ("q",
     "L'ELENCO NON E' SCRITTO A MANO. Il docstring lo dichiara e ne da' la "
     "ragione: si ricava dai fogli che ci sono DAVVERO in quel momento "
     "(wb.sheetnames[da:]). Un elenco fisso resterebbe indietro il giorno che "
     "si aggiunge o si toglie un foglio, e un indice che mente e' peggio di "
     "nessun indice. La descrizione di ciascun foglio viene da _COSA_CONTIENE, "
     "e un foglio non elencato li' compare comunque, con la descrizione vuota: "
     "si perde una spiegazione, non una riga."),
    ("p",
     "Il cartello nasce in coda al gruppo e viene poi spostato davanti con "
     "move_sheet e un offset negativo. E' l'unico modo per sapere quali fogli "
     "compongono il gruppo: bisogna che ci siano gia'."),

    # ==================================================================
    ("h2", "3. scrivi_risultati"),
    ("c", "excel_io.scrivi_risultati", None, "    # -- prima la linea"),
    ("p",
     "Il docstring e' quasi tutto una spiegazione di perche' i due gruppi "
     "stanno nello stesso file invece che in due. La risposta e' pratica: due "
     "file sarebbero due cose da tenere insieme e da non perdere."),
    ("c", "excel_io.scrivi_risultati", "    # -- prima la linea", "    def tabella"),
    ("p",
     "La linea si riscrive solo se sono stati passati cfg e ciclogramma. "
     "Senza, il file dei risultati e' solo un referto -- e non si riapre. E' "
     "il motivo per cui sia l'interfaccia sia il comando da terminale li "
     "passano sempre."),
    ("c", "excel_io.scrivi_risultati", "    def tabella", "    # -- Riepilogo"),
    ("p",
     "`tabella` e' l'equivalente di `prepara` per i fogli del referto, con in "
     "piu' i formati numerici per colonna. Averla come chiusura locale invece "
     "che come funzione del modulo tiene vicino il codice a chi lo usa: e' "
     "chiamata cinque volte, tutte dentro questa funzione."),
    ("c", "excel_io.scrivi_risultati", "    # -- Riepilogo", "    # -- Movimenti"),
    ("p",
     "Il Riepilogo e' il foglio su cui il file si apre, e la sua struttura e' "
     "a VOCI, non a tabella: etichetta, valore, nota. Le note in corsivo "
     "accanto ai numeri sono quello che permette di consegnare il file a "
     "qualcuno che non ha seguito il calcolo."),
    ("p",
     "`sezione` e `voce` sono due chiusure che scrivono rispettivamente un "
     "titolo di gruppo e una riga. Il risultato e' che il corpo del Riepilogo "
     "si legge come un elenco di cosa contiene, invece che come codice di "
     "formattazione."),
    ("c", "excel_io.scrivi_risultati", "    # -- Tempi verticali", "    # -- Flusso del pezzo"),
    ("p",
     "Il foglio TempiVerticali risponde alla domanda 'dove va il tempo di "
     "presa e di rilascio'. La chiusura `quanto` cerca una fase per nome fra "
     "quelle della stazione e ne restituisce la durata: e' il modo per "
     "scomporre una presa nelle sue voci senza duplicare la logica che le "
     "costruisce, che sta in model.py."),
    ("c", "excel_io.scrivi_risultati", "    # -- Verifica", "    # -- dettagli tecnici"),
    ("p",
     "I rilievi del verificatore, divisi per gravita' con _SEVERITA che "
     "traduce in italiano. E' il foglio che si guarda quando il Riepilogo dice "
     "che la verifica non e' passata."),
    ("c", "excel_io.scrivi_risultati", "    # -- dettagli tecnici", None),
    ("p",
     "I dettagli tecnici -- passo di campionamento, limite d'errore, numero di "
     "istanti -- vanno in CODA al Riepilogo e non in cima. Servono a chi vuole "
     "sapere quanto e' affidabile il numero della separazione minima, cioe' a "
     "una minoranza dei lettori; metterli sopra allontanerebbe dal primo "
     "schermo i tre dati che interessano tutti."),
    ("p",
     "In fondo i due cartelli, creati per ultimi perche' devono elencare fogli "
     "che a quel punto esistono tutti."),
]


DOCUMENTI = [
    ("excel_io_1_lettura.docx", LETTURA),
    ("excel_io_2_modello.docx", MODELLO),
    ("excel_io_3_risultati.docx", RISULTATI),
]
