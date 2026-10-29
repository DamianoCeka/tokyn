import json
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
CARTELLA_DOCS = Path("docs")
FILE_DOMANDE = Path("domande.txt")
FILE_RISULTATO = Path("risultato.json")

ISTRUZIONI = """Sei l'assistente interno di un'azienda. Rispondi alle domande dei colleghi \
usando soltanto i documenti aziendali forniti qui sotto, ciascuno racchiuso in un tag \
<documento nome="...">.

Regole:
- Scrivi la risposta in italiano, breve e precisa, con i dati concreti del documento \
(numeri, importi, indirizzi, luoghi).
- In "fonte" metti il nome esatto del file del documento da cui hai preso la risposta.
- Se la risposta non si trova nei documenti, scrivi in "risposta" che l'informazione non \
è presente nei documenti e metti null in "fonte". Non inventare."""


def carica_documenti():
    documenti = {p.name: p.read_text(encoding="utf-8") for p in sorted(CARTELLA_DOCS.glob("*.txt"))}
    if not documenti:
        raise SystemExit(f"Nessun file .txt trovato in {CARTELLA_DOCS}/")
    return documenti


def carica_domande():
    righe = FILE_DOMANDE.read_text(encoding="utf-8").splitlines()
    return [r.strip() for r in righe if r.strip()]


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
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=16000,
        system=system,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": schema},
        },
        messages=[{"role": "user", "content": domanda}],
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError(f"Richiesta rifiutata dal modello: {domanda}")
    testo = next(b.text for b in risposta.content if b.type == "text")
    return json.loads(testo)


def main():
    documenti = carica_documenti()
    domande = carica_domande()
    testo_docs = "\n\n".join(
        f'<documento nome="{nome}">\n{contenuto}\n</documento>' for nome, contenuto in documenti.items()
    )
    # I documenti stanno nel system prompt, uguale per tutte le domande: viene messo in cache.
    system = [
        {"type": "text", "text": ISTRUZIONI},
        {"type": "text", "text": testo_docs, "cache_control": {"type": "ephemeral"}},
    ]
    schema = schema_risposta(list(documenti))
    client = anthropic.Anthropic()

    risultato = []
    for domanda in domande:
        esito = rispondi(client, system, schema, domanda)
        risultato.append({"domanda": domanda, "risposta": esito["risposta"], "fonte": esito["fonte"]})
        print(f"{domanda}\n  -> {esito['risposta']} [{esito['fonte']}]")

    FILE_RISULTATO.write_text(json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nScritto {FILE_RISULTATO} ({len(risultato)} risposte)")


if __name__ == "__main__":
    main()
