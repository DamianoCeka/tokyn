"""Fatturato per paese e migliori clienti da ordini.csv e clienti.csv.

Si avvia con `python programma.py` dalla cartella dei due CSV e scrive
risultato.json. Il riassunto per la direzione lo scrive Claude
(serve la variabile d'ambiente ANTHROPIC_API_KEY).
"""
import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation

import anthropic

MODELLO = "claude-opus-5-5"
CENT = Decimal("0.01")


def leggi_csv(percorso):
    # utf-8-sig: tollera il BOM che alcuni gestionali aggiungono
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def calcola(clienti, ordini):
    anagrafica = {c["id"].strip(): c for c in clienti}
    per_paese = defaultdict(Decimal)
    per_cliente = defaultdict(Decimal)
    for c in clienti:  # anche i paesi senza ordini compaiono, a zero
        per_paese[c["paese"]] += 0

    for riga in ordini:
        cid = riga["cliente_id"].strip()
        cliente = anagrafica.get(cid)
        if cliente is None:
            print(f"Attenzione: ordine {riga['id']} con cliente_id {cid} "
                  "sconosciuto, ignorato", file=sys.stderr)
            continue
        try:
            importo = Decimal(riga["importo"].strip())
        except InvalidOperation:
            sys.exit(f"Importo non valido nell'ordine {riga['id']}: {riga['importo']!r}")
        per_paese[cliente["paese"]] += importo
        per_cliente[cid] += importo

    paesi = sorted(per_paese.items(), key=lambda kv: (-kv[1], kv[0]))
    fatturato = {p: float(v.quantize(CENT)) for p, v in paesi}

    classifica = sorted(per_cliente.items(),
                        key=lambda kv: (-kv[1], anagrafica[kv[0]]["nome"]))
    migliori = [anagrafica[cid]["nome"] for cid, _ in classifica[:3]]
    spesa_migliori = {anagrafica[cid]["nome"]: float(v.quantize(CENT))
                      for cid, v in classifica[:3]}
    return fatturato, migliori, spesa_migliori


def scrivi_riassunto(fatturato, spesa_migliori):
    paese_top = next(iter(fatturato))  # il dizionario è ordinato per fatturato
    dati = json.dumps(
        {"paese_con_fatturato_piu_alto": paese_top,
         "fatturato_per_paese_euro": fatturato,
         "migliori_clienti_spesa_euro": spesa_migliori},
        ensure_ascii=False, indent=2)
    prompt = (
        "Dati del trimestre (importi in euro):\n"
        f"{dati}\n\n"
        "Scrivi in italiano un breve paragrafo (3-5 frasi, testo semplice, "
        "senza elenchi né titoli) per la direzione aziendale. Indica qual è il "
        "paese con il fatturato più alto e commenta i numeri: il peso rispetto "
        "al totale, il confronto con gli altri paesi e il contributo dei "
        "migliori clienti. Scrivi gli importi nel formato italiano (es. "
        "15.230,50 euro). Usa solo i dati forniti, senza inventare cause o "
        "numeri non ricavabili da essi.")
    client = anthropic.Anthropic()
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=2000,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    if not testo:
        raise RuntimeError(f"risposta senza testo (stop_reason={risposta.stop_reason})")
    return testo


def main():
    clienti = leggi_csv("clienti.csv")
    ordini = leggi_csv("ordini.csv")
    fatturato, migliori, spesa_migliori = calcola(clienti, ordini)

    risultato = {"fatturato_per_paese": fatturato, "migliori_clienti": migliori}
    errore = None
    try:
        risultato["riassunto"] = scrivi_riassunto(fatturato, spesa_migliori)
    except Exception as e:  # senza riassunto i numeri restano comunque utili
        errore = e
        risultato["riassunto"] = None

    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")

    if errore:
        sys.exit(f"Riassunto non generato ({type(errore).__name__}: {errore}). "
                 "risultato.json scritto con riassunto null.")
    print("Scritto risultato.json")


if __name__ == "__main__":
    main()
