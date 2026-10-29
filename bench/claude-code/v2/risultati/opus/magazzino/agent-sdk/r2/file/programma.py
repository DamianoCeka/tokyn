"""Risponde in italiano alle domande sull'inventario usando Claude.

Uso: python programma.py  (dalla cartella con inventario.json e domande.txt)
Scrive le risposte in risultato.json.

Tutti i numeri (valori, totali, differenze) sono calcolati in Python con
Decimal e passati a Claude tramite strumenti: il modello non fa conti a mente.
"""

import ast
import asyncio
import json
import operator
import sys
from decimal import Decimal, InvalidOperation
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

FILE_INVENTARIO = Path("inventario.json")
FILE_DOMANDE = Path("domande.txt")
FILE_RISULTATO = Path("risultato.json")
DOMANDE_IN_PARALLELO = 4


def formatta_numero(valore: Decimal, decimali: int | None = None) -> str:
    """Formato italiano: 1.540,2 -> '1.540,20' (con decimali=2)."""
    if decimali is not None:
        valore = valore.quantize(Decimal(1).scaleb(-decimali))
    testo = f"{valore:,f}"  # es. '1,540.20'
    return testo.replace(",", "_").replace(".", ",").replace("_", ".")


def formatta_euro(valore: Decimal) -> str:
    return f"{formatta_numero(valore, 2)} €"


def carica_inventario() -> list[dict]:
    with FILE_INVENTARIO.open(encoding="utf-8") as f:
        prodotti = json.load(f, parse_float=Decimal, parse_int=Decimal)
    return prodotti


def prepara_dati(prodotti: list[dict]) -> dict:
    """Calcola in modo esatto tutti i valori derivati dell'inventario."""
    righe = []
    valore_totale = Decimal(0)
    pezzi_totali = Decimal(0)
    for p in prodotti:
        quantita = p["quantita"]
        prezzo = p["prezzo_unitario"]
        minimo = p["scorta_minima"]
        valore = quantita * prezzo
        mancanti = max(minimo - quantita, Decimal(0))
        valore_totale += valore
        pezzi_totali += quantita
        righe.append(
            {
                "codice": p["codice"],
                "nome": p["nome"],
                "quantita": formatta_numero(quantita),
                "prezzo_unitario": formatta_euro(prezzo),
                "scorta_minima": formatta_numero(minimo),
                "valore_in_magazzino": formatta_euro(valore),
                "sotto_scorta_minima": quantita < minimo,
                "pezzi_mancanti_per_scorta_minima": formatta_numero(mancanti),
                "costo_per_riportare_a_scorta_minima": formatta_euro(mancanti * prezzo),
            }
        )
    sotto_scorta = [r for r in righe if r["sotto_scorta_minima"]]
    return {
        "nota": (
            "Numeri in formato italiano (punto per le migliaia, virgola per i "
            "decimali). 'Sotto scorta minima' significa quantita < scorta_minima."
        ),
        "prodotti": righe,
        "totali": {
            "numero_prodotti": len(righe),
            "pezzi_totali": formatta_numero(pezzi_totali),
            "valore_totale_magazzino": formatta_euro(valore_totale),
            "prodotti_sotto_scorta_minima": [
                f'{r["nome"]} ({r["codice"]})' for r in sotto_scorta
            ],
            "costo_totale_per_riportare_tutto_a_scorta_minima": formatta_euro(
                sum(
                    (
                        max(p["scorta_minima"] - p["quantita"], Decimal(0))
                        * p["prezzo_unitario"]
                        for p in prodotti
                    ),
                    Decimal(0),
                )
            ),
        },
    }


# --- Calcolatrice esatta per domande non coperte dai valori già pronti ---

_OPERATORI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def valuta_espressione(espressione: str) -> Decimal:
    def valuta(nodo):
        if isinstance(nodo, ast.Expression):
            return valuta(nodo.body)
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
            # Usa il testo originale per evitare errori di virgola mobile.
            return Decimal(ast.get_source_segment(espressione, nodo))
        if isinstance(nodo, ast.BinOp) and type(nodo.op) in _OPERATORI:
            return _OPERATORI[type(nodo.op)](valuta(nodo.left), valuta(nodo.right))
        if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in _OPERATORI:
            return _OPERATORI[type(nodo.op)](valuta(nodo.operand))
        raise ValueError("sono ammessi solo numeri, + - * / e parentesi")

    return valuta(ast.parse(espressione, mode="eval"))


