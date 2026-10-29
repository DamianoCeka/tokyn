import asyncio
import json
import re
import sys
from collections import Counter

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

RIGA = re.compile(r'^(\S+) \S+ \S+ \[[^:\]]+:(\d{2}):\d{2}:\d{2} [^\]]+\] "(.*)" (\d{3}) (\S+)$')


def analizza(percorso):
    per_ora, errori, ip = Counter(), Counter(), Counter()
    with open(percorso, encoding="utf-8", errors="replace") as f:
        for riga in f:
            riga = riga.rstrip("\r\n")
            if not riga.strip():
                continue
            m = RIGA.match(riga)
            if not m:
                print(f"Riga non riconosciuta: {riga}", file=sys.stderr)
                continue
            indirizzo, ora, _, stato, _ = m.groups()
            per_ora[ora] += 1
            ip[indirizzo] += 1
            if int(stato) >= 400:
                errori[stato] += 1
    return {
        "richieste_per_ora": dict(sorted(per_ora.items())),
        "errori": dict(sorted(errori.items())),
        # a parità di richieste, ordine di primo ingresso (most_common è stabile)
        "ip_top": [i for i, _ in ip.most_common(3)],
    }


async def commento(stat):
    prompt = (
        "Questi sono i dati statistici del log degli accessi del nostro sito per una giornata "
        "(richieste per ora, conteggio degli errori HTTP per codice, i 3 IP più attivi):\n"
        f"{json.dumps(stat, ensure_ascii=False)}\n\n"
        "Scrivi in italiano un commento sul traffico della giornata di esattamente due frasi. "
        "Rispondi solo con le due frasi, senza elenchi, titoli o altro testo."
    )
    opzioni = ClaudeAgentOptions(
        allowed_tools=[], max_turns=1, setting_sources=[],
        system_prompt="Sei un analista di traffico web. Scrivi in modo conciso e preciso.",
    )
    testo = ""
    async for msg in query(prompt=prompt, options=opzioni):
        if isinstance(msg, AssistantMessage):
            testo += "".join(b.text for b in msg.content if isinstance(b, TextBlock))
    testo = testo.strip()
    if not testo:
        raise RuntimeError("Claude non ha restituito alcun commento")
    return testo


def main():
    stat = analizza("access.log")
    stat["commento"] = asyncio.run(commento(stat))
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(stat, f, ensure_ascii=False, indent=2)
    print(json.dumps(stat, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
