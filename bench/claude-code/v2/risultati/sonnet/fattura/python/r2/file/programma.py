"""Legge fattura.txt con Claude, estrae i dati e verifica il totale al centesimo."""
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

MODELLO = "claude-opus-5-5"


class Riga(BaseModel):
    descrizione: str
    quantita: float
    prezzo_unitario: float = Field(description="Prezzo unitario in euro, come numero")


class Fattura(BaseModel):
    fornitore: str = Field(description="Ragione sociale di chi emette la fattura")
    data: str = Field(description="Data della fattura nel formato AAAA-MM-GG")
    righe: list[Riga] = Field(description="Righe nell'ordine della fattura")
    totale_dichiarato: float = Field(description="Totale scritto in fattura, in euro")


ISTRUZIONI = (
    "Estrai i dati dalla fattura di un fornitore. Il fornitore è chi emette la fattura, "
    "non il destinatario. Riporta le righe nell'ordine della fattura, con quantità e "
    "prezzo unitario esattamente come scritti (non ricalcolare nulla e non usare la colonna "
    "degli importi di riga al posto del prezzo unitario). Il totale dichiarato è quello "
    "scritto in fattura. Gli importi sono numeri in euro (es. 12.5), la data è AAAA-MM-GG."
)


def numero(x: float):
    """Intero se è un valore intero, altrimenti float (per un JSON pulito)."""
    return int(x) if float(x).is_integer() else x


def main() -> int:
    percorso = Path("fattura.txt")
    if not percorso.is_file():
        print("Errore: fattura.txt non trovato nella cartella corrente.", file=sys.stderr)
        return 1
    testo = percorso.read_text(encoding="utf-8")

    client = anthropic.Anthropic()
    try:
        risposta = client.messages.parse(
            model=MODELLO,
            max_tokens=16000,
            output_config={"effort": "low"},
            system=ISTRUZIONI,
            messages=[{"role": "user", "content": f"<fattura>\n{testo}\n</fattura>"}],
            output_format=Fattura,
        )
    except TypeError as e:  # nessuna credenziale configurata
        print("Errore: manca la chiave API. Imposta ANTHROPIC_API_KEY.", file=sys.stderr)
        return 1
    except anthropic.APIError as e:
        print(f"Errore nella chiamata a Claude: {e}", file=sys.stderr)
        return 1

    fattura = risposta.parsed_output
    if fattura is None:
        print(f"Risposta non utilizzabile (stop_reason={risposta.stop_reason}).", file=sys.stderr)
        return 1

    cent = Decimal("0.01")
    # Decimal(str(x)) evita gli errori di rappresentazione dei float.
    calcolato = sum(
        (Decimal(str(r.quantita)) * Decimal(str(r.prezzo_unitario)) for r in fattura.righe),
        Decimal(0),
    ).quantize(cent, ROUND_HALF_UP)
    dichiarato = Decimal(str(fattura.totale_dichiarato)).quantize(cent, ROUND_HALF_UP)

    risultato = {
        "fornitore": fattura.fornitore,
        "data": fattura.data,
        "righe": [
            {
                "descrizione": r.descrizione,
                "quantita": numero(r.quantita),
                "prezzo_unitario": r.prezzo_unitario,
            }
            for r in fattura.righe
        ],
        "totale_dichiarato": float(dichiarato),
        "totale_calcolato": float(calcolato),
        "totale_corretto": calcolato == dichiarato,
    }
    Path("risultato.json").write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(risultato, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
