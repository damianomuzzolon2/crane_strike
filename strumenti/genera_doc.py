"""
genera_doc.py
-------------
Il motore che produce i documenti Word in `doc/`: uno per modulo (anzi, piu'
d'uno per i moduli grossi) piu' l'albero delle chiamate.

    python strumenti/genera_doc.py              # tutto
    python strumenti/genera_doc.py model        # solo doc/model/
    python strumenti/genera_doc.py --albero     # solo l'albero delle chiamate

Il testo di ogni documento sta in `strumenti/doc_contenuti/<modulo>.py`. Qui
c'e' solo la macchina: come si estrae il codice, come si impagina, come si
ricava chi chiama chi.

PERCHE' IL CODICE NON SI RICOPIA
--------------------------------
I blocchi di codice citati non sono trascritti nel testo: vengono estratti dal
sorgente al momento della generazione. Un documento non puo' quindi descrivere
un codice diverso da quello che c'e'.

Il primo generatore (quello di SOLVE_riga_per_riga.docx) citava per INTERVALLI
DI RIGHE, `(1214, 1223)`. Funziona finche' nessuno tocca il file: basta
inserire una riga piu' in alto e da li' in poi ogni citazione punta altrove,
senza che niente se ne accorga. Con nove moduli e 260 funzioni sarebbe una
trappola garantita.

Qui si cita per NOME e per ANCORE:

    ("c", "model.solve")                       tutta la funzione
    ("c", "model.solve", "if not data.zones")  da quella riga alla fine
    ("c", "model.solve", "# 1) catena", "# 2) circuito")   un tratto

Il nome viene risolto con l'AST, quindi segue la funzione dovunque finisca.
Le ancore sono pezzi di righe vere: se una non si trova, la generazione si
FERMA con un errore che dice quale documento e quale ancora. E' il punto: un
documento che non si puo' piu' generare e' un documento che qualcuno deve
aggiornare, e lo si scopre subito invece che rileggendolo fra sei mesi.
"""

from __future__ import annotations

import ast
import importlib
import os
import sys

ATTREZZI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(ATTREZZI)
DOC = os.path.join(RADICE, "doc")

# I moduli documentati. I test no: non descrivono il programma, lo provano.
MODULI = [
    "kinematics",
    "model",
    "verify",
    "excel_io",
    "plotting",
    "manuale",
    "avvio",
    "simulazione",
    "interfaccia",
    "ciclogramma",
]


# ==========================================================================
# 1. Leggere il sorgente e ritagliarlo per nome
# ==========================================================================


