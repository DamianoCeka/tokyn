# Prova in Claude Code: con Tokyn e senza

La domanda: se in Claude Code chiedi un programma Python con agenti IA, quanto costa farlo scrivere a Claude
in Tokyn (con il plugin) invece che direttamente in Python?

## Come ho fatto

- 3 richieste, scritte come le scriverebbe chi programma, ognuna con "Provalo davvero e dammi anche il file Python":
  1. `recensioni`: per ogni recensione di `recensioni.txt` sentimento e voto da 1 a 5, poi la media
  2. `assistente`: assistente clienti da terminale con uno strumento di ricerca nelle FAQ e memoria
  3. `fattura`: estrazione dei dati di una fattura e ricalcolo del totale
- Ogni richiesta in una sessione nuova di Claude Code (Opus 5.5), in una cartella con solo i file di [`dati/`](dati):
  - **con Tokyn**: con il plugin e la frase "Usa la skill tokyn" in fondo alla richiesta
  - **senza Tokyn**: Claude Code normale, che scrive Python come al solito
- Nessuna chiave API nell'ambiente, come succede di solito a chi usa Claude Code con l'abbonamento.

```bash
claude -p "<richiesta>" --model opus --output-format json --no-session-persistence \
  --setting-sources "" --strict-mcp-config --allowedTools "Bash Read Write Edit Glob Grep Skill" \
  [--plugin-dir plugins/tokyn]
```

## Risultati (29 ottobre 2026)

| Richiesta | Costo con Tokyn | Costo senza | Token di output con / senza | Tempo con / senza | Provato con l'IA vera? con / senza |
|---|---:|---:|---:|---:|---|
| recensioni | $0,19 | $0,66 | 2.058 / 4.676 | 41 s / 60 s | sì / no |
| assistente | $0,24 | $0,70 | 2.881 / 5.701 | 69 s / 66 s | sì / no |
| fattura | $0,19 | $0,62 | 1.992 / 4.602 | 34 s / 63 s | sì / no |
| **Totale** | **$0,61** | **$1,99** | **6.931 / 14.979** | **144 s / 189 s** | **3 su 3 / 0 su 3** |

Con Tokyn: **−69% di costo, −54% di token di output, −24% di tempo**, e il programma è stato provato davvero.

- Il costo è quello che Claude Code riporta per la sessione (`total_cost_usd`, a prezzi API).
- **Con Tokyn** Claude ha scritto il programma (23-34 righe), l'ha provato con risposte vere passando dal Claude Code
  dell'utente (nell'assistente la seconda domanda usa la memoria, nella fattura ha trovato un totale sbagliato di
  0,30 €) e ha generato il file Python con `tokyn build --standalone`. Le chiamate degli agenti durante la prova
  sono a parte e costano pochi centesimi (Claude ha riportato $0,001 per le recensioni e circa $0,03 per
  l'assistente).
- **Senza Tokyn** Claude ha scritto un Python corretto (58-123 righe, con l'SDK di Anthropic) ma non è riuscito a
  provarlo: senza chiave API il programma si ferma all'autenticazione.

I sorgenti scritti da Claude sono in [`con-tokyn/`](con-tokyn) e [`senza-tokyn/`](senza-tokyn).

## Limiti

- Una sessione per richiesta: i numeri danno l'ordine di grandezza, non una media.
- Con una chiave API la sessione senza Tokyn avrebbe potuto provare il programma, spendendo altri turni e token.
- Le sessioni senza Tokyn non avevano il plugin, quindi hanno letto meno istruzioni all'inizio: il confronto è
  tra i due modi di lavorare, Skill compresa.
