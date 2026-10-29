"""Ricava decisioni e azioni dalla trascrizione di una riunione (verbale.txt)
e le scrive in risultato.json usando Claude.

Uso: python programma.py   (dalla cartella che contiene verbale.txt)
"""

import datetime
import json
import os
import sys
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

FILE_VERBALE = Path("verbale.txt")
FILE_RISULTATO = Path("risultato.json")
MODELLO = "claude-opus-5-5"

ISTRUZIONI = """Ricevi la trascrizione di una riunione di lavoro. Estrai:

1. "decisioni": le decisioni effettivamente prese durante la riunione, ognuna come
   frase breve in italiano. Non includere proposte rimaste in sospeso, opinioni o
   chiacchiere non pertinenti.
2. "azioni": i compiti assegnati a qualcuno. Per ognuno indica:
   - "cosa": che cosa va fatto, frase breve all'infinito (es. "Prenotare lo stand");
   - "chi": il nome della persona che se ne occupa, come compare nella trascrizione;
   - "entro": la scadenza nel formato AAAA-MM-GG. Se la scadenza è relativa
     ("venerdì prossimo", "entro fine mese"), calcolala rispetto alla data della
     riunione indicata nella trascrizione. Se non è stata detta nessuna scadenza,
     usa null: non inventarla.

Riporta solo ciò che risulta dalla trascrizione."""


class Azione(BaseModel):
    cosa: str = Field(description="Che cosa va fatto")
    chi: str = Field(description="Nome di chi se ne occupa")
    entro: str | None = Field(description="Scadenza AAAA-MM-GG, null se non indicata")


class Risultato(BaseModel):
    decisioni: list[str]
    azioni: list[Azione]


def estrai(trascrizione: str) -> Risultato:
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("Errore: manca la chiave API. Imposta la variabile ANTHROPIC_API_KEY.")
    client = anthropic.Anthropic()
    oggi = datetime.date.today().isoformat()
    risposta = client.messages.parse(
        model=MODELLO,
        max_tokens=16000,
        system=ISTRUZIONI,
        messages=[{
            "role": "user",
            "content": (
                f"Data di oggi (da usare solo se la trascrizione non riporta la data "
                f"della riunione): {oggi}\n\n<trascrizione>\n{trascrizione}\n</trascrizione>"
            ),
        }],
        output_format=Risultato,
    )
    if risposta.stop_reason == "refusal":
        sys.exit("Errore: Claude ha rifiutato di elaborare la trascrizione.")
    if risposta.stop_reason == "max_tokens":
        sys.exit("Errore: la risposta di Claude è stata troncata.")
    return risposta.parsed_output


def controlla_date(risultato: Risultato) -> None:
    """Avvisa se una scadenza non è una data valida nel formato AAAA-MM-GG."""
    for azione in risultato.azioni:
        if azione.entro is None:
            print(f"Attenzione: nessuna scadenza per \"{azione.cosa}\" ({azione.chi}).")
            continue
        try:
            datetime.date.fromisoformat(azione.entro)
        except ValueError:
            print(f"Attenzione: scadenza non valida \"{azione.entro}\" per \"{azione.cosa}\".")


def main() -> None:
    if not FILE_VERBALE.exists():
        sys.exit(f"Errore: non trovo {FILE_VERBALE} nella cartella corrente.")
    trascrizione = FILE_VERBALE.read_text(encoding="utf-8").strip()
    if not trascrizione:
        sys.exit(f"Errore: {FILE_VERBALE} è vuoto.")

    try:
        risultato = estrai(trascrizione)
    except anthropic.AuthenticationError:
        sys.exit("Errore: chiave API non valida o mancante (imposta ANTHROPIC_API_KEY).")
    except anthropic.RateLimitError:
        sys.exit("Errore: troppe richieste, riprova tra poco.")
    except anthropic.APIStatusError as e:
        sys.exit(f"Errore dall'API di Claude ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Errore: impossibile collegarsi all'API di Claude.")

    controlla_date(risultato)
    FILE_RISULTATO.write_text(
        json.dumps(risultato.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Scritto {FILE_RISULTATO}: {len(risultato.decisioni)} decisioni, "
          f"{len(risultato.azioni)} azioni.")


if __name__ == "__main__":
    main()
