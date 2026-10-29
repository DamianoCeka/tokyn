# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import json, os, subprocess
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
out = []
for f in sorted(n for n in os.listdir("email") if n.endswith(".txt")):
    testo = open(os.path.join("email", f), encoding="utf-8").read()
    risposta = chiedi("Smista questa email arrivata a un negozio online. Rispondi solo con JSON {\"categoria\": "
                      "\"ordine|reclamo|informazioni|spam\", \"urgente\": true|false, \"riassunto\": una frase}.\n\n" + testo)
    d = json.loads(risposta[risposta.index("{"):risposta.rindex("}") + 1])
    out.append({"file": f, "categoria": d["categoria"], "urgente": bool(d["urgente"]), "riassunto": d["riassunto"]})
json.dump(out, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
