"""Confronta i token necessari per scrivere lo stesso programma in Tokyn e in Python.

Uso:
    python bench/count_tokens.py --tokenizer percorso/tokenizer.json

Il tokenizer è quello di Claude incluso nel pacchetto `anthropic==0.34.2`
(file anthropic/tokenizer.json). È il tokenizer dei modelli Claude precedenti:
i valori assoluti possono differire da quelli dei modelli attuali, ma il
rapporto tra i due linguaggi resta indicativo.

Le righe di solo commento sono escluse in entrambi i linguaggi; le descrizioni
degli strumenti (docstring) restano, perché servono al programma.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parent
TASKS = ["email", "ristorante", "traduttore", "social", "fatture"]
SETS = {
    "tokyn_sonnet": ("tokyn", "programs/tokyn_sonnet", ".tokyn"),
    "tokyn_haiku": ("tokyn", "programs/tokyn_haiku", ".tokyn"),
    "python_sdk": ("python", "programs/python_sdk", ".py"),
    "python_pydantic_ai": ("python", "programs/python_pydantic_ai", ".py"),
    "python_libero": ("python", "programs/python_libero", ".py"),
}


def strip_comments(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("#")).strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--json", help="salva i risultati in questo file")
    args = ap.parse_args()
    tok = Tokenizer.from_file(args.tokenizer)
    count = lambda s: len(tok.encode(s).ids)

    results = {"tasks": {}, "totals": {}, "fixed": {}}
    for task in TASKS:
        row = {}
        for name, (_lang, folder, ext) in SETS.items():
            path = ROOT / folder / f"{task}{ext}"
            text = strip_comments(path.read_text(encoding="utf-8"))
            row[name] = {"tokens": count(text), "lines": len([l for l in text.splitlines() if l.strip()])}
        results["tasks"][task] = row
    for name in SETS:
        results["totals"][name] = {
            "tokens": sum(results["tasks"][t][name]["tokens"] for t in TASKS),
            "lines": sum(results["tasks"][t][name]["lines"] for t in TASKS),
        }
    repo = ROOT.parent
    results["fixed"]["SKILL.md"] = count((repo / "skill/tokyn/SKILL.md").read_text(encoding="utf-8"))
    results["fixed"]["SPEC.md"] = count((repo / "tokyn/SPEC.md").read_text(encoding="utf-8"))

    header = f"{'compito':<12}" + "".join(f"{n:>20}" for n in SETS)
    print(header)
    for task in TASKS:
        print(f"{task:<12}" + "".join(f"{results['tasks'][task][n]['tokens']:>20}" for n in SETS))
    print(f"{'TOTALE':<12}" + "".join(f"{results['totals'][n]['tokens']:>20}" for n in SETS))
    print("\nrighe:      " + "".join(f"{results['totals'][n]['lines']:>20}" for n in SETS))
    print(f"\ncosto fisso della Skill (lettura): SKILL.md {results['fixed']['SKILL.md']} token "
          f"(SPEC.md {results['fixed']['SPEC.md']}, letta solo per dettagli rari)")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
