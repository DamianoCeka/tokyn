"""Traduce in inglese le descrizioni di catalogo.csv e scrive catalogo_en.csv."""

import csv
import sys

import anthropic

INPUT = "catalogo.csv"
OUTPUT = "catalogo_en.csv"
MODEL = "claude-opus-5-5"

SYSTEM = (
    "You translate Italian product descriptions for an online shop into English. "
    "Write natural, concise e-commerce English, keeping the same tone and level of detail. "
    "Keep measurements, numbers and units exactly as they are (e.g. '28 cm', '120 x 180 cm', '30 litri' -> '30 liters'). "
    "Reply with the English translation only: one line, no quotes, no explanations."
)


def translate(client: anthropic.Anthropic, name: str, description: str) -> str:
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Product name (do not translate, context only): {name}\n"
                f"Description to translate:\n{description}",
            }
        ],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"traduzione rifiutata per '{name}'")
    if response.stop_reason == "max_tokens":
        raise RuntimeError(f"risposta troncata per '{name}'")
    text = "".join(block.text for block in response.content if block.type == "text")
    # La descrizione deve restare su una sola riga del CSV.
    text = " ".join(text.split())
    if not text:
        raise RuntimeError(f"traduzione vuota per '{name}'")
    return text


def main() -> None:
    with open(INPUT, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    if not rows:
        sys.exit(f"{INPUT} è vuoto")

    header, products = rows[0], rows[1:]
    i_name = header.index("nome")
    i_desc = header.index("descrizione")

    client = anthropic.Anthropic()
    for n, row in enumerate(products, start=1):
        if not row:
            continue
        print(f"[{n}/{len(products)}] {row[0]}", file=sys.stderr)
        row[i_desc] = translate(client, row[i_name], row[i_desc])

    with open(OUTPUT, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter=";", lineterminator="\n").writerows([header, *products])
    print(f"Scritto {OUTPUT} ({len(products)} prodotti)", file=sys.stderr)


if __name__ == "__main__":
    main()
