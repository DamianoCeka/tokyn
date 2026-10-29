# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import json
domande = [d for d in open("domande.txt", encoding="utf-8").read().splitlines() if d.strip()]
risposte = [
    "Abbiamo 37 martelli da carpentiere.",
    "La merce in magazzino vale in tutto 2.623,30 €.",
    "Sono sotto la scorta minima il nastro isolante nero (8 pezzi, minimo 40) e il silicone sigillante trasparente "
    "(6 pezzi, minimo 20).",
    "Dobbiamo ordinare 46 pezzi in totale: 32 rotoli di nastro isolante e 14 tubetti di silicone.",
]
json.dump([{"domanda": d, "risposta": r} for d, r in zip(domande, risposte)],
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
