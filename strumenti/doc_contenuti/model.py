"""
Il testo dei documenti di model.py.

Sessantatre' fra funzioni e metodi, 2648 righe: il modulo piu' grande del
progetto e l'unico che nessun altro puo' sostituire. Diviso per argomento,
non per posizione nel file.
"""

from __future__ import annotations

# ==========================================================================
# Documento 1 -- le strutture dati
# ==========================================================================

STRUTTURE = [
    ("h1", "model.py (1) -- le strutture dati e le validazioni"),
    ("p",
     "Primo dei documenti su model.py. Qui si vede COME e' descritto il "
     "problema: le vasche, il percorso, le zone, i tratti di traiettoria. E "
     "soprattutto le validazioni, che sono il quinto del modulo che si occupa "
     "di rifiutare i dati impossibili prima che diventino un INFEASIBLE muto. "
     "Ogni blocco di codice e' estratto dal sorgente al momento della "
     "generazione."),

    # ==================================================================
    ("h2", "I gradi di liberta', e perche' contarli"),
    ("p",
     "Un ciclogramma sembra fatto di moltissime grandezze: istanti di "
     "prelievo, traiettorie, giri a vuoto, tempi di salita. Sono quasi tutte "
     "CONSEGUENZE. I gradi di liberta' veri sono quattro:"),
    ("li", "il TAKT TIME: ogni quanto entra un pezzo in linea;"),
    ("li", "il TEMPO IN VASCA di ogni tappa, entro i limiti di processo;"),
    ("li", "l'ASSEGNAZIONE: quale carroponte esegue quale trasporto;"),
    ("li",
     "la SOSTA: quanto ogni carroponte resta fermo dove ha consegnato, prima "
     "di partire a vuoto verso la mossa successiva."),
    ("p",
     "Tutto il resto si ricalcola da questi. E' il fatto piu' importante "
     "dell'intero progetto, perche' da li' discendono l'editor manuale (si "
     "modificano dei valori, non un disegno), il formato di salvataggio "
     "(quei valori, non le traiettorie) e la possibilita' stessa di "
     "verificare in modo indipendente."),
    ("q",
     "PER MOLTO TEMPO SE NE SONO CONTATI TRE, E LA SOSTA NON C'ERA. Non "
     "perche' non esistesse: perche' la decideva una convenzione scritta nel "
     "codice -- 'riparte appena consegnato' -- e una convenzione non e' un "
     "grado di liberta', e' una costante. Il guaio e' che il solutore una "
     "parte di quella liberta' se l'era gia' presa: la variabile dep_hi gli "
     "lasciava far sostare il carroponte sul confine alto, e nel salvataggio "
     "quel valore non c'era. Si calcolava un ciclogramma, lo si verificava "
     "pulito, lo si salvava, lo si riapriva -- e la traiettoria era un'altra, "
     "perche' veniva ricostruita con la convenzione."),
    ("q",
     "QUANTO COSTAVA, MISURATO. Su 50 soluzioni verificate pulite, ricostruite "
     "come fa il programma quando riapri il file: 15 cambiavano separazione "
     "minima e 14 COLLIDEVANO, una con i due carri sovrapposti (0 mm invece "
     "dei 1200 richiesti), dopo una sosta al confine di 374 secondi che il "
     "file non aveva registrato. Rifatta la stessa prova salvando le soste: "
     "0 su 54. Il quarto grado di liberta' non e' una funzionalita' in piu', "
     "e' il nome di un difetto che non si riusciva a vedere."),

    # ==================================================================
    ("h2", "1. Tank -- la vasca"),
    ("c", "model.Tank"),
    ("q",
     "LE ULTIME DUE NON SERVONO A CALCOLARE NIENTE. `larghezza` e `altezza` "
     "della vasca -- come `larghezza_pezzo` e `altezza_pezzo` in ProblemData "
     "-- le guarda solo la simulazione, per disegnare in proporzione invece "
     "che con misure convenzionali. Sono facoltative, e una linea che non le "
     "dichiara si risolve e si verifica esattamente come prima. Il controllo "
     "in __post_init__ rifiuta solo lo zero o il negativo, che non sarebbero "
     "un disegno diverso ma un rettangolo invisibile."),
    ("p",
     "Immutabile (frozen), e ogni campo porta con se' la ragione per cui sta "
     "li'. Vale la pena leggerli in ordine, perche' raccontano tre "
     "spostamenti di responsabilita' avvenuti nel tempo."),
    ("p",
     "`capacity` e' della VASCA FISICA, non della tappa: se la ricetta passa "
     "due volte dalla stessa vasca, i pezzi delle due tappe si contendono gli "
     "stessi posti. E' la distinzione che rende necessario un vincolo "
     "cumulativo invece di un semplice confronto con il takt time."),
    ("q",
     "PERCHE' lift_height E drain_time SONO OBBLIGATORI. Il commento lo "
     "argomenta: sono proprieta' della vasca -- la sua profondita', la sua "
     "chimica -- non del carroponte. Un valore generale con le vasche come "
     "eccezione sarebbe un DEFAULT SILENZIOSO: chi dimentica una riga non se "
     "ne accorge, e il calcolo usa un numero che nessuno ha scelto per quella "
     "vasca. Meglio scrivere 0 dove non serve niente, che e' una "
     "dichiarazione."),
    ("p",
     "Sono anche keyword-only, ed e' una difesa contro un errore preciso: una "
     "chiamata posizionale scritta per la versione precedente non puo' finire "
     "per assegnarli di nascosto. Con i campi posizionali, aggiungere un "
     "parametro in mezzo rompe in silenzio ogni costruzione esistente."),
    ("p",
     "Gli SVINCOLI sono i due punti, uno per lato, in cui il gancio SCARICO "
     "puo' salire e scendere. Il commento chiarisce l'asimmetria che governa "
     "meta' del modulo: le corse verticali a vuoto avvengono sempre e solo "
     "li', mai sopra il centro di una vasca, mentre il sollevamento COL PEZZO "
     "e' sempre al centro -- perche' e' li' che sta il telaio."),
    ("p",
     "`gancio_basso` a False fa della vasca un OSTACOLO. Il commento racconta "
     "la storia: era un parametro unico per tutta la linea, e obbligava OGNI "
     "rientro a pagare salita e discesa anche dove non serviva. Per vasca, un "
     "rientro che non scavalca nessun ostacolo resta basso e non paga niente."),

    ("h3", "StationSpec e HoistZone"),
    ("c", "model.StationSpec"),
    ("c", "model.HoistZone"),
    ("q",
     "MOSSE, NON STAZIONI. La distinzione piu' facile da sbagliare di tutto il "
     "progetto: una zona e' un intervallo di indici di MOSSA, e la mossa k e' "
     "il trasporto dalla stazione k alla k+1. Con n stazioni ci sono n-1 "
     "mosse. Un carroponte che gestisce le mosse da 2 a 4 tocca le stazioni da "
     "2 a 5: cinque stazioni per tre mosse. Confondere i due indici da' codice "
     "che funziona sugli esempi piccoli e sbaglia di uno agli estremi."),

    # ==================================================================
    ("h2", "2. ZonaCambioQuota"),
    ("c", "model.ZonaCambioQuota", None, "    def quota_interna"),
    ("p",
     "Serve agli impianti in cui il carroponte non puo' salire e scendere "
     "sopra il carico e lo scarico: c'e' un passaggio obbligato -- una porta, "
     "un tunnel, una struttura -- che va attraversato a una quota e non a "
     "un'altra. Ce ne possono essere al massimo due, una per estremo."),
    ("q",
     "DUE SCALE VERTICALI DIVERSE NELLO STESSO PROGRAMMA. E' la trappola che "
     "il docstring dichiara con uno schema. Dentro il modello la quota di "
     "TRASPORTO vale 0 e si scende in negativo; qui invece 0 e' la quota piu' "
     "bassa del carroponte e corsa_totale e' la cima. La ragione e' pratica: "
     "chi compila i dati dell'impianto misura da TERRA, non dalla trave. La "
     "conversione sta in un solo metodo, e chiunque legga questi campi senza "
     "passare di li' sbaglia di corsa_totale -- un errore che non da' "
     "eccezioni, solo un disegno assurdo."),
    ("c", "model.ZonaCambioQuota.quota_interna"),
    ("c", "model.ZonaCambioQuota", "    @property", None),
    ("p",
     "Le quattro proprieta' sono la scala interna gia' convertita. "
     "`corsa_telaio` e' quella che sorprende: alla stazione servita da una "
     "zona di cambio quota il telaio NON sale dal fondo alla quota di "
     "trasporto, ma da intermediate1 a intermediate2. E' la corsa che il "
     "modello deve usare per il tempo di sollevamento, e non ha niente a che "
     "vedere con la corsa dichiarata per la vasca -- che infatti deve essere "
     "zero, come impone una validazione."),

    # ==================================================================
    ("h2", "3. LiftPhase -- un tratto di movimentazione verticale"),
    ("c", "model.LiftPhase"),
    ("p",
     "Le quote sono riferite alla quota di TRASPORTO, che vale 0. Il docstring "
     "difende la scelta contro l'alternativa apparentemente piu' naturale, un "
     "riferimento assoluto sul pavimento: delle vasche si conosce la CORSA, "
     "non la profondita', e un riferimento assoluto obbligherebbe a inventare "
     "un dato che nessuno ha dichiarato."),
    ("p",
     "I tre campi orizzontali in coda -- x_start, x_end, kin_x -- restano None "
     "quasi sempre: durante una presa normale il carroponte e' fermo sopra la "
     "stazione, e la posizione la conosce gia' chi chiama. Li riempie soltanto "
     "una zona di cambio quota."),
    ("q",
     "DURANTE UNA PRESA IL CARROPONTE PUO' NON ESSERE FERMO. E' la "
     "conseguenza che rende quei tre campi necessari, ed e' scritta nel "
     "commento. Con una zona di cambio quota, la presa comprende due "
     "traslazioni fra il punto di cambio quota e la stazione. Chi campiona le "
     "posizioni per il vincolo di non collisione deve saperlo: crederlo fermo "
     "significa proteggere un punto in cui non e'."),
    ("p",
     "`trasla` distingue una fase che sposta davvero da una che ha solo le "
     "coordinate valorizzate. La soglia di 1e-9 evita che un arrotondamento "
     "faccia apparire una traslazione lunga zero."),

    # ==================================================================
    ("h2", "4. ProblemData -- i campi"),
    ("c", "model.ProblemData", None, "    def __post_init__"),
    ("p",
     "Il problema completo. I campi obbligatori vengono prima, poi quelli con "
     "un valore predefinito. Tre commenti meritano lettura."),
    ("p",
     "Gli INGOMBRI si dichiarano separatamente per lato perche' il carrello "
     "non e' detto sia simmetrico rispetto al gancio, e il gancio e' il punto "
     "che deve stare sopra la vasca."),
    ("p",
     "Il blocco sulla movimentazione verticale descrive una mossa per intero, "
     "ed e' la definizione a cui tutto il resto si riferisce: si arriva a "
     "vuoto, si cala il gancio, si aggancia, si solleva, si sgocciola -- e "
     "questa e' la PRESA; si trasla; si cala il telaio, si sgancia e si risale "
     "-- e questo e' il RILASCIO. La frase da ricordare e' l'ultima: lo "
     "spostamento a vuoto successivo non paga nulla, perche' la corsa del "
     "gancio scarico e' gia' contata qui dentro. Contarla due volte e' "
     "l'errore piu' facile da fare estendendo il modello."),
    ("q",
     "clearance_step_mm NON E' UN MARGINE DI SICUREZZA. Il commento insiste "
     "perche' il nome inganna. E' ogni quanti millimetri viene verificata la "
     "distanza fra due carroponti, e lo stesso numero si legge in due modi: "
     "quanto sono fitte le verifiche, e di quanto il modello puo' essere piu' "
     "severo del necessario. La distanza GARANTITA resta D qualunque valore si "
     "metta -- infittire puo' solo far accettare soluzioni buone che prima "
     "venivano scartate, mai accettarne di pericolose. Il margine di sicurezza "
     "vero e' safety_distance, che entra in D."),
    ("p",
     "Le due zone di cambio quota stanno in FONDO alla dataclass, e il "
     "commento dice perche': aggiungerle in mezzo romperebbe le costruzioni "
     "posizionali gia' scritte. E' la stessa preoccupazione dei campi "
     "keyword-only di Tank."),

    # ==================================================================
    ("h2", "5. __post_init__ -- rifiutare bene"),
    ("p",
     "Duecentoquaranta righe di sole validazioni, ed e' proporzionato: quasi "
     "ogni riga qui e' un INFEASIBLE muto che qualcuno non dovra' diagnosticare. "
     "Un solutore che risponde 'impossibile' senza dire perche' e' la peggiore "
     "esperienza che questo programma possa dare, perche' manda a cercare la "
     "causa dappertutto."),

    ("h3", "Coerenza di base"),
    ("c", "model.ProblemData.__post_init__", None, "        # Gli svincoli devono stare fra"),
    ("p",
     "Percorso di almeno due stazioni, zone che coprono tutte le mosse, vasche "
     "che esistono, permanenze ordinate, tempi non negativi. Il confronto "
     "delle zone e' fra LISTE, non insiemi: verifica in un colpo solo che non "
     "manchi niente, che non ci sia niente in piu' e che l'ordine sia "
     "crescente."),
    ("p",
     "L'ultimo controllo del blocco e' di natura diversa: se qualche vasca ha "
     "una corsa verticale, kin_lift_loaded diventa obbligatoria. E il "
     "messaggio non dice 'parametro mancante', dice cosa non si potrebbe "
     "sapere senza: 'quanto ci mette il telaio a uscire dal bagno e a "
     "rientrarci'."),

    ("h3", "Gli svincoli devono stare fra due vasche"),
    ("c", "model.ProblemData.__post_init__", "        # Gli svincoli devono stare fra",
     "        # -- zone di cambio quota"),
    ("q",
     "UN CONTROLLO CHE NE EVITA MOLTI ALTRI. Il commento lo dice: verificare "
     "qui che ogni svincolo cada fra la sua vasca e quella accanto GARANTISCE "
     "che il gancio, traslando basso per raggiungerlo, non scavalchi mai "
     "un'altra vasca. Senza questa garanzia, ogni spostamento andrebbe "
     "verificato lungo il percorso: un controllo statico sui dati sostituisce "
     "un controllo dinamico su ogni movimento. E' il tipo di validazione che "
     "vale dieci volte quello che costa."),
    ("p",
     "Il messaggio d'errore mostra il valore trovato, l'intervallo ammesso con "
     "i due estremi, e la conseguenza fisica -- 'altrimenti il gancio basso "
     "dovrebbe scavalcare un'altra vasca per arrivarci'. Tutti e tre servono: "
     "il valore per riconoscere la cella, l'intervallo per correggerla, la "
     "conseguenza per capire che non e' una pedanteria del programma."),

    ("h3", "Le zone di cambio quota"),
    ("c", "model.ProblemData.__post_init__", "        # -- zone di cambio quota",
     "        # -- svincoli e vasche-ostacolo"),
    ("p",
     "Cinque controlli, e il commento in testa spiega che il vincolo sulla "
     "POSIZIONE porta due garanzie e non una."),
    ("li", "il carroponte, per andare a cambiare quota, non scavalca nessuna "
           "altra stazione -- lo stesso motivo del controllo sugli svincoli;"),
    ("li", "il vai-e-torna dentro la presa si ALLONTANA dal resto della linea, "
           "quindi non avvicina il carroponte a nessun confine di zona piu' di "
           "quanto gia' non faccia il punto di cambio quota."),
    ("q",
     "LA SECONDA GARANZIA TIENE IN PIEDI LA NON COLLISIONE. Senza di essa un "
     "carroponte si muoverebbe in un intervallo in cui il modello lo crede "
     "fermo -- e il modello non avrebbe nessun modo di accorgersene, perche' "
     "il movimento e' dentro la presa. E' un vincolo sui DATI che sostiene un "
     "vincolo sul MODELLO: toglierlo non darebbe nessun errore, darebbe "
     "collisioni con stato OPTIMAL."),
    ("p",
     "Il controllo sulla corsa dichiarata merita attenzione perche' rifiuta un "
     "dato che sembra innocuo: la stazione servita da una zona di cambio quota "
     "deve dichiarare corsa verticale ZERO. Li' la corsa la definisce la zona "
     "(da intermediate1 a intermediate2), e un valore diverso da zero sarebbe "
     "due descrizioni della stessa cosa. Il messaggio calcola e mostra la "
     "corsa vera, cosi' chi legge capisce che il dato non e' perso ma "
     "sostituito."),

    ("h3", "Ostacoli e svincoli, insieme"),
    ("c", "model.ProblemData.__post_init__", "        # -- svincoli e vasche-ostacolo",
     "        if self.clearance_step_mm <= 0:"),
    ("p", "Quattro regole che legano fra loro le due proprieta' per vasca."),
    ("li", "Una vasca ostacolo agli ESTREMI non ha senso: li' non c'e' niente "
           "da scavalcare. Il messaggio non si limita a rifiutare, indirizza "
           "verso lo strumento giusto: 'quello che serve e' una ZONA DI CAMBIO "
           "QUOTA, non un ostacolo'."),
    ("li", "Gli svincoli si dichiarano per TUTTA la linea o per niente. La "
           "ragione e' nel commento: qualunque vasca puo' essere il capo di un "
           "rientro che deve passare alto, e quella senza svincoli non "
           "saprebbe dove salire. Il messaggio elenca le vasche mancanti."),
    ("li", "Una vasca ostacolo senza svincoli e' una contraddizione: il gancio "
           "scarico non avrebbe dove salire per scavalcarla."),
    ("li", "Con degli ostacoli serve kin_lift_empty, altrimenti non si sa "
           "quanto costa la salita."),
    ("p",
     "Sono quattro messaggi diversi per quattro situazioni diverse, e nessuno "
     "di essi dice soltanto che un dato manca: ciascuno dice cosa non si "
     "potrebbe fare senza."),

    ("h3", "L'impossibile dichiarato subito"),
    ("c", "model.ProblemData.__post_init__", "        if self.clearance_step_mm <= 0:", None),
    ("p",
     "Gli ultimi due controlli sono i piu' interessanti del metodo, perche' "
     "non riguardano la coerenza dei dati ma la FATTIBILITA' fisica."),
    ("p",
     "Il primo: il pezzo resta in bagno almeno per le due corse a vuoto del "
     "gancio piu' i tempi morti, anche prelevandolo appena possibile. Se la "
     "permanenza massima ammessa -- il tempo teorico piu' il delta positivo "
     "-- e' inferiore a quel minimo, la linea e' irrealizzabile, e il "
     "messaggio elenca le tre leve vere: alzare il teorico o il delta "
     "positivo, velocizzare il sollevamento a vuoto, ridurre la corsa."),
    ("p",
     "Il secondo: un pezzo occupa un posto per un certo tempo, e ogni T ne "
     "entra uno nuovo; se l'occupazione minima supera capacity * takt_max, non "
     "c'e' ciclogramma possibile. Il commento dichiara che e' una condizione "
     "NECESSARIA valutata una tappa alla volta: se la stessa vasca compare "
     "piu' volte il vincolo vero e' ancora piu' stretto, ma quello lo impone "
     "il modello."),
    ("q",
     "PERCHE' QUI E NON NEL MODELLO. Il commento risponde: 'Meglio dirlo "
     "subito e chiaramente che restituire un INFEASIBLE muto'. Il modello "
     "rileverebbe entrambe le situazioni, ma la sua risposta sarebbe "
     "'impossibile' senza indicare quale vasca -- e su una linea di dieci "
     "vasche la ricerca comincerebbe da zero."),

    # ==================================================================
    ("h2", "6. Le comodita'"),
    ("c", "model.ProblemData", "    # -- comodita'", "    def zona_cambio_quota"),
    ("p",
     "hoist_length ha il docstring piu' lungo di tutti i cinque, e per una "
     "buona ragione: dimostra che i due ingombri contano solo per la loro "
     "SOMMA. Se il carroponte di sinistra ha il gancio in p e quello di destra "
     "in q, lo spazio libero fra i due vale q - p - (pos + neg). Dove sia il "
     "gancio dentro il carrello non cambia nulla. E' il motivo per cui tutto "
     "il vincolo di non collisione lavora su un numero solo."),
    ("p",
     "n_hoists SOLLEVA se le zone non sono ancora decise, invece di "
     "restituire zero o None. E il messaggio dice la funzione da chiamare "
     "(solve_auto_zones). E' l'errore piu' facile da fare usando il modulo "
     "come libreria, perche' la ProblemData appena letta non ha ancora le "
     "zone."),
    ("c", "model.ProblemData", "    def tank_capacity", "    def to_ticks"),
    ("p",
     "steps_by_tank esclude carico e scarico, che stanno fuori dalla catena "
     "delle permanenze. move_distance misura fra i punti di APPROCCIO e non "
     "fra le vasche, per la ragione che il documento sulle fasi verticali "
     "sviluppa: con una zona di cambio quota il tratto col pezzo comincia sul "
     "punto di cambio quota, perche' l'ultimo pezzo di strada lo fa la presa."),
    ("c", "model.ProblemData", "    def to_ticks", "    # -- durate delle tratte"),
    ("q",
     "I TEMPI SONO TICK INTERI, LE POSIZIONI NO. CP-SAT lavora su interi, "
     "quindi ogni durata viene arrotondata al tick (un centesimo di secondo "
     "col valore predefinito). Le posizioni restano millimetri in virgola "
     "mobile e non entrano mai come variabili: le vasche sono ferme, quindi "
     "ogni distanza e ogni tempo di percorrenza sono COSTANTI note prima di "
     "risolvere. E' questa asimmetria che tiene il modello lineare."),
    ("p",
     "eps_seconds e' la conseguenza dichiarata di quell'arrotondamento: chi "
     "ricalcola le stesse durate in virgola mobile deve accettare uno scarto "
     "di quest'ordine. Con time_scale a 100 vale un decimo di secondo -- dieci "
     "tick, non uno, perche' le durate si sommano e gli errori con loro. E' la "
     "tolleranza che usa il verificatore, e usarne una diversa "
     "nasconderebbe errori veri o ne inventerebbe di falsi."),

    # ==================================================================
    ("h2", "7. Segment, HoistPlan, Solution -- il risultato"),
    ("c", "model.Segment"),
    ("p",
     "Un tratto di traiettoria. Sette tipi possibili, e 'quota' e' quello che "
     "il commento spiega: e' l'unico tratto in cui il carroponte si muove "
     "senza che il tratto appartenga ne' al trasporto ne' al rientro a vuoto."),
    ("q",
     "`move` E' None PER ATTESA E RIENTRO, E NON E' UNA MANCANZA. Il commento "
     "la difende: quei tratti stanno FRA due mosse, e attribuirli all'una o "
     "all'altra sarebbe una convenzione arbitraria. Il campo serve a chi deve "
     "risalire dalla traiettoria alla VASCA -- la presa della mossa k avviene "
     "sulla stazione k, il rilascio sulla k+1 -- e da li' si ricavano corsa e "
     "sgocciolamento. Dedurlo dalla posizione sbaglierebbe appena due vasche "
     "stessero alla stessa quota, che e' un caso ammesso."),
    ("c", "model.HoistPlan"),
    ("p",
     "I valori risolti, cosi' come li ha decisi il solutore. Il docstring "
     "dichiara a chi servono e perche' non basterebbero i soli Segment: dalle "
     "traiettorie non si ricostruiscono i tempi ASSOLUTI, perche' le fasi "
     "locali sono note solo modulo T. Senza questi valori il controllo delle "
     "permanenze sarebbe ambiguo per multipli interi del takt time -- ed e' "
     "esattamente la nota che verify.py registra quando i piani mancano."),
    ("c", "model.Solution"),
    ("p",
     "Sei campi, e `raw` e' l'unico non strutturato: un dizionario di valori "
     "grezzi utili a capire cosa e' successo. Ci finiscono il registro dei "
     "tentativi della ricerca automatica e l'elenco delle incoerenze di un "
     "ciclogramma composto a mano."),
    ("p",
     "`status` non e' una lista chiusa. Oltre agli stati del solutore ci sono "
     "'MANUALE' e 'PROPOSTA', ed e' il motivo per cui plotting.py e verify.py "
     "filtrano elencando gli stati da RIFIUTARE invece di quelli da accettare."),

    ("h3", "Interruzione -- fermare un calcolo da un altro thread"),
    ("c", "model.Interruzione"),
    ("p",
     "La richiesta di fermare un calcolo. L'interfaccia ne crea una a ogni "
     "'Calcola auto', la passa al thread che calcola, e il pulsante Ferma "
     "chiama ferma(). Una ricerca automatica puo' durare decine di minuti, e "
     "prima l'unico modo di rinunciarci era chiudere il programma."),
    ("p",
     "Il docstring spiega perche' servono DUE meccanismi. Mentre si costruisce "
     "il modello si e' in Python, e basta guardare `richiesta` ogni tanto: "
     "solve lo fa a ogni carroponte e a ogni confine. Mentre CP-SAT cerca si e' "
     "in codice nativo, che non guarda niente: li' serve StopSearch() sul "
     "solutore in corsa, e per chiamarlo bisogna averlo -- solve lo registra "
     "con _registra prima di lanciarlo e lo toglie con _libera dopo."),
    ("q",
     "IL LUCCHETTO NON E' PRUDENZA GENERICA. Chiude una corsa precisa: una "
     "richiesta che arriva dopo l'ultimo controllo di `richiesta` ma prima che "
     "il solutore sia registrato non troverebbe nessuno da fermare, e il "
     "calcolo durerebbe tutto il suo limite di tempo. Con registrazione e "
     "stop sotto lo stesso lucchetto le possibilita' sono due sole: il "
     "solutore e' gia' in lista e viene fermato, oppure la richiesta c'e' gia' "
     "e _registra risponde False, e il solutore non parte."),
    ("p",
     "Misurato su due linee con svincoli, fermando sia durante la costruzione "
     "sia durante la ricerca: solve risponde fra 0,1 e 0,5 secondi dopo lo "
     "stop."),
    ("c", "model._soluzione_interrotta"),
    ("q",
     "UNKNOWN, NON INFEASIBLE. Un calcolo fermato non ha dimostrato niente, e "
     "INFEASIBLE e' una dimostrazione: l'interfaccia la tratterebbe come tale, "
     "lanciando la diagnosi e consigliando di cambiare la linea. Il segno di "
     "riconoscimento e' `raw['interrotto']`, che solve_auto_zones e "
     "solve_auto_hoists guardano per non passare al tentativo successivo."),
]


