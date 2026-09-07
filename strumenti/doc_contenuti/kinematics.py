"""
Il testo dei documenti di kinematics.py.

Il modulo e' piccolo -- quattro fra funzioni e metodi -- ma sta sotto a tutto
il resto: ogni durata del ciclogramma, ogni vincolo di non collisione e ogni
fotogramma della simulazione finisce qui sotto. Un documento solo, ma che
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
     "Tutto il modulo e' la conseguenza di questa distinzione. C'e' una sola "
     "quantita' che decide quale dei due casi si applica, e vale la pena "
     "ricavarla, perche' torna in tutte e tre le funzioni."),
    ("p",
     "Per portarsi da fermo alla velocita' massima con accelerazione a serve "
     "un tempo v/a, durante il quale si percorre mezzo v^2/a. Per rifermarsi "
     "serve altrettanto. Quindi la distanza minima per riuscire a raggiungere "
     "la velocita' massima, anche solo per un istante, e':"),
    ("p", "        d_acc  =  v_max^2 / a_max"),
    ("p",
     "Se la distanza da percorrere e' almeno d_acc il profilo e' trapezoidale; "
     "se e' minore e' triangolare. Nel codice questa riga compare tre volte, "
     "identica, in travel_time, position_profile e profile_breakpoints: e' la "
     "stessa soglia guardata da tre punti di vista."),

    ("q",
     "PERCHE' NON BASTA distanza/velocita'. Con i valori veri di una linea di "
     "zincatura -- carroponte vuoto a 1600 mm/s con 900 mm/s^2 -- la soglia "
     "d_acc vale 2844 mm. Il passo fra due vasche vicine sta spesso sotto quel "
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
    ("p",
     "Si noti il caso carico a 2500 mm: con v=1000 e a=400 la soglia d_acc "
     "vale esattamente 2500 mm. E' il punto di passaggio fra i due profili, e "
     "il paragrafo 3 spiega perche' li' le due formule danno lo stesso "
     "risultato invece di fare un salto."),

    # ==================================================================
    ("h2", "1. La classe Kinematics"),
    ("c", "kinematics.Kinematics"),
    ("p",
     "Due soli numeri: la velocita' massima e l'accelerazione massima. Non "
     "c'e' una decelerazione separata perche' il modulo assume che sia uguale "
     "all'accelerazione -- il commento accanto al campo lo dichiara. E' "
     "l'ipotesi giusta per un carroponte a inverter, dove il limite e' la "
     "coppia disponibile e non cambia di segno; sarebbe sbagliata per un mezzo "
     "che frena meccanicamente molto piu' forte di quanto acceleri."),
    ("p",
     "La dataclass e' frozen=True, cioe' immutabile. Non e' un vezzo: uno "
     "stesso oggetto Kinematics viene condiviso da tutto il programma e letto "
     "dentro cicli molto stretti (il vincolo di non collisione ne chiama i "
     "campi decine di migliaia di volte). Se qualcuno potesse modificarlo a "
     "meta' di una risoluzione, il modello CP-SAT risulterebbe costruito con "
     "due fisiche diverse, e il verificatore segnalerebbe violazioni "
     "inspiegabili. Immutabile, il problema non esiste."),
    ("p",
     "__post_init__ e' il solo controllo del modulo, e sta qui invece che "
     "dentro le funzioni per una ragione precisa: rifiuta il dato sbagliato "
     "nel momento in cui viene costruito, non venti chiamate dopo. Con a_max = 0 "
     "la divisione in d_acc darebbe ZeroDivisionError da qualche parte in fondo "
     "a travel_time, con un messaggio che non dice quale vasca o quale "
     "carroponte era mal configurato."),

    # ==================================================================
    ("h2", "2. travel_time -- quanto ci mette"),
    ("p",
     "E' la funzione piu' chiamata dell'intero progetto. Ogni durata che "
     "compare in un ciclogramma -- andata carica, ritorno a vuoto, "
     "riposizionamento fra due vasche -- passa di qui, e il vincolo di non "
     "collisione la richiama per ogni passo della discretizzazione."),
    ("c", "kinematics.travel_time"),

    ("h3", "Il valore assoluto e il caso nullo"),
    ("c", "kinematics.travel_time", "d = abs(distance)", "d_acc = ("),
    ("p",
     "La funzione ignora la direzione: andare avanti di 3 metri o indietro di "
     "3 metri costa uguale. Il chiamante sa in che verso sta andando e non ha "
     "bisogno che glielo dica la cinematica. Questa scelta ritorna in tutte e "
     "tre le funzioni del modulo e semplifica parecchio il codice che le usa: "
     "model.py calcola le distanze con un abs() e non deve mai preoccuparsi "
     "dell'ordine delle vasche."),
    ("p",
     "Il caso d == 0 e' trattato a parte e restituisce zero secco. Non e' un "
     "caso teorico: capita ogni volta che due tappe consecutive della ricetta "
     "sono nella stessa vasca (immersione ripetuta), e capita in tutte le "
     "geometrie degenerate che i test provano apposta. Senza questa riga, la "
     "formula triangolare darebbe comunque 0, ma profile_breakpoints piu' "
     "sotto restituirebbe una tupla di spigoli tutti coincidenti."),

    ("h3", "La soglia"),
    ("c", "kinematics.travel_time", "d_acc = (", "if d >= d_acc"),
    ("p",
     "E' la quantita' ricavata in apertura: la distanza spesa per accelerare "
     "fino a v_max e poi tornare a zero. Il commento accanto la spiega in una "
     "riga. Vale la pena notare che non dipende dalla distanza da percorrere: "
     "e' una proprieta' del solo carroponte, e potrebbe essere calcolata una "
     "volta sola e messa in un campo di Kinematics. Non lo e' perche' il "
     "guadagno sarebbe una moltiplicazione e una divisione per chiamata, e la "
     "leggibilita' ne soffrirebbe."),

    ("h3", "Il ramo trapezoidale"),
    ("c", "kinematics.travel_time", "if d >= d_acc", "    else:"),
    ("p",
     "La distanza si spezza in due parti: d_acc consumata dalle due rampe, e "
     "il resto percorso a velocita' costante. Il tratto di crociera dura "
     "quindi (d - d_acc)/v_max, e ciascuna rampa dura v_max/a_max. Il totale "
     "e' la somma delle tre fasi."),
    ("p",
     "Da notare che t_ramp non dipende dalla distanza: e' sempre lo stesso "
     "tempo, 1,78 s a vuoto e 2,50 s carico con i valori tipici. Su un "
     "trasporto lungo dieci metri le rampe sono la meta' del tempo totale."),

    ("h3", "Il ramo triangolare"),
    ("c", "kinematics.travel_time", "    else:", None),
    ("p",
     "Qui la velocita' massima non si raggiunge mai. Si accelera per meta' "
     "distanza e si decelera per l'altra meta'. Percorrere d/2 partendo da "
     "fermo con accelerazione a richiede sqrt(d/a) -- da d/2 = a*t^2/2 -- e le "
     "due meta' sono simmetriche, da cui il fattore 2."),
    ("p",
     "Le due formule si saldano senza gradini. Nel punto d = d_acc la "
     "trapezoidale da' t_cruise = 0 e quindi 2*v/a; la triangolare da' "
     "2*sqrt(d_acc/a) = 2*sqrt(v^2/a^2) = 2*v/a. Identiche. Non e' un dettaglio "
     "estetico: se ci fosse un salto, due vasche distanti quel tanto darebbero "
     "durate diverse a seconda di un errore di arrotondamento sull'ultima "
     "cifra, e il modello CP-SAT diventerebbe instabile rispetto a variazioni "
     "millimetriche del disegno della linea."),

    # ==================================================================
    ("h2", "3. position_profile -- dove si trova"),
    ("p",
     "Mentre travel_time da' la durata totale, questa da' lo spazio percorso a "
     "un istante qualsiasi del movimento. Serve a due cose molto diverse: "
     "disegnare le traiettorie curve nel ciclogramma e nella simulazione, e "
     "-- soprattutto -- permettere al verificatore di misurare la distanza fra "
     "due carroponti mentre si muovono, che e' l'unico modo per accorgersi di "
     "una collisione che avviene a meta' di due corse."),
    ("c", "kinematics.position_profile"),

    ("h3", "La preparazione, e la troncatura di t"),
    ("c", "kinematics.position_profile", "d = abs(distance)", "if d >= d_acc"),
    ("p",
     "Le prime righe ripetono la struttura di travel_time: valore assoluto, "
     "caso nullo, soglia. La riga che conta e' quella che stringe t "
     "nell'intervallo valido."),
    ("p",
     "Senza quella riga, un t leggermente maggiore della durata totale -- "
     "com'e' facile che capiti quando i tempi arrivano da un modello a tick "
     "interi e vengono riconvertiti in secondi -- entrerebbe nel ramo di "
     "decelerazione con t_dec > 0 di troppo, e la parabola, superato il "
     "vertice, tornerebbe INDIETRO. Il carroponte risulterebbe arretrare di "
     "qualche millimetro alla fine di ogni corsa. Con la troncatura, un "
     "istante oltre la fine restituisce semplicemente la posizione di arrivo."),

    ("h3", "Le tre fasi del trapezio"),
    ("c", "kinematics.position_profile", "if d >= d_acc", "    else:"),
    ("p",
     "Le tre righe di ritorno sono le tre fasi, ciascuna con la sua legge:"),
    ("li", "rampa di salita: partenza da fermo, moto uniformemente "
           "accelerato, spazio = a*t^2/2;"),
    ("li", "crociera: si aggiunge allo spazio gia' fatto nella rampa il "
           "tratto a velocita' costante, v*(t - t_ramp);"),
    ("li", "rampa di discesa: dalla posizione raggiunta all'inizio della "
           "frenata si aggiunge v*t_dec meno il recupero a*t_dec^2/2."),
    ("p",
     "Ogni tratto riparte dalla posizione raggiunta alla fine del precedente, "
     "ricalcolandola invece di accumularla: e' il motivo per cui d_at_start_decel "
     "riscrive per esteso la somma dei primi due tratti. Costa due "
     "moltiplicazioni in piu' e in cambio rende ogni ramo leggibile e "
     "verificabile da solo, senza dover seguire uno stato che si trascina."),

    ("h3", "Le due fasi del triangolo"),
    ("c", "kinematics.position_profile", "    else:", None),
    ("p",
     "Piu' semplice: il vertice sta esattamente a meta' tempo, e la velocita' "
     "di picco v_peak = a * t_half e' quella raggiunta li'. Prima del vertice "
     "vale la stessa parabola della rampa di salita, dopo quella della "
     "frenata. Si osservi che v_peak e' sempre minore di v_max, altrimenti "
     "saremmo nell'altro ramo."),

    ("q",
     "LO SPOSTAMENTO E' SEMPRE POSITIVO. La funzione restituisce quanto si e' "
     "percorso, non dove ci si trova: il chiamante deve orientarlo lui, con "
     "partenza + risultato oppure partenza - risultato secondo la direzione. "
     "Il docstring lo dice a chiare lettere perche' e' esattamente il tipo di "
     "errore che non da' nessun sintomo finche' non si guarda un disegno e si "
     "vede un carroponte andare dalla parte sbagliata."),

    # ==================================================================
    ("h2", "4. profile_breakpoints -- gli spigoli"),
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
     "Le tre forme del risultato sono elencate nel docstring. Il caso a "
     "distanza nulla restituisce una tupla di UN solo elemento, non due "
     "coincidenti: chi la riceve puo' cosi' riconoscere un movimento che non "
     "avviene, invece di trovarsi un intervallo di durata zero da campionare."),
    ("p",
     "Con i valori tipici, un salto di 2500 mm a vuoto ha spigoli "
     "(0; 1,667; 3,333) -- triangolare, tre punti -- mentre uno di 10 000 mm "
     "ha (0; 1,778; 6,25; 8,028), dove si riconoscono la rampa di 1,78 s, la "
     "crociera fino a 6,25 s e la frenata finale."),
    ("q",
     "COERENZA FRA LE TRE FUNZIONI. profile_breakpoints ricalcola d_acc e "
     "t_ramp con le stesse formule di travel_time invece di chiamarla. Se un "
     "giorno si cambiasse il modello di moto -- per esempio aggiungendo il "
     "jerk, cioe' rampe di accelerazione non istantanee -- andrebbero cambiate "
     "TUTTE E TRE le funzioni insieme. Un profilo di posizione che non "
     "combacia con i suoi spigoli farebbe fallire il verificatore in modo "
     "difficilissimo da diagnosticare: segnalerebbe collisioni che non ci "
     "sono, o peggio, non ne segnalerebbe di vere."),

    # ==================================================================
    ("h2", "5. L'autotest in fondo al file"),
    ("p",
     "Il modulo non ha un file di test separato: si prova da solo con "
     "`python kinematics.py`. E' l'eccezione alla regola del progetto, ed e' "
     "giustificata dal fatto che qui non c'e' niente da preparare -- nessun "
     "file Excel, nessuna finestra, nessun solutore."),
    ("c", "kinematics", 'if __name__ == "__main__":'),
    ("p", "Le tre asserzioni provano tre proprieta' diverse, e non a caso:"),
    ("li", "la posizione al tempo T deve coincidere con la distanza totale: "
           "lega position_profile a travel_time, cioe' verifica che le due "
           "funzioni raccontino lo stesso movimento;"),
    ("li", "il primo spigolo deve essere 0 e l'ultimo deve coincidere con T: "
           "lega profile_breakpoints alle altre due;"),
    ("li", "gli spigoli devono essere crescenti: e' la proprieta' su cui conta "
           "chi li usa per costruire una griglia di campionamento."),
    ("p",
     "Le quattro distanze provate (0,1 / 1 / 5 / 20 con v=1 e a=0,5, quindi "
     "d_acc = 2) cadono due sotto e due sopra la soglia: entrambi i rami "
     "vengono percorsi. Un autotest che provasse solo distanze lunghe "
     "lascerebbe scoperto tutto il ramo triangolare, che e' proprio quello che "
     "sulle linee vere si usa di piu'."),

    # ==================================================================
    ("h2", "6. Una nota sulle unita', e un difetto dei commenti"),
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
