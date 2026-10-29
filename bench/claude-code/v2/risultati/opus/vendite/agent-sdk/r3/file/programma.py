"""Riepilogo trimestrale degli ordini.

Legge ordini.csv e clienti.csv dalla cartella corrente, calcola il fatturato
per paese e i 3 migliori clienti, chiede a Claude un breve paragrafo per la
direzione e scrive tutto in risultato.json.

Uso: python programma.py
"""

import asyncio
import csv
import json
import sys
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

FILE_ORDINI = "ordini.csv"
FILE_CLIENTI = "clienti.csv"
FILE_RISULTATO = "risultato.json"
MODELLO = "claude-opus-5-5"
CENTESIMO = Decimal("0.01")


def leggi_csv(percorso, colonne_richieste):
    # utf-8-sig tollera il BOM che molti gestionali mettono in testa al file
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        lettore = csv.DictReader(f)
        mancanti = set(colonne_richieste) - set(lettore.fieldnames or [])
        if mancanti:
            raise SystemExit(f"{percorso}: colonne mancanti: {', '.join(sorted(mancanti))}")
        # riga 1 = intestazione, quindi i dati partono dalla 2
        return [(n, riga) for n, riga in enumerate(lettore, start=2) if any(riga.values())]


def carica_clienti():
    clienti = {}
    for n, riga in leggi_csv(FILE_CLIENTI, ["id", "nome", "paese"]):
        id_cliente = riga["id"].strip()
        if id_cliente in clienti:
            raise SystemExit(f"{FILE_CLIENTI}, riga {n}: id cliente {id_cliente} duplicato")
        clienti[id_cliente] = {"nome": riga["nome"].strip(), "paese": riga["paese"].strip()}
    return clienti


def carica_ordini(clienti):
    ordini = []
    for n, riga in leggi_csv(FILE_ORDINI, ["id", "cliente_id", "data", "importo"]):
        id_cliente = riga["cliente_id"].strip()
        if id_cliente not in clienti:
            raise SystemExit(
                f"{FILE_ORDINI}, riga {n}: il cliente {id_cliente} non esiste in {FILE_CLIENTI}"
            )
        try:
            importo = Decimal(riga["importo"].strip())
        except InvalidOperation:
            raise SystemExit(f"{FILE_ORDINI}, riga {n}: importo non valido: {riga['importo']!r}")
        ordini.append((id_cliente, importo))
    return ordini


def calcola(clienti, ordini):
    # Decimal evita gli errori di arrotondamento dei float sulle somme in euro
    per_paese = {c["paese"]: Decimal(0) for c in clienti.values()}
    per_cliente = defaultdict(Decimal)
    for id_cliente, importo in ordini:
        per_paese[clienti[id_cliente]["paese"]] += importo
        per_cliente[id_cliente] += importo

    per_paese = {
        paese: totale.quantize(CENTESIMO, ROUND_HALF_UP)
        for paese, totale in sorted(per_paese.items(), key=lambda kv: (-kv[1], kv[0]))
    }
    # a parità di spesa si ordina per nome, così il risultato è stabile
    classifica = sorted(per_cliente.items(), key=lambda kv: (-kv[1], clienti[kv[0]]["nome"]))
    migliori = [(clienti[i]["nome"], totale.quantize(CENTESIMO, ROUND_HALF_UP)) for i, totale in classifica[:3]]
    return per_paese, migliori


def euro(valore):
    """15230.5 -> '15.230,50'"""
    return f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def scrivi_riassunto(per_paese, migliori, numero_ordini):
    totale = sum(per_paese.values())
    massimo = max(per_paese.values())
    primi = [p for p, v in per_paese.items() if v == massimo]

    righe_paesi = "\n".join(
        f"- {p}: {euro(v)} euro ({euro(v / totale * 100 if totale else 0)}% del totale)"
        for p, v in per_paese.items()
    )
    righe_clienti = "\n".join(f"{i}. {nome}: {euro(v)} euro" for i, (nome, v) in enumerate(migliori, 1))

    prompt = f"""Scrivi un breve paragrafo (3-5 frasi, in italiano, senza titoli, elenchi o markdown) \
per la direzione aziendale che riassuma l'andamento del trimestre.
Il paragrafo deve dire esplicitamente qual è il paese con il fatturato più alto \
({" e ".join(primi)}) e commentare i numeri qui sotto.

Usa solo questi dati, già calcolati e verificati: non ricalcolarli, non inventare \
confronti con altri periodi né dati che non ci sono. Scrivi gli importi nel formato \
italiano come sono riportati qui (es. 15.230,50 euro) e i nomi di paesi e clienti \
esattamente come scritti.

Fatturato totale: {euro(totale)} euro su {numero_ordini} ordini.

Fatturato per paese:
{righe_paesi}

Migliori clienti per spesa:
{righe_clienti}

Rispondi solo con il paragrafo."""

    opzioni = ClaudeAgentOptions(
        model=MODELLO,
        system_prompt="Sei un analista che scrive sintesi chiare e sobrie per la direzione di un'azienda italiana.",
        tools=[],  # serve solo testo: nessun accesso a file o comandi
        setting_sources=[],  # non caricare impostazioni locali di Claude Code
        max_turns=1,
        effort="low",
    )

    testo = []
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, AssistantMessage):
            testo += [b.text for b in messaggio.content if isinstance(b, TextBlock)]
        elif isinstance(messaggio, ResultMessage) and messaggio.is_error:
            raise RuntimeError(f"Claude ha restituito un errore: {messaggio.result}")

    riassunto = " ".join("".join(testo).split())
    if not riassunto:
        raise RuntimeError("Claude non ha restituito alcun testo")
    return riassunto


def main():
    clienti = carica_clienti()
    ordini = carica_ordini(clienti)
    if not ordini:
        raise SystemExit(f"{FILE_ORDINI} non contiene ordini")

    per_paese, migliori = calcola(clienti, ordini)

    try:
        riassunto = asyncio.run(scrivi_riassunto(per_paese, migliori, len(ordini)))
    except Exception as e:
        raise SystemExit(f"Impossibile generare il riassunto con Claude: {e}")

    risultato = {
        "fatturato_per_paese": {p: float(v) for p, v in per_paese.items()},
        "migliori_clienti": [nome for nome, _ in migliori],
        "riassunto": riassunto,
    }
    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Scritto {FILE_RISULTATO}")
    for p, v in per_paese.items():
        print(f"  {p}: {euro(v)} euro")
    print("  Migliori clienti: " + ", ".join(nome for nome, _ in migliori))


if __name__ == "__main__":
    main()
