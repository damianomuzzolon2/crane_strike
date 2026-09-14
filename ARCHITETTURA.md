# Architettura del codice

Documento per chi deve **mettere le mani nel codice**. Il `README.md` spiega
cosa fa il programma e come si usa; questo spiega com'e' fatto dentro, quali
invarianti regge, e dove sono le trappole — comprese quelle in cui siamo gia'
caduti, che sono la parte piu' utile.

Stato al momento della scrittura: 16 file Python, 15.223 righe, cinque suite di
test per **467 asserzioni** complessive.

---

## 1. La mappa, e la direzione delle dipendenze

### Dove stanno i file

In radice ci sono **solo i nove moduli** del programma, i due documenti, il
`.bat` e `requirements.txt`. Il resto sta in `test/`, `strumenti/`, `doc/`,
`dati/`.

I moduli non sono in un package di proposito: si importano per nome
(`from model import solve`) e i programmi si avviano direttamente
(`python interfaccia.py`). Un package obbligherebbe a `python -m` e a
qualificare ogni import, e questo programma non si installa mai con `pip` —
gira dalla cartella o dall'eseguibile PyInstaller. Il prezzo e' che chi sta in
una sottocartella deve rimettersi la radice fra i percorsi di ricerca: i test
lo fanno con tre righe in testa al file, il `.spec` con `SPECPATH`.

### La documentazione riga per riga

In `doc/` c'e' una sottocartella per modulo con i documenti Word che lo
spiegano funzione per funzione — ventiquattro documenti che coprono tutte e
299 le fra funzioni e metodi — piu' `ALBERO_DELLE_CHIAMATE.docx`. Si
rigenerano con `python strumenti/genera_doc.py`, e il testo sta in
`strumenti/doc_contenuti/<modulo>.py`.

Due cose da sapere prima di modificare il codice:

- **il codice citato non e' trascritto**, viene ritagliato dal sorgente per
  nome (via AST) delimitando i tratti con pezzi di righe vere. Se una riga
  citata sparisce la generazione **fallisce**, dicendo quale documento e quale
  ancora: e' il segnale che quel paragrafo va riscritto;
- `python strumenti/genera_doc.py --copertura` dice quali funzioni **non**
  sono ancora spiegate. Una funzione nuova ci compare subito.

L'albero delle chiamate lo ricava l'AST a ogni generazione, e con lui verifica
da solo la regola qui sotto: nessun modulo chiama quelli che gli stanno sopra.

### La direzione delle dipendenze

```text
  interfaccia.py      ciclogramma.py   test/esempio.py      <- si lanciano
        |                   |                  |
        +-------------------+------------------+
        |          |          |         |          |
  excel_io.py manuale.py plotting.py verify.py simulazione.py
        |          |          |         |          |
        +----------+----+-----+---------+----------+
                        |
                    model.py                     <- motore (CP-SAT)
                        |
                  kinematics.py                  <- fisica
```

Le dipendenze vanno **in una direzione sola** ed e' un vincolo, non un caso:

- `kinematics.py` non sa che esiste un ciclogramma. Si prova senza OR-Tools.
- `model.py` non sa che esiste un'interfaccia. Importa `ortools` **in modo
  pigro**, dentro `solve()`: le dataclass, la ricostruzione delle traiettorie e
  `build_solution` restano usabili e testabili anche senza OR-Tools installato.
  `test_verify.py` conta su questo.
- `verify.py` non importa `ortools` **mai**. E' la ragione per cui esiste: un
  verificatore che usasse lo stesso solutore non verificherebbe niente.

Chi rompe questa direzione rompe la testabilita' del progetto.

---

## 2. Convenzioni che valgono ovunque

**Unita': millimetri e secondi.** Tutto. Posizioni, corse, velocita' (mm/s),
accelerazioni (mm/s²). Il progetto e' nato in metri ed e' stato convertito in
blocco: la cinematica e' invariante di scala (profili trapezoidali), quindi la
conversione e' stata una pura rietichettatura. Se aggiungi una grandezza,
scrivi l'unita' nel nome del campo Excel (`_mm`, `_s`, `_mm_s`).

**Tick interi per CP-SAT.** `ProblemData.time_scale` (default 100) e' la
risoluzione: `to_ticks`/`to_seconds` convertono. La tolleranza numerica del
progetto e' `ProblemData.eps_seconds` = `max(10/time_scale, 1e-6)` = 0,1 s.
Ovunque serva confrontare tempi calcolati per vie diverse — CP-SAT arrotonda al
tick, la ricostruzione ricalcola in virgola mobile — si usa **quella**, non un
epsilon inventato sul posto.

**L'italiano e' la lingua del codice.** Commenti, docstring, messaggi
all'utente, nomi dei test. Gli identificatori di `model.py`, `verify.py` e
`kinematics.py` sono in inglese (`pick_time_at`, `loaded_leg_seconds`) perche'
il dominio lo e'; l'interfaccia e i moduli di supporto sono in italiano. I
messaggi di errore sono sempre in italiano e sempre **dicono cosa fare**.

**Niente default silenziosi.** Corsa verticale e sgocciolamento sono
obbligatori per ogni vasca (`Tank.lift_height`, `Tank.drain_time`, dichiarati
`field(kw_only=True)` apposta, cosi' una chiamata posizionale scritta per una
versione vecchia esplode invece di assegnarli di nascosto). Dove non serve
niente si scrive `0`, che e' una dichiarazione; una cella vuota no.

---

## 3. `kinematics.py` — la fisica, 130 righe

Tre funzioni pure, nessuno stato:

| funzione | cosa da |
| --- | --- |
| `travel_time(distance, kin)` | tempo minimo con profilo trapezoidale o triangolare |
| `position_profile(t, distance, kin)` | spazio percorso a `t`, **senza segno**, con `t` clampato in `[0, t_total]` |
| `profile_breakpoints(distance, kin)` | gli spigoli della curva |

Due dettagli che il resto del progetto sfrutta:

