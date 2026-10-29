"""Risponde alle domande sull'inventario usando Claude (Claude Agent SDK).

Uso: python programma.py  (dalla cartella con inventario.json e domande.txt)
Scrive le risposte in risultato.json.

Claude non fa mai i conti "a mente": tutti i numeri arrivano da strumenti
Python che calcolano in modo esatto con Decimal. Dopo ogni risposta il
programma controlla che ogni numero citato compaia davvero nei risultati
degli strumenti; se no, chiede a Claude di correggersi.
"""

import ast
import asyncio
import json
import re
import sys
from decimal import Decimal, InvalidOperation
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
MAX_TENTATIVI = 3


# --- Formattazione numeri all'italiana ------------------------------------

def formato_numero(valore: Decimal) -> str:
    """1540.2 -> '1.540,2'; i numeri interi restano senza decimali."""
    valore = valore.normalize() if valore == valore.to_integral() else valore
    testo = f"{valore:,f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".")


def formato_euro(valore: Decimal) -> str:
    """1540.2 -> '1.540,20 €'."""
    testo = f"{valore.quantize(Decimal('0.01')):,f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def numeri_nel_testo(testo: str) -> set[Decimal]:
    """Estrae i numeri (in formato italiano) da un testo."""
    numeri = set()
    for token in re.findall(r"\d+(?:[.,]\d+)*", testo):
        if "," in token:
            normalizzato = token.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
            normalizzato = token.replace(".", "")  # 1.540 = millecinquecentoquaranta
        else:
            normalizzato = token
        try:
            numeri.add(Decimal(normalizzato))
        except InvalidOperation:
            pass
    return numeri


# --- Dati dell'inventario --------------------------------------------------

def carica_inventario() -> list[dict]:
    # parse_float=Decimal evita gli errori di arrotondamento dei float
    with FILE_INVENTARIO.open(encoding="utf-8") as f:
        prodotti = json.load(f, parse_float=Decimal)
    for p in prodotti:
        p["quantita"] = Decimal(p["quantita"])
        p["prezzo_unitario"] = Decimal(p["prezzo_unitario"])
        p["scorta_minima"] = Decimal(p["scorta_minima"])
    return prodotti


def riepilogo_inventario(prodotti: list[dict]) -> str:
    righe = ["PRODOTTI (valori calcolati esattamente):"]
    valore_totale = Decimal(0)
    pezzi_totali = Decimal(0)
    sotto_scorta = []
    for p in prodotti:
        valore = p["quantita"] * p["prezzo_unitario"]
        mancanti = max(Decimal(0), p["scorta_minima"] - p["quantita"])
        sotto = p["quantita"] < p["scorta_minima"]
        valore_totale += valore
        pezzi_totali += p["quantita"]
        if sotto:
            sotto_scorta.append(p)
        righe.append(
            f"- codice {p['codice']} | {p['nome']} | "
            f"quantità: {formato_numero(p['quantita'])} | "
            f"prezzo unitario: {formato_euro(p['prezzo_unitario'])} | "
            f"scorta minima: {formato_numero(p['scorta_minima'])} | "
            f"valore della giacenza: {formato_euro(valore)} | "
            f"sotto scorta minima: {'SÌ' if sotto else 'no'} | "
            f"pezzi mancanti per arrivare alla scorta minima: {formato_numero(mancanti)}"
        )
    righe += [
        "",
        "TOTALI:",
        f"- numero di prodotti diversi: {len(prodotti)}",
        f"- pezzi totali in magazzino: {formato_numero(pezzi_totali)}",
        f"- valore totale del magazzino: {formato_euro(valore_totale)}",
        "- prodotti sotto la scorta minima (quantità < scorta minima): "
        + (
            "; ".join(
                f"{p['nome']} ({p['codice']}): {formato_numero(p['quantita'])} "
                f"su minimo {formato_numero(p['scorta_minima'])}, "
                f"mancano {formato_numero(p['scorta_minima'] - p['quantita'])}"
                for p in sotto_scorta
            )
            or "nessuno"
        ),
    ]
    return "\n".join(righe)


# --- Calcolatrice esatta ---------------------------------------------------

OPERATORI = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}


def valuta(nodo: ast.AST) -> Decimal:
    if isinstance(nodo, ast.Expression):
        return valuta(nodo.body)
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
        return Decimal(str(nodo.value))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERATORI:
        return OPERATORI[type(nodo.op)](valuta(nodo.left), valuta(nodo.right))
    if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, (ast.USub, ast.UAdd)):
        v = valuta(nodo.operand)
        return -v if isinstance(nodo.op, ast.USub) else v
    raise ValueError("sono ammessi solo numeri, + - * / e parentesi")


# --- Strumenti per Claude --------------------------------------------------

PRODOTTI = carica_inventario() if FILE_INVENTARIO.exists() else []
uscite_strumenti: list[str] = []  # testo restituito dagli strumenti per la domanda corrente


def risposta_strumento(testo: str, errore: bool = False) -> dict:
    uscite_strumenti.append(testo)
    risultato = {"content": [{"type": "text", "text": testo}]}
    if errore:
        risultato["is_error"] = True
    return risultato


