import json
from pathlib import Path

from pydantic_ai import Agent

agent = Agent(
    "anthropic:claude-sonnet-5-5",
    instructions=(
        "Sei l'assistente di prenotazione di un ristorante. Rispondi in italiano. "
        "Controlla la disponibilità prima di prenotare e chiedi i dati mancanti (nome, data YYYY-MM-DD, persone)."
    ),
)


@agent.tool_plain
def controlla_disponibilita(data: str, persone: int) -> str:
    """Verifica se ci sono posti liberi per la data (YYYY-MM-DD) e il numero di persone."""
    tavoli = json.loads(Path("tavoli.json").read_text(encoding="utf-8"))
    liberi = tavoli.get(data, 0)
    return f"{liberi} posti liberi il {data}: {'disponibile' if liberi >= persone else 'non disponibile'}"


@agent.tool_plain
def prenota(nome: str, data: str, persone: int) -> str:
    """Registra una prenotazione a nome del cliente per data e numero di persone."""
    with open("prenotazioni.txt", "a", encoding="utf-8") as f:
        f.write(f"{nome};{data};{persone}\n")
    return "Prenotazione registrata"


history = []
for _ in range(20):
    testo = input("Tu: ").strip()
    if testo.lower() == "esci":
        break
    result = agent.run_sync(testo, message_history=history)
    history = result.all_messages()
    print(f"Assistente: {result.output}")
