# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import json, subprocess
from decimal import Decimal
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
CATEGORIE = ["spesa alimentare", "trasporti", "casa", "svago", "altro"]
righe = [r.split(";") for r in open("movimenti.csv", encoding="utf-8").read().splitlines()[1:] if r.strip()]
elenco = "\n".join(f"{n}. {descr}" for n, (_, descr, _) in enumerate(righe, 1))
risposta = chiedi("Assegna a ogni movimento bancario una categoria tra: " + ", ".join(CATEGORIE) + ". Rispondi solo con "
                  "una lista JSON di stringhe, una categoria per movimento, nello stesso ordine.\n\n" + elenco)
categorie = json.loads(risposta[risposta.index("["):risposta.rindex("]") + 1])
movimenti, totali = [], {}
for (data, descr, importo), cat in zip(righe, categorie):
    importo = Decimal(importo.replace(",", "."))
    movimenti.append({"data": data, "descrizione": descr, "importo": float(importo), "categoria": cat})
    totali[cat] = totali.get(cat, Decimal(0)) + importo
json.dump({"movimenti": movimenti, "totali": {c: float(v) for c, v in totali.items()}}, open("risultato.json", "w"),
          ensure_ascii=False, indent=2)
