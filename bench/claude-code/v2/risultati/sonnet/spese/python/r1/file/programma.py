"""Categorizza i movimenti di movimenti.csv con Claude e scrive risultato.json."""
import csv
import json
import sys
from decimal import Decimal, InvalidOperation

import anthropic

MODELLO = "claude-opus-5-5"
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
FILE_INPUT = "movimenti.csv"
FILE_OUTPUT = "risultato.json"
BLOCCO = 100  # movimenti per richiesta

ISTRUZIONI = (
    "Assegni una categoria a movimenti di un conto bancario italiano. "
    f"Le categorie ammesse sono: {', '.join(CATEGORIE)}. "
    "Usa 'altro' per ciò che non rientra chiaramente nelle altre, "
    "comprese entrate (stipendi, accrediti), commissioni e movimenti poco chiari. "
    "Rispondi con una categoria per ogni movimento, usando il suo id."
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


def leggi_importo(testo):
    """'-1.234,56' -> Decimal('-1234.56')."""
    try:
        return Decimal(testo.strip().replace(".", "").replace(",", "."))
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
                raise ValueError(f"riga {n}: attesi 3 campi, trovati {len(riga)}")
            data, descrizione, importo = riga
            movimenti.append(
                {"data": data.strip(), "descrizione": descrizione.strip(), "importo": leggi_importo(importo)}
            )
    return movimenti


def categorizza_blocco(client, blocco):
    elenco = "\n".join(
        f"{i}; {m['descrizione']}; {m['importo']}" for i, m in enumerate(blocco)
    )
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=16000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": f"Movimenti (id; descrizione; importo):\n{elenco}"}],
    )
    if risposta.stop_reason != "end_turn":
        raise RuntimeError(f"risposta non completa (stop_reason={risposta.stop_reason})")
    testo = next(b.text for b in risposta.content if b.type == "text")
    assegnate = {c["id"]: c["categoria"] for c in json.loads(testo)["categorie"]}
    if set(assegnate) != set(range(len(blocco))):
        raise RuntimeError("Claude non ha categorizzato esattamente tutti i movimenti")
    return [assegnate[i] for i in range(len(blocco))]


def categorizza(client, movimenti):
    categorie = []
    for i in range(0, len(movimenti), BLOCCO):
        categorie += categorizza_blocco(client, movimenti[i : i + BLOCCO])
    return categorie


def main():
    movimenti = leggi_movimenti(FILE_INPUT)
    categorie = categorizza(anthropic.Anthropic(), movimenti)

    totali = {c: Decimal(0) for c in CATEGORIE}
    for m, c in zip(movimenti, categorie):
        totali[c] += m["importo"]

    risultato = {
        "movimenti": [
            {"data": m["data"], "descrizione": m["descrizione"], "importo": float(m["importo"]), "categoria": c}
            for m, c in zip(movimenti, categorie)
        ],
        "totali": {c: float(round(t, 2)) + 0.0 for c, t in totali.items()},
    }
    with open(FILE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"{len(movimenti)} movimenti categorizzati, scritto {FILE_OUTPUT}")


if __name__ == "__main__":
    try:
        main()
    except (anthropic.APIError, OSError, ValueError, RuntimeError) as e:
        sys.exit(f"Errore: {e}")
    except TypeError as e:
        if "authentication" in str(e):
            sys.exit("Errore: credenziali mancanti, imposta ANTHROPIC_API_KEY")
        raise
