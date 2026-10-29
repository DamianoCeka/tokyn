#!/usr/bin/env python3
"""Trova i contratti in scadenza nei 30 giorni dalla data di riferimento e
fa scrivere a Claude un'email di promemoria per ciascuno.

Uso: python programma.py AAAA-MM-GG
Legge contratti.csv dalla cartella corrente e scrive risultato.json.
"""
import csv
import json
import sys
from datetime import date, datetime

import anthropic

MODELLO = "claude-opus-5-5"
FINESTRA_GIORNI = 30
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

SYSTEM = (
    "Scrivi email di promemoria in italiano, a nome dell'azienda che fornisce i servizi, "
    "per clienti il cui contratto sta per scadere. Tono cordiale e professionale, breve "
    "(massimo 120 parole). Inizia con 'Gentile <nome cliente>,' usando il nome del cliente "
    "esattamente come ti viene dato, cita il servizio in scadenza e la data di scadenza, "
    "e invita a contattarci per il rinnovo. Non inventare prezzi, offerte, recapiti o "
    "nomi di persone. Chiudi con una formula di saluto e 'Il team assistenza clienti'. "
    "L'oggetto deve essere breve e indicare servizio e data di scadenza."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "oggetto": {"type": "string"},
        "testo": {"type": "string"},
    },
    "required": ["oggetto", "testo"],
    "additionalProperties": False,
}


def data_estesa(d: date) -> str:
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


def leggi_contratti(percorso: str):
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        for n, riga in enumerate(csv.DictReader(f), start=2):
            try:
                scadenza = datetime.strptime(riga["scadenza"].strip(), "%Y-%m-%d").date()
            except (KeyError, AttributeError, ValueError):
                print(f"Riga {n} ignorata: scadenza non valida ({riga.get('scadenza')!r})",
                      file=sys.stderr)
                continue
            yield riga["cliente"], riga["servizio"], riga["scadenza"].strip(), scadenza


def scrivi_email(client, cliente, servizio, scadenza, giorni):
    quando = "oggi" if giorni == 0 else f"tra {giorni} giorni"
    richiesta = (
        f"Cliente: {cliente}\n"
        f"Servizio in scadenza: {servizio}\n"
        f"Data di scadenza: {data_estesa(scadenza)} ({quando})"
    )
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=2000,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": richiesta}],
    )
    if risposta.stop_reason != "end_turn":
        raise RuntimeError(f"risposta non completa per {cliente} / {servizio}: "
                           f"stop_reason={risposta.stop_reason}")
    testo = next(b.text for b in risposta.content if b.type == "text")
    email = json.loads(testo)
    return email["oggetto"], email["testo"]


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python programma.py AAAA-MM-GG")
    try:
        riferimento = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    except ValueError:
        sys.exit(f"Data di riferimento non valida: {sys.argv[1]!r} (formato AAAA-MM-GG)")

    try:
        contratti = list(leggi_contratti("contratti.csv"))
    except FileNotFoundError:
        sys.exit("contratti.csv non trovato nella cartella corrente")

    in_scadenza = sorted(
        ((c, s, testo, d, (d - riferimento).days) for c, s, testo, d in contratti
         if 0 <= (d - riferimento).days <= FINESTRA_GIORNI),
        key=lambda x: x[3],
    )

    risultato = []
    if in_scadenza:
        client = anthropic.Anthropic()
        for cliente, servizio, testo_data, d, giorni in in_scadenza:
            try:
                oggetto, testo = scrivi_email(client, cliente, servizio, d, giorni)
            except anthropic.APIError as e:
                sys.exit(f"Errore API per {cliente} / {servizio}: {e}")
            except TypeError as e:  # credenziali mancanti (ANTHROPIC_API_KEY)
                sys.exit(f"Impossibile autenticarsi: {e}")
            except RuntimeError as e:
                sys.exit(f"Errore: {e}")
            risultato.append({
                "cliente": cliente,
                "servizio": servizio,
                "scadenza": testo_data,
                "giorni_mancanti": giorni,
                "oggetto": oggetto,
                "testo": testo,
            })

    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump({"in_scadenza": risultato}, f, ensure_ascii=False, indent=2)
    print(f"{len(risultato)} contratti in scadenza, scritto risultato.json")


if __name__ == "__main__":
    main()
