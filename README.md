# Ciclogrammi carroponti (Cyclic Hoist Scheduling) con OR-Tools CP-SAT

Strumento per calcolare il ciclogramma periodico di uno o piu' carroponti
che spostano pezzi attraverso una sequenza di vasche, rispettando:

- tempi di permanenza min/max per vasca (tolleranza di processo),
- un takt time target con tolleranza,
- velocita'/accelerazione massime diverse per carroponte vuoto e carico,
- vincoli di non collisione fra carroponti sulla stessa rotaia.

Si usa da **interfaccia grafica**, da riga di comando o come libreria Python.
La linea si descrive in un file Excel e i risultati escono in Excel. Ogni
soluzione, calcolata o disegnata a mano, passa da un **verificatore
indipendente** che la ricontrolla senza usare il solutore.

## Perche' CP-SAT

Il problema è un **Cyclic Hoist Scheduling Problem (CHSP)**: un problema di
scheduling ciclico, NP-hard, con vincoli fortemente disgiuntivi (due
carroponti non possono occupare lo stesso punto di rotaia nello stesso
istante). La Constraint Programming — e nello specifico CP-SAT di OR-Tools —
è lo strumento standard in letteratura per questo tipo di problema, proprio
per la sua naturalezza nel esprimere vincoli disgiuntivi/di non-overlap e
periodici. È una scelta valida: il codice qui sotto la usa.

## I file del progetto

Sedici file Python, divisi per ruolo. Le dipendenze vanno in una
direzione sola — interfaccia -> motore -> cinematica — e mai al contrario:
`model.py` non sa che esiste un'interfaccia, e `kinematics.py` non sa che
esiste un ciclogramma. E' quello che permette di provare il motore senza
aprire una finestra, e la cinematica senza avere OR-Tools installato.

```text
  interfaccia.py      ciclogramma.py      esempio.py        <- si lanciano
        |                   |                  |
        +-------------------+------------------+
        |          |          |         |          |
  excel_io.py manuale.py plotting.py verify.py simulazione.py   <- contorno
        |          |          |         |          |
        +----------+----+-----+---------+----------+
                        |
                    model.py                                <- motore (CP-SAT)
                        |
                  kinematics.py                             <- fisica
```

### Motore di calcolo

| file | righe | contenuto |
| --- | ---: | --- |
| `kinematics.py` | 130 | La fisica del movimento, in millimetri e secondi. `travel_time()` da' il tempo per percorrere una distanza con profilo trapezoidale o triangolare; `position_profile()` la posizione istante per istante; `profile_breakpoints()` gli spigoli della curva, che servono al verificatore per limitare in modo rigoroso l'errore di campionamento. Non sa nulla del resto del progetto. |
| `model.py` | 1872 | Il cuore. Contiene le **strutture dati** (`Tank`, `StationSpec`, `HoistZone`, `ProblemData`, `Segment`, `Solution`), la costruzione e risoluzione del **modello CP-SAT** (`solve`), la scelta automatica di zone e numero di carroponti (`solve_auto_zones`, `solve_auto_hoists`), e la costruzione di un ciclogramma **senza risolvere** a partire dai suoi gradi di liberta' (`build_solution`, `estrai_gradi_di_liberta`) — quest'ultima e' cio' che rende possibile l'editor. |
| `verify.py` | 1042 | Il **verificatore indipendente**: `verify_solution()` ricontrolla una soluzione in Python puro, senza CP-SAT, campionando le posizioni reali dei carroponti. Restituisce un `VerificationReport` con l'elenco delle `Violation` divise per gravita'. E' la rete di sicurezza contro gli errori nella formulazione del modello. |
| `manuale.py` | 260 | Il ciclogramma nei termini in cui si modifica: il "pettine" dei pezzi (`pettine`, `catena_pezzo`), la composizione libera del ciclogramma (`componi`) e il controllo che i carroponti non si scavalchino sulla rotaia (`perche_non_va`). |

### Ingresso, uscita, disegno

| file | righe | contenuto |
| --- | ---: | --- |
| `excel_io.py` | 1661 | Tutto l'Excel: `scrivi_modello()` genera il file da compilare, `leggi_problema()` lo rilegge raccogliendo **tutti** gli errori di compilazione con foglio e cella, `scrivi_risultati()` produce il file dei risultati -- che e' anche un file di ingresso, col ciclogramma dentro, per poterlo riaprire, diviso in due meta' (`Input` e `Output`) dietro due cartelli colorati. |
| `plotting.py` | 175 | `plot_cyclogram()`: disegna il ciclogramma (posizione lungo la rotaia contro tempo) con il profilo cinematico vero, non con segmenti diritti. |
| `simulazione.py` | 1293 | La **simulazione**: la linea vista di fronte, in movimento. `Simulazione` e' la parte che conta e non importa tkinter — dato un istante dice dove sta ogni carroponte (posizione, quota del gancio, cosa sta facendo) e ogni pezzo; `FinestraSimulazione` e' solo la finestra che la anima. Non calcola niente di nuovo: legge `segments_per_hoist` e `actual_time` della soluzione, cioe' gli stessi oggetti che disegnano il ciclogramma. |

### Programmi da lanciare

