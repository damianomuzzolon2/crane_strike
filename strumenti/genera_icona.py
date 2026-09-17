"""
genera_icona.py
---------------
Ricava le icone del programma da `doc/icon.png`.

    python strumenti/genera_icona.py

L'immagine di partenza e' un quadrato 1024x1024 SENZA trasparenza: fuori dal
quadrato arrotondato c'e' del bianco, che sulla barra delle applicazioni e nel
titolo della finestra comparirebbe come un riquadro bianco attorno all'icona.
Lo si rende trasparente riempiendo a partire dai quattro angoli: il bianco del
carroponte, dentro, non tocca il bordo e resta com'e'.

Scrive in `risorse/`:
  - icona.ico   per l'eseguibile e per la finestra su Windows, con dentro le
                misure fra cui Windows sceglie secondo dove la mostra;
  - icona.png   256 px, per la finestra dove un .ico non si puo' usare.

Si rilancia solo se cambia `doc/icon.png`: i due file prodotti stanno nel
repository, e il programma non ha bisogno di Pillow per usarli.

LE MISURE PICCOLE NON SI RICAVANO DALL'IMMAGINE: SI RIDISEGNANO. Rimpicciolire
1024 px a 16 fa cadere ogni tratto a cavallo fra due pixel, e i tratti sono
sottili -- la V e le cornici rosse misurano 36 px su 1024, cioe' mezzo pixel a
16. Il filtro li mescola col grigio del fondo e quello che resta e' una macchia
rosata, che nel titolo della finestra si vede come un'icona sfocata. Fino a
`MISURA_DISEGNATA` la figura si ridisegna a quella misura con le quote di
`doc/icon.png` (misurate una volta, qui sotto), portando i bordi sulla griglia
dei pixel e dando ai tratti almeno un pixel e mezzo. Se il disegno cambia,
vanno rimisurate anche quelle.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

RADICE = Path(__file__).resolve().parent.parent
SORGENTE = RADICE / "doc" / "icon.png"
USCITA = RADICE / "risorse"

# Le misure che Windows chiede davvero: 16 e 24 nel titolo della finestra e
# nei menu, 32 e 48 sulla barra e sul desktop, 256 nelle cartelle a icone
# grandi. Mancando la misura giusta la ricava lui, e rimpicciolendo 256 a 16
# un disegno con linee sottili diventa una macchia.
MISURE = [16, 24, 32, 48, 64, 128, 256]

# Fino a questa misura compresa l'icona si ridisegna (vedi sopra); oltre, il
# ridimensionamento dell'immagine originale e' gia' nitido.
MISURA_DISEGNATA = 48

# Quanto un pixel puo' scostarsi dal bianco ed essere ancora "fuori": il bordo
# del quadrato arrotondato e' sfumato, e con zero resterebbe un alone chiaro.
SOGLIA = 60

# Colori e quote del disegno, in pixel di `doc/icon.png` (lato 1024).
GRIGIO = (80, 83, 88, 255)
BIANCO = (255, 255, 255, 255)
ROSSO = (216, 11, 13, 255)
TRAVE = (64, 126, 960, 177)
CARRELLO = (372, 109, 652, 126)
STELO = (467, 177, 558, 466)
BOZZELLO = (373, 477, 654, 567)
V = [(325, 350), (512, 756), (699, 350)]  # asse del tratto, 36 px di spessore
CORNICI_X = [(165, 312), (712, 859)]  # sinistra, destra
CORNICI_Y = [(258, 407), (699, 842)]  # alto, basso
SPESSORE_CORNICI = 27

# Il disegno si fa a questa scala e poi si riduce facendo la media: i bordi
# allineati alla griglia restano netti, le diagonali della V e gli angoli
# arrotondati vengono sfumati quanto basta.
SOVRACAMPIONAMENTO = 8


def disegna_piccola(misura: int) -> Image.Image:
    """L'icona ridisegnata a `misura` px, con i bordi sui pixel.

    A 16 px le cornici rosse si tolgono: con un pixel di spessore stanno a un
    pixel dalla V e il tutto diventa un groviglio rosso. Senza, la figura si
    legge ancora -- carroponte e V -- ed e' quella che conta riconoscere."""
    s = SOVRACAMPIONAMENTO
    lato = misura * s
    immagine = Image.new("RGBA", (lato, lato), (0, 0, 0, 0))
    penna = ImageDraw.Draw(immagine)

    def px(quota: float) -> int:
        return round(quota / 1024 * misura)

    def rettangolo(x0, y0, x1, y1, colore):
        # almeno un pixel per lato: un tratto arrotondato a zero sparirebbe
        a, b = px(x0), max(px(x1), px(x0) + 1)
        c, d = px(y0), max(px(y1), px(y0) + 1)
        penna.rectangle([a * s, c * s, b * s - 1, d * s - 1], fill=colore)

    penna.rounded_rectangle(
        [0, 0, lato - 1, lato - 1], radius=0.19 * lato, fill=GRIGIO
    )
    rettangolo(*TRAVE, BIANCO)
    if misura >= 24:
        rettangolo(*CARRELLO, BIANCO)
    rettangolo(*STELO, BIANCO)
    rettangolo(*BOZZELLO, BIANCO)

    spessore_v = 1.5 if misura < 24 else max(2.0, 36 / 1024 * misura)
    penna.line(
        [(x / 1024 * lato, y / 1024 * lato) for x, y in V],
        fill=ROSSO,
        width=round(spessore_v * s),
        joint="curve",
    )

    if misura >= 24:
        t = max(1, px(SPESSORE_CORNICI))
        for x0, x1 in CORNICI_X:
            for y0, y1 in CORNICI_Y:
                # il tratto orizzontale sta sul bordo esterno (in alto o in
                # basso), quello verticale sul bordo esterno (a sinistra o a
                # destra): e' un angolo di inquadratura
                x = px(x0) if x0 < 512 else px(x1) - t
                y = px(y0) if y0 < 512 else px(y1) - t
                penna.rectangle(
                    [px(x0) * s, y * s, px(x1) * s - 1, (y + t) * s - 1], fill=ROSSO
                )
                penna.rectangle(
                    [x * s, px(y0) * s, (x + t) * s - 1, px(y1) * s - 1], fill=ROSSO
                )
    return immagine.resize((misura, misura), Image.BOX)


def main() -> int:
    immagine = Image.open(SORGENTE).convert("RGBA")
    larghezza, altezza = immagine.size
    for angolo in (
        (0, 0),
        (larghezza - 1, 0),
        (0, altezza - 1),
        (larghezza - 1, altezza - 1),
    ):
        ImageDraw.floodfill(immagine, angolo, (255, 255, 255, 0), thresh=SOGLIA)

    # Ogni misura si prepara qui e si passa gia' fatta: per quelle che non
    # trova fra le immagini ricevute Pillow ne ricava una da sola, e lo fa
    # partendo dall'ULTIMA della lista, non dalla piu' grande.
    fotogrammi = [
        disegna_piccola(m) if m <= MISURA_DISEGNATA
        else immagine.resize((m, m), Image.LANCZOS)
        for m in MISURE
    ]
    grande = fotogrammi[-1]

    USCITA.mkdir(exist_ok=True)
    grande.save(USCITA / "icona.png")
    grande.save(
        USCITA / "icona.ico",
        sizes=[(m, m) for m in MISURE],
        append_images=fotogrammi[:-1],
    )
    print(f"Scritte {USCITA / 'icona.ico'} e {USCITA / 'icona.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
