# Programma finto con un errore plausibile (media sbagliata, una negativa con voto 4): il controllo deve bocciarlo.
import json
righe = open("recensioni.txt", encoding="utf-8").read().splitlines()
sent = ["positivo", "negativo", "neutro", "positivo", "negativo", "neutro"]
voti = [5, 4, 3, 5, 1, 3]
json.dump({"recensioni": [{"testo": t, "sentimento": s, "voto": v} for t, s, v in zip(righe, sent, voti)],
           "media": 3}, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
