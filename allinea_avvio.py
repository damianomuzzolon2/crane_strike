"""
allinea_avvio.py
----------------
Rende ESATTO un punto di avvio approssimato, spostando nel tempo il giro di
qualche carroponte.

`avvio.py` legge un ciclogramma e ne ricava l'istante in cui la linea si puo'
mettere in marcia: tutti i carroponti fermi, col gancio in basso, fuori dal
carico e dallo scarico. Quando un istante cosi' non c'e' si prende il meno
sbagliato, e il Riepilogo scrive "approssimato": a qualche carroponte mancano
pochi secondi per essere a riposo. Di solito e' un caso, non una necessita':
il solutore non sa che esiste un punto di avvio, e fra i tanti ciclogrammi
buoni uguali ne ha preso uno in cui le finestre di riposo dei carroponti si
mancano di un soffio.

Qui si rimedia senza risolvere di nuovo la linea. Si SPOSTA RIGIDAMENTE il giro
di ciascun carroponte di qualche secondo, avanti o indietro: tutte le sue mosse
insieme, con i rientri a vuoto, le attese e le soste che aveva. Dentro il giro
di un carroponte non cambia niente. Cambia solo il tempo in vasca nelle tappe di
CONFINE, dove un carroponte consegna e il successivo preleva: se il secondo si
sposta di `s` rispetto al primo, quel bagno si allunga di `s`. E cambia di
quanto due carroponti vicini sono sfasati fra loro, quindi la loro distanza.

Gli spostamenti si scelgono con un piccolo modello CP-SAT, che chiede:

  - i bagni di confine dentro le tolleranze della ricetta;
  - un istante in cui TUTTI i carroponti sono dentro una finestra di riposo,
    con almeno `MARGINE_MINIMO_S` di margine da entrambe le parti;
  - per ogni coppia di carroponti vicini, uno sfasamento fra quelli che non li
    fanno collidere. Quali sono si sa PRIMA di risolvere: spostare rigidamente
    i giri vuol dire che la distanza fra due carroponti dipende solo da di
    quanto sono sfasati, e la si calcola per tutti gli sfasamenti campionando
    le due traiettorie una volta sola.

Fra gli spostamenti possibili si prende quello che CAMBIA MENO il ciclogramma
-- la somma dei secondi di cui cambiano i bagni di confine --, a parita' quello
che allontana meno i bagni dai tempi teorici (lo stesso scarto pesato del
calcolo), e a parita' ancora quello che lascia piu' margine attorno
all'istante di avvio. Il cambiamento minimo viene prima dello scarto di
proposito: e' un ritocco del punto di avvio, non un'altra ottimizzazione dei
tempi in vasca, e su un ciclogramma composto a mano non deve rimettere in
discussione bagni che l'utente ha scelto.

Il risultato si tiene SOLO SE il punto di avvio diventa esatto e la verifica
indipendente lo passa. Il campionamento delle distanze qui e' piu' rado di
quello del verificatore, e non sa niente dei posti nelle vasche: e' il
verificatore a dire l'ultima parola, come per ogni altro ciclogramma.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from avvio import _nel_periodo, finestre_di_riposo, posizione_a, trova_avvio
from model import (
    SCALA_PESI,
    ProblemData,
    Solution,
    build_solution,
    errore_pesato,
    scarti_dal_teorico,
)
from verify import verify_solution

# Margine minimo attorno all'istante di avvio [s]: per tanto prima e tanto dopo
# tutti i carroponti devono essere a riposo. Zero vorrebbe dire un istante che
# tocca appena la fine di una finestra, esatto sulla carta e fragile su un
# impianto.
MARGINE_MINIMO_S = 0.5

# Il margine che si cerca, a parita' di scarto dai teorici [s]. Oltre non serve:
# chi avvia la linea porta i carroponti in posizione e li lascia fermi, e il
# margine dice solo quanto l'istante scritto e' lontano dal bordo.
MARGINE_CERCATO_S = 2.0

# Passo con cui si campionano gli sfasamenti e le traiettorie [s]. Gli
# spostamenti trovati ne sono multipli.
PASSO_S = 0.05

# Tempo concesso a ciascuna delle due risoluzioni CP-SAT [s]. Il modello ha una
# variabile per carroponte e qualche decina di vincoli: si chiude in un attimo.
TEMPO_LIMITE_S = 10.0


@dataclass
class Allineamento:
    """Un ciclogramma il cui punto di avvio e' stato reso esatto."""

    soluzione: Solution
    # [s] di quanto e' stato spostato il giro di ciascun carroponte, per indice
    # di zona: positivo = piu' tardi. Solo quelli spostati.
    spostamenti: dict[int, float]
    # [s] lo stesso, per mossa: serve a chi modifica il ciclogramma per tempi
    # in vasca e non per carroponte (la finestra).
    spostamenti_mosse: dict[int, float]
    margine: float  # [s] attorno all'istante di avvio, dal lato piu' stretto
    errore_pesato_prima: float
    errore_pesato_dopo: float


