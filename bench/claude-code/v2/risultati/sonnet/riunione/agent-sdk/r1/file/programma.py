"""Estrae decisioni e azioni da verbale.txt con Claude e scrive risultato.json."""

import json
import re
import sys
from pathlib import Path

import anyio
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

VERBALE = Path("verbale.txt")
RISULTATO = Path("risultato.json")

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
                    "entro": {"type": "string"},
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
Analizzi verbali di riunioni in italiano ed estrai informazioni strutturate.

- "decisioni": le decisioni effettivamente prese dal gruppo, ciascuna come frase breve \
e autonoma. Non includere domande, opinioni, discussioni o chiacchiere \
non legate a una decisione.
- "azioni": i compiti assegnati e accettati. Per ognuno: "cosa" (che cosa va fatto, \
come frase breve all'infinito), "chi" (solo il nome di chi se ne occupa, \
es. "Paolo") ed "entro" (la scadenza nel formato AAAA-MM-GG).
- Se la scadenza è relativa (es. "venerdì prossimo"), calcolala partendo dalla \
data della riunione indicata nel verbale. Non inventare nulla che non sia nel testo.
"""


def estrai(testo: str) -> dict:
    prompt = f"Ecco il verbale della riunione.\n\n<verbale>\n{testo}\n</verbale>"
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        tools=[],  # nessuno strumento: serve solo ragionare sul testo
        max_turns=5,
        output_format={"type": "json_schema", "schema": SCHEMA},
    )

    async def run() -> dict:
        risultato = None
        async for msg in query(prompt=prompt, options=options):  # consumo tutto lo stream
            if isinstance(msg, ResultMessage):
                risultato = msg
        if risultato is None:
            raise RuntimeError("Nessun risultato ricevuto da Claude")
        if risultato.is_error or risultato.structured_output is None:
            raise RuntimeError(f"Risposta non valida da Claude: {risultato.errors or risultato.result}")
        return risultato.structured_output

    return anyio.run(run)


def controlla(dati: dict) -> None:
    for a in dati["azioni"]:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a["entro"]):
            raise ValueError(f"Scadenza non nel formato AAAA-MM-GG: {a}")


def main() -> int:
    if not VERBALE.exists():
        print(f"Non trovo {VERBALE} nella cartella corrente.", file=sys.stderr)
        return 1
    testo = VERBALE.read_text(encoding="utf-8")
    if not testo.strip():
        print(f"{VERBALE} è vuoto.", file=sys.stderr)
        return 1
    try:
        dati = estrai(testo)
        controlla(dati)
    except Exception as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    RISULTATO.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scritto {RISULTATO}: {len(dati['decisioni'])} decisioni, {len(dati['azioni'])} azioni.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
