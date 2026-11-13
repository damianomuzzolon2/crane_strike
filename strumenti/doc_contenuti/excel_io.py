"""
Il testo dei documenti di excel_io.py.

Cinquantadue fra funzioni e metodi, in tre documenti: leggere il file, generarlo,
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
    ("p",
     "Le cinematiche seguono uno schema regolare: v_max, a_max e d_max, "
     "sdoppiati fra vuoto e carico, per la traslazione e per il sollevamento. "
     "Le due eccezioni sono v_approach_sollevamento_mm_s e "
     "d_approach_sollevamento_mm, che NON sono sdoppiate: la zona di "
     "avvicinamento e' una sola, e vale sia col telaio sia a gancio scarico. "
     "Non e' una semplificazione -- la precisione che serve avvicinandosi al "
     "telaio e' la stessa che serve avvicinandosi col telaio, perche' a "
     "imporla e' il punto di accoppiamento e non il carico appeso."),
    ("p",
     "In tutte e quattro le cinematiche velocita' e accelerazione sono "
     "OBBLIGATORIE e la decelerazione e' facoltativa (vuota = frena come "
     "accelera). Vale anche per il sollevamento, che un tempo era "
     "facoltativo: ogni vasca dichiara la sua corsa verticale, e senza le "
     "cinematiche di sollevamento quella corsa non ha una durata. "
     "Dichiararle obbligatorie qui fa dire al file, con la cella, che cosa "
     "manca, invece di scoprirlo piu' avanti."),
    ("q",
     "DUE PARAMETRI FACOLTATIVI CHE NON SONO INDIPENDENTI. La tabella sa dire "
     "'obbligatorio' o 'facoltativo' di un parametro alla volta, e non sa "
     "esprimere 'o tutti e due o nessuno dei due'. Il controllo sta quindi "
     "piu' avanti, in ProblemData.__post_init__, ed e' il caso in cui la "
     "regola di dichiarare tutto qui non basta: una velocita' di "
     "avvicinamento senza la distanza su cui vale non descrive niente, e "
     "indovinare la distanza mancante sarebbe peggio che fermarsi."),

    ("h3", "I nomi vecchi, e perche' sono ancora qui"),
    ("c", "excel_io", "_INTERI = ", "@dataclass"),
    ("p",
     "_INTERI elenca i parametri che devono essere numeri interi: sono "
     "conteggi (max_carroponti, max_soste_intermedie) o interruttori 0/1 "
     "(takt_fisso, interblocco_vasche), e un 2,5 li' e' un errore di "
     "compilazione da dire, non da troncare."),
    ("p",
     "RISOLUZIONE_TICK_PER_S e' un parametro che non e' piu' un parametro. "
     "Fino a qualche versione fa stava nel foglio come "
     "risoluzione_tick_per_s; adesso e' fissa a 100 tick al secondo, e il "
     "commento dice perche': tutte le tolleranze del progetto (eps_seconds, il "
     "mezzo tick della verifica) sono pensate su quel valore, e lasciarlo "
     "cambiare da un file avrebbe voluto dire spostarle tutte insieme senza "
     "che nessuno se ne accorga. "
     "_NOMI_IGNORATI e' l'altra meta' della decisione: un file vecchio che ha "
     "ancora quella riga si legge SENZA errore, e il valore scritto li' non "
     "conta. Non c'e' niente da convertire e niente che l'utente debba fare, "
     "quindi non c'e' niente da dirgli."),
    ("p",
     "PARAMETRI e VERSI_CAMBIO_QUOTA sono le stesse tabelle esposte con un "
     "nome pubblico, per la finestra 'Dati linea', che mostra i parametri "
     "fuori dal file e propone le due zone di cambio quota in un elenco."),
    ("p",
     "Gli ultimi due dizionari non servono a leggere niente: servono a "
     "RICONOSCERE i file di versioni precedenti e a dirlo con chiarezza."),
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
     "Tre delle sette voci raccontano lo stesso spostamento concettuale: "
     "altezza_sollevamento_mm, tempo_sgocciolamento_s e "
     "traslazione_con_gancio_basso erano proprieta' della LINEA e sono "
     "diventate proprieta' della singola VASCA. Il messaggio di quest'ultima "
     "dice anche perche' conviene -- 'i rientri che non le scavalcano non "
     "pagheranno piu' salita e discesa' -- perche' un utente che ha appena "
     "perso una riga di configurazione ha diritto di sapere cosa ci guadagna."),
    ("p",
     "takt_min_s e takt_max_s sono il caso opposto: non si e' spostato il "
     "posto, si e' cambiata la forma. Il takt time adesso si dichiara come le "
     "permanenze delle vasche -- un teorico e due tolleranze -- e il "
     "messaggio propone due conversioni diverse degli stessi 110 e 150 "
     "(teorico 130 con delta 20 e 20, oppure teorico 110 con delta 0 e 40), "
     "perche' quale sia giusta dipende da quale valore si voleva davvero. "
     "Le due voci hanno un messaggio ciascuna perche' un file vecchio puo' "
     "averne una sola, ma la spiegazione sta in una."),

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
    ("c", "excel_io.leggi_problema"),
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
     "Il lavoro vero lo fa _leggi_libro, su un libro gia' aperto. La "
     "separazione serve alla finestra 'Dati linea': le sue tabelle si "
     "scrivono in un libro IN MEMORIA e si fanno leggere da qui (vedi "
     "leggi_righe nel secondo documento). Cosi' i dati inseriti a mano passano "
     "per gli stessi controlli di un file, con gli stessi messaggi, e non c'e' "
     "una seconda validazione da tenere allineata."),
    ("c", "excel_io._leggi_libro", None, "    tanks = _leggi_vasche"),
    ("p",
     "Il controllo sui fogli mancanti elenca quelli PRESENTI. E' il modo piu' "
     "rapido per accorgersi di un foglio rinominato o di un file sbagliato, e "
     "costa una riga."),
    ("c", "excel_io._leggi_libro", "    tanks = _leggi_vasche", "    def _kin_sollevamento"),
    ("p",
     "L'ordine e' quello delle dipendenze: le vasche prima del percorso, "
     "perche' il percorso le nomina. I tre fogli facoltativi -- Zone, "
     "CambioQuota, Ciclogramma -- si leggono solo se ci sono, e la loro "
     "assenza non e' un errore. Il quarto, Passaggi, si legge solo se c'e' "
     "anche un ciclogramma da attaccargli: dei punti di passaggio senza il "
     "ciclogramma a cui appartengono non saprebbero dove andare."),
    ("p",
     "Poi un solleva_se_presenti: da qui in avanti si costruiscono gli "
     "oggetti, e costruirli con dati mancanti darebbe eccezioni tecniche al "
     "posto dei messaggi utili gia' raccolti."),
    ("c", "excel_io._leggi_libro", "    def _kin_sollevamento", None),
    ("p",
     "_kin_sollevamento legge velocita' e accelerazione con par[...] e non "
     "con par.get: sono obbligatorie, e se mancavano il solleva_se_presenti "
     "qui sopra si e' gia' fermato con il messaggio giusto. La sola "
     "decelerazione resta facoltativa, e None li' vuol dire 'frena come "
     "accelera' -- non 'niente sollevamento'."),
    ("p",
     "La risoluzione temporale non viene dal file: time_scale riceve la "
     "costante RISOLUZIONE_TICK_PER_S, anche se il file porta ancora la "
     "vecchia riga risoluzione_tick_per_s."),
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
     "Una riga per vasca, undici colonne. Le righe senza id si SALTANO: cosi' si "
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
     "La colonna H, con valore predefinito 1: il gancio scarico puo' passare "
     "basso sopra questa vasca. Il commento dice perche' il predefinito e' "
     "quello -- 'e' come sono fatte quasi tutte' -- e quindi la colonna si "
     "compila solo dove c'e' davvero un ostacolo."),
    ("p",
     "Poi `larghezza_mm` e `altezza_mm`, le due colonne che servono solo a "
     "disegnare la simulazione. Vuote non sono un difetto e non producono "
     "nessun messaggio: di parecchie linee il disegno non ce l'ha nessuno, e "
     "il calcolo non le usa comunque. Scritte male si': un testo in quelle "
     "celle viene segnalato come in tutte le altre."),
    ("p",
     "L'ultima colonna, `cover_presente`, dice se la vasca ha un coperchio. "
     "Non cambia il ciclogramma: serve al programma dei carri, che sopra una "
     "vasca coperta apre il coperchio prima di scendere e lo richiude dopo "
     "essere risalito. Il predefinito e' 0, al contrario del gancio basso, "
     "perche' e' 0 il caso comune -- la colonna si compila solo sulle vasche "
     "coperte -- e perche' cosi' un file scritto prima che la colonna "
     "esistesse si legge esattamente com'era."),
    ("p",
     "I due `continue` finali sono la rete: se anche un solo valore "
     "obbligatorio manca, o il gancio basso o il coperchio sono scritti male, "
     "la vasca non si costruisce. L'errore e' gia' stato registrato da "
     "_numero."),

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
     "Ogni tappa si dichiara con un tempo TEORICO e due tolleranze, il delta "
     "negativo e il delta positivo: la finestra di processo e' teorico meno "
     "il primo, teorico piu' il secondo, e a costruirla e' "
     "StationSpec.da_teorico. I due delta sono AMPIEZZE, e il commento dice "
     "cosa succederebbe senza il controllo sul segno: chi scrive '-15' "
     "pensando 'quindici in meno' otterrebbe una finestra rovesciata, senza "
     "nessun messaggio. Il controllo dneg > teorico intercetta l'altro modo di "
     "rompere la finestra, una soglia minima negativa."),
    ("p",
     "Le ultime due colonne sono i pesi dello scarto dal teorico, sotto e "
     "sopra: quanto conta, per il calcolo, allontanarsi dalla ricetta da un "
     "lato o dall'altro. Li legge _peso_scarto, piu' sotto."),
    ("c", "excel_io._percorso_vecchio_formato"),
    ("p",
     "I file compilati prima del passaggio al tempo teorico hanno in C e D la "
     "permanenza minima e la massima. Si riconoscono da una parola "
     "nell'intestazione ('min') e si leggono lo stesso, col ramo "
     "`vecchio_formato` di _leggi_percorso: chi ha gia' descritto una linea "
     "non deve ricompilarla. In quel ramo il solo vincolo fra due celle e' "
     "dmin > dmax, che intercetta l'inversione piu' comune."),
    ("q",
     "IL FORMATO SI RICONOSCE DAI TITOLI, NON DAI NUMERI. In C e D ci sono "
     "numeri in tutti e due i formati, e una coppia come 60 e 90 e' "
     "plausibile sia come minimo e massimo sia come teorico e delta. Solo "
     "l'intestazione dice quale dei due e'. La stessa funzione la usa "
     "righe_da_file, che per un Percorso vecchio rinuncia a mostrare le "
     "tabelle invece di metterci colonne che vogliono dire un'altra cosa."),
    ("c", "excel_io._peso_scarto"),
    ("p",
     "Un peso vuoto vale 1, cioe' tutte le tappe contano uguale: e' il modo "
     "in cui un file che non ha le colonne dei pesi si legge com'era. Due "
     "rifiuti, ciascuno col suo perche'. Un peso negativo non ha senso -- "
     "premierebbe l'allontanarsi dalla ricetta -- e il messaggio dice da dove "
     "partono i pesi validi: da 0, 'scarto indifferente'."),
    ("q",
     "UN PESO PICCOLO CHE DIVENTA ZERO. Il solutore lavora con pesi interi, "
     "moltiplicati per model.SCALA_PESI: un 0,001 arrotondato fa 0, e un "
     "peso che l'utente voleva solo piccolo diventerebbe 'indifferente' "
     "senza che nessuno l'abbia chiesto. Il messaggio non si ferma al "
     "rifiuto, e indica la strada giusta: conta solo il RAPPORTO fra i pesi, "
     "quindi per far contare poco una tappa si alzano le altre."),

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
     "nomi in metri, poi quelli da ignorare (_NOMI_IGNORATI), poi i "
     "sostituiti, poi il generico 'non riconosciuto'. Ogni caso specifico "
     "deve essere intercettato PRIMA di quello generico, altrimenti il "
     "messaggio utile non verrebbe mai emesso -- o, per risoluzione_tick_per_s, "
     "un file vecchio perfettamente buono verrebbe rifiutato."),
    ("p",
     "Da notare la distinzione fra riga assente e riga presente ma vuota: per "
     "un parametro facoltativo valgono entrambe il predefinito, ma il codice le "
     "tratta separatamente perche' per un parametro obbligatorio la prima e' "
     "'assente' e la seconda produce un 'valore mancante' con la cella."),
    ("p",
     "In coda, due controlli che riguardano il VALORE e non la presenza: "
     "quelli del takt time, in una funzione a parte, e quello sui due "
     "interruttori takt_fisso e interblocco_vasche, che valgono 0 oppure 1 e "
     "nient'altro. Un 2 sarebbe letto come 'vero' da bool() senza che "
     "nessuno sappia cosa intendeva chi l'ha scritto."),
    ("c", "excel_io._controlla_takt"),
    ("p",
     "Il takt time si dichiara come le permanenze delle vasche -- un teorico "
     "e due ampiezze -- e i controlli sono gli stessi del foglio Percorso, "
     "per la stessa ragione: un delta col segno meno rovescerebbe la banda "
     "senza dirlo. In piu' c'e' il teorico che deve essere positivo, e il "
     "delta negativo che non deve arrivare al teorico, perche' il ciclo "
     "minimo verrebbe nullo o negativo."),
    ("p",
     "La chiusura `cella` serve a una cosa sola: citare nel messaggio la "
     "riga in cui il parametro sta DAVVERO, presa da `grezzi`. I parametri "
     "non hanno una riga fissa -- il foglio si puo' riordinare, e una riga "
     "si puo' cancellare -- quindi la cella va cercata, e se il parametro "
     "non c'e' resta solo la colonna, 'B'."),
    ("p",
     "Se uno dei tre valori manca o non si legge, la funzione non controlla "
     "niente: l'errore e' gia' stato scritto, e confrontare un None con un "
     "numero darebbe solo un'eccezione tecnica al posto del messaggio utile."),

    # ==================================================================
    ("h2", "6. I fogli facoltativi"),
    ("c", "excel_io._leggi_zone"),
    ("p",
     "Il foglio Zone non dice quali mosse fa ciascun carroponte, ma FIN DOVE "
     "puo' arrivare: una riga per carroponte con la vasca minima e la massima "
     "(model.Portata). E' un limite, non una zona: le portate di due "
     "carroponti vicini possono sovrapporsi, e chi serve le vasche in comune "
     "lo sceglie il solutore. Per questo qui non si controlla nessuna "
     "copertura: solo che ogni riga abbia tutte e due le vasche e che "
     "esistano nel foglio Vasche, con la cella in cui non tornano."),
    ("p",
     "Un foglio Zone presente ma VUOTO vale come assente: nessun limite, "
     "carroponti e zone automatici. E' la scelta giusta, perche' il foglio "
     "viene generato sempre dal modello, e pretendere che l'utente lo cancelli "
     "sarebbe assurdo."),
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
    ("c", "excel_io._colonne_ciclogramma"),
    ("q",
     "LE COLONNE SI CERCANO PER NOME, NON PER POSIZIONE. Il foglio e' "
     "cresciuto: il tempo teorico e lo scarto sono finiti IN MEZZO alla "
     "tabella, attaccati al tempo vero, che e' l'unico posto in cui il "
     "confronto serve -- e cosi' facendo hanno spostato sosta_in_vasca e "
     "sosta_s da G/H a I/J. Un lettore che contasse le colonne leggerebbe i "
     "file di ieri con lo schema di oggi, prendendo lo scarto per l'attesa "
     "dopo la consegna: in silenzio, perche' sono tutti e due numeri "
     "plausibili. Il nome invece sta scritto nel file, e dice da solo cosa "
     "c'e' sotto."),
    ("p",
     "L'ordine STORICO -- le otto colonne di prima -- resta solo come ripiego "
     "per chi ha cancellato la riga dei titoli: e' l'unico file in cui "
     "l'ordine e' noto senza bisogno di leggerlo. Si riconosce dall'assenza di "
     "`tempo_in_vasca_s`, che c'e' sempre stato."),
    ("c", "excel_io._leggi_ciclogramma"),
    ("p",
     "Il foglio che rende il file RIAPRIBILE: contiene i gradi di liberta' del "
     "ciclogramma -- takt time, tempo in vasca di ogni tappa, chi fa cosa, e "
     "dove ogni carroponte passa il tempo morto -- e da quelli il ciclogramma "
     "si ricostruisce identico."),
    ("p",
     "Le due funzioncine in testa, `dove` e `valore`, sono quello che resta "
     "della conversione: la prima ricava l'indirizzo di cella da citare negli "
     "errori dalla colonna trovata DAVVERO -- scriverlo a mano direbbe 'E12' "
     "anche quando il tempo in vasca sta altrove -- e la seconda restituisce "
     "None per le colonne che nel file non ci sono, perche' una colonna "
     "facoltativa che manca non e' un errore."),
    ("p",
     "Le colonne CALCOLATE non si leggono affatto. Il tempo teorico lo detta "
     "il foglio Percorso, e rileggerlo da qui vorrebbe dire poterlo avere in "
     "due versioni diverse nello stesso file."),
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
    ("p",
     "Le due colonne della sosta per strada -- in quale vasca il carroponte "
     "si ferma durante il rientro a vuoto, e per quanto -- vanno insieme: una "
     "sola non dice niente, e una riga con una sola delle due e' un errore. "
     "Tutte e due vuote vuol dire 'rientro diritto'. Per questo la lettura "
     "restituisce un dizionario `soste` vuoto e non None: al contrario delle "
     "attese, qui non c'e' una regola predefinita a cui delegare la scelta, e "
     "vuoto e' gia' una risposta."),
    ("c", "excel_io._stazione_di"),
    ("p",
     "La sosta si scrive col NOME della vasca, che e' quello che si legge "
     "senza contare le righe del Percorso, mentre il programma la vuole come "
     "indice di tappa. Questa funzione fa la traduzione, e None vuol dire che "
     "la vasca non e' nel percorso: il carroponte non ci passa, e il "
     "messaggio lo dice cosi'."),
    ("p",
     "Restituisce la PRIMA tappa e non 'quella giusta', e il docstring "
     "spiega perche' non serve di piu': se una vasca compare due volte nella "
     "ricetta, le due tappe stanno nello stesso punto della rotaia, e per "
     "dire dove un carroponte resta fermo sono la stessa cosa."),

    ("h3", "Il foglio Passaggi"),
    ("c", "excel_io._leggi_passaggi"),
    ("p",
     "I punti di passaggio messi a mano sul grafico: istante, posizione e, "
     "facoltativo, il carroponte che ci deve passare. Il docstring spiega "
     "perche' stanno in un foglio a parte e non in una colonna del "
     "Ciclogramma: non appartengono a una MOSSA. Sono punti che l'utente ha "
     "messo dove voleva, e a quale rientro tocchino lo si ricalcola ogni "
     "volta (model.assegna_passaggi). Rileggerli esattamente come erano "
     "stati scritti e' l'unico modo perche' tornino uguali anche dopo aver "
     "cambiato un tempo in vasca."),
    ("p",
     "Le regole sono quelle del resto del modulo. Una riga del tutto vuota si "
     "salta; tempo e posizione sono obbligatori; il carroponte vuoto vuol "
     "dire 'punto di nessuno', e se c'e' e' numerato da 1 nel file e da 0 nel "
     "programma, con lo stesso controllo del foglio Ciclogramma per chi "
     "scrive 0."),
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
     "Il Percorso porta anche i pesi dello scarto, e il commento dice la "
     "scelta: la zincatura, il bagno che fa il prodotto, pesa piu' dei "
     "risciacqui (10 sotto e 3 sopra contro 1 e 1), e stare sotto il teorico "
     "pesa piu' che starci sopra. E' il modo di far vedere a cosa servono "
     "quelle due colonne senza doverlo spiegare."),
    ("p",
     "Nei Parametri: takt time teorico 300 s con 30 s di tolleranza per parte, traslazione a "
     "500 mm/s con 200 mm/s^2 sia a vuoto sia col pezzo, sollevamento a "
     "350 mm/s con 150 mm/s^2, ingombri asimmetrici (1660 e 620 mm). I "
     "parametri della ricerca sono scritti uguali ai predefiniti -- takt_fisso "
     "1, max_soste_intermedie 2, max_carroponti 10, "
     "tempo_limite_per_tentativo_s 120 -- e scritti invece che lasciati "
     "vuoti: chi apre il modello vede che ci sono e con che valore parte. "
     "Le misure del pezzo restano vuote, e il commento "
     "dice perche': servono solo alla simulazione, che finche' nessuno le "
     "compila disegna il pezzo di una misura convenzionale."),
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
    ("p",
     "Fra i parametri manca risoluzione_tick_per_s, che non e' piu' un "
     "parametro: e' fissa nel programma, e riscriverla nel file farebbe "
     "credere che cambiarla serva a qualcosa. Le cinematiche di sollevamento "
     "passano per la chiusura `cinematica`, che restituisce None quando "
     "l'intera cinematica manca: dal file sono obbligatorie, ma in "
     "ProblemData il campo resta facoltativo, e una linea costruita nel "
     "codice puo' non averle. In quel caso la cella esce vuota, e sara' la "
     "rilettura a dire che manca."),

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
    ("h2", "La linea come tabelle, per la finestra 'Dati linea'"),
    ("p",
     "La finestra 'Dati linea' mostra le stesse tabelle del file e permette di "
     "modificarle. Non ha un formato suo e non ha controlli suoi: tutto passa "
     "di qui."),
    ("c", "excel_io.RigheLinea", None, "    def normalizzata"),
    ("p",
     "Non e' una Configurazione, e il docstring dice perche': deve poter "
     "contenere anche una linea SBAGLIATA, perche' e' li' che la si corregge. "
     "Una Configurazione esiste solo dopo che i controlli sono passati."),
    ("c", "excel_io.RigheLinea.normalizzata"),
    ("c", "excel_io._cella_da_testo"),
    ("p",
     "La finestra lavora con stringhe. Il lettore le accetterebbe, ma un file "
     "salvato cosi' avrebbe i numeri come testo. Le colonne di testo "
     "(_COLONNE_DI_TESTO) restano testo: una vasca che si chiama '10' non deve "
     "diventare il numero 10."),
    ("c", "excel_io.RigheLinea._argomenti"),
    ("p",
     "Il ponte fra le tabelle e il generatore del file: le stesse cinque "
     "tabelle, nell'ordine e nella forma che _aggiungi_fogli_linea si "
     "aspetta. L'unica traduzione e' sulle due tabelle facoltative: nella "
     "finestra Zone e CambioQuota senza righe sono liste vuote, mentre il "
     "generatore 'nessuna tabella' lo dice con None, come la sua firma e come "
     "_righe_esempio. In tutti e due i casi il foglio nasce con la nota "
     "'Vuoto = ...' al posto dei dati."),
    ("h3", "Da dove arrivano le tabelle"),
    ("c", "excel_io._righe"),
    ("p",
     "Il generatore del file e la finestra parlano di righe in due forme "
     "diverse: il primo le vuole come tuple, pronte da appendere a un "
     "foglio, la seconda come liste, perche' le modifica cella per cella. "
     "_righe fa la conversione una volta sola, copiando: la finestra puo' "
     "modificare quello che riceve senza toccare la linea da cui viene. Zone "
     "e CambioQuota assenti diventano liste vuote, cioe' tabelle senza righe."),
    ("c", "excel_io.righe_esempio"),
    ("c", "excel_io.righe_da_configurazione"),
    ("p",
     "Due funzioni di una riga, ed e' il punto: le tabelle della finestra "
     "escono dalle STESSE funzioni che scrivono i file, _righe_esempio e "
     "_righe_da_configurazione. La linea d'esempio che si vede nella "
     "finestra e' quindi per costruzione quella del modello Excel, e una "
     "linea gia' letta si mostra con gli stessi valori con cui verrebbe "
     "risalvata."),
    ("p",
     "righe_da_configurazione e' anche il ripiego dell'interfaccia quando "
     "righe_da_file non puo' rispondere (il Percorso del vecchio formato, "
     "qui sotto): i valori sono gia' interpretati -- una cella 'posti' vuota "
     "e' diventata 1 -- ma la linea si vede e si puo' correggere."),
    ("c", "excel_io.righe_da_file"),
    ("p",
     "Legge le CELLE, non i valori interpretati: una cella 'posti' vuota resta "
     "vuota invece di diventare 1. E' quello che serve per mostrare all'utente "
     "il suo file, e per aprire nella finestra anche un file che non passa i "
     "controlli. Un Percorso del vecchio formato (minimo e massimo) restituisce "
     "None: le sue colonne vogliono dire un'altra cosa, e l'interfaccia ripiega "
     "su righe_da_configurazione."),
    ("h3", "Dove tornano"),
    ("c", "excel_io.leggi_righe"),
    ("p",
     "Il cuore dell'idea: le tabelle si scrivono in un libro in memoria con "
     "_aggiungi_fogli_linea, come le scriverebbe 'Salva', e il libro si legge "
     "con _leggi_libro. Le righe finiscono sul foglio una dopo l'altra dalla "
     "2, quindi la cella di ogni errore indica la riga della tabella: e' cosi' "
     "che la finestra colora le righe sbagliate e ci porta con un clic."),
    ("c", "excel_io.scrivi_righe"),

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
     "Il resto della funzione -- circa seicento righe, quasi tutte testo del "
     "foglio Istruzioni -- e' la costruzione dei sei fogli fissi, foglio per "
     "foglio: Istruzioni, Vasche, Percorso, Parametri, Zone, CambioQuota. "
     "Intestazioni, dati, larghezze, note in corsivo: e' codice ripetitivo "
     "per natura e si legge dall'alto in basso come si legge il file che "
     "produce. Il foglio Parametri ha una riga per OGNI voce di _PARAMETRI, "
     "anche se vuota, e alla descrizione dei facoltativi aggiunge il "
     "predefinito: cosi' il file elenca da solo tutto quello che si puo' "
     "dichiarare."),
    ("p",
     "Zone e CambioQuota nascono sempre, anche vuoti, con una nota che dice "
     "cosa vuol dire lasciarli cosi'. La nota sta in una colonna FUORI da "
     "quelle lette (la D per Zone, la G per CambioQuota), per la stessa "
     "ragione per cui le spiegazioni stanno nelle Istruzioni."),
    ("p",
     "In coda, solo per una linea salvata, i fogli Ciclogramma e Passaggi. Il "
     "secondo nasce soltanto se ci sono punti di passaggio, e il commento "
     "dice perche': un foglio vuoto in piu' in ogni file non direbbe niente a "
     "nessuno. I punti si scrivono ordinati per istante e posizione, col "
     "carroponte numerato da 1 e con tutte le cifre, per lo stesso motivo "
     "per cui non si tagliano nel Ciclogramma."),

    ("h3", "Il foglio Ciclogramma"),
    ("c", "excel_io._scrivi_foglio_ciclogramma"),
    ("p",
     "I gradi di liberta' e nient'altro: takt time, tempo in vasca di ogni "
     "tappa, chi fa ogni trasporto, e dove ogni carroponte passa il tempo "
     "morto (l'attesa dopo la consegna e l'eventuale sosta in una vasca in "
     "mezzo). Il docstring lo dice in modo netto: non si scrivono gli istanti di prelievo ne' le traiettorie, "
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

    ("h3", "Il tempo teorico accanto a quello vero"),
    ("c", "excel_io", "_COLONNE_CICLOGRAMMA = [", "_RIGA_TITOLI_CICLOGRAMMA"),
    ("p",
     "Due colonne che NON sono gradi di liberta': il tempo che quella vasca ha "
     "sulla ricetta (foglio Percorso) e di quanto il ciclogramma se ne "
     "discosta. Stanno in mezzo alla tabella, attaccate a tempo_in_vasca_s, "
     "perche' la domanda che si fa chi apre questo foglio e' una sola -- di "
     "quanto mi sono allontanato dalla ricetta, e dove -- e con il teorico su "
     "un altro foglio bisognava tenere due tabelle aperte e confrontarle riga "
     "per riga."),
    ("q",
     "UNA COLONNA CHE NON SI RILEGGE VA DETTO CHE NON SI RILEGGE. Il teorico "
     "ha una fonte sola; poterlo scrivere anche qui vorrebbe dire poterlo "
     "avere in due versioni nello stesso file. Si riscrive a ogni "
     "salvataggio, quindi un numero messo a mano sparirebbe senza spiegazioni: "
     "per questo il campo `dato` della tabella delle colonne distingue le due "
     "specie, l'intestazione delle calcolate ha un verde piu' chiaro e i loro "
     "valori sono in corsivo grigio."),
    ("p",
     "Lo scarto e' una FORMULA e non un numero (`=E6-F6`): chi ritocca un "
     "tempo in vasca dentro Excel vede subito di quanto si e' allontanato "
     "dalla ricetta, senza dover risalvare dal programma. Il formato "
     "'+0.00;-0.00;0.00' mette il segno anche ai valori positivi, che e' il "
     "modo in cui si legge uno scostamento."),
    ("p",
     "Alla mossa 0 le due celle restano vuote: li' si parte dal carico, dove "
     "il pezzo non STA -- ci viene messo -- e non c'e' nessuna permanenza da "
     "confrontare. E' la stessa ragione per cui `permanenze` comincia da 1."),
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
     "Il file dei risultati contiene quindici fogli in due gruppi, ciascuno "
     "aperto da un cartello. Prima la LINEA (cartello Input) nel formato di "
     "ingresso, col ciclogramma dentro: Istruzioni, Vasche, Percorso, "
     "Parametri, Zone, CambioQuota, Ciclogramma, piu' Passaggi quando ci sono "
     "punti di passaggio. Cosi' lo stesso file si riapre con 'Apri linea...' "
     "e il lavoro riprende da dov'era. Poi il REFERTO (cartello Output): "
     "Riepilogo, Movimenti, SequenzaCarri, TempiVerticali, FlussoPezzo, "
     "Verifica."),
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
     "Il rientro a vuoto e l'attesa sono i due casi risolti guardando la "
     "POSIZIONE invece della struttura, e per la stessa ragione: la sosta in "
     "una vasca in mezzo. Con una sosta il rientro e' spezzato in due, e una "
     "delle due estremita' di ciascun pezzo e' la vasca dove il carroponte si "
     "e' fermato, che la struttura della mossa non conosce."),
    ("p",
     "Per l'attesa si provano prima i due estremi del rientro, che sono il "
     "caso normale, e poi TUTTE le stazioni. Il commento dice cosa "
     "succederebbe senza il secondo giro: la sosta in mezzo verrebbe "
     "attribuita alla vasca di consegna, cioe' scritta nel posto sbagliato. "
     "Il valore di ripiego, se nessuna coincide, e' la stazione di arrivo "
     "della mossa appena finita."),
    ("c", "excel_io._stazione_in_posizione"),
    ("p",
     "La ricerca per posizione del rientro a vuoto. Confronta con "
     "approach_position e non con la posizione della vasca: con una zona di "
     "cambio quota il rientro finisce al punto di cambio quota, non sopra la "
     "stazione, ed e' li' che va cercato. Se in quel punto non c'e' nessuna "
     "tappa -- e' il caso degli svincoli, che stanno fra le vasche -- "
     "restituisce `altrimenti`, cioe' l'estremo dell'arco, e il commento in "
     "_righe_movimenti dice che e' proprio quello che si vuole: un tratto "
     "che passa da uno svincolo resta attribuito alle vasche fra cui viaggia."),

    ("c", "excel_io._scrivi_sequenza_carri"),
    ("p",
     "Il foglio SequenzaCarri e' l'unico del referto che non e' fatto per "
     "essere letto da una persona: e' il programma di ogni carro nel formato "
     "delle tabelle del PLC, da incollare nel progetto cosi' com'e'. Per "
     "questo ha una forma rigida -- un blocco di tre colonne per carro, con "
     "una colonna vuota fra un blocco e l'altro, e cinque righe per passo: "
     "il passo, poi command, param1, param2 e param3 -- e non porta "
     "nient'altro in mezzo. Le spiegazioni, quando servono, stanno in "
     "corsivo sotto l'ultimo passo, dove un copia-e-incolla del blocco non "
     "le prende."),
    ("p",
     "Qui non si decide niente: i passi li calcola programma_carri, e questa "
     "funzione li impagina. E' la stessa divisione del resto del modulo -- "
     "excel_io scrive, la logica sta altrove -- e vuol dire che il programma "
     "si puo' provare senza aprire un file Excel."),
    ("q",
     "IL PASSO 1 DIPENDE DALL'AVVIO. Il programma comincia dall'istante di "
     "avvio scritto nel Riepilogo, se in quell'istante il carro e' fermo in "
     "posizione bassa, altrimenti dal primo istante dopo in cui lo e'. "
     "scrivi_risultati passa a questa funzione lo STESSO `avvio` che scrive "
     "nel Riepilogo, ed e' questo che tiene d'accordo i due fogli: un carro "
     "lasciato dove dice il Riepilogo riparte dal suo passo 1. La prima nota "
     "sotto la tabella lo ripete, con l'istante."),
    ("c", "excel_io._utilizzo_carroponti"),
    ("p",
     "Una riga che risponde a una domanda che l'utente si pone sempre: quanto "
     "lavora davvero ciascun carroponte. Si contano tutti i tratti in cui non "
     "e' fermo -- _FASI_DI_LAVORO -- e si divide per il periodo."),
    ("p",
     "Le corse verticali (presa, rilascio, corsa a vuoto del gancio) contano "
     "come lavoro anche se il carroponte non trasla: l'utilizzo e' il tempo in "
     "cui non e' fermo, e il complemento a 1 e' il tempo passato in attesa."),

    # ==================================================================
    ("h2", "2. I cartelli"),
    ("c", "excel_io", "# Le due meta' del file", "def _cartello"),
    ("p",
     "Due colori -- blu per l'ingresso, verde per il referto -- che finiscono "
     "sulla LINGUETTA. Il commento dice perche': e' l'unico posto in cui si "
     "guarda quando si cerca un foglio."),
    ("c", "excel_io._cartello"),
    ("p",
     "Un foglio che non contiene dati: dice cosa viene dopo. Con quindici "
     "linguette di fila non si capisce dove finisce la linea e comincia il "
     "referto, e un cartello colorato lo si vede senza leggere niente."),
    ("q",
     "L'ELENCO NON E' SCRITTO A MANO. Il docstring lo dichiara e ne da' la "
     "ragione: si ricava dai fogli che ci sono DAVVERO in quel momento "
     "(wb.sheetnames[da:]). Un elenco fisso resterebbe indietro il giorno che "
     "si aggiunge o si toglie un foglio, e un indice che mente e' peggio di "
     "nessun indice. La descrizione di ciascun foglio viene da _COSA_CONTIENE, "
     "e un foglio non elencato li' compare comunque, con la descrizione vuota: "
     "si perde una spiegazione, non una riga. E' quello che succede oggi a "
     "Passaggi, che in _COSA_CONTIENE non c'e'."),
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
     "La linea si riscrive solo se e' stato passato cfg, e il foglio "
     "Ciclogramma solo se c'e' anche il ciclogramma. Senza cfg il file dei "
     "risultati e' solo un referto, senza cartelli -- e non si riapre. E' il "
     "motivo per cui sia il salvataggio dall'interfaccia sia il comando da "
     "terminale passano tutti e due."),
    ("p",
     "La linea si scrive con `dataclasses.replace(cfg, data=data)`: i dati "
     "della configurazione, ma con il ProblemData che e' stato davvero "
     "risolto. Il referto descrive quel ProblemData, e la linea che sta "
     "nello stesso file deve essere la stessa."),
    ("c", "excel_io.scrivi_risultati", "    def tabella", "    # -- Riepilogo"),
    ("p",
     "`tabella` e' l'equivalente di `prepara` per i fogli del referto, con in "
     "piu' i formati numerici per colonna. Averla come chiusura locale invece "
     "che come funzione del modulo tiene vicino il codice a chi lo usa: e' "
     "chiamata quattro volte, tutte dentro questa funzione."),
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
    ("q",
     "LO SCARTO DEL RIEPILOGO NON E' PESATO. Il calcolo rende minimo lo "
     "scarto PESATO dai tempi teorici, ma nel Riepilogo va lo scarto SENZA "
     "pesi (model.scarto_totale): la somma dei valori assoluti, in secondi. "
     "Il motivo e' che il pesato si misura in secondi per peso, e non si "
     "legge come una durata -- chi apre il foglio vuole sapere quanti "
     "secondi di distacco dalla ricetta ci sono davvero. Il pesato non "
     "sparisce: sta riga per riga in FlussoPezzo, accanto ai pesi che lo "
     "producono. La voce si scrive con tutti e due gli obiettivi, perche' "
     "anche col takt time libero lo scarto e' stato reso minimo, a parita' "
     "di takt."),
    ("p",
     "Subito dopo la produzione viene il punto di avvio: dove portare a mano "
     "i carroponti prima di dare il via, e in che istante del ciclo si "
     "trovano cosi'. Il commento spiega la posizione: e' l'unica cosa del "
     "Riepilogo che non descrive il ciclogramma ma dice come USARLO, e chi "
     "legge il foglio per mettere in marcia la linea trova prima il takt "
     "time e poi da dove partire. Se la finestra non ne passa uno, si prende "
     "il primo che trova_avvio propone."),
    ("p",
     "Poi sicurezza (con le vasche interbloccate, 'la prima cosa da sapere "
     "davanti a un takt time piu' alto del previsto'), movimentazione "
     "verticale, esito della verifica, la tabella dei carroponti con il loro "
     "utilizzo e, solo se ce ne sono, le soste durante il rientro a vuoto: "
     "si vedrebbero anche in Movimenti, ma li' bisogna saperle cercare."),
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
     "Fra i dettagli c'e' anche la risoluzione temporale, in tick al secondo: "
     "non si sceglie piu' dal file, e il valore scritto qui e' sempre la "
     "costante RISOLUZIONE_TICK_PER_S."),
    ("p",
     "In fondo il cartello Output, creato per ultimo perche' deve elencare "
     "fogli che a quel punto esistono tutti; quello Input e' stato messo "
     "subito dopo i fogli della linea, per la stessa ragione. Infine il file "
     "viene fatto aprire sul Riepilogo, che non e' piu' il primo foglio."),
]


DOCUMENTI = [
    ("excel_io_1_lettura.docx", LETTURA),
    ("excel_io_2_modello.docx", MODELLO),
    ("excel_io_3_risultati.docx", RISULTATI),
]
