"""Ricava decisioni e azioni dal verbale di una riunione usando Claude.

Uso: python programma.py   (dalla cartella che contiene verbale.txt)
Scrive il risultato in risultato.json.
"""

import datetime
import json
import sys
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

FILE_VERBALE = Path("verbale.txt")
FILE_RISULTATO = Path("risultato.json")
MODELLO = "claude-opus-5-5"

ISTRUZIONI = """Ricevi la trascrizione di una riunione di team. Estrai:

1. "decisioni": le decisioni effettivamente prese durante la riunione, ognuna come una frase breve e \
autonoma in italiano. Non includere proposte rimaste in sospeso, opinioni o chiacchiere non \
pertinenti (ad esempio domande personali o fuori tema).

2. "azioni": i compiti assegnati a una persona. Per ognuno:
   - "cosa": che cosa va fatto, in una frase breve che inizia con un verbo all'infinito;
   - "chi": il nome della persona che se ne occupa, così come compare nella trascrizione;
   - "entro": la scadenza nel formato AAAA-MM-GG. Se la scadenza è espressa in modo relativo \
("venerdì prossimo", "tra due settimane"), calcolala rispetto alla data della riunione indicata \
nella trascrizione; se la trascrizione non riporta la data, usa la data di riferimento fornita. \
Se per un compito non viene detta nessuna scadenza, usa null: non inventarla.

Riporta solo ciò che risulta dalla trascrizione."""


class Azione(BaseModel):
    cosa: str
    chi: str
    entro: str | None = Field(description="Scadenza nel formato AAAA-MM-GG, oppure null se non indicata")


class Risultato(BaseModel):
    decisioni: list[str]
    azioni: list[Azione]


def estrai(trascrizione: str) -> Risultato:
    client = anthropic.Anthropic()
    oggi = datetime.date.today().isoformat()
    risposta = client.messages.parse(
        model=MODELLO,
        max_tokens=16000,
        system=ISTRUZIONI,
        messages=[{
            "role": "user",
            "content": f"Data di riferimento: {oggi}\n\n<trascrizione>\n{trascrizione}\n</trascrizione>",
        }],
        output_format=Risultato,
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato di elaborare la trascrizione.")
    if risposta.stop_reason == "max_tokens":
        raise RuntimeError("La risposta di Claude è stata troncata (max_tokens raggiunto).")
    return risposta.parsed_output


def controlla_date(risultato: Risultato) -> None:
    for azione in risultato.azioni:
        if azione.entro is None:
            print(f"Attenzione: nessuna scadenza indicata per «{azione.cosa}» ({azione.chi}).", file=sys.stderr)
            continue
        try:
            datetime.date.fromisoformat(azione.entro)
        except ValueError:
            raise RuntimeError(f"Scadenza non valida per «{azione.cosa}»: {azione.entro!r}")


def main() -> int:
    if not FILE_VERBALE.exists():
        print(f"Errore: non trovo {FILE_VERBALE} nella cartella corrente.", file=sys.stderr)
        return 1
    trascrizione = FILE_VERBALE.read_text(encoding="utf-8").strip()
    if not trascrizione:
        print(f"Errore: {FILE_VERBALE} è vuoto.", file=sys.stderr)
        return 1

    try:
        risultato = estrai(trascrizione)
        controlla_date(risultato)
    except (anthropic.AuthenticationError, TypeError):
        # TypeError: l'SDK non trova nessuna credenziale configurata
        print("Errore: credenziali Anthropic mancanti o non valide (imposta ANTHROPIC_API_KEY).", file=sys.stderr)
        return 1
    except anthropic.RateLimitError:
        print("Errore: troppe richieste all'API, riprova tra poco.", file=sys.stderr)
        return 1
    except anthropic.APIStatusError as e:
        print(f"Errore dall'API ({e.status_code}): {e.message}", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError:
        print("Errore: impossibile collegarsi all'API Anthropic.", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"Errore: {e}", file=sys.stderr)
        return 1

    FILE_RISULTATO.write_text(
        json.dumps(risultato.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Fatto: {len(risultato.decisioni)} decisioni e {len(risultato.azioni)} azioni scritte in {FILE_RISULTATO}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
