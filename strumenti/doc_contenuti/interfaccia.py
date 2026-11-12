"""
Il testo dei documenti di interfaccia.py.

Centoventitre fra funzioni e metodi, quasi tutti in una classe sola. Divisi
non per posizione nel file ma per GESTO dell'utente: costruire la finestra,
calcolare, comporre a mano, guardare.
"""

from __future__ import annotations

# ==========================================================================
# Documento 1 -- la finestra
# ==========================================================================

FINESTRA = [
    ("h1", "interfaccia.py (1) -- la finestra e i suoi tre stati"),
    ("p",
     "Primo dei quattro documenti su interfaccia.py, il programma che usa un "
     "utente normale. Qui c'e' come e' fatta la finestra e -- soprattutto -- "
     "quali stati puo' avere, che e' la cosa da capire prima di tutto il "
     "resto."),

    # ==================================================================
    ("h2", "Tre stati, non due piu' una scorciatoia"),
    ("p",
     "La decisione che governa tutta l'interfaccia sta in tre righe di "
     "__init__ e nei commenti che le accompagnano. L'utente puo' trovarsi in "
     "uno di tre stati, e sono tre gesti diversi:"),
    ("t", [
        ["stato", "ci si arriva con", "cosa si vede", "si puo' modificare"],
        ["leggere", "Calcola auto", "le traiettorie dei carroponti", "no"],
        ["comporre", "Calcola man", "il pettine dei pezzi", "si"],
        ["modificare", "Modifica", "il pettine dei pezzi", "si"],
    ]),
    ("q",
     "PERCHE' NON SI PUO' MODIFICARE SUBITO. Il commento in __init__ lo dice: "
     "dopo un calcolo automatico si sta LEGGENDO un risultato, e per metterci "
     "le mani bisogna dirlo premendo 'Modifica'. Cosi' i tre pulsanti sono tre "
     "stati veri invece di due piu' una scorciatoia, e un ciclogramma "
     "calcolato non si altera per sbaglio con un trascinamento di troppo. E' "
     "una frizione aggiunta apposta, ed e' quella che rende sicuro il resto."),
    ("p",
     "La VISTA -- ciclogramma o pettine -- non e' invece una scelta "
     "dell'utente: la decide il modo in cui ci e' arrivato. Un interruttore "
     "fra i due c'e' stato ed e' stato tolto, perche' le tabelle della scheda "
     "Ciclogramma permettono di modificare tutto senza cambiare disegno: "
     "restava un comando che chiedeva una decisione senza darne il motivo."),

    ("h3", "Le costanti"),
    ("c", "interfaccia", "_COLORI_GRAVITA", "def _durata_leggibile"),
    ("p",
     "Il commento sui tre valori del disegno manuale enuncia una disciplina: "
     "un solo grigio per tutto cio' che l'utente non ha ancora deciso, e due "
     "soli spessori. Il colore compare SOLO dove si e' assegnato un trasporto "
     "a un carroponte, e li' vuol dire quello e nient'altro. E' la stessa "
     "regola di plotting.py e della simulazione: il colore dice una cosa "
     "sola."),
    ("c", "interfaccia._durata_leggibile"),
    ("p",
     "Una durata come la direbbe una persona. Il docstring argomenta la "
     "soglia -- sotto il minuto i decimi si sentono, sopra non dicono piu' "
     "niente -- e un dettaglio che sembra pedanteria e non lo e': il secondo "
     "si scrive sempre, anche a zero, perche' '2 min' e '2 min 0 s' sembrano "
     "due precisioni diverse, e chi confronta due calcoli vuole leggere lo "
     "stesso formato tutte le volte."),

    # ==================================================================
    ("h2", "1. La barra del grafico"),
    ("c", "interfaccia._BarraGrafico", None, "    def __init__"),
    ("q",
     "PERCHE' AVVISARE L'APPLICAZIONE. Il docstring: il grafico viene "
     "ridisegnato da zero a ogni modifica, e senza sapere che l'utente ha "
     "ingrandito una zona, ogni clic gli farebbe saltare la vista al punto di "
     "partenza -- proprio mentre sta lavorando sul dettaglio per cui aveva "
     "ingrandito. E' un difetto che rende inutilizzabile un editor grafico, e "
     "si risolve solo intercettando i comandi della barra."),
    ("p",
     "`toolitems` ridichiara le voci con le descrizioni in italiano, e ne "
     "TOGLIE una: 'Configure subplots', che regola i margini. Il commento dice "
     "perche': qui i margini vengono comunque ricalcolati da tight_layout a "
     "ogni ridisegno, quindi quel comando non farebbe altro che sfasare il "
     "grafico."),
    ("p",
     "I nomi in prima colonna restano in INGLESE, ed e' un vincolo tecnico "
     "dichiarato nel commento: la barra ci cerca dentro 'Back' e 'Forward' per "
     "abilitarli. Tradurli spegnerebbe i due pulsanti senza nessun errore."),
    ("c", "interfaccia._BarraGrafico", "    def __init__", None),
    ("p",
     "Cinque metodi che chiamano il corrispondente di matplotlib e poi "
     "avvisano. `home` avvisa PRIMA, gli altri dopo: tornare alla vista intera "
     "significa che l'utente rinuncia alla sua inquadratura, e l'applicazione "
     "deve saperlo prima che la vista cambi."),

    # ==================================================================
    ("h2", "2. Lo stato dell'applicazione"),
    ("c", "interfaccia.Applicazione.__init__"),
    ("p",
     "Non costruisce quasi niente: dichiara lo stato. E' la parte piu' utile "
     "da leggere di tutto il modulo, perche' ogni campo porta con se' il "
     "motivo per cui esiste."),
    ("q",
     "IL CICLOGRAMMA E' TRE NUMERI. Il blocco di commento piu' lungo: un "
     "ciclogramma ha pochissimi gradi di liberta' reali, e sono gli stessi che "
     "si usano tracciandolo a mano su carta -- il takt time, il tempo in vasca "
     "di ogni tappa, e quale carroponte fa ogni trasporto. E vale IDENTICO per "
     "un ciclogramma calcolato dal solutore e per uno composto da zero: sono "
     "lo stesso oggetto. Il solutore ne produce uno, e i suoi tempi in vasca "
     "si rileggono dalla catena dei prelievi. E' per questo che si modificano "
     "allo stesso modo, in una pagina sola invece di due."),
    ("p",
     "`durata_calcolo` e' None quando il ciclogramma non viene da un calcolo. "
     "Il commento dice a cosa serve il numero: a sapere se conviene allargare "
     "il tempo limite, e a capire se una linea e' pesante da risolvere -- 'le "
     "due domande che ci si pone davanti a un risultato che non piace'."),
    ("p",
     "`verifica_viva` regola quando il verdetto compare. Non parte da sola, e "
     "il commento ne da' la ragione: comporre da zero vuol dire passare per "
     "stati dichiaratamente sbagliati, e un muro di errori rossi mentre si "
     "sceglie la prima mossa non informa nessuno. Una volta chiesta, pero', si "
     "tiene aggiornata da sola."),
    ("p",
     "`finestra_simulazione` non e' una scheda, ed e' voluto: la si guarda "
     "ACCANTO al ciclogramma, non al posto suo, e cosi' si puo' modificare da "
     "una parte e vedere l'effetto dall'altra."),
    ("p",
     "`righe_linea` tiene la linea COM'E' SCRITTA, accanto alla Configurazione "
     "che ne e' la lettura: il commento spiega che una cella 'posti' vuota "
     "nella Configurazione diventa 1, e la finestra 'Dati linea' deve "
     "mostrare il file dell'utente, non l'interpretazione del programma. "
     "`linea_modificata` dice quando la linea in uso viene da quella finestra "
     "e non corrisponde piu' al file: lo si scrive in barra e nel file dei "
     "risultati, che altrimenti indicherebbe come origine un file che dice "
     "un'altra cosa."),
    ("p",
     "`passaggi` sono i punti di passaggio aggiunti a mano (documento 3): un "
     "grado di liberta' in piu' del giro dei carroponti, che non va confuso "
     "con i punti del pettine -- quelli vengono dalla ricetta e non si "
     "tolgono."),

    ("h3", "La schermata di benvenuto"),
    ("p",
     "Con `con_splash` vero -- lo passa main, non l'autotest -- la finestra "
     "principale si nasconde con withdraw() e davanti compare _Splash. La "
     "ragione e' nel commento: la finestra si costruisce DIETRO, nascosta, e "
     "i tre secondi del benvenuto si contano da prima della costruzione, "
     "cosi' il tempo che serve a costruirla ci sta dentro invece di "
     "sommarsi. In fondo a __init__ si chiede allo splash quanto deve ancora "
     "restare (restante_ms) e si programma la chiusura dopo quel tempo."),
    ("q",
     "IL FILE INIZIALE SI APRE DOPO LO SPLASH. Il caricamento del file "
     "passato da riga di comando e' rimandato di 100 ms oltre la chiusura "
     "del benvenuto: un errore di lettura aprirebbe altrimenti un messaggio "
     "sopra una finestra che ancora non si vede."),
    ("c", "interfaccia.Applicazione._chiudi_splash"),
    ("p",
     "Distrugge il benvenuto e mostra la finestra vera: deiconify la rimette "
     "a schermo, lift e focus_force la portano davanti e le danno la "
     "tastiera, che altrimenti potrebbe restare a un'altra applicazione "
     "mentre lo splash era in primo piano."),

    ("h3", "La costruzione"),
    ("c", "interfaccia.Applicazione._costruisci_interfaccia"),
    ("p",
     "La finestra e' divisa in tre: la barra dei comandi in alto, il grafico a "
     "sinistra, e a destra un verdetto sempre in vista con sotto tre schede. "
     "In basso una barra di stato."),
    ("p",
     "I comandi sono raggruppati per gesto, e i commenti spiegano le "
     "posizioni: 'Dati linea...' accanto ad 'Apri linea...', sempre acceso "
     "perche' senza una linea parte da quella d'esempio; 'Fattibilita'' "
     "PRIMA di 'Calcola auto', perche' dice in un istante se il takt "
     "richiesto e' irraggiungibile e risparmia un calcolo lungo che non "
     "troverebbe niente; 'Ferma' e 'Pausa' subito dopo, perche' ne sono il "
     "contrario. Dopo il secondo separatore stanno le cose che si fanno a un "
     "ciclogramma gia' fatto: Simulazione, il pulsante che scorre i punti di "
     "avvio, 'Allinea avvio' e il salvataggio."),
    ("q",
     "LA BARRA DI STATO SI IMPACCHETTA PER PRIMA. Sta in fondo, ma pack da' "
     "lo spazio nell'ordine in cui i widget sono stati impacchettati: se il "
     "pannello di destra chiede piu' altezza di quella che c'e', l'ultimo "
     "resta schiacciato a zero. Era la barra di stato, e con lei la stima "
     "del tempo. Per questo `before=self.pack_slaves()[0]`."),
    ("c", "interfaccia._cornice_scorrevole"),
    ("p",
     "La scheda Ciclogramma e' la piu' alta, e Tk non scorre da se': taglia. "
     "Il docstring dice cosa veniva tagliato -- i pulsanti in fondo, Annulla, "
     "Verifica, Ottimizza, cioe' proprio quelli che si cercano. La funzione "
     "mette il contenuto in una tela con una barra di scorrimento e "
     "restituisce la cornice INTERNA, in cui si impacchetta come in una "
     "cornice qualsiasi."),
    ("p",
     "`adatta` da' alla cornice interna la larghezza della tela, cosi' i "
     "fill=X funzionano come prima, e ALMENO la sua altezza, cosi' gli "
     "expand=True si allargano quando lo spazio c'e' e si scorre solo quando "
     "non c'e'."),
    ("q",
     "LA ROTELLA ARRIVA DA OVUNQUE. `rotella` e' legata con bind_all, quindi "
     "riceve gli eventi di tutta l'applicazione, e deve scegliere da se' "
     "quando agire: solo se il puntatore sta sopra questa cornice, non se sta "
     "su una tabella che ha righe nascoste (si scorre da sola, e muovere "
     "anche la cornice farebbe muovere due cose insieme), non su uno spinbox "
     "o una combobox, e solo se c'e' davvero qualcosa da scorrere."),
    ("p",
     "Il grafico sta FUORI dalle schede, e non e' un dettaglio di "
     "impaginazione: e' la ragione per cui _su_pressione deve rifare da solo "
     "il controllo su `modifica_aperta`. Una scheda chiusa nasconde i suoi "
     "campi; il grafico resta li' e resta cliccabile."),
    ("c", "interfaccia.Applicazione._grafico_vuoto"),
    ("p",
     "Il riquadro con un messaggio al centro, per quando non c'e' niente da "
     "disegnare. Serve piu' di quanto sembri: un'area bianca senza scritte si "
     "legge come un programma che non ha capito il comando."),

    # ==================================================================
    ("h2", "3. Le utilita' di servizio"),
    ("c", "interfaccia.Applicazione._stato"),
    ("c", "interfaccia.Applicazione._errore"),
    ("c", "interfaccia.Applicazione._scrivi_riepilogo"),
    ("c", "interfaccia.Applicazione._svuota_tabella"),
    ("c", "interfaccia.Applicazione._mostra_percorso"),
    ("p",
     "Cinque metodi brevi. `_mostra_percorso` fa comparire il percorso "
     "completo del file, in barra e anche nel titolo della finestra: la barra "
     "dei comandi ha spazio limitato e un percorso lunghissimo li' viene "
     "tagliato, mentre il titolo lo mostra comunque. Completo e non solo il "
     "nome perche', come dice il commento nella costruzione, su un PC di "
     "stabilimento lo stesso file esiste in piu' copie, e sapere QUALE si sta "
     "guardando conta piu' del nome."),
    ("c", "interfaccia.Applicazione._descrizione_linea"),
    ("p",
     "Il testo che _mostra_percorso scrive, e lo stesso che finisce nel "
     "riepilogo e come `sorgente` nel file dei risultati. Distingue tre casi "
     "perche' il nome del file da solo ingannerebbe: una linea scritta nella "
     "finestra 'Dati linea' e mai salvata non ha un file, e una linea "
     "modificata li' non e' piu' quel file."),
    ("c", "interfaccia.Applicazione.destroy"),
    ("p",
     "La chiusura deve fare tre cose in ordine: chiudere la finestra della "
     "simulazione se e' aperta, fermare i timer, liberare la figura. Una "
     "finestra figlia che sopravvive al genitore resta a schermo senza piu' "
     "nessuno che la aggiorni."),

    # ==================================================================
    ("h2", "4. L'autotest e l'avvio"),
    ("p",
     "In fondo si lascia andare anche self.icona, per la stessa ragione delle "
     "icone della barra del grafico: un'immagine di Tk che sopravvive alla "
     "finestra viene cancellata dal garbage collector su un interprete che "
     "non c'e' piu', e stampa un traceback innocuo che sembra un guasto."),
    ("c", "interfaccia.autotest"),
    ("p",
     "Prova l'installazione da cima a fondo senza intervento umano: crea un "
     "modello Excel, lo legge, calcola, verifica, salva i risultati e "
     "l'immagine, e scrive un resoconto. E' quello che si lancia sul PC di "
     "stabilimento dopo aver copiato la cartella dell'eseguibile."),
    ("q",
     "LA FINESTRA VIENE APERTA DAVVERO. Non e' una prova delle sole funzioni "
     "di calcolo: costruisce l'Applicazione e ne pilota i metodi, facendo "
     "girare il ciclo degli eventi con update() invece di mainloop(). E' "
     "l'unico modo per accorgersi che manca una libreria grafica, che il "
     "backend di matplotlib non parte, o che un pulsante resta disabilitato -- "
     "cose che su un PC di stabilimento capitano, e che una prova del solo "
     "motore non vedrebbe."),
    ("h3", "Il nome e l'icona"),
    ("c", "interfaccia._applica_icona"),
    ("p",
     "Mette l'icona di CraneStrike sulla finestra principale e, con il primo "
     "argomento di iconphoto a True, su tutte quelle che si apriranno dopo: "
     "la simulazione la eredita senza doverlo ripetere."),
    ("p",
     "I file sono due, e se ne usa UNO SOLO. Su Windows l'ICO, che contiene "
     "le misure piccole gia' pronte: nel titolo l'icona e' di 16 pixel, e il "
     "PNG rimpicciolito da Tk viene seghettato. Sugli altri sistemi il PNG, "
     "che Tk legge ovunque."),
    ("q",
     "MAI TUTTI E DUE. La prima versione impostava il PNG con iconphoto e poi "
     "l'ICO con iconbitmap, per prudenza. Nessun errore, il test diceva "
     "'icona caricata', e nel titolo compariva l'icona generica di Windows. "
     "Chiedendolo a Windows (GetClassLongPtr, GCLP_HICONSM) si e' visto "
     "perche': la seconda chiamata toglie alla finestra l'icona PICCOLA, che "
     "e' proprio quella del titolo. Con uno solo dei due file l'icona c'e'. "
     "Il test dell'interfaccia ora controlla quel dato, non il caricamento."),
    ("c", "interfaccia._cartella_risorse"),
    ("p",
     "La cartella `risorse/` si cerca in sys._MEIPASS quando il programma e' "
     "impacchettato -- e' li' che PyInstaller mette i file dichiarati in "
     "`datas` -- e accanto al modulo altrimenti. La usano l'icona e lo "
     "splash, ed e' per questo una funzione a parte. In _applica_icona tutto "
     "sta in un try: un'icona che manca non e' un motivo per non aprire il "
     "programma."),
    ("c", "interfaccia._icona_barra_nitida"),
    ("p",
     "Su Windows, dopo l'ICO, _applica_icona chiama questa. Il problema e' "
     "un'icona SFOCATA sulla barra delle applicazioni: il docstring racconta "
     "che Windows 11 ci disegna l'icona grande della classe di finestra, Tk "
     "ci mette quella da 32 pixel, e la barra -- che al 100% ne vuole 24 -- "
     "la rimpicciolisce da se'. L'ICO ha gia' la misura giusta disegnata a "
     "mano: si carica quella con LoadImageW e la si mette sulla CLASSE con "
     "SetClassLongPtrW, perche' misurando si e' visto che WM_SETICON sulla "
     "finestra non cambia niente."),
    ("p",
     "`dpi_vero` esiste perche' il processo non dichiara di gestire i dpi, e "
     "Windows gli risponderebbe sempre 96: per un attimo si mette il thread "
     "in modalita' consapevole, si chiede, e si rimette com'era. Il lato e' "
     "24 pixel per la scala; se qualcosa va storto si torna a 96."),
    ("q",
     "SI ASPETTA LA PRIMA COMPARSA. `applica` e' legata all'evento <Map> e si "
     "slega da sola al primo giro: la cornice esterna della finestra, a cui "
     "si chiede l'handle con wm_frame(), esiste solo quando la finestra e' "
     "mappata. Basta farlo una volta, perche' la classe e' comune a tutte le "
     "finestre di primo livello di Tk. Un fallimento lascia l'icona di Tk: "
     "sfocata, ma c'e'."),
    ("p",
     "Quello che restituisce va TENUTO: __init__ lo mette in self.icona. Su "
     "Windows e' solo il percorso dell'ICO, ma altrove e' una PhotoImage, e "
     "Tk non conserva un riferimento alle immagini: raccolta dal garbage "
     "collector, la finestra tornerebbe all'icona predefinita."),
    ("c", "interfaccia._identita_windows"),
    ("p",
     "Il problema che risolve si vede solo lanciando da CraneStrike.bat o da "
     "python: il processo e' pythonw.exe, e Windows raggruppa la finestra "
     "sotto l'icona di Python sulla barra delle applicazioni, qualunque icona "
     "abbia la finestra. Un AppUserModelID proprio la separa. Va chiamata "
     "prima di creare la finestra, e per questo la chiama main e non "
     "__init__."),
    ("c", "interfaccia.main"),
    ("p",
     "`multiprocessing.freeze_support()` e' la prima riga, e serve solo "
     "all'eseguibile impacchettato: su Windows un processo figlio reimporta il "
     "modulo principale, e senza quella chiamata PyInstaller riaprirebbe la "
     "finestra invece di eseguire il figlio. Un difetto che si manifesta solo "
     "nella versione impacchettata, cioe' proprio dove e' piu' scomodo "
     "diagnosticarlo."),
    ("p",
     "Poi, nell'ordine: l'identita' per Windows, la finestra di ACCESSO "
     "(accesso.chiedi_accesso, che riceve _applica_icona per avere la stessa "
     "icona), e solo se si e' entrati l'Applicazione, con lo splash. Il "
     "commento e' esplicito: senza utente e password giusti la finestra "
     "principale non si costruisce nemmeno, e main restituisce 1. L'autotest "
     "non passa da qui -- esce prima, con --autotest -- e quindi non chiede "
     "credenziali e non mostra il benvenuto."),

    ("h3", "Il benvenuto"),
    ("c", "interfaccia._immagine_ridotta"),
    ("p",
     "Un PNG portato alla larghezza voluta. Con Pillow, che c'e' sempre "
     "perche' lo porta matplotlib, il ridimensionamento e' filtrato "
     "(LANCZOS); il ripiego e' `subsample` di Tk, che prende un pixel ogni "
     "tanti e sui bordi dei loghi lascia la seghettatura. Se non riesce "
     "nemmeno quello restituisce None, e chi la chiama mostra quello che "
     "c'e'."),
    ("c", "interfaccia._Splash"),
    ("p",
     "Una finestra senza bordi (overrideredirect), sempre in primo piano, al "
     "centro dello schermo: il logo del programma, il nome, e sotto 'powered "
     "by' col logo IMEL. Le misure sono pensate a 96 dpi e crescono con la "
     "scala dello schermo. Le immagini stanno in attributi per la ragione "
     "solita: senza riferimenti Tk le cancella. Se il logo IMEL manca, manca "
     "anche la scritta 'powered by', che da sola non vorrebbe dire niente."),
    ("q",
     "UPDATE() IN FONDO AL COSTRUTTORE. Subito dopo lo splash parte la "
     "costruzione dell'interfaccia, che tiene occupato il ciclo degli eventi: "
     "senza disegnarlo subito, il benvenuto resterebbe a schermo vuoto "
     "proprio per il tempo in cui deve farsi vedere."),
    ("p",
     "`restante_ms` dice quanto manca a DURATA_MS (tre secondi) dall'istante "
     "in cui lo splash e' nato, mai meno di zero: il benvenuto resta almeno "
     "tre secondi anche se la finestra e' pronta prima, e non di piu' se la "
     "costruzione ci mette di piu'. L'orologio e' monotono, come quello del "
     "calcolo."),
]


