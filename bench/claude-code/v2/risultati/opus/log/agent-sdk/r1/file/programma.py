"""Statistiche giornaliere da access.log (Common Log Format) con commento scritto da Claude.

Uso: python programma.py   (dalla cartella che contiene access.log)
Scrive il risultato in risultato.json.
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

FILE_LOG = "access.log"
FILE_RISULTATO = "risultato.json"

# Ora nel timestamp, es. [08/Oct/2026:09:15:02 +0200] -> "09"
RE_ORA = re.compile(r"\[[^\]:]*:(\d{2}):\d{2}:\d{2}")
# Codice di stato: il campo dopo la richiesta tra virgolette, es. "GET / HTTP/1.1" 404 -
RE_STATO = re.compile(r'"\s+(\d{3})\s+\S+\s*$')


def analizza(percorso):
    ore = Counter()
    errori = Counter()
    ip = Counter()
    totale = 0
    with open(percorso, encoding="utf-8", errors="replace") as f:
        for riga in f:
            riga = riga.strip()
            if not riga:
                continue
            totale += 1
            ip[riga.split()[0]] += 1
            m = RE_ORA.search(riga)
            if m:
                ore[m.group(1)] += 1
            m = RE_STATO.search(riga)
            if m and int(m.group(1)) >= 400:
                errori[m.group(1)] += 1
    return {
        "totale": totale,
        "richieste_per_ora": dict(sorted(ore.items())),
        "errori": dict(sorted(errori.items())),
        "ip_top": [indirizzo for indirizzo, _ in ip.most_common(3)],
        "richieste_ip_top": ip.most_common(3),
    }


async def scrivi_commento(stats):
    prompt = (
        "Questi sono i dati sul traffico di una giornata del nostro sito web, ricavati dal log di accesso.\n"
        f"Richieste totali: {stats['totale']}\n"
        f"Richieste per ora (ora: numero): {json.dumps(stats['richieste_per_ora'])}\n"
        f"Richieste con codice di errore (codice: numero): {json.dumps(stats['errori'])}\n"
        f"IP con più richieste (ip, numero): {json.dumps(stats['richieste_ip_top'])}\n\n"
        "Scrivi un breve commento sul traffico della giornata in italiano, esattamente due frasi, "
        "basandoti solo su questi dati. Rispondi solo con le due frasi, in testo semplice, "
        "senza titoli, elenchi, markdown o virgolette."
    )
    opzioni = ClaudeAgentOptions(
        tools=[],
        max_turns=1,
        system_prompt="Sei un analista che commenta in modo conciso il traffico di un sito web.",
        setting_sources=[],
    )
    testo_risultato = None
    parti = []
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, AssistantMessage):
            parti.extend(b.text for b in messaggio.content if isinstance(b, TextBlock))
        elif isinstance(messaggio, ResultMessage):
            if messaggio.is_error:
                raise RuntimeError(f"Claude ha restituito un errore: {messaggio.result}")
            testo_risultato = messaggio.result
    testo = (testo_risultato or "".join(parti)).strip()
    if not testo:
        raise RuntimeError("Claude non ha restituito alcun commento")
    return " ".join(testo.split())


def main():
    try:
        stats = analizza(FILE_LOG)
    except FileNotFoundError:
        sys.exit(f"Errore: {FILE_LOG} non trovato nella cartella corrente")

    try:
        commento = asyncio.run(scrivi_commento(stats))
    except Exception as e:
        sys.exit(f"Errore nella generazione del commento con Claude: {e}")

    risultato = {
        "richieste_per_ora": stats["richieste_per_ora"],
        "errori": stats["errori"],
        "ip_top": stats["ip_top"],
        "commento": commento,
    }
    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"Risultato scritto in {FILE_RISULTATO}")


if __name__ == "__main__":
    main()
