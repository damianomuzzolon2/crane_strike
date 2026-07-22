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
   contigua** di mosse (indici di trasporto, non di vasca). Il numero di
   carroponti e le zone sono un **input** in questa v1 (non decisi dal
   solver) — vedi sotto per come sceglierle.
6. **Sicurezza**: `hoist_length` (ingombro) e `safety_distance` (margine
   minimo aggiuntivo) vengono usati per allargare le finestre temporali di
   occupazione dei punti di confine fra zone adiacenti.

### Come scegliere le zone (v1)

Dividi le stazioni in gruppi contigui, uno per carroponte, nell'ordine
fisico lungo la rotaia. Il "confine" fra due carroponti adiacenti e' la
stazione dove l'uno consegna e l'altro preleva. Una divisione ragionevole
di partenza: bilancia il "contenuto" di ciascuna zona (somma di tempi di
percorrenza e permanenza) in modo che nessuna zona superi da sola il takt
time massimo — altrimenti quel carroponte non riuscirebbe a stare nel
ciclo (vedi limitazioni sotto).

## Assunzioni e limitazioni importanti (leggere prima di fidarsi dei risultati)

Il modello implementato (vedi commenti dettagliati in testa a `model.py`)
fa scelte di modellazione precise, in particolare:

- **Zone contigue e fisse**: ogni carroponte gestisce sempre lo stesso
  gruppo di mosse, nello stesso ordine, ogni ciclo. E' l'approccio piu'
  diffuso nella pratica industriale, ma non e' la formulazione piu'
  generale possibile.
- **Il modello e' corretto (sound) ma non completo**: ogni soluzione
  trovata e' un ciclogramma fisicamente valido, privo di collisioni. Se
  pero' il solver restituisce INFEASIBLE, non e' detto che il problema sia
  davvero irrisolvibile: potrebbe servire una schedulazione piu' sofisticata
  in cui un carroponte "si destreggia" fra piu' pezzi diversi nella propria
  zona (non rappresentata qui). Prima di concludere che serve piu' hardware,
  prova a ribilanciare le zone o ad aumentare la tolleranza sul takt time.
- **Collisioni modellate solo ai confini di zona**: e' l'unico punto in cui
  due carroponti condividono fisicamente lo spazio in questa formulazione.
  Le finestre di occupazione usate sono conservative (tutto l'intervallo fra
  arrivo e partenza), quindi il modello non rifiuta mai una soluzione
  davvero sicura, ma potrebbe scartarne alcune "al limite" che in pratica
  sarebbero fattibili con un margine di sicurezza piu' fine.
- **Un solo percorso vasche** condiviso da tutti i pezzi (nessun mix di
  prodotti diversi in questa v1).

Nella sezione finale di `model.py` ("Estensioni possibili") sono descritte
le direzioni per superare queste limitazioni (zone decise dal solver,
instradamento non contiguo via `AddCircuit`, piu' ricette, collisione meno
conservativa, tempi di presa/rilascio pezzo).

## Nota sui test effettuati

In questo ambiente di sviluppo non e' stato possibile installare `ortools`
(nessun accesso di rete), quindi **la risoluzione CP-SAT vera e propria non
e' stata eseguita qui**. Sono stati pero' testati direttamente:
cinematica (`kinematics.py`), costruzione delle strutture dati e delle loro
validazioni, costruzione ed estrazione della traiettoria
(`_build_trajectories`), normalizzazione di fase e disegno del ciclogramma
(`plotting.py`), il tutto con valori scelti a mano e verificati
manualmente contro i vincoli del modello. Il codice della funzione `solve`
e' stato controllato riga per riga contro la API di OR-Tools CP-SAT ed e'
sintatticamente corretto (`py_compile` su tutti i file). Consiglio di
eseguire `python esempio.py` sulla tua macchina (con `pip install ortools`)
e di segnalarmi eventuali errori residui: sono ovviamente possibile in un
modello di questa complessita' senza un test end-to-end reale.
