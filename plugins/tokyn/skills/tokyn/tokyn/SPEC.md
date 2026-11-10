# Tokyn v0.1 — Specifica

Tokyn è un linguaggio per costruire **agenti IA**. Ha la sintassi di Python, ma con
agenti, strumenti e output strutturati già dentro il linguaggio. Viene tradotto in
Python, quindi può usare qualsiasi libreria Python.

File: `.tokyn` · Indentazione: 4 spazi · Commenti: `#`

## Regole d'oro

1. Parole chiave in inglese, come Python: `def`, `if`, `elif`, `else`, `for`, `in`, `return`, `and`, `or`, `not`, `True`, `False`, `None`.
2. **Un solo modo per fare ogni cosa.** Un solo ciclo (`for`), un solo modo di definire un agente, un solo modo di chiamarlo (`Agente.ask(testo)`).
3. Prima di eseguire, controlla sempre con `tokyn check file.tokyn` e correggi tutti gli errori segnalati.

## Struttura di un file

Un file contiene, in qualunque ordine:

| Costrutto | A cosa serve |
|---|---|
| `import x` / `from x import y as z` | usare una libreria Python |
| `NOME = valore` | costante globale (non si può modificare dopo) |
| `type Nome:` | dati strutturati |
| `def nome(...):` | funzione; può essere usata come strumento da un agente |
| `agent Nome:` | un agente IA |
| `main:` | il punto di partenza del programma (uno solo) |

Le costanti e i valori predefiniti dei parametri si calcolano subito, dall'alto in basso:
possono usare solo costanti e funzioni scritte prima di loro (come in Python).

## Agenti

```
agent Supporto:
    model: "claude"
    instructions: "Rispondi ai clienti in italiano, in modo breve."
    tools: [cerca_faq, prenota]
    memory: True
```

Campi (si scrivono con `:`, mai con `=`):

| Campo | Obbligatorio | Valore |
|---|---|---|
| `instructions` | sì | testo: chi è l'agente e cosa deve fare. Può essere `"""su più righe"""` o una costante |
| `model` | no (default `"claude"`) | `"claude"`, `"claude-opus"`, `"claude-haiku"`, `"mock"`, l'id completo di un modello Claude, oppure `"fornitore:modello"` per un altro fornitore (vedi [Altri fornitori](#altri-fornitori)) |
| `tools` | no | lista di nomi di funzioni `def` o di altri agenti |
| `output` | no | nome di un `type`: l'agente risponde con dati strutturati |
| `memory` | no (default `False`) | `True` per ricordare la conversazione tra una `ask` e l'altra |
| `max_steps` | no (default `10`) | numero massimo di passaggi per ogni `ask` |
| `effort` | no | quanto ragiona l'IA: `"low"`, `"medium"`, `"high"`, `"xhigh"`, `"max"`. `"low"` costa meno: va bene per classificare ed estrarre |

Un agente si usa **solo** così:

- `Agente.ask(testo)` → restituisce la risposta. È un `str`, oppure un valore del `type` indicato in `output`.
- `Agente.ask_all(testi)` → una lista di risposte, nello stesso ordine dei testi: come un ciclo di `ask`, ma con la
  Batch API di Anthropic, che costa la metà. È più lento (di solito minuti, al massimo 24 ore) e non usa la memoria:
  adatto ai lavori in blocco, non alle chat. Un testo rifiutato o con un errore nel batch viene riprovato con una
  chiamata normale; se resta senza risposta, il programma si ferma dicendo quale. Con Claude Code e con gli altri
  fornitori fa richieste normali senza memoria, fino a 4 insieme (`TOKYN_PARALLELO` cambia il numero).
- `Agente.reset()` → cancella la memoria.

Durante `ask` il runtime gestisce da solo il ciclo delle chiamate agli strumenti,
i retry e la validazione dell'output. Non serve scrivere nessun ciclo.

Un agente nella lista `tools` di un altro agente diventa un sotto-agente a cui delegare.

## Altri fornitori

Tokyn è pensato per Claude, e i suoi benchmark sono stati fatti con Claude di Anthropic. Un agente può però usare
un altro fornitore con `model: "fornitore:modello"`, tramite la sua API compatibile con OpenAI (Chat Completions):

```
agent Riassunto:
    model: "openai:gpt-5.6-luna"
    instructions: "Riassumi in tre righe."
```

