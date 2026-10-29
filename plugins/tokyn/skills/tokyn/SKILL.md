---
name: tokyn
description: Scrive in Tokyn (file .tokyn) i programmi che usano Claude (agenti IA, chatbot, estrazione o classificazione di testi), con molti meno token del Python equivalente; li controlla e li prova con il compilatore incluso e, se l'utente vuole Python, gli consegna il file Python generato dal compilatore. Usala quando l'utente chiede un programma o uno script che usa Claude o agenti IA, anche in Python, quando nomina Tokyn, o quando nel progetto ci sono file .tokyn. Non usarla per programmi senza IA, se l'utente chiede esplicitamente un altro framework (SDK Anthropic, LangChain…) o se il codice va in un progetto scritto in un linguaggio diverso da Python.
---

# Tokyn

Linguaggio con la sintassi di Python in cui agenti, strumenti e output strutturati fanno parte del linguaggio:
ciclo degli strumenti, schema JSON, validazione, retry e caching li fa il runtime. Lo stesso programma costa circa
un terzo dei token del Python. Tutto quello che serve per scriverlo è in questo file; la specifica completa,
`${CLAUDE_SKILL_DIR}/tokyn/SPEC.md`, serve solo per dettagli rari.

## Procedura

1. Scrivi il programma in un file `.tokyn` nella cartella del progetto. Se l'utente vuole Python lo riceve al
   passo 4, generato dal compilatore; il `.tokyn` resta accanto come sorgente da modificare.
2. Controlla e prova gratis, con risposte finte: `python ${CLAUDE_SKILL_DIR}/tokyn_cli.py run file.tokyn --mock`
   - Se ci sono errori, li elenca con riga, colonna e correzione (`→`) e non esegue nulla.
     Correggi con modifiche puntuali, senza riscrivere il file, e ripeti finché gira.
   - Se il programma usa `input()`, passa le risposte una per riga:
     `printf 'ciao\nesci\n' | python ${CLAUDE_SKILL_DIR}/tokyn_cli.py run file.tokyn --mock`
   - In mock gli agenti non chiamano gli strumenti; `write_file`, `http_post` ecc. invece vengono eseguiti davvero.
3. Quando serve vedere risposte vere: `python ${CLAUDE_SKILL_DIR}/tokyn_cli.py run file.tokyn --usage`.
   Senza `ANTHROPIC_API_KEY` gli agenti rispondono con il Claude Code dell'utente (`claude -p`: nessuna chiave,
   qualche secondo per ogni `ask`); con la chiave usano l'API. Se il programma fa molte chiamate, avvisa l'utente
   prima e lancialo in background. `--usage` mostra alla fine i token spesi. Per le regole di Anthropic Claude Code
   serve a provare: un programma che gira da solo o per altre persone ha bisogno della chiave API.
4. Se l'utente vuole Python: `python ${CLAUDE_SKILL_DIR}/tokyn_cli.py build file.tokyn --standalone -o file.py`.
   Il file non dipende da Tokyn e funziona con la chiave API o con Claude Code. Non scrivere il Python a mano:
   costerebbe i token che Tokyn fa risparmiare.

## Riferimento del linguaggio

