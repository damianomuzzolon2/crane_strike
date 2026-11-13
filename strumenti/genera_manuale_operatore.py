"""
genera_manuale_operatore.py
---------------------------
Scrive il manuale operatore dell'interfaccia grafica:

    python strumenti/cattura_schermate.py          # 1) le schermate (apre il programma)
    python strumenti/genera_manuale_operatore.py   # 2) il documento Word

Le schermate stanno in `doc/manuale_operatore/img/`, il documento in
`doc/manuale_operatore/manuale_operatore.docx`. Quando l'interfaccia cambia si
rifanno le schermate e si rigenera; il testo sta qui sotto, in CONTENUTO.

Il manuale spiega pulsanti e pagine. Come si compila la linea (Excel o finestra
"Dati linea") e' in un documento a parte: qui la finestra si mostra soltanto.
"""

from __future__ import annotations

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ATTREZZI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(ATTREZZI)
CARTELLA = os.path.join(RADICE, "doc", "manuale_operatore")
IMG = os.path.join(CARTELLA, "img")
ANNOTATE = os.path.join(CARTELLA, "img_annotate")
USCITA = os.path.join(CARTELLA, "manuale_operatore.docx")

ROSSO = (200, 30, 30)
BLU = (20, 90, 180)

# I pulsanti della barra dei comandi, nell'ordine in cui stanno: il numero
# sulla figura annotata e' la posizione in questa lista.
PULSANTI = [
    "Apri linea...",
    "Nuovo modello Excel...",
    "Dati linea...",
    "Fattibilita'",
    "Calcola auto",
    "Ferma",
    "Pausa",
    "Calcola man",
    "Modifica",
    "Simulazione",
    "Avvio",
    "Allinea avvio",
    "Salva risultati...",
]
# Le zone della finestra: lettera sulla figura -> chiave in regioni.json
ZONE = [
    ("A", "percorso"),
    ("B", "grafico"),
    ("C", "barra_grafico"),
    ("D", "verdetto"),
    ("E", "schede"),
    ("F", "stato"),
    ("G", "avanzamento"),
]


# --------------------------------------------------------------------------
# Immagini annotate
# --------------------------------------------------------------------------


def _font(dimensione: int):
    for nome in ("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nome, dimensione)
        except OSError:
            pass
    return ImageFont.load_default()


def _bollino(disegno, cx, cy, testo, colore, r=12):
    disegno.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colore, outline="white", width=2)
    f = _font(13 if len(testo) > 1 else 15)
    l, t, rr, b = disegno.textbbox((0, 0), testo, font=f)
    disegno.text((cx - (rr - l) / 2 - l, cy - (b - t) / 2 - t), testo, fill="white", font=f)


def annota_finestra(regioni: dict):
    """La finestra principale con i pulsanti numerati e le zone a lettere."""
    reg = regioni["08_calcolo_auto_riepilogo"]
    finestra = Image.open(os.path.join(IMG, "08_calcolo_auto_riepilogo.png")).convert("RGB")
    # Una fascia bianca sopra la finestra per i numeri dei pulsanti: messi
    # sotto ai pulsanti finirebbero sul verdetto e sul titolo del grafico.
    FASCIA = 34
    img = Image.new("RGB", (finestra.width, finestra.height + FASCIA), "white")
    img.paste(finestra, (0, FASCIA))
    d = ImageDraw.Draw(img)

    def r(chiave):
        x0, y0, x1, y1 = reg[chiave]
        return x0, y0 + FASCIA, x1, y1 + FASCIA

    for nome, chiave in ZONE:
        x0, y0, x1, y1 = r(chiave)
        d.rectangle((x0 - 2, y0 - 2, x1 + 1, y1 + 1), outline=BLU, width=3)
        if chiave == "grafico":
            _bollino(d, x0 + 22, y0 + 22, nome, BLU, r=14)
        elif chiave == "schede":
            _bollino(d, x1 - 24, y0 + 14, nome, BLU, r=14)
        elif chiave == "percorso":
            cx = (x0 + x1) / 2
            d.line((cx, 28, cx, y0 - 2), fill=BLU, width=2)
            _bollino(d, cx, 15, nome, BLU, r=14)
        elif chiave == "stato":
            _bollino(d, x1 + 20, (y0 + y1) / 2, nome, BLU, r=14)
        else:
            _bollino(d, x1 - 22, (y0 + y1) / 2, nome, BLU, r=14)
    for i, nome in enumerate(PULSANTI, start=1):
        x0, y0, x1, y1 = r(nome)
        d.rectangle((x0 - 1, y0 - 1, x1, y1), outline=ROSSO, width=2)
        cx = (x0 + x1) / 2
        d.line((cx, 26, cx, y0 - 1), fill=ROSSO, width=2)
        _bollino(d, cx, 14, str(i), ROSSO)
    img.save(os.path.join(ANNOTATE, "finestra_annotata.png"))


def ritaglia(nome_img: str, regione, uscita: str, margine=0, scala=1.0):
    img = Image.open(os.path.join(IMG, nome_img + ".png")).convert("RGB")
    x0, y0, x1, y1 = regione
    pezzo = img.crop((x0 - margine, y0 - margine, x1 + margine, y1 + margine))
    if scala != 1.0:
        pezzo = pezzo.resize(
            (round(pezzo.width * scala), round(pezzo.height * scala)), Image.LANCZOS
        )
    pezzo.save(os.path.join(ANNOTATE, uscita + ".png"))


def prepara_immagini():
    os.makedirs(ANNOTATE, exist_ok=True)
    with open(os.path.join(IMG, "regioni.json"), encoding="utf-8") as f:
        regioni = json.load(f)
    annota_finestra(regioni)
    reg = regioni["08_calcolo_auto_riepilogo"]
    # i cinque colori del verdetto: la striscia e' nello stesso punto in tutte
    for sorgente, uscita in [
        ("04_linea_caricata", "verdetto_grigio"),
        ("08_calcolo_auto_riepilogo", "verdetto_verde"),
        ("15_modifica_con_errori", "verdetto_rosso"),
        ("13a_calcola_man_riepilogo", "verdetto_arancio"),
        ("13d_in_composizione", "verdetto_azzurro"),
    ]:
        ritaglia(sorgente, reg["verdetto"], uscita)
    # la barra sotto al grafico, ingrandita: le icone sono piccole
    x0, y0, x1, y1 = reg["barra_grafico"]
    ritaglia("08_calcolo_auto_riepilogo", (x0, y0, x0 + 200, y1), "barra_grafico", scala=2.0)
    # la barra dei comandi della simulazione
    sim = Image.open(os.path.join(IMG, "12_simulazione.png")).convert("RGB")
    sim.crop((0, sim.height - 92, 300, sim.height - 52)).resize((600, 80), Image.LANCZOS).save(
        os.path.join(ANNOTATE, "comandi_simulazione.png")
    )


