"""Trova i contratti in scadenza nei 30 giorni successivi a una data di riferimento
e scrive per ognuno un'email di promemoria generata con Claude.

Uso (dalla cartella che contiene contratti.csv):
    python programma.py AAAA-MM-GG

Richiede il pacchetto `anthropic` e le credenziali dell'API (ANTHROPIC_API_KEY).
"""

import csv
import json
import sys
from datetime import date, timedelta

import anthropic

FILE_CONTRATTI = "contratti.csv"
FILE_RISULTATO = "risultato.json"
GIORNI_FINESTRA = 30
MODELLO = "claude-opus-5-5"

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

ISTRUZIONI = """Scrivi email di promemoria in italiano per conto di un'azienda che fornisce servizi ai propri clienti.
L'email avvisa il cliente che un suo contratto sta per scadere e lo invita a contattarci per il rinnovo.
Regole:
- Il testo inizia con "Gentile <nome del cliente>," usando il nome del cliente esattamente come fornito.
- Cita il servizio in scadenza e la data di scadenza esattamente come forniti.
- Tono cortese e professionale, testo breve (massimo 120 parole), senza segnaposto tra parentesi.
- Chiudi con "Cordiali saluti" senza inventare nomi di persone, numeri di telefono o indirizzi.
- L'oggetto è una riga breve che indica il servizio e la data di scadenza."""


def data_in_italiano(d):
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


def leggi_contratti(percorso):
    contratti = []
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        lettore = csv.DictReader(f)
        mancanti = {"cliente", "servizio", "scadenza"} - set(lettore.fieldnames or [])
        if mancanti:
            sys.exit(f"Errore: in {percorso} mancano le colonne {', '.join(sorted(mancanti))}")
        for riga in lettore:
            cliente = (riga.get("cliente") or "").strip()
            servizio = (riga.get("servizio") or "").strip()
            scadenza = (riga.get("scadenza") or "").strip()
            if not cliente and not servizio and not scadenza:
                continue  # riga vuota
            try:
                data_scadenza = date.fromisoformat(scadenza)
            except ValueError:
                print(f"Attenzione: riga {lettore.line_num} ignorata, scadenza non valida: {scadenza!r}",
                      file=sys.stderr)
                continue
            contratti.append({"cliente": cliente, "servizio": servizio,
                              "scadenza": scadenza, "data": data_scadenza})
    return contratti


def scrivi_email(client, contratto, giorni):
    quando = "oggi" if giorni == 0 else ("domani" if giorni == 1 else f"tra {giorni} giorni")
    richiesta = (
        f"Cliente: {contratto['cliente']}\n"
        f"Servizio: {contratto['servizio']}\n"
        f"Data di scadenza: {data_in_italiano(contratto['data'])} ({quando})"
    )
    messaggi = [{"role": "user", "content": richiesta}]

    for tentativo in range(2):
        risposta = client.beta.messages.create(
            model=MODELLO,
            max_tokens=4000,
            system=ISTRUZIONI,
            messages=messaggi,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA_EMAIL}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if risposta.stop_reason == "refusal":
            raise RuntimeError(f"Claude ha rifiutato la richiesta per {contratto['cliente']}")
        if risposta.stop_reason == "max_tokens":
            continue
        testo = next(b.text for b in risposta.content if b.type == "text")
        email = json.loads(testo)
        # Controllo che l'email si rivolga al cliente per nome e citi il servizio
        corpo = email["testo"].lower()
        if contratto["cliente"].lower() in corpo and contratto["servizio"].lower() in corpo:
            return {"oggetto": email["oggetto"].strip(), "testo": email["testo"].strip()}
    raise RuntimeError(
        f"Non sono riuscito a ottenere un'email valida per {contratto['cliente']} ({contratto['servizio']})")


def main():
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

    limite = riferimento + timedelta(days=GIORNI_FINESTRA)
    in_scadenza = sorted((c for c in contratti if riferimento <= c["data"] <= limite),
                         key=lambda c: c["data"])

    risultato = []
    try:
        client = anthropic.Anthropic() if in_scadenza else None
        for c in in_scadenza:
            giorni = (c["data"] - riferimento).days
            print(f"Scrivo l'email per {c['cliente']} - {c['servizio']} (scade il {c['scadenza']})...",
                  file=sys.stderr)
            email = scrivi_email(client, c, giorni)
            risultato.append({"cliente": c["cliente"], "servizio": c["servizio"],
                              "scadenza": c["scadenza"], "giorni_mancanti": giorni, **email})
    except (anthropic.APIError, RuntimeError, TypeError) as e:
        # TypeError: l'SDK lo solleva quando non trova le credenziali
        sys.exit(f"Errore durante la scrittura delle email: {e}\n{FILE_RISULTATO} non è stato scritto.")

    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump({"in_scadenza": risultato}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{len(risultato)} contratti in scadenza scritti in {FILE_RISULTATO}", file=sys.stderr)


if __name__ == "__main__":
    main()
