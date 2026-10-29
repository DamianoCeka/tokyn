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
| Costo con Sonnet 5.5, Skill compresa | $0,054 | **$0,027 (−50%)** |

La Skill (3.826 token da leggere una volta; 2.976 nella versione inglese) si ripaga con il primo o il secondo programma.
Onestamente: con un framework come Pydantic AI il Python arriva allo stesso numero di token di Tokyn.
Metodo completo, tutti i programmi e i limiti in [`bench/`](bench).

**L'IA lo sa scrivere.** Ho dato solo la specifica a Claude Sonnet e Claude Haiku e ho chiesto 5 programmi
a ciascuno. Risultato: **10 su 10 corretti al primo tentativo**. Poi, con la sola Skill, Opus, Sonnet e Haiku
hanno scritto altri 80 programmi in quattro tornate, anche con la Skill in inglese: **80 su 80 corretti al primo
tentativo**. Dettagli in [`eval/`](eval).

**In Claude Code, dal vivo.** Ho chiesto a Claude Code (Opus 5.5) tre programmi Python con agenti IA, con il
plugin Tokyn e senza. Con Tokyn ha speso **il 69% in meno** ($0,61 contro $1,99), con **il 54% di token di output in
meno**, ci ha messo il 24% di tempo in meno e **ha provato davvero tutti e tre i programmi** con il Claude Code
dell'utente; senza Tokyn non ha potuto provarne nessuno, perché mancava una chiave API. Dettagli in
[`bench/claude-code/`](bench/claude-code).

## Usarlo in Claude Code

Il modo principale per usare Tokyn è come **plugin di Claude Code**. In una sessione di Claude Code:

```text
/plugin marketplace add DamianoCeka/tokyn
/plugin install tokyn@tokyn
```

(`tokyn-en@tokyn` per la versione in inglese della Skill, che costa il 22% di token in meno.)

Poi chiedi quello che ti serve, per esempio *"scrivimi in Python un bot che smista le email dei clienti, usa tokyn"*
(o richiama la Skill con `/tokyn:tokyn`). Claude:

1. scrive il programma in Tokyn, con circa un terzo dei token del Python;
2. lo controlla e lo prova gratis con risposte finte (`--mock`), correggendo gli errori che il compilatore gli spiega;
3. lo prova con l'IA vera **usando il tuo Claude Code**: non serve nessuna chiave API;
4. se vuoi Python, genera con `tokyn build --standalone` un file Python unico. Quel codice lo produce il
   compilatore, non il modello, quindi non costa token.

Il plugin contiene il compilatore: serve solo Python 3.10 o superiore con la libreria `lark` (Claude la installa da
solo se manca).

### Chi risponde agli agenti

Quando il programma gira, ogni `Agente.ask(...)` è una domanda a Claude. Tokyn sceglie da solo chi risponde:

- **Claude Code** (se non c'è una chiave API e il comando `claude` è installato): usa il tuo account, ogni domanda
  è una chiamata `claude -p`. È il modo per provare i programmi mentre li sviluppi.
- **API di Anthropic** (se c'è `ANTHROPIC_API_KEY`): per i programmi che girano da soli, per esempio su un server.
  Qui il runtime usa caching, output strutturati e Batch API per spendere meno.

Si può forzare la scelta con `tokyn run file.tokyn --backend claude-code` (o `api`).

### Senza Claude Code

```bash
pip install git+https://github.com/DamianoCeka/tokyn
```

Serve Python 3.10 o superiore. Gli zip della Skill per Claude (`python scripts/build_skill.py` crea
`dist/tokyn-skill.zip` e `dist/tokyn-skill-en.zip`) si caricano nelle impostazioni delle Skill.

## Uso

```bash
tokyn new primo              # crea primo.tokyn
tokyn check primo.tokyn      # controlla e spiega gli errori
tokyn run primo.tokyn --mock # prova senza chiamare l'IA (gratis)
tokyn run primo.tokyn        # esegue davvero (con Claude Code oppure con ANTHROPIC_API_KEY)
tokyn build primo.tokyn      # genera il Python equivalente
tokyn build primo.tokyn --standalone  # ...in un file unico che non richiede Tokyn
tokyn spec                   # stampa la specifica
```

## Cosa c'è nel linguaggio

- **`agent`**: modello, istruzioni, strumenti, memoria, output strutturato. Si usa con `Agente.ask(testo)`.
- **`def`**: normali funzioni, che diventano strumenti quando le metti nei `tools` di un agente. I parametri arrivati dall'IA vengono validati con i tipi.
- **`type`**: dati strutturati, anche annidati, con valori ammessi (`"a" | "b"`) e descrizioni per l'IA.
- **Agenti come strumenti**: un agente può delegare a un altro.
- **Python ovunque**: `import` di qualsiasi libreria Python.
- **Slice** di testi e liste: `testo[:200]`, `lista[-3:]`.
- **Valori di riserva al posto di `try`**: `read_file(p, "")` e `http_get(url, "")` non fermano il programma se il file manca o la rete cade; `to_number(testo, 0)` converte anche `"4,50"`.

## Meno costi anche quando il programma gira

Il runtime usa da solo le funzioni dell'API di Claude che fanno risparmiare:

- **Prompt caching**: istruzioni e strumenti di ogni agente restano in cache tra una chiamata e l'altra.
- **Output strutturati nativi**: la risposta arriva già nel formato del `type`, senza giri in più.
- **Batch API**: `Agente.ask_all(testi)` risponde a una lista di testi a metà prezzo.
- **`effort: "low"`** negli agenti che classificano o estraggono, per spendere meno token di ragionamento.
- `tokyn run file.tokyn --usage` mostra quanti token sono stati spesi e quanti letti dalla cache.
- **Errori a runtime** riportati alla riga del file `.tokyn`, non del Python generato.
- **Errori mirati per le abitudini di Python**: se un modello scrive una comprehension, `a if c else b`, `is None` o `a, b = ...`, il checker dice esattamente cosa scrivere al loro posto.

La specifica completa è in [`tokyn/SPEC.md`](tokyn/SPEC.md). Gli esempi sono in [`examples/`](examples).

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
- [ ] Chiamate in parallelo tra agenti
- [ ] Messaggi d'errore anche in inglese

## Licenza

MIT
