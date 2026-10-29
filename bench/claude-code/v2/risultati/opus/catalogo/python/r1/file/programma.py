"""Traduce in inglese le descrizioni di catalogo.csv e scrive catalogo_en.csv.

Uso: python programma.py  (dalla cartella che contiene catalogo.csv)
Richiede il pacchetto `anthropic` e le credenziali (es. ANTHROPIC_API_KEY).
"""

import csv
import sys

import anthropic

INPUT = "catalogo.csv"
OUTPUT = "catalogo_en.csv"
MODEL = "claude-opus-5-5"

SYSTEM = (
    "You translate Italian product descriptions for an online shop into natural, "
    "concise English suitable for an e-commerce product listing. Keep measurements, "
    "numbers and units exactly as they are. Reply with the English translation only: "
    "no quotes, no notes, a single line."
)


def traduci(client: anthropic.Anthropic, testo: str) -> str:
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        messages=[{"role": "user", "content": testo}],
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"risposta incompleta (stop_reason={response.stop_reason})")
    testo_en = "".join(b.text for b in response.content if b.type == "text")
    # Una riga sola, senza separatori spuri ai bordi
    return " ".join(testo_en.split())


def main() -> int:
    with open(INPUT, encoding="utf-8-sig", newline="") as f:
        righe = list(csv.reader(f, delimiter=";"))
    if not righe:
        print(f"{INPUT} è vuoto", file=sys.stderr)
        return 1

    intestazione, prodotti = righe[0], righe[1:]
    try:
        col = intestazione.index("descrizione")
    except ValueError:
        print(f"Colonna 'descrizione' non trovata in {INPUT}", file=sys.stderr)
        return 1

    client = anthropic.Anthropic()
    output = [intestazione]
    for n, riga in enumerate(prodotti, start=2):
        if len(riga) <= col or not riga[col].strip():
            output.append(riga)  # riga vuota o senza descrizione: invariata
            continue
        try:
            tradotta = traduci(client, riga[col])
        except (anthropic.APIError, RuntimeError) as e:
            print(f"Errore alla riga {n} ({riga[0]}): {e}", file=sys.stderr)
            return 1
        nuova = list(riga)
        nuova[col] = tradotta
        output.append(nuova)
        print(f"{riga[0]}: {tradotta}")

    with open(OUTPUT, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter=";", lineterminator="\n").writerows(output)
    print(f"Scritto {OUTPUT} ({len(prodotti)} prodotti)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
