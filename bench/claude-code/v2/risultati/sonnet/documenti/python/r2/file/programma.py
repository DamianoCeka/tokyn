"""Risponde alle domande di domande.txt usando i documenti in docs/ tramite Claude.

Uso: python programma.py   (dalla cartella che contiene docs/ e domande.txt)
Richiede ANTHROPIC_API_KEY (o un profilo creato con `ant auth login`).
Scrive risultato.json.
"""
import json
import sys
from pathlib import Path

import anthropic

MODEL = "claude-opus-5-5"
BASE = Path.cwd()

SYSTEM = """Rispondi alle domande dei colleghi basandoti ESCLUSIVAMENTE sui documenti aziendali forniti.
- La risposta deve essere breve, in italiano, con i dati precisi del documento (numeri, limiti, indirizzi).
- "fonte" è il nome esatto del file (es. ferie.txt) che contiene la risposta.
- Se nessun documento contiene la risposta, scrivi in "risposta" che l'informazione non è presente nei documenti e metti "fonte" a null. Non inventare."""


def carica_documenti(cartella: Path) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(cartella.glob("*.txt"))}


def main() -> int:
    docs = carica_documenti(BASE / "docs")
    if not docs:
        print("Nessun documento .txt in docs/", file=sys.stderr)
        return 1
    righe = (BASE / "domande.txt").read_text(encoding="utf-8").splitlines()
    domande = [r.strip() for r in righe if r.strip()]

    # I documenti sono messi nel system prompt, identico per ogni domanda: viene messo in cache.
    corpo = "\n\n".join(f'<documento nome="{n}">\n{t}\n</documento>' for n, t in docs.items())
    system = [
        {"type": "text", "text": SYSTEM},
        {"type": "text", "text": corpo, "cache_control": {"type": "ephemeral"}},
    ]
    schema = {
        "type": "object",
        "properties": {
            "risposta": {"type": "string"},
            "fonte": {"anyOf": [{"type": "string", "enum": list(docs)}, {"type": "null"}]},
        },
        "required": ["risposta", "fonte"],
        "additionalProperties": False,
    }

    client = anthropic.Anthropic()
    risultato = []
    for domanda in domande:
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": domanda}],
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            )
        except TypeError as e:  # l'SDK segnala così l'assenza di credenziali
            print(f"Credenziali mancanti (imposta ANTHROPIC_API_KEY): {e}", file=sys.stderr)
            return 1
        except anthropic.APIError as e:
            print(f"Errore API per «{domanda}»: {e}", file=sys.stderr)
            return 1
        if resp.stop_reason == "refusal":
            print(f"Richiesta rifiutata per «{domanda}»", file=sys.stderr)
            return 1
        testo = next(b.text for b in resp.content if b.type == "text")
        dati = json.loads(testo)
        risultato.append({"domanda": domanda, "risposta": dati["risposta"], "fonte": dati["fonte"]})
        print(f"{domanda} -> {dati['risposta']} [{dati['fonte']}]")

    (BASE / "risultato.json").write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