```
import math                                    # librerie Python
SOGLIA = 3                                     # costante globale: non si può riassegnare

type Riga:                                     # dati strutturati; tutti i campi sono obbligatori
    prodotto: str
    prezzo: float "prezzo unitario in euro"    # stringa dopo il tipo = descrizione per l'IA

type Ticket:
    categoria: "tecnico" | "commerciale" | "altro" "chi deve gestirlo"   # solo uno di questi valori
    urgente: bool
    tag: list[str]
    righe: list[Riga]                          # tipi: str int float bool dict list[T] o un altro type

def cerca_faq(domanda: str) -> str:
    """Cerca una risposta nelle FAQ aziendali."""   # strumento: tipi dei parametri e descrizione obbligatori
    return read_file("faq.txt")

agent Tecnico:
    instructions: "Risolvi problemi tecnici."
    effort: "low"                              # facoltativo: "low" per classificare ed estrarre costa meno

agent Supporto:
    model: "claude"                            # default "claude"; anche "claude-opus", "claude-haiku", "mock" o un id
    instructions: """
        Rispondi ai clienti in italiano.
    """                                        # obbligatorio: qualsiasi testo, anche f"... {COSTANTE}"
    tools: [cerca_faq, Tecnico]                # funzioni def o altri agenti a cui delegare
    output: Ticket                             # facoltativo: risposta strutturata invece di str
    memory: True                               # facoltativo (default False): ricorda tra una ask e l'altra
    max_steps: 10                              # facoltativo: passaggi massimi per ogni ask

def per_prezzo(r: Riga) -> float:
    return r.prezzo

main:                                          # punto di partenza, uno solo
    conteggi = {"tecnico": 0, "commerciale": 0, "altro": 0}
    for turno in range(20):                    # ciclo di chat: for + break
        testo = input("Tu: ")
        if testo.strip().lower() == "esci":
            break
        t = Supporto.ask(testo)                # un solo argomento; restituisce str o il type di output
        conteggi[t.categoria] += 1
        if t.categoria == "tecnico" and t.urgente:
            righe = sorted(t.righe, key=per_prezzo, reverse=True)   # ordinare per campo: def + key=
            for i, r in enumerate(righe[:SOGLIA]):
                print(f"{i + 1}. {r.prodotto}: {r.prezzo:.2f} €")
        elif t.categoria not in ["commerciale"]:
            print(json_dump(t))
    Supporto.reset()                           # cancella la memoria
    note = Tecnico.ask_all(["Il pc non parte", "Il wifi è lento"])  # molti testi: Batch API, metà prezzo
    nuovo = Ticket(categoria="altro", urgente=False, tag=[], righe=[])  # costruttore con i nomi dei campi
    nuovo.urgente = True
```

- Istruzioni: `=` e `+= -= *= /= //= %=` (anche su `d["k"]`, `lista[i]`, `t.campo`), `if`/`elif`/`else`,
  `for x in ...` (anche `for k, v in d.items()` e `for a, b in zip(x, y)`), `break`, `continue`, `return` (in `main` termina il programma),
  `pass`. Le variabili valgono in tutta la funzione, come in Python.
- Espressioni come in Python: `+ - * / // % **`, confronti anche concatenati (`0 <= x < 3`), `and or not in`,
  numeri `1_000` e `1e-9`, escape (`"\n"`), `r"\d+"`, f-string con qualsiasi espressione e formato (`{x:.2f}`),
  indici `x[-1]`, slice `x[:200]` e `x[::-1]`; dentro parentesi si va a capo (virgola finale ammessa). Tutti i metodi di str/list/dict e tutti i moduli
  Python (`import os`, `from x import y as z`, `os.listdir(cartella)`). Nomi anche con accenti.
- Funzioni già presenti: `print input len str int float bool list dict range enumerate zip sum min max sorted
  reversed abs round any all`, `write_file(p, testo)`, `append_file(p, testo)`, `sleep(s)` e:
  - `read_file(p, default)`, `http_get(url, default)`, `http_post(url, dati, default)` → testo;
    `json_parse(testo, default)` → liste e dizionari (non `type`); `env(nome, default)`. Se qualcosa va storto
    (file mancante, rete, risposta HTTP 4xx/5xx, indirizzo o JSON non validi, variabile assente) restituiscono
    `default`; senza `default` il programma si ferma con un errore chiaro. `http_post` invia `dati` come JSON.
    Gli URL non vengono codificati: per inserire un testo usa `urllib.parse.quote(testo)`.
  - `to_number(testo, default)` → int o float da testo (`"42"`, `"4,50"`, `"1.234,56"`), `default` se non lo è.
  - `json_dump(valore)` → JSON indentato con gli accenti, anche di `type` e liste di `type`. `now()` →
    `"2026-10-28T14:30:00"` (la data è `now()[:10]`). A fine input `input()` ferma il programma con un errore:
    per leggere più righe usa un terminatore (es. riga vuota). I percorsi sono relativi alla cartella da cui si esegue.

## Comportamento

