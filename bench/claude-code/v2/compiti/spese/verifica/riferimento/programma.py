# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import json
righe = open("movimenti.csv", encoding="utf-8").read().splitlines()[1:]
categorie = ["spesa alimentare", "trasporti", "casa", "svago", "spesa alimentare", "trasporti", "casa", "altro"]
movimenti, totali = [], {}
for riga, cat in zip(righe, categorie):
    data, descrizione, importo = riga.split(";")
    importo = float(importo.replace(",", "."))
    movimenti.append({"data": data, "descrizione": descrizione, "importo": importo, "categoria": cat})
    totali[cat] = totali.get(cat, 0) + importo
totali = {c: round(v, 2) for c, v in totali.items()}
json.dump({"movimenti": movimenti, "totali": totali}, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
