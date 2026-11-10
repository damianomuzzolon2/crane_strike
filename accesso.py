"""
accesso.py
----------
La schermata di accesso: chi apre CraneStrike deve dare utente e password
prima di vedere la finestra principale.

NEL CODICE NON C'E' NESSUNA PASSWORD, E NEMMENO NESSUN NOME UTENTE. Per ogni
persona abilitata c'e' solo una coppia (sale, impronta):

    impronta = PBKDF2-HMAC-SHA256("utente\\0password", sale, ITERAZIONI)

Utente e password entrano INSIEME nella stessa impronta, cosi' dal sorgente (o
dall'eseguibile) non si legge neppure chi e' abilitato, e chi prova a entrare
non sa se ha sbagliato il nome o la password. Il sale e' diverso per ogni voce:
due persone con la stessa password hanno impronte diverse, e non serve a niente
una tabella di impronte precalcolate. PBKDF2 con molte iterazioni rende lenta
ogni prova (qualche decina di millisecondi): per chi entra non si nota, per chi
volesse provare milioni di password a tavolino si'.

Il nome utente non distingue maiuscole e minuscole e si toglie lo spazio ai
bordi; la password invece si confronta esattamente com'e' scritta.

Per aggiungere una persona:

    python strumenti/genera_utente.py

chiede nome e password e stampa la riga da incollare in `UTENTI` qui sotto.
Per toglierla basta cancellare la sua riga. Poi si ricompila l'eseguibile.

Solo libreria standard (hashlib, hmac, tkinter): niente da installare.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Callable, Optional

# Quante volte PBKDF2 ripete l'hash. Piu' sono, piu' costa ogni tentativo a chi
# prova password a tavolino. Se si cambia, le impronte gia' scritte in `UTENTI`
# non valgono piu' e vanno rigenerate tutte.
ITERAZIONI = 200_000

# Dopo quanti tentativi sbagliati il programma si chiude.
TENTATIVI_MASSIMI = 5

# Le persone abilitate: una voce (sale, impronta), in esadecimale, per ognuna.
# Il commento accanto e' libero e serve solo a chi mantiene il codice: NON ci
# va scritta la password (e meglio non metterci nemmeno il nome utente esatto).
UTENTI: list[tuple[str, str]] = [
    # user: admin, password: FCkl4fvz5c0D
    (
        "7f7bb1e1419b5743ba8e18b595cfdfe4",
        "1c93d482e50ad6b12ae765467caea56c84542325ca9bf6203f0f0ce9cb062576",
    ),
    # user: damiano, password: Ldangela69!
    (
        "02a310af0243af90bbed415b32474f77",
        "94880bf1a94587db85d72c19a0b44aa146d0442dcfd901a7643ce24d0459817b",
    ),
    # user: alessandro.tramontin, password: Atramontin1!
    (
        "f009e122ba192e354180b8c128b09365",
        "f718ce13098ae37b319af6a962b375af27030f0a3692c844fa95d530a9f152e8",
    ),
]


def _normalizza_utente(utente: str) -> str:
    return utente.strip().lower()


def impronta(utente: str, password: str, sale: bytes) -> bytes:
    """L'impronta di una coppia utente/password con un certo sale."""
    segreto = f"{_normalizza_utente(utente)}\0{password}".encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", segreto, sale, ITERAZIONI)


def nuova_voce(utente: str, password: str) -> tuple[str, str]:
    """Crea la voce da mettere in `UTENTI`, con un sale casuale nuovo."""
    sale = os.urandom(16)
    return sale.hex(), impronta(utente, password, sale).hex()


def verifica(
    utente: str, password: str, utenti: Optional[list[tuple[str, str]]] = None
) -> bool:
    """True se la coppia utente/password corrisponde a una delle voci.

    Si provano TUTTE le voci anche dopo averne trovata una giusta: cosi' il
    tempo di risposta non dice a che punto dell'elenco sta l'utente."""
    voci = UTENTI if utenti is None else utenti
    if not utente.strip() or not password:
        return False
    trovato = False
    for sale_hex, impronta_hex in voci:
        try:
            sale = bytes.fromhex(sale_hex)
            attesa = bytes.fromhex(impronta_hex)
        except ValueError:
            continue  # voce scritta male: non apre niente
        if hmac.compare_digest(impronta(utente, password, sale), attesa):
            trovato = True
    return trovato


