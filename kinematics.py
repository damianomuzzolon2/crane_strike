"""
kinematics.py
-------------
Funzioni per calcolare tempo di percorrenza e profilo di posizione di un
carroponte che si muove con un profilo trapezoidale (accelerazione costante,
velocita' di crociera, decelerazione costante) oppure triangolare se la
distanza e' troppo breve per raggiungere la velocita' massima.

Accelerazione e decelerazione sono due numeri distinti. Su un carroponte non
sono quasi mai uguali -- si frena piu' forte di quanto si acceleri, e col
carico appeso il vincolo in frenata e' il pendolo, non il motore -- e usare
l'accelerazione anche per frenare sbagliava ogni trasporto di quanto le due
grandezze differiscono. Chi non ha il dato non deve fare niente: lasciando
`d_max` a None si decelera con `a_max`, che e' il comportamento di prima.

Tutte le funzioni lavorano nelle unita' del progetto (millimetri, mm/s, mm/s^2,
secondi). La conversione in "tick" interi per CP-SAT avviene altrove.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Kinematics:
    """Limiti cinematici di un carroponte in una data condizione (vuoto o carico)."""

    v_max: float  # mm/s
    a_max: float  # mm/s^2, in accelerazione
    # mm/s^2, in frenata. None significa "come in accelerazione": e' il caso
    # di chi non ha il dato, e di tutti i file compilati prima che questo
    # parametro esistesse.
    d_max: Optional[float] = None

    def __post_init__(self):
        if self.v_max <= 0 or self.a_max <= 0:
            raise ValueError("v_max e a_max devono essere > 0")
        if self.d_max is not None and self.d_max <= 0:
            raise ValueError("d_max, se indicata, deve essere > 0")

    @property
    def decel(self) -> float:
        """La decelerazione da usare davvero. Tutto il resto del modulo passa
        di qui: cosi' il caso simmetrico non e' un ramo a parte, ma lo stesso
        conto con due numeri uguali."""
        return self.a_max if self.d_max is None else self.d_max


def _distanza_rampe(kin: Kinematics) -> float:
    """Spazio minimo per arrivare a v_max e tornare a zero: la soglia fra il
    profilo trapezoidale e quello triangolare.

    Con accelerazione e decelerazione uguali vale v_max^2 / a_max, cioe'
    esattamente la formula di prima."""
    return kin.v_max**2 / (2 * kin.a_max) + kin.v_max**2 / (2 * kin.decel)


def _picco_triangolare(d: float, kin: Kinematics) -> float:
    """Velocita' massima raggiunta quando la distanza non basta alla crociera:
    si accelera fino a v_p e da li' si frena, senza tratto piatto.

    v_p^2/(2a) + v_p^2/(2d) = distanza, da cui la radice qui sotto."""
    return math.sqrt(2 * d * kin.a_max * kin.decel / (kin.a_max + kin.decel))


def travel_time(distance: float, kin: Kinematics) -> float:
    """Tempo minimo [s] per percorrere `distance` [m] rispettando v_max, a_max
    e la decelerazione.

    - Se la distanza e' sufficiente a raggiungere v_max, il profilo e'
      trapezoidale: accelerazione, tratto a velocita' costante, decelerazione.
    - Altrimenti il profilo e' triangolare: si accelera e poi si decelera
      subito, senza mai raggiungere v_max.

    Le due rampe hanno pendenze diverse, quindi durate diverse: non si puo'
    piu' contarne una e moltiplicarla per due.
    """
    d = abs(distance)
    if d == 0:
        return 0.0
    d_rampe = _distanza_rampe(kin)
    if d >= d_rampe:
        # trapezoidale
        t_cruise = (d - d_rampe) / kin.v_max
        return kin.v_max / kin.a_max + t_cruise + kin.v_max / kin.decel
    # triangolare (non si raggiunge v_max)
    v_p = _picco_triangolare(d, kin)
    return v_p / kin.a_max + v_p / kin.decel


def position_profile(t: float, distance: float, kin: Kinematics) -> float:
    """Spazio percorso [m] al tempo `t` [s] dall'inizio del movimento
    (0 <= t <= travel_time(distance, kin)). Il segno di `distance` non conta:
    restituisce sempre uno spostamento positivo, e' compito del chiamante
    orientarlo nella direzione giusta (posizione_iniziale +/- risultato).
    """
    d = abs(distance)
    if d == 0:
        return 0.0
    t_total = travel_time(d, kin)
    t = max(0.0, min(t, t_total))

    if d >= _distanza_rampe(kin):
        t_su = kin.v_max / kin.a_max
        t_giu = kin.v_max / kin.decel
        t_cruise = t_total - t_su - t_giu
        d_su = 0.5 * kin.a_max * t_su**2
        if t <= t_su:
            return 0.5 * kin.a_max * t**2
        if t <= t_su + t_cruise:
            return d_su + kin.v_max * (t - t_su)
        t_dec = t - (t_su + t_cruise)
        return (
            d_su
            + kin.v_max * t_cruise
            + kin.v_max * t_dec
            - 0.5 * kin.decel * t_dec**2
        )
    v_p = _picco_triangolare(d, kin)
    t_su = v_p / kin.a_max
    if t <= t_su:
        return 0.5 * kin.a_max * t**2
    t_dec = t - t_su
    d_su = 0.5 * kin.a_max * t_su**2
    return d_su + v_p * t_dec - 0.5 * kin.decel * t_dec**2


def profile_breakpoints(distance: float, kin: Kinematics) -> tuple[float, ...]:
    """Istanti [s], relativi all'inizio del movimento, in cui il profilo di
    posizione cambia tratto (gli "spigoli" della curva).

    - profilo trapezoidale: (0, t_su, t_su + t_cruise, t_total)
    - profilo triangolare:  (0, t_su, t_total)
    - distanza nulla:       (0.0,)

    Lo spigolo del triangolo NON e' piu' a meta' durata: con due rampe di
    pendenza diversa il picco cade dove finisce l'accelerazione, e prenderlo
    a t_total/2 metterebbe il campione nel posto sbagliato -- che e' proprio
    il caso in cui la stima rigorosa dell'errore smetterebbe di essere
    rigorosa.

    Fra due spigoli consecutivi la posizione e' un polinomio di grado <= 2 in
    t. Campionando anche tutti gli spigoli si puo' quindi limitare in modo
    RIGOROSO l'errore commesso cercando un minimo su una griglia finita.
    """
    d = abs(distance)
    if d == 0:
        return (0.0,)
    t_total = travel_time(d, kin)
    if d >= _distanza_rampe(kin):
        t_su = kin.v_max / kin.a_max
        t_cruise = t_total - t_su - kin.v_max / kin.decel
        return (0.0, t_su, t_su + t_cruise, t_total)
    return (0.0, _picco_triangolare(d, kin) / kin.a_max, t_total)


if __name__ == "__main__":
    # Auto-test rapido: il caso simmetrico di sempre, e due asimmetrici.
    for k in (
        Kinematics(v_max=1.0, a_max=0.5),
        Kinematics(v_max=1.0, a_max=0.5, d_max=2.0),
        Kinematics(v_max=1.0, a_max=2.0, d_max=0.5),
    ):
        print(f"\nv_max={k.v_max}  a_max={k.a_max}  decel={k.decel}")
        for dist in [0.1, 1.0, 5.0, 20.0]:
            T = travel_time(dist, k)
            # la posizione al tempo T deve combaciare con la distanza totale
            p_end = position_profile(T, dist, k)
            p_mid = position_profile(T / 2, dist, k)
            print(
                f"dist={dist:6.2f}  T={T:6.3f}s  pos(T)={p_end:6.3f}  "
                f"pos(T/2)={p_mid:6.3f}"
            )
            assert (
                abs(p_end - dist) < 1e-6
            ), "la posizione finale deve coincidere con la distanza"
            bps = profile_breakpoints(dist, k)
            assert bps[0] == 0.0 and abs(bps[-1] - T) < 1e-9, "spigoli incoerenti con T"
            assert list(bps) == sorted(bps), "gli spigoli devono essere crescenti"
            # il profilo deve essere monotono: non si torna mai indietro
            campioni = [position_profile(T * i / 200, dist, k) for i in range(201)]
            assert all(
                b >= a - 1e-9 for a, b in zip(campioni, campioni[1:])
            ), "il profilo non puo' tornare indietro"
    print("\nOK: kinematics.py funziona correttamente")
