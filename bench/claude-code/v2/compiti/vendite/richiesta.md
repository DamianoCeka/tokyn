Ogni trimestre esporto dal gestionale due file CSV, separati da virgole e con una riga di intestazione: `ordini.csv`,
con le colonne `id,cliente_id,data,importo` (data AAAA-MM-GG, importo in euro col punto per i decimali), e
`clienti.csv`, con le colonne `id,nome,paese`. Scrivimi un programma Python che calcola il fatturato di ogni paese (la
somma degli ordini dei suoi clienti) e i 3 clienti che hanno speso di più, e poi usa Claude per scrivere un breve
paragrafo per la direzione che dica qual è il paese con il fatturato più alto e commenti i numeri.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella dei due
CSV. Deve scrivere il risultato in `risultato.json`, con paesi e clienti scritti come in `clienti.csv`, i fatturati
arrotondati al centesimo e i migliori clienti dal primo al terzo:

```json
{"fatturato_per_paese": {"Italia": 15230.5, "Francia": 8120.0},
 "migliori_clienti": ["Rossi Srl", "Dupont SA", "Verdi Spa"],
 "riassunto": "Nel trimestre il paese con il fatturato più alto è l'Italia, con 15.230,50 euro..."}
```
