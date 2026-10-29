Ho il catalogo del nostro negozio online in `catalogo.csv`: una riga di intestazione e poi un prodotto per riga, con le
colonne `codice;nome;descrizione;prezzo` separate da punto e virgola. Le descrizioni sono in italiano e ci servono in
inglese per la versione internazionale del sito. Scrivimi un programma Python che usa Claude per tradurre in inglese la
descrizione di ogni prodotto.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
c'è `catalogo.csv`. Deve scrivere `catalogo_en.csv` con la stessa intestazione, lo stesso separatore e le righe nello
stesso ordine: cambia solo la descrizione, tradotta in inglese, mentre codice, nome e prezzo restano identici. Per
esempio la riga

```
TZ-014;Tazza Aurora;Tazza in ceramica fatta a mano, lavabile in lavastoviglie;12,90
```

in `catalogo_en.csv` diventa

```
TZ-014;Tazza Aurora;Handmade ceramic mug, dishwasher safe;12,90
```
