# Programma finto con un errore plausibile (prende l'ora con split(":"), che sbaglia sulle righe con un IP IPv6):
# il controllo deve bocciarlo.
import json
from collections import Counter
ore, errori, ip = Counter(), Counter(), Counter()
for r in open("access.log", encoding="utf-8"):
    campi = r.split()
    ore[r.split(":")[1]] += 1
    ip[campi[0]] += 1
    if int(campi[-2]) >= 400:
        errori[campi[-2]] += 1
json.dump({"richieste_per_ora": dict(ore), "errori": dict(errori), "ip_top": [a for a, _ in ip.most_common(3)],
           "commento": "Il traffico è concentrato nel pomeriggio, con il picco alle 15. Gli errori sono soprattutto "
                       "pagine non trovate."},
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
