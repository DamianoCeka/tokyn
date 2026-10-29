# Benchmark v2: Tokyn in Claude Code, protocollo

Questo file è stato scritto e pubblicato **prima** di eseguire le prove: la storia del repository lo dimostra.
I risultati si pubblicano tutti, anche quelli sfavorevoli a Tokyn.

## La domanda

In Claude Code chiedi un programma Python che usa Claude. Quanto costa la sessione, quanto dura e quanto spesso il
programma consegnato funziona davvero, se Claude lo scrive:

- **tokyn**: con il plugin Tokyn. Claude scrive il programma in Tokyn, lo prova e consegna il Python generato.
- **python**: con Claude Code normale, che sceglie da solo come scriverlo.
- **agent-sdk**: in Python con il Claude Agent SDK. Funziona con il login di Claude Code, quindi anche qui Claude
  può provare il programma senza chiave API. È il confronto più severo per Tokyn.

## I compiti

15 compiti decisi prima, in [`compiti/`](compiti). Tre sono quasi tutto codice normale con poca IA (`log`,
`vendite`, `scadenze`): lì ci aspettiamo che Tokyn abbia poco vantaggio, ed è giusto misurarlo.

| Compito | Cosa fa il programma |
|---|---|
| `recensioni` | sentimento e voto di ogni recensione, poi la media |
| `assistente` | assistente clienti da terminale che risponde con le FAQ e ricorda la conversazione |
| `fattura` | estrae i dati di una fattura, ricalcola il totale e dice se quello dichiarato è giusto |
| `email` | smista le email di una cartella: categoria, urgenza, riassunto |
| `catalogo` | traduce in inglese le descrizioni di un catalogo CSV lasciando invariato il resto |
| `riunione` | dal verbale di una riunione: decisioni e azioni con responsabile e scadenza |
| `documenti` | risponde a domande su una cartella di documenti indicando il file da cui viene la risposta |
| `moderazione` | modera i commenti di un forum e riscrive in modo cortese quelli da rivedere |
| `spese` | categorizza i movimenti di un estratto conto e somma gli importi per categoria |
| `candidati` | valuta dei CV rispetto a un annuncio di lavoro e li mette in classifica |
| `magazzino` | risponde a domande sull'inventario con numeri esatti |
| `articolo` | titolo, cinque punti chiave e persone e organizzazioni citate in un articolo |
| `log` | statistiche esatte di un log di un server web, più un commento scritto dall'IA |
| `vendite` | fatturato per paese e migliori clienti da due CSV, più un riassunto per la direzione |
| `scadenze` | contratti in scadenza entro 30 giorni da una data, con un'email di promemoria per ognuno |

Ogni compito ha:

- `richiesta.md`: la richiesta, identica nelle tre condizioni, scritta come la scriverebbe chi programma. Dice cosa
  deve fare il programma e il formato del risultato, non come scriverlo.
- `dati/`: i dati di esempio che Claude vede.
- `verifica/`: i dati nascosti e il controllo automatico. Il controllo è stato validato con tre programmi:
  - uno che dà la risposta giusta senza IA, e deve essere promosso;
  - uno con un errore plausibile, e deve essere bocciato;
  - una soluzione semplice con l'IA vera, che deve essere promossa (così i dati nascosti non sono ambigui).

I compiti li hanno scritti agenti Claude, guidati da chi sviluppa Tokyn, e un secondo agente li ha rivisti cercando
richieste sbilanciate e controlli ingiusti. Il conflitto d'interesse resta: per questo è tutto pubblico e si può
rifare con un comando.

## La sessione

Il messaggio è `richiesta.md`, più "Provalo davvero prima di consegnarmelo.", più la frase della condizione:

- tokyn: "Usa la skill tokyn."
- python: niente;
- agent-sdk: "Usa il Claude Agent SDK (il pacchetto Python `claude-agent-sdk`, già installato)."

```bash
claude -p "<messaggio>" --model opus|sonnet --output-format stream-json --verbose --no-session-persistence \
  --setting-sources "" --strict-mcp-config --tools Bash,Read,Write,Edit,Glob,Grep,Skill \
  --allowedTools "Bash Read Write Edit Glob Grep Skill" [--plugin-dir plugin-tokyn]
```

Condizioni uguali per tutti:

- nessuna chiave API, come chi usa Claude Code con l'abbonamento;
- gli stessi strumenti;
- nessuna impostazione dell'utente o del progetto;
- lo sforzo predefinito del modello;
- le skill integrate di Claude Code, per esempio `claude-api`.

Ogni sessione è nuova e gira in una cartella dal nome neutro che contiene solo i dati del compito, con una `/tmp`
tutta sua. Il plugin Tokyn è quello di un commit preciso, preso con `git archive`; il commit e l'impronta sono in
`risultati/versioni.json` e in ogni prova.

## Ripetizioni, modelli, ordine