# ==========================================================================
# Documento 2 -- caricare, calcolare, salvare
# ==========================================================================

CALCOLO = [
    ("h1", "interfaccia.py (2) -- caricare, calcolare, salvare"),
    ("p",
     "Secondo dei quattro documenti su interfaccia.py: il giro che l'utente fa "
     "quando ha un file e vuole un risultato."),

    # ==================================================================
    ("h2", "1. Aprire una linea"),
    ("c", "interfaccia.Applicazione._chiedi_file"),
    ("c", "interfaccia.Applicazione._carica"),
    ("p",
     "Legge il file e ne ricava una Configurazione. Prima pero' chiede "
     "(_dati_linea_scartabili) se si possono perdere le modifiche non "
     "applicate della finestra 'Dati linea', se ce ne sono. Il percorso si "
     "rende assoluto e normalizzato: la finestra di dialogo di Tk restituisce "
     "le barre al contrario e dalla riga di comando puo' arrivare un percorso "
     "relativo, mentre quello che si legge in barra deve essere copiabile in "
     "Esplora risorse. Accanto alla Configurazione si leggono le RIGHE del "
     "file (righe_da_file); un file del vecchio formato, che non le da', si "
     "mostra come lo si e' letto, con righe_da_configurazione. Se la finestra "
     "'Dati linea' e' aperta, la si ricarica con la linea nuova."),
    ("c", "interfaccia.Applicazione._file_illeggibile"),
    ("p",
     "Gli errori di compilazione arrivano gia' pronti da excel_io -- tutti "
     "insieme, con foglio e cella -- e non si riscrivono. Ma un file che non "
     "passa i controlli (ValueError) si puo' correggere nella finestra 'Dati "
     "linea' invece che in Excel, e il messaggio lo propone. Un file che non "
     "e' nemmeno un Excel leggibile no: si dice perche' e basta."),
    ("q",
     "GLI ERRORI SI RICALCOLANO SULLE TABELLE. Il commento: le tabelle della "
     "finestra non hanno le righe vuote del foglio, e le celle indicate "
     "dall'errore del file punterebbero a righe sbagliate. Per questo si "
     "rilegge con leggi_righe e si mostra quell'errore."),
    ("c", "interfaccia.Applicazione._usa_linea"),
    ("p",
     "Il punto di passaggio di ogni linea nuova, che venga da un file o dalla "
     "finestra 'Dati linea': tutto cio' che dipendeva dalla linea di prima si "
     "azzera -- soluzione, tempi in vasca, assegnazione, attese, soste, punti "
     "di passaggio, origine, zoom -- e la simulazione aperta si CHIUDE: "
     "mostrava altre vasche e altre distanze, e non e' aggiornabile. Il "
     "riepilogo descrive la linea, compreso l'obiettivo che il calcolo "
     "inseguira': takt FISSO al teorico con i tempi in vasca vicini ai "
     "teorici, oppure il takt piu' corto nella banda e poi, a quel takt, i "
     "tempi in vasca. Se la linea porta con se' un ciclogramma, lo si "
     "riprende."),
    ("p",
     "Il commento su `attese` e `soste` dice cosa sono: dove ogni carroponte "
     "passa il tempo morto del rientro a vuoto, quando qualcuno (il solutore "
     "o il file) l'ha gia' deciso, e le soste in una vasca IN MEZZO al "
     "rientro. Per le attese None vuol dire 'regola predefinita'; per le "
     "soste non c'e' regola predefinita, una sosta per strada la sa proporre "
     "solo il solutore."),
    ("c", "interfaccia.Applicazione._riprendi_ciclogramma"),
    ("p",
     "Se il file porta con se' un ciclogramma, lo si rimette in piedi. E' la "
     "controparte del foglio Ciclogramma di excel_io: takt time, tempi in "
     "vasca, assegnazione -- piu' le attese, le soste e i punti di passaggio, "
     "quando ci sono -- e da quei valori _ricomponi ricostruisce tutto con "
     "manuale.componi. Una tappa che manca nel file prende il tempo teorico. "
     "La vista e' il ciclogramma se tutte le mosse sono assegnate, il "
     "pettine altrimenti: un ciclogramma a meta' ha trasporti che sulle "
     "traiettorie non comparirebbero."),
    ("q",
     "RIAPRIRE DEVE DARE LO STESSO CICLOGRAMMA. E' la proprieta' che "
     "test_interfaccia verifica esplicitamente, ed e' anche quella che ha "
     "fatto scoprire due difetti raccontati altrove: il salto di un periodo "
     "quando un istante cade appena sotto un multiplo esatto di T "
     "(_fase_nel_periodo), e le cifre tagliate nel salvataggio. Un formato "
     "compatto vale solo se il giro di andata e ritorno e' esatto."),
    ("c", "interfaccia.Applicazione._crea_modello"),
    ("p",
     "'Nuovo modello Excel...': crea un file gia' compilato con la linea "
     "d'esempio. E' la risposta alla prima domanda di chi non ha ancora "
     "niente."),

    # ==================================================================
    ("h2", "1 bis. La finestra 'Dati linea'"),
    ("p",
     "Le stesse tabelle del file, da guardare e modificare senza passare da "
     "Excel. La finestra vera e propria e' editor_linea.FinestraDatiLinea; "
     "qui c'e' solo il dialogo fra lei e l'applicazione."),
    ("c", "interfaccia.Applicazione._finestra_dati_aperta"),
    ("p",
     "Non basta che l'attributo non sia None: la finestra puo' essere stata "
     "chiusa dall'utente, e allora il riferimento c'e' ma il widget no. "
     "winfo_exists() lo dice."),
    ("c", "interfaccia.Applicazione._apri_dati_linea"),
    ("p",
     "Senza argomenti mostra la linea in uso, o quella d'esempio se non ce "
     "n'e' una. Con `righe` mostra quelle -- un file che non si e' riusciti a "
     "leggere, da correggere -- che NON sono la linea in uso, e infatti "
     "`applicate` e' falso. Se la finestra e' gia' aperta la si porta "
     "davanti invece di aprirne una seconda, e la si ricarica solo se le "
     "righe sono state passate esplicitamente o se non ha modifiche: chi "
     "preme di nuovo il pulsante non deve perdere quello che stava "
     "scrivendo."),
    ("c", "interfaccia.Applicazione._applica_dati_linea"),
    ("p",
     "La finestra la chiama quando l'utente applica le tabelle. Rifiuta se "
     "c'e' un calcolo in corso, e il messaggio dice di aspettare che finisca "
     "o di fermarlo: il calcolo sta lavorando sulla linea di prima. Gli errori di "
     "compilazione li solleva leggi_righe come ValueError, con foglio e "
     "cella, ed e' la finestra a mostrarli."),
    ("q",
     "IL CICLOGRAMMA DI PRIMA SI BUTTA, E LO SI CHIEDE. Come per un file "
     "nuovo: era della linea di prima, con altre vasche o altri tempi, e "
     "tenerlo vorrebbe dire mostrare traiettorie che i dati non giustificano "
     "piu'. Per questo, se un ciclogramma c'e', si chiede conferma prima di "
     "chiamare _usa_linea."),
    ("p",
     "La linea e' 'modificata' solo se ha un file di origine a cui non "
     "corrisponde piu'. Una linea scritta da zero nella finestra non ha "
     "file, e la descrizione lo dice gia' (vedi _descrizione_linea)."),
    ("c", "interfaccia.Applicazione._dati_linea_salvati"),
    ("p",
     "La finestra ha scritto le sue tabelle in un file. Se sono le stesse "
     "della linea in uso -- confrontate in forma normalizzata, non per "
     "identita' -- la linea in uso adesso E' quel file: cambia il percorso e "
     "smette di essere 'modificata'. Se sono diverse non si tocca niente: "
     "un file salvato non diventa la linea in uso finche' non lo si "
     "applica."),
    ("c", "interfaccia.Applicazione._dati_linea_scartabili"),
    ("p",
     "La domanda che _carica fa prima di aprire un altro file: le modifiche "
     "non applicate della finestra andrebbero perse. Se la finestra e' "
     "chiusa, o non ha modifiche, non c'e' niente da chiedere."),

    # ==================================================================
    ("h2", "2. Il calcolo in background"),
    ("p",
     "Un calcolo puo' durare minuti. Farlo nel thread della finestra la "
     "congelerebbe: niente si ridisegna, il puntatore diventa una clessidra, e "
     "Windows dopo qualche secondo propone di chiudere il programma che 'non "
     "risponde'. Va quindi fatto altrove, e il risultato riportato indietro."),
    ("c", "interfaccia.Applicazione._calcola_automatico"),
    ("c", "interfaccia.Applicazione._risolvi"),
    ("p",
     "`_risolvi` gira nel thread di lavoro, e il suo docstring e' un "
     "avvertimento in tre parole: niente widget qui dentro. Tkinter non e' "
     "sicuro da usare da piu' thread, e toccare un widget da qui produce "
     "blocchi e sparizioni che non si riproducono mai due volte uguali."),
    ("p",
     "Trovata una soluzione, prima di restituirla la si rifinisce con "
     "rifinisci_soluzione: col takt libero, a takt trovato, si avvicinano i "
     "tempi in vasca ai teorici; se CP-SAT e' scaduto prima dell'ottimo, si "
     "tolgono le soste per strada che non servono. Poi _allinea_nel_lavoro "
     "prova a rendere esatto il punto di avvio. Ognuna di queste fasi mette "
     "nella coda un messaggio 'stato' -- l'unico modo di parlare con la "
     "barra da questo thread -- perche' non hanno tentativi da contare e "
     "altrimenti la barra resterebbe ferma sull'ultimo tentativo della "
     "ricerca. Se una fase non riesce, la soluzione resta quella di prima."),
    ("c", "interfaccia.Applicazione._allinea_nel_lavoro"),
    ("p",
     "Il calcolo automatico rende esatto il punto di avvio da solo, cosi' "
     "l'utente non deve premere 'Allinea avvio' su ogni risultato (il "
     "pulsante resta per i ciclogrammi riletti da file o composti a mano, "
     "documento 4). Non lo fa se il calcolo e' stato fermato: chi ha premuto "
     "Ferma non vuole aspettare altro."),
    ("q",
     "UN RITOCCO NON DEVE MAI FAR PERDERE IL CALCOLO. L'except cattura tutto "
     "e restituisce la soluzione com'era: un allineamento che fallisce "
     "lascia un punto di avvio approssimato, mentre un'eccezione qui "
     "butterebbe via minuti di ricerca riuscita."),

    ("h3", "Prima di calcolare: la fattibilita'"),
    ("c", "interfaccia.Applicazione._mostra_fattibilita"),
    ("p",
     "Il pulsante 'Fattibilita'' sta prima di 'Calcola auto', e il commento "
     "nella costruzione dice perche': risponde in un istante se il takt "
     "richiesto e' irraggiungibile, cosi' non si aspetta mezz'ora un calcolo "
     "che non puo' trovare niente. Calcola i limiti inferiori del takt con "
     "fattibilita.valuta, con lo stesso numero massimo di carroponti che "
     "userebbe 'Calcola auto', e mostra il referto in una finestra a parte "
     "in carattere a spaziatura fissa, perche' e' un testo incolonnato. Non "
     "passa dal thread di lavoro: e' un conto e non una ricerca."),
    ("p",
     "La prima riga del referto va anche nella barra di stato: e' la "
     "conclusione, e resta leggibile dopo aver chiuso la finestra."),
    ("c", "interfaccia.Applicazione._avvia_lavoro"),
    ("p",
     "Il meccanismo e' una CODA: il thread ci mette dentro il risultato, e la "
     "finestra la controlla ogni 80 ms con `after`. E' il modo canonico di far "
     "parlare un thread con tkinter, ed e' l'unico che non richiede lock."),
    ("p",
     "L'involucro cattura QUALUNQUE eccezione e la mette in coda come testo. "
     "Un'eccezione non catturata in un thread secondario sparisce senza "
     "traccia: il programma resterebbe con la barra di avanzamento che gira "
     "per sempre, senza nessun messaggio."),
    ("q",
     "SI CRONOMETRA QUI, NON DENTRO IL SOLUTORE. Il commento argomenta: "
     "interessa quanto ha aspettato CHI GUARDA LO SCHERMO, e quello comprende "
     "tutti i tentativi di solve_auto_hoists piu' la verifica finale. Il tempo "
     "che OR-Tools riporta in solution.raw e' solo l'ultima chiamata, e su una "
     "linea che prova quattro numeri di carroponti direbbe una frazione del "
     "vero. L'orologio e' MONOTONO, cosi' non salta se cambia l'ora di "
     "sistema."),
    ("p",
     "Ogni lavoro riceve un'Interruzione NUOVA, passata come argomento alla "
     "funzione invece di essere letta da self nel thread: una richiesta di "
     "stop rimasta dal calcolo precedente non deve fermare quello nuovo appena "
     "parte, e il thread non deve dipendere da uno stato della finestra che "
     "nel frattempo potrebbe cambiare."),

    ("h3", "Fermare il calcolo"),
    ("c", "interfaccia.Applicazione._ferma_calcolo"),
    ("p",
     "Il pulsante Ferma chiede lo stop e basta. Non tocca la soluzione, non "
     "chiude niente e non aspetta: il thread di lavoro, fermato, restituisce "
     "il suo risultato nella coda come un calcolo finito, e lo gestisce "
     "_controlla_coda. Cosi' c'e' un solo percorso per la fine di un calcolo, "
     "e non due da tenere d'accordo."),
    ("p",
     "Quel risultato puo' essere di due tipi. Se al momento dello stop c'era "
     "gia' una soluzione valida, la si mostra e la si verifica come le altre, "
     "ma l'origine lo dice: 'la migliore trovata prima dello stop: valida, non "
     "dimostrata ottima' -- anche se l'ultima risoluzione aveva detto OPTIMAL, "
     "perche' e' ottima per le zone provate e le altre non lo sono state. Se "
     "non c'era niente, l'esito e' 'interrotto' e il ciclogramma che si stava "
     "guardando RESTA: chi ferma rinuncia al calcolo nuovo, non al lavoro di "
     "prima. _risolvi in quel caso salta anche la diagnosi, che sarebbero "
     "altre risoluzioni da aspettare su una linea che nessuno ha dimostrato "
     "impossibile."),
    ("p",
     "Lo stop non e' istantaneo -- misurato, fra 0,1 e 0,5 secondi -- e per "
     "questo il pulsante si spegne subito e la barra scrive 'Interruzione in "
     "corso...': un clic che non sembra fare niente viene ripetuto."),

    ("h3", "Mettere in pausa il calcolo"),
    ("c", "interfaccia.Applicazione._pausa_calcolo"),
    ("p",
     "Pausa e Riprendi sono lo stesso pulsante, e come Ferma chiedono e basta. "
     "Che la pausa sia cominciata davvero lo dice il thread di lavoro con un "
     "messaggio 'pausa' nella coda: a quel punto la barra lo scrive e si "
     "segna l'ora; alla ripresa _inizio_lavoro si sposta in avanti del tempo "
     "passato in pausa, cosi' la durata finale e la stima di quanto manca "
     "non lo contano. Il pulsante e' acceso solo quando l'Interruzione dice "
     "pausabile -- durante la ricerca delle suddivisioni -- e lo si ricontrolla "
     "a ogni giro di _controlla_coda. Un tentativo rifatto dopo la pausa si "
     "riannuncia con lo stesso indice, e non si conta due volte nella stima."),
    ("p",
     "Cosa vuol dire 'pausa' lo dice il commento nella costruzione: vale fra "
     "un tentativo e l'altro della ricerca, il tentativo in corso si ferma "
     "subito e alla ripresa si rifa' da capo, le soluzioni gia' trovate "
     "restano. Il pulsante ha larghezza fissa perche' l'etichetta cambia."),
    ("c", "interfaccia.Applicazione._aggiorna_pulsante_pausa"),
    ("q",
     "NESSUNO AVVISA QUANDO SI PUO' METTERE IN PAUSA. La ricerca entra ed "
     "esce dal tratto pausabile senza dirlo -- le rifiniture che seguono la "
     "ricerca non lo sono -- e per questo il metodo non e' chiamato da un "
     "evento ma a ogni giro di _controlla_coda, quando la coda e' vuota. "
     "Acceso se la pausa si puo' fare davvero, o se ce n'e' una in corso da "
     "finire; 'Riprendi' solo se si e' in pausa e nessuno ha chiesto lo "
     "stop. Si riconfigura il pulsante solo quando testo o stato cambiano: "
     "lo si chiama ogni 80 ms."),
    ("c", "interfaccia.Applicazione._mostra_pausa"),
    ("p",
     "La risposta al messaggio 'pausa' del thread di lavoro. Entrando in "
     "pausa si segna l'ora, si ferma la barra e si scrive cosa succede alla "
     "ripresa. Uscendo, il tempo passato in pausa si aggiunge a "
     "_inizio_lavoro: il docstring spiega che cosi' la durata finale e la "
     "stima di quanto manca lo ignorano senza doverlo sapere, perche' "
     "entrambe partono da quell'istante. 'Riprendo il calcolo...' non si "
     "scrive se nel frattempo e' stato chiesto lo stop: sarebbe falso."),

    ("h3", "L'avanzamento: quanto manca"),
    ("p",
     "Un calcolo puo' durare minuti, e una barra che oscilla non dice se manca "
     "un secondo o cinque. Il tempo pero' si scompone in due fattori, e solo "
     "uno dei due e' imprevedibile."),
    ("t", [
        ["fattore", "si sa prima?", "perche'"],
        ["quanti tentativi", "SI', esattamente",
         "combinatoria piu' due prefiltri deterministici"],
        ["quanto dura ognuno", "no",
         "da qualche centesimo a tutto il limite di tempo"],
        ["a quanti carroponti si ferma", "no",
         "e' l'informazione che la ricerca sta cercando"],
    ]),
    ("c", "interfaccia.Applicazione._segnala_tentativo"),
    ("p",
     "Il solutore la chiama prima di ogni tentativo, DAL THREAD DI LAVORO. Non "
     "tocca widget: mette il messaggio nella coda, che e' l'unico modo sicuro "
     "di parlare con la finestra da un altro thread. E' la stessa coda che "
     "porta indietro il risultato, usata per un secondo tipo di messaggio."),
    ("c", "interfaccia.Applicazione._mostra_avanzamento"),
    ("p",
     "I tentativi rimasti si sanno esattamente; quanto durera' ciascuno lo si "
     "MISURA su quelli gia' fatti. Al tentativo k ne sono conclusi k-1, e il "
     "tempo trascorso diviso quelli da' la durata media."),
    ("p",
     "Accanto al tempo, le SOLUZIONI GIA' TROVATE: il tempo che manca dice "
     "quanto costa aspettare, non cosa si perde a non aspettare. Con Ferma "
     "si tiene la migliore trovata, ma finche' non ce n'e' nessuna fermarsi "
     "vuol dire restare a mani vuote, e il testo lo dice anche e soprattutto "
     "quando il conteggio e' zero. Con il conteggio va il numero che dice "
     "quanto e' buona la migliore: il takt time, oppure -- col takt FISSO, "
     "uguale per tutte -- il suo scarto dai tempi teorici, in secondi veri e "
     "SENZA i pesi."),
    ("q",
     "LO SCARTO MOSTRATO NON E' QUELLO CHE IL CALCOLO MINIMIZZA. Il solutore "
     "lavora con lo scarto pesato (i pesi del foglio Percorso decidono dove "
     "spenderlo), ma un numero pesato non si legge come una durata. A "
     "schermo va quindi la somma degli scostamenti in secondi, come la "
     "passa il solutore in `best_errore`, con la sua unita' di misura. Prima "
     "si mostrava il pesato, senza unita': un numero che non diceva se il "
     "distacco fosse molto o poco."),
    ("q",
     "LA STIMA NON COMPARE SUBITO. Con meno di due tentativi conclusi la media "
     "e' un numero solo, e su una grandezza cosi' dispersa non vuol dire "
     "niente: meglio non dire un tempo che dirne uno sbagliato di dieci volte. "
     "Anche dopo resta una stima -- i tentativi che finiscono INFEASIBLE sono "
     "molto piu' rapidi di quelli che trovano una soluzione e devono "
     "dimostrarla ottima -- ma sulle linee di prova cade entro un fattore due, "
     "che basta a rispondere alla sola domanda che ci si pone davvero: "
     "aspetto, o mi alzo?"),
    ("q",
     "E COPRE SOLO QUESTO NUMERO DI CARROPONTI. Se anche l'ultimo tentativo "
     "fallisce, la ricerca ricomincia con un carroponte in piu' e il "
     "conteggio riparte da capo con un totale nuovo. E' una limitazione "
     "onesta, e si vede: il testo dice sempre a quale numero di carroponti si "
     "riferisce. Prima di cominciare non si stima invece niente -- l'unico "
     "numero calcolabile a priori sarebbe il caso peggiore, e sull'esempio "
     "darebbe sei minuti e mezzo contro sei secondi e mezzo reali. Un numero "
     "sessanta volte sbagliato non informa, spaventa."),
    ("p",
     "La barra parte INDETERMINATA e passa a determinata al primo tentativo "
     "segnalato. Con le zone dichiarate a mano nel file Excel il solutore fa "
     "una chiamata sola e non segnala niente, quindi resta a oscillare -- ed "
     "e' giusto: li' non c'e' un avanzamento da mostrare, c'e' un'unica "
     "attesa."),

    ("h3", "Il ritorno del risultato"),
    ("c", "interfaccia.Applicazione._controlla_coda", None,
     "        esito, sol, dati, report = carico"),
    ("p",
     "Si prova a leggere senza bloccare; se la coda e' vuota ci si riarma. Un "
     "'eccezione' produce un messaggio con la traccia completa: e' un difetto "
     "del programma, e nasconderla renderebbe impossibile capirlo."),
    ("q",
     "SI SVUOTA LA CODA, NON SI LEGGE UN MESSAGGIO SOLO. Il commento ne da' la "
     "ragione: i messaggi di avanzamento arrivano piu' in fretta di quanto si "
     "controlli, e leggerne uno per giro li farebbe accumulare. La barra "
     "resterebbe indietro rispetto al calcolo, che e' peggio di non averla. Il "
     "ciclo consuma tutti i messaggi intermedi e si ferma al primo messaggio "
     "di esito, che e' quello che chiude il lavoro."),
    ("p",
     "I messaggi intermedi sono di tre tipi: 'progresso' (un tentativo "
     "della ricerca, va a _mostra_avanzamento), 'stato' (una fase senza "
     "tentativi da contare, come la rifinitura: la barra torna a oscillare "
     "e si scrive la fase) e 'pausa' (va a _mostra_pausa). Quando la coda e' "
     "vuota, prima di riarmarsi si aggiorna il pulsante Pausa."),
    ("c", "interfaccia.Applicazione._controlla_coda",
     "        esito, sol, dati, report = carico",
     "        self.soluzione, self.dati, self.report = sol, dati, report"),
    ("q",
     "IL CASO PIU' CURATO E' QUELLO IN CUI NON SI TROVA NIENTE. Il riepilogo "
     "lo scrive _resoconto_fallimento, poco sotto: cinque leve in ordine di "
     "quanto e' probabile che siano loro il "
     "problema, e uno di essi -- infittire passo_controllo_distanza_mm -- si "
     "porta dietro la spiegazione di cosa sia, perche' e' il piu' oscuro e "
     "perche' e' facile scambiarlo per un margine di sicurezza. L'ultima riga "
     "offre la via d'uscita vera: comporlo a mano, e lasciare che il "
     "verificatore dica esattamente cosa manca."),
    ("p",
     "Il tempo di calcolo si dice ANCHE qui, e il commento spiega perche' e' "
     "il caso in cui serve di piu': se il calcolo ha consumato tutto il limite "
     "senza trovare niente, allungarlo e' la prima cosa da provare -- e senza "
     "il numero non si sa se il limite e' stato raggiunto o se la linea e' "
     "davvero infattibile."),
    ("h3", "Quando non si trova niente"),
    ("c", "interfaccia.Applicazione._resoconto_fallimento"),
    ("q",
     "IL REGISTRO C'ERA GIA', E NON VENIVA MOSTRATO. E' il difetto che questo "
     "metodo corregge, e non era innocuo: la ricerca automatica SALTA i numeri "
     "di carroponti per cui le suddivisioni da provare superano il limite, e "
     "senza il registro quel salto era invisibile. Una linea risolvibile con "
     "quattro carroponti poteva sembrare impossibile perche' nessuno aveva "
     "provato con quattro."),
    ("p", "Il resoconto ha tre parti, e ciascuna risponde a una domanda diversa."),
    ("li", "COSA E' STATO PROVATO -- per ogni numero di carroponti: quante "
           "suddivisioni risolte, con quale esito, quante scartate senza "
           "risolverle, e quali non sono state provate affatto;"),
    ("li", "PERCHE' NON RIESCE -- la diagnosi, se ha concluso qualcosa;"),
    ("li", "COSA SI PUO' FARE -- le leve, in ordine di quanto e' probabile che "
           "siano loro."),
    ("q",
     "UNKNOWN E INFEASIBLE VOGLIONO DUE AZIONI OPPOSTE. Il conteggio per stato "
     "e' li' per questo: INFEASIBLE e' una dimostrazione, e allora va cambiata "
     "la linea; UNKNOWN vuol dire solo che il tempo e' scaduto, e allora basta "
     "darne di piu' -- fra quei tentativi potrebbe esserci la soluzione. "
     "Confonderli manda a rifare il lavoro sbagliato, e il messaggio li separa "
     "con un avviso a parte."),
    ("c", "interfaccia.Applicazione._diagnostica"),
    ("p",
     "Gira nel thread di lavoro, subito dopo un calcolo fallito -- di "
     "'Calcola auto' come di 'Ottimizza con questi carroponti' (documento 3) "
     "-- e indaga sulla suddivisione col carico piu' equilibrato fra quelle "
     "provate con il numero PIU' ALTO di carroponti: e' quella che aveva piu' "
     "margine, quindi cio' che blocca lei blocca a maggior ragione le altre. "
     "Ogni risoluzione della diagnosi ha al massimo 20 secondi, o meno se il "
     "limite per tentativo della linea e' piu' corto."),
    ("p",
     "Costa qualche risoluzione in piu' su un calcolo che e' gia' fallito. "
     "Sembra molto e non lo e': l'alternativa e' che l'utente ripeta lo stesso "
     "calcolo tre volte cambiando un parametro a caso ogni volta."),
    ("p",
     "L'except cattura tutto: una diagnosi che fallisce non deve mai portarsi "
     "dietro il risultato del calcolo, che a quel punto e' l'unica cosa che "
     "l'utente ha."),

    ("c", "interfaccia.Applicazione._controlla_coda",
     "        self.soluzione, self.dati, self.report = sol, dati, report", None),
    ("p",
     "Riuscendo, si rimettono a posto tre cose che i commenti difendono una "
     "per una: `modifica_aperta` torna falsa (un risultato del solutore si "
     "LEGGE), la vista torna al ciclogramma (arrivando da 'Calcola man' era "
     "rimasta sul pettine, che e' il foglio su cui si compone), e "
     "`verifica_viva` diventa vera (il solutore ha gia' verificato, quindi da "
     "qui in poi il verdetto resta vivo)."),
    ("p",
     "L'`origine` distingue OPTIMAL da FEASIBLE con parole, non con la sigla: "
     "'ottimo' contro 'soluzione valida, non dimostrata ottima'. E' una "
     "differenza che conta per chi deve decidere se fidarsi del numero."),
    ("p",
     "La barra di stato riassume il risultato: quanto e' durato, il takt "
     "time, e -- quando il calcolo ha lavorato sullo scarto dai teorici, "
     "cioe' quando la soluzione porta `errore_pesato` -- lo scarto dai "
     "teorici in secondi, ricalcolato SENZA pesi con scarti_dal_teorico e "
     "scarto_totale: lo stesso numero, con la stessa unita', che il "
     "Riepilogo mostra e che la stima mostrava durante la ricerca. Se "
     "l'avvio e' stato reso esatto (_allinea_nel_lavoro) si dice anche "
     "quali carroponti sono stati spostati, e di quanti secondi."),

    # ==================================================================
    ("h2", "3. Quali pulsanti sono accesi"),
    ("c", "interfaccia.Applicazione._pronto_per_calcolare"),
    ("c", "interfaccia.Applicazione._aggiorna_stato_pulsanti"),
    ("p",
     "Un metodo solo che decide lo stato di tutti i comandi, richiamato dopo "
     "ogni cambiamento. E' la scelta giusta: distribuire le abilitazioni nei "
     "punti in cui lo stato cambia porta inevitabilmente a un pulsante che "
     "resta acceso quando non dovrebbe, e quel difetto non da' nessun errore "
     "-- solo un comando che poi non funziona."),
    ("p",
     "E' anche il metodo che i test dell'interfaccia interrogano di piu': "
     "verificare che un pulsante si accenda al momento giusto e' verificare "
     "che gli stati siano coerenti."),

    # ==================================================================
    ("h2", "4. Salvare"),
    ("c", "interfaccia.Applicazione._salva"),
    ("p",
     "Scrive il file dei risultati, che e' anche un file di ingresso: gli si "
     "passano `cfg` e il dizionario del ciclogramma, e cosi' lo stesso file si "
     "riapre con 'Apri linea...'. E' lo stesso formato che produce il comando "
     "da terminale -- uno solo, non due."),
    ("p",
     "Nel dizionario del ciclogramma ci sono anche attese, soste e punti di "
     "passaggio: senza, il file riaperto ricomporrebbe i rientri con la "
     "regola predefinita, e il ciclogramma non sarebbe piu' quello salvato. "
     "Il punto di avvio passato e' quello che si sta GUARDANDO, non il "
     "primo: se l'utente ha scorso i punti di avvio, il file deve dire "
     "quello che ha scelto, come il PNG che esce insieme. Se il ciclogramma "
     "non e' ancora stato verificato, la verifica si fa prima di salvare: il "
     "file dei risultati porta il referto."),
    ("c", "interfaccia.Applicazione._salva_immagine"),
    ("q",
     "SI SALVA IL CICLOGRAMMA, NON QUELLO CHE E' A SCHERMO. Il docstring lo "
     "dice in maiuscolo. Se l'utente sta componendo, a schermo c'e' il "
     "PETTINE: salvarlo darebbe un'immagine che non e' il ciclogramma e che "
     "nessuno saprebbe leggere fuori dal programma. L'immagine si costruisce "
     "quindi da capo, come traiettorie dei carroponti, col punto di avvio "
     "che si sta guardando e il logo. E' una delle poche volte in cui il "
     "programma NON fa quello che sembra -- e la scelta e' giusta, perche' "
     "quello che si consegna e' il ciclogramma."),
    ("p",
     "L'unica eccezione e' quando non c'e' nessuna traiettoria da tracciare "
     "-- per esempio nessun trasporto assegnato -- e plot_cyclogram solleva "
     "ValueError: allora si salva la figura a schermo, perche' meglio "
     "l'immagine di quello che si vede che nessuna immagine."),
]


