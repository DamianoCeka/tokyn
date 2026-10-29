import ast
import json
import operator
from decimal import Decimal, InvalidOperation

import anthropic

MODEL = "claude-opus-5-5"
MAX_GIRI = 10

SYSTEM = """Rispondi alle domande dei colleghi sull'inventario del magazzino, in italiano e in modo breve \
(una o due frasi). I numeri servono per fare gli ordini, quindi devono essere esatti.

Regole:
- Usa solo i dati dell'inventario qui sotto. Per ogni prodotto trovi anche il valore (quantita x prezzo) \
e la mancanza rispetto alla scorta minima, già calcolati: usali così come sono.
- Il totale del magazzino è già calcolato. Per qualsiasi altro calcolo (somme, differenze, \
prodotti, percentuali) usa lo strumento `calcola`: non fare mai i conti a mente.
- "Sotto la scorta minima" significa quantità strettamente inferiore alla scorta minima.
- Gli importi sono in euro; scrivili con la virgola decimale e due decimali (es. 1.234,50 euro).
- Se la domanda non si può risolvere con questi dati, o il prodotto non esiste, dillo chiaramente \
senza inventare nulla.

Inventario (JSON):
"""

TOOLS = [{
    "name": "calcola",
    "description": "Calcola con precisione decimale un'espressione aritmetica (+ - * / e parentesi) "
                   "e restituisce il risultato esatto. Usalo per ogni calcolo.",
    "input_schema": {
        "type": "object",
        "properties": {
            "espressione": {"type": "string", "description": "Es. '3 * 78.5 + 18 * 1.2'"},
        },
        "required": ["espressione"],
        "additionalProperties": False,
    },
    "strict": True,
}]

OPERATORI = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _valuta(nodo):
    if isinstance(nodo, ast.Expression):
        return _valuta(nodo.body)
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
        return Decimal(str(nodo.value))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERATORI:
        return OPERATORI[type(nodo.op)](_valuta(nodo.left), _valuta(nodo.right))
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERATORI:
        return OPERATORI[type(nodo.op)](_valuta(nodo.operand))
    raise ValueError("espressione non supportata")


def calcola(espressione):
    try:
        risultato = _valuta(ast.parse(espressione.strip(), mode="eval"))
    except (ValueError, SyntaxError, InvalidOperation, ZeroDivisionError) as e:
        return f"Errore: {e}", True
    return format(risultato.normalize(), "f"), False


def prepara_inventario(path):
    with open(path, encoding="utf-8") as f:
        prodotti = json.load(f)
    totale = Decimal(0)
    righe = []
    for p in prodotti:
        valore = Decimal(str(p["prezzo_unitario"])) * p["quantita"]
        totale += valore
        righe.append({
            **p,
            "valore": format(valore, "f"),
            "sotto_scorta_minima": p["quantita"] < p["scorta_minima"],
            "mancanti_per_scorta_minima": max(p["scorta_minima"] - p["quantita"], 0),
        })
    return {"prodotti": righe, "valore_totale_magazzino": format(totale, "f")}


def rispondi(client, system, domanda):
    messaggi = [{"role": "user", "content": domanda}]
    for _ in range(MAX_GIRI):
        risposta = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=system,
            tools=TOOLS,
            output_config={"effort": "medium"},
            messages=messaggi,
        )
        if risposta.stop_reason == "refusal":
            return "Non posso rispondere a questa domanda."
        if risposta.stop_reason == "tool_use":
            messaggi.append({"role": "assistant", "content": risposta.content})
            risultati = []
            for blocco in risposta.content:
                if blocco.type == "tool_use":
                    testo, errore = calcola(blocco.input.get("espressione", ""))
                    risultati.append({"type": "tool_result", "tool_use_id": blocco.id,
                                      "content": testo, "is_error": errore})
            messaggi.append({"role": "user", "content": risultati})
            continue
        testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
        if risposta.stop_reason == "max_tokens":
            raise RuntimeError("risposta troncata")
        return testo
    raise RuntimeError("troppi passaggi di calcolo")


def main():
    inventario = prepara_inventario("inventario.json")
    system = SYSTEM + json.dumps(inventario, ensure_ascii=False, indent=1)
    with open("domande.txt", encoding="utf-8") as f:
        domande = [r.strip() for r in f if r.strip()]

    client = anthropic.Anthropic()
    risultato = []
    for domanda in domande:
        risposta = rispondi(client, system, domanda)
        print(f"{domanda}\n  -> {risposta}")
        risultato.append({"domanda": domanda, "risposta": risposta})

    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
