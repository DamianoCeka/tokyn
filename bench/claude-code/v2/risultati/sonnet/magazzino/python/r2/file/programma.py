"""Risponde in italiano alle domande di domande.txt sull'inventario di inventario.json.

Uso: python programma.py   (dalla cartella con inventario.json e domande.txt)
Scrive risultato.json. Richiede il pacchetto `anthropic` e le credenziali Anthropic
(ad esempio la variabile d'ambiente ANTHROPIC_API_KEY).

I numeri sono esatti perche' non li calcola il modello: i valori derivati (valore di
ogni prodotto, totale del magazzino, mancanze rispetto alla scorta minima) sono
precalcolati qui con aritmetica decimale, e per qualsiasi altro calcolo il modello
deve usare lo strumento `calcola`, che valuta l'espressione in modo esatto.
"""

import ast
import json
import operator
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import anthropic

MODEL = "claude-opus-5-5"
MAX_GIRI = 10

SYSTEM = """Sei l'assistente del magazzino. Rispondi alle domande dei colleghi \
sull'inventario usando solo i dati forniti qui sotto.

Regole:
- Rispondi in italiano, in una o due frasi brevi, con una risposta diretta alla domanda.
- I numeri devono essere esatti perche' servono per fare gli ordini. Usa i valori \
gia' calcolati nei dati (valore_euro, mancanti_alla_scorta_minima, sotto_scorta_minima, \
riepilogo). Per qualsiasi altro calcolo non farlo a mente: usa lo strumento `calcola`.
- Un prodotto e' sotto la scorta minima solo se la quantita' e' strettamente minore \
della scorta minima.
- Scrivi gli importi in euro con due decimali e formato italiano (es. 1.234,56 euro \
oppure 1.234,56 €) e le quantita' come numeri interi.
- Se la domanda non e' risolvibile con questi dati o il prodotto non esiste, dillo \
chiaramente senza inventare nulla.
- Quando un prodotto e' indicato in modo generico (es. "carta A4"), cercalo per nome \
nell'elenco."""

TOOLS = [
    {
        "name": "calcola",
        "description": (
            "Valuta in modo esatto un'espressione aritmetica (numeri decimali con il punto, "
            "operatori + - * / e parentesi). Restituisce il risultato esatto, senza "
            "arrotondamenti nascosti."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "espressione": {
                    "type": "string",
                    "description": "Ad esempio: 120 * 4.9 + 3 * 78.5",
                }
            },
            "required": ["espressione"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]

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
        return Fraction(str(nodo.value))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _OPERATORI:
        return _OPERATORI[type(nodo.op)](_valuta(nodo.left), _valuta(nodo.right))
    if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, (ast.USub, ast.UAdd)):
        v = _valuta(nodo.operand)
        return -v if isinstance(nodo.op, ast.USub) else v
    raise ValueError("espressione non valida")


def calcola(espressione):
    """Valuta un'espressione aritmetica con frazioni esatte."""
    r = _valuta(ast.parse(espressione.strip(), mode="eval"))
    if r.denominator == 1:
        return str(r.numerator)
    # Decimale esatto se il risultato ha espansione finita, altrimenti 6 decimali.
    den = r.denominator
    for p in (2, 5):
        while den % p == 0:
            den //= p
    if den == 1:
        return format(Decimal(r.numerator) / Decimal(r.denominator), "f")
    return f"{float(r):.6f} (approssimato)"


def prepara_inventario(prodotti):
    """Aggiunge i campi derivati, calcolati con Decimal."""
    out = []
    totale = Decimal(0)
    pezzi = 0
    sotto = []
    for p in prodotti:
        q = int(p["quantita"])
        prezzo = Decimal(str(p["prezzo_unitario"]))
        minima = int(p["scorta_minima"])
        valore = prezzo * q
        totale += valore
        pezzi += q
        voce = {
            "codice": p["codice"],
            "nome": p["nome"],
            "quantita": q,
            "prezzo_unitario_euro": str(prezzo),
            "scorta_minima": minima,
            "valore_euro": str(valore.quantize(Decimal("0.01"))),
            "sotto_scorta_minima": q < minima,
            "mancanti_alla_scorta_minima": max(minima - q, 0),
        }
        if q < minima:
            sotto.append(p["nome"])
        out.append(voce)
    riepilogo = {
        "numero_prodotti": len(out),
        "pezzi_totali": pezzi,
        "valore_totale_magazzino_euro": str(totale.quantize(Decimal("0.01"))),
        "prodotti_sotto_scorta_minima": sotto,
    }
    return {"prodotti": out, "riepilogo": riepilogo}


def rispondi(client, system, domanda):
    messages = [{"role": "user", "content": domanda}]
    for _ in range(MAX_GIRI):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"Risposta rifiutata dal modello per: {domanda}")
        if resp.stop_reason != "tool_use":
            testo = "".join(b.text for b in resp.content if b.type == "text").strip()
            if resp.stop_reason == "max_tokens" or not testo:
                raise RuntimeError(f"Risposta incompleta o vuota per: {domanda}")
            return testo
        messages.append({"role": "assistant", "content": resp.content})
        risultati = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            try:
                contenuto, errore = calcola(b.input["espressione"]), False
            except (ValueError, SyntaxError, ZeroDivisionError, KeyError) as e:
                contenuto, errore = f"Errore: {e}", True
            risultati.append(
                {
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": contenuto,
                    "is_error": errore,
                }
            )
        messages.append({"role": "user", "content": risultati})
    raise RuntimeError(f"Troppi giri di calcolo per: {domanda}")


def main():
    cartella = Path.cwd()
    prodotti = json.loads((cartella / "inventario.json").read_text(encoding="utf-8"))
    domande = [
        r.strip()
        for r in (cartella / "domande.txt").read_text(encoding="utf-8").splitlines()
        if r.strip()
    ]
    inventario = prepara_inventario(prodotti)
    system = (
        SYSTEM
        + "\n\nInventario (JSON):\n"
        + json.dumps(inventario, ensure_ascii=False, indent=1)
    )

    client = anthropic.Anthropic()
    risultato = []
    for i, d in enumerate(domande, 1):
        r = rispondi(client, system, d)
        print(f"[{i}/{len(domande)}] {d}\n    -> {r}")
        risultato.append({"domanda": d, "risposta": r})

    (cartella / "risultato.json").write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
