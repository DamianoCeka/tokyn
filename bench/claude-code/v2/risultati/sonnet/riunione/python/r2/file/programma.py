"""Estrae decisioni e azioni da verbale.txt usando Claude e scrive risultato.json.

Uso: python programma.py   (dalla cartella che contiene verbale.txt)
Richiede la variabile d'ambiente ANTHROPIC_API_KEY.
"""

import json
import sys
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

MODELLO = "claude-opus-5-5"


class Azione(BaseModel):
    cosa: str = Field(description="Che cosa va fatto")
    chi: str = Field(description="Nome di chi se ne occupa")
    entro: str = Field(description="Scadenza nel formato AAAA-MM-GG")


class Risultato(BaseModel):
    decisioni: list[str] = Field(description="Decisioni prese, come frasi brevi")
    azioni: list[Azione]


ISTRUZIONI = """\
Ricevi la trascrizione di una riunione di team. Ricava:
- decisioni: le decisioni effettivamente prese (non le semplici discussioni o le domande \
fuori tema), ciascuna come frase breve e affermativa.
- azioni: i compiti assegnati, con cosa va fatto, chi se ne occupa (solo il nome \
di battesimo, come compare nel verbale) e la scadenza.

Le scadenze vanno scritte nel formato AAAA-MM-GG. Se nel testo compaiono date relative \
(es. "venerdì prossimo"), calcolale partendo dalla data della riunione indicata nel verbale. \
Non inventare nulla che nel verbale non c'è: includi un'azione solo se ha un responsabile \
e una scadenza chiari."""


def main() -> int:
    verbale = Path("verbale.txt")
    if not verbale.is_file():
        print("Errore: non trovo verbale.txt nella cartella corrente.", file=sys.stderr)
        return 1
    testo = verbale.read_text(encoding="utf-8")
    if not testo.strip():
        print("Errore: verbale.txt è vuoto.", file=sys.stderr)
        return 1

    try:
        client = anthropic.Anthropic()
        return elabora(client, testo)
    except TypeError as e:
        # Il client solleva TypeError quando non trova alcuna credenziale.
        if "authentication method" not in str(e):
            raise
        print("Errore: imposta la variabile d'ambiente ANTHROPIC_API_KEY.", file=sys.stderr)
        return 1


def elabora(client: anthropic.Anthropic, testo: str) -> int:
    try:
        risposta = client.messages.parse(
            model=MODELLO,
            max_tokens=16000,
            system=ISTRUZIONI,
            messages=[{"role": "user", "content": f"<verbale>\n{testo}\n</verbale>"}],
            output_format=Risultato,
        )
    except anthropic.AuthenticationError:
        print("Errore: chiave API mancante o non valida (ANTHROPIC_API_KEY).", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError as e:
        print(f"Errore di connessione all'API: {e}", file=sys.stderr)
        return 1
    except anthropic.APIStatusError as e:
        print(f"Errore dell'API ({e.status_code}): {e.message}", file=sys.stderr)
        return 1

    if risposta.stop_reason == "refusal":
        print("Claude ha rifiutato di elaborare il verbale.", file=sys.stderr)
        return 1
    risultato = risposta.parsed_output
    if risultato is None:
        print(f"Risposta non valida (stop_reason={risposta.stop_reason}).", file=sys.stderr)
        return 1

    Path("risultato.json").write_text(
        json.dumps(risultato.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Scritto risultato.json: {len(risultato.decisioni)} decisioni, "
          f"{len(risultato.azioni)} azioni.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
