"""Controllo di `log`: un log nascosto di 240 righe (17 marzo 2026), generato da genera.py.

Valori attesi, ricalcolati qui dal log: richieste in 20 ore (nessuna dalle 02 alle 05, picco di 26 alle 15); errori
{"401": 4, "403": 3, "404": 19, "408": 1, "500": 3} (il 408 è una riga senza richiesta, "-"); ip_top 198.51.100.42
(34), 203.0.113.88 (27), 192.0.2.15 (21), senza pareggi (il quarto ne ha 16). Il log contiene anche un IP IPv6.

Passa se risultato.json ha richieste_per_ora uguale a quella attesa (chiavi "HH", nessuna ora in più o in meno), errori
uguale a quello atteso (nessun codice in più o in meno), ip_top uguale ai 3 IP attesi nell'ordine giusto e un commento
(stringa di almeno 30 caratteri e al massimo 4 frasi).
"""

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from comune import esegui, esito, numero

QUI = Path(__file__).resolve().parent
RIGA = re.compile(r'^(\S+) \S+ \S+ \[[^:]+:(\d\d):\d\d:\d\d [^\]]+\] "[^"]*" (\d{3}) \S+$')
ore, errori, ip = Counter(), Counter(), Counter()
for r in (QUI / "nascosti" / "access.log").read_text(encoding="utf-8").splitlines():
    m = RIGA.match(r)
    assert m, f"riga non riconosciuta nel log nascosto: {r}"
    ore[m[2]] += 1
    ip[m[1]] += 1
    if int(m[3]) >= 400:
        errori[m[3]] += 1
classifica = ip.most_common(4)
assert classifica[2][1] > classifica[3][1], "pareggio al terzo posto nel log nascosto"
IP_TOP = [a for a, _ in classifica[:3]]


def uguale(dato, atteso):
    """Stesso dizionario: stesse chiavi (come stringhe) e stessi conteggi (4 e 4.0 vanno bene)."""
    return (isinstance(dato, dict) and set(map(str, dato)) == set(atteso)
            and all(numero(v) == atteso[str(k)] for k, v in dato.items()))


ex = esegui(sys.argv[1], QUI / "nascosti")
dati = ex.json("risultato.json")
dettagli = []
if not isinstance(dati, dict):
    esito(False, 0, 4, ["risultato.json mancante o non è un oggetto JSON"], ex)
punti = 0

ore_ok = uguale(dati.get("richieste_per_ora"), ore)
punti += ore_ok
dettagli.append(f"richieste_per_ora giuste: {ore_ok} (attese {dict(sorted(ore.items()))}, "
                f"scritte {dati.get('richieste_per_ora')})")

err_ok = uguale(dati.get("errori"), errori)
punti += err_ok
dettagli.append(f"errori giusti: {err_ok} (attesi {dict(sorted(errori.items()))}, scritti {dati.get('errori')})")

top = dati.get("ip_top")
top_ok = isinstance(top, list) and [str(a).strip() for a in top] == IP_TOP
punti += top_ok
dettagli.append(f"ip_top giusti e in ordine: {top_ok} (attesi {IP_TOP}, scritti {top})")

commento = dati.get("commento")
frasi = len(re.findall(r"[.!?]+(?=\s|$)", commento.strip())) if isinstance(commento, str) else 0
commento_ok = isinstance(commento, str) and len(commento.strip()) >= 30 and frasi <= 4
punti += commento_ok
dettagli.append(f"commento presente (almeno 30 caratteri, al massimo 4 frasi): {commento_ok} ({str(commento)[:200]!r})")

esito(punti == 4, punti, 4, dettagli, ex)
