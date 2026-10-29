# Programma finto con un errore plausibile (somme coi float senza arrotondare): il controllo deve bocciarlo.
import csv, json
clienti = {r["id"]: r for r in csv.DictReader(open("clienti.csv", encoding="utf-8", newline=""))}
paesi, spesa = {}, {}
for o in csv.DictReader(open("ordini.csv", encoding="utf-8", newline="")):
    c = clienti[o["cliente_id"]]
    paesi[c["paese"]] = paesi.get(c["paese"], 0.0) + float(o["importo"])
    spesa[c["nome"]] = spesa.get(c["nome"], 0.0) + float(o["importo"])
primo = max(paesi, key=paesi.get)
json.dump({"fatturato_per_paese": paesi,
           "migliori_clienti": sorted(spesa, key=spesa.get, reverse=True)[:3],
           "riassunto": f"Nel trimestre il paese con il fatturato più alto è {primo}, con {paesi[primo]:.2f} euro."},
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
