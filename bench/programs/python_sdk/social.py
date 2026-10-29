import anthropic

client = anthropic.Anthropic()
MODEL = "claude-sonnet-5-5"

TOOLS = [
    {
        "name": "ricercatore",
        "description": "Sub-agente ricercatore: restituisce punti chiave, target e vantaggi di un prodotto.",
        "input_schema": {
            "type": "object",
            "properties": {"richiesta": {"type": "string"}},
            "required": ["richiesta"],
        },
    },
    {
        "name": "copywriter",
        "description": "Sub-agente copywriter: scrive o rivede il testo di un post Instagram a partire da un brief.",
        "input_schema": {
            "type": "object",
            "properties": {"brief": {"type": "string"}},
            "required": ["brief"],
        },
    },
]

VERDETTO = {
    "name": "verdetto",
    "description": "Registra il verdetto sul post.",
    "input_schema": {
        "type": "object",
        "properties": {
            "approvato": {"type": "boolean"},
            "problemi": {"type": "array", "items": {"type": "string"}},
            "testo_finale": {"type": "string"},
        },
        "required": ["approvato", "problemi", "testo_finale"],
    },
}


def sub_agente(system, prompt):
    r = client.messages.create(model=MODEL, max_tokens=1024, system=system, messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in r.content if b.type == "text")


def ricercatore(richiesta):
    """Ricerca informazioni sul prodotto."""
    return sub_agente(
        "Sei un ricercatore di mercato gaming. Elenca in modo conciso punti chiave, target e vantaggi. Non inventare specifiche precise: se non le conosci, resta generico.",
        richiesta,
    )


def copywriter(brief):
    """Scrive il testo del post."""
    return sub_agente(
        "Sei un copywriter social italiano. Scrivi post Instagram brevi, energici, con emoji e hashtag pertinenti.",
        brief,
    )


FUNZIONI = {"ricercatore": ricercatore, "copywriter": copywriter}


def coordinatore(compito):
    messages = [{"role": "user", "content": compito}]
    for _ in range(10):
        r = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system="Sei il coordinatore di un team social. Usa prima il ricercatore, poi il copywriter, quindi rispondi solo con il testo finale del post.",
            tools=TOOLS,
            messages=messages,
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
    raise RuntimeError("Il coordinatore ha superato 10 passi")


def valida(d):
    if not isinstance(d.get("approvato"), bool):
        raise ValueError("approvato deve essere un booleano")
    p = d.get("problemi")
    if not isinstance(p, list) or not all(isinstance(x, str) for x in p):
        raise ValueError("problemi deve essere una lista di stringhe")
    if not isinstance(d.get("testo_finale"), str) or not d["testo_finale"].strip():
        raise ValueError("testo_finale deve essere una stringa non vuota")
    return d


def revisore(post):
    messages = [{"role": "user", "content": f"Controlla questo post Instagram su un nuovo mouse gaming (tono, claim non verificabili, errori, lunghezza, hashtag):\n\n{post}"}]
    for _ in range(10):
        r = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system="Sei un revisore di contenuti social. Rispondi solo con lo strumento verdetto; testo_finale è il post corretto (o invariato se approvato).",
            tools=[VERDETTO],
            tool_choice={"type": "tool", "name": "verdetto"},
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
    raise RuntimeError("Verdetto non valido dopo 10 tentativi")


def main():
    post = coordinatore("Crea un post Instagram per il lancio di un nuovo mouse gaming wireless ultraleggero.")
    print("POST:\n" + post + "\n")
    v = revisore(post)
    print("Approvato:", v["approvato"])
    for p in v["problemi"]:
        print("-", p)
    print("\nTesto finale:\n" + v["testo_finale"])


if __name__ == "__main__":
    main()
