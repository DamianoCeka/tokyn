"""Promemoria di scadenza contratti.

Uso: python programma.py AAAA-MM-GG
Legge contratti.csv dalla cartella corrente, trova i contratti che scadono tra la
data di riferimento e i 30 giorni successivi (estremi compresi), fa scrivere a Claude
un'email di promemoria per ciascuno e salva tutto in risultato.json.
"""
import asyncio
import csv
import json
import sys
from datetime import date, timedelta

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

MODELLO = "claude-opus-5-5"
FINESTRA_GIORNI = 30
MAX_PARALLELE = 4

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

SYSTEM_PROMPT = (
    "Scrivi email di promemoria di scadenza contrattuale, in italiano, per conto "
    "dell'azienda che fornisce il servizio. Tono cordiale e professionale, breve "
    "(massimo 120 parole). Il testo deve iniziare con 'Gentile <nome del cliente>,', "
    "citare il servizio in scadenza e la data di scadenza, invitare a contattarci per "
    "il rinnovo e chiudersi con un saluto. Non inventare prezzi, recapiti, nomi di "
    "persone o condizioni. Non usare segnaposto come [Nome] o [Azienda]. "
    "L'oggetto è una sola riga, senza prefissi come 'Oggetto:'."
)

SCHEMA = {
    "type": "object",
    "properties": {"oggetto": {"type": "string"}, "testo": {"type": "string"}},
    "required": ["oggetto", "testo"],
    "additionalProperties": False,
}


def data_italiana(d: date) -> str:
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


def leggi_contratti(percorso: str, riferimento: date) -> list[dict]:
    fine = riferimento + timedelta(days=FINESTRA_GIORNI)
    trovati = []
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        for n, riga in enumerate(csv.DictReader(f), start=2):
            try:
                scadenza = date.fromisoformat(riga["scadenza"].strip())
            except (ValueError, KeyError, AttributeError):
                print(f"Riga {n} ignorata: scadenza non valida", file=sys.stderr)
                continue
            if riferimento <= scadenza <= fine:
                trovati.append({
                    "cliente": riga["cliente"],
                    "servizio": riga["servizio"],
                    "scadenza": riga["scadenza"],
                    "giorni_mancanti": (scadenza - riferimento).days,
                    "_data": scadenza,
                })
    trovati.sort(key=lambda c: c["_data"])  # ordinamento stabile
    return trovati


async def scrivi_email(contratto: dict) -> dict:
    scadenza = contratto["_data"]
    giorni = contratto["giorni_mancanti"]
    quando = "oggi" if giorni == 0 else f"tra {giorni} giorni"
    prompt = (
        f"Cliente: {contratto['cliente']}\n"
        f"Servizio in scadenza: {contratto['servizio']}\n"
        f"Data di scadenza: {data_italiana(scadenza)} ({quando})\n\n"
        "Scrivi l'oggetto e il testo dell'email di promemoria. L'oggetto deve "
        "citare il servizio e la data di scadenza (giorno e mese)."
    )
    opzioni = ClaudeAgentOptions(
        model=MODELLO,
        system_prompt=SYSTEM_PROMPT,
        tools=[],
        max_turns=3,
        setting_sources=None,
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    esito = None
    async for msg in query(prompt=prompt, options=opzioni):
        if isinstance(msg, ResultMessage):
            esito = msg
    if esito is None or esito.is_error:
        raise RuntimeError(f"Claude non ha risposto per {contratto['cliente']}: {esito}")
    dati = esito.structured_output
    if dati is None:
        dati = json.loads(esito.result)
    return {"oggetto": dati["oggetto"].strip(), "testo": dati["testo"].strip()}


async def main(riferimento: date) -> None:
    contratti = leggi_contratti("contratti.csv", riferimento)
    semaforo = asyncio.Semaphore(MAX_PARALLELE)

    async def uno(c):
        async with semaforo:
            return await scrivi_email(c)

    email = await asyncio.gather(*(uno(c) for c in contratti))
    risultato = []
    for c, e in zip(contratti, email):
        voce = {k: v for k, v in c.items() if not k.startswith("_")}
        voce.update(e)
        risultato.append(voce)
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump({"in_scadenza": risultato}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{len(risultato)} contratti in scadenza scritti in risultato.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python programma.py AAAA-MM-GG")
    try:
        rif = date.fromisoformat(sys.argv[1])
    except ValueError:
        sys.exit("Data di riferimento non valida: usare il formato AAAA-MM-GG")
    asyncio.run(main(rif))
