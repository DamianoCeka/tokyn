"""Assistente per prenotazioni al ristorante con memoria e due tool."""
import json
from datetime import date

import anthropic

MODEL = "claude-sonnet-5-5"
MAX_TURNI = 20
MAX_GIRI_TOOL = 6  # sicurezza contro cicli di tool infiniti

client = anthropic.Anthropic()


def _carica_tavoli() -> dict:
    try:
        with open("tavoli.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def controlla_disponibilita(data: str, persone: int) -> str:
    tavoli = _carica_tavoli()
    liberi = tavoli.get(data)
    if liberi is None:
        return f"Nessuna disponibilita registrata per il {data}."
    if liberi >= persone:
        return f"Disponibile: il {data} ci sono {liberi} posti liberi (richiesti {persone})."
    return f"Non disponibile: il {data} restano solo {liberi} posti (richiesti {persone})."


def prenota(nome: str, data: str, persone: int) -> str:
    tavoli = _carica_tavoli()
    liberi = tavoli.get(data)
    if liberi is None or liberi < persone:
        return f"Impossibile prenotare: posti insufficienti il {data}."
    with open("prenotazioni.txt", "a", encoding="utf-8") as f:
        f.write(f"{nome};{data};{persone}\n")
    # Aggiorna i posti liberi per evitare doppie prenotazioni.
    tavoli[data] = liberi - persone
    with open("tavoli.json", "w", encoding="utf-8") as f:
        json.dump(tavoli, f, ensure_ascii=False, indent=2)
    return f"Prenotazione registrata: {nome}, {data}, {persone} persone."


FUNZIONI = {"controlla_disponibilita": controlla_disponibilita, "prenota": prenota}

TOOLS = [
    {
        "name": "controlla_disponibilita",
        "description": "Controlla se ci sono posti liberi in una data per un certo numero di persone.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Data in formato YYYY-MM-DD"},
                "persone": {"type": "integer", "description": "Numero di persone"},
            },
            "required": ["data", "persone"],
        },
    },
    {
        "name": "prenota",
        "description": "Registra una prenotazione. Usalo solo dopo aver verificato la disponibilita "
        "e ottenuto nome, data e numero di persone dal cliente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "data": {"type": "string", "description": "Data in formato YYYY-MM-DD"},
                "persone": {"type": "integer"},
            },
            "required": ["nome", "data", "persone"],
        },
    },
]

SYSTEM = (
    "Sei l'assistente prenotazioni di un ristorante italiano. Rispondi in italiano, "
    "in modo cordiale e breve. Per prenotare servono nome, data e numero di persone: "
    "chiedi cio che manca, controlla la disponibilita, poi prenota. "
    f"Oggi e {date.today().isoformat()}; converti le date relative in formato YYYY-MM-DD."
)


def turno(messaggi: list) -> str:
    """Esegue un turno: chiama il modello, gestisce i tool, aggiorna la cronologia."""
    for _ in range(MAX_GIRI_TOOL):
        risposta = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM,
            tools=TOOLS,
            messages=messaggi,
        )
        messaggi.append({"role": "assistant", "content": risposta.content})

        if risposta.stop_reason != "tool_use":
            return "".join(b.text for b in risposta.content if b.type == "text")

        risultati = []
        for b in risposta.content:
            if b.type != "tool_use":
                continue
            try:
                esito = FUNZIONI[b.name](**b.input)
            except Exception as e:
                esito = f"Errore: {e}"
            risultati.append({"type": "tool_result", "tool_use_id": b.id, "content": esito})
        messaggi.append({"role": "user", "content": risultati})
    return "Mi dispiace, non sono riuscito a completare la richiesta."


def main() -> None:
    messaggi: list = []  # memoria della conversazione
    print("Assistente ristorante. Scrivi 'esci' per terminare.")
    for _ in range(MAX_TURNI):
        try:
            testo = input("\nTu: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if testo.lower() == "esci":
            break
        if not testo:
            continue
        messaggi.append({"role": "user", "content": testo})
        try:
            print(f"Assistente: {turno(messaggi)}")
        except anthropic.APIError as e:
            print(f"Errore API: {e}")
            messaggi.pop()  # rimuove il messaggio rimasto senza risposta
    print("Arrivederci!")


if __name__ == "__main__":
    main()
