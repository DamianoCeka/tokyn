"""Ricava decisioni e azioni da verbale.txt usando Claude e le scrive in risultato.json.

Uso: python programma.py   (dalla cartella che contiene verbale.txt)
"""

import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

FILE_VERBALE = Path("verbale.txt")
FILE_RISULTATO = Path("risultato.json")

SCHEMA = {
    "type": "object",
    "properties": {
        "decisioni": {
            "type": "array",
            "items": {"type": "string"},
        },
        "azioni": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cosa": {"type": "string"},
                    "chi": {"type": "string"},
                    "entro": {
                        "type": ["string", "null"],
                        "pattern": r"^\d{4}-\d{2}-\d{2}$",
                    },
                },
                "required": ["cosa", "chi", "entro"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["decisioni", "azioni"],
    "additionalProperties": False,
}

ISTRUZIONI = """Sei un assistente che analizza le trascrizioni delle riunioni di un team.
Dalla trascrizione ricava:

- "decisioni": le decisioni effettivamente prese durante la riunione, ciascuna come frase
  breve in italiano. Non includere proposte rimaste aperte, opinioni o chiacchiere fuori tema.
- "azioni": i compiti assegnati a una persona. Per ognuno indica
  - "cosa": che cosa va fatto, come frase breve che inizia con un verbo all'infinito;
  - "chi": il nome della persona che se ne occupa, come compare nella trascrizione;
  - "entro": la scadenza nel formato AAAA-MM-GG. Se è espressa in modo relativo
    ("venerdì prossimo", "tra due settimane"), calcolala a partire dalla data della riunione
    indicata nella trascrizione (o, se manca, dalla data di oggi). Se nella trascrizione non
    c'è alcuna scadenza per quel compito, usa null: non inventarla.

Rispondi solo con i dati strutturati richiesti."""


async def estrai(trascrizione: str) -> dict:
    prompt = (
        f"Data di oggi: {date.today().isoformat()}\n\n"
        "Trascrizione della riunione:\n"
        "<trascrizione>\n"
        f"{trascrizione}\n"
        "</trascrizione>"
    )
    opzioni = ClaudeAgentOptions(
        system_prompt=ISTRUZIONI,
        tools=[],  # basta il testo: nessun accesso a file, shell o web
        setting_sources=[],
        output_format={"type": "json_schema", "schema": SCHEMA},
    )

    risultato = None
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            if messaggio.is_error or messaggio.structured_output is None:
                dettagli = messaggio.errors or messaggio.result or messaggio.subtype
                raise RuntimeError(f"Claude non ha restituito un risultato valido: {dettagli}")
            risultato = messaggio.structured_output
    if risultato is None:
        raise RuntimeError("Nessuna risposta ricevuta da Claude.")
    return risultato


def controlla(dati: dict) -> dict:
    """Verifica la forma del risultato e normalizza le date."""
    decisioni = [str(d).strip() for d in dati.get("decisioni", []) if str(d).strip()]
    azioni = []
    for a in dati.get("azioni", []):
        entro = a.get("entro")
        if entro is not None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", entro):
                raise ValueError(f"Scadenza non nel formato AAAA-MM-GG: {entro!r}")
            date.fromisoformat(entro)  # solleva errore se la data non esiste
        azioni.append({"cosa": a["cosa"].strip(), "chi": a["chi"].strip(), "entro": entro})
    return {"decisioni": decisioni, "azioni": azioni}


def main() -> int:
    if not FILE_VERBALE.exists():
        print(f"Errore: non trovo {FILE_VERBALE} nella cartella corrente.", file=sys.stderr)
        return 1
    trascrizione = FILE_VERBALE.read_text(encoding="utf-8").strip()
    if not trascrizione:
        print(f"Errore: {FILE_VERBALE} è vuoto.", file=sys.stderr)
        return 1

    try:
        dati = controlla(asyncio.run(estrai(trascrizione)))
    except Exception as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1

    FILE_RISULTATO.write_text(
        json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Scritto {FILE_RISULTATO}: {len(dati['decisioni'])} decisioni, "
        f"{len(dati['azioni'])} azioni."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
