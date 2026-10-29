"""Trova i contratti in scadenza nei 30 giorni successivi a una data di riferimento
e scrive con Claude un'email di promemoria per ciascuno.

Uso: python programma.py AAAA-MM-GG
Legge contratti.csv dalla cartella corrente e scrive risultato.json.
"""

import csv
import json
import sys
from datetime import date, timedelta

import anthropic

FILE_CONTRATTI = "contratti.csv"
FILE_RISULTATO = "risultato.json"
GIORNI_FINESTRA = 30
MODELLO = "claude-opus-5-5"

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

SCHEMA_EMAIL = {
    "type": "object",
    "properties": {
        "oggetto": {"type": "string"},
        "testo": {"type": "string"},
    },
    "required": ["oggetto", "testo"],
    "additionalProperties": False,
}

ISTRUZIONI = (
    "Scrivi email di promemoria in italiano per i clienti di un'azienda di servizi. "
    "Tono cortese e professionale, testo breve (massimo 120 parole). "
    "Il testo inizia con 'Gentile <nome cliente>,' usando il nome esattamente come fornito, "
    "cita il servizio in scadenza e la data di scadenza, invita a contattarci per il rinnovo "
    "e chiude con 'Cordiali saluti'. Non inventare prezzi, condizioni, nomi di persone o recapiti. "
    "L'oggetto è una sola riga che indica il servizio e la data di scadenza."
)


def data_in_italiano(d):
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


def leggi_contratti(percorso):
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        righe = list(csv.DictReader(f))
    contratti = []
    for n, riga in enumerate(righe, start=2):
        try:
            scadenza = date.fromisoformat(riga["scadenza"].strip())
        except (ValueError, AttributeError, KeyError):
            print(f"Attenzione: riga {n} ignorata, scadenza non valida: {riga.get('scadenza')!r}",
                  file=sys.stderr)
            continue
        contratti.append({
            "cliente": riga["cliente"].strip(),
            "servizio": riga["servizio"].strip(),
            "scadenza": riga["scadenza"].strip(),
            "data_scadenza": scadenza,
        })
    return contratti


def scrivi_email(client, contratto, giorni):
    scadenza = data_in_italiano(contratto["data_scadenza"])
    quando = "oggi" if giorni == 0 else f"tra {giorni} giorn{'o' if giorni == 1 else 'i'}"
    richiesta = (
        f"Cliente: {contratto['cliente']}\n"
        f"Servizio in scadenza: {contratto['servizio']}\n"
        f"Data di scadenza: {scadenza} ({quando})"
    )
    risposta = client.beta.messages.create(
        model=MODELLO,
        max_tokens=4000,
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": richiesta}],
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": SCHEMA_EMAIL},
        },
        # Se la richiesta viene rifiutata, l'API la ripete su un modello di riserva.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError(f"Claude ha rifiutato la richiesta per {contratto['cliente']}")
    if risposta.stop_reason == "max_tokens":
        raise RuntimeError(f"Risposta troncata per {contratto['cliente']}")
    testo = next(b.text for b in risposta.content if b.type == "text")
    return json.loads(testo)


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python programma.py AAAA-MM-GG")
    try:
        riferimento = date.fromisoformat(sys.argv[1])
    except ValueError:
        sys.exit(f"Data non valida: {sys.argv[1]!r} (formato atteso AAAA-MM-GG)")
    fine = riferimento + timedelta(days=GIORNI_FINESTRA)

    in_scadenza = [c for c in leggi_contratti(FILE_CONTRATTI)
                   if riferimento <= c["data_scadenza"] <= fine]
    in_scadenza.sort(key=lambda c: c["data_scadenza"])

    client = anthropic.Anthropic()
    risultati = []
    for c in in_scadenza:
        giorni = (c["data_scadenza"] - riferimento).days
        print(f"Scrivo l'email per {c['cliente']} ({c['servizio']}, {c['scadenza']})...",
              file=sys.stderr)
        email = scrivi_email(client, c, giorni)
        risultati.append({
            "cliente": c["cliente"],
            "servizio": c["servizio"],
            "scadenza": c["scadenza"],
            "giorni_mancanti": giorni,
            "oggetto": email["oggetto"],
            "testo": email["testo"],
        })

    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump({"in_scadenza": risultati}, f, ensure_ascii=False, indent=2)
    print(f"{len(risultati)} contratti in scadenza scritti in {FILE_RISULTATO}", file=sys.stderr)


if __name__ == "__main__":
    main()
