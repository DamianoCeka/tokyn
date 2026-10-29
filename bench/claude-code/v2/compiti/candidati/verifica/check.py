"""Controllo di `candidati`: annuncio nascosto per un impiegato contabile e 4 curriculum: ferrari_giulia.txt ha tutti i
requisiti, gallo_andrea.txt è un cuoco senza nessun requisito, colombo_luca.txt e ricci_paolo.txt ne hanno solo una
parte (il loro ordine reciproco non conta).

Passa se risultato.json ha in "candidati" i 4 curriculum, ognuno una volta, con file (nome senza cartella), punteggio
intero da 1 a 10 e motivazione non vuota; la lista è in ordine di punteggio decrescente; "migliore" è
ferrari_giulia.txt, con un punteggio più alto di tutti gli altri; e gallo_andrea.txt ha un punteggio più basso di tutti
gli altri. Maiuscole e spazi ai lati del nome del file sono ignorati.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito

QUI = Path(__file__).resolve().parent
MIGLIORE, PEGGIORE = "ferrari_giulia.txt", "gallo_andrea.txt"
FILE = sorted(f.name for f in (QUI / "nascosti" / "cv").glob("*.txt"))

ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
if not isinstance(dati, dict) or not isinstance(dati.get("candidati"), list):
    esito(False, 0, 4, ["risultato.json mancante o senza la lista candidati"], ex)
lista = dati["candidati"]
dettagli = []
punti = 0


def nome(valore):
    return valore.strip().lower() if isinstance(valore, str) else ""


def punteggio(c):
    v = c.get("punteggio") if isinstance(c, dict) else None
    ok = isinstance(v, (int, float)) and not isinstance(v, bool) and v == int(v) and 1 <= v <= 10
    return int(v) if ok else None


nomi = [nome(c.get("file")) if isinstance(c, dict) else "" for c in lista]
voti = [punteggio(c) for c in lista]
completi = (sorted(nomi) == FILE and all(v is not None for v in voti)
            and all(isinstance(c.get("motivazione"), str) and c["motivazione"].strip() for c in lista))
punti += completi
dettagli.append(f"4 curriculum una volta ciascuno con punteggio intero da 1 a 10 e motivazione: {completi} "
                f"({list(zip(nomi, [c.get('punteggio') if isinstance(c, dict) else None for c in lista]))})")

ordinati = completi and all(a >= b for a, b in zip(voti, voti[1:]))
punti += ordinati
dettagli.append(f"in ordine di punteggio decrescente: {ordinati} ({voti})")

per_file = dict(zip(nomi, voti)) if completi else {}
altri = [v for n, v in per_file.items() if n != MIGLIORE]
migliore = (completi and nome(dati.get("migliore")) == MIGLIORE and all(per_file[MIGLIORE] > v for v in altri))
punti += migliore
dettagli.append(f"migliore {MIGLIORE} col punteggio più alto: {migliore} ({dati.get('migliore')!r})")

altri = [v for n, v in per_file.items() if n != PEGGIORE]
peggiore = completi and all(per_file[PEGGIORE] < v for v in altri)
punti += peggiore
dettagli.append(f"{PEGGIORE} col punteggio più basso: {peggiore}")

esito(punti == 4, punti, 4, dettagli, ex)
