# Benchmark v2: risultati

135 sessioni di Claude Code, analizzate come deciso in [PROTOCOLLO.md](PROTOCOLLO.md). I costi sono a prezzi API, come li riporta Claude Code.

## Opus 5.5

| | Costo totale | di cui sessione | di cui prove | Token di output | Tempo | Controlli superati | Provati da Claude |
|---|---:|---:|---:|---:|---:|---:|---:|
| Con Tokyn | $3,51 | $3,16 | $0,34 | 45.823 | 15,3 min | 45 su 45 (100%) | 45 su 45 |
| Python | $10,93 | $10,93 | $0,00 | 103.001 | 19,0 min | 0 su 45 (0%) | 0 su 45 |
| Python + Agent SDK | $9,29 | $8,11 | $1,25 | 75.805 | 16,7 min | 45 su 45 (100%) | 45 su 45 |

Somme sui compiti delle mediane delle 3 ripetizioni.

**Documentazione dell'API.** Sessioni che hanno aperto la skill integrata `claude-api` e costo mediano di una sessione con e senza:

- Con Tokyn: 0 su 45; con –, senza $0,21
- Python: 45 su 45; con $0,73, senza –
- Python + Agent SDK: 29 su 45; con $0,62, senza $0,26

**Tokyn rispetto a Python** (media geometrica dei rapporti sui compiti):

- costo totale: **−68%** (intervallo al 95% da −71% a −66%); Tokyn è sotto in 15 compiti su 15
- token di output: **−56%** (intervallo al 95% da −59% a −52%); Tokyn è sotto in 15 compiti su 15
- tempo: **−23%** (intervallo al 95% da −36% a −8%); Tokyn è sotto in 11 compiti su 15

**Tokyn rispetto a Python + Agent SDK** (media geometrica dei rapporti sui compiti):

- costo totale: **−61%** (intervallo al 95% da −68% a −51%); Tokyn è sotto in 14 compiti su 15
- token di output: **−40%** (intervallo al 95% da −45% a −35%); Tokyn è sotto in 15 compiti su 15
- tempo: **−12%** (intervallo al 95% da −26% a +3%); Tokyn è sotto in 11 compiti su 15

### Per compito

Costo totale mediano (minimo–massimo) e controlli superati su 3.

| Compito | Con Tokyn | Python | Python + Agent SDK |
|---|---:|---:|---:|
| `articolo` | $0,23 ($0,20–$0,23), 3/3 | $0,75 ($0,75–$0,76), 0/3 | $0,66 ($0,45–$0,69), 3/3 |
| `assistente` | $0,22 ($0,19–$0,29), 3/3 | $0,76 ($0,73–$0,76), 0/3 | $0,65 ($0,26–$0,92), 3/3 |
| `candidati` | $0,28 ($0,28–$0,28), 3/3 | $0,78 ($0,67–$0,88), 0/3 | $0,89 ($0,45–$0,93), 3/3 |
| `catalogo` | $0,23 ($0,20–$0,26), 3/3 | $0,68 ($0,61–$0,71), 0/3 | $0,61 ($0,61–$0,81), 3/3 |
| `documenti` | $0,21 ($0,20–$0,23), 3/3 | $0,73 ($0,71–$0,78), 0/3 | $0,66 ($0,65–$0,72), 3/3 |
| `email` | $0,19 ($0,18–$0,20), 3/3 | $0,63 ($0,63–$0,63), 0/3 | $0,65 ($0,60–$0,73), 3/3 |
| `fattura` | $0,23 ($0,21–$0,23), 3/3 | $0,63 ($0,63–$0,67), 0/3 | $0,71 ($0,70–$0,73), 3/3 |
| `log` | $0,25 ($0,21–$0,27), 3/3 | $0,71 ($0,67–$0,78), 0/3 | $0,20 ($0,18–$0,22), 3/3 |
| `magazzino` | $0,33 ($0,30–$0,35), 3/3 | $0,77 ($0,74–$0,81), 0/3 | $0,51 ($0,49–$0,63), 3/3 |
| `moderazione` | $0,19 ($0,17–$0,20), 3/3 | $0,68 ($0,67–$0,74), 0/3 | $0,75 ($0,75–$0,79), 3/3 |
| `recensioni` | $0,16 ($0,15–$0,17), 3/3 | $0,65 ($0,56–$0,67), 0/3 | $0,59 ($0,25–$0,66), 3/3 |
| `riunione` | $0,18 ($0,17–$0,18), 3/3 | $0,74 ($0,72–$0,75), 0/3 | $0,66 ($0,26–$0,69), 3/3 |
| `scadenze` | $0,31 ($0,30–$0,35), 3/3 | $0,81 ($0,70–$0,86), 0/3 | $0,47 ($0,43–$0,54), 3/3 |
| `spese` | $0,21 ($0,19–$0,22), 3/3 | $0,80 ($0,68–$0,83), 0/3 | $0,64 ($0,27–$0,70), 3/3 |
| `vendite` | $0,27 ($0,26–$0,36), 3/3 | $0,82 ($0,71–$0,88), 0/3 | $0,65 ($0,28–$0,71), 3/3 |