# --------------------------------------------------------------------------
# La finestra
# --------------------------------------------------------------------------


def chiedi_accesso(
    titolo: str = "CraneStrike",
    applica_icona: Optional[Callable] = None,
    utenti: Optional[list[tuple[str, str]]] = None,
) -> bool:
    """Mostra la finestra di accesso e aspetta. True se l'utente e' entrato,
    False se ha chiuso la finestra, ha premuto Esci o ha esaurito i tentativi.

    La finestra e' una radice Tk a se' stante, distrutta prima di tornare: la
    finestra principale (un'altra `tk.Tk`) nasce solo dopo, e solo se si e'
    entrati."""
    import tkinter as tk
    from tkinter import ttk

    radice = tk.Tk()
    radice.title(f"{titolo} - accesso")
    radice.resizable(False, False)
    icona = applica_icona(radice) if applica_icona else None  # noqa: F841

    esito = {"entrato": False, "tentativi": 0}

    cornice = ttk.Frame(radice, padding=24)
    cornice.pack(fill="both", expand=True)

    ttk.Label(cornice, text=titolo, font=("Segoe UI", 16, "bold")).grid(
        row=0, column=0, columnspan=2, pady=(0, 4)
    )
    ttk.Label(cornice, text="Inserisci utente e password per continuare.").grid(
        row=1, column=0, columnspan=2, pady=(0, 16)
    )

    ttk.Label(cornice, text="Utente").grid(row=2, column=0, sticky="w", pady=4)
    var_utente = tk.StringVar()
    campo_utente = ttk.Entry(cornice, textvariable=var_utente, width=28)
    campo_utente.grid(row=2, column=1, sticky="ew", pady=4, padx=(12, 0))

    ttk.Label(cornice, text="Password").grid(row=3, column=0, sticky="w", pady=4)
    var_password = tk.StringVar()
    campo_password = ttk.Entry(cornice, textvariable=var_password, show="•", width=28)
    campo_password.grid(row=3, column=1, sticky="ew", pady=4, padx=(12, 0))

    var_messaggio = tk.StringVar()
    ttk.Label(cornice, textvariable=var_messaggio, foreground="#b00020").grid(
        row=4, column=0, columnspan=2, pady=(8, 0)
    )

    pulsanti = ttk.Frame(cornice)
    pulsanti.grid(row=5, column=0, columnspan=2, pady=(16, 0), sticky="e")

    def entra(_evento=None):
        if verifica(var_utente.get(), var_password.get(), utenti):
            esito["entrato"] = True
            radice.destroy()
            return
        esito["tentativi"] += 1
        restanti = TENTATIVI_MASSIMI - esito["tentativi"]
        var_password.set("")
        if restanti <= 0:
            radice.destroy()
            return
        # Una piccola pausa a ogni errore: chi sbaglia per distrazione non se
        # ne accorge, chi prova password a raffica si'.
        radice.update_idletasks()
        time.sleep(1.0)
        var_messaggio.set(
            "Utente o password non corretti. "
            + (
                "Ultimo tentativo."
                if restanti == 1
                else f"Restano {restanti} tentativi."
            )
        )
        campo_password.focus_set()

    def esci(_evento=None):
        radice.destroy()

    ttk.Button(pulsanti, text="Esci", command=esci).pack(side="right")
    ttk.Button(pulsanti, text="Entra", command=entra, default="active").pack(
        side="right", padx=(0, 8)
    )

    radice.bind("<Return>", entra)
    radice.bind("<KP_Enter>", entra)
    radice.bind("<Escape>", esci)
    radice.protocol("WM_DELETE_WINDOW", esci)

    # al centro dello schermo, davanti alle altre finestre
    radice.update_idletasks()
    w, h = radice.winfo_reqwidth(), radice.winfo_reqheight()
    x = (radice.winfo_screenwidth() - w) // 2
    y = (radice.winfo_screenheight() - h) // 3
    radice.geometry(f"+{x}+{y}")
    radice.lift()
    radice.attributes("-topmost", True)
    radice.after(200, lambda: radice.attributes("-topmost", False))
    campo_utente.focus_force()

    radice.mainloop()
    return esito["entrato"]


if __name__ == "__main__":
    print("entrato" if chiedi_accesso() else "accesso negato")
