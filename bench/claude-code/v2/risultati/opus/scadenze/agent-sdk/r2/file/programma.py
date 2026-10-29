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
FINESTRA_GIORNI = 30
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
    "Sei l'assistente amministrativo di un'azienda che fornisce servizi a piccole attività. "
    "Scrivi email di promemoria per contratti in scadenza: in italiano, cordiali, professionali "
    "e brevi (massimo 120 parole nel testo). Rispondi solo con l'oggetto e il testo richiesti."
)


def data_in_italiano(d: date) -> str:
    giorno = "1º" if d.day == 1 else str(d.day)
    return f"{giorno} {MESI[d.month - 1]} {d.year}"


def leggi_contratti_in_scadenza(riferimento: date) -> list[dict]:
    limite = riferimento + timedelta(days=FINESTRA_GIORNI)
    in_scadenza = []
    with open(FILE_CONTRATTI, newline="", encoding="utf-8-sig") as f:
        for n_riga, riga in enumerate(csv.DictReader(f), start=2):
            testo_scadenza = (riga.get("scadenza") or "").strip()
            try:
                scadenza = date.fromisoformat(testo_scadenza)
            except ValueError:
                print(f"Riga {n_riga}: scadenza non valida ({testo_scadenza!r}), la salto.",
                      file=sys.stderr)
                continue
            if riferimento <= scadenza <= limite:
                in_scadenza.append({
                    "cliente": riga["cliente"].strip(),
                    "servizio": riga["servizio"].strip(),
                    "scadenza": testo_scadenza,
                    "giorni_mancanti": (scadenza - riferimento).days,
                })
    # sorted è stabile: a parità di scadenza resta l'ordine del file
    return sorted(in_scadenza, key=lambda c: c["scadenza"])


def email_valida(email: dict, contratto: dict) -> bool:
    testo = email["testo"].lower()
    return (contratto["cliente"].lower() in testo
            and contratto["servizio"].lower() in testo
            and bool(email["oggetto"].strip()))


async def scrivi_email(contratto: dict) -> dict:
    scadenza = date.fromisoformat(contratto["scadenza"])
    giorni = contratto["giorni_mancanti"]
    quando = ("oggi" if giorni == 0 else "domani" if giorni == 1
              else f"tra {giorni} giorni")
    prompt = (
        f"Scrivi un'email di promemoria per questo contratto in scadenza.\n"
        f"- Cliente: {contratto['cliente']}\n"
        f"- Servizio: {contratto['servizio']}\n"
        f"- Data di scadenza: {data_in_italiano(scadenza)} ({quando})\n\n"
        f"Requisiti:\n"
        f"- Il testo deve iniziare con \"Gentile {contratto['cliente']},\" "
        f"rivolgendosi al cliente esattamente con questo nome.\n"
        f"- Il testo deve citare il servizio con il nome esatto \"{contratto['servizio']}\" "
        f"e la data di scadenza.\n"
        f"- Invita il cliente a contattarci per il rinnovo.\n"
        f"- L'oggetto è una riga breve che indica il servizio e la data di scadenza "
        f"(giorno e mese in lettere, per esempio \"12 novembre\").\n"
        f"- Firma come \"Il team clienti\". Non usare segnaposto tra parentesi."
    )
    opzioni = ClaudeAgentOptions(
        system_prompt=ISTRUZIONI,
        tools=[],
        setting_sources=[],
        max_turns=3,
        output_format={"type": "json_schema", "schema": SCHEMA_EMAIL},
    )

    ultimo_errore = "nessuna risposta"
    for _ in range(TENTATIVI):
        email = None
        async for messaggio in query(prompt=prompt, options=opzioni):
            if isinstance(messaggio, ResultMessage):
                if messaggio.is_error:
                    ultimo_errore = f"errore di Claude: {messaggio.result or messaggio.subtype}"
                else:
                    email = messaggio.structured_output
        if not isinstance(email, dict) or not {"oggetto", "testo"} <= email.keys():
            if email is not None:
                ultimo_errore = f"risposta in formato inatteso: {email!r}"
            continue
        if email_valida(email, contratto):
            return {"oggetto": email["oggetto"].strip(), "testo": email["testo"].strip()}
        ultimo_errore = "l'email non cita il nome del cliente o il servizio"
    raise RuntimeError(f"{contratto['cliente']} / {contratto['servizio']}: {ultimo_errore}")


async def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python programma.py AAAA-MM-GG", file=sys.stderr)
        return 2
    try:
        riferimento = date.fromisoformat(sys.argv[1])
    except ValueError:
        print(f"Data non valida: {sys.argv[1]!r} (formato atteso AAAA-MM-GG)", file=sys.stderr)
        return 2
    try:
        contratti = leggi_contratti_in_scadenza(riferimento)
    except FileNotFoundError:
        print(f"Non trovo {FILE_CONTRATTI} nella cartella corrente.", file=sys.stderr)
        return 1

    limite = asyncio.Semaphore(RICHIESTE_IN_PARALLELO)

    async def con_limite(contratto: dict) -> dict:
        async with limite:
            return {**contratto, **await scrivi_email(contratto)}

    try:
        risultati = await asyncio.gather(*(con_limite(c) for c in contratti))
    except Exception as errore:
        print(f"Impossibile generare le email: {errore}", file=sys.stderr)
        return 1

    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump({"in_scadenza": risultati}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{len(risultati)} contratti in scadenza scritti in {FILE_RISULTATO}.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
