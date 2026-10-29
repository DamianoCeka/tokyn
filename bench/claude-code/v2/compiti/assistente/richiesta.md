Mi serve un assistente clienti da terminale per il nostro negozio online. Deve rispondere alle domande dei clienti
usando le FAQ del negozio, che sono nel file `faq.txt` (domande e risposte), e ricordarsi quello che il cliente ha
detto prima nella conversazione. Scrivimi un programma Python che usa Claude per le risposte. Se la risposta non è
nelle FAQ deve dirlo, senza inventare.

Il programma deve stare in un solo file, `programma.py`, e si avvia con `python programma.py` dalla cartella in cui
c'è `faq.txt`. Legge dallo standard input una riga alla volta (ogni riga è un messaggio del cliente) e stampa la
risposta a ogni messaggio. Quando il cliente scrive `esci`, il programma termina.
