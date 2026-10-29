"""Controllo di `documenti`: 4 documenti nascosti in docs/ e 4 domande, ognuna con la risposta (un dato preciso) in un
solo file.

Passa se risultato.json è una lista di 4 oggetti {domanda, risposta, fonte} nell'ordine di domande.txt e per ogni
domanda la risposta contiene il dato giusto (0,42 euro al km; 90 giorni; 2 giorni; le 11) e la fonte è esattamente il
nome del file giusto, senza cartella (maiuscole e spazi ai lati ignorati).
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm

QUI = Path(__file__).resolve().parent
ATTESE = [(r"0[,.]42|\b42 centesimi", "trasferte.txt"),
          (r"\b90\b|novanta", "sicurezza_it.txt"),
          (r"\b2\b|\bdue\b", "smart_working.txt"),
          (r"\b11\b|undici", "magazzino.txt")]
domande = [d for d in (QUI / "nascosti" / "domande.txt").read_text(encoding="utf-8").splitlines() if d.strip()]

ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
if not isinstance(dati, list):
    esito(False, 0, 5, ["risultato.json mancante o non è una lista"], ex)
dettagli = []
punti = 0

ordine = (len(dati) == 4 and all(isinstance(r, dict) and isinstance(r.get("risposta"), str)
                                 and isinstance(r.get("fonte"), str) and norm(r.get("domanda", ""))[:25] == norm(d)[:25]
                                 for r, d in zip(dati, domande)))
punti += ordine
dettagli.append(f"4 oggetti {{domanda, risposta, fonte}} nell'ordine di domande.txt: {ordine}")

for i, (r, (dato, fonte)) in enumerate(zip(dati, ATTESE), 1):
    if not isinstance(r, dict):
        dettagli.append(f"domanda {i}: elemento non valido ({r})")
        continue
    risposta_ok = bool(re.search(dato, norm(r.get("risposta", ""))))
    fonte_ok = isinstance(r.get("fonte"), str) and r["fonte"].strip().lower() == fonte
    punti += risposta_ok and fonte_ok
    dettagli.append(f"domanda {i}: risposta giusta {risposta_ok}, fonte {fonte} {fonte_ok} "
                    f"({r.get('risposta')!r}, {r.get('fonte')!r})")

esito(punti == 5, punti, 5, dettagli, ex)
