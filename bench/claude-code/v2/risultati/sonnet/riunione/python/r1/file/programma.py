"""Ricava decisioni e azioni da verbale.txt usando Claude e scrive risultato.json."""

import json
import re
import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
FILE_VERBALE = Path("verbale.txt")
FILE_RISULTATO = Path("risultato.json")

ISTRUZIONI = """\
Ricevi la trascrizione di una riunione di team. Estrai:
- "decisioni": le decisioni effettivamente prese, ciascuna come frase breve e autonoma.
  Non includere discussioni, opinioni o domande rimaste senza esito.
- "azioni": i compiti assegnati e accettati. Per ciascuno: "cosa" (che cosa va fatto,
  all'infinito, es. "Preparare il preventivo"), "chi" (solo il nome di chi se ne occupa,
  come appare nella trascrizione) ed "entro" (la scadenza nel formato AAAA-MM-GG).
Se la scadenza è relativa (es. "venerdì prossimo"), calcolala partendo dalla data della
riunione indicata nella trascrizione. Se una scadenza non è indicata o non è ricavabile,
usa null: non inventarla. Scrivi in italiano."""

SCHEMA = {
    "type": "object",
    "properties": {
        "decisioni": {"type": "array", "items": {"type": "string"}},
        "azioni": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cosa": {"type": "string"},
                    "chi": {"type": "string"},
                    "entro": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": ["cosa", "chi", "entro"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["decisioni", "azioni"],
    "additionalProperties": False,
}


def estrai(trascrizione: str) -> dict:
    client = anthropic.Anthropic()
    with client.messages.stream(
        model=MODELLO,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=ISTRUZIONI,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": trascrizione}],
    ) as stream:
        risposta = stream.get_final_message()

    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato la richiesta.")
    if risposta.stop_reason == "max_tokens":
        raise RuntimeError("Risposta troncata: trascrizione troppo lunga?")

    testo = "".join(b.text for b in risposta.content if b.type == "text")
    return json.loads(testo)


def valida(risultato: dict) -> dict:
    for azione in risultato["azioni"]:
        entro = azione["entro"]
        if entro is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", entro):
            raise ValueError(f"Scadenza non valida: {entro!r}")
    return risultato


def main() -> int:
    if not FILE_VERBALE.is_file():
        print(f"Non trovo {FILE_VERBALE} in questa cartella.", file=sys.stderr)
        return 1
    trascrizione = FILE_VERBALE.read_text(encoding="utf-8")
    if not trascrizione.strip():
        print(f"{FILE_VERBALE} è vuoto.", file=sys.stderr)
        return 1

    try:
        risultato = valida(estrai(trascrizione))
    except (anthropic.AuthenticationError, TypeError) as e:
        if isinstance(e, TypeError) and "authentication" not in str(e):
            raise
        print("Chiave API mancante o non valida: imposta ANTHROPIC_API_KEY.", file=sys.stderr)
        return 1
    except anthropic.APIError as e:
        print(f"Errore dell'API di Claude: {e}", file=sys.stderr)
        return 1
    except (RuntimeError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1

    FILE_RISULTATO.write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Scritto {FILE_RISULTATO}: {len(risultato['decisioni'])} decisioni, "
          f"{len(risultato['azioni'])} azioni.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
