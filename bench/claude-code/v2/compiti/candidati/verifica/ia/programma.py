# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import json, subprocess
from pathlib import Path
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
annuncio = open("annuncio.txt", encoding="utf-8").read()
out = []
for f in sorted(Path("cv").glob("*.txt")):
    risposta = chiedi("Valuta il curriculum rispetto all'annuncio di lavoro. Rispondi solo con JSON {\"punteggio\": "
                      "intero da 1 a 10, \"motivazione\": una frase}.\n\nANNUNCIO:\n" + annuncio + "\n\nCURRICULUM:\n"
                      + f.read_text(encoding="utf-8"))
    d = json.loads(risposta[risposta.index("{"):risposta.rindex("}") + 1])
    out.append({"file": f.name, "punteggio": int(d["punteggio"]), "motivazione": d["motivazione"]})
out.sort(key=lambda c: c["punteggio"], reverse=True)
json.dump({"candidati": out, "migliore": out[0]["file"]}, open("risultato.json", "w"), ensure_ascii=False, indent=2)
