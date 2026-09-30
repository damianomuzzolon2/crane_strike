"""
Il testo dei documenti di kinematics.py.

Il modulo e' piccolo -- una manciata fra funzioni e metodi -- ma sta sotto a
tutto il resto: ogni durata del ciclogramma, ogni vincolo di non collisione e
ogni fotogramma della simulazione finisce qui sotto. Un documento solo, ma che
entra nella matematica invece di limitarsi a parafrasare il codice.
"""

from __future__ import annotations

# --------------------------------------------------------------------------

RIGA_PER_RIGA = [
    ("h1", "kinematics.py spiegato riga per riga"),
    ("p",
     "Questo documento accompagna la lettura di kinematics.py, il modulo che "
     "risponde a una sola domanda: quanto ci mette un carroponte a percorrere "
     "una certa distanza, e dove si trova mentre la percorre. Ogni blocco di "
     "codice e' estratto dal sorgente al momento della generazione: quello che "
     "si legge qui e' quello che c'e' nel file, non una trascrizione."),
    ("p",
     "E' il modulo piu' in basso di tutti. Non importa nulla del progetto e "
     "non sa che esista un ciclogramma: sa solo di masse che accelerano. "
     "Questo lo rende provabile da solo, senza OR-Tools e senza una finestra, "
     "e infatti l'autotest sta in fondo al file stesso."),

    # ==================================================================
    ("h2", "Che cosa fa, in una pagina"),
    ("p",
     "Un carroponte non parte alla sua velocita' massima: accelera, "
     "eventualmente viaggia un tratto a velocita' costante, poi decelera per "
     "fermarsi. Il grafico della velocita' nel tempo ha percio' la forma di un "
     "TRAPEZIO. Se pero' la distanza e' breve, il carroponte fa in tempo solo "
     "ad accelerare e a rifrenare subito, senza mai toccare la velocita' "
     "massima: il trapezio degenera in un TRIANGOLO."),
    ("p",
     "C'e' una sola quantita' che decide quale dei due casi si applica, e vale "
     "la pena ricavarla, perche' torna dappertutto. Per portarsi da fermo alla "
     "velocita' massima con accelerazione a serve un tempo v/a, durante il "
     "quale si percorre v^2/(2a). Per rifermarsi con decelerazione d serve un "
     "tempo v/d e uno spazio v^2/(2d). Quindi la distanza minima per riuscire "
     "a raggiungere la velocita' massima, anche solo per un istante, e':"),
    ("p", "        d_rampe  =  v_max^2 / (2*a_max)  +  v_max^2 / (2*d_max)"),
    ("p",
     "Se la distanza da percorrere e' almeno d_rampe il profilo e' "
     "trapezoidale; se e' minore e' triangolare. Quando accelerazione e "
     "decelerazione coincidono i due addendi sono uguali e la formula si "
     "riduce a v_max^2 / a_max, che e' la soglia che il modulo usava quando la "
     "frenata non era un dato a se'. Tutti i numeri di questo documento che "
     "non dichiarano una decelerazione sono percio' gli stessi di prima."),

    ("q",
     "PERCHE' NON BASTA distanza/velocita'. Con i valori veri di una linea di "
     "zincatura -- carroponte vuoto a 1600 mm/s con 900 mm/s^2 -- la soglia "
     "vale 2844 mm. Il passo fra due vasche vicine sta spesso sotto quel "
     "valore: un salto di 2500 mm e' quindi TRIANGOLARE, e ci vogliono 3,33 s. "
     "Il conto ingenuo 2500/1600 ne darebbe 1,56: meno della meta'. Su una "
     "linea con decine di trasporti a periodo, sbagliare cosi' non produce un "
     "ciclogramma un po' ottimista, ne produce uno irrealizzabile."),

    ("p",
     "Qualche numero, con le due cinematiche tipiche del progetto (vuoto: "
     "1600 mm/s e 900 mm/s^2; carico: 1000 mm/s e 400 mm/s^2). La colonna "
     "'ingenuo' e' distanza/v_max a carroponte vuoto, cioe' l'errore che si "
     "farebbe ignorando le rampe:"),
    ("t", [
        ["distanza", "vuoto", "carico", "ingenuo (vuoto)", "profilo"],
        ["2 500 mm", "3,33 s", "5,00 s", "1,56 s", "triangolare"],
        ["4 000 mm", "4,28 s", "6,50 s", "2,50 s", "trapezoidale"],
        ["10 000 mm", "8,03 s", "12,50 s", "6,25 s", "trapezoidale"],
    ]),

    # ==================================================================
    ("h2", "La seconda complicazione: l'avvicinamento"),
    ("p",
     "Sul SOLLEVAMENTO il trapezio da solo non basta piu'. Vicino al punto in "
     "cui il telaio viene agganciato o posato la velocita' non e' limitata dal "
     "motore ma dalla precisione: il gancio deve infilarsi nel telaio, e il "
     "telaio deve entrare nella vasca senza sbattere. Su quegli ultimi "
     "millimetri si va piano per scelta, non perche' non si possa fare "
     "altrimenti."),
    ("p",
     "La linea dichiara due numeri: una VELOCITA' DI AVVICINAMENTO e una "
     "DISTANZA DI AVVICINAMENTO. La regola che ne discende ha due facce, una "
     "per verso:"),
    ("li", "SCENDENDO a posare: si viaggia normalmente finche' mancano "
           "`distanza` millimetri al fondo; da li' si e' gia' arrivati alla "
           "velocita' di avvicinamento, la si tiene costante, e si frena solo "
           "all'ultimo, quando la frenata diventa necessaria per fermarsi;"),
    ("li", "SALENDO a prelevare: si parte piano e si resta alla velocita' di "
           "avvicinamento per i primi `distanza` millimetri; solo dopo si "
           "accelera verso la velocita' massima e si prosegue col trapezio di "
           "sempre."),
    ("p",
     "In tutti e due i casi la zona lenta sta al capo BASSO della corsa. Non "
     "e' il verso a sceglierla: e' il punto di accoppiamento fra gancio e "
     "telaio, che sta in fondo e non si sposta. E' per questo che la stessa "
     "cinematica, usata nei due versi, produce due profili che sono l'uno il "
     "rovescio dell'altro."),
    ("q",
     "PERCHE' IL MODULO E' STATO RIFATTO. Con una zona di avvicinamento il "
     "profilo di velocita' non e' piu' UN trapezio: e' una successione di "
     "trapezi, uno per ogni tratto a limite di velocita' diverso, saldati in "
     "un punto che NON e' un arresto -- il confine si attraversa alla "
     "velocita' di avvicinamento. Scrivere il caso nuovo accanto al vecchio "
     "avrebbe voluto dire due motori di calcolo da tenere d'accordo, e prima "
     "o poi uno dei due sarebbe stato corretto senza l'altro. Il modulo ne ha "
     "quindi UNO SOLO, generale, e il caso di sempre e' il caso generale con "
     "un tratto solo -- che da' esattamente le stesse formule di prima."),

    # ==================================================================
    ("h2", "1. Approach -- i due numeri e il verso"),
    ("c", "kinematics.Approach"),
    ("p",
     "Velocita', distanza, e da che parte sta la zona. I primi due vengono dal "
     "file Excel e sono proprieta' dell'impianto; il terzo no: `at_end` "
     "descrive il MOVIMENTO, non il carroponte, e cambia a ogni fase "
     "verticale. E' la ragione per cui questa classe non si costruisce mai "
     "leggendo il file: la costruisce model.py, che e' l'unico a sapere se il "
     "gancio in quel momento sta scendendo o salendo."),
    ("p",
     "La distanza e' in millimetri e non in frazione di corsa. Sono due cose "
     "diverse, e la prima e' quella giusta: il motivo per andare piano e' "
     "l'accoppiamento meccanico, che non sa nulla di quanto sia profonda la "
     "vasca. Con una frazione, una vasca profonda il doppio avrebbe una zona "
     "lenta lunga il doppio senza che nessuno l'abbia chiesto."),
    ("p",
     "__post_init__ rifiuta zero e i negativi. Una velocita' di avvicinamento "
     "nulla non e' 'nessun avvicinamento': e' un carroponte che non arriva "
     "mai, cioe' una durata infinita. Chi non vuole l'avvicinamento non "
     "costruisce l'oggetto -- lascia le due celle vuote -- e il campo resta "
     "None."),

    # ==================================================================
    ("h2", "2. La classe Kinematics"),
    ("c", "kinematics.Kinematics"),
    ("p",
     "Tre numeri piu' un oggetto. Velocita' massima e accelerazione sono "
     "obbligatorie; la decelerazione e' facoltativa, e lasciata a None "
     "significa 'frena come accelera'. L'ipotesi simmetrica e' ragionevole su "
     "un carroponte a inverter, dove il limite e' la coppia disponibile e non "
     "cambia di segno; e' sbagliata quando la frenata e' meccanica e molto "
     "piu' energica, o quando col telaio appeso a limitare non e' il motore ma "
     "il pendolo, che tollera una decelerazione minore dell'accelerazione."),
    ("p",
     "I valori facoltativi non sono una comodita' per chi scrive il codice: "
     "sono quello che permette a un file compilato prima che il parametro "
     "esistesse di dare gli stessi identici tempi di prima. Chi il dato non ce "
     "l'ha lascia la cella vuota e non cambia niente. Vale per d_max e vale "
     "per approach."),
    ("p",
     "La proprieta' `decel` e' il punto in cui il facoltativo diventa "
     "obbligatorio: restituisce a_max quando d_max manca, e tutto il resto "
     "del modulo legge SOLO quella. Cosi' il caso simmetrico non e' un ramo "
     "di codice a parte -- che andrebbe mantenuto in parallelo all'altro, e "
     "prima o poi divergerebbe -- ma lo stesso conto con due numeri uguali."),
    ("c", "kinematics.Kinematics.avvicinandosi"),
    ("p",
     "E' l'unica porta d'ingresso per la zona di avvicinamento, e non prende "
     "un Approach gia' fatto: prende i due numeri e il verso, e l'oggetto lo "
     "costruisce lei. La differenza conta. Se accettasse un Approach, un "
     "chiamante distratto potrebbe riusare quello del movimento precedente e "
     "far scendere il gancio con la zona lenta in testa: nessuna eccezione, "
     "solo una corsa che dura quanto l'altra e un telaio che arriva in fondo a "
     "velocita' piena. Cosi' invece il verso e' un argomento obbligatorio, "
     "nominato, deciso sul posto."),
    ("p",
     "I due numeri a None fanno restituire `self`, cioe' la stessa cinematica "
     "di prima. Il caso 'questa linea non ha l'avvicinamento' non e' quindi un "
     "ramo dei chiamanti: passa da qui come tutti gli altri e non produce "
     "nessun oggetto nuovo."),
    ("p",
     "La dataclass e' frozen=True, cioe' immutabile, e cosi' e' Approach. Non "
     "e' un vezzo, ed e' diventato un requisito: uno stesso oggetto Kinematics "
     "viene condiviso da tutto il programma, letto dentro cicli molto stretti, "
     "e ora usato anche come CHIAVE DI CACHE (si veda _tratti). Se qualcuno "
     "potesse modificarlo a meta' di una risoluzione, il modello CP-SAT "
     "risulterebbe costruito con due fisiche diverse e la cache restituirebbe "
     "il profilo sbagliato."),
    ("p",
     "__post_init__ rifiuta il dato assurdo nel momento in cui viene "
     "costruito, non venti chiamate dopo. Con a_max = 0 la divisione in "
     "_distanza_rampe darebbe ZeroDivisionError da qualche parte in fondo, con "
     "un messaggio che non dice quale vasca o quale carroponte era mal "
     "configurato. Il controllo su d_max e' scritto a parte perche' deve "
     "distinguere due cose diverse: non indicata (lecito) e indicata a zero "
     "(assurdo)."),

    # ==================================================================
    ("h2", "3. Il motore: la corsa spezzata in tratti"),
    ("p",
     "Qui sta la parte nuova, ed e' la sola parte che fa i conti. Le tre "
     "funzioni pubbliche, dopo, non fanno altro che leggerne il risultato in "
     "tre modi diversi."),
    ("p",
     "L'idea e' di rappresentare il movimento come una sequenza di tratti ad "
     "accelerazione COSTANTE, e di ricavarla in tre passi: spezzare la corsa "
     "nei pezzi a limite di velocita' costante, calcolare con che velocita' si "
     "attraversa ogni confine fra un pezzo e l'altro, e poi risolvere ogni "
     "pezzo per conto suo come un trapezio con entrata e uscita assegnate."),

    ("h3", "_Tratto"),
    ("c", "kinematics._Tratto"),
    ("p",
     "Tre numeri: quanto dura, a che velocita' comincia, con che "
     "accelerazione prosegue. Non c'e' la posizione, e non e' una "
     "dimenticanza: la posizione si ottiene integrando, e tenerla anche qui "
     "significherebbe avere lo stesso dato in due posti che possono "
     "sfasarsi."),
    ("p",
     "La proprieta' che conta e' scritta nel docstring: dentro un tratto la "
     "posizione e' un polinomio di grado al piu' 2 in t. E' da questa, e da "
     "nient'altro, che discende la garanzia di profile_breakpoints."),

    ("h3", "_limiti -- dove cambia il limite di velocita'"),
    ("c", "kinematics._limiti"),
    ("p",
     "Restituisce la corsa come lista di coppie (lunghezza, velocita' "
     "massima ammessa li'). Senza avvicinamento la lista ha UN elemento e vale "
     "tutta la corsa: e' la riga che fa rientrare il caso di sempre nel caso "
     "generale senza costare niente, ne' in tempo di calcolo ne' in rami di "
     "codice."),
    ("p",
     "Con l'avvicinamento gli elementi sono due, e l'ordine dipende da "
     "`at_end`: scendendo il pezzo lento e' il secondo, salendo e' il primo. "
     "Tutto il resto del modulo non sa piu' niente del verso -- gli basta "
     "l'ordine della lista."),
    ("p",
     "Due casi limite sono assorbiti qui, e nessuno dei due e' un errore da "
     "segnalare. Una velocita' di avvicinamento piu' alta della massima non "
     "vincola niente e si ignora prendendo la piu' bassa (in excel_io e' "
     "comunque rifiutata alla lettura, perche' e' quasi sempre un refuso). Una "
     "zona piu' lunga della corsa vuol dire che la corsa sta tutta dentro la "
     "zona: il pezzo torna a essere uno solo, con il limite basso."),

    ("h3", "_velocita_di_confine -- il cuore"),
    ("c", "kinematics._velocita_di_confine"),
    ("p",
     "Tre passate su una lista di n+1 confini, e l'ordine e' quello che le "
     "rende esatte. La prima mette su ogni confine il piu' basso dei due "
     "limiti che vi si affacciano, e zero ai due estremi, perche' si parte e "
     "si arriva fermi. La seconda scende in avanti: non si puo' arrivare a un "
     "confine piu' in fretta di quanto l'accelerazione consenta, partendo dal "
     "confine precedente. La terza risale all'indietro: non si puo' "
     "attraversare un confine piu' in fretta di quanto la frenata consenta di "
     "rallentare in tempo per quello dopo."),
    ("p",
     "La formula usata in tutte e due le passate e' sempre la stessa, "
     "v_fine^2 = v_inizio^2 + 2*a*spazio, che e' la relazione fra velocita' e "
     "spazio di un moto uniformemente accelerato scritta senza il tempo."),
    ("q",
     "E' LA TERZA PASSATA CHE EVITA I CASI PARTICOLARI. Immaginiamo una zona "
     "di avvicinamento di 2 mm a 80 mm/s con frenata a 800 mm/s^2: per "
     "fermarsi da 80 mm/s servono 4 mm, il doppio di quelli disponibili. La "
     "regola dichiarata -- 'entra nella zona a velocita' di avvicinamento' -- "
     "e' in quel caso fisicamente impossibile, e un codice scritto a rami "
     "avrebbe avuto bisogno di accorgersene. Qui non serve: la passata "
     "all'indietro trova che dal confine finale (velocita' zero) si puo' "
     "risalire solo fino a 56,6 mm/s, e abbassa il limite del confine da sola. "
     "Lo stesso vale per una corsa piu' corta della zona, o per una zona piu' "
     "lunga di tutto lo spazio di accelerazione disponibile."),

    ("h3", "_distanza_rampe e _picco_triangolare"),
    ("p",
     "Sono i due conti di sempre, generalizzati: non partono piu' da fermo e "
     "non arrivano piu' a fermo, ma da v_in a v_out."),
    ("c", "kinematics._distanza_rampe"),
    ("p",
     "E' la soglia fra trapezio e triangolo, riferita a UN pezzo di corsa. Con "
     "v_in = v_out = 0 e v_cap = v_max si riduce parola per parola alla "
     "formula dell'apertura, ed e' il motivo per cui una linea senza "
     "avvicinamento ha ancora esattamente i tempi di prima."),
    ("c", "kinematics._picco_triangolare"),
    ("p",
     "Quando il pezzo e' troppo corto per arrivare al suo limite di velocita', "
     "si sale fino a un picco v_p e da li' si frena. Con rampe simmetriche e "
     "partenza da fermo v_p cadeva a meta' strada e non serviva calcolarla; "
     "con rampe diverse il punto di picco si sposta -- verso la partenza se si "
     "frena piu' forte, verso l'arrivo se si frena piu' piano -- e con "
     "un'entrata e un'uscita non nulle si sposta ancora. Lo si trova imponendo "
     "che i due tratti sommino la lunghezza del pezzo."),
    ("p",
     "Il max() finale sembra una precauzione e non lo e' del tutto: "
     "matematicamente v_p non puo' stare sotto v_in ne' sotto v_out, perche' "
     "le due passate di _velocita_di_confine lo hanno gia' garantito. Serve a "
     "coprire l'ultimo bit di errore numerico, che altrimenti produrrebbe una "
     "durata di rampa negativa -- e un tempo di percorrenza piu' corto del "
     "vero, cioe' esattamente l'errore che nessuno vede."),

    ("h3", "_tratti_di_pezzo -- un trapezio alla volta"),
    ("c", "kinematics._tratti_di_pezzo"),
    ("p",
     "Dato un pezzo con la sua lunghezza, il suo limite e le due velocita' "
     "agli estremi, ne restituisce i tratti. La struttura e' quella di sempre: "
     "se c'e' spazio per la crociera e' un trapezio, altrimenti e' un "
     "triangolo con il picco calcolato."),
    ("p",
     "I tre `if` finali servono a non emettere tratti di durata nulla. Non e' "
     "cosmesi: un tratto vuoto diventerebbe uno spigolo duplicato in "
     "profile_breakpoints, e capita spessissimo -- il pezzo lento di una "
     "discesa, per esempio, ENTRA gia' alla sua velocita' di crociera e non ha "
     "nessuna rampa di salita."),

    ("h3", "_tratti -- il profilo completo, e la cache"),
    ("c", "kinematics._tratti"),
    ("p",
     "Mette insieme i tre passi: spezza, calcola le velocita' di confine, "
     "risolve ogni pezzo. Il risultato e' una tupla di _Tratto, ed e' l'unico "
     "oggetto da cui le tre funzioni pubbliche ricavano tutto."),
    ("q",
     "PERCHE' LA CACHE. La decorazione lru_cache non e' un'ottimizzazione di "
     "comodo. Il verificatore campiona la stessa tratta centinaia di volte per "
     "cercare il minimo della distanza fra due carroponti, e la simulazione la "
     "ricampiona a ogni fotogramma: senza cache ogni campione ricostruirebbe "
     "da zero lo stesso profilo. La chiave e' la coppia (distanza, "
     "cinematica), e le distanze di una linea sono poche e sempre le stesse. "
     "E' anche il motivo per cui Kinematics e Approach DEVONO restare frozen: "
     "una chiave mutabile non e' una chiave."),

    # ==================================================================
    ("h2", "4. travel_time -- quanto ci mette"),
    ("p",
     "E' la funzione piu' chiamata dell'intero progetto. Ogni durata che "
     "compare in un ciclogramma -- andata carica, ritorno a vuoto, "
     "riposizionamento fra due vasche, corsa verticale -- passa di qui, e il "
     "vincolo di non collisione la richiama per ogni passo della "
     "discretizzazione."),
    ("c", "kinematics.travel_time"),
    ("p",
     "Il corpo e' diventato tre righe, e questa e' la misura di quanto il "
     "motore nuovo abbia semplificato le cose: valore assoluto, caso nullo, "
     "somma delle durate dei tratti. I due rami trapezio/triangolo non sono "
     "spariti, sono scesi dentro _tratti_di_pezzo, dove ce n'e' una copia sola "
     "per tutte e tre le funzioni pubbliche."),
    ("p",
     "La funzione ignora la direzione ORIZZONTALE: andare avanti di 3 metri o "
     "indietro di 3 metri costa uguale, e il chiamante sa in che verso sta "
     "andando senza che glielo dica la cinematica. Attenzione a non "
     "confondere questo con il verso dell'avvicinamento, che invece conta "
     "eccome: quello non sta nel segno della distanza, sta dentro la "
     "cinematica, in Approach.at_end."),
    ("p",
     "Il caso d == 0 e' trattato a parte e restituisce zero secco. Non e' un "
     "caso teorico: capita ogni volta che due tappe consecutive della ricetta "
     "sono nella stessa vasca (immersione ripetuta), e capita in tutte le "
     "geometrie degenerate che i test provano apposta."),

    ("h3", "Quanto costa l'avvicinamento"),
    ("p",
     "Col sollevamento del modello d'esempio -- gancio scarico a 500 mm/s e "
     "800 mm/s^2, telaio a 300 mm/s e 500 mm/s^2 -- e una zona di "
     "avvicinamento di 150 mm a 80 mm/s:"),
    ("t", [
        ["corsa", "a gancio scarico", "col telaio"],
        ["900 mm, senza avvicinamento", "2,43 s", "3,60 s"],
        ["900 mm, con avvicinamento", "3,96 s", "4,92 s"],
        ["1 500 mm, senza avvicinamento", "3,63 s", "5,60 s"],
        ["1 500 mm, con avvicinamento", "5,16 s", "6,92 s"],
    ]),
    ("p",
     "Il sovrapprezzo e' quasi costante -- circa un secondo e mezzo a gancio "
     "scarico -- e infatti non dipende dalla corsa: sono sempre gli stessi 150 "
     "mm percorsi a 80 mm/s invece che a velocita' piena. Su una mossa "
     "completa quelle corse verticali sono quattro, e il conto va fatto: e' "
     "tempo che il takt time deve contenere, ed e' esattamente il motivo per "
     "cui il parametro esiste invece di essere un margine a occhio."),
    ("p",
     "Nella tabella le due colonne hanno accelerazione e frenata uguali, e "
     "percio' salita e discesa durano lo stesso. Con una frenata diversa "
     "dall'accelerazione i due versi si separano: la zona lenta cade una volta "
     "in coda e una volta in testa, e i due profili non sono piu' l'uno lo "
     "specchio dell'altro. E' per questo che model.empty_lift_seconds ha "
     "dovuto prendere il verso come argomento."),

    # ==================================================================
    ("h2", "5. position_profile -- dove si trova"),
    ("p",
     "Mentre travel_time da' la durata totale, questa da' lo spazio percorso a "
     "un istante qualsiasi del movimento. Serve a due cose molto diverse: "
     "disegnare le traiettorie curve nel ciclogramma e nella simulazione, e "
     "-- soprattutto -- permettere al verificatore di misurare la distanza fra "
     "due carroponti mentre si muovono, che e' l'unico modo per accorgersi di "
     "una collisione che avviene a meta' di due corse."),
    ("c", "kinematics.position_profile"),
    ("p",
     "Il ciclo consuma i tratti uno dopo l'altro finche' il tempo richiesto "
     "non e' esaurito, e dentro ciascuno applica la legge oraria del moto "
     "uniformemente accelerato, v0*dt + a*dt^2/2. Le tre fasi del trapezio, "
     "che prima erano tre rami di codice con tre formule diverse, sono oggi "
     "tre giri dello stesso ciclo: la crociera e' un tratto con a = 0, la "
     "frenata un tratto con a negativa."),
    ("p",
     "Questa e' anche la ragione per cui il conto e' ora ACCUMULATO invece che "
     "ricalcolato da capo a ogni ramo. La versione vecchia riscriveva per "
     "esteso la somma dei tratti precedenti, e andava bene con tre fasi note; "
     "con un numero variabile di tratti non e' piu' possibile, e il prezzo da "
     "pagare e' un errore di arrotondamento che si accumula. E' un prezzo "
     "molto basso -- cinque addizioni su numeri dello stesso ordine -- ed e' "
     "coperto dal clamp finale."),
    ("q",
     "IL CLAMP. L'ultima riga stringe il risultato fra 0 e la distanza totale, "
     "e fa due lavori insieme. Il primo e' la cortesia di sempre verso chi "
     "chiede un istante fuori intervallo: i tempi arrivano da un modello a "
     "tick interi e riconvertiti in secondi sforano di un pelo la durata, e "
     "senza il clamp l'ultima parabola, superato il vertice, tornerebbe "
     "INDIETRO -- il carroponte risulterebbe arretrare di qualche millimetro "
     "alla fine di ogni corsa. Il secondo e' assorbire l'ultimo bit "
     "dell'accumulo, cosi' che pos(T) sia esattamente la distanza e non la "
     "distanza meno 1e-13."),
    ("q",
     "LO SPOSTAMENTO E' SEMPRE POSITIVO. La funzione restituisce quanto si e' "
     "percorso, non dove ci si trova: il chiamante deve orientarlo lui, con "
     "partenza + risultato oppure partenza - risultato secondo la direzione. "
     "Il docstring lo dice a chiare lettere perche' e' esattamente il tipo di "
     "errore che non da' nessun sintomo finche' non si guarda un disegno e si "
     "vede un carroponte andare dalla parte sbagliata."),

    # ==================================================================
    ("h2", "6. profile_breakpoints -- gli spigoli"),
    ("p",
     "E' la funzione meno ovvia del modulo, ed esiste per un motivo solo: "
     "rendere RIGOROSO il controllo di collisione. Vale la pena spiegare il "
     "problema prima del codice."),
    ("p",
     "Il verificatore deve rispondere alla domanda 'la distanza fra due "
     "carroponti e' mai scesa sotto il minimo?'. La distanza e' una funzione "
     "del tempo, e cercarne il minimo campionandola su una griglia e' un "
     "controllo che, di per se', non dimostra niente: il minimo potrebbe "
     "cadere fra due campioni."),
    ("p",
     "Qui pero' si sa qualcosa in piu' sulla funzione. Fra due spigoli "
     "consecutivi del profilo, la posizione di ciascun carroponte e' un "
     "polinomio di grado al piu' 2 in t (costante, lineare o parabolico). La "
     "differenza fra due polinomi di grado 2 e' ancora di grado 2, e una "
     "parabola ha un solo estremo: campionando gli spigoli e un numero finito "
     "di punti fra di essi si puo' LIMITARE l'errore commesso, invece di "
     "sperare. Ecco perche' gli spigoli servono, e perche' devono essere "
     "esatti."),
    ("c", "kinematics.profile_breakpoints"),
    ("p",
     "Con il motore a tratti la funzione e' diventata la somma cumulata delle "
     "loro durate, e la sua correttezza non e' piu' una cosa da dimostrare a "
     "parte: gli spigoli SONO i confini fra i tratti, per definizione di "
     "_Tratto. Prima le durate delle rampe venivano ricalcolate qui con le "
     "stesse formule di travel_time, ed erano due copie da tenere d'accordo."),
    ("p",
     "Il caso a distanza nulla restituisce una tupla di UN solo elemento, non "
     "due coincidenti: chi la riceve puo' cosi' riconoscere un movimento che "
     "non avviene, invece di trovarsi un intervallo di durata zero da "
     "campionare."),
    ("p",
     "Qualche spigolo vero, sul sollevamento a gancio scarico dell'esempio "
     "(500 mm/s, 800 mm/s^2) per una corsa di 1500 mm. Senza avvicinamento "
     "sono (0; 0,625; 3,0; 3,625): rampa, crociera, frenata. Con la zona di "
     "150 mm a 80 mm/s, scendendo, diventano (0; 0,625; 2,708; 3,233; 5,058; "
     "5,158) -- cinque tratti: rampa, crociera, frenata fino a 80 mm/s, il "
     "lungo tratto lento, la frenata finale di un decimo di secondo. Salendo "
     "sono (0; 0,1; 1,925; 2,45; 4,533; 5,158), che e' la stessa sequenza "
     "letta al contrario."),
    ("q",
     "LO SPIGOLO DEL TRIANGOLO. E' il punto in cui questa funzione poteva "
     "sbagliare in silenzio. In una versione ancora precedente lo spigolo era "
     "t_total/2, che con rampe uguali e' esatto; con rampe diverse il picco "
     "cade altrove, e restituire la meta' avrebbe messo il campione in un "
     "punto dove la curva NON ha uno spigolo -- lasciando il vero spigolo fra "
     "due campioni. La garanzia sull'errore, che e' tutta la ragione per cui "
     "questa funzione esiste, sarebbe decaduta senza che niente fallisse."),
    ("q",
     "COERENZA FRA LE TRE FUNZIONI. Oggi le tre funzioni pubbliche leggono "
     "tutte lo stesso _tratti, e non possono piu' divergere: e' il guadagno "
     "principale della riscrittura, piu' ancora dell'avvicinamento in se'. Se "
     "un giorno si cambiasse il modello di moto -- per esempio aggiungendo il "
     "jerk, cioe' rampe di accelerazione non istantanee -- basterebbe cambiare "
     "il motore, e _Tratto diventerebbe un tratto a jerk costante con la "
     "posizione polinomio di grado 3. Un profilo di posizione che non combacia "
     "con i suoi spigoli farebbe fallire il verificatore in modo "
     "difficilissimo da diagnosticare: segnalerebbe collisioni che non ci "
     "sono, o peggio, non ne segnalerebbe di vere."),

    # ==================================================================
    ("h2", "7. L'autotest in fondo al file"),
    ("p",
     "Il modulo non ha un file di test separato: si prova da solo con "
     "`python kinematics.py`. E' l'eccezione alla regola del progetto, ed e' "
     "giustificata dal fatto che qui non c'e' niente da preparare -- nessun "
     "file Excel, nessuna finestra, nessun solutore."),
    ("c", "kinematics", 'if __name__ == "__main__":'),
    ("p", "Le asserzioni provano proprieta' diverse, e non a caso:"),
    ("li", "la posizione al tempo T deve coincidere con la distanza totale: "
           "lega position_profile a travel_time, cioe' verifica che le due "
           "funzioni raccontino lo stesso movimento;"),
    ("li", "il primo spigolo deve essere 0 e l'ultimo deve coincidere con T: "
           "lega profile_breakpoints alle altre due;"),
    ("li", "gli spigoli devono essere crescenti: e' la proprieta' su cui conta "
           "chi li usa per costruire una griglia di campionamento;"),
    ("li", "il profilo non torna mai indietro. Coglie l'errore piu' probabile "
           "di tutti: una rampa di frenata scritta con il coefficiente "
           "sbagliato produce una parabola che supera il vertice prima della "
           "fine e fa arretrare il carroponte, senza sollevare nessuna "
           "eccezione;"),
    ("li", "nessun campione supera la velocita' massima, e dentro la zona di "
           "avvicinamento nessuno supera quella di avvicinamento. E' "
           "l'asserzione aggiunta con l'avvicinamento, ed e' l'unica che "
           "controlla la regola per quello che e': un limite di velocita' in "
           "funzione della POSIZIONE, non del tempo;"),
    ("li", "l'avvicinamento deve costare. Un limite in piu' non puo' far "
           "guadagnare tempo, e se lo facesse vorrebbe dire che una delle tre "
           "passate di _velocita_di_confine sta alzando un limite invece di "
           "abbassarlo."),
    ("q",
     "IL CAMPIONE A CAVALLO DEL CONFINE. Il controllo sulla velocita' dentro "
     "la zona guarda l'estremo del campione PIU' LONTANO dal capo lento, non "
     "il piu' vicino. Non e' un dettaglio: l'intervallo che attraversa il "
     "confine sta per meta' nel pezzo veloce, e la sua velocita' media e' "
     "legittimamente sopra quella di avvicinamento. Controllarlo farebbe "
     "fallire l'autotest su un codice giusto -- ed e' successo alla prima "
     "stesura."),
    ("p",
     "Le quattro distanze provate (0,1 / 1 / 5 / 20 con v=1 e a=0,5, quindi "
     "soglia 2) cadono due sotto e due sopra: entrambi i rami vengono "
     "percorsi. Un autotest che provasse solo distanze lunghe lascerebbe "
     "scoperto tutto il ramo triangolare, che e' proprio quello che sulle "
     "linee vere si usa di piu'. La zona di avvicinamento provata e' lunga 3, "
     "cioe' piu' della meta' delle distanze in elenco e piu' di due di esse "
     "per intero: anche il caso degenere 'la corsa sta tutta dentro la zona' "
     "viene percorso."),
    ("p",
     "Le tre cinematiche di base coprono il simmetrico, il carroponte che "
     "frena piu' forte di quanto accelera e quello che fa il contrario, e ogni "
     "cinematica viene poi riprovata con la zona in fondo e con la zona in "
     "testa: nove casi in tutto."),

    # ==================================================================
    ("h2", "8. Una nota sulle unita', e un difetto dei commenti"),
    ("p",
     "L'intestazione del modulo dichiara che tutto e' in millimetri, mm/s, "
     "mm/s^2 e secondi. E' cosi', ed e' la convenzione dell'intero progetto."),
    ("q",
     "I docstring di travel_time e position_profile dicono pero' [m], metri: "
     "sono rimasti indietro rispetto al passaggio del progetto ai millimetri. "
     "Il codice e' giusto e le formule sono adimensionali -- funzionano in "
     "qualsiasi unita' coerente -- ma chi legge solo il docstring puo' "
     "convincersi che l'ingresso vada in metri e sbagliare di mille. Sono due "
     "parole da correggere nel sorgente, non in questo documento."),
    ("p",
     "Nel modello CP-SAT i tempi diventano poi TICK interi, perche' il "
     "solutore lavora su interi; la conversione avviene in model.py "
     "(to_ticks) e non riguarda questo modulo, che resta in virgola mobile. "
     "Le posizioni invece restano millimetri reali anche dentro il modello: le "
     "vasche sono ferme, quindi ogni distanza e' una costante nota prima di "
     "risolvere, e non serve discretizzarla."),
]

DOCUMENTI = [
    ("kinematics_riga_per_riga.docx", RIGA_PER_RIGA),
]
