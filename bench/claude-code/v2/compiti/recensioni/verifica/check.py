"""Controllo di `recensioni`: 6 recensioni nascoste dal sentimento chiaro (2 positive, 2 negative, 2 neutre).

Passa se risultato.json ha le 6 recensioni nell'ordine del file, almeno 5 sentimenti giusti, voti interi da 1 a 5
coerenti (positive almeno 4, negative al massimo 2) e la media giusta dei voti scritti.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm, numero

QUI = Path(__file__).resolve().parent
ATTESI = ["positivo", "negativo", "neutro", "positivo", "negativo", "neutro"]
righe = (QUI / "nascosti" / "recensioni.txt").read_text(encoding="utf-8").splitlines()

ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
dettagli = []
if not isinstance(dati, dict) or not isinstance(dati.get("recensioni"), list):
    esito(False, 0, 4, ["risultato.json mancante o senza la lista recensioni"], ex)
lista = dati["recensioni"]
punti = 0

ordine = len(lista) == 6 and all(isinstance(r, dict) and norm(r.get("testo", ""))[:25] == norm(t)[:25]
                                 for r, t in zip(lista, righe))
punti += ordine
dettagli.append(f"6 recensioni nell'ordine del file: {ordine}")

giusti = sum(1 for r, a in zip(lista, ATTESI) if isinstance(r, dict) and norm(r.get("sentimento", "")).startswith(a[:5]))
punti += giusti >= 5
dettagli.append(f"sentimenti giusti: {giusti} su 6")

voti = [numero(r.get("voto")) if isinstance(r, dict) else None for r in lista]
validi = all(v is not None and v == int(v) and 1 <= v <= 5 for v in voti) and len(voti) == 6
coerenti = validi and all((a != "positivo" or v >= 4) and (a != "negativo" or v <= 2) for v, a in zip(voti, ATTESI))
punti += coerenti
dettagli.append(f"voti interi da 1 a 5 e coerenti col sentimento: {coerenti} ({voti})")

media = numero(dati.get("media"))
media_ok = validi and media is not None and abs(media - sum(voti) / 6) < 0.01
punti += media_ok
dettagli.append(f"media giusta dei voti: {media_ok} ({media})")

esito(punti == 4, punti, 4, dettagli, ex)
