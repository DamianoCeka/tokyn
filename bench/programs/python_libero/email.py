"""Classifica le email di emails.txt (una per riga) con Claude e salva riepilogo.json.

Nota: il file si chiama email.py come richiesto, ma questo nome oscura il modulo
`email` della libreria standard. Per evitare conflitti rimuoviamo la cartella dello
script da sys.path PRIMA di importare altro.
"""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != _here]

import json
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

MODEL = "claude-haiku-5-5"  # classificazione semplice: basta il modello economico


class Classificazione(BaseModel):
    categoria: Literal["lavoro", "personale", "spam"]
    priorita: int = Field(ge=1, le=5, description="1 = minima, 5 = massima urgenza")
    riassunto: str = Field(description="Riassunto in una sola riga")


client = anthropic.Anthropic()  # usa ANTHROPIC_API_KEY

SYSTEM = (
    "Sei un assistente che smista la posta. Classifica l'email ricevuta: "
    "categoria (lavoro, personale, spam), priorita da 1 (trascurabile) a 5 (urgente) "
    "e un riassunto di una riga in italiano. Lo spam ha priorita 1."
)


def classifica(testo: str) -> Classificazione:
    risposta = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM,
        tools=[
            {
                "name": "registra_classificazione",
                "description": "Registra la classificazione dell'email.",
                "input_schema": Classificazione.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "registra_classificazione"},
        messages=[{"role": "user", "content": f"Email:\n{testo}"}],
    )
    for blocco in risposta.content:
        if blocco.type == "tool_use":
            return Classificazione.model_validate(blocco.input)
    raise RuntimeError("Il modello non ha restituito una classificazione")


def main() -> None:
    try:
        with open("emails.txt", encoding="utf-8") as f:
            righe = [r.strip() for r in f if r.strip()]
    except FileNotFoundError:
        sys.exit("File emails.txt non trovato.")

    risultati = []
    for i, testo in enumerate(righe, 1):
        try:
            c = classifica(testo)
        except Exception as e:  # errore API o validazione: continua con le altre
            print(f"[{i}] errore: {e}", file=sys.stderr)
            continue
        risultati.append({"email": testo, **c.model_dump()})

    non_spam = [r for r in risultati if r["categoria"] != "spam"]
    non_spam.sort(key=lambda r: r["priorita"], reverse=True)

    print("=== Email non spam (priorita decrescente) ===")
    for r in non_spam:
        print(f"[{r['priorita']}] ({r['categoria']}) {r['riassunto']}")
    if not non_spam:
        print("Nessuna email non spam.")

    with open("riepilogo.json", "w", encoding="utf-8") as f:
        json.dump(risultati, f, ensure_ascii=False, indent=2)
    print(f"\nSalvate {len(risultati)} email in riepilogo.json")


if __name__ == "__main__":
    main()