def _proprietari(sol: Solution, data: ProblemData) -> Optional[dict[int, int]]:
    """Mossa -> indice della zona del carroponte che la fa. None se qualche
    mossa non e' di nessuno: un ciclogramma ancora da comporre non ha un punto
    di avvio da sistemare."""
    fuori = {}
    for p in sol.plans:
        h = data.zones.index(p.zone)
        for k in p.order:
            fuori[k] = h
    if any(k not in fuori for k in range(data.n_moves)):
        return None
    return fuori


def _intervalli(valori: list[int]) -> list[list[int]]:
    """Interi ordinati -> intervalli chiusi `[a, b]` di valori consecutivi."""
    fuori: list[list[int]] = []
    for v in valori:
        if fuori and v == fuori[-1][1] + 1:
            fuori[-1][1] = v
        else:
            fuori.append([v, v])
    return fuori


def _sfasamenti_sicuri(
    xi: np.ndarray, xj: np.ndarray, richiesta: float, buffer: float, limite: int
) -> list[int]:
    """Gli sfasamenti `r` (in passi) per cui il carroponte i spostato di `r`
    rispetto al j resta sempre ad almeno `richiesta + buffer` da lui.

    Le traiettorie sono periodiche e campionate sullo stesso periodo, quindi
    spostarne una e' una rotazione dell'array. Lo zero c'e' sempre: e' il
    ciclogramma di partenza, che il verificatore ha gia' passato, e un
    campionamento piu' rado del suo non deve poterlo escludere."""
    fuori = []
    for r in range(-limite, limite + 1):
        if r == 0 or np.min(np.abs(np.roll(xi, r) - xj)) >= richiesta + buffer:
            fuori.append(r)
    return fuori


