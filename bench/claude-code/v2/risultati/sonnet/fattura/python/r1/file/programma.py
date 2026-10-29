"""Legge fattura.txt con Claude, ricalcola il totale e scrive risultato.json."""
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import anthropic
from pydantic import BaseModel

MODELLO = "claude-opus-5-5"

ISTRUZIONI = """\
Sei un assistente che legge fatture di fornitori in testo semplice.
Estrai:
- fornitore: la ragione sociale di chi EMETTE la fattura (non il cliente);
- data: la data della fattura nel formato AAAA-MM-GG;
- righe: tutte le righe di merce/servizio, nell'ordine della fattura, con
  descrizione, quantita e prezzo_unitario (in euro, come numero: 3,40 -> 3.4);
- totale_dichiarato: il totale finale scritto in fattura (quello da pagare),
  in euro, come numero.
Copia i valori come sono scritti nella fattura: NON ricalcolare nulla e non
correggere eventuali errori. Non inventare righe che non esistono."""


class Riga(BaseModel):
    descrizione: str
    quantita: float
    prezzo_unitario: float


class Fattura(BaseModel):
    fornitore: str
    data: str
    righe: list[Riga]
    totale_dichiarato: float


def estrai(testo: str) -> Fattura:
    client = anthropic.Anthropic()
    risposta = client.messages.parse(
        model=MODELLO,
        max_tokens=16000,
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": testo}],
        output_format=Fattura,
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato la richiesta")
    if risposta.parsed_output is None:
        raise RuntimeError(f"Risposta non valida (stop_reason={risposta.stop_reason})")
    return risposta.parsed_output


def in_centesimi(valore: float) -> Decimal:
    return Decimal(str(valore)).quantize(Decimal("0.01"))


def numero(valore: float):
    """Interi senza '.0' (4, non 4.0); altrimenti float."""
    return int(valore) if float(valore).is_integer() else valore


def elabora(f: Fattura) -> dict:
    date.fromisoformat(f.data)  # fallisce se non è AAAA-MM-GG valida
    # Somma esatta con Decimal, poi arrotondata al centesimo una volta sola.
    calcolato = sum(
        (Decimal(str(r.quantita)) * Decimal(str(r.prezzo_unitario)) for r in f.righe),
        Decimal(0),
    ).quantize(Decimal("0.01"))
    return {
        "fornitore": f.fornitore,
        "data": f.data,
        "righe": [
            {
                "descrizione": r.descrizione,
                "quantita": numero(r.quantita),
                "prezzo_unitario": r.prezzo_unitario,
            }
            for r in f.righe
        ],
        "totale_dichiarato": f.totale_dichiarato,
        "totale_calcolato": float(calcolato),
        "totale_corretto": in_centesimi(f.totale_dichiarato) == calcolato,
    }


def main() -> int:
    try:
        testo = Path("fattura.txt").read_text(encoding="utf-8")
    except FileNotFoundError:
        print("Errore: fattura.txt non trovato nella cartella corrente.", file=sys.stderr)
        return 1
    try:
        risultato = elabora(estrai(testo))
    except TypeError as e:
        if "authentication" in str(e):
            print("Errore: imposta la variabile d'ambiente ANTHROPIC_API_KEY.", file=sys.stderr)
            return 1
        raise
    except anthropic.APIError as e:
        print(f"Errore nella chiamata a Claude: {e}", file=sys.stderr)
        return 1
    except (RuntimeError, ValueError) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1

    Path("risultato.json").write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if risultato["totale_corretto"]:
        print(f"Totale corretto: {risultato['totale_calcolato']:.2f} €")
    else:
        print(
            f"TOTALE SBAGLIATO: in fattura {risultato['totale_dichiarato']:.2f} €, "
            f"ricalcolato {risultato['totale_calcolato']:.2f} €"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
