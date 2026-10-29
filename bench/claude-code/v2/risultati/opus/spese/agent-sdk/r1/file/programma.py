"""Categorizza i movimenti di movimenti.csv con Claude e scrive i totali in risultato.json."""

import asyncio
import csv
import json
import sys
from decimal import Decimal, ROUND_HALF_UP

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

FILE_INPUT = "movimenti.csv"
FILE_OUTPUT = "risultato.json"
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
TENTATIVI = 3


def leggi_movimenti(percorso):
    movimenti = []
    with open(percorso, encoding="utf-8-sig", newline="") as f:
        lettore = csv.DictReader(f, delimiter=";")
        for riga in lettore:
            if not riga.get("data"):
                continue
            testo = riga["importo"].strip().replace(".", "").replace(",", ".")
            movimenti.append({
                "data": riga["data"].strip(),
                "descrizione": riga["descrizione"].strip(),
                "importo": Decimal(testo),
            })
    return movimenti


async def classifica(movimenti):
    elenco = "\n".join(
        f"{i}. {m['descrizione']} (importo {m['importo']})" for i, m in enumerate(movimenti)
    )
    prompt = (
        "Assegna a ciascuno di questi movimenti bancari italiani una categoria tra: "
        + ", ".join(CATEGORIE)
        + ".\n"
        "- spesa alimentare: supermercati e negozi di alimentari\n"
        "- trasporti: treni, mezzi pubblici, carburante, pedaggi, taxi, parcheggi\n"
        "- casa: utenze, affitto, condominio, arredamento, bricolage, manutenzione\n"
        "- svago: ristoranti, bar, abbonamenti streaming, cinema, libri, viaggi, hobby\n"
        "- altro: tutto il resto (stipendi, commissioni, bonifici, ecc.)\n\n"
        f"Restituisci esattamente {len(movimenti)} categorie, una per movimento, "
        "nello stesso ordine dell'elenco.\n\n"
        f"Movimenti:\n{elenco}"
    )
    schema = {
        "type": "object",
        "properties": {
            "categorie": {
                "type": "array",
                "items": {"type": "string", "enum": CATEGORIE},
            }
        },
        "required": ["categorie"],
        "additionalProperties": False,
    }
    opzioni = ClaudeAgentOptions(
        model="claude-opus-5-5",
        tools=[],
        setting_sources=[],
        effort="low",
        output_format={"type": "json_schema", "schema": schema},
    )

    risultato = None
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            risultato = messaggio
    if risultato is None or risultato.is_error or risultato.structured_output is None:
        dettaglio = risultato.errors or risultato.result if risultato else "nessuna risposta"
        raise RuntimeError(f"Claude non ha restituito le categorie: {dettaglio}")

    categorie = risultato.structured_output.get("categorie", [])
    if len(categorie) != len(movimenti) or any(c not in CATEGORIE for c in categorie):
        raise RuntimeError(
            f"Risposta non valida: {len(categorie)} categorie per {len(movimenti)} movimenti"
        )
    return categorie


async def classifica_con_tentativi(movimenti):
    for tentativo in range(1, TENTATIVI + 1):
        try:
            return await classifica(movimenti)
        except RuntimeError as errore:
            if tentativo == TENTATIVI:
                raise
            print(f"Tentativo {tentativo} fallito ({errore}), riprovo...", file=sys.stderr)


def main():
    movimenti = leggi_movimenti(FILE_INPUT)
    categorie = asyncio.run(classifica_con_tentativi(movimenti)) if movimenti else []

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
    print(f"Classificati {len(movimenti)} movimenti, risultato in {FILE_OUTPUT}")


if __name__ == "__main__":
    main()