# ==========================================================================
# Documento 3 -- comporre e modificare
# ==========================================================================

MODIFICA = [
    ("h1", "interfaccia.py (3) -- comporre e modificare a mano"),
    ("p",
     "Terzo dei quattro documenti su interfaccia.py. E' la parte che rende il "
     "programma qualcosa di piu' di un risolutore: si compone un ciclogramma "
     "come si e' sempre fatto su carta, e il solutore diventa una seconda "
     "opinione invece che un oracolo."),

    # ==================================================================
    ("h2", "Il principio: tutto passa da _ricomponi"),
    ("c", "interfaccia", "# Il ciclogramma: comporlo", "    def _stato_da_soluzione"),
    ("p",
     "Il commento di sezione enuncia la regola: cambio del takt, dei tempi in "
     "vasca, dell'assegnazione, trascinamento sul grafico -- tutto passa da "
     "_ricomponi(). E che il ciclogramma venga dal solutore o sia stato "
     "composto da zero non fa differenza: il solutore fornisce solo lo stato "
     "di partenza, e da li' in poi e' lo stesso oggetto modificato nello "
     "stesso modo."),
    ("c", "interfaccia.Applicazione._stato_da_soluzione"),
    ("q",
     "E' IL FATTO CHE RENDE POSSIBILE UNA PAGINA SOLA. Il docstring lo "
     "dichiara: i tempi in vasca sono le differenze della catena dei prelievi "
     "meno la durata del trasporto, e ricomporre il ciclogramma da quei valori "
     "restituisce ESATTAMENTE lo stesso ciclogramma -- stesso takt, stesso "
     "esito, nessuna incoerenza. Senza questa proprieta' ci sarebbero due "
     "editor, uno per i risultati del solutore e uno per i ciclogrammi "
     "manuali, e il primo sarebbe di sola lettura."),
    ("c", "interfaccia.Applicazione._ricomponi"),
    ("q",
     "NON RIFIUTA MAI NIENTE. Il docstring: manuale.componi disegna anche "
     "l'impossibile, e rifiutare una modifica vorrebbe dire rimettere i "
     "controlli proprio dove si e' scelto di toglierli -- e il verificatore li "
     "fa meglio. E' la stessa filosofia di manuale.py, applicata "
     "all'interfaccia: si mostra cosa non torna invece di impedirlo."),
    ("p",
     "L'unico caso in cui non fa niente e' un calcolo in corso, e il "
     "commento lo chiama 'ultima rete': qui passa OGNI modifica, quindi "
     "basta questa riga perche' nessuna possa infilarsi mentre il solutore "
     "lavora -- anche da una strada che oggi non esiste."),
    ("q",
     "LE PAUSE DEI RIENTRI SI TENGONO, RIENTRO PER RIENTRO. Attese e soste "
     "per strada erano state scelte per il ciclogramma di PRIMA. Buttarle "
     "tutte a ogni ritocco -- com'era una volta -- faceva sparire anche "
     "quelle dei rientri che la modifica non toccava, e il ciclogramma "
     "cambiava ben oltre il ritocco fatto. Adesso si compone una versione "
     "provvisoria con la regola predefinita, e manuale.adatta_rientri riporta "
     "su di lei "
     "quelle di prima, confrontando l'assegnazione di prima (prima[2], "
     "nell'istantanea) con quella nuova: restano dov'erano, accorciate se il "
     "tempo libero non basta piu', e solo i rientri nuovi passano alla "
     "regola predefinita."),
    ("p",
     "`tieni_rientri` salta del tutto quel passaggio: lo passano le "
     "modifiche che toccano solo i punti di passaggio, e 'Allinea avvio'. Il "
     "docstring: chi sposta una pausa su un rientro non deve vedersi "
     "cambiare tutte le altre."),

    # ==================================================================
    ("h2", "1. Entrare e uscire dalla modifica"),
    ("c", "interfaccia.Applicazione._vai_a_modifica"),
    ("p",
     "Il docstring chiarisce cosa NON fa: non sceglie fra una versione "
     "automatica e una manuale -- ce n'e' una sola -- ne' cambia niente. E' il "
     "momento in cui si dichiara di voler mettere le mani su un risultato, che "
     "e' diverso dal guardarlo."),
    ("q",
     "SI MODIFICA SEMPRE SUL PETTINE. Anche un ciclogramma appena calcolato. "
     "Il commento ne da' la ragione: il ciclogramma disegna le traiettorie dei "
     "CARROPONTI, e un trasporto che non e' ancora di nessuno -- o che si e' "
     "appena tolto a qualcuno -- li' non compare. Resterebbe invisibile e per "
     "giunta cliccabile, 'che e' il peggio'. Nel pettine il pezzo passa "
     "comunque, grigio finche' nessuno lo porta."),
    ("p",
     "L'ordine delle ultime chiamate non e' indifferente: prima si sblocca la "
     "scheda con _aggiorna_stato_pulsanti, poi la si seleziona. Selezionare "
     "una scheda disabilitata non fa niente e non da' errore."),
    ("c", "interfaccia.Applicazione._chiudi_modifica"),
    ("p",
     "Il docstring spiega perche' serve un'uscita: la modifica porta sul "
     "pettine, e senza un modo di uscirne chi ha ritoccato un tempo in vasca "
     "non rivedrebbe piu' il ciclogramma se non ricalcolandolo da capo. E "
     "precisa che non e' l'interruttore fra due viste che era stato tolto: e' "
     "l'uscita da uno stato di lavoro."),
    ("c", "interfaccia.Applicazione._componi_da_zero"),
    ("q",
     "SI PARTE DA NIENTE ASSEGNATO. Il commento difende la scelta contro "
     "l'alternativa apparentemente piu' gentile: partire da una suddivisione "
     "gia' fatta 'significava non avere mai niente da assegnare -- si restava "
     "a correggere una proposta invece di comporre'. Il pettine parte tutto "
     "grigio ed e' l'utente a darlo ai carroponti una mossa per volta, che e' "
     "il modo in cui un ciclogramma si traccia."),
    ("p",
     "`verifica_viva` resta falsa: si riparte da uno stato dichiaratamente "
     "provvisorio, e il verdetto arriva quando lo si chiede."),
    ("p",
     "Si buttano anche attese, soste e punti di passaggio. Il commento: dove "
     "i carri sostavano era una scelta fatta per il ciclogramma di prima, e "
     "qui non c'e' piu' nemmeno una mossa assegnata -- tenerla vorrebbe dire "
     "far aspettare un carro in un posto deciso per un giro che non esiste. "
     "Il numero di carroponti di partenza e' quello del foglio Zone, se la "
     "linea dichiara le portate, altrimenti due (o uno, se c'e' una mossa "
     "sola)."),

    # ==================================================================
    ("h2", "2. La scheda, e i campi"),
    ("c", "interfaccia.Applicazione._costruisci_scheda_ciclogramma"),
    ("p",
     "La pagina unica in cui il ciclogramma si modifica: takt time, numero di "
     "carroponti e carroponte attivo, la tabella dei tempi in vasca e quella "
     "dell'assegnazione. Gli stessi tre gradi di liberta', in forma di campi. "
     "Sotto, la tabella dei punti di passaggio (sezione 3 bis) e i tre "
     "pulsanti: Annulla modifica, Verifica adesso, Ottimizza con questi "
     "carroponti."),
    ("p",
     "La tabella dei tempi in vasca porta accanto al tempo il teorico, lo "
     "scarto e i limiti min e max. Il testo sotto la tabella dice la cosa "
     "importante: i limiti vengono dal teorico piu' o meno i delta, si "
     "possono sforare, e la verifica lo dira'. E' di nuovo il principio di "
     "_ricomponi: la tabella informa, non rifiuta."),
    ("c", "interfaccia.Applicazione._sincronizza_campi"),
    ("p",
     "Riporta nei campi i valori dello stato. Serve dopo ogni modifica fatta "
     "ALTROVE -- un trascinamento sul grafico, un annullamento -- perche' i "
     "campi e il grafico sono due viste dello stesso stato e devono restare "
     "d'accordo."),
    ("c", "interfaccia.Applicazione._popola_tabelle"),
    ("c", "interfaccia.Applicazione._carro_della_zona"),

    # ==================================================================
    ("h2", "3. I quattro modi di cambiare qualcosa"),
    ("c", "interfaccia.Applicazione._modifica_takt"),
    ("c", "interfaccia.Applicazione._modifica_permanenza"),
    ("c", "interfaccia.Applicazione._cambia_carroponti"),
    ("q",
     "CAMBIARE IL NUMERO NON RIDISTRIBUISCE LE MOSSE. La prima riga del "
     "docstring dice ancora 'ridistribuisce in blocchi contigui', ma il resto "
     "del docstring e il codice dicono il contrario: l'assegnazione la fa "
     "l'utente, e rifargliela sotto sarebbe buttare via il suo lavoro. "
     "Aggiungendo un carroponte lo si rende solo disponibile nel menu "
     "'attivo'; togliendone uno, le sue mosse -- e i suoi punti di passaggio "
     "-- passano all'ultimo rimasto, che e' l'unico modo di non scavalcare i "
     "vicini. Chi vuole una suddivisione gia' fatta ha il pulsante apposta."),
    ("p",
     "Se la linea dichiara le portate nel foglio Zone il numero non si "
     "cambia affatto: i carroponti sono quelli delle righe del foglio, uno "
     "in piu' non avrebbe una portata, e togliendone uno le sue mosse "
     "andrebbero a un vicino che magari non ci arriva. Lo spinbox torna al "
     "valore di prima e la barra dice dove si cambia davvero."),
    ("c", "interfaccia.Applicazione._modifica_numero_carroponti"),
    ("p",
     "'Ottimizza con questi carroponti': rifa' il calcolo tenendo fisso il "
     "numero e lasciando scegliere le zone. E' la via di mezzo fra il calcolo "
     "completamente automatico e la composizione a mano -- si sa quanti "
     "carroponti si hanno, non come dividerli. Le modifiche fatte a mano si "
     "perdono, e per questo e' un pulsante e non un effetto collaterale "
     "dello spinbox."),
    ("p",
     "Il lavoro segue la stessa strada di _risolvi, in piccolo: se non trova "
     "niente scrive nel registro dei tentativi la sua unica voce "
     "(voce_registro) e lancia la diagnosi -- il commento ricorda che senza, "
     "il resoconto diceva solo 'nessun registro dei tentativi' -- e se trova "
     "una soluzione prova a renderne esatto il punto di avvio con "
     "_allinea_nel_lavoro. Il risultato torna dalla coda e lo gestisce "
     "_controlla_coda, come quello di 'Calcola auto'."),
    ("c", "interfaccia.Applicazione._assegna"),
    ("q",
     "LO STESSO GESTO ASSEGNA E TOGLIE. Il docstring: si da' la mossa al "
     "carroponte attivo, o gliela si toglie se era gia' sua. E' la scelta che "
     "rende la composizione un lavoro fluido: non serve un comando 'togli', "
     "non serve selezionare prima. Si clicca finche' il disegno non e' quello "
     "che si vuole."),
    ("p",
     "Prima di assegnare si chiede a manuale.perche_non_va se l'assegnazione "
     "sarebbe geometricamente impossibile -- due carroponti che dovrebbero "
     "scavalcarsi sulla stessa rotaia. E' l'unico rifiuto di tutta la "
     "composizione, e il messaggio spiega quali carroponti e quali vasche."),
    ("c", "interfaccia.Applicazione._assegna_da_tabella"),
    ("p",
     "Lo stesso gesto, dalla tabella invece che dal grafico, ma con una "
     "differenza: il doppio clic non usa il carroponte attivo, fa GIRARE la "
     "mossa al carroponte successivo, e dopo l'ultimo la riporta a nessuno. "
     "Il commento spiega perche': cosi' il giro comprende anche il togliere, "
     "che dalla tabella altrimenti non si potrebbe fare. Un carroponte che "
     "scavalcherebbe i vicini si salta, quindi il doppio clic propone solo "
     "cose possibili; se nessuno puo', lo dice la barra. Due strade per lo "
     "stesso scopo: il grafico e' piu' rapido, la tabella e' piu' precisa "
     "quando i trasporti sono fitti."),

    # ==================================================================
    ("h2", "3 bis. I punti di passaggio"),
    ("p",
     "Un punto di passaggio dice: il carroponte deve trovarsi in questa "
     "posizione a questo istante, durante un rientro a vuoto. Due punti alla "
     "stessa posizione sono una sosta. Il commento nella scheda spiega perche' "
     "si inseriscono scrivendo tempo e posizione: e' cosi' che li si legge su "
     "un ciclogramma di carta, 'a 40 s deve essere a 4000 mm'. Nascono di "
     "nessuno, come i trasporti del pettine, e si danno a un carroponte con "
     "lo stesso gesto."),
    ("c", "interfaccia.Applicazione._aggiungi_passaggio"),
    ("p",
     "Il punto nuovo entra nella lista tenuta in ordine di tempo e "
     "posizione, i campi si svuotano per il prossimo, e la barra dice come "
     "proseguire: clic sul grafico per darlo al carroponte attivo. Come tutte "
     "le modifiche ai punti, passa da _ricomponi con `tieni_rientri`: un "
     "punto di nessuno non cambia nessun rientro."),
    ("c", "interfaccia.Applicazione._togli_passaggi"),
    ("p",
     "Toglie i punti selezionati (anche col tasto Canc). Solo quelli "
     "aggiunti a mano: i punti del pettine non stanno in questa tabella e "
     "non si tolgono, perche' vengono dalla ricetta. Senza selezione non "
     "toglie niente e dice cosa fare."),
    ("c", "interfaccia.Applicazione._passaggio_da_tabella"),
    ("c", "interfaccia.Applicazione._assegna_passaggio"),
    ("p",
     "Doppio clic sulla riga, o clic secco sul rombo nel grafico: in tutti e "
     "due i casi si arriva qui, che fa per i punti quello che _assegna fa per "
     "i trasporti -- il punto va al carroponte attivo, o gli viene tolto se "
     "era gia' suo. A differenza dei trasporti non si chiede niente a "
     "manuale.perche_non_va: vale il principio di _ricomponi, si mostra cosa "
     "non torna invece di impedirlo."),

    # ==================================================================
    ("h2", "4. Annullare"),
    ("c", "interfaccia.Applicazione._istantanea"),
    ("c", "interfaccia.Applicazione._annulla_modifica"),
    ("p",
     "L'annullamento e' una pila di ISTANTANEE dello stato -- takt, "
     "permanenze, assegnazione, numero di carroponti, punti di passaggio, "
     "attese e soste -- non di comandi inversi. E' molto piu' semplice da "
     "rendere corretto: uno stato ripristinato e' esattamente quello di "
     "prima, mentre un comando inverso puo' sempre avere un caso che non "
     "copre."),
    ("q",
     "LE PAUSE STANNO NELL'ISTANTANEA. Da quando _ricomponi le adatta invece "
     "di buttarle, una modifica puo' accorciarle; senza attese e soste "
     "nell'istantanea, il commento lo dice, annullare la modifica le avrebbe "
     "lasciate come la modifica le aveva ridotte. I dizionari e i punti si "
     "COPIANO: un'istantanea che condivide gli oggetti con lo stato verrebbe "
     "cambiata dalla modifica successiva."),
    ("p",
     "Costa memoria, e qui non e' un problema: lo stato sono pochi "
     "dizionari piccoli, e le modifiche in una sessione sono decine, non "
     "milioni."),

    # ==================================================================
    ("h2", "5. Il verdetto"),
    ("c", "interfaccia.Applicazione._verifica_adesso"),
    ("c", "interfaccia.Applicazione._popola_verifica"),
    ("c", "interfaccia.Applicazione._esito_breve"),
    ("c", "interfaccia.Applicazione._aggiorna_banner_e_riepilogo"),
    ("p",
     "Il verdetto sta sempre in vista, sopra le schede, e cambia colore con la "
     "gravita' peggiore trovata. E' la scelta che rende la composizione a mano "
     "praticabile: si vede subito se l'ultima modifica ha risolto o rotto "
     "qualcosa, senza dover andare a cercare."),
    ("c", "interfaccia.Applicazione._banner_neutro"),
    ("p",
     "Il banner quando non c'e' niente da giudicare: una linea appena "
     "caricata, un calcolo fallito. Grigio e senza verdetto, perche' quello "
     "del ciclogramma di prima, letto accanto a un'altra linea o a un "
     "calcolo che non ha trovato niente, direbbe una cosa falsa."),
    ("p",
     "Il riepilogo raccoglie tutto quello che si vorrebbe sapere di un "
     "ciclogramma: da dove viene (e se e' stato poi modificato a mano), il "
     "tempo di calcolo, takt e produttivita', lo scarto dai teorici, i "
     "carroponti con le loro mosse, i tempi in vasca, il punto di avvio, le "
     "soste per strada, le mosse ancora da assegnare, e alla fine la "
     "distanza minima fra i carroponti e il verdetto. I numeri sono scritti "
     "come nel foglio Riepilogo del file dei risultati -- i secondi del "
     "punto di avvio con due decimali, per esempio -- perche' le due scritte "
     "si confrontano, e '16.6' accanto a '16,60' fa dubitare."),
    ("q",
     "LE INCOERENZE VENGONO PRIMA DI TUTTO. Se manuale.componi ne ha "
     "trovate, il banner diventa arancione e il riepilogo parla solo di "
     "quelle. Il commento racconta perche': il disegno le assorbe allungando "
     "un'attesa e tirando dritto, e il risultato e' una riga orizzontale "
     "lunghissima che sembra una stranezza del grafico, mentre e' il "
     "sintomo. Si calcolavano gia' e non si mostravano: chi riapriva un file "
     "rotto vedeva la riga e non sapeva cosa fosse."),
    ("c", "interfaccia.Applicazione._scarto_corrente"),
    ("p",
     "Lo scarto dai teorici del ciclogramma a schermo, in secondi e SENZA "
     "pesi: la somma di quanto ogni bagno si scosta dal suo teorico, sopra o "
     "sotto. Il docstring spiega la scelta: i pesi decidono dove il calcolo "
     "spende lo scarto, ma il numero pesato non si legge come una durata, "
     "mentre questo dice quanti secondi di distacco ci sono davvero."),
    ("p",
     "Si calcola dai tempi in vasca e non dalla soluzione del solutore: "
     "cosi' vale anche per un ciclogramma composto o ritoccato a mano, ed e' "
     "il numero con cui confrontarlo con quello del calcolo automatico."),
    ("q",
     "LA NOTA ACCANTO AL NUMERO. Col takt fisso il riepilogo aggiunge 'e' "
     "cio' che Calcola auto rende minimo'; col takt libero, su un risultato "
     "del calcolo non ritoccato, 'minimo a parita' di takt'. A essere "
     "minimizzato, pero', e' lo scarto PESATO (model.scarto_totale lo dice: "
     "il pesato resta l'obiettivo del calcolo). Con tutti i pesi uguali, "
     "sopra e sotto, i due "
     "minimi coincidono, con pesi diversi il numero mostrato puo' non essere "
     "il piu' piccolo possibile. La nota va letta come 'e' la grandezza su "
     "cui il calcolo lavora', non come una garanzia sul valore."),
    ("c", "interfaccia.Applicazione._tabella_tempi_in_vasca"),
    ("p",
     "Teorico, effettivo, scarto e sgocciolamento di ogni vasca, come righe "
     "incolonnate. La stessa cosa sta nella tabella della scheda "
     "Ciclogramma, ma quella si apre solo per modificare: qui la si legge "
     "accanto al takt time e allo scarto dai teorici, che sono i numeri con "
     "cui la si giudica. Lo sgocciolamento sta accanto e non dentro "
     "l'effettivo: e' tempo che il telaio passa sopra la vasca DOPO il "
     "bagno."),
    ("p",
     "Le vasche fuori tolleranza si segnano con '< min' o '> max', perche' "
     "in una colonna di numeri non si vedono: il verdetto lo da' la "
     "verifica, il segno dice dove guardare. Con mezzo centesimo di "
     "tolleranza, lo stesso dei valori mostrati: un bagno sul minimo, "
     "arrotondato, non deve sembrare fuori."),
]