- `position_profile` **clampa da sola** il tempo fuori intervallo. E' quello
  che permette al campionatore di `verify.py` e alla simulazione di assorbire
  senza logica aggiuntiva le micro-sovrapposizioni fra segmenti lasciate dagli
  arrotondamenti sui tick.
- `profile_breakpoints` esiste per un motivo preciso: fra due spigoli la
  posizione e' un polinomio di grado ≤ 2, quindi anche la **differenza** fra due
  traiettorie lo e'. Campionando tutti gli spigoli piu' una griglia di passo
  `dt`, l'errore sul minimo cercato e' limitato da `(a_i + a_j)/2 · (dt/2)²`.
  E' cosi' che `verify.py` da' un limite **rigoroso** e non una speranza.

---

## 4. `model.py` — strutture dati, 2071 righe

### 4.1 Le dataclass

```text
Tank            id, position, capacity, lift_height, drain_time,
                svincolo_pos, svincolo_neg, gancio_basso
StationSpec     tank_id, dwell_min, dwell_max       (una tappa del percorso)
HoistZone       lo, hi                               (intervallo di MOSSE)
ZonaCambioQuota position, intermediate1, intermediate2, corsa_totale
LiftPhase       name, duration, z_start, z_end, kin, loaded,
                x_start, x_end, kin_x
ProblemData     tutto il problema
Segment         kind, t_start, t_end, x_start, x_end, kin, move
HoistPlan       zone, order, local_pick, finish, dep_hi, arr_lo
Solution        status, T, segments_per_hoist, raw, plans, actual_time
```

**Mossa contro stazione.** La mossa `k` porta il pezzo dalla stazione `k` alla
`k+1`. Le zone sono intervalli di **mosse**, non di stazioni. Sbagliare i due
indici e' l'errore piu' facile del progetto: `pick_time_at(k)` vuole una
STAZIONE, `loaded_leg_seconds(k)` una MOSSA.

