# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import json, subprocess
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
verbale = open("verbale.txt", encoding="utf-8").read()
risposta = chiedi("Dalla trascrizione di questa riunione ricava le decisioni prese e le azioni da fare. Rispondi solo "
                  "con JSON {\"decisioni\": [frasi brevi], \"azioni\": [{\"cosa\": ..., \"chi\": nome, \"entro\": "
                  "\"AAAA-MM-GG\"}]}.\n\nTrascrizione:\n" + verbale)
d = json.loads(risposta[risposta.index("{"):risposta.rindex("}") + 1])
json.dump({"decisioni": d["decisioni"], "azioni": d["azioni"]}, open("risultato.json", "w"), ensure_ascii=False, indent=2)
