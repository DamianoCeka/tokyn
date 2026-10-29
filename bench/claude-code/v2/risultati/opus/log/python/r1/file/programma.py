"""Statistiche sul log degli accessi Apache (common log format) con un commento scritto da Claude.

Uso: python programma.py   (dalla cartella che contiene access.log)
Scrive il risultato in risultato.json.
"""

import json
import re
import sys
from collections import Counter

import anthropic

FILE_LOG = "access.log"
FILE_RISULTATO = "risultato.json"
MODELLO = "claude-opus-5-5"

# host ident authuser [gg/Mmm/aaaa:hh:mm:ss zona] "richiesta" stato byte
RIGA_LOG = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ '
    r'\[\d{2}/\w{3}/\d{4}:(?P<ora>\d{2}):\d{2}:\d{2} [+-]\d{4}\] '
    r'"(?:[^"\\]|\\.)*" '
    r'(?P<stato>\d{3}) \S+$'
)


def analizza_log(percorso):
    richieste_per_ora = Counter()
    errori = Counter()
    richieste_per_ip = Counter()
    totale = 0

    with open(percorso, encoding="utf-8", errors="replace") as f:
        for numero, riga in enumerate(f, start=1):
            riga = riga.strip()
            if not riga:
                continue
            m = RIGA_LOG.match(riga)
            if not m:
                print(f"Riga {numero} non riconosciuta, la salto: {riga!r}", file=sys.stderr)
                continue
            totale += 1
            richieste_per_ora[m["ora"]] += 1
            richieste_per_ip[m["ip"]] += 1
            stato = int(m["stato"])
            if stato >= 400:
                errori[str(stato)] += 1

    return {
        "totale": totale,
        "richieste_per_ora": dict(sorted(richieste_per_ora.items())),
        "errori": dict(sorted(errori.items())),
        "ip_top": [ip for ip, _ in richieste_per_ip.most_common(3)],
        "richieste_ip_top": richieste_per_ip.most_common(3),
    }


def scrivi_commento(statistiche):
    dati = {
        "richieste_totali": statistiche["totale"],
        "richieste_per_ora": statistiche["richieste_per_ora"],
        "errori_per_codice_di_stato": statistiche["errori"],
        "ip_con_piu_richieste": dict(statistiche["richieste_ip_top"]),
    }
    prompt = (
        "Ecco alcune statistiche ricavate dal log degli accessi del nostro sito web "
        "per una singola giornata:\n\n"
        f"{json.dumps(dati, ensure_ascii=False, indent=2)}\n\n"
        "Scrivi un breve commento sul traffico della giornata: esattamente due frasi in italiano, "
        "basate solo su questi dati (andamento nelle ore, picchi, errori). "
        "Rispondi solo con le due frasi, senza titoli, elenchi o formattazione."
    )

    client = anthropic.Anthropic()
    if not (client.api_key or client.auth_token):
        raise RuntimeError("manca la chiave API: imposta la variabile d'ambiente ANTHROPIC_API_KEY.")
    risposta = client.beta.messages.create(
        model=MODELLO,
        max_tokens=16000,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato di scrivere il commento.")

    testo = " ".join(b.text.strip() for b in risposta.content if b.type == "text").strip()
    if not testo:
        raise RuntimeError(f"Claude non ha restituito testo (stop_reason={risposta.stop_reason}).")
    return testo


def main():
    try:
        statistiche = analizza_log(FILE_LOG)
    except FileNotFoundError:
        sys.exit(f"Non trovo {FILE_LOG} nella cartella corrente.")

    try:
        commento = scrivi_commento(statistiche)
    except (anthropic.APIError, RuntimeError) as e:
        sys.exit(f"Errore nel chiedere il commento a Claude: {e}")

    risultato = {
        "richieste_per_ora": statistiche["richieste_per_ora"],
        "errori": statistiche["errori"],
        "ip_top": statistiche["ip_top"],
        "commento": commento,
    }
    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Risultato scritto in {FILE_RISULTATO}")


if __name__ == "__main__":
    main()