| Prefisso | Chiave | Note |
|---|---|---|
| `openai` | `OPENAI_API_KEY` | per gli strumenti `gpt-5.6-terra` o `gpt-5.6-luna`: altri modelli recenti li usano solo con la Responses API o con `reasoning_effort` `"none"`, che Tokyn non manda |
| `gemini` | `GEMINI_API_KEY` | API compatibile di Google, ancora in beta |
| `mistral` | `MISTRAL_API_KEY` | `effort` vale solo come `"high"` (o più) |
| `deepseek` | `DEEPSEEK_API_KEY` | output come JSON libero, validato e ritentato |
| `groq` | `GROQ_API_KEY` | schema rigido solo su alcuni modelli e senza strumenti; altrimenti JSON libero o lo strumento `rispondi` |
| `openrouter` | `OPENROUTER_API_KEY` | il modello si scrive con il suo autore: `openrouter:google/gemini-3.8-flash` |
| `xai` | `XAI_API_KEY` | `effort` non si usa |
| `ollama` | nessuna | in locale (`http://localhost:11434/v1`); prima `ollama pull modello`. Contesto predefinito corto: alzalo con `OLLAMA_CONTEXT_LENGTH` |
| `openai-compatible` | `TOKYN_OPENAI_API_KEY` (se serve) | qualunque altro server compatibile, all'indirizzo in `TOKYN_OPENAI_BASE_URL` (es. `http://localhost:8000/v1`) |

- Si comportano come gli agenti Claude: istruzioni, strumenti, `max_steps`, `memory`, `reset`, output strutturati
  validati e ritentati. Dove il fornitore lo permette l'output usa uno schema rigido (`json_schema`), altrimenti
  JSON libero o lo strumento `rispondi`. `ask_all` fa fino a 4 richieste insieme.
- `effort` diventa `reasoning_effort` solo con `openai`, `gemini`, `mistral`, `deepseek` e `groq`; altrove si ignora.
- Senza la chiave il programma si ferma dicendo quale variabile impostare. `--mock` funziona con ogni fornitore,
  senza chiavi. `--backend` e Claude Code valgono solo per i modelli Claude.
- I limiti di frequenza e i server occupati si riprovano da soli (rispettando `Retry-After`); credito esaurito e
  richieste sbagliate no. `--usage` conta anche i token degli altri fornitori.

## Strumenti (funzioni)

Ogni `def` è una normale funzione. Se compare nei `tools` di un agente, deve avere:

- il **tipo di ogni parametro**;
- una **descrizione** come prima riga del corpo (stringa), che l'IA legge per decidere quando usarla.

```
def cerca_cliente(email: str) -> str:
    """Cerca un cliente per email e restituisce nome e piano attivo."""
    clienti = json_parse(read_file("clienti.json"))
    for c in clienti:
        if c["email"] == email:
            return f"{c['nome']} ({c['piano']})"
    return "Cliente non trovato."
```

Gli argomenti che arrivano dall'IA vengono controllati e convertiti in base ai tipi
dichiarati. Se lo strumento va in errore, l'errore torna all'IA, che può riprovare.
Con `ask_all` senza Batch API (Claude Code, altri fornitori) uno strumento può girare più volte insieme, in
thread diversi.

## Tipi

```
type Ticket:
    categoria: "tecnico" | "commerciale" | "altro"
    urgente: bool "True se il cliente è bloccato"
    tag: list[str]
```

- Tipi base: `str`, `int`, `float`, `bool`, `dict`, `list[T]`, oppure il nome di un altro `type`.
- `"a" | "b" | "c"`: solo uno dei valori elencati. Il checker segnala i confronti con valori non previsti.
- Una stringa dopo il tipo è la descrizione del campo e viene passata all'IA.
- Tutti i campi sono obbligatori.
- Si crea con i nomi dei campi: `Ticket(categoria="altro", urgente=False, tag=[])`.
- Si legge e si modifica con il punto: `t.categoria`, `t.urgente = True`.

## Istruzioni ed espressioni

Come in Python:

- `x = valore`, `x += 1`, `x -= 1`, `x *= 2`, `x /= 2`, `x //= 2`, `x %= 2`; anche su `d["k"]`, `lista[i]`, `t.campo`
- `if` / `elif` / `else`
- `for x in lista:`, `for i in range(n):`, `for k, v in dizionario.items():`, `break`, `continue`
- `return`, `pass`
- Numeri: `3`, `2.5`, `1_000`, `1e-9`
- Operatori: `+ - * / // % **`, `== != < > <= >=` (anche concatenati: `0 <= x < 3`), `in`, `not in`, `and`, `or`, `not`
- Liste `[1, 2]`, dizionari `{"a": 1}`, indici `x[0]`, attributi `x.y`, chiamate `f(a, b=1)`
- Slice di testi e liste: `testo[:200]`, `lista[1:]`, `lista[-3:]`, `testo[::-1]`
- Stringhe `"..."`, `'...'`, `"""..."""`, `r"\d+"` e f-string `f"Ciao {nome}"`
- Metodi di stringhe, liste e dizionari di Python: `.upper()`, `.split()`, `.append()`, `.get()`, `.items()`…

Non esistono in Tokyn (il checker lo segnala e dice cosa usare): `while`, `class`, `lambda`,
`try`/`except`, `with`, `async`/`await`, `yield`, `global`, `match`, le comprehension
`[x for x in ...]` (usa `for` con `.append()`), `a if c else b` (usa `if`/`else`),
`is` (usa `==` e `!=`), tuple e set (usa liste), `a, b = ...` e `return a, b` (usa una lista),
`del` (usa `.pop()`), `raise` e `assert` (usa `if` e `return`), `def` dentro altre funzioni.
Al posto di `try`/`except`, `read_file`, `http_get`, `http_post` e `json_parse` accettano un valore di riserva (`default`).

