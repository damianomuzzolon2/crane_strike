"""
Il testo dei documenti di simulazione.py.

Sessantasette fra funzioni e metodi, in tre documenti che seguono la divisione
del modulo: cosa c'e' da sapere, chi lo sa dire, chi lo disegna.
"""

from __future__ import annotations

# ==========================================================================
# Documento 1 -- il modello di cio' che si vede
# ==========================================================================

MODELLO = [
    ("h1", "simulazione.py (1) -- il modello di cio' che si vede"),
    ("p",
     "Primo dei tre documenti su simulazione.py. Qui ci sono le strutture e le "
     "funzioni che traducono un ciclogramma in 'dove sta ogni cosa': le fasi "
     "di un pezzo, le quote del gancio scarico, i profili. Nessuna di queste "
     "importa tkinter."),

    # ==================================================================
    ("h2", "A cosa serve una simulazione, se il ciclogramma dice gia' tutto"),
    ("p",
     "Il ciclogramma e' un diagramma tempo-posizione: dice tutto, ma bisogna "
     "saperlo leggere, e un errore di composizione ci si nasconde bene. Due "
     "linee che si sfiorano su un grafico non gridano niente."),
    ("p",
     "Guardando invece la linea come la si guarderebbe dal capannone, un "
     "carroponte che passa attraverso un altro, o un pezzo che resta appeso "
     "mentre nessuno lo tiene, si vede senza doverlo cercare. E' lo stesso "
     "ciclogramma letto in un altro modo."),
    ("q",
     "NON CALCOLA NIENTE DI NUOVO. E' la regola del modulo, scritta "
     "nell'intestazione: tutto quello che mostra viene da "
     "segments_per_hoist (i carroponti) e da actual_time (i pezzi), cioe' "
     "esattamente gli oggetti che disegnano il ciclogramma. Se i due disegni "
     "dicessero cose diverse, sarebbe un guasto. E' anche la proprieta' che "
     "test_simulazione.py verifica in modo incrociato: ogni pezzo appeso deve "
     "stare ESATTAMENTE dove sta il gancio di un carroponte che lo tiene."),

    ("h3", "I colori"),
    ("c", "simulazione", "_SFONDO = ", "# --------"),
    ("p",
     "I carroponti hanno lo stesso colore del ciclogramma (_HOIST_COLORS "
     "importato da plotting): i due disegni si guardano uno accanto all'altro, "
     "e il carroponte 1 deve essere rosso in tutti e due."),
    ("q",
     "IL BAGNO E' UGUALE IN TUTTE LE VASCHE. Il commento racconta "
     "l'esperimento e perche' e' stato scartato: una tinta diversa per vasca "
     "distingue bene, ma sembra dire qualcosa sulla CHIMICA -- che il "
     "programma non conosce -- e riempie di colore un disegno in cui i colori "
     "devono voler dire una cosa sola, di quale carroponte si tratta. E' la "
     "stessa disciplina di plotting.py, dove l'arcobaleno per tipo di tratto "
     "e' stato tolto."),

    # ==================================================================
    ("h2", "1. Le strutture"),
    ("c", "simulazione.StatoCarro"),
    ("c", "simulazione.StatoPezzo"),
    ("c", "simulazione.Istantanea"),
    ("p",
     "Tre dataclass immutabili che descrivono un istante. Due campi meritano "
     "attenzione perche' non sono ovvi."),
    ("p",
     "`corsia` dice su quale POSTO della vasca si sta lavorando. Serve alle "
     "vasche che tengono dentro piu' pezzi insieme: senza, i pezzi si "
     "disegnerebbero tutti nello stesso punto e sembrerebbero uno solo -- "
     "proprio nelle vasche lente, che sono quelle per cui i posti in piu' si "
     "comprano."),
    ("q",
     "`corsa` NON E' RIDONDANTE. E' la corsa verticale a cui la quota `z` si "
     "riferisce, e il commento spiega perche' viaggia insieme alla quota: il "
     "disegno non mostra i millimetri ma il PUNTO a cui e' arrivata la "
     "discesa. Senza, bisognerebbe risalire alla vasca dal nome -- e mentre il "
     "carroponte trasla a gancio basso non e' sopra nessuna vasca."),
    ("p",
     "L'`indice` di StatoPezzo e' il numero d'ordine con cui il pezzo e' "
     "entrato in linea: lo 0 e' quello entrato all'istante zero, quelli prima "
     "hanno indice negativo. Il docstring precisa che serve a distinguerli, "
     "non a fare gerarchie: fanno tutti lo stesso percorso, sfasati di un takt "
     "time."),
    ("c", "simulazione._Fase"),
    ("p",
     "Un tratto della vita di un pezzo. Ha DUE profili, uno orizzontale e uno "
     "verticale, perche' un pezzo appeso durante una presa con cambio quota si "
     "muove in tutte e due le direzioni insieme."),
    ("p",
     "st_da e st_a coincidono in tutte le fasi tranne la traslazione, e "
     "servono a sapere di quale vasca e' il posto occupato -- cioe' a "
     "interpolare la corsia mentre il pezzo passa da una vasca all'altra."),
    ("c", "simulazione._Traiettoria"),
    ("p",
     "Il giro di un carroponte, precalcolato per essere interrogabile a "
     "qualunque istante. Sei dei suoi otto campi sono indici o cumulati, e "
     "ciascuno esiste per rispondere in fretta a una domanda diversa."),
    ("li", "`inizi` -- i t_start, per la ricerca binaria del tratto attivo;"),
    ("li", "`t0` -- da dove parte il ciclo di QUESTO carroponte, che non e' "
           "zero e non e' lo stesso per tutti;"),
    ("li", "`inizi_mossa` -- quando comincia ogni mossa, per risalire a quale "
           "pezzo si sta servendo;"),
    ("li", "`impegni` -- gli intervalli in cui il telaio e' appeso al gancio;"),
    ("li", "`mobile_t`/`mobile_c` -- il tempo passato muovendosi, cumulato;"),
    ("li", "`quote` -- le frazioni di discesa dei tratti a gancio scarico."),
    ("q",
     "GLI IMPEGNI SONO LA REGOLA DEL CARRELLO. Il commento lo dice: solo "
     "durante un impegno il carroponte DEVE stare sul posto del pezzo -- "
     "altrimenti il telaio si staccherebbe dal bilancino -- e fuori e' libero "
     "di spostarsi di lato, e lo fa con calma invece di scattare. E' la "
     "distinzione che ha risolto lo scatto laterale, ed e' argomento del "
     "secondo documento."),

    # ==================================================================
    ("h2", "2. _quote_a_vuoto -- la quota del gancio scarico"),
    ("c", "simulazione._quote_a_vuoto"),
    ("p",
     "E' la funzione piu' lunga e piu' sottile del modulo, e risolve un "
     "problema che il modello non pone: dove sta il gancio quando non ha "
     "niente in mano."),
    ("p",
     "Il modello non ne ha bisogno. Le corse verticali a vuoto o hanno un "
     "tempo dedicato -- i tratti `lift_empty`, e allora la quota la dice il "
     "modello -- oppure non esistono affatto, perche' il gancio trasla basso e "
     "non sale mai. Ma nel secondo caso due stazioni con corse DIVERSE vogliono "
     "il gancio a quote diverse, e quel dislivello va messo da qualche parte."),
    ("q",
     "LA REGOLA: MENTRE IL CARROPONTE TRASLA, LA QUOTA NON CAMBIA. Il "
     "docstring la enuncia in maiuscolo e ne da' la ragione, che e' di "
     "coerenza fra le due viste: nel ciclogramma un tratto obliquo e' uno "
     "spostamento e un tratto piatto e' tutto il resto. Una discesa disegnata "
     "in mezzo a una traslazione fa dire alle due viste due cose diverse, e "
     "chi le confronta non ci si ritrova. E' una richiesta arrivata guardando "
     "la simulazione accanto al grafico e non riconoscendoci la stessa linea."),
    ("p",
     "La funzione lavora in due tempi. Prima fissa le quote dei tratti che le "
     "hanno per costruzione -- trasporto, presa, rilascio, e i tre tipi di "
     "tratta a vuoto -- poi ne deduce quelle di attese e corse verticali "
     "guardando i vicini."),
    ("p",
     "Il riconoscimento delle tratte a vuoto e' per ESCLUSIONE, e il commento "
     "lo spiega: un rientro che deve passare alto e' spezzato in tre "
     "traslazioni, e gli svincoli non sono posizioni di stazione. Chi non "
     "parte ne' arriva da una stazione e' la tratta alta; chi parte da una "
     "stazione e non arriva da nessuna parte sta uscendo verso lo svincolo, e "
     "viceversa."),
    ("q",
     "IL DISLIVELLO VA IN UNA SOSTA, SE C'E'. Quando due stazioni vogliono il "
     "gancio a quote diverse, il codice preferisce mettere la rampa in "
     "un'attesa adiacente invece che nella traslazione. Il commento ne da' la "
     "ragione visiva: nel ciclogramma una sosta e' un tratto piatto, e quindi "
     "e' li' che l'occhio si aspetta un movimento verticale. Solo se non c'e' "
     "nessuna sosta a fianco non resta che farlo durante la traslazione."),
    ("p",
     "`vicino` gira in tondo perche' il giro si richiude: l'attesa dell'ultimo "
     "tratto ha come vicino il primo."),
    ("q",
     "LE CORSE VERTICALI NON DEDUCONO IL VERSO. Il commento sopra il ciclo dei "
     "`lift_empty` e' esplicito: la quota va da quella del tratto prima a "
     "quella del tratto dopo, e non serve sapere se sale o se scende -- lo "
     "dicono i due vicini. Dedurlo da una macchina a stati sui tipi di tratto "
     "'e' proprio l'errore che sbagliava tutto sulle postazioni senza corsa', "
     "dove 'calato' e 'in alto' sono la stessa quota."),

    # ==================================================================
    ("h2", "3. Le altre funzioni di supporto"),
    ("c", "simulazione._cumulato_mobile"),
    ("p",
     "Il tempo passato MUOVENDOSI, cumulato lungo il giro. Un'attesa non lo fa "
     "crescere, tutto il resto si'."),
    ("p",
     "Il docstring dice a cosa serve e -- soprattutto -- perche' non basta il "
     "tempo normale: distribuire lo spostamento laterale del carrello su tutto "
     "l'intervallo libero lo fa 'scorrere di fianco per un minuto mentre e' "
     "fermo sopra una vasca', e la sosta e' proprio quando non dovrebbe "
     "muoversi affatto."),
    ("c", "simulazione._fino_al_carico"),
    ("c", "simulazione._finche_c_e_il_carico"),
    ("p",
     "Due funzioni speculari che dicono quando il telaio arriva sul gancio e "
     "quando lo lascia, leggendo il campo `loaded` delle fasi. Insieme "
     "delimitano gli IMPEGNI."),
    ("p",
     "Il `break` sta in posizioni diverse per la stessa ragione che vale in "
     "plotting.py: la prima cerca l'INIZIO della prima fase carica, la seconda "
     "la FINE dell'ultima. Due cicli quasi identici che dicono cose diverse."),
    ("c", "simulazione._valuta"),
    ("p",
     "Il valore di una grandezza che va da v0 a v1 fra due istanti. Senza "
     "cinematica interpola linearmente; con la cinematica usa il profilo vero."),
    ("q",
     "PERCHE' IL PROFILO VERO ANCHE QUI. Il docstring: 'un carroponte che "
     "parte e si ferma di scatto si vede subito, e non e' quello che il "
     "calcolo ha previsto'. E' lo stesso argomento di _sample_segment in "
     "plotting.py -- la simulazione deve essere credibile, altrimenti chi la "
     "guarda smette di fidarsi anche quando ha ragione."),

    # ==================================================================
    ("h2", "4. _fasi_pezzo -- la vita di un pezzo"),
    ("c", "simulazione._fasi_pezzo"),
    ("p",
     "Trasforma la catena dei tempi nella sequenza di fasi di UN pezzo, dal "
     "primo prelievo all'ultima immersione. Gli altri pezzi sono la stessa "
     "sequenza traslata di un multiplo del takt time."),
    ("q",
     "IL PEZZO NON SEGUE IL GANCIO DAPPERTUTTO. E' la frase che apre il "
     "docstring, ed e' la sola difficolta' della funzione. Mentre il gancio "
     "scende vuoto a prenderlo, o risale vuoto dopo averlo sganciato, il pezzo "
     "sta FERMO in fondo alla vasca. E' quello che distingue le fasi `loaded` "
     "dalle altre, ed e' anche cio' che il test incrociato verifica: un pezzo "
     "che seguisse il gancio anche da sganciato si vedrebbe subito."),
    ("p",
     "`fase_appesa` traduce una LiftPhase dal punto di vista del pezzo. Se il "
     "telaio e' appeso segue il gancio in tutto, traslazioni comprese -- su "
     "una zona di cambio quota il pezzo fa avanti e indietro insieme al "
     "carroponte. Se non e' appeso resta dov'e'."),
    ("p",
     "Le fasi di durata nulla si saltano. Sono frequenti: su una stazione "
     "senza corsa verticale quasi tutte le fasi durano zero, e emetterle "
     "produrrebbe una sequenza piena di istanti coincidenti che la ricerca "
     "binaria non saprebbe ordinare."),
    ("p",
     "L'ultima sosta non si emette dopo l'ultima mossa: il pezzo e' scaricato "
     "ed esce dalla linea. E' quello che fa finire la sua vita, e da li' si "
     "ricava quanti pezzi sono contemporaneamente in linea."),
]