# --------------------------------------------------------------------------
# Il testo
# --------------------------------------------------------------------------
#
# Ogni voce e' una tupla:
#   ("h1"|"h2"|"h3", testo)    titoli
#   ("p", testo)               paragrafo; **grassetto** e `pulsante` ammessi
#   ("b", testo)               punto elenco
#   ("n", testo)               elenco numerato
#   ("img", file, larghezza_cm, didascalia)   file in img/ o img_annotate/
#   ("tab", [intestazione], [[riga], ...], [larghezze_cm])
#   ("nota", testo)            riquadro evidenziato
#   ("pagina",)                salto pagina

CONTENUTO = [
    ("h1", "1. Introduzione"),
    ("p", "CraneStrike calcola il **ciclogramma** dei carroponti di una linea di "
          "trattamento: quale carroponte sposta ogni pezzo, quando, e quanto "
          "tempo il pezzo resta in ogni vasca. Il risultato si controlla con una "
          "**verifica indipendente**, si può ritoccare a mano, guardare in "
          "movimento e salvare in Excel."),
    ("p", "Questo manuale spiega **come si usa l'interfaccia**: cosa fa ogni "
          "pulsante e cosa mostra ogni pagina. Non spiega come si descrive la "
          "linea (vasche, percorso, parametri, zone): quello è oggetto di un "
          "documento a parte, a cui si rimanda ogni volta che serve."),
    ("p", "Le schermate sono state prese sulla linea d'esempio che il programma "
          "fornisce (`Nuovo modello Excel...`): sette stazioni, dal carico allo "
          "scarico passando per sgrassatura, risciacqui, zincatura e passivazione."),
    ("h2", "Il percorso tipico"),
    ("n", "Si apre una linea (`Apri linea...`) oppure la si compila nella finestra "
          "`Dati linea...`."),
    ("n", "Facoltativo: `Fattibilita'` dice in un istante se il takt time richiesto "
          "è certamente impossibile."),
    ("n", "Si ottiene un ciclogramma: lo calcola il programma (`Calcola auto`) "
          "oppure lo si compone a mano (`Calcola man`)."),
    ("n", "Si legge il **verdetto** in alto a destra e, se serve, si ritocca "
          "(`Modifica`)."),
    ("n", "Si sceglie il punto di avvio (`Avvio 1 di N`) e si guarda la linea in "
          "movimento (`Simulazione`)."),
    ("n", "Si salva (`Salva risultati...`): Excel dei risultati più immagine del "
          "ciclogramma."),

    ("h1", "2. Avvio del programma"),
    ("p", "Il programma si avvia con un doppio clic su **CraneStrike.exe** (o su "
          "CraneStrike.bat, nella versione non impacchettata)."),
    ("h2", "2.1 Accesso"),
    ("img", "01_accesso", 6.0, "La finestra di accesso."),
    ("p", "Per prima cosa si apre la finestra di accesso. Si scrivono **Utente** e "
          "**Password** e si preme `Entra` (oppure Invio). `Esci` (oppure Esc) "
          "chiude il programma."),
    ("b", "Se utente o password sono sbagliati la password si cancella e compare "
          "un messaggio in rosso con il numero di tentativi rimasti."),
    ("b", "Dopo l'ultimo tentativo sbagliato il programma si chiude: basta "
          "riavviarlo."),
    ("b", "Utenti e password li assegna chi distribuisce il programma; non si "
          "cambiano dall'interfaccia."),
    ("h2", "2.2 Schermata di benvenuto"),
    ("img", "02_splash", 4.5, "La schermata di benvenuto."),
    ("p", "Entrati, per circa tre secondi compare la schermata con il logo del "
          "programma, mentre la finestra principale si prepara. Non richiede "
          "nessuna azione."),

    ("pagina",),
    ("h1", "3. La finestra principale"),
    ("img", "finestra_annotata", 16.5,
     "La finestra principale dopo un calcolo. In rosso i pulsanti (numerati come "
     "nel capitolo 4), in blu le zone (lettere)."),
    ("p", "La finestra è divisa in quattro parti:"),
    ("tab", ["", "zona", "a cosa serve"], [
        ["1–13", "Barra dei comandi", "I pulsanti, da sinistra a destra nell'ordine "
                 "in cui di solito si usano. Sono spiegati uno per uno nel capitolo 4."],
        ["A", "Percorso del file", "Il percorso completo del file aperto. Lo stesso "
              "percorso compare nel titolo della finestra e in cima al Riepilogo. "
              "Se la linea è stata cambiata in Dati linea accanto c'è scritto "
              "(modificata in Dati linea)."],
        ["B", "Grafico", "Il ciclogramma, oppure la pagina di modifica. Vedi capitolo 5."],
        ["C", "Barra del grafico", "Ingrandire, spostare, salvare l'immagine. Vedi 5.4."],
        ["D", "Verdetto", "Striscia colorata sempre in vista: dice se il ciclogramma "
              "è valido. Vedi capitolo 6."],
        ["E", "Schede", "Riepilogo, Ciclogramma, Verifica. Vedi capitolo 7."],
        ["F", "Barra di stato", "Cosa sta facendo il programma o cosa ha appena "
              "fatto. Sul grafico mostra anche tempo e posizione sotto il puntatore."],
        ["G", "Avanzamento", "Si riempie durante il calcolo automatico."],
    ], [1.3, 3.5, 11.5]),
    ("p", "La finestra si apre a 1280×800 e si può ingrandire. La linea che "
          "divide grafico e pannello di destra si può trascinare per dare più "
          "spazio all'uno o all'altro."),
    ("img", "03_finestra_vuota", 14.0,
     "Appena avviato: nessuna linea aperta, quasi tutti i pulsanti sono spenti."),
    ("p", "Appena avviato il programma non ha nessuna linea: sono accesi solo "
          "`Apri linea...`, `Nuovo modello Excel...` e `Dati linea...`. Gli altri "
          "pulsanti si accendono quando hanno qualcosa su cui lavorare (vedi la "
          "tabella al capitolo 10)."),

    ("pagina",),
    ("h1", "4. La barra dei comandi"),

    ("h2", "4.1  [1] Apri linea..."),
    ("p", "Apre un file Excel con la definizione della linea. Si può aprire:"),
    ("b", "un file di ingresso compilato (ad esempio quello creato con "
          "`Nuovo modello Excel...`);"),
    ("b", "un file di **risultati** salvato in precedenza con `Salva risultati...`: "
          "contiene anche la linea e il ciclogramma, e si riprende il lavoro da "
          "dove lo si era lasciato (vedi 8.7)."),
    ("img", "04_linea_caricata", 14.0,
     "Linea aperta: il Riepilogo descrive la linea, il grafico è ancora vuoto."),
    ("p", "Aperto il file, il Riepilogo mostra stazioni, mosse, takt time teorico "
          "con la sua banda, obiettivo del calcolo e l'elenco delle vasche. Il "
          "grafico resta vuoto finché non si calcola o si compone un ciclogramma."),
    ("p", "Se il file contiene errori di compilazione non succede nulla di grave: "
          "compare un messaggio con **tutti** gli errori trovati (foglio e cella) "
          "e la domanda se aprire i dati nella finestra `Dati linea` per "
          "correggerli lì."),

    ("h2", "4.2  [2] Nuovo modello Excel..."),
    ("p", "Chiede dove salvare un nuovo file Excel e lo scrive **già compilato con "
          "una linea d'esempio**, poi chiede se aprirlo subito. È il modo "
          "consigliato di cominciare una linea nuova: si parte da un file che "
          "funziona e lo si modifica. Come compilarlo è spiegato nel documento "
          "dedicato."),

    ("h2", "4.3  [3] Dati linea..."),
    ("p", "Apre una finestra con le **tabelle della linea**, le stesse dei fogli "
          "del file Excel, per guardarle e modificarle senza uscire dal programma. "
          "Il pulsante è sempre acceso: senza una linea aperta la finestra parte "
          "dalla linea d'esempio."),
    ("img", "05_dati_linea_vasche", 15.0, "La finestra Dati linea, scheda Vasche."),
    ("img", "05_dati_linea_2_parametri", 15.0,
     "Scheda Parametri: in grassetto i parametri obbligatori; selezionando una riga, "
     "in basso compare la sua spiegazione."),
    ("nota", "In questa finestra ci sono dati da compilare: le vasche, il percorso "
             "del pezzo, i parametri della linea (takt time, velocità e "
             "accelerazioni dei carroponti, ingombri, distanze...), le zone e i "
             "cambi di quota. Il significato di ogni colonna e di ogni parametro è "
             "spiegato nel documento dedicato alla compilazione della linea."),
    ("p", "La finestra ha cinque schede — **Vasche**, **Percorso**, **Parametri**, "
          "**Zone**, **Cambio quota** — e in basso quattro pulsanti:"),
    ("tab", ["pulsante", "cosa fa"], [
        ["Applica alla linea", "Rende le tabelle la linea in uso. I controlli sono gli "
         "stessi di un file: se qualcosa non va compare l'elenco «Da correggere» e "
         "le righe sbagliate diventano rosse (un clic sull'errore porta alla riga). "
         "Se c'era già un ciclogramma il programma chiede conferma, perché va rifatto."],
        ["Annulla modifiche", "Torna alla linea in uso, buttando le modifiche non "
         "ancora applicate."],
        ["Salva come Excel...", "Scrive le tabelle in un file di ingresso, da riaprire "
         "con Apri linea... Salva anche una linea non ancora corretta."],
        ["Chiudi", "Chiude la finestra; se ci sono modifiche non applicate chiede "
         "cosa farne."],
    ], [4.0, 12.3]),
    ("p", "Finché non si preme `Applica alla linea` la linea in uso non cambia."),

    ("h2", "4.4  [4] Fattibilita'"),
    ("p", "Un **controllo preventivo** che dura pochi millesimi di secondo e non usa "
          "il solutore. Apre una finestra con i limiti inferiori del takt time, "
          "vasca per vasca e per numero di carroponti."),
    ("img", "06_fattibilita", 9.5, "La finestra Fattibilita'."),
    ("b", "Se il limite supera il takt time richiesto la linea è **certamente "
          "impossibile**: inutile lanciare il calcolo, vanno cambiati i dati."),
    ("b", "Se non lo supera (come nell'esempio: «NON ESCLUSA») la linea "
          "**potrebbe** funzionare: lo dirà `Calcola auto`."),
    ("p", "La finestra indica anche la vasca **collo di bottiglia** e quanti "
          "carroponti servono almeno. Si chiude con `Chiudi`."),

    ("h2", "4.5  [5] Calcola auto"),
    ("p", "Il programma cerca da solo il **numero minimo di carroponti** e la "
          "suddivisione migliore della linea fra loro, e costruisce il ciclogramma. "
          "Al termine lo verifica e, se serve, rende esatto il punto di avvio."),
    ("img", "07_calcolo_in_corso", 14.0,
     "Calcolo in corso: sono accesi solo Ferma e Pausa, la barra in basso dice a che "
     "punto è."),
    ("p", "Durante il calcolo:"),
    ("b", "la finestra **non si blocca**, ma quasi tutti i pulsanti si spengono e la "
          "scheda Ciclogramma resta chiusa;"),
    ("b", "la barra di stato dice con quanti carroponti sta provando, il tentativo "
          "in corso sul totale, una stima del tempo che manca e **quante soluzioni "
          "ha già trovato**, ad esempio:"),
    ("code", "2 carroponti: tentativo 3 di 5 - ancora circa 2,4 s - 1 soluzione "
             "trovata, scarto dai teorici = 12.62 s: fermando ora resta quella"),
    ("b", "se con un certo numero di carroponti non trova niente riparte con un "
          "carroponte in più, e il conteggio dei tentativi ricomincia: è normale;"),
    ("b", "la stima del tempo è indicativa: un tentativo che non trova niente è "
          "molto più rapido di uno che trova una soluzione."),
    ("p", "La durata va da pochi secondi a parecchi minuti, secondo la linea. Finito "
          "il calcolo compare il ciclogramma, con il verdetto e il Riepilogo."),
    ("img", "08_calcolo_auto_riepilogo", 14.0,
     "Calcolo finito: ciclogramma, verdetto verde, Riepilogo."),

    ("h2", "4.6  [6] Ferma"),
    ("p", "Interrompe `Calcola auto` (e `Ottimizza con questi carroponti`). È "
          "acceso solo mentre il calcolo gira; il calcolo si ferma entro mezzo "
          "secondo."),
    ("b", "Se era già stata trovata almeno una soluzione, la mostra e la verifica; "
          "il Riepilogo dice che **non è dimostrata ottima** (è la migliore fra le "
          "suddivisioni provate fino a quel momento)."),
    ("b", "Se non era stato trovato niente, il ciclogramma che c'era a schermo "
          "resta com'era e la barra scrive «Calcolo interrotto»."),
    ("p", "Fermare non vuol dire che la linea sia impossibile: vuol dire solo che "
          "non si è aspettato. Per sapere se fermarsi conviene, guardare nella "
          "barra di stato quante soluzioni sono già state trovate: se sono zero, "
          "fermando non resta niente."),

    ("h2", "4.7  [7] Pausa / Riprendi"),
    ("p", "Sospende il calcolo automatico per liberare il computer, e lo fa "
          "ripartire più tardi: l'etichetta diventa `Riprendi`. Il tentativo in "
          "corso alla ripresa si rifà da capo; quelli già conclusi e le soluzioni "
          "trovate restano. Il tempo passato in pausa non conta nella durata del "
          "calcolo. Il programma deve restare aperto; `Ferma` funziona anche in "
          "pausa. Nelle rifiniture finali del calcolo il pulsante è spento."),

    ("h2", "4.8  [8] Calcola man"),
    ("p", "Butta via il ciclogramma corrente e prepara la **composizione a mano**: "
          "tempi in vasca uguali ai teorici della ricetta, takt time teorico, e "
          "**nessun trasporto assegnato** a nessun carroponte. Si passa subito "
          "alla pagina di modifica e alla scheda Ciclogramma. La procedura "
          "completa è al paragrafo 8.3."),

    ("h2", "4.9  [9] Modifica / Fine modifica"),
    ("p", "Apre alla modifica il ciclogramma che c'è (calcolato, composto a mano o "
          "riaperto da file): il grafico passa alla pagina di modifica e si "
          "accende la scheda **Ciclogramma**. Premere `Modifica` non cambia "
          "niente: è il passaggio obbligato per poter intervenire."),
    ("p", "Con la modifica aperta il pulsante diventa `Fine modifica`: chiude la "
          "scheda e riporta il grafico al ciclogramma. Così un risultato non si "
          "altera per sbaglio con un clic di troppo."),
    ("tab", ["situazione", "scheda Ciclogramma"], [
        ["linea appena aperta", "chiusa (non c'è niente da modificare)"],
        ["dopo Calcola auto", "chiusa (c'è un risultato da leggere)"],
        ["dopo Calcola man o Modifica", "aperta"],
        ["dopo Fine modifica", "chiusa"],
        ["mentre il calcolo gira", "chiusa, sempre"],
    ], [7.0, 9.3]),

    ("h2", "4.10  [10] Simulazione"),
    ("p", "Apre una finestra a parte in cui la linea si vede **di fronte e in "
          "movimento**. Si accende solo quando c'è un ciclogramma. Vedi 8.6."),

    ("h2", "4.11  [11] Avvio 1 di N"),
    ("p", "La **linea nera verticale** sul ciclogramma è il **punto di avvio**: un "
          "istante in cui tutti i carroponti sono fermi, con il gancio in basso, e "
          "nessuno sta sul carico o sullo scarico. Da lì la linea si può mettere in "
          "marcia."),
    ("p", "Di solito gli istanti adatti sono più d'uno, tutti equivalenti: il "
          "numero sul pulsante dice quanti ce ne sono. Ogni pressione sposta la "
          "linea nera sul successivo (dopo l'ultimo torna al primo) e il Riepilogo "
          "riscrive dove si trova ciascun carroponte. Quale convenga lo sa chi "
          "conosce l'impianto. Il pulsante è spento se il punto di avvio è uno "
          "solo."),
    ("img", "14_avvio_2", 14.0,
     "Dopo una pressione su Avvio: la linea nera si è spostata sul secondo dei "
     "quattro istanti possibili («avvio 2/4»)."),
    ("p", "Il punto di avvio che si sta guardando è quello che finisce nell'Excel e "
          "nell'immagine quando si salva."),

    ("h2", "4.12  [12] Allinea avvio"),
    ("p", "Se non esiste un istante in cui tutti i carroponti sono fermi in basso, "
          "la linea nera porta la scritta *avvio (approssimato)* e il Riepilogo "
          "dice di quanti secondi si sbaglia e su quale carroponte. `Allinea "
          "avvio` sposta di qualche secondo il giro di uno o più carroponti perché "
          "l'avvio diventi esatto, restando dentro le tolleranze della ricetta."),
    ("p", "Il pulsante è acceso solo quando c'è qualcosa da allineare. "
          "`Calcola auto` lo fa già da solo; serve per i ciclogrammi composti a "
          "mano o riaperti da file. È una modifica come le altre: si annulla con "
          "`Annulla modifica`."),

    ("h2", "4.13  [13] Salva risultati..."),
    ("p", "Chiede dove salvare e scrive due file:"),
    ("b", "**nome_risultati.xlsx** — il referto dei risultati, che contiene anche la "
          "linea e il ciclogramma: si riapre con `Apri linea...` per riprendere il "
          "lavoro;"),
    ("b", "**nome_risultati.png** — l'immagine del ciclogramma (sempre il "
          "ciclogramma, anche se si stava guardando la pagina di modifica)."),
    ("p", "Si accende quando c'è un ciclogramma. Se la verifica non era ancora stata "
          "fatta, la fa prima di salvare. Il file della linea di partenza non viene "
          "mai toccato."),

    ("pagina",),
    ("h1", "5. Il grafico"),
    ("p", "Il grafico ha due modi di disegnare, e non c'è niente da scegliere: lo "
          "decide il modo in cui ci si è arrivati."),
    ("tab", ["disegno", "quando", "cosa mostra"], [
        ["Ciclogramma", "dopo Calcola auto, dopo Ottimizza con questi carroponti, "
         "dopo Fine modifica", "le traiettorie dei carroponti su due cicli"],
        ["Modifica", "dopo Calcola man e dopo Modifica",
         "il percorso dei pezzi in grigio, con sopra il giro dei carroponti: è il "
         "foglio su cui si clicca per assegnare"],
    ], [3.0, 6.5, 6.8]),

    ("h2", "5.1 Leggere il ciclogramma"),
    ("b", "**In orizzontale il tempo**, in secondi; **in verticale la posizione** "
          "lungo la rotaia: ogni riga è una vasca, con nome e quota."),
    ("b", "Il disegno ripete **due cicli** di seguito, separati da una linea "
          "puntinata, così si vede che il giro si richiude."),
    ("b", "Ogni **colore** è un carroponte (legenda in alto a destra)."),
    ("b", "Tratti **obliqui**: il carroponte si sposta. Tratti **piatti**: è fermo "
          "sopra una vasca, a prendere, depositare o aspettare."),
    ("b", "I **pallini** segnano gli istanti in cui succede qualcosa: aggancio e "
          "sgancio del telaio, partenza e arrivo di ogni spostamento."),
    ("b", "Le piccole **frecce** ↑ e ↓ indicano che il gancio sale o scende mentre "
          "il carro è fermo."),
    ("b", "La **linea grigia** sulla riga di una vasca è il pezzo immerso."),
    ("b", "La **linea nera verticale** è il punto di avvio (vedi 4.11)."),

    ("h2", "5.2 La pagina di modifica"),
    ("img", "10_modifica", 14.0,
     "La pagina di modifica di un ciclogramma calcolato, con la scheda Ciclogramma aperta."),
    ("p", "Sotto, in **grigio sottile**, il percorso dei pezzi (il «pettine»): "
          "tutti i trasporti, ripetuti a ogni takt time. Sopra, nel colore di ogni "
          "carroponte, il giro che fa. Un trasporto che nessuno ha ancora preso "
          "resta grigio; appena lo si assegna prende il colore del carroponte. Il "
          "**rientro a vuoto** è tratteggiato."),

    ("h2", "5.3 Gesti sul grafico (solo nella pagina di modifica)"),
    ("tab", ["gesto", "effetto"], [
        ["Clic su un trasporto", "Lo assegna al carroponte attivo (scelto nella "
         "scheda Ciclogramma). Un secondo clic glielo toglie e il trasporto torna grigio."],
        ["Trascinare l'inizio di un trasporto", "Allunga o accorcia la sosta nella "
         "vasca da cui il pezzo parte. Una guida arancione mostra dove finirà."],
        ["Clic su un punto di passaggio (rombo)", "Lo assegna al carroponte attivo, "
         "o glielo toglie."],
        ["Trascinare un punto di passaggio", "Lo sposta."],
    ], [5.5, 10.8]),
    ("p", "Non viene mai rifiutato niente, tranne un'assegnazione che costringerebbe "
          "due carroponti a **scavalcarsi** sulla rotaia: in quel caso la barra di "
          "stato scrive «Non si può:» con il motivo."),

    ("h2", "5.4 Ingrandire e spostarsi"),
    ("img", "barra_grafico", 6.0, "La barra sotto al grafico."),
    ("tab", ["comando", "cosa fa"], [
        ["Casetta", "Torna a inquadrare tutto."],
        ["Frecce ← →", "Ripercorrono le inquadrature precedenti e successive."],
        ["Croce", "Sposta l'inquadratura trascinando con il mouse."],
        ["Lente", "Ingrandisce il rettangolo che si disegna con il mouse."],
        ["Dischetto", "Salva l'immagine così come la si vede, ingrandimento compreso."],
        ["Rotella del mouse", "Ingrandisce/rimpicciolisce i **tempi**, centrata sul "
         "puntatore. Con Maiusc agisce sulle posizioni, con Ctrl su tutti e due gli assi."],
    ], [4.0, 12.3]),
    ("p", "Quando la croce o la lente sono premute il clic serve a navigare: "
          "assegnare e trascinare sono sospesi finché non le si rilascia (si "
          "ripreme lo stesso pulsante). Muovendo il mouse sul grafico, la barra di "
          "stato mostra il tempo e la posizione esatti sotto il puntatore. "
          "L'ingrandimento resta anche dopo una modifica."),

    ("pagina",),
    ("h1", "6. Il verdetto"),
    ("p", "La striscia colorata in alto a destra è l'informazione più importante, "
          "ed è sempre in vista:"),
    ("img", "verdetto_grigio", 10.0, "Grigio: nessun ciclogramma."),
    ("img", "verdetto_verde", 10.0,
     "Verde: VERIFICA SUPERATA, con takt time e pezzi/ora. Il ciclogramma è valido "
     "e rispetta tutte le tolleranze."),
    ("img", "verdetto_rosso", 10.0,
     "Rosso: la verifica ha trovato errori; il dettaglio è nella scheda Verifica."),
    ("img", "verdetto_arancio", 10.0,
     "Arancio: INCOERENZE. Il ciclogramma così non si può realizzare (ad esempio "
     "ci sono trasporti non ancora assegnati); il motivo è scritto nel Riepilogo."),
    ("img", "verdetto_azzurro", 10.0,
     "Azzurro: IN COMPOSIZIONE. La verifica non è ancora stata chiesta: si preme "
     "Verifica adesso nella scheda Ciclogramma."),
    ("p", "Dopo un calcolo automatico, e dopo che `Verifica adesso` è stato premuto "
          "una volta, la verifica **si aggiorna da sola** a ogni modifica: il "
          "verdetto cambia colore appena si tocca qualcosa."),

    ("h1", "7. Le schede"),
    ("h2", "7.1 Riepilogo"),
    ("p", "Testo che descrive il ciclogramma corrente:"),
    ("b", "**Origine** (calcolo automatico, composto da zero, riaperto da file, "
          "«poi modificato a mano») e **tempo di calcolo**;"),
    ("b", "**takt time** e **produttività** in pezzi/ora;"),
    ("b", "**scarto dai teorici**: la somma, in secondi, di quanto ogni vasca si "
          "scosta dal suo tempo teorico;"),
    ("b", "quanti **carroponti** e quali mosse fa ciascuno;"),
    ("b", "la tabella dei **tempi in vasca**: teorico, effettivo, scarto, sgocciolamento;"),
    ("b", "il **punto di avvio** e dove si trova ogni carroponte in quell'istante;"),
    ("b", "la **distanza minima** raggiunta fra i carroponti contro quella richiesta;"),
    ("b", "l'esito della **verifica** (errori, avvisi, note)."),
    ("p", "Se il calcolo non trova soluzioni, il Riepilogo dice cosa è stato provato "
          "e, quando riesce a stabilirlo, **perché** non si riesce (vedi capitolo 9)."),

    ("h2", "7.2 Ciclogramma"),
    ("p", "È la scheda in cui si modifica. È aperta solo dopo `Calcola man` o "
          "`Modifica`. La parte bassa si raggiunge scorrendo con la rotella."),
    ("img", "11_modifica_in_fondo", 14.0, "La scheda Ciclogramma, scorsa fino in fondo."),
    ("tab", ["elemento", "cosa fa"], [
        ["Takt time [s] + Applica", "Cambia il takt time (anche con Invio)."],
        ["Carroponti", "Numero di carroponti. Su un ciclogramma con le mosse già "
         "assegnate le ridistribuisce subito fra i carroponti, a blocchi contigui, senza "
         "solutore. Componendo da zero aggiunge o toglie un carroponte disponibile."],
        ["attivo", "Il carroponte a cui va il prossimo clic su un trasporto o su un "
         "punto di passaggio."],
        ["Tempi in vasca", "Per ogni vasca: tempo attuale, teorico, scarto, minimo e "
         "massimo ammessi. Doppio clic sul tempo per cambiarlo (Invio conferma, Esc "
         "annulla). Si possono sforare minimo e massimo: lo dirà la verifica."],
        ["Assegnazione", "Ogni trasporto (da vasca → a vasca) e il carroponte che lo "
         "fa. Doppio clic per passarlo al carroponte successivo; dopo l'ultimo torna "
         "«-», non assegnato."],
        ["Punti di passaggio", "Scrivere tempo [s] e posizione [mm] e premere Aggiungi "
         "(o Invio). Il punto compare sul grafico come rombo vuoto. Togli (o Canc) "
         "cancella i punti selezionati. Doppio clic su una riga = clic sul rombo."],
        ["Annulla modifica", "Torna indietro di un passo; si può premere più volte."],
        ["Verifica adesso", "Fa la verifica indipendente e porta alla scheda Verifica. "
         "Da quel momento la verifica si aggiorna da sola."],
        ["Ottimizza con questi carroponti", "Fa lavorare il solutore per trovare la "
         "suddivisione migliore con il numero di carroponti scelto qui sopra. "
         "Butta via le modifiche fatte a mano. Si ferma con Ferma, come Calcola auto."],
    ], [4.5, 11.8]),

    ("h2", "7.3 Verifica"),
    ("img", "09_verifica", 14.0, "La scheda Verifica dopo un calcolo riuscito: una sola nota."),
    ("p", "L'elenco dei rilievi del verificatore indipendente, con colonne "
          "gravità, tipo e descrizione. **Un clic su una riga** mostra la "
          "descrizione per intero. Il numero sulla linguetta, ad esempio "
          "«Verifica (2)», dice quanti rilievi ci sono."),
    ("tab", ["gravità", "colore", "significato"], [
        ["ERRORE", "rosso", "Il ciclogramma non è utilizzabile così (collisione, "
         "tempo in vasca fuori tolleranza, interblocco...)."],
        ["avviso", "arancio", "Qualcosa che il programma non sa vincolare e va "
         "guardato a mano."],
        ["nota", "grigio", "Informazione. Ad esempio: una vasca a due posti lavora "
         "con due pezzi dentro, che è normale."],
    ], [2.5, 2.3, 11.5]),
    ("p", "Le descrizioni dicono anche **dove**: quali carroponti, a che istante, "
          "sopra quale vasca."),

    ("pagina",),
    ("h1", "8. Come si lavora"),
    ("h2", "8.1 Calcolo automatico"),
    ("n", "`Apri linea...` e scegliere il file."),
    ("n", "(Facoltativo) `Fattibilita'`: se dice che la linea è impossibile, "
          "correggere i dati prima di calcolare."),
    ("n", "`Calcola auto` e aspettare; per interrompere `Ferma`, per sospendere `Pausa`."),
    ("n", "Leggere il verdetto: verde = valido."),
    ("n", "Scegliere il punto di avvio con `Avvio 1 di N`."),
    ("n", "`Salva risultati...`."),

    ("h2", "8.2 Ritoccare un ciclogramma"),
    ("n", "Premere `Modifica`: si apre la scheda Ciclogramma e il grafico passa alla "
          "pagina di modifica."),
    ("n", "Cambiare un tempo in vasca (doppio clic nella tabella, oppure "
          "trascinando l'inizio di un trasporto sul grafico), il takt time o "
          "l'assegnazione di un trasporto."),
    ("n", "Guardare subito il verdetto: la verifica si aggiorna da sola."),
    ("n", "Se qualcosa non va, `Annulla modifica`."),
    ("n", "`Fine modifica` per tornare al ciclogramma."),
    ("img", "15_modifica_con_errori", 14.0,
     "Un tempo in vasca accorciato troppo: il verdetto diventa rosso e la scheda "
     "Verifica dice che l'interblocco fra i carroponti 1 e 2 non è rispettato."),

    ("h2", "8.3 Comporre un ciclogramma a mano"),
    ("n", "Premere `Calcola man`. Il grafico mostra il pettine tutto grigio: "
          "nessun trasporto è assegnato. Il verdetto è arancio, perché ci sono "
          "trasporti senza carroponte."),
    ("n", "Nella scheda Ciclogramma scegliere il numero di `Carroponti` e il "
          "carroponte `attivo`."),
    ("n", "Fare clic sui trasporti che deve fare il carroponte attivo; cambiare "
          "carroponte attivo e continuare. Un secondo clic toglie l'assegnazione."),
    ("n", "Regolare tempi in vasca e takt time se serve."),
    ("n", "Quando tutto è assegnato il verdetto diventa azzurro: premere "
          "`Verifica adesso`."),
    ("img", "13b_calcola_man", 14.0, "Subito dopo Calcola man: tutto grigio, nessun trasporto assegnato."),
    ("img", "13c_calcola_man_parziale", 14.0,
     "Composizione a metà: le prime due mosse al carroponte 1 (rosso), la terza al 2 "
     "(blu); le altre sono ancora grigie."),
    ("img", "13d_in_composizione", 14.0,
     "Tutti i trasporti assegnati: verdetto azzurro, in attesa di Verifica adesso."),

    ("h2", "8.4 Punti di passaggio"),
    ("p", "Servono a decidere **dove e quando** passa un carroponte durante un "
          "rientro a vuoto (ad esempio per spostare dove aspetta)."),
    ("n", "Nella scheda Ciclogramma, sotto Punti di passaggio, scrivere tempo [s] e "
          "posizione [mm] e premere `Aggiungi`."),
    ("n", "Il punto compare sul grafico come **rombo vuoto**. Con un clic lo si dà "
          "al carroponte attivo (il rombo si colora); un altro clic glielo toglie."),
    ("n", "Trascinarlo per spostarlo; `Togli` o Canc per cancellarlo."),
    ("p", "Due punti alla stessa posizione con tempi diversi sono una sosta. I punti "
          "si salvano con i risultati e si ritrovano riaprendo il file."),

    ("h2", "8.5 Scegliere il punto di avvio"),
    ("p", "Premere `Avvio 1 di N` più volte e guardare, per ogni posizione della "
          "linea nera, dove si fermano i carroponti (lo scrive il Riepilogo). Ci si "
          "ferma su quello più comodo per l'impianto, poi si salva. Se l'avvio è "
          "approssimato, `Allinea avvio`."),

    ("h2", "8.6 Guardare la linea in movimento"),
    ("img", "12_simulazione", 15.0, "La finestra Simulazione."),
    ("p", "`Simulazione` apre la linea vista di fronte: le vasche in fila, la rotaia, "
          "i carroponti con il loro numero e colore, i telai che vengono presi, "
          "sollevati, spostati e immersi. Parte da sola, **a tempo reale**, dal "
          "punto di avvio scelto. Sotto il disegno è scritto cosa sta facendo "
          "ciascun carroponte."),
    ("img", "comandi_simulazione", 7.5, "I comandi della simulazione."),
    ("tab", ["comando", "cosa fa"], [
        ["◀◀", "Indietro di un fotogramma; tenuto premuto scorre all'indietro. "
         "Anche freccia ←."],
        ["▶ / ❚❚", "Avvia / mette in pausa."],
        ["▶▶", "Avanti di un fotogramma; tenuto premuto scorre in avanti. Anche freccia →."],
        ["❙◀", "Torna all'inizio (al punto di avvio)."],
        ["velocita'", "Da mezza a venti volte il tempo reale. Regola anche quanto è "
         "lungo un fotogramma nel passo a passo."],
        ["cursore", "Trascinandolo si va a un istante preciso."],
    ], [3.0, 13.3]),
    ("p", "La finestra si può tenere aperta accanto a quella principale: **si "
          "aggiorna da sola** a ogni modifica del ciclogramma. Se ci sono trasporti "
          "non assegnati compare un avviso in rosso: quei pezzi si vedono spostarsi "
          "da soli."),

    ("h2", "8.7 Salvare e riprendere il lavoro"),
    ("p", "`Salva risultati...` scrive l'Excel dei risultati e l'immagine. Per "
          "riprendere un altro giorno si riapre **lo stesso Excel dei risultati** "
          "con `Apri linea...`: il ciclogramma ricompare com'era, anche se "
          "lasciato a metà. Per intervenire si preme `Modifica`."),

    ("h1", "9. Se il calcolo non trova niente"),
    ("p", "Il verdetto resta grigio e il Riepilogo spiega **cosa è stato provato** e, "
          "quando riesce a stabilirlo, **perché** non si riesce. Due parole da "
          "distinguere:"),
    ("b", "**INFEASIBLE** — dimostrato impossibile con quella suddivisione: vanno "
          "cambiati i dati della linea;"),
    ("b", "**UNKNOWN** — il tempo concesso a quel tentativo è finito prima della "
          "risposta: la soluzione potrebbe esserci, si allunga il tempo limite "
          "nei parametri."),
    ("p", "Il Riepilogo può indicare la causa e di quanto bisogna muoversi, ad "
          "esempio «il takt time è troppo stretto» o «basta portare il massimo di "
          "una vasca da 190 a 212 s». In alternativa si prova `Calcola man` e si "
          "guarda sul grafico dove il conto non torna."),

    ("h1", "10. Riepilogo dei pulsanti"),
    ("tab", ["n", "pulsante", "acceso quando"], [
        ["1", "Apri linea...", "sempre"],
        ["2", "Nuovo modello Excel...", "sempre"],
        ["3", "Dati linea...", "sempre"],
        ["4", "Fattibilita'", "c'è una linea e non si sta calcolando"],
        ["5", "Calcola auto", "c'è una linea e non si sta calcolando"],
        ["6", "Ferma", "solo durante il calcolo"],
        ["7", "Pausa / Riprendi", "solo durante la ricerca del calcolo automatico"],
        ["8", "Calcola man", "c'è una linea e non si sta calcolando"],
        ["9", "Modifica / Fine modifica", "c'è un ciclogramma"],
        ["10", "Simulazione", "c'è un ciclogramma"],
        ["11", "Avvio 1 di N", "c'è più di un punto di avvio"],
        ["12", "Allinea avvio", "l'avvio è approssimato e si può rendere esatto"],
        ["13", "Salva risultati...", "c'è un ciclogramma"],
    ], [1.0, 5.0, 10.3]),
]


