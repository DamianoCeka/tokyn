# Programma finto con un errore plausibile (scadenze scritte all'italiana, 13/11/2026 invece di 2026-11-13):
# il controllo deve bocciarlo.
import json
json.dump({
    "decisioni": ["Il lancio dell'app nuova slitta dal 10 al 24 novembre",
                  "Da dicembre tutto il budget pubblicitario passa dai giornali ai social"],
    "azioni": [
        {"cosa": "Sistemare i due bug del pagamento con carta", "chi": "Marco", "entro": "13/11/2026"},
        {"cosa": "Scrivere le risposte pronte per il supporto sul nuovo lancio", "chi": "Sara", "entro": "18/11/2026"},
        {"cosa": "Preparare il piano delle campagne social di dicembre", "chi": "Davide", "entro": "30/11/2026"},
    ],
}, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
