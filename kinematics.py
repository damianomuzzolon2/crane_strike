"""
kinematics.py
-------------
Funzioni per calcolare tempo di percorrenza e profilo di posizione di un
carroponte che si muove con un profilo trapezoidale (accelerazione costante,
velocita' di crociera, decelerazione costante) oppure triangolare se la
distanza e' troppo breve per raggiungere la velocita' massima.

Tutte le funzioni lavorano in unita' fisiche "naturali" (metri, m/s, m/s^2,
secondi). La conversione in "tick" interi per CP-SAT avviene altrove.
"""

from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Kinematics:
    """Limiti cinematici di un carroponte in una data condizione (vuoto o carico)."""

    v_max: float  # m/s
    a_max: float  # m/s^2 (si assume accelerazione = decelerazione)

    def __post_init__(self):
        if self.v_max <= 0 or self.a_max <= 0:
            raise ValueError("v_max e a_max devono essere > 0")


def travel_time(distance: float, kin: Kinematics) -> float:
    """Tempo minimo [s] per percorrere `distance` [m] rispettando v_max e a_max.

    - Se la distanza e' sufficiente a raggiungere v_max, il profilo e'
      trapezoidale: accelerazione, tratto a velocita' costante, decelerazione.
    - Altrimenti il profilo e' triangolare: si accelera e poi si decelera
      subito, senza mai raggiungere v_max.
    """
    d = abs(distance)
    if d == 0:
        return 0.0
    d_acc = (
        kin.v_max**2 / kin.a_max
    )  # distanza per accelerare 0->v_max e poi decelerare v_max->0
    if d >= d_acc:
        # trapezoidale
        t_cruise = (d - d_acc) / kin.v_max
        t_ramp = kin.v_max / kin.a_max
        return 2 * t_ramp + t_cruise
    else:
        # triangolare (non si raggiunge v_max)
        return 2 * math.sqrt(d / kin.a_max)


def position_profile(t: float, distance: float, kin: Kinematics) -> float:
    """Spazio percorso [m] al tempo `t` [s] dall'inizio del movimento
    (0 <= t <= travel_time(distance, kin)). Il segno di `distance` non conta:
    restituisce sempre uno spostamento positivo, e' compito del chiamante
    orientarlo nella direzione giusta (posizione_iniziale +/- risultato).
    """
    d = abs(distance)
    if d == 0:
        return 0.0
    d_acc = kin.v_max**2 / kin.a_max
    t_total = travel_time(d, kin)
    t = max(0.0, min(t, t_total))

    if d >= d_acc:
        t_ramp = kin.v_max / kin.a_max
        t_cruise = t_total - 2 * t_ramp
        if t <= t_ramp:
            return 0.5 * kin.a_max * t**2
        elif t <= t_ramp + t_cruise:
            return 0.5 * kin.a_max * t_ramp**2 + kin.v_max * (t - t_ramp)
        else:
            t_dec = t - (t_ramp + t_cruise)
            d_at_start_decel = 0.5 * kin.a_max * t_ramp**2 + kin.v_max * t_cruise
            return d_at_start_decel + kin.v_max * t_dec - 0.5 * kin.a_max * t_dec**2
    else:
        t_half = t_total / 2
        if t <= t_half:
            return 0.5 * kin.a_max * t**2
        else:
            t_dec = t - t_half
            v_peak = kin.a_max * t_half
            d_half = 0.5 * kin.a_max * t_half**2
            return d_half + v_peak * t_dec - 0.5 * kin.a_max * t_dec**2


if __name__ == "__main__":
    # Auto-test rapido
    k = Kinematics(v_max=1.0, a_max=0.5)
    for dist in [0.1, 1.0, 5.0, 20.0]:
        T = travel_time(dist, k)
        # la posizione al tempo T deve combaciare con la distanza totale
        p_end = position_profile(T, dist, k)
        p_mid = position_profile(T / 2, dist, k)
        print(
            f"dist={dist:6.2f}  T={T:6.3f}s  pos(T)={p_end:6.3f}  pos(T/2)={p_mid:6.3f}"
        )
        assert (
            abs(p_end - dist) < 1e-6
        ), "la posizione finale deve coincidere con la distanza"
    print("OK: kinematics.py funziona correttamente")
