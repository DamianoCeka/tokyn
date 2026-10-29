"""Risponde in italiano alle domande di domande.txt sull'inventario in inventario.json.

Uso: python programma.py   (dalla cartella con inventario.json e domande.txt)
Scrive risultato.json: [{"domanda": ..., "risposta": ...}, ...] nello stesso ordine.

Per avere numeri esatti, Claude non calcola "a mente": riceve l'inventario con i
valori derivati già calcolati in Python (Decimal) e ha a disposizione uno
strumento `calcola` per qualsiasi altra operazione aritmetica.
"""

import ast
import asyncio
import json
import operator
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

MODELLO = "claude-sonnet-5-5"
CARTELLA = Path.cwd()

OPERATORI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def valuta(nodo):
    """Valuta in modo sicuro un'espressione aritmetica usando Decimal."""
    if isinstance(nodo, ast.Expression):
        return valuta(nodo.body)
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
        return Decimal(str(nodo.value))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERATORI:
        return OPERATORI[type(nodo.op)](valuta(nodo.left), valuta(nodo.right))
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERATORI:
        return OPERATORI[type(nodo.op)](valuta(nodo.operand))
    raise ValueError("espressione non valida")


@tool(
    "calcola",
    "Calcola esattamente un'espressione aritmetica (+ - * / e parentesi, numeri con il punto decimale). "
    "Usalo per ogni calcolo non già presente nella tabella dell'inventario.",
    {"espressione": str},
)
async def calcola(args):
    try:
        risultato = valuta(ast.parse(args["espressione"], mode="eval"))
        testo = format(risultato.normalize(), "f")
        return {"content": [{"type": "text", "text": testo}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Errore: {e}"}], "is_error": True}


def euro(x: Decimal) -> str:
    return f"{x:.2f}"


def tabella_inventario(prodotti: list[dict]) -> str:
    righe = ["codice | nome | quantita | prezzo_unitario_eur | scorta_minima | valore_eur | differenza_da_scorta_minima"]
    totale = Decimal(0)
    sotto = []
    for p in prodotti:
        prezzo = Decimal(str(p["prezzo_unitario"]))
        valore = prezzo * p["quantita"]
        diff = p["quantita"] - p["scorta_minima"]
        totale += valore
        if diff < 0:
            sotto.append(f"{p['nome']} ({p['codice']}): ne mancano {-diff}")
        righe.append(
            f"{p['codice']} | {p['nome']} | {p['quantita']} | {euro(prezzo)} | "
            f"{p['scorta_minima']} | {euro(valore)} | {diff:+d}"
        )
    righe.append(f"\nVALORE TOTALE MAGAZZINO: {euro(totale)} EUR")
    righe.append("PRODOTTI SOTTO LA SCORTA MINIMA (quantita < scorta_minima): " + ("; ".join(sotto) or "nessuno"))
    return "\n".join(righe)


def prompt_di_sistema(prodotti: list[dict]) -> str:
    return (
        "Rispondi a domande sull'inventario di un magazzino, sempre in italiano e in modo breve "
        "(una o due frasi). I numeri sono usati per fare ordini: devono essere esatti.\n"
        "Usa solo i dati qui sotto; non inventare nulla. Riporta i valori già calcolati nella tabella "
        "e per qualsiasi altro calcolo usa lo strumento calcola, mai il calcolo a mente. "
        "Gli importi sono in euro, scritti con due decimali (es. 1.234,50 euro o 4,90 euro).\n"
        "Se la domanda non è risolvibile con questi dati, o il prodotto non esiste, dillo chiaramente. "
        "Rispondi solo con la risposta, senza premesse.\n\n"
        "INVENTARIO:\n" + tabella_inventario(prodotti)
    )


async def rispondi(domanda: str, opzioni: ClaudeAgentOptions) -> str:
    testo, finale = [], None
    async for msg in query(prompt=domanda, options=opzioni):
        if isinstance(msg, AssistantMessage):
            testo = [b.text for b in msg.content if isinstance(b, TextBlock)] or testo
        elif isinstance(msg, ResultMessage):
            if msg.is_error:
                raise RuntimeError(f"Errore da Claude: {msg.result}")
            finale = msg.result
    risposta = (finale or " ".join(testo)).strip()
    if not risposta:
        raise RuntimeError("Risposta vuota")
    return risposta


async def main():
    prodotti = json.loads((CARTELLA / "inventario.json").read_text(encoding="utf-8"))
    domande = [r.strip() for r in (CARTELLA / "domande.txt").read_text(encoding="utf-8").splitlines() if r.strip()]

    opzioni = ClaudeAgentOptions(
        model=MODELLO,
        system_prompt=prompt_di_sistema(prodotti),
        mcp_servers={"calc": create_sdk_mcp_server("calc", tools=[calcola])},
        tools=[],  # nessuno strumento integrato (file, shell, ecc.)
        allowed_tools=["mcp__calc__calcola"],
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=8,
    )

    risultato = []
    for domanda in domande:
        risposta = await rispondi(domanda, opzioni)
        print(f"- {domanda}\n  {risposta}")
        risultato.append({"domanda": domanda, "risposta": risposta})

    (CARTELLA / "risultato.json").write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
