"""Ricava decisioni e azioni dal verbale della riunione (verbale.txt) e le scrive in risultato.json."""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

VERBALE = Path("verbale.txt")
RISULTATO = Path("risultato.json")

SCHEMA = {
    "type": "object",
    "properties": {
        "decisioni": {"type": "array", "items": {"type": "string"}},
        "azioni": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cosa": {"type": "string"},
                    "chi": {"type": ["string", "null"]},
                    "entro": {"type": ["string", "null"]},
                },
                "required": ["cosa", "chi", "entro"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["decisioni", "azioni"],
    "additionalProperties": False,
}

ISTRUZIONI = """Sei l'assistente di un team che verbalizza le proprie riunioni. Leggi la trascrizione e ricava:

- "decisioni": le decisioni effettivamente prese dal gruppo, ciascuna in una frase breve in italiano. Escludi proposte \
non approvate, opinioni e chiacchiere non legate all'ordine del giorno.
- "azioni": i compiti assegnati a una persona. Per ciascuno:
  - "cosa": che cosa va fatto, in una frase breve che inizia con un verbo all'infinito;
  - "chi": il nome della persona che se ne occupa, così come compare nella trascrizione;
  - "entro": la scadenza nel formato AAAA-MM-GG. Se la scadenza è relativa ("venerdì", "fra due settimane"), \
calcolala rispetto alla data della riunione indicata nella trascrizione (o, se manca, rispetto alla data di oggi: {oggi}).

Se per un'azione non è indicato chi se ne occupa o non è indicata alcuna scadenza, usa null: non inventare."""


async def estrai(testo: str) -> dict:
    options = ClaudeAgentOptions(
        model="claude-opus-5-5",
        system_prompt=ISTRUZIONI.format(oggi=date.today().isoformat()),
        tools=[],  # basta leggere il testo: nessuno strumento
        setting_sources=[],  # non caricare impostazioni o CLAUDE.md locali
        output_format={"type": "json_schema", "schema": SCHEMA},
        max_turns=3,
    )
    prompt = f"Ecco la trascrizione della riunione:\n\n<trascrizione>\n{testo}\n</trascrizione>"

    risultato = None
    async for messaggio in query(prompt=prompt, options=options):
        if isinstance(messaggio, ResultMessage):
            risultato = messaggio
    if risultato is None or risultato.is_error or risultato.structured_output is None:
        dettagli = risultato and (risultato.errors or risultato.result or risultato.subtype)
        raise RuntimeError(f"Claude non ha restituito un risultato valido: {dettagli}")
    return risultato.structured_output


def controlla(dati: dict) -> list[str]:
    """Restituisce gli avvisi sulle azioni senza responsabile o con scadenza mancante o non valida."""
    avvisi = []
    for azione in dati["azioni"]:
        if not azione["chi"]:
            avvisi.append(f"Nessun responsabile per: {azione['cosa']}")
        if not azione["entro"]:
            avvisi.append(f"Nessuna scadenza per: {azione['cosa']}")
            continue
        try:
            date.fromisoformat(azione["entro"])
        except ValueError:
            avvisi.append(f"Scadenza non valida ({azione['entro']}) per: {azione['cosa']}")
    return avvisi


def main() -> None:
    if not VERBALE.exists():
        sys.exit(f"File {VERBALE} non trovato nella cartella corrente.")
    testo = VERBALE.read_text(encoding="utf-8").strip()
    if not testo:
        sys.exit(f"Il file {VERBALE} è vuoto.")

    dati = asyncio.run(estrai(testo))
    RISULTATO.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Scritto {RISULTATO}: {len(dati['decisioni'])} decisioni, {len(dati['azioni'])} azioni.")
    for avviso in controlla(dati):
        print(f"Attenzione: {avviso}")


if __name__ == "__main__":
    main()
