# Programma finto che risponde senza IA (sceglie la FAQ con più parole in comune e ricorda il nome): il controllo deve
# promuoverlo.
import re, sys
testo = open("faq.txt", encoding="utf-8").read()
faq = re.findall(r"D: (.*)\nR: (.*)", testo)
parole = lambda s: set(re.findall(r"\w{4,}", s.lower()))
nome = None
print("Ciao! Sono l'assistente di Casa Nespolo. Scrivi esci per terminare.")
for riga in sys.stdin:
    riga = riga.strip()
    if riga.lower() == "esci":
        print("Arrivederci!")
        break
    m = re.search(r"mi chiamo (\w+)", riga, re.IGNORECASE)
    if "come mi chiamo" in riga.lower():
        print(f"Ti chiami {nome}." if nome else "Non me l'hai ancora detto.")
    elif m:
        nome = m.group(1)
        print(f"Ciao {nome}, come posso aiutarti?")
    else:
        d, r = max(faq, key=lambda qa: len(parole(riga) & parole(qa[0] + " " + qa[1])))
        print(r)
