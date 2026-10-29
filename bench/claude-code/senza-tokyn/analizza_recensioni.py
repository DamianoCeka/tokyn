"""Analizza le recensioni di recensioni.txt con Claude.

Per ogni riga stampa il sentimento (positiva/neutra/negativa) e un voto da 1 a 5,
poi la media dei voti.

Uso:  python analizza_recensioni.py [file]      (default: recensioni.txt)
Serve la variabile d'ambiente ANTHROPIC_API_KEY.
"""

import sys
from typing import Literal

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"

ISTRUZIONI = (
    "Sei un analista di recensioni di prodotti. Classifica il sentimento della "
    "recensione come 'positiva', 'neutra' o 'negativa' e assegna un voto intero "
    "da 1 (pessimo) a 5 (ottimo) coerente con il tono del cliente."
)


class Valutazione(BaseModel):
    sentimento: Literal["positiva", "neutra", "negativa"]
    voto: Literal[1, 2, 3, 4, 5]


def valuta(client: anthropic.Anthropic, recensione: str) -> Valutazione:
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=1024,
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": f"Recensione:\n{recensione}"}],
        output_format=Valutazione,
        output_config={"effort": "low"},
        # Se il modello rifiuta la richiesta, l'API riprova in automatico con un altro modello.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("il modello ha rifiutato di valutare la recensione")
    return response.parsed_output


def main() -> None:
    percorso = sys.argv[1] if len(sys.argv) > 1 else "recensioni.txt"
    with open(percorso, encoding="utf-8") as f:
        recensioni = [riga.strip() for riga in f if riga.strip()]

    if not recensioni:
        print(f"Nessuna recensione trovata in {percorso}.")
        return

    client = anthropic.Anthropic()
    voti = []
    for i, recensione in enumerate(recensioni, 1):
        try:
            v = valuta(client, recensione)
        except (anthropic.APIError, RuntimeError) as e:
            print(f"{i}. {recensione}\n   ERRORE: {e}\n")
            continue
        voti.append(v.voto)
        print(f"{i}. {recensione}\n   Sentimento: {v.sentimento} | Voto: {v.voto}/5\n")

    if voti:
        media = sum(voti) / len(voti)
        print(f"Media dei voti: {media:.2f}/5 (su {len(voti)} recensioni)")
    else:
        print("Nessuna recensione valutata: impossibile calcolare la media.")


if __name__ == "__main__":
    main()
