Sul forum del nostro sito di giardinaggio i commenti nuovi restano in attesa finché qualcuno non li approva. In
`commenti.json` ci sono quelli in attesa: una lista di oggetti con `id`, `autore` e `testo`. Scrivimi un programma
Python che usa Claude per moderarli con queste regole: `rifiuta` se il commento è spam, contiene insulti o contiene
dati personali (numeri di telefono, indirizzi, email); `rivedi` se il contenuto è utile ma il tono è aggressivo;
`pubblica` in tutti gli altri casi.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
c'è `commenti.json`. Deve scrivere il risultato in `risultato.json`: una lista con un elemento per commento, nello
stesso ordine del file, con l'`id` del commento, la `decisione`, il `motivo` in una frase e, solo per i commenti da
rivedere, una `riscrittura`, cioè una versione educata del commento che ne mantenga il contenuto:

```json
[
  {"id": 17, "decisione": "pubblica", "motivo": "Domanda pertinente e cortese."},
  {"id": 18, "decisione": "rivedi", "motivo": "Consiglio utile ma scritto con tono aggressivo.",
   "riscrittura": "Ricordo a tutti che il rame contro la peronospora va dato solo con il tempo asciutto."}
]
```
