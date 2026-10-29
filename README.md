# Tokyn

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
lo schema JSON, il parsing e la validazione della risposta, i retry. In Tokyn è tutto dentro `Supporto.ask(...)`.

## Perché funziona con le IA

| Principio | Cosa ho fatto |
|---|---|
| Sintassi che i modelli conoscono già | Parole chiave e regole di Python |
| Pochi concetti | Un solo ciclo, un solo modo di definire e usare un agente |
| L'IA si corregge da sola | `tokyn check --json` restituisce codice errore, riga, colonna e suggerimento |
| Meno codice = meno errori | Agenti, strumenti, schema e validazione dell'output sono parte del linguaggio |

Esempio di errore:

```
supporto.tokyn:11:24 errore E133: lo strumento "prenota_appuntameto" non esiste
  11 |     tools: [cerca_faq, prenota_appuntameto]
     |                        ^^^^^^^^^^^^^^^^^^^
     → Forse intendevi "prenota_appuntamento"? Strumenti disponibili: cerca_faq, prenota_appuntamento
```

## I numeri

**Meno token.** Ho fatto scrivere gli stessi 5 programmi in Tokyn e in Python, sempre da Claude.
Lasciato libero di scegliere, in Python Claude ha scritto **5.397 token**; in Tokyn **1.910**.

| | Python (quello che Claude scrive di solito) | Tokyn |
|---|---:|---:|
| Token di codice per 5 programmi | 5.397 | **1.910 (−65%)** |
| Costo con Sonnet 5.5, Skill compresa | $0,054 | **$0,027 (−51%)** |

La Skill (3.737 token da leggere una volta) si ripaga già dal primo programma.
Onestamente: con un framework come Pydantic AI il Python arriva allo stesso numero di token di Tokyn.
Metodo completo, tutti i programmi e i limiti in [`bench/`](bench).

**L'IA lo sa scrivere.** Ho dato solo la specifica a Claude Sonnet e Claude Haiku e ho chiesto 5 programmi
a ciascuno. Risultato: **10 su 10 corretti al primo tentativo**. Dettagli in [`eval/`](eval).

## Installazione

```bash
pip install git+https://github.com/DamianoCeka/tokyn
```

Serve Python 3.10 o superiore.

## Uso

```bash
tokyn new primo              # crea primo.tokyn
tokyn check primo.tokyn      # controlla e spiega gli errori
tokyn run primo.tokyn --mock # prova senza chiamare l'IA (gratis)
tokyn run primo.tokyn        # esegue davvero (serve ANTHROPIC_API_KEY)
tokyn build primo.tokyn      # genera il Python equivalente
tokyn spec                   # stampa la specifica
```

## Cosa c'è nel linguaggio

- **`agent`**: modello, istruzioni, strumenti, memoria, output strutturato. Si usa con `Agente.ask(testo)`.
- **`def`**: normali funzioni, che diventano strumenti quando le metti nei `tools` di un agente. I parametri arrivati dall'IA vengono validati con i tipi.
- **`type`**: dati strutturati, anche annidati, con valori ammessi (`"a" | "b"`) e descrizioni per l'IA.
- **Agenti come strumenti**: un agente può delegare a un altro.
- **Python ovunque**: `import` di qualsiasi libreria Python.
- **Errori a runtime** riportati alla riga del file `.tokyn`, non del Python generato.

La specifica completa è in [`tokyn/SPEC.md`](tokyn/SPEC.md). Gli esempi sono in [`examples/`](examples).

## Usarlo con Claude (Skill)

Il modo principale per usare Tokyn è come **Skill di Claude**: quando chiedi un agente o un'automazione con IA,
Claude lo scrive in Tokyn, lo controlla con `tokyn check` finché non ci sono errori, e lo esegue.

1. Crea lo zip: `python scripts/build_skill.py` (oppure scaricalo dalle Release).
2. Caricalo in Claude, nelle impostazioni delle Skill.

Lo zip contiene anche il compilatore, quindi non serve installare niente oltre a `lark`.

**Compatibile con tutto:** se ti serve Python, Claude scrive in Tokyn e poi genera il Python con
`tokyn build`. Quel codice lo produce il compilatore, non il modello, quindi non costa token, e gira ovunque giri Python.

## Come funziona

```
file.tokyn → parser (Lark) → checker (tipi, nomi, agenti) → generatore → Python → runtime
```

- `tokyn/grammar.lark`: la grammatica
- `tokyn/checker.py`: i controlli e i messaggi d'errore
- `tokyn/codegen.py`: la traduzione in Python
- `tokyn/runtime.py`: agenti, ciclo degli strumenti, validazione, funzioni di base

## Stato e prossimi passi

È la **v0.1**, un prototipo funzionante. Cosa voglio aggiungere:

- [ ] Server MCP con `check`, `run` e la specifica, così qualsiasi agente di coding può usarlo
- [ ] Estensione VS Code (colori ed errori in tempo reale)
- [ ] Benchmark più ampio: più compiti, altri modelli, token spesi in sessioni reali con correzioni
- [ ] Altri provider oltre ad Anthropic
- [ ] Gestione degli errori (`try`) e chiamate in parallelo tra agenti
- [ ] Messaggi d'errore anche in inglese

## Licenza

MIT
