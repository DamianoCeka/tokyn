# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import csv, json, subprocess, sys
from datetime import date
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
rif = date.fromisoformat(sys.argv[1])
scelti = []
for r in csv.DictReader(open("contratti.csv", encoding="utf-8", newline="")):
    giorni = (date.fromisoformat(r["scadenza"]) - rif).days
    if 0 <= giorni <= 30:
        scelti.append((r, giorni))
scelti.sort(key=lambda x: x[0]["scadenza"])
out = []
for r, giorni in scelti:
    risposta = chiedi("Scrivi in italiano una breve email di promemoria per un cliente il cui contratto sta per scadere. "
                      "Rivolgiti al cliente per nome e cita il servizio. Rispondi solo con JSON "
                      "{\"oggetto\": \"...\", \"testo\": \"...\"}.\n"
                      f"Cliente: {r['cliente']}\nServizio: {r['servizio']}\nScadenza: {r['scadenza']} "
                      f"(tra {giorni} giorni)")
    d = json.loads(risposta[risposta.index("{"):risposta.rindex("}") + 1])
    out.append({"cliente": r["cliente"], "servizio": r["servizio"], "scadenza": r["scadenza"], "giorni_mancanti": giorni,
                "oggetto": d["oggetto"], "testo": d["testo"]})
json.dump({"in_scadenza": out}, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
