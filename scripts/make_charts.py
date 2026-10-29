"""Disegna i grafici del README (SVG, tema chiaro e scuro) a partire dai dati misurati.

Uso: python scripts/make_charts.py
Legge bench/claude-code/risultati.json e bench/results.json, scrive docs/grafici/*.svg.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "grafici"
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
WIDTH = 880

# Colori per ruolo (palette validata: blu d'accento per Tokyn, grigio per il confronto).
THEMES = {
    "light": {"surface": "#fcfcfb", "border": "rgba(11,11,11,0.10)", "ink": "#0b0b0b", "ink2": "#52514e",
              "muted": "#898781", "baseline": "#c3c2b7", "accent": "#2a78d6", "gray": "#8f8e88", "good": "#006300"},
    "dark": {"surface": "#1a1a19", "border": "rgba(255,255,255,0.10)", "ink": "#f0efec", "ink2": "#c3c2b7",
             "muted": "#898781", "baseline": "#383835", "accent": "#3987e5", "gray": "#6e6d68", "good": "#0ca30c"},
}
TASK_NAMES = {"recensioni": "Recensioni", "assistente": "Assistente clienti", "fattura": "Fattura",
              "email": "Email", "ristorante": "Prenotazioni", "traduttore": "Traduttore", "social": "Post social",
              "fatture": "Fatture"}


def num(value, decimals=0):
    """Numeri all'italiana: 6.931 e 0,61."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def card(t, height, title, subtitle, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" '
        f'font-family="{FONT}" role="img" aria-label="{title}">\n'
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="12" fill="{t["surface"]}" stroke="{t["border"]}"/>\n'
        f'<text x="28" y="40" font-size="18" font-weight="600" fill="{t["ink"]}">{title}</text>\n'
        f'<text x="28" y="62" font-size="13" fill="{t["ink2"]}">{subtitle}</text>\n'
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
        out.append(f'<text x="{cx + 16}" y="{y}" font-size="12" fill="{t["ink2"]}">{label}</text>')
        cx += 22 + len(label) * 6.6
    return "\n".join(out)


def grouped_bars(t, title, subtitle, rows, fmt, legend_items):
    """Una riga per compito, due barre (Tokyn in evidenza, Python in grigio), valore in punta e differenza a destra."""
    x0, right_pad = 200, 120
    scale = (WIDTH - x0 - right_pad - 70) / max(max(a, b) for _, a, b in rows)
    h, gap, group_gap = 18, 2, 26
    top = 108
    body = [legend(t, 28, 92, legend_items)]
    y = top
    for name, ours, theirs in rows:
        body.append(f'<text x="28" y="{y + h + 5}" font-size="13" fill="{t["ink"]}">{name}</text>')
        for i, (value, color) in enumerate([(ours, t["accent"]), (theirs, t["gray"])]):
            by = y + i * (h + gap)
            w = max(value * scale, 2)
            body.append(bar(x0, by, w, h, color))
            body.append(f'<text x="{x0 + w + 8:.1f}" y="{by + 13}" font-size="12" fill="{t["ink2"]}" '
                        f'font-variant-numeric="tabular-nums">{fmt(value)}</text>')
        saving = round((1 - ours / theirs) * 100)
        body.append(f'<text x="{WIDTH - 28}" y="{y + h + 5}" font-size="14" font-weight="600" text-anchor="end" '
                    f'fill="{t["good"]}">↓ {saving}%</text>')
        y += 2 * h + gap + group_gap
    body.insert(0, f'<line x1="{x0}" y1="{top - 6}" x2="{x0}" y2="{y - group_gap + 6}" stroke="{t["baseline"]}"/>')
    return card(t, y - group_gap + 34, title, subtitle, "\n".join(body) + "\n")


