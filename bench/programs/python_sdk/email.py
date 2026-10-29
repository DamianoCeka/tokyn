import sys

sys.path.pop(0)

import json
import anthropic

client = anthropic.Anthropic()
CATEGORIE = ("lavoro", "personale", "spam")

TOOL = {
    "name": "classifica",
    "description": "Registra la classificazione di una email.",
    "input_schema": {
        "type": "object",
        "properties": {
            "categoria": {"type": "string", "enum": list(CATEGORIE)},
            "priorita": {"type": "integer", "minimum": 1, "maximum": 5},
            "riassunto": {"type": "string"},
        },
        "required": ["categoria", "priorita", "riassunto"],
    },
}


def valida(d):
    if d.get("categoria") not in CATEGORIE:
        raise ValueError(f"categoria deve essere una tra {CATEGORIE}")
    p = d.get("priorita")
    if not isinstance(p, int) or isinstance(p, bool) or not 1 <= p <= 5:
        raise ValueError("priorita deve essere un intero tra 1 e 5")
    r = d.get("riassunto")
    if not isinstance(r, str) or not r.strip() or "\n" in r.strip():
        raise ValueError("riassunto deve essere una stringa non vuota di una sola riga")
    return {"categoria": d["categoria"], "priorita": p, "riassunto": r.strip()}


def classifica(testo):
    messages = [{"role": "user", "content": f"Classifica questa email:\n\n{testo}"}]
    for _ in range(10):
        r = client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=512,
            system="Classifichi email in italiano. Rispondi solo usando lo strumento classifica.",
            tools=[TOOL],
            tool_choice={"type": "tool", "name": "classifica"},
            messages=messages,
        )
        blocco = next(b for b in r.content if b.type == "tool_use")
        try:
            return valida(blocco.input)
        except ValueError as e:
            messages.append({"role": "assistant", "content": r.content})
            messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": blocco.id, "content": f"Non valido: {e}", "is_error": True}],
            })
    raise RuntimeError("Classificazione non valida dopo 10 tentativi")


def main():
    with open("emails.txt", encoding="utf-8") as f:
        emails = [riga.strip() for riga in f if riga.strip()]
    risultati = [{"email": e, **classifica(e)} for e in emails]
    non_spam = sorted((r for r in risultati if r["categoria"] != "spam"), key=lambda r: -r["priorita"])
    for r in non_spam:
        print(f"[P{r['priorita']}] ({r['categoria']}) {r['riassunto']}")
    with open("riepilogo.json", "w", encoding="utf-8") as f:
        json.dump(risultati, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
