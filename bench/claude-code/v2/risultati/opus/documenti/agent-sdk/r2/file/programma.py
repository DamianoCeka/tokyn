"""Risponde alle domande di domande.txt usando i documenti in docs/ e Claude.

Uso: python programma.py  (dalla cartella che contiene docs/ e domande.txt)
Scrive il risultato in risultato.json.
"""

import asyncio
import json
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

CARTELLA_DOCS = Path("docs")
FILE_DOMANDE = Path("domande.txt")
FILE_RISULTATO = Path("risultato.json")
MODELLO = "claude-opus-5-5"


def carica_documenti():
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(CARTELLA_DOCS.glob("*.txt"))}


def carica_domande():
    righe = FILE_DOMANDE.read_text(encoding="utf-8").splitlines()
    return [r.strip() for r in righe if r.strip()]


def prepara_system_prompt(documenti):
    blocchi = "\n\n".join(
        f'<documento nome="{nome}">\n{testo}\n</documento>' for nome, testo in documenti.items()
    )
    return (
        "Sei l'assistente che risponde alle domande dei colleghi sui documenti interni dell'azienda.\n"
        "Rispondi in italiano, in modo breve e preciso, usando solo le informazioni contenute nei "
        "documenti qui sotto. In 'fonte' indica il nome esatto del documento da cui viene la risposta.\n"
        "Se nessun documento contiene la risposta, scrivi in 'risposta' che l'informazione non è "
        "presente nei documenti e metti 'fonte' a null: non inventare.\n\n"
        f"{blocchi}"
    )


def prepara_opzioni(documenti):
    schema = {
        "type": "object",
        "properties": {
            "risposta": {"type": "string"},
            "fonte": {"anyOf": [{"type": "string", "enum": list(documenti)}, {"type": "null"}]},
        },
        "required": ["risposta", "fonte"],
        "additionalProperties": False,
    }
    return ClaudeAgentOptions(
        model=MODELLO,
        system_prompt=prepara_system_prompt(documenti),
        tools=[],  # i documenti sono già nel prompt: nessuno strumento serve
        setting_sources=[],  # ignora impostazioni e CLAUDE.md locali
        output_format={"type": "json_schema", "schema": schema},
    )


async def rispondi(domanda, opzioni, documenti):
    risultato = None
    async for messaggio in query(prompt=domanda, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            risultato = messaggio
    if risultato is None or risultato.is_error or not isinstance(risultato.structured_output, dict):
        dettaglio = getattr(risultato, "errors", None) or getattr(risultato, "subtype", "nessuna risposta")
        raise RuntimeError(f"Claude non ha risposto correttamente alla domanda {domanda!r}: {dettaglio}")

    dati = risultato.structured_output
    fonte = dati.get("fonte")
    if fonte is not None and fonte not in documenti:
        fonte = None
    return {"domanda": domanda, "risposta": dati.get("risposta", "").strip(), "fonte": fonte}


async def main():
    documenti = carica_documenti()
    if not documenti:
        raise SystemExit(f"Nessun file .txt trovato in {CARTELLA_DOCS}/")
    domande = carica_domande()
    opzioni = prepara_opzioni(documenti)

    risultati = []
    for i, domanda in enumerate(domande, 1):
        print(f"[{i}/{len(domande)}] {domanda}")
        voce = await rispondi(domanda, opzioni, documenti)
        print(f"    -> {voce['risposta']} ({voce['fonte']})")
        risultati.append(voce)

    FILE_RISULTATO.write_text(json.dumps(risultati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Risultato scritto in {FILE_RISULTATO}")


if __name__ == "__main__":
    asyncio.run(main())
