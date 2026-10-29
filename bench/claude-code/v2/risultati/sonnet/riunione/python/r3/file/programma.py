"""Estrae decisioni e azioni da verbale.txt usando Claude e scrive risultato.json."""
import json
import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
FILE_VERBALE = Path("verbale.txt")
FILE_RISULTATO = Path("risultato.json")

ISTRUZIONI = """Ricevi la trascrizione di una riunione di team. Estrai:
- "decisioni": le decisioni effettivamente prese, ciascuna come frase breve e autonoma. \
Non includere discussioni, domande o argomenti senza una conclusione.
- "azioni": i compiti assegnati e accettati. Per ognuna: "cosa" (che cosa va fatto), \
"chi" (solo il nome di chi se ne occupa) ed "entro" (scadenza in formato AAAA-MM-GG).

Le date relative (es. "venerdì prossimo") vanno risolte rispetto alla data della riunione \
indicata nella trascrizione. Se una scadenza non viene detta o non si può ricavare con \
certezza, usa null per "entro": non inventarla. Non aggiungere nulla che non sia nel testo."""

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
                    "entro": {"type": ["string", "null"]},
                },
                "required": ["cosa", "chi", "entro"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["decisioni", "azioni"],
    "additionalProperties": False,
}


def main():
    if not FILE_VERBALE.is_file():
        sys.exit(f"Errore: non trovo {FILE_VERBALE} nella cartella corrente.")
    trascrizione = FILE_VERBALE.read_text(encoding="utf-8")
    if not trascrizione.strip():
        sys.exit(f"Errore: {FILE_VERBALE} è vuoto.")

    client = anthropic.Anthropic()
    try:
        risposta = client.messages.create(
            model=MODELLO,
            max_tokens=16000,
            system=ISTRUZIONI,
            messages=[{"role": "user", "content": f"<trascrizione>\n{trascrizione}\n</trascrizione>"}],
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
        )
    except (anthropic.AuthenticationError, TypeError) as e:
        # l'SDK solleva TypeError quando non trova alcuna credenziale
        if isinstance(e, TypeError) and "authentication" not in str(e):
            raise
        sys.exit("Errore: credenziali mancanti o non valide. Imposta ANTHROPIC_API_KEY.")
    except anthropic.APIConnectionError as e:
        sys.exit(f"Errore di connessione all'API: {e}")
    except anthropic.APIStatusError as e:
        sys.exit(f"Errore dell'API ({e.status_code}): {e.message}")

    if risposta.stop_reason in ("refusal", "max_tokens"):
        sys.exit(f"Risposta non utilizzabile (stop_reason={risposta.stop_reason}).")

    testo = next(b.text for b in risposta.content if b.type == "text")
    risultato = json.loads(testo)

    FILE_RISULTATO.write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Scritto {FILE_RISULTATO}: {len(risultato['decisioni'])} decisioni, "
        f"{len(risultato['azioni'])} azioni."
    )


if __name__ == "__main__":
    main()