3 ripetizioni × 15 compiti × 3 condizioni × 2 modelli (Opus 5.5 e Sonnet 5.5) = **270 sessioni**. Prima Opus, poi
Sonnet. Per ogni modello l'ordine è mescolato con un seme fisso, così le condizioni si alternano nel tempo. Le
sessioni girano 4 alla volta. Lo script è [`esegui.py`](esegui.py).

## Le misure

Per ogni sessione:

- **Costo totale**, la misura principale. È la somma di due parti:
  - il costo della sessione riportato da Claude Code (`total_cost_usd`, a prezzi API);
  - il costo delle chiamate all'IA che il programma fa quando Claude lo prova. Queste le misura la telemetria
    OpenTelemetry di Claude Code, raccolta in locale; si tengono solo costi e token, nessun dato dell'account.
    Claude Code toglie le variabili `OTEL_*` ai comandi che lancia, quindi un piccolo script davanti a `claude` le
    rimette e avvia lo stesso `claude` di prima. Lo script sta sia nel `PATH` sia al posto della copia di `claude`
    dentro l'Agent SDK; il comportamento non cambia.
- Token di output, turni e tempo della sessione.
- Se `programma.py` è stato consegnato, e le sue righe di codice.
- **Controllo automatico**: `programma.py` gira sui dati nascosti in una cartella pulita, senza chiave API.
  - L'esito è promosso o bocciato, con i punti.
  - Si misura anche il costo dell'IA durante il controllo, cioè quanto costa far girare una volta il programma
    consegnato.
- **Provato con l'IA vera**: il programma ha fatto almeno una chiamata vera all'IA durante la sessione, secondo la
  telemetria. È una misura oggettiva. In più c'è una stima ricavata dai comandi, che dice se l'esecuzione è riuscita.

## L'analisi, decisa prima

Lo script è [`analizza.py`](analizza.py).

- Per modello e condizione: mediana, minimo e massimo di ogni misura per compito, e la somma delle mediane sui 15
  compiti.
- Il **rapporto** tokyn/python e tokyn/agent-sdk:
  - per ogni compito si confrontano le mediane delle 3 ripetizioni;
  - sui 15 compiti si fa la media geometrica, con un intervallo al 95% (bootstrap sui compiti, 10.000
    ricampionamenti, seme fisso);
  - la riduzione è 1 − rapporto.
- La **percentuale di controlli superati** per condizione, con un intervallo di Wilson al 95%.
- Si mostrano tutti i compiti, anche quelli in cui Tokyn perde.

## Le regole

- Una sessione si rifà solo se si è fermata per l'infrastruttura: limiti d'uso, API sovraccarica, nessun risultato.
  Le sessioni concluse non si rifanno e non si scartano, anche se il programma è sbagliato o manca.
- Se dopo le prove si scopre un errore in un controllo, si corregge il controllo e si rifanno i controlli di tutte le
  prove di quel compito (non le sessioni). La correzione si dichiara nei risultati.
- Le prove pilota non entrano nei risultati. Sono servite a verificare lo script e i controlli: prima sul compito
  `recensioni`, poi una sessione per condizione su tutti i compiti, con Sonnet. Hanno portato a questi cambiamenti, fatti
  prima di cominciare:
  - una `/tmp` privata per ogni sessione;
  - la misura dei costi delle prove con la telemetria, e lo script che la fa arrivare ai programmi provati;
  - una riga nella Skill di Tokyn: il sorgente `.tokyn` va scritto nella cartella del progetto. In una sessione
    Claude l'aveva scritto in `/tmp`, e l'utente non se lo sarebbe ritrovato.
  - Le correzioni ai controlli dei compiti emerse dalla pilota, se ce ne sono, sono nella storia del repository.
- Altri cambiamenti fatti a Tokyn prima delle prove, non dovuti alla pilota ma a una revisione delle regole di
  Anthropic: il runtime avvisa una volta quando gli agenti usano Claude Code invece della chiave API; la Skill descrive
  in modo più preciso quando usarla e ricorda che Claude Code serve a provare i programmi.
- Il plugin misurato viene dal commit passato a `esegui.py --commit`, scritto in `risultati/versioni.json`. Le
  modifiche fatte a Tokyn mentre le prove girano (per esempio i messaggi in inglese) non entrano nelle prove.

## Limiti noti

- **I programmi della condizione python** usano quasi sempre l'SDK di Anthropic, che senza chiave API non parte. Il
  controllo li segna come "non eseguibili senza chiave". Con una chiave (`BENCH_CHIAVE=1 python esegui.py
  --solo-controlli`) si possono verificare anche loro.
- **La cache dei prompt di Claude Code** è condivisa tra sessioni dello stesso account. L'ordine mescolato evita che
  favorisca una condizione.
- **La lingua:** richieste e Skill sono in italiano. La Skill italiana costa più token di quella inglese, quindi è il
  caso meno favorevole a Tokyn.
- **Una sola versione:** i risultati valgono per questa versione di Claude Code e di questi modelli.
