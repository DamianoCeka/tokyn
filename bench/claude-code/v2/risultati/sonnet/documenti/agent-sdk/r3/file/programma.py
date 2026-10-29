"""Risponde alle domande di domande.txt usando i documenti in docs/ e Claude.

Avvio: python programma.py (dalla cartella che contiene docs/ e domande.txt).
Scrive risultato.json: [{"domanda", "risposta", "fonte"}, ...] nell'ordine delle domande.
"""

import asyncio
import json
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

BASE = Path.cwd()
CONCORRENZA = 4
TENTATIVI = 3

SCHEMA = {
    "type": "object",
    "properties": {
        "risposta": {"type": "string"},
        "fonte": {"type": ["string", "null"]},
    },
    "required": ["risposta", "fonte"],
    "additionalProperties": False,
}


def carica_documenti() -> dict[str, str]:
    docs = {p.name: p.read_text(encoding="utf-8") for p in sorted((BASE / "docs").glob("*.txt"))}
    if not docs:
        sys.exit("Nessun file .txt trovato in docs/")
    return docs


def costruisci_system_prompt(docs: dict[str, str]) -> str:
    testo = "\n\n".join(f'<documento nome="{nome}">\n{contenuto}\n</documento>' for nome, contenuto in docs.items())
    return (
        "Sei l'assistente interno di un'azienda e rispondi alle domande dei colleghi "
        "basandoti ESCLUSIVAMENTE sui documenti qui sotto.\n"
        "- Rispondi in italiano, in modo breve e preciso, riportando i dati (numeri, orari, nomi) come nel documento.\n"
        "- 'fonte' deve essere il nome esatto del file (attributo nome) da cui hai ricavato la risposta.\n"
        "- Se i documenti non contengono la risposta, scrivi in 'risposta' che l'informazione non è presente "
        "nei documenti e metti 'fonte' a null. Non usare conoscenze esterne.\n\n"
        f"{testo}"
    )


async def rispondi(domanda: str, options: ClaudeAgentOptions, docs: dict[str, str]) -> dict:
    ultimo_errore = None
    for _ in range(TENTATIVI):
        try:
            async for msg in query(prompt=domanda, options=options):
                if isinstance(msg, ResultMessage):
                    if msg.is_error or not isinstance(msg.structured_output, dict):
                        raise RuntimeError(f"risposta non valida: {msg.result!r}")
                    out = msg.structured_output
                    fonte = out.get("fonte")
                    if fonte not in docs:
                        fonte = None
                    return {"domanda": domanda, "risposta": out["risposta"], "fonte": fonte}
            raise RuntimeError("nessun risultato ricevuto")
        except Exception as e:  # riprova su errori transitori
            ultimo_errore = e
    sys.exit(f"Errore sulla domanda {domanda!r}: {ultimo_errore}")


async def main() -> None:
    docs = carica_documenti()
    domande = [r.strip() for r in (BASE / "domande.txt").read_text(encoding="utf-8").splitlines() if r.strip()]

    options = ClaudeAgentOptions(
        system_prompt=costruisci_system_prompt(docs),
        tools=[],  # nessuno strumento: i documenti sono già nel prompt
        max_turns=1,
        setting_sources=[],  # ignora configurazioni locali
        output_format={"type": "json_schema", "schema": SCHEMA},
    )

    sem = asyncio.Semaphore(CONCORRENZA)

    async def lavora(d: str) -> dict:
        async with sem:
            return await rispondi(d, options, docs)

    risultati = await asyncio.gather(*(lavora(d) for d in domande))  # gather mantiene l'ordine

    (BASE / "risultato.json").write_text(json.dumps(risultati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scritte {len(risultati)} risposte in risultato.json")


if __name__ == "__main__":
    asyncio.run(main())
