import json
from datetime import date

import anthropic

client = anthropic.Anthropic()

TOOLS = [
    {
        "name": "controlla_disponibilita",
        "description": "Restituisce i posti liberi per una data (YYYY-MM-DD) e dice se bastano per il numero di persone.",
        "input_schema": {
            "type": "object",
            "properties": {"data": {"type": "string"}, "persone": {"type": "integer", "minimum": 1}},
            "required": ["data", "persone"],
        },
    },
    {
        "name": "prenota",
        "description": "Registra una prenotazione a nome del cliente per una data (YYYY-MM-DD) e un numero di persone.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "data": {"type": "string"},
                "persone": {"type": "integer", "minimum": 1},
            },
            "required": ["nome", "data", "persone"],
        },
    },
]


def carica_tavoli():
    with open("tavoli.json", encoding="utf-8") as f:
        return json.load(f)


def controlla_disponibilita(data, persone):
    """Controlla i posti liberi per una data."""
    liberi = carica_tavoli().get(data, 0)
    return json.dumps({"data": data, "posti_liberi": liberi, "disponibile": liberi >= persone})


def prenota(nome, data, persone):
    """Registra una prenotazione."""
    tavoli = carica_tavoli()
    if tavoli.get(data, 0) < persone:
        raise ValueError("posti insufficienti per questa data")
    tavoli[data] -= persone
    with open("tavoli.json", "w", encoding="utf-8") as f:
        json.dump(tavoli, f, ensure_ascii=False, indent=2)
    with open("prenotazioni.txt", "a", encoding="utf-8") as f:
        f.write(f"{nome};{data};{persone}\n")
    return "Prenotazione registrata"


FUNZIONI = {"controlla_disponibilita": controlla_disponibilita, "prenota": prenota}
SYSTEM = f"Sei l'assistente prenotazioni di un ristorante. Rispondi in italiano, in modo breve. Oggi è {date.today().isoformat()}. Chiedi i dati mancanti (nome, data, persone) e prenota solo dopo aver verificato la disponibilità."


def turno(messages):
    for _ in range(10):
        r = client.messages.create(
            model="claude-sonnet-5-5", max_tokens=1024, system=SYSTEM, tools=TOOLS, messages=messages
        )
        messages.append({"role": "assistant", "content": r.content})
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text")
        risultati = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            try:
                out, err = FUNZIONI[b.name](**b.input), False
            except Exception as e:
                out, err = f"Errore: {e}", True
            risultati.append({"type": "tool_result", "tool_use_id": b.id, "content": out, "is_error": err})
        messages.append({"role": "user", "content": risultati})
    return "Limite di passi raggiunto."


def main():
    messages = []
    for _ in range(20):
        try:
            testo = input("Tu: ").strip()
        except EOFError:
            break
        if testo.lower() == "esci":
            break
        if not testo:
            continue
        messages.append({"role": "user", "content": testo})
        print("Assistente:", turno(messages))


if __name__ == "__main__":
    main()
