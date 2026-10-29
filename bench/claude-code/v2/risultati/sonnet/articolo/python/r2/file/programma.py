"""Prepara la scheda di un articolo di giornale usando Claude.

Legge articolo.txt dalla cartella corrente e scrive risultato.json.
Richiede il pacchetto `anthropic` e la variabile ANTHROPIC_API_KEY.
"""

import json
import os
import sys
from pathlib import Path

import anthropic

MODELLO = "claude-opus-5-5"
N_PUNTI = 5
TENTATIVI = 3

ISTRUZIONI = f"""Prepari schede di articoli di giornale per dei colleghi.
Dall'articolo che ricevi ricava:
- titolo: un titolo breve (al massimo una dozzina di parole), in italiano, senza punto finale;
- punti: esattamente {N_PUNTI} punti chiave, ciascuno una sola frase compiuta in italiano,
  basata solo su quanto scritto nell'articolo;
- citati: i nomi delle persone e delle organizzazioni citate nell'articolo, ognuno una sola volta,
  nella forma più completa che compare nel testo (es. "Marco Tessari", non "Tessari").
  Escludi luoghi, edifici e reparti, a meno che siano essi stessi un ente (azienda, associazione,
  fondazione, ospedale come istituzione, sindacato). Se un ente è nominato solo in modo generico
  (es. "i sindacati degli infermieri") includilo con la dicitura usata nel testo."""

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


def valida(scheda):
    titolo = scheda["titolo"].strip()
    punti = [p.strip() for p in scheda["punti"] if p.strip()]
    if not titolo:
        raise ValueError("titolo vuoto")
    if len(punti) != N_PUNTI:
        raise ValueError(f"attesi {N_PUNTI} punti, ricevuti {len(punti)}")
    return {"titolo": titolo, "punti": punti, "citati": senza_duplicati(scheda["citati"])}


def prepara_scheda(client, testo):
    errore = None
    for _ in range(TENTATIVI):
        risposta = client.messages.create(
            model=MODELLO,
            max_tokens=16000,
            system=ISTRUZIONI,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": f"<articolo>\n{testo}\n</articolo>"}],
        )
        if risposta.stop_reason == "refusal":
            raise RuntimeError("Claude ha rifiutato di elaborare l'articolo")
        if risposta.stop_reason == "max_tokens":
            errore = ValueError("risposta troncata")
            continue
        try:
            blocco = next(b for b in risposta.content if b.type == "text")
            return valida(json.loads(blocco.text))
        except (StopIteration, KeyError, TypeError, ValueError) as e:
            errore = e
    raise RuntimeError(f"Risposta non valida dopo {TENTATIVI} tentativi: {errore}")


def main():
    percorso = Path("articolo.txt")
    if not percorso.is_file():
        sys.exit("Non trovo articolo.txt nella cartella corrente.")
    testo = percorso.read_text(encoding="utf-8").strip()
    if not testo:
        sys.exit("articolo.txt è vuoto.")

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("Manca la chiave: imposta la variabile d'ambiente ANTHROPIC_API_KEY.")

    try:
        scheda = prepara_scheda(anthropic.Anthropic(), testo)
    except anthropic.AnthropicError as e:
        sys.exit(f"Errore nella chiamata a Claude: {e}")
    except RuntimeError as e:
        sys.exit(str(e))

    Path("risultato.json").write_text(
        json.dumps(scheda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Scheda scritta in risultato.json")


if __name__ == "__main__":
    main()
