import json
import re
import sys
from collections import Counter

import anthropic

LOG = "access.log"
OUT = "risultato.json"
MODEL = "claude-opus-5-5"

# IP - utente [gg/Mese/aaaa:HH:MM:SS fuso] "richiesta" stato byte
RIGA = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[[^:]+:(?P<ora>\d{2}):\d{2}:\d{2} [^\]]+\] '
    r'"[^"]*" (?P<stato>\d{3}) \S+\s*$'
)


def leggi_log(percorso):
    per_ora, errori, per_ip = Counter(), Counter(), Counter()
    with open(percorso, encoding="utf-8", errors="replace") as f:
        for numero, riga in enumerate(f, 1):
            if not riga.strip():
                continue
            m = RIGA.match(riga)
            if not m:
                print(f"riga {numero} non riconosciuta: {riga.strip()}", file=sys.stderr)
                continue
            per_ora[m["ora"]] += 1
            per_ip[m["ip"]] += 1
            if int(m["stato"]) >= 400:
                errori[m["stato"]] += 1
    return per_ora, errori, per_ip


def top_ip(per_ip, n=3):
    # a parità di richieste, ordine per indirizzo, così il risultato è stabile
    ordinati = sorted(per_ip.items(), key=lambda kv: (-kv[1], kv[0]))
    return [ip for ip, _ in ordinati[:n]]


def commento(stat):
    client = anthropic.Anthropic()
    prompt = (
        "Queste sono le statistiche del traffico di una giornata sul nostro sito "
        "(dal log degli accessi):\n\n"
        + json.dumps(stat, ensure_ascii=False, indent=2)
        + "\n\nScrivi in italiano un commento di esattamente due frasi sul traffico "
        "della giornata, basandoti solo su questi dati. Rispondi solo con le due "
        "frasi, senza titoli né elenchi."
    )
    risposta = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato la richiesta")
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    if not testo:
        raise RuntimeError("risposta di Claude senza testo")
    return testo


def main():
    per_ora, errori, per_ip = leggi_log(LOG)
    stat = {
        "richieste_per_ora": dict(sorted(per_ora.items())),
        "errori": dict(sorted(errori.items())),
        "ip_top": top_ip(per_ip),
    }
    try:
        stat["commento"] = commento(stat)
    except anthropic.APIError as e:
        sys.exit(f"Errore nella chiamata a Claude: {e}")
    except TypeError:
        sys.exit("Credenziali mancanti: imposta ANTHROPIC_API_KEY")
    except RuntimeError as e:
        sys.exit(f"Errore: {e}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(stat, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
