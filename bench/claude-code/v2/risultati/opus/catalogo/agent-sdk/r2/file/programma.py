"""Traduce in inglese le descrizioni di catalogo.csv e scrive catalogo_en.csv.

Uso: python programma.py   (dalla cartella che contiene catalogo.csv)
"""

import asyncio
import csv
import json
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

INPUT = Path("catalogo.csv")
OUTPUT = Path("catalogo_en.csv")
SEPARATORE = ";"
COLONNA = "descrizione"
LOTTO = 25          # descrizioni tradotte per singola richiesta
TENTATIVI = 3
MODELLO = "claude-opus-5-5"

ISTRUZIONI = (
    "Sei un traduttore professionista per un negozio online. Traduci dall'italiano "
    "all'inglese le descrizioni di prodotto che ricevi. Scrivi un inglese naturale da "
    "e-commerce, conciso, fedele al significato: non aggiungere né togliere "
    "informazioni, mantieni numeri e unità di misura così come sono (es. '28 cm', "
    "'120 x 180 cm'). Restituisci solo le traduzioni, una per ogni id ricevuto."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "traduzioni": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "inglese": {"type": "string"},
                },
                "required": ["id", "inglese"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["traduzioni"],
    "additionalProperties": False,
}


async def traduci_lotto(descrizioni: dict[int, str]) -> dict[int, str]:
    """Traduce un gruppo di descrizioni {id: testo} e restituisce {id: traduzione}."""
    options = ClaudeAgentOptions(
        model=MODELLO,
        system_prompt=ISTRUZIONI,
        tools=[],               # nessuno strumento: serve solo la traduzione
        setting_sources=[],     # ignora configurazioni locali di Claude Code
        output_format={"type": "json_schema", "schema": SCHEMA},
        max_turns=3,
    )
    prompt = "Descrizioni da tradurre (JSON id -> testo):\n" + json.dumps(
        {str(i): t for i, t in descrizioni.items()}, ensure_ascii=False, indent=2
    )

    risultato = None
    async for messaggio in query(prompt=prompt, options=options):
        if isinstance(messaggio, ResultMessage):
            risultato = messaggio
    if risultato is None or risultato.is_error or risultato.structured_output is None:
        dettaglio = risultato and (risultato.errors or risultato.subtype)
        raise RuntimeError(f"risposta non valida da Claude: {dettaglio}")

    tradotte = {
        int(t["id"]): " ".join(t["inglese"].split())  # sempre su una sola riga
        for t in risultato.structured_output["traduzioni"]
    }
    mancanti = set(descrizioni) - set(tradotte)
    if mancanti or any(not tradotte[i] for i in descrizioni):
        raise RuntimeError(f"traduzioni mancanti o vuote per le righe {sorted(mancanti)}")
    return {i: tradotte[i] for i in descrizioni}


async def traduci_con_tentativi(descrizioni: dict[int, str]) -> dict[int, str]:
    for tentativo in range(1, TENTATIVI + 1):
        try:
            return await traduci_lotto(descrizioni)
        except Exception as errore:
            if tentativo == TENTATIVI:
                raise
            print(f"  tentativo {tentativo} fallito ({errore}), riprovo...", file=sys.stderr)
            await asyncio.sleep(2 * tentativo)


def campi_grezzi(riga: str) -> list[str]:
    """Divide una riga nei suoi campi così come sono scritti (virgolette comprese)."""
    campi, inizio, tra_virgolette = [], 0, False
    for pos, carattere in enumerate(riga):
        if carattere == '"':
            tra_virgolette = not tra_virgolette
        elif carattere == SEPARATORE and not tra_virgolette:
            campi.append(riga[inizio:pos])
            inizio = pos + 1
    campi.append(riga[inizio:])
    return campi


def valore(campo: str) -> str:
    """Valore di un campo grezzo, senza virgolette di protezione."""
    return next(csv.reader([campo], delimiter=SEPARATORE), [""])[0] if campo else ""


def codifica(testo: str) -> str:
    """Scrive un valore come campo CSV, tra virgolette solo se serve."""
    if any(c in testo for c in (SEPARATORE, '"', "\n", "\r")):
        return '"' + testo.replace('"', '""') + '"'
    return testo


async def main() -> None:
    if not INPUT.exists():
        sys.exit(f"File {INPUT} non trovato nella cartella corrente.")

    # Le righe vengono lette come testo e si sostituisce solo il campo descrizione:
    # così intestazione, codice, nome, prezzo e fine riga restano identici byte per byte.
    with INPUT.open(encoding="utf-8", newline="") as f:
        righe = f.read().splitlines(keepends=True)
    if not righe:
        sys.exit(f"{INPUT} è vuoto.")

    intestazione = [valore(c).lstrip("﻿") for c in campi_grezzi(righe[0].rstrip("\r\n"))]
    if COLONNA not in intestazione:
        sys.exit(f"Colonna '{COLONNA}' non trovata nell'intestazione: {intestazione}")
    col = intestazione.index(COLONNA)

    # Solo le righe di prodotto con una descrizione non vuota vanno tradotte.
    prodotti = righe[1:]
    da_tradurre = {}
    for i, riga in enumerate(prodotti):
        campi = campi_grezzi(riga.rstrip("\r\n"))
        if len(campi) > col and valore(campi[col]).strip():
            da_tradurre[i] = valore(campi[col])
    ids = list(da_tradurre)
    print(f"{len(prodotti)} prodotti, {len(ids)} descrizioni da tradurre.")

    for inizio in range(0, len(ids), LOTTO):
        lotto = {i: da_tradurre[i] for i in ids[inizio:inizio + LOTTO]}
        print(f"Traduzione righe {inizio + 1}-{inizio + len(lotto)}...")
        for i, inglese in (await traduci_con_tentativi(lotto)).items():
            contenuto = prodotti[i].rstrip("\r\n")
            fine = prodotti[i][len(contenuto):]
            campi = campi_grezzi(contenuto)
            campi[col] = codifica(inglese)
            prodotti[i] = SEPARATORE.join(campi) + fine

    OUTPUT.write_text(righe[0] + "".join(prodotti), encoding="utf-8", newline="")
    print(f"Scritto {OUTPUT}.")


if __name__ == "__main__":
    asyncio.run(main())
