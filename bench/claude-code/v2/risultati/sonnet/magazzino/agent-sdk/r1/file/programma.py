"""Risponde in italiano alle domande di domande.txt sull'inventario di inventario.json.

Claude non fa i conti da solo: legge i dati e calcola solo tramite strumenti
deterministici (Decimal), così quantità e importi nelle risposte sono esatti.
"""
import asyncio
import json
import sys
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

MODEL = "claude-opus-5-5"
QUI = Path.cwd()

INVENTARIO = [
    {
        **p,
        "prezzo_unitario": Decimal(str(p["prezzo_unitario"])),
    }
    for p in json.loads((QUI / "inventario.json").read_text(encoding="utf-8"))
]


def euro(x: Decimal) -> str:
    s = f"{x.quantize(Decimal('0.01')):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def descrivi(p: dict) -> str:
    valore = p["prezzo_unitario"] * p["quantita"]
    return (
        f"{p['codice']} | {p['nome']} | quantità: {p['quantita']} | "
        f"prezzo unitario: {euro(p['prezzo_unitario'])} | "
        f"scorta minima: {p['scorta_minima']} | valore della scorta: {euro(valore)}"
    )


def risposta(testo: str) -> dict:
    return {"content": [{"type": "text", "text": testo}]}


@tool("elenco_prodotti", "Elenca tutti i prodotti con quantità, prezzo, scorta minima e valore della scorta.", {})
async def elenco_prodotti(args):
    return risposta("\n".join(descrivi(p) for p in INVENTARIO))


@tool(
    "cerca_prodotto",
    "Cerca prodotti per codice o parte del nome (senza distinzione tra maiuscole e minuscole).",
    {"testo": str},
)
async def cerca_prodotto(args):
    t = args["testo"].lower()
    trovati = [p for p in INVENTARIO if t in p["nome"].lower() or t in p["codice"].lower()]
    if not trovati:
        return risposta("Nessun prodotto trovato. Prova con un'altra parola o usa elenco_prodotti.")
    return risposta("\n".join(descrivi(p) for p in trovati))


@tool("valore_magazzino", "Valore totale del magazzino (somma di quantità × prezzo unitario) e numero totale di pezzi.", {})
async def valore_magazzino(args):
    totale = sum((p["prezzo_unitario"] * p["quantita"] for p in INVENTARIO), Decimal(0))
    pezzi = sum(p["quantita"] for p in INVENTARIO)
    return risposta(f"Valore totale: {euro(totale)}; pezzi totali: {pezzi}; prodotti: {len(INVENTARIO)}")


@tool(
    "sotto_scorta_minima",
    "Prodotti con quantità inferiore alla scorta minima, con i pezzi mancanti per raggiungerla e il costo di reintegro.",
    {},
)
async def sotto_scorta_minima(args):
    righe = []
    for p in INVENTARIO:
        mancanti = p["scorta_minima"] - p["quantita"]
        if mancanti > 0:
            righe.append(
                f"{p['codice']} | {p['nome']} | quantità: {p['quantita']} | "
                f"scorta minima: {p['scorta_minima']} | mancanti: {mancanti} | "
                f"costo per reintegrare: {euro(p['prezzo_unitario'] * mancanti)}"
            )
    return risposta("\n".join(righe) if righe else "Nessun prodotto è sotto la scorta minima.")


STRUMENTI = [elenco_prodotti, cerca_prodotto, valore_magazzino, sotto_scorta_minima]
NOMI = [f"mcp__magazzino__{t.name}" for t in STRUMENTI]

SYSTEM = (
    "Rispondi in italiano, in una o due frasi brevi, a domande sull'inventario di un magazzino. "
    "Per ogni dato usa SEMPRE gli strumenti: non stimare e non fare calcoli a mente. "
    "Riporta numeri e importi esattamente come li restituiscono gli strumenti (stesso formato), senza arrotondarli. "
    "Se il prodotto citato non esiste o la domanda non riguarda l'inventario, dillo chiaramente."
)


async def rispondi(domanda: str) -> str:
    opzioni = ClaudeAgentOptions(
        model=MODEL,
        system_prompt=SYSTEM,
        mcp_servers={"magazzino": create_sdk_mcp_server("magazzino", tools=STRUMENTI)},
        tools=[],  # nessuno strumento integrato (file, shell, web)
        allowed_tools=NOMI,
        setting_sources=[],
        max_turns=8,
        effort="low",
    )
    testi, finale = [], None
    async for msg in query(prompt=domanda, options=opzioni):
        if isinstance(msg, AssistantMessage):
            testi = [b.text for b in msg.content if isinstance(b, TextBlock)] or testi
        elif isinstance(msg, ResultMessage):
            if msg.is_error:
                raise RuntimeError(f"errore dell'agente: {msg.subtype} {msg.result}")
            finale = msg.result
    risp = (finale or " ".join(testi)).strip()
    if not risp:
        raise RuntimeError("risposta vuota")
    return risp


async def main() -> int:
    domande = [r.strip() for r in (QUI / "domande.txt").read_text(encoding="utf-8").splitlines() if r.strip()]
    risultato, errori = [], 0
    for d in domande:
        for tentativo in (1, 2):
            try:
                risp = await rispondi(d)
                break
            except Exception as e:  # noqa: BLE001
                if tentativo == 2:
                    print(f"Errore sulla domanda {d!r}: {e}", file=sys.stderr)
                    risp, errori = None, errori + 1
        risultato.append({"domanda": d, "risposta": risp})
        print(f"- {d}\n  {risp}")
    (QUI / "risultato.json").write_text(json.dumps(risultato, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
