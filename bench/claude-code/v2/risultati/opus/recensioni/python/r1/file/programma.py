"""Analizza le recensioni in recensioni.txt con Claude e scrive risultato.json."""

import json
import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
FILE_INPUT = Path("recensioni.txt")
FILE_OUTPUT = Path("risultato.json")

ISTRUZIONI = (
    "Sei un analista di recensioni di prodotti. Per la recensione che ti viene data "
    "indica il sentimento (positivo, negativo o neutro) e un voto intero da 1 a 5 "
    "che rappresenti quanto il cliente è soddisfatto (1 = per niente, 5 = moltissimo)."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "sentimento": {"type": "string", "enum": ["positivo", "negativo", "neutro"]},
        "voto": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    },
    "required": ["sentimento", "voto"],
    "additionalProperties": False,
}


def analizza(client: anthropic.Anthropic, testo: str) -> dict:
    risposta = client.beta.messages.create(
        model=MODELLO,
        max_tokens=4000,
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": f"Recensione:\n{testo}"}],
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        # Se il modello rifiuta la richiesta, l'API riprova in automatico con un modello di riserva.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError(f"Claude ha rifiutato di analizzare la recensione: {testo!r}")
    if risposta.stop_reason == "max_tokens":
        raise RuntimeError(f"Risposta troncata per la recensione: {testo!r}")

    testo_json = next(b.text for b in risposta.content if b.type == "text")
    dati = json.loads(testo_json)
    return {"testo": testo, "sentimento": dati["sentimento"], "voto": dati["voto"]}


def main() -> None:
    if not FILE_INPUT.exists():
        sys.exit(f"File {FILE_INPUT} non trovato nella cartella corrente.")

    righe = FILE_INPUT.read_text(encoding="utf-8").splitlines()
    recensioni = [r.strip() for r in righe if r.strip()]
    if not recensioni:
        sys.exit(f"Il file {FILE_INPUT} non contiene recensioni.")

    client = anthropic.Anthropic()
    risultati = []
    for i, testo in enumerate(recensioni, start=1):
        print(f"[{i}/{len(recensioni)}] {testo}")
        risultati.append(analizza(client, testo))

    media = round(sum(r["voto"] for r in risultati) / len(risultati), 2)
    FILE_OUTPUT.write_text(
        json.dumps({"recensioni": risultati, "media": media}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nVoto medio: {media}  →  risultati salvati in {FILE_OUTPUT}")


if __name__ == "__main__":
    main()
