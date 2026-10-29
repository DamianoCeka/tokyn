"""Controllo di `articolo`: un articolo nascosto di circa 700 parole sul nuovo stabilimento Valtek a Montebrenna.

I fatti principali sono quattro: investimento di 48 milioni, 320 posti di lavoro, produzione da settembre 2027, pompe
di calore. Le persone e le organizzazioni citate sono sei: Elena Marchesini, Laura Benedetti, Paolo Ricci, Valtek
Impianti, Comune di Montebrenna, Istituto Tecnico Volta.

Passa se risultato.json ha un titolo (stringa non vuota che parla dello stabilimento), esattamente 5 punti (stringhe
non vuote) che insieme riportano almeno 3 dei 4 fatti principali, e in `citati` (lista di stringhe) almeno 5 delle 6
persone e organizzazioni.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm

QUI = Path(__file__).resolve().parent
FATTI = {
    "investimento di 48 milioni": r"\b48 ?(milion|mln|mil\b|m\b)|48\.000\.000",
    "320 posti di lavoro": r"\b320\b",
    "produzione dal 2027": r"\b2027\b",
    "pompe di calore": r"\bpomp[ae] di calore",
}
CITATI = {
    "Elena Marchesini": r"marchesini",
    "Laura Benedetti": r"benedetti",
    "Paolo Ricci": r"\bricci\b",
    "Valtek Impianti": r"valtek",
    "Comune di Montebrenna": r"montebrenna",
    "Istituto Tecnico Volta": r"\bvolta\b",
}
TEMA = r"valtek|montebrenna|pomp[ae] di calore|stabiliment|fabbrica|posti di lavoro|assunzion|investiment|\b320\b|\b48\b"

ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
dettagli = []
if not isinstance(dati, dict):
    esito(False, 0, 4, ["risultato.json mancante o non è un oggetto JSON"], ex)
punti = 0

titolo = dati.get("titolo")
titolo_ok = isinstance(titolo, str) and 0 < len(titolo.strip()) <= 200 and re.search(TEMA, norm(titolo)) is not None
punti += titolo_ok
dettagli.append(f"titolo sullo stabilimento: {titolo_ok} ({titolo!r})")

lista = dati.get("punti")
cinque = isinstance(lista, list) and len(lista) == 5 and all(isinstance(p, str) and p.strip() for p in lista)
testo = norm(" ".join(p for p in lista if isinstance(p, str))) if isinstance(lista, list) else ""
punti += cinque
dettagli.append(f"esattamente 5 punti (stringhe non vuote): {cinque} "
                f"({len(lista) if isinstance(lista, list) else 'nessuna lista'})")
coperti = [f for f, regola in FATTI.items() if re.search(regola, testo)]
fatti_ok = cinque and len(coperti) >= 3
punti += fatti_ok
dettagli.append(f"i 5 punti riportano almeno 3 fatti principali su 4: {fatti_ok} ({coperti})")

citati = dati.get("citati")
nomi = [norm(c) for c in citati if isinstance(c, str)] if isinstance(citati, list) else []
stringhe = isinstance(citati, list) and len(nomi) == len(citati)
trovati = [c for c, regola in CITATI.items() if any(re.search(regola, n) for n in nomi)]
citati_ok = stringhe and len(trovati) >= 5
punti += citati_ok
dettagli.append(f"citati (lista di stringhe) con almeno 5 su 6: {citati_ok} ({len(trovati)} trovati: {trovati})")

esito(punti == 4, punti, 4, dettagli, ex)
