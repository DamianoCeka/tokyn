"""Fatturato per paese e migliori clienti dai CSV del trimestre.

Si avvia dalla cartella dei due CSV:  python programma.py
Legge ordini.csv e clienti.csv, scrive risultato.json.
Per il riassunto serve la variabile d'ambiente ANTHROPIC_API_KEY.
"""
import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import anthropic

MODELLO = "claude-opus-5-5"
CENTESIMO = Decimal("0.01")


def leggi_csv(percorso):
    # utf-8-sig tollera il BOM che alcuni gestionali aggiungono
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def calcola():
    clienti = {r["id"].strip(): r for r in leggi_csv("clienti.csv")}
    per_paese = defaultdict(Decimal)
    per_cliente = defaultdict(Decimal)

    for riga in leggi_csv("ordini.csv"):
        cid = riga["cliente_id"].strip()
        if cid not in clienti:
            print(f"Attenzione: ordine {riga['id']} con cliente {cid} sconosciuto, ignorato",
                  file=sys.stderr)
            continue
        try:
            importo = Decimal(riga["importo"].strip())
        except InvalidOperation:
            sys.exit(f"Importo non valido nell'ordine {riga['id']}: {riga['importo']!r}")
        cliente = clienti[cid]
        per_paese[cliente["paese"]] += importo
        per_cliente[cliente["nome"]] += importo

    def arrotonda(d):
        return d.quantize(CENTESIMO, rounding=ROUND_HALF_UP)

    # a parità di importo ordina per nome, così il risultato è deterministico
    paesi = sorted(per_paese.items(), key=lambda x: (-x[1], x[0]))
    migliori = sorted(per_cliente.items(), key=lambda x: (-x[1], x[0]))[:3]
    return (
        {p: float(arrotonda(t)) for p, t in paesi},
        [n for n, _ in migliori],
        {n: float(arrotonda(t)) for n, t in migliori},
    )


def euro(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def riassunto(fatturato, migliori, spesa_migliori):
    righe_paesi = "\n".join(f"- {p}: {euro(t)} euro" for p, t in fatturato.items())
    righe_clienti = "\n".join(f"{i}. {n}: {euro(spesa_migliori[n])} euro"
                              for i, n in enumerate(migliori, 1))
    prompt = (
        "Scrivi per la direzione un breve paragrafo in italiano (3-4 frasi, testo semplice, "
        "senza elenchi né titoli) sul fatturato dell'ultimo trimestre. Deve dire qual è il "
        "paese con il fatturato più alto e commentare i numeri, ad esempio il peso dei paesi "
        "tra loro e dei migliori clienti. Usa solo i dati qui sotto, senza inventare cause o "
        "confronti con altri periodi. Scrivi gli importi in formato italiano "
        "(es. 15.230,50 euro).\n\n"
        f"Fatturato per paese (dal più alto):\n{righe_paesi}\n\n"
        f"Tre clienti che hanno speso di più:\n{righe_clienti}"
    )
    client = anthropic.Anthropic()
    risposta = client.beta.messages.create(
        model=MODELLO,
        max_tokens=2000,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato la richiesta")
    return "".join(b.text for b in risposta.content if b.type == "text").strip()


def main():
    fatturato, migliori, spesa_migliori = calcola()
    risultato = {"fatturato_per_paese": fatturato, "migliori_clienti": migliori}
    errore = None
    try:
        risultato["riassunto"] = riassunto(fatturato, migliori, spesa_migliori)
    except Exception as e:  # i numeri restano comunque utili
        errore = e
        risultato["riassunto"] = ""
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    if errore:
        sys.exit(f"Riassunto non generato ({type(errore).__name__}: {errore}). "
                 "risultato.json contiene solo i numeri.")
    print("Scritto risultato.json")


if __name__ == "__main__":
    main()
