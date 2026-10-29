# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
import csv, subprocess
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
with open("catalogo.csv", encoding="utf-8", newline="") as f:
    righe = list(csv.reader(f, delimiter=";"))
with open("catalogo_en.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(righe[0])
    for codice, nome, descrizione, prezzo in righe[1:]:
        inglese = chiedi("Traduci in inglese questa descrizione di un prodotto di un negozio online. Rispondi solo con "
                         "la traduzione, su una riga, senza virgolette.\nDescrizione: " + descrizione)
        w.writerow([codice, nome, inglese.splitlines()[0].strip().strip('"'), prezzo])
