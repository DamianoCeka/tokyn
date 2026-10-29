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
| `import x` / `from x import y` | usare una libreria Python |
| `NOME = valore` | costante globale (non si può modificare dopo) |
| `type Nome:` | dati strutturati |
| `def nome(...):` | funzione; può essere usata come strumento da un agente |
| `agent Nome:` | un agente IA |
| `main:` | il punto di partenza del programma (uno solo) |

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
| `model` | no (default `"claude"`) | `"claude"`, `"claude-opus"`, `"claude-haiku"`, `"mock"` oppure l'id completo di un modello |
| `tools` | no | lista di nomi di funzioni `def` o di altri agenti |
| `output` | no | nome di un `type`: l'agente risponde con dati strutturati |
| `memory` | no (default `False`) | `True` per ricordare la conversazione tra una `ask` e l'altra |
| `max_steps` | no (default `10`) | numero massimo di passaggi per ogni `ask` |

Un agente si usa **solo** così:

- `Agente.ask(testo)` → restituisce la risposta. È un `str`, oppure un valore del `type` indicato in `output`.
- `Agente.reset()` → cancella la memoria.

Durante `ask` il runtime gestisce da solo il ciclo delle chiamate agli strumenti,
i retry e la validazione dell'output. Non serve scrivere nessun ciclo.

Un agente nella lista `tools` di un altro agente diventa un sotto-agente a cui delegare.

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

- `x = valore`, `x += 1`, `x -= 1`, `x *= 2`, `x /= 2`
- `if` / `elif` / `else`
- `for x in lista:`, `for i in range(n):`, `for k, v in dizionario.items():`, `break`, `continue`
- `return`, `pass`
- Operatori: `+ - * / // %`, `== != < > <= >=`, `in`, `not in`, `and`, `or`, `not`
- Liste `[1, 2]`, dizionari `{"a": 1}`, indici `x[0]`, attributi `x.y`, chiamate `f(a, b=1)`
- Stringhe `"..."`, `'...'`, `"""..."""` e f-string `f"Ciao {nome}"`
- Metodi di stringhe, liste e dizionari di Python: `.upper()`, `.split()`, `.append()`, `.get()`, `.items()`…

Non esistono in Tokyn (il checker lo segnala e dice cosa usare): `while`, `class`, `lambda`,
`try`/`except`, `with`, `async`/`await`, `yield`, `global`, `match`.

## Funzioni già presenti

`print`, `input`, `len`, `str`, `int`, `float`, `bool`, `list`, `dict`, `range`, `enumerate`,
`zip`, `sum`, `min`, `max`, `sorted`, `reversed`, `abs`, `round`, `any`, `all`, e inoltre:

| Funzione | Cosa fa |
|---|---|
| `read_file(percorso)` | legge un file di testo |
| `write_file(percorso, testo)` | scrive (sovrascrive) un file |
| `append_file(percorso, testo)` | aggiunge in fondo a un file |
| `http_get(url)` | scarica una pagina e restituisce il testo |
| `http_post(url, dati)` | invia dati JSON e restituisce la risposta |
| `json_parse(testo)` | da testo JSON a liste/dizionari |
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
| `tokyn run file.tokyn` | esegue (serve `ANTHROPIC_API_KEY`) |
| `tokyn run file.tokyn --mock` | esegue con risposte finte, senza chiamare l'IA |
| `tokyn build file.tokyn` | genera il file Python equivalente |
| `tokyn spec` | stampa questa specifica |
| `tokyn new nome` | crea un file di partenza |

## Codici di errore principali

| Codice | Significato |
|---|---|
| E002 | costrutto Python che Tokyn non ha (`while`, `class`…) |
| E003 / E004 / E005 / E009 | manca `:` / manca il blocco indentato / indentazione sbagliata |
| E101 | nome definito due volte |
| E110 | tipo sconosciuto |
| E121 / E122 | strumento senza tipi dei parametri / senza descrizione |
| E130–E139 | campo dell'agente sbagliato, mancante o con un valore non valido |
| E142 | si tenta di modificare una costante |
| E160 / E161 | nome non definito / variabile usata prima di assegnarla |
| E170 | metodo inesistente su un agente (esistono solo `.ask` e `.reset`) |
| E171 | campo inesistente in un `type` |
| E175 | metodo inesistente su testo, lista o dizionario |
| E180–E187 | argomenti sbagliati in una chiamata |
| E190 | valore non previsto confrontato con un campo `"a" \| "b"` |
| E194 | testo + numero |