class Sorgente:
    """Un modulo del progetto, con il suo indice di funzioni e metodi.

    L'indice e' costruito con l'AST e usa nomi puntati: `solve`,
    `ProblemData.to_ticks`, e anche le funzioni annidate dentro un'altra
    funzione, che in questo progetto ci sono (`near_boundary.fermo`).
    """

    def __init__(self, modulo: str):
        self.modulo = modulo
        self.percorso = os.path.join(RADICE, f"{modulo}.py")
        with open(self.percorso, encoding="utf-8") as f:
            self.testo = f.read()
        self.righe = self.testo.splitlines()
        self.albero = ast.parse(self.testo)
        self.voci: dict[str, ast.AST] = {}
        self._indicizza(self.albero.body, "")

    def _indicizza(self, corpo, prefisso: str) -> None:
        for nodo in corpo:
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                nome = f"{prefisso}{nodo.name}"
                self.voci[nome] = nodo
                self._indicizza(nodo.body, f"{nome}.")

    def estensione(self, nome: str) -> tuple[int, int]:
        """Prima e ultima riga (numerate da 1) della definizione `nome`.

        Un nome vuoto vale tutto il file: serve a citare il codice che non sta
        dentro nessuna funzione, come l'autotest in coda a kinematics.py.
        """
        if not nome:
            return 1, len(self.righe)
        nodo = self.voci.get(nome)
        if nodo is None:
            simili = [v for v in self.voci if v.endswith("." + nome)
                      or v.startswith(nome + ".")]
            aiuto = f" Forse cercavi: {', '.join(sorted(simili)[:5])}." if simili else ""
            raise KeyError(
                f"in {self.modulo}.py non esiste '{nome}'.{aiuto}"
            )
        # I decoratori stanno sopra la riga del def: fanno parte della
        # definizione e vanno citati con lei (@property, @dataclass).
        inizio = nodo.lineno
        for d in getattr(nodo, "decorator_list", []):
            inizio = min(inizio, d.lineno)
        return inizio, nodo.end_lineno

    def ritaglia(self, nome: str, da: str | None = None,
                 a: str | None = None) -> tuple[int, int]:
        """L'intervallo di righe di `nome`, eventualmente ristretto.

        `da` e `a` sono pezzi di riga da cercare DENTRO la definizione. Il
        tratto va dalla prima riga che contiene `da` fino alla riga PRIMA di
        quella che contiene `a` (cosi' due blocchi consecutivi si scrivono
        con la stessa ancora di confine, senza contare righe a mano).
        """
        inizio, fine = self.estensione(nome)
        if da is not None:
            inizio = self._cerca(nome, da, inizio, fine)
        if a is not None:
            fine = self._cerca(nome, a, inizio, fine) - 1
        if fine < inizio:
            raise ValueError(
                f"{self.modulo}.{nome}: l'ancora finale '{a}' viene prima "
                f"di quella iniziale '{da}'."
            )
        return inizio, fine

    def _cerca(self, nome: str, ancora: str, inizio: int, fine: int) -> int:
        """La prima riga fra `inizio` e `fine` che corrisponde all'ancora.

        Prima si cerca una riga UGUALE all'ancora (a meno degli spazi in
        coda), poi, se non c'e', una che la contenga. L'ordine conta: con la
        sola sottostringa, '    else:' verrebbe trovato dentro
        '        else:', e un blocco annidato si prenderebbe il posto di
        quello esterno. Con l'uguaglianza si scrive l'ancora con la sua
        indentazione e si punta esattamente al ramo che si vuole.
        """
        for n in range(inizio, fine + 1):
            if self.righe[n - 1].rstrip() == ancora:
                return n
        for n in range(inizio, fine + 1):
            if ancora in self.righe[n - 1]:
                return n
        raise ValueError(
            f"{self.modulo}.{nome}: l'ancora '{ancora}' non compare fra le "
            f"righe {inizio} e {fine}. Il codice e' cambiato: aggiorna il "
            f"documento invece di lasciarlo citare righe a caso."
        )

    def codice(self, inizio: int, fine: int) -> str:
        """Le righe da `inizio` a `fine`, col loro numero davanti."""
        return "\n".join(f"{n:5d}  {self.righe[n - 1]}"
                         for n in range(inizio, fine + 1))

    def firma(self, nome: str) -> str:
        """La riga del `def`, ripulita, per i titoli e gli elenchi."""
        nodo = self.voci[nome]
        riga = self.righe[nodo.lineno - 1].strip()
        return riga[4:].rstrip(":") if riga.startswith("def ") else riga

    def docstring(self, nome: str) -> str:
        return ast.get_docstring(self.voci[nome]) or ""


_APERTI: dict[str, Sorgente] = {}


def sorgente(modulo: str) -> Sorgente:
    if modulo not in _APERTI:
        _APERTI[modulo] = Sorgente(modulo)
    return _APERTI[modulo]


# ==========================================================================
# 2. Chi chiama chi
# ==========================================================================


