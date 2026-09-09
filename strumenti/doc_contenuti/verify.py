"""
Il testo dei documenti di verify.py.

Ventisette fra funzioni e metodi, divisi in tre documenti perche' rispondono a
tre domande diverse: come si racconta il risultato, quali controlli si fanno,
e come si dimostra -- non si spera -- che due carroponti non si toccano.
"""

from __future__ import annotations

# ==========================================================================
# Documento 1 -- il referto e il giro
# ==========================================================================

REFERTO = [
    ("h1", "verify.py (1) -- il referto e il giro dei controlli"),
    ("p",
     "Primo dei tre documenti su verify.py, il verificatore indipendente. Qui "
     "si vede come e' fatto il referto e in che ordine vengono eseguiti i "
     "nove controlli; il secondo documento entra nei controlli uno per uno, il "
     "terzo nella ricerca delle collisioni. Ogni blocco di codice e' estratto "
     "dal sorgente al momento della generazione."),

    # ==================================================================
    ("h2", "Perche' questo modulo esiste"),
    ("p",
     "Il solutore restituisce OPTIMAL. Sembrerebbe la fine della storia, e "
     "invece e' il punto in cui comincia il problema."),
    ("p",
     "OPTIMAL significa una cosa sola: fra tutte le soluzioni che rispettano i "
     "vincoli CHE GLI SONO STATI SCRITTI, questa e' la migliore. Non dice "
     "niente su quei vincoli. Se uno e' formulato male, o ne manca uno, il "
     "solutore risponde OPTIMAL con la stessa sicurezza, e nessuna parte del "
     "programma se ne accorge -- perche' tutto il resto crede al solutore."),
    ("p",
     "verify.py riparte da capo: prende le traiettorie prodotte e ricontrolla "
     "in Python puro che descrivano un movimento fisicamente possibile. Non "
     "importa `ortools`, mai, e questa e' la sua caratteristica essenziale: un "
     "verificatore che usasse lo stesso solutore non verificherebbe niente, "
     "confermerebbe soltanto."),
    ("q",
     "LA STESSA REGOLA VALE PIU' IN PICCOLO. Un controllore che misura la "
     "stessa cosa del controllato non controlla niente, e non e' un principio "
     "astratto: e' successo. Per un periodo questo modulo ha calcolato le "
     "permanenze in vasca con la stessa definizione del modello, e una linea "
     "con SEI VASCHE SU DIECI fuori tolleranza e' passata con 'VERIFICA "
     "SUPERATA'. Il paragrafo sulle permanenze, nel secondo documento, "
     "racconta cosa era sbagliato."),

    ("h3", "I nove controlli"),
    ("t", [
        ["n.", "controlla", "gravita' tipica"],
        ["1", "struttura: status, takt nella banda, zone contigue", "errore"],
        ["2", "layout: vicinanze che il modello non vincola", "avviso"],
        ["3", "coerenza dei segmenti: continuita', periodo T", "errore"],
        ["4", "copertura delle mosse e durate delle tratte", "errore"],
        ["5", "coerenza di fase (la linearizzazione modulo T)", "errore"],
        ["6", "permanenze minime e massime in vasca", "errore"],
        ["7", "fattibilita' dei trasferimenti a vuoto", "errore"],
        ["8", "COLLISIONI reali, campionate nel tempo", "errore"],
        ["9", "capienza delle vasche", "errore o nota"],
    ]),

    ("q",
     "IL CONTROLLO 8 E' PIU' STRETTO DI QUELLO CHE IL MODELLO IMPONE. Il "
     "modello costruisce la non collisione attorno alla stazione di CONFINE "
     "fra due zone, riservandone la finestra di sosta. Qui invece si pretende "
     "che la distanza fra ogni coppia di carroponti stia sopra il minimo in "
     "OGNI istante e OVUNQUE sulla rotaia. Non e' un eccesso di zelo: serve a "
     "intercettare il caso in cui una stazione vicina a un confine cada dentro "
     "la zona di esclusione, dove il modello non ha alcun vincolo. E' "
     "esattamente il tipo di buco che un verificatore fatto sulla falsariga "
     "del modello non troverebbe mai."),

    ("h3", "I tre insiemi di tipi in testa al file"),
    ("c", "verify", "# Tipi di segmento in cui", "# ---"),
    ("p",
     "_STATIONARY_KINDS e _MOVING_KINDS dividono i segmenti fra quelli in cui "
     "il carroponte trasla e quelli in cui sta fermo lungo la rotaia. Il "
     "commento spiega perche' sono insiemi e non confronti diretti con una "
     "stringa: i tipi fermi sono cresciuti nel tempo e cresceranno ancora."),
    ("p",
     "'quota' e' l'unico che sorprende, ed e' anche l'unico che si sbaglia "
     "facilmente: e' una traslazione che avviene DENTRO una presa o un "
     "rilascio, per raggiungere una posizione di svincolo. Sta dentro "
     "l'operazione, ma il carroponte si muove davvero, quindi appartiene ai "
     "tipi mobili."),
    ("p",
     "_STATI_SENZA_SOLUZIONE elenca cio' che si rifiuta invece di cio' che si "
     "accetta, e la differenza e' quella che permette di verificare anche un "
     "ciclogramma composto a mano ('MANUALE') o una proposta di partenza "
     "('PROPOSTA'). Elencando gli stati ammessi, ogni stato nuovo sarebbe "
     "stato rifiutato per omissione."),

    # ==================================================================
    ("h2", "1. Violation -- una singola anomalia"),
    ("c", "verify.Violation"),
    ("p",
     "Una violazione non e' una stringa: e' un dato. Porta con se' il tipo, la "
     "gravita', il messaggio e -- soprattutto -- le coordinate del problema: "
     "quali carroponti, quale mossa, quale stazione, quale istante, il valore "
     "misurato e quello richiesto."),
    ("p",
     "Il campo `slack` merita attenzione: e' la differenza fra il valore "
     "misurato e quello richiesto, con la convenzione che sotto zero significa "
     "violato. E' cio' che permette di ORDINARE le violazioni per gravita' "
     "reale, e ai test degli sweep di misurare di quanto si sbaglia invece di "
     "sapere solo che si sbaglia."),
    ("p",
     "__str__ costruisce la localizzazione mettendo insieme solo i campi "
     "valorizzati. Il risultato e' allineato in colonne di larghezza fissa "
     "(7 e 16 caratteri) perche' il referto si legge quasi sempre come un "
     "elenco, e le colonne disallineate lo rendono illeggibile appena le righe "
     "sono piu' di cinque."),

    # ==================================================================
    ("h2", "2. VerificationReport -- il referto"),
    ("c", "verify.VerificationReport", None, "    @property"),
    ("p",
     "Oltre alle violazioni, il referto porta le MISURE. E' una scelta "
     "importante: un verificatore che dicesse solo si' o no sarebbe molto meno "
     "utile. Sapere che la separazione minima e' 3500 mm contro i 1800 "
     "richiesti dice che c'e' aria; sapere che e' 1820 dice che la linea sta "
     "in piedi per un pelo, ed e' un'informazione che nessun errore avrebbe "
     "trasmesso."),
    ("p",
     "Tre campi riguardano il campionamento -- passo, numero di istanti, "
     "errore massimo -- e sono li' per una ragione precisa, spiegata nel terzo "
     "documento: senza il limite d'errore, la separazione minima sarebbe un "
     "numero senza garanzie."),
    ("c", "verify.VerificationReport", "    @property", "    def summary"),
    ("p",
     "Le tre proprieta' filtrano per gravita'. `ok` invece non e' calcolato "
     "qui ma passato al costruttore, e vale 'nessuna violazione di gravita' "
     "error': gli avvisi non fanno fallire la verifica. E' voluto -- un avviso "
     "di layout segnala un rischio, non un difetto -- ma va tenuto presente "
     "leggendo un referto: `ok` a True con dieci avvisi merita comunque "
     "un'occhiata."),
    ("c", "verify.VerificationReport.summary"),
    ("p",
     "E' la faccia del modulo: quello che l'utente legge davvero. Vale la pena "
     "notare cosa mostra anche quando va tutto bene."),
    ("li", "la separazione minima con il MARGINE residuo, cioe' quanto si e' "
           "stati vicini al limite;"),
    ("li", "il campionamento, con l'errore massimo: e' la dichiarazione di "
           "quanto ci si puo' fidare del numero sopra;"),
    ("li", "la permanenza PIU' STRETTA fra tutte, con i due margini: dice "
           "quale vasca comanda il ciclogramma;"),
    ("li", "i pezzi contemporanei in vasca, ma solo dove sono piu' di uno."),
    ("p",
     "Il caso con un solo carroponte e' trattato a parte e dice 'n/d "
     "(un solo carroponte, nessuna coppia da controllare)'. Scrivere "
     "'separazione minima: inf' sarebbe stato tecnicamente corretto e "
     "praticamente incomprensibile."),

    # ==================================================================
    ("h2", "3. verify_solution -- il giro"),

    ("h3", "La firma, e le quattro manopole"),
    ("c", "verify.verify_solution", None, "    # -- validazione dell'input"),
    ("p",
     "I valori predefiniti dei primi due parametri sono presi dal problema, "
     "non fissati qui: dt vale un tick e time_tol vale data.eps_seconds, la "
     "stessa tolleranza che usa il modello. Verificare con una tolleranza piu' "
     "larga di quella del modello nasconderebbe gli errori; con una piu' "
     "stretta li inventerebbe."),
    ("p",
     "warn_margin e' spento (0.0) e serve a chi studia la linea: acceso, "
     "segnala anche le separazioni che superano il minimo per poco. Non e' un "
     "controllo di correttezza, e' un allarme di fragilita'."),
    ("q",
     "COSA SOLLEVA E COSA NO. Il docstring lo dice ed e' la regola del "
     "modulo: le violazioni NON sollevano eccezioni, si raccolgono nel "
     "referto. Si solleva ValueError solo se l'input e' malformato. La "
     "distinzione e' fra 'questa soluzione e' sbagliata' -- che e' una "
     "risposta -- e 'questo non e' una soluzione' -- che e' un errore di chi "
     "chiama."),

    ("h3", "La validazione dell'ingresso"),
    ("c", "verify.verify_solution", "    # -- validazione dell'input", "    T = solution.T"),
    ("p",
     "Cinque controlli, tutti con eccezione. Il piu' istruttivo e' quello "
     "sulle zone: il messaggio non dice solo che mancano, dice COME "
     "ottenerle, con la riga di codice pronta "
     "(dataclasses.replace(data, zones=zones)). E' l'errore piu' facile da "
     "fare chiamando questo modulo, perche' la ProblemData di partenza non ha "
     "le zone -- le decide solve_auto_hoists -- e passare quella sbagliata e' "
     "naturale."),
    ("p",
     "L'ultimo controllo confronta il numero di traiettorie con quello delle "
     "zone. E' la guardia contro l'errore precedente commesso a meta': aver "
     "aggiornato le zone ma non la soluzione, o viceversa."),

    ("h3", "L'ordine dei nove controlli"),
    ("c", "verify.verify_solution", "    T = solution.T", "    violations = sorted("),
    ("p",
     "La funzione `add` e' una chiusura che accumula in V: passandola a tutti "
     "i controlli, ciascuno di essi non deve sapere niente di come le "
     "violazioni vengono raccolte. E' il motivo per cui i controlli hanno "
     "firme cosi' uniformi e si possono leggere uno per volta."),
    ("p",
     "L'ordine non e' casuale. _resolve_plans viene per primo perche' tutti "
     "gli altri possono averne bisogno. _check_per_hoist e' l'unico che "
     "RESTITUISCE qualcosa -- le traiettorie campionabili -- e deve percio' "
     "precedere il controllo delle collisioni, che le usa. In mezzo, i "
     "controlli indipendenti fra loro."),
    ("p",
     "Da notare che nessun controllo interrompe la catena: si eseguono tutti, "
     "sempre. Fermarsi al primo errore darebbe un referto che dice una cosa "
     "sola e costringerebbe a rilanciare dopo ogni correzione. E' la stessa "
     "scelta che fa excel_io con gli errori di compilazione."),

    ("h3", "L'ordinamento finale"),
    ("c", "verify.verify_solution", "    violations = sorted(", None),
    ("p",
     "Le violazioni vengono ordinate per gravita' -- errori, avvisi, note -- "
     "con un ordinamento STABILE, che quindi conserva l'ordine di scoperta "
     "dentro ciascun gruppo. Chi legge trova in cima quello che deve "
     "correggere, e sotto, nell'ordine in cui il verificatore le ha "
     "incontrate, le cose da sapere."),

    # ==================================================================
    ("h2", "4. Ricostruire quello che manca"),
    ("p",
     "Una soluzione porta con se' i valori risolti dal modello (solution.plans). "
     "Non sempre: un ciclogramma composto a mano non passa dal solutore, e un "
     "file salvato da una versione vecchia del programma potrebbe non averli. "
     "Il verificatore deve funzionare comunque."),
    ("c", "verify._resolve_plans"),
    ("p",
     "Se i piani ci sono, si usano. Se non ci sono, si ricostruiscono dai "
     "SEGMENTI, che ci sono sempre: l'ordine di visita, la fase locale di "
     "ogni prelievo e l'istante di fine si leggono dai tratti a carico."),
    ("q",
     "COSA NON SI PUO' RICOSTRUIRE. I tempi ASSOLUTI (actual_time). Dai "
     "segmenti si ricava la fase, cioe' l'istante modulo T, ma non a quale "
     "periodo appartenga: il ciclogramma e' periodico, e un segmento non porta "
     "scritto quante volte il ciclo si e' gia' ripetuto. Per questo la "
     "funzione registra una nota nel referto -- 'le permanenze sono "
     "verificabili solo modulo T' -- invece di far finta di niente. I "
     "controlli 5, 6 e 9 in quel caso si fermano, ed e' giusto che chi legge "
     "lo sappia."),
    ("p",
     "dep_hi e arr_lo -- partenza dal confine alto e arrivo al confine basso "
     "-- si cercano fra i tratti a vuoto confrontando le posizioni con i punti "
     "di APPROCCIO. Se non si trovano restano NaN, che si propaga nei "
     "confronti senza far scattare falsi allarmi: ogni confronto con NaN e' "
     "falso."),

    ("h3", "_at e _move_of_loaded_segment"),
    ("c", "verify._at"),
    ("c", "verify._move_of_loaded_segment"),
    ("p",
     "La seconda risponde a: 'di quale mossa e' questo tratto a carico?'. La "
     "riconosce dagli ESTREMI, confrontandoli con i punti di approccio di ogni "
     "mossa della zona."),
    ("q",
     "PERCHE' NON SI GUARDA seg.move. Il segmento porta scritto a quale mossa "
     "appartiene, e leggerlo sarebbe immediato. Il docstring spiega perche' "
     "non si fa: il verificatore deve poter controllare anche una traiettoria "
     "che il modello non ha prodotto, dove `move` potrebbe essere sbagliato o "
     "assente. Fidarsi di un campo scritto da chi si sta verificando e' "
     "esattamente il modo in cui un controllo smette di controllare. Lo stesso "
     "principio ritorna in _durata_traslazione_di_quota, che guarda la fase e "
     "non la cinematica scritta nel segmento."),
    ("p",
     "Si noti che si confrontano i punti di APPROCCIO e non le posizioni delle "
     "stazioni. Con una zona di cambio quota il tratto col pezzo parte -- o "
     "finisce -- sul punto di cambio quota, che sta altrove: cercare la "
     "stazione non troverebbe niente e ogni tratto a carico verrebbe segnalato "
     "come non corrispondente a nessuna mossa."),
]


