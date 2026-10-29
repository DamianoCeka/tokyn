import json
import re
import sys
from collections import Counter

import anthropic

MODEL = "claude-opus-5-5"

# IP (anche IPv6), ident, utente, [data], "richiesta", stato, byte.
# La richiesta può essere "-" (es. errori 408), quindi si ancora lo stato all'ultimo campo.
RIGA = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[\d{2}/\w{3}/\d{4}:(?P<ora>\d{2}):\d{2}:\d{2} [^\]]+\] '
    r'"(?:[^"]*)" (?P<stato>\d{3}) (?:\d+|-)\s*$'
)


def leggi_log(percorso):
    per_ora = Counter()
    errori = Counter()
    per_ip = Counter()
    for n, riga in enumerate(open(percorso, encoding="utf-8"), 1):
        if not riga.strip():
            continue
        m = RIGA.match(riga)
        if not m:
            sys.exit(f"{percorso}:{n}: riga non riconosciuta: {riga.rstrip()!r}")
        per_ora[m["ora"]] += 1
        per_ip[m["ip"]] += 1
        if int(m["stato"]) >= 400:
            errori[m["stato"]] += 1
    return per_ora, errori, per_ip


def commento(statistiche):
    client = anthropic.Anthropic()
    risposta = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "low"},
        messages=[{
            "role": "user",
            "content": (
                "Queste sono le statistiche del traffico di un sito web in una giornata "
                "(richieste per ora, errori per codice di stato, IP più attivi):\n\n"
                + json.dumps(statistiche, ensure_ascii=False)
                + "\n\nScrivi in italiano un commento di esattamente due frasi sul traffico "
                "della giornata. Rispondi solo con le due frasi, senza elenchi né titoli."
            ),
        }],
    )
    if risposta.stop_reason == "refusal":
        sys.exit("Claude ha rifiutato la richiesta del commento.")
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    if not testo:
        sys.exit("Claude non ha restituito alcun commento.")
    return testo


def main():
    per_ora, errori, per_ip = leggi_log("access.log")
    # a parità di richieste, l'IP con ordine alfabetico viene prima (risultato deterministico)
    ip_top = [ip for ip, _ in sorted(per_ip.items(), key=lambda x: (-x[1], x[0]))[:3]]
    statistiche = {
        "richieste_per_ora": dict(sorted(per_ora.items())),
        "errori": dict(sorted(errori.items())),
        "ip_top": ip_top,
    }
    statistiche["commento"] = commento(
        {**statistiche, "richieste_totali": sum(per_ora.values())}
    )
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(statistiche, f, ensure_ascii=False, indent=2)
    print("Scritto risultato.json")


if __name__ == "__main__":
    main()
