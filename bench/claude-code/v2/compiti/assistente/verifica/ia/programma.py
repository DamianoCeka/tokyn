# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import subprocess, sys
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
faq = open("faq.txt", encoding="utf-8").read()
storia = []
for riga in sys.stdin:
    riga = riga.strip()
    if not riga:
        continue
    if riga.lower() == "esci":
        print("Arrivederci!")
        break
    storia.append("Cliente: " + riga)
    risposta = chiedi("Sei l'assistente clienti di un negozio online. Rispondi in italiano, in breve, usando solo queste "
                      "FAQ; se la risposta non c'è, dillo.\n\nFAQ:\n" + faq + "\n\nConversazione finora:\n"
                      + "\n".join(storia) + "\n\nScrivi solo la risposta dell'assistente all'ultimo messaggio del cliente.")
    storia.append("Assistente: " + risposta)
    print(risposta, flush=True)
