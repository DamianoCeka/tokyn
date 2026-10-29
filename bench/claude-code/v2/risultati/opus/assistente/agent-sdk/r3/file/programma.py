"""Assistente clienti da terminale che risponde usando le FAQ in faq.txt.

Uso: python programma.py  (dalla cartella che contiene faq.txt)
Ogni riga letta da stdin è un messaggio del cliente; "esci" termina.
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

MODELLO = "claude-opus-5-5"

ISTRUZIONI = """Sei l'assistente clienti del negozio online descritto nelle FAQ qui sotto.
Rispondi in italiano, in modo cortese e breve, al messaggio del cliente.

Regole:
- Usa SOLO le informazioni contenute nelle FAQ. Non inventare prezzi, tempi, \
politiche o altri dettagli che non ci sono.
- Se la risposta alla domanda non è nelle FAQ, dillo chiaramente (ad esempio \
"Mi dispiace, questa informazione non è presente nelle nostre FAQ") e non provare a indovinare.
- Puoi combinare più FAQ e fare semplici calcoli sui dati presenti (ad esempio \
sommare il costo della spedizione e della confezione regalo).
- Ricorda quello che il cliente ti ha detto in precedenza nella conversazione \
(nome, ordine, paese, ecc.) e usalo nelle risposte successive.
- Rispondi con testo semplice, senza formattazione Markdown.

<faq>
{faq}
</faq>"""


def leggi_faq(percorso: Path) -> str:
    try:
        return percorso.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        sys.exit(f"Errore: file {percorso} non trovato. Avvia il programma dalla cartella che contiene faq.txt.")


async def rispondi(client: ClaudeSDKClient, messaggio: str) -> str:
    await client.query(messaggio)
    parti: list[str] = []
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            parti.extend(b.text for b in msg.content if isinstance(b, TextBlock))
        elif isinstance(msg, ResultMessage) and msg.is_error:
            return "Mi dispiace, si è verificato un errore tecnico. Riprova tra poco."
    return "\n".join(p.strip() for p in parti if p.strip())


async def main() -> None:
    faq = leggi_faq(Path("faq.txt"))
    opzioni = ClaudeAgentOptions(
        model=MODELLO,
        system_prompt=ISTRUZIONI.format(faq=faq),
        tools=[],  # nessuno strumento: l'assistente risponde solo dalle FAQ
        setting_sources=[],  # ignora impostazioni e CLAUDE.md della macchina
        effort="low",
    )
    async with ClaudeSDKClient(options=opzioni) as client:
        for riga in sys.stdin:
            messaggio = riga.strip()
            if not messaggio:
                continue
            if messaggio.lower() == "esci":
                break
            print(await rispondi(client, messaggio), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
