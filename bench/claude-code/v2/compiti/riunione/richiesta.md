Dopo ogni riunione del team salviamo la trascrizione in `verbale.txt`. Scrivimi un programma Python che usa Claude per
ricavare dalla trascrizione le decisioni prese e le azioni da fare, con chi se ne occupa e la scadenza.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
c'è `verbale.txt`. Deve scrivere il risultato in `risultato.json`: `decisioni` è una lista di frasi brevi, `azioni` una
lista di oggetti con `cosa` (che cosa va fatto), `chi` (il nome di chi se ne occupa) ed `entro` (la scadenza, nel
formato AAAA-MM-GG):

```json
{
  "decisioni": ["Il nuovo sito va online a gennaio"],
  "azioni": [
    {"cosa": "Preparare il preventivo per il nuovo server", "chi": "Anna", "entro": "2026-11-20"}
  ]
}
```
