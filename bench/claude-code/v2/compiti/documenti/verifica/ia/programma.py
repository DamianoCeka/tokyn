# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import json, subprocess
from pathlib import Path
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
documenti = "\n\n".join(f"=== FILE: {f.name}\n{f.read_text(encoding='utf-8')}" for f in sorted(Path("docs").glob("*.txt")))
domande = [d for d in open("domande.txt", encoding="utf-8").read().splitlines() if d.strip()]
out = []
for d in domande:
    risposta = chiedi("Rispondi alla domanda usando solo questi documenti. Rispondi solo con JSON {\"risposta\": "
                      "risposta breve, \"fonte\": nome del file da cui viene}.\n\n" + documenti + "\n\nDomanda: " + d)
    j = json.loads(risposta[risposta.index("{"):risposta.rindex("}") + 1])
    out.append({"domanda": d, "risposta": j["risposta"], "fonte": j["fonte"]})
json.dump(out, open("risultato.json", "w"), ensure_ascii=False, indent=2)
