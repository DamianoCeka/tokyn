"""Categorizza i movimenti di movimenti.csv con Claude e scrive risultato.json."""

import csv
import json
import sys
from decimal import Decimal, ROUND_HALF_UP

import anthropic

FILE_CSV = "movimenti.csv"
FILE_RISULTATO = "risultato.json"
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
MODELLO = "claude-opus-5-5"
MOVIMENTI_PER_RICHIESTA = 100

ISTRUZIONI = f"""Sei un assistente che classifica i movimenti di un conto corrente italiano.
Per ogni movimento ricevuto assegna esattamente una di queste categorie: {", ".join(CATEGORIE)}.

- spesa alimentare: supermercati, alimentari, discount, panetterie, macellerie, mercati.
- trasporti: carburante, treni, autobus, metro, taxi, pedaggi, parcheggi, manutenzione dell'auto.
- casa: affitto, mutuo, condominio, bollette (luce, gas, acqua, internet, telefono fisso), \
arredamento, bricolage, ferramenta, manutenzione della casa.
- svago: ristoranti, bar, pizzerie, cinema, abbonamenti streaming, libri, viaggi, sport, hobby.
- altro: tutto il resto, comprese le entrate (stipendi, rimborsi), le commissioni bancarie e i \
movimenti che non rientrano chiaramente nelle categorie precedenti.

Restituisci una voce per ogni movimento, con lo stesso indice che ti è stato dato."""

SCHEMA = {
    "type": "object",
    "properties": {
        "classificazioni": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "indice": {"type": "integer"},
                    "categoria": {"type": "string", "enum": CATEGORIE},
                },
                "required": ["indice", "categoria"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["classificazioni"],
    "additionalProperties": False,
}


def leggi_testo(percorso):
    with open(percorso, "rb") as f:
        dati = f.read()
    try:
        return dati.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dati.decode("cp1252")


def importo_da_testo(testo):
    # "1.850,00" -> Decimal("1850.00"), "-23,40" -> Decimal("-23.40")
    return Decimal(testo.strip().replace(".", "").replace(",", "."))


def leggi_movimenti(percorso):
    righe = csv.reader(leggi_testo(percorso).splitlines(), delimiter=";")
    intestazione = [campo.strip().lower() for campo in next(righe)]
    if intestazione != ["data", "descrizione", "importo"]:
        raise ValueError(f"intestazione inattesa in {percorso}: {intestazione}")
    movimenti = []
    for numero, riga in enumerate(righe, start=2):
        if not any(campo.strip() for campo in riga):
            continue
        if len(riga) != 3:
            raise ValueError(f"riga {numero} di {percorso}: attesi 3 campi, trovati {len(riga)}")
        data, descrizione, importo = riga
        movimenti.append({
            "data": data,
            "descrizione": descrizione,
            "importo": importo_da_testo(importo),
        })
    return movimenti


def classifica_gruppo(client, gruppo):
    elenco = "\n".join(
        f"{indice}. {m['descrizione']} (importo {m['importo']} euro)"
        for indice, m in enumerate(gruppo)
    )
    risposta = client.beta.messages.create(
        model=MODELLO,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": f"Movimenti da classificare:\n{elenco}"}],
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato la richiesta di classificazione")
    if risposta.stop_reason == "max_tokens":
        raise RuntimeError("risposta di Claude troncata: riduci MOVIMENTI_PER_RICHIESTA")

    testo = next(b.text for b in risposta.content if b.type == "text")
    categorie = {}
    for voce in json.loads(testo)["classificazioni"]:
        categorie[voce["indice"]] = voce["categoria"]
    mancanti = [i for i in range(len(gruppo)) if i not in categorie]
    if mancanti:
        raise RuntimeError(f"Claude non ha classificato i movimenti con indice {mancanti}")
    return [categorie[i] for i in range(len(gruppo))]


def classifica(movimenti):
    client = anthropic.Anthropic()
    categorie = []
    for inizio in range(0, len(movimenti), MOVIMENTI_PER_RICHIESTA):
        gruppo = movimenti[inizio:inizio + MOVIMENTI_PER_RICHIESTA]
        categorie.extend(classifica_gruppo(client, gruppo))
    return categorie


def main():
    movimenti = leggi_movimenti(FILE_CSV)
    categorie = classifica(movimenti) if movimenti else []

    totali = {categoria: Decimal("0") for categoria in CATEGORIE}
    for movimento, categoria in zip(movimenti, categorie):
        totali[categoria] += movimento["importo"]

    risultato = {
        "movimenti": [
            {
                "data": m["data"],
                "descrizione": m["descrizione"],
                "importo": float(m["importo"]),
                "categoria": categoria,
            }
            for m, categoria in zip(movimenti, categorie)
        ],
        "totali": {
            categoria: float(totale.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            for categoria, totale in totali.items()
        },
    }
    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"Classificati {len(movimenti)} movimenti, risultato in {FILE_RISULTATO}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, anthropic.APIError) as errore:
        sys.exit(f"Errore: {errore}")
