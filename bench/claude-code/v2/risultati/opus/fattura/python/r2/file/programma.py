"""Legge fattura.txt con Claude, ricalcola il totale e scrive risultato.json."""

import json
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

FILE_FATTURA = Path("fattura.txt")
FILE_RISULTATO = Path("risultato.json")
CENTESIMO = Decimal("0.01")

ISTRUZIONI = """Estrai i dati dalla fattura di un fornitore italiano che ti viene fornita come testo.

- fornitore: la ragione sociale di chi emette la fattura (non il cliente destinatario), come scritta.
- data: la data della fattura in formato AAAA-MM-GG. Le date italiane sono giorno/mese/anno.
- righe: tutte le righe di dettaglio, nell'ordine in cui compaiono, con descrizione, quantità e
  prezzo unitario come numeri (virgola decimale italiana -> punto, niente simbolo €).
  Non includere righe di totale, subtotale, IVA o sconto riepilogativo.
- totale_dichiarato: il totale finale da pagare scritto in fattura, come numero.

Riporta i valori esattamente come scritti: non correggere né ricalcolare nulla."""


class Riga(BaseModel):
    descrizione: str
    quantita: float
    prezzo_unitario: float


class Fattura(BaseModel):
    fornitore: str
    data: str = Field(description="Data della fattura in formato AAAA-MM-GG")
    righe: list[Riga]
    totale_dichiarato: float


def estrai_fattura(testo: str) -> Fattura:
    client = anthropic.Anthropic()
    risposta = client.beta.messages.parse(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": f"<fattura>\n{testo}\n</fattura>"}],
        output_format=Fattura,
    )
    if risposta.stop_reason == "refusal":
        sys.exit("Claude ha rifiutato di elaborare la fattura.")
    if risposta.stop_reason == "max_tokens":
        sys.exit("Risposta di Claude troncata: fattura troppo lunga.")
    if risposta.parsed_output is None:
        sys.exit("Claude non ha restituito dati strutturati validi.")
    return risposta.parsed_output


def numero(valore: Decimal) -> int | float:
    """Converte in numero JSON: intero se non ha decimali, altrimenti float."""
    return int(valore) if valore == valore.to_integral_value() else float(valore)


def main() -> None:
    if not FILE_FATTURA.exists():
        sys.exit(f"File {FILE_FATTURA} non trovato nella cartella corrente.")
    fattura = estrai_fattura(FILE_FATTURA.read_text(encoding="utf-8"))

    try:
        data = date.fromisoformat(fattura.data).isoformat()
    except ValueError:
        sys.exit(f"Data non valida estratta dalla fattura: {fattura.data!r}")

    # Decimal(str(...)) evita gli errori di arrotondamento dei float binari
    righe = [
        (r.descrizione, Decimal(str(r.quantita)), Decimal(str(r.prezzo_unitario)))
        for r in fattura.righe
    ]
    totale_calcolato = sum((q * p for _, q, p in righe), Decimal("0"))
    totale_calcolato = totale_calcolato.quantize(CENTESIMO, rounding=ROUND_HALF_UP)
    totale_dichiarato = Decimal(str(fattura.totale_dichiarato)).quantize(
        CENTESIMO, rounding=ROUND_HALF_UP
    )

    risultato = {
        "fornitore": fattura.fornitore,
        "data": data,
        "righe": [
            {"descrizione": d, "quantita": numero(q), "prezzo_unitario": float(p)}
            for d, q, p in righe
        ],
        "totale_dichiarato": float(totale_dichiarato),
        "totale_calcolato": float(totale_calcolato),
        "totale_corretto": totale_calcolato == totale_dichiarato,
    }
    FILE_RISULTATO.write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    esito = "CORRETTO" if risultato["totale_corretto"] else "ERRATO"
    print(
        f"Totale dichiarato € {totale_dichiarato}, calcolato € {totale_calcolato}: {esito}"
    )
    print(f"Risultato scritto in {FILE_RISULTATO}")


if __name__ == "__main__":
    main()
