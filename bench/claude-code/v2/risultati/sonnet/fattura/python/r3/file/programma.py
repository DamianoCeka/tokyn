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
Estrai i dati dalla fattura di un fornitore fornita dall'utente.

- fornitore: chi emette la fattura (il venditore), non il cliente a cui è intestata.
- data: la data della fattura in formato AAAA-MM-GG. Le date italiane sono GG/MM/AAAA.
- righe: tutte le righe di prodotto, nell'ordine in cui compaiono, con descrizione \
(senza l'unità di misura tra parentesi solo se non fa parte del nome; in dubbio \
copiala com'è scritta), quantità e prezzo unitario in euro come numero.
- totale_dichiarato: il totale finale scritto in fattura (es. "Totale da pagare"), \
copiato così com'è, senza ricalcolarlo.

Non correggere né ricalcolare nulla: riporta fedelmente ciò che è scritto."""


class Riga(BaseModel):
    descrizione: str
    quantita: float
    prezzo_unitario: float


class Fattura(BaseModel):
    fornitore: str
    data: str
    righe: list[Riga]
    totale_dichiarato: float


def estrai(testo: str, client: anthropic.Anthropic) -> Fattura:
    risposta = client.messages.parse(
        model=MODELLO,
        max_tokens=16000,
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": testo}],
        output_format=Fattura,
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato la richiesta.")
    if risposta.parsed_output is None:
        raise RuntimeError("Risposta di Claude non valida o troncata.")
    return risposta.parsed_output


def numero(valore: Decimal | float):
    """Numero per il JSON: int se intero, altrimenti float."""
    d = Decimal(str(valore))
    return int(d) if d == d.to_integral_value() else float(d)


def costruisci_risultato(f: Fattura) -> dict:
    data = date.fromisoformat(f.data).isoformat()  # solleva errore se non AAAA-MM-GG

    # Calcolo in Decimal per evitare errori di arrotondamento dei float.
    calcolato = sum(
        (Decimal(str(r.quantita)) * Decimal(str(r.prezzo_unitario)) for r in f.righe),
        Decimal("0"),
    )
    dichiarato = Decimal(str(f.totale_dichiarato))

    return {
        "fornitore": f.fornitore,
        "data": data,
        "righe": [
            {
                "descrizione": r.descrizione,
                "quantita": numero(r.quantita),
                "prezzo_unitario": numero(r.prezzo_unitario),
            }
            for r in f.righe
        ],
        "totale_dichiarato": numero(dichiarato),
        "totale_calcolato": numero(calcolato),
        # Confronto al centesimo: il totale calcolato è arrotondato a 2 decimali.
        "totale_corretto": calcolato.quantize(Decimal("0.01")) == dichiarato.quantize(Decimal("0.01")),
    }


def main() -> int:
    percorso = Path("fattura.txt")
    if not percorso.is_file():
        print("Errore: fattura.txt non trovato nella cartella corrente.", file=sys.stderr)
        return 1

    try:
        fattura = estrai(percorso.read_text(encoding="utf-8"), anthropic.Anthropic())
        risultato = costruisci_risultato(fattura)
    except (anthropic.AuthenticationError, TypeError) as e:
        # TypeError: l'SDK non trova nessuna credenziale (ANTHROPIC_API_KEY non impostata).
        if isinstance(e, TypeError) and "authentication" not in str(e).lower():
            raise
        print("Errore: chiave API mancante o non valida (ANTHROPIC_API_KEY).", file=sys.stderr)
        return 1
    except anthropic.APIError as e:
        print(f"Errore dall'API di Claude: {e}", file=sys.stderr)
        return 1
    except (RuntimeError, ValueError) as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1

    Path("risultato.json").write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    stato = "CORRETTO" if risultato["totale_corretto"] else "ERRATO"
    print(
        f"Totale in fattura {risultato['totale_dichiarato']:.2f} €, "
        f"ricalcolato {risultato['totale_calcolato']:.2f} €: {stato}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
