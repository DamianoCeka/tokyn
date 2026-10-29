Teniamo i contratti dei nostri clienti in `contratti.csv`, separato da virgole, con la riga di intestazione
`cliente,servizio,scadenza,email` e la scadenza nel formato AAAA-MM-GG. Scrivimi un programma Python che, data una data
di riferimento, trova i contratti che scadono tra quella data e i 30 giorni successivi, estremi compresi, e per ognuno
usa Claude per scrivere un'email di promemoria che si rivolga al cliente per nome e citi il servizio in scadenza.

Il programma deve stare in un solo file, `programma.py`, e si avvia dalla cartella in cui c'è `contratti.csv` con la
data di riferimento come argomento, per esempio `python programma.py 2026-11-01`. Deve scrivere in `risultato.json` i
contratti in scadenza ordinati per scadenza, dal più vicino, con cliente, servizio e scadenza come nel file e in
`giorni_mancanti` i giorni dalla data di riferimento alla scadenza (0 se scade proprio quel giorno):

```json
{"in_scadenza": [
  {"cliente": "Ottica Ferri", "servizio": "Assistenza tecnica", "scadenza": "2026-11-12", "giorni_mancanti": 11,
   "oggetto": "Il contratto di assistenza tecnica scade il 12 novembre", "testo": "Gentile Ottica Ferri, ..."}
]}
```
