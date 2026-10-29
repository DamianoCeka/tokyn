"""Risponde alle domande sull'inventario usando Claude (Claude Agent SDK).

Legge inventario.json e domande.txt dalla cartella corrente e scrive risultato.json.

Tutti i calcoli vengono fatti in Python con aritmetica decimale esatta ed esposti a
Claude come strumenti: Claude sceglie i numeri giusti e formula la risposta, ma non
fa conti a mente.
"""

import ast
import asyncio
import json
import operator
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

FILE_INVENTARIO = Path("inventario.json")
FILE_DOMANDE = Path("domande.txt")
FILE_RISULTATO = Path("risultato.json")


# --- Dati e calcoli esatti -------------------------------------------------


def carica_inventario():
    # parse_float=Decimal evita gli errori di arrotondamento dei float (es. 0.85 * 260)
    with FILE_INVENTARIO.open(encoding="utf-8") as f:
        prodotti = json.load(f, parse_float=Decimal)
    for p in prodotti:
        p["quantita"] = Decimal(p["quantita"])
        p["prezzo_unitario"] = Decimal(p["prezzo_unitario"])
        p["scorta_minima"] = Decimal(p["scorta_minima"])
    return prodotti


def numero(d):
    """Decimal -> stringa senza zeri inutili, con il punto decimale (es. 588, 4.9)."""
    d = d.normalize()
    return format(d, "f")


def euro(d):
    """Decimal -> importo in formato italiano, es. 1.234,50 €."""
    d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    testo = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{testo} €"


def scheda(p):
    mancanti = max(p["scorta_minima"] - p["quantita"], Decimal(0))
    valore = p["quantita"] * p["prezzo_unitario"]
    return {
        "codice": p["codice"],
        "nome": p["nome"],
        "quantita": numero(p["quantita"]),
        "prezzo_unitario": euro(p["prezzo_unitario"]),
        "scorta_minima": numero(p["scorta_minima"]),
        "sotto_scorta_minima": p["quantita"] < p["scorta_minima"],
        "pezzi_mancanti_per_scorta_minima": numero(mancanti),
        "costo_per_raggiungere_scorta_minima": euro(mancanti * p["prezzo_unitario"]),
        "valore_in_magazzino": euro(valore),
    }


def riepilogo(prodotti):
    sotto = [p for p in prodotti if p["quantita"] < p["scorta_minima"]]
    return {
        "numero_prodotti": len(prodotti),
        "pezzi_totali": numero(sum((p["quantita"] for p in prodotti), Decimal(0))),
        "valore_totale_magazzino": euro(
            sum((p["quantita"] * p["prezzo_unitario"] for p in prodotti), Decimal(0))
        ),
        "prodotti_sotto_scorta_minima": [p["nome"] for p in sotto],
        "costo_totale_per_riportare_tutto_alla_scorta_minima": euro(
            sum(((p["scorta_minima"] - p["quantita"]) * p["prezzo_unitario"] for p in sotto), Decimal(0))
        ),
    }


_OPERATORI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def valuta(espressione):
    """Valuta un'espressione aritmetica (+ - * / parentesi) con Decimal, in modo sicuro."""

    def nodo(n):
        if isinstance(n, ast.Expression):
            return nodo(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return Decimal(str(n.value))
        if isinstance(n, ast.BinOp) and type(n.op) in _OPERATORI:
            return _OPERATORI[type(n.op)](nodo(n.left), nodo(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPERATORI:
            return _OPERATORI[type(n.op)](nodo(n.operand))
        raise ValueError("sono ammessi solo numeri, + - * / e parentesi")

    return nodo(ast.parse(espressione.replace(",", "."), mode="eval"))


# --- Strumenti per Claude --------------------------------------------------


def crea_server(prodotti):
    def testo(dati):
        return {"content": [{"type": "text", "text": json.dumps(dati, ensure_ascii=False, indent=1)}]}

    @tool(
        "inventario",
        "Restituisce tutti i prodotti del magazzino con i valori già calcolati in modo esatto "
        "(quantità, prezzo unitario, scorta minima, se è sotto scorta, pezzi mancanti, valore) "
        "e un riepilogo con i totali (valore totale del magazzino, prodotti sotto scorta, ecc.).",
        {},
    )
    async def strumento_inventario(args):
        return testo({"prodotti": [scheda(p) for p in prodotti], "riepilogo": riepilogo(prodotti)})

    @tool(
        "calcola",
        "Calcolatrice esatta (aritmetica decimale). Usala per QUALSIASI conto non già presente "
        "nei dati dell'inventario. Accetta numeri, + - * / e parentesi, es. '(30 - 18) * 1.2'.",
        {"espressione": str},
    )
    async def strumento_calcola(args):
        try:
            risultato = valuta(args["espressione"])
        except Exception as e:  # restituisce l'errore a Claude perché possa correggersi
            return {"content": [{"type": "text", "text": f"Errore: {e}"}], "is_error": True}
        return testo({"risultato": numero(risultato), "come_importo_in_euro": euro(risultato)})

    return create_sdk_mcp_server(name="magazzino", tools=[strumento_inventario, strumento_calcola])


ISTRUZIONI = """Sei l'assistente del magazzino. Rispondi in italiano alle domande dei colleghi sull'inventario.

Regole:
- Prima di rispondere chiama sempre lo strumento `inventario`.
- I numeri devono essere esatti perché si usano per fare gli ordini: usa i valori forniti dagli
  strumenti così come sono. Non fare mai conti a mente: se ti serve un numero che non è già nei dati,
  usa lo strumento `calcola`.
- Gli importi in euro scrivili nel formato italiano restituito dagli strumenti (es. 1.234,50 €).
- Risposta breve: di norma una sola frase, senza premesse, senza markdown, senza spiegare i passaggi.
  Rispondi solo a ciò che è chiesto, senza aggiungere informazioni non richieste (codici, costi,
  scorte, valori) se la domanda non li riguarda.
- Se la domanda riguarda un prodotto che non è in inventario o non si può rispondere con i dati
  disponibili, dillo chiaramente invece di inventare."""


# --- Programma principale --------------------------------------------------


async def rispondi(domanda, server):
    opzioni = ClaudeAgentOptions(
        system_prompt=ISTRUZIONI,
        mcp_servers={"magazzino": server},
        tools=[],  # niente strumenti predefiniti (file, shell, web): solo quelli del magazzino
        allowed_tools=["mcp__magazzino__inventario", "mcp__magazzino__calcola"],
        setting_sources=[],
        max_turns=10,
    )
    risposta = None
    async for messaggio in query(prompt=domanda, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            if messaggio.is_error:
                raise RuntimeError(f"errore di Claude: {messaggio.result or messaggio.subtype}")
            risposta = (messaggio.result or "").strip()
    if not risposta:
        raise RuntimeError("Claude non ha restituito una risposta")
    return risposta


async def main():
    prodotti = carica_inventario()
    domande = [r.strip() for r in FILE_DOMANDE.read_text(encoding="utf-8").splitlines() if r.strip()]
    server = crea_server(prodotti)

    risultati = []
    for i, domanda in enumerate(domande, 1):
        print(f"[{i}/{len(domande)}] {domanda}", file=sys.stderr)
        risposta = await rispondi(domanda, server)
        print(f"    -> {risposta}", file=sys.stderr)
        risultati.append({"domanda": domanda, "risposta": risposta})

    FILE_RISULTATO.write_text(json.dumps(risultati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scritto {FILE_RISULTATO} ({len(risultati)} risposte).", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
