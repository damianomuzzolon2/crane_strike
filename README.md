# Ciclogrammi carroponti (Cyclic Hoist Scheduling) con OR-Tools CP-SAT

Strumento per calcolare il ciclogramma periodico di uno o piu' carroponti
che spostano pezzi attraverso una sequenza di vasche, rispettando:

- tempi di permanenza min/max per vasca (tolleranza di processo),
- un takt time target con tolleranza,
- velocita'/accelerazione massime diverse per carroponte vuoto e carico,
- vincoli di non collisione fra carroponti sulla stessa rotaia.

## Perche' CP-SAT

Il problema è un **Cyclic Hoist Scheduling Problem (CHSP)**: un problema di
scheduling ciclico, NP-hard, con vincoli fortemente disgiuntivi (due
carroponti non possono occupare lo stesso punto di rotaia nello stesso
istante). La Constraint Programming — e nello specifico CP-SAT di OR-Tools —
è lo strumento standard in letteratura per questo tipo di problema, proprio
per la sua naturalezza nel esprimere vincoli disgiuntivi/di non-overlap e
periodici. È una scelta valida: il codice qui sotto la usa.

## File

- `kinematics.py` — tempo di percorrenza e profilo di posizione per un moto
  trapezoidale/triangolare (accelerazione costante, eventuale crociera,
  decelerazione costante).
- `model.py` — strutture dati di input, costruzione del modello CP-SAT e
  risoluzione, estrazione della traiettoria di ciascun carroponte.
- `plotting.py` — disegna il ciclogramma (posizione vs tempo).
- `verify.py` — **verificatore indipendente**: ricontrolla in Python puro
  (senza CP-SAT) che la soluzione trovata sia davvero valida.
- `test_verify.py` — test del verificatore, non richiede OR-Tools.
- `test_model.py` — test end-to-end del modello, richiede OR-Tools.
- `esempio.py` — esempio completo end-to-end, eseguibile da riga di comando.

## Installazione ed esecuzione

```bash
pip install ortools matplotlib
python esempio.py
```

Verra' stampato lo stato della risoluzione e (se una soluzione e' trovata)
salvato `ciclogramma.png` col grafico.

## Come modellare il tuo caso

1. **Vasche** (`Tank`): id, posizione `[m]` lungo la rotaia e numero di posti
   simultanei (`capacity`, default 1 — vedi sotto).
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
6. **Sicurezza**: `hoist_length` (ingombro) e `safety_distance` (margine
   minimo aggiuntivo) vengono usati per allargare le finestre temporali di
   occupazione dei punti di confine fra zone adiacenti.
7. **Movimentazione verticale**: `pick_time` e `release_time` (vedi sotto).

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

### Tempo di presa e rilascio (immersione/emersione)

Il carroponte non si limita a traslare: deve calare il gancio, agganciare e
tirare su il telaio, e all'arrivo immergerlo, sganciare e risalire. Sono due
costanti in `ProblemData`, entrambe con default `0.0`:

- `pick_time` — discesa gancio + aggancio + emersione dal bagno con
  l'eventuale sgocciolamento sopra la vasca;
- `release_time` — immersione nella vasca di destinazione + sgancio +
  risalita del gancio a vuoto.

Ogni mossa dura quindi `pick_time + traslazione + release_time`. Lo
spostamento **a vuoto non paga alcun tempo verticale**: dopo lo sgancio il
gancio e' gia' in alto (lo ha portato su `release_time`) e ridiscendera'
dentro `pick_time` della mossa successiva — contarlo di nuovo sarebbe doppio
conteggio.

Conseguenza importante per l'interpretazione dei dati di processo: i tempi di
permanenza (`dwell_min`/`dwell_max`) restano il tempo **effettivo in bagno**,
misurato da fine immersione a inizio emersione. Non vanno gonfiati a mano per
tenere conto delle fasi verticali.

Le due fasi compaiono nel ciclogramma come segmenti orizzontali dedicati
(`Segment.kind` vale `"pick"` o `"release"`), in arancio e viola: il
carroponte e' fermo sopra la vasca. Con entrambi i tempi a zero non viene
emesso alcun segmento verticale e il risultato e' identico a prima.

Attenzione al dimensionamento: i tempi verticali si sommano a **ogni** mossa e
si fanno sentire in fretta. Nell'esempio fornito, `pick_time=6 s` e
`release_time=4 s` su 6 mosse aggiungono 60 s di contenuto e fanno passare la
linea da 1 a 2 carroponti — e' un risultato corretto, non una regressione.

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
lungo piu' del passo della griglia. Usando passo `δ = D / clearance_steps` e
portando il bersaglio a `D + δ`, **la distanza garantita torna esattamente D**.

"`a(t) < r`" e' un'unione di intervalli temporali calcolabile dal modello: il
carroponte e' dentro la fascia mentre sosta su una stazione a distanza `< r`,
e per i tratti di percorso che ci entrano — con un margine costante, perche'
le vasche sono in posizioni fisse e quindi tutti i tempi di percorrenza lo
sono. La traiettoria di un periodo viene partizionata in blocchi (una mossa;
un trasferimento a vuoto) e dentro ogni blocco la distanza dal confine e'
monotona, il che rende il calcolo esatto.

