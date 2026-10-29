"""Risponde alle domande di domande.txt usando i documenti in docs/ e Claude.

Uso: python programma.py   (dalla cartella che contiene docs/ e domande.txt)
Scrive risultato.json con domanda, risposta e fonte per ogni domanda.
"""

import asyncio
import json
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

CARTELLA_DOCS = Path("docs")
FILE_DOMANDE = Path("domande.txt")
FILE_RISULTATO = Path("risultato.json")
MODELLO = "claude-opus-5-5"
MAX_IN_PARALLELO = 4
NON_TROVATO = "Non trovato nei documenti"


def carica_documenti() -> dict[str, str]:
    documenti = {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(CARTELLA_DOCS.glob("*.txt"))
    }
    if not documenti:
        sys.exit(f"Nessun file .txt trovato in {CARTELLA_DOCS}/")
    return documenti


def carica_domande() -> list[str]:
    righe = FILE_DOMANDE.read_text(encoding="utf-8").splitlines()
    return [r.strip() for r in righe if r.strip()]


def crea_system_prompt(documenti: dict[str, str]) -> str:
    blocchi = "\n\n".join(
        f'<documento nome="{nome}">\n{testo.strip()}\n</documento>'
        for nome, testo in documenti.items()
    )
    return (
        "Sei un assistente che risponde alle domande dei dipendenti usando "
        "SOLO i documenti interni dell'azienda riportati qui sotto.\n"
        "Rispondi in italiano, in modo breve e preciso, riportando i dati "
        "esatti del documento (cifre, nomi, scadenze).\n"
        "In 'fonte' indica il nome del file del documento da cui hai preso la "
        "risposta. Se nessun documento contiene la risposta, scrivi "
        f"'{NON_TROVATO}' come risposta e lascia la fonte vuota (null): "
        "non inventare.\n\n"
        f"{blocchi}"
    )


def crea_schema(nomi_file: list[str]) -> dict:
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "risposta": {"type": "string"},
                "fonte": {"anyOf": [{"type": "string", "enum": nomi_file}, {"type": "null"}]},
            },
            "required": ["risposta", "fonte"],
            "additionalProperties": False,
        },
    }


async def rispondi(domanda: str, opzioni: ClaudeAgentOptions, nomi_file: list[str]) -> dict:
    esito = None
    async for messaggio in query(prompt=domanda, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            esito = messaggio

    if esito is None or esito.is_error or not isinstance(esito.structured_output, dict):
        dettaglio = esito.errors or esito.result if esito else "nessuna risposta"
        raise RuntimeError(f"Errore sulla domanda {domanda!r}: {dettaglio}")

    risposta = str(esito.structured_output.get("risposta", "")).strip()
    fonte = esito.structured_output.get("fonte")
    if fonte not in nomi_file:
        fonte = None
    return {"domanda": domanda, "risposta": risposta, "fonte": fonte}


async def main() -> None:
    documenti = carica_documenti()
    domande = carica_domande()
    nomi_file = list(documenti)

    opzioni = ClaudeAgentOptions(
        model=MODELLO,
        system_prompt=crea_system_prompt(documenti),
        output_format=crea_schema(nomi_file),
        tools=[],              # i documenti sono già nel prompt: niente strumenti
        setting_sources=[],    # ignora impostazioni e CLAUDE.md locali
        effort="low",
    )

    semaforo = asyncio.Semaphore(MAX_IN_PARALLELO)

    async def con_limite(domanda: str) -> dict:
        async with semaforo:
            risultato = await rispondi(domanda, opzioni, nomi_file)
            print(f"- {domanda}\n  -> {risultato['risposta']} [{risultato['fonte']}]")
            return risultato

    # gather mantiene l'ordine delle domande
    risultati = await asyncio.gather(*(con_limite(d) for d in domande))

    FILE_RISULTATO.write_text(
        json.dumps(risultati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nScritto {FILE_RISULTATO} ({len(risultati)} risposte)")


if __name__ == "__main__":
    asyncio.run(main())
