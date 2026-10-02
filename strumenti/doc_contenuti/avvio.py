"""
Il testo dei documenti di avvio.py.

Sedici fra funzioni e dataclass, e una domanda sola: in quali istanti del ciclo
si puo' accendere l'impianto. Il modulo e' piccolo, ma quasi tutto il suo
codice risponde a una delle tre difficolta' che la domanda nasconde -- che un
ciclogramma e' periodico e quindi la distanza fra due istanti e' circolare, che
un istante buono spesso non esiste e bisogna comunque darne uno, e che quando
esiste non e' uno solo.
"""

from __future__ import annotations

# --------------------------------------------------------------------------

RIGA_PER_RIGA = [
    ("h1", "avvio.py spiegato riga per riga"),
    ("p",
     "Questo documento accompagna la lettura di avvio.py, il modulo che "
     "individua il PUNTO DI AVVIO di un ciclogramma. Ogni blocco di codice e' "
     "estratto dal sorgente al momento della generazione."),
    ("p",
     "Il modulo non calcola niente di nuovo e non decide niente sul "
     "ciclogramma: legge i Segment che ci sono gia' -- gli stessi che "
     "disegnano il grafico e che muovono la simulazione -- e ne ricava un "
     "istante e una posizione per carroponte."),

    # ==================================================================
    ("h2", "Il problema: un ciclogramma non ha un inizio"),
    ("p",
     "Un ciclogramma e' periodico. L'origine dell'asse dei tempi, quella da cui "
     "il programma lo scrive, e' il prelievo della prima mossa del primo "
     "carroponte: e' una convenzione comoda per il calcolo e non vuol dire "
     "niente per chi deve far partire l'impianto."),
    ("p",
     "Chi lo avvia ha invece bisogno di UNO istante preciso, perche' in quello "
     "istante i carroponti vanno portati a mano nella posizione da cui il ciclo "
     "riparte -- e quella posizione dev'essere una in cui si possano lasciare. "
     "Da qui le tre condizioni, che sono scritte nell'intestazione del modulo e "
     "che tutto il resto del file non fa che applicare:"),
    ("li",
     "FERMI: nessuna traslazione in corso lungo la rotaia, e nessuna corsa del "
     "gancio."),
    ("li",
     "IN POSIZIONE BASSA: il gancio in fondo alla corsa della vasca su cui "
     "stanno, cioe' dove lo lascia un rilascio e dove lo trova una presa. E' la "
     "quota in cui il carroponte non scavalca niente e non tiene niente "
     "sospeso."),
    ("li",
     "NE' AL CARICO NE' ALLO SCARICO: le due stazioni agli estremi sono quelle "
     "presidiate, dove il pezzo viene appeso e staccato. Lasciarci fermo un "
     "carroponte vuol dire tenere occupato il posto dell'operatore."),
    ("q",
     "NON SEMPRE UN ISTANTE COSI' ESISTE. Basta un carroponte che nel suo giro "
     "non stia mai fermo in basso nello stesso momento degli altri. Il modulo "
     "allora non rinuncia -- un punto di avvio serve comunque -- e prende il "
     "MENO SBAGLIATO: quello in cui la somma di quanto manca a ciascun "
     "carroponte, in secondi, e' minima. E' la stessa scelta di fondo di "
     "manuale.py: descrivere l'imperfezione invece di rifiutarsi di "
     "rispondere."),

    # ==================================================================
    ("h2", "1. Le tre dataclass"),

    ("h3", "Riposo -- una finestra in cui il carroponte si puo' lasciare"),
    ("c", "avvio.Riposo"),
    ("p",
     "Un intervallo di tempo, la posizione lungo la rotaia e la tappa del "
     "percorso su cui il carroponte e' fermo. I due istanti sono nella scala "
     "del ciclo del carroponte, la stessa dei Segment: possono essere negativi "
     "o superare il takt time, e vanno letti modulo T. Non si normalizzano qui "
     "perche' la normalizzazione e' una faccenda della ricerca, non della "
     "lettura dei segmenti."),

    ("h3", "PosizioneAvvio -- dove sta un carroponte all'istante scelto"),
    ("c", "avvio.PosizioneAvvio"),
    ("p",
     "Il campo che conta e' `errore`: quanto manca, in secondi, perche' quel "
     "carroponte sia a riposo. Zero vuol dire che ci e' gia'. E' una distanza "
     "nel tempo, avanti o indietro, dalla finestra di riposo piu' vicina, e si "
     "legge come 'tanto percorso bisogna fargli fare a mano prima di dare il "
     "via'."),
    ("p",
     "`mai` e' il caso a parte: il carroponte non ha NESSUNA finestra di riposo "
     "in tutto il giro. Il suo errore allora non entra nel confronto fra "
     "istanti -- sarebbe lo stesso per tutti e non cambierebbe quale vince -- e "
     "viene segnalato a parte."),

    ("h3", "Avvio -- il risultato"),
    ("c", "avvio.Avvio"),
    ("p",
     "L'istante, dentro [0, T), e lo stato di ogni carroponte. L'errore totale "
     "e' una proprieta' calcolata e non un campo: e' la somma di quelli dei "
     "singoli, e tenerlo come dato indipendente vorrebbe dire poterlo avere "
     "diverso dai suoi addendi."),

    # ==================================================================
    ("h2", "2. Le finestre di riposo"),

    ("h3", "stazione_di_riposo -- dove un carroponte si puo' lasciare"),
    ("c", "avvio.stazione_di_riposo"),
    ("q",
     "CARICO E SCARICO SI ESCLUDONO PER POSIZIONE, NON PER INDICE. Se la "
     "ricetta ripassa dalla vasca di carico a meta' percorso, quella resta "
     "comunque la vasca presidiata, e un carroponte fermo li' da' lo stesso "
     "fastidio. Confrontare gli indici di tappa -- 0 e n-1 -- avrebbe "
     "ammesso proprio quel caso."),
    ("p",
     "La funzione restituisce None anche quando in quella posizione non c'e' "
     "nessuna tappa: il carroponte e' per strada, o su uno svincolo. Le "
     "posizioni vengono dalle vasche e non da un conto, quindi o coincidono o "
     "sono lontane metri: la tolleranza di un millesimo di millimetro serve "
     "solo a non inciampare nella virgola mobile."),
    ("p",
     "C'e' una conseguenza che fa risparmiare un ramo intero: le ZONE DI CAMBIO "
     "QUOTA esistono soltanto alla prima e all'ultima tappa, che qui sono "
     "escluse. Dentro questo modulo non si incontrano mai, e `approach_position` "
     "coincide sempre con `station_position`."),

    ("h3", "_coda_ferma_in_basso -- l'aggancio e lo sgancio"),
    ("c", "avvio._coda_ferma_in_basso"),
    ("p",
     "Agli estremi di una presa e di un rilascio ci sono due fasi in cui il "
     "gancio e' gia' (o e' ancora) in fondo corsa e non si muove: l'AGGANCIO in "
     "testa alla presa e lo SGANCIO in coda al rilascio. Il telaio sta "
     "appoggiato in vasca, il carroponte e' fermo: e' riposo a tutti gli "
     "effetti, ed e' anzi il momento in cui e' piu' fermo di tutto il giro."),
    ("q",
     "NON E' UN DETTAGLIO. In un giro INCATENATO -- un carroponte che passa da "
     "una consegna alla presa successiva senza mai aspettare, che e' il caso "
     "normale di una linea densa -- non c'e' nessun tratto 'wait', e aggancio e "
     "sgancio sono L'UNICO riposo che esiste. Senza di loro un ciclogramma fitto "
     "non avrebbe nessun punto di avvio."),
    ("p",
     "Le fasi si guardano una per una, dalla testa o dalla coda secondo il "
     "verso, e si smette alla prima che non va: una fase che alza il gancio, che "
     "trasla, o che lo tiene a una quota diversa dal fondo chiude la finestra. "
     "Il fondo si prende da `corsa_verticale` della stazione, non da una "
     "costante: ogni vasca ha la sua."),

    ("h3", "finestre_di_riposo -- la lettura dei segmenti"),
    ("c", "avvio.finestre_di_riposo"),
    ("p",
     "Le finestre sono di due tipi, che poi si saldano fra loro: le ATTESE "
     "('wait'), che sono per definizione il carroponte fermo sopra una vasca, e "
     "le code ferme di presa e rilascio appena viste."),
    ("p",
     "Che durante un'attesa il gancio sia in fondo non e' un'ipotesi: e' dove lo "
     "lascia il rilascio che precede l'attesa, ed e' dove lo prende la presa che "
     "la segue. Lungo un rientro a gancio basso non risale mai, e dove risale -- "
     "sugli svincoli -- il carroponte non e' fermo sopra una vasca ma sopra lo "
     "svincolo, che non e' una tappa e quindi non produce nessuna finestra."),
    ("p",
     "I tempi della presa e del rilascio si ricavano dal tratto A CARICO: la "
     "presa comincia `pick_time_at` secondi prima, il rilascio finisce "
     "`release_time_at` secondi dopo. E' lo stesso conto che fanno il disegno "
     "(plotting.eventi_del_trasporto) e la simulazione, e per la stessa ragione: "
     "il tratto a carico c'e' sempre ed e' uno solo per mossa, mentre presa e "
     "rilascio possono essere spezzati in piu' tratti."),
    ("p",
     "In fondo le finestre adiacenti si fondono. Un rilascio che finisce, lo "
     "sgancio, e l'attesa che segue sono un unico tratto di tempo in cui il "
     "carroponte sta fermo: spezzarlo in tre non vorrebbe dire niente, e "
     "soprattutto farebbe scegliere il punto di mezzo del pezzo sbagliato."),

    # ==================================================================
    ("h2", "3. Leggere la traiettoria"),

    ("h3", "posizione_a -- dove sta il carroponte a un istante qualunque"),
    ("c", "avvio.posizione_a"),
    ("p",
     "Serve a dire DOVE va portato ciascun carroponte all'istante di avvio, "
     "anche quando quell'istante non e' per lui una finestra di riposo -- cioe' "
     "proprio nel caso approssimato, che e' quello in cui la domanda e' piu' "
     "interessante."),
    ("p",
     "Il `(t - t0) % T` riporta l'istante dentro il ciclo DEL CARROPONTE, che "
     "non comincia a zero: ogni carroponte ha il suo t0, ed e' quello del primo "
     "dei suoi segmenti."),
    ("q",
     "IL PROFILO E' QUELLO VERO. Dentro un tratto in movimento la posizione si "
     "calcola con `position_profile` -- accelerazione, crociera, frenata -- e "
     "non interpolando fra i due estremi. Un'interpolazione lineare darebbe una "
     "posizione che il carroponte in quell'istante non ha, e il numero scritto "
     "nel Riepilogo e' un numero con cui qualcuno va davanti all'impianto."),
    ("p",
     "L'ultima riga e' una rete: fra due segmenti non ci sono buchi, ma se un "
     "arrotondamento ne aprisse uno largo un millisecondo e' meglio dare la "
     "posizione del segmento piu' vicino che far saltare il conto."),

    ("h3", "vasca_a -- il nome da scrivere"),
    ("c", "avvio.vasca_a"),
    ("p",
     "Si guardano sia il punto di approccio sia la vasca: di norma sono lo "
     "stesso posto, e differiscono solo al carico e allo scarico serviti da una "
     "zona di cambio quota, dove il carroponte parcheggia fuori dal campo delle "
     "vasche ma durante la presa ci entra. Qui, a differenza di "
     "`stazione_di_riposo`, non si esclude niente: non si sta decidendo dove si "
     "puo' sostare, si sta scrivendo dove il carro si trova."),

    # ==================================================================
    ("h2", "4. La circolarita', e perche' costa tre funzioni"),
    ("p",
     "Il ciclo si richiude: un carroponte a riposo tre secondi dopo la fine del "
     "periodo lo e' anche tre secondi dopo l'istante zero. Tutte le distanze "
     "sono quindi circolari, e le tre funzioni che seguono esistono per questo."),

    ("h3", "_nel_periodo -- le finestre dentro un periodo"),
    ("c", "avvio._nel_periodo"),
    ("q",
     "UN `b` OLTRE T NON E' UN ERRORE: e' una finestra A CAVALLO DELL'ORIGINE, "
     "e ce n'e' quasi sempre una. Il giro di un carroponte comincia con la presa "
     "della sua prima mossa, cioe' con l'AGGANCIO -- che e' riposo -- e finisce "
     "con l'attesa che la precede: le due si toccano. Spezzarle in due pezzi "
     "agli estremi del periodo le farebbe sembrare due finestre corte dove ce "
     "n'e' una lunga, e il punto di mezzo (sezione 5) cadrebbe nel posto "
     "sbagliato."),
    ("p",
     "Le finestre si fondono prima nel senso lineare, poi si guarda se l'ultima "
     "rientra dentro la prima: in quel caso sono la stessa finestra vista da "
     "due parti. Il `min(b, a + T)` alla fine impedisce che una finestra lunga "
     "piu' di un periodo si avvolga su se stessa."),

    ("h3", "_distanza -- quanto manca"),
    ("c", "avvio._distanza"),
    ("p",
     "Tre righe, e tutte e tre circolari. `(t - a) % T <= b - a` dice se t cade "
     "dentro la finestra: e' l'unico modo di scriverlo che funziona anche con "
     "una finestra a cavallo dell'origine, dove `a <= t <= b` sarebbe falso per "
     "meta' della finestra."),
    ("p",
     "Fuori, la distanza e' la piu' corta fra l'andare avanti fino all'inizio "
     "della finestra e il tornare indietro fino alla sua fine: `(a - t) % T` e "
     "`(t - b) % T`."),

    ("h3", "_estensione -- il margine"),
    ("c", "avvio._estensione"),
    ("p",
     "Di quanto si puo' arretrare e di quanto si puo' avanzare partendo da t "
     "senza uscire dalla finestra che lo contiene. E' il MARGINE del carroponte "
     "su quell'istante, e serve a scegliere, fra tutti gli istanti buoni, quello "
     "che ne lascia il piu' possibile da entrambe le parti."),

    # ==================================================================
    ("h2", "5. La ricerca degli istanti"),

    ("h3", "trova_avvii -- i candidati"),
    ("c", "avvio.trova_avvii", None, "    errori = ["),
    ("p",
     "Si saltano le zone senza nessun segmento: in un ciclogramma composto a "
     "meta' una zona puo' non avere ancora nessuna mossa assegnata, e non e' di "
     "nessun carroponte."),
    ("p",
     "I candidati sono gli SPIGOLI della somma degli errori, cioe' gli istanti "
     "in cui una delle distanze cambia pendenza. Fra due spigoli consecutivi "
     "ogni distanza e' lineare in t, quindi la somma lo e' anche lei: li' dentro "
     "non puo' succedere niente che non si veda dagli estremi. L'istante zero si "
     "aggiunge comunque, perche' serve nel caso limite in cui un carroponte sia a "
     "riposo per tutto il periodo e non abbia nessun estremo da offrire."),
    ("q",
     "GLI SPIGOLI SONO DI DUE SPECIE, E LA SECONDA E' COSTATA UN BUG. Per "
     "trovare il MINIMO bastano gli ESTREMI delle finestre: nel mezzo di un buco "
     "ci sta il massimo, non il minimo. Ma per sapere QUANTI tratti distinti "
     "arrivano al minimo servono anche i COLMI DEI BUCHI, a meta' fra la fine di "
     "una finestra e l'inizio della successiva: li' la distanza smette di "
     "crescere e comincia a calare, ed e' l'unico posto in cui l'errore puo' "
     "RISALIRE fra due candidati che stanno tutti e due al minimo. Senza, due "
     "tratti buoni separati da un buco stretto si fondevano in uno, e il "
     "pulsante dell'interfaccia mostrava un istante dove ce n'erano due. "
     "Aggiungerli non puo' spostare il minimo: nel colmo la pendenza della somma "
     "cala di due, e un minimo stretto vorrebbe che salisse."),

    ("h3", "trova_avvii -- i tratti e gli istanti"),
    ("c", "avvio.trova_avvii", "    errori = [", "    fuori = []"),
    ("p",
     "Un TRATTO e' una sequenza di candidati consecutivi che stanno tutti al "
     "minimo. Che fra due di loro l'errore ci resti non si controlla: fra due "
     "candidati la somma e' lineare, e una funzione lineare che vale lo stesso "
     "ai due estremi e' costante. E' il motivo per cui i colmi dei buchi devono "
     "essere candidati: senza, quel ragionamento sarebbe falso."),
    ("p",
     "L'ultima riga chiude il giro: fra l'ultimo candidato e il primo -- che e' "
     "lo zero -- non ci sono spigoli, quindi anche li' l'errore e' lineare. Se "
     "stanno al minimo tutti e due, il tratto che finisce in fondo al periodo e "
     "quello che comincia da capo sono lo stesso tratto visto da due parti, e "
     "contarli due volte vorrebbe dire mostrare due volte lo stesso istante."),
    ("p",
     "Di ogni tratto esce UN istante. Se l'errore e' zero e' il PUNTO DI MEZZO: "
     "il primo estremo e' l'istante in cui l'ultimo carroponte si e' appena "
     "fermato, e avviare esattamente li' vuol dire non avere nessun margine ne' "
     "prima ne' dopo. Lo spostamento `(avanti - dietro) / 2` e' sempre dentro "
     "il margine di tutti, perche' i due termini sono gia' i minimi su tutti i "
     "carroponti. Se invece l'errore non e' zero si tiene il PRIMO, che e' la "
     "regola dichiarata: a pari errore, il primo istante."),
    ("p",
     "I carroponti senza nessuna finestra restano fuori dal confronto e vengono "
     "segnalati con `mai`: nessun istante li accontenterebbe, e farli pesare "
     "sull'errore aggiungerebbe la stessa costante a ogni candidato senza "
     "cambiare quale vince."),
    ("q",
     "PERCHE' TUTTI E NON UNO SOLO. All'errore minimo ci arriva quasi sempre "
     "piu' di un tratto del ciclo, e sono tratti lontani fra loro: sulla linea "
     "d'esempio sono CINQUE, uno per ogni coppia di vasche in cui i due "
     "carroponti si trovano fermi insieme. Sono equivalenti, e sceglierne uno "
     "sarebbe una decisione che questo modulo non ha gli elementi per prendere: "
     "quale convenga davvero dipende dall'impianto -- da dove si entra, dove si "
     "vuole il pezzo quando si riparte. Si restituiscono tutti, e nella finestra "
     "si scorrono col pulsante 'Avvio'."),

    ("h3", "trova_avvio -- il primo"),
    ("c", "avvio.trova_avvio"),
    ("p",
     "Tre righe sopra `trova_avvii`. E' quello che si scrive quando non c'e' "
     "nessuno a scegliere: il foglio Riepilogo, il PNG da riga di comando. "
     "L'interfaccia invece passa a `plot_cyclogram` e a `scrivi_risultati` "
     "l'istante che l'utente sta guardando -- il file e l'immagine che escono "
     "insieme devono dire quello che ha davanti, non un altro."),

    # ==================================================================
    ("h2", "6. Lo stesso risultato in quattro posti"),

    ("h3", "righe_di_riepilogo"),
    ("c", "avvio.righe_di_riepilogo"),
    ("q",
     "UNA DEFINIZIONE SOLA PER QUATTRO LETTORI. Il punto di avvio si scrive sul "
     "grafico (la linea nera di plot_cyclogram), nel foglio Riepilogo, nel "
     "pannello della finestra e sul terminale di ciclogramma.py. Se due di "
     "questi lo dicessero con parole diverse, chi li confronta si chiederebbe "
     "quale dei due ha ragione."),
    ("p",
     "Le tre colonne -- etichetta, valore, nota -- sono quelle del Riepilogo "
     "dell'Excel, dove si passano tali e quali a `voce`; a schermo e sul "
     "terminale si scrivono una dietro l'altra. E' la forma piu' stretta delle "
     "due, e adattarla all'altra costa una riga."),
    ("p",
     "`carri` traduce l'indice di ZONA nel numero di CARROPONTE da mostrare, "
     "come nella simulazione: in un ciclogramma composto a meta' le zone vengono "
     "riempite per continuita' e i due numeri divergono."),
    ("p",
     "Il caso `avvio is None` non salta la riga, la scrive dicendo che non e' "
     "calcolabile. Una sezione che sparisce senza spiegazione fa pensare a una "
     "dimenticanza del programma."),
]

DOCUMENTI = [
    ("avvio_riga_per_riga.docx", RIGA_PER_RIGA),
]
