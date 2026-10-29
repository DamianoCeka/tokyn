"""Categorizza i movimenti di movimenti.csv con Claude e scrive risultato.json."""

import asyncio
import csv
import json
import sys
from decimal import Decimal, InvalidOperation

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

FILE_INGRESSO = "movimenti.csv"
FILE_USCITA = "risultato.json"
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
TENTATIVI = 3

SCHEMA = {
    "type": "object",
    "properties": {
        "movimenti": {
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
    "required": ["movimenti"],
    "additionalProperties": False,
}


def leggi_movimenti(percorso):
    """Legge il CSV e restituisce una lista di (data, descrizione, importo Decimal)."""
    movimenti = []
    with open(percorso, encoding="utf-8-sig", newline="") as f:
        righe = csv.reader(f, delimiter=";")
        intestazione = next(righe, None)
        if intestazione is None:
            return movimenti
        for n, riga in enumerate(righe, start=2):
            if not any(campo.strip() for campo in riga):
                continue
            if len(riga) != 3:
                raise ValueError(f"riga {n}: attesi 3 campi, trovati {len(riga)}")
            data, descrizione, importo = (campo.strip() for campo in riga)
            # "1.850,00" -> "1850.00"
            testo = importo.replace(".", "").replace(",", ".")
            try:
                valore = Decimal(testo)
            except InvalidOperation:
                raise ValueError(f"riga {n}: importo non valido {importo!r}") from None
            movimenti.append((data, descrizione, valore))
    return movimenti


def costruisci_prompt(movimenti):
    elenco = "\n".join(
        f"{i}. {descrizione} | importo: {importo}"
        for i, (_, descrizione, importo) in enumerate(movimenti, start=1)
    )
    return (
        "Sei un assistente che classifica i movimenti di un conto corrente italiano.\n"
        "Assegna a ciascun movimento esattamente una di queste categorie:\n"
        "- spesa alimentare: supermercati, alimentari, discount (Esselunga, Lidl, Carrefour, Coop...)\n"
        "- trasporti: treni, mezzi pubblici, carburante, pedaggi, taxi, parcheggi, auto\n"
        "- casa: utenze (luce, gas, acqua, internet), affitto, condominio, bricolage, arredamento\n"
        "- svago: ristoranti, bar, pizzerie, abbonamenti streaming, libri, cinema, viaggi, hobby\n"
        "- altro: tutto ciò che non rientra chiaramente nelle categorie precedenti, "
        "comprese entrate (stipendi, rimborsi), commissioni bancarie e trasferimenti\n\n"
        "Rispondi con un elemento per ogni movimento, usando il suo numero.\n\n"
        f"Movimenti:\n{elenco}"
    )


async def chiedi_categorie(movimenti):
    """Chiede a Claude le categorie; restituisce una lista allineata ai movimenti."""
    opzioni = ClaudeAgentOptions(
        model="claude-opus-5-5",
        tools=[],  # serve solo il ragionamento, nessuno strumento
        setting_sources=[],  # ignora impostazioni e CLAUDE.md della macchina
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    risultato = None
    async for messaggio in query(prompt=costruisci_prompt(movimenti), options=opzioni):
        if isinstance(messaggio, ResultMessage):
            risultato = messaggio
    if risultato is None:
        raise RuntimeError("nessuna risposta da Claude")
    if risultato.is_error or risultato.structured_output is None:
        dettaglio = risultato.errors or risultato.result or risultato.subtype
        raise RuntimeError(f"Claude non ha restituito le categorie: {dettaglio}")

    per_numero = {}
    for voce in risultato.structured_output.get("movimenti", []):
        numero, categoria = voce.get("numero"), voce.get("categoria")
        if categoria not in CATEGORIE:
            raise RuntimeError(f"categoria non valida per il movimento {numero}: {categoria!r}")
        per_numero[numero] = categoria
    mancanti = [i for i in range(1, len(movimenti) + 1) if i not in per_numero]
    if mancanti:
        raise RuntimeError(f"categoria mancante per i movimenti {mancanti}")
    return [per_numero[i] for i in range(1, len(movimenti) + 1)]


async def categorizza(movimenti):
    for tentativo in range(1, TENTATIVI + 1):
        try:
            return await chiedi_categorie(movimenti)
        except RuntimeError as errore:
            if tentativo == TENTATIVI:
                raise
            print(f"Tentativo {tentativo} fallito ({errore}), riprovo...", file=sys.stderr)


def main():
    try:
        movimenti = leggi_movimenti(FILE_INGRESSO)
    except FileNotFoundError:
        sys.exit(f"File {FILE_INGRESSO} non trovato nella cartella corrente.")
    except ValueError as errore:
        sys.exit(f"Errore in {FILE_INGRESSO}: {errore}")

    categorie = asyncio.run(categorizza(movimenti)) if movimenti else []

    totali = {categoria: Decimal("0") for categoria in CATEGORIE}
    for (_, _, importo), categoria in zip(movimenti, categorie):
        totali[categoria] += importo

    risultato = {
        "movimenti": [
            {"data": data, "descrizione": descrizione, "importo": float(importo), "categoria": categoria}
            for (data, descrizione, importo), categoria in zip(movimenti, categorie)
        ],
        "totali": {
            categoria: float(totale.quantize(Decimal("0.01"))) for categoria, totale in totali.items()
        },
    }
    with open(FILE_USCITA, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"Scritto {FILE_USCITA}: {len(movimenti)} movimenti categorizzati.")


if __name__ == "__main__":
    main()
