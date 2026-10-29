"""Fatturato trimestrale per paese e migliori clienti, con riassunto per la direzione.

Uso: dalla cartella che contiene ordini.csv e clienti.csv
    python programma.py

Richiede il pacchetto `anthropic` (pip install anthropic) e una credenziale
Anthropic (per esempio la variabile d'ambiente ANTHROPIC_API_KEY).
Scrive risultato.json nella stessa cartella.
"""

import csv
import json
import sys
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import anthropic

MODELLO = "claude-opus-5-5"
CENTESIMO = Decimal("0.01")


def leggi_csv(nome_file):
    # utf-8-sig: tollera il BOM che alcuni gestionali aggiungono in testa al file
    with open(nome_file, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def euro(valore):
    """Formatta un importo all'italiana: 15230.5 -> '15.230,50'."""
    testo = f"{Decimal(valore).quantize(CENTESIMO, rounding=ROUND_HALF_UP):,.2f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".")


def calcola(clienti, ordini):
    nomi = {}
    paesi = {}
    for riga in clienti:
        id_cliente = riga["id"].strip()
        nomi[id_cliente] = riga["nome"].strip()
        paesi[id_cliente] = riga["paese"].strip()

    speso = defaultdict(Decimal)
    for riga in ordini:
        id_cliente = riga["cliente_id"].strip()
        if id_cliente not in nomi:
            print(
                f"Attenzione: l'ordine {riga['id']} si riferisce al cliente "
                f"{id_cliente}, che non è in clienti.csv; l'ordine viene ignorato.",
                file=sys.stderr,
            )
            continue
        try:
            speso[id_cliente] += Decimal(riga["importo"].strip())
        except InvalidOperation:
            sys.exit(f"Errore: importo non valido nell'ordine {riga['id']}: {riga['importo']!r}")

    # Ogni paese presente in clienti.csv compare, anche se nel trimestre non ha ordini
    fatturato = {paese: Decimal(0) for paese in paesi.values()}
    for id_cliente, totale in speso.items():
        fatturato[paesi[id_cliente]] += totale
    fatturato = {
        paese: totale.quantize(CENTESIMO, rounding=ROUND_HALF_UP)
        for paese, totale in sorted(fatturato.items(), key=lambda kv: (-kv[1], kv[0]))
    }

    # A parità di spesa decide l'ordine alfabetico, così il risultato è stabile
    classifica = sorted(speso.items(), key=lambda kv: (-kv[1], nomi[kv[0]]))
    migliori = [(nomi[id_cliente], totale) for id_cliente, totale in classifica[:3]]

    return fatturato, migliori


def scrivi_riassunto(fatturato, migliori):
    massimo = max(fatturato.values())
    paesi_in_testa = [paese for paese, totale in fatturato.items() if totale == massimo]
    totale = sum(fatturato.values())

    def quota(valore):
        if not totale:
            return ""
        percentuale = f"{valore / totale * 100:.1f}".replace(".", ",")
        return f" ({percentuale}% del totale)"

    righe_paesi = "\n".join(
        f"- {paese}: {euro(valore)} euro{quota(valore)}" for paese, valore in fatturato.items()
    )
    righe_clienti = "\n".join(
        f"{posizione}. {nome}: {euro(valore)} euro"
        for posizione, (nome, valore) in enumerate(migliori, start=1)
    )

    dati = f"""Fatturato del trimestre per paese (dal più alto al più basso):
{righe_paesi}

Fatturato totale: {euro(totale)} euro
Paese con il fatturato più alto: {", ".join(paesi_in_testa)}

Clienti che hanno speso di più:
{righe_clienti}"""

    client = anthropic.Anthropic()
    risposta = client.beta.messages.create(
        model=MODELLO,
        max_tokens=16000,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=(
            "Scrivi in italiano per la direzione di un'azienda. Rispondi solo con un "
            "breve paragrafo (3-5 frasi) di testo semplice, senza titoli, elenchi o "
            "formattazione markdown."
        ),
        messages=[{
            "role": "user",
            "content": (
                "Ecco i numeri del trimestre, già calcolati e verificati:\n\n"
                f"{dati}\n\n"
                "Scrivi un breve paragrafo che dica qual è il paese con il fatturato più "
                "alto e commenti i numeri (peso dei paesi sul totale, migliori clienti). "
                "Usa esattamente le cifre fornite, nel formato italiano in cui sono "
                "scritte, e non inventare dati che non sono qui (per esempio confronti "
                "con trimestri precedenti)."
            ),
        }],
    )

    if risposta.stop_reason == "refusal":
        sys.exit("Errore: Claude ha rifiutato di scrivere il riassunto.")
    testo = "".join(blocco.text for blocco in risposta.content if blocco.type == "text").strip()
    if not testo:
        sys.exit(f"Errore: Claude non ha restituito testo (stop_reason={risposta.stop_reason}).")
    return testo


def main():
    try:
        clienti = leggi_csv("clienti.csv")
        ordini = leggi_csv("ordini.csv")
    except FileNotFoundError as errore:
        sys.exit(f"Errore: file non trovato: {errore.filename}. "
                 "Avvia il programma dalla cartella che contiene i due CSV.")

    fatturato, migliori = calcola(clienti, ordini)
    if not fatturato:
        sys.exit("Errore: clienti.csv non contiene clienti.")

    try:
        riassunto = scrivi_riassunto(fatturato, migliori)
    except anthropic.AuthenticationError:
        sys.exit("Errore: credenziale Anthropic non valida (controlla ANTHROPIC_API_KEY).")
    except TypeError as errore:
        # L'SDK solleva TypeError quando non trova nessuna credenziale
        if "authentication" not in str(errore):
            raise
        sys.exit("Errore: credenziale Anthropic mancante (imposta ANTHROPIC_API_KEY).")
    except anthropic.RateLimitError:
        sys.exit("Errore: limite di richieste Anthropic raggiunto, riprova tra qualche minuto.")
    except anthropic.APIStatusError as errore:
        sys.exit(f"Errore dall'API Anthropic ({errore.status_code}): {errore.message}")
    except anthropic.APIConnectionError:
        sys.exit("Errore: impossibile collegarsi all'API Anthropic, controlla la connessione.")

    risultato = {
        "fatturato_per_paese": {paese: float(valore) for paese, valore in fatturato.items()},
        "migliori_clienti": [nome for nome, _ in migliori],
        "riassunto": riassunto,
    }
    with open("risultato.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Fatto: risultato scritto in risultato.json")


if __name__ == "__main__":
    main()