class Chiamate:
    """Estrae dall'AST le chiamate fra funzioni, dentro e fra i moduli.

    Non e' un'analisi di flusso: e' una lettura sintattica. Riconosce quattro
    forme, che coprono tutto quello che questo progetto usa:

        pippo()              funzione dello stesso modulo, o importata per
                             nome (`from model import solve`)
        self.pippo()         metodo della classe che racchiude la chiamata
        manuale.pippo()      funzione di un modulo importato intero
        data.pippo()         metodo: certo se `data` porta un'annotazione di
                             tipo (`data: ProblemData`), altrimenti si accetta
                             solo se quel nome di metodo e' unico in tutto il
                             progetto, e si marca INCERTO

        L'ultima e' l'unica dubbia, e viene marcata come tale invece che data
        per buona: un albero delle chiamate che inventa archi e' peggio di uno
        che ne dichiara qualcuno in meno.
    """

    def __init__(self, moduli: list[str]):
        self.moduli = moduli
        self.sorgenti = {m: sorgente(m) for m in moduli}
        # nome semplice -> [(modulo, nome puntato)], per i metodi ambigui
        self.per_nome: dict[str, list[tuple[str, str]]] = {}
        # nome di classe -> modulo dove e' definita (le classi del progetto
        # hanno nomi unici; se un giorno non lo fossero, vince la prima)
        self.classi: dict[str, str] = {}
        for m, s in self.sorgenti.items():
            for nome, nodo in s.voci.items():
                if isinstance(nodo, ast.ClassDef):
                    self.classi.setdefault(nome, m)
                    continue
                self.per_nome.setdefault(nome.split(".")[-1], []).append((m, nome))
        self.importati = {m: self._importazioni(s) for m, s in self.sorgenti.items()}
        self.archi: dict[tuple[str, str], set[tuple[str, str, bool]]] = {}
        for m in moduli:
            self._scandaglia(m)

    def _importazioni(self, s: Sorgente) -> dict[str, str]:
        """alias locale -> modulo del progetto (per gli import risolvibili)."""
        mappa = {}
        for nodo in ast.walk(s.albero):
            if isinstance(nodo, ast.ImportFrom) and nodo.module in self.moduli:
                for a in nodo.names:
                    mappa[a.asname or a.name] = nodo.module
            elif isinstance(nodo, ast.Import):
                for a in nodo.names:
                    if a.name in self.moduli:
                        mappa[a.asname or a.name] = a.name
        return mappa

    def _scandaglia(self, modulo: str) -> None:
        s = self.sorgenti[modulo]
        for nome, nodo in s.voci.items():
            if isinstance(nodo, ast.ClassDef):
                continue
            classe = nome.rsplit(".", 1)[0] if "." in nome else None
            partenza = (modulo, nome)
            self.archi.setdefault(partenza, set())
            tipi = self._annotazioni(nodo)
            for interno in ast.walk(nodo):
                if not isinstance(interno, ast.Call):
                    continue
                arrivo = self._risolvi(modulo, classe, interno.func, tipi)
                if arrivo is not None and arrivo[:2] != partenza:
                    self.archi[partenza].add(arrivo)

    @staticmethod
    def _annotazioni(nodo) -> dict[str, str]:
        """variabile -> nome di classe, dalle annotazioni di tipo scritte.

        Il progetto annota quasi sempre i parametri (`data: ProblemData`,
        `sol: Solution`), e quella e' informazione vera, gia' nel codice: usarla
        trasforma decine di chiamate "forse" in chiamate certe.
        """
        tipi = {}

        def nome_del_tipo(ann):
            # ProblemData, "ProblemData", Optional[ProblemData], ProblemData|None
            if isinstance(ann, ast.Name):
                return ann.id
            if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
                return ann.value.strip("'\" ").split("[")[0].split("|")[0].strip()
            if isinstance(ann, ast.Subscript):
                return nome_del_tipo(ann.slice)
            if isinstance(ann, ast.BinOp):  # X | None
                return nome_del_tipo(ann.left) or nome_del_tipo(ann.right)
            if isinstance(ann, ast.Tuple) and ann.elts:
                return nome_del_tipo(ann.elts[0])
            return None

        args = getattr(nodo, "args", None)
        if args is not None:
            for a in (list(args.posonlyargs) + list(args.args)
                      + list(args.kwonlyargs)):
                if a.annotation is not None:
                    t = nome_del_tipo(a.annotation)
                    if t:
                        tipi[a.arg] = t
        for interno in ast.walk(nodo):
            if (isinstance(interno, ast.AnnAssign)
                    and isinstance(interno.target, ast.Name)
                    and interno.annotation is not None):
                t = nome_del_tipo(interno.annotation)
                if t:
                    tipi[interno.target.id] = t
        return tipi

    def _risolvi(self, modulo: str, classe: str | None, f,
                 tipi: dict[str, str] | None = None) -> tuple | None:
        s = self.sorgenti[modulo]
        if isinstance(f, ast.Name):
            if f.id in s.voci:
                return (modulo, f.id, True)
            altro = self.importati[modulo].get(f.id)
            if altro and f.id in self.sorgenti[altro].voci:
                return (altro, f.id, True)
            return None
        if isinstance(f, ast.Attribute):
            base = f.value
            if isinstance(base, ast.Name):
                if base.id == "self" and classe:
                    # sale la catena delle classi annidate finche' trova
                    pezzi = classe.split(".")
                    while pezzi:
                        cand = ".".join(pezzi + [f.attr])
                        if cand in s.voci:
                            return (modulo, cand, True)
                        pezzi.pop()
                    return None
                altro = self.importati[modulo].get(base.id)
                if altro and f.attr in self.sorgenti[altro].voci:
                    return (altro, f.attr, True)
                # `data.station_position()` con `data: ProblemData` scritto
                # nella firma: il tipo lo dice il codice, non lo indoviniamo.
                tipo = (tipi or {}).get(base.id)
                if tipo and tipo in self.classi:
                    m = self.classi[tipo]
                    cand = f"{tipo}.{f.attr}"
                    if cand in self.sorgenti[m].voci:
                        return (m, cand, True)
            # `qualcosa.metodo()`: buono solo se il nome e' unico nel progetto
            candidati = self.per_nome.get(f.attr, [])
            if len(candidati) == 1:
                m, nome = candidati[0]
                if "." in nome:  # e' davvero un metodo, non una funzione
                    return (m, nome, False)
        return None

    def uscenti(self, modulo: str, nome: str) -> list:
        return sorted(self.archi.get((modulo, nome), ()))

    def entranti(self, modulo: str, nome: str) -> list:
        dentro = []
        for (m, n), verso in self.archi.items():
            for vm, vn, certo in verso:
                if (vm, vn) == (modulo, nome):
                    dentro.append((m, n, certo))
        return sorted(dentro)

    def foglie(self, modulo: str) -> list[str]:
        return sorted(n for (m, n) in self.archi if m == modulo
                      and not self.archi[(m, n)])

    def radici(self, modulo: str) -> list[str]:
        return sorted(n for (m, n) in self.archi if m == modulo
                      and not self.entranti(m, n))

    def fra_moduli(self) -> dict[tuple[str, str], set]:
        """(da_modulo, a_modulo) -> le coppie di funzioni che lo attraversano."""
        fra = {}
        for (m, n), verso in self.archi.items():
            for vm, vn, certo in verso:
                if vm != m:
                    fra.setdefault((m, vm), set()).add((n, vn))
        return fra


