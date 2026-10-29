# Test: un'IA sa scrivere Tokyn leggendo solo la specifica?

È la domanda più importante per questo linguaggio, quindi l'ho misurata.

## Come ho fatto

- Due modelli: **Claude Sonnet** e **Claude Haiku** (il più piccolo).
- Ognuno aveva a disposizione **solo** [`SPEC.md`](../tokyn/SPEC.md): niente esempi del repository, niente web, niente compilatore per provare.
- Stessi 5 compiti per entrambi, scritti in un solo tentativo:
  1. `email.tokyn`: classifica email con output strutturato, ordina per priorità, salva in JSON
  2. `ristorante.tokyn`: assistente prenotazioni con memoria, due strumenti e un ciclo di al massimo 20 turni che termina con "esci"
  3. `traduttore.tokyn`: traduzione in inglese e francese con output strutturato e tabella
  4. `social.tokyn`: coordinatore con due sotto-agenti più un revisore con verdetto strutturato
  5. `fatture.tokyn`: estrazione di una fattura con tipi annidati (`list[Riga]`) e ricalcolo del totale

## Risultati (v0.1, 28 ottobre 2026)

| Modello | `tokyn check` al primo tentativo | Eseguiti con `--mock` |
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

## La Skill da sola (29 ottobre 2026)

Poi ho riscritto la Skill pensando al modello che la legge: un solo file, `SKILL.md`, con un riferimento compatto
del linguaggio al posto della specifica completa. Ho ripetuto il test in tre tornate, con le stesse regole di prima
(solo `SKILL.md`, niente compilatore, un solo tentativo). Dopo ogni tornata ho letto i dubbi dei modelli e ho fatto
verificare ogni affermazione della Skill sul compilatore vero, correggendo la Skill e, dove serviva, il linguaggio.

| Tornata | Modelli | Compiti | `tokyn check` al primo tentativo |
|---|---|---|---|
| 1 | Opus, Haiku | i 5 di sopra + `rassegna` (pagine web) e `contatti` (campi che possono mancare) | 14/14 ✓ |
| 2 | Opus, Sonnet, Haiku | 6 nuovi: `ticket`, `meteo`, `cv`, `verbale`, `quiz`, `catalogo` | 18/18 ✓ |
| 3 | Opus, Sonnet, Haiku | gli stessi 6, con la Skill aggiornata | 18/18 ✓ |

Tutti i 50 programmi girano anche con `--mock`, dando a `input()` le risposte che il programma si aspetta.
I programmi della tornata 3, non modificati, sono in [`skill/`](skill).

Cosa ho imparato:

- **Scrivere Tokyn corretto non è il problema**: 100% al primo tentativo già con la Skill più corta (1.961 token).
- **Il problema erano i dubbi.** Ogni modello elencava 10-15 punti su cui aveva dovuto indovinare (cosa succede se un
  file manca, se si può scrivere `d[k] += 1`, cosa controlla il runtime). Nel dubbio scrivevano codice più lungo
  "per sicurezza", e in una sessione vera sarebbero andati a leggersi `SPEC.md`. La Skill ora risponde a questi punti.
- Le risposte non hanno accorciato i programmi (tornata 3 rispetto alla 2: Opus +11%, Sonnet −2%, Haiku +5% di
  token, su un solo campione), ma evitano errori che il mock non mostra.
- **I dubbi hanno trovato bug veri**, ora corretti: errori a runtime indicati alla riga sbagliata, un agente che
  delega a un agente scritto più sotto si rompeva in esecuzione, le descrizioni con accenti arrivavano corrotte
  all'IA, nessun modo di gestire un file mancante o un URL rotto (ora `read_file(p, default)` e `http_get(url, default)`).
- Le abitudini di Python (comprehension, `a if c else b`, `is None`, `a, b = ...`) ora hanno un errore che dice
  esattamente cosa scrivere al loro posto.

Stessi limiti di prima: esecuzioni solo in `--mock` e solo modelli Claude.
