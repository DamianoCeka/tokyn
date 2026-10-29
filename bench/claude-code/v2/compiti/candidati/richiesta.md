Quando pubblichiamo un annuncio di lavoro ci arrivano tanti curriculum e leggerli tutti richiede ore. Ho l'annuncio in
`annuncio.txt`, con i requisiti, e i curriculum nella cartella `cv/`, uno per file `.txt`. Scrivimi un programma
Python che usa Claude per valutare ogni curriculum rispetto all'annuncio, con un punteggio intero da 1 a 10 e una breve
motivazione, e che poi metta i candidati in ordine di punteggio, dal più alto al più basso, e mi dica il migliore.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
ci sono `annuncio.txt` e `cv/`. Deve scrivere il risultato in `risultato.json`, dove `file` è il nome del file del
curriculum (senza la cartella) e `migliore` è il file del candidato con il punteggio più alto:

```json
{
  "candidati": [
    {"file": "verdi_marco.txt", "punteggio": 8, "motivazione": "Ha l'esperienza richiesta, ma l'inglese è scolastico."},
    {"file": "neri_sara.txt", "punteggio": 5, "motivazione": "Buona formazione, ma poca esperienza nel ruolo."}
  ],
  "migliore": "verdi_marco.txt"
}
```
