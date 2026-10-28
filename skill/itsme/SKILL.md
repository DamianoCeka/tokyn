---
name: itsme
description: Scrive, corregge ed esegue programmi nel linguaggio Itsme (file .itsme) per costruire agenti IA. Usala quando l'utente chiede un agente, un bot o un'automazione con IA in Itsme, o quando nel progetto ci sono file .itsme.
---

# Itsme

Itsme è un linguaggio con sintassi Python e con agenti, strumenti e output strutturati
già dentro il linguaggio. La specifica completa si ottiene con `itsme spec`.

## Procedura

1. Se `itsme` non è installato: `pip install git+https://github.com/DamianoCeka/itsme-lang`.
2. Leggi la specifica con `itsme spec` prima di scrivere codice, se non la conosci già.
3. Scrivi il programma in un file `.itsme`.
4. Esegui `itsme check --json file.itsme`. Per ogni errore leggi `message` e `hint`
   e correggi. Ripeti finché `ok` è `true`. Non saltare questo passo.
5. Prova senza costi con `itsme run file.itsme --mock`.
6. Esegui davvero con `itsme run file.itsme` (serve `ANTHROPIC_API_KEY`).

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
- Un agente si usa solo con `.ask(testo)` e `.reset()`.
- Le funzioni nei `tools` hanno il tipo di ogni parametro e una descrizione come prima riga.
- Niente `while`, `class`, `try`, `lambda`, `with`, `async`: per i cicli usa `for x in ...` o `for i in range(n)`.
- `True`, `False`, `None` con la maiuscola. Le costanti in cima al file non si modificano.
