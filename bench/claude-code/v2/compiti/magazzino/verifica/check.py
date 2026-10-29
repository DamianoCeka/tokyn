"""Controllo di `magazzino`: inventario nascosto di 6 articoli di ferramenta e 4 domande.

Risposte giuste (calcolate con codice): 37 martelli; valore totale 2623,30 €; sotto scorta il nastro isolante (8 su 40)
e il silicone (6 su 20); da ordinare 46 pezzi (32 + 14).

Passa se risultato.json è una lista di 4 elementi con le domande nell'ordine del file e se ogni risposta contiene il
numero esatto (scritto in qualsiasi formato: 2623.3, 2623,30, 2.623,30, 2,623.30, 2 623,30) o, per la terza domanda,
nomina i due articoli sotto scorta e nessuno degli altri quattro come sotto scorta: un altro articolo può comparire solo
in una frase che dice che è sopra la scorta (per esempio "trapano e guanti sono sopra la scorta minima").
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm

QUI = Path(__file__).resolve().parent
domande = [d for d in (QUI / "nascosti" / "domande.txt").read_text(encoding="utf-8").splitlines() if d.strip()]
SOTTO = ["nastro", "silicone"]
ALTRI = ["trapano", "martell", "guanti", "livella"]


def interpreta(tok):
    """I valori che un numero scritto può voler dire (1.234 può essere 1234 o 1,234)."""
    t = re.sub(r"[\s\xa0\u202f']", "", tok).strip(".,")
    if not re.fullmatch(r"\d[\d.,]*", t):
        return set()
    if "." in t and "," in t:
        dec = "." if t.rfind(".") > t.rfind(",") else ","
        mil = "," if dec == "." else "."
        intera, _, frazione = t.rpartition(dec)
        if re.fullmatch(r"\d{1,3}(\%s\d{3})*" % mil, intera) and frazione.isdigit():
            return {float(intera.replace(mil, "") + "." + frazione)}
        return set()
    valori = set()
    for sep in ".,":
        if sep in t:
            if re.fullmatch(r"\d{1,3}(\%s\d{3})+" % sep, t):
                valori.add(float(t.replace(sep, "")))
            if t.count(sep) == 1:
                valori.add(float(t.replace(sep, ".")))
            return valori
    return {float(t)}


def numeri(testo):
    valori = set()
    for tok in re.findall(r"\d[\d.,'\xa0\u202f ]*\d|\d", str(testo)):
        # il gruppo intero ("2 623,30") e i pezzi separati da spazi, virgola + spazio o punto + spazio ("8, 6")
        for parte in [tok, *re.split(r"[.,]?[\s\xa0\u202f]+", tok)]:
            valori |= interpreta(parte)
    return valori


def contiene(testo, atteso):
    return any(abs(v - atteso) < 0.005 for v in numeri(testo))


ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
dettagli = []
if not isinstance(dati, list):
    esito(False, 0, 5, ["risultato.json mancante o non è una lista"], ex)
punti = 0

ordine = len(dati) == 4 and all(isinstance(r, dict) and norm(r.get("domanda", ""))[:25] == norm(d)[:25]
                                for r, d in zip(dati, domande))
punti += ordine
dettagli.append(f"4 elementi con le domande nell'ordine del file: {ordine}")

risposte = [str(r.get("risposta", "")) if isinstance(r, dict) else "" for r in dati] + [""] * 4

ok1 = contiene(risposte[0], 37)
punti += ok1
dettagli.append(f"martelli 37: {ok1} ({risposte[0][:150]!r})")

ok2 = contiene(risposte[1], 2623.30)
punti += ok2
dettagli.append(f"valore totale 2623,30: {ok2} ({risposte[1][:150]!r})")

r3 = norm(risposte[2])
nominati = [p for p in SOTTO if p in r3]
# un altro articolo nominato va bene solo in una frase che dice che è sopra la scorta
SOPRA = r"sopra|oltre|superior|non (e|sono) sotto|in regola|\bsufficient|\badeguat"
intrusi = [p for p in ALTRI if any(p in f and not re.search(SOPRA, f) for f in re.split(r"[.;!?\n]|\bmentre\b|\binvece\b", r3))]
ok3 = len(nominati) == 2 and not intrusi
punti += ok3
dettagli.append(f"sotto scorta nastro e silicone, nessun altro: {ok3} (nominati {nominati}, di troppo {intrusi})")

ok4 = contiene(risposte[3], 46)
punti += ok4
dettagli.append(f"pezzi da ordinare 46: {ok4} ({risposte[3][:150]!r})")

esito(punti == 5, punti, 5, dettagli, ex)