Conseguenze pratiche:

- **le vasche possono stare vicine quanto si vuole.** Con passo 1,0 m e
  `D = 1,80 m` il modello trova soluzioni in cui i due carroponti sostano uno
  alla stazione precedente e uno alla successiva del confine: 2,0 m di
  separazione, sicuri. E' proprio la configurazione che il modello precedente
  non sapeva rappresentare;
- **se davvero non ci stanno, esce INFEASIBLE**, non una soluzione sbagliata.
  Con passo 0,80 m, mentre un carroponte e' sul confine l'altro non ha nessuna
  stazione abbastanza lontana in cui sostare: corretto;
- il vincolo e' anche **meno cautelativo del precedente**, che garantiva
  `hoist_length + 2·safety_distance` invece dei richiesti
  `hoist_length + safety_distance`.

### Il parametro `clearance_steps`

Regola la finezza della griglia di soglie (default 6). La distanza garantita
e' sempre quella richiesta: alzarlo riduce la **conservativita'**, cioe'
permette takt time piu' bassi, al prezzo di un modello piu' grande. Misurato
su una linea a 4 mosse con passo 1,5 m:

| `clearance_steps` | takt time | separazione reale |
| ---: | ---: | ---: |
| 2 | 18,86 s | 3,000 m |
| 4 | 14,39 s | 2,985 m |
| 8 | 13,45 s | 2,545 m |

Sotto i 4 passi la conservativita' si vede, sopra i 12 il modello cresce senza
gran guadagno.

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
  Quanto, lo regola `clearance_steps` (vedi "Non collisione").
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
python kinematics.py     # autotest della cinematica
python test_verify.py    # test del verificatore (non richiede OR-Tools)
python test_model.py     # test end-to-end del modello (richiede OR-Tools)
python esempio.py        # risoluzione CP-SAT reale + verifica + grafico
```

**La risoluzione CP-SAT e' eseguita e verificata end-to-end.** Sull'esempio
fornito (con i tempi verticali attivi) il solver trova `T = 110 s` con 2
carroponti, separazione minima 3,50 m contro 1,80 m richiesti, e il
verificatore indipendente conferma la soluzione senza errori.

I due file di test rispondono a domande opposte e si completano:

- `test_verify.py` — 19 casi, 49 asserzioni. *Il verificatore trova davvero
  quello che deve trovare?* Uno solo dei casi e' corretto, gli altri sono rotti
  di proposito (collisioni, permanenze, periodicita', fasi verticali, capienza,
  geometrie patologiche). Non richiede OR-Tools: le soluzioni sono costruite a
  mano.
- `test_model.py` — 7 casi, 16 asserzioni. *Il modello produce soluzioni
  fisicamente valide?* Risolve davvero e passa ogni risultato al verificatore.

In piu', il vincolo di non collisione e' stato validato su uno **sweep di 288
configurazioni** (numero di mosse, spaziatura da 1,0 a 3,0 m, tempi verticali,
`clearance_steps`, punto di taglio delle zone): 146 risolte e verificate,
**zero errori**. Come controllo di sensibilita', lo stesso sweep con il vincolo
disattivato produce 159 soluzioni con collisioni reali — se ci fosse un buco
nella formulazione, lo sweep lo avrebbe visto.

### Cosa ha gia' trovato il verificatore

Non e' un esercizio teorico: da quando esiste ha intercettato tre problemi
reali, tutti invisibili guardando solo lo stato `OPTIMAL` del solver.

1. **Collisioni con vasche ravvicinate** — con spaziatura inferiore a
   `hoist_length + safety_distance`, CP-SAT restituiva soluzioni `OPTIMAL`
   con i carroponti a 1,24 m invece di 1,80 m, perche' il vincolo copriva solo
   la stazione di confine. **Corretto** riformulando la non collisione sulla
   fascia di esclusione (vedi sopra): ora quelle geometrie si risolvono, e
   correttamente.
2. **Finestre di occupazione da correggere per i tempi verticali** — l'aggiunta
   di `pick_time`/`release_time` avrebbe introdotto una collisione vera se le
   finestre ai confini non fossero state estese per coprire le fasi verticali
   (il carroponte e' fermo sopra la vasca di confine anche mentre immerge o
   ripesca il pezzo). Su uno sweep di 108 configurazioni, la versione priva di
   quella correzione produce 58 soluzioni con collisioni — fino a 0,00 m di
   separazione; con la correzione, zero errori.
3. **Segmenti degeneri di durata nulla** — quando due mosse consecutive
   condividono la stazione, la ricostruzione della traiettoria emetteva uno
   spostamento a vuoto di lunghezza zero che, sommato allo scarto di
   arrotondamento sui tick, si ordinava male rispetto ai vicini e spezzava la
   traiettoria. Difetto preesistente, corretto.

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
