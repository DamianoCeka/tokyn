# Programma finto con un errore plausibile (decisioni giuste, ma la "riscrittura" è il testo originale, con le parole
# offensive): il controllo deve bocciarlo.
import json
commenti = json.load(open("commenti.json", encoding="utf-8"))
decisioni = ["pubblica", "rifiuta", "rivedi", "pubblica", "rifiuta", "rivedi"]
out = []
for c, d in zip(commenti, decisioni):
    r = {"id": c["id"], "decisione": d, "motivo": "Valutato secondo le regole del forum."}
    if d == "rivedi":
        r["riscrittura"] = c["testo"]
    out.append(r)
json.dump(out, open("risultato.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
