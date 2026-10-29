"""Assistente clienti da terminale basato sulle FAQ del negozio (faq.txt) e su Claude.

Uso: python programma.py   (dalla cartella che contiene faq.txt)
Ogni riga letta da stdin è un messaggio del cliente; "esci" termina il programma.
Richiede la variabile d'ambiente ANTHROPIC_API_KEY (o un profilo `ant auth login`).
"""

import sys

import anthropic

MODELLO = "claude-opus-5-5"
FILE_FAQ = "faq.txt"

ISTRUZIONI = """\
Sei l'assistente clienti di un negozio online. Rispondi alle domande dei clienti \
usando esclusivamente le FAQ qui sotto.

Regole:
- Usa solo informazioni presenti nelle FAQ. Non inventare prezzi, tempi, politiche o altri dettagli.
- Se la risposta non è nelle FAQ (o lo è solo in parte), dillo chiaramente: di' cosa non sai \
e suggerisci di contattare direttamente il negozio. Se una parte della domanda è coperta dalle FAQ, \
rispondi a quella parte.
- Ricorda quello che il cliente ha detto prima nella conversazione (nome, ordine, paese, ecc.) \
e usalo quando serve, anche per applicare le FAQ al suo caso (ad esempio calcolare se ha diritto \
alla spedizione gratuita). Le informazioni date dal cliente su di sé sono affidabili; \
quelle sul negozio vengono solo dalle FAQ.
- Rispondi nella lingua del cliente, in modo breve e cortese, in testo semplice (senza Markdown).

<faq>
{faq}
</faq>"""


def carica_faq(percorso):
    try:
        with open(percorso, encoding="utf-8") as f:
            testo = f.read().strip()
    except OSError as e:
        sys.exit(f"Impossibile leggere {percorso}: {e.strerror}")
    if not testo:
        sys.exit(f"{percorso} è vuoto.")
    return testo


def rispondi(client, sistema, cronologia):
    """Invia la cronologia a Claude e restituisce (testo, contenuto_assistente)."""
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=2000,
        system=sistema,
        output_config={"effort": "low"},
        messages=cronologia,
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("la richiesta è stata rifiutata dal modello")
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    if not testo:
        raise RuntimeError("risposta vuota dal modello")
    return testo, risposta.content


def main():
    sistema = ISTRUZIONI.format(faq=carica_faq(FILE_FAQ))
    client = anthropic.Anthropic()
    cronologia = []

    for riga in sys.stdin:
        messaggio = riga.strip()
        if not messaggio:
            continue
        if messaggio.lower() == "esci":
            break

        cronologia.append({"role": "user", "content": messaggio})
        try:
            testo, contenuto = rispondi(client, sistema, cronologia)
        except anthropic.AuthenticationError:
            sys.exit("Errore: credenziali Anthropic non valide (ANTHROPIC_API_KEY).")
        except TypeError as e:
            # l'SDK solleva TypeError quando non trova nessuna credenziale
            if "authentication" not in str(e):
                raise
            sys.exit("Errore: credenziali Anthropic mancanti (imposta ANTHROPIC_API_KEY).")
        except anthropic.APIError as e:
            cronologia.pop()  # il messaggio non è stato elaborato: lo togliamo
            print(f"Errore di servizio, riprova ({type(e).__name__}).", flush=True)
            continue
        except RuntimeError as e:
            cronologia.pop()
            print(f"Non riesco a rispondere: {e}.", flush=True)
            continue

        cronologia.append({"role": "assistant", "content": contenuto})
        print(testo, flush=True)


if __name__ == "__main__":
    main()
