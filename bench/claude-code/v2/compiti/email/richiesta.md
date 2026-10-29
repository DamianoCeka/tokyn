Nella cartella `email/` ho le email arrivate all'indirizzo del negozio, una per file `.txt`. Scrivimi un programma
Python che usa Claude per smistarle: per ogni email deve dire la categoria (una tra `ordine`, `reclamo`,
`informazioni` e `spam`), se è urgente e un riassunto di una frase.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella che
contiene `email/`. Deve scrivere il risultato in `risultato.json`: una lista con un elemento per email, in ordine di
nome del file, e in ogni elemento il nome del file:

```json
[
  {"file": "msg_001.txt", "categoria": "reclamo", "urgente": true,
   "riassunto": "La cliente ha ricevuto un vaso rotto e chiede la sostituzione prima di sabato."}
]
```
