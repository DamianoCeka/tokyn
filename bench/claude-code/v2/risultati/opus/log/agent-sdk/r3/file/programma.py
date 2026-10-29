"""Statistiche da access.log (Common Log Format) con commento scritto da Claude.

Uso: python programma.py  (dalla cartella che contiene access.log)
Scrive il risultato in risultato.json.
"""

import asyncio
import json
import re
import sys
from collections import Counter

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

FILE_LOG = "access.log"
FILE_RISULTATO = "risultato.json"

# host ident authuser [gg/Mmm/aaaa:HH:MM:SS zona] "richiesta" stato byte
RIGA_CLF = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[[^:\]]+:(?P<ora>\d{2}):\d{2}:\d{2}[^\]]*\] '
    r'"(?P<richiesta>.*)" (?P<stato>\d{3}) \S+\s*$'
)


def analizza(percorso):
    per_ora = Counter()
    errori = Counter()
    per_ip = Counter()
    scartate = 0

    with open(percorso, encoding="utf-8", errors="replace") as f:
        for riga in f:
            if not riga.strip():
                continue
            m = RIGA_CLF.match(riga)
            if not m:
                scartate += 1
                continue
            per_ora[m["ora"]] += 1
            per_ip[m["ip"]] += 1
            stato = int(m["stato"])
            if stato >= 400:
                errori[str(stato)] += 1

    if scartate:
        print(f"Attenzione: {scartate} righe non riconosciute e ignorate.", file=sys.stderr)

    return {
        "richieste_per_ora": dict(sorted(per_ora.items())),
        "errori": dict(sorted(errori.items())),
        # a parità di richieste vince l'IP comparso prima nel log
        "ip_top": [ip for ip, _ in per_ip.most_common(3)],
    }, sum(per_ora.values())


async def scrivi_commento(statistiche, totale):
    prompt = (
        "Questi sono i dati di una giornata di traffico di un sito web, ricavati dal log degli accessi.\n"
        f"Richieste totali: {totale}\n"
        f"Richieste per ora: {json.dumps(statistiche['richieste_per_ora'])}\n"
        f"Richieste con codice di errore (>= 400): {json.dumps(statistiche['errori'])}\n"
        f"I 3 IP più attivi: {json.dumps(statistiche['ip_top'])}\n\n"
        "Scrivi un commento sul traffico della giornata in italiano, di esattamente due frasi. "
        "Rispondi solo con le due frasi, senza titoli, elenchi o formattazione."
    )
    options = ClaudeAgentOptions(
        system_prompt="Sei un analista web che commenta in modo sintetico i dati di traffico.",
        tools=[],
        max_turns=1,
        setting_sources=[],
    )
    parti = []
    async for messaggio in query(prompt=prompt, options=options):
        if isinstance(messaggio, AssistantMessage):
            parti.extend(b.text for b in messaggio.content if isinstance(b, TextBlock))
    commento = " ".join(" ".join(parti).split())
    if not commento:
        raise RuntimeError("Claude non ha restituito alcun commento.")
    return commento


def main():
    try:
        statistiche, totale = analizza(FILE_LOG)
    except FileNotFoundError:
        sys.exit(f"File {FILE_LOG} non trovato nella cartella corrente.")

    statistiche["commento"] = asyncio.run(scrivi_commento(statistiche, totale))

    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(statistiche, f, ensure_ascii=False, indent=2)
    print(f"Risultato scritto in {FILE_RISULTATO}.")


if __name__ == "__main__":
    main()
