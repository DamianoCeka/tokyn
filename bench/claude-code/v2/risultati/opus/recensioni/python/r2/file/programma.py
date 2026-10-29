"""Analizza le recensioni in recensioni.txt con Claude e scrive risultato.json."""

import json
import sys

import anthropic

MODELLO = "claude-opus-5-5"
FILE_INGRESSO = "recensioni.txt"
FILE_USCITA = "risultato.json"

SCHEMA = {
    "type": "object",
    "properties": {
        "sentimento": {"type": "string", "enum": ["positivo", "negativo", "neutro"]},
        "voto": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    },
    "required": ["sentimento", "voto"],
    "additionalProperties": False,
}

ISTRUZIONI = (
    "Sei un analista di recensioni di prodotti. Per la recensione che ricevi indica il "
    "sentimento (positivo, negativo o neutro) e il voto da 1 a 5 che il cliente avrebbe "
    "probabilmente dato: 1 = pessimo, 3 = nella media, 5 = eccellente."
)


def analizza(client: anthropic.Anthropic, testo: str) -> dict:
    risposta = client.beta.messages.create(
        model=MODELLO,
        max_tokens=4000,
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": f"Recensione:\n{testo}"}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if risposta.stop_reason != "end_turn":
        raise RuntimeError(f"risposta incompleta (stop_reason={risposta.stop_reason})")
    json_testo = next(b.text for b in risposta.content if b.type == "text")
    return json.loads(json_testo)


def main() -> None:
    try:
        with open(FILE_INGRESSO, encoding="utf-8") as f:
            recensioni = [riga.strip() for riga in f if riga.strip()]
    except FileNotFoundError:
        sys.exit(f"File {FILE_INGRESSO} non trovato nella cartella corrente.")

    client = anthropic.Anthropic()
    risultati = []
    for i, testo in enumerate(recensioni, start=1):
        try:
            analisi = analizza(client, testo)
        except TypeError as e:
            # L'SDK solleva TypeError quando non trova nessuna credenziale
            sys.exit(f"Credenziali Anthropic mancanti: imposta ANTHROPIC_API_KEY. ({e})")
        except (anthropic.APIError, RuntimeError) as e:
            sys.exit(f"Errore sulla recensione {i} ({testo!r}): {e}")
        risultati.append({"testo": testo, "sentimento": analisi["sentimento"], "voto": analisi["voto"]})
        print(f"[{i}/{len(recensioni)}] {analisi['sentimento']:8} {analisi['voto']}  {testo}")

    media = round(sum(r["voto"] for r in risultati) / len(risultati), 2) if risultati else None

    with open(FILE_USCITA, "w", encoding="utf-8") as f:
        json.dump({"recensioni": risultati, "media": media}, f, ensure_ascii=False, indent=2)
    print(f"Voto medio: {media}  ->  {FILE_USCITA}")


if __name__ == "__main__":
    main()
