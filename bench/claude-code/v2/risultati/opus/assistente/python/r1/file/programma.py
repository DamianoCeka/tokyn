"""Assistente clienti da terminale basato sulle FAQ del negozio.

Uso: python programma.py  (dalla cartella che contiene faq.txt)
Ogni riga letta dallo standard input è un messaggio del cliente; "esci" termina.
"""

import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
FILE_FAQ = Path("faq.txt")

ISTRUZIONI = """Sei l'assistente clienti del negozio online descritto nelle FAQ qui sotto. \
Rispondi in italiano, in modo cortese e conciso, come in una chat di assistenza.

Regole:
- Usa solo le informazioni contenute nelle FAQ. Non inventare prezzi, tempi, politiche o servizi.
- Puoi combinare più FAQ o fare semplici calcoli a partire da esse (ad esempio sommare costi).
- Se la risposta non si trova nelle FAQ, dillo chiaramente al cliente (ad esempio: "Mi dispiace, \
questa informazione non è presente nelle nostre FAQ") e suggerisci di contattare il servizio clienti. \
Non tentare di indovinare.
- Tieni conto di quello che il cliente ha detto in precedenza nella conversazione.
- Scrivi testo semplice, senza formattazione Markdown.

<faq>
{faq}
</faq>"""


def testo_risposta(risposta) -> str:
    if risposta.stop_reason == "refusal":
        return "Mi dispiace, non posso rispondere a questa richiesta."
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    return testo or "Mi dispiace, non sono riuscito a formulare una risposta."


def main() -> None:
    try:
        faq = FILE_FAQ.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        sys.exit(f"Errore: file {FILE_FAQ} non trovato nella cartella corrente.")

    client = anthropic.Anthropic()
    if not (client.api_key or client.auth_token):
        sys.exit("Errore: nessuna credenziale trovata. Imposta la variabile d'ambiente ANTHROPIC_API_KEY.")
    # Le FAQ stanno nel system prompt (stabile), così vengono messe in cache tra un turno e l'altro.
    system = [{
        "type": "text",
        "text": ISTRUZIONI.format(faq=faq),
        "cache_control": {"type": "ephemeral"},
    }]
    messaggi = []

    for riga in sys.stdin:
        messaggio = riga.strip()
        if not messaggio:
            continue
        if messaggio.lower() == "esci":
            break

        messaggi.append({"role": "user", "content": messaggio})
        try:
            risposta = client.beta.messages.create(
                model=MODELLO,
                max_tokens=16000,
                system=system,
                messages=messaggi,
                thinking={"type": "adaptive"},
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIError as e:
            messaggi.pop()  # il turno non è andato a buon fine: non resta nella cronologia
            print(f"Mi dispiace, si è verificato un errore tecnico ({e.__class__.__name__}). Riprova.",
                  flush=True)
            continue

        if risposta.stop_reason == "refusal":
            messaggi.pop()  # un turno rifiutato non resta nella cronologia
        else:
            # La risposta completa (compresi eventuali blocchi di thinking) torna nella cronologia così com'è.
            messaggi.append({"role": "assistant", "content": risposta.content})
        print(testo_risposta(risposta), flush=True)


if __name__ == "__main__":
    main()
