# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import csv, json, subprocess
from decimal import Decimal
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
clienti = {r["id"]: r for r in csv.DictReader(open("clienti.csv", encoding="utf-8", newline=""))}
paesi, spesa = {}, {}
for o in csv.DictReader(open("ordini.csv", encoding="utf-8", newline="")):
    c = clienti[o["cliente_id"]]
    paesi[c["paese"]] = paesi.get(c["paese"], Decimal(0)) + Decimal(o["importo"])
    spesa[c["nome"]] = spesa.get(c["nome"], Decimal(0)) + Decimal(o["importo"])
fatturato = {p: float(v) for p, v in sorted(paesi.items(), key=lambda x: -x[1])}
migliori = sorted(spesa, key=spesa.get, reverse=True)[:3]
riassunto = chiedi("Scrivi in italiano un breve paragrafo (al massimo 5 frasi) per la direzione sulle vendite del "
                   "trimestre. Di' qual è il paese con il fatturato più alto e commenta i numeri. Rispondi solo con il "
                   "paragrafo.\nFatturato per paese (euro): " + json.dumps(fatturato, ensure_ascii=False)
                   + "\nMigliori clienti: " + ", ".join(f"{n} ({spesa[n]} euro)" for n in migliori))
json.dump({"fatturato_per_paese": fatturato, "migliori_clienti": migliori, "riassunto": riassunto},
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