# ==========================================================================
# Documento 2 -- la classe Simulazione
# ==========================================================================

STATO = [
    ("h1", "simulazione.py (2) -- Simulazione: dove sta ogni cosa"),
    ("p",
     "Secondo dei tre documenti su simulazione.py. La classe che, dato un "
     "istante, dice dove sta ogni carroponte e ogni pezzo. Non importa "
     "tkinter, quindi si prova senza finestre -- ed e' su questa che si fanno "
     "tutti i controlli di coerenza."),

    # ==================================================================
    ("h2", "1. La costruzione"),
    ("c", "simulazione.Simulazione", None, "    def __init__"),
    ("p",
     "Il docstring chiarisce il parametro meno ovvio: `carri` traduce l'indice "
     "di ZONA nel numero di CARROPONTE da mostrare. Di norma coincidono, ma in "
     "un ciclogramma composto a meta' le zone vengono riempite per continuita' "
     "-- e' la finzione di manuale.zone_coprenti -- e i due numeri divergono. "
     "Le zone senza nessuna mossa assegnata si omettono passando None."),
    ("c", "simulazione.Simulazione.__init__"),
    ("p",
     "Tutto il lavoro pesante e' qui: per ogni carroponte si costruisce una "
     "_Traiettoria con i suoi indici, gli impegni, il cumulato mobile e le "
     "quote a vuoto. Interrogare poi un istante costa una ricerca binaria."),
    ("p",
     "Gli IMPEGNI si calcolano da inizi_mossa piu' gli scostamenti che "
     "_fino_al_carico e _finche_c_e_il_carico ricavano dalle fasi: sono gli "
     "intervalli in cui il telaio e' davvero appeso, che cominciano DOPO "
     "l'inizio della presa e finiscono PRIMA della fine del rilascio."),
    ("q",
     "PERCHE' PIU' DI UN PERIODO. Il commento lo argomenta: in regime tutto si "
     "ripete ogni T, quindi un solo periodo basterebbe -- ma non si potrebbe "
     "seguire un pezzo dall'ingresso all'uscita, che e' proprio quello che si "
     "vuole guardare. La durata si arrotonda a un numero INTERO di periodi, "
     "cosi' il ritorno a zero e' impercettibile: la linea e' identica a se "
     "stessa."),

    ("h3", "I posti in vasca"),
    ("c", "simulazione.Simulazione._prepara_posti"),
    ("q",
     "IL NUMERO DI POSTI NON E' QUELLO DICHIARATO. E' la scelta piu' "
     "interessante del metodo, e il docstring la difende in tutte e due le "
     "direzioni. Si conta quanti posti il ciclogramma USA DAVVERO, non "
     "Tank.capacity. Con tre posti dichiarati e un pezzo solo, disegnarne tre "
     "metterebbe il pezzo fuori centro; e con un ciclogramma che SFORA la "
     "capienza, i pezzi di troppo finirebbero uno sopra l'altro -- nascondendo "
     "proprio l'errore che si vuole vedere."),
    ("p",
     "I posti si contano per VASCA e non per tappa: se la ricetta ci passa due "
     "volte, i pezzi delle due tappe si contendono lo stesso spazio. "
     "`_primo_posto` mette in fila i posti delle diverse tappe, cosi' non si "
     "sovrappongono."),

    # ==================================================================
    ("h2", "2. Le corsie"),
    ("c", "simulazione.Simulazione._corsia"),
    ("p",
     "Su quale posto della vasca sta un pezzo, contato dal centro. Il conto e' "
     "`pezzo % posti`, e il docstring spiega perche' basta: i pezzi che stanno "
     "insieme in una tappa hanno numeri d'ordine CONSECUTIVI -- ne entra uno "
     "ogni takt time -- quindi il resto della divisione da' a ciascuno il suo, "
     "senza tenere nessuno stato."),
    ("p",
     "Con un posto solo il conto fa sempre zero, e per una vasca normale il "
     "disegno non cambia."),
    ("c", "simulazione.Simulazione._corsia_fra"),
    ("p",
     "La corsia durante una traslazione: si passa dal posto di partenza a "
     "quello di arrivo mentre il carroponte trasla, invece di scattarci."),

    ("h3", "_corsia_carro -- il difetto che ha richiesto due tentativi"),
    ("c", "simulazione.Simulazione._corsia_carro"),
    ("p",
     "Il docstring e' il piu' lungo del modulo e racconta un difetto, una "
     "correzione sbagliata e la correzione giusta. Vale la pena seguirlo."),
    ("p",
     "LA REGOLA e' una sola: mentre il telaio e' appeso al gancio il "
     "carroponte sta sul posto di quel pezzo -- altrimenti il telaio si "
     "staccherebbe dal bilancino -- e in tutto il resto del giro si sposta di "
     "lato con calma."),
    ("q",
     "IL PRIMO DIFETTO. La corsia era legata al TRATTO invece che al telaio, e "
     "fuori dai tratti di una mossa valeva zero, cioe' il centro della vasca. "
     "Su una vasca a un posto solo non si vedeva -- il centro E' il posto -- ma "
     "su una vasca a piu' posti il carrello SCATTAVA di lato: appena finito un "
     "rilascio, e di nuovo passando da un pezzo al successivo nella stessa "
     "vasca, dove fra i due non c'e' nemmeno un istante di attesa."),
    ("q",
     "LA PRIMA CORREZIONE ERA PEGGIO. Spalmare lo spostamento su tutto "
     "l'intervallo libero faceva scivolare il carrello di fianco per un minuto "
     "mentre stava fermo sopra una vasca. Lo scatto era brutto, la deriva lenta "
     "e' peggio: uno scatto si legge come un difetto di disegno, un movimento "
     "lento e continuo si legge come una cosa che la macchina fa."),
    ("p",
     "La correzione giusta e' distribuire lo spostamento sul tempo in cui il "
     "carroponte GIA' SI MUOVE -- il rientro a vuoto, la discesa del gancio, "
     "l'aggancio -- e non sulle attese. E' a questo che serve il cumulato "
     "mobile: la frazione di interpolazione si calcola su quello, non sul "
     "tempo."),
    ("p",
     "L'ultimo ramo copre il caso in cui fra i due impegni non ci sia NIENTE "
     "che si muove: allora si spalma sull'intervallo, perche' meglio scivolare "
     "che saltare. E' il ripiego, non la regola."),
    ("p",
     "La ricerca degli impegni vicini gira in tondo: se dopo `tau` non ce n'e' "
     "nessuno si prende il primo del giro successivo, spostato di un periodo. "
     "E' lo `scarto` che poi viaggia fino a _pezzo_servito."),
    ("c", "simulazione.Simulazione._mobile_a"),
    ("p",
     "Il cumulato mobile a un istante qualsiasi, anche fuori dal periodo. Il "
     "docstring dice la proprieta' che serve: deve restare MONOTONO, perche' "
     "l'istante puo' cadere nel giro prima o in quello dopo e la frazione di "
     "interpolazione si calcola come differenza."),
    ("c", "simulazione.Simulazione._corsia_impegno"),
    ("p",
     "La corsia mentre il carroponte porta il pezzo della mossa k: quella "
     "della stazione di partenza durante la presa, quella di arrivo durante il "
     "rilascio, e l'interpolazione fra le due durante la traslazione."),
    ("q",
     "DUE ISTANTI DIVERSI, E NON E' UN REFUSO. `istante` e' il punto del giro "
     "da valutare, `tau` quello in cui ci si trova adesso: divergono quando si "
     "chiede la corsia agli estremi di un impegno vicino, per interpolare. Il "
     "PEZZO servito si ricava sempre da `tau`, perche' e' quello del giro "
     "corrente. Confonderli e' un difetto gia' fatto: i due parametri erano "
     "invertiti e il carroponte si metteva sul posto del pezzo sbagliato."),
    ("c", "simulazione.Simulazione._pezzo_servito"),
    ("p",
     "Pura aritmetica: il carroponte ha cominciato quella mossa a "
     "`t - avanzamento`, e la mossa comincia per il pezzo j all'istante "
     "`catena[k] + j*T`. Da li' j si ricava con una divisione e un "
     "arrotondamento."),

    # ==================================================================
    ("h2", "3. Lo stato dei carroponti"),
    ("c", "simulazione.Simulazione.istantanea"),
    ("c", "simulazione.Simulazione._stato_carri"),
    ("p",
     "Il wrap e' rispetto a `c.t0`, non a zero: i segmenti di un carroponte "
     "non partono dall'origine, e ciascuno ha la sua. E' la stessa trappola "
     "che verify._Trajectory denuncia, e la stessa soluzione."),
    ("c", "simulazione.Simulazione._gruppo_verticale"),
    ("p",
     "A quale presa o rilascio appartiene un tratto, e quando quel gruppo e' "
     "cominciato. Il docstring dice perche' serve: con una zona di cambio "
     "quota la presa non e' piu' un tratto solo -- e' sosta, traslazione, "
     "sosta, traslazione, sosta -- e il t_start del singolo tratto non dice "
     "piu' a che punto della presa si e' arrivati."),
    ("c", "simulazione.Simulazione._fase_verticale"),
    ("p",
     "Il metodo centrale: quota del gancio, se ha il pezzo, cosa sta facendo e "
     "sopra cosa. Tre rami, uno per famiglia di tratti."),
    ("q",
     "LA STAZIONE NON SI INDOVINA DALLA POSIZIONE. Prima frase del docstring: "
     "la dice il segmento (Segment.move), perche' la stessa vasca puo' "
     "comparire due volte nella ricetta e due vasche possono stare vicine "
     "quanto si vuole. E' lo stesso principio del campo `move` in model.py."),
    ("q",
     "ASPETTANDO SOPRA UNA VASCA IL GANCIO STA IN FONDO. Il secondo paragrafo "
     "del docstring risponde a una domanda che viene naturale -- non dovrebbe "
     "alzarsi un po'? -- e la risposta e' no, e non c'e' niente da correggere: "
     "le corse a vuoto del gancio non stanno in presa e rilascio, stanno nel "
     "rientro, quindi le fasi lo lasciano gia' dov'e'. Per un periodo il "
     "gancio si staccava di un dito dal telaio durante l'attesa, per far "
     "vedere che non lo teneva piu'. Era una cosa che il carroponte non fa, e "
     "si e' tolta: la macchina non ha nessun motivo di alzarsi per poi "
     "riabbassarsi, e il disegno non deve inventargliene uno."),
    ("q",
     "SI INTERPOLA IN MILLIMETRI, NON IN FRAZIONE. Il commento nel mezzo "
     "spiega un difetto sottile: position_profile misura una DISTANZA, e "
     "dandogli una frazione fra 0 e 1 esaurirebbe tutta la corsa nel primo "
     "millisecondo. Le due quote si riportano quindi sulla stessa corsa di "
     "riferimento e poi si interpola in millimetri. La frazione resta il "
     "riferimento perche' e' quella che si DISEGNA: due quote diverse su corse "
     "diverse possono benissimo essere tutte e due 'in fondo'."),

    ("h3", "Le tre ricerche di postazione"),
    ("c", "simulazione.Simulazione._vasca_a"),
    ("c", "simulazione.Simulazione._corsa_a"),
    ("c", "simulazione.Simulazione._riposo_a"),
    ("c", "simulazione.Simulazione._corsa_vicina"),
    ("p",
     "Quattro metodi che cercano una postazione a partire da una posizione, e "
     "differiscono in cosa restituiscono e in quanto sono tolleranti."),
    ("p",
     "_corsa_a e _riposo_a guardano i punti di APPROCCIO e non le vasche: e' "
     "li' che il gancio si trova quando comincia un rientro, e su una stazione "
     "con cambio quota il punto di approccio non e' la vasca."),
    ("q",
     "_corsa_vicina RIPIEGA, MA SOLO DOPO. Serve sugli SVINCOLI, che non sono "
     "posizioni di vasca ma stanno per costruzione fra una vasca e quella "
     "accanto: la piu' vicina e' la propria. Il docstring spiega pero' perche' "
     "si prova prima la corrispondenza esatta: un punto di CAMBIO QUOTA e' "
     "esso stesso il punto di approccio della sua stazione, e li' la risposta "
     "certa esiste. Ripiegare subito sulla piu' vicina darebbe la corsa della "
     "vasca sbagliata."),

    # ==================================================================
    ("h2", "4. Lo stato dei pezzi"),
    ("c", "simulazione.Simulazione._stato_pezzi"),
    ("p",
     "Quali pezzi sono in linea adesso: quelli entrati fra t meno la vita di "
     "un pezzo e t. Il conto con ceil e floor da' esattamente gli indici, "
     "senza bisogno di tenere una lista."),
    ("c", "simulazione.Simulazione._pezzo"),
    ("p",
     "Lo stato di un pezzo: ricerca binaria sulla fase attiva, poi "
     "interpolazione con i due profili. La corsia si interpola con la frazione "
     "di avanzamento DENTRO la fase, che e' quello che fa passare il pezzo da "
     "un posto all'altro mentre viene trasportato."),
    ("c", "simulazione.Simulazione.numeri_carri"),
    ("c", "simulazione.Simulazione.mosse_scoperte"),
    ("p",
     "Le mosse che nessun carroponte esegue. In un ciclogramma finito la lista "
     "e' vuota; durante la composizione a mano no, e allora nella simulazione "
     "si vedono pezzi che si spostano DA SOLI."),
    ("q",
     "ED E' BENE CHE SI VEDA. Il docstring lo dice in tre parole. Un pezzo che "
     "attraversa la linea senza che nessuno lo tocchi e' esattamente la "
     "rappresentazione onesta di un ciclogramma incompleto: nasconderlo -- "
     "saltando quel trasporto, o rifiutando di simulare -- toglierebbe "
     "all'utente il modo piu' diretto di accorgersi di cosa manca."),
]