def kpi_row(t, tiles):
    """Riga di riquadri numerici: etichetta, valore grande, confronto."""
    n, pad, gap = len(tiles), 28, 16
    w = (WIDTH - 2 * pad - (n - 1) * gap) / n
    body = []
    for i, (label, value, detail) in enumerate(tiles):
        x = pad + i * (w + gap)
        body.append(f'<rect x="{x:.1f}" y="84" width="{w:.1f}" height="108" rx="10" fill="none" stroke="{t["border"]}"/>')
        body.append(f'<text x="{x + 16:.1f}" y="110" font-size="12" fill="{t["ink2"]}">{label}</text>')
        body.append(f'<text x="{x + 16:.1f}" y="152" font-size="34" font-weight="600" fill="{t["ink"]}">{value}</text>')
        body.append(f'<text x="{x + 16:.1f}" y="176" font-size="12" fill="{t["muted"]}">{detail}</text>')
    return card(t, 214, "Claude Code (Opus 5.5): tre programmi Python con agenti IA, con Tokyn e senza",
                "Sessioni reali, stesse richieste, nessuna chiave API. Con Tokyn Claude scrive in Tokyn e genera il Python.",
                "\n".join(body) + "\n")


def main():
    live = json.loads((ROOT / "bench" / "claude-code" / "risultati.json").read_text(encoding="utf-8"))["richieste"]
    bench = json.loads((ROOT / "bench" / "results.json").read_text(encoding="utf-8"))
    total = lambda key, field: sum(r[key][field] for r in live.values())
    cost_a, cost_b = total("con_tokyn", "costo_usd"), total("senza_tokyn", "costo_usd")
    out_a, out_b = total("con_tokyn", "token_output"), total("senza_tokyn", "token_output")
    sec_a, sec_b = total("con_tokyn", "secondi"), total("senza_tokyn", "secondi")
    tested_a = sum(r["con_tokyn"]["provato_con_ia_vera"] for r in live.values())
    tested_b = sum(r["senza_tokyn"]["provato_con_ia_vera"] for r in live.values())
    tiles = [
        ("Costo della sessione", f"−{round((1 - cost_a / cost_b) * 100)}%", f"${num(cost_a, 2)} invece di ${num(cost_b, 2)}"),
        ("Token di output", f"−{round((1 - out_a / out_b) * 100)}%", f"{num(out_a)} invece di {num(out_b)}"),
        ("Tempo", f"−{round((1 - sec_a / sec_b) * 100)}%", f"{sec_a} s invece di {sec_b} s"),
        ("Provati con l'IA vera", f"{tested_a} su {len(live)}", f"senza Tokyn: {tested_b} su {len(live)}"),
    ]
    cost_rows = [(TASK_NAMES[k], r["con_tokyn"]["costo_usd"], r["senza_tokyn"]["costo_usd"]) for k, r in live.items()]
    token_rows = [(TASK_NAMES[k], v["tokyn_sonnet"]["tokens"], v["python_libero"]["tokens"])
                  for k, v in bench["tasks"].items()]
    OUT.mkdir(parents=True, exist_ok=True)
    for mode, t in THEMES.items():
        files = {
            "numeri": kpi_row(t, tiles),
            "costo-claude-code": grouped_bars(
                t, "Costo della sessione in Claude Code, per programma",
                "Dollari a prezzi API, come riportati da Claude Code (Opus 5.5)", cost_rows,
                lambda v: f"${num(v, 2)}", [("Con Tokyn", t["accent"]), ("Senza Tokyn (Python)", t["gray"])]),
            "token-codice": grouped_bars(
                t, "Token del codice scritto da Claude, per programma",
                "Lo stesso compito in Tokyn e nel Python che Claude scrive di solito (benchmark in bench/)", token_rows,
                lambda v: num(v), [("Tokyn", t["accent"]), ("Python", t["gray"])]),
        }
        for name, svg in files.items():
            (OUT / f"{name}-{mode}.svg").write_text(svg, encoding="utf-8")
    print(f"grafici in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
