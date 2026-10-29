"""Prepara la scheda di un articolo di giornale con Claude.

Legge `articolo.txt` dalla cartella corrente e scrive `risultato.json`.
Serve la variabile d'ambiente ANTHROPIC_API_KEY (o un profilo `ant auth login`).
"""

import json
import sys
from pathlib import Path

import anthropic
from pydantic import BaseModel

MODELLO = "claude-opus-5-5"
N_PUNTI = 5
TENTATIVI = 3

ISTRUZIONI = f"""Prepari schede di articoli di giornale per dei colleghi. Rispondi in italiano.

- titolo: un titolo breve (al massimo dieci parole circa), senza punto finale.
- punti: esattamente {N_PUNTI} punti chiave dell'articolo, ciascuno una sola frase compiuta.
- citati: i nomi delle persone e delle organizzazioni citate nell'articolo, ognuno una sola volta, \
con il nome completo come appare nel testo (senza titoli o ruoli). Includi solo persone e \
organizzazioni, non luoghi."""


class Scheda(BaseModel):
    titolo: str
    punti: list[str]
    citati: list[str]


def senza_duplicati(nomi):
    visti = set()
    risultato = []
    for nome in nomi:
        nome = " ".join(nome.split())
        chiave = nome.casefold()
        if nome and chiave not in visti:
            visti.add(chiave)
            risultato.append(nome)
    return risultato


def prepara_scheda(client, articolo):
    messaggi = [{"role": "user", "content": f"<articolo>\n{articolo}\n</articolo>"}]
    for _ in range(TENTATIVI):
        risposta = client.messages.parse(
            model=MODELLO,
            max_tokens=16000,
            system=ISTRUZIONI,
            messages=messaggi,
            output_format=Scheda,
        )
        if risposta.stop_reason == "refusal":
            raise RuntimeError("Claude ha rifiutato di elaborare l'articolo.")
        scheda = risposta.parsed_output
        if scheda is not None and len(scheda.punti) == N_PUNTI:
            return {
                "titolo": scheda.titolo.strip(),
                "punti": [p.strip() for p in scheda.punti],
                "citati": senza_duplicati(scheda.citati),
            }
        trovati = "nessun risultato valido" if scheda is None else f"{len(scheda.punti)} punti"
        messaggi = [
            messaggi[0],
            {"role": "assistant", "content": risposta.content},
            {"role": "user", "content": f"Hai restituito {trovati}: servono esattamente {N_PUNTI} punti. Riprova."},
        ]
    raise RuntimeError(f"Dopo {TENTATIVI} tentativi non ho ottenuto esattamente {N_PUNTI} punti.")


def main():
    percorso = Path("articolo.txt")
    if not percorso.is_file():
        sys.exit("Non trovo articolo.txt nella cartella corrente.")
    articolo = percorso.read_text(encoding="utf-8").strip()
    if not articolo:
        sys.exit("articolo.txt è vuoto.")

    try:
        scheda = prepara_scheda(anthropic.Anthropic(), articolo)
    except TypeError as e:
        if "authentication" in str(e):
            sys.exit("Credenziali mancanti: imposta ANTHROPIC_API_KEY.")
        raise
    except anthropic.AuthenticationError:
        sys.exit("Autenticazione fallita: controlla ANTHROPIC_API_KEY.")
    except anthropic.APIError as e:
        sys.exit(f"Errore dell'API Anthropic: {e}")
    except RuntimeError as e:
        sys.exit(str(e))

    Path("risultato.json").write_text(json.dumps(scheda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Scheda scritta in risultato.json")


if __name__ == "__main__":
    main()
