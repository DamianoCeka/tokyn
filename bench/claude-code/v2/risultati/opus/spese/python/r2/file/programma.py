"""Categorizza i movimenti di movimenti.csv con Claude e scrive risultato.json.

Uso: python programma.py  (dalla cartella che contiene movimenti.csv)
Richiede il pacchetto `anthropic` e una credenziale (es. ANTHROPIC_API_KEY).
"""

import csv
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import anthropic

FILE_INPUT = "movimenti.csv"
FILE_OUTPUT = "risultato.json"
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
MODELLO = "claude-opus-5-5"
MOVIMENTI_PER_RICHIESTA = 100
TENTATIVI = 3

ISTRUZIONI = f"""Sei un assistente che classifica i movimenti di un conto corrente italiano.
Per ogni movimento scegli esattamente una categoria tra: {", ".join(CATEGORIE)}.

- spesa alimentare: supermercati, alimentari, discount, mercati (non ristoranti o bar).
- trasporti: carburante, mezzi pubblici, treni, taxi, pedaggi, parcheggi, manutenzione auto.
- casa: affitto, mutuo, bollette (luce, gas, acqua, internet), condominio, arredamento, bricolage.
- svago: ristoranti, bar, pizzerie, cinema, abbonamenti streaming, libri, viaggi, hobby, sport.
- altro: tutto il resto, incluse entrate (stipendi, rimborsi), commissioni bancarie, prelievi, bonifici.

Restituisci una voce per ogni movimento, con lo stesso numero indicato in ingresso."""


def leggi_testo(percorso):
    with open(percorso, "rb") as f:
        dati = f.read()
    try:
        return dati.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dati.decode("cp1252")


def converti_importo(testo, riga):
    pulito = testo.strip().replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return Decimal(pulito)
    except InvalidOperation:
        sys.exit(f"Riga {riga}: importo non valido: {testo!r}")


def leggi_movimenti(percorso):
    righe = csv.reader(leggi_testo(percorso).splitlines(), delimiter=";")
    intestazione = [campo.strip().lower() for campo in next(righe, [])]
    if intestazione[:3] != ["data", "descrizione", "importo"]:
        sys.exit(f"Intestazione inattesa in {percorso}: {intestazione}")
    movimenti = []
    for numero_riga, campi in enumerate(righe, start=2):
        if not any(c.strip() for c in campi):
            continue
        if len(campi) != 3:
            sys.exit(f"Riga {numero_riga}: attesi 3 campi, trovati {len(campi)}: {campi}")
        data, descrizione, importo = campi
        movimenti.append({
            "data": data.strip(),
            "descrizione": descrizione.strip(),
            "importo": converti_importo(importo, numero_riga),
        })
    return movimenti


def schema_risposta():
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "classificazioni": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "numero": {"type": "integer"},
                            "categoria": {"type": "string", "enum": CATEGORIE},
                        },
                        "required": ["numero", "categoria"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["classificazioni"],
            "additionalProperties": False,
        },
    }


def classifica_blocco(client, blocco):
    elenco = "\n".join(
        f"{i}. {m['data']} | {m['descrizione']} | {m['importo']} EUR"
        for i, m in enumerate(blocco, start=1)
    )
    for tentativo in range(1, TENTATIVI + 1):
        risposta = client.beta.messages.create(
            model=MODELLO,
            max_tokens=16000,
            system=ISTRUZIONI,
            messages=[{"role": "user", "content": f"Movimenti da classificare:\n{elenco}"}],
            output_config={"effort": "low", "format": schema_risposta()},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if risposta.stop_reason == "refusal":
            sys.exit("Claude ha rifiutato di classificare i movimenti.")
        if risposta.stop_reason == "max_tokens":
            print(f"Tentativo {tentativo}: risposta troncata, riprovo.", file=sys.stderr)
            continue
        testo = next(b.text for b in risposta.content if b.type == "text")
        voci = json.loads(testo)["classificazioni"]
        categorie = {v["numero"]: v["categoria"] for v in voci}
        if set(categorie) == set(range(1, len(blocco) + 1)):
            return [categorie[i] for i in range(1, len(blocco) + 1)]
        print(f"Tentativo {tentativo}: risposta incompleta, riprovo.", file=sys.stderr)
    sys.exit("Impossibile ottenere una classificazione completa da Claude.")


def main():
    movimenti = leggi_movimenti(FILE_INPUT)
    client = anthropic.Anthropic()

    categorie = []
    for inizio in range(0, len(movimenti), MOVIMENTI_PER_RICHIESTA):
        categorie += classifica_blocco(client, movimenti[inizio:inizio + MOVIMENTI_PER_RICHIESTA])

    totali = {c: Decimal("0") for c in CATEGORIE}
    for movimento, categoria in zip(movimenti, categorie):
        movimento["categoria"] = categoria
        totali[categoria] += movimento["importo"]

    risultato = {
        "movimenti": [
            {
                "data": m["data"],
                "descrizione": m["descrizione"],
                "importo": float(m["importo"]),
                "categoria": m["categoria"],
            }
            for m in movimenti
        ],
        "totali": {
            c: float(t.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            for c, t in totali.items()
        },
    }
    with open(FILE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"Classificati {len(movimenti)} movimenti, risultato in {FILE_OUTPUT}.")


if __name__ == "__main__":
    main()
