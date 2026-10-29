"""Disegna i grafici del README (SVG, inglese e italiano, tema chiaro e scuro) dai risultati del benchmark v2.

Uso: python scripts/make_charts.py
Legge bench/claude-code/v2/risultati/riepilogo.json (scritto da analizza.py) e scrive docs/grafici/*.svg.
"""

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "grafici"
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
WIDTH = 880

# Colori per ruolo (palette validata): blu d'accento per Tokyn, due grigi per i confronti. Il grigio chiaro ha poco
# contrasto con lo sfondo, quindi ogni barra porta il suo valore scritto accanto.
THEMES = {
    "light": {"surface": "#fcfcfb", "border": "rgba(11,11,11,0.10)", "ink": "#0b0b0b", "ink2": "#52514e",
              "muted": "#898781", "baseline": "#c3c2b7", "accent": "#2a78d6", "gray": "#8f8e88", "gray2": "#c3c2b7",
              "good": "#006300"},
    "dark": {"surface": "#1a1a19", "border": "rgba(255,255,255,0.10)", "ink": "#f0efec", "ink2": "#c3c2b7",
             "muted": "#898781", "baseline": "#383835", "accent": "#3987e5", "gray": "#6e6d68", "gray2": "#a3a29b",
             "good": "#0ca30c"},
}
MODELLI = {"opus": "Opus 5.5", "sonnet": "Sonnet 5.5"}
TESTI = {
    "en": {
        "conditions": {"tokyn": "With Tokyn", "python": "Python", "agent-sdk": "Python + Agent SDK"},
        "tasks": {"recensioni": "Reviews", "assistente": "Support chat", "fattura": "Invoice", "email": "Email triage",
                  "catalogo": "Catalog translation", "riunione": "Meeting minutes", "documenti": "Document Q&A",
                  "moderazione": "Moderation", "spese": "Expenses", "candidati": "CV screening",
                  "magazzino": "Inventory", "articolo": "Article summary", "log": "Web server log",
                  "vendite": "Sales report", "scadenze": "Contract reminders"},
        "kpi_title": "15 Python programs that use Claude, written by Claude Code in three ways",
        "kpi_sub": "{n} sessions with {models}, 3 runs per program. Medians; costs at API list prices.",
        "kpi": [("Cost vs Python", "{ab}"), ("Cost vs Agent SDK", "{ac}"), ("Output tokens vs Python", "{tb}"),
                ("Passed the hidden tests", "{ok}")],
        "detail_model": "{model}: {value}", "ok_detail": ["Python: {b} (no API key)", "Agent SDK: {c}"],
        "cost_title": "Cost of the Claude Code session, per program ({model})",
        "cost_sub": "Median of 3 runs, at API list prices. Right: Tokyn compared with Python + Agent SDK.",
        "of": "of",
    },
    "it": {
        "conditions": {"tokyn": "Con Tokyn", "python": "Python", "agent-sdk": "Python + Agent SDK"},
        "tasks": {"recensioni": "Recensioni", "assistente": "Assistente clienti", "fattura": "Fattura",
                  "email": "Smistamento email", "catalogo": "Traduzione catalogo", "riunione": "Verbale riunione",
                  "documenti": "Domande sui documenti", "moderazione": "Moderazione", "spese": "Spese",
                  "candidati": "Selezione CV", "magazzino": "Magazzino", "articolo": "Riassunto articolo",
                  "log": "Log del server web", "vendite": "Report vendite", "scadenze": "Promemoria contratti"},
        "kpi_title": "15 programmi Python che usano Claude, scritti da Claude Code in tre modi",
        "kpi_sub": "{n} sessioni con {models}, 3 ripetizioni per programma. Mediane; costi a prezzi API.",
        "kpi": [("Costo vs Python", "{ab}"), ("Costo vs Agent SDK", "{ac}"), ("Token di output vs Python", "{tb}"),
                ("Test nascosti superati", "{ok}")],
        "detail_model": "{model}: {value}", "ok_detail": ["Python: {b} (senza chiave)", "Agent SDK: {c}"],
        "cost_title": "Costo della sessione di Claude Code, per programma ({model})",
        "cost_sub": "Mediana di 3 ripetizioni, a prezzi API. A destra: Tokyn rispetto a Python + Agent SDK.",
        "of": "su",
    },
}


