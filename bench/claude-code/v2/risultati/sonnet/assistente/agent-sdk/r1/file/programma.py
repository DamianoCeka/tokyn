"""Assistente clienti da terminale: risponde usando solo le FAQ in faq.txt.

Avvio: python programma.py   (dalla cartella che contiene faq.txt)
Ogni riga letta da stdin è un messaggio del cliente; "esci" termina il programma.
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

FAQ_PATH = Path("faq.txt")

SYSTEM_PROMPT = """\
Sei l'assistente clienti di un negozio online. Rispondi in italiano, in modo \
cortese e breve.

Rispondi SOLO con le informazioni contenute nelle FAQ qui sotto. Non usare \
conoscenze esterne e non inventare prezzi, tempi, politiche o altri dettagli. \
Se la risposta alla domanda del cliente non è nelle FAQ, dillo chiaramente \
(ad esempio: "Non ho questa informazione nelle FAQ del negozio") e, se \
opportuno, suggerisci di contattare direttamente il negozio. Se la FAQ copre \
solo una parte della domanda, rispondi alla parte coperta e dì che il resto \
non è indicato.

Ricorda quello che il cliente ha detto in precedenza nella conversazione \
(nome, paese, ordine, preferenze) e usalo per rispondere alle domande \
successive, sempre nei limiti delle FAQ.

FAQ DEL NEGOZIO:
{faq}
"""


async def rispondi(client: ClaudeSDKClient, messaggio: str) -> str:
    await client.query(messaggio)
    testo = []
    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage):
            testo.extend(b.text for b in msg.content if isinstance(b, TextBlock))
        elif isinstance(msg, ResultMessage) and msg.is_error:
            raise RuntimeError(msg.result or "errore sconosciuto")
    return "".join(testo).strip()


async def main() -> int:
    try:
        faq = FAQ_PATH.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Impossibile leggere {FAQ_PATH}: {e}", file=sys.stderr)
        return 1

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT.format(faq=faq),
        tools=[],  # nessuno strumento: solo risposte testuali
        setting_sources=[],  # ignora CLAUDE.md e impostazioni locali
        max_turns=1,
    )

    async with ClaudeSDKClient(options=options) as client:
        # Un solo client per tutta la sessione: la conversazione resta in memoria.
        for riga in sys.stdin:
            messaggio = riga.strip()
            if not messaggio:
                continue
            if messaggio.lower() == "esci":
                break
            try:
                print(await rispondi(client, messaggio), flush=True)
            except Exception as e:
                print(f"[Errore: {e}]", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
