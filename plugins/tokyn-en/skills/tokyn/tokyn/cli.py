"""Riga di comando: tokyn check | build | run | spec | new."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__, lingua
from .compiler import check_source, compile_source, run_source
from .errors import TokynError, diagnostics_json, format_diagnostics
from .lingua import tr

TEMPLATE = '''# {name}.tokyn — creato con `tokyn new`

agent Assistente:
    model: "claude"
    instructions: "Rispondi in italiano, in modo breve e chiaro."

main:
    domanda = input("Domanda: ")
    print(Assistente.ask(domanda))
'''

TEMPLATE_EN = '''# {name}.tokyn — created with `tokyn new`

agent Assistant:
    model: "claude"
    instructions: "Answer in English, briefly and clearly."

main:
    question = input("Question: ")
    print(Assistant.ask(question))
'''


def _read(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(tr(f'errore: il file "{path}" non esiste', f'error: the file "{path}" does not exist'), file=sys.stderr)
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
        compiled = compile_source(source, args.file, standalone=args.standalone)
    except TokynError as err:
        print(err, file=sys.stderr)
        return 1
    out = args.output or str(Path(args.file).with_suffix(".py"))
    Path(out).write_text(compiled.python, encoding="utf-8")
    print(tr(f"scritto {out}", f"wrote {out}"))
    return 0


def cmd_run(args) -> int:
    source = _read(args.file)
    if args.backend:
        os.environ["TOKYN_BACKEND"] = args.backend
    try:
        return run_source(source, args.file, mock=args.mock)
    except TokynError as err:
        print(err, file=sys.stderr)
        return 1
    finally:
        if args.usage:
            from . import runtime
            print(runtime.usage_report(), file=sys.stderr)


def cmd_spec(args) -> int:
    print((Path(__file__).parent / tr("SPEC.md", "SPEC.en.md")).read_text(encoding="utf-8"))
    return 0


def cmd_new(args) -> int:
    path = Path(args.name if args.name.endswith(".tokyn") else args.name + ".tokyn")
    if path.exists():
        print(tr(f'errore: "{path}" esiste già', f'error: "{path}" already exists'), file=sys.stderr)
        return 1
    path.write_text(tr(TEMPLATE, TEMPLATE_EN).format(name=path.stem), encoding="utf-8")
    print(tr(f"creato {path}. Provalo con: tokyn run {path} --mock", f"created {path}. Try it with: tokyn run {path} --mock"))
    return 0


def _lang(argv) -> str | None:
    """Il valore di --lang (anche --lang=en): serve già per i testi dell'aiuto, prima di leggere gli argomenti."""
    value = None
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            value = argv[i + 1]
        elif a.startswith("--lang="):
            value = a.split("=", 1)[1]
    return value


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    lingua.imposta_opzione(_lang(argv))

    comuni = argparse.ArgumentParser(add_help=False)
    comuni.add_argument("--lang", choices=lingua.LINGUE, default=argparse.SUPPRESS,
                        help=tr("lingua dei messaggi (se non c'è la variabile TOKYN_LANG); di solito quella del sistema",
                                "language of the messages (unless TOKYN_LANG is set); by default the system's"))
    parser = argparse.ArgumentParser(prog="tokyn", description=tr("Tokyn: il linguaggio per agenti IA.", "Tokyn: the language for AI agents."),
                                     parents=[comuni])
    parser.add_argument("--version", action="version", version=f"tokyn {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", parents=[comuni], help=tr("controlla uno o più file e mostra gli errori",
                                                          "check one or more files and show the errors"))
    p.add_argument("files", nargs="+")
    p.add_argument("--json", action="store_true", help=tr("output in JSON (per IA e strumenti)", "output in JSON (for AI and tools)"))
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("build", parents=[comuni], help=tr("traduce in Python", "translate to Python"))
    p.add_argument("file")
    p.add_argument("-o", "--output")
    p.add_argument("--standalone", action="store_true",
                   help=tr("include il runtime nel file: non serve installare tokyn, solo anthropic",
                           "include the runtime in the file: no need to install tokyn, only anthropic"))
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("run", parents=[comuni], help=tr("esegue un programma", "run a program"))
    p.add_argument("file")
    p.add_argument("--mock", action="store_true", help=tr("risposte finte, senza chiamare l'IA", "fake answers, without calling the AI"))
    p.add_argument("--usage", action="store_true", help=tr("alla fine mostra i token spesi e quelli letti dalla cache",
                                                           "at the end show the tokens spent and those read from the cache"))
    p.add_argument("--backend", choices=["api", "claude-code"],
                   help=tr("chi risponde agli agenti (di solito si sceglie da solo: API con la chiave, altrimenti Claude Code)",
                           "who answers the agents (usually chosen automatically: the API with a key, otherwise Claude Code)"))
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("spec", parents=[comuni], help=tr("stampa la specifica del linguaggio (utile da dare a un'IA)",
                                                         "print the language specification (useful to give to an AI)"))
    p.set_defaults(func=cmd_spec)

    p = sub.add_parser("new", parents=[comuni], help=tr("crea un nuovo file di esempio", "create a new example file"))
    p.add_argument("name")
    p.set_defaults(func=cmd_new)

    args = parser.parse_args(argv)
    lingua.imposta_opzione(getattr(args, "lang", None))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
