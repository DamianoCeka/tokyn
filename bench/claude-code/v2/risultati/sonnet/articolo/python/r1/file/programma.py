"""Prepara la scheda di un articolo di giornale usando Claude.

Legge `articolo.txt` dalla cartella corrente e scrive `risultato.json`.
Richiede la variabile d'ambiente ANTHROPIC_API_KEY (oppure `ant auth login`).
"""

import json
import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
N_PUNTI = 5
TENTATIVI = 3

ISTRUZIONI = f"""Sei il redattore che prepara la scheda di un articolo di giornale per i colleghi.
Scrivi in italiano e usa solo informazioni presenti nell'articolo.

- titolo: breve (al massimo una decina di parole), senza punto finale.
- punti: esattamente {N_PUNTI} punti chiave, ciascuno una sola frase completa, diversi tra loro.
- citati: nomi delle persone e delle organizzazioni (enti, aziende, associazioni, ospedali, \
fondazioni, sindacati...) citate nell'articolo, ognuno una sola volta, con il nome completo \
come appare per primo nel testo. Non includere luoghi, e non includere ruoli senza nome."""

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


def richiedi_scheda(client, articolo):
    risposta = client.messages.create(
        model=MODELLO,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=ISTRUZIONI,
        messages=[{"role": "user", "content": f"<articolo>\n{articolo}\n</articolo>"}],
    )
    if risposta.stop_reason == "refusal":
        raise RuntimeError("Claude ha rifiutato di elaborare l'articolo.")
    if risposta.stop_reason == "max_tokens":
        raise RuntimeError("Risposta troncata (max_tokens).")
    testo = next(b.text for b in risposta.content if b.type == "text")
    return json.loads(testo)


def normalizza(dati):
    """Pulisce la risposta e verifica i vincoli; solleva ValueError se non rispettati."""
    titolo = " ".join(str(dati["titolo"]).split())
    punti = [" ".join(str(p).split()) for p in dati["punti"] if str(p).strip()]
    citati, visti = [], set()
    for nome in dati["citati"]:
        nome = " ".join(str(nome).split())
        if nome and nome.casefold() not in visti:
            visti.add(nome.casefold())
            citati.append(nome)
    if not titolo:
        raise ValueError("titolo vuoto")
    if len(punti) != N_PUNTI:
        raise ValueError(f"{len(punti)} punti invece di {N_PUNTI}")
    return {"titolo": titolo, "punti": punti, "citati": citati}


def main():
    percorso = Path("articolo.txt")
    if not percorso.is_file():
        sys.exit("Non trovo articolo.txt nella cartella corrente.")
    articolo = percorso.read_text(encoding="utf-8").strip()
    if not articolo:
        sys.exit("articolo.txt è vuoto.")

    client = anthropic.Anthropic()
    ultimo_errore = None
    for _ in range(TENTATIVI):
        try:
            scheda = normalizza(richiedi_scheda(client, articolo))
            break
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            ultimo_errore = e  # risposta non conforme: riprova
        except anthropic.AuthenticationError:
            sys.exit("Autenticazione non riuscita: controlla ANTHROPIC_API_KEY.")
        except anthropic.APIError as e:
            sys.exit(f"Errore dell'API Anthropic: {e}")
        except RuntimeError as e:
            sys.exit(str(e))
    else:
        sys.exit(f"Scheda non valida dopo {TENTATIVI} tentativi: {ultimo_errore}")

    Path("risultato.json").write_text(
        json.dumps(scheda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Scritto risultato.json")


if __name__ == "__main__":
    main()