# ==========================================================================
# Documento 4 -- il grafico, il mouse, la simulazione
# ==========================================================================

GRAFICO = [
    ("h1", "interfaccia.py (4) -- il grafico, il mouse, la simulazione"),
    ("p",
     "Quarto e ultimo documento su interfaccia.py: come si disegna, come si "
     "clicca, e come si apre la vista in movimento."),

    # ==================================================================
    ("h2", "1. I due disegni"),
    ("c", "interfaccia.Applicazione._mostra_ciclogramma"),
    ("p",
     "Sceglie quale dei due disegnare secondo `self.vista`, e riapplica "
     "l'inquadratura se l'utente ne aveva scelta una. Prima pero' ricalcola i "
     "punti di avvio: e' il passaggio obbligato di ogni ridisegno, ed e' da "
     "li' che il grafico e il riepilogo prendono lo stesso istante."),

    # ==================================================================
    ("h2", "1 bis. I punti di avvio, e il pulsante che li scorre"),
    ("p",
     "Gli istanti da cui la linea si puo' mettere in marcia (vedi avvio.py) non "
     "sono uno: sono tutti quelli che sbagliano uguale, e stanno lontani fra "
     "loro. Quale convenga lo sa chi conosce l'impianto, quindi il programma "
     "li mostra tutti e lascia scegliere. Uno pero' lo propone per primo: "
     "avvio.trova_avvii mette in testa alla lista l'istante con PIU' "
     "MARGINE -- un avvio esatto ma lungo un attimo non lascia tempo ne' "
     "prima ne' dopo -- e gli altri a seguire in ordine di tempo lungo il "
     "giro. E' quello che la finestra mostra appena calcolato e quello che "
     "finisce nel file, se non se ne sceglie un altro."),
    ("c", "interfaccia.Applicazione._aggiorna_avvii"),
    ("q",
     "SI RICALCOLANO DA UN POSTO SOLO. Il grafico, il riepilogo e il "
     "salvataggio devono mostrare lo STESSO istante: tre calcoli separati in "
     "tre momenti diversi non lo garantirebbero, e si finirebbe per salvare un "
     "istante diverso da quello che si ha davanti."),
    ("p",
     "L'indice di quello che si sta guardando si conserva solo se i punti di "
     "avvio NON sono cambiati. Un ridisegno che non tocca il ciclogramma -- si "
     "passa da una vista all'altra, si riapre la simulazione -- non deve far "
     "saltare la linea nera altrove; un ciclogramma diverso invece ha istanti "
     "diversi, e il terzo di prima non e' il terzo di adesso. Il confronto si fa "
     "sui TEMPI e non sul numero: due liste lunghe uguale ma con istanti diversi "
     "sono due cose diverse."),
    ("c", "interfaccia.Applicazione._avvio_corrente"),
    ("c", "interfaccia.Applicazione._t_avvio"),
    ("p",
     "Due letture dello stesso dato. L'Avvio intero serve al grafico, al "
     "riepilogo e al salvataggio; la simulazione vuole solo l'istante da cui "
     "ripartire, e _t_avvio glielo da' senza che chi la chiama debba "
     "controllare se un avvio c'e'."),
    ("c", "interfaccia.Applicazione._prossimo_avvio"),
    ("p",
     "Scorre in tondo: dopo l'ultimo si torna al primo. Sono tutti equivalenti, "
     "quindi non c'e' un ultimo oltre il quale si e' finito -- c'e' un giro di "
     "istanti fra cui scegliere."),
    ("p",
     "Non passa da _mostra_ciclogramma: gli istanti sono gli stessi, cambia "
     "solo quale si guarda, e ricalcolarli azzererebbe l'indice appena mosso. "
     "Per la stessa ragione non RICOSTRUISCE la simulazione: il punto di "
     "avvio non cambia il ciclogramma, dice solo da dove lo si legge. Le "
     "dice pero' da dove ripartire, con imposta_avvio."),
    ("c", "interfaccia.Applicazione._aggiorna_pulsante_avvio"),
    ("p",
     "A parte e non dentro _aggiorna_stato_pulsanti, che dipende da cosa c'e' "
     "caricato e da cosa sta girando: questo dipende da quanti istanti sono "
     "venuti fuori, che cambia in un altro momento. Lo chiamano tutti e due, "
     "cosi' non resta indietro ne' nell'uno ne' nell'altro caso."),
    ("p",
     "L'etichetta porta il conto ('Avvio 1 di 5'): dice da sola che ce ne sono "
     "altri, che altrimenti non si saprebbe. Larghezza fissa nel costruttore, se "
     "no ballerebbe passando da 'di 5' a 'di 1'. Spento quando ce n'e' uno solo: "
     "non c'e' niente dove andare."),
    ("p",
     "Qui si decide anche 'Allinea avvio', perche' dipende dalla stessa "
     "cosa: acceso solo se il punto di avvio corrente e' APPROSSIMATO e non "
     "c'e' un calcolo in corso. Un avvio gia' esatto non ha niente da "
     "allineare."),
    ("c", "interfaccia.Applicazione._allinea_avvio"),
    ("p",
     "Quando nessun istante del giro ha errore zero, allinea_avvio cerca "
     "uno spostamento rigido nel tempo del giro di qualche carroponte che lo "
     "renda esatto, restando nelle tolleranze e senza collisioni. Il "
     "calcolo automatico lo fa da solo (_allinea_nel_lavoro, documento 2); "
     "il pulsante serve ai ciclogrammi riletti da file o composti a mano."),
    ("p",
     "Per la finestra e' una modifica come le altre, e il docstring elenca "
     "cosa vuol dire: i tempi in vasca si rileggono dalla soluzione "
     "allineata, come in _stato_da_soluzione; si annulla con Annulla; i "
     "punti di passaggio si spostano col loro carroponte, della stessa "
     "quantita'. Attese e soste si prendono dalla soluzione allineata e si "
     "tengono (`tieni_rientri`): dentro il giro di un carroponte non cambia "
     "niente, quindi sono ancora giuste, e ricadere sulla regola "
     "predefinita disegnerebbe rientri diversi da quelli appena verificati."),
    ("p",
     "A differenza del calcolo gira nel thread della finestra, senza Ferma "
     "ne' Pausa: il puntatore diventa una clessidra finche' non ha finito, "
     "e un errore si mostra senza toccare niente. La barra di stato dice quali "
     "carroponti sono stati spostati e lo scarto dai teorici prima e dopo, "
     "in secondi senza pesi; se nessuno spostamento funziona lo dice, e non "
     "cambia niente."),
    ("c", "interfaccia.Applicazione._disegna_traiettorie"),
    ("p",
     "Il ciclogramma vero e proprio, delegato a plotting.plot_cyclogram sullo "
     "stesso asse. E' la stessa funzione che produce il PNG e quella che usa "
     "il comando da terminale: un solo disegno, non tre."),
    ("c", "interfaccia.Applicazione._disegna_pettine"),
    ("p",
     "Il foglio su cui si compone: una scalinata per ogni pezzo in "
     "lavorazione, e i trasporti colorati per carroponte. Quello che nessuno "
     "ha ancora preso resta grigio e sottile."),
    ("q",
     "IL GRIGIO NON E' UN COLORE FRA GLI ALTRI. Con la disciplina dichiarata "
     "in testa al modulo -- un solo grigio per cio' che non e' deciso, due "
     "soli spessori -- il disegno risponde a colpo d'occhio alla sola domanda "
     "che conta durante la composizione: cosa manca ancora. Dando un colore "
     "anche ai trasporti liberi, quella domanda richiederebbe di leggere."),
    ("p",
     "Anche il pettine porta i suoi PUNTI, e sono i QUATTRO che il ciclogramma "
     "marca su ogni trasporto -- aggancio, partenza, arrivo, immersione -- "
     "presi da plotting.eventi_del_trasporto, cioe' dall'unica definizione che "
     "hanno. Servono perche' su una linea con molte tappe un trasporto corto "
     "non si distingue da una sosta se non seguendo la pendenza, e la pendenza "
     "su pochi pixel non si vede."),
    ("q",
     "IL GIRO SI POSA SUI PUNTI CHE ERANO GIA' LI'. E' la proprieta' per cui i "
     "punti valgono la pena: assegnando una mossa, i quattro istanti che il "
     "carroponte marca cadono ESATTAMENTE su quelli che il pettine mostrava in "
     "grigio. Sono lo stesso fatto visto dal pezzo e dal carroponte. Prima il "
     "giro ne marcava due -- i soli estremi della traslazione -- e assegnare "
     "sembrava cambiare cio' che il pezzo fa; ora i due disegni si "
     "sovrappongono, e test_interfaccia lo verifica confrontando le due liste "
     "modulo il takt time."),
    ("p",
     "A quale mossa appartiene ogni tratto della scalinata lo dice "
     "manuale.mosse_del_pettine, non un contatore: la scalinata ha un tratto a "
     "carico per mossa, ma dedurlo dall'ordine sarebbe un'ipotesi sulla "
     "costruzione invece di una domanda a chi la costruisce."),
    ("p",
     "Sono piu' piccoli e senza bordo bianco di quelli dei carroponti: il "
     "pettine e' lo sfondo su cui si lavora, e deve restare leggibile SOTTO il "
     "giro che si sta componendo invece di contendergli l'occhio."),
    ("p",
     "Sopra il pettine, il giro di ogni carroponte, ripetuto sui cicli: "
     "colore del carroponte, linea spessa, e punti sugli stessi istanti del "
     "ciclogramma (sui rientri, gli estremi delle traslazioni). Poi i punti "
     "di passaggio aggiunti a mano, come ROMBI: tondi sono i punti del "
     "pettine, che vengono dalla ricetta, a rombo quelli dell'utente, e solo "
     "questi si tolgono. Vuoti finche' non sono di nessuno, pieni del colore "
     "del carroponte che ci passa. Le posizioni ripetute le da' "
     "_ripetizioni_passaggi, la stessa funzione che usa il mouse per "
     "trovarli."),
    ("p",
     "Infine la linea nera del punto di avvio, su tutte le ripetizioni "
     "disegnate e con la stessa funzione del ciclogramma "
     "(plotting.disegna_avvio), cosi' le due viste non possono metterla in "
     "due punti diversi. Il commento dice perche' serve anche qui: "
     "componendo si sposta il ciclogramma, e vedere dove va a finire "
     "l'istante di avvio mentre lo si fa e' meta' del motivo per cui "
     "esiste."),
    ("q",
     "UN DISEGNO SOLO, CON I NaN A SEPARARE I TRATTI. Vale per il pettine come "
     "per i carroponti poco piu' sotto: con dieci scalinate e diciassette "
     "mosse, una chiamata di disegno per tratto sono seicento artisti -- e di "
     "ritocchi se ne fanno molti di seguito, ciascuno dei quali ridisegna "
     "tutto da capo. Raggruppando, il pettine intero sta in due chiamate: la "
     "linea e i punti."),

    # ==================================================================
    ("h2", "2. Cliccare e trascinare"),
    ("c", "interfaccia.Applicazione._punti_prelievo"),
    ("c", "interfaccia.Applicazione._tratti_trasporto"),
    ("p",
     "Le due geometrie su cui il mouse lavora: i punti di prelievo (le "
     "maniglie) e i tratti dei trasporti (le zone cliccabili). Si ricavano "
     "dalle stesse funzioni di manuale.py che producono il disegno, non da un "
     "calcolo parallelo -- altrimenti la zona sensibile e quello che si vede "
     "potrebbero non coincidere."),
    ("c", "interfaccia.Applicazione._trasporto_sotto"),
    ("q",
     "SI MISURA IN PIXEL. Il docstring lo argomenta: in coordinate dati un "
     "secondo e un millimetro non sono paragonabili, e la tolleranza sarebbe "
     "assurda. Una soglia di 12 pixel vuol dire la stessa cosa a qualunque "
     "ingrandimento, mentre una soglia in secondi diventerebbe enorme "
     "ingrandendo e microscopica allargando."),
    ("c", "interfaccia.Applicazione._ripetizioni_passaggi"),
    ("p",
     "Dove si vede ogni punto di passaggio: ripetuto a ogni takt time, "
     "perche' il carroponte ci ripassa a ogni giro. Il docstring aggiunge "
     "che vale anche per un punto ancora di nessuno, che e' periodico quanto "
     "quello che diventera'. Solo sul pettine, che e' la vista in cui si "
     "modifica: sul ciclogramma la lista e' vuota, e i rombi non si "
     "disegnano."),
    ("c", "interfaccia.Applicazione._passaggio_sotto"),
    ("p",
     "La stessa misura in pixel dei trasporti, con un raggio piu' stretto -- "
     "9 pixel invece di 12 -- perche' il bersaglio e' un punto e non un "
     "tratto."),
    ("c", "interfaccia.Applicazione._su_pressione"),
    ("q",
     "IL GRAFICO STA FUORI DALLA SCHEDA. Il commento spiega perche' qui si "
     "ricontrolla `modifica_aperta`: il cancello della scheda non copre il "
     "grafico, quindi senza questo controllo trascinare un prelievo su un "
     "risultato appena calcolato lo modificherebbe senza che nessuno abbia "
     "detto di volerlo. E' la stessa difesa che _vai_a_modifica costruisce, "
     "rifatta dove serve."),
    ("p",
     "Prima di tutto si cerca un punto di passaggio, e il commento spiega "
     "l'ordine: e' piccolo e sta spesso sopra un tratto del pettine, e chi "
     "lo centra vuole proprio lui. Se c'e', il trascinamento lo ricorda con "
     "le coordinate di partenza in dati e in pixel, su tutti e due gli assi: "
     "un punto si sposta nel tempo E nella posizione."),
    ("p",
     "Altrimenti il commento lungo distingue DUE bersagli con due raggi "
     "diversi, e la ragione e' nel gesto:"),
    ("li", "il PUNTO DI PRELIEVO e' la maniglia per trascinare -- il tempo in "
           "vasca si allunga da li', quindi il trascinamento ha senso solo "
           "prendendolo per quell'estremo. Raggio stretto, 18 pixel;"),
    ("li", "il TRATTO si clicca dove lo vedi, per tutta la sua lunghezza: "
           "assegnare una mossa a un carroponte non ha niente a che fare con "
           "un estremo particolare, e 'obbligare a centrare la vasca di "
           "partenza era una precisione chiesta senza motivo'."),
    ("p",
     "L'istantanea dello stato viene presa alla PRESSIONE, non al rilascio: "
     "cosi' l'annullamento riporta a prima del gesto, qualunque cosa il gesto "
     "sia risultato essere."),
    ("c", "interfaccia.Applicazione._su_movimento"),
    ("p",
     "Durante il trascinamento si mostra una guida verticale arancione e si "
     "scrive lo spostamento nella barra di stato. Non si ricompone niente: "
     "ricostruire il ciclogramma a ogni pixel sarebbe lento e "
     "illeggibile. Due casi non trascinano affatto -- una pressione a meta' "
     "tratto (nessuna maniglia) e la mossa 0, che e' l'origine dei tempi. "
     "Un punto di passaggio trascinato non ha guida: la barra scrive dove "
     "finirebbe, in secondi e millimetri."),
    ("c", "interfaccia.Applicazione._su_rilascio"),
    ("q",
     "CLIC SECCO O TRASCINAMENTO? SI MISURA IN PIXEL. Il commento: in secondi "
     "la soglia dipenderebbe da quanto si e' ingrandito il grafico. Sotto i 4 "
     "pixel e' un clic, e allora si assegna; sopra e' un trascinamento, e si "
     "cambia il tempo in vasca. E' lo stesso gesto fisico che significa due "
     "cose, e la distinzione deve essere stabile."),
    ("p",
     "Trascinare la mossa 0 non da' un errore: da' una spiegazione. Il primo "
     "prelievo fissa l'origine dei tempi, e per spostarlo si cambiano i tempi "
     "in vasca a valle."),
    ("c", "interfaccia.Applicazione._rilascia_passaggio"),
    ("p",
     "La fine di un gesto cominciato su un punto di passaggio, a cui "
     "_su_rilascio passa la mano. La stessa distinzione dei trasporti, "
     "ma su tutti e due gli assi: fermo entro 4 pixel in orizzontale E in "
     "verticale e' un clic, e il punto va al carroponte attivo (o gli viene "
     "tolto, _assegna_passaggio); altrimenti e' un trascinamento, e il punto "
     "si sposta di quanto si e' mosso il mouse, in tempo e in posizione. La "
     "lista si rimette in ordine, e si ricompone tenendo i rientri."),
    ("c", "interfaccia.Applicazione._mostra_dettaglio"),

    # ==================================================================
    ("h2", "3. L'inquadratura"),
    ("c", "interfaccia.Applicazione._segna_zoom"),
    ("c", "interfaccia.Applicazione._azzera_zoom"),
    ("c", "interfaccia.Applicazione._vista_corrente"),
    ("c", "interfaccia.Applicazione._riapplica_vista"),
    ("c", "interfaccia.Applicazione._reimposta_grafico"),
    ("p",
     "Cinque metodi per una sola esigenza: il grafico viene ridisegnato da "
     "zero a ogni modifica, e l'inquadratura scelta dall'utente deve "
     "sopravvivere al ridisegno."),
    ("q",
     "MA NON A TUTTI I RIDISEGNI. _reimposta_grafico esiste per il caso "
     "opposto: quando il grafico cambia NATURA -- un'altra linea, o il "
     "passaggio da ciclogramma a pettine -- l'inquadratura precedente non "
     "vuol piu' dire niente, perche' cambia la scala dei tempi. Conservarla "
     "lascerebbe l'utente a guardare un rettangolo vuoto senza capire "
     "perche'. E non basta azzerare lo zoom: si butta anche la cronologia "
     "di navigazione della barra, perche' le viste memorizzate si "
     "riferiscono a un disegno che non c'e' piu', e 'indietro' porterebbe "
     "su una fetta a caso di quello nuovo."),
    ("c", "interfaccia.Applicazione._su_rotella"),
    ("p",
     "Zoom con la rotella, centrato dove sta il puntatore. E' il gesto che "
     "tutti si aspettano da un grafico, e senza si e' costretti a passare "
     "dalla barra ogni volta."),
    ("p",
     "Agisce sul solo asse dei TEMPI, e il docstring dice perche': le vasche "
     "sono poche e fisse, mentre il tempo e' la direzione in cui si cerca il "
     "dettaglio. Con Shift si zooma sulle posizioni, con Ctrl su tutti e "
     "due. Ogni rotellata segna l'inquadratura come scelta dall'utente, "
     "cosi' sopravvive al ridisegno come quella fatta con la barra."),
    ("c", "interfaccia.Applicazione._navigazione_attiva"),
    ("p",
     "Vero quando e' selezionato lo zoom a rettangolo o lo spostamento. "
     "Serve a _su_pressione per farsi da parte: in quel momento il clic e' "
     "della barra, non dell'editor. Senza, ingrandire una zona assegnerebbe "
     "anche un trasporto."),

    # ==================================================================
    ("h2", "4. La simulazione"),
    ("c", "interfaccia.Applicazione._apri_simulazione"),
    ("p",
     "Mostra il ciclogramma corrente in movimento, in una finestra a se'. Si "
     "apre solo quando un ciclogramma c'e' davvero -- e' una delle cose che "
     "_aggiorna_stato_pulsanti governa."),
    ("c", "interfaccia.Applicazione._simulazione_chiusa"),
    ("c", "interfaccia.Applicazione._aggiorna_simulazione"),
    ("q",
     "LA SIMULAZIONE SEGUE LE MODIFICHE MENTRE E' APERTA. E' la ragione per "
     "cui e' una finestra separata e non una scheda: si modifica da una parte "
     "e si vede l'effetto dall'altra, senza chiudere e riaprire. Ogni "
     "_ricomponi passa di qui, e la finestra si aggiorna da sola."),
    ("c", "interfaccia.Applicazione._carri_delle_zone"),
    ("p",
     "Quale carroponte corrisponde a ogni zona. Serve perche' durante la "
     "composizione le zone vengono riempite per continuita' -- e' la finzione "
     "di manuale.zone_coprenti -- e l'indice di zona non e' piu' il numero del "
     "carroponte. Le zone senza nessuna mossa assegnata si omettono passando "
     "None, ed e' esattamente il parametro `carri` che Simulazione documenta."),
]


DOCUMENTI = [
    ("interfaccia_1_finestra.docx", FINESTRA),
    ("interfaccia_2_calcolo.docx", CALCOLO),
    ("interfaccia_3_modifica.docx", MODIFICA),
    ("interfaccia_4_grafico.docx", GRAFICO),
]