# ==========================================================================
# Documento 2 -- presa, rilascio, e il tempo verticale
# ==========================================================================

FASI = [
    ("h1", "model.py (2) -- presa, rilascio e il tempo verticale"),
    ("p",
     "Secondo dei documenti su model.py. Qui si vede da dove escono le durate "
     "che il modello usa: quanto dura una presa, un rilascio, una mossa "
     "intera, e quanto tempo il pezzo passa davvero in bagno."),

    # ==================================================================
    ("h2", "Dove sta il carroponte, e a che quota"),
    ("c", "model.ProblemData", "    def zona_cambio_quota", "    def tank_capacity"),
    ("p",
     "Quattro metodi che rispondono alla stessa domanda in quattro modi, e "
     "che sulle linee normali danno tutti la risposta ovvia. Esistono per il "
     "caso in cui la risposta ovvia e' sbagliata."),
    ("p",
     "zona_cambio_quota ammette solo la PRIMA e l'ULTIMA tappa, e il docstring "
     "chiarisce perche': sono le uniche due agli estremi della linea, dove il "
     "carroponte esce dal campo delle vasche. Se la stessa vasca ricompare a "
     "meta' percorso non c'entra nulla -- li' e' una vasca come le altre. Il "
     "controllo e' quindi sull'INDICE di tappa, non sulla vasca."),
    ("q",
     "approach_position NON E' station_position. E' la distinzione che "
     "attraversa mezzo progetto, e il docstring la chiude con una frase in "
     "maiuscolo: e' QUESTA la posizione da usare per le distanze fra tratte "
     "del giro. Di norma coincide con la stazione; con una zona di cambio "
     "quota e' il punto di cambio quota, perche' li' finiscono i rientri a "
     "vuoto e li' comincia la traslazione col pezzo -- l'andata alla stazione "
     "e il ritorno stanno dentro la presa. Usare station_position al suo posto "
     "produce distanze sbagliate senza nessun errore visibile."),
    ("p",
     "quota_di_riposo e corsa_verticale sono la coppia verticale della stessa "
     "distinzione. Sulle vasche il telaio riposa a -lift_height e il gancio "
     "scende di altrettanto; su una zona di cambio quota il telaio riposa a "
     "z_int1, ma il gancio arriva fino in fondo -- corsa_totale. Sono due "
     "numeri diversi e servono a due cose diverse: il primo a sapere dove sta "
     "il telaio, il secondo a sapere quanto costa la corsa a vuoto."),

    # ==================================================================
    ("h2", "Il principio: un solo posto in cui le durate sono definite"),
    ("c", "model.ProblemData", "    # -- durate delle tratte", "    def pick_phases"),
    ("p",
     "Il commento in testa alla sezione e' una regola per chi modifica: tutto "
     "il resto del codice -- modello CP-SAT, ricostruzione delle traiettorie, "
     "pre-filtro delle zone, verificatore -- DEVE passare da qui. Cosi' una "
     "modifica alla definizione di 'durata di una mossa' si propaga ovunque "
     "senza rischio di disallineamenti."),
    ("p",
     "_lift_seconds restituisce zero per corsa nulla o cinematica assente. E' "
     "la scorciatoia che permette a tutto il resto di non distinguere una "
     "stazione senza movimentazione verticale: carico e scarico attraversano "
     "le stesse funzioni delle vasche, e ne escono con durate zero."),

    # ==================================================================
    ("h2", "1. Le fasi, non le durate"),
    ("c", "model.ProblemData.pick_phases"),
    ("p",
     "Il docstring dichiara l'inversione che governa tutto il modulo: il "
     "ciclogramma avrebbe bisogno solo della durata totale, ma chi deve "
     "MOSTRARE la presa -- la simulazione -- ha bisogno di sapere dove sta il "
     "gancio istante per istante. Allora le FASI sono la definizione, e la "
     "durata e' la loro somma."),
    ("p",
     "E' una scelta che costa: una lista di oggetti dove basterebbe un numero. "
     "In cambio i due usi non possono divergere. La durata usata dal modello e "
     "la sequenza disegnata dalla simulazione sono la stessa cosa vista da due "
     "parti, non due descrizioni da tenere allineate a mano."),
    ("q",
     "LA DISCESA DEL GANCIO SCARICO NON E' QUI DENTRO. Il docstring lo dice in "
     "maiuscolo, ed e' la ripartizione piu' facile da sbagliare. O l'impianto "
     "lascia traslare il gancio basso -- e allora il carroponte arriva con il "
     "gancio gia' in fondo, e non c'e' nessuna discesa -- oppure il gancio "
     "scende su una posizione di svincolo, e quella e' parte del RIENTRO A "
     "VUOTO. Metterla nella presa la conterebbe due volte, perche' il rientro "
     "la paga gia'."),
    ("p",
     "Le tre fasi della presa normale sono aggancio (a quota di fondo, senza "
     "movimento), sollevamento col telaio da -h a 0, e sgocciolamento (fermo "
     "alla quota di trasporto). Si noti che `loaded` diventa True dal "
     "sollevamento in poi: e' il campo da cui la simulazione sa quando il "
     "pezzo comincia ad appartenere al carroponte."),
    ("c", "model.ProblemData.release_phases"),
    ("p",
     "Speculare, con due sole fasi: immersione e sgancio. Non c'e' la risalita "
     "del gancio scarico, per la ragione simmetrica a quella della presa."),

    # ==================================================================
    ("h2", "2. Il giro con la zona di cambio quota"),
    ("p",
     "Quando la stazione e' servita da una zona di cambio quota, presa e "
     "rilascio non sono piu' una sequenza verticale sopra un punto fisso: sono "
     "un GIRO che comprende due traslazioni orizzontali."),
    ("c", "model.ProblemData._pick_phases_cambio_quota"),
    ("p", "Sette fasi, che il docstring elenca in una riga:"),
    ("li", "sale a intermediate1 (gancio scarico, fermo sul punto di cambio "
           "quota);"),
    ("li", "trasla alla stazione -- prima traslazione, a vuoto;"),
    ("li", "aggancia;"),
    ("li", "solleva il telaio a intermediate2;"),
    ("li", "sgocciola;"),
    ("li", "torna al punto di cambio quota -- seconda traslazione, col pezzo;"),
    ("li", "sale in cima, alla quota di trasporto."),
    ("q",
     "LE DUE TRASLAZIONI SONO TEMPO DI PRESA. Il docstring lo sottolinea "
     "perche' e' contro l'intuizione: durante la presa il carroponte NON e' "
     "fermo. Sono le fasi che riempiono x_start, x_end e kin_x di LiftPhase, e "
     "chi campiona le posizioni deve leggerle da li'. Trattare la presa come "
     "un intervallo immobile significa proteggere dalla collisione un punto "
     "diverso da quello in cui il carroponte si trova."),
    ("p",
     "Le due traslazioni usano cinematiche DIVERSE: l'andata alla stazione e' "
     "a vuoto (kin_empty), il ritorno e' col telaio appeso (kin_loaded). Il "
     "campo `loaded` cambia alla quarta fase, il sollevamento, e da li' in poi "
     "resta True."),
    ("p",
     "Si osservi che la prima e l'ultima salita usano cinematiche diverse per "
     "lo stesso motivo: da z_basso a z_int1 il gancio e' scarico, da z_int2 "
     "alla quota di trasporto porta il telaio."),
    ("c", "model.ProblemData._release_phases_cambio_quota"),
    ("p",
     "Lo stesso giro al contrario, in sei fasi invece di sette -- manca lo "
     "sgocciolamento, che appartiene alla presa. Il carroponte finisce alla "
     "quota piu' bassa, e il docstring spiega perche' e' importante: e' da li' "
     "che riparte il rientro a vuoto."),

    ("h3", "Le due somme"),
    ("c", "model.ProblemData.pick_time_at"),
    ("c", "model.ProblemData.release_time_at"),
    ("p",
     "Due righe ciascuna: la somma delle durate delle fasi. Sono le funzioni "
     "che il modello CP-SAT chiama, e il fatto che siano una somma invece di "
     "un calcolo proprio e' tutta la garanzia di coerenza fra il numero e il "
     "disegno."),

    # ==================================================================
    ("h2", "3. bath_extra_seconds -- l'errore che costava quindici secondi"),
    ("c", "model.ProblemData.bath_extra_seconds"),
    ("p",
     "Restituisce la somma di due tempi morti, e il docstring e' lungo dieci "
     "volte il corpo. E' proporzionato: dietro c'e' un difetto vero e la sua "
     "diagnosi."),
    ("p",
     "Il gancio che ha appena sganciato deve risalire; quello che verra' a "
     "riprendere il pezzo deve ricalare. Sono due corse a vuoto che avvengono "
     "mentre il pezzo e' gia' -- o ancora -- immerso. Piu' i tempi morti di "
     "sgancio e aggancio, che il telaio passa anch'essi in fondo alla vasca."),
    ("q",
     "SU UNA LINEA CON CORSA 1500 mm SONO OLTRE QUINDICI SECONDI. Il "
     "docstring lo quantifica, ed e' il punto: non contarli non e' "
     "un'imprecisione, e' abbastanza da sforare il massimo di processo senza "
     "che nessuno lo dicesse. La formula giusta e' scritta nel docstring -- "
     "bagno = (prelievo - fine rilascio) + bath_extra -- e sono i limiti del "
     "PROCESSO ad applicarsi al bagno, non all'intervallo fra i movimenti del "
     "gancio."),
    ("p",
     "L'ultimo capoverso del docstring chiude la questione: sono i SOLI tempi "
     "morti. Tutto il resto di quello che il gancio fa fra un rilascio e la "
     "presa successiva -- traslare, salire, riscendere -- cade nell'intervallo "
     "fra i due movimenti, e li' e' gia' contato. E' la ragione per cui il "
     "corpo e' una somma di due soli termini, e non va allungato."),
    ("p",
     "Vale la pena ricordare che questa e' la funzione su cui verify.py e "
     "model.py hanno smesso di essere d'accordo -- ed e' stato quel disaccordo "
     "a rendere il verificatore capace di trovare qualcosa. Finche' "
     "condividevano la definizione sbagliata, la verifica confermava."),

    ("c", "model.ProblemData.slot_occupancy_seconds"),
    ("p",
     "Quanto un pezzo tiene occupato un POSTO, che non coincide col bagno: il "
     "telaio ingombra il posto da quando comincia a calare a quando ha finito "
     "di emergere e di sgocciolare. E' questa la grandezza da confrontare con "
     "capacity * T -- e confrontare il bagno sarebbe ottimistico, cioe' "
     "sbagliato dal lato pericoloso."),
    ("p",
     "La sottrazione di bath_extra_seconds nel mezzo evita il doppio "
     "conteggio: quei secondi stanno gia' dentro release_time_at e "
     "pick_time_at."),

    # ==================================================================
    ("h2", "4. Le durate composte"),
    ("c", "model.ProblemData.loaded_leg_seconds"),
    ("c", "model.ProblemData.horizontal_loaded_seconds"),
    ("p",
     "La prima e' la mossa per intero, la seconda la sola traslazione. Servono "
     "entrambe, e verify.py le usa tutte e due sullo stesso tratto proprio "
     "perche' controllare solo il totale lascerebbe passare una traslazione "
     "impossibile compensata da una presa piu' lunga."),
    ("c", "model.ProblemData.empty_lift_seconds"),
    ("p",
     "Quanto costa UNA corsa verticale a gancio scarico. Il docstring "
     "chiarisce che qui c'e' solo il costo: se qualcuno la faccia davvero lo "
     "decide serve_alto, ed e' argomento del terzo documento."),
    ("q",
     "SU UNA ZONA DI CAMBIO QUOTA LA CORSA E' L'INTERA CORSA DEL CARROPONTE. "
     "Non quella della vasca -- che li' e' obbligatoriamente zero -- ma "
     "corsa_totale, perche' il gancio arriva fino in fondo ed e' da li' che "
     "deve ripartire. E' il motivo per cui esiste corsa_verticale() accanto a "
     "lift_height_at(): due funzioni che sulle vasche normali danno lo stesso "
     "numero e agli estremi no."),
]


