"""Risponde con Claude alle domande sull'inventario del magazzino.

Legge inventario.json e domande.txt dalla cartella corrente e scrive risultato.json.

I numeri non vengono mai calcolati dal modello: tutti i valori derivati (valore di
ogni prodotto, valore totale, pezzi mancanti alla scorta minima, ...) sono calcolati
qui in Python con aritmetica decimale esatta, e per qualsiasi altro conto Claude
dispone dello strumento `calcola`, che esegue l'operazione in Python.
"""

import ast
import json
import operator
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
MAX_ITERAZIONI_STRUMENTI = 10


def euro(valore: Decimal) -> str:
    """Formatta un importo in euro all'italiana: 1234.5 -> '1.234,50 €'."""
    testo = f"{valore.quantize(Decimal('0.01')):,.2f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def numero(valore: Decimal) -> str:
    """Formatta un numero senza zeri superflui, con la virgola decimale."""
    testo = format(valore.normalize(), "f") if valore != valore.to_integral() else str(int(valore))
    return testo.replace(".", ",")


def carica_inventario(percorso: Path) -> list[dict]:
    # parse_float=Decimal evita gli errori di arrotondamento dei float (es. 4.9).
    prodotti = json.loads(percorso.read_text(encoding="utf-8"), parse_float=Decimal)
    for p in prodotti:
        for campo in ("quantita", "prezzo_unitario", "scorta_minima"):
            p[campo] = Decimal(p[campo])
    return prodotti


def prepara_dati(prodotti: list[dict]) -> str:
    """Testo con i dati grezzi e tutti i valori derivati già calcolati in modo esatto."""
    righe = []
    for p in prodotti:
        valore = p["quantita"] * p["prezzo_unitario"]
        mancanti = max(Decimal(0), p["scorta_minima"] - p["quantita"])
        righe.append(
            {
                "codice": p["codice"],
                "nome": p["nome"],
                "quantita": numero(p["quantita"]),
                "prezzo_unitario": euro(p["prezzo_unitario"]),
                "scorta_minima": numero(p["scorta_minima"]),
                "valore_in_magazzino (quantita x prezzo)": euro(valore),
                "sotto_scorta_minima (quantita < scorta_minima)": "sì" if p["quantita"] < p["scorta_minima"] else "no",
                "pezzi_mancanti_per_arrivare_alla_scorta_minima": numero(mancanti),
                "costo_per_reintegrare_la_scorta_minima": euro(mancanti * p["prezzo_unitario"]),
            }
        )

    sotto_scorta = [p for p in prodotti if p["quantita"] < p["scorta_minima"]]
    riepilogo = {
        "numero_prodotti": len(prodotti),
        "pezzi_totali_in_magazzino": numero(sum((p["quantita"] for p in prodotti), Decimal(0))),
        "valore_totale_magazzino": euro(sum((p["quantita"] * p["prezzo_unitario"] for p in prodotti), Decimal(0))),
        "prodotti_sotto_scorta_minima": [p["nome"] for p in sotto_scorta] or "nessuno",
        "costo_totale_per_reintegrare_le_scorte_minime": euro(
            sum(((p["scorta_minima"] - p["quantita"]) * p["prezzo_unitario"] for p in sotto_scorta), Decimal(0))
        ),
    }
    return (
        "PRODOTTI:\n"
        + json.dumps(righe, ensure_ascii=False, indent=2)
        + "\n\nRIEPILOGO:\n"
        + json.dumps(riepilogo, ensure_ascii=False, indent=2)
    )


# --- Strumento di calcolo esatto -------------------------------------------------

_OPERATORI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _valuta(nodo: ast.AST) -> Decimal:
    if isinstance(nodo, ast.Expression):
        return _valuta(nodo.body)
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)) and not isinstance(nodo.value, bool):
        # repr del float riporta il letterale scritto (es. 4.9), non l'approssimazione binaria.
        return Decimal(repr(nodo.value)) if isinstance(nodo.value, float) else Decimal(nodo.value)
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _OPERATORI:
        return _OPERATORI[type(nodo.op)](_valuta(nodo.left), _valuta(nodo.right))
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in _OPERATORI:
        return _OPERATORI[type(nodo.op)](_valuta(nodo.operand))
    raise ValueError("sono ammessi solo numeri, + - * / e parentesi")


