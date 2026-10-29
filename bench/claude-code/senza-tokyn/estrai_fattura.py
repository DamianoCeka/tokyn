"""Estrae con Claude i dati di una fattura in testo libero e verifica il totale.

Uso:  python estrai_fattura.py [fattura.txt]
Richiede: pip install anthropic pydantic  e  ANTHROPIC_API_KEY impostata.
"""
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"
TOLLERANZA = Decimal("0.01")


class Riga(BaseModel):
    descrizione: str
    quantita: float
    prezzo_unitario: float


class Fattura(BaseModel):
    fornitore: str
    data: str  # formato ISO AAAA-MM-GG
    righe: list[Riga]
    totale: float  # totale così come scritto in fattura


PROMPT = """Estrai i dati da questa fattura.
- data in formato AAAA-MM-GG
- per ogni riga: descrizione, quantità e prezzo unitario (non il prezzo di riga)
- totale: il valore esattamente come riportato nella fattura, senza ricalcolarlo
- i numeri con la virgola decimale italiana (es. 1,50) vanno resi come 1.50

<fattura>
{testo}
</fattura>"""


def estrai(testo: str) -> Fattura:
    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "low"},
        # Se i classificatori di sicurezza rifiutano, il server riprova su un altro modello.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": PROMPT.format(testo=testo)}],
        output_format=Fattura,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Richiesta rifiutata dal modello: {response.stop_details}")
    if response.parsed_output is None:
        raise RuntimeError(f"Estrazione fallita (stop_reason={response.stop_reason})")
    return response.parsed_output


def euro(x: float | Decimal) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def verifica(f: Fattura) -> bool:
    """Stampa il riepilogo e restituisce True se il totale dichiarato corrisponde."""
    print(f"Fornitore: {f.fornitore}")
    print(f"Data:      {f.data}")
    print("Righe:")
    ricalcolato = Decimal("0")
    for r in f.righe:
        importo = euro(Decimal(str(r.quantita)) * Decimal(str(r.prezzo_unitario)))
        ricalcolato += importo
        print(f"  {r.quantita:g} x {r.descrizione:<20} @ {euro(r.prezzo_unitario):>8} = {importo:>8}")
    dichiarato = euro(f.totale)
    print(f"Totale dichiarato: {dichiarato} euro")
    print(f"Totale ricalcolato: {ricalcolato} euro")
    if abs(dichiarato - ricalcolato) > TOLLERANZA:
        print(f"⚠️  ATTENZIONE: il totale non corrisponde (differenza {dichiarato - ricalcolato:+} euro)")
        return False
    print("✅ Il totale corrisponde.")
    return True


def main() -> int:
    percorso = Path(sys.argv[1] if len(sys.argv) > 1 else "fattura.txt")
    fattura = estrai(percorso.read_text(encoding="utf-8"))
    return 0 if verifica(fattura) else 1


if __name__ == "__main__":
    sys.exit(main())
