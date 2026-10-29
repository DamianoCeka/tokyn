"""Fatturato per paese e migliori clienti da ordini.csv e clienti.csv.

Avvio: python programma.py (dalla cartella dei due CSV). Scrive risultato.json.
"""
import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

CENT = Decimal("0.01")


def leggi_csv(percorso):
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def calcola():
    clienti = {r["id"].strip(): r for r in leggi_csv("clienti.csv")}
    per_paese = defaultdict(Decimal)
    per_cliente = defaultdict(Decimal)
    for r in leggi_csv("ordini.csv"):
        cid = r["cliente_id"].strip()
        if cid not in clienti:
            print(f"Attenzione: ordine {r['id']} con cliente_id {cid} sconosciuto, ignorato",
                  file=sys.stderr)
            continue
        importo = Decimal(r["importo"].strip())
        per_paese[clienti[cid]["paese"]] += importo
        per_cliente[clienti[cid]["nome"]] += importo

    paesi = {p: tot.quantize(CENT) for p, tot in
             sorted(per_paese.items(), key=lambda x: x[1], reverse=True)}
    migliori = [n for n, _ in sorted(per_cliente.items(), key=lambda x: x[1], reverse=True)[:3]]
    spesa = {n: per_cliente[n].quantize(CENT) for n in migliori}
    return paesi, migliori, spesa


def euro(valore):
    """1234.5 -> '1.234,50' (formato italiano)."""
    return f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def scrivi_riassunto(paesi, spesa):
    righe_paesi = "\n".join(f"- {p}: {euro(t)} euro" for p, t in paesi.items())
    righe_clienti = "\n".join(f"{i}. {n}: {euro(t)} euro" for i, (n, t) in enumerate(spesa.items(), 1))
    prompt = (
        "Scrivi in italiano un breve paragrafo (3-4 frasi, testo semplice, senza elenchi né "
        "titoli) per la direzione sul fatturato del trimestre. Deve dire qual è il paese con "
        "il fatturato più alto e commentare i numeri. Usa solo i dati seguenti, già calcolati, "
        "e scrivi gli importi come sono scritti qui.\n\n"
        f"Fatturato per paese (dal più alto):\n{righe_paesi}\n\n"
        f"Clienti che hanno speso di più:\n{righe_clienti}"
    )
    opzioni = ClaudeAgentOptions(
        model="claude-opus-5-5",
        tools=[],  # nessuno strumento: serve solo scrivere testo
        max_turns=1,
        setting_sources=[],
        system_prompt="Sei un analista che scrive sintesi chiare e sobrie per la direzione aziendale.",
    )
    testo = []
    async for msg in query(prompt=prompt, options=opzioni):
        if isinstance(msg, AssistantMessage):
            testo += [b.text for b in msg.content if isinstance(b, TextBlock)]
        elif isinstance(msg, ResultMessage) and msg.is_error:
            raise RuntimeError(f"Claude ha restituito un errore: {msg.result}")
    riassunto = "".join(testo).strip()
    if not riassunto:
        raise RuntimeError("Claude non ha prodotto alcun testo")
    return riassunto


def main():
    paesi, migliori, spesa = calcola()
    riassunto = anyio.run(scrivi_riassunto, paesi, spesa)
    risultato = {
        "fatturato_per_paese": {p: float(t) for p, t in paesi.items()},
        "migliori_clienti": migliori,
        "riassunto": riassunto,
    }
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print("Scritto risultato.json")


if __name__ == "__main__":
    main()
