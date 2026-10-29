# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import csv, json
from decimal import Decimal
clienti = {r["id"]: r for r in csv.DictReader(open("clienti.csv", encoding="utf-8", newline=""))}
paesi, spesa = {}, {}
for o in csv.DictReader(open("ordini.csv", encoding="utf-8", newline="")):
    c = clienti[o["cliente_id"]]
    paesi[c["paese"]] = paesi.get(c["paese"], Decimal(0)) + Decimal(o["importo"])
    spesa[c["nome"]] = spesa.get(c["nome"], Decimal(0)) + Decimal(o["importo"])
primo = max(paesi, key=paesi.get)
json.dump({"fatturato_per_paese": {p: float(v) for p, v in paesi.items()},
           "migliori_clienti": sorted(spesa, key=spesa.get, reverse=True)[:3],
           "riassunto": f"Nel trimestre il paese con il fatturato più alto è {primo}, con {paesi[primo]} euro."},
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