def num(value, decimals=0, lang="it"):
    """1.234,5 in italiano, 1,234.5 in inglese."""
    text = f"{value:,.{decimals}f}"
    return text if lang == "en" else text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def dollari(value, lang):
    return "$" + num(value, 2, lang)


def variazione(rapporto, lang):
    v = rapporto * 100 - 100
    return ("−" if v < 0 else "+") + num(abs(v), 0, lang) + "%"


def card(t, height, title, subtitle, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
        f'font-family="{FONT}" role="img" aria-label="{escape(title)}">\n'
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="12" fill="{t["surface"]}" stroke="{t["border"]}"/>\n'
        f'<text x="28" y="40" font-size="17" font-weight="600" fill="{t["ink"]}">{escape(title)}</text>\n'
        f'<text x="28" y="62" font-size="13" fill="{t["ink2"]}">{escape(subtitle)}</text>\n'
        f'{body}</svg>\n'
    )


def bar(x, y, w, h, color):
    """Barra orizzontale: squadrata sulla linea di base, 4px arrotondati in punta."""
    r = min(4, w / 2, h / 2)
    return (f'<path d="M{x},{y} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r} a{r},{r} 0 0 1 {-r},{r} '
            f'h{-(w - r):.1f} z" fill="{color}"/>')


def legend(t, x, y, items):
    out, cx = [], x
    for label, color in items:
        out.append(f'<rect x="{cx}" y="{y - 9}" width="10" height="10" rx="2" fill="{color}"/>')
        out.append(f'<text x="{cx + 16}" y="{y}" font-size="12" fill="{t["ink2"]}">{escape(label)}</text>')
        cx += 26 + len(label) * 6.6
    return "\n".join(out)


def kpi_row(t, title, subtitle, tiles):
    """Riga di riquadri numerici: etichetta, valore grande, dettaglio."""
    n, pad, gap = len(tiles), 28, 16
    w = (WIDTH - 2 * pad - (n - 1) * gap) / n
    body = []
    for i, (label, value, detail) in enumerate(tiles):
        x = pad + i * (w + gap)
        body.append(f'<rect x="{x:.1f}" y="84" width="{w:.1f}" height="112" rx="10" fill="none" stroke="{t["border"]}"/>')
        body.append(f'<text x="{x + 14:.1f}" y="108" font-size="12" fill="{t["ink2"]}">{escape(label)}</text>')
        body.append(f'<text x="{x + 14:.1f}" y="150" font-size="32" font-weight="600" fill="{t["ink"]}">{value}</text>')
        for j, riga in enumerate(detail):
            body.append(f'<text x="{x + 14:.1f}" y="{172 + 15 * j}" font-size="11.5" fill="{t["muted"]}">{escape(riga)}</text>')
    return card(t, 218, title, subtitle, "\n".join(body) + "\n")


def cost_bars(t, lang, title, subtitle, rows):
    """Una riga per programma: tre barre (Tokyn in evidenza, i confronti in grigio) con il valore in punta e, a
    destra, la variazione di Tokyn rispetto a Python + Agent SDK."""
    tx = TESTI[lang]
    serie = [("tokyn", t["accent"]), ("python", t["gray"]), ("agent-sdk", t["gray2"])]
    x0, right_pad = 210, 96
    scale = (WIDTH - x0 - right_pad - 56) / max(max(r[1].values()) for r in rows)
    h, gap, group_gap, top = 13, 2, 16, 104
    body = [legend(t, 28, 90, [(tx["conditions"][k], c) for k, c in serie])]
    y = top
    for name, valori in rows:
        altezza = 3 * h + 2 * gap
        body.append(f'<text x="28" y="{y + altezza / 2 + 4:.1f}" font-size="12.5" fill="{t["ink"]}">{escape(name)}</text>')
        for i, (k, color) in enumerate(serie):
            by = y + i * (h + gap)
            w = max(valori[k] * scale, 2)
            body.append(bar(x0, by, w, h, color))
            body.append(f'<text x="{x0 + w + 6:.1f}" y="{by + 10.5}" font-size="11" fill="{t["ink2"]}" '
                        f'font-variant-numeric="tabular-nums">{dollari(valori[k], lang)}</text>')
        r = valori["tokyn"] / valori["agent-sdk"]
        colore = t["good"] if r < 1 else t["ink2"]
        body.append(f'<text x="{WIDTH - 28}" y="{y + altezza / 2 + 5:.1f}" font-size="13" font-weight="600" '
                    f'text-anchor="end" fill="{colore}">{variazione(r, lang)}</text>')
        y += altezza + group_gap
    body.insert(0, f'<line x1="{x0}" y1="{top - 4}" x2="{x0}" y2="{y - group_gap + 4}" stroke="{t["baseline"]}"/>')
    return card(t, y - group_gap + 30, title, subtitle, "\n".join(body) + "\n")


