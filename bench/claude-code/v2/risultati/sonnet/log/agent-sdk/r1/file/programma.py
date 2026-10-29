"""Statistiche sul log degli accessi (access.log) con commento scritto da Claude.

Uso: python programma.py   (dalla cartella che contiene access.log)
Scrive risultato.json.
"""
import asyncio
import json
import re
import sys
from collections import Counter

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

# IP, identd, utente, [gg/Mon/aaaa:HH:MM:SS fuso], "richiesta", stato, byte
RIGA = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[\d{2}/\w{3}/\d{4}:(?P<ora>\d{2}):\d{2}:\d{2} [+-]\d{4}\] '
    r'"(?P<richiesta>.*)" (?P<stato>\d{3}) (?:\d+|-)\s*$'
)


def analizza(percorso):
    per_ora, errori, ip = Counter(), Counter(), Counter()
    with open(percorso, encoding="utf-8", errors="replace") as f:
        for numero, riga in enumerate(f, 1):
            if not riga.strip():
                continue
            m = RIGA.match(riga)
            if not m:
                print(f"riga {numero} non riconosciuta, ignorata: {riga.rstrip()}", file=sys.stderr)
                continue
            per_ora[m["ora"]] += 1
            ip[m["ip"]] += 1
            if int(m["stato"]) >= 400:
                errori[m["stato"]] += 1
    # a parità di richieste, l'IP che compare prima nel log passa avanti
    # (Counter.most_common è stabile sull'ordine di inserimento)
    return {
        "richieste_per_ora": dict(sorted(per_ora.items())),
        "errori": dict(sorted(errori.items())),
        "ip_top": [i for i, _ in ip.most_common(3)],
    }


async def commento(stat):
    prompt = (
        "Queste sono le statistiche del traffico di una giornata sul nostro sito "
        "(richieste per ora, conteggio degli errori HTTP per codice, i 3 IP più attivi):\n\n"
        f"{json.dumps(stat, ensure_ascii=False, indent=1)}\n\n"
        "Scrivi in italiano un commento di esattamente due frasi sul traffico della giornata. "
        "Basati solo su questi dati. Rispondi solo con le due frasi, senza titoli né elenchi."
    )
    opzioni = ClaudeAgentOptions(tools=[], max_turns=1, setting_sources=[])
    testo, finale = [], None
    async for msg in query(prompt=prompt, options=opzioni):
        if isinstance(msg, AssistantMessage):
            testo += [b.text for b in msg.content if isinstance(b, TextBlock)]
        elif isinstance(msg, ResultMessage):
            finale = msg
    if finale is None or finale.is_error:
        raise RuntimeError(f"Claude non ha risposto: {finale}")
    risposta = " ".join("".join(testo).split())
    if not risposta:
        raise RuntimeError("Claude ha restituito un commento vuoto")
    return risposta


def main():
    stat = analizza("access.log")
    stat["commento"] = asyncio.run(commento(stat))
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(stat, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
