Le fatture dei fornitori mi arrivano come testo semplice. Scrivimi un programma Python che usa Claude per leggere la
fattura in `fattura.txt` e tirarne fuori il fornitore, la data e le righe (descrizione, quantità e prezzo unitario).
Poi il programma deve ricalcolare il totale dalle righe (somma di quantità per prezzo unitario) e dirmi se il totale
scritto in fattura è giusto al centesimo.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
c'è `fattura.txt`. Deve scrivere il risultato in `risultato.json`, con le righe nell'ordine della fattura, la data nel
formato AAAA-MM-GG e gli importi in euro come numeri:

```json
{
  "fornitore": "Rossi Forniture S.r.l.",
  "data": "2026-01-15",
  "righe": [
    {"descrizione": "Cartucce inchiostro nero", "quantita": 4, "prezzo_unitario": 12.5}
  ],
  "totale_dichiarato": 50.0,
  "totale_calcolato": 50.0,
  "totale_corretto": true
}
```
