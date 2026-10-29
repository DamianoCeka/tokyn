import csv
import json
import sys
from decimal import Decimal

import anyio
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
BLOCCO = 100  # movimenti per richiesta a Claude

SYSTEM_PROMPT = (
    "Sei un classificatore di movimenti bancari italiani. Assegni a ogni movimento "
    "esattamente una di queste categorie: " + ", ".join(CATEGORIE) + ". "
    "Usa 'altro' per ciò che non rientra chiaramente nelle altre (stipendi, commissioni, "
    "bonifici, ecc.). Rispondi solo con i dati strutturati richiesti."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "categorie": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "indice": {"type": "integer"},
                    "categoria": {"type": "string", "enum": CATEGORIE},
                },
                "required": ["indice", "categoria"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["categorie"],
    "additionalProperties": False,
}


def leggi_movimenti(percorso):
    movimenti = []
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        for riga in csv.DictReader(f, delimiter=";"):
            importo = Decimal(riga["importo"].strip().replace(".", "").replace(",", "."))
            movimenti.append(
                {"data": riga["data"].strip(), "descrizione": riga["descrizione"].strip(), "importo": importo}
            )
    return movimenti


async def classifica_blocco(blocco):
    elenco = "\n".join(
        f"{i}; {m['descrizione']}; {m['importo']}" for i, m in enumerate(blocco)
    )
    prompt = (
        "Classifica questi movimenti (formato: indice; descrizione; importo). "
        "Restituisci una categoria per ogni indice.\n\n" + elenco
    )
    opzioni = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        max_turns=3,
        setting_sources=[],
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    risultato = None
    async for msg in query(prompt=prompt, options=opzioni):
        if isinstance(msg, ResultMessage):
            risultato = msg
    if risultato is None or risultato.is_error or not risultato.structured_output:
        raise RuntimeError(f"Classificazione fallita: {risultato}")
    per_indice = {c["indice"]: c["categoria"] for c in risultato.structured_output["categorie"]}
    mancanti = [i for i in range(len(blocco)) if per_indice.get(i) not in CATEGORIE]
    if mancanti:
        raise RuntimeError(f"Categorie mancanti o non valide per gli indici {mancanti}")
    return [per_indice[i] for i in range(len(blocco))]


async def main():
    movimenti = leggi_movimenti("movimenti.csv")
    categorie = []
    for i in range(0, len(movimenti), BLOCCO):
        categorie += await classifica_blocco(movimenti[i : i + BLOCCO])

    totali = {c: Decimal(0) for c in CATEGORIE}
    out = []
    for m, cat in zip(movimenti, categorie):
        totali[cat] += m["importo"]
        out.append({**m, "importo": float(m["importo"]), "categoria": cat})

    risultato = {
        "movimenti": out,
        "totali": {c: float(round(t, 2)) for c, t in totali.items()},
    }
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"Scritti {len(out)} movimenti in risultato.json")


if __name__ == "__main__":
    try:
        anyio.run(main)
    except Exception as e:
        sys.exit(f"Errore: {e}")