# ==========================================================================
# Documento 2 -- i controlli
# ==========================================================================

CONTROLLI = [
    ("h1", "verify.py (2) -- i controlli, uno per uno"),
    ("p",
     "Secondo dei tre documenti su verify.py. Qui si entra nei controlli da 1 "
     "a 7 e nel 9; le collisioni -- il controllo 8 -- hanno un documento "
     "loro. Il primo documento spiega come e' fatto il referto e in che ordine "
     "i controlli vengono chiamati."),

    # ==================================================================
    ("h2", "1. Struttura"),
    ("c", "verify._check_structure"),
    ("p",
     "Tre cose: il takt time sta nella banda dichiarata; le zone sono "
     "intervalli sensati; le zone coprono tutte le mosse in modo contiguo ed "
     "esclusivo."),
    ("p",
     "L'ultimo controllo e' scritto in modo compatto e vale la pena leggerlo "
     "bene: si mettono in fila tutte le mosse coperte e si confronta la lista "
     "con range(n_moves). Un confronto di LISTE, non di insiemi, quindi "
     "verifica in un colpo solo tre proprieta' diverse -- che non manchi "
     "niente, che non ci sia niente in piu', e che l'ordine sia crescente. "
     "Due zone che si scambiano di posto lungo la rotaia darebbero lo stesso "
     "insieme e una lista diversa."),

    # ==================================================================
    ("h2", "2. Layout"),
    ("c", "verify._check_layout"),
    ("p",
     "Chiama model.zone_layout_conflicts, cioe' ESATTAMENTE la stessa funzione "
     "con cui solve() rifiuta le suddivisioni non rappresentabili. Non una "
     "copia: la stessa. Cosi' le due analisi non possono divergere."),
    ("q",
     "QUI CONDIVIDERE E' GIUSTO, ALTROVE NO. Puo' sembrare in contraddizione "
     "con il principio del modulo -- non misurare la stessa cosa del "
     "controllato. Non lo e', perche' qui non si sta verificando un RISULTATO "
     "del modello, si sta rilevando un fatto geometrico sui dati di ingresso. "
     "E il verdetto e' comunque diverso: per solve() e' un rifiuto, qui e' "
     "solo un avviso, perche' una soluzione fatta a mano o prodotta con "
     "allow_unsafe_layout va comunque verificata. A dire se il rischio si e' "
     "concretizzato e' il controllo 8, che invece e' indipendente per davvero."),

    # ==================================================================
    ("h2", "3 e 4. I segmenti di ciascun carroponte"),
    ("p",
     "E' il controllo piu' lungo del modulo, e fa sei cose diverse su ogni "
     "traiettoria. Le si vede una per volta."),
    ("c", "verify._check_per_hoist", None, "        # -- continuita' nel tempo"),

    ("h3", "Il carroponte in due posti insieme"),
    ("c", "verify._check_per_hoist", "        # -- il carroponte e' in due posti insieme?",
     "        # -- continuita' nel tempo"),
    ("c", "verify._mosse_sovrapposte"),
    ("q",
     "VA CERCATO PER PRIMO, PERCHE' RENDE PRIVO DI SENSO IL RESTO. Continuita', "
     "periodicita' e durata della mossa si calcolano tutte confrontando tratti "
     "CONSECUTIVI, e hanno senso solo se i tratti formano una catena. Se due "
     "mosse si sovrappongono nel tempo la catena non esiste, e quei controlli "
     "si mettono a segnalare la stessa cosa una volta per ogni coppia. Su una "
     "composizione a mano lasciata a meta' -- che e' lo stato normale mentre "
     "si lavora -- significa trentacinque violazioni per sei fatti, con il "
     "messaggio utile sepolto in mezzo."),
    ("p",
     "La funzione restituisce una riga per COPPIA DI MOSSE, non per tratto: "
     "due mosse sovrapposte producono decine di tratti che si accavallano, e "
     "ciascuno darebbe una violazione. Guarda solo i tratti che dichiarano una "
     "mossa -- attesa e rientro a vuoto non ne hanno una, e possono "
     "legittimamente toccare l'inizio o la fine di un'altra."),
    ("p",
     "Il messaggio nomina le due mosse e le due vasche, e dice le due cose "
     "che si possono fare: dare una delle due a un altro carroponte, oppure "
     "allontanarle nel tempo cambiando i tempi in vasca."),

    ("h3", "Continuita'"),
    ("c", "verify._check_per_hoist", "        # -- continuita' nel tempo",
     "        for s in segs:"),
    ("p",
     "Due controlli su ogni coppia di segmenti consecutivi: che non ci sia un "
     "buco o una sovrapposizione nel TEMPO, e che non ci sia un salto nello "
     "SPAZIO. Il secondo e' quello che intercetta un carroponte che si "
     "teletrasporta -- un difetto che non produce nessun sintomo nel modello, "
     "perche' li' i segmenti sono solo intervalli con delle durate."),
    ("q",
     "UNA ROTTURA SOLA SI DICE PER INTERO, MOLTE SI RIASSUMONO. Una "
     "traiettoria spezzata si rompe in piu' punti, e ogni punto produce due "
     "violazioni -- il tempo e la posizione -- che descrivono lo stesso "
     "guasto visto da dove si vede. Con una sola rottura il punto preciso E' "
     "l'informazione e va detto; con dieci, quello che serve e' sapere che "
     "sono dieci e qual e' la peggiore, piu' il fatto che spariranno tutte "
     "insieme. Non e' un filtro sulla severita': la soluzione resta "
     "rifiutata."),
    ("p",
     "Le due tolleranze sono diverse, e non per distrazione: il tempo si "
     "confronta con time_tol (un decimo di secondo, la tolleranza del "
     "modello), lo spazio con 1e-6 mm. I tempi nel modello sono tick interi e "
     "riconvertiti, quindi hanno un errore vero; le posizioni sono costanti "
     "note, e un salto di un micron e' gia' un difetto di costruzione."),
    ("p",
     "Il terzo controllo -- durata negativa -- sembra superfluo dopo i primi "
     "due, e non lo e': un segmento con t_end minore di t_start passa "
     "inosservato ai controlli di continuita' se anche il successivo e' "
     "spostato in modo coerente."),

    ("h3", "Periodicita'"),
    ("c", "verify._check_per_hoist", "        # -- il ciclo deve durare",
     "        # -- confini spaziali"),
    ("p",
     "Un ciclogramma e' periodico, e questo significa due cose che vanno "
     "controllate separatamente: il giro dura esattamente T, e il carroponte "
     "TORNA dove era partito. La seconda non segue dalla prima, ed e' quella "
     "che intercetta la traiettoria che deriva -- un giro che si sposta di "
     "qualche millimetro a ogni ripetizione, e che dopo cento cicli e' "
     "altrove."),
    ("q",
     "SOLO SE I TRATTI FORMANO UNA CATENA. Su una traiettoria spezzata, "
     "`ultimo.t_end - primo.t_start` non e' la durata di un giro: e' la "
     "distanza fra due istanti che non si susseguono. Segnalarla come periodo "
     "sbagliato aggiunge un errore che non descrive niente -- e sulla "
     "composizione a mano ne aggiungeva uno per carroponte."),

    ("h3", "Confini della zona"),
    ("c", "verify._check_per_hoist", "        # -- confini spaziali",
     "        # -- copertura delle mosse"),
    ("p",
     "Ogni carroponte deve restare nell'intervallo di rotaia delle sue "
     "stazioni. Il `break` dopo la segnalazione evita di riportare due volte "
     "lo stesso segmento quando entrambi gli estremi sono fuori."),

    ("h3", "Le durate delle tratte a carico"),
    ("c", "verify._check_per_hoist", "        # -- copertura delle mosse",
     '            elif s.kind == "empty":'),
    ("p",
     "Qui ci sono DUE controlli sulla stessa mossa, e il commento nel codice "
     "difende la ridondanza. Il primo verifica la sola traslazione "
     "orizzontale contro horizontal_loaded_seconds; il secondo verifica la "
     "mossa nel suo insieme -- presa, traslazione, rilascio -- contro "
     "loaded_leg_seconds."),
    ("q",
     "PERCHE' NON BASTA IL TOTALE. Controllando solo la durata complessiva, "
     "una traslazione fisicamente impossibile compensata da una presa piu' "
     "lunga del dovuto passerebbe: i due errori si annullano nella somma. "
     "Sono proprio i due valori che il modello calcola separatamente, quindi "
     "sono anche i due posti in cui puo' sbagliare separatamente."),
    ("q",
     "E PERCHE' IL TOTALE TACE SU UNA TRAIETTORIA SPEZZATA. La durata della "
     "mossa intera si ricava allargandosi ai tratti ADIACENTI: se i tratti di "
     "due mosse sono intrecciati, il vicino di una presa e' il rilascio "
     "dell'altra e l'allargamento si ferma subito. Ne esce 'la mossa dura "
     "26,7 s invece di 46,7' -- vero come misura e inservibile come diagnosi, "
     "perche' la causa e' l'intreccio, gia' segnalato. Il controllo sulla sola "
     "traslazione invece regge sempre: guarda un tratto solo."),

    ("h3", "Le tratte a vuoto, le quote, e i tipi sconosciuti"),
    ("c", "verify._check_per_hoist", '            elif s.kind == "empty":',
     "        for k in range(zone.lo, zone.hi + 1):"),
    ("p",
     "Il rientro a vuoto si controlla TRATTA PER TRATTA, non come giro "
     "complessivo. Il commento spiega perche': fra due vasche il rientro puo' "
     "essere spezzato dalla salita e dalla discesa sugli svincoli, e la somma "
     "delle tratte non e' la distanza in linea d'aria."),
    ("p",
     "L'ultimo ramo -- tipo di segmento sconosciuto -- e' la rete di "
     "sicurezza contro un'estensione fatta a meta'. Introdurre un tipo nuovo "
     "senza aggiungerlo a _STATIONARY_KINDS o _MOVING_KINDS lo fa segnalare "
     "come errore, invece di lasciarlo passare senza controlli. E' la "
     "differenza fra un'omissione che si vede subito e una che sta nascosta "
     "finche' non produce un danno."),

    ("h3", "Copertura delle mosse e ordine"),
    ("c", "verify._check_per_hoist", "        for k in range(zone.lo, zone.hi + 1):",
     None),
    ("p",
     "Ogni mossa della zona deve comparire ESATTAMENTE una volta nel ciclo, e "
     "i due difetti opposti si dicono in modo diverso. Le mosse MANCANTI si "
     "raccolgono in una riga sola: durante una composizione a mano sono tutte "
     "quelle non ancora assegnate, e su una linea lunga possono essere dieci "
     "-- dieci righe identiche dicono lo stesso fatto che ne basta una a dire. "
     "Quelle RIPETUTE restano una per una: sono poche e ciascuna e' un difetto "
     "a se'."),
    ("p",
     "Sull'ordine si controlla poi che non contenga mosse ESTRANEE alla zona "
     "ne' mosse elencate due volte. Le mancanti no: le ha gia' contate il "
     "controllo di copertura, e ripeterle direbbe due volte la stessa cosa con "
     "parole diverse."),
    ("q",
     "IL GIRO VA RACCONTATO IN ORDINE DI PRELIEVO. Non e' una convenzione di "
     "comodo: e' cio' che rende ben definito l'arco su cui il periodo si "
     "richiude -- l'ultimo -- e quindi l'unico a cui si somma un T. Un elenco "
     "fuori ordine sposterebbe quel +T su un arco qualunque, e il controllo "
     "dei trasferimenti misurerebbe distanze fra istanti che non si "
     "susseguono."),
    ("q",
     "PRIMA QUI SI PRETENDEVA CHE IL GIRO COMINCIASSE DALLA MOSSA DI CONFINE "
     "BASSO, ed era un difetto vero. Per il solutore le due cose coincidono -- "
     "il modello costringe quella mossa a essere anche la prima in ordine di "
     "tempo -- ma componendo A MANO nessuno lo costringe: si sceglie il tempo "
     "in vasca e le fasi cadono dove cadono. Il giro veniva allora RUOTATO per "
     "farlo cominciare da li', e il +T restava attaccato alla mossa sbagliata: "
     "ne usciva la pretesa di andare dall'ultima mossa alla prima senza "
     "cambiare periodo, cioe' indietro nel tempo. Un 'non arriva in tempo' "
     "sfasato di esattamente un takt time, su un giro che stava benissimo in "
     "piedi."),

    ("h3", "_leg_duration -- allargarsi fino a dove?"),
    ("c", "verify._leg_duration"),
    ("p",
     "Serve a rispondere a 'quanto e' durata questa mossa per intero', "
     "partendo dal suo tratto a carico e allargandosi ai tratti adiacenti. La "
     "difficolta' e' sapere dove fermarsi."),
    ("p",
     "Il criterio e' il campo `move`: ci si allarga finche' i tratti "
     "dichiarano la stessa mossa e sono di un tipo compatibile (pick e quota "
     "prima, release e quota dopo). Attesa e rientro a vuoto non dichiarano "
     "nessuna mossa, quindi fermano da soli l'allargamento."),
    ("q",
     "QUI SI GUARDA seg.move, POCO FA NO. La contraddizione e' apparente. In "
     "_move_of_loaded_segment si stabiliva DI CHI e' un tratto, ed e' un dato "
     "da verificare: fidarsi sarebbe stato circolare. Qui si sta invece "
     "delimitando un raggruppamento, e la durata risultante viene poi "
     "confrontata con loaded_leg_seconds. Se `move` fosse sbagliato, il "
     "raggruppamento sarebbe sbagliato e il confronto fallirebbe: il difetto "
     "verrebbe comunque a galla, solo con un messaggio diverso."),

    ("h3", "_durata_traslazione_di_quota"),
    ("c", "verify._durata_traslazione_di_quota"),
    ("p",
     "Quanto deve durare una traslazione fatta dentro una presa o un rilascio. "
     "Si cerca la fase corrispondente confrontando gli estremi con quelli "
     "dichiarati dalle fasi della stazione."),
    ("p",
     "Il docstring difende la scelta di guardare la FASE e non la cinematica "
     "scritta nel segmento, ed e' lo stesso principio di "
     "_move_of_loaded_segment: la cinematica del segmento e' uno dei dati che "
     "il verificatore deve controllare, non uno su cui appoggiarsi. Se il "
     "modello avesse associato la cinematica sbagliata a quel tratto -- quella "
     "a vuoto invece di quella a carico, per dire -- appoggiarsi ad essa "
     "renderebbe il controllo cieco proprio all'errore che deve trovare."),

    # ==================================================================
    ("h2", "5. Coerenza di fase"),
    ("c", "verify._check_phase_and_dwell", None, "    if not solution.actual_time:"),
    ("p",
     "Il modello lavora modulo T: i prelievi sono espressi come fase locale "
     "dentro il periodo, non come istanti assoluti. Questo controllo verifica "
     "che quella rappresentazione sia coerente con se stessa -- che la fase "
     "stia dentro [0, T) e che l'istante di fine sia davvero la fase piu' la "
     "durata della mossa."),
    ("c", "verify._check_phase_and_dwell", "    if not solution.actual_time:",
     "    # 5) la fase locale"),
    ("p",
     "Senza i tempi assoluti i controlli 5, 6 e 9 non si possono fare, e la "
     "funzione si ferma. Non aggiunge una nota qui: l'ha gia' messa "
     "_resolve_plans, e ripeterla farebbe apparire due volte la stessa cosa "
     "nel referto."),
    ("c", "verify._check_phase_and_dwell", "    # 5) la fase locale",
     "    # 6) permanenze"),
    ("p",
     "Il cuore del controllo 5: il tempo assoluto e la fase locale devono "
     "differire di un multiplo INTERO di T. Il conto e' fatto con attenzione: "
     "si prende il resto della differenza modulo T e poi il minimo fra il "
     "resto e T meno il resto, cosi' uno scarto appena SOTTO il multiplo -- che "
     "darebbe un resto vicino a T -- viene misurato come piccolo e non come "
     "enorme. Senza quella riga, un errore di un millesimo verrebbe riportato "
     "come uno scarto di T meno un millesimo."),

    # ==================================================================
    ("h2", "6. Le permanenze, e l'errore che le ha rese inutili"),
    ("c", "verify._check_phase_and_dwell", "    # 6) permanenze", None),
    ("p",
     "Il pezzo deve stare in vasca fra il minimo e il massimo di processo. "
     "Sembra il controllo piu' semplice del modulo, ed e' quello che ha avuto "
     "il difetto piu' grave."),
    ("q",
     "IL BAGNO NON E' L'INTERVALLO FRA I MOVIMENTI DEL GANCIO. E' scritto nel "
     "commento del codice, ed e' la lezione piu' cara di questo modulo. Il "
     "pezzo e' IMMERSO anche mentre il gancio che lo ha deposto risale, e "
     "anche mentre quello che verra' a riprenderlo ricala: sono secondi di "
     "bagno a tutti gli effetti. Il verificatore ha condiviso per un periodo "
     "la definizione del modello, ed e' cosi' che una linea con SEI VASCHE SU "
     "DIECI fuori tolleranza e' passata con 'VERIFICA SUPERATA'."),
    ("p",
     "La correzione e' il termine `extra`, che data.bath_extra_seconds "
     "calcola: il tempo di immersione che non appartiene a nessun trasporto. "
     "Il messaggio d'errore lo espone -- 'di cui Ns con il gancio in movimento "
     "a vuoto' -- perche' senza quel dettaglio la permanenza segnalata non "
     "corrisponderebbe a nessun numero che l'utente riesce a ritrovare sul "
     "ciclogramma."),
    ("p",
     "Vale la pena notare che il caso e' passato inosservato proprio perche' "
     "il verificatore era d'accordo con il modello. Nessuno dei due sbagliava "
     "rispetto all'altro: sbagliavano insieme, e la verifica confermava."),

    ("h3", "_compute_dwell_slack"),
    ("c", "verify._compute_dwell_slack"),
    ("p",
     "Non controlla niente: misura. Per ogni permanenza restituisce quanto sta "
     "sopra il minimo e quanto sotto il massimo, ed e' da qui che il referto "
     "ricava la riga 'permanenza piu' stretta'."),
    ("p",
     "Le permanenze rigide -- dove massimo e minimo coincidono -- vengono "
     "SALTATE. Sono quelle senza margine per definizione, e includerle "
     "risulterebbe sempre come la piu' stretta di tutte, nascondendo la vasca "
     "che davvero comanda il ciclogramma."),

    # ==================================================================
    ("h2", "7. I trasferimenti a vuoto"),
    ("c", "verify._check_transfers"),
    ("p",
     "Finita una mossa, il carroponte deve arrivare in tempo all'inizio della "
     "successiva. E' il vincolo che rende difficile il problema: e' quello che "
     "il disegno a mano sbaglia sempre."),
    ("p",
     "Il giro e' CICLICO -- `order[(i + 1) % len(order)]` -- perche' dopo "
     "l'ultima mossa il carroponte torna alla prima, e quel trasferimento "
     "attraversa il confine fra un periodo e il successivo. E' proprio quello "
     "il piu' teso, perche' e' il ritorno da un capo all'altro della zona."),
    ("q",
     "IL TERMINE `+T`. Quando la mossa successiva e' quella di confine basso "
     "(k2 == z.lo), il prelievo avviene nel periodo DOPO: alla fase locale va "
     "aggiunto un T. Senza quel termine, il verificatore confronterebbe un "
     "arrivo a 95 s con un prelievo a 5 s e dichiarerebbe impossibile ogni "
     "ciclogramma corretto. E' una riga sola, e sbagliarla produce errori a "
     "raffica su soluzioni perfette."),
    ("p",
     "Il messaggio e' fra i piu' curati del modulo: nomina il carroponte, le "
     "due mosse, le due vasche per nome, e i due istanti che non tornano. Chi "
     "lo legge sa gia' dove guardare sul ciclogramma."),

    # ==================================================================
    ("h2", "9. La capienza delle vasche"),
    ("c", "verify._check_tank_capacity"),
    ("p",
     "Quanti pezzi stanno contemporaneamente in ciascuna vasca FISICA. La "
     "parola fisica e' la difficolta': la stessa vasca puo' comparire piu' "
     "volte nella ricetta -- un'immersione ripetuta, un risciacquo che torna "
     "-- e i posti sono gli stessi."),
    ("p",
     "Un pezzo occupa un posto da quando finisce l'immersione a quando finisce "
     "l'emersione, non solo per la durata del bagno: data.slot_occupancy_seconds "
     "aggiunge le fasi verticali. Un posto occupato dal telaio che sta ancora "
     "salendo non e' libero."),
    ("q",
     "PERCHE' NON SI SOMMANO I MASSIMI. Il docstring lo dice: se la stessa "
     "vasca compare in piu' tappe, gli intervalli delle diverse tappe possono "
     "essere SFASATI, e sommare i massimi di ciascuna darebbe un numero troppo "
     "alto -- una vasca dichiarata insufficiente quando invece basta. Si "
     "contano le sovrapposizioni vere."),
    ("p",
     "La distinzione fra errore e nota e' utile: sopra la capienza e' un "
     "errore; sotto la capienza ma con piu' di un pezzo e' una NOTA, perche' "
     "e' un fatto che l'utente deve sapere -- una vasca che lavora sempre con "
     "due pezzi ha meno margine di quanto sembri -- ma non un difetto. Il "
     "dettaglio riporta il conto tappa per tappa, cosi' il numero si puo' "
     "rifare a mano."),

    ("h3", "_max_sovrapposizioni"),
    ("c", "verify._max_sovrapposizioni"),
    ("p",
     "Il classico conteggio per attraversamenti: si mettono in fila le entrate "
     "e le uscite, si scorre tenendo un contatore, si registra il massimo. Con "
     "due complicazioni dovute alla periodicita'."),
    ("p",
     "La prima: gli intervalli si RIPETONO ogni T, e uno di essi puo' essere "
     "piu' lungo di un periodo -- un pezzo che resta in vasca piu' del takt "
     "time, che e' normalissimo. Si replicano quindi su abbastanza periodi da "
     "coprire per intero una finestra centrale, e si conta solo li', dove la "
     "copertura e' completa. Contare sui bordi darebbe numeri troppo bassi, "
     "perche' mancherebbero le repliche non generate."),
    ("p",
     "La seconda, nel `sort`: a parita' di istante si mettono prima le USCITE. "
     "Un posto liberato nello stesso istante in cui ne serve un altro puo' "
     "essere riusato, e l'ordine opposto conterebbe un posto in piu' -- "
     "facendo risultare insufficiente una vasca che basta esattamente."),
    ("p",
     "Il `max(1, ...)` finale copre il caso di una vasca attraversata senza "
     "mai sostare: zero sarebbe formalmente giusto e praticamente confondente."),
]


