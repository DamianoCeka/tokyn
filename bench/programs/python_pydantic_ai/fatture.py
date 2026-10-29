from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import Agent


class Riga(BaseModel):
    descrizione: str
    quantita: float
    prezzo_unitario: float


class Fattura(BaseModel):
    fornitore: str
    numero: str
    righe: list[Riga]


agent = Agent(
    "anthropic:claude-haiku-5-5",
    output_type=Fattura,
    instructions="Estrai fornitore, numero fattura e righe (descrizione, quantità, prezzo unitario) dal testo della fattura.",
)

fattura = agent.run_sync(Path("fattura.txt").read_text(encoding="utf-8")).output

print(f"Fornitore: {fattura.fornitore} - Fattura n. {fattura.numero}")
for r in fattura.righe:
    print(f"{r.descrizione}: {r.quantita} x {r.prezzo_unitario:.2f} = {r.quantita * r.prezzo_unitario:.2f}")
    if r.quantita == 0:
        print(f"ATTENZIONE: quantità zero per '{r.descrizione}'")

print(f"Totale: {sum(r.quantita * r.prezzo_unitario for r in fattura.righe):.2f}")
