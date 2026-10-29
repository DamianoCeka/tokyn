"""Analizza le prove del benchmark v2 come deciso in PROTOCOLLO.md.

Uso: python analizza.py [--risultati CARTELLA]
Legge risultati/**/esito.json, scrive risultati/riepilogo.json e RISULTATI.md.
"""

import argparse
import json
import math
import random
import statistics
from pathlib import Path

QUI = Path(__file__).resolve().parent
CONDIZIONI = ["tokyn", "python", "agent-sdk"]
NOMI = {"tokyn": "Con Tokyn", "python": "Python", "agent-sdk": "Python + Agent SDK"}
MODELLI = {"opus": "Opus 5.5", "sonnet": "Sonnet 5.5"}
MISURE = ["costo_totale", "costo_sessione", "costo_prove", "token_output", "secondi", "turni"]


def misure(e):
    prove = (e.get("prove_del_programma") or {}).get("costo_usd") or 0
    controllo = e.get("controllo") or {}
    return {
        "costo_sessione": e.get("costo_usd") or 0,
        "costo_prove": prove,
        "costo_totale": (e.get("costo_usd") or 0) + prove,
        "token_output": e.get("token_output") or 0,
        "secondi": e.get("secondi") or 0,
        "turni": e.get("turni") or 0,
        "ok": bool(controllo.get("ok")),
        "eseguibile": bool(controllo.get("eseguibile")),
        "costo_esecuzione": (controllo.get("costo_ia") or {}).get("costo_usd"),
        "provato": (e.get("prove_del_programma") or {}).get("chiamate", 0) > 0,  # chiamate vere all'IA in sessione
        "consegnato": bool(e.get("programma_consegnato")),
    }


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    margine = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(centro - margine, 3), round(centro + margine, 3))


def media_geometrica(valori):
    return math.exp(sum(math.log(v) for v in valori) / len(valori))


def bootstrap(rapporti, n=10_000, seme=2026):
    """Intervallo al 95% della media geometrica dei rapporti, ricampionando i compiti."""
    rnd = random.Random(seme)
    medie = sorted(media_geometrica([rnd.choice(rapporti) for _ in rapporti]) for _ in range(n))
    return (medie[int(0.025 * n)], medie[int(0.975 * n) - 1])


def analizza(esiti):
    out = {"modelli": {}, "avvisi": []}
    for modello in MODELLI:
        del_modello = [e for e in esiti if e["modello"] == modello]
        if not del_modello:
            continue
        compiti = sorted({e["compito"] for e in del_modello})
        celle = {}
        for e in del_modello:
            celle.setdefault((e["compito"], e["condizione"]), []).append(misure(e))
        m = {"compiti": {}, "condizioni": {}, "confronti": {}}
        for c in compiti:
            m["compiti"][c] = {}
            for cond in CONDIZIONI:
                prove = celle.get((c, cond), [])
                if len(prove) != 3:
                    out["avvisi"].append(f"{modello}/{c}/{cond}: {len(prove)} prove invece di 3")
                if not prove:
                    continue
                cella = {k: {"mediana": statistics.median(p[k] for p in prove), "min": min(p[k] for p in prove),
                             "max": max(p[k] for p in prove)} for k in MISURE}
                cella["ok"] = sum(p["ok"] for p in prove)
                cella["eseguibili"] = sum(p["eseguibile"] for p in prove)
                cella["provati"] = sum(p["provato"] for p in prove)
                cella["prove"] = len(prove)
                esec = [p["costo_esecuzione"] for p in prove if p["eseguibile"] and p["costo_esecuzione"] is not None]
                cella["costo_esecuzione"] = statistics.median(esec) if esec else None
                m["compiti"][c][cond] = cella
        for cond in CONDIZIONI:
            celle_c = [m["compiti"][c][cond] for c in compiti if cond in m["compiti"][c]]
            tutte = [misure(e) for e in del_modello if e["condizione"] == cond]
            k, n = sum(p["ok"] for p in tutte), len(tutte)
            esec = [x["costo_esecuzione"] for x in celle_c if x["costo_esecuzione"] is not None]
            m["condizioni"][cond] = {
                **{f"somma_{k2}": round(sum(x[k2]["mediana"] for x in celle_c), 4) for k2 in MISURE},
                "prove": n, "ok": k, "ok_percento": round(100 * k / n, 1) if n else None, "ok_intervallo": wilson(k, n),
                "eseguibili": sum(p["eseguibile"] for p in tutte), "provati": sum(p["provato"] for p in tutte),
                "consegnati": sum(p["consegnato"] for p in tutte),
                "costo_esecuzione_mediano": statistics.median(esec) if esec else None,
            }
        for altra in ("python", "agent-sdk"):
            confronto = {}
            for k2 in ("costo_totale", "costo_sessione", "token_output", "secondi"):
                rapporti, per_compito = [], {}
                for c in compiti:
                    a, b = m["compiti"][c].get("tokyn"), m["compiti"][c].get(altra)
                    if a and b and a[k2]["mediana"] > 0 and b[k2]["mediana"] > 0:
                        r = a[k2]["mediana"] / b[k2]["mediana"]
                        rapporti.append(r)
                        per_compito[c] = round(r, 3)
                if not rapporti:
                    continue
                g = media_geometrica(rapporti)
                basso, alto = bootstrap(rapporti)
                confronto[k2] = {"rapporto": round(g, 3), "intervallo": [round(basso, 3), round(alto, 3)],
                                 "riduzione_percento": round(100 * (1 - g), 1),
                                 "riduzione_intervallo": [round(100 * (1 - alto), 1), round(100 * (1 - basso), 1)],
                                 "compiti_vinti": sum(1 for r in rapporti if r < 1), "compiti": len(rapporti),
                                 "per_compito": per_compito}
            m["confronti"][f"tokyn/{altra}"] = confronto
        out["modelli"][modello] = m

    for e in esiti:
        if e["condizione"] == "tokyn" and not any("tokyn" in s for s in e.get("skill", [])):
            out["avvisi"].append(f"{e['prova']}: la Skill tokyn non è stata usata")
        if e["condizione"] == "agent-sdk" and e.get("programma_consegnato") and not e.get("usa_agent_sdk"):
            out["avvisi"].append(f"{e['prova']}: il programma non usa l'Agent SDK")
        if e.get("letto_benchmark"):
            out["avvisi"].append(f"{e['prova']}: la sessione nomina i file del benchmark")
        if e.get("scaduta"):
            out["avvisi"].append(f"{e['prova']}: sessione scaduta dopo 30 minuti")
    impronte = {e.get("impronta_plugin") for e in esiti}
    if len(impronte) > 1:
        out["avvisi"].append(f"versioni diverse del plugin tra le prove: {sorted(map(str, impronte))}")
    return out