# ==========================================================================
# Documento 3 -- le collisioni
# ==========================================================================

COLLISIONI = [
    ("h1", "verify.py (3) -- le collisioni, e perche' il risultato e' garantito"),
    ("p",
     "Terzo dei tre documenti su verify.py. E' il controllo 8: la distanza fra "
     "ogni coppia di carroponti, in ogni istante. E' anche l'unico controllo "
     "del progetto in cui non basta guardare il codice per capire se e' "
     "giusto: serve un argomento."),

    # ==================================================================
    ("h2", "Il problema, prima del codice"),
    ("p",
     "Due carroponti sulla stessa rotaia non possono avvicinarsi oltre un "
     "minimo. La domanda da porre e': la distanza fra loro e' MAI scesa sotto "
     "quel minimo?"),
    ("p",
     "La distanza e' una funzione del tempo. Il modo ovvio di cercarne il "
     "minimo e' campionarla: si prendono mille istanti, si misura, si prende "
     "il piu' piccolo. E questo, preso da solo, non dimostra niente -- il "
     "minimo vero potrebbe cadere fra due campioni. Un verificatore che "
     "rispondesse cosi' darebbe un'illusione di rigore: sarebbe piu' onesto "
     "dire che non lo sa."),
    ("p",
     "Qui pero' si sa qualcosa in piu' sulla funzione, e da li' viene la "
     "garanzia. Fra due spigoli del profilo cinematico, la posizione di "
     "ciascun carroponte e' un polinomio di grado al piu' 2 in t. La "
     "differenza fra due polinomi di grado 2 e' ancora di grado 2. Su un "
     "intervallo in cui la funzione e' una parabola con curvatura limitata, "
     "l'errore che si commette prendendo il minimo dei campioni invece del "
     "minimo vero si puo' LIMITARE."),
    ("p",
     "Con passo dt, il campione piu' vicino al minimo vero dista al massimo "
     "dt/2 da esso, e su una parabola di curvatura a lo scarto e' al piu' "
     "1/2 * a * (dt/2)^2. Per la differenza di due traiettorie, la curvatura "
     "in gioco e' la somma delle due accelerazioni. Da cui:"),
    ("p", "        errore  <=  1/2 * (a_i + a_j) * (dt/2)^2"),
    ("p",
     "Il verificatore non dice quindi 'la separazione minima e' 3500 mm'. "
     "Dice: 'la separazione minima campionata e' 3500 mm, e quella vera non "
     "puo' essere piu' di X mm inferiore'. Con dt di un tick e le "
     "accelerazioni tipiche, X e' una frazione di millimetro."),
    ("q",
     "QUESTA E' LA RAGIONE PER CUI profile_breakpoints ESISTE. In "
     "kinematics.py c'e' una funzione che restituisce gli spigoli del profilo "
     "e che, letta li', sembra un dettaglio. E' invece il presupposto di "
     "tutto: l'argomento sopra vale solo DENTRO un tratto di parabola. "
     "Campionare a passo fisso senza includere gli spigoli lascerebbe scoperti "
     "proprio i punti in cui il grado 2 si spezza -- e sono quelli in cui il "
     "carroponte cambia comportamento, cioe' i piu' interessanti."),

    # ==================================================================
    ("h2", "1. _Trajectory -- una traiettoria valutabile ovunque"),
    ("c", "verify._Trajectory", None, "    def __init__"),
    ("p",
     "Il campionamento ha bisogno di chiedere 'dove sta il carroponte h "
     "all'istante t' per un t qualsiasi, anche fuori dal periodo. Questa "
     "classe lo permette, estendendo la traiettoria per periodicita'."),
    ("q",
     "IL WRAP NON E' MODULO T RISPETTO A ZERO. E' la trappola che il docstring "
     "denuncia. I segmenti di un carroponte non partono da t=0: partono da "
     "local_pick[zone.lo], che e' DIVERSO per ogni carroponte -- e' proprio lo "
     "sfasamento fra i giri che permette a due carroponti di non incontrarsi. "
     "Un wrap rispetto a 0 riporterebbe gli istanti in una finestra che per "
     "quel carroponte e' vuota, e position() cadrebbe sul segmento sbagliato. "
     "Il risultato sarebbe un verificatore che confronta le posizioni di due "
     "carroponti a istanti diversi: numeri plausibili e completamente privi di "
     "senso."),
    ("c", "verify._Trajectory.__init__"),
    ("p",
     "I segmenti vengono ordinati per istante di inizio e si memorizza "
     "l'elenco degli inizi: serve alla ricerca binaria di position(). t0 e' "
     "l'origine del carroponte, cioe' l'inizio del suo primo segmento."),
    ("c", "verify._Trajectory.position"),
    ("p",
     "Tre righe di sostanza. Il wrap riporta t nella finestra del carroponte; "
     "bisect trova il segmento attivo in tempo logaritmico -- serve, perche' "
     "questa funzione viene chiamata per ogni carroponte e per ogni istante "
     "campionato, che sono decine di migliaia di chiamate; poi si valuta il "
     "profilo cinematico dentro il segmento."),
    ("p",
     "Il commento sul clamp e' importante: position_profile stringe da sola il "
     "tempo nell'intervallo valido, e questo assorbe le micro sovrapposizioni "
     "fra segmenti lasciate dagli arrotondamenti. Senza, un istante che cade "
     "un microsecondo oltre la fine di un segmento darebbe una posizione "
     "leggermente ARRETRATA, e su una differenza fra due traiettorie quel "
     "rumore diventa un falso minimo."),
    ("c", "verify._Trajectory.breakpoints"),
    ("p",
     "Gli istanti notevoli in coordinate ASSOLUTE: gli estremi di ogni "
     "segmento, piu' gli spigoli del profilo cinematico interno a ciascun "
     "segmento traslante. Sono i punti che l'argomento del paragrafo "
     "precedente pretende siano campionati."),
    ("c", "verify._Trajectory.max_accel"),
    ("p",
     "L'accelerazione massima presente nella traiettoria: e' il termine a che "
     "entra nel limite d'errore. Si prende il MASSIMO e non una media perche' "
     "il limite deve valere sempre, anche nel tratto peggiore. Il `default=0.0` "
     "copre le traiettorie fatte di sole attese, dove non c'e' nessuna "
     "cinematica: li' l'errore di campionamento e' nullo, e giustamente."),

    # ==================================================================
    ("h2", "2. Dire DOVE, non solo quanto"),
    ("c", "verify._dove"),
    ("p",
     "Traduce una quota della rotaia in un riferimento riconoscibile "
     "sull'impianto. Il docstring spiega il perche': '11200 mm' non dice "
     "niente a chi legge, perche' il ciclogramma si ragiona per vasche."),
    ("p",
     "Se la quota e' entro 150 mm da una vasca si nomina quella; altrimenti si "
     "dice fra quali due si trova. La soglia di 150 mm e' generosa di "
     "proposito: un carroponte fermo su una vasca ci sta sopra esattamente, "
     "ma uno che ci passa vicino e' meglio descriverlo come 'sopra' quella "
     "vasca che come 'fra' quella e la successiva."),
    ("c", "verify._chi_e_dove"),
    ("p",
     "La frase che apre ogni rilievo di collisione. Il docstring difende la "
     "sua esistenza con un argomento pratico: senza, il referto direbbe solo "
     "che due carroponti sono troppo vicini -- vero e inservibile. Per "
     "rimediare bisogna sapere QUALI e in che punto della linea, altrimenti "
     "tocca ricostruirlo a mano dal grafico."),

    # ==================================================================
    ("h2", "3. _check_collisions"),

    ("h3", "Il caso banale"),
    ("c", "verify._check_collisions", None, "    # -- insieme dei campioni"),
    ("p",
     "Con un solo carroponte non ci sono coppie, e la funzione restituisce "
     "subito una separazione infinita. Il referto poi la traduce in 'n/d', "
     "come si e' visto nel primo documento."),

    ("h3", "L'insieme dei campioni"),
    ("c", "verify._check_collisions", "    # -- insieme dei campioni",
     "    # -- errore massimo"),
    ("p",
     "Qui si costruisce l'insieme degli istanti da provare, ed e' la parte su "
     "cui poggia la garanzia. Tre contributi: gli estremi 0 e T; TUTTI gli "
     "spigoli di TUTTE le traiettorie; una griglia uniforme di passo dt."),
    ("p",
     "Gli spigoli vengono aggiunti due volte, riportati in due modi diversi -- "
     "modulo T rispetto all'origine del carroponte, e modulo T rispetto a "
     "zero. Puo' sembrare ridondante ed e' invece necessario: uno spigolo "
     "riportato nella finestra del suo carroponte serve a quel carroponte, ma "
     "il confronto avviene fra COPPIE, e l'altro carroponte ha un'origine "
     "diversa. Aggiungendoli in entrambe le forme, ogni spigolo di ciascuno "
     "viene provato in un istante in cui entrambi sono valutati correttamente."),
    ("p",
     "Si usa un insieme, quindi i duplicati -- che sono molti, perche' gli "
     "estremi dei segmenti coincidono a due a due -- spariscono da soli."),

    ("h3", "Il limite d'errore"),
    ("c", "verify._check_collisions", "    # -- errore massimo",
     "    # -- posizioni di tutti"),
    ("p",
     "Tre righe che valgono tutto l'argomento del primo paragrafo. Si "
     "prendono le DUE accelerazioni piu' grandi fra tutte le traiettorie, non "
     "quelle della coppia peggiore: e' una maggiorazione, cioe' un limite che "
     "vale per qualunque coppia. Un limite valido per tutti e' quello che "
     "serve, perche' viene poi riportato nel referto come garanzia unica."),
    ("q",
     "accels[1] ESISTE SEMPRE? Si', ma solo grazie al controllo n < 2 fatto "
     "poche righe sopra, che esce prima. Se un giorno quel controllo venisse "
     "spostato o allentato, questa riga darebbe IndexError su una linea con un "
     "solo carroponte -- il caso piu' comune di tutti."),

    ("h3", "Il campionamento vero e proprio"),
    ("c", "verify._check_collisions", "    # -- posizioni di tutti",
     "    for (i, j), (sep, t, xi, xj) in worst.items():"),
    ("p",
     "Prima si valutano TUTTE le posizioni di TUTTI i carroponti a TUTTI gli "
     "istanti, in una matrice. Poi si scorrono le coppie. L'ordine e' voluto: "
     "valutando dentro il doppio ciclo sulle coppie, ogni traiettoria verrebbe "
     "ricalcolata una volta per ciascun partner, e position() e' la funzione "
     "piu' costosa del giro."),
    ("p",
     "Di ogni coppia si tiene solo il caso PEGGIORE, con l'istante e le due "
     "posizioni. Il commento spiega perche': riportare ogni istante sotto "
     "soglia sommergerebbe il referto con migliaia di righe quasi identiche, "
     "che descrivono un unico avvicinamento visto fotogramma per fotogramma."),

    ("h3", "I tre livelli di segnalazione"),
    ("c", "verify._check_collisions", "    for (i, j), (sep, t, xi, xj) in worst.items():",
     "    return dict("),
    ("p",
     "La stessa misura produce tre esiti diversi, e la soglia di ciascuno e' "
     "scelta con cura."),
    ("li", "sotto il minimo di PIU' del limite d'errore piu' la tolleranza: "
           "e' un ERRORE. La distanza e' cosi' bassa che nessuna incertezza di "
           "calcolo puo' spiegarla."),
    ("li", "sotto il minimo ma DENTRO quel margine: e' un AVVISO, e il "
           "messaggio dichiara la tolleranza di calcolo. Qui il verificatore "
           "sta ammettendo di non poter distinguere -- ed e' il "
           "comportamento onesto: segnalare come errore un caso al limite del "
           "proprio potere risolutivo abituerebbe a ignorare gli errori."),
    ("li", "sopra il minimo ma per meno di warn_margin: e' un avviso di "
           "FRAGILITA', spento per impostazione predefinita."),
    ("p",
     "Il messaggio d'errore scompone il minimo richiesto nei suoi tre "
     "addendi -- ingombro negativo, ingombro positivo, distanza di sicurezza "
     "-- perche' quello e' il punto in cui l'utente deve decidere: allargare "
     "la sicurezza o rivedere la geometria del carroponte sono due azioni "
     "diverse, e il numero unico non permette di scegliere."),
]


DOCUMENTI = [
    ("verify_1_referto_e_giro.docx", REFERTO),
    ("verify_2_controlli.docx", CONTROLLI),
    ("verify_3_collisioni.docx", COLLISIONI),
]
