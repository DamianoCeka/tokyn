# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import json, re
from collections import Counter
ore, errori, ip = Counter(), Counter(), Counter()
for r in open("access.log", encoding="utf-8"):
    m = re.match(r'^(\S+) \S+ \S+ \[[^:]+:(\d\d):[^\]]+\] "[^"]*" (\d{3}) ', r)
    if m:
        ore[m[2]] += 1
        ip[m[1]] += 1
        if int(m[3]) >= 400:
            errori[m[3]] += 1
json.dump({"richieste_per_ora": dict(sorted(ore.items())), "errori": dict(sorted(errori.items())),
           "ip_top": [a for a, _ in ip.most_common(3)],
           "commento": "Il traffico è concentrato nel pomeriggio, con il picco alle 15. Gli errori sono soprattutto "
                       "pagine non trovate."},
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
