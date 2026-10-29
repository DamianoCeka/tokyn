"""Analizza le recensioni in recensioni.txt con Claude e scrive risultato.json."""

import json
import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
FILE_INPUT = Path("recensioni.txt")
FILE_OUTPUT = Path("risultato.json")

SISTEMA = (
    "Analizzi recensioni di prodotti scritte dai clienti. Per la recensione ricevuta "
    "indica il sentimento (positivo, negativo o neutro) e un voto intero da 1 (pessimo) "
    "a 5 (ottimo). Il voto deve essere coerente con il sentimento."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "sentimento": {"type": "string", "enum": ["positivo", "negativo", "neutro"]},
        "voto": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    },
    "required": ["sentimento", "voto"],
    "additionalProperties": False,
}


def analizza(client, testo):
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=1024,
        system=SISTEMA,
        messages=[{"role": "user", "content": f"Recensione:\n{testo}"}],
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
    )
    if risposta.stop_reason != "end_turn":
        raise RuntimeError(f"risposta non completata (stop_reason={risposta.stop_reason})")
    testo_json = next(b.text for b in risposta.content if b.type == "text")
    dati = json.loads(testo_json)
    return {"testo": testo, "sentimento": dati["sentimento"], "voto": dati["voto"]}


def main():
    if not FILE_INPUT.exists():
        sys.exit(f"Errore: {FILE_INPUT} non trovato nella cartella corrente.")
    righe = [r.strip() for r in FILE_INPUT.read_text(encoding="utf-8").splitlines()]
    recensioni = [r for r in righe if r]
    if not recensioni:
        sys.exit(f"Errore: {FILE_INPUT} non contiene recensioni.")

    client = anthropic.Anthropic()
    risultati = []
    for i, testo in enumerate(recensioni, 1):
        try:
            risultati.append(analizza(client, testo))
        except Exception as e:
            sys.exit(f"Errore sulla recensione {i} ({testo[:40]!r}): {e}")
        print(f"[{i}/{len(recensioni)}] {risultati[-1]['sentimento']} {risultati[-1]['voto']}")

    media = round(sum(r["voto"] for r in risultati) / len(risultati), 2)
    FILE_OUTPUT.write_text(
        json.dumps({"recensioni": risultati, "media": media}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Voto medio: {media} - scritto {FILE_OUTPUT}")


if __name__ == "__main__":
    main()
