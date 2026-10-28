# Itsme

**Il linguaggio per costruire agenti IA, progettato per essere scritto bene dalle IA.**

Oggi il codice lo scrivono sempre più spesso Claude, GPT e gli altri modelli. Allora ho
pensato a un linguaggio fatto apposta per loro: sintassi di Python (che conoscono già),
pochissimi concetti, agenti e output strutturati dentro il linguaggio, ed errori che
spiegano esattamente cosa correggere.

```
type Ticket:
    categoria: "tecnico" | "commerciale" | "altro"
    urgente: bool "True se il cliente è bloccato"

def cerca_faq(domanda: str) -> str:
    """Cerca una risposta nelle FAQ aziendali."""
    return read_file("faq.txt")

agent Supporto:
    model: "claude"
    instructions: "Rispondi ai clienti in italiano, in modo breve."
    tools: [cerca_faq]
    output: Ticket

main:
    t = Supporto.ask(input("Come posso aiutarti? "))
    if t.categoria == "tecnico" and t.urgente:
        print("Ti passo subito a un operatore.")
```

Lo stesso programma in Python richiede client API, il ciclo delle chiamate agli strumenti,
lo schema JSON, il parsing e la validazione della risposta, i retry. In Itsme è tutto dentro `Supporto.ask(...)`.

## Perché funziona con le IA

| Principio | Cosa ho fatto |
|---|---|
| Sintassi che i modelli conoscono già | Parole chiave e regole di Python |
| Pochi concetti | Un solo ciclo, un solo modo di definire e usare un agente |
| L'IA si corregge da sola | `itsme check --json` restituisce codice errore, riga, colonna e suggerimento |
| Meno codice = meno errori | Agenti, strumenti, schema e validazione dell'output sono parte del linguaggio |

Esempio di errore:

```
supporto.itsme:11:24 errore E133: lo strumento "prenota_appuntameto" non esiste
  11 |     tools: [cerca_faq, prenota_appuntameto]
     |                        ^^^^^^^^^^^^^^^^^^^
     → Forse intendevi "prenota_appuntamento"? Strumenti disponibili: cerca_faq, prenota_appuntamento
```

**L'ho testato:** ho dato solo la specifica a Claude Sonnet e Claude Haiku e ho chiesto 5 programmi
a ciascuno. Risultato: **10 su 10 corretti al primo tentativo**. Dettagli e limiti del test in [`eval/`](eval).

## Installazione

```bash
pip install git+https://github.com/DamianoCeka/itsme-lang
```

Serve Python 3.10 o superiore.

## Uso

```bash
itsme new primo              # crea primo.itsme
itsme check primo.itsme      # controlla e spiega gli errori
itsme run primo.itsme --mock # prova senza chiamare l'IA (gratis)
itsme run primo.itsme        # esegue davvero (serve ANTHROPIC_API_KEY)
itsme build primo.itsme      # genera il Python equivalente
itsme spec                   # stampa la specifica
```

## Cosa c'è nel linguaggio

- **`agent`**: modello, istruzioni, strumenti, memoria, output strutturato. Si usa con `Agente.ask(testo)`.
- **`def`**: normali funzioni, che diventano strumenti quando le metti nei `tools` di un agente. I parametri arrivati dall'IA vengono validati con i tipi.
- **`type`**: dati strutturati, anche annidati, con valori ammessi (`"a" | "b"`) e descrizioni per l'IA.
- **Agenti come strumenti**: un agente può delegare a un altro.
- **Python ovunque**: `import` di qualsiasi libreria Python.
- **Errori a runtime** riportati alla riga del file `.itsme`, non del Python generato.

La specifica completa è in [`itsme/SPEC.md`](itsme/SPEC.md). Gli esempi sono in [`examples/`](examples).

## Usarlo con Claude

In [`skill/itsme/SKILL.md`](skill/itsme/SKILL.md) c'è una Skill pronta: insegna a Claude a scrivere
codice Itsme e a controllarlo con `itsme check` finché non ci sono errori.

## Come funziona

```
file.itsme → parser (Lark) → checker (tipi, nomi, agenti) → generatore → Python → runtime
```

- `itsme/grammar.lark`: la grammatica
- `itsme/checker.py`: i controlli e i messaggi d'errore
- `itsme/codegen.py`: la traduzione in Python
- `itsme/runtime.py`: agenti, ciclo degli strumenti, validazione, funzioni di base

## Stato e prossimi passi

È la **v0.1**, un prototipo funzionante. Cosa voglio aggiungere:

- [ ] Server MCP con `check`, `run` e la specifica, così qualsiasi agente di coding può usarlo
- [ ] Estensione VS Code (colori ed errori in tempo reale)
- [ ] Benchmark più ampio, anche con modelli non Claude
- [ ] Altri provider oltre ad Anthropic
- [ ] Gestione degli errori (`try`) e chiamate in parallelo tra agenti
- [ ] Messaggi d'errore anche in inglese

## Licenza

MIT
