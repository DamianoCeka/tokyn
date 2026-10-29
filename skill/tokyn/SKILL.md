---
name: tokyn
description: Scrive agenti IA, chatbot e automazioni con LLM nel linguaggio Tokyn (file .tokyn), che richiede molti meno token del Python equivalente, e li controlla ed esegue con il compilatore incluso. Usala quando l'utente chiede un agente IA, un bot, un'estrazione o classificazione di testi con IA o un'automazione con Claude, quando nomina Tokyn, o quando nel progetto ci sono file .tokyn. Non usarla se l'utente chiede un altro linguaggio o framework (SDK Anthropic, LangChain, TypeScript…) o se il codice va dentro un progetto esistente scritto in un altro linguaggio.
---

# Tokyn

Linguaggio con la sintassi di Python in cui agenti, strumenti e output strutturati fanno parte
del linguaggio: ciclo degli strumenti, schema JSON, validazione e retry li fa il runtime.
Tutto quello che serve per scriverlo è in questo file; `<skill>/SPEC.md` (dove `<skill>` è la
cartella di questo file) serve solo per dettagli rari.

## Procedura

1. Scrivi il programma in un file `.tokyn` seguendo il riferimento qui sotto.
2. Controlla e prova in un solo comando, gratis (risposte finte, nessuna chiamata all'IA):
   `python <skill>/tokyn_cli.py run file.tokyn --mock`
   - Se ci sono errori, li elenca con riga, colonna e correzione (`→`) e non esegue nulla.
     Correggi con modifiche puntuali, senza riscrivere il file, e ripeti finché gira.
   - Se il programma usa `input()`, passa le risposte una per riga:
     `printf 'ciao\nesci\n' | python <skill>/tokyn_cli.py run file.tokyn --mock`
   - In mock gli agenti non chiamano gli strumenti; `write_file`, `http_post` ecc. invece vengono eseguiti davvero.
3. Esecuzione reale: `python <skill>/tokyn_cli.py run file.tokyn` (serve `ANTHROPIC_API_KEY`; se manca, fermati al passo 2).
4. Se l'utente vuole Python: `python <skill>/tokyn_cli.py build file.tokyn --standalone -o file.py`
   (file autonomo, serve solo `pip install anthropic`). Non scrivere il Python a mano.

Se il comando dice che manca `lark`: `pip install lark anthropic` (con `--break-system-packages` se pip lo chiede).

Per l'utente: `pip install git+https://github.com/DamianoCeka/tokyn`, poi `tokyn run file.tokyn`
con `ANTHROPIC_API_KEY` impostata.

## Riferimento del linguaggio

```
import math                                    # qualsiasi libreria Python: import x / from x import y
SOGLIA = 3                                     # costante globale: non si può riassegnare

type Riga:                                     # dati strutturati; tutti i campi sono obbligatori
    prodotto: str
    prezzo: float "prezzo unitario in euro"    # stringa dopo il tipo = descrizione per l'IA

type Ticket:
    categoria: "tecnico" | "commerciale" | "altro"   # solo uno di questi valori
    urgente: bool
    righe: list[Riga]                          # tipi: str int float bool dict list[T] o un altro type

def cerca_faq(domanda: str) -> str:
    """Cerca una risposta nelle FAQ aziendali."""   # strumento: tipi dei parametri e descrizione obbligatori
    return read_file("faq.txt")

agent Tecnico:
    instructions: "Risolvi problemi tecnici."

agent Supporto:
    model: "claude"                            # default "claude"; anche "claude-opus", "claude-haiku", "mock" o un id
    instructions: """
        Rispondi ai clienti in italiano.
    """                                        # obbligatorio: testo, testo su più righe o costante
    tools: [cerca_faq, Tecnico]                # funzioni def o altri agenti a cui delegare
    output: Ticket                             # facoltativo: risposta strutturata invece di str
    memory: True                               # facoltativo (default False): ricorda tra una ask e l'altra
    max_steps: 10                              # facoltativo: passaggi massimi per ogni ask

def per_prezzo(r: Riga) -> float:
    return r.prezzo

main:                                          # punto di partenza, uno solo
    t = Supporto.ask(input("> "))              # un solo argomento; restituisce str o il type di output
    if t.categoria == "tecnico" and t.urgente:
        righe = sorted(t.righe, key=per_prezzo, reverse=True)   # ordinare per campo: def + key=
        for i, r in enumerate(righe[:SOGLIA]):
            print(f"{i + 1}. {r.prodotto}: {r.prezzo:.2f} €")
    elif t.categoria not in ["commerciale"]:
        print(json_dump(t))
    Supporto.reset()                           # cancella la memoria
    nuovo = Ticket(categoria="altro", urgente=False, righe=[])  # costruttore con i nomi dei campi
    nuovo.urgente = True
```

- Istruzioni: `=`, `+=`, `-=`, `*=`, `/=`, `if`/`elif`/`else`, `for x in ...` (anche `for k, v in d.items()`),
  `break`, `continue`, `return`, `pass`. Espressioni, f-string, indici `x[-1]`, slice `x[:200]` e metodi di
  str/list/dict come in Python. Campi dei `type` con il punto (`t.campo`), chiavi dei dizionari con `d["k"]`.
- Funzioni già presenti: `print input len str int float bool list dict range enumerate zip sum min max sorted
  reversed abs round any all`, `read_file(p)`, `write_file(p, testo)`, `append_file(p, testo)`, `http_get(url)`,
  `http_post(url, dati)`, `json_parse(testo)`, `json_dump(valore)`, `env(nome, default)`, `now()`, `sleep(s)`.
- Se uno strumento va in errore, l'errore torna all'IA, che può riprovare. Il valore restituito arriva all'IA come testo o JSON.

## Non esistono

`while` (usa `for i in range(n):` con `break`), `class` (usa `type`/`agent`), `try`/`except`, `lambda` (usa `def`),
`with`, `async`/`await`, `yield`, `global`, `match`, comprehension (usa `for` e `.append()`), `a if c else b`
(usa `if`/`else`), `is` (usa `==`), `a, b = ...` e `return a, b` (usa una lista), campi facoltativi come
`str | None` (usa `""`, `[]` o un valore come `"nessuno"`). Dentro una f-string usa le virgolette dell'altro
tipo: `f"{d['k']}"`. Gli agenti hanno solo `.ask` e `.reset`. `True`, `False`, `None` con la maiuscola.
