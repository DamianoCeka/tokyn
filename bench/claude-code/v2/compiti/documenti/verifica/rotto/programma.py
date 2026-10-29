# Programma finto con un errore plausibile (risposte giuste ma fonte con la cartella, docs/trasferte.txt invece di
# trasferte.txt): il controllo deve bocciarlo.
import json
domande = [d for d in open("domande.txt", encoding="utf-8").read().splitlines() if d.strip()]
risposte = [("0,42 euro al chilometro", "docs/trasferte.txt"), ("Ogni 90 giorni", "docs/sicurezza_it.txt"),
            ("Fino a 2 giorni alla settimana", "docs/smart_working.txt"), ("Fino alle 11:00", "docs/magazzino.txt")]
json.dump([{"domanda": d, "risposta": r, "fonte": f} for d, (r, f) in zip(domande, risposte)],
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