**`Segment.kind`** vale `pick | loaded | release | empty | wait | lift_empty |
quota`.
`move` e' valorizzato per `pick`, `loaded`, `release` e `quota` — attesa e rientro a
vuoto stanno *fra* due mosse e attribuirli a una delle due sarebbe una
convenzione arbitraria. Serve a risalire dalla traiettoria alla vasca (la presa
della mossa `k` e' sulla stazione `k`, il rilascio sulla `k+1`) senza indovinare
dalla posizione, cosa che sbaglierebbe appena due vasche stessero alla stessa
quota o la stessa vasca comparisse due volte nella ricetta — entrambi casi
ammessi.

### 4.2 Le durate: **un solo punto in cui sono definite**

E' l'invariante centrale del progetto. Tutto — modello CP-SAT, ricostruzione
delle traiettorie, pre-filtro delle zone, verificatore, simulazione, Excel —
passa da questi metodi, cosi' una modifica alla definizione di "durata" si
propaga ovunque senza disallineamenti:

```python
pick_phases(station)        # la PRESA scomposta: aggancio, sollevamento, sgocciolamento
release_phases(station)     # il RILASCIO: immersione, sgancio
pick_time_at(station)       # = somma delle fasi, non un calcolo parallelo
release_time_at(station)    # idem
horizontal_loaded_seconds(k)
loaded_leg_seconds(k)       # presa(k) + traslazione + rilascio(k+1)
tratte_rientro(data, a, b)  # il rientro a vuoto: DA DOVE A DOVE, e quanto dura
empty_leg_seconds(a, b)     # = somma delle durate delle sue tratte
serve_alto(a, b)            # se quel rientro deve passare alto
horizontal_empty_seconds(x, y)  # la singola tratta orizzontale
bath_extra_seconds(station)
slot_occupancy_seconds(station, bath)
approach_position(station)  # dove sta il carroponte PRIMA della presa
corsa_verticale(station)    # di quanto scende il gancio sotto la quota di trasporto
quota_di_riposo(station)    # a che quota riposa il telaio
```

`pick_time_at` **somma le fasi** invece di ricalcolare: al modello serve solo il
totale, alla simulazione serve sapere dove sta il gancio istante per istante, e
derivando l'uno dall'altre i due usi non possono divergere. `tratte_rientro` fa
la stessa cosa per il rientro a vuoto, e ne discendono tutte e tre le cose che
se ne devono sapere: quanto dura, che aspetto ha, dove passa e quando (§5.3).

**`approach_position` contro `station_position`.** Il punto di APPROCCIO e' dove
il carroponte si trova prima di cominciare la presa e dopo aver finito il
rilascio; la stazione e' dove sta il pezzo. Coincidono sempre, tranne sulle due
tappe servite da una zona di cambio quota (§4.5). Per le distanze fra tratte del
giro — durata delle mosse, rientri a vuoto, finestre di non collisione — si usa
**sempre** il punto di approccio.

### 4.3 Il tempo in bagno — la definizione che e' stata sbagliata

Il modello maneggia due istanti: la fine del rilascio e l'inizio della presa
successiva. Il pezzo pero' e' immerso anche **prima** e **dopo**, durante i
tempi morti:

```text
   immersione   sgancio    il gancio se ne va e torna    aggancio  emersione
──────────────┬──────────┬───────── ... ─────────────────┬─────────┬──────────
              └──────────── il pezzo e' in bagno ──────────────────┘
```

`bath_extra_seconds(station)` = `disengage_time + engage_time`, e

```text
bagno = (istante del prelievo − istante in cui il rilascio finisce) + bath_extra
```

**I limiti di processo `dwell_min`/`dwell_max` valgono sul BAGNO**, non
sull'intervallo fra i movimenti. Per un periodo non e' stato cosi', e su una
linea reale sei vasche su dieci sforavano il massimo mentre il file diceva
`VERIFICA SUPERATA` — perche' il verificatore condivideva la definizione del
modello. Un controllore che misura la stessa cosa del controllato non controlla
niente.

Nel CP-SAT il vincolo si sposta di una costante nota in anticipo, non cambia
forma:

```python
extra = T_(data.bath_extra_seconds(station))
dwell_min = max(0, T_(spec.dwell_min) - extra)
dwell_max = T_(spec.dwell_max) - extra
```

### 4.4 Movimentazione verticale, e le posizioni di svincolo

Presa e rilascio **non contengono mai** corse a vuoto del gancio: quelle
avvengono fra due mosse, e le paga il rientro.

**Il gancio basso e' una proprieta' della VASCA** (`Tank.gancio_basso`, default
`True`), non della linea. Una vasca a `False` e' un OSTACOLO: sopra di lei il
gancio calato non passa e non cambia quota. `serve_alto(a, b)` decide se un
rientro deve passare alto, e risponde di si' in tre casi — si parte da un
ostacolo, si arriva su un ostacolo, o ne cade uno fra i due punti di approccio.

- Se **no**: il rientro e' una sola tratta bassa e non paga niente.
- Se **si'**: `empty_leg_seconds(a, b)` diventa cinque tratte:

```text
bassa(vasca_a → svincolo_a) → salita → alta(svincolo_a → svincolo_b)
  → discesa → bassa(svincolo_b → vasca_b)
```

`Tank.svincolo_pos` / `svincolo_neg` sono quote **assolute** e `__post_init__`
verifica che cadano fra la vasca e quella accanto. E' quel vincolo a garantire
che il tratto percorso col gancio basso non scavalchi un'altra vasca: senza,
servirebbe un controllo di percorso a ogni spostamento.

`svincolo_verso(station, verso_pos)` sceglie lo svincolo **dalla parte in cui si
va**. La scelta e' quindi determinata dalla geometria e non e' una decisione del
solutore — ed e' questo che tiene le durate costanti e note prima di risolvere.
Se una vasca non dichiara svincoli, li' il gancio sale e scende dov'e'.

> Se da una parte lo svincolo manca si esce dall'altra, e allora **il rientro
> torna indietro prima di ripartire**. Il percorso non e' monotono, e dedurre da
> dove passa guardando solo i due estremi e' sbagliato: e' per questo che
> `tratte_rientro` restituisce le tratte una per una.

**La trappola del flag per vasca.** Quando era un parametro della linea, o
*tutti* i rientri avevano le corse verticali o *nessuno*. Adesso convivono: due
rientri fra le stesse due zone possono avere forme diverse. Il vincolo di non
collisione legge le tratte da `tratte_rientro` e si adegua da solo — **purche'
nessuno ricalcoli la forma del rientro da un'altra parte**. Se ti trovi a
scrivere un secondo posto che decide se un rientro passa alto, fermati.

Gli svincoli si dichiarano **per tutte le vasche o per nessuna** (almeno uno
per vasca): qualunque vasca puo' essere il capo di un rientro che deve passare
alto. Un ostacolo **agli estremi** della linea viene rifiutato: li' non c'e'
niente da scavalcare, e quello che serve e' una zona di cambio quota (§4.5).

### 4.5 Le zone di cambio quota

`ZonaCambioQuota` descrive un punto della rotaia in cui il carroponte cambia
quota, per gli impianti in cui non puo' farlo sopra il carico e sopra lo
scarico. Ce ne possono essere due, una per estremo:
`ProblemData.cambio_quota_carico` e `cambio_quota_scarico`.

**La scala verticale e' dichiarata dal basso**, e non e' quella interna: qui `0`
e' la quota piu' bassa del carroponte e `corsa_totale` la cima, mentre nel
modello la quota di trasporto vale `0` e si scende in negativo. La conversione
sta tutta in `ZonaCambioQuota.quota_interna()` e nelle proprieta' `z_basso`,
`z_int1`, `z_int2`: chi compila l'impianto misura da terra, non dalla trave.

Il giro verso il carico e' sale-a-int1 → trasla → aggancia e solleva a int2 →
torna → sale in cima, e verso lo scarico e' lo stesso a rovescio. **Sta tutto
dentro `pick_phases` / `release_phases`**, traslazioni comprese, ed e' per
questo che serve `LiftPhase.x_start` / `x_end` / `kin_x`: una fase puo' non
essere solo verticale.

Ne discendono tre conseguenze, tutte da tenere presenti:

1. `approach_position` di quelle due tappe e' il punto di cambio quota. Il
   tratto col pezzo comincia (o finisce) li'.
2. **Durante la presa il carroponte NON e' fermo.** Vedi §5.3, che e' il posto
   dove questa cosa fa danno.
3. La presa non e' piu' un tratto solo: `_segmenti_fasi` la spezza in soste
   (`pick` / `release`) e traslazioni (`quota`).

La posizione dichiarata deve cadere **fra la stazione servita e quella accanto**,
e `__post_init__` lo verifica. Porta due garanzie, non una: il carroponte non
scavalca nessun'altra stazione per andarci, e il vai-e-torna dentro la presa si
allontana dal resto della linea — quindi non lo avvicina a nessun confine di
zona piu' di quanto gia' non lo sia il punto di cambio quota.

La corsa verticale della vasca servita deve essere `0`: li' la corsa la
definisce la zona (`corsa_telaio = intermediate2 - intermediate1`), e dichiararla
due volte vorrebbe dire che uno dei due valori viene ignorato in silenzio.

---

## 5. Il modello CP-SAT (`solve`, in `model.py`)

### 5.1 Variabili

| variabile | significato |
| --- | --- |
| `Tv` | il takt time, in tick, in `[takt_min, takt_max]` |
| `actual_time[k]` | istante assoluto del prelievo della mossa `k` (catena del pezzo) |
| `local_pick[k]` | la **fase** dello stesso prelievo dentro `[0, T)` |
| `finish[k]` | `local_pick[k] + loaded_leg` |
| `dep_hi`, `arr_lo` | quando il carroponte lascia il confine alto e torna a quello basso |

Il legame `local_pick[k] = actual_time[k] − m·Tv` e' realizzato con una
`AddExactlyOne` su letterali, uno per traslazione possibile: e' la parte piu'
delicata del modello, e il controllo 5 di `verify.py` esiste apposta per
validarla.

### 5.2 Vincoli, in ordine

1. **Catena del pezzo** — dwell fra `dwell_min − extra` e `dwell_max − extra`.
2. **Capienza** — `occupancy[station] <= capacity · Tv`. `capacity` e' una
   costante intera e `Tv` una variabile: il prodotto resta **lineare**.
3. **Circuito del carroponte** — un giro che parte e torna a `zone.lo`, con i
   trasferimenti a vuoto che devono arrivare in tempo.
4. **Non collisione** — vedi sotto.

### 5.3 La fascia di esclusione — il vincolo difficile

La condizione fisica e' `a(t) + c(t) >= D` con `D = hoist_length +
safety_distance`, e **non e' esprimibile in CP-SAT**. Si copre con una serie di
verifiche a distanza crescente dal confine, passo `clearance_step_mm`: la prima
a `δ`, la seconda a `2δ`, e cosi' via. Ne segue che

- la distanza **garantita** resta `D` qualunque valore si metta;
- il modello puo' arrivare a pretendere `D + δ`, perche' fra una verifica e
  l'altra sta dal lato sicuro.

Infittire il passo puo' solo far accettare soluzioni buone che prima venivano
scartate, mai accettarne di pericolose. Costa un modello piu' grande.

`near_boundary(zd, x_b, radius)` restituisce gli intervalli in cui un
carroponte puo' trovarsi entro `radius` dal confine. Il giro di un periodo viene
scomposto in **tratte elementari**, ciascuna di due specie sole:

| specie | com'e' fatta | come si tratta |
| --- | --- | --- |
| `fermo(t0, t1, a, b)` | il carroponte resta dentro l'intervallo di rotaia `[a,b]` | se `[a,b]` tocca la fascia, ci sta dentro tutto il tempo |
| `traslazione(t0, t1, xa, xb)` | va da `xa` a `xb` senza inversioni | distanza monotona: bastano i due estremi, piu' il margine `escape_ticks` |

Le tratte non si stimano: **vengono dalle stesse funzioni che le disegnano**.
Presa e rilascio da `pick_phases` / `release_phases` (le fasi ferme consecutive
sullo stesso punto si accorpano, cosi' su una linea normale ne esce una finestra
sola, com'era prima); il rientro a vuoto da `tratte_rientro`, gli stessi tratti
che `_segmenti_rientro` trasforma in `Segment`. Il vincolo protegge quindi il
percorso vero, corse verticali e vai-e-torna compresi.

> **Il carroponte che sale o scende col gancio e' FERMO, e quello che sembra
> fermo puo' non esserlo.** Se il modello sbaglia una delle due cose, lascia
> entrare il vicino mentre l'altro e' ancora li'.

Questo errore e' stato commesso **due volte**: la prima con l'introduzione di
`pick_time`/`release_time`, la seconda quando le corse a vuoto sono state
spostate nel rientro senza riestendere le finestre. Il secondo caso dava
**separazione zero** — due carroponti nello stesso punto con stato `OPTIMAL`.

Per un periodo la seconda e' stata tappata con un parametro `fermo`, che sommava
in blocco il tempo verticale a tutti e due gli estremi del blocco. Era sicuro ma
grossolano, e soprattutto **non copriva il rientro che torna indietro** (§4.4):
li' gli estremi non limitano piu' la distanza, e il buco restava. Adesso non
c'e' piu' nessuna stima — ogni tratta e' trattata per quello che e'.

**Se aggiungi una fase alla presa, al rilascio o al rientro, non c'e' niente da
aggiornare qui**: basta che la fase dichiari le sue posizioni. E' il punto di
tutta la struttura.

---

## 6. Dalla soluzione alle traiettorie

`_build_zone_trajectory(data, zone, order, local_pick, dep_hi, arr_lo, T,
incoerenze)` produce i `Segment` di **una** zona.

Il parametro `incoerenze` decide il comportamento davanti a valori impossibili:

- `None` → solleva `ValueError`. E' il caso del solutore, dove un valore
  incoerente e' un bug del modello.
- una lista → il problema viene **descritto li' dentro** e la traiettoria si
  disegna comunque. E' il caso del disegno manuale: l'utente compone come
  vuole, anche cose impossibili, e vuole *vederle* invece di essere bloccato.

`_segmenti_rientro` emette i cinque tratti del rientro **uno per uno** e non
riassunti in uno: durante il giro il carroponte si spinge fino allo svincolo,
che sta *oltre* la vasca, ed e' li' che puo' incontrare il vicino. I tratti li
detta `tratte_rientro`, la stessa funzione che li detta al vincolo di non
collisione.

`_segmenti_fasi` fa la cosa analoga per presa e rilascio. Di norma ne esce un
tratto solo (`pick` o `release`), identico a prima; se le fasi contengono una
traslazione — cioe' con una zona di cambio quota — le soste e le traslazioni
escono separate, e le seconde hanno `kind == "quota"`. Un tratto unico
nasconderebbe un movimento vero, e chi campiona le posizioni lo crederebbe fermo.

### 6.1 I gradi di liberta', e la trappola del modulo

Un ciclogramma ha **quattro** gradi di liberta' reali: takt time, tempo in
vasca di ogni tappa, assegnazione delle mosse, e la **sosta** di ogni
carroponte dove ha consegnato, prima del rientro a vuoto. Tutto il resto e'
conseguenza.

La sosta e' arrivata per ultima e per necessita': `dep_hi` era gia' una
variabile libera del solutore — il carroponte poteva sostare sul confine alto —
ma quel valore non veniva salvato, e la ricostruzione lo rifaceva con una
convenzione. Su 50 soluzioni verificate pulite, riaperte come fa il programma,
**14 collidevano**, una con i due carri sovrapposti (0 mm invece di 1200), dopo
una sosta di 374 s che il file non registrava. Salvando le soste: 0 su 54.

`build_solution` accetta due parametrizzazioni equivalenti:

- `local_pick` (le fasi) → la catena `actual_time` viene dedotta;
- `actual_time` (i tempi assoluti) → le fasi ne discendono.

E' questo che rende possibile salvare un ciclogramma in poche colonne di Excel
e ricostruirlo identico. **Attenzione a `_fase_nel_periodo`**:

```python
resto = istante % T
return 0.0 if T - resto <= data.eps_seconds else resto
```

Il resto di un multiplo esatto di `T` vale zero, e un capello meno vale quasi
`T`: fra i due c'e' un salto di **un periodo intero**. La catena si ricostruisce
sommando le permanenze in virgola mobile, quindi un istante che dovrebbe cadere
su `2T` ci cade appena sotto — e il carroponte comincia il giro un periodo dopo,
senza piu' arrivare in tempo da nessuna parte. Sintomo: un file appena calcolato
e' pulito, lo stesso file riaperto e' pieno di attese lunghe un takt.

---

## 7. `verify.py` — il verificatore indipendente, 1043 righe

Ricontrolla una soluzione **in Python puro**, senza CP-SAT, campionando le
posizioni reali. Non solleva mai eccezioni su una violazione — restituisce un
`VerificationReport` con le `Violation` divise per gravita' (`error`,
`warning`, `info`). Una violazione e' una decisione di modellazione da prendere,
non un crash.

I controlli, in ordine: strutturali → layout → coerenza per carroponte →
copertura delle mosse → fase → permanenze → trasferimenti → **collisioni** →
capienza.

**Il campionamento e' rigoroso.** L'insieme dei campioni e' `{0, T} ∪ {tutti gli
spigoli cinematici modulo T} ∪ {griglia di passo dt}`, e l'errore e' limitato
analiticamente (§3). `sampling_error_bound` finisce nel report ed e' tipicamente
~0,02 mm.

Il verificatore controlla una condizione **piu' stretta** di quella imposta dal
modello: ingombro pieno, ovunque, contro mezzo ingombro convertito in tempo alla
sola stazione di confine. Per questo un `warning` di layout non e'
necessariamente un difetto.

Dove puo', misura **per una via diversa** dal modello. `_move_of_loaded_segment`
riconosce una mossa dalla geometria degli estremi e non da `Segment.move`, cosi'
un `move` sbagliato non si autoconferma; `_durata_traslazione_di_quota` confronta
un tratto di cambio quota con la FASE che dovrebbe averlo generato, non con la
cinematica scritta dentro il segmento — che e' proprio uno dei dati da
verificare.

**Regola d'oro**: se cambi una definizione in `model.py`, il verificatore deve
essere aggiornato *pensando*, non copiando. Il valore di questo modulo sta
tutto nel misurare le cose per una via diversa.

---

## 8. `excel_io.py` — 1748 righe

Un file di **ingresso** ha i fogli `Istruzioni`, `Vasche`, `Percorso`,
`Parametri`, `Zone` (facoltativo), `CambioQuota` (facoltativo), `Ciclogramma`
(facoltativo).

Il file dei **risultati** e' due cose insieme, in quest'ordine:

```text
Input | Istruzioni Vasche Percorso Parametri Zone CambioQuota Ciclogramma
Output | Riepilogo Movimenti TempiVerticali FlussoPezzo Verifica
```

`Input` e `Output` sono cartelli con la linguetta colorata. Il file si apre sul
`Riepilogo` (`wb.active`), non sul primo foglio. **I fogli si creano
nell'ordine in cui devono comparire**: riordinarli dopo vorrebbe dire mettere le
mani in `wb._sheets`, che e' roba di openpyxl e puo' cambiare.

Nella lettura, gli errori si **raccolgono tutti** (`_Errori`) e si presentano
insieme con foglio e cella. Chi compila a mano sbaglia in piu' punti, e farlo
tornare indietro un errore per volta e' crudele.

`_NOMI_IN_METRI` e `_NOMI_SOSTITUITI` producono messaggi di migrazione espliciti
per i file scritti per versioni precedenti.

Due punti che si sono gia' rivelati fragili:

- **Le cifre salvate.** Le permanenze finiscono in una catena che le risomma e
  decide, con un arrotondamento all'insu', quanti periodi interi il pezzo resta
  in vasca. Tagliare a tre decimali e' fragile: si salva a nove.
- **Il foglio `TempiVerticali`** esiste perche' una presa da 26 s su una corsa
  da un metro e mezzo sembra un errore di calcolo, finche' non si vede che dieci
  di quei secondi sono lo sgocciolamento dichiarato.

---

## 9. `interfaccia.py` — 2070 righe

La classe `Applicazione(tk.Tk)` e' tutta la finestra. Lo stato utile:

```python
T_corrente, permanenze, assegnazione, n_carroponti   # i gradi di liberta'
attese              # dove ogni carro sosta; None = decide la regola
soluzione, dati, report, incoerenze
vista               # "ciclogramma" | "pettine"
modifica_aperta     # se la scheda Ciclogramma e' aperta
verifica_viva       # se il verdetto si aggiorna da solo
_lavoro_in_corso    # il solutore sta girando
```

**`_ricomponi()` e' il funnel di ogni modifica.** Cambio del takt, dei tempi in
vasca, dell'assegnazione, trascinamento sul grafico: tutto passa di li'. Ne
segue che una riga sola — la guardia su `_lavoro_in_corso` — impedisce a
qualunque modifica di infilarsi mentre il solutore lavora, anche da una strada
che oggi non esiste. Se aggiungi un comando che modifica il ciclogramma, fallo
passare da `_ricomponi`.

**`_mostra_ciclogramma()` e' il funnel di ogni ridisegno**, ed e' li' che la
finestra della simulazione viene aggiornata.

Il lavoro pesante gira in un thread con una `queue.Queue`: `_avvia_lavoro`
mette, `_controlla_coda` ritira con `after(80)`. Nel thread **non si tocca
nessun widget**.

### 9.1 Le due viste, e perche' si modifica solo su una

| vista | quando | cosa |
| --- | --- | --- |
| ciclogramma | `Calcola auto`, `Fine modifica` | traiettorie dei carroponti, 2 cicli |
| modifica | `Calcola man`, `Modifica` | percorso dei pezzi in **grigio** + giro dei carroponti sopra |

Si modifica sempre sulla seconda, e non e' una preferenza: nel ciclogramma nudo
si disegnano solo le traiettorie, quindi un trasporto **non assegnato non
compare affatto** — pur restando cliccabile, perche' `_tratti_trasporto()` lo
calcola comunque. Invisibile e cliccabile insieme e' la combinazione peggiore.

### 9.2 Clic e trascinamento

Due raggi diversi, e non per caso:

- il **clic** vale su tutto il tratto disegnato (12 px dalla polilinea
  campionata): assegnare una mossa non ha a che fare con un estremo
  particolare;
- il **trascinamento** prende solo dal punto di prelievo (18 px), perche' li'
  l'estremo conta davvero — e' da quel punto che la sosta si allunga.

`_su_pressione` distingue i due memorizzando `mossa` (maniglia) e `mossa_clic`
(tratto sotto il puntatore); `_su_rilascio` decide in base allo spostamento in
**pixel**: in secondi la soglia dipenderebbe dall'ingrandimento.

### 9.3 Zoom

`_zoom_utente` dice se l'inquadratura l'ha scelta l'utente. Se si', va
conservata attraverso i ridisegni: sarebbe inutile ingrandire per lavorare su un
dettaglio se il primo ritocco riportasse la vista al punto di partenza. Si
riparte da capo solo quando cambia il disegno stesso (`_reimposta_grafico`).

> C'e' stato un mirino verticale che seguiva il puntatore, ed e' stato tolto:
> per essere fluido usava il blitting, e ogni ridisegno altrui lasciava a
> schermo pezzi di grafico vecchio. **Un riferimento che ogni tanto mente e'
> peggio di nessun riferimento.**

---

## 10. `simulazione.py` — 1388 righe

Diviso in due, apposta:

- **`Simulazione`** — dato un istante dice dove sta ogni carroponte e ogni
  pezzo. Non importa tkinter: si prova senza finestre.
  `_gruppo_verticale` dice a quale presa o rilascio appartiene un tratto e
  **quando quel gruppo e' cominciato**: con una zona di cambio quota la presa e'
  spezzata in piu' tratti, e il `t_start` del singolo non basta piu' a sapere a
  che punto delle fasi si e' arrivati.
- **`FinestraSimulazione`** — la finestra che la anima.

Non calcola niente di nuovo: legge `segments_per_hoist` (i carroponti, con wrap
modulo T) e `actual_time` (i pezzi). **Il controllo che conta e' incrociato**:
ogni pezzo appeso deve stare *esattamente* dove sta il gancio di un carroponte
che lo tiene. Su un ciclogramma coerente lo scarto misurato e' 3·10⁻¹¹ mm.

Tre cose che il disegno fa e che vanno capite prima di toccarlo:

**Le quote sono rimappate.** Non si disegnano i millimetri ma *a che punto e'
arrivata la discesa*, da 0 a 1, su una profondita' unica. Cosi' i telai immersi
stanno tutti alla stessa altezza. Il rimappaggio vale identico per il gancio e
per il telaio, altrimenti il pezzo si stacca dal bilancino — difetto del solo
disegno, invisibile ai controlli sulle quote vere, e per questo c'e' un test
che lo verifica **sulle coordinate disegnate**.

L'ORLO della vasca non sta poco sotto la quota di trasporto: sta poco sopra la
quota del telaio immerso, cosi' il pezzo galleggia a filo. Il fondo invece resta
dov'e'. Con l'orlo in alto le vasche erano scatoloni alti due terzi del disegno
con dentro un telaio piccolo in fondo, e le proporzioni non dicevano piu' niente.

Il denominatore del rimappaggio e' `corsa_verticale(stazione)`, non
`lift_height_at`: su una zona di cambio quota il gancio scende fino in fondo
alla corsa del carroponte, e le quote in gioco diventano quattro (fondo,
intermediate1, intermediate2, cima) invece di due. Con la corsa giusta al
denominatore il disegno regge senza altri casi particolari — e le due stazioni
si disegnano come POSTAZIONI e non come vasche, perche' la loro
`Tank.lift_height` vale zero.

**Anche la scena fissa passa dal rimappaggio.** Il piano di carico e quello di
scarico stanno alla quota a cui il telaio ci viene posato — `intermediate1`
riportato sul disegno da `_quota_disegnata`, meno l'altezza del simbolo del
telaio perche' ci si appoggi sopra invece di attraversarlo. Lasciati alla quota
di trasporto sembravano inghiottire il telaio, con le funi del carroponte che ci
passavano dentro. E' il motivo per cui `_quota_disegnata` e' una funzione a se'
e non il corpo di `_quota`: se la scena fissa e le cose che si muovono usassero
due formule, il telaio finirebbe accanto al suo appoggio invece che sopra.

**Le corsie.** Piu' pezzi nella stessa vasca si disegnavano nello stesso punto e
sembravano uno solo. `_corsia(pezzo, stazione)` li affianca. I posti li detta il
**ciclogramma** (quanto tempo un pezzo occupa la vasca, diviso il takt), non la
capienza dichiarata: con tre posti e un pezzo solo lo si disegnerebbe fuori
centro, e con un ciclogramma che sfora la capienza i pezzi di troppo
sparirebbero uno sotto l'altro — nascondendo proprio l'errore da vedere.

Per il CARROPONTE la corsia segue una regola sola: **sta sul posto del pezzo
solo mentre lo tiene**, e in tutto il resto del giro si sposta di lato con
continuita', da dove l'ha lasciato l'ultimo pezzo a dove lo vuole il prossimo.
Gli intervalli in cui e' vincolato sono precalcolati in `_Traiettoria.impegni`,
ricavati dalle fasi con `loaded=True`.

Lo spostamento non e' spalmato sul tempo, ma sul tempo in cui il carroponte
**gia' si muove** — `_Traiettoria.mobile_t/mobile_c`, il cumulato che le attese
non fanno crescere. Distribuendolo sull'intervallo intero, un carrello fermo
sopra una vasca per un minuto scivolava di lato per tutto il minuto: continuo
sui numeri, e peggio dello scatto che sostituiva.

> Legandola al TRATTO invece che al telaio — com'era prima — fuori dalle mosse
> la corsia valeva zero, cioe' il centro della vasca, e il carrello **scattava**
> di lato: appena finito un rilascio, e di nuovo passando da un pezzo al
> successivo nella stessa vasca, dove fra i due non c'e' nemmeno un istante di
> attesa in cui spostarsi. Su una vasca a un posto solo era invisibile, perche'
> li' il centro E' il posto: e' un difetto che si vede solo dove ci sono piu'
> posti, ed e' per questo che il test di continuita' sta nel caso a due pezzi.

**Le postazioni SENZA CORSA sono il caso che rompe tutto.** Sul carico e sullo
scarico di quasi tutte le linee `lift_height` vale zero, e li' "il gancio e'
calato" e "il gancio e' in alto" sono **la stessa quota**. Chi teneva il conto a
stati — dopo un rilascio e' giu', dopo una salita e' su — da quel punto in poi
diceva il contrario del vero: la discesa successiva veniva disegnata come una
salita, e al primo aggancio il gancio saltava di tutta la corsa. Adesso lo stato
si ricava dalla quota vera (`quota_di_riposo`), non dal tipo di tratto.

Lo stesso vale col gancio che trasla basso: partendo da una postazione senza
corsa il gancio e' in alto e alla vasca dopo deve stare in basso, e il modello
non da' un secondo per portarcelo. Dove mettere quel dislivello lo decide
`_quote_a_vuoto`, e la regola e' una sola:

> **Mentre il carroponte TRASLA la quota non cambia.** Tutto quello che sale o
> scende avviene da fermi. E' la stessa cosa che racconta il ciclogramma — un
> tratto obliquo e' uno spostamento, un tratto piatto e' tutto il resto — e le
> due viste devono dire la stessa cosa, altrimenti chi le confronta vede due
> macchine diverse.

Il dislivello finisce quindi in una **sosta**, che nel ciclogramma e' il tratto
piatto dove l'occhio si aspetta un movimento verticale. Se attorno al rientro
non c'e' nessuna sosta si ripiega sulla traslazione, ed e' un ripiego
dichiarato: non c'e' nessun altro posto dove metterlo.

Si interpola la **frazione** di discesa, non i millimetri: due quote diverse su
corse diverse possono essere tutte e due "in fondo". E le quote agli estremi si
leggono dalle FASI (`pick_phases[0].z_start`, `release_phases[-1].z_end`), non
dalla quota di riposo del telaio: su una zona di cambio quota sono due cose
diverse — il telaio riposa a meta' corsa, il gancio ci arriva dal fondo.

> Il test da scrivere non e' "il gancio non si alza mai": andando verso una
> postazione senza corsa il telaio si prende alla quota di trasporto, e li' il
> gancio DEVE alzarsi. E' "non si alza piu' di quanto chiedano i due capi del
> rientro". Il criterio sbagliato e' rimasto in `test_simulazione.py` finche'
> non ha cominciato a bocciare il comportamento corretto.

**Il gancio resta calato** finche' il carroponte sta fermo sopra una vasca, in
tutti e due i casi in cui capita: dopo aver deposto, e aspettando di prelevare.
Non serve nessun correttivo — da quando le corse a vuoto sono state spostate nel
rientro (§4.4), `pick_phases` e `release_phases` lasciano gia' il gancio dov'e'.

> C'e' stato un `_tratti_col_gancio_giu` che serviva proprio a questo, quando le
> corse a vuoto stavano ancora dentro presa e rilascio. Spostate quelle, e'
> rimasto a fare una cosa sola: staccare il gancio di un dito dal telaio durante
> l'attesa, per far vedere che non lo teneva piu'. Era un movimento che il
> carroponte non compie, ed e' stato tolto insieme al meccanismo — 118 righe in
> meno. **Un correttivo sopravvissuto alla ragione per cui esisteva** e' una
> cosa da cercare quando si sposta una definizione: qui la ragione era sparita
> da un pezzo, e nessuno se n'era accorto perche' il test controllava che il
> meccanismo ci fosse invece di controllare che il gancio stesse giu'.

Timer: un `after(PASSO_MS)` che si richiama. `_passo` e `_continua_raffica`
**adottano il timer in corso** invece di affiancarglisi — senza, ogni chiamata
esterna avvia una seconda catena e le catene si moltiplicano. Anche
`_Suggerimento` ha un `after`, e lo annulla sia all'uscita dal pulsante sia
alla distruzione del widget: un timer che scatta su una finestra gia' chiusa e'
lo stesso `invalid command name` di sempre.

**Le icone dei comandi sono disegnate, non scritte.** `icona_comando()` compone
triangoli e barre dentro una `tk.PhotoImage`, che nasce trasparente e quindi si
adatta a qualunque tema. I simboli media di Unicode (U+23F8 e vicini) sarebbero
stati una riga di codice, ma si vedono solo dove il sistema trova un font che li
contiene: dove non lo trova compare un quadratino, che e' peggio della parola
che sostituivano. Chi usa le immagini deve **tenerne un riferimento** (qui
`self.icone`): Tk non lo fa, e un'immagine raccolta dal garbage collector
lascia il pulsante vuoto.

---

## 11. I test — 467 asserzioni, cinque suite

Nessun pytest: ogni file si lancia da solo, stampa cosa ha provato e restituisce
un codice d'uscita.

| file | asserzioni | richiede | domanda a cui risponde |
| --- | ---: | --- | --- |
| `test/test_verify.py` | 119 | — | il verificatore trova davvero quello che deve? |
| `test/test_excel_io.py` | 97 | — | un file compilato male viene respinto con un messaggio utile? |
| `test/test_simulazione.py` | 78 | — | la simulazione mostra il ciclogramma che c'e'? |
| `test/test_model.py` | 61 | OR-Tools | il modello produce soluzioni fisicamente valide? |
| `test/test_interfaccia.py` | 112 | OR-Tools + grafica | l'interfaccia si comporta come deve? |

> `test_model.py` risolve davvero, con limiti di tempo dell'ordine del minuto.
> Su una macchina occupata un caso puo' scadere e restituire `UNKNOWN`: e'
> l'unico modo in cui questa suite fallisce senza che ci sia un difetto, e si
> riconosce perche' il messaggio dice `UNKNOWN` invece di `INFEASIBLE` o di una
> violazione. Rilanciarlo da solo.

Tre principi che vale la pena mantenere:

1. **Per ogni controllo, un caso che DEVE farlo scattare.** In `test_verify.py`
   un solo caso e' corretto, gli altri sono rotti di proposito.
2. **I test dell'interfaccia pilotano la finestra vera**, con `update()` invece
   di `mainloop()`. E' l'unico modo per accorgersi che un pulsante e' rimasto
   disabilitato o che il lavoro in background non consegna mai.
3. **Le grandezze di prova sono diverse fra loro apposta.** Le vasche di
   `test_simulazione.py` hanno corse verticali diverse: con corse uguali,
   prendere la corsa della vasca sbagliata darebbe comunque il risultato giusto.

---

## 12. Trappole note

Queste sono costate tempo. Valgono piu' di qualunque descrizione di funzione.

**Il carroponte fermo che il modello crede in moto — e viceversa.** §5.3.
Commesso due volte, in tutte e due le direzioni: prima le fasi verticali
credute movimento, poi il rientro che torna indietro e la presa che con una
zona di cambio quota non e' piu' una sosta. Sintomo: `OPTIMAL` con separazione
sotto il minimo. La difesa strutturale e' che le finestre del vincolo vengano
dalle stesse funzioni che disegnano il giro, mai da una copia.

**Il modulo su un multiplo esatto del takt.** §6.1. Sintomo: un file riaperto
diventa incoerente, con attese lunghe un periodo.

**Il verificatore che condivide una definizione col modello.** §4.3. Sintomo:
`VERIFICA SUPERATA` su una linea fuori tolleranza.

**Un controllo scritto per rifiutare l'input sbagliato che rifiuta anche quello
giusto.** `plot_cyclogram` accettava solo `OPTIMAL`/`FEASIBLE`, ma una
soluzione ritoccata a mano ha stato `MANUALE`: il grafico si svuotava alla prima
modifica, proprio nella funzione che serve a modificare guardando il grafico. Le
tabelle intanto si aggiornavano, quindi nessun test se ne accorgeva. Oggi il
filtro e' su `_STATI_SENZA_SOLUZIONE`.

**Timer che si moltiplicano.** §10.

**Segmenti degeneri di durata nulla** quando due mosse consecutive condividono
la stazione: sommati allo scarto di arrotondamento si ordinano male e spezzano
la traiettoria. Non si emettono.

**`plans` disallineato con `segments_per_hoist`.** In `_assembla`, una zona
senza mosse assegnate aggiunge `[]` ai segmenti ma **salta** il piano. Con
assegnazioni parziali gli indici non corrispondono: non usare `plans[h]` per
indicizzare i segmenti.

**Un caso che passa non e' una dimostrazione.** Lo sweep di validazione del
vincolo di non collisione ha un **controllo di sensibilita'**: rifare tutto con
il vincolo disattivato e verificare che le collisioni compaiano. Se due misure
coincidono al numero, sospetta che la seconda non stia misurando niente — e'
successo, con un monkeypatch che non agganciava (`AddNoOverlap` e' un alias di
`add_no_overlap` in questa versione di OR-Tools).

> Ultimo sweep, sulle zone di cambio quota: 192 configurazioni (punto di cambio
> quota a distanze crescenti dal confine, con e senza traslazione a gancio
> basso), **0 collisioni** su 121 risolte col vincolo attivo, **51** col vincolo
> disattivato — la peggiore a separazione zero contro 1200 mm richiesti.

**`UNKNOWN` non e' `INFEASIBLE`.** `test_model.py` risolve davvero: su una
macchina occupata un caso scade e restituisce `UNKNOWN`, e il test fallisce
senza che ci sia niente di rotto. Prima di mettersi a cercare un difetto,
guardare quale delle due parole c'e' nel messaggio e rilanciare la suite da
sola.

---

## 13. Come aggiungere qualcosa

**Un parametro nuovo**: campo in `ProblemData` (in fondo, mai in mezzo:
romperebbe le costruzioni posizionali) → validazione in `__post_init__` con un
messaggio che dice cosa fare → riga in `_PARAMETRI` di `excel_io.py` → lettura →
`_righe_da_configurazione` per il ritorno → README.

**Una durata nuova**: solo in §4.2, mai duplicata altrove.

**Una fase nuova nella presa, nel rilascio o nel rientro**: si aggiunge in
`pick_phases` / `release_phases` / `tratte_rientro`, dichiarando le posizioni se
comporta uno spostamento. Durata, disegno e vincolo di non collisione la
raccolgono da soli (§5.3). Se ti trovi ad aggiornare `near_boundary` a mano,
fermati: vuol dire che la fase non ha detto dove passa.

**Un tipo di segmento nuovo**: `_STYLE` in `plotting.py` (la riga che lo disegna
va in `KeyError` altrimenti), `_STATIONARY_KINDS` o `_MOVING_KINDS` in
`verify.py`, `_FASI` in `excel_io.py` (altrimenti il foglio Movimenti stampa il
nome interno), `_fase_verticale` in `simulazione.py`.

**Un controllo nuovo nel verificatore**: e un caso in `test_verify.py` che lo
faccia scattare, altrimenti non sai se funziona.

Prima di considerare finito qualunque cambiamento:

```bash
python kinematics.py
python test/test_verify.py   python test/test_excel_io.py  python test/test_simulazione.py
python test/test_model.py    python test/test_interfaccia.py
python test/esempio.py       python interfaccia.py --autotest
```

Sull'esempio, `test/esempio.py` deve restare a **T = 110,00 s** con separazione
minima 3500 mm contro 1800 richiesti. Se cambia, o hai migliorato qualcosa e lo
sai, oppure hai rotto qualcosa e non lo sai ancora.
