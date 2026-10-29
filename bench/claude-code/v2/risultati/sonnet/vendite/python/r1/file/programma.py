import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import anthropic

MODELLO = "claude-opus-5-5"
CENT = Decimal("0.01")


def leggi_csv(percorso):
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def calcola():
    clienti = {r["id"].strip(): r for r in leggi_csv("clienti.csv")}
    per_paese = {r["paese"]: Decimal(0) for r in clienti.values()}
    per_cliente = {cid: Decimal(0) for cid in clienti}

    for r in leggi_csv("ordini.csv"):
        cid = r["cliente_id"].strip()
        if cid not in clienti:
            sys.exit(f"Errore: l'ordine {r['id']} riguarda il cliente {cid}, che non è in clienti.csv")
        try:
            importo = Decimal(r["importo"].strip())
        except InvalidOperation:
            sys.exit(f"Errore: importo non valido nell'ordine {r['id']}: {r['importo']!r}")
        per_cliente[cid] += importo
        per_paese[clienti[cid]["paese"]] += importo

    fatturato = {p: v.quantize(CENT) for p, v in per_paese.items()}
    classifica = sorted(clienti, key=lambda cid: (-per_cliente[cid], clienti[cid]["nome"]))
    migliori = [(clienti[cid]["nome"], per_cliente[cid].quantize(CENT)) for cid in classifica[:3]]
    return fatturato, migliori


def riassunto(fatturato, migliori):
    paesi = "\n".join(f"- {p}: {v} euro" for p, v in sorted(fatturato.items(), key=lambda x: -x[1]))
    clienti = "\n".join(f"{i}. {n}: {v} euro" for i, (n, v) in enumerate(migliori, 1))
    prompt = (
        "Questi sono i dati di fatturato del trimestre (importi in euro, punto per i decimali):\n\n"
        f"Fatturato per paese:\n{paesi}\n\nI 3 clienti che hanno speso di più:\n{clienti}\n\n"
        "Scrivi in italiano un breve paragrafo (3-5 frasi, testo semplice, senza elenchi né titoli) "
        "per la direzione. Indica qual è il paese con il fatturato più alto e commenta i numeri, "
        "ad esempio il peso dei paesi sul totale e dei migliori clienti. Usa solo i dati forniti, "
        "senza inventare confronti con altri periodi. Scrivi gli importi nel formato italiano "
        "(es. 15.230,50 euro)."
    )
    risposta = anthropic.Anthropic().messages.create(
        model=MODELLO,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato la richiesta")
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    if not testo:
        raise RuntimeError("Claude non ha restituito testo")
    return testo


def main():
    fatturato, migliori = calcola()
    risultato = {
        "fatturato_per_paese": {p: float(v) for p, v in fatturato.items()},
        "migliori_clienti": [n for n, _ in migliori],
        "riassunto": None,
    }
    errore = None
    try:
        risultato["riassunto"] = riassunto(fatturato, migliori)
    except Exception as e:  # il calcolo resta valido anche se il riassunto fallisce
        errore = e
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    if errore:
        sys.exit(f"Numeri salvati in risultato.json, ma il riassunto non è stato generato: {errore}")
    print("Scritto risultato.json")


if __name__ == "__main__":
    main()
