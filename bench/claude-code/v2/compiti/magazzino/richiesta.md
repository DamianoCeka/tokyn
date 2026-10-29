Ho l'inventario del magazzino in `inventario.json`: per ogni prodotto il codice, il nome, la quantità, il prezzo
unitario in euro e la scorta minima. I colleghi mi fanno continuamente domande sull'inventario (quanti pezzi abbiamo di
un prodotto, quanto vale in tutto il magazzino, quali prodotti sono sotto la scorta minima e simili) e le ho raccolte
in `domande.txt`, una per riga. Scrivimi un programma Python che usa Claude per rispondere a ogni domanda in italiano,
con una risposta breve. I numeri nelle risposte devono essere esatti: li usiamo per fare gli ordini.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
ci sono `inventario.json` e `domande.txt`. Deve scrivere il risultato in `risultato.json`: una lista con un elemento
per domanda, nello stesso ordine di `domande.txt`:

```json
[
  {"domanda": "Quante risme di carta A4 abbiamo?", "risposta": "Abbiamo 120 risme di carta A4."}
]
```
