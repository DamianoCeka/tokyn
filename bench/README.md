# Benchmark: quanti token risparmio con Tokyn?

> **Benchmark vecchio, tenuto come storia.** I token sono contati con il tokenizer del pacchetto `anthropic==0.34.2`,
> che è quello dei modelli Claude 2 e per i modelli di oggi è solo una stima grossolana. Il benchmark attuale, con
> sessioni vere di Claude Code, test nascosti e analisi decisa prima, è in [`claude-code/v2/`](claude-code/v2).

Ho misurato quanti token servono a un'IA per scrivere **lo stesso programma** in Tokyn e in Python.
I token di output sono quelli che si pagano di più (5 volte quelli di input), e sono proprio quelli del codice scritto.

## Come ho fatto

Gli stessi 5 compiti (gli stessi di [`eval/`](../eval)):

1. `email`: classificazione con output strutturato, ordinamento, salvataggio in JSON
2. `ristorante`: assistente con memoria, due strumenti, ciclo di al massimo 20 turni
3. `traduttore`: traduzione in due lingue con output strutturato e tabella
4. `social`: coordinatore con due sotto-agenti più un revisore con verdetto strutturato
5. `fatture`: estrazione con tipi annidati e ricalcolo del totale

Cinque versioni, tutte scritte da IA, **nessuna scritta da me**:

| Versione | Chi l'ha scritta | Istruzioni |
|---|---|---|
| `tokyn_sonnet` | Claude Sonnet | solo la specifica di Tokyn |
| `tokyn_haiku` | Claude Haiku | solo la specifica di Tokyn |
| `python_libero` | Claude Sonnet | "usa le librerie che useresti normalmente": ha scelto l'SDK Anthropic + pydantic |
| `python_sdk` | Claude Sonnet | SDK Anthropic, codice conciso |
| `python_pydantic_ai` | Claude Sonnet | framework Pydantic AI, codice conciso |

Nessuna IA sapeva che il suo codice sarebbe stato confrontato.

**Tutti i 25 programmi funzionano**: quelli Tokyn con `tokyn run --mock`, quelli Python con un'API Anthropic
simulata (o, per Pydantic AI, con il suo `TestModel`). I programmi sono in [`programs/`](programs).

I token sono contati con il tokenizer di Claude incluso in `anthropic==0.34.2`, escludendo le righe di solo commento in tutti i linguaggi
(le descrizioni degli strumenti restano, perché servono). Per rifare il conteggio: `python bench/count_tokens.py --tokenizer <tokenizer.json>`.

## Risultati

| Compito | Tokyn (Sonnet) | Tokyn (Haiku) | Python libero | Python SDK | Python + Pydantic AI |
|---|---:|---:|---:|---:|---:|
| email | 317 | 331 | 936 | 804 | 302 |
| ristorante | 453 | 442 | 1.424 | 1.005 | 426 |
| traduttore | 282 | 259 | 774 | 994 | 331 |
| social | 511 | 507 | 1.544 | 1.442 | 532 |
| fatture | 347 | 368 | 719 | 963 | 341 |
| **Totale** | **1.910** | **1.907** | **5.397** | **5.208** | **1.932** |
| Righe | 133 | 118 | 422 | 414 | 130 |

**Rispetto a quello che Claude scrive normalmente (Python libero): −65% di token, cioè 2,8 volte meno.**

## Il costo della Skill

Per scrivere Tokyn, Claude deve prima leggere la Skill: `SKILL.md`, cioè **3.826 token di input** (2.976 nella versione
inglese), una volta per conversazione. Contiene un riferimento compatto del linguaggio scritto per il modello; la
specifica completa (`SPEC.md`, 3.626 token) la legge solo se gli serve un dettaglio raro.

Con i prezzi di Claude Sonnet 5.5 ($2 per milione di token di input, $10 per milione di output):

| | Python libero | Tokyn |
|---|---:|---:|
| Codice dei 5 programmi (output) | $0,0540 | $0,0191 |
| Lettura della Skill (input, una volta) | – | $0,0077 |
| **Totale** | **$0,0540** | **$0,0268 (−50%)** |

- In media ogni programma fa risparmiare circa **700 token di output**.
- In soldi, il primo programma ripaga il 91% della lettura della Skill (il 117% con la versione inglese, $0,0060),
  e dal secondo è guadagno puro.
- Rispetto alla prima versione della Skill (`SKILL.md` + `SPEC.md`, 3.737 token in due letture) la lettura costa
  quanto prima ma in una chiamata sola, e risponde ai dubbi che i modelli avevano scrivendo Tokyn (vedi [`eval/`](../eval)).
  La versione inglese costa il 23% in meno. In più `run --mock` controlla e prova il programma con un solo comando.
- Se la Skill resta in cache, rileggerla costa 20 volte meno ($0,10 per milione di token su Sonnet 5.5).
- Con Opus 5.5 ($4 / $20) i rapporti sono gli stessi, i valori assoluti il doppio.

Prezzi da [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing) al 29 ottobre 2026.

## Cosa dicono davvero questi numeri

- **Il risparmio è reale rispetto al Python che Claude scrive di solito.** Lasciato libero, Claude usa l'SDK Anthropic
  e riscrive ogni volta il ciclo degli strumenti, gli schemi e la validazione. In Tokyn tutto questo è nel linguaggio.
- **Un buon framework come Pydantic AI arriva allo stesso numero di token.** Se chiedi esplicitamente Pydantic AI,
  il risparmio sui token sparisce. Il vantaggio di Tokyn in quel caso è altrove: errori pensati per far correggere l'IA da sola,
  un solo modo per fare ogni cosa, nessuna dipendenza da quanto il modello ricorda l'API di un framework che cambia spesso.
- **Nelle sessioni reali il risparmio dovrebbe crescere**, perché il codice viene riletto e modificato più volte.
  Non l'ho ancora misurato.

## Limiti

- 5 compiti sono pochi, e piccoli.
- Il tokenizer è quello dei modelli Claude precedenti: i valori assoluti possono cambiare, il rapporto tra i linguaggi è indicativo.
- Tutte le IA del test sono Claude. Va ripetuto con altri modelli.
- Ho misurato la dimensione del codice finale, non i token spesi per correggerlo durante una sessione.