# ==========================================================================
# 3. L'impaginazione Word
# ==========================================================================
#
# Le voci di CONTENUTO sono tuple (stile, ...):
#
#   ("h1", testo)   titolo del documento
#   ("h2", testo)   capitolo          ("h3", testo) paragrafo
#   ("p",  testo)   testo corrente    ("li", testo) elenco puntato
#   ("q",  testo)   riquadro giallo: le trappole, le cose da non fare
#   ("c",  "modulo.nome")                    codice: tutta la definizione
#   ("c",  "modulo.nome", da)                da quell'ancora in poi
#   ("c",  "modulo.nome", da, a)             il tratto fra le due ancore
#   ("t",  [riga, ...])                      tabella, la prima riga e' testata


def _riferimento(spec: str) -> tuple[Sorgente, str]:
    """'model.solve' -> il sorgente di model.py e il nome 'solve'.

    Il solo nome del modulo ('kinematics') vale tutto il file: si usa con le
    ancore per citare il codice fuori dalle funzioni.
    """
    modulo, _, nome = spec.partition(".")
    if modulo not in MODULI:
        raise ValueError(f"'{spec}': '{modulo}' non e' un modulo documentato.")
    return sorgente(modulo), nome


def scrivi(contenuto: list, uscita: str) -> str:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.0)
        s.top_margin = s.bottom_margin = Cm(2.0)

    normale = doc.styles["Normal"]
    normale.font.name = "Calibri"
    normale.font.size = Pt(10.5)
    normale.paragraph_format.space_after = Pt(6)

    def sfondo(par, colore):
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), colore)
        par._p.get_or_add_pPr().append(shd)

    def bordo_sinistro(par, colore):
        pbdr = OxmlElement("w:pBdr")
        left = OxmlElement("w:left")
        left.set(qn("w:val"), "single")
        left.set(qn("w:sz"), "18")
        left.set(qn("w:space"), "6")
        left.set(qn("w:color"), colore)
        pbdr.append(left)
        par._p.get_or_add_pPr().append(pbdr)

    for voce in contenuto:
        stile, resto = voce[0], voce[1:]
        if stile == "h1":
            doc.add_heading(resto[0], level=0)
        elif stile == "h2":
            doc.add_heading(resto[0], level=1)
        elif stile == "h3":
            doc.add_heading(resto[0], level=2)
        elif stile == "li":
            p = doc.add_paragraph(resto[0], style="List Bullet")
            p.paragraph_format.space_after = Pt(4)
        elif stile == "q":
            p = doc.add_paragraph()
            p.add_run(resto[0]).italic = True
            p.paragraph_format.left_indent = Cm(0.4)
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(10)
            sfondo(p, "FFF4E0")
            bordo_sinistro(p, "E0A030")
        elif stile == "c":
            src, nome = _riferimento(resto[0])
            a, b = src.ritaglia(nome, *(resto[1:3] + (None, None))[:2])
            p = doc.add_paragraph()
            r = p.add_run(src.codice(a, b))
            r.font.name = "Consolas"
            r.font.size = Pt(7.8)
            r.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.line_spacing = 1.0
            sfondo(p, "F4F6F8")
            bordo_sinistro(p, "9AA3AB")
        elif stile == "t":
            righe = resto[0]
            tab = doc.add_table(rows=len(righe), cols=len(righe[0]))
            tab.style = "Light Grid Accent 1"
            for i, riga in enumerate(righe):
                for j, cella in enumerate(riga):
                    cel = tab.cell(i, j)
                    cel.text = str(cella)
                    for par in cel.paragraphs:
                        for run in par.runs:
                            run.font.size = Pt(9)
                            if i == 0:
                                run.font.bold = True
            doc.add_paragraph()
        else:
            p = doc.add_paragraph(resto[0])
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    os.makedirs(os.path.dirname(uscita), exist_ok=True)
    doc.save(uscita)
    return uscita


