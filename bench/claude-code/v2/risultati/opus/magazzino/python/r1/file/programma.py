"""Risponde alle domande sull'inventario usando Claude.

Legge inventario.json e domande.txt dalla cartella corrente e scrive risultato.json.

I numeri devono essere esatti, quindi Claude non fa mai conti a mente: i valori
più richiesti (valore per prodotto, valore totale, prodotti sotto scorta e pezzi
mancanti) sono calcolati qui in Python con Decimal, e per ogni altro conto Claude
usa lo strumento `calcola`, che valuta l'espressione in aritmetica decimale esatta.
"""

import ast
import json
import operator
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
MAX_GIRI_STRUMENTI = 10

STRUMENTO_CALCOLA = {
    "name": "calcola",
    "description": (
        "Valuta un'espressione aritmetica con numeri decimali esatti (niente errori di "
        "arrotondamento). Operatori ammessi: + - * / e parentesi. Usa il punto come "
        "separatore decimale, es. '3 * 78.5 + 18 * 1.2'. Usalo per QUALSIASI calcolo "
        "non già presente nei dati precalcolati."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "espressione": {"type": "string", "description": "Espressione da valutare"}
        },
        "required": ["espressione"],
        "additionalProperties": False,
    },
    "strict": True,
}

_OPERATORI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _valuta(nodo):
    if isinstance(nodo, ast.Expression):
        return _valuta(nodo.body)
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
        # Passando per str() 4.9 resta 4.9 e non 4.9000000000000003552...
        return Decimal(str(nodo.value))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _OPERATORI:
        return _OPERATORI[type(nodo.op)](_valuta(nodo.left), _valuta(nodo.right))
    if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, (ast.USub, ast.UAdd)):
        valore = _valuta(nodo.operand)
        return -valore if isinstance(nodo.op, ast.USub) else valore
    raise ValueError("espressione non ammessa")


def calcola(espressione):
    try:
        risultato = _valuta(ast.parse(espressione.replace(",", "."), mode="eval"))
    except (SyntaxError, ValueError, InvalidOperation, ZeroDivisionError) as e:
        return f"Errore: {e}", True
    return format(risultato.normalize(), "f"), False


def decimale(valore):
    return Decimal(str(valore))


def euro(valore):
    return f"{valore.quantize(Decimal('0.01'))} €"


def prepara_dati(inventario):
    """Restituisce il testo con i dati grezzi e i valori già calcolati in modo esatto."""
    righe = []
    totale = Decimal(0)
    sotto_scorta = []
    for p in inventario:
        quantita = decimale(p["quantita"])
        prezzo = decimale(p["prezzo_unitario"])
        minima = decimale(p["scorta_minima"])
        valore = quantita * prezzo
        totale += valore
        righe.append(
            f"- {p['codice']} | {p['nome']} | quantità: {quantita} | "
            f"prezzo unitario: {euro(prezzo)} | scorta minima: {minima} | "
            f"valore in magazzino: {euro(valore)}"
        )
        if quantita < minima:
            sotto_scorta.append(
                f"- {p['codice']} {p['nome']}: {quantita} pezzi, scorta minima {minima}, "
                f"mancano {minima - quantita} pezzi per arrivare alla scorta minima "
                f"(costo per reintegrarli: {euro((minima - quantita) * prezzo)})"
            )
    return (
        "PRODOTTI (codice | nome | quantità | prezzo unitario | scorta minima | valore = quantità × prezzo):\n"
        + "\n".join(righe)
        + f"\n\nVALORE TOTALE DEL MAGAZZINO: {euro(totale)}\n\n"
        + "PRODOTTI SOTTO LA SCORTA MINIMA (quantità strettamente inferiore alla scorta minima):\n"
        + ("\n".join(sotto_scorta) if sotto_scorta else "- nessuno")
    )


def prompt_di_sistema(dati):
    return f"""Sei l'assistente del magazzino. Rispondi in italiano alle domande dei colleghi \
sull'inventario, con una risposta breve (una o due frasi) e senza formattazione Markdown.

I numeri che dai vengono usati per fare gli ordini, quindi devono essere esatti:
- Usa i valori già calcolati qui sotto quando la domanda li riguarda.
- Per qualsiasi altro conto usa lo strumento `calcola`; non fare mai calcoli a mente.
- Gli importi in euro scrivili con due decimali e la virgola decimale (es. 1.234,50 €).
- Se la domanda riguarda un prodotto che non è nell'inventario, o i dati non bastano per \
rispondere, dillo chiaramente invece di inventare.

Dati dell'inventario (calcolati in modo esatto):
{dati}"""


def rispondi(client, sistema, domanda):
    messaggi = [{"role": "user", "content": domanda}]
    for _ in range(MAX_GIRI_STRUMENTI):
        risposta = client.beta.messages.create(
            model=MODELLO,
            max_tokens=16000,
            system=sistema,
            tools=[STRUMENTO_CALCOLA],
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=messaggi,
        )
        if risposta.stop_reason == "refusal":
            raise RuntimeError("Claude ha rifiutato di rispondere")
        if risposta.stop_reason == "max_tokens":
            raise RuntimeError("risposta troncata (max_tokens)")

        messaggi.append({"role": "assistant", "content": risposta.content})
        if risposta.stop_reason != "tool_use":
            testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
            if not testo:
                raise RuntimeError("risposta vuota")
            return testo

        risultati = []
        for blocco in risposta.content:
            if blocco.type == "tool_use":
                if blocco.name == "calcola":
                    contenuto, errore = calcola(blocco.input["espressione"])
                else:
                    contenuto, errore = f"Strumento sconosciuto: {blocco.name}", True
                risultati.append({
                    "type": "tool_result",
                    "tool_use_id": blocco.id,
                    "content": contenuto,
                    "is_error": errore,
                })
        messaggi.append({"role": "user", "content": risultati})
    raise RuntimeError("troppe chiamate allo strumento di calcolo")


def main():
    inventario = json.loads(Path("inventario.json").read_text(encoding="utf-8"))
    domande = [
        riga.strip()
        for riga in Path("domande.txt").read_text(encoding="utf-8").splitlines()
        if riga.strip()
    ]

    sistema = prompt_di_sistema(prepara_dati(inventario))
    client = anthropic.Anthropic()

    risultato = []
    errori = 0
    for i, domanda in enumerate(domande, 1):
        print(f"[{i}/{len(domande)}] {domanda}", file=sys.stderr)
        try:
            testo = rispondi(client, sistema, domanda)
        except (anthropic.APIError, RuntimeError) as e:
            errori += 1
            testo = f"ERRORE: impossibile ottenere una risposta ({e})"
        print(f"    -> {testo}", file=sys.stderr)
        risultato.append({"domanda": domanda, "risposta": testo})

    Path("risultato.json").write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Scritto risultato.json ({len(risultato)} risposte)", file=sys.stderr)
    if errori:
        print(f"Attenzione: {errori} domande senza risposta", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
