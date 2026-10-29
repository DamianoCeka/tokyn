"""Fatturato per paese e migliori clienti dai CSV del trimestre.

Si avvia con `python programma.py` dalla cartella che contiene `ordini.csv` e
`clienti.csv`; scrive `risultato.json` nella stessa cartella.
"""

import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

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
    # utf-8-sig: tollera il BOM che alcuni gestionali aggiungono
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def calcola():
    clienti = {r["id"].strip(): r for r in leggi_csv("clienti.csv")}
    per_cliente = defaultdict(Decimal)
    for r in leggi_csv("ordini.csv"):
        cid = r["cliente_id"].strip()
        if cid not in clienti:
            print(f"Attenzione: ordine {r['id']} di un cliente sconosciuto ({cid}), ignorato",
                  file=sys.stderr)
            continue
        per_cliente[cid] += Decimal(r["importo"].strip())

    per_paese = defaultdict(Decimal)
    for cid, tot in per_cliente.items():
        per_paese[clienti[cid]["paese"]] += tot

    # a parità di spesa, ordine alfabetico per un risultato stabile
    classifica = sorted(per_cliente.items(), key=lambda kv: (-kv[1], clienti[kv[0]]["nome"]))
    migliori = [(clienti[cid]["nome"], tot) for cid, tot in classifica[:3]]
    paesi = dict(sorted(per_paese.items(), key=lambda kv: -kv[1]))
    return paesi, migliori


def euro(valore):
    """Formato italiano: 15.230,50"""
    s = f"{valore.quantize(CENT, ROUND_HALF_UP):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


async def scrivi_riassunto(paesi, migliori):
    righe_paesi = "\n".join(f"- {p}: {euro(t)} euro" for p, t in paesi.items())
    righe_clienti = "\n".join(f"{i}. {n}: {euro(t)} euro" for i, (n, t) in enumerate(migliori, 1))
    primo = next(iter(paesi))
    prompt = (
        "Scrivi per la direzione un breve paragrafo (3-5 frasi, in italiano, senza elenchi né "
        "titoli) sul fatturato del trimestre. Indica qual è il paese con il fatturato più alto "
        "e commenta i numeri (distacco dagli altri paesi, peso dei migliori clienti). "
        "Usa solo i dati qui sotto, senza inventare nulla, e scrivi gli importi in formato "
        "italiano come sono riportati. Rispondi soltanto con il paragrafo.\n\n"
        f"Paese con il fatturato più alto: {primo}\n\n"
        f"Fatturato per paese:\n{righe_paesi}\n\n"
        f"I 3 clienti che hanno speso di più:\n{righe_clienti}"
    )
    opzioni = ClaudeAgentOptions(
        system_prompt="Sei un analista che redige sintesi concise per la direzione aziendale.",
        tools=[],  # nessuno strumento: serve solo scrivere testo
        max_turns=1,
        setting_sources=[],  # ignora configurazioni di progetto/utente
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
    paesi, migliori = calcola()
    riassunto = anyio.run(scrivi_riassunto, paesi, migliori)
    risultato = {
        "fatturato_per_paese": {p: float(t.quantize(CENT, ROUND_HALF_UP)) for p, t in paesi.items()},
        "migliori_clienti": [n for n, _ in migliori],
        "riassunto": riassunto,
    }
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print(json.dumps(risultato, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