@tool(
    "leggi_inventario",
    "Restituisce l'inventario completo con quantità, prezzi, scorte minime e i valori "
    "già calcolati in modo esatto (valore di ogni giacenza, totale del magazzino, "
    "prodotti sotto scorta, pezzi mancanti).",
    {},
)
async def leggi_inventario(args):
    return risposta_strumento(riepilogo_inventario(PRODOTTI))


@tool(
    "calcola",
    "Calcola in modo esatto un'espressione aritmetica con numeri, + - * / e parentesi. "
    "Scrivi i numeri con il punto come separatore decimale e senza separatori delle "
    "migliaia (es. '3 * 78.5 + 12'). Usalo per QUALSIASI conto non già presente "
    "nell'inventario.",
    {"espressione": str},
)
async def calcola(args):
    espressione = args["espressione"]
    try:
        valore = valuta(ast.parse(espressione, mode="eval"))
    except ZeroDivisionError:
        return risposta_strumento("Errore: divisione per zero", errore=True)
    except (SyntaxError, ValueError) as e:
        return risposta_strumento(f"Errore nell'espressione: {e}", errore=True)
    valore = valore.quantize(Decimal("0.000001")).normalize()
    return risposta_strumento(
        f"{espressione} = {formato_numero(valore)} "
        f"(se è un importo in euro: {formato_euro(valore)})"
    )


SERVER = create_sdk_mcp_server("magazzino", tools=[leggi_inventario, calcola])

SYSTEM_PROMPT = """Sei l'assistente del magazzino. Rispondi in italiano, in modo breve \
(una o due frasi), alle domande dei colleghi sull'inventario.

Regole obbligatorie, perché i numeri servono per fare gli ordini:
- Chiama sempre prima lo strumento leggi_inventario.
- Non fare MAI calcoli a mente: ogni numero della risposta deve essere copiato \
esattamente da un risultato degli strumenti. Se ti serve un conto che non è già \
nell'inventario, usa lo strumento calcola.
- Scrivi i numeri nel formato italiano esattamente come li restituiscono gli \
strumenti (es. 1.540,20 €).
- "Sotto la scorta minima" significa quantità strettamente minore della scorta minima.
- Se la domanda riguarda un prodotto che non esiste o non si può rispondere con i \
dati disponibili, dillo chiaramente invece di inventare.
- Rispondi solo con la risposta finale, senza preamboli e senza markdown."""


def opzioni() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"magazzino": SERVER},
        tools=[],  # nessuno strumento integrato (file, shell, web...)
        allowed_tools=["mcp__magazzino__leggi_inventario", "mcp__magazzino__calcola"],
        setting_sources=[],
        max_turns=10,
    )


async def chiedi(prompt: str) -> str:
    risposta = None
    async for messaggio in query(prompt=prompt, options=opzioni()):
        if isinstance(messaggio, ResultMessage):
            if messaggio.is_error:
                raise RuntimeError(f"Errore da Claude: {messaggio.errors or messaggio.result}")
            risposta = (messaggio.result or "").strip()
    if not risposta:
        raise RuntimeError("Claude non ha restituito una risposta")
    return risposta


async def rispondi(domanda: str) -> str:
    prompt = f"Domanda: {domanda}"
    for tentativo in range(1, MAX_TENTATIVI + 1):
        uscite_strumenti.clear()
        risposta = await chiedi(prompt)
        numeri_verificati = numeri_nel_testo("\n".join(uscite_strumenti) + "\n" + domanda)
        non_verificati = numeri_nel_testo(risposta) - numeri_verificati
        if not non_verificati:
            return risposta
        print(
            f"  tentativo {tentativo}: numeri non verificati "
            f"{sorted(map(str, non_verificati))}, riprovo",
            file=sys.stderr,
        )
        prompt = (
            f"Domanda: {domanda}\n\n"
            f"Una risposta precedente conteneva numeri non presenti nei risultati "
            f"degli strumenti ({', '.join(map(formato_numero, sorted(non_verificati)))}). "
            f"Ricontrolla usando gli strumenti e copia i numeri esattamente come "
            f"li restituiscono."
        )
    raise RuntimeError(
        f"Impossibile ottenere una risposta con numeri verificati per: {domanda!r}"
    )


async def main() -> None:
    for file in (FILE_INVENTARIO, FILE_DOMANDE):
        if not file.exists():
            sys.exit(f"File non trovato: {file.resolve()}")

    domande = [
        riga.strip()
        for riga in FILE_DOMANDE.read_text(encoding="utf-8").splitlines()
        if riga.strip()
    ]
    risultato = []
    for i, domanda in enumerate(domande, 1):
        print(f"[{i}/{len(domande)}] {domanda}", file=sys.stderr)
        risposta = await rispondi(domanda)
        print(f"  -> {risposta}", file=sys.stderr)
        risultato.append({"domanda": domanda, "risposta": risposta})

    FILE_RISULTATO.write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Scritte {len(risultato)} risposte in {FILE_RISULTATO}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
