"""Fatturato per paese e migliori clienti dai CSV trimestrali, con commento di Claude.

Uso: python programma.py   (dalla cartella che contiene ordini.csv e clienti.csv)
Scrive risultato.json nella cartella corrente.
"""
import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import anyio
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

CENT = Decimal("0.01")


def leggi_csv(percorso):
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def calcola():
    clienti = {r["id"].strip(): r for r in leggi_csv("clienti.csv")}
    per_cliente = defaultdict(Decimal)
    for r in leggi_csv("ordini.csv"):
        cid = r["cliente_id"].strip()
        if cid not in clienti:
            print(f"Attenzione: ordine {r['id']} con cliente_id {cid} sconosciuto, ignorato", file=sys.stderr)
            continue
        try:
            per_cliente[cid] += Decimal(r["importo"].strip())
        except InvalidOperation:
            sys.exit(f"Importo non valido nell'ordine {r['id']}: {r['importo']!r}")

    per_paese = defaultdict(Decimal)
    for cid, totale in per_cliente.items():
        per_paese[clienti[cid]["paese"]] += totale

    fatturato = {p: t.quantize(CENT, ROUND_HALF_UP) for p, t in per_paese.items()}
    fatturato = dict(sorted(fatturato.items(), key=lambda kv: (-kv[1], kv[0])))
    ordinati = sorted(per_cliente.items(), key=lambda kv: (-kv[1], clienti[kv[0]]["nome"]))
    migliori = [(clienti[cid]["nome"], t.quantize(CENT, ROUND_HALF_UP)) for cid, t in ordinati[:3]]
    return fatturato, migliori


def euro(d):
    # formato italiano: 15.230,50
    return f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def riassunto(fatturato, migliori):
    righe_paesi = "\n".join(f"- {p}: {euro(t)} euro" for p, t in fatturato.items())
    righe_clienti = "\n".join(f"{i}. {n}: {euro(t)} euro" for i, (n, t) in enumerate(migliori, 1))
    prompt = (
        "Scrivi in italiano un breve paragrafo (3-5 frasi, testo semplice, senza elenchi né titoli) "
        "per la direzione sui risultati del trimestre. Deve dire qual è il paese con il fatturato più alto "
        "e commentare i numeri, citando i migliori clienti. Usa solo i dati seguenti, senza inventare altro "
        "e riportando gli importi nello stesso formato.\n\n"
        f"Fatturato per paese (dal più alto):\n{righe_paesi}\n\nI 3 clienti che hanno speso di più:\n{righe_clienti}"
    )
    opzioni = ClaudeAgentOptions(
        system_prompt="Sei un analista che scrive sintesi chiare e sobrie per la direzione aziendale.",
        tools=[],
        max_turns=1,
        setting_sources=[],
    )
    testo, finale = [], None
    async for msg in query(prompt=prompt, options=opzioni):
        if isinstance(msg, AssistantMessage):
            testo += [b.text for b in msg.content if isinstance(b, TextBlock)]
        elif isinstance(msg, ResultMessage):
            finale = msg
    if finale is None or finale.is_error or not "".join(testo).strip():
        sys.exit("Claude non ha restituito un riassunto valido; risultato.json non scritto.")
    return "".join(testo).strip()


def main():
    fatturato, migliori = calcola()
    if not fatturato:
        sys.exit("Nessun ordine da elaborare.")
    testo = anyio.run(riassunto, fatturato, migliori)
    risultato = {
        "fatturato_per_paese": {p: float(t) for p, t in fatturato.items()},
        "migliori_clienti": [n for n, _ in migliori],
        "riassunto": testo,
    }
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
    print("Scritto risultato.json")


if __name__ == "__main__":
    main()
