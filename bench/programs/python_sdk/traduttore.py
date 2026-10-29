from dataclasses import dataclass

import anthropic

client = anthropic.Anthropic()

FRASI = [
    "Il treno per Roma parte alle otto.",
    "Vorrei un caffè senza zucchero, per favore.",
    "Domani andiamo al mare con gli amici.",
    "Non trovo le chiavi di casa.",
]

TOOL = {
    "name": "salva_traduzioni",
    "description": "Salva le traduzioni delle frasi, nello stesso ordine di input.",
    "input_schema": {
        "type": "object",
        "properties": {
            "traduzioni": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "italiano": {"type": "string"},
                        "inglese": {"type": "string"},
                        "francese": {"type": "string"},
                    },
                    "required": ["italiano", "inglese", "francese"],
                },
            }
        },
        "required": ["traduzioni"],
    },
}


@dataclass
class Traduzione:
    italiano: str
    inglese: str
    francese: str


def valida(d):
    righe = d.get("traduzioni")
    if not isinstance(righe, list) or len(righe) != len(FRASI):
        raise ValueError(f"servono esattamente {len(FRASI)} traduzioni")
    out = []
    for i, r in enumerate(righe):
        if not isinstance(r, dict) or not all(isinstance(r.get(k), str) and r[k].strip() for k in ("italiano", "inglese", "francese")):
            raise ValueError(f"traduzione {i}: italiano, inglese e francese devono essere stringhe non vuote")
        if r["italiano"].strip() != FRASI[i]:
            raise ValueError(f"traduzione {i}: la frase italiana deve essere esattamente {FRASI[i]!r}")
        out.append(Traduzione(r["italiano"].strip(), r["inglese"].strip(), r["francese"].strip()))
    return out


def traduci():
    elenco = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(FRASI))
    messages = [{"role": "user", "content": f"Traduci in inglese e francese:\n{elenco}"}]
    for _ in range(10):
        r = client.messages.create(
            model="claude-sonnet-5-5",
            max_tokens=1024,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": "salva_traduzioni"},
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
    raise RuntimeError("Traduzioni non valide dopo 10 tentativi")


def main():
    righe = traduci()
    larghezze = [max(len(getattr(r, c)) for r in righe + [Traduzione("ITALIANO", "INGLESE", "FRANCESE")]) for c in ("italiano", "inglese", "francese")]
    formato = " | ".join(f"{{:<{w}}}" for w in larghezze)
    print(formato.format("ITALIANO", "INGLESE", "FRANCESE"))
    print("-+-".join("-" * w for w in larghezze))
    for r in righe:
        print(formato.format(r.italiano, r.inglese, r.francese))


if __name__ == "__main__":
    main()
