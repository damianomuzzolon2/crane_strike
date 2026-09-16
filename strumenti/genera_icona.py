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

# Quanto un pixel puo' scostarsi dal bianco ed essere ancora "fuori": il bordo
# del quadrato arrotondato e' sfumato, e con zero resterebbe un alone chiaro.
SOGLIA = 60


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

    USCITA.mkdir(exist_ok=True)
    immagine.resize((256, 256), Image.LANCZOS).save(USCITA / "icona.png")
    immagine.save(USCITA / "icona.ico", sizes=[(m, m) for m in MISURE])
    print(f"Scritte {USCITA / 'icona.ico'} e {USCITA / 'icona.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
