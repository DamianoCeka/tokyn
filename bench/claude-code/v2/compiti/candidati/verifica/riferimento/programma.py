# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import json
candidati = [
    {"file": "ferrari_giulia.txt", "punteggio": 10, "motivazione": "Ha tutti i requisiti: economia, dieci anni di contabilità, TeamSystem, Excel avanzato, inglese B2."},
    {"file": "colombo_luca.txt", "punteggio": 5, "motivazione": "Diploma di ragioneria e un po' di prima nota, ma niente TeamSystem, Excel di base e inglese A2."},
    {"file": "ricci_paolo.txt", "punteggio": 4, "motivazione": "Laurea in economia e buon inglese, ma solo uno stage e nessun gestionale."},
    {"file": "gallo_andrea.txt", "punteggio": 1, "motivazione": "Cuoco, nessuna esperienza né formazione in contabilità."},
]
json.dump({"candidati": candidati, "migliore": "ferrari_giulia.txt"}, open("risultato.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