# ==========================================================================
# Documento 3 -- i rientri a vuoto e la geometria
# ==========================================================================

RIENTRI = [
    ("h1", "model.py (3) -- i rientri a vuoto, gli svincoli, la geometria"),
    ("p",
     "Terzo dei documenti su model.py. Il rientro a vuoto e' il movimento che "
     "non produce niente e decide tutto: e' quello che stabilisce se un "
     "carroponte fa in tempo, ed e' l'unico su cui il progetto abbia dovuto "
     "cambiare modello due volte."),

    # ==================================================================
    ("h2", "Il problema"),
    ("p",
     "Deposto un telaio, il carroponte deve raggiungere la mossa successiva "
     "del suo giro. Sulla maggior parte degli impianti e' una semplice "
     "traslazione: il gancio scarico resta calato e passa sotto tutto. Su "
     "altri no -- c'e' una vasca con una struttura sopra, una cappa, un "
     "coperchio -- e li' il gancio calato non passa: bisogna salire, "
     "scavalcare, riscendere."),
    ("p",
     "La prima versione trattava la cosa come una proprieta' della LINEA: un "
     "interruttore unico, traslazione_con_gancio_basso. Il difetto e' che "
     "obbligava OGNI rientro a pagare salita e discesa, anche quelli che non "
     "passavano nemmeno vicino all'ostacolo. Su una linea di dieci vasche con "
     "una sola cappa, nove rientri su dieci pagavano un pedaggio inesistente, "
     "e il takt time ne risentiva."),
    ("p",
     "Ora e' una proprieta' della VASCA, e le tre funzioni di questo documento "
     "sono la conseguenza: quando serve passare alto, da dove si sale, e come "
     "e' fatto il giro che ne risulta."),

    # ==================================================================
    ("h2", "1. serve_alto -- quando"),
    ("c", "model.ProblemData.serve_alto"),
    ("p",
     "Tre casi, e il docstring dice che sono tre facce della stessa regola: il "
     "gancio calato non puo' stare nella campata di una vasca ostacolo se non "
     "per raggiungerne il centro dal proprio svincolo."),
    ("li", "si PARTE da un ostacolo: il gancio e' calato al suo centro, e per "
           "uscire dalla sua campata deve prima salire sullo svincolo;"),
    ("li", "si ARRIVA a un ostacolo: bisogna calarsi sullo svincolo e poi "
           "traslare bassi fino al centro;"),
    ("li", "fra i due punti di approccio ne cade uno: va scavalcato."),
    ("q",
     "SI GUARDANO TUTTE LE VASCHE, NON SOLO QUELLE DELLA RICETTA. Il commento "
     "nel codice lo dice, ed e' una distinzione facile da perdere: una vasca "
     "fuori percorso -- dichiarata nell'impianto ma non usata da questa "
     "ricetta -- sta comunque sulla rotaia e fa comunque ostacolo. Iterare su "
     "`route` invece che su `tanks` darebbe rientri che attraversano una "
     "struttura che c'e' davvero."),
    ("p",
     "Il confronto usa i punti di APPROCCIO, non le posizioni delle stazioni: "
     "con una zona di cambio quota il rientro comincia e finisce sul punto di "
     "cambio quota, e l'intervallo da esaminare e' quello."),
    ("p",
     "Il caso a == b restituisce False: due tappe nella stessa vasca non "
     "richiedono nessun rientro, e senza questa riga l'intervallo degenere "
     "confonderebbe il confronto."),

    # ==================================================================
    ("h2", "2. svincolo_verso -- da dove"),
    ("c", "model.ProblemData.svincolo_verso"),
    ("p",
     "Si sceglie lo svincolo dalla parte in cui si deve andare. Non e' un "
     "dettaglio di ottimizzazione: e' quello che evita di tornare indietro "
     "prima di ripartire, e rende il tratto percorso basso il piu' corto "
     "possibile."),
    ("p",
     "Se da quella parte non ce n'e', si prende l'altro. Se non ce n'e' "
     "nessuno, si restituisce la posizione della vasca stessa -- e quello "
     "significa che li' il gancio sale e scende dov'e', perche' quella vasca "
     "non e' un ostacolo."),
    ("q",
     "SU UNA ZONA DI CAMBIO QUOTA LO SVINCOLO E' IL PUNTO DI CAMBIO QUOTA. La "
     "prima riga del corpo, e il docstring la motiva: e' li', e SOLO li', che "
     "il carroponte puo' cambiare quota -- che il gancio sia carico o vuoto. "
     "E' anche il motivo per cui il ripiego di questa funzione e la logica "
     "delle zone di cambio quota non entrano mai in conflitto."),
    ("p",
     "La ricaduta interessante e' che il percorso risultante NON e' detto sia "
     "monotono: se da una parte lo svincolo non e' dichiarato si esce "
     "dall'altra, e allora il carroponte torna indietro prima di ripartire. E' "
     "il fatto che rende necessario il modo in cui e' scritta la funzione "
     "successiva."),

    # ==================================================================
    ("h2", "3. tratte_rientro -- l'unica definizione"),
    ("c", "model.tratte_rientro"),
    ("p",
     "E' una funzione di modulo e non un metodo, ma e' fra le piu' importanti "
     "del progetto. Il docstring dichiara il suo ruolo: e' L'UNICA DEFINIZIONE "
     "del rientro, e da qui discendono tutte e tre le cose che se ne devono "
     "sapere."),
    ("t", [
        ["domanda", "chi risponde", "come"],
        ["quanto dura", "empty_leg_seconds", "somma le durate"],
        ["che aspetto ha", "_segmenti_rientro", "ne fa dei Segment"],
        ["dove passa e quando", "near_boundary", "ne ricava le finestre del "
                                                 "vincolo di non collisione"],
    ]),
    ("q",
     "AVERNE UNA SOLA NON E' ELEGANZA. Il docstring lo dice in modo netto: e' "
     "quello che impedisce al vincolo di proteggere un percorso diverso da "
     "quello che il carroponte fa davvero. Se la durata la calcolasse una "
     "funzione e il percorso ne descrivesse un'altra, il modello garantirebbe "
     "la non collisione su un giro immaginario -- e il carroponte ne "
     "farebbe un altro."),
    ("p",
     "Il risultato ha due forme. Senza ostacoli da scavalcare, una sola tratta "
     "orizzontale: il gancio resta calato da capo a fondo e non paga nessuna "
     "corsa verticale. Con un ostacolo, cinque tratte: traslata bassa fino "
     "allo svincolo, salita, traslata in alto, discesa sullo svincolo di "
     "arrivo, traslata bassa fino alla vasca."),
    ("q",
     "UNA TRATTA CON da == a E' UNA CORSA VERTICALE. Il docstring lo dichiara "
     "e ne dice la posta: lungo la rotaia il carroponte e' FERMO, e chi ne "
     "campiona le posizioni deve trattarla come tale. Crederla un movimento "
     "'e' l'errore che ha gia' prodotto due carroponti nello stesso punto con "
     "stato OPTIMAL'. E' la frase piu' seria del modulo, ed e' scritta al "
     "passato perche' e' successo."),
    ("p",
     "L'ultimo capoverso del docstring spiega perche' le tratte vanno "
     "guardate una per una invece di dedurre tutto dai due estremi: il "
     "percorso non e' detto sia monotono. Un rientro che esce dalla parte "
     "sbagliata perche' da quella giusta lo svincolo non e' dichiarato passa "
     "per posizioni che non stanno fra partenza e arrivo -- e un vincolo "
     "costruito sui soli estremi non le coprirebbe."),
    ("c", "model.ProblemData.empty_leg_seconds"),
    ("p",
     "Una somma. Il docstring descrive a parole i due casi e chiude con la "
     "ripartizione delle responsabilita': il giro alto sta QUI e non dentro "
     "presa e rilascio perche' e' un movimento che avviene FRA due mosse, e "
     "chi lo paga e' lo spostamento -- non il pezzo, che nel frattempo e' in "
     "bagno."),
    ("c", "model.ProblemData.horizontal_empty_seconds"),
    ("p",
     "La singola tratta, non il giro. La distinzione e' quella che verify.py "
     "usa per controllare i rientri tratta per tratta invece che nel loro "
     "insieme."),

    # ==================================================================
    ("h2", "4. zone_layout_conflicts -- la geometria che il modello non sa gestire"),
    ("c", "model.zone_layout_conflicts"),
    ("p",
     "Il vincolo di non collisione e' costruito attorno a ogni stazione di "
     "CONFINE fra due zone adiacenti, e assume due cose: che la zona di "
     "sinistra stia tutta da un lato del confine e quella di destra tutta "
     "dall'altro, e che due zone non adiacenti non si sovrappongano nello "
     "spazio."),
    ("q",
     "NULLA OBBLIGA LE VASCHE A ESSERE ORDINATE LUNGO LA ROTAIA. E' il punto "
     "del docstring: move_distance usa un valore assoluto e accetterebbe "
     "qualunque disposizione. Una linea con le posizioni non monotone e' un "
     "dato perfettamente valido per le strutture, e completamente fuori "
     "portata per il meccanismo di non collisione. Va rilevata, perche' il "
     "modello non ha modo di accorgersene da solo: costruirebbe il vincolo "
     "attorno a un confine che non separa niente."),
    ("p",
     "Il primo controllo determina da che parte sta la zona di destra "
     "(`lato`), poi verifica che nessuna stazione della zona di sinistra "
     "sconfini e nessuna della destra faccia il contrario. La tolleranza di "
     "1e-9 ammette le stazioni esattamente sul confine, che e' il caso normale "
     "-- la stazione di confine appartiene a entrambe."),
    ("p",
     "Il secondo controlla le zone NON adiacenti (j parte da i+2): fra due "
     "zone lontane nell'ordine delle mosse il modello non impone niente, "
     "perche' presuppone che siano lontane anche nello spazio. Se i loro "
     "tratti di rotaia distano meno del minimo richiesto, quella presunzione "
     "cade."),
    ("p",
     "La funzione restituisce una lista di STRINGHE gia' leggibili, non di "
     "codici. E' quello che permette di usarla in due modi opposti senza "
     "duplicarla: solve() la usa per rifiutare, verify.py per avvisare. Le due "
     "analisi non possono divergere perche' sono la stessa funzione."),
]


