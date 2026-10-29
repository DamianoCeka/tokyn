"""Ricava decisioni e azioni da verbale.txt e le scrive in risultato.json.

Uso: python programma.py  (dalla cartella che contiene verbale.txt)
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

FILE_VERBALE = Path("verbale.txt")
FILE_RISULTATO = Path("risultato.json")

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
                    "chi": {"type": "string"},
                    "entro": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                },
                "required": ["cosa", "chi", "entro"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["decisioni", "azioni"],
    "additionalProperties": False,
}

ISTRUZIONI = """Ricevi la trascrizione di una riunione di team. Estrai:

- "decisioni": le decisioni effettivamente prese durante la riunione, ognuna come frase breve \
in italiano (es. "Il nuovo sito va online a gennaio"). Non includere proposte rimaste in sospeso, \
opinioni, domande o chiacchiere non legate alle decisioni.
- "azioni": i compiti assegnati a una persona. Per ciascuno: "cosa" (che cosa va fatto, frase \
breve all'infinito), "chi" (il nome della persona incaricata, solo il nome come compare nella \
trascrizione), "entro" (la scadenza nel formato AAAA-MM-GG).

Per le scadenze espresse in modo relativo ("venerdì", "la prossima settimana") calcola la data \
a partire dalla data della riunione indicata nella trascrizione; se la trascrizione non riporta \
una data, usa come riferimento la data di oggi: {oggi}. Includi solo azioni con una persona \
incaricata e una scadenza ricavabili dalla trascrizione.

Trascrizione:
<verbale>
{verbale}
</verbale>"""


def controlla(dati):
    """Verifica che il risultato abbia la forma attesa; solleva ValueError altrimenti."""
    if not isinstance(dati, dict):
        raise ValueError("il risultato non è un oggetto JSON")
    if not isinstance(dati.get("decisioni"), list) or not isinstance(dati.get("azioni"), list):
        raise ValueError("mancano 'decisioni' o 'azioni'")
    if not all(isinstance(d, str) and d.strip() for d in dati["decisioni"]):
        raise ValueError("'decisioni' deve essere una lista di frasi")
    for azione in dati["azioni"]:
        for campo in ("cosa", "chi", "entro"):
            if not isinstance(azione.get(campo), str) or not azione[campo].strip():
                raise ValueError(f"azione senza '{campo}': {azione}")
        date.fromisoformat(azione["entro"])  # ValueError se la data non è valida
    return {
        "decisioni": dati["decisioni"],
        "azioni": [{k: a[k] for k in ("cosa", "chi", "entro")} for a in dati["azioni"]],
    }


async def estrai(verbale):
    opzioni = ClaudeAgentOptions(
        model="claude-opus-5-5",
        tools=[],  # basta il testo del verbale: nessuno strumento necessario
        max_turns=3,
        output_format={"type": "json_schema", "schema": SCHEMA},
        setting_sources=[],
    )
    prompt = ISTRUZIONI.format(oggi=date.today().isoformat(), verbale=verbale)
    risultato = None
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            risultato = messaggio
    if risultato is None or risultato.is_error or risultato.structured_output is None:
        dettagli = risultato and (risultato.errors or risultato.result or risultato.subtype)
        raise RuntimeError(f"Claude non ha restituito un risultato valido: {dettagli}")
    return risultato.structured_output


def main():
    if not FILE_VERBALE.exists():
        sys.exit(f"Errore: {FILE_VERBALE} non trovato nella cartella corrente.")
    verbale = FILE_VERBALE.read_text(encoding="utf-8").strip()
    if not verbale:
        sys.exit(f"Errore: {FILE_VERBALE} è vuoto.")

    try:
        dati = controlla(asyncio.run(estrai(verbale)))
    except (RuntimeError, ValueError) as errore:
        sys.exit(f"Errore: {errore}")

    FILE_RISULTATO.write_text(
        json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Scritto {FILE_RISULTATO}: {len(dati['decisioni'])} decisioni, "
          f"{len(dati['azioni'])} azioni.")


if __name__ == "__main__":
    main()
