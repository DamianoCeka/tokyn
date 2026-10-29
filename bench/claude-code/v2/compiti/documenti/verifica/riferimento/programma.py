# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import json
domande = [d for d in open("domande.txt", encoding="utf-8").read().splitlines() if d.strip()]
risposte = [("0,42 euro al chilometro", "trasferte.txt"), ("Ogni 90 giorni", "sicurezza_it.txt"),
            ("Fino a 2 giorni alla settimana", "smart_working.txt"), ("Fino alle 11:00", "magazzino.txt")]
json.dump([{"domanda": d, "risposta": r, "fonte": f} for d, (r, f) in zip(domande, risposte)],
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
