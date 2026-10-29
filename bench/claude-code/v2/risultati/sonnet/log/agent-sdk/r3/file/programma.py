import json
import re
import sys
from collections import Counter

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

LOG = "access.log"
OUT = "risultato.json"

# IP ident utente [gg/Mes/aaaa:HH:MM:SS fuso] "richiesta" stato byte
RIGA = re.compile(
    r'^(\S+) \S+ \S+ \[[^:\]]+:(\d{2}):\d{2}:\d{2} [^\]]+\] "[^"]*" (\d{3}) \S+\s*$'
)


def analizza(percorso):
    per_ora = Counter()
    errori = Counter()
    per_ip = Counter()
    for n, riga in enumerate(open(percorso, encoding="utf-8", errors="replace"), 1):
        if not riga.strip():
            continue
        m = RIGA.match(riga)
        if not m:
            print(f"riga {n} non riconosciuta, ignorata: {riga.strip()!r}", file=sys.stderr)
            continue
        ip, ora, stato = m.groups()
        per_ora[ora] += 1
        per_ip[ip] += 1
        if int(stato) >= 400:
            errori[stato] += 1
    return {
        "richieste_per_ora": dict(sorted(per_ora.items())),
        "errori": dict(sorted(errori.items())),
        "ip_top": [ip for ip, _ in per_ip.most_common(3)],
    }


async def commento(statistiche):
    prompt = (
        "Questi sono i dati statistici del log degli accessi del nostro sito per una giornata "
        "(richieste per ora, errori HTTP per codice di stato, tre IP più attivi):\n\n"
        + json.dumps(statistiche, ensure_ascii=False, indent=1)
        + "\n\nScrivi in italiano un commento sul traffico della giornata di esattamente due frasi. "
        "Rispondi solo con le due frasi, senza elenchi, titoli o formattazione."
    )
    opzioni = ClaudeAgentOptions(
        system_prompt="Sei un analista che commenta il traffico di un sito web in modo sintetico e preciso.",
        allowed_tools=[],
        tools=[],
        max_turns=1,
        setting_sources=[],
    )
    testo = []
    async for msg in query(prompt=prompt, options=opzioni):
        if isinstance(msg, AssistantMessage):
            testo += [b.text for b in msg.content if isinstance(b, TextBlock)]
        elif isinstance(msg, ResultMessage) and msg.is_error:
            raise RuntimeError(f"Claude ha restituito un errore: {msg.result}")
    risposta = " ".join("".join(testo).split())
    if not risposta:
        raise RuntimeError("Claude non ha restituito alcun commento")
    return risposta


def main():
    risultato = analizza(LOG)
    risultato["commento"] = anyio.run(commento, {k: v for k, v in risultato.items()})
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Scritto {OUT}")


if __name__ == "__main__":
    main()