def calcola(espressione: str) -> str:
    try:
        risultato = _valuta(ast.parse(espressione, mode="eval"))
    except (SyntaxError, ValueError, ZeroDivisionError, InvalidOperation) as e:
        raise ValueError(f"Espressione non valida: {e}") from e
    return numero(risultato)


STRUMENTI = [
    {
        "name": "calcola",
        "description": (
            "Calcola in modo esatto (aritmetica decimale) un'espressione aritmetica. "
            "Ammessi solo numeri, + - * / e parentesi; usa il punto come separatore decimale. "
            "Esempio: '3 * 78.5 + 120 * 4.9'. Restituisce il risultato con la virgola decimale."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"espressione": {"type": "string", "description": "L'espressione da calcolare."}},
            "required": ["espressione"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]


SISTEMA = """Sei l'assistente del magazzino. Rispondi in italiano alle domande dei colleghi \
sull'inventario, con una risposta breve (una o due frasi), senza markdown.

Le risposte servono per fare gli ordini, quindi i numeri devono essere esatti:
- Usa solo i dati qui sotto. Molti valori derivati sono già calcolati: se la risposta \
è già presente, riportala esattamente così com'è.
- Non fare mai calcoli a mente. Per qualsiasi conto non già presente nei dati usa lo \
strumento `calcola` e riporta il risultato che restituisce.
- Gli importi in euro scrivili nel formato italiano, ad es. 1.234,50 €.
- Se la domanda riguarda un prodotto che non è in inventario, o i dati non bastano per \
rispondere, dillo chiaramente invece di inventare.

DATI DELL'INVENTARIO:
"""


def rispondi(client: anthropic.Anthropic, sistema: str, domanda: str) -> str:
    messaggi = [{"role": "user", "content": domanda}]
    for _ in range(MAX_ITERAZIONI_STRUMENTI):
        risposta = client.beta.messages.create(
            model=MODELLO,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            # Se un classificatore di sicurezza rifiuta per errore, la richiesta
            # viene ripetuta automaticamente su un altro modello.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
            tools=STRUMENTI,
            messages=messaggi,
        )

        if risposta.stop_reason == "refusal":
            raise RuntimeError("il modello ha rifiutato di rispondere")
        if risposta.stop_reason == "max_tokens":
            raise RuntimeError("risposta troncata (max_tokens)")

        if risposta.stop_reason != "tool_use":
            testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
            if not testo:
                raise RuntimeError(f"risposta vuota (stop_reason={risposta.stop_reason})")
            return testo

        messaggi.append({"role": "assistant", "content": risposta.content})
        risultati = []
        for blocco in risposta.content:
            if blocco.type != "tool_use":
                continue
            try:
                if blocco.name != "calcola":
                    raise ValueError(f"strumento sconosciuto: {blocco.name}")
                contenuto, errore = calcola(blocco.input["espressione"]), False
            except (ValueError, KeyError, TypeError) as e:
                contenuto, errore = str(e), True
            risultati.append(
                {"type": "tool_result", "tool_use_id": blocco.id, "content": contenuto, "is_error": errore}
            )
        messaggi.append({"role": "user", "content": risultati})

    raise RuntimeError("troppe chiamate allo strumento di calcolo")


def main() -> int:
    cartella = Path.cwd()
    prodotti = carica_inventario(cartella / "inventario.json")
    domande = [
        riga.strip()
        for riga in (cartella / "domande.txt").read_text(encoding="utf-8").splitlines()
        if riga.strip()
    ]

    sistema = SISTEMA + prepara_dati(prodotti)
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

    (cartella / "risultato.json").write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Scritto risultato.json ({len(risultato)} risposte, {errori} errori).", file=sys.stderr)
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
