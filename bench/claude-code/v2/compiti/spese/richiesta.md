Ogni mese scarico dalla banca i movimenti del conto in `movimenti.csv`: una riga di intestazione `data;descrizione;importo`
e poi un movimento per riga, con i campi separati da punto e virgola, la data nel formato GG/MM/AAAA e l'importo con la
virgola per i decimali, negativo per le uscite (per esempio `03/09/2026;PAGAMENTO POS ESSELUNGA MILANO;-23,40`).
Scrivimi un programma Python che usa Claude per assegnare a ogni movimento una categoria tra queste: `spesa alimentare`,
`trasporti`, `casa`, `svago` e `altro`. Poi il programma deve fare il totale di ogni categoria, sommando gli importi.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
c'è `movimenti.csv`. Deve scrivere il risultato in `risultato.json`, con i movimenti nello stesso ordine del file, data
e descrizione come nel file, l'importo come numero e i totali arrotondati al centesimo:

```json
{
  "movimenti": [
    {"data": "03/09/2026", "descrizione": "PAGAMENTO POS ESSELUNGA MILANO", "importo": -23.4, "categoria": "spesa alimentare"}
  ],
  "totali": {"spesa alimentare": -87.45, "trasporti": -35.0, "casa": -120.3, "svago": -42.9, "altro": -15.0}
}
```
