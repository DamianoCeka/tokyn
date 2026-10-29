"""Statistiche giornaliere da access.log (Apache common log format) con commento di Claude.

Uso: python programma.py   (dalla cartella che contiene access.log)
Scrive risultato.json.
"""

import json
import re
import sys
from collections import Counter

import anthropic

FILE_LOG = "access.log"
FILE_RISULTATO = "risultato.json"
MODELLO = "claude-opus-5-5"

# host ident authuser [gg/Mmm/aaaa:HH:MM:SS zona] "richiesta" stato byte
RIGA = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[[^:\]]+:(?P<ora>\d{2}):\d{2}:\d{2}[^\]]*\] "[^"]*" (?P<stato>\d{3}) \S+$'
)


def analizza(percorso):
    per_ora = Counter()
    errori = Counter()
    per_ip = Counter()
    totale = 0
    with open(percorso, encoding="utf-8", errors="replace") as f:
        for numero, riga in enumerate(f, 1):
            riga = riga.strip()
            if not riga:
                continue
            m = RIGA.match(riga)
            if not m:
                print(f"Riga {numero} non riconosciuta, ignorata: {riga!r}", file=sys.stderr)
                continue
            totale += 1
            per_ora[m["ora"]] += 1
            per_ip[m["ip"]] += 1
            stato = int(m["stato"])
            if stato >= 400:
                errori[str(stato)] += 1
    return {
        "richieste_per_ora": dict(sorted(per_ora.items())),
        "errori": dict(sorted(errori.items(), key=lambda kv: int(kv[0]))),
        # A parità di richieste vince l'IP comparso prima nel log.
        "ip_top": [ip for ip, _ in per_ip.most_common(3)],
    }, totale


def commenta(statistiche, totale):
    client = anthropic.Anthropic()
    dati = dict(statistiche, richieste_totali=totale)
    response = client.beta.messages.create(
        model=MODELLO,
        max_tokens=16000,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=(
            "Sei un analista web. Scrivi in italiano esattamente due frasi, semplici e concrete, "
            "che commentano il traffico di una giornata di un sito a partire dalle statistiche "
            "del log degli accessi. Rispondi solo con le due frasi, senza titoli né elenchi."
        ),
        messages=[{
            "role": "user",
            "content": "Statistiche della giornata (JSON):\n" + json.dumps(dati, ensure_ascii=False),
        }],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato di scrivere il commento.")
    testo = "".join(b.text for b in response.content if b.type == "text").strip()
    if not testo:
        raise RuntimeError(f"Risposta di Claude senza testo (stop_reason={response.stop_reason}).")
    return " ".join(testo.split())


def main():
    try:
        statistiche, totale = analizza(FILE_LOG)
    except FileNotFoundError:
        sys.exit(f"File {FILE_LOG} non trovato nella cartella corrente.")

    try:
        statistiche["commento"] = commenta(statistiche, totale)
    except anthropic.APIConnectionError as e:
        sys.exit(f"Impossibile contattare l'API di Claude: {e}")
    except anthropic.APIStatusError as e:
        sys.exit(f"Errore dall'API di Claude ({e.status_code}): {e.message}")
    except RuntimeError as e:
        sys.exit(str(e))

    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(statistiche, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Scritto {FILE_RISULTATO} ({totale} richieste analizzate).")


if __name__ == "__main__":
    main()
