"""Fatturato trimestrale per paese e migliori clienti, con riassunto scritto da Claude.

Uso: dalla cartella che contiene ordini.csv e clienti.csv
    python programma.py
Scrive risultato.json nella stessa cartella.
"""

import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import anthropic

MODELLO = "claude-opus-5-5"
CENTESIMO = Decimal("0.01")


def leggi_csv(nome_file, colonne):
    # utf-8-sig: tollera il BOM che alcuni gestionali aggiungono all'inizio del file
    with open(nome_file, newline="", encoding="utf-8-sig") as f:
        lettore = csv.DictReader(f)
        mancanti = set(colonne) - set(lettore.fieldnames or [])
        if mancanti:
            sys.exit(f"{nome_file}: mancano le colonne {', '.join(sorted(mancanti))}")
        righe = list(lettore)
    for numero, riga in enumerate(righe, start=2):
        # Campi in più o in meno: tipicamente una virgola non racchiusa tra virgolette (es. "10,50")
        if None in riga or None in riga.values():
            sys.exit(f"{nome_file} riga {numero}: numero di campi errato (virgola non tra virgolette?)")
    return righe


def calcola(clienti, ordini):
    paese_di = {}
    nome_di = {}
    for c in clienti:
        paese_di[c["id"].strip()] = c["paese"].strip()
        nome_di[c["id"].strip()] = c["nome"].strip()

    speso = defaultdict(Decimal)
    for riga, o in enumerate(ordini, start=2):
        cliente_id = o["cliente_id"].strip()
        try:
            importo = Decimal(o["importo"].strip())
        except InvalidOperation:
            sys.exit(f"ordini.csv riga {riga}: importo non valido {o['importo']!r}")
        if cliente_id not in paese_di:
            sys.exit(f"ordini.csv riga {riga}: cliente_id {cliente_id} non presente in clienti.csv")
        speso[cliente_id] += importo

    # Ogni paese presente in clienti.csv compare, anche se nel trimestre non ha ordini
    per_paese = {paese: Decimal(0) for paese in paese_di.values()}
    for cliente_id, totale in speso.items():
        per_paese[paese_di[cliente_id]] += totale
    per_paese = dict(sorted(per_paese.items(), key=lambda kv: (-kv[1], kv[0])))

    # A parità di spesa decide l'ordine alfabetico, così il risultato è stabile
    classifica = sorted(speso.items(), key=lambda kv: (-kv[1], nome_di[kv[0]]))
    migliori = [(nome_di[cid], totale) for cid, totale in classifica[:3]]
    return per_paese, migliori


def euro(valore):
    """Formato italiano: 15230.5 -> '15.230,50 euro'."""
    testo = f"{valore.quantize(CENTESIMO, ROUND_HALF_UP):,.2f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".") + " euro"


def scrivi_riassunto(per_paese, migliori):
    totale = sum(per_paese.values())
    paese_top = next(iter(per_paese))
    righe_paesi = "\n".join(
        f"- {paese}: {euro(v)} ({f'{v / totale * 100:.1f}'.replace('.', ',')}% del totale)" if totale else f"- {paese}: {euro(v)}"
        for paese, v in per_paese.items()
    )
    righe_clienti = "\n".join(f"{i}. {nome}: {euro(v)}" for i, (nome, v) in enumerate(migliori, start=1))

    prompt = f"""Ecco i dati di vendita del trimestre, già calcolati e verificati.

Fatturato totale: {euro(totale)}

Fatturato per paese:
{righe_paesi}

I tre clienti che hanno speso di più:
{righe_clienti}

Scrivi un breve paragrafo (4-6 frasi) in italiano per la direzione aziendale. La prima frase deve dire che il paese con il fatturato più alto è {paese_top} e indicarne l'importo. Poi commenta i numeri: peso relativo dei paesi, concentrazione sui clienti principali, eventuali aspetti da tenere d'occhio.
Usa solo i numeri forniti sopra, scritti esattamente nello stesso formato (es. "1.234,56 euro"); se ti serve un dato derivato, limitati a confronti qualitativi. Rispondi solo con il paragrafo, senza titoli, elenchi o formattazione markdown."""

    client = anthropic.Anthropic()
    try:
        risposta = client.beta.messages.create(
            model=MODELLO,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            # Se il modello rifiuta la richiesta, l'API la ripete su un modello di riserva
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
    except TypeError as e:
        # L'SDK solleva TypeError quando non trova alcuna credenziale configurata
        if "authentication" not in str(e):
            raise
        sys.exit("Chiave API Anthropic mancante: imposta la variabile ANTHROPIC_API_KEY.")
    except anthropic.AuthenticationError:
        sys.exit("Chiave API Anthropic mancante o non valida: imposta la variabile ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        sys.exit("Limite di richieste Anthropic raggiunto: riprova tra qualche minuto.")
    except anthropic.APIStatusError as e:
        sys.exit(f"Errore dall'API Anthropic ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Impossibile contattare l'API Anthropic: controlla la connessione.")

    if risposta.stop_reason == "refusal":
        sys.exit("Claude ha rifiutato di scrivere il riassunto.")
    if risposta.stop_reason == "max_tokens":
        sys.exit("Il riassunto è stato troncato (max_tokens raggiunto).")
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    if not testo:
        sys.exit("Claude ha restituito un riassunto vuoto.")
    return testo


def main():
    clienti = leggi_csv("clienti.csv", ["id", "nome", "paese"])
    ordini = leggi_csv("ordini.csv", ["id", "cliente_id", "data", "importo"])
    if not ordini:
        sys.exit("ordini.csv non contiene ordini.")

    per_paese, migliori = calcola(clienti, ordini)
    riassunto = scrivi_riassunto(per_paese, migliori)

    risultato = {
        "fatturato_per_paese": {
            paese: float(v.quantize(CENTESIMO, ROUND_HALF_UP)) for paese, v in per_paese.items()
        },
        "migliori_clienti": [nome for nome, _ in migliori],
        "riassunto": riassunto,
    }
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Scritto risultato.json")


if __name__ == "__main__":
    main()
