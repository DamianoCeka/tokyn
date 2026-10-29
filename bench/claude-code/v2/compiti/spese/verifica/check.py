"""Controllo di `spese`: 8 movimenti nascosti di esercenti inconfondibili (2 spesa alimentare, 2 trasporti, 2 casa,
1 svago, 1 altro), tutti uscite; la somma dei due trasporti fatta con i float dà -51.800000000000004.

Passa se risultato.json ha i movimenti nell'ordine del file con data e descrizione come nel file e l'importo numerico
giusto (col segno); le categorie sono tutte tra le cinque ammesse e almeno 7 su 8 sono giuste; e i totali sono numeri
arrotondati al centesimo, uguali alla somma degli importi del file per le categorie che il programma ha assegnato (una
categoria senza movimenti può mancare o valere 0). Con le categorie giuste i totali sono: spesa alimentare -85.50,
trasporti -51.80, casa -728.45, svago -19.00, altro -12.80.
"""

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm

QUI = Path(__file__).resolve().parent
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
ATTESE = ["spesa alimentare", "trasporti", "casa", "svago", "spesa alimentare", "trasporti", "casa", "altro"]
righe = (QUI / "nascosti" / "movimenti.csv").read_text(encoding="utf-8").splitlines()[1:]
FILE = [(d, t, Decimal(i.replace(",", "."))) for d, t, i in (r.split(";") for r in righe if r.strip())]

ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
if not isinstance(dati, dict) or not isinstance(dati.get("movimenti"), list):
    esito(False, 0, 3, ["risultato.json mancante o senza la lista movimenti"], ex)
movimenti = dati["movimenti"]
dettagli = []
punti = 0


def importo(valore):
    """Un importo scritto come numero JSON (non come testo), o None."""
    return Decimal(str(valore)) if isinstance(valore, (int, float)) and not isinstance(valore, bool) else None


ordine = len(movimenti) == 8 and all(
    isinstance(m, dict) and str(m.get("data", "")).strip() == d and norm(m.get("descrizione", "")) == norm(t)
    and importo(m.get("importo")) is not None and abs(importo(m["importo"]) - i) < Decimal("0.005")
    for m, (d, t, i) in zip(movimenti, FILE))
punti += ordine
dettagli.append(f"8 movimenti nell'ordine del file con data, descrizione e importo giusti: {ordine}")

assegnate = [norm(m.get("categoria", "")) if isinstance(m, dict) else "" for m in movimenti][:8]
giuste = sum(c == a for c, a in zip(assegnate, ATTESE))
cat_ok = len(assegnate) == 8 and all(c in CATEGORIE for c in assegnate) and giuste >= 7
punti += cat_ok
dettagli.append(f"categorie ammesse e giuste: {cat_ok} ({giuste} su 8: {assegnate})")

totali = dati.get("totali")
totali = {norm(k): v for k, v in totali.items()} if isinstance(totali, dict) else {}
tot_ok = bool(totali)
for cat in CATEGORIE:
    somma = sum((i for c, (_, _, i) in zip(assegnate, FILE) if c == cat), Decimal(0))
    valore = totali.get(cat)
    if somma == 0 and valore is None:
        continue
    n = importo(valore)
    giusto = n is not None and abs(n - somma) < Decimal("0.005") and round(valore, 2) == valore
    tot_ok = tot_ok and giusto
    if not giusto:
        dettagli.append(f"totale {cat}: atteso {somma} dalle categorie assegnate, scritto {valore!r}")
punti += tot_ok
attesi = {c: sum((i for a, (_, _, i) in zip(ATTESE, FILE) if a == c), Decimal(0)) for c in CATEGORIE}
come_attesi = all(importo(totali.get(c)) is not None and abs(importo(totali[c]) - s) < Decimal("0.005")
                  for c, s in attesi.items())
dettagli.append(f"totali arrotondati al centesimo e coerenti con le categorie assegnate: {tot_ok} "
                f"(uguali ai totali attesi: {come_attesi}; {dati.get('totali')})")

esito(punti == 3, punti, 3, dettagli, ex)
