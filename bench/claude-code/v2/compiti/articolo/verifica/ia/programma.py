# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import json, subprocess
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
articolo = open("articolo.txt", encoding="utf-8").read()
risposta = chiedi("Leggi l'articolo e prepara una scheda. Rispondi solo con JSON {\"titolo\": stringa breve, "
                  "\"punti\": lista di esattamente 5 frasi con i punti chiave, \"citati\": lista dei nomi delle persone "
                  "e delle organizzazioni citate, ognuno una volta}.\n\nArticolo:\n" + articolo)
d = json.loads(risposta[risposta.index("{"):risposta.rindex("}") + 1])
json.dump({"titolo": d["titolo"], "punti": d["punti"], "citati": d["citati"]},
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
