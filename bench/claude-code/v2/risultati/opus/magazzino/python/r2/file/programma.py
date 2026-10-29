"""Risponde alle domande sull'inventario usando Claude.

Uso: python programma.py  (dalla cartella con inventario.json e domande.txt)
Scrive le risposte in risultato.json.

I numeri non vengono calcolati dal modello: i valori derivati (valore per
prodotto, pezzi mancanti, totali) sono calcolati qui in Python con Decimal,
e per qualsiasi altro conto Claude usa lo strumento "calcola", che esegue
l'aritmetica in modo esatto.
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


def euro(valore: Decimal) -> str:
    return str(valore.quantize(Decimal("0.01")))


def carica_inventario(percorso: Path) -> list[dict]:
    # parse_float=Decimal evita gli errori di arrotondamento dei float
    return json.loads(percorso.read_text(encoding="utf-8"), parse_float=Decimal)


def prepara_dati(inventario: list[dict]) -> dict:
    prodotti = []
    valore_totale = Decimal(0)
    for p in inventario:
        quantita = Decimal(p["quantita"])
        prezzo = Decimal(p["prezzo_unitario"])
        scorta_minima = Decimal(p["scorta_minima"])
        valore = quantita * prezzo
        valore_totale += valore
        mancanti = max(scorta_minima - quantita, Decimal(0))
        prodotti.append({
            "codice": p["codice"],
            "nome": p["nome"],
            "quantita": int(quantita),
            "prezzo_unitario_euro": euro(prezzo),
            "scorta_minima": int(scorta_minima),
            "valore_in_magazzino_euro": euro(valore),
            "sotto_scorta_minima": quantita < scorta_minima,
            "pezzi_mancanti_alla_scorta_minima": int(mancanti),
        })
    return {
        "prodotti": prodotti,
        "riepilogo": {
            "numero_prodotti": len(prodotti),
            "pezzi_totali": sum(p["quantita"] for p in prodotti),
            "valore_totale_magazzino_euro": euro(valore_totale),
            "prodotti_sotto_scorta_minima": [
                p["nome"] for p in prodotti if p["sotto_scorta_minima"]
            ],
        },
    }


# --- Calcolatrice esatta (solo + - * / e parentesi, su Decimal) ---

_OPERATORI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _valuta(nodo: ast.AST) -> Decimal:
    if isinstance(nodo, ast.Expression):
        return _valuta(nodo.body)
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)) \
            and not isinstance(nodo.value, bool):
        # repr del float letterale -> Decimal esatto come scritto (es. 4.9, non 4.90000000000000035...)
        return Decimal(repr(nodo.value))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _OPERATORI:
        return _OPERATORI[type(nodo.op)](_valuta(nodo.left), _valuta(nodo.right))
    if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, (ast.USub, ast.UAdd)):
        valore = _valuta(nodo.operand)
        return -valore if isinstance(nodo.op, ast.USub) else valore
    raise ValueError("espressione non ammessa: usa solo numeri, + - * / e parentesi")


def calcola(espressione: str) -> str:
    try:
        risultato = _valuta(ast.parse(espressione.replace(",", "."), mode="eval"))
    except (SyntaxError, ValueError, InvalidOperation, ZeroDivisionError) as e:
        raise ValueError(f"impossibile calcolare '{espressione}': {e}") from e
    return format(risultato.normalize(), "f")


STRUMENTI = [{
    "name": "calcola",
    "description": (
        "Calcola in modo esatto un'espressione aritmetica con numeri decimali, "
        "+, -, *, / e parentesi (es. '(30 - 18) * 1.20'). Usalo per ogni conto "
        "che non sia già presente nei dati dell'inventario."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "espressione": {"type": "string", "description": "Espressione aritmetica da calcolare."},
        },
        "required": ["espressione"],
        "additionalProperties": False,
    },
    "strict": True,
}]


def prompt_di_sistema(dati: dict) -> str:
    return (
        "Sei l'assistente del magazzino. Rispondi in italiano alle domande dei colleghi "
        "sull'inventario, con una risposta breve (una o due frasi).\n\n"
        "I numeri vengono usati per fare gli ordini e devono essere esatti:\n"
        "- usa solo i dati qui sotto, che includono già valori, totali e pezzi mancanti calcolati in modo esatto;\n"
        "- non fare mai conti a mente: per qualsiasi altro calcolo usa lo strumento `calcola`;\n"
        "- un prodotto è sotto la scorta minima quando la quantità è strettamente inferiore alla scorta minima;\n"
        "- scrivi gli importi in euro con due decimali e la virgola decimale (es. 1.234,50 €);\n"
        "- se la domanda non si può rispondere con questi dati, dillo chiaramente invece di inventare.\n\n"
        "<inventario>\n"
        + json.dumps(dati, ensure_ascii=False, indent=2)
        + "\n</inventario>"
    )


def rispondi(client: anthropic.Anthropic, sistema: str, domanda: str) -> str:
    messaggi = [{"role": "user", "content": domanda}]
    for _ in range(MAX_GIRI_STRUMENTI):
        risposta = client.beta.messages.create(
            model=MODELLO,
            # se il modello declina per i filtri di sicurezza, il server riprova su un modello di riserva
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            max_tokens=16000,
            output_config={"effort": "medium"},
            # il prompt di sistema (con l'inventario) è identico per tutte le domande
            system=[{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
            tools=STRUMENTI,
            messages=messaggi,
        )

        if risposta.stop_reason == "refusal":
            raise RuntimeError("il modello ha rifiutato di rispondere")
        if risposta.stop_reason == "max_tokens":
            raise RuntimeError("risposta troncata (max_tokens)")

        chiamate = [b for b in risposta.content if b.type == "tool_use"]
        if risposta.stop_reason != "tool_use" or not chiamate:
            testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
            if not testo:
                raise RuntimeError(f"risposta vuota (stop_reason={risposta.stop_reason})")
            return testo

        messaggi.append({"role": "assistant", "content": risposta.content})
        risultati = []
        for chiamata in chiamate:
            try:
                if chiamata.name != "calcola":
                    raise ValueError(f"strumento sconosciuto: {chiamata.name}")
                contenuto, errore = calcola(chiamata.input["espressione"]), False
            except (ValueError, KeyError, TypeError) as e:
                contenuto, errore = f"Errore: {e}", True
            risultati.append({
                "type": "tool_result",
                "tool_use_id": chiamata.id,
                "content": contenuto,
                "is_error": errore,
            })
        messaggi.append({"role": "user", "content": risultati})

    raise RuntimeError("troppe chiamate allo strumento senza una risposta finale")


def main() -> int:
    cartella = Path.cwd()
    dati = prepara_dati(carica_inventario(cartella / "inventario.json"))
    domande = [
        riga.strip()
        for riga in (cartella / "domande.txt").read_text(encoding="utf-8").splitlines()
        if riga.strip()
    ]

    client = anthropic.Anthropic()
    if client.api_key is None and client.auth_token is None:
        print("Manca la chiave API: imposta ANTHROPIC_API_KEY (export ANTHROPIC_API_KEY=...)", file=sys.stderr)
        return 2
    sistema = prompt_di_sistema(dati)

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

    (cartella / "risultato.json").write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Scritto risultato.json ({len(risultato)} risposte, {errori} errori)", file=sys.stderr)
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
