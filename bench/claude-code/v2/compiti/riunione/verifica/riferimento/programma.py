# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import json
json.dump({
    "decisioni": ["Il lancio dell'app nuova slitta dal 10 al 24 novembre",
                  "Da dicembre tutto il budget pubblicitario passa dai giornali ai social"],
    "azioni": [
        {"cosa": "Sistemare i due bug del pagamento con carta", "chi": "Marco", "entro": "2026-11-13"},
        {"cosa": "Scrivere le risposte pronte per il supporto sul nuovo lancio", "chi": "Sara", "entro": "2026-11-18"},
        {"cosa": "Preparare il piano delle campagne social di dicembre", "chi": "Davide", "entro": "2026-11-30"},
    ],
}, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