# ==========================================================================
# Documento 4 -- solve()
# ==========================================================================

SOLVE = [
    ("h1", "model.py (4) -- solve() riga per riga"),
    ("p",
     "Quarto dei documenti su model.py, e il piu' lungo: solve() occupa 643 "
     "righe, un quarto del modulo. Costruisce il modello CP-SAT del problema e "
     "lo risolve. Ogni blocco di codice e' estratto dal sorgente al momento "
     "della generazione: quello che si legge qui e' quello che c'e' nel file."),
    ("p",
     "Presuppone i primi tre documenti -- strutture, fasi verticali, rientri "
     "-- perche' qui le durate non si calcolano: si chiamano."),

    # ==================================================================
    ("h2", "Che cosa fa solve(), in una pagina"),
    ("p",
     "Dei gradi di liberta' di un ciclogramma, solve() ne riceve uno gia' "
     "deciso -- l'assegnazione, cioe' le zone -- e cerca gli altri: il takt "
     "time, che minimizza, il tempo che ogni pezzo passa in ciascuna vasca, e "
     "dove ogni carroponte passa il tempo morto del rientro a vuoto."),
    ("p", "Il modello si compone di quattro blocchi, nell'ordine del codice:"),
    ("li", "1) la CATENA DEL PEZZO: quando ogni pezzo viene prelevato da ogni "
           "vasca, con i limiti di permanenza del processo;"),
    ("li", "1-bis e 2-bis) la CAPIENZA delle vasche: quanti pezzi ci stanno "
           "dentro contemporaneamente;"),
    ("li", "2) il CIRCUITO di ciascun carroponte: il giro che compie in un "
           "periodo, con l'ordine di visita libero;"),
    ("li", "3) la NON COLLISIONE fra carroponti adiacenti, che e' il vincolo "
           "difficile e occupa piu' della meta' della funzione."),
    ("q",
     "UNITA' E TICK. Nel modello tutti i tempi sono TICK INTERI, non secondi: "
     "CP-SAT lavora su interi. Le posizioni restano millimetri in virgola "
     "mobile, perche' non entrano mai come variabili: le vasche sono ferme, "
     "quindi ogni distanza e ogni tempo di percorrenza sono COSTANTI note "
     "prima di risolvere. E' questa asimmetria la ragione per cui il modello "
     "resta lineare, e per cui un problema di scheduling con profili "
     "cinematici trapezoidali si puo' scrivere in CP-SAT."),

    # ==================================================================
    ("h2", "1. Il contratto d'ingresso"),
    ("c", "model.solve", None, "    # Import posticipato"),
    ("p",
     "solve() NON sceglie le zone: le riceve. La scelta automatica sta fuori, "
     "in solve_auto_zones(), che enumera le suddivisioni possibili e chiama "
     "solve() su ciascuna. E' una separazione voluta: mettere anche le zone "
     "dentro il modello CP-SAT si potrebbe fare, ma renderebbe il modello "
     "molto piu' complesso e difficile da validare."),
    ("p",
     "Il messaggio di errore non si limita a dire che manca un dato: dice "
     "quale funzione usare per ottenerlo. E' la regola dei messaggi del "
     "progetto."),
    ("p",
     "Il secondo controllo rifiuta le geometrie che il vincolo di non "
     "collisione non sa rappresentare, usando zone_layout_conflicts -- la "
     "stessa funzione che verify.py usa per AVVISARE. Il messaggio spiega "
     "l'assunzione violata e chiude con due vie d'uscita concrete."),
    ("q",
     "allow_unsafe_layout SALTA QUEL CONTROLLO. Esiste per lo studio del "
     "modello, non per l'uso normale: le soluzioni prodotte cosi' possono "
     "contenere collisioni vere, che il verificatore indipendente poi segnala. "
     "Il valore predefinito e' quello sicuro, ed e' giusto che lo sia -- ma "
     "vale la pena sapere che esiste, perche' e' il modo per vedere cosa "
     "succederebbe senza il controllo."),

    ("h3", "L'import posticipato, e i tempi precalcolati"),
    ("c", "model.solve", "    # Import posticipato", "    # -- Variabili di takt time"),
    ("p",
     "`from ortools...` sta QUI dentro e non in testa al file. Il commento ne "
     "da' la ragione, ed e' architetturale: cosi' le dataclass, la "
     "ricostruzione delle traiettorie e build_solution restano usabili e "
     "TESTABILI anche senza OR-Tools installato. E' quello che permette a "
     "test_verify.py di girare senza il solutore."),
    ("p",
     "travel_loaded e' un elenco di costanti: le durate delle mosse, gia' in "
     "tick. Non sono variabili perche' non possono esserlo -- le vasche sono "
     "ferme e le cinematiche sono date. Precalcolarle qui evita di ricalcolare "
     "un profilo trapezoidale dentro cicli che girano decine di migliaia di "
     "volte."),
    ("q",
     "escape_ticks E' UNA MAGGIORAZIONE, E DEVE ESSERLO. Restituisce un limite "
     "SUPERIORE al tempo che serve a coprire i primi (o gli ultimi) x "
     "millimetri di uno spostamento che parte da fermo. Il docstring "
     "argomenta quale sia il caso peggiore: uno spostamento lungo esattamente "
     "x, che deve anche decelerare -- piu' lento di un tratto iniziale di uno "
     "spostamento piu' lungo, dove il carroponte accelera e basta. E si prende "
     "la piu' lenta delle due cinematiche. Sottostimarlo qui significherebbe "
     "dichiarare il carroponte fuori dalla fascia di esclusione mentre ci sta "
     "ancora dentro."),

    ("h3", "Domini e orizzonte"),
    ("c", "model.solve", "    # -- Variabili di takt time", "    # -- 1) Catena di flusso pezzo"),
    ("p",
     "Tv e' la variabile del takt time, e l'unica che compare nell'obiettivo. "
     "L'orizzonte e' una maggiorazione generosa del tempo che un pezzo impiega "
     "ad attraversare la linea: serve solo a dare domini finiti."),
    ("p",
     "DEP_MAX invece e' calcolato con attenzione, e il commento spiega "
     "perche': dep_hi e arr_lo sarebbero comunque limitati dai vincoli del "
     "modello, ma dichiararlo nel DOMINIO tiene piccolo il numero di "
     "traslazioni da generare nel vincolo di non collisione. E' una di quelle "
     "righe che non cambiano cosa il modello significa e cambiano molto quanto "
     "e' grande."),
    ("p",
     "_as_intvar materializza un'espressione in un vero IntVar. Il docstring "
     "dice che serve alla robustezza fra versioni di OR-Tools: passare sempre "
     "IntVar puri a NewIntervalVar invece di espressioni composte."),

    # ==================================================================
    ("h2", "2. La catena del pezzo, e la capienza"),
    ("c", "model.solve", "    # -- 1) Catena di flusso pezzo", "    # -- 2) Per ciascun carroponte"),
    ("p",
     "actual_time[k] e' l'istante in cui un pezzo di riferimento viene "
     "prelevato dalla stazione k. Il primo e' fissato a zero: e' l'origine dei "
     "tempi. Ogni successivo e' vincolato fra l'arrivo piu' la permanenza "
     "minima e l'arrivo piu' la massima."),
    ("q",
     "IL VINCOLO SI SPOSTA, NON CAMBIA FORMA. E' il commento piu' importante "
     "del blocco. I limiti di processo valgono sul BAGNO, che comprende anche "
     "le corse a vuoto del gancio che vanno e vengono col pezzo gia' immerso. "
     "Fra i due istanti che il modello maneggia -- fine del rilascio e inizio "
     "della presa -- resta quindi una finestra piu' STRETTA, di una costante "
     "nota in anticipo: bath_extra_seconds. Il modello sottrae quella costante "
     "dai due limiti e continua a scrivere lo stesso vincolo lineare. E' la "
     "correzione dell'errore che aveva fatto passare una linea con sei vasche "
     "su dieci fuori tolleranza."),
    ("p",
     "Il max(0, ...) sul minimo copre il caso di un bagno minimo piccolo: il "
     "gancio che deposita si toglie di mezzo prima che arrivi quello che "
     "preleva, quindi la finestra non puo' diventare negativa."),
    ("p",
     "La capienza a tappa singola e' tre righe e il commento la dimostra: i "
     "pezzi entrano ogni T e ciascuno occupa un posto per `slot_occupancy` "
     "secondi, quindi i presenti sono ceil(occupazione / T). Imporre "
     "occupazione <= capacity * T e' ESATTAMENTE equivalente. E poiche' "
     "capacity e' una costante intera e Tv una variabile, il prodotto resta "
     "lineare -- il vincolo non costa praticamente nulla."),

    # ==================================================================
    ("h2", "3. Il circuito: l'ordine di visita libero"),
    ("p",
     "E' la scelta di modellazione che distingue questa versione dalla prima. "
     "Nella v1 ogni carroponte percorreva un giro sequenziale fisso: lo, lo+1, "
     "..., hi, poi un unico rientro. Qui puo' visitare le mosse della propria "
     "zona in QUALSIASI ordine."),
    ("p",
     "La differenza non e' un raffinamento: e' quello che permette a un "
     "carroponte di andare a servire un'altra mossa mentre un pezzo e' ancora "
     "a bagno in una vasca lenta, invece di restare fermo ad aspettare. Con "
     "l'ordine fisso, una zona il cui contenuto a calendario supera il takt "
     "time e' infattibile; con l'ordine libero, spesso no."),

    ("h3", "La fase locale, e come resta lineare"),
    ("c", "model.solve", "    # -- 2) Per ciascun carroponte", "        if n_h == 1:"),
    ("p",
     "Il problema: actual_time[k] e' un istante ASSOLUTO, e due mosse della "
     "stessa zona possono essere separate da parecchi periodi -- succede "
     "sempre quando una vasca ha un tempo di processo lungo. Il giro del "
     "carroponte pero' si ragiona DENTRO un periodo."),
    ("p",
     "Serve quindi local_pick[k] = actual_time[k] mod T. Ma il modulo fra due "
     "VARIABILI non e' lineare, e CP-SAT non lo accetta direttamente."),
    ("q",
     "LA SOLUZIONE E' UNA RICERCA SUI GIRI. Per ogni mossa si creano n_shifts "
     "letterali booleani, uno per ciascun numero possibile di periodi interi, "
     "e si impone lp == actual_time[k] - m*Tv sotto il letterale m-esimo, con "
     "AddExactlyOne a scegliere. Il prodotto m*Tv e' fra una COSTANTE e una "
     "variabile, quindi lineare. E' il trucco che tiene tutto il modello "
     "dentro la programmazione lineare intera: si sostituisce un'operazione "
     "non lineare con un'enumerazione finita di casi lineari. Il prezzo e' "
     "n_shifts letterali per mossa."),
    ("p",
     "`finish[k]` e' semplicemente local_pick[k] piu' la durata della mossa: "
     "l'istante in cui il pezzo e' stato consegnato e il carroponte e' libero."),

    ("h3", "Il caso di una sola mossa"),
    ("c", "model.solve", "        if n_h == 1:", "        # -- circuito generale"),
    ("p",
     "Con una sola mossa nella zona non c'e' nessun ordine da scegliere: il "
     "giro e' andata e ritorno. Il codice lo tratta a parte perche' AddCircuit "
     "su un solo nodo non ha senso, e produce comunque la stessa struttura "
     "dati -- un unico 'arco' -- cosi' che il vincolo di non collisione, piu' "
     "sotto, non debba distinguere i due casi."),
    ("p",
     "E' un caso frequentissimo: una linea con un carroponte per ogni "
     "trasporto, o le zone di estremita' di una linea lunga."),

    ("h3", "AddCircuit"),
    ("c", "model.solve", "        # -- circuito generale", "        # -- da quale mossa comincia il giro"),
    ("p",
     "Si crea un letterale booleano per ogni arco possibile fra due mosse "
     "diverse, e AddCircuit impone che gli archi scelti formino un unico "
     "circuito hamiltoniano: il carroponte tocca tutte le sue mosse "
     "esattamente una volta per periodo."),

    ("h3", "Da quale mossa comincia il giro"),
    ("c", "model.solve", "        # -- da quale mossa comincia il giro", "        # -- variabili libere di confine"),
    ("p",
     "Il giro e' un CICLO: uno dei suoi archi attraversa la fine del periodo, e "
     "a quello -- e solo a quello -- si somma un T, perche' il prelievo a cui "
     "porta appartiene al ciclo dopo. Quale sia lo decide il solutore: "
     "`inizio[k]` vale 1 sulla mossa a cui il periodo si richiude."),
    ("p",
     "La scelta viene poi materializzata in `bersaglio[k]`: l'istante entro cui "
     "bisogna essere pronti per il prelievo della mossa k, cioe' la sua fase "
     "piu' un periodo se e' li' che il giro si richiude. Da quel punto in poi "
     "il +T non compare piu' da nessuna parte: ogni vincolo si scrive una volta "
     "sola, contro `bersaglio[k2]`."),
    ("q",
     "LA PRIMA STESURA NON FACEVA COSI', E SI VEDEVA. Condizionava ogni "
     "vincolo e ogni intervallo su `inizio[k2]`, in due versioni -- col +T e "
     "senza -- ciascuna sotto la propria coppia di letterali. E' corretto, e "
     "costa il doppio: su una zona di n mosse gli archi sono n*(n-1), quindi "
     "una scelta che riguarda la MOSSA veniva ripetuta su ogni ARCO che ci "
     "arriva. Una variabile intera per mossa -- n variabili invece di n*(n-1) "
     "duplicazioni -- dice la stessa cosa e la dice una volta."),
    ("q",
     "QUANTO COSTA LA LIBERTA' IN PIU'? Misurato: 56 configurazioni, stesso "
     "limite di dieci secondi, versione col giro obbligato a partire dal "
     "confine contro versione attuale. Tempo totale 1078 s contro 1070 s -- "
     "uguale. Esiti: OPTIMAL da 21 a 26, FEASIBLE da 21 a 28, scaduti "
     "(UNKNOWN) da 14 a 2. Togliere la restrizione non costa: RENDE il "
     "modello piu' facile, perche' quei ciclogrammi non erano vicoli ciechi "
     "da esplorare, erano soluzioni da trovare."),
    ("q",
     "E ATTENZIONE A COSA SI MISURA. Quasi tutte le configurazioni saturano "
     "il limite di tempo, quindi le due versioni ci mettono uguale per "
     "costruzione: il tempo non distingue niente. A distinguere e' la "
     "colonna degli esiti. Una misura di prestazioni che guardasse solo il "
     "cronometro qui direbbe 'nessuna differenza' su una differenza grossa."),
    ("q",
     "PRIMA ERA FISSATO SU lo_h, E NON ERA UNA CONVENZIONE INNOCUA. Il vincolo "
     "per ogni arco che non portava a lo_h era `finish[k1] + t_vuoto <= "
     "local_pick[k2]`, e poiche' finish[k1] e' maggiore di local_pick[k1] ne "
     "seguiva local_pick[k2] > local_pick[k1]: lungo il giro le fasi DOVEVANO "
     "crescere. Partendo da lo_h, questo OBBLIGAVA lo_h a essere la mossa piu' "
     "anticipata del carroponte -- una restrizione che nessuno aveva scelto e "
     "che non era scritta da nessuna parte."),
    ("q",
     "COSA COSTAVA. I ciclogrammi in cui un carroponte comincia il giro da "
     "un'altra mossa non stavano nello spazio di ricerca: il solutore li "
     "dichiarava INFEASIBLE senza averli mai considerati. Su una linea vera di "
     "diciassette mosse questo ha fatto dichiarare impossibile con quattro "
     "carroponti una linea che con quattro carroponti si fa -- e la prova e' "
     "che lo stesso ciclogramma, composto a mano, supera la verifica "
     "indipendente con 1810 mm di margine sulla separazione. Un modello "
     "incompleto non sbaglia le soluzioni che trova: sbaglia quelle che dice "
     "non esistere."),

    ("h3", "Le due variabili di confine"),
    ("c", "model.solve", "        # -- variabili libere di confine", "        # Istanti di partenza/arrivo"),
    ("p",
     "dep_hi e' l'istante in cui il carroponte lascia il confine superiore "
     "della zona, arr_lo quello in cui arriva pronto al confine inferiore. "
     "Sono variabili LIBERE -- il modello non le lega a un arco specifico -- e "
     "servono a due cose insieme: ricostruire la traiettoria e costruire il "
     "vincolo di non collisione ai confini."),
    ("p",
     "dep_hi e' vincolato a stare dopo la consegna della mossa hi_h, e a "
     "permettere l'arrivo in tempo a qualunque mossa l'arco uscente da hi_h "
     "punti. arr_lo, simmetricamente, deve essere dopo l'arrivo da qualunque "
     "mossa l'arco entrante in lo_h provenga, e prima del prelievo di lo_h."),
    ("q",
     "DEL PRELIEVO DI QUESTO PERIODO O DEL PROSSIMO? E' esattamente la domanda "
     "a cui risponde `bersaglio[lo_h]`, e infatti il vincolo si scrive "
     "`arr_lo <= bersaglio[lo_h]` e basta. Le due cose sono indipendenti e "
     "vanno tenute separate: dep_hi e arr_lo riguardano le STAZIONI di confine "
     "-- e' su quelle che si costruisce la non collisione -- mentre il +T "
     "riguarda il PERIODO. Per un lungo tratto hanno condiviso la stessa "
     "condizione perche' il modello obbligava le due mosse a coincidere."),
    ("p",
     "L'ultimo blocco tratta il caso in cui l'arco hi_h -> lo_h sia proprio "
     "quello scelto: allora dep_hi e arr_lo descrivono lo STESSO spostamento, "
     "e vanno legati esattamente invece che con due disuguaglianze "
     "indipendenti. Senza, il modello potrebbe piazzarli a distanza arbitraria "
     "e la traiettoria ricostruita avrebbe un buco."),

    ("h3", "Gli archi, e la convenzione che va tenuta"),
    ("c", "model.solve", "        # Istanti di partenza/arrivo", "    # -- 2-bis)"),
    ("q",
     "LE CONVENZIONI DEVONO ESSERE IDENTICHE A _build_zone_trajectory. Il "
     "commento lo scrive in chiaro, ed e' la dipendenza piu' fragile del "
     "modulo: qui si decide QUANDO ciascun trasferimento a vuoto avviene, e "
     "piu' avanti un'altra funzione lo disegna. Se le due convenzioni "
     "divergessero, il vincolo di non collisione proteggerebbe una traiettoria "
     "diversa da quella poi disegnata -- e il disegno sarebbe quello vero."),
    ("p",
     "`span_end` chiude l'attesa dopo l'arrivo, ed e' `bersaglio[k2]`: un "
     "estremo che dipende da una scelta del solutore, ma che resta UNA "
     "variabile. L'arco porta quindi un solo intervallo di attesa, condizionato "
     "al solo letterale dell'arco -- che e' anche l'unica condizione di "
     "presenza che un intervallo opzionale di CP-SAT accetta."),
    ("p",
     "Le tre convenzioni sono: chi parte dal confine alto parte a dep_hi; chi "
     "arriva al confine basso arriva ad arr_lo (e quindi parte a arr_lo meno "
     "la durata); tutti gli altri ripartono appena consegnato. L'ultima e' una "
     "scelta arbitraria fra le tante possibili -- il carroponte potrebbe anche "
     "aspettare -- ed e' arbitraria in modo SICURO solo finche' chi disegna fa "
     "la stessa scelta."),

    # ==================================================================
    ("h2", "4. La capienza quando una vasca compare piu' volte"),
    ("c", "model.solve", "    # -- 2-bis)", "    # -- 3) Non collisione"),
    ("p",
     "Il vincolo 1-bis copre esattamente una vasca usata una volta sola nella "
     "ricetta. Se la stessa vasca fisica compare in due o piu' tappe, i pezzi "
     "delle diverse tappe si contendono gli stessi posti."),
    ("q",
     "SOMMARE I MASSIMI SAREBBE CAUTELATIVO E SBAGLIATO. Il commento lo dice: "
     "le due tappe potrebbero essere SFASATE fra loro, e sommare i massimi "
     "darebbe un numero piu' alto del vero. Per una vasca a posto singolo "
     "scarterebbe soluzioni perfettamente valide. La formulazione esatta e' un "
     "vincolo CUMULATIVO: ogni pezzo occupa un posto per un intervallo, gli "
     "intervalli si ripetono ogni T, e in nessun istante se ne possono "
     "sovrapporre piu' di capacity."),
    ("p",
     "La replica su piu' periodi (da k_lo a k_hi) e' necessaria perche' un "
     "intervallo puo' essere piu' lungo di un periodo. Il commento chiarisce "
     "la proprieta' che rende la cosa sicura: ai bordi il vincolo risulta solo "
     "piu' DEBOLE, mai piu' forte -- quindi replicare abbastanza da coprire "
     "una finestra centrale basta, e non si rischia di rifiutare soluzioni "
     "valide per un difetto di copertura."),
    ("p",
     "E' lo stesso ragionamento che verify.py rifa' in _max_sovrapposizioni, "
     "in Python puro e senza solutore."),

    # ==================================================================
    ("h2", "5. La non collisione -- l'idea"),
    ("c", "model.solve", "    # -- 3) Non collisione", "    def _make_interval"),
    ("p",
     "Trenta righe di commento prima di una riga di codice, e sono la parte "
     "piu' densa del progetto. Vale la pena seguirle passo per passo."),
    ("p",
     "Attorno alla stazione di confine b fra due zone adiacenti, sia a(t) la "
     "distanza del carroponte di sinistra da b e c(t) quella del carroponte di "
     "destra. Poiche' le due zone stanno su lati opposti -- ed e' quello che "
     "zone_layout_conflicts garantisce -- la distanza fra i due carroponti "
     "vale esattamente a(t) + c(t). Serve dunque:"),
    ("p", "        a(t) + c(t)  >=  D        con D = ingombro + sicurezza"),
    ("p",
     "Questa condizione non e' esprimibile in CP-SAT: a e c non sono variabili "
     "del modello, sono funzioni del tempo che dipendono da tutto il giro."),
    ("q",
     "LA MOSSA CHE RENDE TUTTO POSSIBILE. Per ogni soglia r si puo' imporre "
     "una condizione LOCALE e lineare: 'mai contemporaneamente a(t) < r e "
     "c(t) <= D - r'. Questa vieta solo configurazioni con a + c < D, quindi "
     "non taglia mai nulla di sicuro. E imponendola su una griglia di soglie "
     "abbastanza fitta si copre tutta la condizione: se a + c < D, basta una "
     "soglia nell'intervallo (a, D - c], che e' lungo piu' del passo della "
     "griglia. Una disuguaglianza fra due funzioni del tempo diventa cosi' una "
     "collezione di vincoli di NON SOVRAPPOSIZIONE fra intervalli -- che e' "
     "esattamente cio' che CP-SAT sa fare bene."),
    ("p",
     "Il passo delta e' clearance_step_mm, e portando il bersaglio a D + delta "
     "la distanza GARANTITA torna esattamente D: delta e' tutto e solo "
     "l'eccesso di severita', cioe' lo stesso passo letto dall'altro lato."),
    ("p",
     "Resta da calcolare 'a(t) < r', cioe' quando il carroponte e' entro r dal "
     "confine. E' un'unione di intervalli temporali: le soste su stazioni "
     "vicine, e i tratti di percorso che entrano nella fascia con il margine "
     "di escape_ticks. E' il compito di near_boundary."),
    ("p",
     "L'ultimo capoverso dice cosa questo sostituisce: il vecchio vincolo "
     "riservava l'intera sosta sulla SOLA stazione di confine, ed era sano "
     "solo se nessun'altra stazione cadeva entro D -- oltre a essere piu' "
     "cautelativo di quanto serva."),

    ("h3", "_make_interval"),
    ("c", "model.solve", "    def _make_interval", "    def near_boundary"),
    ("p",
     "Costruisce un intervallo CP-SAT, opzionale se gli si passa un letterale. "
     "Il docstring spiega perche' con lit falso start ed end restano LIBERI: "
     "le espressioni che li definiscono hanno senso solo se l'arco "
     "corrispondente e' effettivamente scelto. Forzarli comunque "
     "aggiungerebbe vincoli su una traiettoria che non esiste."),

    # ==================================================================
    ("h2", "6. near_boundary -- quando si e' vicini al confine"),
    ("c", "model.solve", "    def near_boundary", "        def fermo"),
    ("p",
     "Il giro di un periodo si scompone in TRATTE elementari, e ciascuna e' "
     "una di due cose: una sosta -- il carroponte sta fermo in un punto, o si "
     "muove dentro un intervallo noto -- oppure una traslazione monotona fra "
     "due punti. Su una tratta monotona la distanza dal confine e' monotona, "
     "quindi bastano i due estremi; su una sosta si guarda tutto l'intervallo."),
    ("q",
     "NON SI FANNO STIME. E' la frase del docstring che vale tutto il "
     "paragrafo: le tratte del rientro a vuoto vengono da tratte_rientro, "
     "cioe' dalla STESSA definizione che il disegno usa per farne dei "
     "segmenti. Il vincolo protegge quindi il percorso vero, corse verticali "
     "comprese -- ed e' proprio dimenticarsene che ha gia' prodotto DUE VOLTE "
     "due carroponti nello stesso punto. Una versione precedente stimava il "
     "rientro dai soli estremi, e su un percorso non monotono la stima era "
     "falsa."),

    ("h3", "fermo"),
    ("c", "model.solve", "        def fermo", "        def traslazione"),
    ("p",
     "Un tratto in cui il carroponte resta dentro l'intervallo [a,b] senza "
     "percorrerlo in un verso solo: una sosta sopra una stazione (a == b), la "
     "corsa verticale del gancio su uno svincolo, oppure il vai-e-torna della "
     "presa su una zona di cambio quota."),
    ("p",
     "Il conto di `dentro` e' la distanza fra il confine e l'intervallo, zero "
     "se il confine ci cade dentro. Se e' minore del raggio, l'intero tratto "
     "entra nella fascia."),
    ("q",
     "SI STA DENTRO TUTTO IL TEMPO, E VA BENE COSI'. Il docstring difende "
     "l'approssimazione: stimare quando si entra e quando si esce vorrebbe "
     "dire modellare il vai-e-torna, e per guadagnare qualche decimo su una "
     "sosta corta non vale la pena rischiare di sbagliarlo. E' "
     "un'approssimazione dal lato SICURO -- si dichiara vicini piu' a lungo "
     "del vero -- ed e' la direzione giusta in cui sbagliare."),

    ("h3", "traslazione"),
    ("c", "model.solve", "        def traslazione", "        def fasi_verticali"),
    ("p",
     "Quattro casi, e il quarto e' quello che si vede solo per assenza. Se "
     "entrambi gli estremi sono dentro la fascia, ci si sta per tutta la "
     "tratta. Se solo la partenza e' dentro, si esce durante la traslazione, e "
     "il tempo speso dentro e' limitato da escape_ticks del residuo. Se solo "
     "l'arrivo e' dentro, simmetricamente, si entra. Se sono entrambi fuori "
     "NON SI FA NIENTE: la distanza dal confine e' monotona lungo la tratta, "
     "quindi non si entra mai."),
    ("p",
     "L'ultimo caso e' corretto solo grazie alla monotonia, ed e' il motivo "
     "per cui il rientro va spezzato in tratte monotone invece di essere "
     "trattato come un unico spostamento fra i due estremi."),

    ("h3", "fasi_verticali"),
    ("c", "model.solve", "        def fasi_verticali", '        for k in zd["moves"]:'),
    ("p",
     "Le finestre di una presa o di un rilascio, fase per fase. Su una "
     "stazione normale tutte le fasi sono ferme sullo stesso punto e ne esce "
     "una finestra sola, identica a quella che si otterrebbe trattando la "
     "presa come un blocco unico."),
    ("q",
     "SU UNA ZONA DI CAMBIO QUOTA NO. Li' in mezzo ci sono due traslazioni, e "
     "il carroponte per un buon pezzo della presa sta LONTANO dalla stazione. "
     "Il docstring dice cosa costerebbe ignorarlo: trattare tutto il giro come "
     "una sosta sarebbe sicuro ma sprecone -- venti secondi bloccati per una "
     "vicinanza che dura un istante -- e basterebbe a rendere INFATTIBILI "
     "linee che non lo sono. E' successo: una versione precedente trattava la "
     "presa come un blocco e una linea stretta usciva INFEASIBLE."),
    ("p",
     "L'accorpamento delle fasi ferme consecutive sullo stesso punto e' quello "
     "che tiene il modello della stessa dimensione di prima sulle linee senza "
     "cambio quota: tre fasi ferme diventano una finestra sola, non tre."),
    ("p",
     "Da notare che i tick si calcolano sul tempo CUMULATO (`secondi`) e non "
     "fase per fase. E' lo stesso accorgimento che ritorna piu' sotto sulle "
     "tratte del rientro, e serve a non lasciare buchi da arrotondamento fra "
     "una finestra e la successiva."),

    ("h3", "Le mosse"),
    ("c", "model.solve", '        for k in zd["moves"]:', '        for arco in zd["archi"].values():'),
    ("p",
     "Ogni mossa in tre pezzi: la presa (fase per fase), la traslazione col "
     "pezzo fra i due punti di APPROCCIO, il rilascio (fase per fase). Il "
     "letterale e' None perche' le mosse ci sono sempre: non dipendono da "
     "quale arco il solutore sceglie."),

    ("h3", "Gli archi"),
    ("c", "model.solve", '        for arco in zd["archi"].values():', "    # Quante traslazioni di T servono"),
    ("p",
     "Per ogni arco possibile, e per ogni ALTERNATIVA di quell'arco: l'attesa "
     "prima di partire, le tappe del rientro una per una, la sosta nella vasca "
     "in mezzo se l'alternativa ne prevede una, l'attesa dopo essere arrivati. "
     "Tutto sotto il letterale dell'alternativa, quindi vincolante solo se il "
     "solutore sceglie quell'arco percorso in quel modo. Con "
     "max_soste_intermedie a zero -- o su un arco senza vasche candidate -- "
     "l'alternativa e' una sola e questo giro e' identico a quello di prima."),
    ("p",
     "Le tratte si distinguono per forma: `xa == xb` e' una corsa verticale, e "
     "va trattata come una sosta -- lungo la rotaia il carroponte e' fermo. E' "
     "esattamente l'avvertimento del docstring di tratte_rientro, applicato."),
    ("q",
     "I TICK SI CONTANO SUL CUMULATO. Il commento spiega la ragione precisa: "
     "cosi' l'ultimo confine coincide con T_(empty_leg_seconds), che e' quello "
     "che il modello ha usato per legare `arrive` a `depart`. Convertendo "
     "tratta per tratta, la somma degli arrotondamenti potrebbe non coincidere "
     "con l'arrotondamento della somma, e fra le tratte si aprirebbero buchi "
     "di un tick -- istanti in cui il carroponte non e' coperto da nessuna "
     "finestra."),

    # ==================================================================
    ("h2", "7. Le soglie, e la generazione dei vincoli"),
    ("c", "model.solve", "    # Quante traslazioni di T servono", "    n_sep_constraints = 0"),
    ("p",
     "Le finestre di un carroponte vanno confrontate con quelle dell'altro non "
     "solo nello stesso periodo, ma anche nei periodi vicini: il ciclogramma "
     "e' periodico, e due blocchi possono incontrarsi a cavallo di un "
     "confine. n_shifts_sep dice quante copie traslate generare."),
    ("q",
     "SE IL MODELLO DIVENTA LENTO, STRINGERE IL TAKT TIME. Il commento lo "
     "dichiara: il conto e' fatto sul caso peggiore T = takt_min, quindi una "
     "banda molto larga (takt_max >> takt_min) fa crescere parecchio il numero "
     "di vincoli generati. E' il consiglio pratico piu' utile del modulo, "
     "perche' il sintomo -- un modello che non finisce -- non suggerisce da "
     "solo la causa."),
    ("c", "model.solve", "    n_sep_constraints = 0", "    # -- Obiettivo"),
    ("p",
     "Per ogni coppia di zone adiacenti si genera la griglia di soglie. Il "
     "commento su `delta` argomenta una scelta di interfaccia: il passo si "
     "dichiara in MILLIMETRI e il numero di verifiche e' una conseguenza. Al "
     "contrario -- numero dichiarato, passo derivato -- la grandezza che si "
     "capisce, cioe' di quanto si puo' sbagliare per eccesso, resterebbe "
     "implicita."),
    ("p",
     "Per ogni soglia si costruiscono le finestre dei due carroponti con "
     "near_boundary, poi si impone che non si sovrappongano. A destra la "
     "condizione e' '<= r_right' invece di '< r_right', e un epsilon di un "
     "tick basta a trasformarla in un confronto stretto."),
    ("q",
     "A COPPIE, NON TUTTI IN UN UNICO AddNoOverlap. E' l'ultimo commento del "
     "blocco e descrive un difetto vero. Gli intervalli di uno STESSO "
     "carroponte possono sovrapporsi fra loro -- i margini di ingresso e "
     "uscita dalla fascia sconfinano nel blocco vicino -- e metterli insieme "
     "in un unico AddNoOverlap li renderebbe mutuamente esclusivi. Il modello "
     "diventerebbe infattibile per un motivo inesistente: non perche' i due "
     "carroponti si scontrano, ma perche' uno solo non puo' stare in due sue "
     "finestre insieme. Il costo e' un vincolo per ogni coppia, ed e' il "
     "motivo per cui n_sep_constraints puo' arrivare a decine di migliaia."),

    # ==================================================================
    ("h2", "8. Risolvere, e ricostruire"),
    ("c", "model.solve", "    # -- Obiettivo", "    segments_per_hoist = []"),
    ("p",
     "L'obiettivo e' una riga: minimizzare il takt time. Tutto il resto sono "
     "vincoli. num_workers=8 fa lavorare in parallelo otto strategie di "
     "ricerca diverse, che e' il modo in cui CP-SAT ottiene le sue "
     "prestazioni."),
    ("p",
     "Se lo stato non e' OPTIMAL o FEASIBLE si restituisce una Solution vuota "
     "col solo stato. Non si solleva: 'non c'e' soluzione' e' una risposta "
     "legittima, e chi chiama deve poterla distinguere da un errore."),
    ("p",
     "Prima di Solve il solutore si registra presso l'Interruzione, se c'e', e "
     "si toglie in un finally: anche se Solve sollevasse, un solutore finito "
     "non deve restare in lista. Se la richiesta era gia' arrivata _registra "
     "risponde False e non si parte nemmeno. Dopo, `interrotto` finisce in "
     "raw sia quando non c'e' soluzione sia quando c'e': una soluzione "
     "trovata prima dello stop e' valida, ma chi la mostra deve sapere che "
     "non e' stata dimostrata ottima."),
    ("c", "model.solve", "    segments_per_hoist = []", "    raw = {"),
    ("p",
     "L'ordine di visita si ricostruisce SEGUENDO gli archi scelti: si parte "
     "dalla mossa su cui il periodo si richiude -- quella con `inizio` vera, "
     "che il solutore ha scelto -- si guarda quale arco uscente e' vero, ci si "
     "sposta, e si va avanti finche' non si torna al punto di partenza."),
    ("q",
     "NON SI PARTE DA z.lo. Sembra un dettaglio di presentazione e non lo e': "
     "il giro elencato a partire da un'altra mossa avrebbe le fasi fuori "
     "ordine, e chi lo legge -- il disegno delle traiettorie, il controllo dei "
     "trasferimenti del verificatore -- metterebbe il +T sull'arco sbagliato. "
     "E' la stessa proprieta' che verify.py controlla: le fasi devono crescere "
     "lungo il giro."),
    ("p",
     "Poi _build_zone_trajectory trasforma i valori risolti in segmenti "
     "disegnabili. E' la funzione le cui convenzioni devono coincidere con "
     "quelle degli archi, ed e' argomento del documento successivo."),
    ("c", "model.solve", "    raw = {", None),
    ("p",
     "`raw` porta i valori diagnostici: il tempo di calcolo, il takt in tick, "
     "la separazione richiesta, e il numero di vincoli di separazione "
     "generati. Quest'ultimo e' il piu' utile quando un modello e' lento: dice "
     "quanto e' grande la parte che costa."),
    ("p",
     "actual_time viene riconvertito in secondi e restituito per intero. E' "
     "quello che permette a verify.py di controllare le permanenze in modo "
     "assoluto invece che modulo T -- e senza, come si e' visto, il controllo "
     "sarebbe ambiguo per multipli interi del periodo."),
]


