#!/usr/bin/env python3
"""Categorizza i movimenti bancari di movimenti.csv con Claude e scrive risultato.json."""

import csv
import json
import sys
from decimal import Decimal, InvalidOperation

import anthropic

INPUT = "movimenti.csv"
OUTPUT = "risultato.json"
MODEL = "claude-opus-5-5"
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
BLOCCO = 100  # movimenti per richiesta

SYSTEM = (
    "Sei un assistente che classifica i movimenti di un conto corrente italiano. "
    "Per ogni movimento scegli esattamente una categoria tra: "
    "'spesa alimentare' (supermercati e negozi di alimentari), "
    "'trasporti' (treni, mezzi pubblici, carburante, pedaggi, taxi, parcheggi), "
    "'casa' (affitto, mutuo, utenze luce/gas/acqua, internet, ferramenta, arredamento), "
    "'svago' (ristoranti, bar, streaming, libri, cinema, hobby, viaggi), "
    "'altro' (tutto il resto: stipendi, commissioni bancarie, bonifici, ecc.). "
    "Rispondi usando l'id di ciascun movimento."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "categorie": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "categoria": {"type": "string", "enum": CATEGORIE},
                },
                "required": ["id", "categoria"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["categorie"],
    "additionalProperties": False,
}


def parse_importo(testo):
    """'-1.234,56' -> Decimal('-1234.56')."""
    pulito = testo.strip().replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return Decimal(pulito)
    except InvalidOperation:
        raise ValueError(f"importo non valido: {testo!r}")


def leggi_movimenti(percorso):
    movimenti = []
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        lettore = csv.reader(f, delimiter=";")
        next(lettore, None)  # intestazione
        for n, riga in enumerate(lettore, start=2):
            if not any(c.strip() for c in riga):
                continue
            if len(riga) != 3:
                raise ValueError(f"riga {n}: attesi 3 campi, trovati {len(riga)}: {riga}")
            data, descrizione, importo = riga
            movimenti.append(
                {"data": data, "descrizione": descrizione, "importo": parse_importo(importo)}
            )
    return movimenti


def categorizza_blocco(client, blocco):
    """blocco: lista di (id, movimento). Ritorna {id: categoria}."""
    righe = "\n".join(
        f"{i}\t{m['data']}\t{m['descrizione']}\t{m['importo']}" for i, m in blocco
    )
    risposta = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        messages=[
            {
                "role": "user",
                "content": "Movimenti (id, data, descrizione, importo separati da tab):\n" + righe,
            }
        ],
    )
    if risposta.stop_reason != "end_turn":
        raise RuntimeError(f"risposta incompleta (stop_reason={risposta.stop_reason})")
    testo = next(b.text for b in risposta.content if b.type == "text")
    risultato = {e["id"]: e["categoria"] for e in json.loads(testo)["categorie"]}
    attesi = {i for i, _ in blocco}
    if set(risultato) != attesi:
        raise RuntimeError(
            f"id non corrispondenti: mancanti={sorted(attesi - set(risultato))}, "
            f"extra={sorted(set(risultato) - attesi)}"
        )
    return risultato


def main():
    movimenti = leggi_movimenti(INPUT)
    client = anthropic.Anthropic()

    categorie = {}
    indicizzati = list(enumerate(movimenti))
    try:
        for i in range(0, len(indicizzati), BLOCCO):
            categorie.update(categorizza_blocco(client, indicizzati[i : i + BLOCCO]))
    except TypeError as e:
        if "authentication" in str(e):
            raise RuntimeError("credenziali mancanti: imposta la variabile ANTHROPIC_API_KEY")
        raise

    totali = {c: Decimal("0") for c in CATEGORIE}
    out = []
    for i, m in enumerate(movimenti):
        cat = categorie[i]
        totali[cat] += m["importo"]
        out.append(
            {
                "data": m["data"],
                "descrizione": m["descrizione"],
                "importo": float(m["importo"]),
                "categoria": cat,
            }
        )

    risultato = {
        "movimenti": out,
        "totali": {c: float(t.quantize(Decimal("0.01"))) for c, t in totali.items()},
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"Scritti {len(out)} movimenti in {OUTPUT}")


if __name__ == "__main__":
    try:
        main()
    except (anthropic.APIError, OSError, ValueError, RuntimeError) as e:
        sys.exit(f"Errore: {e}")
