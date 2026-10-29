"""Fatturato trimestrale per paese, migliori clienti e riassunto per la direzione.

Si avvia dalla cartella che contiene ordini.csv e clienti.csv:

    python programma.py

Scrive risultato.json nella stessa cartella. Richiede il pacchetto `anthropic`
e le credenziali dell'API Claude (ad esempio la variabile ANTHROPIC_API_KEY).
"""

import csv
import json
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import anthropic

MODELLO = "claude-opus-5-5"
CENTESIMO = Decimal("0.01")


def leggi_csv(nome_file, colonne):
    # utf-8-sig tollera il BOM che alcuni gestionali mettono in testa al file
    try:
        with open(nome_file, encoding="utf-8-sig", newline="") as f:
            lettore = csv.DictReader(f)
            mancanti = set(colonne) - set(lettore.fieldnames or [])
            if mancanti:
                sys.exit(f"{nome_file}: mancano le colonne {', '.join(sorted(mancanti))}")
            righe = list(enumerate(lettore, start=2))
    except FileNotFoundError:
        sys.exit(f"File {nome_file} non trovato: avvia il programma dalla cartella dei CSV")
    for riga, r in righe:
        # campi in più o in meno: ad es. un importo scritto "100,50" senza virgolette
        if None in r or None in r.values():
            sys.exit(f"{nome_file}, riga {riga}: numero di campi sbagliato (virgola non tra virgolette?)")
    return righe


def leggi_clienti():
    clienti = {}
    for riga, r in leggi_csv("clienti.csv", ["id", "nome", "paese"]):
        id_cliente = r["id"].strip()
        if id_cliente in clienti:
            sys.exit(f"clienti.csv, riga {riga}: id cliente {id_cliente} ripetuto")
        clienti[id_cliente] = {"nome": r["nome"].strip(), "paese": r["paese"].strip()}
    return clienti


def leggi_ordini(clienti):
    ordini = []
    for riga, r in leggi_csv("ordini.csv", ["id", "cliente_id", "data", "importo"]):
        try:
            importo = Decimal(r["importo"].strip())
            giorno = date.fromisoformat(r["data"].strip())
        except (InvalidOperation, ValueError):
            sys.exit(f"ordini.csv, riga {riga}: data o importo non validi ({r['data']!r}, {r['importo']!r})")
        id_cliente = r["cliente_id"].strip()
        if id_cliente not in clienti:
            # meglio fermarsi che presentare alla direzione un fatturato incompleto
            sys.exit(f"ordini.csv, riga {riga}: cliente {id_cliente} non presente in clienti.csv")
        ordini.append({"cliente_id": id_cliente, "data": giorno, "importo": importo})
    if not ordini:
        sys.exit("ordini.csv non contiene ordini")
    return ordini


def calcola(clienti, ordini):
    per_cliente = defaultdict(Decimal)
    for o in ordini:
        per_cliente[o["cliente_id"]] += o["importo"]

    per_paese = {c["paese"]: Decimal(0) for c in clienti.values()}
    for id_cliente, totale in per_cliente.items():
        per_paese[clienti[id_cliente]["paese"]] += totale

    paesi = sorted(per_paese.items(), key=lambda p: (-p[1], p[0]))
    migliori = sorted(per_cliente.items(), key=lambda c: (-c[1], clienti[c[0]]["nome"]))[:3]
    migliori = [(clienti[id_cliente]["nome"], clienti[id_cliente]["paese"], totale)
                for id_cliente, totale in migliori]
    return paesi, migliori


def euro(valore):
    """Formato italiano: 15230.5 -> '15.230,50'."""
    testo = f"{valore.quantize(CENTESIMO, ROUND_HALF_UP):,.2f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".")


def scrivi_riassunto(paesi, migliori, ordini):
    totale = sum(t for _, t in paesi)
    inizio = min(o["data"] for o in ordini)
    fine = max(o["data"] for o in ordini)
    righe_paesi = "\n".join(
        f"- {p}: {euro(t)} euro ({euro(t / totale * 100)}% del totale)" for p, t in paesi
    )
    righe_clienti = "\n".join(
        f"{i}. {nome} ({paese}): {euro(t)} euro" for i, (nome, paese, t) in enumerate(migliori, 1)
    )
    dati = (
        f"Periodo degli ordini: dal {inizio:%d/%m/%Y} al {fine:%d/%m/%Y}\n"
        f"Numero di ordini: {len(ordini)}\n"
        f"Fatturato totale: {euro(totale)} euro\n\n"
        f"Fatturato per paese (dal più alto):\n{righe_paesi}\n\n"
        f"Clienti che hanno speso di più:\n{righe_clienti}"
    )

    client = anthropic.Anthropic()
    try:
        risposta = client.beta.messages.create(
            model=MODELLO,
            max_tokens=4000,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=(
                "Sei l'analista commerciale di un'azienda e scrivi per la direzione. "
                "Rispondi in italiano con un solo paragrafo di prosa (4-6 frasi), senza titoli, "
                "elenchi o formattazione Markdown. Indica per primo il paese con il fatturato più alto "
                "e la cifra, poi commenta i numeri: peso dei paesi sul totale, distanze tra loro, "
                "concentrazione sui migliori clienti. Usa solo i numeri forniti, scritti esattamente "
                "come sono (formato italiano, es. 15.230,50 euro): non ricalcolarli e non inventarne altri."
            ),
            messages=[{
                "role": "user",
                "content": f"Dati del trimestre, già calcolati:\n<dati>\n{dati}\n</dati>",
            }],
        )
    except TypeError as e:
        # l'SDK segnala così l'assenza di qualsiasi credenziale
        if "authentication" not in str(e):
            raise
        sys.exit("Credenziali API Claude mancanti: imposta ANTHROPIC_API_KEY")
    except anthropic.APIConnectionError as e:
        sys.exit(f"Impossibile contattare l'API Claude: {e}")
    except anthropic.AuthenticationError:
        sys.exit("Credenziali API Claude mancanti o non valide (imposta ANTHROPIC_API_KEY)")
    except anthropic.RateLimitError:
        sys.exit("API Claude: troppe richieste, riprova tra qualche minuto")
    except anthropic.APIStatusError as e:
        sys.exit(f"Errore dell'API Claude ({e.status_code}): {e.message}")

    if risposta.stop_reason == "refusal":
        sys.exit("Claude ha rifiutato di scrivere il riassunto")
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    if not testo:
        sys.exit("Claude ha restituito un riassunto vuoto")
    if risposta.stop_reason == "max_tokens":
        sys.exit("Il riassunto è stato troncato: riprova")
    if paesi[0][0] not in testo:
        print(f"Attenzione: il riassunto non nomina {paesi[0][0]}, controllalo prima di inviarlo",
              file=sys.stderr)
    return testo


def main():
    clienti = leggi_clienti()
    ordini = leggi_ordini(clienti)
    paesi, migliori = calcola(clienti, ordini)
    riassunto = scrivi_riassunto(paesi, migliori, ordini)

    risultato = {
        "fatturato_per_paese": {
            p: float(t.quantize(CENTESIMO, ROUND_HALF_UP)) for p, t in paesi
        },
        "migliori_clienti": [nome for nome, _, _ in migliori],
        "riassunto": riassunto,
    }
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Scritto risultato.json (paese con il fatturato più alto: {paesi[0][0]})")


if __name__ == "__main__":
    main()