# ==========================================================================
# Documento 5 -- costruire un ciclogramma senza risolvere
# ==========================================================================

COSTRUZIONE = [
    ("h1", "model.py (5) -- costruire un ciclogramma senza risolvere"),
    ("p",
     "Quinto dei documenti su model.py. Qui c'e' la meta' del modulo che NON "
     "usa CP-SAT: come si costruisce una Solution completa dai soli tre gradi "
     "di liberta', e come da quei valori si ricavano le traiettorie."),
    ("p",
     "E' la parte che rende possibile l'editor manuale, il salvataggio "
     "compatto, e il fatto che meta' dei test giri senza OR-Tools installato."),

    # ==================================================================
    ("h2", "1. build_solution -- l'inverso di solve()"),
    ("c", "model.build_solution", None, "    # Due modi di dire la stessa cosa"),
    ("p",
     "Il docstring dichiara la proprieta' che tiene in piedi tutto: dai soli "
     "takt time e fasi di prelievo, TUTTO il resto e' derivato -- ordine di "
     "visita, tempi assoluti, traiettorie. Non risolve e non verifica: "
     "compone. E il risultato si passa al verificatore esattamente come una "
     "soluzione del solutore."),
    ("p",
     "Le convenzioni elencate nel docstring sono le stesse della "
     "ricostruzione delle traiettorie, e vanno lette come un contratto: il "
     "carroponte visita le mosse nell'ordine dei loro prelievi; il pezzo si "
     "preleva al primo istante compatibile con la fase scelta; e dove passa "
     "il tempo morto lo dicono `attese` e `soste`, se ci sono."),
    ("p",
     "`soste` e' il quinto grado di liberta': la fermata in una vasca IN MEZZO "
     "durante il rientro a vuoto (model.SostaIntermedia). Vale quel che si dice "
     "qui sotto di `attese`, e di piu': la' cambia QUANDO il carroponte si "
     "muove, qui cambia DOVE passa. Senza, il rientro si ricostruirebbe "
     "diritto, piu' corto di quanto e', e non tornerebbero nemmeno i tempi. "
     "Nessuna regola predefinita ne inventa: sostare per strada ha senso solo "
     "guardando dov'e' il vicino, e quello lo sa il solutore."),
    ("q",
     "L'ULTIMA VOCE ERA UNA CONVENZIONE, ADESSO E' UN DATO. Diceva: dal "
     "confine alto si riparte appena consegnato, e il margine diventa attesa "
     "all'arrivo. Chi ricostruiva la applicava, e otteneva una traiettoria "
     "diversa da quella che il solutore aveva scelto e che il verificatore "
     "aveva approvato. Quando `attese` arriva valorizzato -- dal solutore, o "
     "dal file in cui era stato salvato -- la convenzione non si guarda "
     "nemmeno: si usa la scelta gia' fatta. Quando non c'e' (un ciclogramma "
     "composto a mano, un file scritto prima che la colonna esistesse) si "
     "ripiega sulla regola predefinita, che almeno non sosta sulle vasche di "
     "confine."),
    ("p",
     "`tollerante` e' l'interruttore che spegne i rifiuti: con la lista delle "
     "incoerenze valorizzata, i valori impossibili vengono descritti invece "
     "che sollevati. E' quello che permette al disegno manuale di mostrare un "
     "ciclogramma che non sta in piedi, invece di bloccare l'utente."),

    ("h3", "Due modi di dire la stessa cosa"),
    ("c", "model.build_solution", "    # Due modi di dire la stessa cosa", "    if local_pick is None:"),
    ("q",
     "DUE INGRESSI, DUE USI. Il commento distingue i due casi con precisione. "
     "O si danno le FASI e la catena dei tempi assoluti viene dedotta -- ed e' "
     "la modifica di un ciclogramma esistente, dove si sposta un prelievo. O "
     "si danno direttamente i TEMPI ASSOLUTI del pezzo e le fasi ne discendono "
     "-- ed e' il disegno manuale, dove a essere scelti sono i tempi in vasca. "
     "Sono la stessa informazione vista dalle due parti, e averle entrambe "
     "evita di costringere ciascun chiamante a convertire."),
    ("p",
     "`mosse_attive` serve al solo disegno manuale: finche' l'utente non ha "
     "assegnato tutte le mosse, quelle scoperte non fanno parte di nessun giro "
     "e non vanno disegnate. Il verificatore le segnalera' come mancanti, che "
     "e' esatto -- e questa e' la contropartita della finzione di "
     "manuale.zone_coprenti."),
    ("c", "model.build_solution", "    if local_pick is None:", None),
    ("p",
     "La catena dei tempi assoluti: ogni prelievo deve stare almeno alla "
     "permanenza minima dopo l'arrivo, e la fase scelta dall'utente resta "
     "quella -- si sale di PERIODI INTERI."),
    ("q",
     "LA TOLLERANZA SUL ceil NON E' UN DETTAGLIO. Il commento e' esplicito e "
     "vale la pena capirlo. Quando la permanenza cade esattamente sul minimo "
     "-- il caso TIPICO di una soluzione ottima -- basta uno scarto "
     "infinitesimo per far scattare un periodo di troppo, e la permanenza "
     "salta di T secondi interi. E lo scarto c'e' sempre: le fasi che arrivano "
     "dal solutore sono arrotondate al tick, mentre qui i tempi di percorrenza "
     "sono ricalcolati in virgola mobile. La tolleranza usata e' quindi quella "
     "del progetto (eps_seconds), non un epsilon numerico -- perche' l'errore "
     "da assorbire e' quello dell'arrotondamento ai tick, che e' molto piu' "
     "grande della precisione di macchina."),

    ("h3", "_fase_nel_periodo"),
    ("c", "model._fase_nel_periodo"),
    ("p",
     "Due righe, e un docstring che racconta un difetto trovato sul campo. "
     "Sarebbe `istante % T`, ma il modulo ha una discontinuita' proprio dove "
     "serve continuita': il resto di un multiplo esatto vale zero, e un "
     "capello meno di quel multiplo vale quasi T."),
    ("q",
     "IL SINTOMO ERA CHIARISSIMO E LA CAUSA NO. Il docstring lo descrive: "
     "'succedeva riaprendo un file -- il ciclogramma appena calcolato era "
     "pulito, quello riletto pieno di attese lunghe un takt'. La catena dei "
     "tempi si ricostruisce sommando una permanenza dopo l'altra in virgola "
     "mobile, quindi un istante che dovrebbe cadere esattamente su 2T ci cade "
     "appena SOTTO -- e il carroponte si ritrova a cominciare il giro un "
     "periodo dopo, senza piu' fare in tempo ad arrivare da nessuna parte. La "
     "correzione e' una riga, e la tolleranza e' di nuovo eps_seconds."),
    ("p",
     "E' anche la ragione per cui excel_io scrive i tempi in vasca con nove "
     "cifre invece delle due che basterebbero a leggerli: tagliarle "
     "riproporrebbe lo stesso salto in un altro punto della catena."),

    ("h3", "_assembla"),
    ("c", "model._assembla"),
    ("p",
     "Da fasi e tempi assoluti alle traiettorie. L'ordine di visita si ricava "
     "ORDINANDO le mosse per fase di prelievo: il giro comincia dalla mossa "
     "che il carroponte serve per prima dentro il periodo."),
    ("q",
     "PRIMA LA LISTA VENIVA RUOTATA per farla cominciare dalla mossa di indice "
     "piu' basso, che e' la convenzione del solutore -- ed era un difetto. Nel "
     "modello quella convenzione regge perche' il modello COSTRINGE la mossa "
     "di confine basso a essere anche la prima in ordine di tempo: lungo il "
     "giro le fasi crescono, e il giro parte da lei. Componendo a mano nessuno "
     "lo costringe. Se il carroponte serve prima la mossa 6 e poi la 5, la "
     "rotazione produce il giro [5, 6] e pretende che dalla 5 si arrivi alla 6 "
     "SENZA cambiare periodo, cioe' indietro nel tempo: ne usciva un 'non "
     "arriva in tempo' sfasato di esattamente un takt time, su un giro che "
     "sta benissimo in piedi, e una traiettoria disegnata a pezzi scambiati."),
    ("p",
     "dep_hi e arr_lo si calcolano con la stessa convenzione del modello: "
     "'parte appena consegnato'. Il commento lo dichiara, ed e' la terza volta "
     "che quella convenzione compare -- nel modello, qui, e in "
     "_build_zone_trajectory. Le tre devono restare d'accordo."),
    ("p",
     "Una zona senza mosse attive produce una traiettoria VUOTA invece di un "
     "errore: e' lo stato normale del disegno manuale a meta'."),

    # ==================================================================
    ("h2", "2. estrai_gradi_di_liberta -- il giro di ritorno"),
    ("c", "model.estrai_gradi_di_liberta"),
    ("p",
     "Prende una soluzione e ne estrae i valori che bastano a ricostruirla. "
     "Insieme a build_solution chiude il cerchio: si calcola, si estrae, si "
     "modifica, si ricostruisce, si verifica. Il cerchio si chiude davvero "
     "solo se non si perde niente per strada, ed e' esattamente qui che per "
     "molto tempo si perdeva la sosta."),
    ("q",
     "IL TERZO VALORE NON E' DEDUCIBILE. E' il punto del docstring, e non e' "
     "ovvio: i periodi IN PIU' rispetto al minimo non si ricavano dalle fasi. "
     "Il solutore puo' benissimo scegliere di lasciare il pezzo in vasca un "
     "takt in piu' del necessario -- perche' cosi' il carroponte fa in tempo "
     "altrove -- e la fase resta esattamente la stessa. Senza questo terzo "
     "valore la ricostruzione tornerebbe al minimo, e le permanenze "
     "cambierebbero: il ciclogramma riaperto non sarebbe piu' quello salvato."),
    ("p",
     "Il conto di n_min ripete esattamente quello di build_solution, "
     "tolleranza compresa. Devono coincidere: n_min e' il numero di periodi "
     "che la ricostruzione dedurra' da sola, e `extra` e' solo la differenza "
     "fra quello e il numero vero."),

    ("h3", "proposta_semplice"),
    ("c", "model.proposta_semplice"),
    ("p",
     "Un ciclogramma di partenza banale ma sempre COSTRUIBILE: un carroponte "
     "solo che percorre la linea da un capo all'altro senza pause, poi torna "
     "indietro a vuoto."),
    ("q",
     "SI COMPONE DAL PUNTO DI VISTA DEL CARROPONTE. Il docstring dice che e' "
     "l'unico modo per essere certi che la traiettoria ESISTA. Componendo dal "
     "punto di vista del pezzo -- scegliendo i tempi in vasca -- si ottiene "
     "facilmente qualcosa che nessun carroponte puo' eseguire. Qui invece si "
     "incatenano le mosse una dopo l'altra: finita la k-1 il carroponte e' "
     "gia' sulla stazione da cui parte la k, quindi non c'e' nemmeno uno "
     "spostamento a vuoto nel mezzo, e la fattibilita' e' garantita per "
     "costruzione."),
    ("p",
     "Le permanenze vengono di conseguenza, e non e' detto che rientrino nelle "
     "tolleranze di processo. Il docstring lo dichiara e dice chi lo dira': il "
     "verificatore. E' la scelta giusta -- meglio partire da qualcosa di "
     "concreto e verificabile che da un foglio bianco."),
    ("p",
     "Il takt time, se non imposto, si sceglie dentro la banda dichiarata "
     "quando ci sta; altrimenti si prende il ciclo minimo, e sara' di nuovo il "
     "verificatore a segnalare che il takt non e' rispettato."),

    # ==================================================================
    ("h2", "3. Dai valori ai segmenti"),
    ("c", "model._segmenti_rientro"),
    ("p",
     "Il rientro a vuoto come tratti disegnabili. Un tratto solo col gancio "
     "basso, cinque quando c'e' un ostacolo da scavalcare."),
    ("q",
     "VANNO EMESSI TUTTI E CINQUE, NON RIASSUNTI IN UNO. Il docstring ne da' "
     "la ragione, e non e' estetica: durante il giro il carroponte si spinge "
     "FINO ALLO SVINCOLO, che sta OLTRE la vasca, ed e' li' che puo' "
     "incontrare il vicino. Un tratto unico da vasca a vasca nasconderebbe "
     "proprio le posizioni in cui la collisione e' piu' probabile."),
    ("p",
     "Le corse verticali diventano segmenti di tipo `lift_empty`. I due "
     "commenti nel codice spiegano perche' non si usa ne' un 'empty' di "
     "lunghezza nulla -- verrebbe campionato come un movimento che non c'e' -- "
     "ne' un'attesa: e' un movimento, e la simulazione deve poterlo mostrare "
     "per quello che e'."),
    ("p",
     "Ogni `lift_empty` porta anche il VERSO, nel campo `sale`: vero per la "
     "tratta 1 di tratte_rientro, la salita sullo svincolo di partenza, falso "
     "per la 3, la discesa su quello di arrivo. E' l'unico punto in cui lo si "
     "sa per certo. Dopo, dai soli segmenti, bisognerebbe dedurlo dai tratti "
     "vicini, e se una delle due corse manca -- una vasca senza corsa, la cui "
     "tratta ha durata zero e viene saltata -- quella che resta non dice da "
     "sola da che parte va. Lo usa il ciclogramma per le frecce su e giu'."),
    ("c", "model._segmenti_fasi"),
    ("p",
     "I tratti disegnabili di una presa o di un rilascio. Il caso normale e' "
     "la prima riga: se nessuna fase trasla, esce un tratto solo, fermo sopra "
     "la stazione."),
    ("p",
     "Con una zona di cambio quota le fasi vanno emesse per quello che sono: "
     "le soste con il loro kind (`pick` o `release`), le traslazioni con "
     "`kind='quota'`. Le soste consecutive sullo stesso punto si accorpano, "
     "come in fasi_verticali dentro solve()."),
    ("q",
     "UN TRATTO UNICO NASCONDEREBBE UN MOVIMENTO VERO. E' la frase finale del "
     "docstring, e ripete per il disegno cio' che fasi_verticali fa per il "
     "vincolo: chi campiona le posizioni -- il verificatore, la simulazione -- "
     "lo crederebbe fermo. Sono due funzioni diverse in due punti diversi che "
     "devono raccontare la stessa storia, ed e' il motivo per cui entrambe "
     "leggono le stesse LiftPhase."),

    # ==================================================================
    ("h2", "4. _build_zone_trajectory"),
    ("c", "model._build_zone_trajectory", None, "    for i, k in enumerate(order):"),
    ("p",
     "Trasforma i valori risolti nella traiettoria di un carroponte. E' "
     "separata dalla risoluzione apposta, come dice il commento di sezione, "
     "cosi' da poter essere provata senza risolvere realmente un modello."),
    ("p",
     "Il primo commento del corpo definisce EPS e ne da' la ragione: il "
     "modello lavora con tempi arrotondati al tick, mentre qui si ricalcolano "
     "i tempi di percorrenza con la formula esatta in virgola mobile. Le due "
     "cose possono differire di qualche tick per puro arrotondamento, senza "
     "che ci sia un'incoerenza reale. Distinguere uno scarto di "
     "arrotondamento da un errore vero e' quello che questa funzione fa in "
     "quattro punti diversi."),

    ("h3", "La mossa in tre pezzi"),
    ("c", "model._build_zone_trajectory", "    for i, k in enumerate(order):", "        is_last = i == n - 1"),
    ("p",
     "Presa, traslazione col pezzo, rilascio. Le posizioni sono i punti di "
     "APPROCCIO e non le vasche, per la ragione che il primo commento "
     "richiama."),
    ("q",
     "LE FASI VERTICALI NON GONFIANO IL TRATTO 'loaded'. Il secondo commento "
     "lo dice e ne da' la conseguenza: altrimenti il profilo cinematico "
     "verrebbe disegnato e campionato nel posto sbagliato. Il tratto a carico "
     "dura esattamente horizontal_loaded_seconds, e presa e rilascio sono "
     "segmenti separati. E' anche cio' che permette a verify.py di fare i due "
     "controlli distinti sulla durata."),

    ("h3", "Quando parte e quando arriva"),
    ("c", "model._build_zone_trajectory", "        is_last = i == n - 1", "        if depart_t < t1 - EPS:"),
    ("p",
     "Quattro casi, e sono ESATTAMENTE i quattro del blocco `arcs` dentro "
     "solve(). Chi parte dal confine alto parte a dep_hi; chi torna alla PRIMA "
     "mossa del giro arriva ad arr_lo; se vale l'una e l'altra, entrambe; "
     "altrimenti si riparte appena consegnati."),
    ("q",
     "arr_lo E' LEGATO A order[0], NON A zone.lo. Per il solutore sono la "
     "stessa mossa -- il modello costringe quella di confine basso a essere "
     "anche la prima in ordine di tempo -- ma un giro composto a mano puo' "
     "cominciare da un'altra, e li' i due indici divergono. Guardare zone.lo "
     "attaccava l'istante di richiusura del periodo alla mossa sbagliata."),
    ("p",
     "Il primo ramo, `attesa_alla_partenza`, e' quello del DISEGNO MANUALE, e "
     "non guarda ne' dep_hi ne' arr_lo: sceglie arco per arco dove far passare "
     "il tempo morto, con la regola della funzione qui sotto. Puo' farlo "
     "perche' li' non c'e' nessun vincolo del modello da rispettare -- e' il "
     "verificatore a controllare cio' che si vede."),
    ("c", "model._aspetta_dove_ha_consegnato"),
    ("q",
     "NON SOSTARE SU UNA VASCA DI CONFINE. Le stazioni agli estremi della zona "
     "sono quelle CONDIVISE col vicino: uno consegna, l'altro viene a "
     "prendere. Restarci fermi per un minuto quando si potrebbe stare altrove "
     "e' il modo piu' facile di fabbricare una collisione che non c'era "
     "bisogno di avere -- ed e' esattamente quello che il disegno manuale "
     "faceva, parcheggiando il carroponte sulla vasca di destinazione appena "
     "consegnato altrove. Su un ciclogramma vero questo bastava a far "
     "segnalare una collisione su un giro perfettamente realizzabile."),
    ("p",
     "La traslazione resta a VELOCITA' PIENA in tutti i casi: cambia QUANDO "
     "avviene, non quanto dura. E quando entrambi gli estremi sono confini -- "
     "capita a un carroponte con poche mosse -- non c'e' una scelta migliore "
     "dell'altra e si tiene quella predefinita, partire subito: almeno il "
     "tratto in mezzo lo si percorre presto invece di restare fermi in mezzo "
     "alla rotaia."),
    ("q",
     "IL SOLUTORE TIENE LA CONVENZIONE VECCHIA, E DEVE. Il vincolo di non "
     "collisione e' costruito su di essa (in solve, blocco `arcs`) e protegge "
     "quella traiettoria: disegnarne un'altra vorrebbe dire garantire una cosa "
     "e mostrarne un'altra. E' il motivo per cui il comportamento e' un "
     "parametro con valore predefinito, e non la nuova regola per tutti."),
    ("p",
     "Il commento sull'ultimo caso dichiara che e' una convenzione per la "
     "VISUALIZZAZIONE: nessuna attesa gratuita prima della partenza, e "
     "l'eventuale margine mostrato come attesa DOPO l'arrivo. E' arbitraria, "
     "ed e' arbitraria in modo sicuro solo perche' solve() ha fatto la stessa "
     "scelta."),

    ("h3", "Le due incoerenze possibili"),
    ("c", "model._build_zone_trajectory", "        if depart_t < t1 - EPS:", "        # `target_pick` e' calcolato sopra"),
    ("p",
     "La prima: il carroponte lascerebbe la stazione prima di aver finito la "
     "consegna. La struttura del controllo e' quella che si ripete anche piu' "
     "sotto, e ha tre rami."),
    ("li", "scarto MAGGIORE di EPS: e' un errore vero. Senza la lista delle "
           "incoerenze si solleva; con la lista si registra un messaggio "
           "leggibile e si disegna comunque, a partire da quando il carroponte "
           "e' libero;"),
    ("li", "scarto minuscolo: si corregge in silenzio, perche' e' "
           "arrotondamento e non un difetto;"),
    ("li", "margine reale: diventa un tratto di attesa."),
    ("p",
     "Il messaggio dell'incoerenza e' scritto per l'utente -- nomina la vasca, "
     "i due istanti e i secondi mancanti -- mentre quello dell'eccezione e' "
     "scritto per chi sviluppa: 'Controlla i vincoli del modello'. Sono due "
     "pubblici diversi per lo stesso fatto, ed e' giusto che siano diversi: se "
     "questa condizione scatta senza la lista, significa che il MODELLO ha "
     "prodotto valori impossibili, ed e' un difetto del programma."),
    ("p",
     "Il tratto fra le due mosse si emette come rientro solo se le due "
     "posizioni differiscono. Il commento spiega il caso opposto: sulla stessa "
     "stazione un 'empty' di lunghezza nulla creerebbe un segmento degenere "
     "che, con lo scarto di arrotondamento sui tick, si ordina male rispetto "
     "ai vicini e SPEZZA la traiettoria."),
    ("c", "model._build_zone_trajectory", "        # `target_pick` e' calcolato sopra", None),
    ("p",
     "La seconda incoerenza: non si fa in tempo ad arrivare. Stessa struttura "
     "a tre rami, e il messaggio dice di quanti secondi si e' in ritardo -- che "
     "e' il numero su cui l'utente puo' agire, allungando una permanenza o "
     "spostando una mossa a un altro carroponte."),
    ("q",
     "IL +T STA SULL'ARCO CHE CHIUDE IL PERIODO, cioe' quello che riporta alla "
     "PRIMA mossa del giro: quel prelievo appartiene al ciclo dopo. La stessa "
     "riga sta in solve() e in verify.py -- tre punti che devono dire la stessa "
     "cosa -- e per un po' l'hanno detta in un modo che regge solo per il "
     "solutore: il +T sulla mossa di CONFINE BASSO. Coincidono finche' il giro "
     "comincia da li', che il modello garantisce e la composizione a mano no. "
     "Su un giro manuale che cominci da un'altra mossa, il +T finiva sull'arco "
     "sbagliato e il ciclogramma veniva dichiarato irrealizzabile per esattamente "
     "un takt time."),
]


