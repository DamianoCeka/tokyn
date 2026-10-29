import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent


class Email(BaseModel):
    category: Literal["lavoro", "personale", "spam"]
    priority: int = Field(ge=1, le=5)
    summary: str = Field(description="Riassunto in una riga")


agent = Agent(
    "anthropic:claude-haiku-5-5",
    output_type=Email,
    instructions="Classifica l'email: categoria, priorità (1=bassa, 5=urgente) e riassunto in una riga.",
)

emails = [r for r in Path("emails.txt").read_text(encoding="utf-8").splitlines() if r.strip()]
results = [{"email": e, **agent.run_sync(e).output.model_dump()} for e in emails]

for r in sorted((r for r in results if r["category"] != "spam"), key=lambda r: -r["priority"]):
    print(f"[{r['priority']}] ({r['category']}) {r['summary']}")

Path("riepilogo.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
