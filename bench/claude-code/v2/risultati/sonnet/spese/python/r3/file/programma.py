import csv
import json
import sys
from decimal import Decimal, InvalidOperation

import anthropic

MODELLO = "claude-opus-5-5"
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
DIMENSIONE_BLOCCO = 100

ISTRUZIONI = (
    "Assegni una categoria ai movimenti di un conto corrente italiano. "
    "Le categorie ammesse sono: " + ", ".join(CATEGORIE) + ". "
    "spesa alimentare: supermercati e alimentari. trasporti: treni, bus, taxi, carburante, pedaggi. "
    "casa: affitto, mutuo, utenze (luce, gas, acqua, internet), arredamento e bricolage. "
    "svago: ristoranti, bar, abbonamenti di intrattenimento, libri, cinema, viaggi. "
    "altro: tutto il resto (stipendi, commissioni, bonifici, salute, ecc.). "
    "Rispondi con una categoria per ogni movimento, usando l'id ricevuto."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "categorie": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "categoria": {"type": "string", "enum": CATEGORIE},
                },
                "required": ["id", "categoria"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["categorie"],
    "additionalProperties": False,
}


def leggi_movimenti(percorso):
    movimenti = []
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        lettore = csv.reader(f, delimiter=";")
        next(lettore, None)  # intestazione
        for numero, riga in enumerate(lettore, start=2):
            if not any(campo.strip() for campo in riga):
                continue
            if len(riga) != 3:
                raise ValueError(f"riga {numero}: attesi 3 campi, trovati {len(riga)}")
            data, descrizione, importo = (campo.strip() for campo in riga)
            try:
                valore = Decimal(importo.replace(".", "").replace(",", "."))
            except InvalidOperation:
                raise ValueError(f"riga {numero}: importo non valido: {importo!r}")
            movimenti.append({"data": data, "descrizione": descrizione, "importo": valore})
    return movimenti


def classifica_blocco(client, blocco):
    """blocco: lista di (id, movimento). Restituisce {id: categoria}."""
    elenco = [
        {"id": i, "descrizione": m["descrizione"], "importo": str(m["importo"])}
        for i, m in blocco
    ]
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=16000,
        system=ISTRUZIONI,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": json.dumps(elenco, ensure_ascii=False)}],
    )
    if risposta.stop_reason != "end_turn":
        raise RuntimeError(f"risposta non completa (stop_reason={risposta.stop_reason})")
    testo = "".join(b.text for b in risposta.content if b.type == "text")
    risultato = {}
    for voce in json.loads(testo)["categorie"]:
        if voce["categoria"] in CATEGORIE:
            risultato[voce["id"]] = voce["categoria"]
    attesi = {i for i, _ in blocco}
    if set(risultato) != attesi:
        raise RuntimeError(f"id mancanti o inattesi nella risposta: {sorted(attesi ^ set(risultato))}")
    return risultato


def classifica(client, movimenti):
    categorie = {}
    indicizzati = list(enumerate(movimenti))
    for inizio in range(0, len(indicizzati), DIMENSIONE_BLOCCO):
        categorie.update(classifica_blocco(client, indicizzati[inizio:inizio + DIMENSIONE_BLOCCO]))
    return [categorie[i] for i in range(len(movimenti))]


def main():
    movimenti = leggi_movimenti("movimenti.csv")
    client = anthropic.Anthropic()
    categorie = classifica(client, movimenti)

    totali = {c: Decimal("0") for c in CATEGORIE}
    for m, c in zip(movimenti, categorie):
        totali[c] += m["importo"]

    risultato = {
        "movimenti": [
            {
                "data": m["data"],
                "descrizione": m["descrizione"],
                "importo": float(m["importo"]),
                "categoria": c,
            }
            for m, c in zip(movimenti, categorie)
        ],
        "totali": {c: float(round(t, 2)) for c, t in totali.items()},
    }
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"Scritto risultato.json ({len(movimenti)} movimenti)")


if __name__ == "__main__":
    try:
        main()
    except (anthropic.AuthenticationError, TypeError):
        # TypeError: l'SDK non trova nessuna credenziale
        sys.exit("Chiave API mancante o non valida: imposta ANTHROPIC_API_KEY.")
    except (anthropic.APIError, OSError, ValueError, RuntimeError) as e:
        sys.exit(f"Errore: {e}")
