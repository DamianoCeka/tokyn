"""Prepara la scheda di un articolo di giornale usando Claude.

Legge `articolo.txt` dalla cartella corrente e scrive `risultato.json` con:
  - titolo: un titolo breve
  - punti:  esattamente cinque punti chiave, una frase ciascuno
  - citati: persone e organizzazioni citate, ognuna una volta sola

Uso:  python programma.py
"""

import asyncio
import json
import re
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

FILE_ARTICOLO = Path("articolo.txt")
FILE_RISULTATO = Path("risultato.json")
TENTATIVI = 3

SCHEMA = {
    "type": "object",
    "properties": {
        "titolo": {"type": "string"},
        "punti": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 5,
            "maxItems": 5,
        },
        "citati": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titolo", "punti", "citati"],
    "additionalProperties": False,
}

ISTRUZIONI = """\
Sei un redattore che prepara ogni mattina, per i colleghi, una scheda sintetica
degli articoli di giornale. Scrivi sempre in italiano, attenendoti a ciò che dice
l'articolo, senza aggiungere informazioni o commenti.

La scheda contiene:
- "titolo": un titolo breve e informativo (al massimo una decina di parole, senza punto finale).
- "punti": esattamente cinque punti chiave, in ordine di importanza. Ogni punto è
  UNA sola frase completa, che termina con un punto.
- "citati": le persone e le organizzazioni citate nell'articolo con un nome proprio
  (enti, aziende, ospedali, associazioni, fondazioni...). Regole:
  * ogni persona o organizzazione compare UNA sola volta;
  * per le persone usa nome e cognome completi come compaiono nell'articolo
    (se una persona è citata prima per esteso e poi solo per cognome, è la stessa);
  * niente ruoli, titoli o descrizioni accanto al nome (es. "Marco Tessari", non
    "il direttore Marco Tessari");
  * per le organizzazioni usa il nome proprio, senza la parola descrittiva che lo
    precede se non ne fa parte (es. "l'ospedale Santa Chiara" -> "Santa Chiara",
    ma "Fondazione Rinaldi" resta così perché è il nome dell'ente);
  * non includere gruppi generici senza nome proprio (es. "i sindacati", "le famiglie")
    né luoghi geografici;
  * elencali nell'ordine in cui compaiono la prima volta.
"""


def una_frase(testo: str) -> bool:
    """Vero se il testo è una sola frase (nessun punto fermo seguito da un'altra frase)."""
    return not re.search(r"[.!?]\s+[A-ZÀ-Ý«\"]", testo.strip())


def pulisci(dati: dict) -> dict:
    """Normalizza la scheda e toglie i doppioni da `citati`."""
    titolo = " ".join(dati["titolo"].split()).rstrip(".")
    punti = [" ".join(p.split()) for p in dati["punti"]]

    citati, visti = [], set()
    for nome in dati["citati"]:
        nome = " ".join(nome.split())
        chiave = nome.casefold()
        if nome and chiave not in visti:
            visti.add(chiave)
            citati.append(nome)

    return {"titolo": titolo, "punti": punti, "citati": citati}


def problemi(scheda: dict) -> list[str]:
    """Elenca cosa non va nella scheda (lista vuota se è valida)."""
    errori = []
    if not scheda["titolo"]:
        errori.append("il titolo è vuoto")
    if len(scheda["punti"]) != 5:
        errori.append(f"ci sono {len(scheda['punti'])} punti invece di 5")
    for i, punto in enumerate(scheda["punti"], 1):
        if not punto:
            errori.append(f"il punto {i} è vuoto")
        elif not una_frase(punto):
            errori.append(f"il punto {i} contiene più di una frase: {punto!r}")
    if not scheda["citati"]:
        errori.append("l'elenco dei citati è vuoto")
    return errori


async def chiedi_scheda(articolo: str, correzioni: list[str]) -> dict:
    prompt = f"Prepara la scheda di questo articolo.\n\n<articolo>\n{articolo}\n</articolo>"
    if correzioni:
        prompt += (
            "\n\nUn tentativo precedente non andava bene per questi motivi; evitali:\n- "
            + "\n- ".join(correzioni)
        )

    opzioni = ClaudeAgentOptions(
        system_prompt=ISTRUZIONI,
        tools=[],  # basta leggere il testo: nessuno strumento (file, shell, web)
        output_format={"type": "json_schema", "schema": SCHEMA},
        max_turns=3,
    )

    risultato = None
    async for messaggio in query(prompt=prompt, options=opzioni):
        if isinstance(messaggio, ResultMessage):
            risultato = messaggio

    if risultato is None:
        raise RuntimeError("Claude non ha restituito alcun risultato")
    if risultato.is_error or risultato.structured_output is None:
        dettaglio = risultato.errors or risultato.result or risultato.subtype
        raise RuntimeError(f"Claude non ha prodotto una scheda valida: {dettaglio}")
    return risultato.structured_output


async def main() -> int:
    if not FILE_ARTICOLO.exists():
        print(f"Errore: non trovo {FILE_ARTICOLO} nella cartella corrente.", file=sys.stderr)
        return 1
    articolo = FILE_ARTICOLO.read_text(encoding="utf-8").strip()
    if not articolo:
        print(f"Errore: {FILE_ARTICOLO} è vuoto.", file=sys.stderr)
        return 1

    correzioni: list[str] = []
    for tentativo in range(1, TENTATIVI + 1):
        try:
            scheda = pulisci(await chiedi_scheda(articolo, correzioni))
        except (RuntimeError, KeyError, TypeError, AttributeError) as e:
            correzioni = [str(e)]
            print(f"Tentativo {tentativo}: {e}", file=sys.stderr)
            continue

        correzioni = problemi(scheda)
        if not correzioni:
            FILE_RISULTATO.write_text(
                json.dumps(scheda, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"Scheda scritta in {FILE_RISULTATO}: {scheda['titolo']}")
            return 0
        print(f"Tentativo {tentativo}: " + "; ".join(correzioni), file=sys.stderr)

    print(f"Errore: nessuna scheda valida dopo {TENTATIVI} tentativi.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