# ==========================================================================
# 4. L'albero delle chiamate, costruito da solo
# ==========================================================================


def contenuto_albero(ch: Chiamate) -> list:
    c = [
        ("h1", "Albero delle chiamate"),
        ("p",
         "Chi chiama chi, in tutto il programma. Questo documento non e' "
         "scritto a mano: viene ricavato leggendo l'albero sintattico dei "
         "sorgenti a ogni generazione, quindi non puo' descrivere chiamate "
         "che non ci sono piu' ne' dimenticare quelle nuove."),
        ("q",
         "COSA NON C'E' QUI. E' una lettura SINTATTICA, non un'analisi di "
         "flusso: dice che la funzione A contiene una chiamata a B, non che "
         "la esegue sempre (potrebbe stare dentro un if che non scatta mai). "
         "Le chiamate su un oggetto qualsiasi -- `qualcosa.metodo()` -- si "
         "risolvono solo quando quel nome di metodo e' unico in tutto il "
         "progetto: sono segnate come INCERTE. Le chiamate a funzioni di "
         "libreria (OR-Tools, matplotlib, tkinter, openpyxl) non compaiono: "
         "questo albero riguarda il codice del progetto."),
    ]

    # -- la mappa fra i moduli ------------------------------------------
    fra = ch.fra_moduli()
    c += [
        ("h2", "1. Le dipendenze fra i moduli"),
        ("p",
         "Ogni riga e' un modulo che chiama funzioni di un altro. E' la "
         "verifica automatica della regola dell'architettura: le frecce "
         "vanno in una direzione sola, da chi si lancia verso il motore, "
         "e mai al contrario."),
    ]
    tab = [["modulo", "chiama", "quante funzioni"]]
    for (da, a) in sorted(fra):
        tab.append([f"{da}.py", f"{a}.py", str(len({v for _, v in fra[(da, a)]}))])
    c.append(("t", tab))

    ordine = {m: i for i, m in enumerate(MODULI)}
    # Le frecce devono scendere: un modulo puo' chiamare solo quelli che lo
    # precedono in MODULI, che e' l'ordine dichiarato in ARCHITETTURA.md.
    contrarie = [(da, a) for (da, a) in fra if ordine[da] < ordine[a]]
    if contrarie:
        c.append(("p", "Chiamate contro la direzione dichiarata: "
                       + ", ".join(f"{d} -> {a}" for d, a in contrarie)))
    else:
        c.append(("p",
                  "Nessuna chiamata risale la catena: la direzione dichiarata "
                  "in ARCHITETTURA.md e' rispettata."))

    # -- il dettaglio, modulo per modulo --------------------------------
    for i, m in enumerate(MODULI, start=2):
        s = ch.sorgenti[m]
        c.append(("h2", f"{i}. {m}.py"))
        radici = ch.radici(m)
        c.append(("p",
                  f"{len([n for n in s.voci if not isinstance(s.voci[n], ast.ClassDef)])} "
                  f"fra funzioni e metodi. Nessun altro punto del progetto "
                  f"chiama {len(radici)} di essi: sono le porte d'ingresso del "
                  f"modulo, oppure codice che non serve piu'."))
        for nome in sorted(n for n in s.voci
                           if not isinstance(s.voci[n], ast.ClassDef)):
            usc = ch.uscenti(m, nome)
            ent = ch.entranti(m, nome)
            if not usc and not ent:
                continue
            c.append(("h3", nome))
            if ent:
                c.append(("p", "Chiamata da: " + ", ".join(
                    f"{vm}.{vn}" + ("" if certo else " (incerta)")
                    for vm, vn, certo in ent)))
            else:
                c.append(("p", "Non chiamata da nessuna parte del progetto."))
            if usc:
                c.append(("p", "Chiama: " + ", ".join(
                    f"{vm}.{vn}" + ("" if certo else " (incerta)")
                    for vm, vn, certo in usc)))
    return c


