"""Legge fattura.txt con Claude, estrae i dati e verifica il totale.

Uso: python programma.py   (dalla cartella che contiene fattura.txt)
Scrive risultato.json nella stessa cartella.
"""

import asyncio
import json
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

MODELLO = "claude-opus-5-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "fornitore": {"type": "string"},
        "data": {"type": "string", "description": "Data della fattura, formato AAAA-MM-GG"},
        "righe": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "descrizione": {"type": "string"},
                    "quantita": {"type": "number"},
                    "prezzo_unitario": {"type": "number", "description": "Euro, per unità"},
                },
                "required": ["descrizione", "quantita", "prezzo_unitario"],
                "additionalProperties": False,
            },
        },
        "totale_dichiarato": {"type": "number", "description": "Totale scritto in fattura, in euro"},
    },
    "required": ["fornitore", "data", "righe", "totale_dichiarato"],
    "additionalProperties": False,
}

ISTRUZIONI = """Estrai i dati dalla fattura di un fornitore qui sotto.

- fornitore: la ragione sociale di chi emette la fattura (non del destinatario).
- data: la data della fattura in formato AAAA-MM-GG. Le date italiane sono GG/MM/AAAA.
- righe: tutte le righe di merce/servizi, nell'ordine in cui compaiono. Per ognuna descrizione,
  quantità e prezzo unitario, copiati dal documento. Non ricalcolare né correggere nulla,
  e non usare la colonna dell'importo di riga al posto del prezzo unitario.
- totale_dichiarato: il totale finale scritto in fattura, così com'è, anche se sembra sbagliato.
- Importi in euro come numeri (virgola decimale italiana -> punto, niente simbolo €).

FATTURA:
{testo}
"""


def centesimi(valore: Decimal) -> Decimal:
    return valore.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def numero(valore: Decimal) -> int | float:
    """Numero JSON: intero se non ha decimali, altrimenti float."""
    return int(valore) if valore == valore.to_integral_value() else float(valore)


async def estrai(testo: str) -> dict:
    opzioni = ClaudeAgentOptions(
        model=MODELLO,
        tools=[],  # nessuno strumento: serve solo leggere il testo
        max_turns=3,
        setting_sources=[],  # ignora configurazioni locali
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    risultato = None
    async for msg in query(prompt=ISTRUZIONI.format(testo=testo), options=opzioni):
        if isinstance(msg, ResultMessage):
            risultato = msg
    if risultato is None:
        raise RuntimeError("Nessuna risposta da Claude")
    if risultato.is_error or risultato.structured_output is None:
        raise RuntimeError(
            f"Estrazione fallita ({risultato.subtype}): {risultato.errors or risultato.result}"
        )
    return risultato.structured_output


def costruisci_risultato(dati: dict) -> dict:
    date.fromisoformat(dati["data"])  # fallisce se Claude non ha rispettato AAAA-MM-GG
    if not dati["righe"]:
        raise ValueError("Nessuna riga estratta dalla fattura")

    # Decimal da str(): niente errori binari dei float, il confronto è esatto al centesimo
    calcolato = centesimi(
        sum((Decimal(str(r["quantita"])) * Decimal(str(r["prezzo_unitario"])) for r in dati["righe"]),
            Decimal(0))
    )
    dichiarato = centesimi(Decimal(str(dati["totale_dichiarato"])))

    return {
        "fornitore": dati["fornitore"],
        "data": dati["data"],
        "righe": [
            {
                "descrizione": r["descrizione"],
                "quantita": numero(Decimal(str(r["quantita"]))),
                "prezzo_unitario": numero(Decimal(str(r["prezzo_unitario"]))),
            }
            for r in dati["righe"]
        ],
        "totale_dichiarato": numero(dichiarato),
        "totale_calcolato": numero(calcolato),
        "totale_corretto": dichiarato == calcolato,
    }


def main() -> int:
    percorso = Path("fattura.txt")
    if not percorso.is_file():
        print("fattura.txt non trovato nella cartella corrente", file=sys.stderr)
        return 1
    try:
        dati = asyncio.run(estrai(percorso.read_text(encoding="utf-8")))
        out = costruisci_risultato(dati)
    except Exception as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1
    Path("risultato.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    esito = "CORRETTO" if out["totale_corretto"] else "ERRATO"
    print(f"Totale in fattura {out['totale_dichiarato']:.2f} €, ricalcolato {out['totale_calcolato']:.2f} €: {esito}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
