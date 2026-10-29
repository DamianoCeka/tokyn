# Programma finto con un errore plausibile (ordina dal punteggio più basso al più alto, con sorted() senza reverse, e
# prende come migliore il primo della lista): il controllo deve bocciarlo.
import json
candidati = [
    {"file": "ferrari_giulia.txt", "punteggio": 10, "motivazione": "Ha tutti i requisiti."},
    {"file": "colombo_luca.txt", "punteggio": 5, "motivazione": "Esperienza parziale."},
    {"file": "ricci_paolo.txt", "punteggio": 4, "motivazione": "Neolaureato con solo uno stage."},
    {"file": "gallo_andrea.txt", "punteggio": 1, "motivazione": "Profilo non pertinente."},
]
candidati = sorted(candidati, key=lambda c: c["punteggio"])
json.dump({"candidati": candidati, "migliore": candidati[0]["file"]}, open("risultato.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
