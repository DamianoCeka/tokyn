import anthropic

client = anthropic.Anthropic()

TOOL = {
    "name": "salva_fattura",
    "description": "Salva i dati estratti dalla fattura.",
    "input_schema": {
        "type": "object",
        "properties": {
            "fornitore": {"type": "string"},
            "numero": {"type": "string"},
            "righe": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "descrizione": {"type": "string"},
                        "quantita": {"type": "number", "minimum": 0},
                        "prezzo_unitario": {"type": "number", "minimum": 0},
                    },
                    "required": ["descrizione", "quantita", "prezzo_unitario"],
                },
            },
        },
        "required": ["fornitore", "numero", "righe"],
    },
}


def numero(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0


def valida(d):
    for k in ("fornitore", "numero"):
        if not isinstance(d.get(k), str) or not d[k].strip():
            raise ValueError(f"{k} deve essere una stringa non vuota")
    righe = d.get("righe")
    if not isinstance(righe, list) or not righe:
        raise ValueError("righe deve essere una lista non vuota")
    for i, r in enumerate(righe):
        if not isinstance(r, dict) or not isinstance(r.get("descrizione"), str) or not r["descrizione"].strip():
            raise ValueError(f"riga {i}: descrizione mancante o non valida")
        if not numero(r.get("quantita")) or not numero(r.get("prezzo_unitario")):
            raise ValueError(f"riga {i}: quantita e prezzo_unitario devono essere numeri >= 0")
    return d


def estrai(testo):
    messages = [{"role": "user", "content": f"Estrai i dati da questa fattura:\n\n{testo}"}]
    for _ in range(10):
        r = client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=2048,
            system="Estrai dati da fatture. Rispondi solo con lo strumento salva_fattura; non calcolare totali.",
            tools=[TOOL],
            tool_choice={"type": "tool", "name": "salva_fattura"},
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
    raise RuntimeError("Estrazione non valida dopo 10 tentativi")


def main():
    with open("fattura.txt", encoding="utf-8") as f:
        d = estrai(f.read())
    print(f"Fornitore: {d['fornitore']}  Fattura n. {d['numero']}")
    totale = 0.0
    for r in d["righe"]:
        importo = r["quantita"] * r["prezzo_unitario"]
        totale += importo
        print(f"{r['descrizione']}: {r['quantita']} x {r['prezzo_unitario']:.2f} = {importo:.2f}")
        if r["quantita"] == 0:
            print(f"ATTENZIONE: quantità zero per '{r['descrizione']}'")
    print(f"Totale: {totale:.2f}")


if __name__ == "__main__":
    main()
