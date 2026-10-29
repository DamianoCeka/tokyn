# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import json, subprocess
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
fattura = open("fattura.txt", encoding="utf-8").read()
risposta = chiedi("Estrai i dati da questa fattura. Rispondi solo con JSON {\"fornitore\": testo, \"data\": \"AAAA-MM-GG\", "
                  "\"righe\": [{\"descrizione\": testo, \"quantita\": numero, \"prezzo_unitario\": numero}], "
                  "\"totale_dichiarato\": numero}. Gli importi come numeri in euro.\n\n" + fattura)
d = json.loads(risposta[risposta.index("{"):risposta.rindex("}") + 1])
calcolato = round(sum(float(r["quantita"]) * float(r["prezzo_unitario"]) for r in d["righe"]), 2)
d["totale_calcolato"] = calcolato
d["totale_corretto"] = abs(calcolato - float(d["totale_dichiarato"])) < 0.005
json.dump(d, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
