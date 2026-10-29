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

ISTRUZIONI = """Sei un assistente che estrae dati da fatture italiane in testo semplice.
Estrai dalla fattura:
- fornitore: la ragione sociale di chi emette la fattura (non il cliente destinatario), così come è scritta.
- data: la data della fattura in formato AAAA-MM-GG. Le date italiane sono scritte giorno/mese/anno (05/03/2026 = 5 marzo 2026 = 2026-03-05).
- righe: tutte le righe di dettaglio, nell'ordine in cui compaiono, con descrizione (testo della riga senza quantità e prezzi), quantita e prezzo_unitario in euro.
- totale_dichiarato: il totale finale da pagare scritto in fattura, in euro.
Gli importi italiani usano la virgola per i decimali e il punto per le migliaia (1.234,50 = 1234.50): restituiscili come numeri.
Riporta i valori come sono scritti in fattura, senza correggerli né ricalcolarli."""


class Riga(BaseModel):
    descrizione: str
    quantita: float
    prezzo_unitario: float


class DatiFattura(BaseModel):
    fornitore: str
    data: str = Field(description="Data della fattura in formato AAAA-MM-GG")
    righe: list[Riga]
    totale_dichiarato: float


def estrai_dati(testo: str) -> DatiFattura:
    client = anthropic.Anthropic()
    risposta = client.beta.messages.parse(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "medium"},
        # Se il modello rifiuta la richiesta, l'API la riprova su un modello di riserva.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": f"<fattura>\n{testo}\n</fattura>"}],
        output_format=DatiFattura,
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato di elaborare la fattura.")
    if risposta.stop_reason == "max_tokens":
        raise RuntimeError("La risposta di Claude è stata troncata.")
    if risposta.parsed_output is None:
        raise RuntimeError("Claude non ha restituito dati validi.")
    return risposta.parsed_output


def in_euro(valore: Decimal) -> float:
    return float(valore.quantize(CENTESIMO, rounding=ROUND_HALF_UP))


def numero(valore: float) -> int | float:
    # Le quantità intere restano intere nel JSON (4, non 4.0).
    return int(valore) if float(valore).is_integer() else valore


def main() -> int:
    if not FILE_FATTURA.exists():
        print(f"File {FILE_FATTURA} non trovato nella cartella corrente.", file=sys.stderr)
        return 1

    dati = estrai_dati(FILE_FATTURA.read_text(encoding="utf-8"))

    # Verifica che la data sia davvero una data valida AAAA-MM-GG.
    data = date.fromisoformat(dati.data).isoformat()

    # Calcolo con Decimal per evitare gli errori di arrotondamento dei float.
    totale = sum(
        (Decimal(str(r.quantita)) * Decimal(str(r.prezzo_unitario)) for r in dati.righe),
        Decimal("0"),
    )
    totale_calcolato = totale.quantize(CENTESIMO, rounding=ROUND_HALF_UP)
    totale_dichiarato = Decimal(str(dati.totale_dichiarato)).quantize(CENTESIMO, rounding=ROUND_HALF_UP)

    risultato = {
        "fornitore": dati.fornitore,
        "data": data,
        "righe": [
            {
                "descrizione": r.descrizione,
                "quantita": numero(r.quantita),
                "prezzo_unitario": r.prezzo_unitario,
            }
            for r in dati.righe
        ],
        "totale_dichiarato": in_euro(totale_dichiarato),
        "totale_calcolato": in_euro(totale_calcolato),
        "totale_corretto": totale_calcolato == totale_dichiarato,
    }

    FILE_RISULTATO.write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    esito = "corretto" if risultato["totale_corretto"] else "SBAGLIATO"
    print(f"Fornitore: {risultato['fornitore']} - data {data}")
    print(f"Totale dichiarato {totale_dichiarato} €, calcolato {totale_calcolato} €: {esito}.")
    print(f"Risultato scritto in {FILE_RISULTATO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
