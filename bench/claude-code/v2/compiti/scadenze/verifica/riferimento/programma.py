# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import csv, json, sys
from datetime import date
rif = date.fromisoformat(sys.argv[1])
out = []
for r in csv.DictReader(open("contratti.csv", encoding="utf-8", newline="")):
    giorni = (date.fromisoformat(r["scadenza"]) - rif).days
    if 0 <= giorni <= 30:
        out.append({"cliente": r["cliente"], "servizio": r["servizio"], "scadenza": r["scadenza"], "giorni_mancanti": giorni,
                    "oggetto": f"Il contratto {r['servizio']} scade il {r['scadenza']}",
                    "testo": f"Gentile {r['cliente']}, le ricordiamo che il contratto {r['servizio']} scade il {r['scadenza']}."})
out.sort(key=lambda c: c["scadenza"])
json.dump({"in_scadenza": out}, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