# --------------------------------------------------------------------------
# Impaginazione
# --------------------------------------------------------------------------


def _testo_ricco(paragrafo, testo: str):
    """**grassetto** e `pulsante` (grassetto blu scuro)."""
    import re

    from docx.shared import RGBColor

    for pezzo in re.split(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)", testo):
        if not pezzo:
            continue
        if pezzo.startswith("**"):
            paragrafo.add_run(pezzo[2:-2]).bold = True
        elif pezzo.startswith("`"):
            r = paragrafo.add_run(pezzo[1:-1])
            r.bold = True
            r.font.color.rgb = RGBColor(0x1C, 0x45, 0x87)
        elif pezzo.startswith("*") and pezzo.endswith("*") and len(pezzo) > 2:
            paragrafo.add_run(pezzo[1:-1]).italic = True
        else:
            paragrafo.add_run(pezzo)


def _sfondo_cella(cella, colore: str):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    tcPr = cella._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), colore)
    tcPr.append(shd)


def _immagine(nome: str, cartelle=None) -> str:
    for cartella in cartelle or (ANNOTATE, IMG):
        p = os.path.join(cartella, nome + ".png")
        if os.path.exists(p):
            return p
    raise FileNotFoundError(nome)


def scrivi_documento(
    contenuto=None,
    uscita=USCITA,
    sottotitolo="Manuale operatore dell'interfaccia grafica",
    descrizione=(
        "Pulsanti, pagine e finestre del programma.\n"
        "La compilazione della linea è descritta in un documento a parte."
    ),
    cartelle_img=None,
    etichetta_nota="Da compilare  ",
):
    """Impagina `contenuto` (default: CONTENUTO) e lo salva in `uscita`.

    I parametri servono a riusare la stessa impaginazione per gli altri
    manuali (genera_manuale_excel.py): stessa copertina, stesso indice, stesse
    voci."""
    from docx import Document
    from docx.enum.section import WD_ORIENT  # noqa: F401
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    sezione = doc.sections[0]
    sezione.page_width, sezione.page_height = Cm(21.0), Cm(29.7)
    for lato in ("left_margin", "right_margin"):
        setattr(sezione, lato, Cm(2.2))
    sezione.top_margin = sezione.bottom_margin = Cm(2.0)

    normale = doc.styles["Normal"]
    normale.font.name = "Calibri"
    normale.font.size = Pt(10.5)
    normale.paragraph_format.space_after = Pt(6)
    for nome, dim in (("Heading 1", 16), ("Heading 2", 12.5), ("Heading 3", 11)):
        st = doc.styles[nome]
        st.font.name = "Calibri"
        st.font.size = Pt(dim)
        st.font.color.rgb = RGBColor(0x1F, 0x2A, 0x36)

    # -- copertina --------------------------------------------------------
    logo = os.path.join(RADICE, "risorse", "icona.png")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(90)
    if os.path.exists(logo):
        p.add_run().add_picture(logo, width=Cm(4.5))
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("CraneStrike")
    r.bold, r.font.size = True, Pt(32)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(sottotitolo)
    r.font.size = Pt(16)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    r = p.add_run(descrizione)
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    imel = os.path.join(RADICE, "risorse", "logo_imel.png")
    if os.path.exists(imel):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(120)
        p.add_run().add_picture(imel, width=Cm(4.0))
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # -- indice (campo: si aggiorna in Word con F9) -----------------------
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc.add_heading("Indice", level=1)
    p = doc.add_paragraph()
    r = p.add_run()
    for tipo, testo in (("begin", None), (None, 'TOC \\o "1-2" \\h \\z \\u'),
                        ("separate", None), (None, None), ("end", None)):
        if tipo:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tipo)
            r._r.append(el)
        elif testo:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = testo
            r._r.append(el)
        else:
            t = OxmlElement("w:t")
            t.text = "Aprire il documento in Word e premere F9 per aggiornare l'indice."
            r._r.append(t)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # -- corpo --------------------------------------------------------------
    n_figura = 0
    numero, tipo = 0, None
    for voce in contenuto or CONTENUTO:
        precedente, tipo = tipo, voce[0]
        if tipo in ("h1", "h2", "h3"):
            doc.add_heading(voce[1], level=int(tipo[1]))
        elif tipo == "p":
            _testo_ricco(doc.add_paragraph(), voce[1])
        elif tipo == "b":
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
            _testo_ricco(p, voce[1])
        elif tipo == "n":
            # Numerazione scritta a mano: lo stile "List Number" di Word
            # continua il conto da un elenco all'altro, e ogni procedura deve
            # ripartire da 1.
            numero = numero + 1 if precedente == "n" else 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.9)
            p.paragraph_format.first_line_indent = Cm(-0.6)
            p.paragraph_format.space_after = Pt(3)
            p.add_run(f"{numero}.\t")
            p.paragraph_format.tab_stops.add_tab_stop(Cm(0.9))
            _testo_ricco(p, voce[1])
        elif tipo == "code":
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            r = p.add_run(voce[1])
            r.font.name = "Consolas"
            r.font.size = Pt(8.5)
        elif tipo == "nota":
            tab = doc.add_table(rows=1, cols=1)
            tab.alignment = WD_TABLE_ALIGNMENT.CENTER
            cella = tab.rows[0].cells[0]
            _sfondo_cella(cella, "FFF4D6")
            cella.paragraphs[0].add_run(etichetta_nota).bold = True
            _testo_ricco(cella.paragraphs[0], voce[1])
            doc.add_paragraph()
        elif tipo == "img":
            _, nome, larghezza, didascalia = voce
            n_figura += 1
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_before = Pt(6)
            p.add_run().add_picture(_immagine(nome, cartelle_img), width=Cm(larghezza))
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(f"Figura {n_figura} – ")
            r.bold, r.font.size = True, Pt(9)
            r = p.add_run(didascalia)
            r.italic, r.font.size = True, Pt(9)
            r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
        elif tipo == "tab":
            _, intestazione, righe, larghezze = voce
            tab = doc.add_table(rows=1 + len(righe), cols=len(intestazione))
            tab.style = "Table Grid"
            tab.alignment = WD_TABLE_ALIGNMENT.CENTER
            for i, (cella, testo) in enumerate(zip(tab.rows[0].cells, intestazione)):
                _sfondo_cella(cella, "DCE6F1")
                run = cella.paragraphs[0].add_run(testo)
                run.bold, run.font.size = True, Pt(9.5)
            for riga, valori in zip(tab.rows[1:], righe):
                for cella, testo in zip(riga.cells, valori):
                    par = cella.paragraphs[0]
                    par.paragraph_format.space_after = Pt(0)
                    _testo_ricco(par, testo)
                    for run in par.runs:
                        run.font.size = Pt(9.5)
                    if testo in PULSANTI or testo.split(" /")[0] in PULSANTI:
                        for run in par.runs:
                            run.bold = True
            for riga in tab.rows:
                for cella, cm in zip(riga.cells, larghezze):
                    cella.width = Cm(cm)
            doc.add_paragraph()
        elif tipo == "pagina":
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        else:
            raise ValueError(f"voce sconosciuta: {tipo}")

    doc.save(uscita)
    return n_figura


def main() -> int:
    if not os.path.exists(os.path.join(IMG, "regioni.json")):
        print("Mancano le schermate: lancia prima strumenti/cattura_schermate.py")
        return 1
    prepara_immagini()
    n = scrivi_documento()
    print(f"Scritto {os.path.relpath(USCITA, RADICE)} ({n} figure)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
