# Tokyn per Claude Code

Tokyn è un piccolo linguaggio di programmazione con la sintassi di Python per i programmi che usano Claude.
Agenti, strumenti e output strutturati fanno parte del linguaggio: il ciclo degli strumenti, gli schemi JSON, la
validazione delle risposte, i retry e il prompt caching li gestisce il runtime. Così, quando chiedi a Claude Code
uno di questi programmi, Claude scrive molto meno codice, e spende meno token, che in Python.

Questo plugin aggiunge una Skill, `tokyn`, insieme al compilatore di Tokyn. Con la Skill Claude scrive il programma
in Tokyn, lo controlla, lo prova e, se vuoi Python, ti consegna il file Python generato dal compilatore. I messaggi
del compilatore sono in italiano; il plugin
[`tokyn-en`](https://github.com/DamianoCeka/tokyn/tree/main/plugins/tokyn-en) è la stessa Skill in inglese.

## Quando usarlo

Per i programmi che chiamano Claude:

- agenti IA, anche con strumenti (funzioni Python scritte da te) o altri agenti a cui delegare;
- chatbot e assistenti, nel terminale o dentro il tuo codice;
- estrazione di dati strutturati dai testi (fatture, email, moduli) e classificazione (ticket, recensioni);
- lavori in blocco su molti testi, con la Batch API a metà prezzo.

Non usarlo per programmi senza IA, quando vuoi un framework preciso (l'SDK di Anthropic, LangChain…) o quando il
codice va in un progetto scritto in un linguaggio diverso da Python: Tokyn compila solo in Python.

Claude usa la Skill da solo quando chiedi un programma che usa Claude o agenti IA, quando nomini Tokyn o quando nel
progetto ci sono già file `.tokyn`; per chiederla esplicitamente aggiungi "usa tokyn" alla richiesta. Puoi anche
richiamarla con `/tokyn:tokyn`.

## Installazione

In una sessione di Claude Code:

```text
/plugin marketplace add DamianoCeka/tokyn
/plugin install tokyn@tokyn
```

## Requisiti

- **Python 3.10 o superiore.** Per scrivere, controllare e provare i programmi con risposte finte non serve
  nessun `pip install`: il compilatore e la libreria di parsing che usa ([lark](https://github.com/lark-parser/lark),
  licenza MIT) sono dentro il plugin.
- **Per avere risposte vere dagli agenti**, una di queste due cose:
  - il tuo **login di Claude Code**, per provare i programmi mentre li sviluppi (il comando `claude` deve essere nel
    `PATH`; nessuna chiave API);
  - una **chiave dell'API di Anthropic** in `ANTHROPIC_API_KEY`, più l'SDK: `pip install "anthropic>=0.108"`. È la
    strada per i programmi che girano da soli o per altre persone (vedi [la regola qui sotto](#login-di-claude-code-o-chiave-api)).

## Esempi di richieste

- *Scrivimi uno script Python che legge `recensioni.txt` e per ogni recensione dà il sentimento e un voto da 1 a 5,
  poi stampa la media dei voti. Provalo davvero e dammi anche il file Python. Usa tokyn.*
- *Fammi un assistente clienti da terminale che cerca le risposte in `faq.txt` con uno strumento e ricorda la
  conversazione. Usa tokyn.*
- *Estrai fornitore, data, righe e totale da `fattura.txt`, ricalcola il totale dalle righe e dimmi se torna.
  Usa tokyn.*
- *Smista le email dei clienti nella cartella `posta/` in tecnico, commerciale e altro, con il modello più economico,
  e scrivi il risultato in `smistate.json`. Usa tokyn.*

## Come funziona

1. **Claude scrive il programma in un file `.tokyn`** nel tuo progetto. Per esempio:

   ```
   type Ticket:
       categoria: "tecnico" | "commerciale" | "altro"
       urgente: bool "True se il cliente non può lavorare"

   agent Smistatore:
       model: "claude-haiku"
       instructions: "Classifica la richiesta del cliente."
       output: Ticket

   main:
       t = Smistatore.ask(input("Come posso aiutarti? "))
       print(t.categoria, t.urgente)
   ```

2. **Lo controlla e lo prova gratis**, con risposte finte:
   `python <cartella della skill>/tokyn_cli.py run file.tokyn --mock`. Gli errori arrivano con riga, colonna e
   correzione, e Claude li corregge finché il programma gira.
3. **Lo esegue con risposte vere** (`run file.tokyn --usage`, che alla fine mostra anche i token spesi): con il tuo
   Claude Code se non c'è una chiave API, con l'API di Anthropic se c'è `ANTHROPIC_API_KEY`. Se il programma fa
   molte chiamate, Claude ti avvisa prima.
4. **Se vuoi Python, ti consegna il file generato dal compilatore**: `build file.tokyn --standalone -o file.py`.
   È un file unico che non richiede Tokyn (con la chiave API gli basta `pip install anthropic`). Il file `.tokyn`
   resta accanto come sorgente da modificare.

## Cosa esegue e cosa invia questo plugin

**Cosa contiene.** Le istruzioni della Skill (`SKILL.md`), il compilatore e il runtime di Tokyn come sorgenti
Python, con la specifica del linguaggio (`skills/tokyn/tokyn/`), un lanciatore (`skills/tokyn/tokyn_cli.py`), una
copia non modificata di lark 1.3.1 (`skills/tokyn/vendor/lark/`, usata solo se lark non è installato), la licenza e
l'icona. Non ci sono hook, server MCP, comandi, agenti o programmi binari: installare il plugin o aprire una
sessione non esegue nulla.

**Cosa esegue.** Claude avvia il lanciatore con il suo strumento Bash (`python …/tokyn_cli.py check`, `run` o
`build`), quindi ogni comando passa dai permessi che hai impostato in Claude Code. `check` e `build` leggono solo il
tuo file `.tokyn` e, nel caso di `build`, scrivono il file `.py`. `run` compila il programma e lo esegue in un
processo Python locale, con i permessi del tuo utente.

**Cosa invia quando rispondono gli agenti.** Con `--mock`, niente. Altrimenti, per ogni domanda, ad Anthropic
arrivano le instructions dell'agente, la domanda, i turni precedenti se l'agente ha `memory: True`, la descrizione
dei suoi strumenti e i loro risultati, e il formato della risposta, in uno di due modi:

- **Senza chiave API, con il tuo Claude Code.** Tokyn avvia `claude -p` con il tuo login. Per quella chiamata
  spegne gli strumenti di Claude Code, i file di impostazioni, i comandi slash e gli altri server MCP, e la sessione
  non viene salvata. Se l'agente ha strumenti, Tokyn scrive un piccolo script ponte MCP in una cartella temporanea
  (cancellata dopo la chiamata) e ascolta su una porta casuale di `127.0.0.1`, protetta da un token casuale, così
  gli strumenti girano dentro il tuo programma.
- **Con `ANTHROPIC_API_KEY`, con l'API di Anthropic**, tramite l'SDK Python ufficiale `anthropic`: la Messages API,
  la Message Batches API per `ask_all` e, sui modelli che lo prevedono, la beta dei fallback lato server (se un
  modello rifiuta, l'API riprova su un altro).

**Cosa fanno i tuoi programmi.** I programmi che scrive Claude sono programmi normali. `read_file`, `write_file` e
`append_file` usano i tuoi file, `http_get` e `http_post` chiamano gli indirizzi scritti nel programma, `env` legge
le variabili d'ambiente e con `import` si usa qualsiasi modulo Python. Tutto questo succede davvero anche con
`--mock`: quando un programma scrive file o chiama indirizzi web, leggilo prima di eseguirlo.

**Nient'altro.** Tokyn non ha telemetria né statistiche d'uso, non cerca aggiornamenti, non scarica nulla e non
installa mai pacchetti.

## Login di Claude Code o chiave API

La [pagina legale di Claude Code](https://code.claude.com/docs/en/legal-and-compliance) dice che l'accesso con un
abbonamento Claude serve all'uso normale di Claude Code, e che chi sviluppa prodotti o servizi che usano Claude
dovrebbe usare una chiave API della [Claude Console](https://platform.claude.com/) o di un fornitore cloud
supportato. Anthropic non permette di far passare dalle credenziali di un piano Free, Pro o Max le richieste fatte
per conto di altre persone, e i limiti d'uso dei piani Pro e Max presuppongono un uso normale e individuale.

In pratica:

- **Provare i tuoi programmi con il tuo Claude Code mentre li sviluppi va bene.**
- **Un prodotto, o un programma usato da altre persone** (un bot, un servizio web), **deve usare
  `ANTHROPIC_API_KEY`**: Anthropic non permette di farlo passare dal tuo abbonamento.
- **Per un programma tuo che gira da solo** (su un server, come lavoro pianificato) consigliamo comunque la chiave
  API: i limiti dei piani sono pensati per un uso normale e individuale di Claude Code.

Quando Tokyn sceglie da solo Claude Code, perché manca la chiave API, stampa una volta questo avviso:

```text
Tokyn: senza chiave API gli agenti rispondono con il tuo Claude Code e usano il tuo abbonamento. Va bene per provare
i tuoi programmi; un prodotto o un programma usato da altre persone deve usare una chiave dell'API di Anthropic
(https://code.claude.com/docs/en/legal-and-compliance).
```

Se c'è `ANTHROPIC_API_KEY`, Tokyn usa l'API. Puoi anche scegliere tu con `--backend api` o `--backend claude-code`
(oppure con la variabile `TOKYN_BACKEND`).

## Problemi frequenti

- **`python: command not found`.** Installa Python 3.10 o superiore; dove c'è solo `python3`, gli stessi comandi
  funzionano con `python3`.
- **"manca la chiave ANTHROPIC_API_KEY".** Non c'è una chiave API e il comando `claude` non è stato trovato (oppure
  hai scelto `--backend api`). Imposta la chiave, oppure installa Claude Code e fai il login, oppure prova il
  programma con `--mock`.
- **"Claude Code non ha risposto per l'agente …".** Apri `claude` una volta e completa il login, poi riprova.
- **"manca il pacchetto anthropic" o "è troppo vecchio".** Serve solo con la chiave API:
  `pip install -U "anthropic>=0.108"`.
- **"l'agente … non ha finito entro 10 passaggi".** All'agente servivano più chiamate agli strumenti: aumenta
  `max_steps` nell'agente o rendi più precise le sue instructions.
- **"input() non ha ricevuto una riga".** Il programma legge dalla tastiera: passa le risposte una per riga, per
  esempio `printf 'ciao\nesci\n' | python …/tokyn_cli.py run file.tokyn --mock`.
- **`ask_all` impiega minuti.** Usa la Batch API: costa la metà, ma di solito ci vogliono minuti e al massimo 24
  ore. Per pochi testi, o se ti servono subito le risposte, usa un ciclo di `ask`. Con Claude Code, `ask_all` invia
  i testi uno alla volta.
- **Messaggi in inglese.** Questo plugin scrive i messaggi in italiano, a meno che non sia impostato
  `TOKYN_LANG=en`: togli la variabile, oppure imposta `TOKYN_LANG=it`.

## Licenza e link

Tokyn è distribuito con [licenza MIT](https://github.com/DamianoCeka/tokyn/blob/main/LICENSE). La copia di lark
in `skills/tokyn/vendor/lark/` mantiene la sua licenza MIT.

- Codice sorgente e documentazione: <https://github.com/DamianoCeka/tokyn>
- Specifica completa del linguaggio, anche in questo plugin in `skills/tokyn/tokyn/SPEC.md`:
  <https://github.com/DamianoCeka/tokyn/blob/main/tokyn/SPEC.md>
- Problemi e domande: <https://github.com/DamianoCeka/tokyn/issues>
