"""Trova i contratti in scadenza nei 30 giorni successivi a una data di riferimento
e scrive con Claude un'email di promemoria per ciascuno.

Uso: python programma.py AAAA-MM-GG
Legge contratti.csv dalla cartella corrente e scrive risultato.json.
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
CHIAMATE_PARALLELE = 4

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
    "Sei l'assistente amministrativo di un'azienda che fornisce servizi a piccole attività. "
    "Scrivi email di promemoria in italiano, cortesi e concise, per avvisare un cliente che "
    "un suo contratto sta per scadere e invitarlo a contattarci per il rinnovo. "
    "Rispondi solo con l'oggetto e il testo dell'email, senza firma con nomi inventati: "
    "chiudi con 'Cordiali saluti' seguito da una riga vuota."
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
        for numero, riga in enumerate(lettore, start=2):
            riga = {k: (v or "").strip() for k, v in riga.items() if k}
            if not any(riga.values()):
                continue
            try:
                riga["_data"] = date.fromisoformat(riga["scadenza"])
            except ValueError:
                print(f"Attenzione: riga {numero} ignorata, scadenza non valida: "
                      f"{riga['scadenza']!r}", file=sys.stderr)
                continue
            contratti.append(riga)
    return contratti


def in_scadenza(contratti: list[dict], riferimento: date) -> list[dict]:
    fine = riferimento + timedelta(days=GIORNI_FINESTRA)
    scelti = [c for c in contratti if riferimento <= c["_data"] <= fine]
    return sorted(scelti, key=lambda c: (c["_data"], c["cliente"], c["servizio"]))


def prompt_email(c: dict, giorni: int) -> str:
    quando = "oggi" if giorni == 0 else ("domani" if giorni == 1 else f"tra {giorni} giorni")
    return (
        "Scrivi l'email di promemoria per questo contratto.\n"
        f"- Cliente (rivolgiti al cliente con esattamente questo nome): {c['cliente']}\n"
        f"- Servizio in scadenza (citalo con esattamente questo nome): {c['servizio']}\n"
        f"- Data di scadenza: {data_in_italiano(c['_data'])}\n"
        f"- Il contratto scade {quando}.\n"
        "Il testo deve iniziare con 'Gentile " + c["cliente"] + ",'. "
        "L'oggetto deve citare il servizio e la data di scadenza."
    )


def email_valida(email, c: dict) -> bool:
    if not isinstance(email, dict):
        return False
    oggetto, testo = email.get("oggetto"), email.get("testo")
    if not (isinstance(oggetto, str) and oggetto.strip() and isinstance(testo, str)):
        return False
    return c["cliente"].lower() in testo.lower() and c["servizio"].lower() in testo.lower()


async def chiedi_a_claude(prompt: str):
    opzioni = ClaudeAgentOptions(
        system_prompt=ISTRUZIONI,
        tools=[],
        max_turns=3,
        output_format={"type": "json_schema", "schema": SCHEMA_EMAIL},
        setting_sources=[],
    )
    risultato = None
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            if messaggio.is_error:
                raise RuntimeError(f"Claude ha restituito un errore: {messaggio.subtype} "
                                   f"{messaggio.errors or messaggio.result or ''}")
            risultato = messaggio.structured_output
            if risultato is None and messaggio.result:
                try:
                    risultato = json.loads(messaggio.result)
                except json.JSONDecodeError:
                    pass
    return risultato


async def scrivi_email(c: dict, giorni: int, limite: asyncio.Semaphore) -> dict:
    prompt = prompt_email(c, giorni)
    ultimo_errore = "risposta non valida"
    async with limite:
        for _ in range(TENTATIVI):
            try:
                email = await chiedi_a_claude(prompt)
            except Exception as e:  # errore di rete/CLI: si riprova
                ultimo_errore = str(e)
                continue
            if email_valida(email, c):
                return {"oggetto": email["oggetto"].strip(), "testo": email["testo"].strip()}
            ultimo_errore = f"l'email non cita cliente e servizio: {email!r}"
    raise RuntimeError(f"Impossibile scrivere l'email per {c['cliente']} "
                       f"({c['servizio']}): {ultimo_errore}")


async def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Uso: python programma.py AAAA-MM-GG")
    try:
        riferimento = date.fromisoformat(sys.argv[1])
    except ValueError:
        sys.exit(f"Errore: data di riferimento non valida: {sys.argv[1]!r} (formato AAAA-MM-GG)")

    try:
        contratti = leggi_contratti(FILE_CONTRATTI)
    except FileNotFoundError:
        sys.exit(f"Errore: {FILE_CONTRATTI} non trovato nella cartella corrente")

    scelti = in_scadenza(contratti, riferimento)
    print(f"Contratti in scadenza tra il {riferimento} e il "
          f"{riferimento + timedelta(days=GIORNI_FINESTRA)}: {len(scelti)}")

    limite = asyncio.Semaphore(CHIAMATE_PARALLELE)
    giorni = [(c["_data"] - riferimento).days for c in scelti]
    email = await asyncio.gather(*(scrivi_email(c, g, limite) for c, g in zip(scelti, giorni)))

    voci = [
        {"cliente": c["cliente"], "servizio": c["servizio"], "scadenza": c["scadenza"],
         "giorni_mancanti": g, **e}
        for c, g, e in zip(scelti, giorni, email)
    ]
    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump({"in_scadenza": voci}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Scritto {FILE_RISULTATO}")


if __name__ == "__main__":
    asyncio.run(main())
