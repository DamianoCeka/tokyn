# Benchmark v2: risultati

82 sessioni di Claude Code, analizzate come deciso in [PROTOCOLLO.md](PROTOCOLLO.md). I costi sono a prezzi API, come li riporta Claude Code.

## Opus 5.5

| | Costo totale | di cui sessione | di cui prove | Token di output | Tempo | Controlli superati | Provati da Claude |
|---|---:|---:|---:|---:|---:|---:|---:|
| Con Tokyn | $3,58 | $3,22 | $0,36 | 48.616 | 15,6 min | 29 su 29 (100%) | 29 su 29 |
| Python | $8,56 | $8,56 | $0,00 | 79.818 | 14,7 min | 0 su 25 (0%) | 0 su 25 |
| Python + Agent SDK | $8,55 | $7,20 | $1,35 | 74.222 | 16,8 min | 28 su 28 (100%) | 28 su 28 |

Somme sui compiti delle mediane delle 3 ripetizioni.

**Documentazione dell'API.** Sessioni che hanno aperto la skill integrata `claude-api` e costo mediano di una sessione con e senza:

- Con Tokyn: 0 su 29; con –, senza $0,20
- Python: 25 su 25; con $0,71, senza –
- Python + Agent SDK: 18 su 28; con $0,63, senza $0,27

**Tokyn rispetto a Python** (media geometrica dei rapporti sui compiti):

- costo totale: **−68%** (intervallo al 95% da −72% a −64%); Tokyn è sotto in 12 compiti su 12
- token di output: **−54%** (intervallo al 95% da −60% a −46%); Tokyn è sotto in 12 compiti su 12
- tempo: **−22%** (intervallo al 95% da −38% a −3%); Tokyn è sotto in 9 compiti su 12

**Tokyn rispetto a Python + Agent SDK** (media geometrica dei rapporti sui compiti):

- costo totale: **−61%** (intervallo al 95% da −68% a −51%); Tokyn è sotto in 13 compiti su 14
- token di output: **−41%** (intervallo al 95% da −48% a −32%); Tokyn è sotto in 14 compiti su 14
- tempo: **−16%** (intervallo al 95% da −29% a +1%); Tokyn è sotto in 11 compiti su 14

### Per compito

Costo totale mediano (minimo–massimo) e controlli superati su 3.

| Compito | Con Tokyn | Python | Python + Agent SDK |
|---|---:|---:|---:|
| `articolo` | $0,23 ($0,20–$0,23), 3/3 | – | $0,66 ($0,45–$0,69), 3/3 |
| `assistente` | $0,22 ($0,22–$0,22), 1/3 | – | $0,78 ($0,65–$0,92), 2/3 |
| `candidati` | $0,28 ($0,28–$0,28), 1/3 | $0,78 ($0,67–$0,88), 0/3 | $0,67 ($0,45–$0,89), 2/3 |
| `catalogo` | $0,25 ($0,23–$0,26), 2/3 | $0,65 ($0,61–$0,68), 0/3 | $0,61 ($0,61–$0,61), 2/3 |
| `documenti` | $0,21 ($0,20–$0,23), 3/3 | $0,73 ($0,71–$0,78), 0/3 | $0,72 ($0,72–$0,72), 1/3 |
| `email` | $0,19 ($0,18–$0,19), 2/3 | $0,63 ($0,63–$0,63), 0/3 | $0,73 ($0,73–$0,73), 1/3 |
| `fattura` | $0,23 ($0,23–$0,23), 1/3 | $0,63 ($0,63–$0,63), 0/3 | $0,71 ($0,70–$0,73), 3/3 |
| `log` | $0,26 ($0,25–$0,27), 2/3 | $0,69 ($0,67–$0,71), 0/3 | – |
| `magazzino` | $0,33 ($0,30–$0,35), 2/3 | $0,77 ($0,74–$0,81), 0/3 | $0,57 ($0,51–$0,63), 2/3 |
| `moderazione` | $0,19 ($0,17–$0,20), 2/3 | $0,71 ($0,67–$0,74), 0/3 | $0,77 ($0,75–$0,79), 2/3 |
| `recensioni` | $0,16 ($0,15–$0,17), 3/3 | $0,66 ($0,65–$0,67), 0/3 | $0,45 ($0,25–$0,66), 2/3 |
| `riunione` | $0,18 ($0,17–$0,18), 3/3 | $0,75 ($0,75–$0,75), 0/3 | $0,66 ($0,26–$0,69), 3/3 |
| `scadenze` | $0,35 ($0,35–$0,35), 1/3 | $0,78 ($0,70–$0,86), 0/3 | $0,45 ($0,43–$0,47), 2/3 |
| `spese` | $0,19 ($0,19–$0,19), 1/3 | $0,80 ($0,68–$0,83), 0/3 | $0,48 ($0,27–$0,70), 2/3 |
| `vendite` | $0,32 ($0,27–$0,36), 2/3 | – | $0,28 ($0,28–$0,28), 1/3 |

## Avvisi

- opus/articolo/python: 0 prove invece di 3
- opus/assistente/tokyn: 1 prove invece di 3
- opus/assistente/python: 0 prove invece di 3
- opus/assistente/agent-sdk: 2 prove invece di 3
- opus/candidati/tokyn: 1 prove invece di 3
- opus/candidati/agent-sdk: 2 prove invece di 3
- opus/catalogo/tokyn: 2 prove invece di 3
- opus/catalogo/python: 2 prove invece di 3
- opus/catalogo/agent-sdk: 2 prove invece di 3
- opus/documenti/agent-sdk: 1 prove invece di 3
- opus/email/tokyn: 2 prove invece di 3
- opus/email/python: 2 prove invece di 3
- opus/email/agent-sdk: 1 prove invece di 3
- opus/fattura/tokyn: 1 prove invece di 3
- opus/fattura/python: 1 prove invece di 3
- opus/log/tokyn: 2 prove invece di 3
- opus/log/python: 2 prove invece di 3
- opus/log/agent-sdk: 0 prove invece di 3
- opus/magazzino/tokyn: 2 prove invece di 3
- opus/magazzino/python: 2 prove invece di 3
- opus/magazzino/agent-sdk: 2 prove invece di 3
- opus/moderazione/tokyn: 2 prove invece di 3
- opus/moderazione/python: 2 prove invece di 3
- opus/moderazione/agent-sdk: 2 prove invece di 3
- opus/recensioni/python: 2 prove invece di 3
- opus/recensioni/agent-sdk: 2 prove invece di 3
- opus/riunione/python: 1 prove invece di 3
- opus/scadenze/tokyn: 1 prove invece di 3
- opus/scadenze/python: 2 prove invece di 3
- opus/scadenze/agent-sdk: 2 prove invece di 3
- opus/spese/tokyn: 1 prove invece di 3
- opus/spese/agent-sdk: 2 prove invece di 3
- opus/vendite/tokyn: 2 prove invece di 3
- opus/vendite/python: 0 prove invece di 3
- opus/vendite/agent-sdk: 1 prove invece di 3
