"""Categorizza i movimenti di movimenti.csv con Claude e scrive i totali in risultato.json."""

import anyio
import csv
import json
import sys
from decimal import Decimal, ROUND_HALF_UP

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

FILE_INPUT = "movimenti.csv"
FILE_OUTPUT = "risultato.json"
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
MOVIMENTI_PER_RICHIESTA = 100
TENTATIVI = 3

ISTRUZIONI = (
    "Sei un assistente che classifica i movimenti di un conto corrente italiano. "
    "Per ogni movimento scegli esattamente una categoria tra: "
    + ", ".join(CATEGORIE)
    + ". Linee guida: 'spesa alimentare' = supermercati, alimentari, discount; "
    "'trasporti' = carburante, treni, mezzi pubblici, pedaggi, parcheggi, taxi; "
    "'casa' = affitto, mutuo, bollette (luce, gas, acqua, internet), condominio, "
    "manutenzione, arredamento e bricolage; 'svago' = ristoranti, bar, pizzerie, "
    "cinema, abbonamenti streaming, libri, viaggi, hobby; 'altro' = tutto il resto "
    "(stipendi, bonifici, commissioni, prelievi, ecc.). "
    "Restituisci una voce per ogni movimento, usando lo stesso indice ricevuto."
)

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


def converti_importo(testo):
    # "1.850,00" -> Decimal("1850.00"); "-23,40" -> Decimal("-23.40")
    pulito = testo.strip().replace(" ", "").replace(".", "").replace(",", ".")
    return Decimal(pulito)


def leggi_movimenti(percorso):
    righe = csv.reader(leggi_testo(percorso).splitlines(), delimiter=";")
    intestazione = next(righe, None)
    if intestazione is None:
        return []
    colonne = [c.strip().lower() for c in intestazione]
    try:
        i_data = colonne.index("data")
        i_descr = colonne.index("descrizione")
        i_importo = colonne.index("importo")
    except ValueError:
        sys.exit(f"Intestazione non valida in {percorso}: attesa 'data;descrizione;importo'")

    movimenti = []
    for numero, riga in enumerate(righe, start=2):
        if not any(campo.strip() for campo in riga):
            continue
        try:
            movimenti.append({
                "data": riga[i_data].strip(),
                "descrizione": riga[i_descr].strip(),
                "importo": converti_importo(riga[i_importo]),
            })
        except (IndexError, ArithmeticError):
            sys.exit(f"Riga {numero} di {percorso} non valida: {';'.join(riga)}")
    return movimenti


async def classifica_gruppo(gruppo):
    """gruppo: lista di (indice, movimento). Restituisce {indice: categoria}."""
    elenco = "\n".join(
        f"{i}\t{m['descrizione']}\t{m['importo']}" for i, m in gruppo
    )
    prompt = (
        "Classifica questi movimenti (indice, descrizione, importo in euro; "
        "negativo = uscita):\n\n" + elenco
    )
    opzioni = ClaudeAgentOptions(
        system_prompt=ISTRUZIONI,
        tools=[],
        setting_sources=[],
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    attesi = {i for i, _ in gruppo}

    for tentativo in range(1, TENTATIVI + 1):
        risultato = None
        async for messaggio in query(prompt=prompt, options=opzioni):
            if isinstance(messaggio, ResultMessage):
                risultato = messaggio
        if risultato is None or risultato.is_error or not risultato.structured_output:
            motivo = getattr(risultato, "errors", None) or getattr(risultato, "result", None)
            print(f"  tentativo {tentativo}: risposta non valida ({motivo})", file=sys.stderr)
            continue
        categorie = {}
        for voce in risultato.structured_output.get("classificazioni", []):
            if voce.get("indice") in attesi and voce.get("categoria") in CATEGORIE:
                categorie[voce["indice"]] = voce["categoria"]
        if set(categorie) == attesi:
            return categorie
        mancanti = sorted(attesi - set(categorie))
        print(f"  tentativo {tentativo}: mancano gli indici {mancanti}", file=sys.stderr)

    sys.exit("Claude non ha classificato tutti i movimenti, riprova più tardi.")


async def main():
    movimenti = leggi_movimenti(FILE_INPUT)
    print(f"Letti {len(movimenti)} movimenti da {FILE_INPUT}")

    categorie = {}
    numerati = list(enumerate(movimenti))
    for inizio in range(0, len(numerati), MOVIMENTI_PER_RICHIESTA):
        gruppo = numerati[inizio:inizio + MOVIMENTI_PER_RICHIESTA]
        print(f"Classificazione movimenti {inizio + 1}-{inizio + len(gruppo)}...")
        categorie.update(await classifica_gruppo(gruppo))

    totali = {c: Decimal("0") for c in CATEGORIE}
    for i, m in enumerate(movimenti):
        totali[categorie[i]] += m["importo"]

    centesimo = Decimal("0.01")
    risultato = {
        "movimenti": [
            {
                "data": m["data"],
                "descrizione": m["descrizione"],
                "importo": float(m["importo"]),
                "categoria": categorie[i],
            }
            for i, m in enumerate(movimenti)
        ],
        "totali": {
            c: float(t.quantize(centesimo, rounding=ROUND_HALF_UP))
            for c, t in totali.items()
        },
    }
    with open(FILE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"Risultato scritto in {FILE_OUTPUT}")
    for c, t in risultato["totali"].items():
        print(f"  {c:<17} {t:>10.2f}")


if __name__ == "__main__":
    anyio.run(main)