# ==========================================================================
# Documento 3 -- la finestra
# ==========================================================================

FINESTRA = [
    ("h1", "simulazione.py (3) -- la finestra"),
    ("p",
     "Terzo dei tre documenti su simulazione.py: la parte che disegna e che "
     "anima. Non decide niente -- interroga la Simulazione e mette gli oggetti "
     "dove lei dice -- ma le scelte di disegno hanno il loro peso, perche' "
     "questo e' lo strumento con cui si guarda un ciclogramma per capire se "
     "regge."),

    # ==================================================================
    ("h2", "1. Le icone dei comandi, disegnate a mano"),
    ("c", "simulazione", "# Le icone dei comandi", "def _colonna"),
    ("c", "simulazione._colonna"),
    ("c", "simulazione._triangolo"),
    ("c", "simulazione._barra"),
    ("c", "simulazione.icona_comando"),
    ("p",
     "I pulsanti della simulazione portano simboli -- play, pausa, stop, passo "
     "avanti e indietro -- e i simboli sono immagini Tk costruite pixel per "
     "pixel al momento."),
    ("q",
     "PERCHE' NON UN CARATTERE UNICODE. Il commento in testa alla sezione lo "
     "argomenta: i simboli media di Unicode (U+23F8 e vicini) su Windows si "
     "vedono solo se il sistema trova un font che li contiene, e dove non lo "
     "trova compare un QUADRATINO -- che e' molto peggio della parola che "
     "sostituiva. Disegnate pixel per pixel sono invece identiche su qualunque "
     "macchina, eseguibile impacchettato compreso, e non c'e' nessun file da "
     "portarsi dietro. E' la stessa preoccupazione che porta a impacchettare "
     "il programma in una cartella sola."),
    ("p",
     "_colonna, _triangolo e _barra sono tre primitive che scrivono colonne di "
     "pixel; icona_comando le compone secondo il nome richiesto. Il triangolo "
     "e' pieno e si costruisce per colonne, con l'altezza che si stringe verso "
     "la punta."),
    ("c", "simulazione._Suggerimento"),
    ("p",
     "Il fumetto che compare fermandosi su un pulsante. Serve proprio perche' "
     "i pulsanti portano simboli e non parole: un simbolo e' piu' rapido da "
     "riconoscere quando lo si conosce gia', e muto quando non lo si conosce. "
     "Il suggerimento e' la parola che manca."),
    ("p",
     "I quattro metodi sono la meccanica standard: si arma un timer entrando, "
     "lo si annulla uscendo, e si mostra una finestra senza bordi accanto al "
     "puntatore. Il ritardo evita che il fumetto lampeggi passando sopra la "
     "barra dei comandi."),

    # ==================================================================
    ("h2", "2. La finestra"),
    ("c", "simulazione._Carro"),
    ("p",
     "Gli oggetti grafici di un carroponte, creati UNA volta e poi spostati. "
     "E' la scelta che rende l'animazione fluida: ridisegnare tutto a ogni "
     "fotogramma con matplotlib e' troppo lento per venti fotogrammi al "
     "secondo, mentre spostare gli oggetti esistenti no."),
    ("c", "simulazione.FinestraSimulazione", None, "    def __init__"),
    ("q",
     "PERCHE' UNA FINESTRA A SE'. Il docstring lo dice: la simulazione si "
     "guarda MENTRE si tiene d'occhio il ciclogramma. Incorporandola nella "
     "finestra principale si sarebbe dovuto scegliere quale delle due vedere, "
     "e il confronto fra le due viste -- che e' il motivo per cui la "
     "simulazione esiste -- sarebbe diventato impossibile."),
    ("c", "simulazione.FinestraSimulazione.__init__"),
    ("p",
     "Costruisce la finestra, la barra dei comandi e la tela di matplotlib. La "
     "velocita' parte da 1x: e' la velocita' reale, ed e' quella con cui si "
     "capisce se un movimento e' plausibile -- una simulazione accelerata "
     "rende tutto convincente."),
    ("c", "simulazione.FinestraSimulazione.aggiorna"),
    ("p",
     "Rilegge il ciclogramma. Si chiama anche mentre la finestra e' aperta: "
     "l'utente modifica il ciclogramma nell'editor e la simulazione lo segue, "
     "senza doverla chiudere e riaprire. E' la ragione per cui la scena si "
     "ricostruisce da zero invece di essere creata una volta sola nel "
     "costruttore."),

    # ==================================================================
    ("h2", "3. _prepara_scena -- quello che non si muove"),
    ("c", "simulazione.FinestraSimulazione._prepara_scena", None, "        # -- misure del disegno"),
    ("c", "simulazione.FinestraSimulazione._prepara_scena",
     "        # -- misure del disegno", "        # -- il capannone"),
    ("p",
     "Le misure del disegno si ricavano tutte dalla corsa verticale piu' "
     "grande della linea: l'altezza del telaio, il bordo delle vasche, il "
     "franco sopra la rotaia. Cosi' il disegno resta proporzionato sia su una "
     "linea con corse di 800 mm sia su una con corse di 3 metri."),
    ("p",
     "Dove la linea le DICHIARA, pero', si usano le misure vere: la larghezza "
     "di ogni vasca (`Tank.larghezza`), la larghezza del pezzo e il rapporto "
     "fra l'altezza del pezzo e quella della vasca. Sono gli unici dati del "
     "progetto che non servono a calcolare niente -- esistono per il disegno e "
     "basta -- e sono facoltativi: senza, restano le convenzioni di sempre, "
     "cioe' vasche tutte larghe il 62% del passo e un telaio grande una "
     "frazione fissa dell'altezza."),
    ("q",
     "LE LARGHEZZE SI USANO COM'E', LE ALTEZZE NO. In orizzontale l'asse e' "
     "gia' in millimetri veri, quindi una vasca larga 2600 si disegna larga "
     "2600. In verticale il disegno non e' in scala -- e' la frazione di "
     "discesa riportata su una profondita' comune, per la ragione spiegata "
     "sotto -- e una quota in millimetri non ci si puo' mettere. Dell'altezza "
     "si usa quindi il RAPPORTO fra pezzo e vasca: quanto il pezzo riempie la "
     "vasca sul disegno e' quanto la riempie davvero."),
    ("p",
     "_CORSA_PREDEFINITA copre il caso in cui nessuna vasca dichiari una "
     "corsa: senza, il grafico avrebbe altezza zero e non si vedrebbe niente. "
     "E' uno dei casi degeneri che test_simulazione prova apposta."),
    ("c", "simulazione.FinestraSimulazione._prepara_scena",
     "        # -- il capannone", "        # -- vasche e postazioni"),
    ("p",
     "Pavimento e colonne che reggono la rotaia. Non servono a niente di "
     "funzionale, e servono moltissimo: danno la scala. Senza un pavimento e "
     "delle colonne, un carroponte sospeso nel vuoto non fa capire quanto e' "
     "alta la linea ne' quanto e' lunga."),
    ("c", "simulazione.FinestraSimulazione._prepara_scena",
     "        # -- vasche e postazioni", "        # -- la rotaia"),
    ("p",
     "Il blocco piu' lungo, e quello con la distinzione che conta: una "
     "posizione e' una VASCA -- con il bagno colorato -- solo se una tappa "
     "INTERMEDIA del percorso ci si immerge. Carico e scarico sono POSTAZIONI, "
     "disegnate come piattaforme grigie su un piedistallo."),
    ("q",
     "LA DISCRIMINANTE E' IL PERCORSO, NON LA CORSA. Il criterio precedente "
     "era 'corsa zero significa postazione', e funzionava solo perche' di "
     "solito carico e scarico non ne hanno. Appena gliene si dava una -- una "
     "fossa, una rulliera piu' bassa -- diventavano bagni pieni di liquido. Il "
     "criterio giusto guarda se una tappa intermedia si immerge li': carico e "
     "scarico non lo sono mai, qualunque corsa abbiano."),
    ("p",
     "L'altezza del piano di una postazione segue la quota a cui il telaio "
     "viene posato, meno l'altezza del telaio. Anche questo calcolo esisteva "
     "prima solo per le zone di cambio quota, e il difetto -- telaio infilato "
     "dentro la postazione, funi che ci passano attraverso -- si sarebbe "
     "ripresentato su qualunque postazione con una rulliera piu' bassa. Ora e' "
     "una regola sola per tutti i casi."),
    ("c", "simulazione.FinestraSimulazione._misura_il_pezzo"),
    ("p",
     "Il telaio e' un MARKER e non un rettangolo in coordinate della linea: "
     "cosi' tutti i pezzi in lavorazione stanno in un oggetto grafico solo, "
     "che e' la ragione per cui la simulazione resta fluida con venti pezzi in "
     "linea. Il prezzo e' che un marker si misura in PUNTI TIPOGRAFICI, non in "
     "millimetri."),
    ("p",
     "Convertire non e' una moltiplicazione sola perche' i due assi hanno "
     "scale diversissime -- venti metri in orizzontale contro un metro e mezzo "
     "in verticale -- e un marker e' un simbolo unico: la larghezza in punti "
     "da' la DIMENSIONE del marker, e il rapporto fra le due misure da' la "
     "FORMA, schiacciando i vertici del simbolo in verticale."),
    ("p",
     "Si rifa' a ogni fotogramma, non una volta sola: la scala cambia quando "
     "si ridimensiona la finestra, e un simbolo calcolato all'apertura "
     "resterebbe della misura di allora. Costa due moltiplicazioni."),
    ("c", "simulazione.FinestraSimulazione._appoggio"),
    ("p",
     "Il basamento che regge una postazione. Esiste perche' un piano che "
     "galleggia a mezz'aria non si legge come una postazione: si legge come un "
     "errore di disegno."),
    ("c", "simulazione.FinestraSimulazione._prepara_scena",
     "        # -- la rotaia", "        # -- carroponti"),
    ("p",
     "La rotaia e' una TRAVE, non una riga: ha uno spessore. E' un dettaglio "
     "di un pixel che cambia molto, perche' i carroponti ci stanno appesi e "
     "una riga sottile li fa sembrare sospesi a niente."),
    ("c", "simulazione.FinestraSimulazione._prepara_scena",
     "        # -- carroponti", "        # -- pezzi"),
    ("c", "simulazione.FinestraSimulazione._prepara_scena",
     "        # -- pezzi", None),
    ("p",
     "Carroponti e pezzi sono gli oggetti che si muovono: si creano qui e si "
     "spostano a ogni fotogramma. Il numero di pezzi da creare e' il massimo "
     "che possono essere contemporaneamente in linea."),
    ("c", "simulazione.FinestraSimulazione._crea_carro"),
    ("c", "simulazione.FinestraSimulazione._posiziona_carro"),
    ("c", "simulazione._percorso_telaio"),
    ("p",
     "Il carroponte e' un carrello con le ruote sulla trave, le funi e il "
     "gancio; il telaio appeso e' una traversa con le barre verticali. Sono "
     "disegnati con la precisione minima che li rende riconoscibili: quello "
     "che deve leggersi e' se il gancio e' alto o basso e se il telaio c'e', "
     "non com'e' fatta la macchina."),

    # ==================================================================
    ("h2", "4. I comandi"),
    ("c", "simulazione.FinestraSimulazione.avvia_o_ferma"),
    ("c", "simulazione.FinestraSimulazione.da_capo"),
    ("c", "simulazione.FinestraSimulazione._fotogramma"),
    ("p",
     "Di quanti secondi di simulazione avanza un fotogramma: dipende dalla "
     "velocita' scelta e dalla frequenza di aggiornamento. E' l'unico punto in "
     "cui la velocita' entra, ed e' giusto che sia uno solo."),
    ("c", "simulazione.FinestraSimulazione.avanti"),
    ("c", "simulazione.FinestraSimulazione.indietro"),
    ("c", "simulazione.FinestraSimulazione._passo"),
    ("c", "simulazione.FinestraSimulazione._passo_a_mano"),
    ("c", "simulazione.FinestraSimulazione._pulsante_passo"),
    ("c", "simulazione.FinestraSimulazione._inizia_raffica"),
    ("c", "simulazione.FinestraSimulazione._continua_raffica"),
    ("c", "simulazione.FinestraSimulazione._ferma_raffica"),
    ("q",
     "TENERE PREMUTO DEVE SCORRERE. I pulsanti di passo avanti e indietro "
     "fanno un passo se li si preme, e continuano finche' li si tiene "
     "premuti. Il docstring di _pulsante_passo dice perche' serve: anche "
     "mettendo la velocita' a 20x, cercare un istante a clic singoli non e' "
     "praticabile -- e ALL'INDIETRO non c'e' proprio altro modo di farlo, "
     "perche' la riproduzione va solo avanti. La raffica e' un timer che si "
     "riarma finche' il tasto e' giu'."),
    ("c", "simulazione.FinestraSimulazione._trascinato"),
    ("p",
     "Il cursore del tempo si puo' trascinare, ed e' il modo piu' rapido per "
     "arrivare a un istante che si e' visto sul ciclogramma."),

    # ==================================================================
    ("h2", "5. Il disegno di un fotogramma"),
    ("c", "simulazione.FinestraSimulazione._disegna"),
    ("p",
     "Chiede l'istantanea alla Simulazione e sposta gli oggetti. Non crea "
     "niente: tutto esiste gia' dalla preparazione della scena."),
    ("c", "simulazione.FinestraSimulazione._ascissa"),
    ("p",
     "Dove disegnare un gancio o un telaio lungo la rotaia: la posizione piu' "
     "lo scostamento della corsia. E' qui che la corsia calcolata dal modello "
     "diventa millimetri sul disegno."),
    ("c", "simulazione.FinestraSimulazione._quota"),
    ("c", "simulazione.FinestraSimulazione._quota_disegnata"),
    ("q",
     "LE QUOTE DISEGNATE NON SONO QUELLE VERE. E' la scelta di disegno piu' "
     "importante del modulo. Una linea puo' avere una vasca con 800 mm di "
     "corsa e una con 3000: disegnandole in scala, la prima diventa un "
     "trattino e il movimento non si vede. Si disegna quindi la FRAZIONE di "
     "discesa -- quanto il gancio e' sceso rispetto alla corsa di quella vasca "
     "-- normalizzata su una profondita' comune. Il costo e' che una quota sul "
     "disegno non e' un millimetro reale; il guadagno e' che ogni "
     "movimentazione verticale si vede, che e' il motivo per cui si guarda."),
    ("p",
     "test_simulazione rifa' il controllo incrociato anche sulle quote "
     "DISEGNATE, non solo su quelle vere: il telaio deve restare appeso al "
     "bilancino anche dopo il rimappaggio. E' facile che una funzione di "
     "rimappaggio sia coerente per il gancio e non per il pezzo."),
    ("c", "simulazione.FinestraSimulazione._titolo"),
    ("c", "simulazione.FinestraSimulazione._descrizione"),
    ("p",
     "Il testo che accompagna il fotogramma: quale carroponte sta facendo "
     "cosa, sopra quale vasca. E' quello che permette di fermare la "
     "simulazione su un istante e leggere cosa sta succedendo, invece di "
     "dedurlo."),
    ("c", "simulazione.FinestraSimulazione.destroy"),
    ("p",
     "La chiusura ferma il timer e libera la figura matplotlib. Non e' "
     "formalita': un timer che continua a scattare su una finestra distrutta "
     "solleva eccezioni a raffica, e una figura non liberata resta in memoria "
     "-- e queste finestre si aprono e si chiudono molte volte in una "
     "sessione di lavoro."),
]


DOCUMENTI = [
    ("simulazione_1_modello.docx", MODELLO),
    ("simulazione_2_stato.docx", STATO),
    ("simulazione_3_finestra.docx", FINESTRA),
]