## Funzioni già presenti

`print`, `input`, `len`, `str`, `int`, `float`, `bool`, `list`, `dict`, `range`, `enumerate`,
`zip`, `sum`, `min`, `max`, `sorted`, `reversed`, `abs`, `round`, `any`, `all`, e inoltre:

| Funzione | Cosa fa |
|---|---|
| `read_file(percorso, default)` | legge un file di testo; se non esiste restituisce `default` (senza `default` si ferma con un errore) |
| `write_file(percorso, testo)` | scrive (sovrascrive) un file |
| `append_file(percorso, testo)` | aggiunge in fondo a un file |
| `http_get(url, default)` | scarica una pagina e restituisce il testo; se la rete fallisce restituisce `default` |
| `http_post(url, dati, default)` | invia dati JSON e restituisce la risposta; se fallisce restituisce `default` |
| `json_parse(testo, default)` | da testo JSON a liste/dizionari; se non è JSON valido restituisce `default` |
| `to_number(testo, default)` | da testo a `int` o `float` (`"42"`, `"4,50"`, `"1.234,56"`); se non è un numero restituisce `default` |
| `json_dump(valore)` | da valore (anche `type`) a testo JSON |
| `env(nome, default)` | legge una variabile d'ambiente |
| `now()` | data e ora attuali, es. `"2026-10-28T14:30:00"` |
| `sleep(secondi)` | aspetta |

## Esempio completo

```
type Recensione:
    sentimento: "positivo" | "neutro" | "negativo"
    punteggio: int "da 1 a 5"
    riassunto: str

agent Analista:
    model: "claude-haiku"
    instructions: "Analizza la recensione di un cliente."
    output: Recensione

main:
    testi = read_file("recensioni.txt").split("\n")
    negative = 0
    for testo in testi:
        if not testo.strip():
            continue
        r = Analista.ask(testo)
        if r.sentimento == "negativo":
            negative += 1
            print(f"⚠️ {r.punteggio}/5 — {r.riassunto}")
    print(f"Recensioni negative: {negative}")
```

## Comandi

| Comando | Cosa fa |
|---|---|
| `tokyn check file.tokyn` | controlla il file e mostra gli errori con il suggerimento per correggerli |
| `tokyn check --json file.tokyn` | stessa cosa in JSON (per IA e strumenti) |
| `tokyn run file.tokyn` | esegue: gli agenti rispondono con l'API se c'è `ANTHROPIC_API_KEY`, altrimenti con Claude Code (`claude -p`, l'account di chi lo usa) |
| `tokyn run file.tokyn --backend claude-code` | sceglie chi risponde agli agenti (`claude-code` o `api`) |
| `tokyn run file.tokyn --mock` | esegue con risposte finte, senza chiamare l'IA |
| `tokyn run file.tokyn --usage` | alla fine mostra i token spesi e quelli letti dalla cache |
| `tokyn build file.tokyn` | genera il file Python equivalente |
| `tokyn build file.tokyn --standalone` | genera un file Python autonomo (serve solo `anthropic`, e per gli altri fornitori niente) |
| `tokyn spec` | stampa questa specifica |
| `tokyn new nome` | crea un file di partenza |
| `tokyn check --lang en file.tokyn` | lingua dei messaggi (`it` o `en`), con ogni comando. Vince la variabile `TOKYN_LANG`; senza nessuna delle due vale la lingua della Skill o del sistema |

## Codici di errore principali

| Codice | Significato |
|---|---|
| E002 | costrutto Python che Tokyn non ha (`while`, `class`, comprehension…) |
| E003 / E004 / E005 / E009 | manca `:` / manca il blocco indentato / indentazione sbagliata |
| E101 | nome definito due volte |
| E110 | tipo sconosciuto |
| E115 | `type` ricorsivo (contiene se stesso, anche tramite altri `type`) |
| E121 / E122 | strumento senza tipi dei parametri / senza descrizione |
| E130–E139 | campo dell'agente sbagliato, mancante o con un valore non valido |
| E144 | agenti che si delegano a vicenda |
| E145 | valore di `effort` non valido |
| E146 | fornitore sconosciuto in `model: "fornitore:modello"`, o nome del modello mancante |
| E142 | si tenta di modificare una costante |
| E160 / E161 | nome non definito / variabile usata prima di assegnarla |
| E162 | costante o valore predefinito che usa qualcosa scritto più sotto |
| E170 | metodo inesistente su un agente (esistono solo `.ask` e `.reset`) |
| E171 | campo inesistente in un `type` |
| E175 | metodo inesistente su testo, lista o dizionario |
| E180–E187 | argomenti sbagliati in una chiamata |
| E190 | valore non previsto confrontato con un campo `"a" \| "b"` |
| E194 | testo + numero |
