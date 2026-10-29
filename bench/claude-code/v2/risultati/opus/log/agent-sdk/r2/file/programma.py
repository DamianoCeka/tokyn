"""Statistiche sul log degli accessi (Apache common log format) con commento scritto da Claude.

Uso: python programma.py   (dalla cartella che contiene access.log)
Scrive risultato.json.
"""

import asyncio
import json
import re
import sys
from collections import Counter

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

FILE_LOG = "access.log"
FILE_RISULTATO = "risultato.json"

# host ident authuser [gg/Mmm/aaaa:HH:MM:SS zona] "richiesta" stato byte
RIGA_LOG = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[[^:\]]+:(?P<ora>\d{2}):\d{2}:\d{2}[^\]]*\] ".*" (?P<stato>\d{3}) \S+\s*$'
)


def analizza(percorso):
    """Conta richieste per ora, errori (stato >= 400) e richieste per IP."""
    per_ora = Counter()
    errori = Counter()
    per_ip = Counter()
    scartate = 0

    with open(percorso, encoding="utf-8", errors="replace") as f:
        for numero, riga in enumerate(f, start=1):
            if not riga.strip():
                continue
            m = RIGA_LOG.match(riga)
            if not m:
                scartate += 1
                print(f"Attenzione: riga {numero} non riconosciuta, ignorata: {riga.rstrip()}", file=sys.stderr)
                continue
            per_ora[m["ora"]] += 1
            per_ip[m["ip"]] += 1
            stato = int(m["stato"])
            if stato >= 400:
                errori[str(stato)] += 1

    return per_ora, errori, per_ip, scartate


async def scrivi_commento(statistiche):
    """Chiede a Claude due frasi di commento sul traffico."""
    prompt = (
        "Questi sono i dati di una giornata di traffico di un sito web, ricavati dal log degli accessi:\n"
        f"{json.dumps(statistiche, ensure_ascii=False, indent=2)}\n\n"
        "Scrivi un commento sul traffico della giornata in italiano, lungo esattamente due frasi. "
        "Rispondi solo con le due frasi, senza titoli, elenchi, markdown o virgolette."
    )
    opzioni = ClaudeAgentOptions(
        tools=[],          # nessuno strumento: serve solo testo
        max_turns=1,
        setting_sources=[],
    )
    testo = None
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            if messaggio.is_error:
                raise RuntimeError(f"Claude ha restituito un errore: {messaggio.result}")
            testo = messaggio.result
    if not testo or not testo.strip():
        raise RuntimeError("Claude non ha restituito alcun commento")
    return " ".join(testo.split())


def main():
    try:
        per_ora, errori, per_ip, scartate = analizza(FILE_LOG)
    except FileNotFoundError:
        sys.exit(f"Errore: {FILE_LOG} non trovato nella cartella corrente")

    # Counter.most_common è stabile: a parità di richieste vince l'IP comparso prima nel log.
    ip_top = [ip for ip, _ in per_ip.most_common(3)]

    risultato = {
        "richieste_per_ora": dict(sorted(per_ora.items())),
        "errori": dict(sorted(errori.items(), key=lambda kv: int(kv[0]))),
        "ip_top": ip_top,
    }

    statistiche_per_claude = dict(risultato)
    statistiche_per_claude["richieste_totali"] = sum(per_ora.values())
    statistiche_per_claude["richieste_ip_top"] = {ip: per_ip[ip] for ip in ip_top}

    try:
        risultato["commento"] = asyncio.run(scrivi_commento(statistiche_per_claude))
    except Exception as e:
        sys.exit(f"Errore nel generare il commento con Claude: {e}")

    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")

    if scartate:
        print(f"{scartate} righe non riconosciute sono state ignorate", file=sys.stderr)
    print(f"Risultato scritto in {FILE_RISULTATO}")


if __name__ == "__main__":
    main()
