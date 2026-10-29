"""Statistiche sul log degli accessi (common log format) con un commento scritto da Claude.

Uso: python programma.py  (dalla cartella che contiene access.log)
Scrive risultato.json. Richiede il pacchetto `anthropic` e una credenziale
Anthropic (per esempio la variabile d'ambiente ANTHROPIC_API_KEY).
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
RIGA = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[[^:\]]+:(?P<ora>\d{2}):\d{2}:\d{2}[^\]]*\] '
    r'"[^"]*" (?P<stato>\d{3}) \S+'
)


def analizza(percorso):
    ore, errori, ip = Counter(), Counter(), Counter()
    totale = 0
    scartate = 0
    with open(percorso, encoding="utf-8", errors="replace") as f:
        for riga in f:
            riga = riga.strip()
            if not riga:
                continue
            m = RIGA.match(riga)
            if not m:
                scartate += 1
                continue
            totale += 1
            ore[m["ora"]] += 1
            ip[m["ip"]] += 1
            stato = int(m["stato"])
            if stato >= 400:
                errori[str(stato)] += 1
    if scartate:
        print(f"Attenzione: {scartate} righe non riconosciute e ignorate.", file=sys.stderr)
    return totale, ore, errori, ip


def chiedi_commento(client, totale, ore, errori, ip_top):
    dati = {
        "richieste_totali": totale,
        "richieste_per_ora": ore,
        "errori_per_codice": errori,
        "ip_con_piu_richieste": ip_top,
    }
    prompt = (
        "Ecco le statistiche del log degli accessi di un sito web per una giornata "
        "(le ore sono quelle locali scritte nel log):\n\n"
        f"{json.dumps(dati, ensure_ascii=False, indent=2)}\n\n"
        "Scrivi un commento sul traffico della giornata in italiano, di esattamente due frasi, "
        "basato solo su questi dati: per esempio l'andamento nelle ore, il picco, e quanti e "
        "quali errori ci sono stati. Rispondi solo con le due frasi, in testo semplice, "
        "senza titoli, elenchi o formattazione."
    )
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
    testo = " ".join(b.text for b in risposta.content if b.type == "text").strip()
    if not testo:
        raise RuntimeError(f"Risposta di Claude senza testo (stop_reason={risposta.stop_reason}).")
    return " ".join(testo.split())


def main():
    try:
        totale, ore, errori, ip = analizza(FILE_LOG)
    except FileNotFoundError:
        sys.exit(f"File {FILE_LOG} non trovato nella cartella corrente.")

    richieste_per_ora = {h: ore[h] for h in sorted(ore)}
    errori_per_codice = {c: errori[c] for c in sorted(errori, key=int)}
    # A parità di richieste vale l'ordine di prima comparsa nel log.
    ip_top = [indirizzo for indirizzo, _ in ip.most_common(3)]

    try:
        commento = chiedi_commento(
            anthropic.Anthropic(), totale, richieste_per_ora, errori_per_codice, ip_top
        )
    except (anthropic.AuthenticationError, TypeError):
        # TypeError: l'SDK non trova nessuna credenziale da usare.
        sys.exit("Credenziali Anthropic mancanti o non valide (imposta ANTHROPIC_API_KEY).")
    except anthropic.RateLimitError:
        sys.exit("Limite di richieste all'API Anthropic raggiunto: riprova tra poco.")
    except anthropic.APIStatusError as e:
        sys.exit(f"Errore dall'API Anthropic ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Impossibile collegarsi all'API Anthropic.")
    except RuntimeError as e:
        sys.exit(str(e))

    risultato = {
        "richieste_per_ora": richieste_per_ora,
        "errori": errori_per_codice,
        "ip_top": ip_top,
        "commento": commento,
    }
    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Scritto {FILE_RISULTATO} ({totale} richieste analizzate).")


if __name__ == "__main__":
    main()
