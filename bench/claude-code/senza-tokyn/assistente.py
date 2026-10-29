#!/usr/bin/env python3
"""Assistente clienti da terminale basato sulle FAQ in faq.txt.

Claude risponde usando lo strumento `cerca_faq`, ricorda la conversazione
e termina quando l'utente scrive "esci".
"""
import re
import sys
from pathlib import Path

import anthropic

MODEL = "claude-opus-5-5"
FAQ_PATH = Path(__file__).with_name("faq.txt")

SYSTEM = (
    "Sei l'assistente clienti del negozio. Rispondi in italiano, in modo breve e cortese. "
    "Per qualsiasi domanda su negozio, ordini, spedizioni, resi o orari usa sempre lo "
    "strumento cerca_faq prima di rispondere, e basa la risposta solo su ciò che trovi. "
    "Se le FAQ non contengono la risposta, dillo chiaramente e suggerisci di contattare "
    "il servizio clienti. Puoi usare la conversazione precedente per capire le domande di seguito."
)

TOOLS = [
    {
        "name": "cerca_faq",
        "description": (
            "Cerca nelle FAQ del negozio le voci pertinenti alla domanda del cliente. "
            "Restituisce le coppie domanda/risposta più rilevanti, oppure un messaggio "
            "se nessuna voce corrisponde."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Parole chiave o domanda da cercare, in italiano.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]


def carica_faq(path: Path) -> list[tuple[str, str]]:
    voci = []
    for riga in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*D:\s*(.*?)\s*R:\s*(.*)", riga)
        if m:
            voci.append((m.group(1), m.group(2)))
    return voci


def _parole(testo: str) -> set[str]:
    # Prefissi di 5 lettere: "spedite" e "spedizioni" combaciano
    return {p[:5] for p in re.findall(r"\w+", testo.lower()) if len(p) > 2}


def cerca_faq(faq: list[tuple[str, str]], query: str, top_k: int = 3) -> str:
    q = _parole(query)
    punteggi = []
    for domanda, risposta in faq:
        score = len(q & _parole(domanda)) * 2 + len(q & _parole(risposta))
        if score:
            punteggi.append((score, domanda, risposta))
    punteggi.sort(reverse=True)
    if not punteggi:
        return "Nessuna FAQ pertinente trovata."
    return "\n".join(f"D: {d}\nR: {r}" for _, d, r in punteggi[:top_k])


def main() -> None:
    faq = carica_faq(FAQ_PATH)
    client = anthropic.Anthropic()
    messages: list = []  # memoria della conversazione

    print("Assistente clienti — scrivi la tua domanda (\"esci\" per terminare).")
    while True:
        try:
            testo = input("\nTu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not testo:
            continue
        if testo.lower() == "esci":
            break

        inizio = len(messages)
        messages.append({"role": "user", "content": testo})
        try:
            while True:
                response = client.beta.messages.create(
                    model=MODEL,
                    max_tokens=16000,
                    system=SYSTEM,
                    tools=TOOLS,
                    messages=messages,
                    output_config={"effort": "low"},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
                # Salva l'intero contenuto (tool_use e thinking inclusi) per la memoria
                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason != "tool_use":
                    break
                for blocco in response.content:
                    if blocco.type == "tool_use":
                        print(f"  [cerca_faq: {blocco.input['query']!r}]")
                risultati = [
                    {
                        "type": "tool_result",
                        "tool_use_id": blocco.id,
                        "content": cerca_faq(faq, blocco.input["query"]),
                    }
                    for blocco in response.content
                    if blocco.type == "tool_use" and blocco.name == "cerca_faq"
                ]
                messages.append({"role": "user", "content": risultati})
        except anthropic.APIConnectionError:
            print("Assistente: errore di connessione, riprova.")
            del messages[inizio:]  # scarta il turno fallito
            continue
        except anthropic.APIStatusError as e:
            print(f"Assistente: errore dal servizio ({e.status_code}), riprova.")
            del messages[inizio:]  # scarta il turno fallito
            continue

        if response.stop_reason == "refusal":
            print("Assistente: mi dispiace, non posso aiutarti con questa richiesta.")
            continue
        risposta = "".join(b.text for b in response.content if b.type == "text")
        print(f"Assistente: {risposta}")

    print("Arrivederci!")


if __name__ == "__main__":
    sys.exit(main())
