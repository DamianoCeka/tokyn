"""Controllo di `moderazione`: 6 commenti nascosti dalla decisione chiara (2 da pubblicare, 2 da rifiutare: uno spam e
uno con insulti e dati personali, 2 da rivedere: consigli utili scritti con tono aggressivo).

Passa se risultato.json è una lista di 6 oggetti nell'ordine del file, ognuno con l'id del commento (201 o "201") e un
motivo non vuoto; le decisioni sono tutte tra pubblica, rivedi e rifiuta (maiuscole e accenti ignorati) e almeno 5 su 6
sono giuste; ogni commento marcato "rivedi" ha una riscrittura non vuota; e ognuno dei due commenti da rivedere che il
programma ha marcato "rivedi" (almeno uno) ha una riscrittura senza le parole offensive dell'originale ("ridicolo",
"fesseria") che mantiene il contenuto (almeno 2 parole chiave del consiglio). Chiavi in più, come una riscrittura vuota
o null per gli altri commenti, sono ammesse.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, norm, numero

QUI = Path(__file__).resolve().parent
ATTESE = {201: "pubblica", 202: "rifiuta", 203: "rivedi", 204: "pubblica", 205: "rifiuta", 206: "rivedi"}
DECISIONI = {"pubblica", "rivedi", "rifiuta"}
RISCRITTURE = {  # id: (parole offensive da togliere, parole del contenuto di cui ne servono almeno 2)
    203: (["ridicol"], ["ortensi", "invern", "gemm", "autunn", "potat", "potan", "potar"]),
    206: (["fesseri"], ["grass", "succulent", "annaff", "irrig", "asciutt", "invern", "estat", "10", "dieci", "15",
                        "quindici"]),
}
commenti = json.loads((QUI / "nascosti" / "commenti.json").read_text(encoding="utf-8"))
ids = [c["id"] for c in commenti]

ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
if not isinstance(dati, list):
    esito(False, 0, 4, ["risultato.json mancante o non è una lista"], ex)
dettagli = []
punti = 0


def chiave(valore):
    """L'id come intero se è un numero intero (201, 201.0 o "201"), altrimenti il testo normalizzato."""
    n = numero(valore)
    if n is not None and n == n and abs(n) != float("inf") and n == int(n):
        return int(n)
    return norm(valore)


def testo(valore):
    return valore.strip() if isinstance(valore, str) else ""


def decisione(r):
    return norm(r.get("decisione", "")).strip(" .!") if isinstance(r, dict) else ""


ordine = (len(dati) == 6 and all(isinstance(r, dict) and chiave(r.get("id")) == i and testo(r.get("motivo"))
                                 for r, i in zip(dati, ids)))
punti += ordine
dettagli.append(f"6 commenti nell'ordine del file con id e motivo: {ordine} "
                f"({[r.get('id') if isinstance(r, dict) else r for r in dati]})")

per_id = {}
for r in dati:
    if isinstance(r, dict):
        per_id.setdefault(chiave(r.get("id")), r)
trovati = {i: per_id.get(i, {}) for i in ids}

decisioni = {i: decisione(r) for i, r in trovati.items()}
giuste = sum(decisioni[i] == a for i, a in ATTESE.items())
dec_ok = all(d in DECISIONI for d in decisioni.values()) and giuste >= 5
punti += dec_ok
dettagli.append(f"decisioni ammesse e giuste: {dec_ok} ({giuste} su 6: {list(decisioni.values())})")

da_rivedere = [r for r in dati if decisione(r) == "rivedi"]
presenti = bool(da_rivedere) and all(testo(r.get("riscrittura")) for r in da_rivedere)
punti += presenti
dettagli.append(f"riscrittura per ogni commento da rivedere: {presenti} ({len(da_rivedere)} da rivedere)")

controllate, buone = 0, 0
for i, (offese, contenuto) in RISCRITTURE.items():
    r = trovati[i]
    if decisioni[i] != "rivedi":
        dettagli.append(f"commento {i}: non marcato rivedi, riscrittura non controllata")
        continue
    controllate += 1
    nuova = norm(testo(r.get("riscrittura")))
    educata = bool(nuova) and not any(o in nuova for o in offese)
    fedele = sum(p in nuova for p in contenuto) >= 2
    buone += educata and fedele
    dettagli.append(f"commento {i}: riscrittura senza offese {educata}, con il contenuto {fedele} "
                    f"({r.get('riscrittura')!r})")
punti += controllate >= 1 and buone == controllate

esito(punti == 4, punti, 4, dettagli, ex)