# ==========================================================================
# 5. Il comando
# ==========================================================================


def copertura(modulo: str) -> tuple[list[str], list[str]]:
    """(spiegate, mancanti) -- quali funzioni del modulo il documento cita.

    Con 260 fra funzioni e metodi da documentare, 'mi pare di averle fatte
    tutte' non e' una risposta. Una funzione conta come spiegata se almeno un
    blocco di codice del documento la cita, per nome o perche' e' compresa in
    un blocco piu' ampio (una classe cita i suoi metodi).
    """
    sys.path.insert(0, ATTREZZI)
    try:
        mod = importlib.import_module(f"doc_contenuti.{modulo}")
    except ModuleNotFoundError:
        s = sorgente(modulo)
        return [], sorted(n for n, v in s.voci.items()
                          if not isinstance(v, ast.ClassDef))

    s = sorgente(modulo)
    tratti = []
    for _, contenuto in mod.DOCUMENTI:
        for voce in contenuto:
            if voce[0] != "c":
                continue
            src, nome = _riferimento(voce[1])
            if src.modulo != modulo:
                continue
            tratti.append(src.ritaglia(nome, *(voce[2:4] + (None, None))[:2]))

    spiegate, mancanti = [], []
    for nome, nodo in sorted(s.voci.items()):
        if isinstance(nodo, ast.ClassDef):
            continue
        a, b = s.estensione(nome)
        # basta che una riga del corpo compaia da qualche parte
        if any(x <= a and b <= y or (x <= a <= y) for x, y in tratti):
            spiegate.append(nome)
        else:
            mancanti.append(nome)
    return spiegate, mancanti


def genera_modulo(modulo: str) -> list[str]:
    """Genera i documenti di un modulo leggendo il suo file di contenuti."""
    sys.path.insert(0, ATTREZZI)
    try:
        mod = importlib.import_module(f"doc_contenuti.{modulo}")
    except ModuleNotFoundError:
        return []
    fatti = []
    for nome_file, contenuto in mod.DOCUMENTI:
        uscita = os.path.join(DOC, modulo, nome_file)
        fatti.append(scrivi(contenuto, uscita))
    return fatti


def main(argv: list[str]) -> int:
    try:
        import docx  # noqa: F401
    except ImportError:
        print("Manca python-docx. Installalo con:  pip install python-docx")
        return 2

    solo_albero = "--albero" in argv
    voluti = [a for a in argv if not a.startswith("-")] or MODULI
    ignoti = [m for m in voluti if m not in MODULI]
    if ignoti:
        print(f"Moduli sconosciuti: {', '.join(ignoti)}")
        print(f"Quelli documentati sono: {', '.join(MODULI)}")
        return 2

    if "--copertura" in argv:
        print(f"{'modulo':14s} {'spiegate':>9s} {'da fare':>8s}")
        tot_s = tot_m = 0
        for m in voluti:
            sp, ma = copertura(m)
            tot_s += len(sp)
            tot_m += len(ma)
            print(f"{m:14s} {len(sp):9d} {len(ma):8d}"
                  + ("" if not ma else "   " + ", ".join(ma[:4])
                     + (" ..." if len(ma) > 4 else "")))
        tot = tot_s + tot_m
        print(f"\n{tot_s} funzioni su {tot} spiegate "
              f"({100 * tot_s / tot:.0f}%), {tot_m} da fare.")
        return 0

    fatti = []
    if not solo_albero:
        for m in voluti:
            prodotti = genera_modulo(m)
            if not prodotti:
                print(f"  {m:15s} -- nessun contenuto scritto "
                      f"(manca strumenti/doc_contenuti/{m}.py)")
            for p in prodotti:
                print(f"  {os.path.relpath(p, RADICE)}")
            fatti += prodotti

    if not argv or solo_albero or set(voluti) == set(MODULI):
        ch = Chiamate(MODULI)
        p = scrivi(contenuto_albero(ch),
                   os.path.join(DOC, "ALBERO_DELLE_CHIAMATE.docx"))
        print(f"  {os.path.relpath(p, RADICE)}")
        fatti.append(p)

    print(f"\n{len(fatti)} documenti scritti in doc/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