def main():
    r = json.loads((ROOT / "bench" / "claude-code" / "v2" / "risultati" / "riepilogo.json").read_text(encoding="utf-8"))
    modelli = [m for m in MODELLI if m in r["modelli"]]
    principale = modelli[0]
    OUT.mkdir(parents=True, exist_ok=True)
    for lang, tx in TESTI.items():
        def per_modello(chiave, misura):
            return [tx["detail_model"].format(model=MODELLI[m], value=variazione(
                r["modelli"][m]["confronti"][chiave][misura]["rapporto"], lang)) for m in modelli]

        def superati(m, cond):
            s = r["modelli"][m]["condizioni"][cond]
            return f'{s["ok"]} {tx["of"]} {s["prove"]}'

        m0 = r["modelli"][principale]
        valori = {
            "ab": variazione(m0["confronti"]["tokyn/python"]["costo_totale"]["rapporto"], lang),
            "ac": variazione(m0["confronti"]["tokyn/agent-sdk"]["costo_totale"]["rapporto"], lang),
            "tb": variazione(m0["confronti"]["tokyn/python"]["token_output"]["rapporto"], lang),
            "ok": f'{sum(r["modelli"][m]["condizioni"]["tokyn"]["ok"] for m in modelli)}/'
                  f'{sum(r["modelli"][m]["condizioni"]["tokyn"]["prove"] for m in modelli)}',
        }
        dettagli = [per_modello("tokyn/python", "costo_totale"), per_modello("tokyn/agent-sdk", "costo_totale"),
                    per_modello("tokyn/python", "token_output"),
                    [riga.format(
                        b=f'{sum(r["modelli"][m]["condizioni"]["python"]["ok"] for m in modelli)}/'
                          f'{sum(r["modelli"][m]["condizioni"]["python"]["prove"] for m in modelli)}',
                        c=f'{sum(r["modelli"][m]["condizioni"]["agent-sdk"]["ok"] for m in modelli)}/'
                          f'{sum(r["modelli"][m]["condizioni"]["agent-sdk"]["prove"] for m in modelli)}')
                     for riga in tx["ok_detail"]]]
        tiles = [(label, valore.format(**valori), det) for (label, valore), det in zip(tx["kpi"], dettagli)]
        n = r["prove_concluse"]
        for mode, t in THEMES.items():
            files = {f"numeri-{lang}": kpi_row(t, tx["kpi_title"], tx["kpi_sub"].format(
                n=n, models=" e ".join(MODELLI[m] for m in modelli) if lang == "it" else
                " and ".join(MODELLI[m] for m in modelli)), tiles)}
            for m in modelli:
                compiti = r["modelli"][m]["compiti"]
                rows = sorted(((tx["tasks"][c], {k: v[k]["costo_totale"]["mediana"] for k in v})
                               for c, v in compiti.items() if len(v) == 3),  # solo compiti con le tre condizioni
                              key=lambda x: x[1]["tokyn"] / x[1]["agent-sdk"])
                files[f"costo-{m}-{lang}"] = cost_bars(t, lang, tx["cost_title"].format(model=MODELLI[m]),
                                                       tx["cost_sub"], rows)
            for name, svg in files.items():
                (OUT / f"{name}-{mode}.svg").write_text(svg, encoding="utf-8")
    print(f"grafici in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