- Ordine: `type`, `def` e `agent` vanno in qualsiasi ordine. Costanti e valori predefiniti dei parametri si
  calcolano subito, dall'alto in basso: usano solo costanti e funzioni scritte prima, mai agenti (neanche tramite
  una funzione). Una costante è qualsiasi espressione (`ANNUNCIO = "Ruolo: " + read_file("a.txt", "")`) e può
  fare da `instructions`; non si riassegna, ma liste e dizionari costanti si modificano (`LISTA.append(x)`).
  Le funzioni vedono tutte le costanti e gli import, ovunque siano scritti.
- `def`: tipi e `->` facoltativi; negli strumenti servono il tipo di ogni parametro e la descrizione.
- Tipi in campi, parametri e ritorni: `str int float bool dict list list[T]` e i `type`; la descrizione va dopo
  qualsiasi campo. Il runtime controlla i campi dei `type`, l'`output` degli agenti e gli argomenti che l'IA passa
  agli strumenti (un intero va bene per `float`); non controlla le chiamate del tuo codice né limiti come "da 1 a 5":
  scrivili nella descrizione e, se servono, verificali con un `if`. Le scelte con `|` sono solo testi; niente type
  ricorsivi. Gli oggetti, anche quelli restituiti dagli agenti, si modificano con il punto.
- `output` è il nome di un solo `type`: per una lista usa un type contenitore con un campo `list[Voce]`.
- Uno strumento può restituire qualsiasi valore: l'IA lo riceve come testo o JSON (date e simili diventano testo).
  Se va in errore, l'errore torna all'IA, che può riprovare. Un agente usato come strumento riceve un testo e
  restituisce la sua risposta (JSON se ha `output`); chi lo usa vede i primi 300 caratteri delle sue
  `instructions`, quindi scrivi all'inizio a cosa serve.
- `memory` ricorda domande e risposte finali (non i risultati degli strumenti) per tutta l'esecuzione. Ogni
  chiamata all'IA è un passaggio: `max_steps` (default 10) deve bastare per gli strumenti più la risposta finale,
  altrimenti il programma si ferma con un errore (se l'agente fa da strumento, l'errore torna a chi lo usa).
- In mock: testi `"esempio <campo>"`, numeri 1 e 1.0, dict vuoti, liste di 2 elementi; valori `"a" | "b"` e bool
  cambiano a ogni `ask` di quell'agente e da un elemento al successivo (si parte dal primo valore e da True).
  Senza `output` la risposta è `"[mock Nome] risposta a: ..."`.
- Con Claude Code (senza chiave API) `ask_all` fa le richieste una alla volta, perché la Batch API c'è solo con la
  chiave, e `max_steps` non si applica.
- `Agente.ask_all(testi)` dà le stesse risposte di un ciclo di `ask`, nello stesso ordine, ma con la Batch API:
  metà prezzo, più lento (di solito minuti, al massimo 24 ore), senza `memory`. Usalo per i lavori in blocco
  (classificare 100 email); per pochi testi o se servono subito usa un ciclo di `ask`. In mock è immediato. Se un
  testo resta senza risposta anche dopo un nuovo tentativo, il programma si ferma dicendo quale.
- Costi: `"claude-haiku"` per classificare o estrarre molti testi semplici, il default `"claude"` per il resto,
  `"claude-opus"` solo per compiti difficili; `effort: "low"` riduce i token di ragionamento. Istruzioni e
  strumenti restano in cache tra una chiamata e l'altra: tienili fissi e metti i dati che cambiano nel testo dell'`ask`.

## Non esistono

`while` (usa `for i in range(n):` con `break`), `class` (usa `type`/`agent`), `try`/`except` (usa i `default`),
`raise`/`assert` (usa `if` e `return`; uno strumento restituisce il messaggio d'errore come testo), `lambda` (usa
`def`), `def` annidate, `with`, `async`/`await`, `yield`, `global`, `del` (usa `.pop()`), `match`, comprehension
(usa `for` e `.append()`), `a if c else b` (usa `if`/`else`), `is` (usa `==`), tuple e set (usa liste),
`a, b = ...` e `return a, b` (usa una lista), campi facoltativi come `str | None` (usa `""`, `[]` o un valore
come `"nessuno"`). Dentro una f-string usa le virgolette dell'altro tipo: `f"{d['k']}"`. Gli agenti hanno solo
`.ask`, `.ask_all` e `.reset`. `True`, `False`, `None` con la maiuscola.
