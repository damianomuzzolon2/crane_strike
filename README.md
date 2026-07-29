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
- `esempio.py` — esempio completo end-to-end, eseguibile da riga di comando.

## Installazione ed esecuzione

```bash
pip install ortools matplotlib
python esempio.py
```

Verra' stampato lo stato della risoluzione e (se una soluzione e' trovata)
salvato `ciclogramma.png` col grafico.

## Come modellare il tuo caso

1. **Vasche** (`Tank`): id e posizione `[m]` lungo la rotaia.
2. **Percorso** (`route`, lista di `StationSpec`): sequenza di vasche che il
   pezzo attraversa, con tempo di permanenza `[min,max]` in secondi.
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
9. quanti pezzi stanno contemporaneamente in ciascuna vasca.

Il campionamento del punto 8 include **tutti** gli spigoli dei profili
cinematici piu' una griglia uniforme di un tick. Fra due spigoli la posizione
e' un polinomio di grado ≤ 2, quindi l'errore del minimo cosi' trovato e'
limitato in modo rigoroso da `(a_i + a_j)·dt²/8` — circa 0,02 mm con i valori
di default. Il valore e' riportato in `report.sampling_error_bound`.

### Il verificatore e' piu' severo del modello (di proposito)

Il modello riserva l'intera finestra di sosta alla stazione di **confine** fra
due zone, gonfiata di un buffer temporale ricavato da **mezzo** ingombro
(`hoist_length/2 + safety_distance`). Il verificatore invece pretende
`hoist_length + safety_distance` fra i due carroponti **ovunque e sempre**.

Sul confine i due criteri sono compatibili: la non sovrapposizione delle
finestre separa partenza e arrivo di due buffer, e poiche' lo spazio percorso
da fermo cresce in modo convesso, nell'istante peggiore entrambi i carroponti
sono ad almeno mezzo ingombro dal confine, su lati opposti. La separazione
garantita e' quindi `hoist_length + 2·safety_distance`, piu' del richiesto.

**La garanzia cade in un caso preciso**: se la stazione *adiacente* a una
stazione di confine dista meno di `hoist_length + safety_distance`, il
carroponte ci sosta dentro la zona di esclusione del vicino, e il modello non
ha alcun vincolo che lo impedisca. Il controllo 2 segnala questa condizione in
anticipo, come avviso; il controllo 8 la trova poi come errore se si traduce
in una collisione vera. E' una **lacuna nota del modello**, non un falso
positivo del verificatore: con vasche molto ravvicinate CP-SAT restituisce
soluzioni `OPTIMAL` che il verificatore respinge, ed ha ragione lui.
Nell'esempio fornito le vasche distano almeno 2,5 m contro 1,8 m richiesti,
quindi la condizione e' rispettata e la verifica passa pulita.

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
- **Collisioni modellate solo ai confini di zona**: e' l'unico punto in cui
  due carroponti condividono fisicamente lo spazio in questa formulazione.
  Le finestre di occupazione usate sono conservative (tutto l'intervallo fra
  arrivo e partenza), quindi il modello non rifiuta mai una soluzione
  davvero sicura, ma potrebbe scartarne alcune "al limite" che in pratica
  sarebbero fattibili con un margine di sicurezza piu' fine.
  **Attenzione**: questo vale solo se le stazioni adiacenti a un confine
  distano almeno `hoist_length + safety_distance`; altrimenti il modello ha
  una vera lacuna — vedi "Il verificatore e' piu' severo del modello".
- **Nessun vincolo di capienza delle vasche**: nulla impedisce che piu' pezzi
  si trovino contemporaneamente nella stessa vasca. Accade sistematicamente
  quando la permanenza supera il takt time (nell'esempio ZINCATURA ha una
  permanenza di ~200 s con takt 110 s, quindi ci sono sempre 2 pezzi dentro).
  Il verificatore lo riporta come nota informativa.
- **Un solo percorso vasche** condiviso da tutti i pezzi (nessun mix di
  prodotti diversi in questa versione).

Nella sezione finale di `model.py` ("Estensioni possibili") sono descritte
le direzioni per superare le limitazioni residue (assegnazione non
contigua fra zone, piu' ricette, collisione meno conservativa, tempi di
presa/rilascio pezzo).

## Nota sui test effettuati

```bash
python kinematics.py     # autotest della cinematica
python test_verify.py    # test del verificatore (non richiede OR-Tools)
python esempio.py        # risoluzione CP-SAT reale + verifica + grafico
```

**La risoluzione CP-SAT e' ora eseguita e verificata end-to-end.** Sull'esempio
fornito il solver trova `T = 110 s` con un solo carroponte e il verificatore
indipendente conferma la soluzione senza errori. Sono stati provati anche i
casi a 2 e 3 carroponti forzati (zone imposte a mano): separazione minima
rispettivamente 3,50 m e 3,00 m contro 1,80 m richiesti.

`test_verify.py` contiene 13 casi: uno corretto e dodici rotti di proposito
(collisione statica, collisione visibile solo campionando dentro il
movimento, permanenze fuori tolleranza, periodicita' incoerente, ciclo di
durata sbagliata, discontinuita', tratta piu' veloce della cinematica, layout
stretto, takt fuori banda, capienza vasca, input malformato, soluzione senza
valori risolti). Tutti e 13 passano.

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
