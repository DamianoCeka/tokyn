"""Assistente clienti da terminale per Casa Nespolo.

Legge un messaggio del cliente per riga dallo standard input e stampa la
risposta di Claude, basata esclusivamente sulle FAQ in faq.txt.
Si esce scrivendo "esci" (o chiudendo lo standard input).
"""

import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
FILE_FAQ = "faq.txt"
COMANDO_USCITA = "esci"

ISTRUZIONI = """Sei l'assistente clienti di un negozio online. Rispondi in italiano, \
in modo cortese e conciso, alle domande dei clienti.

Regole:
- Usa SOLO le informazioni contenute nelle FAQ qui sotto. Non inventare prezzi, \
tempi, politiche o altri dettagli che non compaiono nelle FAQ.
- Se la risposta a una domanda non è nelle FAQ, dillo chiaramente al cliente \
(ad esempio: "Mi dispiace, questa informazione non è presente nelle nostre FAQ") \
e non tentare di indovinarla. Se una domanda è coperta solo in parte, rispondi \
alla parte coperta e dichiara che il resto non è nelle FAQ.
- Tieni conto di quello che il cliente ha detto prima nella conversazione \
(nome, ordine, paese, prodotti, ecc.) e usalo per rendere le risposte pertinenti.
- Puoi fare semplici ragionamenti a partire dalle FAQ (ad esempio sommare un \
importo o verificare se un ordine supera la soglia della spedizione gratuita).
- Scrivi testo semplice, adatto a un terminale: niente Markdown.

<faq>
{faq}
</faq>"""


def carica_faq(percorso: Path) -> str:
    try:
        testo = percorso.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        sys.exit(f"Errore: file {percorso} non trovato. Avvia il programma dalla cartella che contiene {FILE_FAQ}.")
    if not testo:
        sys.exit(f"Errore: il file {percorso} è vuoto.")
    return testo


def testo_risposta(risposta) -> str:
    if risposta.stop_reason == "refusal":
        return "Mi dispiace, non posso rispondere a questa richiesta."
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    return testo or "Mi dispiace, non sono riuscito a formulare una risposta. Puoi riformulare la domanda?"


def main() -> None:
    sistema = ISTRUZIONI.format(faq=carica_faq(Path(FILE_FAQ)))
    client = anthropic.Anthropic()
    messaggi = []

    for riga in sys.stdin:
        messaggio = riga.strip()
        if not messaggio:
            continue
        if messaggio.lower() == COMANDO_USCITA:
            break

        messaggi.append({"role": "user", "content": messaggio})
        try:
            risposta = client.beta.messages.create(
                model=MODELLO,
                max_tokens=16000,
                system=sistema,
                messages=messaggi,
                output_config={"effort": "low"},
                cache_control={"type": "ephemeral"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError:
            sys.exit("Errore: credenziali Anthropic non valide (controlla ANTHROPIC_API_KEY).")
        except TypeError as e:
            # L'SDK solleva TypeError se non trova nessuna credenziale.
            if "authentication" not in str(e):
                raise
            sys.exit("Errore: credenziali Anthropic mancanti (imposta ANTHROPIC_API_KEY).")
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError) as e:
            # Errore temporaneo: si scarta il messaggio e si lascia riprovare il cliente.
            messaggi.pop()
            print(f"Il servizio è momentaneamente non disponibile ({type(e).__name__}). Riprova tra poco.", flush=True)
            continue
        except anthropic.APIStatusError as e:
            sys.exit(f"Errore dell'API ({e.status_code}): {e.message}")

        if risposta.stop_reason == "refusal":
            # Non si conserva lo scambio rifiutato, così la conversazione resta valida.
            messaggi.pop()
        else:
            # Si conserva il contenuto completo (anche i blocchi di thinking) senza modificarlo.
            messaggi.append({"role": "assistant", "content": risposta.content})
        print(testo_risposta(risposta), flush=True)


if __name__ == "__main__":
    main()
