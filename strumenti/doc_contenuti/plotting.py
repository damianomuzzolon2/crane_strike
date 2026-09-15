"""
Il testo dei documenti di plotting.py.

Nove funzioni, ma il modulo e' interessante piu' per le scelte di
disegno che per il codice: buona parte dei suoi commenti racconta cose che
sono state PROVATE e tolte. Questo documento le riprende, perche' sono la
parte che non si ricava rileggendo il codice.
"""

from __future__ import annotations

# --------------------------------------------------------------------------

RIGA_PER_RIGA = [
    ("h1", "plotting.py spiegato riga per riga"),
    ("p",
     "Questo documento accompagna la lettura di plotting.py, il modulo che "
     "disegna il ciclogramma: la posizione lungo la rotaia in funzione del "
     "tempo, per ciascun carroponte. Ogni blocco di codice e' estratto dal "
     "sorgente al momento della generazione."),
    ("p",
     "E' un modulo piccolo e senza stato: riceve un ProblemData e una "
     "Solution, e restituisce un disegno. Non calcola niente di nuovo e non "
     "puo' correggere niente -- se il ciclogramma e' sbagliato, lo disegna "
     "sbagliato. La sua unica responsabilita' e' non far sembrare giusto "
     "quello che non lo e'."),

    # ==================================================================
    ("h2", "Che cosa si vede in un ciclogramma"),
    ("p",
     "Il tempo sull'asse orizzontale, la posizione lungo la rotaia su quello "
     "verticale. Ogni carroponte e' una linea continua che sale quando porta "
     "un pezzo verso il fondo della linea e ridiscende a vuoto per andare a "
     "prenderne un altro. Dove la linea e' piatta, il carroponte e' fermo "
     "sopra una vasca: sta prendendo, lasciando, o aspettando."),
    ("p",
     "Il disegno ripete DUE periodi affiancati. Non e' ridondanza: un "
     "ciclogramma e' periodico per costruzione, e vederne uno solo non "
     "permette di accorgersi se la fine si raccorda con l'inizio. Con due "
     "periodi il raccordo si vede, e si vede anche quali carroponti si "
     "incrociano a cavallo del confine fra un ciclo e il successivo, che e' "
     "proprio dove le collisioni sono piu' facili da introdurre."),

    ("h3", "Le costanti di stile, e cosa e' stato tolto"),
    ("c", "plotting", "_LARGHEZZA = 2.2", "_HOIST_COLORS"),
    ("p",
     "I commenti di questo blocco raccontano due esperimenti falliti, e vale "
     "la pena leggerli come tali."),
    ("p",
     "Il primo: dare un colore diverso a ogni tipo di tratto -- carico, vuoto, "
     "attesa, presa, rilascio -- e un colore diverso a ogni carroponte. Il "
     "risultato era un arcobaleno in cui non si seguiva piu' nessuna "
     "traiettoria. Ora il colore dice UNA cosa sola: di quale carroponte e' la "
     "linea."),
    ("p",
     "Il secondo: tratteggiare i tratti a vuoto per distinguerli da quelli "
     "carichi. Spezzava la traiettoria a meta' del giro e faceva sembrare due "
     "cose diverse quello che e' il percorso di un carroponte solo. Tolto "
     "anche quello: tutti i tratti sono linea continua, e se il pezzo e' "
     "appeso si capisce dal verso -- si sale carichi e si ridiscende vuoti -- "
     "e dal foglio Movimenti del file dei risultati, che lo scrive tratto per "
     "tratto."),
    ("p",
     "Restano sette voci nel dizionario _STYLE, una per tipo di segmento, che "
     "differiscono ormai solo per lo zorder, cioe' per chi sta sopra a chi. I "
     "tratti con il pezzo (loaded, pick, release, quota) stanno sopra a quelli "
     "a vuoto: quando due linee si sovrappongono, quella che conta e' quella "
     "che porta il pezzo."),
    ("p",
     "_COLORE_PEZZO e' l'unico colore che non e' di un carroponte: la linea "
     "del pezzo fermo in vasca, spiegata nel paragrafo 4. Il commento dice "
     "anche da quali grigi deve restare distinto -- quello del pettine, che "
     "nella vista Modifica vuol dire 'ancora da assegnare', e quello delle "
     "righe delle vasche -- e il test [9-ter] lo controlla."),
    ("p",
     "Prima era una linea sottile del colore del carro che aveva lasciato il "
     "pezzo. Nelle vasche di confine, dove il pezzo lo lascia un carro e lo "
     "riprende l'altro, il colore era di uno solo dei due, e le righe colorate "
     "si confondevano con le traiettorie: il colore deve dire UNA cosa sola."),
    ("q",
     "IL DIZIONARIO _STYLE DEVE AVERE UNA VOCE PER OGNI KIND. La riga che "
     "disegna fa `**_STYLE[seg.kind]`: un tipo di segmento nuovo che non sia "
     "stato aggiunto qui non produce un disegno brutto, fa fallire tutto il "
     "grafico con un KeyError. E' il primo dei quattro posti da toccare "
     "quando si introduce un tipo di segmento -- gli altri sono verify.py, "
     "excel_io.py e simulazione.py."),

    ("h3", "Quali tratti sono davvero traslazioni"),
    ("c", "plotting", "# I tratti in cui il carroponte trasla", "def _sample_segment"),
    ("p",
     "_KINEMATIC_KINDS elenca i tre soli tipi in cui il carroponte si sposta "
     "lungo la rotaia. Presa, rilascio, attesa e corse verticali del gancio "
     "sono tempo speso da fermi: sul ciclogramma sono segmenti orizzontali."),
    ("p",
     "'quota' e' l'unico che sorprende. E' la traslazione fra il centro della "
     "vasca e una posizione di svincolo, che avviene DENTRO una presa o un "
     "rilascio: il carroponte e' nel mezzo di un'operazione, ma si sta "
     "muovendo davvero, e va disegnato come tale. Trattarlo come tempo fermo "
     "farebbe apparire la traiettoria come un salto istantaneo."),
    ("p",
     "_STATI_SENZA_SOLUZIONE elenca invece gli stati per cui non c'e' niente "
     "da disegnare. E' un elenco di cio' che si ESCLUDE, non di cio' che si "
     "accetta, e la differenza conta: cosi' stati come MANUALE (un ciclogramma "
     "composto a mano) o PROPOSTA (un punto di partenza) vengono disegnati "
     "senza doverli aggiungere all'elenco. Sono anzi i casi in cui guardare il "
     "ciclogramma serve di piu'."),

    # ==================================================================
    ("h2", "1. _sample_segment -- la curva vera, non il segmento diritto"),
    ("c", "plotting._sample_segment"),
    ("p",
     "E' la funzione che lega questo modulo a kinematics.py, e la ragione per "
     "cui il ciclogramma dice la verita'."),
    ("p",
     "Un tratto di traslazione si potrebbe disegnare come un segmento diritto "
     "fra il punto di partenza e quello di arrivo: agli estremi sarebbe "
     "esatto, e in mezzo sbagliato. Sbagliato in modo sistematico, oltretutto: "
     "il segmento diritto corrisponde a velocita' costante, mentre il "
     "carroponte parte piano, accelera e rifrena. Nella prima meta' della "
     "corsa il carroponte vero e' sempre INDIETRO rispetto alla retta."),
    ("p",
     "Il disegno campiona invece 25 punti e chiede a position_profile dove si "
     "trova il carroponte a ciascuno di essi. Il risultato e' una curva a S. "
     "Chi guarda il ciclogramma per capire se due carroponti si sfiorano deve "
     "poter credere a quello che vede, e con le rette non potrebbe: due rette "
     "che non si toccano possono corrispondere a due curve che si toccano."),
    ("p",
     "Le due righe iniziali sono la scorciatoia per i tratti che non sono "
     "traslazioni: se il segmento e' un'attesa, o se non ha una cinematica "
     "associata, bastano i due estremi. Il controllo `seg.kin is None` copre "
     "anche i tratti fermi che non sono attese -- presa, rilascio, corse "
     "verticali -- ed e' il motivo per cui la condizione non elenca i kind uno "
     "per uno: la presenza della cinematica dice gia' tutto."),
    ("p",
     "math_sign serve perche' position_profile restituisce sempre uno "
     "spostamento POSITIVO, come si e' visto nel documento di kinematics.py: "
     "orientarlo e' compito del chiamante, e qui il verso e' il segno di "
     "x_end - x_start."),

    # ==================================================================
    ("h2", "2. I due istanti in cui il telaio cambia mano"),
    ("p",
     "Sulle traiettorie si marcano dei punti. Due di questi sono i piu' "
     "importanti del disegno: l'istante in cui il telaio si stacca dal fondo "
     "della vasca -- da li' in poi il pezzo e' del carroponte -- e quello in "
     "cui torna dentro la vasca successiva. Fra i due, il pezzo e' appeso."),
    ("p",
     "Il calcolo di quei due istanti e' meno ovvio di quanto sembri, e le due "
     "funzioni che seguono esistono per un errore che e' stato fatto e "
     "corretto."),

    ("h3", "_aggancio_dall_inizio_presa"),
    ("c", "plotting._aggancio_dall_inizio_presa"),
    ("p",
     "L'aggancio si ottiene sommando le durate delle fasi della presa fino a "
     "quella chiamata 'sollevamento del telaio', esclusa: quando comincia il "
     "sollevamento, il telaio si e' appena staccato."),
    ("q",
     "PERCHE' NON SI CONTA ALL'INDIETRO. Il modo naturale sarebbe partire "
     "dalla fine della presa e sottrarre sgocciolamento e sollevamento. "
     "Funziona su una linea semplice e SMETTE di funzionare appena c'e' una "
     "zona di cambio quota: li' la presa contiene anche due traslazioni "
     "orizzontali e una seconda salita, e il conto all'indietro piazzerebbe il "
     "punto in un istante in cui il carroponte non e' nemmeno sopra la "
     "stazione. Il docstring lo dice esplicitamente perche' e' un errore che "
     "si rifarebbe volentieri."),
    ("p",
     "Le fasi si leggono da data.pick_phases(), cioe' dalla stessa "
     "scomposizione che usa il modello CP-SAT per calcolare la durata della "
     "presa. Se le fasi cambiano, il punto si sposta da solo: non c'e' una "
     "seconda descrizione della presa da tenere allineata."),

    ("h3", "eventi_del_trasporto -- l'unica definizione dei punti"),
    ("c", "plotting.eventi_del_trasporto"),
    ("p",
     "Restituisce i quattro istanti in cui, durante un trasporto, succede "
     "qualcosa: l'AGGANCIO (il telaio si stacca dal fondo e il pezzo diventa "
     "del carroponte), la PARTENZA della traslazione, l'ARRIVO, e "
     "l'IMMERSIONE (il telaio torna in vasca e smette di essere del "
     "carroponte)."),
    ("q",
     "LA USANO TUTTI E TRE I DISEGNI. Le traiettorie del ciclogramma, i giri "
     "dei carroponti sul pettine, e il pettine stesso. Averne una sola non e' "
     "pignoleria: sono gli stessi istanti visti dal lato del carroponte e dal "
     "lato del PEZZO, e il pettine e il ciclogramma si guardano apposta uno "
     "accanto all'altro. Se i due disegni li mettessero in punti diversi -- o "
     "se uno ne mostrasse quattro e l'altro due, com'era prima -- chi li "
     "confronta non ci si ritroverebbe, e assegnare una mossa sembrerebbe "
     "cambiare cio' che il pezzo fa."),
    ("p",
     "Le due posizioni della traslazione si passano da fuori perche' cambiano "
     "con il disegno: sul giro del carroponte sono i punti di APPROCCIO, sul "
     "pettine sono le vasche. Aggancio e immersione invece avvengono sempre "
     "sopra la stazione, che il carroponte ci arrivi da un punto di cambio "
     "quota o no -- ed e' per questo che quelle due le calcola la funzione "
     "invece di riceverle."),

    ("h3", "_immersione_dall_inizio_rilascio"),
    ("c", "plotting._immersione_dall_inizio_rilascio"),
    ("p",
     "Speculare, con una differenza che si vede solo guardando dove sta il "
     "`break`: qui la durata della fase viene sommata PRIMA di uscire, perche' "
     "l'istante che interessa e' la fine dell'immersione -- quando il telaio "
     "e' appoggiato -- non il suo inizio. Nell'altra funzione il break viene "
     "prima della somma, perche' li' interessava l'inizio del sollevamento. "
     "Due righe quasi identiche che dicono cose diverse, ed e' esattamente il "
     "tipo di dettaglio che una rilettura distratta uniforma per sbaglio."),

    ("h3", "pezzi_in_vasca -- dove sta il pezzo quando nessuno lo tiene"),
    ("c", "plotting.pezzi_in_vasca"),
    ("p",
     "Per ogni vasca intermedia restituisce tre cose: la stazione, l'istante "
     "in cui il pezzo entra e quello in cui esce. Entrata e uscita sono l'immersione del trasporto che lo "
     "porta e l'aggancio di quello che lo riprende: gli stessi due pallini "
     "disegnati sulle traiettorie, presi da eventi_del_trasporto e da "
     "_aggancio_dall_inizio_presa, cosi' la linea grigia comincia e finisce "
     "esattamente sotto di loro."),
    ("q",
     "I TEMPI VENGONO DA actual_time, NON DAI SEGMENTI. I segmenti sono "
     "istanti entro un ciclo, noti solo modulo T: un pezzo che resta in vasca "
     "130 secondi con un takt time di 34 sembrerebbe restarci 28, e la riga "
     "resterebbe vuota proprio nelle vasche in cui non si svuota mai. "
     "actual_time e' la catena ASSOLUTA del pezzo di riferimento, e la "
     "compilano sia il solutore sia la ricostruzione di una composizione "
     "manuale. Il test [9-ter] prova esattamente questo guasto, e lo vede."),
    ("p",
     "Una vasca compare solo se almeno uno dei due trasporti che la toccano e' "
     "di un carroponte. Quali lo siano si ricava dai tratti a carico -- per la "
     "stessa ragione per cui da li' si ricavano gli eventi: c'e' sempre, ed e' "
     "uno per mossa. In una composizione a mano ancora a meta' i trasporti "
     "non assegnati non si vedono, e la sosta fra due di loro sarebbe un pezzo "
     "che nessuno ha portato li'."),
    ("p",
     "Carico e scarico sono esclusi dal ciclo: nella prima il pezzo non e' "
     "stato depositato da un carroponte, dall'ultima non viene ripreso."),

    # ==================================================================
    ("h3", "corse_verticali -- le frecce su e giu'"),
    ("c", "plotting.corse_verticali"),
    ("p",
     "Per UN carroponte restituisce dove il gancio sale o scende: l'istante a "
     "meta' della corsa, la posizione lungo la rotaia e il verso. Il "
     "ciclogramma ci mette sopra una freccetta, perche' i tratti in cui il "
     "gancio lavora sono piatti come un'attesa e senza la freccia non si "
     "distinguono."),
    ("q",
     "IL VERSO E' UN DATO, MAI UNA DEDUZIONE. Per presa e rilascio lo dicono "
     "le fasi: ogni LiftPhase ha quota iniziale e finale, e basta confrontarle. "
     "Per le corse a vuoto sugli svincoli lo porta scritto il segmento, nel "
     "campo Segment.sale, che riempie chi costruisce il rientro. Dedurlo dai "
     "tratti vicini -- 'dopo un rilascio il gancio e' in basso, quindi sale' "
     "-- e' il tipo di macchina a stati che nella simulazione sbagliava tutto "
     "sulle postazioni senza corsa, ed e' ambiguo quando una delle due corse "
     "manca."),
    ("p",
     "I tempi della presa si contano dal suo inizio, ricavato dal tratto a "
     "carico sottraendo pick_time_at(k); quelli del rilascio dall'arrivo, che "
     "e' la fine del tratto a carico. E' la stessa scelta di "
     "eventi_del_trasporto, per la stessa ragione: presa e rilascio possono "
     "essere spezzati in piu' tratti da una zona di cambio quota, il tratto a "
     "carico no."),
    ("p",
     "La posizione e' quella della fase quando la fase la dichiara -- in una "
     "zona di cambio quota le salite avvengono sul punto di cambio quota, non "
     "sopra la vasca -- e altrimenti quella della stazione. Le fasi senza "
     "durata o senza dislivello -- aggancio, sgancio, sgocciolamento, una "
     "vasca con corsa zero -- non producono frecce."),
    ("q",
     "COME SI SA CHE IL VERSO E' GIUSTO. Il test [9-quater] non ricalcola il "
     "verso con un secondo metodo: controlla che su ogni giro le frecce si "
     "ALTERNINO, perche' un gancio non puo' salire due volte senza essere "
     "sceso. Su una linea con svincoli e senza zone di cambio quota e' una "
     "legge fisica, e un verso invertito -- sulle fasi o sui tratti a vuoto -- "
     "la rompe: e' stato provato."),

    # ==================================================================
    ("h2", "3. Le due funzioni di servizio"),
    ("c", "plotting.math_sign"),
    ("p",
     "Restituisce +1 o -1. Da notare che lo zero da' +1, non 0: per orientare "
     "uno spostamento nullo il verso non conta, ma restituire 0 "
     "moltiplicherebbe la posizione azzerandola."),
    ("c", "plotting.lettura_coordinate"),
    ("p",
     "Sostituisce la scritta che matplotlib mette in basso nella finestra "
     "accanto al puntatore. Esiste per un difetto preciso, spiegato nel "
     "docstring: le etichette dell'asse Y sono i NOMI DELLE VASCHE, non "
     "numeri. Matplotlib usa lo stesso formattatore anche per la lettura del "
     "puntatore e, quando il puntatore non e' esattamente sopra una vasca, "
     "quel formattatore restituisce una stringa vuota. Si finisce per leggere "
     "'(x, y) = (175.0, )', che non dice niente."),
    ("p",
     "La sostituzione riporta la posizione in millimetri, che e' il dato che "
     "serve davvero quando si misura a occhio la distanza fra due carroponti."),

    # ==================================================================
    ("h2", "4. plot_cyclogram -- il disegno"),

    ("h3", "La guardia iniziale"),
    ("c", "plotting.plot_cyclogram", None, "    T = solution.T"),
    ("p",
     "La firma dice due cose utili. `ax=None` permette di disegnare dentro "
     "una figura gia' esistente -- e' cosi' che l'interfaccia grafica "
     "incorpora il ciclogramma nella finestra invece di aprirne una nuova. "
     "`save_path=None` fa scrivere direttamente un PNG, ed e' la strada del "
     "comando da terminale."),
    ("p",
     "Il controllo iniziale filtra sugli stati che dichiarano di NON avere una "
     "soluzione, come detto sopra, e in piu' sul fatto che ci siano davvero "
     "dei segmenti. Il commento richiama la stessa convenzione di "
     "verify._STATI_SENZA_SOLUZIONE: sono due elenchi in due moduli che devono "
     "restare d'accordo."),

    ("h3", "L'asse delle vasche"),
    ("c", "plotting.plot_cyclogram", "    etichette: dict", "    # -- traiettorie"),
    ("p",
     "I nomi delle vasche diventano le ETICHETTE dell'asse Y, non del testo "
     "aggiunto accanto. Il commento spiega perche': scritti a mano finirebbero "
     "sopra i valori numerici e, su una finestra stretta, diventerebbero "
     "illeggibili."),
    ("p",
     "Il dizionario `etichette` e' indicizzato per POSIZIONE, non per vasca. "
     "E' la cosa che conta di questo blocco: due stazioni diverse possono "
     "stare alla stessa posizione lungo la rotaia -- una ricetta che passa due "
     "volte dalla stessa vasca, oppure due vasche gemelle disegnate alla "
     "stessa quota -- e in quel caso l'etichetta le elenca entrambe separate "
     "da una barra. Indicizzare per vasca avrebbe prodotto due tacche "
     "sovrapposte alla stessa altezza."),

    ("h3", "I punti degli eventi"),
    ("c", "plotting.plot_cyclogram", "    for h, segs in enumerate",
     "        for cycle in range(n_cycles):"),
    ("p",
     "Il commento lungo sopra questo blocco e' il piu' istruttivo del modulo, "
     "perche' spiega cosa NON si e' fatto. Marcare ogni cambio di fase -- fine "
     "discesa, fine aggancio, fine sollevamento, fine sgocciolamento -- "
     "avrebbe riempito la linea di punti fino a non vedere piu' niente. Usare "
     "simboli diversi per l'aggancio e per la partenza avrebbe chiesto "
     "all'occhio di leggere una differenza che il disegno mostra gia' da "
     "solo: se li' la linea diventa obliqua il carroponte parte, se resta "
     "piatta il telaio cambia mano."),
    ("p",
     "Restano quattro punti per trasporto: aggancio, sgancio, partenza e "
     "arrivo di ogni traslazione. Tutti con lo stesso simbolo e senza voce in "
     "legenda."),
    ("p",
     "In fondo al blocco si preparano anche le FRECCE delle corse verticali, "
     "da corse_verticali, divise per verso. Anche loro senza voce in legenda: "
     "una freccia in su sopra un tratto piatto si spiega da sola. Vengono "
     "disegnate con una trasformazione spostata di 9 punti tipografici verso "
     "l'alto (offset_copy), non di un numero di millimetri sull'asse: cosi' "
     "restano appena sopra la linea a qualunque ingrandimento, invece di "
     "staccarsene zoomando o finirci sopra allargando."),
    ("q",
     "GLI EVENTI SI RICAVANO DAL TRATTO A CARICO. La condizione e' "
     "`seg.kind == 'loaded'`, non 'pick' o 'release'. La ragione e' che presa "
     "e rilascio possono essere SPEZZATI in piu' tratti da una zona di cambio "
     "quota, mentre il tratto a carico c'e' sempre ed e' uno solo per "
     "trasporto. Prendendo i tratti di presa uno per uno, i punti si "
     "moltiplicherebbero. Da li' si risale all'inizio della presa "
     "sottraendo pick_time_at(k), e si chiedono i quattro istanti a "
     "eventi_del_trasporto."),
    ("p",
     "Il secondo ramo -- `elif` -- marca gli estremi delle traslazioni che NON "
     "sono il trasporto: il rientro a vuoto e il vai-e-torna di una zona di "
     "cambio quota. E' un elif e non un if perche' i due estremi del tratto a "
     "carico li ha gia' messi il ramo sopra: metterli due volte non si "
     "vedrebbe, ma raddoppierebbe i punti da disegnare."),
    ("p",
     "La condizione x_end diverso da x_start esclude le traslazioni di "
     "lunghezza nulla. Un tratto che parte e arriva nello stesso punto non e' "
     "una partenza, e marcarlo metterebbe due punti sovrapposti dove non "
     "succede niente."),

    ("h3", "Le traiettorie, ripetute"),
    ("c", "plotting.plot_cyclogram", "        for cycle in range(n_cycles):",
     "    # -- i pezzi in vasca"),
    ("p",
     "Il ciclo esterno sono i periodi: gli stessi segmenti vengono ridisegnati "
     "traslati di T, 2T e cosi' via. Non si ricalcola niente -- e' letteralmente "
     "lo stesso disegno spostato -- ed e' questa la dimostrazione visiva che "
     "il ciclogramma e' periodico."),
    ("p",
     "Anche i punti degli eventi vengono ripetuti con lo stesso offset. Si "
     "noti che sono calcolati UNA volta sola, fuori dal ciclo dei periodi: "
     "calcolarli dentro avrebbe rifatto lo stesso lavoro n_cycles volte."),

    ("h3", "I pezzi in vasca"),
    ("c", "plotting.plot_cyclogram", "    # -- i pezzi in vasca",
     "    # -- linee verticali"),
    ("p",
     "Sulla riga di ogni vasca intermedia, una linea grigia spessa come le "
     "traiettorie, dall'immersione all'aggancio. Gli intervalli li da' "
     "pezzi_in_vasca; qui si ripetono ogni T, si tagliano alla fine "
     "dell'ultimo ciclo e finiscono tutti in un disegno solo, separati da NaN."),
    ("p",
     "La ripetizione parte dal periodo m = floor(-uscita / T), cioe' dal primo "
     "la cui copia finisce dopo lo zero: un pezzo entrato 'prima' dell'inizio "
     "del disegno -- nel ciclo precedente, o in quello prima ancora se la "
     "permanenza e' lunga -- e' ancora in vasca all'istante zero, e la sua "
     "linea deve comparire a sinistra. Partire da m = 0 lascerebbe scoperto "
     "l'inizio del grafico proprio nelle vasche con i tempi piu' lunghi."),
    ("p",
     "Le copie di un intervallo piu' lungo di T si accavallano sulla stessa "
     "riga, e va bene: sono pezzi diversi in una vasca a capienza multipla, e "
     "la riga sempre piena dice che quella vasca non si svuota mai."),
    ("q",
     "ZORDER 1, SOTTO LE TRAIETTORIE. Quando il carro resta fermo sopra la "
     "vasca col pezzo dentro, la sua linea copre quella grigia. Non e' "
     "una perdita: la linea del pezzo serve a dire dov'e' il pezzo quando "
     "nessun carro e' li' a mostrarlo."),

    ("h3", "Assi, confini fra cicli, legenda"),
    ("c", "plotting.plot_cyclogram", "    # -- linee verticali", "    if save_path:"),
    ("p",
     "Le linee verticali punteggiate segnano i confini fra un periodo e il "
     "successivo. Sono n_cycles + 1 perche' servono anche i due estremi."),
    ("p",
     "La legenda elenca i carroponti e, se ce n'e' almeno una, la linea "
     "grigia del pezzo in vasca. Il commento ricorda che c'erano anche due "
     "voci sul tipo di tratto -- 'con il pezzo', 'senza pezzo' -- che "
     "descrivevano il tratteggio: tolto quello, spiegavano una distinzione "
     "che il disegno non fa piu'. Una legenda che nomina cose invisibili e' "
     "peggio di nessuna legenda."),
    ("p",
     "La voce del pezzo invece resta, perche' una riga di vasca grigia non si "
     "spiega da sola come un pallino su una traiettoria."),
    ("p",
     "L'ultima riga sostituisce il lettore di coordinate con la funzione del "
     "paragrafo 3."),

    ("h3", "Il salvataggio, e i due modi di restituire"),
    ("c", "plotting.plot_cyclogram", "    if save_path:", None),
    ("p",
     "tight_layout viene chiamato solo prima di salvare: dentro una finestra "
     "e' il contenitore a decidere i margini, e forzarli qui darebbe un "
     "risultato peggiore."),
    ("p",
     "Il valore restituito dipende da chi ha creato la figura. Se l'ha creata "
     "questa funzione (ax era None) restituisce la FIGURA, che e' quello che "
     "serve per salvarla o mostrarla; se gliel'hanno passata, restituisce "
     "l'ASSE, perche' la figura e' gia' di chi l'ha fatta. E' una piccola "
     "asimmetria, ma e' quella che permette allo stesso codice di servire sia "
     "il comando da terminale sia la finestra."),
]

DOCUMENTI = [
    ("plotting_riga_per_riga.docx", RIGA_PER_RIGA),
]
