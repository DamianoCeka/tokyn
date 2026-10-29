# Programma finto con un errore plausibile (somma i float senza arrotondare: trasporti -51.800000000000004): il
# controllo deve bocciarlo.
import json
righe = open("movimenti.csv", encoding="utf-8").read().splitlines()[1:]
categorie = ["spesa alimentare", "trasporti", "casa", "svago", "spesa alimentare", "trasporti", "casa", "altro"]
movimenti, totali = [], {}
for riga, cat in zip(righe, categorie):
    data, descrizione, importo = riga.split(";")
    importo = float(importo.replace(",", "."))
    movimenti.append({"data": data, "descrizione": descrizione, "importo": importo, "categoria": cat})
    totali[cat] = totali.get(cat, 0) + importo
json.dump({"movimenti": movimenti, "totali": totali}, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
