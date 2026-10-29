"""Traduce 4 frasi italiane in inglese e francese con output strutturato."""
import anthropic
from pydantic import BaseModel

MODEL = "claude-haiku-5-5"  # traduzioni brevi: modello economico

FRASI = [
    "Buongiorno, vorrei prenotare un tavolo per due persone.",
    "Domani il treno per Milano parte alle otto e un quarto.",
    "Mi piace molto passeggiare lungo il fiume al tramonto.",
    "Potrebbe dirmi dove si trova la farmacia piu vicina?",
]


class Traduzione(BaseModel):
    italiano: str
    inglese: str
    francese: str


class Traduzioni(BaseModel):
    traduzioni: list[Traduzione]


client = anthropic.Anthropic()


def traduci(frasi: list[str]) -> Traduzioni:
    elenco = "\n".join(f"{i}. {f}" for i, f in enumerate(frasi, 1))
    risposta = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system="Sei un traduttore professionista. Traduci in modo naturale e fedele.",
        tools=[
            {
                "name": "consegna_traduzioni",
                "description": "Consegna le traduzioni, nello stesso ordine delle frasi originali.",
                "input_schema": Traduzioni.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "consegna_traduzioni"},
        messages=[
            {
                "role": "user",
                "content": f"Traduci in inglese e in francese queste frasi italiane:\n{elenco}",
            }
        ],
    )
    for b in risposta.content:
        if b.type == "tool_use":
            return Traduzioni.model_validate(b.input)
    raise RuntimeError("Nessuna traduzione ricevuta")


def stampa_tabella(righe: list[Traduzione]) -> None:
    colonne = [("Italiano", "italiano"), ("English", "inglese"), ("Francais", "francese")]
    larghezze = [
        max(len(titolo), *(len(getattr(r, attr)) for r in righe)) for titolo, attr in colonne
    ]
    sep = "+" + "+".join("-" * (w + 2) for w in larghezze) + "+"
    print(sep)
    print("| " + " | ".join(t.ljust(w) for (t, _), w in zip(colonne, larghezze)) + " |")
    print(sep)
    for r in righe:
        print("| " + " | ".join(getattr(r, a).ljust(w) for (_, a), w in zip(colonne, larghezze)) + " |")
    print(sep)


def main() -> None:
    risultato = traduci(FRASI)
    stampa_tabella(risultato.traduzioni)


if __name__ == "__main__":
    main()
