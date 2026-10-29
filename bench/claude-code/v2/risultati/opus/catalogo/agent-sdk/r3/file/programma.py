"""Traduce in inglese le descrizioni di catalogo.csv e scrive catalogo_en.csv.

Uso: python programma.py  (dalla cartella che contiene catalogo.csv)
"""

import asyncio
import csv
import sys

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

FILE_INGRESSO = "catalogo.csv"
FILE_USCITA = "catalogo_en.csv"
SEPARATORE = ";"
COLONNA_DESCRIZIONE = "descrizione"
TRADUZIONI_IN_PARALLELO = 4
TENTATIVI = 3

ISTRUZIONI = (
    "You translate Italian product descriptions for an online shop into English. "
    "Reply with the English translation only: one line, no quotes, no notes, no preamble. "
    "Keep the tone of e-commerce copy, keep numbers and units as they are "
    "(for example '28 cm', '120 x 180 cm'), and do not add or drop information."
)

OPZIONI = ClaudeAgentOptions(
    model="claude-opus-5-5",
    system_prompt=ISTRUZIONI,
    tools=[],  # nessuno strumento: serve solo il testo della traduzione
    max_turns=1,
    setting_sources=[],  # non caricare impostazioni o CLAUDE.md dalla cartella
    effort="low",
)


async def traduci(descrizione: str) -> str:
    """Chiede a Claude la traduzione inglese di una singola descrizione."""
    testo = []
    risultato = None
    async for messaggio in query(prompt=descrizione, options=OPZIONI):
        if isinstance(messaggio, AssistantMessage):
            testo.extend(b.text for b in messaggio.content if isinstance(b, TextBlock))
        elif isinstance(messaggio, ResultMessage):
            risultato = messaggio
    if risultato is None or risultato.is_error:
        motivo = risultato.result if risultato else "nessuna risposta"
        raise RuntimeError(f"traduzione non riuscita: {motivo}")
    # Una descrizione deve restare su una sola riga del CSV.
    traduzione = " ".join("".join(testo).split())
    if not traduzione:
        raise RuntimeError("traduzione vuota")
    return traduzione


async def traduci_con_tentativi(descrizione: str, limite: asyncio.Semaphore) -> str:
    if not descrizione.strip():
        return descrizione
    async with limite:
        for tentativo in range(1, TENTATIVI + 1):
            try:
                return await traduci(descrizione)
            except Exception as errore:
                if tentativo == TENTATIVI:
                    raise RuntimeError(f"{descrizione!r}: {errore}") from errore
                await asyncio.sleep(2 * tentativo)


async def main() -> int:
    with open(FILE_INGRESSO, encoding="utf-8-sig", newline="") as f:
        righe = list(csv.reader(f, delimiter=SEPARATORE))
    if not righe:
        print(f"{FILE_INGRESSO} è vuoto", file=sys.stderr)
        return 1

    intestazione, prodotti = righe[0], righe[1:]
    if COLONNA_DESCRIZIONE not in intestazione:
        print(f"Colonna '{COLONNA_DESCRIZIONE}' non trovata in {FILE_INGRESSO}", file=sys.stderr)
        return 1
    indice = intestazione.index(COLONNA_DESCRIZIONE)

    limite = asyncio.Semaphore(TRADUZIONI_IN_PARALLELO)
    descrizioni = [r[indice] if len(r) > indice else "" for r in prodotti]
    try:
        traduzioni = await asyncio.gather(
            *(traduci_con_tentativi(d, limite) for d in descrizioni)
        )
    except RuntimeError as errore:
        print(f"Errore: {errore}", file=sys.stderr)
        return 1

    with open(FILE_USCITA, "w", encoding="utf-8", newline="") as f:
        scrittore = csv.writer(f, delimiter=SEPARATORE, lineterminator="\n")
        scrittore.writerow(intestazione)
        for riga, traduzione in zip(prodotti, traduzioni):
            nuova = list(riga)
            if len(nuova) > indice:
                nuova[indice] = traduzione
            scrittore.writerow(nuova)

    print(f"Scritto {FILE_USCITA}: {len(prodotti)} prodotti tradotti.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
