Ogni mattina preparo per i colleghi una scheda degli articoli di giornale che ci interessano. Scrivimi un programma
Python che usa Claude per leggere l'articolo in `articolo.txt` e preparare la scheda: un titolo breve, i cinque punti
chiave dell'articolo e le persone e le organizzazioni citate.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
c'è `articolo.txt`. Deve scrivere il risultato in `risultato.json`, con esattamente cinque punti (una frase ciascuno)
e in `citati` i nomi delle persone e delle organizzazioni, ognuno una volta sola:

```json
{
  "titolo": "Apre il pronto soccorso pediatrico del San Matteo",
  "punti": ["Primo punto chiave.", "Secondo punto chiave.", "Terzo punto chiave.", "Quarto punto chiave.",
            "Quinto punto chiave."],
  "citati": ["Marco Tessari", "Fondazione Rinaldi"]
}
```
