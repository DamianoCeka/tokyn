#!/usr/bin/env python3
"""Trova i contratti in scadenza e fa scrivere a Claude le email di promemoria.

Uso: python programma.py AAAA-MM-GG
Legge contratti.csv dalla cartella corrente e scrive risultato.json.
"""
import csv
import json
import sys
from datetime import date, timedelta

import anthropic

MODELLO = "claude-opus-5-5"
FINESTRA_GIORNI = 30

SYSTEM = (
    "Scrivi email di promemoria di scadenza contratto, in italiano, per conto del fornitore del servizio. "
    "Tono cortese e professionale, breve (3-5 frasi). Il testo deve iniziare rivolgendosi al cliente per nome "
    "(es. «Gentile <cliente>,»), citare il servizio in scadenza e la data di scadenza scritta per esteso "
    "(es. «12 novembre 2026»), e invitare a contattarci per il rinnovo. "
    "Non inventare nomi di persone, aziende, recapiti o prezzi e non lasciare segnaposto tra parentesi: "
    "chiudi con una formula generica come «Cordiali saluti». "
    "L'oggetto è una riga sola, senza prefissi come «Oggetto:»."
)

SCHEMA = {
    "type": "object",
    "properties": {"oggetto": {"type": "string"}, "testo": {"type": "string"}},
    "required": ["oggetto", "testo"],
    "additionalProperties": False,
}


def leggi_contratti(percorso):
    contratti = []
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        for n, riga in enumerate(csv.DictReader(f), start=2):
            try:
                scadenza = date.fromisoformat(riga["scadenza"].strip())
            except (ValueError, AttributeError, KeyError):
                print(f"Riga {n} ignorata: scadenza non valida ({riga.get('scadenza')!r})", file=sys.stderr)
                continue
            contratti.append((riga["cliente"], riga["servizio"], riga["scadenza"], scadenza))
    return contratti


def scrivi_email(client, cliente, servizio, scadenza, riferimento):
    richiesta = (
        f"Cliente: {cliente}\n"
        f"Servizio in scadenza: {servizio}\n"
        f"Data di scadenza: {scadenza.isoformat()}\n"
        f"Data odierna: {riferimento.isoformat()}"
    )
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=2000,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": richiesta}],
    )
    if risposta.stop_reason != "end_turn":
        raise RuntimeError(f"risposta non completa (stop_reason={risposta.stop_reason})")
    testo = next(b.text for b in risposta.content if b.type == "text")
    return json.loads(testo)


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python programma.py AAAA-MM-GG")
    try:
        riferimento = date.fromisoformat(sys.argv[1])
    except ValueError:
        sys.exit(f"Data di riferimento non valida: {sys.argv[1]!r} (formato AAAA-MM-GG)")

    limite = riferimento + timedelta(days=FINESTRA_GIORNI)
    in_scadenza = [c for c in leggi_contratti("contratti.csv") if riferimento <= c[3] <= limite]
    in_scadenza.sort(key=lambda c: c[3])

    client = anthropic.Anthropic() if in_scadenza else None
    risultati = []
    for cliente, servizio, scadenza_txt, scadenza in in_scadenza:
        email = scrivi_email(client, cliente, servizio, scadenza, riferimento)
        risultati.append({
            "cliente": cliente,
            "servizio": servizio,
            "scadenza": scadenza_txt,
            "giorni_mancanti": (scadenza - riferimento).days,
            "oggetto": email["oggetto"],
            "testo": email["testo"],
        })

    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump({"in_scadenza": risultati}, f, ensure_ascii=False, indent=2)
    print(f"{len(risultati)} contratti in scadenza scritti in risultato.json")


if __name__ == "__main__":
    main()
