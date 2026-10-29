# Programma finto con un errore plausibile (risponde a ogni messaggio da solo, senza ricordare la conversazione): il
# controllo deve bocciarlo.
import re, sys
testo = open("faq.txt", encoding="utf-8").read()
faq = re.findall(r"D: (.*)\nR: (.*)", testo)
parole = lambda s: set(re.findall(r"\w{4,}", s.lower()))
for riga in sys.stdin:
    riga = riga.strip()
    if riga.lower() == "esci":
        break
    m = re.search(r"mi chiamo (\w+)", riga, re.IGNORECASE)
    if "come mi chiamo" in riga.lower():
        print("Mi dispiace, non conosco il tuo nome.")
    elif m:
        print(f"Ciao {m.group(1)}, come posso aiutarti?")
    else:
        d, r = max(faq, key=lambda qa: len(parole(riga) & parole(qa[0] + " " + qa[1])))
        print(r)
