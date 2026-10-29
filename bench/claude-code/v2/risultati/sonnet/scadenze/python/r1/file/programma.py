#!/usr/bin/env python3
"""Trova i contratti in scadenza e scrive con Claude le email di promemoria.

Uso: python programma.py AAAA-MM-GG
Legge contratti.csv dalla cartella corrente e scrive risultato.json.
Richiede il pacchetto `anthropic` e le credenziali (ANTHROPIC_API_KEY).
"""
import csv
import json
import sys
from datetime import date, timedelta

import anthropic

MODELLO = "claude-opus-5-5"
GIORNI_FINESTRA = 30

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
    "Scrivi in italiano un'email di promemoria per un cliente il cui contratto sta per scadere. "
    "Rivolgiti al cliente per nome (ad esempio 'Gentile <cliente>,'), cita il servizio in scadenza "
    "e la data di scadenza, e invitalo a contattarci per il rinnovo. Tono cordiale e professionale, "
    "breve. Non usare segnaposto tra parentesi e non inventare nomi di persone, aziende, recapiti o "
    "prezzi: chiudi con una formula di saluto generica senza firma. "
    "L'oggetto deve essere una riga sola e contenere servizio e data. "
    "Rispondi con un oggetto JSON con i campi 'oggetto' e 'testo'."
)


def leggi_contratti(percorso):
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        for riga in csv.DictReader(f):
            yield {k: (v or "").strip() for k, v in riga.items() if k}


def contratti_in_scadenza(percorso, riferimento):
    limite = riferimento + timedelta(days=GIORNI_FINESTRA)
    trovati = []
    for n, c in enumerate(leggi_contratti(percorso), start=2):
        try:
            scadenza = date.fromisoformat(c["scadenza"])
        except (KeyError, ValueError):
            print(f"Attenzione: riga {n} ignorata, scadenza non valida: {c.get('scadenza')!r}",
                  file=sys.stderr)
            continue
        if riferimento <= scadenza <= limite:
            trovati.append({
                "cliente": c["cliente"],
                "servizio": c["servizio"],
                "scadenza": c["scadenza"],
                "giorni_mancanti": (scadenza - riferimento).days,
                "_data": scadenza,
            })
    trovati.sort(key=lambda c: c["_data"])  # stabile: a pari data resta l'ordine del file
    for c in trovati:
        del c["_data"]
    return trovati


def scrivi_email(client, contratto):
    giorni = contratto["giorni_mancanti"]
    quando = "oggi" if giorni == 0 else f"tra {giorni} giorni"
    richiesta = (
        f"Cliente: {contratto['cliente']}\n"
        f"Servizio in scadenza: {contratto['servizio']}\n"
        f"Data di scadenza: {contratto['scadenza']} (formato AAAA-MM-GG; scrivila per esteso in "
        f"italiano, ad esempio '12 novembre 2026'), cioè {quando}."
    )
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=4000,
        system=ISTRUZIONI,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA_EMAIL}},
        messages=[{"role": "user", "content": richiesta}],
    )
    if risposta.stop_reason != "end_turn":
        raise RuntimeError(f"risposta non completa per {contratto['cliente']} "
                           f"({contratto['servizio']}): stop_reason={risposta.stop_reason}")
    testo = next(b.text for b in risposta.content if b.type == "text")
    email = json.loads(testo)
    return email["oggetto"].strip(), email["testo"].strip()


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python programma.py AAAA-MM-GG")
    try:
        riferimento = date.fromisoformat(sys.argv[1])
    except ValueError:
        sys.exit(f"Data di riferimento non valida: {sys.argv[1]!r} (atteso AAAA-MM-GG)")

    in_scadenza = contratti_in_scadenza("contratti.csv", riferimento)

    client = anthropic.Anthropic()
    for c in in_scadenza:
        c["oggetto"], c["testo"] = scrivi_email(client, c)

    # Si scrive solo a lavoro completato: niente file parziali se una chiamata fallisce.
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump({"in_scadenza": in_scadenza}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{len(in_scadenza)} contratti in scadenza, scritto risultato.json")


if __name__ == "__main__":
    main()
