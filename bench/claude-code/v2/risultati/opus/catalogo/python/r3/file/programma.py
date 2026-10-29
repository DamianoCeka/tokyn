"""Traduce in inglese le descrizioni di catalogo.csv e scrive catalogo_en.csv.

Uso: python programma.py  (dalla cartella che contiene catalogo.csv)
Credenziali: ANTHROPIC_API_KEY (o un profilo `ant auth login`).
"""

import csv
import sys

import anthropic

INPUT = "catalogo.csv"
OUTPUT = "catalogo_en.csv"
SEPARATORE = ";"
COLONNA = "descrizione"
MODELLO = "claude-opus-5-5"

ISTRUZIONI = (
    "You translate product descriptions for an online shop from Italian to English. "
    "Reply with the English translation only: no quotes, no notes, no preamble, a single line. "
    "Write natural e-commerce English and keep the same meaning. Keep every number and "
    "measurement exactly as written (never convert units, e.g. keep '120 x 180 cm'). "
    "Keep proper names and brand names unchanged."
)


def traduci(client: anthropic.Anthropic, testo: str) -> str:
    risposta = client.beta.messages.create(
        model=MODELLO,
        max_tokens=2000,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": testo}],
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError(f"Claude ha rifiutato di tradurre: {testo!r}")
    if risposta.stop_reason == "max_tokens":
        raise RuntimeError(f"Traduzione troncata: {testo!r}")
    traduzione = "".join(b.text for b in risposta.content if b.type == "text")
    # Una descrizione per riga: niente a capo nella cella tradotta.
    traduzione = " ".join(traduzione.split())
    if not traduzione:
        raise RuntimeError(f"Risposta vuota per: {testo!r}")
    return traduzione


def main() -> int:
    with open(INPUT, encoding="utf-8-sig", newline="") as f:
        righe = list(csv.reader(f, delimiter=SEPARATORE))

    if not righe:
        print(f"{INPUT} è vuoto.", file=sys.stderr)
        return 1

    intestazione, prodotti = righe[0], righe[1:]
    if COLONNA not in intestazione:
        print(f"Colonna '{COLONNA}' non trovata nell'intestazione: {intestazione}", file=sys.stderr)
        return 1
    indice = intestazione.index(COLONNA)

    client = anthropic.Anthropic()
    tradotte = {}  # descrizioni ripetute vengono tradotte una volta sola
    risultato = [intestazione]

    for numero, riga in enumerate(prodotti, start=2):
        if not any(cella.strip() for cella in riga):
            risultato.append(riga)  # riga vuota: lasciata com'è
            continue
        if len(riga) <= indice:
            print(f"Riga {numero}: manca la descrizione, lasciata invariata.", file=sys.stderr)
            risultato.append(riga)
            continue
        originale = riga[indice]
        if originale.strip():
            if originale not in tradotte:
                tradotte[originale] = traduci(client, originale)
            nuova = list(riga)
            nuova[indice] = tradotte[originale]
            riga = nuova
        risultato.append(riga)
        print(f"[{numero - 1}/{len(prodotti)}] {riga[0]}: {riga[indice]}")

    # Scrittura solo a traduzione completata, per non lasciare file a metà.
    with open(OUTPUT, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter=SEPARATORE, lineterminator="\n").writerows(risultato)

    print(f"Scritto {OUTPUT} ({len(prodotti)} prodotti).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileNotFoundError as e:
        print(f"File non trovato: {e.filename}", file=sys.stderr)
        sys.exit(1)
    except TypeError as e:
        if "authentication" not in str(e):
            raise
        print("Credenziali Anthropic mancanti: imposta ANTHROPIC_API_KEY.", file=sys.stderr)
        sys.exit(1)
    except anthropic.AuthenticationError:
        print("Credenziali Anthropic non valide o mancanti (imposta ANTHROPIC_API_KEY).", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIConnectionError as e:
        print(f"Impossibile contattare l'API Anthropic: {e}", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIStatusError as e:
        print(f"Errore dall'API Anthropic ({e.status_code}): {e.message}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
