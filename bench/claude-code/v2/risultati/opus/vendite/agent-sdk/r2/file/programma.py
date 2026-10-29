"""Analisi trimestrale degli ordini.

Legge ordini.csv e clienti.csv dalla cartella corrente, calcola il fatturato
per paese e i 3 migliori clienti, fa scrivere a Claude un breve paragrafo per
la direzione e salva tutto in risultato.json.

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
CENTESIMO = Decimal("0.01")


def errore(messaggio):
    print(f"Errore: {messaggio}", file=sys.stderr)
    sys.exit(1)


def leggi_csv(percorso, colonne):
    """Restituisce le righe del CSV come dizionari, controllando l'intestazione."""
    try:
        # utf-8-sig: tollera il BOM che alcuni gestionali aggiungono
        with open(percorso, newline="", encoding="utf-8-sig") as f:
            lettore = csv.DictReader(f)
            mancanti = set(colonne) - set(lettore.fieldnames or [])
            if mancanti:
                errore(f"{percorso}: mancano le colonne {', '.join(sorted(mancanti))}")
            # salta le righe completamente vuote
            return [r for r in lettore if any((v or "").strip() for v in r.values())]
    except FileNotFoundError:
        errore(f"file {percorso} non trovato nella cartella corrente")


def calcola(ordini, clienti):
    anagrafica = {}
    for riga in clienti:
        anagrafica[riga["id"].strip()] = (riga["nome"].strip(), riga["paese"].strip())

    # Tutti i paesi presenti in anagrafica partono da zero, anche senza ordini
    per_paese = {paese: Decimal(0) for _, paese in anagrafica.values()}
    per_cliente = defaultdict(Decimal)
    for n, riga in enumerate(ordini, start=2):
        cliente_id = riga["cliente_id"].strip()
        try:
            importo = Decimal(riga["importo"].strip())
        except InvalidOperation:
            errore(f"{FILE_ORDINI}, riga {n}: importo non valido {riga['importo']!r}")
        if cliente_id not in anagrafica:
            errore(f"{FILE_ORDINI}, riga {n}: cliente_id {cliente_id} non presente in {FILE_CLIENTI}")
        nome, paese = anagrafica[cliente_id]
        per_paese[paese] += importo
        per_cliente[cliente_id] += importo

    fatturato_per_paese = {
        paese: totale.quantize(CENTESIMO, ROUND_HALF_UP)
        for paese, totale in sorted(per_paese.items(), key=lambda kv: (-kv[1], kv[0]))
    }
    # A parità di spesa si ordina per nome, così il risultato è stabile
    classifica = sorted(per_cliente.items(), key=lambda kv: (-kv[1], anagrafica[kv[0]][0]))
    migliori = [(anagrafica[cid][0], totale.quantize(CENTESIMO, ROUND_HALF_UP)) for cid, totale in classifica[:3]]
    return fatturato_per_paese, migliori


def euro(valore):
    """Formatta un importo all'italiana: 15230.5 -> '15.230,50'."""
    return f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def scrivi_riassunto(fatturato_per_paese, migliori, numero_ordini):
    totale = sum(fatturato_per_paese.values())
    paese_top = next(iter(fatturato_per_paese))
    righe_paesi = "\n".join(
        f"- {p}: {euro(v)} euro ({euro(v / totale * 100) if totale else '0,00'}% del totale)"
        for p, v in fatturato_per_paese.items()
    )
    righe_clienti = "\n".join(f"{i}. {nome}: {euro(v)} euro" for i, (nome, v) in enumerate(migliori, start=1))

    prompt = f"""Dati del trimestre (già calcolati, non ricalcolarli e non inventarne altri):

Numero di ordini: {numero_ordini}
Fatturato totale: {euro(totale)} euro
Paese con il fatturato più alto: {paese_top}

Fatturato per paese:
{righe_paesi}

I 3 clienti che hanno speso di più:
{righe_clienti}

Scrivi un breve paragrafo (3-5 frasi) in italiano per la direzione aziendale. Inizia dicendo
qual è il paese con il fatturato più alto e con quale importo, poi commenta i numeri
(peso dei vari paesi, concentrazione sui migliori clienti). Usa solo i dati sopra, con gli
importi scritti come sopra. Rispondi solo con il paragrafo, senza titoli, elenchi o markdown."""

    opzioni = ClaudeAgentOptions(
        system_prompt="Sei un analista commerciale che scrive sintesi chiare e sobrie per la direzione.",
        tools=[],  # serve solo testo: nessuno strumento
        max_turns=1,
        setting_sources=[],  # non caricare impostazioni/CLAUDE.md della macchina
    )

    testo = []
    esito = None
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, AssistantMessage):
            testo.extend(b.text for b in messaggio.content if isinstance(b, TextBlock))
        elif isinstance(messaggio, ResultMessage):
            esito = messaggio

    if esito is None or esito.is_error:
        dettaglio = (esito.errors or esito.result) if esito else "nessuna risposta"
        raise RuntimeError(f"Claude non ha restituito il riassunto: {dettaglio}")
    riassunto = " ".join("".join(testo).split())
    if not riassunto:
        raise RuntimeError("Claude ha restituito un riassunto vuoto")
    return riassunto


def main():
    ordini = leggi_csv(FILE_ORDINI, ["id", "cliente_id", "data", "importo"])
    clienti = leggi_csv(FILE_CLIENTI, ["id", "nome", "paese"])
    if not ordini:
        errore(f"{FILE_ORDINI} non contiene ordini")

    fatturato_per_paese, migliori = calcola(ordini, clienti)

    try:
        riassunto = asyncio.run(scrivi_riassunto(fatturato_per_paese, migliori, len(ordini)))
    except Exception as e:
        errore(f"impossibile ottenere il riassunto da Claude ({e})")

    risultato = {
        "fatturato_per_paese": {p: float(v) for p, v in fatturato_per_paese.items()},
        "migliori_clienti": [nome for nome, _ in migliori],
        "riassunto": riassunto,
    }
    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Scritto {FILE_RISULTATO}")


if __name__ == "__main__":
    main()
