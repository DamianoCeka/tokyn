<div align="center">

# Tokyn

**Un piccolo linguaggio con la sintassi di Python che Claude Code scrive al posto del Python quando un programma
usa Claude.<br>Circa un terzo del costo, programmi provati prima di arrivarti, Python normale alla fine.**

[![test](https://github.com/DamianoCeka/tokyn/actions/workflows/test.yml/badge.svg)](https://github.com/DamianoCeka/tokyn/actions/workflows/test.yml)
![Plugin per Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-2a78d6)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-2a78d6)
![Licenza MIT](https://img.shields.io/badge/licenza-MIT-2a78d6)

[English](README.md) · Italiano

</div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/DamianoCeka/tokyn/main/docs/grafici/numeri-it-dark.svg">
  <img alt="270 sessioni di Claude Code, 15 programmi Python che usano Claude, in tre modi. Costo di Tokyn rispetto al Python normale: −68% con Opus 5.5 e con Sonnet 5.5. Rispetto al Python con il Claude Agent SDK: −61% con Opus, −70% con Sonnet. Token di output rispetto al Python: −56% con Opus, −52% con Sonnet. Programmi che superano i test nascosti: Tokyn 89 su 90, Python 0 su 90 (senza chiave API non parte), Agent SDK 90 su 90." src="https://raw.githubusercontent.com/DamianoCeka/tokyn/main/docs/grafici/numeri-it-light.svg">
</picture>

Chiedi a Claude Code un programma che usa Claude: uno smistatore di email, un assistente clienti, un programma che
legge le fatture. Con il plugin Tokyn, Claude lo scrive in **Tokyn**, dove agenti, strumenti e risposte strutturate
fanno parte del linguaggio, quindi scrive molto meno codice. Il compilatore lo controlla, Claude lo prova con risposte
vere usando il tuo Claude Code e tu ricevi un normale file Python.

## Installa in Claude Code

```text
/plugin install tokyn --marketplace DamianoCeka/tokyn
```

Con Claude Code precedente alla 2.1.275 servono due comandi: `/plugin marketplace add DamianoCeka/tokyn`, poi
`/plugin install tokyn@tokyn`. La Skill in inglese è `tokyn-en@tokyn`. Il plugin contiene il compilatore e tutto
quello che serve: basta Python 3.10 o superiore.

## Come si usa

Chiedi il programma come sempre aggiungendo *"usa tokyn"*, oppure richiama la Skill con `/tokyn:tokyn`. Claude:

1. **scrive il programma in Tokyn**;
2. **lo controlla e lo prova gratis** con risposte finte (`--mock`), correggendo gli errori che il compilatore gli
   spiega riga per riga;
3. **lo prova con risposte vere** usando il tuo Claude Code mentre lo sviluppi, senza chiave API;
4. **ti dà il file Python**, generato dal compilatore con `tokyn build --standalone`. Quel codice non lo scrive il
   modello, quindi non costa token.

## Com'è un programma Tokyn

```
type Ticket:
    categoria: "tecnico" | "commerciale" | "altro"
    urgente: bool "True se il cliente è bloccato"

def cerca_faq(domanda: str) -> str:
    """Cerca una risposta nelle FAQ aziendali."""
    return read_file("faq.txt", "")

agent Supporto:
    instructions: "Rispondi ai clienti in italiano, in modo breve."
    tools: [cerca_faq]
    output: Ticket

main:
    t = Supporto.ask(input("Come posso aiutarti? "))
    if t.categoria == "tecnico" and t.urgente:
        print("Ti passo subito a un operatore.")
```

In Python lo stesso programma richiede il client dell'API, il ciclo delle chiamate agli strumenti, lo schema JSON, il
parsing e la validazione della risposta, i tentativi. In Tokyn è tutto dentro `Supporto.ask(...)`. La logica normale
non è più corta che in Python: il risparmio è nella parte che parla con il modello.

Quando qualcosa non va, il compilatore dice esattamente cosa correggere, così l'IA si corregge da sola:

```
supporto.tokyn:11:24 errore E133: lo strumento "prenota_appuntameto" non esiste
  11 |     tools: [cerca_faq, prenota_appuntameto]
     |                        ^^^^^^^^^^^^^^^^^^^
     → Forse intendevi "prenota_appuntamento"? Strumenti disponibili: cerca_faq, prenota_appuntamento
```

## I numeri

**Tutti i benchmark sono stati fatti con Claude di Anthropic** (Claude Code con Opus 5.5 e Sonnet 5.5). Tokyn
funziona anche con altri fornitori (vedi sotto), ma non li abbiamo misurati.

**Il metodo.** 15 richieste di programmi Python che usano Claude, fatte a Claude Code in tre modi:

- **con Tokyn**;
- **in Python normale**, come lo scrive di solito Claude Code;
- **in Python con il Claude Agent SDK**, che si può provare anche senza chiave API, tramite Claude Code.

Ogni richiesta è stata ripetuta 3 volte per modello: 270 sessioni nuove, in una cartella pulita e senza chiave API,
come per chi usa Claude Code con l'abbonamento. Ogni `programma.py` consegnato è stato poi eseguito su dati nascosti e
controllato in automatico.

Compiti, controlli, script e analisi sono stati [pubblicati prima delle prove](https://github.com/DamianoCeka/tokyn/commit/80ccedb).
Risultati completi, metodo e limiti sono in [`bench/claude-code/v2/`](bench/claude-code/v2).

| | Opus 5.5 | Sonnet 5.5 |
|---|---:|---:|
| **Costo, Tokyn rispetto al Python normale** | **−68%** (intervallo al 95% da −71% a −66%) | **−68%** (da −71% a −65%) |
| **Costo, Tokyn rispetto al Python + Agent SDK** | **−61%** (da −68% a −51%) | **−70%** (da −72% a −68%) |
| Token di output, Tokyn rispetto al Python normale | −56% | −52% |
| Tempo, Tokyn rispetto al Python normale | −23% | ±0% |
| Test nascosti superati: Tokyn / Python normale / Agent SDK | 45 · 0 · 45 su 45 | 44 · 0 · 45 su 45 |
| Costo di un'esecuzione del programma consegnato: Tokyn / Agent SDK | $0,008 / $0,036 | $0,008 / $0,037 |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/DamianoCeka/tokyn/main/docs/grafici/costo-opus-it-dark.svg">
  <img alt="Costo della sessione di Claude Code per programma con Opus 5.5, mediana di 3 ripetizioni: Tokyn costa meno del Python con l'Agent SDK in 14 programmi su 15, da −74% (moderazione) a −34% (promemoria contratti); costa di più solo per il log del server web (+23%), un compito con poca IA." src="https://raw.githubusercontent.com/DamianoCeka/tokyn/main/docs/grafici/costo-opus-it-light.svg">
</picture>

**Cosa dicono i numeri, e cosa no:**

- **Da dove viene il risparmio.** Senza Tokyn, Claude apre quasi sempre la Skill integrata `claude-api` di Claude Code
  per studiarsi l'API di Anthropic: 90 sessioni su 90 con il Python normale, 73 su 90 con l'Agent SDK. Costa molti
  token. Le poche sessioni con l'Agent SDK che non l'hanno aperta costano più o meno come Tokyn.
- **Il tempo non è un vantaggio sicuro.** Tokyn prova il programma con risposte vere, e questo richiede tempo: più
  veloce con Opus, uguale o un po' più lento con Sonnet.
- **Il Python normale non poteva girare.** Senza chiave API il programma scritto da Claude si è fermato
  all'autenticazione in tutte le 90 prove. Con una chiave Claude l'avrebbe provato, spendendo altri turni e token.
- **Tokyn perde dove c'è poca IA.** Nel compito sul log del server web, quasi tutto codice normale, con Opus l'Agent
  SDK è costato meno. Tokyn ha anche sbagliato un test nascosto (un report delle vendite, con Sonnet).
- **I compiti li ha progettati l'autore di Tokyn**, con agenti Claude e una revisione indipendente per evitare
  sbilanciamenti. I costi sono a prezzi di listino, come li riporta Claude Code.

Un benchmark precedente, più piccolo, contava i token del codice con un tokenizer vecchio: resta in [`bench/`](bench)
solo come storia. Le tornate in [`eval/`](eval) mostrano che Opus, Sonnet e Haiku scrivono Tokyn leggendo solo la
Skill: 80 programmi su 80 si sono compilati e hanno girato con risposte finte al primo tentativo.

## Chi risponde agli agenti

Quando il programma gira, ogni `Agente.ask(...)` è una richiesta a un modello. Tokyn sceglie chi risponde.

**Il tuo Claude Code, per provare i tuoi programmi.** Se manca `ANTHROPIC_API_KEY` e `claude` è installato, ogni
richiesta è una chiamata `claude -p` con il tuo login. Tokyn stampa un avviso la prima volta.

Le [regole di Anthropic per Claude Code](https://code.claude.com/docs/en/legal-and-compliance) dicono che
l'abbonamento serve all'uso normale e individuale: un prodotto, o un programma usato da altre persone, deve usare una
chiave API.

**L'API di Anthropic, con `ANTHROPIC_API_KEY`**, per i programmi che girano da soli o servono altre persone. Qui il
runtime risparmia da solo:

- prompt caching;
- output strutturati nativi;
- `Agente.ask_all(testi)` sulla Batch API a metà prezzo;
- `effort: "low"` per gli agenti che classificano o estraggono.

**Altri fornitori.** Scrivi `model: "openai:gpt-5.6-luna"`, `"gemini:gemini-3.8-flash"`, `"mistral:..."`,
`"deepseek:..."`, `"groq:..."`, `"openrouter:..."`, `"xai:..."`, `"ollama:qwen3.8"` (un modello locale e gratuito)
oppure `"openai-compatible:..."` per qualsiasi server compatibile. Ognuno usa la sua chiave, per esempio
`OPENAI_API_KEY`.

- Strumenti, output strutturati, memoria e tentativi funzionano come con Claude.
- Questo adattatore è provato con un server finto, non ancora con i servizi veri.
- La prova senza chiave funziona solo con Claude, tramite Claude Code, oppure con Ollama sul tuo computer.

`tokyn run file.tokyn --backend claude-code` (o `api`) forza la scelta, e `--usage` mostra i token spesi.

## Il confronto

| | Tokyn | [BAML](https://github.com/BoundaryML/baml) | [Pydantic AI](https://github.com/pydantic/pydantic-ai) | SDK Python di Anthropic | Claude Agent SDK |
|---|---|---|---|---|---|
| **Cosa scrivi** | `.tokyn` (sintassi Python) | file `.baml` | Python | Python | Python |
| **Cosa consegni** | Un file Python. Gli serve `anthropic` o il comando `claude`, o solo HTTP per gli altri fornitori | Client Python/TypeScript generati, o un eseguibile | Python | Python | Python |
| **Output strutturato** | `type` + `output:` | Classi; un parser che corregge il testo del modello | `output_type=ModelloPydantic` | `messages.parse(...)` | Schema JSON, da validare a mano |
| **Modelli** | Claude; fornitori compatibili con OpenAI | Molti | Circa 30 fornitori | Solo Claude | Solo Claude |
| **Controllo prima di eseguire** | Compilatore con 63 codici d'errore e correzioni; `--mock` | Compilatore, estensione per l'editor, `baml test` | Type checker; `TestModel` per girare senza modello | Type checker | Type checker |
| **Fatto perché lo scriva Claude Code** | Sì: Skill, errori che dicono la correzione | Sì: `baml agent install` aggiunge una skill | No | La sua documentazione è una Skill integrata di Claude Code | No |
| **Maturità** | Nuovo (0.1) | Circa 9.500 stelle, v1 in beta pubblica | Circa 20.900 stelle | Ufficiale | Ufficiale |

Stelle al 29 ottobre 2026. Pydantic AI e BAML sono più maturi e supportano più fornitori. La scommessa di Tokyn è più
stretta: il modo più economico perché Claude Code scriva, controlli e provi un programma che usa Claude.

## Domande frequenti

**Perché un linguaggio e non una libreria?** Con una libreria il modello deve comunque scrivere il codice di contorno
e conoscerne l'API. In Tokyn le dichiarazioni sono tutto il programma, e il compilatore può spiegare a Claude gli
errori proprio in base a quelle dichiarazioni. Un buon framework come Pydantic AI si avvicina come lunghezza del
codice; la differenza nel benchmark viene dalla sessione nel suo insieme.

**Il modello non ha mai visto Tokyn: non sbaglia?** La sintassi è quella di Python e la Skill (circa 3.000 token
quella inglese) insegna il resto; il compilatore spiega ogni errore prima che il programma giri. Nel benchmark Claude
ha usato la Skill in tutte le sessioni con Tokyn e 89 programmi su 90 hanno superato i test nascosti.

**Resto legato a Tokyn?** No. `tokyn build --standalone` ti dà un file Python normale, che puoi tenere e modificare
senza Tokyn.

**Tokyn manda dati da qualche parte?** Il compilatore gira in locale. Gli agenti chiamano il modello che scegli (il tuo
Claude Code, l'API di Anthropic o il fornitore indicato in `model`) e il tuo programma chiama gli indirizzi che usa.
Non c'è telemetria.

## Il linguaggio in breve

- **`agent`**: modello, istruzioni, strumenti, memoria, output strutturato, `effort`. Si usa con `Agente.ask(testo)`
  o, per tanti testi, `Agente.ask_all(testi)`.
- **`def`**: funzioni normali, che diventano strumenti quando le metti nei `tools` di un agente; gli argomenti che
  arrivano dall'IA vengono controllati con i tipi.
- **`type`**: dati strutturati, anche annidati, con valori ammessi (`"a" | "b"`) e descrizioni per l'IA.
- **Agenti come strumenti**: un agente può delegare a un altro.
- **Python ovunque**: `import` di qualsiasi libreria, slice, f-string, metodi di testi, liste e dizionari.
- **Valori di riserva al posto di `try`**: `read_file(p, "")`, `http_get(url, "")` e `to_number(testo, 0)` non fermano
  il programma se il file manca, la rete cade o il numero non è valido.
- **Errori pensati per l'IA**, in italiano o in inglese: alla riga del file `.tokyn`, con la correzione. Se un modello
  scrive per abitudine una comprehension, `a if c else b` o `is None`, il compilatore dice cosa scrivere al loro posto.

La specifica completa è [`tokyn/SPEC.md`](tokyn/SPEC.md), gli esempi sono in [`examples/`](examples).

## Da terminale

```bash
pip install git+https://github.com/DamianoCeka/tokyn
```

```bash
tokyn new primo                       # crea primo.tokyn
tokyn check primo.tokyn               # controlla e spiega gli errori
tokyn run primo.tokyn --mock          # prova senza chiamare l'IA (gratis)
tokyn run primo.tokyn --usage         # esegue davvero (Claude Code o una chiave API)
tokyn build primo.tokyn --standalone  # genera un file Python che non richiede Tokyn
tokyn spec                            # stampa la specifica
```

I messaggi sono in italiano o in inglese: `--lang it|en` o `TOKYN_LANG`.

## Come funziona

```
file.tokyn → parser (Lark) → checker (tipi, nomi, agenti) → generatore → Python → runtime (Claude o altri fornitori)
```

- `tokyn/grammar.lark`: la grammatica
- `tokyn/checker.py`: i controlli e i messaggi d'errore
- `tokyn/codegen.py`: la traduzione in Python
- `tokyn/runtime.py`: agenti, ciclo degli strumenti, validazione, API di Anthropic, Claude Code, altri fornitori
- `plugins/`: i plugin per Claude Code; `scripts/build_skill.py` ci copia il compilatore

I grafici di questa pagina si rigenerano dai dati con `python scripts/make_charts.py`.

## Dove sta andando

<table>
<tr>
<td width="50%" valign="top">

**Agenti in squadra**<br>
Più agenti al lavoro nello stesso momento, che si dividono un compito e si passano i risultati. Oggi un agente
può già delegare a un altro: il prossimo passo è farli lavorare in parallelo.

</td>
<td width="50%" valign="top">

**Anche in TypeScript**<br>
Lo stesso programma Tokyn compilato anche per Node e per il web: lo scrivi una volta e lo usi dove ti serve.

</td>
</tr>
<tr>
<td width="50%" valign="top">

**Da programma a servizio, con un comando**<br>
`tokyn serve`: l'agente che hai appena provato diventa un'API o un bot, pronto da mettere online.

</td>
<td width="50%" valign="top">

**Errori mentre scrivi**<br>
Un'estensione per VS Code con i colori di Tokyn e gli stessi errori che oggi guidano Claude, in tempo reale.

</td>
</tr>
</table>

## Licenza

MIT. Tokyn è scritto da Damiano Ceka con molto aiuto di Claude, che ha scritto buona parte del codice.
