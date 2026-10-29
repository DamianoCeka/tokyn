"""Estrae dati strutturati da fattura.txt, ricalcola il totale nel codice e segnala anomalie."""
import sys
from decimal import Decimal

import anthropic
from pydantic import BaseModel

MODEL = "claude-sonnet-5-5"


class Riga(BaseModel):
    descrizione: str
    quantita: float
    prezzo_unitario: float


class Fattura(BaseModel):
    fornitore: str
    numero_fattura: str
    righe: list[Riga]


client = anthropic.Anthropic()


def estrai(testo: str) -> Fattura:
    risposta = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=(
            "Estrai i dati da fatture in italiano. Riporta fedelmente quantita e prezzi unitari "
            "(numeri con il punto come separatore decimale, senza simboli di valuta). "
            "Non calcolare totali e non inventare righe."
        ),
        tools=[
            {
                "name": "registra_fattura",
                "description": "Registra i dati estratti dalla fattura.",
                "input_schema": Fattura.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "registra_fattura"},
        messages=[{"role": "user", "content": f"Testo della fattura:\n\n{testo}"}],
    )
    for b in risposta.content:
        if b.type == "tool_use":
            return Fattura.model_validate(b.input)
    raise RuntimeError("Nessun dato estratto")


def main() -> None:
    try:
        with open("fattura.txt", encoding="utf-8") as f:
            testo = f.read()
    except FileNotFoundError:
        sys.exit("File fattura.txt non trovato.")

    fattura = estrai(testo)
    print(f"Fornitore: {fattura.fornitore}")
    print(f"Fattura n.: {fattura.numero_fattura}\n")

    totale = Decimal("0")
    avvisi = []
    for i, r in enumerate(fattura.righe, 1):
        q, p = Decimal(str(r.quantita)), Decimal(str(r.prezzo_unitario))
        importo = q * p
        totale += importo
        print(f"{i:>2}. {r.descrizione:<40} {q:>8} x {p:>10.2f} = {importo:>11.2f}")
        if q == 0:
            avvisi.append(f"Riga {i} ('{r.descrizione}'): quantita pari a zero")

    print(f"\nTotale ricalcolato: {totale:.2f}")
    for a in avvisi:
        print(f"ATTENZIONE: {a}")


if __name__ == "__main__":
    main()
