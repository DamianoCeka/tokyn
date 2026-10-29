"""Risponde alle domande di domande.txt usando i documenti in docs/ e Claude.

Avvio: python programma.py  (dalla cartella che contiene docs/ e domande.txt)
Richiede la variabile d'ambiente ANTHROPIC_API_KEY (o un profilo `ant auth login`).
Scrive risultato.json: [{"domanda", "risposta", "fonte"}, ...] nello stesso ordine.
"""

import json
import sys
from pathlib import Path

import anthropic

MODEL = "claude-opus-5-5"
NON_TROVATA = "Non risulta nei documenti."

SCHEMA = {
    "type": "object",
    "properties": {
        "risposta": {"type": "string"},
        "fonte": {"type": ["string", "null"]},
    },
    "required": ["risposta", "fonte"],
    "additionalProperties": False,
}

SYSTEM = (
    "Sei l'assistente interno di un'azienda. Rispondi alle domande dei colleghi "
    "usando ESCLUSIVAMENTE i documenti forniti, in italiano, in modo breve e preciso "
    "(solo l'informazione richiesta, con numeri e condizioni rilevanti). "
    "In 'fonte' indica il nome esatto del file (come nell'attributo name del tag "
    "<documento>) da cui proviene la risposta; se servono più file, scegli quello "
    "principale. Se la risposta non è nei documenti, non inventarla: scrivi in "
    f"'risposta' \"{NON_TROVATA}\" e metti 'fonte' a null."
)


def carica_documenti(cartella: Path) -> dict[str, str]:
    docs = {p.name: p.read_text(encoding="utf-8") for p in sorted(cartella.glob("*.txt"))}
    if not docs:
        sys.exit(f"Nessun file .txt trovato in {cartella}/")
    return docs


def carica_domande(percorso: Path) -> list[str]:
    righe = percorso.read_text(encoding="utf-8").splitlines()
    return [r.strip() for r in righe if r.strip()]


def rispondi(client: anthropic.Anthropic, blocco_docs: str, domanda: str, nomi: set[str]) -> dict:
    risposta = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        messages=[
            {
                "role": "user",
                "content": [
                    # I documenti sono uguali per ogni domanda: li mettiamo in cache.
                    {"type": "text", "text": blocco_docs, "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": f"Domanda: {domanda}"},
                ],
            }
        ],
    )
    if risposta.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"risposta non utilizzabile (stop_reason={risposta.stop_reason})")
    testo = next(b.text for b in risposta.content if b.type == "text")
    dati = json.loads(testo)
    fonte = dati["fonte"]
    if fonte is not None and fonte not in nomi:
        # Il modello ha citato un file inesistente: meglio nessuna fonte che una falsa.
        fonte = None
    return {"domanda": domanda, "risposta": dati["risposta"], "fonte": fonte}


def main() -> None:
    docs = carica_documenti(Path("docs"))
    domande = carica_domande(Path("domande.txt"))
    blocco_docs = "\n\n".join(
        f'<documento name="{nome}">\n{testo}\n</documento>' for nome, testo in docs.items()
    )

    client = anthropic.Anthropic()
    risultato = []
    for domanda in domande:
        try:
            voce = rispondi(client, blocco_docs, domanda, set(docs))
        except anthropic.APIError as e:
            sys.exit(f"Errore API sulla domanda {domanda!r}: {e}")
        except (RuntimeError, json.JSONDecodeError, StopIteration) as e:
            print(f"Attenzione: {domanda!r}: {e}", file=sys.stderr)
            voce = {"domanda": domanda, "risposta": NON_TROVATA, "fonte": None}
        print(f"- {voce['domanda']} -> {voce['risposta']} [{voce['fonte']}]")
        risultato.append(voce)

    Path("risultato.json").write_text(
        json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
