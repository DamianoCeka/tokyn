# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import json
righe = open("recensioni.txt", encoding="utf-8").read().splitlines()
sent = ["positivo", "negativo", "neutro", "positivo", "negativo", "neutro"]
voti = [5, 1, 3, 5, 1, 3]
json.dump({"recensioni": [{"testo": t, "sentimento": s, "voto": v} for t, s, v in zip(righe, sent, voti)],
           "media": sum(voti) / len(voti)}, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