def euro(v):
    return "–" if v is None else f"${v:.2f}".replace(".", ",")


def numero(v, d=0):
    if v is None:
        return "–"
    t = f"{v:,.{d}f}"
    return t.replace(",", "\0").replace(".", ",").replace("\0", ".")


def variazione(v):
    """Una variazione in percentuale col segno: -88 -> "−88%", 30 -> "+30%"."""
    return ("−" if v < 0 else "+") + numero(abs(v)) + "%"


def rapporto_testo(c):
    if not c:
        return "–"
    v = c["rapporto"] * 100 - 100
    basso, alto = (r * 100 - 100 for r in c["intervallo"])
    return (f"**{variazione(v)}** (intervallo al 95% da {variazione(basso)} a {variazione(alto)}); "
            f"Tokyn è sotto in {c['compiti_vinti']} compiti su {c['compiti']}")


def markdown(r, n_prove):
    righe = ["# Benchmark v2: risultati", "",
             f"{n_prove} sessioni di Claude Code, analizzate come deciso in [PROTOCOLLO.md](PROTOCOLLO.md). "
             "I costi sono a prezzi API, come li riporta Claude Code.", ""]
    for modello, m in r["modelli"].items():
        righe += [f"## {MODELLI[modello]}", "",
                  "| | Costo totale | di cui sessione | di cui prove | Token di output | Tempo | Controlli superati | Provati da Claude |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for cond in CONDIZIONI:
            s = m["condizioni"].get(cond)
            if not s:
                continue
            lo, hi = s["ok_intervallo"]
            righe.append(f"| {NOMI[cond]} | {euro(s['somma_costo_totale'])} | {euro(s['somma_costo_sessione'])} | "
                         f"{euro(s['somma_costo_prove'])} | {numero(s['somma_token_output'])} | "
                         f"{numero(s['somma_secondi'] / 60, 1)} min | {s['ok']} su {s['prove']} "
                         f"({numero(s['ok_percento'])}%) | {s['provati']} su {s['prove']} |")
        righe += ["", "Somme sui compiti delle mediane delle 3 ripetizioni.", ""]
        for altra in ("python", "agent-sdk"):
            c = m["confronti"].get(f"tokyn/{altra}", {})
            righe += [f"**Tokyn rispetto a {NOMI[altra]}** (media geometrica dei rapporti sui compiti):", "",
                      f"- costo totale: {rapporto_testo(c.get('costo_totale'))}",
                      f"- token di output: {rapporto_testo(c.get('token_output'))}",
                      f"- tempo: {rapporto_testo(c.get('secondi'))}", ""]
        righe += ["### Per compito", "",
                  "Costo totale mediano (minimo–massimo) e controlli superati su 3.", "",
                  "| Compito | " + " | ".join(NOMI[c] for c in CONDIZIONI) + " |",
                  "|---|" + "---:|" * len(CONDIZIONI)]
        for compito, celle in m["compiti"].items():
            valori = []
            for cond in CONDIZIONI:
                x = celle.get(cond)
                if not x:
                    valori.append("–")
                    continue
                ct = x["costo_totale"]
                valori.append(f"{euro(ct['mediana'])} ({euro(ct['min'])}–{euro(ct['max'])}), {x['ok']}/3")
            righe.append(f"| `{compito}` | " + " | ".join(valori) + " |")
        righe.append("")
    if r["avvisi"]:
        righe += ["## Avvisi", ""] + [f"- {a}" for a in r["avvisi"]] + [""]
    return "\n".join(righe)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risultati", default=str(QUI / "risultati"))
    a = ap.parse_args()
    cartella = Path(a.risultati)
    esiti = [json.loads(f.read_text()) for f in sorted(cartella.rglob("esito.json"))]
    concluse = [e for e in esiti if e.get("completata")]
    r = analizza(concluse)
    r["prove_concluse"] = len(concluse)
    r["da_rifare"] = len(esiti) - len(concluse)
    (cartella / "riepilogo.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    (QUI / "RISULTATI.md" if cartella == QUI / "risultati" else cartella / "RISULTATI.md").write_text(
        markdown(r, len(concluse)), encoding="utf-8")
    print(f"{len(concluse)} prove concluse, {r['da_rifare']} da rifare, {len(r['avvisi'])} avvisi")


if __name__ == "__main__":
    main()
