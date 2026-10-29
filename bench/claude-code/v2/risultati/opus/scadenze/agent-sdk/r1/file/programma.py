"""Trova i contratti in scadenza nei 30 giorni successivi a una data di riferimento
e, per ognuno, fa scrivere a Claude un'email di promemoria.

Uso (dalla cartella che contiene contratti.csv):
    python programma.py AAAA-MM-GG
"""

import asyncio
import csv
import json
import sys
from datetime import date, timedelta

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

FILE_CONTRATTI = "contratti.csv"
FILE_RISULTATO = "risultato.json"
GIORNI_FINESTRA = 30
TENTATIVI = 3
RICHIESTE_IN_PARALLELO = 4

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

SCHEMA_EMAIL = {
    "type": "object",
    "properties": {
        "oggetto": {"type": "string"},
        "testo": {"type": "string"},
    },
    "required": ["oggetto", "testo"],
    "additionalProperties": False,
}

ISTRUZIONI = (
    "Sei l'assistente amministrativo di un'azienda di servizi. Scrivi email di "
    "promemoria per contratti in scadenza, in italiano, con tono cortese e "
    "professionale. Non inventare prezzi, condizioni o nomi di persona; non "
    "aggiungere segnaposto tra parentesi quadre. Firma come \"Il nostro staff\"."
)


def data_in_italiano(d: date) -> str:
    giorno = "1º" if d.day == 1 else str(d.day)
    return f"{giorno} {MESI[d.month - 1]} {d.year}"


def leggi_contratti(percorso: str) -> list[dict]:
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        lettore = csv.DictReader(f)
        mancanti = {"cliente", "servizio", "scadenza"} - set(lettore.fieldnames or [])
        if mancanti:
            sys.exit(f"Errore: in {percorso} mancano le colonne {', '.join(sorted(mancanti))}")
        contratti = []
        for riga in lettore:
            if not any((v or "").strip() for v in riga.values()):
                continue  # riga vuota
            contratti.append({k: (v or "").strip() for k, v in riga.items() if k})
        return contratti


def in_scadenza(contratti: list[dict], riferimento: date) -> list[dict]:
    limite = riferimento + timedelta(days=GIORNI_FINESTRA)
    trovati = []
    for c in contratti:
        try:
            scadenza = date.fromisoformat(c["scadenza"])
        except ValueError:
            print(f"Attenzione: scadenza non valida per {c['cliente']!r} "
                  f"({c['scadenza']!r}), riga ignorata", file=sys.stderr)
            continue
        if riferimento <= scadenza <= limite:
            trovati.append({**c, "_data": scadenza,
                            "giorni_mancanti": (scadenza - riferimento).days})
    trovati.sort(key=lambda c: (c["_data"], c["cliente"], c["servizio"]))
    return trovati


def richiesta_email(c: dict) -> str:
    giorni = c["giorni_mancanti"]
    quando = "oggi" if giorni == 0 else ("domani" if giorni == 1 else f"tra {giorni} giorni")
    return (
        "Scrivi un'email di promemoria per questo contratto in scadenza.\n"
        f"- Cliente: {c['cliente']}\n"
        f"- Servizio: {c['servizio']}\n"
        f"- Data di scadenza: {data_in_italiano(c['_data'])} ({quando})\n\n"
        "Requisiti:\n"
        f"- Il testo inizia con \"Gentile {c['cliente']},\" rivolgendosi al cliente per nome.\n"
        f"- Il testo cita esplicitamente il servizio \"{c['servizio']}\" e la data di scadenza.\n"
        "- Invita il cliente a contattarci per il rinnovo.\n"
        "- L'oggetto è breve e indica il servizio e la data di scadenza.\n"
        "Rispondi solo con oggetto e testo dell'email."
    )


def problemi_email(email: dict, c: dict) -> list[str]:
    problemi = []
    testo = email.get("testo", "")
    if not email.get("oggetto", "").strip():
        problemi.append("l'oggetto è vuoto")
    if c["cliente"].lower() not in testo.lower():
        problemi.append(f"il testo non si rivolge al cliente per nome ({c['cliente']})")
    if c["servizio"].lower() not in testo.lower():
        problemi.append(f"il testo non cita il servizio \"{c['servizio']}\"")
    return problemi


async def chiedi_a_claude(prompt: str) -> dict:
    opzioni = ClaudeAgentOptions(
        system_prompt=ISTRUZIONI,
        tools=[],
        setting_sources=[],
        output_format={"type": "json_schema", "schema": SCHEMA_EMAIL},
    )
    risultato = None
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            risultato = messaggio
    if risultato is None:
        raise RuntimeError("nessuna risposta da Claude")
    if risultato.is_error or not isinstance(risultato.structured_output, dict):
        dettagli = risultato.errors or risultato.result or risultato.subtype
        raise RuntimeError(f"risposta non valida da Claude: {dettagli}")
    return risultato.structured_output


async def scrivi_email(c: dict, semaforo: asyncio.Semaphore) -> dict:
    prompt = richiesta_email(c)
    ultimo_errore = ""
    async with semaforo:
        for _ in range(TENTATIVI):
            try:
                email = await chiedi_a_claude(prompt)
            except Exception as e:  # errori di rete/API: riprova
                ultimo_errore = str(e)
                continue
            problemi = problemi_email(email, c)
            if not problemi:
                return {"oggetto": email["oggetto"].strip(), "testo": email["testo"].strip()}
            ultimo_errore = "; ".join(problemi)
            prompt = richiesta_email(c) + "\n\nAttenzione: " + ultimo_errore + "."
    raise RuntimeError(f"email per {c['cliente']} ({c['servizio']}) non generata: {ultimo_errore}")


async def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Uso: python programma.py AAAA-MM-GG")
    try:
        riferimento = date.fromisoformat(sys.argv[1])
    except ValueError:
        sys.exit(f"Errore: data non valida {sys.argv[1]!r}, usa il formato AAAA-MM-GG")
    try:
        contratti = leggi_contratti(FILE_CONTRATTI)
    except FileNotFoundError:
        sys.exit(f"Errore: {FILE_CONTRATTI} non trovato nella cartella corrente")

    trovati = in_scadenza(contratti, riferimento)
    semaforo = asyncio.Semaphore(RICHIESTE_IN_PARALLELO)
    email = await asyncio.gather(*(scrivi_email(c, semaforo) for c in trovati))

    risultato = {"in_scadenza": [
        {"cliente": c["cliente"], "servizio": c["servizio"], "scadenza": c["scadenza"],
         "giorni_mancanti": c["giorni_mancanti"], **e}
        for c, e in zip(trovati, email)
    ]}
    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(f"{len(trovati)} contratti in scadenza tra il {data_in_italiano(riferimento)} "
          f"e il {data_in_italiano(riferimento + timedelta(days=GIORNI_FINESTRA))}: "
          f"scritto {FILE_RISULTATO}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        sys.exit(f"Errore: {e}")
