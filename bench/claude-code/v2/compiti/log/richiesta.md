Ho il log degli accessi del nostro sito di una giornata, `access.log`, nel formato standard di Apache (common log
format). Scrivimi un programma Python che ne ricava qualche statistica e che usa Claude per scrivere un breve commento
sul traffico della giornata.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
c'è `access.log`. Deve scrivere il risultato in `risultato.json`, contando ogni riga del log come una richiesta:
`richieste_per_ora` dice quante richieste ci sono state in ogni ora (l'ora in due cifre, come è scritta nel log), solo
per le ore con almeno una richiesta; `errori` quante richieste hanno avuto ciascun codice di stato da 400 in su, solo
per i codici presenti nel log; `ip_top` i 3 indirizzi IP che hanno fatto più richieste, dal primo al terzo; `commento`
due frasi scritte da Claude sul traffico della giornata.

```json
{"richieste_per_ora": {"08": 12, "09": 31}, "errori": {"404": 7, "500": 1},
 "ip_top": ["203.0.113.7", "198.51.100.23", "192.0.2.41"],
 "commento": "Il traffico cresce durante la mattina e ha il picco alle 9. Gli errori sono pochi, quasi tutte pagine non trovate."}
```
