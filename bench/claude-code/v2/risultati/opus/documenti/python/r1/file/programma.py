"""Risponde alle domande in domande.txt usando i documenti in docs/ e scrive risultato.json."""

import json
import sys
from pathlib import Path

import anthropic

CARTELLA_DOCS = Path("docs")
FILE_DOMANDE = Path("domande.txt")
FILE_RISULTATO = Path("risultato.json")
MODELLO = "claude-opus-5-5"
NESSUNA_FONTE = "NESSUNA"

ISTRUZIONI = """Sei l'assistente interno dell'azienda e rispondi alle domande dei colleghi.
Usa esclusivamente le informazioni contenute nei documenti forniti qui sotto, senza aggiungere
conoscenze esterne o supposizioni. Rispondi in italiano, in modo breve e diretto (una frase al massimo).
In "fonte" indica il nome del file del documento da cui hai preso la risposta.
Se nessun documento contiene la risposta, scrivi in "risposta" che l'informazione non è presente
nei documenti e metti "fonte" a "NESSUNA"."""


def carica_documenti():
    documenti = {p.name: p.read_text(encoding="utf-8") for p in sorted(CARTELLA_DOCS.glob("*.txt"))}
    if not documenti:
        sys.exit(f"Nessun file .txt trovato in {CARTELLA_DOCS}/")
    return documenti


def carica_domande():
    righe = FILE_DOMANDE.read_text(encoding="utf-8").splitlines()
    return [r.strip() for r in righe if r.strip()]


def costruisci_system(documenti):
    blocchi = [
        f'<documento nome="{nome}">\n{testo.strip()}\n</documento>' for nome, testo in documenti.items()
    ]
    return [
        {
            "type": "text",
            "text": ISTRUZIONI + "\n\n<documenti>\n" + "\n\n".join(blocchi) + "\n</documenti>",
            # I documenti sono uguali per tutte le domande: li mettiamo in cache.
            "cache_control": {"type": "ephemeral"},
        }
    ]


def schema_risposta(nomi_file):
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "risposta": {"type": "string"},
                "fonte": {"type": "string", "enum": [*nomi_file, NESSUNA_FONTE]},
            },
            "required": ["risposta", "fonte"],
            "additionalProperties": False,
        },
    }


def rispondi(client, system, formato, domanda):
    response = client.beta.messages.create(
        model=MODELLO,
        max_tokens=16000,
        system=system,
        output_config={"effort": "low", "format": formato},
        # Se il modello rifiuta la richiesta, l'API la ripete su un modello di riserva.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": domanda}],
    )
    if response.stop_reason == "refusal":
        return {"risposta": "Il modello si è rifiutato di rispondere a questa domanda.", "fonte": None}
    if response.stop_reason == "max_tokens":
        return {"risposta": "Risposta interrotta: limite di token raggiunto.", "fonte": None}
    testo = next(b.text for b in response.content if b.type == "text")
    dati = json.loads(testo)
    fonte = None if dati["fonte"] == NESSUNA_FONTE else dati["fonte"]
    return {"risposta": dati["risposta"], "fonte": fonte}


def main():
    documenti = carica_documenti()
    domande = carica_domande()
    system = costruisci_system(documenti)
    formato = schema_risposta(list(documenti))

    client = anthropic.Anthropic()
    risultato = []
    for i, domanda in enumerate(domande, 1):
        print(f"[{i}/{len(domande)}] {domanda}")
        try:
            esito = rispondi(client, system, formato, domanda)
        except TypeError as e:
            # L'SDK solleva TypeError quando non trova credenziali.
            sys.exit(f"Credenziali Anthropic mancanti: imposta ANTHROPIC_API_KEY. ({e})")
        except anthropic.APIError as e:
            print(f"  errore: {e}", file=sys.stderr)
            esito = {"risposta": f"Errore durante la richiesta: {e}", "fonte": None}
        print(f"  -> {esito['risposta']} ({esito['fonte']})")
        risultato.append({"domanda": domanda, **esito})

    FILE_RISULTATO.write_text(json.dumps(risultato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scritto {FILE_RISULTATO} con {len(risultato)} risposte.")


if __name__ == "__main__":
    main()
