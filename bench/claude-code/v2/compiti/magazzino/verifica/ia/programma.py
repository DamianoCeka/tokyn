# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
# I conti li fa Python; Claude legge i dati già calcolati e scrive la risposta.
import json, subprocess
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
inventario = json.load(open("inventario.json", encoding="utf-8"))
righe = []
for p in inventario:
    valore = round(p["quantita"] * p["prezzo_unitario"], 2)
    sotto = p["quantita"] < p["scorta_minima"]
    righe.append(f"- {p['codice']} {p['nome']}: quantità {p['quantita']}, prezzo unitario {p['prezzo_unitario']:.2f} €, "
                 f"scorta minima {p['scorta_minima']}, valore {valore:.2f} €, sotto scorta: {'sì' if sotto else 'no'}"
                 + (f", mancano {p['scorta_minima'] - p['quantita']} pezzi per arrivare alla scorta minima" if sotto else ""))
totale = round(sum(p["quantita"] * p["prezzo_unitario"] for p in inventario), 2)
fatti = "\n".join(righe) + f"\nValore totale del magazzino: {totale:.2f} €"
domande = [d for d in open("domande.txt", encoding="utf-8").read().splitlines() if d.strip()]
out = []
for d in domande:
    risposta = chiedi("Sei l'assistente del magazzino. Dati dell'inventario, con i conti già fatti:\n" + fatti +
                      "\n\nRispondi in italiano, in una frase breve, alla domanda qui sotto. Usa esattamente i numeri già "
                      "calcolati; se devi sommarne alcuni fallo con attenzione. Se la domanda chiede quali prodotti, "
                      "nomina solo quelli giusti.\nDomanda: " + d)
    out.append({"domanda": d, "risposta": risposta})
json.dump(out, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
