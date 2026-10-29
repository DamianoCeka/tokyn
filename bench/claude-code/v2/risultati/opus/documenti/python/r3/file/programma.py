"""Risponde alle domande in domande.txt usando i documenti in docs/ e scrive risultato.json."""

import json
import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
CARTELLA_DOCS = Path("docs")
FILE_DOMANDE = Path("domande.txt")
FILE_RISULTATO = Path("risultato.json")


def carica_documenti():
    documenti = {}
    for percorso in sorted(CARTELLA_DOCS.glob("*.txt")):
        documenti[percorso.name] = percorso.read_text(encoding="utf-8")
    return documenti


def carica_domande():
    righe = FILE_DOMANDE.read_text(encoding="utf-8").splitlines()
    return [riga.strip() for riga in righe if riga.strip()]


def prepara_system(documenti):
    parti = [
        "Sei l'assistente interno dell'azienda. Rispondi alle domande dei colleghi "
        "basandoti esclusivamente sui documenti aziendali qui sotto.",
        "La risposta deve essere breve e diretta, in italiano, e riportare il dato preciso "
        "presente nel documento (numeri, nomi, indirizzi).",
        "In 'fonte' indica il nome del file del documento da cui hai preso la risposta. "
        "Se nessun documento contiene la risposta, scrivi in 'risposta' che l'informazione "
        "non è presente nei documenti e metti 'fonte' a null. Non inventare.",
    ]
    for nome, testo in documenti.items():
        parti.append(f'<documento nome="{nome}">\n{testo.strip()}\n</documento>')
    return "\n\n".join(parti)


def prepara_schema(documenti):
    return {
        "type": "object",
        "properties": {
            "risposta": {"type": "string"},
            "fonte": {"anyOf": [{"type": "string", "enum": list(documenti)}, {"type": "null"}]},
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
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": domanda}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato di rispondere")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("risposta troncata (max_tokens)")
    testo = next((block.text for block in response.content if block.type == "text"), None)
    if testo is None:
        raise RuntimeError("nessun testo nella risposta")
    esito = json.loads(testo)
    if not isinstance(esito, dict) or "risposta" not in esito or "fonte" not in esito:
        raise RuntimeError(f"risposta in formato inatteso: {testo[:200]}")
    return esito


def main():
    if not CARTELLA_DOCS.is_dir() or not FILE_DOMANDE.is_file():
        sys.exit("Avvia il programma dalla cartella che contiene docs/ e domande.txt")

    documenti = carica_documenti()
    if not documenti:
        sys.exit("Nessun file .txt trovato in docs/")
    domande = carica_domande()

    client = anthropic.Anthropic()
    system = prepara_system(documenti)
    schema = prepara_schema(documenti)

    risultati = []
    for i, domanda in enumerate(domande, 1):
        print(f"[{i}/{len(domande)}] {domanda}")
        try:
            esito = rispondi(client, system, schema, domanda)
            risultati.append({"domanda": domanda, "risposta": esito["risposta"], "fonte": esito["fonte"]})
        except (anthropic.APIError, RuntimeError, ValueError) as errore:
            print(f"    errore: {errore}", file=sys.stderr)
            risultati.append({"domanda": domanda, "risposta": f"Errore: {errore}", "fonte": None})

    FILE_RISULTATO.write_text(json.dumps(risultati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scritto {FILE_RISULTATO} ({len(risultati)} risposte)")


if __name__ == "__main__":
    main()
