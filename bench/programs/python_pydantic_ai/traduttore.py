from pydantic import BaseModel
from pydantic_ai import Agent


class Traduzione(BaseModel):
    italiano: str
    inglese: str
    francese: str


class Traduzioni(BaseModel):
    frasi: list[Traduzione]


agent = Agent(
    "anthropic:claude-sonnet-5-5",
    output_type=Traduzioni,
    instructions="Traduci ogni frase italiana in inglese e francese, mantenendo l'ordine.",
)

frasi = [
    "Buongiorno, vorrei un caffè.",
    "Dove si trova la stazione?",
    "Domani andremo al mare.",
    "Mi piace molto questo libro.",
]

result = agent.run_sync("\n".join(frasi)).output

larghezze = [max(len(t.italiano), len(t.inglese), len(t.francese), 8) for t in result.frasi]
w = max(larghezze)
print(f"{'Italiano':<{w}} | {'English':<{w}} | Français")
print("-" * (w * 3 + 6))
for t in result.frasi:
    print(f"{t.italiano:<{w}} | {t.inglese:<{w}} | {t.francese}")
