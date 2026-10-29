"""Classifica i movimenti di movimenti.csv con Claude e calcola i totali per categoria.

Uso: python programma.py  (dalla cartella che contiene movimenti.csv)
Richiede il pacchetto `anthropic` e la variabile d'ambiente ANTHROPIC_API_KEY.
"""

import csv
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import anthropic

FILE_INGRESSO = "movimenti.csv"
FILE_USCITA = "risultato.json"
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
MODELLO = "claude-opus-5-5"
MOVIMENTI_PER_RICHIESTA = 100

ISTRUZIONI = """Sei un assistente che classifica i movimenti di un conto corrente italiano.
Per ogni movimento scegli esattamente una categoria tra queste:
- "spesa alimentare": supermercati, alimentari, discount, mercati (es. Esselunga, Lidl, Carrefour, Coop, Conad).
- "trasporti": treni, mezzi pubblici, carburante, pedaggi, parcheggi, taxi, car sharing, manutenzione auto.
- "casa": affitto, mutuo, condominio, bollette (luce, gas, acqua, internet, telefono fisso), arredamento, bricolage, manutenzione della casa.
- "svago": ristoranti, pizzerie, bar, cinema, abbonamenti di streaming, libri, viaggi, sport, hobby.
- "altro": tutto il resto, incluse entrate (stipendi, rimborsi), commissioni bancarie, bonifici e prelievi.
Ti viene dato l'elenco dei movimenti numerati. Restituisci una categoria per ciascun numero."""


def leggi_movimenti(percorso):
    movimenti = []
    with open(percorso, encoding="utf-8-sig", newline="") as f:
        lettore = csv.reader(f, delimiter=";")
        intestazione = next(lettore, None)
        if intestazione is None or [c.strip().lower() for c in intestazione] != ["data", "descrizione", "importo"]:
            raise ValueError(f"intestazione inattesa in {percorso}: {intestazione}")
        for numero_riga, campi in enumerate(lettore, start=2):
            if not any(c.strip() for c in campi):
                continue
            if len(campi) != 3:
                raise ValueError(f"riga {numero_riga}: attesi 3 campi, trovati {len(campi)}: {campi}")
            data, descrizione, importo_testo = (c.strip() for c in campi)
            try:
                importo = Decimal(importo_testo.replace(".", "").replace(",", "."))
            except InvalidOperation:
                raise ValueError(f"riga {numero_riga}: importo non valido: {importo_testo!r}") from None
            movimenti.append({"data": data, "descrizione": descrizione, "importo": importo})
    return movimenti


def classifica_blocco(client, blocco):
    elenco = "\n".join(
        f"{i}. {m['descrizione']} (importo {m['importo']} EUR)" for i, m in enumerate(blocco)
    )
    schema = {
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
    }
    risposta = client.beta.messages.create(
        model=MODELLO,
        max_tokens=16000,
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": elenco}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError(f"Claude ha rifiutato la richiesta: {risposta.stop_details}")
    if risposta.stop_reason == "max_tokens":
        raise RuntimeError("risposta di Claude troncata (max_tokens)")
    testo = next(b.text for b in risposta.content if b.type == "text")
    categorie = {c["numero"]: c["categoria"] for c in json.loads(testo)["classificazioni"]}
    mancanti = [i for i in range(len(blocco)) if i not in categorie]
    if mancanti:
        raise RuntimeError(f"Claude non ha classificato i movimenti numero {mancanti}")
    return [categorie[i] for i in range(len(blocco))]


def main():
    try:
        movimenti = leggi_movimenti(FILE_INGRESSO)
    except (OSError, ValueError) as e:
        sys.exit(f"Errore nella lettura di {FILE_INGRESSO}: {e}")

    client = anthropic.Anthropic()
    categorie = []
    try:
        for inizio in range(0, len(movimenti), MOVIMENTI_PER_RICHIESTA):
            categorie += classifica_blocco(client, movimenti[inizio:inizio + MOVIMENTI_PER_RICHIESTA])
    except anthropic.AuthenticationError:
        sys.exit("Errore: chiave API non valida o mancante (imposta ANTHROPIC_API_KEY).")
    except anthropic.RateLimitError:
        sys.exit("Errore: limite di richieste raggiunto, riprova tra qualche minuto.")
    except anthropic.APIStatusError as e:
        sys.exit(f"Errore dall'API di Claude ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Errore: impossibile collegarsi all'API di Claude.")
    except RuntimeError as e:
        sys.exit(f"Errore: {e}")
    except TypeError as e:
        # L'SDK solleva TypeError quando non trova nessuna credenziale
        if "authentication" not in str(e):
            raise
        sys.exit("Errore: chiave API mancante (imposta ANTHROPIC_API_KEY).")

    totali = {c: Decimal("0") for c in CATEGORIE}
    for m, categoria in zip(movimenti, categorie):
        totali[categoria] += m["importo"]

    risultato = {
        "movimenti": [
            {"data": m["data"], "descrizione": m["descrizione"], "importo": float(m["importo"]), "categoria": c}
            for m, c in zip(movimenti, categorie)
        ],
        "totali": {
            c: float(t.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) for c, t in totali.items()
        },
    }
    with open(FILE_USCITA, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"Classificati {len(movimenti)} movimenti, risultato scritto in {FILE_USCITA}")
    for c, t in risultato["totali"].items():
        print(f"  {c}: {t:.2f}")


if __name__ == "__main__":
    main()
