# Programma finto con un errore plausibile (per gli articoli sotto scorta somma le scorte minime, 40 + 20, invece dei
# pezzi che mancano): il controllo deve bocciarlo.
import json
domande = [d for d in open("domande.txt", encoding="utf-8").read().splitlines() if d.strip()]
risposte = [
    "Abbiamo 37 martelli da carpentiere.",
    "La merce in magazzino vale in tutto 2623.30 euro.",
    "Sono sotto la scorta minima il nastro isolante nero e il silicone sigillante trasparente.",
    "Dobbiamo ordinare 60 pezzi in totale.",
]
json.dump([{"domanda": d, "risposta": r} for d, r in zip(domande, risposte)],
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
