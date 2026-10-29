import json
from pathlib import Path

import anyio
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

DOCS_DIR = Path("docs")
DOMANDE = Path("domande.txt")
RISULTATO = Path("risultato.json")


def carica_documenti():
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(DOCS_DIR.glob("*.txt"))}


def costruisci_opzioni(documenti):
    corpo = "\n\n".join(f'<documento nome="{n}">\n{t}\n</documento>' for n, t in documenti.items())
    system_prompt = (
        "Rispondi alle domande dei dipendenti usando esclusivamente i documenti aziendali qui sotto. "
        "Rispondi in italiano, in modo breve e preciso, riportando i dati (numeri, orari, indirizzi) "
        "come scritti nel documento. Indica in `fonte` il nome esatto del file da cui hai preso la risposta. "
        "Se i documenti non contengono la risposta, scrivi in `risposta` che l'informazione non è presente "
        "nei documenti e imposta `fonte` a null: non inventare.\n\n" + corpo
    )
    schema = {
        "type": "object",
        "properties": {
            "risposta": {"type": "string"},
            "fonte": {"enum": list(documenti) + [None]},
        },
        "required": ["risposta", "fonte"],
        "additionalProperties": False,
    }
    return ClaudeAgentOptions(
        system_prompt=system_prompt,
        tools=[],  # tutto il contesto è già nel prompt, nessuno strumento necessario
        setting_sources=[],
        max_turns=3,
        output_format={"type": "json_schema", "schema": schema},
    )


async def rispondi(domanda, opzioni):
    esito = None
    async for msg in query(prompt=domanda, options=opzioni):
        if isinstance(msg, ResultMessage):
            esito = msg
    if esito is None or esito.is_error or not isinstance(esito.structured_output, dict):
        raise RuntimeError(f"Nessuna risposta valida per: {domanda!r}")
    return {
        "domanda": domanda,
        "risposta": esito.structured_output["risposta"],
        "fonte": esito.structured_output["fonte"],
    }


async def main():
    documenti = carica_documenti()
    domande = [r.strip() for r in DOMANDE.read_text(encoding="utf-8").splitlines() if r.strip()]
    opzioni = costruisci_opzioni(documenti)
    risultati = [await rispondi(d, opzioni) for d in domande]
    RISULTATO.write_text(json.dumps(risultati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scritte {len(risultati)} risposte in {RISULTATO}")


if __name__ == "__main__":
    anyio.run(main)
