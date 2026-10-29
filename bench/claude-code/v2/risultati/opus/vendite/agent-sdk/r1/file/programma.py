"""Fatturato trimestrale per paese, migliori clienti e riassunto per la direzione.

Uso: dalla cartella che contiene ordini.csv e clienti.csv
    python programma.py
Scrive risultato.json nella stessa cartella.
"""

import asyncio
import csv
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

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


def leggi_csv(percorso, colonne_attese):
    # utf-8-sig: tollera il BOM che alcuni gestionali/Excel aggiungono in testa al file
    with open(percorso, newline="", encoding="utf-8-sig") as f:
        lettore = csv.DictReader(f)
        mancanti = set(colonne_attese) - set(lettore.fieldnames or [])
        if mancanti:
            sys.exit(f"Errore: in {percorso} mancano le colonne {sorted(mancanti)}")
        # salta le righe completamente vuote (es. a fine file)
        return [r for r in lettore if any((v or "").strip() for v in r.values())]


def carica_clienti():
    clienti = {}
    for n, riga in enumerate(leggi_csv(FILE_CLIENTI, ["id", "nome", "paese"]), start=2):
        id_cliente = riga["id"].strip()
        if id_cliente in clienti:
            sys.exit(f"Errore: {FILE_CLIENTI} riga {n}: id cliente {id_cliente} duplicato")
        clienti[id_cliente] = {"nome": riga["nome"].strip(), "paese": riga["paese"].strip()}
    return clienti


def carica_ordini(clienti):
    ordini = []
    for n, riga in enumerate(leggi_csv(FILE_ORDINI, ["id", "cliente_id", "data", "importo"]), start=2):
        id_cliente = riga["cliente_id"].strip()
        if id_cliente not in clienti:
            sys.exit(f"Errore: {FILE_ORDINI} riga {n}: cliente_id {id_cliente} non presente in {FILE_CLIENTI}")
        try:
            importo = Decimal(riga["importo"].strip())
        except InvalidOperation:
            sys.exit(f"Errore: {FILE_ORDINI} riga {n}: importo non valido {riga['importo']!r}")
        ordini.append((id_cliente, importo))
    return ordini


def calcola(clienti, ordini):
    # Decimal per evitare errori di arrotondamento dei float sulle somme in euro
    speso = {id_cliente: Decimal(0) for id_cliente in clienti}
    for id_cliente, importo in ordini:
        speso[id_cliente] += importo

    per_paese = {}
    for id_cliente, dati in clienti.items():
        per_paese[dati["paese"]] = per_paese.get(dati["paese"], Decimal(0)) + speso[id_cliente]
    # dal paese con più fatturato al meno; a parità, in ordine alfabetico
    per_paese = dict(sorted(per_paese.items(), key=lambda kv: (-kv[1], kv[0])))

    # i clienti senza ordini non entrano in classifica; a parità di spesa, ordine alfabetico
    classifica = sorted(
        (id_cliente for id_cliente in clienti if speso[id_cliente] > 0),
        key=lambda c: (-speso[c], clienti[c]["nome"]),
    )
    migliori = [(clienti[c]["nome"], speso[c]) for c in classifica[:3]]
    return per_paese, migliori


def euro(valore):
    """Formatta un importo all'italiana: 15230.5 -> '15.230,50 euro'."""
    testo = f"{valore.quantize(CENTESIMO, ROUND_HALF_UP):,.2f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".") + " euro"


async def scrivi_riassunto(per_paese, migliori, num_ordini):
    totale = sum(per_paese.values())
    paese_top, fatturato_top = next(iter(per_paese.items()))
    righe_paesi = "\n".join(
        f"- {p}: {euro(v)} ({f'{v / totale * 100:.1f}'.replace('.', ',')}% del totale)" if totale else f"- {p}: {euro(v)}"
        for p, v in per_paese.items()
    )
    righe_clienti = "\n".join(f"{i}. {nome}: {euro(v)}" for i, (nome, v) in enumerate(migliori, 1))

    prompt = f"""Dati del trimestre ({num_ordini} ordini, fatturato totale {euro(totale)}).

Fatturato per paese:
{righe_paesi}

Paese con il fatturato più alto: {paese_top} ({euro(fatturato_top)}).

I 3 clienti che hanno speso di più:
{righe_clienti}

Scrivi un breve paragrafo (4-6 frasi) per la direzione aziendale. Deve dire chiaramente qual è il paese \
con il fatturato più alto e commentare i numeri (peso dei paesi sul totale, concentrazione sui clienti \
principali). Usa solo i numeri forniti sopra, scritti nello stesso formato, senza inventarne altri. \
Rispondi solo con il paragrafo, in italiano, senza titoli, elenchi o formattazione markdown."""

    opzioni = ClaudeAgentOptions(
        model=MODELLO,
        system_prompt="Sei un analista commerciale che scrive sintesi chiare e sobrie per la direzione.",
        tools=[],              # nessuno strumento: deve solo scrivere testo
        max_turns=1,
        setting_sources=[],    # non caricare impostazioni/CLAUDE.md dalla cartella
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
        raise RuntimeError(f"Claude non ha prodotto il riassunto: {dettaglio}")
    riassunto = (esito.result or "".join(testo)).strip()
    if not riassunto:
        raise RuntimeError("Claude ha restituito un riassunto vuoto")
    return riassunto


def main():
    clienti = carica_clienti()
    ordini = carica_ordini(clienti)
    if not ordini:
        sys.exit(f"Errore: {FILE_ORDINI} non contiene ordini")
    per_paese, migliori = calcola(clienti, ordini)

    try:
        riassunto = asyncio.run(scrivi_riassunto(per_paese, migliori, len(ordini)))
    except Exception as e:
        sys.exit(f"Errore durante la generazione del riassunto con Claude: {e}")

    risultato = {
        "fatturato_per_paese": {p: float(v.quantize(CENTESIMO, ROUND_HALF_UP)) for p, v in per_paese.items()},
        "migliori_clienti": [nome for nome, _ in migliori],
        "riassunto": riassunto,
    }
    with open(FILE_RISULTATO, "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Scritto {FILE_RISULTATO}")


if __name__ == "__main__":
    main()
