# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import json, subprocess
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
REGOLE = ("Sei il moderatore di un forum di giardinaggio. Regole: \"rifiuta\" se il commento è spam, contiene insulti "
          "o contiene dati personali (numeri di telefono, indirizzi, email); \"rivedi\" se il contenuto è utile ma il "
          "tono è aggressivo; \"pubblica\" in tutti gli altri casi. Rispondi solo con JSON {\"decisione\": "
          "\"pubblica|rivedi|rifiuta\", \"motivo\": una frase, \"riscrittura\": solo se rivedi, una versione educata "
          "del commento che ne mantenga il contenuto, altrimenti null}.\nCommento: ")
out = []
for c in json.load(open("commenti.json", encoding="utf-8")):
    risposta = chiedi(REGOLE + c["testo"])
    d = json.loads(risposta[risposta.index("{"):risposta.rindex("}") + 1])
    r = {"id": c["id"], "decisione": d["decisione"], "motivo": d["motivo"]}
    if d["decisione"] == "rivedi":
        r["riscrittura"] = d.get("riscrittura")
    out.append(r)
json.dump(out, open("risultato.json", "w"), ensure_ascii=False, indent=2)
