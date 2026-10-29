Ho un file `recensioni.txt` con una recensione di un nostro prodotto per riga. Scrivimi un programma Python che usa
Claude per capire, per ogni recensione, il sentimento (positivo, negativo o neutro) e un voto da 1 a 5, e che alla
fine calcola il voto medio.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
c'è `recensioni.txt`. Deve scrivere il risultato in `risultato.json`, con le recensioni nello stesso ordine del file:

```json
{
  "recensioni": [
    {"testo": "Arrivato in tempo, funziona benissimo.", "sentimento": "positivo", "voto": 5}
  ],
  "media": 4.0
}
```
