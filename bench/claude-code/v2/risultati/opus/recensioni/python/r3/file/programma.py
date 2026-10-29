"""Analizza le recensioni di recensioni.txt con Claude e scrive risultato.json."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

MODELLO = "claude-opus-5-5"
FILE_INPUT = "recensioni.txt"
FILE_OUTPUT = "risultato.json"

ISTRUZIONI = (
    "Sei un analista di recensioni di prodotti. Per la recensione che ti viene data, "
    "indica il sentimento (positivo, negativo o neutro) e il voto da 1 a 5 che il cliente "
    "darebbe al prodotto, dove 1 è pessimo, 3 è nella media e 5 è eccellente."
)


class Analisi(BaseModel):
    sentimento: Literal["positivo", "negativo", "neutro"]
    voto: int = Field(ge=1, le=5)


client = anthropic.Anthropic()


def analizza(testo: str) -> dict:
    risposta = client.beta.messages.parse(
        model=MODELLO,
        max_tokens=4096,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low"},
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": f"Recensione:\n{testo}"}],
        output_format=Analisi,
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError(f"Claude ha rifiutato di analizzare la recensione: {testo!r}")
    if risposta.parsed_output is None:
        raise RuntimeError(
            f"Risposta non valida (stop_reason={risposta.stop_reason}) per: {testo!r}"
        )
    analisi = risposta.parsed_output
    return {"testo": testo, "sentimento": analisi.sentimento, "voto": analisi.voto}


def main() -> None:
    with open(FILE_INPUT, encoding="utf-8") as f:
        recensioni = [riga.strip() for riga in f if riga.strip()]

    if not recensioni:
        sys.exit(f"Nessuna recensione trovata in {FILE_INPUT}.")

    # map() restituisce i risultati nello stesso ordine delle recensioni
    with ThreadPoolExecutor(max_workers=4) as pool:
        risultati = list(pool.map(analizza, recensioni))

    media = round(sum(r["voto"] for r in risultati) / len(risultati), 2)

    with open(FILE_OUTPUT, "w", encoding="utf-8") as f:
        json.dump({"recensioni": risultati, "media": media}, f, ensure_ascii=False, indent=2)

    for r in risultati:
        print(f"[{r['voto']}] {r['sentimento']:<8} {r['testo']}")
    print(f"\nVoto medio: {media} su {len(risultati)} recensioni. Salvato in {FILE_OUTPUT}.")


if __name__ == "__main__":
    main()