| file | righe | contenuto |
| --- | ---: | --- |
| `interfaccia.py` | 2053 | L'**interfaccia grafica** (tkinter). La classe `Applicazione` e' tutta la finestra: caricamento, calcolo in background, grafico incorporato (ciclogramma o pettine, secondo come ci si e' arrivati), la pagina unica in cui il ciclogramma si modifica -- calcolato o composto da zero che sia -- simulazione, verifica e salvataggio. `autotest()` prova l'installazione da sola. E' il programma che usa un utente normale. |
| `ciclogramma.py` | 191 | Lo stesso lavoro da **riga di comando**, per chi preferisce il terminale o vuole automatizzare. |
| `esempio.py` | 198 | La linea di esempio definita **in codice** invece che in Excel, per chi vuole integrare il solutore in qualcos'altro. |
| `costruisci_exe.py` | 119 | Costruisce l'**eseguibile autonomo** con PyInstaller. Vedi sotto. |
| `ciclogrammi.spec` | — | La ricetta per PyInstaller: cosa includere, cosa escludere, come impacchettare. Non si lancia a mano, la usa `costruisci_exe.py`. |
| `Ciclogrammi.bat` | — | Avvia l'interfaccia con un doppio clic, senza aprire il terminale. |

### Test

Ogni file di test si lancia da solo (`python test_xxx.py`), stampa cosa ha
provato e restituisce un codice d'uscita diverso da zero se qualcosa non va.
Non serve pytest.

| file | righe | cosa verifica |
| --- | ---: | --- |
| `test_verify.py` | 862 | **Il verificatore.** Risponde a "chi verifica il verificatore?": venti casi, di cui uno solo corretto e tutti gli altri rotti di proposito (collisioni, permanenze fuori tolleranza, periodicita' incoerente, geometrie patologiche, capienze). Un controllore che non segnala mai nulla e' inutile, quindi ogni controllo ha un caso che DEVE farlo scattare. Non richiede OR-Tools: le soluzioni sono costruite a mano. |
| `test_model.py` | 483 | **Il modello CP-SAT.** Risolve davvero e passa ogni soluzione al verificatore: vasche ravvicinate, tre carroponti, capienza, tempi verticali, e la fedelta' della ricostruzione di una soluzione dai suoi gradi di liberta'. Richiede OR-Tools. |
| `test_excel_io.py` | 919 | **La lettura e la scrittura Excel.** Quasi tutti i casi sono file compilati male: valori mancanti o non numerici, vasche inesistenti o duplicate, righe riordinate, parametri sbagliati, o un file scritto per la vecchia versione in metri. Piu' l'andata e ritorno del ciclogramma salvato nel file, e la struttura del file dei risultati: l'ordine dei fogli, i due cartelli colorati, e che l'elenco dentro un cartello dica davvero i fogli che seguono. Non richiede OR-Tools. |
| `test_simulazione.py` | 735 | **La simulazione.** Il controllo che conta e' incrociato: ogni pezzo appeso deve stare *esattamente* dove sta il gancio di un carroponte che lo tiene, e ogni carroponte che tiene qualcosa deve avere un pezzo li'. Se simulazione e ciclogramma raccontassero due storie diverse, una delle due sarebbe sbagliata. Lo stesso controllo viene rifatto sulle quote **disegnate**, che non sono quelle vere: il telaio deve restare appeso al bilancino anche dopo il rimappaggio delle profondita'. Le vasche di prova hanno corse verticali **diverse fra loro** apposta: con corse tutte uguali, prendere la corsa della vasca sbagliata darebbe comunque il risultato giusto. In fondo, i casi in cui la geometria del disegno degenera: corse e ingombri tutti a zero, tutte le tappe nella stessa vasca. Non richiede OR-Tools. |
| `test_interfaccia.py` | 1085 | **Le funzioni dell'interfaccia grafica.** La finestra viene costruita davvero e pilotata da codice — si "premono" i pulsanti chiamando i metodi e si fa girare il ciclo degli eventi con `update()` invece di `mainloop()`. Verifica che i pulsanti si abilitino al momento giusto, che il calcolo in background consegni il risultato, che una soluzione calcolata riletta come tempi in vasca e ricomposta dia esattamente lo stesso ciclogramma, che le modifiche vengano riverificate, che l'immagine salvata sia il ciclogramma anche componendo dal pettine, che la scheda di modifica si apra solo dopo 'Calcola man' o 'Modifica' e mai mentre il solutore lavora, che un ciclogramma salvato si riapra identico anche se lasciato a meta', che la composizione da zero produca il pettine giusto, che un trasporto assegnato si possa togliere con lo stesso gesto con cui lo si e' assegnato, e che la simulazione si apra solo quando un ciclogramma c'e' davvero e segua le modifiche mentre e' aperta. Richiede OR-Tools e un ambiente grafico. |

`kinematics.py` ha in fondo un autotest che si lancia allo stesso modo
(`python kinematics.py`).

## Installazione ed esecuzione

```bash
pip install -r requirements.txt
```

Servono `ortools` (il solutore), `matplotlib` (il disegno) e `openpyxl` (i file
Excel). `pyinstaller` serve solo a chi deve costruire l'eseguibile.

## Come si usa l'interfaccia

Doppio clic su **`Ciclogrammi.bat`** (oppure `python interfaccia.py`, oppure
`Ciclogrammi.exe` se si usa la versione impacchettata).

![interfaccia](doc/interfaccia.png)

La finestra e' divisa in tre: la **barra dei comandi** in alto, il
**ciclogramma** a sinistra, e a destra un **verdetto** sempre in vista con
sotto tre schede. In basso una barra di stato che dice cosa sta facendo il
programma.

### Il giro completo, in breve

1. `Nuovo modello Excel...` — se non hai ancora un file, questo te lo crea gia'
   compilato con una linea di esempio.
2. Compili il file (vedi *Come modellare il tuo caso*, piu' sotto).
3. `Apri linea...` — lo carichi.
4. `Calcola auto` oppure `Calcola man`.
5. Guardi il verdetto, eventualmente ritocchi.
6. `Salva risultati...` — esce l'Excel dei risultati e l'immagine.

### La barra dei comandi

| pulsante | cosa fa |
| --- | --- |
| `Apri linea...` | Carica un file Excel con la definizione della linea. Se il file e' compilato male non succede nulla di brutto: compare una finestra con **tutti** gli errori trovati, con foglio e cella. |
| `Nuovo modello Excel...` | Crea il file da compilare, gia' pieno con una linea di zincatura d'esempio, e chiede se aprirlo subito. E' il modo consigliato di cominciare: si parte da qualcosa che funziona e lo si modifica. |
| `Calcola auto` | Cerca il numero minimo di carroponti, la suddivisione migliore della linea e il takt time piu' basso. Puo' durare da qualche secondo a qualche minuto: la barra in basso a destra si muove, i pulsanti si spengono e la scheda *Ciclogramma* si chiude finche' non ha finito. La finestra **non si blocca**. |
| `Calcola man` | Butta via il ciclogramma corrente e riparte dai tempi minimi di processo, con **nessun trasporto assegnato**, per comporlo a mano (vedi sotto). |
| `Modifica` / `Fine modifica` | Apre alla modifica il ciclogramma che c'e', portando sul **pettine** — che e' il foglio su cui si assegna. Non cambia niente, ma e' il passaggio obbligato: senza, la scheda *Ciclogramma* resta chiusa. Premuto di nuovo chiude la modifica e riporta a guardare il ciclogramma. |
| `Simulazione` | Apre una finestra a parte in cui la linea si vede **di fronte e in movimento**: i carroponti che scorrono, calano il gancio, tirano su il telaio, lo portano e lo immergono. Si accende solo quando un ciclogramma c'e' — calcolato o composto a mano, e' lo stesso oggetto. Vedi sotto. |
| `Salva risultati...` | Scrive l'Excel dei risultati e, accanto, l'immagine del ciclogramma. **Lo stesso Excel si riapre con `Apri linea...`** per riprendere il lavoro: contiene anche la linea e il ciclogramma. Si abilita solo quando c'e' qualcosa da salvare. |

A destra nella stessa barra c'e' il **percorso completo** del file caricato —
non solo il nome, perche' dello stesso file girano di solito piu' copie (la
scrivania, la cartella di commessa, la rete) e serve sapere quale si sta
guardando. Lo stesso percorso compare nel titolo della finestra e in cima alla
scheda *Riepilogo*: se la barra e' troppo stretta per contenerlo, si legge li'.

### Come si legge il ciclogramma

Il grafico ha **due disegni**, e non c'e' niente da scegliere: lo decide il
modo in cui sei arrivato.

| disegno | quando compare | cosa mostra |
| --- | --- | --- |
| **ciclogramma** | dopo `Calcola auto`, dopo `Ottimizza con questi carroponti` e dopo `Fine modifica` | le traiettorie dei **carroponti**, su due cicli: chi si muove quando, chi rischia di incontrare chi |
| **pettine** | dopo `Calcola man` e dopo `Modifica` | le scalinate dei **pezzi**, dieci, una ogni takt time: e' il foglio su cui si compone, e le pedate **sono** i tempi in vasca |

Vale anche tornando indietro: se stavi componendo a mano e premi `Calcola
auto`, il disegno torna al ciclogramma. Il pettine e' il foglio su cui si
**compone**, e un risultato del solutore non si compone: si legge.

**Si modifica sempre sul pettine**, anche un ciclogramma appena calcolato. Non
e' una preferenza: nel ciclogramma si disegnano solo le traiettorie dei
carroponti, quindi un trasporto che non e' ancora di nessuno — o che hai appena
tolto a qualcuno — li' **non compare affatto**, pur restando cliccabile. Non lo
vedi e ci inciampi, che e' la combinazione peggiore. Nel pettine il pezzo passa
comunque, grigio finche' nessuno lo porta.

Un interruttore fra i due c'e' stato ed e' stato tolto: le tabelle della scheda
*Ciclogramma* permettono di modificare tutto — tempi in vasca, assegnazione,
takt time, carroponti — senza cambiare disegno, quindi restava un comando che
chiedeva una decisione senza darne il motivo.

Quello che il disegno a schermo **non** decide e' l'immagine consegnata:
`Salva risultati...` esporta sempre il **ciclogramma**, anche se l'hai composto
guardando il pettine. E' il documento che esce, e non puo' dipendere da cosa
stavi guardando quando hai premuto Salva.

Nel **ciclogramma**: in orizzontale il tempo, in verticale la posizione lungo la
rotaia: le vasche sono le righe, col nome e la quota sull'asse. Il disegno
ripete **due cicli** di seguito, cosi' si vede a occhio che il pattern si
richiude.

Il colore dice una cosa sola: **di quale carroponte** e' la traiettoria. Il
tratto ne dice un'altra sola:

- **continuo** — il carroponte ha il pezzo in mano. I tratti che salgono o
  scendono sono i trasferimenti fra vasche, quelli piatti agli estremi sono la
  presa e il rilascio (il carro e' fermo sopra la vasca mentre il telaio esce
  dal bagno o ci entra).
- **tratteggiato** — il carroponte e' senza pezzo: rientro a vuoto se la linea
  si muove, attesa sopra la vasca se e' piatta.

Niente altro. Un colore per ogni tipo di tratto rendeva il grafico un
arcobaleno in cui non si riusciva piu' a seguire un carroponte dall'inizio alla
fine, che e' l'unica cosa per cui serve un ciclogramma.

### Ingrandire

Su una linea lunga i punti interessanti stanno spesso in pochi secondi. Il
grafico si ingrandisce in due modi:

- **rotella del mouse** — ingrandisce e rimpicciolisce sui **tempi**, centrato
  dove tieni il puntatore. E' la direzione in cui si cerca il dettaglio: le
  vasche sono poche e fisse. Con **Shift** la rotella agisce sulle posizioni,
  con **Ctrl** su tutti e due gli assi.
- **barra sotto al grafico** — la lente ingrandisce un rettangolo che disegni
  tu, la croce sposta l'inquadratura trascinando, la casetta torna a inquadrare
  tutto, le frecce ripercorrono le viste precedenti. Il dischetto salva
  l'immagine **cosi' come la stai vedendo**, ingrandimento compreso.

Quando la lente o la croce sono premute il clic serve a navigare: il
trascinamento dei punti e l'assegnazione dei trasporti sono sospesi finche' non
le rilasci.

Mentre muovi il mouse sul grafico, **in basso si legge l'istante e la quota
esatti** sotto al puntatore (`t = 175.0 s   posizione = 10000 mm`).

(C'e' stata anche una linea verticale che seguiva il puntatore, ed e' stata
tolta. Per restare fluida sul pettine -- centinaia di segmenti -- si appoggiava
a una copia in cache dello sfondo; ogni volta che qualcos'altro ridisegnava il
grafico quella copia restava vecchia e finiva a schermo, lasciando in giro
pezzi di disegno precedente. Un riferimento che ogni tanto mente e' peggio di
nessun riferimento.)

**L'ingrandimento sopravvive alle modifiche.** Ritocchi un punto, cambi un tempo
in vasca, assegni un trasporto: il grafico viene ridisegnato ma resta inquadrato
dov'eri. Sarebbe inutile ingrandire per lavorare su un dettaglio se poi il primo
ritocco riportasse la vista al punto di partenza. Si riparte da capo solo quando
cambia il disegno stesso: un'altra linea, o il passaggio dal ciclogramma al
pettine.

### Guardare la linea in movimento

Il pulsante `Simulazione` apre una finestra a parte in cui la linea si vede
**di fronte**, come dal capannone: le vasche in fila con dentro il bagno, la
rotaia sopra, i carroponti che ci scorrono. Il tempo scorre e si vedono calare
il gancio in una vasca, agganciare il telaio, tirarlo su, lasciarlo
sgocciolare, traslare fino alla vasca successiva e immergercelo.

E' **lo stesso ciclogramma**, letto in un altro modo. Non c'e' nessun calcolo
in piu' e nessuna approssimazione: la simulazione legge le traiettorie dei
carroponti e la catena dei tempi del pezzo, cioe' esattamente gli oggetti da
cui viene disegnato il diagramma. Serve perche' un ciclogramma dice tutto ma
bisogna saperlo leggere, e certi errori ci si nascondono bene — mentre un
carroponte che passa attraverso un altro, o un pezzo che resta appeso al
nulla, nella linea in movimento si vedono senza doverli cercare.

Cosa c'e' da guardare:

- **i telai** sono tutti uguali, perche' tutti uguali sono: fanno lo stesso
  percorso, sfasati di un takt time l'uno dall'altro. Quanti se ne vedono
  insieme e' quanti pezzi la linea tiene dentro contemporaneamente.
- **una vasca che tiene piu' pezzi insieme** li mostra **affiancati**, ognuno
  sul suo posto. I posti disegnati sono quelli che il ciclogramma usa davvero,
  non quelli dichiarati in `posti`: con tre posti e un pezzo solo il pezzo sta
  in mezzo, e se il ciclogramma sfora la capienza i pezzi di troppo si vedono
  lo stesso — sono proprio quelli da vedere. Lo spostamento di lato e' un
  espediente di disegno: il modello tratta la vasca come un punto e non sa dove
  stiano i posti dentro. Per le distanze fra carroponti non si guarda qui, si
  legge la separazione minima in millimetri che da' il verificatore.
- **i carroponti** hanno il colore che hanno nel ciclogramma e il numero
  scritto sopra. Sono disegnati con il loro **ingombro vero**
  (`ingombro_lato_positivo_mm` e `ingombro_lato_negativo_mm`), cosi' lo spazio
  che resta fra due carrelli vicini si vede per quello che e'. Sotto il
  carrello ci sono l'argano, le due funi e il bilancino a cui il telaio si
  appende: la lunghezza delle funi dice a che punto e' la discesa.
- **un carroponte che deposita un telaio e resta li'** ad aspettare, per
  prenderne un altro dalla stessa vasca, **tiene il gancio calato** per tutta
  l'attesa: si stacca appena dal telaio, aspetta in basso, e si riaccosta solo
  all'ultimo, prima di agganciare. Alzarlo per ricalarlo subito dopo non serve
  a niente e a vederlo sembra un difetto. **Non e' un tempo che si guadagna**:
  il telaio successivo viene agganciato nello stesso identico istante di prima,
  e il ciclogramma resta quello — cambia solo dove il gancio passa l'attesa.
- **le tappe senza corsa verticale** (tipicamente carico e scarico) sono
  disegnate come piattaforme e non come vasche col bagno: il telaio li' non
  scende, e mostrarle piene direbbe una cosa falsa proprio sulle due tappe che
  si guardano per prime.
- **sotto al disegno** c'e' scritto cosa sta facendo ciascun carroponte in
  quell'istante, con il nome della vasca: `discesa del gancio in SGRASSO`,
  `sgocciolamento in ZINCATURA`, `rientro a vuoto`.

Le vasche sono **tutte uguali** e i telai immersi stanno **tutti alla stessa
altezza**, sospesi nel bagno: sul fondo non ci si appoggiano mai, perche' non
ci si appoggiano nemmeno davvero.

Quello che si disegna non e' la quota in millimetri ma **a che punto e'
arrivata la discesa**, da zero (quota di trasporto) a uno (immerso). La
profondita' vera della vasca non e' un dato dichiarato — delle vasche si sa
solo di quanto sale e scende il telaio — quindi disegnarla avrebbe messo a
grafico un numero che nessuno ha scritto, con l'aria di dire qualcosa che il
programma non sa. La corsa vera non sparisce, cambia dove la si legge: sta nel
**tempo** che la discesa impiega, e una vasca con la corsa piu' lunga si vede
perche' il gancio ci mette di piu' a scendere. In cambio i pezzi in vasca
stanno in fila e le vasche si confrontano a colpo d'occhio.

I comandi: `Indietro` / `Avvia`-`Pausa` / `Avanti`, `Da capo`, la velocita' (da
mezza a venti volte il tempo reale — a velocita' 1x un takt time dura quanto
dura davvero, che e' parecchio) e un cursore per portarsi a un istante preciso.

`Indietro` e `Avanti` spostano di **un fotogramma per volta**, e si possono
premere anche con le frecce ← e →. Servono quando guardare non basta piu': per
capire *esattamente* quando due carroponti si sfiorano bisogna fermarsi
sull'istante e spostarsi di poco, avanti e indietro, senza rincorrere il
cursore. Premuti mentre la simulazione va, la mettono in pausa: passo a passo e
andatura non convivono.

**Tenendoli premuti** la simulazione scorre in quel verso, all'andatura scelta
col menu della velocita' — cosi' per spostarsi di parecchio non si clicca
cinquanta volte, e per andare piu' veloci basta mettere 20x. All'indietro non
c'e' altro modo di farlo. Anche le frecce si ripetono, tenendole premute.

Un fotogramma e' lo stesso salto che la simulazione fa da sola, quindi **dipende
dalla velocita'**: a 20x un passo e' 0,8 s per scorrere il ciclo, a mezza
velocita' e' 0,02 s per fermarsi sull'istante buono. La stessa manopola regola
l'andatura e la finezza del passo.

La simulazione dura
un numero intero di takt time, quanti ne servono a coprire la vita di un pezzo
dal carico allo scarico, e poi **riparte da capo**: a regime la linea dopo un
takt e' identica a se stessa, quindi il ritorno a capo non si vede.

La finestra e' a se' apposta, non e' una scheda: si tiene aperta accanto a
quella principale e **si aggiorna da sola** a ogni modifica del ciclogramma —
cambi un tempo in vasca o assegni un trasporto, e la vedi cambiare. Una
simulazione che continuasse a mostrare il ciclogramma di prima, mentre a
fianco se ne modifica un altro, sarebbe peggio che non averla.

Su un ciclogramma composto a meta' si apre lo stesso, con un avviso in rosso:
i trasporti che nessun carroponte fa ancora si vedono come **pezzi che si
spostano da soli**. E' esatto, ed e' bene che si veda.

### Il verdetto

La striscia colorata in alto a destra e' l'informazione piu' importante, e per
questo non finisce mai dentro una scheda:

- **verde** — `VERIFICA SUPERATA`, con takt time e pezzi/ora. Il ciclogramma e'
  fisicamente valido e rispetta tutte le tolleranze dichiarate.
- **rosso** — quanti errori sono stati trovati. Il dettaglio e' nella scheda
  *Verifica*.
- **azzurro** — `IN COMPOSIZIONE`: la verifica non e' ancora stata chiesta.
  Componi come vuoi, il verdetto arriva quando premi `Verifica adesso`.

### Le tre schede

**Riepilogo** — da dove viene il ciclogramma, takt time, produttivita' in
pezzi/ora, quanti carroponti e che tratto di linea serve ciascuno, distanza
minima raggiunta fra i carri contro quella richiesta, esito della verifica.

**Ciclogramma** — dove si modifica. Vedi sotto.

**Verifica** — l'elenco dei rilievi del verificatore indipendente, colorati per
gravita': rosso gli errori, arancio gli avvisi, grigio le note. Le descrizioni
sono lunghe: **clic su una riga** per leggerla per intero.

La differenza fra i tre livelli conta. Un **errore** vuol dire che il
ciclogramma non e' utilizzabile (una collisione, una permanenza fuori
tolleranza). Un **avviso** segnala qualcosa che il modello non sa vincolare e
che va guardato a mano. Una **nota** e' informativa: per esempio che una vasca
lavora con due pezzi dentro contemporaneamente, il che e' normale se e' a due
posti.

### Modificare il ciclogramma

**Una sola scheda, per il calcolato e per il composto a mano.** Non sono due
cose: sono lo stesso oggetto, e i gradi di liberta' sono gli stessi che si
usano tracciando un ciclogramma su carta.

Sono tre:

1. il **takt time**;
2. il **tempo in vasca** di ogni tappa;
3. **quale carroponte** fa ogni trasporto.

Tutto il resto — istanti di prelievo, traiettorie, rientri a vuoto, ordine di
visita — e' conseguenza. Il solutore non produce niente di piu': produce una
scelta di questi tre, e la si rilegge cosi'. Ricomporre il ciclogramma dai
valori riletti restituisce **esattamente** lo stesso ciclogramma — stesso takt,
stesso esito della verifica — ed e' il motivo per cui la pagina puo' essere una
sola invece di due. (C'e' un test che lo controlla: se un giorno smettesse di
valere, salterebbe.)

Si modifica in tre modi, tutti equivalenti:

- **Doppio clic su un tempo in vasca**, nella tabella. Le soste successive si
  spostano di conseguenza. La tabella mostra accanto il minimo e il massimo di
  processo, ma **non impedisce** di uscirne: sara' la verifica a dirlo.
- **Trascinando un prelievo sul grafico** — prendi l'**inizio** di un
  trasporto e spostalo. Fa la stessa identica cosa: allunga o accorcia la sosta
  nella vasca da cui il pezzo parte. Mentre trascini, una guida arancione
  mostra dove finira'.
- **Clic su un trasporto** per darlo al carroponte attivo (si sceglie col menu
  `attivo`), oppure **doppio clic su una riga di `Assegnazione`** per passarlo
  al carroponte successivo.

**Per togliere un'assegnazione** si rifa' la stessa cosa: un secondo clic sul
trasporto lo toglie al carroponte attivo, e il tratto torna grigio. Dalla
tabella, il doppio clic dopo l'ultimo carroponte passa per *non assegnato*
prima di ricominciare il giro. Lo stesso gesto fa e disfa perche' assegnare per
sbaglio costa un clic, e il carroponte a cui si vuole togliere una mossa e'
quasi sempre quello a cui si sta lavorando — cioe' proprio quello attivo.
Togliere non puo' mai essere rifiutato: i carroponti si scavalcano per quello
che *fanno*, e una mossa in meno non obbliga nessuno a passare da nessuna
parte.

Il clic e il trascinamento hanno raggi d'azione diversi, e non per caso. Il
**clic** vale su tutto il tratto disegnato, dalla vasca di partenza a quella di
arrivo: assegnare una mossa non ha niente a che fare con un estremo
particolare, quindi non c'e' ragione di far centrare un punto. Il
**trascinamento** invece prende solo dall'inizio, perche' li' l'estremo conta
davvero — e' da quel punto che la sosta si allunga o si accorcia.

`Takt time` e `Carroponti` stanno in alto. Lo spinbox dei carroponti
**ridistribuisce subito** le mosse in blocchi contigui, senza far girare il
solutore: e' istantaneo e si annulla. Se invece vuoi la suddivisione *migliore*
per quel numero, c'e' `Ottimizza con questi carroponti`, che fa lavorare il
solutore e **butta via le modifiche fatte a mano**.

`Annulla modifica` torna indietro di un passo, e si puo' premere piu' volte.

**Niente viene mai rifiutato.** Anche una modifica che rende il ciclogramma
impossibile viene composta e disegnata: e' il verificatore a dire cosa non va,
non un blocco che ti impedisce di provare.

#### `Modifica`: cosa modifica, e quando serve

Quello che c'e'. **Non sceglie fra una versione automatica e una manuale**,
perche' non ce ne sono due: da quando la pagina e' una sola, il ciclogramma
calcolato e quello composto a mano sono lo stesso oggetto con gli stessi tre
gradi di liberta'. Da dove sia partito lo dice il *Riepilogo*, alla voce
`Origine`. Un pulsante che dovesse scegliere la sorgente obbligherebbe a
tenerne due vivi insieme, che e' la duplicazione tolta unificando le schede.

**La scheda *Ciclogramma* non e' sempre aperta**, ed e' questo pulsante ad
aprirla. La regola sta in tre righe:

| quando | scheda |
| --- | --- |
| linea appena aperta | chiusa: non c'e' niente da modificare |
| dopo `Calcola auto` | chiusa: c'e' un risultato da **leggere** |
| dopo `Calcola man` o `Modifica` | aperta |
| dopo `Fine modifica` | chiusa di nuovo |
| mentre il solutore lavora | chiusa, sempre |

Un risultato del solutore si guarda prima di toccarlo, e premere `Modifica` e'
il momento in cui si dichiara di volerci mettere le mani. Cosi' non lo si
altera per sbaglio con un trascinamento di troppo — il grafico e' fuori dalla
scheda, quindi ha lo stesso cancello — e i tre pulsanti diventano tre stati
veri: leggi, componi, modifica.

Aperta la modifica, **lo stesso pulsante diventa `Fine modifica`**: chiude la
scheda e riporta a guardare il ciclogramma. Serve perche' la modifica porta sul
pettine, e senza un'uscita chi ha ritoccato un tempo in vasca non rivedrebbe
piu' il ciclogramma se non ricalcolandolo da capo. Non e' l'interruttore fra le
due viste — quello e' stato tolto apposta — ma l'uscita da uno stato di lavoro:
chiudendo si torna a leggere, e il ciclogramma non si altera piu' per un clic
di troppo.

#### Mentre il calcolo gira

La scheda si chiude comunque, e se era quella aperta si torna al *Riepilogo*.
Chiuderla vuol dire chiuderla davvero, non ingrigire i pulsanti che contiene: i
doppi clic sulle tabelle sono associazioni di evento e non hanno uno stato da
spegnere. Un tempo in vasca ritoccato durante il calcolo si vedeva cambiare sul
grafico e spariva quando il risultato arrivava a sovrascriverlo — senza un
avviso, che e' il modo peggiore di perdere del lavoro.

#### Quando parte la verifica

- Se il ciclogramma arriva dal **calcolo automatico**, la verifica c'e' gia' e
  da quel momento **si tiene aggiornata da sola**: cambi un tempo in vasca e il
  verdetto e l'elenco dei rilievi si aggiornano subito.
- Se stai **componendo da zero**, no. Si parte da uno stato dichiaratamente
  provvisorio — nessun trasporto ancora al posto giusto — e un muro di errori
  rossi mentre scegli la prima mossa non informerebbe nessuno. Il verdetto
  arriva quando premi `Verifica adesso`, e **da li' in poi resta vivo** anche
  lui.

Una regola sola: *la verifica, una volta chiesta, si tiene aggiornata*.

Il report dice tutto — permanenze, collisioni, capienze, takt time — e dice
**dove**. Per esempio, di due carri che si toccano, quali sono e in che punto
della linea:

```text
COLLISIONE fra carroponti 1 e 2 a t=61.6s: il 1 e' sopra PASSIVAZIONE
(16500 mm), il 2 e' sopra PASSIVAZIONE (16500 mm) -- restano 0 mm contro
i 1800 mm richiesti (ingombro 700+500 + sicurezza 600)
```

Quando il punto non coincide con una vasca il messaggio dice fra quali due si
trova: `il 2 e' fra ZINCATURA e RISCIACQUO_2 (10800 mm)`. Una quota da sola non
si riconosce sull'impianto; il nome della vasca si'.

#### L'unica cosa impedita

Assegnare i trasporti in modo che due carroponti debbano **scavalcarsi** sulla
rotaia. Non e' una regola del modello: e' la rotaia. Il messaggio lo dice, e il
doppio clic sulla tabella propone solo i carroponti che possono davvero
prendersi quella mossa.

### Comporre da zero

`Calcola man` butta via tutto, passa alla vista **pettine** e riparte dai
**tempi minimi di processo**, col takt time piu' basso ammesso e — soprattutto
— **nessun trasporto assegnato a nessuno**.

![composizione a mano](doc/disegno-manuale.png)

E' il metodo con cui i ciclogrammi si tracciano a mano da sempre: prima il
pettine dei pezzi, che e' il vincolo di processo, poi si decide una mossa per
volta chi la fa. Partire da una suddivisione gia' pronta voleva dire non avere
mai niente "da assegnare": si finiva a correggere una proposta invece di
comporre, che e' un'altra cosa.

Nel pettine il colore vuol dire una cosa sola: **l'ho assegnato io**. Tutto
quello che non hai ancora deciso e' dello stesso grigio sottile, cosi' il
disegno resta uno sfondo e le tue scelte si vedono da lontano.

Appena dai un trasporto a un carroponte, prende il suo colore tutta la parte di
scalinata che gli tocca: **il trasporto e la sosta in vasca che lo precede**,
identici — stesso colore, stesso spessore, una linea sola. La sosta e' il pezzo
che aspetta proprio quel carroponte, quindi e' sua quanto il trasporto.

E' il motivo per cui a lavoro finito **non resta niente di grigio**. Una sosta
lasciata grigia sembrerebbe lavoro ancora da fare, che e' esattamente quello
che il grigio vuol dire qui.

A parte si vede il **rientro a vuoto**, tratteggiato: e' la conseguenza piu'
importante di un'assegnazione — dice dove quel carro e' costretto a tornare e
quando — e va guardata mentre si decide, non dopo. Tratteggiato perche' e' il
percorso del carroponte, non quello del pezzo.

Il numero di `Carroponti` non ridistribuisce niente: aggiungerne uno lo rende
disponibile nel menu `attivo`, e da li' in poi gli si danno le mosse a mano.
Toglierne uno passa le sue mosse a chi resta, che e' l'unico modo di non far
scavalcare i vicini.

A parte il punto di partenza, i comandi sono quelli di sopra: sono gli stessi.

### Riprendere il lavoro un altro giorno

Un ciclogramma composto a mano vive nella memoria del programma: chiuso il
programma, andrebbe rifatto da capo. Per questo **l'Excel dei risultati e'
anche un file di ingresso**: dopo i quattro fogli del referto ne trova altri
sei — `Istruzioni`, `Vasche`, `Percorso`, `Parametri`, `Zone` e `Ciclogramma`
— e si riapre con `Apri linea...`.

Un file solo perche' non ce n'e' bisogno di due: `leggi_problema` cerca i fogli
per nome e ignora gli altri. Due file separati sarebbero due cose da tenere
insieme e da non confondere, e prima o poi si consegna quello sbagliato.

Riaprendolo il ciclogramma e' gia' li', **anche se lasciato a meta'**: i
trasporti ancora da assegnare restano tali, e si riprende da quel punto. La
scheda resta chiusa come sempre, e si preme `Modifica` per intervenire.

Nel foglio ci sono i **tre gradi di liberta'** e nient'altro: takt time, tempo
in vasca di ogni tappa, e quale carroponte fa ogni trasporto (piu' quanti
carroponti hai a disposizione). Le traiettorie e gli istanti di prelievo non ci
sono, perche' sono conseguenze: riscriverli vorrebbe dire poterli rileggere in
contrasto con i valori da cui derivano. Si ricostruiscono, e tornano identici.

Il file di partenza **non viene toccato**: quello descrive l'impianto, e a
riscriverlo si rischierebbe di perdere quello che openpyxl non sa riprodurre —
grafici, commenti, formattazioni fatte a mano.

**Perche' non si riapre invece il file dei risultati**, che pure contiene i
tempi in vasca: perche' e' un referto, scritto per essere letto da una persona,
e soprattutto **non contiene le cinematiche**. Senza velocita' e accelerazioni
le durate dei trasporti non si possono ricalcolare, quindi il ciclogramma non
si ricostruisce. Un file di ingresso invece descrive gia' tutto.

Cancellando il foglio `Ciclogramma` il file torna a essere una linea e basta.

### Se il calcolo non trova niente

Capita, ed e' un'informazione: vuol dire che con i dati dati la linea non sta in
piedi. Il riepilogo elenca cosa provare — allargare la tolleranza sul takt time,
aumentare il numero massimo di carroponti, aggiungere posti alle vasche piu'
lente, allungare il tempo limite di calcolo. In alternativa `Calcola man`, e
si guarda dove il conto non torna: li' non c'e' niente da trovare, si vede.

## Cosa produce

Sia l'interfaccia sia la riga di comando producono, accanto al file di
ingresso:

- **`linea_risultati.xlsx`** — tredici fogli, in **due meta'**, ciascuna dietro
  un cartello con la linguetta colorata:

  **`Input`** (linguetta blu) — quello che segue e' la **linea nel formato di
  ingresso**, col ciclogramma dentro: `Istruzioni`, `Vasche`, `Percorso`,
  `Parametri`, `Zone`, `Ciclogramma`. Serve a riaprire lo stesso file con
  `Apri linea...` e riprendere il lavoro. Vale anche da riga di comando.

  **`Output`** (linguetta verde) — il referto:

  | foglio | contenuto |
  | --- | --- |
  | `Riepilogo` | takt time, **produttivita' in pezzi/ora**, numero di carroponti, zone e tratto di rotaia servito, **utilizzo di ciascun carroponte**, distanza minima raggiunta contro quella richiesta, esito della verifica |
  | `Movimenti` | una riga per tratto: carroponte, fase (presa, trasporto, rilascio, spostamento a vuoto, attesa), vasca di partenza e arrivo, istanti di inizio e fine, durata, posizioni. E' la tabella da passare a chi programma il PLC |
  | `TempiVerticali` | dove va a finire il tempo di presa e di rilascio, vasca per vasca: discesa del gancio, aggancio, sollevamento, sgocciolamento, e i totali. Serve a non dover indovinare perche' una presa duri quanto dura |
  | `FlussoPezzo` | il percorso di **un** pezzo lungo tutta la linea: ingresso e uscita da ogni vasca, permanenza effettiva, margine rispetto ai limiti di processo, posti occupati |
  | `Verifica` | l'elenco dei rilievi del verificatore indipendente, colorati per gravita' |

  L'ordine e' quello in cui le cose sono successe: si parte da una linea e se
  ne ricava un risultato. I due cartelli non contengono dati, dicono cosa viene
  dopo — e l'elenco che c'e' dentro non e' scritto a mano ma ricavato dai fogli
  che ci sono davvero, cosi' non puo' restare indietro il giorno che se ne
  aggiunge uno. Il file si apre comunque sul `Riepilogo`, che e' quello che si
  va a leggere.

  Chiedendo solo il referto, senza la linea dentro, i cartelli non compaiono:
  non ci sarebbe niente da dividere.

- **`linea.png`** — il **ciclogramma** disegnato. Sempre quello, anche se a
  schermo c'era il pettine: e' il documento che si consegna.

Il comando stampa anche a video il takt time e il report della verifica.
Altre opzioni: `--risultati FILE.xlsx`, `--grafico FILE.png`, `--cicli N`,
`--niente-grafico`, `--niente-excel`, `--log`.

Gli errori di compilazione vengono raccolti **tutti insieme**, con foglio e
cella, cosi' si corregge il file in una volta sola:

```text
Il file 'linea.xlsx' non e' compilato correttamente:
  - [Vasche!B3] posizione: atteso un numero, trovato 'due metri'
  - [Percorso!B4] la vasca 'SGRASSAGGIO' non e' definita nel foglio Vasche
  - [Parametri!A2] parametro 'takt_minimo' non riconosciuto. Quelli ammessi sono: ...
```

I numeri scritti con la virgola decimale (`2500,5`) vengono accettati.

**Tutte le lunghezze sono in millimetri**, e le cinematiche di conseguenza in
`mm/s` e `mm/s^2`. Il nome di ogni parametro lo dice (`posizione_mm`,
`v_max_carico_mm_s`), e il foglio `Parametri` ha una colonna con l'unita'.

Un file della versione precedente, che lavorava in metri, **non viene letto**:
i parametri hanno nomi diversi e il programma lo riconosce, dicendo come si
chiama adesso ciascuno e che il valore va moltiplicato per 1000. Serve perche'
le colonne dei fogli si leggono per posizione e non per intestazione: senza
questo controllo, una vasca a 9,5 m verrebbe presa per una a 9,5 mm senza che
nessuno se ne accorga. Il modo piu' rapido di aggiornare un file vecchio e'
rigenerare il modello e ricopiarci dentro i dati, moltiplicati.

## Altri modi di usarlo

### Da riga di comando

```bash
python ciclogramma.py --modello linea.xlsx    # crea il file da compilare
# ... compili linea.xlsx ...
python ciclogramma.py linea.xlsx              # calcola il ciclogramma
```

Il modello generato e' gia' compilato con una linea di zincatura d'esempio, in
modo che si possa lanciare subito e poi modificarlo pezzo per pezzo. Ha cinque
fogli (sei se ci si salva dentro un ciclogramma):

| foglio | contenuto |
| --- | --- |
| `Istruzioni` | come compilare gli altri fogli |
| `Vasche` | una riga per vasca: id, posizione lungo la rotaia **in millimetri**, numero di posti, corsa verticale, sgocciolamento. Corsa e sgocciolamento sono **obbligatori** (0 dove non servono) |
| `Percorso` | sequenza di vasche attraversate, con le permanenze |
| `Parametri` | quello che vale per tutta la linea: takt time, cinematiche del carroponte, ingombri, tempi di aggancio/sgancio, opzioni di calcolo |
| `Zone` | facoltativo: suddivisione manuale delle mosse fra i carroponti. **Lasciandolo vuoto** numero di carroponti e zone vengono scelti automaticamente |
| `Ciclogramma` | facoltativo: il ciclogramma gia' composto. Lo scrive il programma quando salvi, e riaprendo il file si riprende da li' |

### Uso da Python

`esempio.py` mostra come definire la stessa linea direttamente in codice e
richiamare il solutore, se serve integrarlo in qualcos'altro:

```bash
python esempio.py
```

## Creare l'eseguibile per PC senza Python

Serve PyInstaller una volta sola:

```bash
pip install pyinstaller
```

Poi, dalla cartella del progetto, **un comando**:

```bash
python costruisci_exe.py
```

Ci vogliono un paio di minuti. Al termine si trova tutto in
`dist/Ciclogrammi/`, circa 290 MB: si copia **la cartella intera** sul PC di
destinazione e si lancia `Ciclogrammi.exe`. Non serve installare ne' Python
ne' altro.

Con `--con-test` il comando esegue prima l'intera suite di test, e non
impacchetta se qualcosa non passa. Non e' obbligatorio, ma e' l'unico modo per
non scoprire un problema in stabilimento.

### Verificare che funzioni davvero

Sul PC di destinazione, una volta sola:

```bash
Ciclogrammi.exe --autotest
```

Crea un file di esempio, lo rilegge, calcola il ciclogramma, lo verifica, salva
i risultati e scrive un `autotest.txt` con l'esito. Trenta secondi.

Non e' una formalita': **che l'eseguibile si costruisca non vuol dire che
funzioni.** Durante la messa a punto il pacchetto veniva creato senza il
minimo errore, si apriva regolarmente, e poi moriva al primo calcolo con
`No module named 'pandas'` — perche' OR-Tools importa pandas internamente e
lo spec lo escludeva come alleggerimento. Un problema del genere, scoperto
davanti al cliente, e' un'altra faccenda.

### Perche' una cartella e non un singolo file

Con OR-Tools e matplotlib dentro, un `--onefile` supera i 280 MB e a **ogni
avvio** deve scompattarsi in una cartella temporanea: decine di secondi di
attesa tutte le volte. La cartella si copia tale e quale e parte subito.

### Se serve rimettere le mani nello spec

`ciclogrammi.spec` e' la ricetta per PyInstaller. Due punti delicati:

- **`excludes`**: qui si tolgono i pacchetti inutili per alleggerire. Attenzione
  a `pandas`: il progetto non lo usa, ma OR-Tools si', quindi non va escluso.
  Vale la regola generale che un pacchetto va tolto solo se si e' sicuri che
  nessuna dipendenza lo importi.
- **`console=False`**: niente finestra nera all'avvio. Come contropartita, un
  errore all'avvio sarebbe invisibile, quindi `interfaccia.py` lo intercetta e
  lo mostra in una finestra di dialogo.

## Come modellare il tuo caso

1. **Vasche** (`Tank`): id, posizione `[mm]` lungo la rotaia, numero di posti
   simultanei (`capacity`, default 1), corsa verticale (`lift_height`) e
   sgocciolamento (`drain_time`). Le ultime due sono **obbligatorie e proprie
   di ogni vasca**: dove non c'e' movimentazione verticale si scrive 0.
2. **Percorso** (`route`, lista di `StationSpec`): sequenza di vasche che il
   pezzo attraversa, con tempo di permanenza `[min,max]` in secondi. La stessa
   vasca puo' comparire piu' volte.
   Assunzione v1: **un solo percorso condiviso da tutti i pezzi**.
3. **Cinematica**: `Kinematics(v_max, a_max)` separata per carroponte vuoto
   e carico.
4. **Takt time**: `takt_min`, `takt_max` (puoi calcolarli da
   `nominale ± tolleranza`).
5. **Carroponti e zone** (`HoistZone`): ogni carroponte serve una **zona
   contigua** di mosse (indici di trasporto, non di vasca). Ci sono tre
   modi per specificarli, dal piu' al meno automatico:
   - **numero di carroponti + zone entrambi automatici**: usa
     `solve_auto_hoists(data, max_hoists=...)` — cerca il numero minimo di
     carroponti che rispetta il takt time dato, e per ciascuno le zone
     migliori;
   - **numero di carroponti fissato, zone automatiche**: passa
     `zones=None` a `ProblemData` e usa
     `solve_auto_zones(data, n_hoists=...)`;
   - **tutto manuale**: specifica `zones` (lista di `HoistZone`) e usa
     `solve(data)` direttamente, se hai gia' un'idea precisa di come
     dividere la linea.
6. **Sicurezza**: `hoist_extent_pos`, `hoist_extent_neg` (ingombro del
   carrello, vedi sotto) e `safety_distance` (margine minimo aggiuntivo).
7. **Movimentazione verticale**: `kin_lift_empty`, `kin_lift_loaded`,
   `engage_time`, `disengage_time` — grandezze del carroponte. Corsa e
   sgocciolamento stanno sulla vasca (punto 1). Vedi sotto.

### Ingombro del carroponte

La posizione di un carroponte e' quella del suo **gancio**, che deve stare
sopra la vasca. Il carrello attorno al gancio non e' detto sia simmetrico, per
cui i due lati si dichiarano separatamente:

- `hoist_extent_pos` — quanto sporge verso le posizioni **crescenti**;
- `hoist_extent_neg` — quanto sporge verso le posizioni **decrescenti**.

La distanza minima richiesta fra i ganci di due carroponti e'

```text
D = hoist_extent_pos + hoist_extent_neg + safety_distance
```

Vale la pena capire **perche' compare solo la somma**. Se il carroponte di
sinistra ha il gancio in `p` e quello di destra in `q`, il bordo destro del
primo sta in `p + pos` e il bordo sinistro del secondo in `q - neg`: lo spazio
libero fra i due vale `q - p - (pos + neg)`. Dove sia il gancio *dentro* il
carrello non entra nel conto — a parita' di lunghezza totale, spostarlo avanti
o indietro non cambia nulla, perche' quello che si guadagna da un lato lo si
perde dall'altro.

Dichiararli separati resta comunque utile: rende esplicito che le posizioni
delle vasche sono riferite al gancio e non al centro del carrello, ed e' il
dato giusto da avere se un giorno servisse vincolare il carroponte rispetto a
strutture fisse o usare carroponti di modelli diversi sulla stessa rotaia.

### Capienza delle vasche (`capacity`)

`Tank.capacity` e' il numero di **posti simultanei** nella vasca, e vale `1`
per default. E' una proprieta' della **vasca fisica**, non della tappa del
percorso: se la ricetta passa due volte dalla stessa vasca, i pezzi delle due
tappe si contendono gli stessi posti.

Un pezzo tiene occupato un posto per

```text
occupazione = release_time + dwell + pick_time
```

— non solo il tempo in bagno: il telaio ingombra il posto dall'inizio
dell'immersione fino alla fine dell'emersione.

Per una vasca usata **una sola volta** nella ricetta i pezzi contemporaneamente
presenti sono `ceil(occupazione / T)`, e il modello impone

```text
occupazione <= capacity * T
```

che e' esattamente equivalente. `capacity` e' una costante intera e `T` una
variabile, quindi il vincolo resta lineare e non costa praticamente nulla.

Per una vasca usata **piu' volte** serve altro. Sommare i massimi delle singole
tappe sarebbe cautelativo e scarterebbe soluzioni valide: le tappe possono
essere sfasate fra loro, e allora un posto solo puo' bastare per entrambe. Il
modello usa quindi un vincolo **cumulativo** esatto — ogni pezzo occupa un
posto per il suo intervallo, gli intervalli si ripetono ogni `T`, e in nessun
istante se ne possono sovrapporre piu' di `capacity`. Verificato: su una linea
che passa due volte dalla stessa vasca con permanenze brevi, il modello trova
una soluzione con **un posto solo**, sfasando le due tappe.

Il default `1` e' deliberatamente il caso restrittivo: obbliga a **dichiarare**
le vasche multi-posto invece di lasciarlo implicito. Conseguenza pratica: con
`capacity=1` il takt time non puo' scendere sotto l'occupazione della vasca
piu' lenta. Nell'esempio ZINCATURA ha una permanenza di ~190 s con takt 110 s,
quindi e' dichiarata `capacity=2`.

Se una vasca e' irrimediabilmente insufficiente
(`release + dwell_min + pick > capacity * takt_max`), `ProblemData` lo rifiuta
subito con un messaggio esplicito, invece di lasciar restituire un
`INFEASIBLE` muto dopo minuti di ricerca.

Un limite da conoscere: la prima e l'ultima stazione (carico/scarico) sono
fuori dalla catena delle permanenze e quindi **non** hanno vincolo di capienza.

### Movimentazione verticale (presa e rilascio)

Il carroponte non si limita a traslare: cala il gancio, aggancia e tira su il
telaio, e all'arrivo lo immerge, sgancia e risale. I tempi **non si
dichiarano**: si ricavano dalla corsa verticale e dalle cinematiche di
sollevamento, con lo stesso profilo trapezoidale usato per il moto
orizzontale.

Del **carroponte** (uguali su tutta la linea, in `ProblemData`):

- `kin_lift_empty`, `kin_lift_loaded` — velocita' e accelerazione massime di
  sollevamento, a gancio scarico e col telaio;
- `engage_time` — aggancio del telaio, prima del sollevamento (tempo morto);
- `disengage_time` — sgancio, dopo l'immersione (tempo morto).

Della **vasca** (una per vasca, in `Tank`):

- `lift_height` — corsa fra quota di trasporto e quota di immersione: dipende
  da quanto e' profonda;
- `drain_time` — **sgocciolamento**: quanto il telaio resta sospeso sopra la
  vasca a lasciar scolare il bagno, dopo l'emersione.

Da cui:

```text
presa    = discesa a vuoto  + aggancio + risalita a carico + sgocciolamento
rilascio = discesa a carico + sgancio  + risalita a vuoto
```

Lo sgocciolamento sta **solo** nella presa: si scola uscendo dalla vasca, non
entrandoci.

Attenzione a leggere il foglio `Movimenti`: **`presa dalla vasca` non e' la
sola emersione**, e nemmeno la sola corsa verticale. Su una linea con corsa
1500 mm, sollevamento a 200 mm/s e sgocciolamento 10 s, una presa dura 26,5 s —
di cui 7,7 s sono la discesa del gancio a vuoto, 8,8 s l'emersione vera e 10 s
lo sgocciolamento. Cercarci dentro solo il tempo di salita, non trovarcelo e
sospettare un errore di calcolo e' successo davvero: per questo c'e' il foglio
`TempiVerticali`, che scompone presa e rilascio vasca per vasca.

Ne segue una cosa che vale la pena notare: **presa e rilascio percorrono le
stesse due tratte** (una a vuoto e una a carico), solo in ordine invertito, e
quindi differiscono unicamente per i tempi morti.

Nel codice le due righe qui sopra sono `ProblemData.pick_phases(stazione)` e
`release_phases(stazione)`: la scomposizione, non la sola durata. Ogni fase
dice quanto dura, da che quota a che quota porta il gancio, con quale profilo,
e **se il telaio e' appeso** — che e' l'unica cosa che distingue il pezzo dal
gancio (mentre il gancio scende vuoto a prenderlo, il pezzo sta ancora fermo in
fondo alla vasca). La durata totale e' la somma delle fasi, non un calcolo
parallelo: al calcolo serve solo il totale, alla simulazione serve sapere dove
sta il gancio istante per istante, e cosi' i due usi non possono divergere.

Allo stesso scopo ogni `Segment` porta il numero della **mossa** a cui
appartiene (`None` per attesa e rientro a vuoto, che stanno *fra* due mosse e
non sono di nessuna). Serve a risalire dalla traiettoria alla vasca — la presa
della mossa k avviene sulla stazione k, il rilascio sulla k+1 — e quindi alla
corsa verticale e allo sgocciolamento giusti. Dedurlo dalla posizione
sbaglierebbe appena due vasche stessero alla stessa quota, o appena la stessa
vasca comparisse due volte nella ricetta: due casi ammessi.

#### Perche' corsa e sgocciolamento stanno sulla vasca

Perche' sono della vasca, non del carroponte: la corsa dipende da quanto e'
profonda, lo sgocciolamento dalla chimica del bagno e dalla geometria del pezzo
— sulla zincatura e' lungo, su un risciacquo quasi nullo.

**Vanno dichiarati per ognuna, e non esiste un valore generale da cui
ereditare.** C'e' stato, ed era una trappola: un numero nei Parametri che si
applicava a tutte le vasche lasciate in bianco. Chi dimenticava una riga non
riceveva nessun segnale, e il calcolo usava un valore che nessuno aveva scelto
per quella vasca. Adesso una cella vuota e' un errore con foglio e cella, e
dove non serve niente si scrive **0** — che e' una dichiarazione, non una
dimenticanza.

Si vede subito sull'esempio: carico e scarico non sono bagni, quindi hanno
corsa 0 e scolo 0. Col vecchio valore generale prendevano 800 mm di corsa e 2 s
di scolo che nessuno voleva, e il takt time ne pagava il conto — 131,88 s
contro i 127,39 s che si ottennero togliendoli (e i 112,49 s di adesso, dopo la
correzione sulla permanenza descritta piu' sotto).

Con `lift_height = 0` su **tutte** le vasche le cinematiche di sollevamento non
servono e restano solo i tempi morti: e' la via da usare se si hanno tempi gia'
misurati sul campo invece della meccanica.

Ogni mossa dura quindi `presa + traslazione + rilascio`. Lo spostamento **a
vuoto non paga alcun tempo verticale**: dopo lo sgancio il gancio e' gia' in
alto (ce lo ha portato il rilascio) e ridiscendera' dentro la presa della mossa
successiva — contarlo di nuovo sarebbe doppio conteggio.

### Cosa comprende la permanenza in vasca

I tempi di permanenza (`permanenza_min_s` / `permanenza_max_s`) sono il tempo
**effettivo in bagno**: da quando il telaio e' immerso a quando ricomincia a
salire. Non vanno gonfiati a mano — ma bisogna sapere cosa ci sta dentro.

Ci stanno dentro **le due corse a vuoto del gancio**. Dopo lo sgancio il gancio
risale e il pezzo resta giu'; per riprenderlo un gancio deve ricalare, e il
pezzo e' ancora immerso. Sono secondi di bagno a tutti gli effetti, e su una
linea con corsa 1500 mm e sollevamento a 250 mm/s fanno **oltre quindici
secondi** — non un dettaglio.

```text
        immersione     sgancio   RISALITA          DISCESA   aggancio   emersione
   ────────────────┬──────────┬──────────┬── ... ──┬────────┬─────────┬───────────
                   └──────────────── il pezzo e' in bagno ────────────┘
                                  (permanenza)
                              └─ il gancio non c'e' ─┘
```

Per un po' il conto e' stato fatto sull'intervallo **fra i movimenti del
gancio** invece che sul bagno, ed era un errore vero: su una linea reale sei
vasche su dieci sforavano il massimo di processo — fino a +15,3 s — e il file
usciva con `VERIFICA SUPERATA` e zero rilievi. Il verificatore indipendente non
lo prendeva perche' misurava la stessa cosa del modello, che e' il modo in cui
un controllore smette di controllare.

Corretto, il conto va nelle due direzioni:

- dove il **massimo** e' vincolante, il ciclogramma si stringe — e qualche
  linea che prima "passava" adesso viene respinta, perche' sforava davvero;
- dove il **minimo** e' vincolante, si smette di sovra-processare e il ciclo si
  accorcia: sull'esempio il takt time scende **da 127,39 a 112,49 s**, cioe'
  circa un 13% di produttivita' in piu' a parita' di impianto.

Se la finestra di processo e' piu' stretta del bagno inevitabile — cioe' se
`permanenza_max_s` e' minore delle sole corse a vuoto piu' i tempi morti — la
linea non e' realizzabile e il programma **lo dice subito**, con il numero:
meglio di un `INFEASIBLE` muto che manda a cercare la causa dove non c'e'.

Le due fasi compaiono nel ciclogramma come segmenti orizzontali dedicati
(`Segment.kind` vale `"pick"` o `"release"`): il carroponte e' fermo sopra la
vasca, quindi si leggono come le spalle piatte agli estremi di ogni
trasferimento. Con tempi verticali nulli non viene emesso alcun segmento e il
risultato torna quello di una linea senza sollevamento.

Attenzione al dimensionamento: i tempi verticali si sommano a **ogni** mossa e
si fanno sentire in fretta. Nell'esempio fornito valgono da 16 a 25 s per mossa,
cioe' oltre 100 s di contenuto su 6 mosse: abbastanza da far passare la linea da
1 a 2 carroponti e da alzare il takt time da 110 a 132 s. E' un risultato
corretto, non una regressione — e' esattamente la ragione per cui vale la pena
modellarli invece di stimarli a occhio. Lo sgocciolamento, in particolare, e' il
contributo che si tende a dimenticare: portarlo da 2 a 15 s sulla sola zincatura
fa passare l'esempio a 3 carroponti.

### Scelta automatica del numero di carroponti e delle zone

```python
data = ProblemData(..., zones=None, ...)
solution, zones, n_hoists = solve_auto_hoists(data, max_hoists=4, time_limit_per_candidate=15.0,
                                               log_progress=True)
```

`solve_auto_hoists` prova N = 1, 2, 3, ... carroponti (fino a `max_hoists`)
in ordine crescente e si ferma al **primo** N per cui esiste una
suddivisione in zone fattibile entro la tolleranza di takt time data —
poiche' aggiungere carroponti puo' solo ampliare cio' che e' fattibile
(mai restringerlo), il primo N fattibile e' anche il minimo. Per ciascun N
tentato, internamente chiama `solve_auto_zones` (vedi sotto). Se nessun N
fino a `max_hoists` e' fattibile, `solution.status` sara' `"INFEASIBLE"` e
`zones`/`n_hoists` saranno `None` — in tal caso prova ad aumentare
`max_hoists` o la tolleranza sul takt time. Il dettaglio di ogni tentativo
(N, esito, T se trovato) e' anche in `solution.raw["hoist_sweep"]`.

### Scelta automatica delle sole zone (numero di carroponti fissato)

```python
data = ProblemData(..., zones=None, ...)
solution, zones = solve_auto_zones(data, n_hoists=2, time_limit_per_candidate=15.0,
                                    log_progress=True)
```

`solve_auto_zones` prova **tutte** le suddivisioni contigue possibili delle
mosse in `n_hoists` zone (scartando a priori, senza invocare CP-SAT, quelle
palesemente infattibili: una zona il cui solo trasporto-a-carico supera
gia' da solo il takt time massimo) e tiene la soluzione con il takt time
minore fra quelle fattibili. Il numero di suddivisioni possibili e'
`C(n_moves-1, n_hoists-1)`: per una manciata di carroponti e qualche decina
di mosse resta gestibile, ma cresce in fretta — il parametro
`max_candidates` (default 500) fa fallire la chiamata con un messaggio
chiaro se la ricerca esaustiva rischia di essere troppo lunga, cosi' puoi
decidere se aumentarlo, ridurre il problema, o specificare le zone a mano.

Nota: `data.zones` resta `None` dopo la chiamata (non viene modificato);
usa `zones` (il secondo valore restituito) — ad es. con
`dataclasses.replace(data, zones=zones)` — se ti serve un `ProblemData`
completo per altri usi (es. richiamare `plot_cyclogram`).

## Verifica indipendente della soluzione

```python
from verify import verify_solution

report = verify_solution(data_final, solution)   # data_final ha le zone valorizzate
print(report.summary())
if not report.ok:
    ...
```

`esempio.py` la esegue automaticamente dopo ogni risoluzione.

Il verificatore **non usa CP-SAT**: riparte dalla soluzione e ricontrolla ogni
vincolo in Python puro. Serve a rispondere alla domanda "e se fosse sbagliata
la formulazione stessa del modello?" — in quel caso il solver restituisce
comunque una soluzione dichiarata `OPTIMAL` e nulla se ne accorgerebbe.
Controlla:

1. struttura (takt time nella banda, zone contigue e coprenti);
2. **layout**: stazioni cosi' vicine a un confine di zona che il modello non
   le vincola (vedi sotto);
3. coerenza dei segmenti (continuita' nel tempo e nello spazio, ciclo di
   durata esattamente T, traiettoria che si richiude);
4. copertura delle mosse e durate delle tratte contro la cinematica reale;
5. coerenza di fase, cioe' la linearizzazione modulo T del modello;
6. permanenze min/max in vasca, dai tempi **assoluti**;
7. fattibilita' degli spostamenti a vuoto;
8. **collisioni reali**: la posizione di ogni carroponte viene campionata con
   `position_profile` (il profilo cinematico vero, non solo gli estremi delle
   finestre) e si controlla `|x_i(t) - x_j(t)| >= hoist_length + safety_distance`
   per ogni coppia e ogni istante;
9. capienza delle vasche: quanti posti servono davvero contro quanti sono
   dichiarati in `capacity`.

Il campionamento del punto 8 include **tutti** gli spigoli dei profili
cinematici piu' una griglia uniforme di un tick. Fra due spigoli la posizione
e' un polinomio di grado ≤ 2, quindi l'errore del minimo cosi' trovato e'
limitato in modo rigoroso da `(a_i + a_j)·dt²/8` — circa 0,02 mm con i valori
di default. Il valore e' riportato in `report.sampling_error_bound`.

### Verificatore e modello si controllano a vicenda

Il verificatore pretende `hoist_length + safety_distance` fra i due carroponti
**ovunque e sempre**, campionando la posizione reale. Il modello impone la
stessa cosa, ma per una via completamente diversa (vincoli lineari su
intervalli temporali, vedi sotto). Due strade indipendenti verso lo stesso
requisito: e' quello che rende la verifica utile invece che tautologica.

Storicamente il modello riservava l'intera finestra di sosta alla sola
stazione di **confine**, gonfiata di un buffer ricavato da *mezzo* ingombro.
Sul confine il criterio reggeva — la non sovrapposizione delle finestre separa
partenza e arrivo di due buffer, e poiche' lo spazio percorso da fermo cresce
in modo convesso, nell'istante peggiore entrambi i carroponti sono ad almeno
mezzo ingombro dal confine, su lati opposti.

**La garanzia cadeva in un caso preciso**: se un'altra stazione delle due zone
distava meno di `hoist_length + safety_distance` dal confine, il carroponte ci
sostava dentro la zona di esclusione del vicino, e nessun vincolo lo impediva.
Il modello ora non ragiona piu' in termini di "occupazione della stazione di
confine" ma di posizione reale nel tempo: vedi la sezione seguente.

## Non collisione: la fascia di esclusione

Attorno alla stazione di confine `b` fra due zone adiacenti, siano `a(t)` la
distanza del carroponte di sinistra da `b` e `c(t)` quella del carroponte di
destra. Poiche' le due zone stanno su lati opposti, la distanza fra i due
carroponti e' esattamente `a(t) + c(t)`, e serve

```text
a(t) + c(t) >= D          con D = hoist_length + safety_distance
```

Non e' esprimibile direttamente in CP-SAT, ma per ogni soglia `r` vale una
condizione **locale e lineare** che ne e' un'implicazione:

```text
mai contemporaneamente   a(t) < r   e   c(t) <= D - r
```

Vieta solo configurazioni con `a + c < D`, quindi non taglia mai nulla di
sicuro. Imponendola su una griglia di soglie abbastanza fitta si copre l'intera
condizione: se `a + c < D` basta una soglia nell'intervallo `(a, D - c]`, che e'
lungo piu' del passo della griglia. Usando passo `δ = passo_controllo_distanza_mm`
e portando il bersaglio a `D + δ`, **la distanza garantita torna esattamente D**,
e `δ` e' tutto e solo l'eccesso di severita' -- cioe' lo stesso passo, letto
dall'altro lato.

"`a(t) < r`" e' un'unione di intervalli temporali calcolabile dal modello: il
carroponte e' dentro la fascia mentre sosta su una stazione a distanza `< r`,
e per i tratti di percorso che ci entrano — con un margine costante, perche'
le vasche sono in posizioni fisse e quindi tutti i tempi di percorrenza lo
sono. La traiettoria di un periodo viene partizionata in blocchi (una mossa;
un trasferimento a vuoto) e dentro ogni blocco la distanza dal confine e'
monotona, il che rende il calcolo esatto.

Conseguenze pratiche:

- **le vasche possono stare vicine quanto si vuole.** Con passo 1000 mm e
  `D = 1800 mm` il modello trova soluzioni in cui i due carroponti sostano uno
  alla stazione precedente e uno alla successiva del confine: 2000 mm di
  separazione, sicuri. E' proprio la configurazione che il modello precedente
  non sapeva rappresentare. (Con la griglia predefinita a 6 passi questo caso
  cade appena oltre il limite della conservativita' e viene dichiarato
  infattibile: basta infittire `passo_controllo_distanza_mm` a 100. Vedi sotto.)
- **se davvero non ci stanno, esce INFEASIBLE**, non una soluzione sbagliata.
  Con passo 800 mm, mentre un carroponte e' sul confine l'altro non ha nessuna
  stazione abbastanza lontana in cui sostare: corretto;
- il vincolo e' anche **meno cautelativo del precedente**, che garantiva
  `hoist_length + 2·safety_distance` invece dei richiesti
  `hoist_length + safety_distance`.

### Il passo di controllo (`passo_controllo_distanza_mm`)

**Ogni quanti millimetri viene verificata la distanza fra due carroponti**,
attorno al confine fra le loro zone. Col valore predefinito, 200 mm: la prima
verifica a 200 mm dal confine, la seconda a 400, la terza a 600, e cosi' via
fino a coprire tutta la distanza richiesta.

Lo stesso numero si legge in due modi, ed e' la stessa quantita':

- **quanto sono fitte le verifiche** — il verso in cui lo si imposta;
- **di quanto il calcolo puo' essere piu' severo del dovuto** — la
  conseguenza. Fra una verifica e la successiva il modello non sa distinguere
  e sta dal lato sicuro, quindi con `D = 1800 mm` e passo 200 mm puo' arrivare
  a pretendere 2000 mm.

**Non e' un margine di sicurezza.** Se vuoi tenere i carroponti piu' lontani,
alza `distanza_sicurezza_mm`: quella e' una scelta d'impianto, entra nella
distanza richiesta e compare nei risultati. Questo e' il prezzo di
un'approssimazione, e infatti si infittisce quando da' fastidio.

**La distanza garantita e' sempre `D`, qualunque passo si metta.** Il
parametro puo' solo far scartare soluzioni buone, mai accettarne di
pericolose: non esiste un valore imprudente. L'unico costo e' la dimensione
del modello, perche' le verifiche sono `D / passo`.

Misurato su una linea a 4 mosse con vasche ogni 1500 mm (`D = 1800 mm`):

| passo | verifiche | pretende fino a | vincoli | calcolo | takt time | separazione reale |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 900 mm | 3 | 2700 mm | 696 | 1,6 s | 18,86 s | 3000 mm |
| 450 mm | 5 | 2250 mm | 928 | 0,9 s | 14,39 s | 2985 mm |
| 300 mm | 7 | 2100 mm | 1276 | 1,5 s | 13,79 s | 2699 mm |
| **200 mm** (default) | 10 | 2000 mm | 1740 | 2,1 s | 13,33 s | 2488 mm |
| 100 mm | 19 | 1900 mm | 3132 | 4,5 s | 12,85 s | 2297 mm |
| 50 mm | 37 | 1850 mm | 5916 | 7,0 s | 12,58 s | 2193 mm |

Il rendimento cala in fretta: da 900 a 200 mm si guadagnano 5,5 s di takt
time, da 200 a 50 mm altri 0,7 s al triplo del costo.

**Zero non e' ammesso**, e non per prudenza: il numero di verifiche e'
`D / passo`, che a zero e' infinito. Il valore viene rifiutato prima di
calcolare, con un messaggio che lo dice.

**"Pretende fino a" e' un limite superiore, non una formula esatta.** Il
vincolo agisce su intervalli di TEMPO, non sulle sole posizioni di sosta:
comprende anche i tratti in cui un carroponte entra o esce dalla fascia
muovendosi. Che una linea passi o no dipende quindi anche da come le verifiche
cadono rispetto alle traiettorie, non solo dal confronto fra `D + passo` e lo
spazio disponibile.

**Come regolarlo:**

- **lascialo a 200** finche' il calcolo trova soluzioni e il takt time e'
  ragionevole. Su una linea normale, dove le vasche stanno molto piu' larghe
  di `D`, quei 200 mm non toccano niente;
- **portalo a 100** se una linea con vasche ravvicinate esce INFEASIBLE. E' la
  prima cosa da provare, prima di aggiungere un carroponte: costa qualche
  secondo di calcolo e potrebbe non esserci nessun problema reale;
- **portalo a 100-50** se il takt time trovato sembra piu' alto di quanto la
  linea dovrebbe reggere e i carroponti si aspettano a vicenda vicino a un
  confine;
- **sotto i 50 mm non ha senso**: il modello cresce e il guadagno e'
  nell'ordine dei decimi di secondo. Su una linea con piu' confini fra
  carroponti il costo si moltiplica ancora.

Il modo rapido di capire se ti riguarda: guarda la **separazione minima** nel
riepilogo. Se e' molto piu' grande di quella richiesta, i carroponti hanno
spazio da vendere e questo parametro non c'entra. Se e' appiccicata al minimo,
sono le verifiche che stanno stringendo.

**Attenzione alla larghezza della banda di takt time.** Il numero di copie
traslate da generare e' calcolato sul caso peggiore `T = takt_min`, quindi una
banda molto larga (`takt_max` molte volte `takt_min`) fa crescere parecchio il
modello. Se la risoluzione diventa lenta, stringere la tolleranza sul takt time
e' la prima cosa da provare.

### Cosa resta non rappresentabile

Solo la geometria patologica: vasche non ordinate lungo la rotaia, con zone
adiacenti che si scavalcano o zone lontane che si sovrappongono nello spazio.
`model.zone_layout_conflicts(data, zones)` la rileva, `solve()` la rifiuta con
un messaggio esplicito, e `solve_auto_zones` la usa come pre-filtro accanto a
quello sul takt time — cosi' la scelta automatica delle zone trova da sola una
suddivisione valida quando esiste.

## Assunzioni e limitazioni importanti (leggere prima di fidarsi dei risultati)

Il modello implementato (vedi commenti dettagliati in testa a `model.py`)
fa scelte di modellazione precise, in particolare:

- **Zone contigue**: ogni carroponte gestisce sempre un gruppo contiguo di
  mosse (stazioni). E' l'approccio piu' diffuso nella pratica industriale,
  ma non e' la formulazione piu' generale possibile (un carroponte non puo'
  "scavalcare" il territorio di un altro).
- **Le zone sono scelte per enumerazione esaustiva, non dentro al modello
  CP-SAT**: `solve_auto_zones` risolve un modello CP-SAT separato per
  ciascuna suddivisione candidata e tiene la migliore, invece di rendere il
  confine fra zone una variabile del modello unico. E' una scelta
  deliberatamente piu' semplice e robusta (riusa `solve()` cosi' com'e',
  gia' testato) a scapito della scalabilita' per problemi con molte mosse e
  molti carroponti — vedi `max_candidates`.
- **Ordine di visita libero entro la zona**: ogni carroponte puo' visitare
  le mosse della propria zona in QUALSIASI ordine ad ogni ciclo (non
  costretto a un unico giro sequenziale + un solo rientro), modellato con
  un vincolo di circuito ciclico (`AddCircuit`). Questo permette di trovare
  un ciclogramma fattibile anche quando il tempo "a calendario" della zona
  (attese nelle vasche incluse) supera abbondantemente il takt time: il
  carroponte puo' andare a servire un'altra mossa mentre un pezzo e'
  ancora a bagno, invece di restare fermo ad aspettare. Il vincolo che
  resta davvero rigido e' che la somma dei tempi di trasporto carico e dei
  trasferimenti a vuoto necessari (esclusi i tempi di attesa nelle vasche)
  stia entro il takt time: se anche questo viene superato, nessun ordine
  di visita puo' risolvere il problema.
- **Collisioni vincolate attorno ai confini di zona**: e' l'unica regione in
  cui due carroponti possono avvicinarsi in questa formulazione (zone
  contigue). Il vincolo tiene conto della posizione reale nel tempo e funziona
  con qualunque spaziatura fra le vasche, ma resta leggermente conservativo:
  puo' scartare soluzioni "al limite" che in pratica sarebbero fattibili.
  Quanto, lo regola `passo_controllo_distanza_mm` (vedi "Non collisione").
- **Posizione di attesa non scelta dal solver**: per convenzione un carroponte
  che ha consegnato riparte subito e attende alla stazione della mossa
  successiva. Poterlo far attendere altrove gli darebbe piu' modo di
  allontanarsi dal vicino.
- **Capienza delle vasche**: vincolata tramite `Tank.capacity`, in modo esatto
  anche quando la stessa vasca compare piu' volte nella ricetta, ma solo per le
  stazioni intermedie (carico e scarico restano fuori).
- **Un solo percorso vasche** condiviso da tutti i pezzi (nessun mix di
  prodotti diversi in questa versione).

Nella sezione finale di `model.py` ("Estensioni possibili") sono descritte
le direzioni per superare le limitazioni residue (assegnazione non
contigua fra zone, piu' ricette, collisione meno conservativa).

## Nota sui test effettuati

```bash
python kinematics.py        # autotest della cinematica
python test_verify.py       # il verificatore              (no OR-Tools)
python test_excel_io.py     # lettura e scrittura Excel    (no OR-Tools)
python test_simulazione.py  # la simulazione               (no OR-Tools)
python test_model.py        # il modello CP-SAT            (serve OR-Tools)
python test_interfaccia.py  # l'interfaccia grafica        (serve OR-Tools)
python esempio.py           # risoluzione reale + verifica + grafico
```

Ognuno stampa cosa ha provato e finisce con `RISULTATO: n ok, m falliti`.
Nessuna dipendenza da pytest. Stato attuale: **67, 81, 56, 28 e 95 asserzioni,
zero fallimenti**.

**La risoluzione CP-SAT e' eseguita e verificata end-to-end.** Sull'esempio
fornito il solver trova `T = 112,49 s` con 2 carroponti, separazione minima
3500 mm contro 1800 mm richiesti, e il verificatore indipendente conferma la
soluzione senza errori.

I cinque file rispondono a domande diverse e si completano:

- `test_verify.py` — 21 casi. *Il verificatore trova davvero quello che deve
  trovare?* Uno solo dei casi e' corretto, gli altri sono rotti di proposito
  (collisioni, permanenze, periodicita', fasi verticali, capienza, geometrie
  patologiche). Le soluzioni sono costruite a mano, quindi non serve OR-Tools.
- `test_model.py` — 10 casi. *Il modello produce soluzioni fisicamente valide?*
  Risolve davvero e passa ogni risultato al verificatore.
- `test_excel_io.py` — 23 casi. *Un file compilato male viene respinto con un
  messaggio utile, e i risultati escono corretti?* In ingresso: valori mancanti
  o non numerici, vasche inesistenti o duplicate, righe riordinate, parametri
  sbagliati, zone incomplete, e un file della vecchia versione in metri. In uscita: struttura dei fogli, corrispondenza
  fra tratti e vasche, somma delle durate pari al takt time.
- `test_simulazione.py` — 10 casi. *La simulazione mostra il ciclogramma che
  c'e', o una sua approssimazione?* Il controllo che conta e' incrociato: su un
  ciclogramma coerente, ogni pezzo appeso deve stare **esattamente** dove sta
  il gancio di un carroponte che lo tiene, e viceversa — su millecinquecento
  istanti lo scarto massimo e' 3e-11 mm, cioe' zero. E le vasche di prova hanno
  corse verticali diverse fra loro apposta, perche' con corse tutte uguali
  prendere quella della vasca sbagliata darebbe comunque il risultato giusto.
- `test_interfaccia.py` — 11 casi. *L'interfaccia si comporta come deve?* La
  finestra viene costruita davvero e pilotata da codice. E' l'unico modo per
  accorgersi che un pulsante e' rimasto disabilitato, che il calcolo in
  background non consegna mai il risultato, o che una modifica impossibile
  manda tutto per aria invece di essere rifiutata: cose che un test sulle sole
  funzioni di calcolo non vedrebbe.

In piu', il vincolo di non collisione e' stato validato su uno **sweep di 288
configurazioni** (numero di mosse, spaziatura da 1000 a 3000 mm, tempi verticali,
passo di controllo, punto di taglio delle zone): 146 risolte e verificate,
**zero errori**. Come controllo di sensibilita', lo stesso sweep con il vincolo
disattivato produce 159 soluzioni con collisioni reali — se ci fosse un buco
nella formulazione, lo sweep lo avrebbe visto.

### Cosa ha gia' trovato il verificatore

Non e' un esercizio teorico: da quando esiste ha intercettato quattro problemi
reali, tutti invisibili guardando solo lo stato `OPTIMAL` del solver.

0. **Permanenze in vasca fuori tolleranza, non viste da nessuno** — e' il caso
   che il verificatore *non* ha trovato, ed e' istruttivo per questo. La
   permanenza veniva misurata fra i movimenti del gancio invece che sul bagno,
   e il verificatore usava la stessa definizione del modello: su una linea
   reale sei vasche su dieci sforavano il massimo di processo (fino a +15,3 s
   su una da 215 s) e il referto diceva `VERIFICA SUPERATA`, zero rilievi. Se
   n'e' accorto un utente guardando i tempi. **Corretto** portando il controllo
   sul tempo effettivo in bagno; morale: un verificatore che condivide una
   definizione col controllato, su quella definizione non verifica niente.

1. **Collisioni con vasche ravvicinate** — con spaziatura inferiore a
   `hoist_length + safety_distance`, CP-SAT restituiva soluzioni `OPTIMAL`
   con i carroponti a 1240 mm invece di 1800 mm, perche' il vincolo copriva solo
   la stazione di confine. **Corretto** riformulando la non collisione sulla
   fascia di esclusione (vedi sopra): ora quelle geometrie si risolvono, e
   correttamente.
2. **Finestre di occupazione da correggere per i tempi verticali** — l'aggiunta
   di `pick_time`/`release_time` avrebbe introdotto una collisione vera se le
   finestre ai confini non fossero state estese per coprire le fasi verticali
   (il carroponte e' fermo sopra la vasca di confine anche mentre immerge o
   ripesca il pezzo). Su uno sweep di 108 configurazioni, la versione priva di
   quella correzione produce 58 soluzioni con collisioni — fino a 0 mm di
   separazione; con la correzione, zero errori.
3. **Segmenti degeneri di durata nulla** — quando due mosse consecutive
   condividono la stazione, la ricostruzione della traiettoria emetteva uno
   spostamento a vuoto di lunghezza zero che, sommato allo scarto di
   arrotondamento sui tick, si ordinava male rispetto ai vicini e spezzava la
   traiettoria. Difetto preesistente, corretto.

Un quarto difetto non l'ha trovato il verificatore ma l'uso dell'interfaccia:
`plot_cyclogram` disegnava solo gli stati `OPTIMAL` e `FEASIBLE`, mentre una
soluzione ritoccata a mano ha stato `MANUALE`. Il risultato era che **il
grafico si svuotava alla prima modifica**, sostituito da "Impossibile
disegnare", proprio nella funzione che serve a modificare guardando il grafico.
Le tabelle e la verifica intanto si aggiornavano regolarmente, quindi nessun
test se ne era accorto. Ora si disegna qualunque soluzione che abbia dei
segmenti, e un test controlla che dopo una modifica il grafico ci sia ancora.
Morale: un controllo scritto per rifiutare l'input sbagliato che finisce per
rifiutare anche quello giusto e' un modo comune di rompere le cose in silenzio.

### Storia precedente

Nella prima stesura non era stato possibile installare `ortools`
(nessun accesso di rete), quindi la risoluzione CP-SAT non era mai stata
eseguita. Erano stati testati solo:
cinematica (`kinematics.py`), costruzione delle strutture dati e delle loro
validazioni (incluso `zones=None`), l'enumerazione delle suddivisioni
contigue (`_enumerate_contiguous_partitions`, con verifica che ogni
suddivisione copra tutte le mosse esattamente una volta), i controlli di
validazione di `solve_auto_zones` e `solve_auto_hoists` (n_hoists/
min_hoists/max_hoists eccessivi o incoerenti, max_candidates superato), lo
sweep crescente su N carroponti di `solve_auto_hoists` (verificato che
parta da `min_hoists` e proceda correttamente fino al primo tentativo di
risoluzione reale), e la ricostruzione della traiettoria
(`_build_zone_trajectory`) con valori scelti a mano — incluso un caso con
**ordine di visita non sequenziale** (es. un carroponte con zona di 4 mosse
che le esegue nell'ordine 0→2→1→3→0) e un caso limite di puro arrotondamento
numerico (la causa del secondo bug segnalato, ora corretto con una
tolleranza proporzionata alla risoluzione dei tick). Il codice era stato
controllato riga per riga contro la API di OR-Tools CP-SAT, ma senza mai
eseguirlo: e' esattamente il rischio residuo che il verificatore indipendente
descritto sopra e' stato costruito per coprire.
