"""Estrae i dati da fattura.txt con Claude e verifica il totale dichiarato.

Uso: python programma.py   (dalla cartella che contiene fattura.txt)
Scrive il risultato in risultato.json.
"""

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
        "fornitore": {
            "type": "string",
            "description": "Ragione sociale di chi emette la fattura (non il cliente destinatario).",
        },
        "data": {
            "type": "string",
            "description": "Data della fattura nel formato AAAA-MM-GG.",
        },
        "righe": {
            "type": "array",
            "description": "Righe di dettaglio, nell'ordine in cui compaiono in fattura.",
            "items": {
                "type": "object",
                "properties": {
                    "descrizione": {"type": "string"},
                    "quantita": {"type": "number"},
                    "prezzo_unitario": {
                        "type": "number",
                        "description": "Prezzo unitario in euro, come scritto in fattura.",
                    },
                },
                "required": ["descrizione", "quantita", "prezzo_unitario"],
                "additionalProperties": False,
            },
        },
        "totale_dichiarato": {
            "type": "number",
            "description": "Totale finale da pagare scritto in fattura, in euro.",
        },
    },
    "required": ["fornitore", "data", "righe", "totale_dichiarato"],
    "additionalProperties": False,
}

ISTRUZIONI = """Sei un estrattore di dati da fatture italiane in testo semplice.
Leggi la fattura e restituisci i dati richiesti dallo schema, copiando i valori
così come sono scritti, senza ricalcolare nulla:
- fornitore: chi emette la fattura, non il cliente ("Spett.le ...").
- data: la data di emissione della fattura, convertita in AAAA-MM-GG
  (le date italiane sono nel formato GG/MM/AAAA).
- righe: una per ogni voce di dettaglio, nell'ordine della fattura. La descrizione
  è il testo della voce; quantità e prezzo unitario vanno presi dalle rispettive
  colonne (attenzione a non confondere numeri che fanno parte della descrizione,
  come "latta 5 l", con la quantità). Gli importi con la virgola decimale
  (es. "€ 1.234,50") vanno resi come numeri (1234.5).
- totale_dichiarato: il totale finale da pagare scritto in fattura."""


async def estrai_dati(testo_fattura: str) -> dict:
    opzioni = ClaudeAgentOptions(
        model="claude-opus-5-5",
        system_prompt=ISTRUZIONI,
        tools=[],  # nessuno strumento: Claude deve solo leggere il testo che gli passiamo
        setting_sources=[],
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    prompt = f"Ecco la fattura:\n\n<fattura>\n{testo_fattura}\n</fattura>"

    risultato = None
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            risultato = messaggio

    if risultato is None:
        raise RuntimeError("Nessuna risposta da Claude.")
    if risultato.is_error or risultato.structured_output is None:
        dettagli = risultato.errors or risultato.result or risultato.subtype
        raise RuntimeError(f"Estrazione non riuscita: {dettagli}")
    return risultato.structured_output


def in_euro(valore) -> Decimal:
    # Passando da str si evitano gli errori di rappresentazione dei float.
    return Decimal(str(valore))


def come_numero(valore: Decimal):
    return int(valore) if valore == valore.to_integral_value() else float(valore)


def costruisci_risultato(dati: dict) -> dict:
    data_fattura = date.fromisoformat(dati["data"])  # solleva errore se non è AAAA-MM-GG

    totale_calcolato = sum(
        (in_euro(r["quantita"]) * in_euro(r["prezzo_unitario"]) for r in dati["righe"]),
        Decimal("0"),
    ).quantize(CENTESIMO, rounding=ROUND_HALF_UP)
    totale_dichiarato = in_euro(dati["totale_dichiarato"]).quantize(CENTESIMO)

    return {
        "fornitore": dati["fornitore"],
        "data": data_fattura.isoformat(),
        "righe": [
            {
                "descrizione": r["descrizione"],
                "quantita": come_numero(in_euro(r["quantita"])),
                "prezzo_unitario": float(in_euro(r["prezzo_unitario"])),
            }
            for r in dati["righe"]
        ],
        "totale_dichiarato": float(totale_dichiarato),
        "totale_calcolato": float(totale_calcolato),
        "totale_corretto": totale_calcolato == totale_dichiarato,
    }


def main() -> int:
    if not FILE_FATTURA.exists():
        print(f"File {FILE_FATTURA} non trovato nella cartella corrente.", file=sys.stderr)
        return 1

    dati = asyncio.run(estrai_dati(FILE_FATTURA.read_text(encoding="utf-8")))
    risultato = costruisci_risultato(dati)

    FILE_RISULTATO.write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Fornitore: {risultato['fornitore']}  -  Data: {risultato['data']}")
    print(f"Totale dichiarato: € {risultato['totale_dichiarato']:.2f}")
    print(f"Totale calcolato:  € {risultato['totale_calcolato']:.2f}")
    if risultato["totale_corretto"]:
        print("Il totale in fattura è corretto.")
    else:
        differenza = Decimal(str(risultato["totale_dichiarato"])) - Decimal(
            str(risultato["totale_calcolato"])
        )
        print(f"ATTENZIONE: il totale in fattura NON torna (differenza € {differenza}).")
    print(f"Risultato scritto in {FILE_RISULTATO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