def crea_server_strumenti(dati: dict):
    @tool(
        "inventario",
        "Restituisce l'inventario completo con i valori già calcolati in modo "
        "esatto: per ogni prodotto quantità, prezzo, scorta minima, valore in "
        "magazzino, se è sotto scorta e quanti pezzi mancano; più i totali.",
        {},
    )
    async def strumento_inventario(args):
        return {
            "content": [
                {"type": "text", "text": json.dumps(dati, ensure_ascii=False, indent=1)}
            ]
        }

    @tool(
        "calcola",
        "Calcola in modo esatto un'espressione aritmetica (numeri con il punto "
        "decimale, + - * / e parentesi), es. '12 * 1.2 + 3'. Usala per "
        "qualsiasi conto non già presente nell'inventario.",
        {"espressione": str},
    )
    async def strumento_calcola(args):
        try:
            risultato = valuta_espressione(args["espressione"])
            testo = f"{risultato.normalize():f} (formato italiano: {formatta_numero(risultato.normalize())})"
        except (ValueError, SyntaxError, InvalidOperation, ZeroDivisionError) as e:
            return {"content": [{"type": "text", "text": f"Errore: {e}"}], "is_error": True}
        return {"content": [{"type": "text", "text": testo}]}

    return create_sdk_mcp_server(
        name="magazzino", tools=[strumento_inventario, strumento_calcola]
    )


ISTRUZIONI = """Sei l'assistente del magazzino. Rispondi alle domande dei colleghi \
sull'inventario.

Regole:
- Prima di rispondere chiama sempre lo strumento `inventario`.
- Non fare mai conti a mente: usa i valori già calcolati dall'inventario oppure \
lo strumento `calcola`. I numeri servono per fare ordini e devono essere esatti.
- Riporta i numeri esattamente come forniti (formato italiano, euro con due \
decimali e simbolo €).
- Rispondi in italiano con una sola frase breve che risponde esattamente a \
quello che è stato chiesto, senza aggiungere informazioni non richieste \
(codici, consigli, altri totali), senza markdown, elenchi puntati o premesse.
- Se l'inventario non contiene l'informazione richiesta, dillo chiaramente \
invece di inventare."""


async def rispondi(domanda: str, server, limite: asyncio.Semaphore) -> str:
    opzioni = ClaudeAgentOptions(
        system_prompt=ISTRUZIONI,
        mcp_servers={"magazzino": server},
        tools=[],  # niente strumenti integrati (file, shell, web...)
        allowed_tools=["mcp__magazzino__inventario", "mcp__magazzino__calcola"],
        max_turns=10,
    )
    async with limite:
        testo_finale = None
        ultimi_testi: list[str] = []
        async for messaggio in query(prompt=domanda, options=opzioni):
            if isinstance(messaggio, AssistantMessage):
                testi = [b.text for b in messaggio.content if isinstance(b, TextBlock)]
                if testi:
                    ultimi_testi = testi
            elif isinstance(messaggio, ResultMessage):
                if messaggio.is_error:
                    raise RuntimeError(
                        f"Errore da Claude per la domanda {domanda!r}: {messaggio.result}"
                    )
                testo_finale = messaggio.result
        risposta = (testo_finale or "\n".join(ultimi_testi)).strip()
        if not risposta:
            raise RuntimeError(f"Nessuna risposta per la domanda {domanda!r}")
        return risposta


async def main() -> None:
    dati = prepara_dati(carica_inventario())
    domande = [
        riga.strip()
        for riga in FILE_DOMANDE.read_text(encoding="utf-8").splitlines()
        if riga.strip()
    ]
    server = crea_server_strumenti(dati)
    limite = asyncio.Semaphore(DOMANDE_IN_PARALLELO)

    risposte = await asyncio.gather(*(rispondi(d, server, limite) for d in domande))

    risultato = [{"domanda": d, "risposta": r} for d, r in zip(domande, risposte)]
    FILE_RISULTATO.write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for voce in risultato:
        print(f"D: {voce['domanda']}\nR: {voce['risposta']}\n")
    print(f"Risultato scritto in {FILE_RISULTATO}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
