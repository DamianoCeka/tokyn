"""Risponde alle domande in domande.txt sull'inventario in inventario.json usando Claude.

Tutti i calcoli (valori, totali, differenze dalla scorta minima) vengono fatti qui
in Python con Decimal; Claude si limita a leggere i valori già calcolati e a
formulare la risposta, così i numeri sono esatti.
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

import anthropic

MODEL = "claude-opus-5-5"


def euro(x: Decimal) -> str:
    """Formato italiano, es. 1.234,50 €"""
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def prepara_inventario(prodotti: list[dict]) -> str:
    righe = []
    tot_valore = Decimal(0)
    tot_pezzi = 0
    sotto = []
    costo_riordino_tot = Decimal(0)
    for p in prodotti:
        q = int(p["quantita"])
        prezzo = Decimal(str(p["prezzo_unitario"]))
        minima = int(p["scorta_minima"])
        valore = q * prezzo
        mancanti = max(minima - q, 0)
        costo_rip = mancanti * prezzo
        tot_valore += valore
        tot_pezzi += q
        if q < minima:
            sotto.append(p["nome"])
            costo_riordino_tot += costo_rip
        righe.append(
            f"- codice {p['codice']} | {p['nome']} | quantità: {q} | prezzo unitario: {euro(prezzo)}"
            f" | scorta minima: {minima} | valore della scorta: {euro(valore)}"
            f" | sotto scorta minima: {'sì' if q < minima else 'no'}"
            f" | pezzi mancanti alla scorta minima: {mancanti}"
            f" | costo per raggiungere la scorta minima: {euro(costo_rip)}"
        )
    righe.append("")
    righe.append("TOTALI (già calcolati)")
    righe.append(f"- numero di prodotti: {len(prodotti)}")
    righe.append(f"- pezzi totali in magazzino: {tot_pezzi}")
    righe.append(f"- valore totale del magazzino: {euro(tot_valore)}")
    righe.append(f"- prodotti sotto scorta minima ({len(sotto)}): {', '.join(sotto) or 'nessuno'}")
    righe.append(f"- costo totale per riportare i prodotti sotto soglia alla scorta minima: {euro(costo_riordino_tot)}")
    return "\n".join(righe)


def main() -> int:
    prodotti = json.loads(Path("inventario.json").read_text(encoding="utf-8"))
    domande = [r.strip() for r in Path("domande.txt").read_text(encoding="utf-8").splitlines() if r.strip()]

    system = (
        "Sei l'assistente del magazzino. Rispondi in italiano, in modo breve (una o due frasi), "
        "alle domande sull'inventario qui sotto.\n"
        "- Usa SOLO i dati forniti e copia i numeri esattamente come sono scritti: non ricalcolare e non arrotondare. "
        "I valori derivati (valore della scorta, mancanti, totali) sono già calcolati.\n"
        "- Se la domanda non si può risolvere con questi dati, dillo chiaramente invece di inventare.\n"
        "- Se un prodotto citato non esiste, dillo.\n\n"
        "INVENTARIO\n" + prepara_inventario(prodotti)
    )

    try:
        client = anthropic.Anthropic()
        client.messages  # noqa: B018
        client._validate_headers(client.auth_headers, set())
    except TypeError:
        print("Credenziali mancanti: imposta ANTHROPIC_API_KEY e riprova.", file=sys.stderr)
        return 1
    risultato = []
    for domanda in domande:
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=system,
                thinking={"type": "adaptive"},
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": domanda}],
            )
            if msg.stop_reason == "refusal":
                risposta = "Errore: la richiesta è stata rifiutata dal modello."
            else:
                risposta = "".join(b.text for b in msg.content if b.type == "text").strip()
                if not risposta:
                    risposta = "Errore: risposta vuota dal modello."
        except anthropic.APIError as e:
            print(f"Errore API per '{domanda}': {e}", file=sys.stderr)
            risposta = f"Errore: impossibile ottenere la risposta ({type(e).__name__})."
        print(f"{domanda}\n  -> {risposta}")
        risultato.append({"domanda": domanda, "risposta": risposta})

    Path("risultato.json").write_text(json.dumps(risultato, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
