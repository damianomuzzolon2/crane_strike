# Architettura del codice di CraneStrike

Documento per chi deve **mettere le mani nel codice**. Il `README.md` spiega
cosa fa il programma e come si usa; questo spiega com'e' fatto dentro, quali
invarianti regge, e dove sono le trappole — comprese quelle in cui siamo gia'
caduti, che sono la parte piu' utile.

Stato al momento della scrittura: 30 file Python (quindici moduli, quattro
strumenti, undici file di test), 33.840 righe, dieci suite di test per **quasi
novecento controlli** complessivi.

---

## 1. La mappa, e la direzione delle dipendenze

### Dove stanno i file

In radice ci sono **solo i quindici moduli** del programma, i due documenti,
`CraneStrike.bat` e `requirements.txt`. Il resto sta in `test/`, `strumenti/`,
`doc/`, `dati/`, `risorse/` e `.github/` (la CI: scrivendo `check` in un
commento di una pull request i test girano su Windows, in tre gruppi).

`risorse/` contiene il logo IMEL (`logo_imel.png`, sulla schermata di
benvenuto, sul PNG salvato e nella simulazione; lo trova
`plotting.cartella_risorse`, anche dentro l'eseguibile) e l'icona in due
formati: `icona.png`, l'originale con gli
angoli trasparenti, per Tk, e `icona.ico` per Windows e per il file `.exe`,
ricavato dal PNG con le misure da 16 a 256 px. Se l'icona cambia, l'ICO va
rigenerato dal PNG nuovo (con Pillow: tutte le misure in un solo file). `interfaccia._applica_icona` la cerca accanto al modulo o, impacchettata,
in `sys._MEIPASS`; per questo il `.spec` la dichiara in `datas`. Sulla finestra
se ne imposta **uno solo dei due** (l'ICO su Windows): impostarli entrambi,
misurato, toglie a Windows l'icona piccola e nel titolo compare quella
generica, senza nessun errore. Se si cambia
l'immagine l'ICO va rifatto a mano: il programma non lo rigenera da solo. Pillow
il programma la usa in un punto solo, per rimpicciolire bene le immagini della
schermata di benvenuto (`interfaccia._immagine_ridotta`), e non va installata a
parte: la porta matplotlib.

I moduli non sono in un package di proposito: si importano per nome
(`from model import solve`) e i programmi si avviano direttamente
(`python interfaccia.py`). Un package obbligherebbe a `python -m` e a
qualificare ogni import, e questo programma non si installa mai con `pip` —
gira dalla cartella o dall'eseguibile PyInstaller. Il prezzo e' che chi sta in
una sottocartella deve rimettersi la radice fra i percorsi di ricerca: i test
lo fanno con tre righe in testa al file, il `.spec` con `SPECPATH`.

### La documentazione riga per riga

In `doc/` c'e' una sottocartella per modulo con i documenti Word che lo
spiegano funzione per funzione — venticinque documenti che coprono tutte le
469 fra funzioni e metodi dei dieci moduli documentati — piu'
`ALBERO_DELLE_CHIAMATE.docx`. `allinea_avvio`, `programma_carri`,
`fattibilita`, `editor_linea` e `accesso` non hanno ancora un documento loro. Si
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
        |                   |
        |           allinea_avvio.py             <- ritocco dell'avvio
        |                   |
        +----------+--------+-+---------+----------+
        |          |          |         |          |
  excel_io.py manuale.py plotting.py verify.py simulazione.py
        |          |          |         |          |
  programma_carri.py          |         |          |
        |          |          |         |          |
        +----------+----+-----+---------+----------+
                        |
                    avvio.py                     <- letture della soluzione
                        |
                    model.py                     <- motore (CP-SAT)
                        |
                  kinematics.py                  <- fisica
```

Lo schema lascia fuori tre moduli che usa **solo** `interfaccia.py`:
`editor_linea.py` (sopra `excel_io`), `fattibilita.py` (sopra `model`, piu'
`excel_io` solo quando lo si lancia da solo) e `accesso.py`, che non importa
niente del progetto. E una dipendenza laterale: `simulazione.py` prende da
`plotting.py` i colori dei carroponti e il percorso del logo, cosi' le due
viste usano gli stessi.

Le dipendenze vanno **in una direzione sola** ed e' un vincolo, non un caso:

- `kinematics.py` non sa che esiste un ciclogramma. Si prova senza OR-Tools.
- `model.py` non sa che esiste un'interfaccia. Importa `ortools` **in modo
  pigro**, dentro `solve()`: le dataclass, la ricostruzione delle traiettorie e
  `build_solution` restano usabili e testabili anche senza OR-Tools installato.
  `test_verify.py` conta su questo.
- `verify.py` non importa `ortools` **mai**. E' la ragione per cui esiste: un
  verificatore che usasse lo stesso solutore non verificherebbe niente.
- `avvio.py` **legge e basta**: non importa `ortools`, non tocca la soluzione e
  non ha niente da dire sul disegno. Sta sopra `model.py` perche' usa le fasi e
  le posizioni, e sotto tutti gli altri perche' il punto di avvio si scrive in
  quattro posti -- il grafico, il foglio Riepilogo, il pannello della finestra e
  il terminale -- e deve essere lo stesso in tutti e quattro.
- `allinea_avvio.py` invece **cambia** il ciclogramma, e per questo non sta in
  `avvio.py`: usa `avvio` per sapere cosa sistemare, CP-SAT (in modo pigro,
  come `model.py`) per scegliere gli spostamenti, e `verify` per decidere se
  tenerli. Sta sopra tutti e tre, e lo chiamano solo i programmi.
- `editor_linea.py` (la finestra "Dati linea") sta fra `interfaccia.py` e
  `excel_io.py`, e importa **solo** `excel_io`. Non ha controlli suoi: le
  tabelle sono `excel_io.RigheLinea`, e "Applica" le passa a
  `excel_io.leggi_righe`, che le scrive in un libro openpyxl **in memoria** e
  lo legge con `_leggi_libro` -- lo stesso corpo di `leggi_problema`. Cosi' i
  dati inseriti a mano e quelli di un file passano per gli stessi controlli e
  danno gli stessi messaggi `[Foglio!Cella]`; le righe finiscono sul foglio a
  partire dalla 2 e senza buchi, quindi la cella di un errore e' anche la
  riga della tabella (riga del foglio - 2, e nel Percorso una colonna in meno
  per la "n"). Chi aggiunge una colonna ai fogli di ingresso la aggiunge a
  `COLONNE_*` e alla lettura, e la finestra la mostra da sola; chi aggiunge un
  parametro lo aggiunge a `_PARAMETRI`, che e' anche l'elenco delle righe della
  scheda Parametri. La finestra non conosce `Applicazione`: riceve due funzioni
  (`applica`, `salvato`), e la finestra principale decide cosa voglia dire
  applicare -- scartare il ciclogramma, segnare la linea come modificata.
- `fattibilita.py` (il pulsante `Fattibilita'`) **legge e basta**, come
  `avvio.py`: non importa `ortools` e non tocca niente. Da `ProblemData` ricava
  in pochi millisecondi dei **limiti inferiori** del takt time, dalle vasche e
  dai carroponti. E' una condizione necessaria e non sufficiente: se un limite
  supera il takt richiesto la linea e' certamente impossibile e il calcolo si
  puo' risparmiare; se non lo supera, lo dice solo il solutore.
- `accesso.py` e' la schermata di accesso, e usa solo la libreria standard.
  Nel codice non ci sono ne' password ne' nomi utente: per ogni persona c'e'
  una coppia (sale, impronta PBKDF2-HMAC-SHA256 di utente e password insieme).
  La riga da aggiungere a `UTENTI` la stampa `strumenti/genera_utente.py`; poi
  si ricompila l'eseguibile. `interfaccia.main` la chiama prima di tutto, poi
  mostra la schermata di benvenuto, poi la finestra.

Chi rompe questa direzione rompe la testabilita' del progetto.

---

## 2. Convenzioni che valgono ovunque

**Unita': millimetri e secondi.** Tutto. Posizioni, corse, velocita' (mm/s),
accelerazioni (mm/s²). Il progetto e' nato in metri ed e' stato convertito in
blocco: la cinematica e' invariante di scala (profili trapezoidali), quindi la
conversione e' stata una pura rietichettatura. Se aggiungi una grandezza,
scrivi l'unita' nel nome del campo Excel (`_mm`, `_s`, `_mm_s`).

**Tick interi per CP-SAT.** `ProblemData.time_scale` e' la risoluzione, fissa
a 100 tick al secondo: `to_ticks`/`to_seconds` convertono. Dal file Excel non
si cambia piu' (`excel_io.RISOLUZIONE_TICK_PER_S`), e un vecchio parametro
`risoluzione_tick_per_s` si legge senza errori e si ignora. La tolleranza numerica del
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
niente si scrive `0`, che e' una dichiarazione; una cella vuota no. Lo stesso
vale per velocita' e accelerazione delle quattro cinematiche, sollevamento
compreso: nel file Excel sono obbligatorie, e resta facoltativa solo la
decelerazione.

---

## 3. `kinematics.py` — la fisica, 497 righe

Tre funzioni pure, nessuno stato, e sotto di loro **un motore solo**: la corsa
spezzata in tratti ad accelerazione costante.

| funzione | cosa da |
| --- | --- |
| `travel_time(distance, kin)` | tempo minimo con profilo trapezoidale o triangolare |
| `position_profile(t, distance, kin)` | spazio percorso a `t`, **senza segno**, con `t` clampato in `[0, t_total]` |
| `profile_breakpoints(distance, kin)` | gli spigoli della curva |
| `_tratti(d, kin)` | il profilo completo, tratto per tratto — **con cache** |
| `_limiti(d, kin)` | la corsa spezzata nei pezzi a limite di velocita' costante |
| `_velocita_di_confine(limiti, kin)` | con che velocita' si attraversa ogni confine |
| `_distanza_rampe(v_cap, v_in, v_out, kin)` | la soglia fra trapezio e triangolo, per un pezzo |
| `_picco_triangolare(lung, v_in, v_out, kin)` | la velocita' di picco quando la crociera non c'e' |
| `_tratti_di_pezzo(...)` | un pezzo risolto come trapezio con entrata e uscita assegnate |

`Kinematics` porta `v_max`, `a_max`, `d_max` e `approach`. **La decelerazione
e' un numero a se'**, facoltativo: `None` significa "frena come accelera", e la
proprieta' `decel` e' l'unico punto in cui quel `None` diventa un valore. Tutto
il resto del modulo legge `decel`, mai `a_max`, per la frenata — cosi' il caso
simmetrico non e' un ramo di codice parallelo che prima o poi diverge.

Con rampe diverse cadono due semplificazioni che il modulo faceva:

- le due rampe hanno durate diverse, quindi non se ne conta una e la si
  raddoppia;
- il vertice del profilo triangolare **non sta piu' a meta' durata**, ma dove
  finisce l'accelerazione. `profile_breakpoints` lo restituisce li': prenderlo
  a `t_total/2` lascerebbe il vero spigolo fra due campioni e farebbe decadere
  in silenzio la garanzia sull'errore descritta sotto.

### La zona di avvicinamento

`Approach(speed, distance, at_end)` e' il **limite di velocita' in funzione
della posizione** che il sollevamento ha vicino al punto di presa o deposito:
`distance` millimetri percorsi a `speed`, al capo BASSO della corsa. `at_end`
dice a quale estremo cade — in fondo scendendo a posare, in testa salendo a
prelevare — ed e' una proprieta' del **movimento**, non del carroponte: la
mette `model.ProblemData.kin_avvicinamento`, che sa in che verso va il gancio.
Si costruisce solo attraverso `Kinematics.avvicinandosi(v, d, scendendo=...)`.

Con una zona di avvicinamento il profilo non e' piu' *un* trapezio ma una
successione di trapezi, saldati in un punto che **non e' un arresto**. Per non
avere due motori di calcolo destinati a divergere, il modulo ne ha uno solo e
il caso di sempre e' quel motore con un pezzo soltanto — con formule identiche,
numero per numero, a quelle di prima.

L'algoritmo sta in `_velocita_di_confine`: tre passate (limite del confine,
accelerazione in avanti, frenata all'indietro) che fissano la velocita' di
attraversamento di ogni confine. La terza e' quella che **assorbe tutti i casi
degeneri** — zona piu' corta del proprio spazio di frenata, corsa piu' corta
della zona — senza un solo ramo dedicato.

`_tratti` e' decorata con `lru_cache`: il verificatore campiona la stessa
tratta centinaia di volte, e le distanze di una linea sono poche e sempre le
stesse. E' per questo che `Kinematics` e `Approach` **devono** restare frozen:
sono chiavi di cache.

Due dettagli che il resto del progetto sfrutta:

- `position_profile` **clampa da sola** il tempo fuori intervallo. E' quello
  che permette al campionatore di `verify.py` e alla simulazione di assorbire
  senza logica aggiuntiva le micro-sovrapposizioni fra segmenti lasciate dagli
  arrotondamenti sui tick.
- `profile_breakpoints` esiste per un motivo preciso: fra due spigoli la
  posizione e' un polinomio di grado ≤ 2, quindi anche la **differenza** fra due
  traiettorie lo e'. Campionando tutti gli spigoli piu' una griglia di passo
  `dt`, l'errore sul minimo cercato e' limitato da `(a_i + a_j)/2 · (dt/2)²`.
  E' cosi' che `verify.py` da' un limite **rigoroso** e non una speranza. Gli
  `a_i` sono il massimo fra accelerazione e decelerazione (`Trajectory.
  max_accel`): serve la curvatura massima del profilo, e su un carroponte che
  frena piu' forte di quanto accelera quella sta nella rampa di frenata.

---

## 4. `model.py` — strutture dati, 5631 righe

### 4.1 Le dataclass

```text
Tank            id, position, capacity, lift_height, drain_time,
                svincolo_pos, svincolo_neg, gancio_basso,
                larghezza, altezza, cover_presente
StationSpec     tank_id, dwell_min, dwell_max, dwell_nominal,
                peso_sotto, peso_sopra
                                                    (una tappa del percorso;
                                                    si dichiara come teorico
                                                    +/- due delta, vedi
                                                    StationSpec.da_teorico)
HoistZone       lo, hi                               (intervallo di MOSSE)
Portata         vasca_min, vasca_max                 (fin dove arriva un
                                                    carroponte; foglio Zone)
ZonaCambioQuota position, intermediate1, intermediate2, corsa_totale
LiftPhase       name, duration, z_start, z_end, kin, loaded,
                x_start, x_end, kin_x
ProblemData     tutto il problema
Segment         kind, t_start, t_end, x_start, x_end, kin, move,
                sale, kin_z
SostaIntermedia stazione, secondi                    (dove il carro si ferma
                                                    durante un rientro, e per
                                                    quanto)
HoistPlan       zone, order, local_pick, finish, dep_hi, arr_lo, attese,
                soste_intermedie, passaggi
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
**Dati di solo disegno.** `Tank.larghezza`, `Tank.altezza`,
`ProblemData.larghezza_pezzo` e `ProblemData.altezza_pezzo` sono gli unici campi
che **nessun calcolo legge**: li usa solo `simulazione.py`, per disegnare in
proporzione invece che con misure convenzionali. Sono facoltativi (`None` =
non dichiarato) e `__post_init__` rifiuta solo lo zero e il negativo. Se aggiungi
altri dati di questo tipo, tienili facoltativi e fuori da `model`/`verify`:
il giorno in cui un disegno diventa un vincolo, due moduli che non c'entrano
niente cominciano a dipendere da un dato che nessuno ha misurato.
`Tank.cover_presente` e' dello stesso genere ma per un altro lettore: dice se
la vasca ha un coperchio, e lo usa solo `programma_carri.py` per il programma
dei carri. Il modello e il verificatore non lo leggono.

**Pesi dello scarto.** `StationSpec.peso_sotto` / `peso_sopra` dicono quanto
costa, per ogni secondo, allontanarsi dal tempo teorico in meno o in piu'. Li
usa solo l'obiettivo (§5.2); a schermo e nel Riepilogo si mostra invece lo
scarto **senza pesi** (`scarto_totale`), in secondi, che si legge senza sapere
quali pesi ha la ricetta. `__post_init__` controlla, tappa per tappa, che i
pesi non siano negativi e che `dwell_min` stia fra 0 e `dwell_max`.

`sale` e' valorizzato solo per `lift_empty`: `True` se il gancio scarico sale
sullo svincolo, `False` se scende. Lo scrive `_segmenti_rientro`, che sa quale
delle tratte di `tratte_rientro` e' la salita (la 1) e quale la discesa (la 3);
dedurlo dopo dai tratti vicini e' ambiguo quando una delle due corse manca. Lo
legge `plotting.corse_verticali` per le frecce del ciclogramma.

`kin_z` e' valorizzato anch'esso solo per `lift_empty`, ed e' la cinematica
**verticale** del tratto — orientata nel verso giusto, zona di avvicinamento
compresa. `kin` resta quella ORIZZONTALE, e su questi tratti e' `None` perche'
lungo la rotaia il carroponte sta fermo. Tenerle separate non e' pignoleria:
`verify.Trajectory.max_accel` conta i segmenti con `kin` non nullo per il
limite d'errore sulle posizioni di rotaia, e una corsa del gancio li' dentro
allargherebbe quel limite per un movimento che non lo riguarda.

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
empty_lift_seconds(station, scendendo=...)   # UNA corsa verticale a vuoto
kin_avvicinamento(kin, station, scendendo=...)  # la zona di avvicinamento, orientata
kin_lift_empty_at(station, scendendo=...)    # la stessa, per il gancio scarico
serve_alto(a, b)            # se quel rientro deve passare alto
horizontal_empty_seconds(x, y)  # la singola tratta orizzontale
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

**Ogni fase verticale passa da `kin_avvicinamento`.** E' l'unico punto in cui
`v_approach_lift` e `d_approach_lift` (§3) entrano nel calcolo, ed e' passaggio
obbligato per durata, disegno e simulazione insieme: una fase che non ci
passasse durerebbe una cosa e se ne disegnerebbe un'altra. Il metodo esclude le
stazioni servite da una zona di cambio quota (§4.5), dove le quote intermedie
sono di transito e non punti di presa.

**`empty_lift_seconds` vuole il verso.** Fino a quando il profilo era un
trapezio, salire e scendere della stessa corsa durava esattamente uguale. Con
una zona di avvicinamento la zona lenta cade una volta in coda e una volta in
testa, e su un carroponte che frena diversamente da come accelera i due conti
danno numeri diversi. Il parametro `scendendo` e' obbligatorio e nominato: un
default avrebbe lasciato passare il verso sbagliato in silenzio.

**`approach_position` contro `station_position`.** Il punto di APPROCCIO e' dove
il carroponte si trova prima di cominciare la presa e dopo aver finito il
rilascio; la stazione e' dove sta il pezzo. Coincidono sempre, tranne sulle due
tappe servite da una zona di cambio quota (§4.5). Per le distanze fra tratte del
giro — durata delle mosse, rientri a vuoto, finestre di non collisione — si usa
**sempre** il punto di approccio.

### 4.3 Il tempo in bagno, e dove comincia il tempo di gancio

Il modello maneggia due istanti: la fine del rilascio e l'inizio della presa
successiva. **Il bagno e' esattamente l'intervallo fra i due**, e i limiti di
processo `dwell_min`/`dwell_max` si applicano a quello senza correzioni:

```text
   immersione   sgancio    il gancio se ne va e torna    aggancio  emersione
──────────────┬──────────┬───────── ... ─────────────────┬─────────┬──────────
              ·          └──────── il pezzo e' a bagno ──┘         ·
              └────────────── il POSTO e' occupato ────────────────┘
```

```text
bagno = istante del prelievo − istante in cui il rilascio finisce
```

```python
dwell_min = T_(spec.dwell_min)
dwell_max = T_(spec.dwell_max)
```

> **Sgancio e aggancio sono tempo di GANCIO, non di processo.** Lo sgancio e'
> l'ultima fase del rilascio, l'aggancio la prima della presa: un offset in
> coda all'immersione e uno in testa al sollevamento. Il telaio e' davvero in
> fondo alla vasca mentre li si fa — e infatti il **posto resta occupato**,
> `slot_occupancy_seconds` li conta — ma il processo non li vede. Alzarli non
> stringe la permanenza utile; allunga il ciclo e l'occupazione del posto.

> **Le corse a vuoto del gancio stanno fuori per un'altra ragione.** Quello
> che risale dopo lo sgancio e quello che ricala prima dell'aggancio
> avvengono davvero col pezzo giù, ma cadono **dentro** l'intervallo fra i due
> istanti, quindi sono già contate lì. Sommarle di nuovo e' l'errore classico
> di questo punto: il foglio `FlussoPezzo` l'ha fatto per un po', gonfiando
> ogni permanenza riportata di una decina di secondi.

La definizione vive in tre posti — il modello (`solve_*`), il verificatore
(`_check_phase_and_dwell`) e il foglio `FlussoPezzo` di `excel_io` — e oggi i
tre concordano perche' la formula e' una sottrazione sola. Chi la cambia deve
cambiarla in tutti e tre: per un periodo modello e verificatore hanno
condiviso una definizione sbagliata, e su una linea reale sei vasche su dieci
sforavano il massimo mentre il file diceva `VERIFICA SUPERATA`. Un controllore
che misura la stessa cosa del controllato non controlla niente.

### 4.4 Movimentazione verticale, e le posizioni di svincolo

Presa e rilascio **non contengono mai** corse a vuoto del gancio: quelle
avvengono fra due mosse, e le paga il rientro.

**La zona di avvicinamento.** `ProblemData.v_approach_lift` e
`d_approach_lift` sono i millimetri attorno al punto di presa o deposito che si
percorrono a velocita' ridotta, e quella velocita'. Sono facoltativi e vanno
insieme (`__post_init__` rifiuta uno solo dei due) e **non** sono sdoppiati fra
vuoto e carico: a imporre la precisione e' il punto di accoppiamento fra gancio
e telaio, non il carico appeso. La regola che ne discende ha due facce, e la
zona lenta sta sempre al capo BASSO della corsa:

- **scendendo** a posare: si viaggia normalmente finche' mancano `d_approach`
  millimetri, li' si e' gia' alla velocita' di avvicinamento, la si tiene, e si
  frena solo all'ultimo;
- **salendo** a prelevare: si parte piano e si resta a quella velocita' per i
  primi `d_approach` millimetri, poi si accelera come sempre.

Il verso lo mette `kin_avvicinamento` (§4.2), che esclude anche le stazioni
servite da una zona di cambio quota (§4.5).

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
alto. Anche **carico e scarico** possono essere ostacoli: vuol dire che li' il
gancio SCARICO non puo' salire o scendere dov'e', e lo fa sul suo svincolo,
mentre il telaio si prende e si posa al centro come sempre. Non va confuso con
una zona di cambio quota (§4.5), che cambia il giro anche col pezzo appeso.
Fino a una versione precedente un ostacolo agli estremi veniva rifiutato,
sull'idea sbagliata che li' non ci fosse niente da evitare.

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

La posizione dichiarata deve cadere **fra la stazione servita e quella accanto** (estremi compresi),
e `__post_init__` lo verifica. Porta due garanzie, non una: il carroponte non
scavalca nessun'altra stazione per andarci, e il vai-e-torna dentro la presa si
allontana dal resto della linea — quindi non lo avvicina a nessun confine di
zona piu' di quanto gia' non lo sia il punto di cambio quota.

La corsa verticale della vasca servita deve essere `0`: li' la corsa la
definisce la zona (`corsa_telaio = intermediate2 - intermediate1`), e dichiararla
due volte vorrebbe dire che uno dei due valori viene ignorato in silenzio.

**Niente zona di avvicinamento qui.** Su queste due tappe il giro verticale e'
fatto di quote di TRANSITO — si sale a una quota per traslare, si scende a
un'altra per posare — e rallentare a ognuna sarebbe tempo regalato su quote
dove non c'e' niente da accoppiare con precisione. E' l'unica esclusione, e sta
in una riga di `kin_avvicinamento`.

---

## 5. Il modello CP-SAT (`solve`, in `model.py`)

### 5.1 Variabili

| variabile | significato |
| --- | --- |
| `Tv` | il takt time, in tick, in `[takt_min_ricerca, takt_max_ricerca]`: la banda dichiarata, oppure il solo teorico con `takt_fisso` |
| `sotto_k`, `sopra_k` | solo con `takt_fisso`: di quanto il bagno della tappa `k` sta sotto o sopra il teorico |
| `actual_time[k]` | istante assoluto del prelievo della mossa `k` (catena del pezzo) |
| `local_pick[k]` | la **fase** dello stesso prelievo dentro `[0, T)` |
| `finish[k]` | `local_pick[k] + loaded_leg` |
| `dep_hi`, `arr_lo` | quando il carroponte lascia il confine alto e torna a quello basso |
| `dep`, `arr` (per arco) | partenza e arrivo dello spostamento a vuoto di quell'arco; sui due archi di confine **sono** `dep_hi` e `arr_lo` |
| `sosta_..._i` (per arco e candidata) | il selettore dell'alternativa: rientro diritto, oppure con sosta in quella vasca in mezzo |
| `ripart_..._i` | quando il carroponte riparte dalla vasca in mezzo |

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
4. **Alternative del rientro** (`rientro`, dentro `solve`) — per ogni arco, una
   sola fra: diritto, oppure con una sosta in una delle vasche candidate
   (`soste_candidate`). `sum(selettori) == literal dell'arco`: se l'arco non si
   percorre non se ne sceglie nessuna, altrimenti i suoi intervalli entrerebbero
   nel vincolo di non collisione come se il carroponte fosse in due giri
   insieme. Ogni alternativa si racconta come una lista di **tappe**
   `(da, a, partenza, arrivo)`, ed e' da quelle che discendono sia il disegno sia
   gli intervalli del punto 5.
5. **Non collisione** — vedi sotto.
6. **Interblocco delle vasche** — vedi §5.4.

**L'obiettivo** ha un primo criterio che dipende da `takt_fisso`:

- **takt libero** (`takt_fisso = 0`): `Tv`, il takt time piu' corto;
- **takt fisso** (`takt_fisso = 1`, il default dei file Excel): `Tv` e' una
  costante, e si minimizza lo **scarto pesato** dai tempi teorici,
  `sum(peso_sotto · sotto_k + peso_sopra · sopra_k)`. Nel dominio di `Tv`
  c'e' un valore solo, quindi il presolve lo sostituisce con la costante e
  tutti i prodotti per `Tv` diventano termini noti senza toccarli uno per uno.

Quando ci sono soste in mezzo fra cui scegliere diventa
`Minimize(primo · (n_moves + 1) + numero di soste)`. Il peso e' `n_moves + 1`
perche' le soste non possono essere piu' di una per mossa: cosi' l'ordine fra
i due obiettivi e' garantito invece che sperato. Serve perche' a
parita' di takt time il solutore prenderebbe una qualunque delle soluzioni
ottime, e una sosta di zero secondi che nessuno ha voluto non si potrebbe
nemmeno togliere a posteriori — il vincolo di non collisione protegge il percorso
CON la sosta, non quello diritto.

L'ordine pero' vale solo se CP-SAT arriva all'ottimo. Quando scade prima
(FEASIBLE) il tempo e' andato tutto sul primo criterio, e le soste di zero
secondi restano: il carroponte va in un'altra vasca e torna senza fermarsi. Per
questo chi lancia il calcolo (`interfaccia`, `ciclogramma.main`) passa la
soluzione scelta a **`rifinisci_soluzione`**, che fa due passate:

1. **solo col takt libero**: risolve di nuovo sulle stesse zone con il takt
   INCHIODATO a quello trovato, cercando lo scarto pesato minimo -- lo stesso
   obiettivo di `takt_fisso`. Il takt minimo, da solo, lascia scegliere al
   solutore uno qualunque dei giri che lo raggiungono, anche lontanissimo dai
   teorici. Si tiene la nuova solo se lo scarto scende;
2. **sempre**: `riduci_soste`, sulla soluzione che si e' tenuta.

`riduci_soste` e' lo stesso modello con il solo obiettivo
`numero di soste`, takt time, prelievi e ordine del giro inchiodati alla
soluzione (`_DECISE_FUORI_DAI_RIENTRI`), e i rientri a vuoto liberi con la
soluzione come `AddHint`. Lasciando libero tutto non funzionava: il solo presolve
dei vincoli di non collisione si prendeva quasi tutto il tempo.
Si fa **una volta**, sulla soluzione finale, non dentro `solve`: la ricerca
automatica chiama `solve` per ogni suddivisione in zone. Si tiene il risultato
solo se ha lo stesso takt e meno soste, altrimenti torna la soluzione di prima.

`riduci_soste` ha anche un secondo compito, che viene PRIMA delle soste: il
tempo che un carroponte passa **fermo sopra il carico o lo scarico**
(`stazioni_presidiate`, per posizione). Dove il carroponte passa il tempo che
gli avanza e' indifferente al takt time, e il solutore sceglieva a caso: il
primo carro restava sopra il carico, l'ultimo sopra lo scarico. Nella
rifinitura l'obiettivo e' `(soste_possibili + 1) · attesa_presidiate + soste`:
l'attesa si sposta dove ha consegnato, dove prelevera' o in una vasca in mezzo
(anche a costo di una sosta in piu'), e resta li' solo se la non collisione la
impone. Le attese nelle altre vasche non costano niente. Per questo la
rifinitura gira anche su una soluzione OPTIMAL, e si tiene la nuova se
`(attesa_presidiate, soste)` scende in ordine lessicografico.
Gira senza rilassamento lineare (`PARAMETRI_RIFINITURA`), che qui non serve, e
con un limite suo (`TEMPO_RIDUCI_SOSTE_S`, 20 s). Un calcolo fermato con
`Ferma` salta tutte e due le passate: chi l'ha fermato ha rinunciato al resto
del lavoro.

**Riproducibilita'.** `configura_solutore` e' l'unico punto in cui si
impostano limite di tempo e thread del solutore. Normalmente: `NUM_WORKERS`
strategie in parallelo, otto ma mai piu' dei processori, e un limite in
secondi. Con la variabile d'ambiente `CRANESTRIKE_DETERMINISTICO=1`, che
accendono solo i test e la CI, le strategie si alternano a turni fissi e il
limite e' una quantita' di LAVORO (`max_deterministic_time`): la stessa linea
da' la stessa soluzione su qualunque macchina, a circa tre volte il tempo.
Senza, un test che passa sul PC puo' fallire sulla CI.

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

### 5.4 L'interblocco delle vasche

E' la regola del PLC: chi deve andare in una vasca interbloccata non parte
finche' il vicino non l'ha lasciata ed e' **arrivato su un'altra**. Si AGGIUNGE
alla fascia di esclusione, non la sostituisce. Le coppie di vasche in conflitto
le decide una funzione sola, `vasche_in_interblocco` (stessa vasca, oppure
vasche piu' vicine di `D`; nessuna con `ProblemData.interblocco` falso), e `coppie_interblocco(data, zones)` le
raccoglie per coppia di carroponti. Modello, verificatore, diagnosi, Riepilogo e
`allinea_avvio` passano tutti di li'.

Ogni carroponte **prenota** la vasca in cui si ferma, dalla partenza verso di
lei all'arrivo sulla vasca successiva. Nel modello (`prenotazioni`, dentro
`solve`) per ogni mossa `k` ce ne sono due, entrambe sempre presenti:

- sulla vasca `k`: da `il_s_{h}_{k}` -- la partenza dell'ultima tappa del
  rientro che ce lo porta, legata con `OnlyEnforceIf` al selettore
  dell'alternativa scelta -- fino all'arrivo sulla `k+1` col pezzo;
- sulla vasca `k+1`: dalla fine della presa sulla `k` fino a `il_e_{h}_{k}`,
  l'arrivo della prima tappa del rientro (la vasca dove prelevera', o quella
  della sosta).

Una sosta in mezzo e' una terza prenotazione, opzionale sul suo selettore. Se il
carroponte riprende dalla stessa vasca in cui ha consegnato, le due
prenotazioni coincidono e vanno dalla fine della presa precedente all'arrivo
della mossa dopo: una corsa del gancio sullo svincolo non e' "arrivare su
un'altra vasca". Le prenotazioni di due carroponti su vasche in conflitto non
si sovrappongono: `AddNoOverlap` a coppie, con le copie traslate di `±n·T`,
come per la fascia (le prenotazioni di uno stesso carroponte si sovrappongono
durante ogni traslazione, e un unico `AddNoOverlap` le escluderebbe).

Il verificatore (`verify.prenotazioni`) le ricostruisce dai **segmenti**: il
carroponte e' su una vasca durante presa e rilascio (cambio quota compreso),
durante un'attesa ferma sopra di lei, e nell'istante in cui una traslazione
comincia o finisce li' -- cosi' si vede anche una sosta di zero secondi, che il
modello conta come vasca raggiunta. Fermate successive sulla stessa vasca sono
una fermata sola.

**La trappola**: le due definizioni devono coincidere. Se il verificatore
vedesse una vasca raggiunta che il modello non conta, accetterebbe soluzioni
che il modello non garantisce; nel verso opposto respingerebbe soluzioni
buone. Chi cambia cosa vuol dire "fermarsi su una vasca" -- un tipo di
segmento nuovo, una sosta in un posto che non e' una vasca -- deve aggiornare
tutte e due.

Il default e' **acceso**, anche costruendo `ProblemData` a mano. I test di
`test_verify.py` che compongono soluzioni a mano lo spengono in `make_data`:
sono stati scritti per la sola distanza, e parecchi fanno aspettare un carro
sulla vasca di confine.

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

Un ciclogramma ha **cinque** gradi di liberta' reali: takt time, tempo in
vasca di ogni tappa, assegnazione delle mosse, l'**attesa** di ogni carroponte
dove ha consegnato prima del rientro a vuoto, e l'eventuale **sosta in una vasca
in mezzo** durante quel rientro. Tutto il resto e' conseguenza.

La sosta e' arrivata per ultima e per necessita': `dep_hi` era gia' una
variabile libera del solutore — il carroponte poteva sostare sul confine alto —
ma quel valore non veniva salvato, e la ricostruzione lo rifaceva con una
convenzione. Su 50 soluzioni verificate pulite, riaperte come fa il programma,
**14 collidevano**, una con i due carri sovrapposti (0 mm invece di 1200), dopo
una sosta di 374 s che il file non registrava. Salvando le soste: 0 su 54.

La **sosta** (`SostaIntermedia`, quinto grado di liberta') e' arrivata dopo, e
per un motivo diverso: quando tutti e due gli estremi del rientro sono dentro la
fascia di un vicino, nessuno dei due e' un buon posto dove restare fermi. Li' il
solutore puo' spezzare il rientro in due traslate e aspettare altrove. Vale quel
che si e' detto dell'attesa, e di piu': qui non cambia solo QUANDO il carroponte
si muove, cambia DOVE passa -- senza salvarla, il rientro si ricostruirebbe
diritto, piu' corto di quanto e', e non tornerebbero nemmeno i tempi.

**Non e' detto che la vasca stia FRA le due**, e il caso piu' frequente e'
proprio quello in cui un "fra" non esiste: due mosse consecutive che condividono
la vasca (si consegna in FO1 e dalla stessa FO1 si riprende). Li' il carroponte
non si sposta affatto, e se quella vasca e' sotto il naso del vicino ci resta
fermo per minuti: l'unica via d'uscita e' andarsene e tornare. Pretendere una
vasca "in mezzo" lasciava fuori esattamente questo caso, che e' quello che sulla
linea vera produce la collisione.

Quali vasche siano candidate lo decide `soste_candidate`, e non sono tutte: se
uno dei due estremi e' AL RIPARO la sosta non puo' servire, perche' partire
subito e passare li' tutto il tempo morto e' gia' nel modello e fa meglio (vedi
il README).

**Il primo candidato e' quasi gratis, il secondo no**, e la ragione sta nel
vincolo di non collisione: `soste_candidate` mette per primo un posto al riparo
da tutti e due i confini, e una sosta fuori dalle fasce non genera nessuna
finestra. Dal secondo in poi si prendono vasche ancora esposte, e li' la sosta
e' una finestra LUNGA che si accoppia con tutte quelle del vicino. Misurato su
una linea da 14 mosse e 4 carroponti: 43.264 vincoli di separazione a zero
candidati, 60.684 a uno (+40%), 120.120 a due. Per questo
`ProblemData.max_soste_intermedie` vale **1** di default. Il file Excel d'esempio
e quello scritto dal programma ne dichiarano invece **2**: i due default sono
diversi di proposito, e chi costruisce `ProblemData` a mano (i test, per
primi) parte dal modello piu' piccolo. Lo stesso vale per `takt_fisso`, falso
in `ProblemData` e a 1 nei file Excel.

Per lo stesso motivo le due attese LUNGHE di un arco -- quella prima di partire
e quella dopo essere arrivati -- si scrivono una volta sola sotto il letterale
dell'arco e non una per alternativa: partenza e arrivo sono le stesse per tutte,
e ripeterle triplicherebbe proprio gli intervalli che generano piu' coppie.

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

### 6.2 `avvio.py` — il punto di avvio, 617 righe

Un ciclogramma e' periodico e **non ha un inizio**: l'origine con cui viene
scritto e' il prelievo della prima mossa del primo carroponte, che per chi deve
accendere l'impianto non vuol dire niente. `avvio.py` ne ricava un istante che
invece vuol dire qualcosa: quello in cui i carroponti si possono lasciare come
stanno, perche' sono tutti

- **fermi** — nessuna traslazione, nessuna corsa del gancio;
- **in posizione bassa** — il gancio in fondo alla corsa della vasca su cui
  stanno, che e' dove lo lascia un rilascio e dove lo trova una presa;
- **ne' al carico ne' allo scarico** — le due stazioni presidiate, dove il pezzo
  viene appeso e staccato.

Le **finestre di riposo** di un carroponte (`finestre_di_riposo`) si leggono dai
suoi soli `Segment`, e sono di due tipi che si saldano fra loro: le **attese**
(`wait`), e l'**aggancio** e lo **sgancio** — le fasi ferme in fondo corsa in
testa alla presa e in coda al rilascio. I secondi non sono un dettaglio: in un
giro incatenato, dove il carroponte passa da una consegna alla presa successiva
senza mai aspettare, sono **l'unico** riposo che esiste, e senza di loro
nessun ciclogramma denso avrebbe un punto di avvio.

Carico e scarico si escludono **per posizione e non per indice**: se la ricetta
ci ripassa a meta' percorso resta comunque la vasca presidiata. E' anche la
ragione per cui le zone di cambio quota (§4.5) qui non si incontrano mai —
esistono solo a quelle due tappe.

**Quando un istante comune non c'e'** non si rinuncia, si prende il meno
sbagliato: quello in cui la somma, su tutti i carroponti, di quanto manca a
ciascuno — la distanza *circolare* dalla sua finestra piu' vicina — e' minima; a
pari errore, il primo.

`trova_avvii` restituisce **tutti** i tratti del ciclo che arrivano a
quell'errore, non il primo: sono quasi sempre piu' d'uno e stanno lontani fra
loro (sulla linea d'esempio del file Excel sono tre). Sono equivalenti per
l'errore, e quale convenga davvero lo sa chi conosce l'impianto. L'unica
preferenza che il modulo si prende e' l'**ordine**: per primo quello con piu'
margine (`Avvio.margine`, il lato piu' stretto del carroponte piu' stretto),
poi gli altri nell'ordine del ciclo. Nella finestra si scorrono col pulsante
`Avvio`; `trova_avvio` da' il primo, ed e' quello che si scrive quando non c'e'
nessuno a scegliere (il file dei risultati, il PNG da riga di comando).

Di ogni tratto si restituisce un istante: il **punto di mezzo** se l'errore e'
zero (`_estensione`) — il primo estremo e' l'istante in cui l'ultimo carroponte
si e' appena fermato, e avviare li' non lascerebbe margine da nessuna delle due
parti — e il **primo** altrimenti, perche' a pari errore si tiene il primo.

> **I candidati non sono solo gli estremi delle finestre.** Per trovare il
> minimo basterebbero quelli: fra due estremi consecutivi ogni distanza e'
> lineare, e nel mezzo di un buco ci sta il massimo, non il minimo. Ma per
> capire **quanti** tratti distinti arrivano al minimo servono anche i **colmi
> dei buchi**, a meta' fra la fine di una finestra e l'inizio della successiva:
> li' la distanza smette di crescere e comincia a calare, ed e' l'unico posto in
> cui l'errore puo' risalire *fra* due candidati che stanno tutti e due al
> minimo. Senza, due tratti buoni separati da un buco stretto si fondono in uno,
> e il pulsante ne mostra uno dove ce ne sono due. Costato un test: `test_avvio`
> conta i tratti campionando il ciclo e li confronta con quelli dichiarati.
> Aggiungere i colmi non puo' spostare il minimo: li' la pendenza della somma
> **cala di due**, quindi un minimo stretto non ci puo' stare.

Le finestre si trattano **circolarmente** ovunque, e `_nel_periodo` le restituisce
come `(a, b)` con `a` in `[0, T)` e `b` fino ad `a + T`: un `b` oltre `T` e' una
finestra a cavallo dell'origine, e ce n'e' quasi sempre una, perche' il giro di
un carroponte comincia con l'aggancio della sua prima presa e finisce con
l'attesa che la precede. Spezzarla in due agli estremi del periodo la farebbe
sembrare due finestre corte dove ce n'e' una lunga, e il punto di mezzo
cadrebbe nel posto sbagliato.

Il risultato si scrive in **quattro posti** e con le stesse parole, da
`righe_di_riepilogo`: la linea nera verticale del grafico (`plot_cyclogram`), la
sezione *Avvio della linea* del foglio Riepilogo, il pannello della finestra e
il terminale di `ciclogramma.py`.

### 6.3 `allinea_avvio.py` — l'avvio reso esatto, 400 righe

Quando `avvio.py` trova solo un avvio **approssimato**, quasi sempre e' un caso:
CP-SAT non sa che esiste un punto di avvio, e fra i giri buoni uguali ne ha
preso uno in cui le finestre di riposo di due carroponti si mancano di pochi
secondi. `allinea_avvio` rimedia senza risolvere di nuovo la linea, con
**spostamenti rigidi**: il giro di ciascun carroponte si sposta in blocco di
`s_h` secondi -- tutte le sue mosse (`actual_time`), con le stesse attese e
soste, che quindi restano valide e si ripassano tali e quali a
`build_solution`.

Uno spostamento rigido tocca solo due cose, ed e' cio' che rende il problema
piccolo:

- i **bagni di confine** -- la tappa `k` in cui il carroponte di `k-1` consegna
  e un altro preleva -- che cambiano di `s_dopo - s_prima` e devono restare
  in `[dwell_min, dwell_max]`;
- lo **sfasamento** fra due carroponti vicini. La loro distanza dipende solo da
  `s_i - s_j`, quindi gli sfasamenti sicuri si calcolano *prima* di risolvere:
  si campionano le traiettorie una volta su una griglia che divide esattamente
  il periodo (`PASSO_S`), e spostarne una e' un `np.roll`. Fra due campioni la
  distanza puo' calare al piu' di `(v_i + v_j) * passo / 2`, che si aggiunge
  alla distanza richiesta. Lo sfasamento zero e' ammesso sempre: e' il
  ciclogramma di partenza, gia' verificato.

Il modello CP-SAT ha una variabile per carroponte (quello della mossa 0 sta
fermo: uno spostamento comune a tutti non cambia niente), l'istante di avvio
`t` e, per ogni carroponte, la scelta della finestra di riposo che deve
contenere `t - s_h` con `MARGINE_MINIMO_S` da tutte e due le parti. Le finestre
sono quelle di `avvio._nel_periodo`, ripetute di un periodo avanti e indietro.
Tre obiettivi in fila, ciascuno a parita' dei precedenti:

1. **il cambiamento minimo** -- la somma dei secondi di cui cambiano i bagni di
   confine. Viene prima dello scarto di proposito: con lo scarto per primo, su
   un ciclogramma lontano dai teorici il ritocco ne approfittava per spostare i
   carroponti di decine di secondi, riottimizzando bagni che non c'entravano
   niente con l'avvio -- e su un ciclogramma composto a mano, bagni scelti
   dall'utente;
2. lo **scarto pesato** dai teorici, con i pesi del foglio Percorso;
3. il **margine** attorno all'avvio, fino a `MARGINE_CERCATO_S`.

Il risultato si tiene **solo se** `trova_avvio` lo dice esatto e
`verify_solution` lo passa. Usare il verificatore come filtro non lo rende meno
indipendente dal modello principale -- non ne condivide niente -- ma vuol dire
che su *questo* ritocco e' l'unico controllo: il campionamento a 50 ms delle
distanze e' una scrematura, e i posti nelle vasche li guarda solo lui.

Lo chiamano tre posti: `ciclogramma.py` e `interfaccia._allinea_nel_lavoro`
alla fine del calcolo automatico (in silenzio: se non riesce resta la soluzione
di prima), e il pulsante `Allinea avvio` sul ciclogramma che c'e'. Il pulsante
non usa la soluzione restituita: rilegge i tempi in vasca da `actual_time`,
sposta i punti di passaggio col loro carroponte, fissa attese e soste a quelle
della soluzione e ricompone con `tieni_rientri=True` -- altrimenti
`_ricomponi` tornerebbe alla regola predefinita delle attese, e disegnerebbe
rientri diversi da quelli appena verificati. Gli spostamenti restano scritti
in `Solution.raw["allineamento_avvio"]`, per indice di zona.

---

## 7. `verify.py` — il verificatore indipendente, 1544 righe

Ricontrolla una soluzione **in Python puro**, senza CP-SAT, campionando le
posizioni reali. Non solleva mai eccezioni su una violazione — restituisce un
`VerificationReport` con le `Violation` divise per gravita' (`error`,
`warning`, `info`). Una violazione e' una decisione di modellazione da prendere,
non un crash.

I controlli, in ordine: strutturali (copertura delle mosse compresa) → layout
→ **portata** (nessun carroponte oltre la sua `Portata`) → coerenza per
carroponte → fase e permanenze → trasferimenti → capienza → **collisioni** →
**interblocco** (§5.4).

Il controllo dei **trasferimenti** misura il percorso SCELTO, sosta in mezzo
compresa: guardare il rientro diritto sarebbe piu' permissivo del vero, cioe'
esattamente il tipo di svista per cui questo file esiste. La durata delle singole
traslate invece si ricontrolla dai segmenti, uno per uno, come sempre.

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

## 8. `excel_io.py` — 3429 righe

Un file di **ingresso** ha i fogli `Istruzioni`, `Vasche`, `Percorso`,
`Parametri`, `Zone` (facoltativo), `CambioQuota` (facoltativo), `Passaggi`
(facoltativo, si legge solo se c'e' anche il Ciclogramma) e `Ciclogramma`
(facoltativo). Il file modello (`scrivi_modello`, gia' compilato con la linea
d'esempio) ha i primi sei.

Il file dei **risultati** e' due cose insieme, in quest'ordine — quindici
fogli, sedici se ci sono punti di passaggio:

```text
Input | Istruzioni Vasche Percorso Parametri Zone CambioQuota [Passaggi] Ciclogramma
Output | Riepilogo Movimenti SequenzaCarri TempiVerticali FlussoPezzo Verifica
```

Il `Riepilogo` riporta, accanto al takt time, lo **scarto dai teorici senza
pesi** (§4.1): e' il numero che si legge anche nella barra di stato.

`Input` e `Output` sono cartelli con la linguetta colorata. Il file si apre sul
`Riepilogo` (`wb.active`), non sul primo foglio. **I fogli si creano
nell'ordine in cui devono comparire**: riordinarli dopo vorrebbe dire mettere le
mani in `wb._sheets`, che e' roba di openpyxl e puo' cambiare.

Nella lettura, gli errori si **raccolgono tutti** (`_Errori`) e si presentano
insieme con foglio e cella. Chi compila a mano sbaglia in piu' punti, e farlo
tornare indietro un errore per volta e' crudele.

`_NOMI_IN_METRI` e `_NOMI_SOSTITUITI` producono messaggi di migrazione espliciti
per i file scritti per versioni precedenti; `_NOMI_IGNORATI` elenca i parametri
che non esistono piu' e si leggono senza errori (oggi
`risoluzione_tick_per_s`).

### 8.1 Il foglio `Ciclogramma`: colonne per nome, non per posizione

Il foglio tiene i **gradi di liberta'** e due colonne che non lo sono:
`tempo_teorico_s` (quello della ricetta, dal foglio `Percorso`) e `scarto_s`, la
differenza. Stanno attaccate a `tempo_in_vasca_s` perche' li' serve il confronto
— *di quanto mi sono allontanato dalla ricetta, e dove* — e di li' discendono
tre scelte:

- **non si rileggono.** Il teorico ha una fonte sola; poterlo scrivere anche qui
  vorrebbe dire poterlo avere in due versioni nello stesso file. Si riscrivono a
  ogni salvataggio, e l'intestazione le marca con un verde piu' chiaro;
- `scarto_s` e' una **formula** (`=E6-F6`), non un numero: chi ritocca un tempo
  in vasca dentro Excel vede l'effetto senza ripassare dal programma;
- **le colonne si cercano per NOME** (`_colonne_ciclogramma`), ed e' la parte che
  conta. Infilarne due in mezzo alla tabella ha spostato `sosta_in_vasca` e
  `sosta_s` da G/H a I/J: un lettore che contasse le posizioni avrebbe letto i
  file di ieri con lo schema di oggi, prendendo lo scarto per l'attesa dopo la
  consegna — in silenzio, perche' sono tutti e due numeri plausibili. L'ordine
  storico resta solo come ripiego per chi ha cancellato la riga dei titoli.

> La stessa trappola ha morso i **test**: una prova scriveva -3.0 in `F5` per
> controllare che un'attesa negativa venisse respinta, e dopo lo spostamento
> continuava a scrivere in F5 — che adesso e' il tempo teorico, una colonna che
> il programma non legge. Il test non falliva, controllava un'altra cosa. Ora
> l'indirizzo lo da' `cella_ciclogramma(file, titolo, mossa)`, che cerca la
> colonna per nome come il lettore vero.

Due punti che si sono gia' rivelati fragili:

- **Le cifre salvate.** Le permanenze finiscono in una catena che le risomma e
  decide, con un arrotondamento all'insu', quanti periodi interi il pezzo resta
  in vasca. Tagliare a tre decimali e' fragile: si salva a nove.
- **Il foglio `TempiVerticali`** esiste perche' una presa da 26 s su una corsa
  da un metro e mezzo sembra un errore di calcolo, finche' non si vede che dieci
  di quei secondi sono lo sgocciolamento dichiarato.

### 8.2 Il foglio `SequenzaCarri` e `programma_carri.py`

Il programma di ogni carro nei comandi del PLC. `programma_carri.py` decide i
passi, `excel_io._scrivi_sequenza_carri` li scrive e basta. Tre cose da sapere:

- **I passi si leggono, non si calcolano.** Trasporti, rientri a vuoto, corse
  sugli svincoli e attese vengono dai `Segment`; presa e rilascio dalle loro
  **fasi** (`pick_phases` / `release_phases`), una volta per blocco anche
  quando il cambio quota li spezza in piu' segmenti. Aggancio e sgancio non
  sono passi. Lo sgocciolamento si riconosce dalla forma della fase (ferma,
  col telaio appeso, sopra la quota di riposo), non dal nome.
- **Il `Crane Syncro` e' l'interblocco detto a passi.** Le coppie di vasche in
  conflitto sono quelle di `coppie_interblocco`, e "arrivare su una vasca"
  vuol dire la stessa cosa che in `verify.prenotazioni`: un Transfer che
  finisce SU una vasca del percorso; svincoli e punti di passaggio sono
  strada, il punto di cambio quota conta come la sua vasca. Se le due
  definizioni divergessero, i passi indicati non sarebbero quelli in cui il
  vicino e' davvero fuori. Quando il ciclogramma viola l'interblocco il
  Crane Syncro si scrive lo stesso, con una nota sotto le tabelle.
- **Il passo 1 si sceglie carro per carro** (`_inizio_del_programma`):
  l'istante di avvio se il carro li' e' a riposo secondo
  `avvio.finestre_di_riposo`, altrimenti l'inizio della sua prossima finestra.
  Le due definizioni di "a riposo" sono la stessa apposta: il Riepilogo dice
  dove lasciare i carri, e il programma deve partire da li'.
- **I numeri di passo si risolvono per ultimi.** Il passo da aspettare si
  tiene come riferimento all'oggetto `Passo` (il Transfer che porta il vicino
  fuori), e diventa un numero solo quando tutti i programmi sono completi:
  ruotati sull'avvio, con le richieste inserite e le pause a zero tolte.
  Contarlo prima darebbe un numero sbagliato appena si aggiunge un passo.

---

## 9. `interfaccia.py` — 3860 righe

`main` apre prima la schermata di accesso (`accesso.chiedi_accesso`), poi la
schermata di benvenuto con il logo, e solo dopo la finestra. La classe
`Applicazione(tk.Tk)` e' tutta la finestra. Lo stato utile:

```python
T_corrente, permanenze, assegnazione, n_carroponti   # i gradi di liberta'
attese              # dove ogni carro sosta; None = decide la regola
soste               # le fermate in una vasca in mezzo; {} = nessuna, e non
                    # c'e' nessuna regola che le inventi
passaggi            # i punti di passaggio aggiunti a mano: {"t", "x", "carro"}
avvii, indice_avvio # i punti di avvio equivalenti, e quale si sta guardando
soluzione, dati, report, incoerenze
vista               # "ciclogramma" | "pettine"
modifica_aperta     # se la scheda Ciclogramma e' aperta
verifica_viva       # se il verdetto si aggiorna da solo
_lavoro_in_corso    # il solutore sta girando
_interruzione       # model.Interruzione del calcolo in corso, None se non ce n'e'
```

**`_ricomponi()` e' il funnel di ogni modifica.** Cambio del takt, dei tempi in
vasca, dell'assegnazione, trascinamento sul grafico, punti di passaggio: tutto
passa di li'. Ne segue che una riga sola — la guardia su `_lavoro_in_corso` —
impedisce a qualunque modifica di infilarsi mentre il solutore lavora, anche da
una strada che oggi non esiste. Se aggiungi un comando che modifica il
ciclogramma, fallo passare da `_ricomponi`. Una modifica non butta le pause
gia' decise: `manuale.adatta_rientri` riporta attese e soste sui rientri che
restano gli stessi, e le accorcia se non ci stanno piu'.

**Dopo un calcolo automatico** la finestra chiama `rifinisci_soluzione` e poi
`allinea_avvio` (`_allinea_nel_lavoro`), come `ciclogramma.py`. Se il calcolo
non trova niente parte la diagnosi (`_diagnostica`), anche dopo `Ottimizza con
questi carroponti`. Il pulsante `Fattibilita'` invece non risolve niente:
mostra i limiti di `fattibilita.py`.

**`_mostra_ciclogramma()` e' il funnel di ogni ridisegno**, ed e' li' che la
finestra della simulazione viene aggiornata.

Il lavoro pesante gira in un thread con una `queue.Queue`: `_avvia_lavoro`
mette, `_controlla_coda` ritira con `after(80)`. Nel thread **non si tocca
nessun widget**.

**Fermare un calcolo.** `_avvia_lavoro` crea una `model.Interruzione` nuova per
ogni lavoro e la passa come argomento alla funzione del thread; il pulsante
`Ferma` chiama `ferma()` e basta. Il thread, fermato, mette il suo risultato in
coda come un calcolo finito: la fine di un calcolo ha un solo percorso. Dentro
`model` lo stop agisce in due punti: `solve` guarda `richiesta` a ogni
carroponte e a ogni confine mentre costruisce il modello (Python), e registra il
`CpSolver` presso l'`Interruzione` perche' `ferma()` possa chiamare
`StopSearch()` mentre CP-SAT cerca (codice nativo). Registrazione e stop stanno
sotto lo stesso lucchetto, altrimenti una richiesta arrivata fra l'ultimo
controllo e il lancio andrebbe persa. Misurato: risposta fra 0,1 e 0,5 s. Un
calcolo fermato e' **UNKNOWN con `raw["interrotto"]`, mai INFEASIBLE**: non ha
dimostrato niente, e l'interfaccia non deve lanciare la diagnosi ne' cancellare
il ciclogramma che c'era.

**Mettere in pausa.** `Pausa` chiama `Interruzione.pausa()`, `Riprendi`
`riprendi()`. CP-SAT non sa sospendersi, e congelarlo da fuori non servirebbe:
`max_time_in_seconds` e' tempo reale, e alla ripresa il tentativo scadrebbe.
Allora la pausa vale solo dentro il ciclo dei tentativi di `solve_auto_zones`
(il tratto `Interruzione._ricerca`): il solutore in corso riceve
`StopSearch()`, il suo esito si butta (un contatore di pause dice se un
tentativo ne e' stato toccato), il thread aspetta su una `Condition` e alla
ripresa rifa' lo stesso tentativo. Fuori da quel tratto la pausa non ferma
niente: le rifiniture cambierebbero risultato. Il thread annuncia inizio e
fine della pausa con `su_pausa`, che l'interfaccia passa nella coda: serve a
dirlo nella barra e a spostare in avanti `_inizio_lavoro`, cosi' durata e stima
di quanto manca ignorano il tempo in pausa.

### 9.1 Le due viste, e perche' si modifica solo su una

| vista | quando | cosa |
| --- | --- | --- |
| ciclogramma | `Calcola auto`, `Fine modifica` | traiettorie dei carroponti, 2 cicli, e il pezzo fermo in vasca come linea grigia (`plotting.pezzi_in_vasca`) |
| modifica | `Calcola man`, `Modifica` | percorso dei pezzi in **grigio** + giro dei carroponti sopra |

Si modifica sempre sulla seconda, e non e' una preferenza: nel ciclogramma nudo
si disegnano solo le traiettorie e le soste in vasca dei pezzi, quindi un
trasporto **non assegnato non compare affatto** — pur restando cliccabile,
perche' `_tratti_trasporto()` lo calcola comunque. Invisibile e cliccabile
insieme e' la combinazione peggiore.

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

## 10. `simulazione.py` — 2058 righe

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

**Il logo** sta sulla riga del titolo, allineato al bordo sinistro del disegno
come nel PNG del ciclogramma (`_metti_logo`, con `plotting.PERCORSO_LOGO`). E'
ancorato agli assi, quindi va **rimesso dopo ogni `assi.clear()`**, ed e'
escluso dal `tight_layout`. Se il file non si legge, il logo semplicemente non
c'e'.

---

## 11. I test — dieci suite, quasi novecento controlli

Nessun pytest: ogni file si lancia da solo, stampa cosa ha provato e restituisce
un codice d'uscita.

| file | controlli | richiede | domanda a cui risponde |
| --- | ---: | --- | --- |
| `test/test_verify.py` | 137 | — | il verificatore trova davvero quello che deve? |
| `test/test_excel_io.py` | 183 | — | un file compilato male viene respinto con un messaggio utile? |
| `test/test_simulazione.py` | 93 | — | la simulazione mostra il ciclogramma che c'e'? |
| `test/test_avvio.py` | 37 | — | il punto di avvio e' davvero un punto di avvio? |
| `test/test_programma_carri.py` | 70 | — | il programma dei carri e' il ciclogramma, detto nei comandi del PLC? |
| `test/test_accesso.py` | — | — | utente e password giusti entrano, e tutto il resto no? (senza aprire finestre) |
| `test/test_fattibilita.py` | 13 | OR-Tools | i limiti inferiori del takt time non escludono mai una linea fattibile? |
| `test/test_allinea_avvio.py` | 15 | OR-Tools | un avvio approssimato diventa esatto senza rompere niente? |
| `test/test_model.py` | 145 | OR-Tools | il modello produce soluzioni fisicamente valide? |
| `test/test_interfaccia.py` | 183 | OR-Tools + grafica | l'interfaccia si comporta come deve? |

I numeri sono quelli dell'ultimo giro completo. `test_accesso` non li conta:
dice solo se i controlli sono passati tutti. Su un PC da ufficio `test_model`
e `test_interfaccia` durano ciascuno fra mezz'ora e un'ora: sono loro a
decidere quanto dura un giro completo.

**La CI.** Scrivendo `check` in un commento di una pull request,
`.github/workflows/check.yml` lancia i test su Windows, divisi in tre gruppi
che girano in parallelo, con `CRANESTRIKE_DETERMINISTICO=1` (§5.2). Un nuovo
push sulla stessa pull request annulla il giro in corso.

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
la traiettoria. Non si emettono. Lo stesso vale per una **sosta in mezzo
indicata su un estremo** del viaggio a vuoto — che dal file puo' arrivare,
perche' la' la scrive una persona: sarebbe una traslata di lunghezza zero, e
`_perche_la_sosta_non_va` la respinge come incoerenza invece di disegnarla.

**Una sosta in mezzo NON si puo' togliere a posteriori.** Il vincolo di non
collisione protegge il percorso CON la sosta; ripiegare sul rientro diritto --
per esempio perche' la sosta dura zero secondi e sembra inutile -- vorrebbe dire
disegnare una traiettoria che nessuno ha verificato, con il carroponte in posti
diversi negli stessi istanti. Per questo le soste inutili si evitano
nell'OBIETTIVO (§5.2), prima che esistano, e non dopo.

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
python test/test_verify.py      python test/test_excel_io.py   python test/test_simulazione.py
python test/test_avvio.py       python test/test_programma_carri.py
python test/test_accesso.py     python test/test_fattibilita.py
python test/test_allinea_avvio.py
python test/test_model.py       python test/test_interfaccia.py
python test/esempio.py          python interfaccia.py --autotest
```

Oppure, su una pull request, il commento `check` (§11), che li lancia tutti.

Sull'esempio, `test/esempio.py` deve restare a **T = 115,67 s** con separazione
minima 3500 mm contro 1800 richiesti. Se cambia, o hai migliorato qualcosa e lo
sai, oppure hai rotto qualcosa e non lo sai ancora.
