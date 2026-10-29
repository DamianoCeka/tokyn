"""Trova i contratti in scadenza e scrive le email di promemoria con Claude.

Uso: python programma.py AAAA-MM-GG
Legge contratti.csv dalla cartella corrente e scrive risultato.json.
"""
import asyncio
import csv
import json
import sys
from datetime import date, datetime

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

FINESTRA_GIORNI = 30
MAX_PARALLELE = 4
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

SYSTEM_PROMPT = (
    "Sei l'assistente che scrive i promemoria di scadenza contratto per la nostra azienda. "
    "Scrivi in italiano, con tono cortese e professionale, email brevi. "
    "Rispondi solo con l'oggetto e il testo dell'email, senza altri commenti."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "oggetto": {"type": "string"},
        "testo": {"type": "string"},
    },
    "required": ["oggetto", "testo"],
    "additionalProperties": False,
}


def data_italiana(d: date) -> str:
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


def leggi_contratti(percorso: str) -> list[dict]:
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        righe = list(csv.DictReader(f))
    contratti = []
    for n, riga in enumerate(righe, start=2):
        try:
            scadenza = datetime.strptime(riga["scadenza"].strip(), "%Y-%m-%d").date()
        except (KeyError, AttributeError, ValueError):
            print(f"Riga {n} ignorata: scadenza non valida ({riga.get('scadenza')!r})", file=sys.stderr)
            continue
        contratti.append({
            "cliente": riga["cliente"],
            "servizio": riga["servizio"],
            "scadenza": riga["scadenza"].strip(),
            "_data": scadenza,
        })
    return contratti


async def scrivi_email(contratto: dict) -> dict:
    prompt = (
        "Scrivi un'email di promemoria per un contratto in scadenza.\n"
        f"Cliente: {contratto['cliente']}\n"
        f"Servizio in scadenza: {contratto['servizio']}\n"
        f"Data di scadenza: {data_italiana(contratto['_data'])}\n"
        f"Giorni mancanti alla scadenza: {contratto['giorni_mancanti']}\n\n"
        "Requisiti: il testo si rivolge al cliente per nome (es. «Gentile <cliente>,»), cita il "
        "servizio in scadenza e la data, invita a contattarci per il rinnovo e termina con una firma "
        "generica («Il team di assistenza clienti»). Non inventare prezzi, recapiti o condizioni. "
        "L'oggetto è una riga sola che cita servizio e data."
    )
    opzioni = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        max_turns=2,
        setting_sources=[],
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    esito = None
    async for msg in query(prompt=prompt, options=opzioni):
        if isinstance(msg, ResultMessage):
            esito = msg
    if esito is None or esito.is_error or not isinstance(esito.structured_output, dict):
        raise RuntimeError(
            f"Nessuna email generata per {contratto['cliente']} / {contratto['servizio']}: "
            f"{esito.errors or esito.result if esito else 'nessun risultato'}"
        )
    return {"oggetto": esito.structured_output["oggetto"], "testo": esito.structured_output["testo"]}


async def main(riferimento: date) -> None:
    in_scadenza = []
    for c in leggi_contratti("contratti.csv"):
        giorni = (c["_data"] - riferimento).days
        if 0 <= giorni <= FINESTRA_GIORNI:
            c["giorni_mancanti"] = giorni
            in_scadenza.append(c)
    in_scadenza.sort(key=lambda c: c["_data"])  # sort stabile: a parità, ordine del file

    limite = asyncio.Semaphore(MAX_PARALLELE)

    async def con_limite(c):
        async with limite:
            return await scrivi_email(c)

    email = await asyncio.gather(*(con_limite(c) for c in in_scadenza))

    risultato = {"in_scadenza": [
        {
            "cliente": c["cliente"],
            "servizio": c["servizio"],
            "scadenza": c["scadenza"],
            "giorni_mancanti": c["giorni_mancanti"],
            **e,
        }
        for c, e in zip(in_scadenza, email)
    ]}
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"{len(in_scadenza)} contratti in scadenza scritti in risultato.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python programma.py AAAA-MM-GG")
    try:
        data_rif = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    except ValueError:
        sys.exit(f"Data di riferimento non valida: {sys.argv[1]!r} (formato AAAA-MM-GG)")
    asyncio.run(main(data_rif))
