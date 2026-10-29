"""Legge fattura.txt con Claude, ricalcola il totale e scrive risultato.json."""

import asyncio
import json
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

FILE_FATTURA = Path("fattura.txt")
FILE_RISULTATO = Path("risultato.json")
CENTESIMO = Decimal("0.01")

SCHEMA = {
    "type": "object",
    "properties": {
        "fornitore": {"type": "string"},
        "data": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "righe": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "descrizione": {"type": "string"},
                    "quantita": {"type": "number"},
                    "prezzo_unitario": {"type": "number"},
                },
                "required": ["descrizione", "quantita", "prezzo_unitario"],
                "additionalProperties": False,
            },
        },
        "totale_dichiarato": {"type": "number"},
    },
    "required": ["fornitore", "data", "righe", "totale_dichiarato"],
    "additionalProperties": False,
}

ISTRUZIONI = """Sei un estrattore di dati da fatture italiane in testo semplice.
Riporta i dati esattamente come scritti nella fattura, senza correggerli né ricalcolarli:
- fornitore: la ragione sociale di chi emette la fattura (non il cliente destinatario);
- data: la data della fattura convertita in formato AAAA-MM-GG;
- righe: tutte le righe di dettaglio, nell'ordine in cui compaiono, con descrizione,
  quantità e prezzo unitario in euro (converti la virgola decimale in punto);
- totale_dichiarato: il totale finale da pagare scritto in fattura, in euro.
Non inventare righe e non usare l'importo di riga al posto del prezzo unitario."""


async def estrai_dati(testo: str) -> dict:
    opzioni = ClaudeAgentOptions(
        model="claude-opus-5-5",
        system_prompt=ISTRUZIONI,
        tools=[],  # il testo è già nel prompt: nessuno strumento serve
        setting_sources=[],
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    prompt = f"Estrai i dati da questa fattura:\n\n<fattura>\n{testo}\n</fattura>"
    dati = None
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            if messaggio.is_error or messaggio.structured_output is None:
                raise RuntimeError(
                    f"Estrazione non riuscita ({messaggio.subtype}): {messaggio.result}"
                )
            dati = messaggio.structured_output
    if dati is None:
        raise RuntimeError("Nessun risultato ricevuto da Claude")
    return dati


def come_decimale(valore) -> Decimal:
    # str() evita di portarsi dietro gli errori di rappresentazione dei float
    return Decimal(str(valore))


def come_numero(valore: Decimal):
    return int(valore) if valore == valore.to_integral_value() else float(valore)


def costruisci_risultato(dati: dict) -> dict:
    data_fattura = date.fromisoformat(dati["data"])  # solleva errore se non valida
    righe = []
    totale = Decimal("0")
    for riga in dati["righe"]:
        quantita = come_decimale(riga["quantita"])
        prezzo = come_decimale(riga["prezzo_unitario"])
        totale += quantita * prezzo
        righe.append(
            {
                "descrizione": riga["descrizione"].strip(),
                "quantita": come_numero(quantita),
                "prezzo_unitario": float(prezzo),
            }
        )
    totale_calcolato = totale.quantize(CENTESIMO, rounding=ROUND_HALF_UP)
    totale_dichiarato = come_decimale(dati["totale_dichiarato"]).quantize(
        CENTESIMO, rounding=ROUND_HALF_UP
    )
    return {
        "fornitore": dati["fornitore"].strip(),
        "data": data_fattura.isoformat(),
        "righe": righe,
        "totale_dichiarato": float(totale_dichiarato),
        "totale_calcolato": float(totale_calcolato),
        "totale_corretto": totale_calcolato == totale_dichiarato,
    }


def main() -> int:
    if not FILE_FATTURA.exists():
        print(f"File {FILE_FATTURA} non trovato nella cartella corrente", file=sys.stderr)
        return 1
    testo = FILE_FATTURA.read_text(encoding="utf-8")
    dati = asyncio.run(estrai_dati(testo))
    risultato = costruisci_risultato(dati)
    FILE_RISULTATO.write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Fornitore: {risultato['fornitore']}  Data: {risultato['data']}")
    print(f"Totale dichiarato: € {risultato['totale_dichiarato']:.2f}")
    print(f"Totale calcolato:  € {risultato['totale_calcolato']:.2f}")
    if risultato["totale_corretto"]:
        print("Il totale in fattura è corretto.")
    else:
        differenza = Decimal(str(risultato["totale_dichiarato"])) - Decimal(
            str(risultato["totale_calcolato"])
        )
        print(f"ATTENZIONE: il totale in fattura non torna (differenza € {differenza:.2f}).")
    print(f"Risultato scritto in {FILE_RISULTATO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
