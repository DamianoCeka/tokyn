"""Estrae decisioni e azioni da verbale.txt usando Claude e scrive risultato.json."""

import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

CARTELLA = Path.cwd()
INPUT = CARTELLA / "verbale.txt"
OUTPUT = CARTELLA / "risultato.json"

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
Analizzi verbali di riunioni di lavoro in italiano ed estrai informazioni strutturate.

- "decisioni": le decisioni effettivamente prese dal gruppo, ciascuna come frase breve \
e autonoma (non domande, opinioni o chiacchiere come il parcheggio).
- "azioni": i compiti assegnati e accettati. Per ognuna: "cosa" (che cosa va fatto, \
frase breve all'infinito), "chi" (solo il nome di chi se ne occupa, non di chi assegna il compito), \
"entro" (scadenza in formato AAAA-MM-GG).
- Le date relative (es. "venerdì prossimo") vanno risolte rispetto alla data della riunione.
- Non inventare nulla: se una scadenza non è indicata nel verbale, usa una stringa vuota.
"""


def _estrai_json(testo: str) -> dict:
    m = re.search(r"\{.*\}", testo, re.DOTALL)
    return json.loads(m.group(0) if m else testo)


def _valida(dati: dict) -> dict:
    decisioni = [str(d).strip() for d in dati["decisioni"] if str(d).strip()]
    azioni = []
    for a in dati["azioni"]:
        entro = str(a["entro"]).strip()
        if entro:
            date.fromisoformat(entro)  # solleva ValueError se non è AAAA-MM-GG
        azioni.append(
            {"cosa": str(a["cosa"]).strip(), "chi": str(a["chi"]).strip(), "entro": entro}
        )
    return {"decisioni": decisioni, "azioni": azioni}


async def analizza(verbale: str) -> dict:
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        tools=[],  # nessuno strumento: solo analisi del testo
        max_turns=3,
        cwd=str(CARTELLA),
        setting_sources=[],
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    prompt = f"Verbale della riunione:\n\n{verbale}"
    testo = ""
    strutturato = None
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock):
                    testo += b.text
        elif isinstance(msg, ResultMessage):
            if msg.is_error:
                raise RuntimeError(f"Errore da Claude: {msg.result or msg.errors}")
            if msg.structured_output is not None:
                strutturato = msg.structured_output
            elif msg.result:
                testo = msg.result
    # niente return dentro il ciclo: il generatore deve chiudersi da solo
    return _valida(strutturato if strutturato is not None else _estrai_json(testo))


def main() -> int:
    if not INPUT.exists():
        print(f"File non trovato: {INPUT}", file=sys.stderr)
        return 1
    verbale = INPUT.read_text(encoding="utf-8")
    try:
        risultato = asyncio.run(analizza(verbale))
    except Exception as e:
        print(f"Impossibile analizzare il verbale: {e}", file=sys.stderr)
        return 1
    OUTPUT.write_text(json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scritto {OUTPUT.name}: {len(risultato['decisioni'])} decisioni, "
          f"{len(risultato['azioni'])} azioni")
    return 0


if __name__ == "__main__":
    sys.exit(main())
