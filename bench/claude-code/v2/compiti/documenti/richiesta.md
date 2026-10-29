Nella cartella `docs/` ho alcuni documenti interni dell'azienda (regolamenti, procedure, istruzioni), ognuno in un file
`.txt`, e in `domande.txt` le domande che ci fanno più spesso i colleghi, una per riga. Scrivimi un programma Python
che usa Claude per rispondere a ogni domanda basandosi sui documenti e che dica da quale file viene la risposta.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
ci sono `docs/` e `domande.txt`. Deve scrivere il risultato in `risultato.json`: una lista con un elemento per domanda,
nello stesso ordine di `domande.txt`, dove `fonte` è il nome del file del documento (senza la cartella):

```json
[
  {"domanda": "Quanti giorni di ferie abbiamo all'anno?", "risposta": "26 giorni lavorativi", "fonte": "ferie.txt"}
]
```
