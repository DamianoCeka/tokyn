"""Controllo di `fattura`: una fattura nascosta di 5 righe (somma vera 439,60 €) che dichiara un totale di 440,60 €.

Passa se risultato.json ha il fornitore (Marchetti), la data 2026-02-18, le 5 righe nell'ordine della fattura con
quantità e prezzi unitari giusti, totale_dichiarato 440,60, totale_calcolato 439,60 e totale_corretto false (booleano). Importi con tolleranza di mezzo
centesimo, anche come testo ("439,60"). 6 punti, uno per requisito; ok solo con 6 su 6.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm, numero

QUI = Path(__file__).resolve().parent
RIGHE = [("carta", 20, 4.35), ("toner", 3, 89.90), ("raccoglitor", 12, 3.20), ("penn", 2, 14.75), ("consegna", 1, 15.00)]
DICHIARATO, CALCOLATO = 440.60, 439.60

ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
dettagli = []
if not isinstance(dati, dict):
    esito(False, 0, 6, ["risultato.json mancante o non è un oggetto JSON"], ex)
punti = 0


def vicino(valore, atteso):
    n = numero(valore)
    return n is not None and abs(n - atteso) < 0.005


fornitore = "marchetti" in norm(dati.get("fornitore", ""))
punti += fornitore
dettagli.append(f"fornitore: {fornitore} ({dati.get('fornitore')!r})")

data = str(dati.get("data", "")).strip() == "2026-02-18"
punti += data
dettagli.append(f"data 2026-02-18: {data} ({dati.get('data')!r})")

righe = dati.get("righe") if isinstance(dati.get("righe"), list) else []
giuste = sum(1 for r, (parola, q, p) in zip(righe, RIGHE) if isinstance(r, dict)
             and parola in norm(r.get("descrizione", "")) and vicino(r.get("quantita"), q) and vicino(r.get("prezzo_unitario"), p))
righe_ok = len(righe) == 5 and giuste == 5
punti += righe_ok
dettagli.append(f"5 righe in ordine con quantità e prezzi giusti: {righe_ok} ({giuste} giuste su {len(righe)})")

dich = vicino(dati.get("totale_dichiarato"), DICHIARATO)
punti += dich
dettagli.append(f"totale_dichiarato 440.60: {dich} ({dati.get('totale_dichiarato')!r})")

calc = vicino(dati.get("totale_calcolato"), CALCOLATO)
punti += calc
dettagli.append(f"totale_calcolato 439.60: {calc} ({dati.get('totale_calcolato')!r})")

corretto = dati.get("totale_corretto") is False
punti += corretto
dettagli.append(f"totale_corretto false: {corretto} ({dati.get('totale_corretto')!r})")

esito(punti == 6, punti, 6, dettagli, ex)
