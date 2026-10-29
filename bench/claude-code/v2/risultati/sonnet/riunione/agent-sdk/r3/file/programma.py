"""Ricava decisioni e azioni da verbale.txt usando Claude e scrive risultato.json."""

import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

INPUT = Path("verbale.txt")
OUTPUT = Path("risultato.json")

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

SYSTEM_PROMPT = """\
Ricevi la trascrizione di una riunione di team. Estrai:
- decisioni: le decisioni effettivamente prese, ciascuna come frase breve e \
autonoma. Non includere opinioni, domande o chiacchiere.
- azioni: i compiti assegnati. Per ognuna: "cosa" (che cosa va fatto, \
all'infinito, es. "Preparare il preventivo"), "chi" (solo il nome di battesimo \
di chi se ne occupa, come scritto nel verbale) ed "entro" (la scadenza nel \
formato AAAA-MM-GG).

Regole:
- Includi solo azioni che qualcuno ha accettato o a cui è stata assegnata una \
persona. Non inventare nulla che non sia nel testo.
- Se la scadenza è relativa (es. "venerdì prossimo"), calcolala partendo dalla \
data della riunione indicata nel verbale. Se non c'è alcuna scadenza, usa null.
- Rispondi in italiano."""


def valida(r: dict) -> None:
    for a in r["azioni"]:
        e = a["entro"]
        if e is not None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", e):
                raise ValueError(f"Scadenza non valida: {e!r}")
            date.fromisoformat(e)


async def main() -> int:
    if not INPUT.exists():
        print(f"Errore: non trovo {INPUT} nella cartella corrente.", file=sys.stderr)
        return 1
    testo = INPUT.read_text(encoding="utf-8")
    if not testo.strip():
        print(f"Errore: {INPUT} è vuoto.", file=sys.stderr)
        return 1

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        tools=[],  # solo analisi del testo: nessun accesso a file o shell
        setting_sources=[],
        output_format={"type": "json_schema", "schema": SCHEMA},
    )

    risultato = None
    async for msg in query(prompt=f"Verbale della riunione:\n\n{testo}", options=options):
        if isinstance(msg, ResultMessage):
            if msg.is_error:
                print(f"Errore da Claude: {msg.result}", file=sys.stderr)
                return 1
            risultato = msg.structured_output

    if not isinstance(risultato, dict):
        print("Errore: Claude non ha restituito un risultato strutturato.", file=sys.stderr)
        return 1
    valida(risultato)

    OUTPUT.write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Scritto {OUTPUT}: {len(risultato['decisioni'])} decisioni, "
        f"{len(risultato['azioni'])} azioni."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
