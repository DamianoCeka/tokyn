"""Trova i contratti in scadenza nei 30 giorni successivi a una data di riferimento
e, per ognuno, fa scrivere a Claude un'email di promemoria per il cliente.

Uso (dalla cartella che contiene contratti.csv):
    python programma.py AAAA-MM-GG

Richiede il pacchetto `anthropic` e una chiave in ANTHROPIC_API_KEY.
"""

import csv
import json
import os
import sys
from datetime import date, timedelta

import anthropic
from pydantic import BaseModel

FILE_CONTRATTI = "contratti.csv"
FILE_RISULTATO = "risultato.json"
GIORNI_FINESTRA = 30
MODELLO = "claude-opus-5-5"
TENTATIVI_EMAIL = 3

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

ISTRUZIONI = """Scrivi email di promemoria per la scadenza dei contratti di servizio dei nostri clienti.
L'email è in italiano, cortese e professionale, e breve (al massimo 120 parole nel testo).
Il testo si rivolge al cliente per nome, iniziando con "Gentile <nome del cliente>,", riportando il nome
esattamente come fornito. Cita il servizio in scadenza e la data di scadenza, invita il cliente a contattarci
per il rinnovo e chiudi con una firma generica ("Il team assistenza clienti").
Non inventare prezzi, condizioni, numeri di telefono, nomi di persone o altri dettagli non forniti.
L'oggetto è una sola riga che nomina il servizio e la data di scadenza."""


class Email(BaseModel):
    oggetto: str
    testo: str


def data_in_italiano(d: date) -> str:
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


def leggi_contratti(percorso: str) -> list[dict]:
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        lettore = csv.DictReader(f)
        mancanti = {"cliente", "servizio", "scadenza", "email"} - set(lettore.fieldnames or [])
        if mancanti:
            raise ValueError(f"colonne mancanti in {percorso}: {', '.join(sorted(mancanti))}")
        contratti = []
        for riga in lettore:
            if not any((v or "").strip() for v in riga.values()):
                continue  # riga vuota
            n = lettore.line_num
            try:
                scadenza = date.fromisoformat(riga["scadenza"].strip())
            except (ValueError, AttributeError):
                raise ValueError(f"riga {n}: scadenza non valida {riga['scadenza']!r} (atteso AAAA-MM-GG)")
            contratti.append({
                "cliente": riga["cliente"].strip(),
                "servizio": riga["servizio"].strip(),
                "scadenza": scadenza,
            })
        return contratti


def in_scadenza(contratti: list[dict], riferimento: date) -> list[dict]:
    fine = riferimento + timedelta(days=GIORNI_FINESTRA)
    trovati = [c for c in contratti if riferimento <= c["scadenza"] <= fine]
    return sorted(trovati, key=lambda c: c["scadenza"])


def scrivi_email(client: anthropic.Anthropic, contratto: dict, giorni: int) -> Email:
    quando = {0: "oggi", 1: "domani"}.get(giorni, f"tra {giorni} giorni")
    richiesta = (
        f"Cliente: {contratto['cliente']}\n"
        f"Servizio in scadenza: {contratto['servizio']}\n"
        f"Data di scadenza: {data_in_italiano(contratto['scadenza'])} ({quando})"
    )
    for tentativo in range(1, TENTATIVI_EMAIL + 1):
        risposta = client.beta.messages.parse(
            model=MODELLO,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=ISTRUZIONI,
            messages=[{"role": "user", "content": richiesta}],
            output_format=Email,
        )
        if risposta.stop_reason == "refusal":
            raise RuntimeError(f"Claude ha rifiutato di scrivere l'email per {contratto['cliente']}")
        email = risposta.parsed_output
        if email is None:
            continue  # risposta troncata o non conforme: riprova
        # Il testo deve rivolgersi al cliente per nome e citare il servizio.
        testo = email.testo.casefold()
        if contratto["cliente"].casefold() in testo and contratto["servizio"].casefold() in testo:
            return email
        print(f"  tentativo {tentativo}: l'email non cita cliente o servizio, la rigenero", file=sys.stderr)
    raise RuntimeError(f"impossibile ottenere un'email valida per {contratto['cliente']} - {contratto['servizio']}")


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python programma.py AAAA-MM-GG", file=sys.stderr)
        return 2
    try:
        riferimento = date.fromisoformat(sys.argv[1])
    except ValueError:
        print(f"Data di riferimento non valida: {sys.argv[1]!r} (atteso AAAA-MM-GG)", file=sys.stderr)
        return 2

    try:
        contratti = leggi_contratti(FILE_CONTRATTI)
    except FileNotFoundError:
        print(f"File {FILE_CONTRATTI} non trovato nella cartella corrente", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Errore in {FILE_CONTRATTI}: {e}", file=sys.stderr)
        return 1

    scadenze = in_scadenza(contratti, riferimento)
    print(f"{len(scadenze)} contratti in scadenza tra il {riferimento} e il "
          f"{riferimento + timedelta(days=GIORNI_FINESTRA)}", file=sys.stderr)

    client = anthropic.Anthropic()
    risultati = []
    try:
        for c in scadenze:
            giorni = (c["scadenza"] - riferimento).days
            print(f"- {c['cliente']}: {c['servizio']} ({c['scadenza']})", file=sys.stderr)
            email = scrivi_email(client, c, giorni)
            risultati.append({
                "cliente": c["cliente"],
                "servizio": c["servizio"],
                "scadenza": c["scadenza"].isoformat(),
                "giorni_mancanti": giorni,
                "oggetto": email.oggetto.strip(),
                "testo": email.testo.strip(),
            })
    except (anthropic.APIError, RuntimeError) as e:
        print(f"Errore durante la scrittura delle email: {e}", file=sys.stderr)
        return 1

    # Scrittura atomica: un risultato parziale non sostituisce mai quello precedente.
    temporaneo = FILE_RISULTATO + ".tmp"
    with open(temporaneo, "w", encoding="utf-8") as f:
        json.dump({"in_scadenza": risultati}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temporaneo, FILE_RISULTATO)
    print(f"Scritto {FILE_RISULTATO}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