def allinea_avvio(
    data: ProblemData,
    sol: Solution,
    tempo_limite_s: float = TEMPO_LIMITE_S,
) -> Optional[Allineamento]:
    """Sposta i giri dei carroponti perche' il punto di avvio diventi esatto.

    None se non serve (e' gia' esatto), se non si puo' (nessuno spostamento
    accontenta le tolleranze e le distanze, o un carroponte non sta mai fermo
    in basso), o se il ciclogramma spostato non passa la verifica. In tutti
    questi casi chi chiama tiene il ciclogramma che aveva.

    `data` deve avere le zone della soluzione."""
    T = sol.T
    if (
        not T
        or T <= 0
        or data.zones is None
        or sol.status in ("INFEASIBLE", "MODEL_INVALID", "UNKNOWN")
        or not sol.actual_time
    ):
        return None
    prima = trova_avvio(data, sol)
    if prima is None or prima.esatto:
        return None
    proprietario = _proprietari(sol, data)
    if proprietario is None:
        return None
    n = len(sol.segments_per_hoist)
    attivi = [h for h in range(n) if sol.segments_per_hoist[h]]
    finestre = {
        h: _nel_periodo(finestre_di_riposo(data, sol.segments_per_hoist[h]), T)
        for h in attivi
    }
    if any(not f for f in finestre.values()):
        return None  # un carroponte mai fermo in basso: non c'e' rimedio

    # -- la griglia ---------------------------------------------------------
    # Il passo divide il periodo esattamente, cosi' spostare una traiettoria
    # campionata e' una rotazione e non un'interpolazione.
    N = max(1, round(T / PASSO_S))
    g = T / N
    at = list(sol.actual_time)
    eps = data.eps_seconds

    # -- i bagni di confine e di quanto possono cambiare --------------------
    # (tappa, carroponte che consegna, carroponte che preleva, di quanti passi
    # il bagno puo' accorciarsi e allungarsi, il bagno di adesso [s])
    confini = []
    for k in range(1, data.n_moves):
        hp, hd = proprietario[k - 1], proprietario[k]
        if hp == hd:
            continue
        bagno = at[k] - at[k - 1] - data.loaded_leg_seconds(k - 1)
        spec = data.route[k]
        lo = math.ceil((spec.dwell_min - bagno - eps) / g)
        hi = math.floor((spec.dwell_max - bagno + eps) / g)
        confini.append((k, hp, hd, min(lo, 0), max(hi, 0), bagno))
    if not confini:
        return None  # un carroponte solo: spostarlo non cambia niente
    escursione = sum(max(-lo, hi) for _, _, _, lo, hi, _ in confini)
    S = max(1, min(escursione, N // 2))

    # -- gli sfasamenti che non fanno collidere i vicini --------------------
    richiesta = data.hoist_length + data.safety_distance
    tempi = [i * g for i in range(N)]
    pos = {
        h: np.array([posizione_a(sol.segments_per_hoist[h], t, T) for t in tempi])
        for h in attivi
    }
    # Fra due campioni la distanza puo' scendere al piu' di quanto i due
    # carroponti percorrono in mezzo passo ciascuno.
    vmax = {
        h: float(np.max(np.abs(np.diff(pos[h], append=pos[h][0])))) / g
        for h in attivi
    }
    sicuri = {}
    for a, b in zip(attivi, attivi[1:]):
        buffer = (vmax[a] + vmax[b]) * g / 2.0 + 1.0
        sicuri[(a, b)] = _sfasamenti_sicuri(
            pos[a], pos[b], richiesta, buffer, min(2 * S, N // 2)
        )

    # -- il modello ---------------------------------------------------------
    from ortools.sat.python import cp_model

    m = cp_model.CpModel()
    riferimento = proprietario[0]
    s = {
        h: m.NewIntVar(*((0, 0) if h == riferimento else (-S, S)), f"s{h}")
        for h in attivi
    }
    t = m.NewIntVar(0, N - 1, "t")
    m_min = math.ceil(MARGINE_MINIMO_S / g)
    m_cap = max(m_min, math.floor(MARGINE_CERCATO_S / g))
    margine = m.NewIntVar(m_min, m_cap, "margine")

    costo = []
    w_scarto = []
    for k, hp, hd, lo, hi, bagno in confini:
        delta = m.NewIntVar(lo, hi, f"d{k}")
        m.Add(delta == s[hd] - s[hp])
        modulo = m.NewIntVar(0, max(-lo, hi), f"ad{k}")
        m.AddAbsEquality(modulo, delta)
        costo.append(modulo)
        # lo scarto dal teorico, in passi, con i pesi del calcolo
        spec = data.route[k]
        base = round((bagno - spec.nominale) / g)
        sotto = m.NewIntVar(0, abs(base) + max(-lo, hi), f"u{k}")
        sopra = m.NewIntVar(0, abs(base) + max(-lo, hi), f"o{k}")
        m.Add(sotto >= -(base + delta))
        m.Add(sopra >= base + delta)
        w_scarto.append(round(spec.peso_sotto * SCALA_PESI) * sotto)
        w_scarto.append(round(spec.peso_sopra * SCALA_PESI) * sopra)

    for (a, b), valori in sicuri.items():
        m.AddLinearExpressionInDomain(
            s[a] - s[b], cp_model.Domain.FromIntervals(_intervalli(valori))
        )

    for h in attivi:
        scelte = []
        for fa, fb in finestre[h]:
            A, B = math.ceil(fa / g - 1e-9), math.floor(fb / g + 1e-9)
            for giro in (-1, 0, 1):
                a_, b_ = A + giro * N, B + giro * N
                if b_ < -S or a_ > N + S:
                    continue
                c = m.NewBoolVar(f"w{h}_{a_}")
                m.Add(t - s[h] - margine >= a_).OnlyEnforceIf(c)
                m.Add(t - s[h] + margine <= b_).OnlyEnforceIf(c)
                scelte.append(c)
        if not scelte:
            return None
        m.AddBoolOr(scelte)

    # Tre obiettivi in fila, ciascuno a parita' dei precedenti: il cambiamento
    # piu' piccolo, lo scarto dai teorici piu' piccolo, il margine piu' largo.
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = tempo_limite_s
    solver.parameters.num_workers = 8
    for verso, obiettivo in (
        (+1, sum(costo)),
        (+1, sum(w_scarto)),
        (-1, margine),
    ):
        m.ClearObjective()
        if verso > 0:
            m.Minimize(obiettivo)
        else:
            m.Maximize(obiettivo)
        if solver.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        valore = round(solver.ObjectiveValue())
        m.Add(obiettivo <= valore if verso > 0 else obiettivo >= valore)
    passi = {h: solver.Value(s[h]) for h in attivi}

    # -- il ciclogramma spostato -------------------------------------------
    sposta = {k: passi[proprietario[k]] * g for k in range(data.n_moves)}
    nuovi = [at[k] + sposta[k] for k in range(data.n_moves)]
    passaggi = {}
    for p in sol.plans:
        h = data.zones.index(p.zone)
        punti = [
            (tp + passi[h] * g, xp)
            for lista in p.passaggi.values()
            for tp, xp in lista
        ]
        if punti:
            passaggi[h] = punti
    nuova = build_solution(
        data,
        T,
        actual_time=nuovi,
        status=sol.status,
        attese={k: v for p in sol.plans for k, v in p.attese.items()},
        soste={k: v for p in sol.plans for k, v in p.soste_intermedie.items()},
        passaggi=passaggi or None,
    )
    dopo = trova_avvio(data, nuova)
    if dopo is None or not dopo.esatto:
        return None
    if not verify_solution(data, nuova).ok:
        return None

    e_prima = errore_pesato(data, scarti_dal_teorico(data, at))
    e_dopo = errore_pesato(data, scarti_dal_teorico(data, nuovi))
    spostamenti = {h: v * g for h, v in passi.items() if v}
    nuova = dataclasses.replace(
        nuova,
        raw={
            **sol.raw,
            "errore_pesato": e_dopo,
            "allineamento_avvio": dict(spostamenti),
        },
    )
    return Allineamento(
        soluzione=nuova,
        spostamenti=spostamenti,
        spostamenti_mosse=sposta,
        margine=solver.Value(margine) * g,
        errore_pesato_prima=e_prima,
        errore_pesato_dopo=e_dopo,
    )


def descrivi(spostamenti: dict[int, float], carri: Optional[dict] = None) -> str:
    """Gli spostamenti in una riga, da mostrare a chi guarda: "carroponte 3
    anticipato di 2.00 s, carroponte 4 ritardato di 2.70 s".

    `spostamenti` e' `Allineamento.spostamenti`, o lo stesso dizionario come
    resta scritto in `Solution.raw["allineamento_avvio"]`. `carri` traduce
    l'indice di zona nel numero di carroponte, come in
    `avvio.righe_di_riepilogo`."""
    parti = []
    for h, v in sorted(spostamenti.items()):
        n = h if carri is None else carri.get(h, h)
        numero = (h if n is None else n) + 1
        verso = "ritardato" if v > 0 else "anticipato"
        parti.append(f"carroponte {numero} {verso} di {abs(v):.2f} s")
    return ", ".join(parti) if parti else "nessuno spostamento"
