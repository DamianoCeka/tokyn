"""Prepara la scheda di un articolo di giornale usando Claude.

Legge `articolo.txt` dalla cartella corrente e scrive `risultato.json` con
un titolo breve, i cinque punti chiave e le persone e organizzazioni citate.

Uso:  python programma.py
Richiede il pacchetto `anthropic` e una credenziale (es. ANTHROPIC_API_KEY).
"""

import json
import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
FILE_ARTICOLO = Path("articolo.txt")
FILE_RISULTATO = Path("risultato.json")
NUMERO_PUNTI = 5
TENTATIVI = 3

ISTRUZIONI = """Prepari schede di articoli di giornale per una rassegna stampa interna, in italiano.
Dall'articolo che ti viene dato estrai:

- "titolo": un titolo breve e informativo (al massimo una decina di parole), senza punto finale.
- "punti": esattamente cinque punti chiave, in ordine di importanza. Ogni punto è una sola
  frase completa che termina con un punto e riporta i fatti dell'articolo (numeri, date,
  luoghi quando servono), senza commenti o informazioni esterne.
- "citati": le persone e le organizzazioni nominate nell'articolo, ciascuna una sola volta.
  Per le persone usa nome e cognome completi anche se in alcuni passaggi compare solo il
  cognome. Per le organizzazioni usa il nome proprio (es. "Fondazione Rinaldi"). Includi
  solo soggetti identificati da un nome proprio, non categorie generiche come "i sindacati"
  o "le famiglie". Elencali nell'ordine in cui compaiono."""

SCHEMA = {
    "type": "object",
    "properties": {
        "titolo": {"type": "string"},
        "punti": {"type": "array", "items": {"type": "string"}},
        "citati": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titolo", "punti", "citati"],
    "additionalProperties": False,
}


def chiedi_scheda(client: anthropic.Anthropic, articolo: str) -> dict:
    response = client.beta.messages.create(
        model=MODELLO,
        max_tokens=16000,
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": f"<articolo>\n{articolo}\n</articolo>"}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        # Se il modello declina la richiesta, l'API la ripete su un modello di riserva.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato di elaborare l'articolo.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("La risposta di Claude è stata troncata.")
    testo = next(b.text for b in response.content if b.type == "text")
    return json.loads(testo)


def senza_doppioni(nomi: list[str]) -> list[str]:
    visti = set()
    risultato = []
    for nome in nomi:
        nome = " ".join(nome.split())
        chiave = nome.casefold()
        if nome and chiave not in visti:
            visti.add(chiave)
            risultato.append(nome)
    return risultato


def main() -> int:
    if not FILE_ARTICOLO.is_file():
        print(f"Non trovo {FILE_ARTICOLO} nella cartella corrente.", file=sys.stderr)
        return 1
    articolo = FILE_ARTICOLO.read_text(encoding="utf-8").strip()
    if not articolo:
        print(f"{FILE_ARTICOLO} è vuoto.", file=sys.stderr)
        return 1

    client = anthropic.Anthropic()
    scheda = None
    for tentativo in range(1, TENTATIVI + 1):
        try:
            dati = chiedi_scheda(client, articolo)
        except anthropic.AuthenticationError:
            print("Credenziali Anthropic non valide (ANTHROPIC_API_KEY).", file=sys.stderr)
            return 1
        except TypeError as e:
            # L'SDK solleva TypeError quando non trova nessuna credenziale.
            if "authentication" not in str(e):
                raise
            print("Manca la chiave: imposta ANTHROPIC_API_KEY prima di avviare il programma.", file=sys.stderr)
            return 1
        except anthropic.APIConnectionError:
            print("Impossibile contattare l'API di Anthropic: controlla la connessione.", file=sys.stderr)
            return 1
        except anthropic.APIStatusError as e:
            print(f"Errore dall'API di Anthropic ({e.status_code}): {e.message}", file=sys.stderr)
            return 1
        except RuntimeError as e:
            print(e, file=sys.stderr)
            return 1

        punti = [p.strip() for p in dati["punti"] if p.strip()]
        titolo = dati["titolo"].strip()
        if titolo and len(punti) == NUMERO_PUNTI:
            scheda = {"titolo": titolo, "punti": punti, "citati": senza_doppioni(dati["citati"])}
            break
        print(f"Tentativo {tentativo}: ricevuti {len(punti)} punti invece di {NUMERO_PUNTI}, riprovo.",
              file=sys.stderr)

    if scheda is None:
        print("Claude non ha prodotto una scheda valida.", file=sys.stderr)
        return 1

    FILE_RISULTATO.write_text(json.dumps(scheda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scheda scritta in {FILE_RISULTATO}: {scheda['titolo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
