# Test: un'IA sa scrivere Itsme leggendo solo la specifica?

È la domanda più importante per questo linguaggio, quindi l'ho misurata.

## Come ho fatto

- Due modelli: **Claude Sonnet** e **Claude Haiku** (il più piccolo).
- Ognuno aveva a disposizione **solo** [`SPEC.md`](../itsme/SPEC.md): niente esempi del repository, niente web, niente compilatore per provare.
- Stessi 5 compiti per entrambi, scritti in un solo tentativo:
  1. `email.itsme`: classifica email con output strutturato, ordina per priorità, salva in JSON
  2. `ristorante.itsme`: assistente prenotazioni con memoria, due strumenti e un ciclo di al massimo 20 turni che termina con "esci"
  3. `traduttore.itsme`: traduzione in inglese e francese con output strutturato e tabella
  4. `social.itsme`: coordinatore con due sotto-agenti più un revisore con verdetto strutturato
  5. `fatture.itsme`: estrazione di una fattura con tipi annidati (`list[Riga]`) e ricalcolo del totale

## Risultati (v0.1, 28 ottobre 2026)

| Modello | `itsme check` al primo tentativo | Eseguiti con `--mock` |
|---|---|---|
| Sonnet | 5/5 ✓ | 5/5 ✓ |
| Haiku | 5/5 ✓ | 5/5 ✓ |

Ho anche chiamato gli strumenti scritti dalle IA (es. `controlla_disponibilita`, `prenota`) con dati veri: funzionano.

Un dettaglio che mi ha fatto piacere: per il ciclo "fino a quando l'utente scrive esci" entrambi
hanno usato `for turno in range(20):` con `break`, perché la specifica dice che `while` non esiste.
La regola "un solo modo per fare ogni cosa" funziona anche per le IA.

## Limiti di questo test

- 10 programmi sono pochi: serve un benchmark più ampio e compiti più difficili.
- Le esecuzioni sono in modalità `--mock`, cioè senza chiamate reali al modello.
- Le IA che hanno scritto il codice e quella che ha progettato il linguaggio sono della stessa famiglia (Claude). Va ripetuto con altri modelli.

I programmi originali, non modificati, sono nelle cartelle [`sonnet/`](sonnet) e [`haiku/`](haiku).
