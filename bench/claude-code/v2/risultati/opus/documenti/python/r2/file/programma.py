"""Risponde alle domande di domande.txt usando i documenti in docs/ e scrive risultato.json."""

import json
import sys
from pathlib import Path

import anthropic

CARTELLA_DOCS = Path("docs")
FILE_DOMANDE = Path("domande.txt")
FILE_RISULTATO = Path("risultato.json")
MODELLO = "claude-opus-5-5"

ISTRUZIONI = """Rispondi alle domande dei colleghi usando SOLO i documenti aziendali qui sotto.

Regole:
- La risposta deve essere breve e diretta (una frase o meno), in italiano, e basata esclusivamente sul testo dei documenti.
- In "fonte" indica il nome del file del documento da cui proviene la risposta.
- Se nessun documento contiene la risposta, scrivi in "risposta" che l'informazione non è presente nei documenti e metti "fonte" a null. Non inventare.
"""


def carica_documenti():
    documenti = {}
    for percorso in sorted(CARTELLA_DOCS.glob("*.txt")):
        documenti[percorso.name] = percorso.read_text(encoding="utf-8")
    return documenti


def carica_domande():
    righe = FILE_DOMANDE.read_text(encoding="utf-8").splitlines()
    return [riga.strip() for riga in righe if riga.strip()]


def costruisci_system(documenti):
    blocchi = [
        f'<documento nome="{nome}">\n{testo.strip()}\n</documento>'
        for nome, testo in documenti.items()
    ]
    return ISTRUZIONI + "\n<documenti>\n" + "\n\n".join(blocchi) + "\n</documenti>"


def schema_risposta(nomi_file):
    return {
        "type": "object",
        "properties": {
            "risposta": {"type": "string"},
            "fonte": {"anyOf": [{"type": "string", "enum": nomi_file}, {"type": "null"}]},
        },
        "required": ["risposta", "fonte"],
        "additionalProperties": False,
    }


def rispondi(client, system, schema, domanda):
    response = client.beta.messages.create(
        model=MODELLO,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        # I documenti sono identici per ogni domanda: li mettiamo in cache.
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": domanda}],
    )
    if response.stop_reason == "refusal":
        return {"risposta": "Richiesta rifiutata dal modello.", "fonte": None}
    if response.stop_reason == "max_tokens":
        return {"risposta": "Risposta troncata: limite di token raggiunto.", "fonte": None}
    testo = "".join(b.text for b in response.content if b.type == "text")
    return json.loads(testo)


def main():
    documenti = carica_documenti()
    if not documenti:
        sys.exit(f"Nessun documento .txt trovato in {CARTELLA_DOCS}/")
    domande = carica_domande()

    client = anthropic.Anthropic()
    system = costruisci_system(documenti)
    schema = schema_risposta(list(documenti))

    risultati = []
    for i, domanda in enumerate(domande, 1):
        print(f"[{i}/{len(domande)}] {domanda}")
        try:
            esito = rispondi(client, system, schema, domanda)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.BadRequestError) as errore:
            # Errori che si ripeterebbero identici per ogni domanda: inutile proseguire.
            sys.exit(f"Errore dell'API, interrompo: {errore}")
        except anthropic.APIError as errore:
            print(f"  errore: {errore}", file=sys.stderr)
            esito = {"risposta": f"Errore durante la richiesta: {errore}", "fonte": None}
        risultati.append({"domanda": domanda, "risposta": esito["risposta"], "fonte": esito["fonte"]})
        print(f"  -> {esito['risposta']} ({esito['fonte']})")

    FILE_RISULTATO.write_text(json.dumps(risultati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scritto {FILE_RISULTATO} con {len(risultati)} risposte.")


if __name__ == "__main__":
    main()