# ==========================================================================
# Documento 6 -- la scelta automatica
# ==========================================================================

AUTOMATICA = [
    ("h1", "model.py (6) -- scegliere le zone e il numero di carroponti"),
    ("p",
     "Sesto e ultimo documento su model.py. Il terzo grado di liberta' -- chi "
     "fa cosa -- non e' dentro il modello CP-SAT: si sceglie fuori, provando."),

    # ==================================================================
    ("h2", "Perche' fuori dal modello"),
    ("c", "model", "# Le zone (quali mosse assegnare a quale carroponte) NON sono decise",
     "def _enumerate_contiguous_partitions"),
    ("p",
     "Il commento di sezione argomenta la scelta. Mettere le zone dentro il "
     "modello sarebbe possibile -- servirebbero variabili di confine fra zone "
     "-- ma renderebbe il modello sensibilmente piu' complesso e RISCHIOSO DA "
     "VALIDARE senza un ambiente con OR-Tools a disposizione."),
    ("q",
     "L'ALTERNATIVA E' PIU' SEMPLICE E PIU' ROBUSTA. Si enumerano tutte le "
     "suddivisioni contigue possibili, si risolve il modello GIA' TESTATO per "
     "ciascuna, e si tiene la migliore. Costa molte risoluzioni invece di una, "
     "e in cambio la parte difficile del programma resta una sola, con una "
     "sola forma, coperta da un solo insieme di test. E' un buon affare: il "
     "numero di suddivisioni e' C(n_moves-1, n_hoists-1), che per problemi "
     "reali -- una manciata di carroponti, qualche decina di mosse -- resta "
     "gestibile."),
    ("p",
     "Il commento avverte pero' che cresce in fretta, e rimanda a "
     "max_candidates come limite di sicurezza. E' l'onesta' che serve: la "
     "strategia e' esponenziale, e lo dice."),

    ("h3", "I due prefiltri, in un posto solo"),
    ("c", "model._scarto_prefiltro"),
    ("p",
     "Restituisce None se la suddivisione va provata col solutore, altrimenti "
     "il motivo per cui si scarta. I due filtri sono economici -- una somma e "
     "un confronto fra intervalli -- e tolgono di mezzo moltissimo: su una "
     "linea di dieci vasche con il takt time stretto, 176 suddivisioni "
     "diventano 10."),
    ("q",
     "PERCHE' NON DENTRO solve_auto_zones. Il docstring lo dice: servono a due "
     "cose, scartare e CONTARE. Il conteggio a priori -- quante risoluzioni si "
     "faranno -- e' quello che permette all'interfaccia di mostrare un "
     "avanzamento vero invece di una barra che oscilla. Duplicare i filtri "
     "vorrebbe dire che il conteggio e la ricerca possono dire numeri diversi, "
     "e la barra arriverebbe in fondo prima della fine."),
    ("c", "model.tentativi_previsti"),
    ("p",
     "Quante risoluzioni CP-SAT servirebbero per un dato numero di "
     "carroponti. Costa millisecondi e si puo' chiamare prima di cominciare: "
     "il numero di suddivisioni e' combinatoria pura e i prefiltri sono "
     "deterministici."),
    ("q",
     "COSA RESTA IMPREVEDIBILE, E VA DETTO. Il docstring lo dichiara: non si "
     "sa a quale numero di carroponti la ricerca si fermera' -- e' proprio "
     "l'informazione che si sta cercando -- ne' quanto durera' ciascuna "
     "risoluzione, che va da qualche centesimo a tutto il limite di tempo "
     "secondo quanto e' difficile l'istanza. Il totale a priori sarebbe quindi "
     "il caso peggiore: sull'esempio del programma darebbe sei minuti e mezzo "
     "contro sei secondi e mezzo reali. E' per questo che l'interfaccia stima "
     "STRADA FACENDO, misurando i tentativi gia' fatti, invece di annunciare "
     "un numero prima di partire."),

    ("c", "model._enumerate_contiguous_partitions"),
    ("p",
     "Tre righe. Una suddivisione contigua in n gruppi e' determinata dai suoi "
     "n-1 TAGLI, e i tagli possibili sono le combinazioni di n-1 elementi fra "
     "gli n_moves-1 punti interni. itertools.combinations le genera in ordine "
     "lessicografico, e ogni combinazione diventa una lista di HoistZone."),
    ("p",
     "La lista `bounds` con -1 in testa e n_moves-1 in coda evita di trattare "
     "il primo e l'ultimo gruppo come casi speciali: e' il trucco che rende la "
     "comprensione finale una riga sola."),

    # ==================================================================
    ("h2", "1. solve_auto_zones"),
    ("c", "model.solve_auto_zones", None, "    travel_loaded_seconds ="),
    ("p",
     "I controlli d'ingresso sono due e riguardano solo la coerenza: "
     "n_hoists positivo e non superiore al numero di mosse. Il tetto sul "
     "numero di suddivisioni non e' qui -- si applica piu' avanti, quando si "
     "sa quante ne restano davvero da risolvere."),

    ("h3", "Filtrare tutto, poi risolvere"),
    ("c", "model.solve_auto_zones", "    travel_loaded_seconds =", "    if best_solution is None:"),
    ("p",
     "Il lavoro e' in DUE tempi: prima si applicano i prefiltri a tutte le "
     "suddivisioni, poi si risolvono quelle sopravvissute."),
    ("q",
     "PERCHE' NON IN UN CICLO SOLO. Il commento lo dice: farlo in due tempi "
     "costa una lista di poche decine di elementi e in cambio da' il TOTALE "
     "ESATTO delle risoluzioni da fare. Senza, un avanzamento potrebbe solo "
     "dire quante ne sono state fatte, non quante ne mancano -- e una barra "
     "che non sa dove finisce non e' una barra."),
    ("p",
     "Il primo prefiltro e' una condizione necessaria banale: se la somma dei "
     "soli trasporti a carico di una zona -- senza contare nemmeno un "
     "trasferimento a vuoto -- supera gia' il takt time massimo, quella "
     "suddivisione e' infattibile qualunque sia l'ordine di visita. Costa una "
     "somma e risparmia una risoluzione CP-SAT intera."),
    ("p",
     "Il secondo scarta le geometrie patologiche. Farlo qui invece di lasciar "
     "fallire solve() fa si' che la scelta automatica TROVI DA SOLA una "
     "suddivisione valida quando esiste: lasciando fallire solve(), la prima "
     "geometria patologica farebbe abortire tutta la ricerca -- e su una linea "
     "con vasche non perfettamente ordinate sarebbe la norma, non "
     "l'eccezione."),
    ("q",
     "IL TETTO SI APPLICA A QUELLO CHE SI RISOLVE. E' l'unica cosa che ha "
     "senso contare, e contare le combinazioni sulla carta e' costato caro: su "
     "una linea di diciassette mosse con quattro carroponti le combinazioni "
     "sono 560 e le suddivisioni che arrivano al solutore 336. Col tetto a 500 "
     "applicato alle prime, quella ricerca veniva saltata per intero -- e con "
     "lei tutti i numeri di carroponti superiori, perche' crescono. Una linea "
     "risolvibile con sei carroponti risultava impossibile senza che nessuno "
     "avesse provato oltre i tre."),
    ("p",
     "Il valore predefinito e' 5000, alto di proposito: saltare una ricerca e' "
     "un danno molto peggiore di farla durare. Una ricerca lunga si vede -- la "
     "barra dice a che tentativo e' arrivata e quanto manca -- e si puo' "
     "interrompere; una saltata produce un 'nessuna soluzione' che sembra un "
     "verdetto sulla linea e non lo e'. Quello che resta e' una rete contro il "
     "caso veramente fuori scala, dove aspettare non avrebbe comunque senso."),
    ("p",
     "Quando il tetto scatta si SOLLEVA invece di troncare l'esplorazione: "
     "restituire la migliore fra le prime cinquemila darebbe una risposta che "
     "sembra completa e non lo e'. Chi chiama decide -- solve_auto_hoists "
     "registra il salto e passa al numero successivo, cosi' un valore "
     "impraticabile non impedisce di provare gli altri."),
    ("p",
     "`su_tentativo` viene chiamata prima di ogni risoluzione, con l'indice e "
     "il totale gia' al netto dei prefiltri, piu' quante suddivisioni "
     "fattibili si sono trovate finora e il takt time della migliore. Gira "
     "nel thread del chiamante, quindi "
     "-- come avverte il docstring -- non deve toccare widget: chi la usa "
     "dall'interfaccia grafica ci mette dentro solo un accodamento."),
    ("p",
     "Gli ultimi due argomenti sono i soli che non descrivono l'avanzamento "
     "ma il RISULTATO PARZIALE, e sono li' per una domanda precisa di chi "
     "guarda: fermando adesso, mi resta qualcosa? La ricerca si puo' "
     "interrompere, e interrotta restituisce la migliore fra le suddivisioni "
     "gia' provate -- ma solo se ce n'e' almeno una. Senza il conteggio la "
     "differenza fra 'fermati pure' e 'fermarti ti lascia a mani vuote' si "
     "scopriva fermandosi."),
    ("p",
     "Il takt time della migliore risponde al seguito della stessa domanda: "
     "non se fermarsi e' sicuro, ma se conviene. Puo' solo scendere mentre la "
     "ricerca va avanti -- si tiene la piu' veloce fra quelle provate -- "
     "quindi chi ha in mente il valore che gli serve vede da se' quando e' "
     "arrivato, invece di aspettare la fine per scoprire che ci era gia'."),
    ("p",
     "`log_progress` stampa una riga per candidata, ed e' il modo per capire "
     "da terminale perche' una ricerca non trova niente."),
    ("c", "model.solve_auto_zones", "    if best_solution is None:", None),
    ("p",
     "Fallendo, si restituisce un INFEASIBLE che porta con se' i CONTATORI: "
     "quante provate, quante scartate dal primo filtro, quante dal secondo, e "
     "un esempio di problema di geometria."),
    ("q",
     "I CONTATORI SONO LA DIAGNOSI. Senza di essi 'INFEASIBLE' non "
     "distinguerebbe tre situazioni molto diverse: nessuna suddivisione "
     "provata perche' tutte troppo cariche (serve un carroponte in piu'), "
     "tutte scartate per geometria (le vasche non sono ordinate lungo la "
     "rotaia), oppure provate tutte e nessuna fattibile (e' il takt time o "
     "sono le permanenze). Sono tre azioni diverse per l'utente, e sono "
     "distinguibili solo grazie a quei numeri."),

    # ==================================================================
    ("h2", "2. Perche' non si riesce"),
    ("c", "model", "# \"Nessuna soluzione\" e' la risposta meno utile", "def _prova"),
    ("p",
     "Il commento di sezione pone il problema: il solutore dice che i vincoli "
     "insieme sono incompatibili, non quale sia di troppo. Non lo nasconde -- "
     "non lo sa. Lo si scopre RILASSANDO un vincolo per volta e riprovando."),
    ("q",
     "E' UN METODO GREZZO, E RISPONDE ALLA DOMANDA GIUSTA. Non e' un'analisi "
     "esatta di infattibilita': se a bloccare sono due vincoli insieme, "
     "nessun rilassamento singolo basta. Ma la domanda di chi ha davanti un "
     "rifiuto non e' 'quali sono i vincoli attivi', e' 'dove metto le mani' -- "
     "e a quella un elenco di tutto cio' che si potrebbe cambiare non risponde."),
    ("c", "model._prova"),
    ("q",
     "LA DISTINZIONE FRA 'no' E 'boh' E' TUTTA LA DIFFERENZA. 'no' e' "
     "INFEASIBLE, cioe' una dimostrazione: nemmeno rilassando quel vincolo si "
     "riesce, quindi non e' lui a bloccare. 'boh' e' UNKNOWN, cioe' tempo "
     "scaduto: non si sa niente. Confonderli fa dire alla diagnosi che un "
     "vincolo e' innocente quando invece non e' stato esaminato -- ed e' il "
     "modo piu' efficace di mandare qualcuno a cercare nel posto sbagliato. "
     "Non e' un rischio teorico: e' successo alla prima stesura, e proprio "
     "sulla prova piu' utile."),
    ("c", "model.diagnosi_zone"),
    ("p",
     "Quattro prove in ordine, e ciascuna esce appena conclude. La prima cosa "
     "che fa pero' non e' una prova: e' chiedersi se ci sia qualcosa da "
     "diagnosticare."),
    ("q",
     "SU UNA LINEA CHE FUNZIONA, OGNI RILASSAMENTO RIESCE. Senza il controllo "
     "iniziale, la prima prova verrebbe scambiata per la causa e la diagnosi "
     "annuncerebbe un colpevole inventato. Costa una risoluzione ed e' il "
     "controllo piu' importante del metodo -- e' anche l'errore che si fa "
     "usando la funzione a mano su una suddivisione sbagliata."),
    ("p",
     "La prova sul takt time non ALLARGA la banda: la SPOSTA, tenendola "
     "stretta. Allargarla ingrandisce il modello -- il numero di traslazioni "
     "da generare va come orizzonte diviso takt minimo -- e la prova scade "
     "prima di dire qualcosa. Una banda stretta piazzata piu' in alto costa "
     "quanto l'originale e risponde alla stessa domanda."),
    ("p",
     "Anche il limite INFERIORE del takt puo' bloccare, e sorprende: un ciclo "
     "piu' lungo tiene i pezzi in vasca piu' a lungo, e se il processo non lo "
     "tollera la linea non sta in piedi."),
    ("q",
     "IL MINIMO SI RIPORTA COME INTERVALLO. Trovato uno scalino che funziona, "
     "il minimo sta fra quello e lo scalino precedente che aveva fallito. "
     "Annunciare il valore trovato come 'il minimo' farebbe alzare "
     "takt_max_s piu' del necessario. E' la stessa disciplina del limite "
     "d'errore nel verificatore: si dichiara quello che si sa, con "
     "l'incertezza attaccata."),
    ("c", "model._vasche_che_bloccano"),
    ("p",
     "Quando a bloccare sono i tempi di processo, dire 'i tempi sono stretti' "
     "non serve a niente: serve sapere QUALE vasca e DI QUANTO. Si allarga "
     "una vasca per volta, e se quella da sola sblocca si cerca per bisezione "
     "il minimo che basta."),
    ("p",
     "Nella bisezione un esito incerto si tratta come un no: l'intervallo si "
     "stringe dal lato prudente, e il valore riportato non promette meno di "
     "quanto serva davvero."),
    ("c", "model._piu_equilibrata"),
    ("p",
     "Quando NESSUNA suddivisione funziona bisogna sceglierne una su cui "
     "indagare. Il docstring argomenta perche' questa e' la meno arbitraria: "
     "se il problema fosse il carico, sarebbe l'ultima a soffrirne, quindi "
     "quello che blocca lei blocca anche tutte le altre."),

    # ==================================================================
    ("h2", "3. solve_auto_hoists"),
    ("c", "model", "# Piu' carroponti possono solo ampliare", "def solve_auto_hoists"),
    ("q",
     "PERCHE' BASTA UNO SWEEP CRESCENTE. Il commento contiene l'argomento: "
     "piu' carroponti possono solo AMPLIARE, mai restringere, cio' che e' "
     "fattibile -- se una linea ce la fa con N, aggiungerne un altro "
     "spezzando ulteriormente le zone non puo' peggiorare le cose. Quindi la "
     "ricerca del numero MINIMO e' semplicemente N=1,2,3,... fermandosi al "
     "primo che funziona. Senza quella proprieta' bisognerebbe provarli tutti "
     "e confrontare."),
    ("p",
     "Vale la pena notare che la proprieta' e' vera per la FATTIBILITA', non "
     "per il takt time: un carroponte in piu' non peggiora, ma nemmeno "
     "garantisce di migliorare. Fermarsi al primo N fattibile e' quindi la "
     "risposta alla domanda 'quanti me ne servono', non a 'quale numero da' il "
     "ciclogramma piu' veloce'."),
    ("c", "model.solve_auto_hoists"),
    ("p",
     "max_hoists viene limitato al numero di mosse: piu' carroponti che mosse "
     "non ha senso, ogni carroponte deve averne almeno una."),
    ("q",
     "UN ValueError DI solve_auto_zones NON FERMA LA RICERCA. Il blocco "
     "try/except intercetta il caso 'troppe suddivisioni possibili per questo "
     "n_hoists', lo registra come SKIPPED e prova il numero successivo. Il "
     "commento lo dichiara. E' la scelta giusta: quel limite dipende da "
     "n_hoists, e un valore intermedio impraticabile non deve impedire di "
     "provare quelli successivi."),
    ("p",
     "Tutto il percorso della ricerca finisce in `hoist_sweep`, dentro raw: "
     "una voce per ogni numero di carroponti provato, con lo stato, il takt "
     "trovato e -- se ce ne sono state -- le suddivisioni scartate per "
     "geometria con un esempio. E' quello che ciclogramma.py stampa quando non "
     "trova soluzione, ed e' spesso l'unica cosa che spiega il perche'."),
    ("p",
     "Il messaggio sulle suddivisioni scartate viene stampato solo se la "
     "ricerca per quel numero di carroponti e' FALLITA: se ha trovato una "
     "soluzione, che qualche geometria sia stata scartata e' un dettaglio "
     "interno che non interessa nessuno."),
]


DOCUMENTI = [
    ("model_1_strutture.docx", STRUTTURE),
    ("model_2_fasi_verticali.docx", FASI),
    ("model_3_rientri_e_geometria.docx", RIENTRI),
    ("solve_riga_per_riga.docx", SOLVE),
    ("model_5_costruzione.docx", COSTRUZIONE),
    ("model_6_scelta_automatica.docx", AUTOMATICA),
]
