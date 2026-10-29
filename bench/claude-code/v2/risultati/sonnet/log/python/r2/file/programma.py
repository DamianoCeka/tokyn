import json
import re
import sys
from collections import Counter

import anthropic

LINEA = re.compile(r'^(\S+) \S+ \S+ \[[^\]:]*:(\d{2}):\d{2}:\d{2} [^\]]*\] ".*" (\d{3}) (?:\d+|-)\s*$')


def leggi_log(percorso):
    per_ora, errori, per_ip = Counter(), Counter(), Counter()
    with open(percorso, encoding="utf-8", errors="replace") as f:
        for riga in f:
            if not riga.strip():
                continue
            m = LINEA.match(riga)
            if not m:
                print(f"Riga non riconosciuta, ignorata: {riga.rstrip()}", file=sys.stderr)
                continue
            ip, ora, stato = m.groups()
            per_ora[ora] += 1
            per_ip[ip] += 1
            if int(stato) >= 400:
                errori[stato] += 1
    return per_ora, errori, per_ip


def commento_di_claude(per_ora, errori, per_ip):
    riepilogo = {
        "richieste_totali": sum(per_ora.values()),
        "richieste_per_ora": dict(sorted(per_ora.items())),
        "errori": dict(sorted(errori.items())),
        "ip_top": dict(per_ip.most_common(3)),
    }
    client = anthropic.Anthropic()
    risposta = client.messages.create(
        model="claude-opus-5-5",
        max_tokens=2000,
        output_config={"effort": "low"},
        system="Sei un analista web. Rispondi in italiano.",
        messages=[{
            "role": "user",
            "content": "Ecco le statistiche degli accessi al nostro sito in una giornata:\n"
            + json.dumps(riepilogo, ensure_ascii=False)
            + "\n\nScrivi un breve commento sul traffico della giornata: esattamente due frasi, "
            "solo testo semplice, senza elenchi né titoli.",
        }],
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato la richiesta")
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    if not testo:
        raise RuntimeError("Claude non ha restituito alcun testo")
    return testo


def main():
    per_ora, errori, per_ip = leggi_log("access.log")
    risultato = {
        "richieste_per_ora": dict(sorted(per_ora.items())),
        "errori": dict(sorted(errori.items())),
        "ip_top": [ip for ip, _ in per_ip.most_common(3)],
        "commento": commento_di_claude(per_ora, errori, per_ip),
    }
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
