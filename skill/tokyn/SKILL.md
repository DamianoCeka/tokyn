---
name: tokyn
description: Costruisce agenti IA, bot e automazioni con LLM scrivendoli nel linguaggio Tokyn (file .tokyn) invece che in Python, usando molti meno token. Usala quando l'utente chiede un agente IA, un chatbot, un'estrazione o classificazione con IA, un'automazione con Claude, o quando nel progetto ci sono file .tokyn.
---

# Tokyn

Tokyn è un linguaggio con la sintassi di Python, ma con agenti, strumenti e output
strutturati già dentro il linguaggio. Lo stesso programma richiede molto meno codice
(e quindi meno token) che in Python. Il compilatore lo traduce in Python normale,
quindi il risultato funziona ovunque e può usare qualsiasi libreria Python.

## Quando usarla

Usa Tokyn per programmi in cui uno o più modelli IA fanno il lavoro: classificare,
estrarre dati, rispondere con strumenti, coordinare più agenti. Per codice senza IA
usa il linguaggio normale del progetto.

## Preparazione (una volta per sessione)

Questa cartella contiene il compilatore (`tokyn/`). Serve solo la libreria `lark`:

```bash
pip install lark anthropic        # se mancano (aggiungi --break-system-packages se richiesto)
export PYTHONPATH="<cartella di questa skill>:$PYTHONPATH"
python -m tokyn --version
```

Se è installato il pacchetto (`pip install git+https://github.com/DamianoCeka/tokyn`), puoi usare direttamente il comando `tokyn`.

## Procedura

1. Leggi `SPEC.md` in questa cartella, se non conosci già il linguaggio.
2. Scrivi il programma in un file `.tokyn`.
3. Esegui `python -m tokyn check --json file.tokyn`. Per ogni errore leggi `message`
   e `hint` e correggi. Ripeti finché `ok` è `true`. Non saltare questo passo.
4. Prova senza costi con `python -m tokyn run file.tokyn --mock`.
5. Esegui davvero con `python -m tokyn run file.tokyn` (serve `ANTHROPIC_API_KEY`).
6. Se l'utente vuole un file Python, genera `python -m tokyn build file.tokyn -o file.py`:
   non riscrivere tu il Python a mano, perché costerebbe i token che Tokyn fa risparmiare.

## Promemoria rapido

```
type Ticket:
    categoria: "tecnico" | "altro"
    urgente: bool "True se il cliente è bloccato"

def cerca_faq(domanda: str) -> str:
    """Cerca una risposta nelle FAQ."""
    return "..."

agent Supporto:
    model: "claude"
    instructions: "Rispondi in italiano."
    tools: [cerca_faq]
    output: Ticket

main:
    t = Supporto.ask(input("> "))
    if t.urgente:
        print(t.categoria)
```

- Campi agente con `:`, non con `=`. `instructions` è obbligatorio.
- Un agente si usa solo con `.ask(testo)` e `.reset()`. Il ciclo degli strumenti, i retry e la validazione dell'output li fa il runtime.
- Le funzioni nei `tools` hanno il tipo di ogni parametro e una descrizione come prima riga.
- Niente `while`, `class`, `try`, `lambda`, `with`, `async`: per i cicli usa `for x in ...` o `for i in range(n)` con `break`.
- `True`, `False`, `None` con la maiuscola. Le costanti in cima al file non si modificano.
