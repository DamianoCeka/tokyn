"""Assistente clienti da terminale che risponde usando le FAQ del negozio (faq.txt).

Uso: python programma.py  (dalla cartella che contiene faq.txt)
Ogni riga letta dallo standard input è un messaggio del cliente; "esci" termina.
Le credenziali si leggono dall'ambiente (ANTHROPIC_API_KEY o profilo `ant auth login`).
"""

import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
FILE_FAQ = Path("faq.txt")

ISTRUZIONI = """Sei l'assistente clienti del negozio online descritto nelle FAQ qui sotto.
Rispondi in italiano, in modo cortese e conciso, come in una chat: testo semplice, senza markdown.

Regole:
- Per le informazioni sul negozio (prezzi, spedizioni, resi, pagamenti, servizi, tempi) usa SOLO le FAQ.
  Non inventare e non dedurre dati che le FAQ non contengono.
- Se la risposta non è nelle FAQ, dillo chiaramente (per esempio: "Mi dispiace, questa informazione
  non è presente nelle nostre FAQ") senza tirare a indovinare. Se le FAQ coprono solo una parte della
  domanda, rispondi a quella parte e di' esplicitamente che il resto non è nelle FAQ.
- Puoi usare quello che il cliente ti ha detto prima nella conversazione (nome, ordine, paese, importo
  del carrello...) e applicarci le FAQ, per esempio per calcolare un costo di spedizione.
- Se il cliente si limita a salutare o ringraziare, rispondi brevemente in modo cordiale.

<faq>
{faq}
</faq>"""


def leggi_faq() -> str:
    try:
        return FILE_FAQ.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        sys.exit(f"Errore: non trovo {FILE_FAQ} nella cartella corrente.")


def blocchi_da_conservare(contenuto):
    """Blocchi della risposta da rimettere nella cronologia.

    Se il modello principale ha rifiutato a metà risposta ed è subentrato il modello di
    riserva, i blocchi non di testo prima dell'ultimo blocco "fallback" vanno scartati.
    """
    indici_fallback = [i for i, b in enumerate(contenuto) if b.type == "fallback"]
    if not indici_fallback:
        return list(contenuto)
    confine = indici_fallback[-1]
    return [b for i, b in enumerate(contenuto) if i > confine or b.type == "text"]


def rispondi(client, sistema, cronologia):
    risposta = client.beta.messages.create(
        model=MODELLO,
        max_tokens=16000,
        system=sistema,
        messages=cronologia,
        output_config={"effort": "low"},
        cache_control={"type": "ephemeral"},
        # Se il modello rifiuta per motivi di policy, l'API riprova su un modello di riserva.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if risposta.stop_reason == "refusal":
        return None, "Mi dispiace, non posso aiutarti con questa richiesta."
    testo = "".join(b.text for b in risposta.content if b.type == "text").strip()
    if risposta.stop_reason == "max_tokens":
        testo += " [...]"
    blocchi = [b.model_dump(exclude_none=True) for b in blocchi_da_conservare(risposta.content)]
    return blocchi, testo or "Mi dispiace, non sono riuscito a formulare una risposta."


def main():
    for flusso in (sys.stdin, sys.stdout):
        flusso.reconfigure(encoding="utf-8")

    sistema = ISTRUZIONI.format(faq=leggi_faq())
    client = anthropic.Anthropic()
    if not (client.api_key or client.auth_token or client.credentials):
        sys.exit("Errore: credenziali Anthropic mancanti (imposta ANTHROPIC_API_KEY o usa `ant auth login`).")
    cronologia = []
    interattivo = sys.stdin.isatty()

    while True:
        if interattivo:
            print("Tu: ", end="", flush=True)
        riga = sys.stdin.readline()
        if not riga:  # fine dell'input
            break
        messaggio = riga.strip()
        if not messaggio:
            continue
        if messaggio.lower() == "esci":
            print("Grazie per averci contattato, a presto!")
            break

        cronologia.append({"role": "user", "content": messaggio})
        try:
            blocchi, testo = rispondi(client, sistema, cronologia)
        except anthropic.AuthenticationError:
            sys.exit("Errore: credenziali Anthropic mancanti o non valide (imposta ANTHROPIC_API_KEY).")
        except anthropic.RateLimitError:
            cronologia.pop()
            print("Il servizio è momentaneamente sovraccarico, riprova tra poco.", flush=True)
            continue
        except anthropic.APIStatusError as e:
            cronologia.pop()
            print(f"Si è verificato un errore del servizio ({e.status_code}), riprova.", flush=True)
            continue
        except anthropic.APIConnectionError:
            cronologia.pop()
            print("Impossibile contattare il servizio, controlla la connessione e riprova.", flush=True)
            continue

        if blocchi is None:
            cronologia.pop()  # richiesta rifiutata: non la teniamo nella conversazione
        else:
            cronologia.append({"role": "assistant", "content": blocchi})
        print(f"{'Assistente: ' if interattivo else ''}{testo}", flush=True)


if __name__ == "__main__":
    main()
