"""Riga di comando: tokyn check | build | run | spec | new."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .compiler import check_source, compile_source, run_source
from .errors import TokynError, diagnostics_json, format_diagnostics

TEMPLATE = '''# {name}.tokyn — creato con `tokyn new`

agent Assistente:
    model: "claude"
    instructions: "Rispondi in italiano, in modo breve e chiaro."

main:
    domanda = input("Domanda: ")
    print(Assistente.ask(domanda))
'''


def _read(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f'errore: il file "{path}" non esiste', file=sys.stderr)
        sys.exit(2)
    return p.read_text(encoding="utf-8")


def cmd_check(args) -> int:
    worst = 0
    for path in args.files:
        result = check_source(_read(path), path)
        if args.json:
            print(diagnostics_json(result.diagnostics, path))
        elif result.diagnostics:
            print(format_diagnostics(result.diagnostics, result.source, path))
        else:
            print(f"{path}: ok ✓")
        if not result.ok:
            worst = 1
    return worst


def cmd_build(args) -> int:
    source = _read(args.file)
    try:
        compiled = compile_source(source, args.file)
    except TokynError as err:
        print(err, file=sys.stderr)
        return 1
    out = args.output or str(Path(args.file).with_suffix(".py"))
    Path(out).write_text(compiled.python, encoding="utf-8")
    print(f"scritto {out}")
    return 0


def cmd_run(args) -> int:
    source = _read(args.file)
    try:
        return run_source(source, args.file, mock=args.mock)
    except TokynError as err:
        print(err, file=sys.stderr)
        return 1


def cmd_spec(args) -> int:
    print((Path(__file__).parent / "SPEC.md").read_text(encoding="utf-8"))
    return 0


def cmd_new(args) -> int:
    path = Path(args.name if args.name.endswith(".tokyn") else args.name + ".tokyn")
    if path.exists():
        print(f'errore: "{path}" esiste già', file=sys.stderr)
        return 1
    path.write_text(TEMPLATE.format(name=path.stem), encoding="utf-8")
    print(f"creato {path}. Provalo con: tokyn run {path} --mock")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tokyn", description="Tokyn: il linguaggio per agenti IA.")
    parser.add_argument("--version", action="version", version=f"tokyn {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="controlla uno o più file e mostra gli errori")
    p.add_argument("files", nargs="+")
    p.add_argument("--json", action="store_true", help="output in JSON (per IA e strumenti)")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("build", help="traduce in Python")
    p.add_argument("file")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("run", help="esegue un programma")
    p.add_argument("file")
    p.add_argument("--mock", action="store_true", help="risposte finte, senza chiamare l'IA")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("spec", help="stampa la specifica del linguaggio (utile da dare a un'IA)")
    p.set_defaults(func=cmd_spec)

    p = sub.add_parser("new", help="crea un nuovo file di esempio")
    p.add_argument("name")
    p.set_defaults(func=cmd_new)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
