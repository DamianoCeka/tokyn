"""Assistente clienti da terminale basato sulle FAQ del negozio.

Uso: python programma.py (dalla cartella che contiene faq.txt).
Legge un messaggio del cliente per riga dallo standard input e stampa la
risposta. Scrivere "esci" per terminare.
"""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

FILE_FAQ = "faq.txt"
COMANDO_USCITA = "esci"

ISTRUZIONI = """Sei l'assistente clienti del negozio online descritto nelle FAQ qui sotto.
Rispondi ai clienti in italiano, in modo cortese e conciso, come in una chat.

Regole:
- Usa SOLO le informazioni contenute nelle FAQ. Non inventare prezzi, tempi,
  servizi, politiche o qualsiasi altro dato che non compaia nelle FAQ.
- Se la risposta a una domanda non è nelle FAQ, dillo chiaramente (ad esempio
  "Mi dispiace, non ho questa informazione nelle nostre FAQ") e non tirare a
  indovinare. Puoi suggerire di contattare il servizio clienti, senza inventare
  recapiti.
- Puoi combinare più FAQ e fare semplici ragionamenti o calcoli sui dati delle
  FAQ (ad esempio sommare un costo di spedizione e una confezione regalo).
- Ricorda ciò che il cliente ha detto in precedenza nella conversazione (nome,
  ordine, paese, importo, ecc.) e usalo nelle risposte successive.
- Rispondi in testo semplice, senza formattazione Markdown.

<faq>
{faq}
</faq>"""


def carica_faq(percorso: Path) -> str:
    try:
        testo = percorso.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        sys.exit(f"Errore: file '{percorso}' non trovato nella cartella corrente.")
    if not testo:
        sys.exit(f"Errore: il file '{percorso}' è vuoto.")
    return testo


async def rispondi(client: ClaudeSDKClient, messaggio: str) -> str:
    await client.query(messaggio)
    parti: list[str] = []
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            parti.extend(b.text for b in msg.content if isinstance(b, TextBlock))
        elif isinstance(msg, ResultMessage) and msg.is_error:
            raise RuntimeError(msg.result or "errore sconosciuto")
    return "\n".join(p.strip() for p in parti if p.strip())


async def main() -> None:
    faq = carica_faq(Path(FILE_FAQ))
    options = ClaudeAgentOptions(
        system_prompt=ISTRUZIONI.format(faq=faq),
        tools=[],  # solo conversazione: nessuno strumento (file, shell, web)
        setting_sources=[],  # ignora CLAUDE.md e impostazioni locali
        max_turns=1,
    )

    async with ClaudeSDKClient(options=options) as client:
        while True:
            riga = await asyncio.to_thread(sys.stdin.readline)
            if not riga:  # fine dell'input
                break
            messaggio = riga.strip()
            if not messaggio:
                continue
            if messaggio.lower() == COMANDO_USCITA:
                break
            try:
                risposta = await rispondi(client, messaggio)
            except Exception as e:
                risposta = f"Mi dispiace, si è verificato un errore: {e}"
            print(risposta, flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
