"""Ricava decisioni e azioni da verbale.txt usando Claude e le scrive in risultato.json.

Uso: python programma.py  (dalla cartella che contiene verbale.txt)
Richiede il pacchetto `anthropic` e una chiave API (variabile ANTHROPIC_API_KEY).
"""

import datetime
import json
import sys
from pathlib import Path
from typing import List, Optional

import anthropic
from pydantic import BaseModel, ValidationError

FILE_VERBALE = Path("verbale.txt")
FILE_RISULTATO = Path("risultato.json")
MODELLO = "claude-opus-5-5"

ISTRUZIONI = """Ti do la trascrizione di una riunione di lavoro. Estrai:

- decisioni: le decisioni effettivamente prese dal gruppo, ciascuna come frase breve in italiano \
(es. "Il nuovo sito va online a gennaio"). Non includere proposte rimaste in sospeso, opinioni \
o chiacchiere non legate al lavoro.
- azioni: i compiti assegnati a una persona. Per ognuno:
  - cosa: che cosa va fatto, frase breve all'infinito (es. "Preparare il preventivo per il nuovo server");
  - chi: il nome della persona che se ne occupa, come compare nella trascrizione;
  - entro: la scadenza nel formato AAAA-MM-GG. Se la scadenza è relativa ("venerdì prossimo", \
"tra due settimane") calcolala a partire dalla data della riunione indicata nella trascrizione \
(o, se manca, da oggi: {oggi}). Se per un compito non viene detta nessuna scadenza, usa null: \
non inventarla.

Trascrizione:
<verbale>
{verbale}
</verbale>"""


class Azione(BaseModel):
    cosa: str
    chi: str
    entro: Optional[str]


class Risultato(BaseModel):
    decisioni: List[str]
    azioni: List[Azione]


def data_valida(testo):
    try:
        datetime.date.fromisoformat(testo)
        return len(testo) == 10
    except ValueError:
        return False


def main():
    if not FILE_VERBALE.exists():
        sys.exit(f"Non trovo {FILE_VERBALE} nella cartella corrente.")
    verbale = FILE_VERBALE.read_text(encoding="utf-8").strip()
    if not verbale:
        sys.exit(f"{FILE_VERBALE} è vuoto.")

    client = anthropic.Anthropic()
    prompt = ISTRUZIONI.format(oggi=datetime.date.today().isoformat(), verbale=verbale)
    try:
        risposta = client.beta.messages.parse(
            model=MODELLO,
            max_tokens=16000,
            output_config={"effort": "medium"},
            # Se il modello rifiuta la richiesta, l'API la ripete su un modello di riserva.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
            output_format=Risultato,
        )
    except (anthropic.AuthenticationError, TypeError):
        # TypeError: l'SDK non trova nessuna credenziale e non invia nemmeno la richiesta.
        sys.exit("Chiave API mancante o non valida: imposta la variabile ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        sys.exit("Troppe richieste a Claude in questo momento: riprova tra qualche minuto.")
    except anthropic.APIStatusError as e:
        sys.exit(f"Errore dall'API di Claude ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Impossibile collegarsi a Claude: controlla la connessione a internet.")
    except ValidationError:
        sys.exit("La risposta di Claude non ha il formato atteso: riprova.")

    if risposta.stop_reason == "refusal":
        sys.exit("Claude si è rifiutato di elaborare questo verbale.")
    if risposta.stop_reason == "max_tokens" or risposta.parsed_output is None:
        sys.exit("La risposta di Claude è incompleta: riprova.")

    risultato = risposta.parsed_output
    for azione in risultato.azioni:
        if azione.entro is not None and not data_valida(azione.entro):
            print(f"Attenzione: scadenza non valida per \"{azione.cosa}\": {azione.entro}")
            azione.entro = None

    FILE_RISULTATO.write_text(
        json.dumps(risultato.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Scritto {FILE_RISULTATO}: {len(risultato.decisioni)} decisioni, {len(risultato.azioni)} azioni.")
    for azione in risultato.azioni:
        if azione.entro is None:
            print(f"Nota: scadenza da verificare a mano per \"{azione.cosa}\" ({azione.chi}).")


if __name__ == "__main__":
    main()
