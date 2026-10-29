# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import json, subprocess
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
righe = [r for r in open("recensioni.txt", encoding="utf-8").read().splitlines() if r.strip()]
out = []
for r in righe:
    risposta = chiedi("Classifica la recensione. Rispondi solo con JSON {\"sentimento\": \"positivo|negativo|neutro\", "
                      "\"voto\": intero da 1 a 5}.\nRecensione: " + r)
    d = json.loads(risposta[risposta.index("{"):risposta.rindex("}") + 1])
    out.append({"testo": r, "sentimento": d["sentimento"], "voto": int(d["voto"])})
json.dump({"recensioni": out, "media": sum(x["voto"] for x in out) / len(out)}, open("risultato.json", "w"), ensure_ascii=False)
