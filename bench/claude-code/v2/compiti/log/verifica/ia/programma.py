# Soluzione di prova con l'IA vera (claude -p), scritta solo per verificare che i dati nascosti siano chiari.
# Le statistiche le calcola Python; Claude scrive solo il commento.
import json, re, subprocess
from collections import Counter
def chiedi(testo):
    p = subprocess.run(["claude", "-p", testo, "--model", "sonnet", "--tools", "", "--no-session-persistence",
                        "--setting-sources", ""], capture_output=True, text=True, timeout=300)
    return p.stdout.strip()
ore, errori, ip = Counter(), Counter(), Counter()
for r in open("access.log", encoding="utf-8"):
    m = re.match(r'^(\S+) \S+ \S+ \[[^:]+:(\d\d):[^\]]+\] "[^"]*" (\d{3}) ', r)
    if m:
        ore[m[2]] += 1
        ip[m[1]] += 1
        if int(m[3]) >= 400:
            errori[m[3]] += 1
stat = {"richieste_per_ora": dict(sorted(ore.items())), "errori": dict(sorted(errori.items())),
        "ip_top": [a for a, _ in ip.most_common(3)]}
commento = chiedi("Queste sono le statistiche del log di un sito web per una giornata:\n" + json.dumps(stat) +
                  "\nScrivi in italiano un commento di esattamente due frasi sul traffico della giornata. "
                  "Rispondi solo con le due frasi.")
stat["commento"] = commento
json.dump(stat, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False)
