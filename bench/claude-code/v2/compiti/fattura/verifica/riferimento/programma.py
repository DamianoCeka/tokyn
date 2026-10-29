# Programma finto che scrive la risposta giusta senza IA: il controllo deve promuoverlo.
import json
righe = [{"descrizione": "Risme carta A4 80 g", "quantita": 20, "prezzo_unitario": 4.35},
         {"descrizione": "Toner nero HP 59A", "quantita": 3, "prezzo_unitario": 89.90},
         {"descrizione": "Raccoglitori ad anelli dorso 8 cm", "quantita": 12, "prezzo_unitario": 3.20},
         {"descrizione": "Penne a sfera blu, confezione da 50", "quantita": 2, "prezzo_unitario": 14.75},
         {"descrizione": "Consegna al piano", "quantita": 1, "prezzo_unitario": 15.00}]
calcolato = round(sum(r["quantita"] * r["prezzo_unitario"] for r in righe), 2)
json.dump({"fornitore": "Cartoleria Marchetti & Figli S.n.c.", "data": "2026-02-18", "righe": righe,
           "totale_dichiarato": 440.60, "totale_calcolato": calcolato, "totale_corretto": calcolato == 440.60},
          open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
