"""Risponde alle domande di domande.txt sull'inventario in inventario.json usando Claude.

I numeri non li calcola il modello "a mente": Claude dispone di uno strumento
(`calcola`) che esegue un'espressione Python sull'inventario con aritmetica
decimale esatta, e riporta nella risposta il risultato ottenuto.
"""

import asyncio
import json
from decimal import Decimal
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

MODELLO = "claude-opus-5-5"
CARTELLA = Path.cwd()

# Prezzi come Decimal: nessun errore di arrotondamento nei totali.
with open(CARTELLA / "inventario.json", encoding="utf-8") as f:
    INVENTARIO = json.load(f, parse_float=Decimal)

SYSTEM_PROMPT = """\
Sei l'assistente del magazzino. Rispondi in italiano, in modo breve (una o due frasi), \
alle domande sull'inventario.

Regole:
- I numeri devono essere esatti perché servono per fare gli ordini. Non fare mai calcoli \
a mente e non stimare: per qualsiasi quantità, somma, valore, differenza o filtro usa lo \
strumento `calcola` e riporta esattamente il risultato che ti restituisce.
- Gli importi sono in euro: scrivili con due decimali e il simbolo € (es. 1.234,50 €).
- Se un prodotto citato non esiste nell'inventario, dillo invece di inventare un valore.
- Se la domanda non riguarda l'inventario o non si può rispondere con i dati, dillo brevemente.
- Rispondi solo con la risposta, senza spiegare i passaggi, in testo semplice (niente Markdown, niente grassetto)."""


def _calcola(espressione: str) -> str:
    ambiente = {
        "__builtins__": {},
        "inventario": INVENTARIO,
        "Decimal": Decimal,
        "sum": sum, "len": len, "min": min, "max": max, "sorted": sorted,
        "round": round, "abs": abs, "any": any, "all": all, "list": list,
        "str": str, "int": int,
    }
    return str(eval(espressione, ambiente))  # noqa: S307 - input limitato, niente builtins


@tool(
    "calcola",
    "Valuta un'espressione Python sull'inventario e restituisce il risultato esatto. "
    "La variabile `inventario` è la lista di dizionari con chiavi: codice, nome, quantita (int), "
    "prezzo_unitario (Decimal, euro), scorta_minima (int). Esempi: "
    "\"sum(p['quantita'] * p['prezzo_unitario'] for p in inventario)\"; "
    "\"[p['nome'] for p in inventario if p['quantita'] < p['scorta_minima']]\"; "
    "\"[p for p in inventario if 'carta' in p['nome'].lower()]\". "
    "Sono disponibili solo sum, len, min, max, sorted, round, abs, any, all, list, str, int, Decimal.",
    {"espressione": str},
)
async def calcola(args):
    try:
        testo = _calcola(args["espressione"])
        return {"content": [{"type": "text", "text": testo}]}
    except Exception as e:  # l'errore torna al modello, che può correggere l'espressione
        return {"content": [{"type": "text", "text": f"Errore: {e!r}"}], "is_error": True}


async def rispondi(domanda: str) -> str:
    opzioni = ClaudeAgentOptions(
        model=MODELLO,
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"magazzino": create_sdk_mcp_server("magazzino", tools=[calcola])},
        tools=[],  # nessuno strumento integrato (file, bash, ...)
        allowed_tools=["mcp__magazzino__calcola"],
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=10,
    )
    testi: list[str] = []
    finale = None
    async for msg in query(prompt=domanda, options=opzioni):
        if isinstance(msg, AssistantMessage):
            testi = [b.text for b in msg.content if isinstance(b, TextBlock)] or testi
        elif isinstance(msg, ResultMessage):
            if msg.is_error:
                raise RuntimeError(f"Errore da Claude: {msg.result or msg.subtype}")
            finale = msg.result
    risposta = (finale or "\n".join(testi)).strip()
    if not risposta:
        raise RuntimeError("Risposta vuota")
    return risposta


async def main() -> None:
    domande = [
        r.strip()
        for r in (CARTELLA / "domande.txt").read_text(encoding="utf-8").splitlines()
        if r.strip()
    ]
    risultati = []
    for domanda in domande:
        try:
            risposta = await rispondi(domanda)
        except Exception as e:
            print(f"ERRORE su '{domanda}': {e}")
            risposta = f"Errore: impossibile rispondere ({e})"
        print(f"- {domanda}\n  {risposta}")
        risultati.append({"domanda": domanda, "risposta": risposta})
    with open(CARTELLA / "risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultati, f, ensure_ascii=False, indent=2)
    print("Scritto risultato.json")


if __name__ == "__main__":
    asyncio.run(main())
