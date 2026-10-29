#!/usr/bin/env python3
"""Traduce in inglese la descrizione dei prodotti di catalogo.csv usando Claude.

Uso: python programma.py   (dalla cartella che contiene catalogo.csv)
Richiede: pip install anthropic, e ANTHROPIC_API_KEY impostata.
Scrive catalogo_en.csv: stessa intestazione, stesso separatore, stesso ordine;
cambia solo la colonna "descrizione".
"""
import csv
import sys
from concurrent.futures import ThreadPoolExecutor

import anthropic

INPUT = "catalogo.csv"
OUTPUT = "catalogo_en.csv"
DELIMITER = ";"
MODEL = "claude-opus-5-5"
WORKERS = 4

SYSTEM = (
    "You translate product descriptions for an online shop from Italian to English. "
    "Reply with the English translation only: no quotes, no notes, no preamble. "
    "Keep the register short and catalogue-like, keep numbers and units exactly as "
    "written (e.g. '28 cm', '120 x 180 cm', '40 ore' -> '40 hours'), and do not add "
    "or drop information. Never translate or alter anything that is a proper name."
)

client = anthropic.Anthropic()


def translate(text: str) -> str:
    if not text.strip():
        return text
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": text}],
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"risposta non completa (stop_reason={response.stop_reason})")
    result = "".join(b.text for b in response.content if b.type == "text").strip()
    if not result:
        raise RuntimeError("risposta vuota")
    # il separatore e gli a capo romperebbero la struttura del file
    return " ".join(result.replace(DELIMITER, ",").split())


def main() -> int:
    with open(INPUT, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f, delimiter=DELIMITER))
    if not rows:
        print(f"{INPUT} è vuoto", file=sys.stderr)
        return 1

    header, products = rows[0], rows[1:]
    try:
        col = header.index("descrizione")
    except ValueError:
        print("Colonna 'descrizione' non trovata nell'intestazione", file=sys.stderr)
        return 1

    for n, row in enumerate(products, start=2):
        if len(row) != len(header):
            print(f"Riga {n}: attese {len(header)} colonne, trovate {len(row)}", file=sys.stderr)
            return 1

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            translated = list(pool.map(translate, (r[col] for r in products)))
    except TypeError as e:
        if "authentication" not in str(e):
            raise
        print("Credenziali mancanti: imposta ANTHROPIC_API_KEY.", file=sys.stderr)
        return 1
    except anthropic.AnthropicError as e:
        print(f"Errore API: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"Errore di traduzione: {e}", file=sys.stderr)
        return 1

    for row, desc in zip(products, translated):
        row[col] = desc

    # Scrittura solo a traduzione completata: niente file a metà in caso di errore.
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter=DELIMITER, lineterminator="\n").writerows([header, *products])
    print(f"Tradotte {len(products)} descrizioni -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
