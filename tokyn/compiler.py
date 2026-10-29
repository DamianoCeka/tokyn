"""API di alto livello: controlla, compila ed esegue programmi Tokyn."""

from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass

from .checker import check
from .codegen import generate
from .errors import Diagnostic, TokynError, TokynRuntimeError
from .parser import parse


@dataclass
class CheckResult:
    diagnostics: list[Diagnostic]
    source: str
    filename: str

    @property
    def ok(self) -> bool:
        return not any(d.severity == "errore" for d in self.diagnostics)


@dataclass
class Compiled:
    python: str
    linemap: dict[int, int]
    diagnostics: list[Diagnostic]
    source: str
    filename: str


def check_source(source: str, filename: str = "<tokyn>") -> CheckResult:
    try:
        tree = parse(source, filename)
    except TokynError as err:
        return CheckResult(err.diagnostics, source, filename)
    _prog, diags = check(tree)
    return CheckResult(diags, source, filename)


def compile_source(source: str, filename: str = "<tokyn>", standalone: bool = False) -> Compiled:
    tree = parse(source, filename)
    prog, diags = check(tree)
    if any(d.severity == "errore" for d in diags):
        raise TokynError(diags, source, filename)
    code, linemap = generate(tree, prog, os.path.basename(filename), standalone)
    return Compiled(code, linemap, diags, source, filename)


def run_source(source: str, filename: str = "<tokyn>", mock: bool = False) -> int:
    """Esegue un programma. Restituisce il codice di uscita."""
    compiled = compile_source(source, filename)
    if mock:
        os.environ["TOKYN_MOCK"] = "1"
    pseudo = f"<tokyn:{filename}>"
    namespace = {"__name__": "__tokyn__", "__file__": filename}
    try:
        code = compile(compiled.python, pseudo, "exec")
        exec(code, namespace)
        namespace["__tokyn_main__"]()
        return 0
    except KeyboardInterrupt:
        print("\ninterrotto.", file=sys.stderr)
        return 130
    except BaseException as err:  # noqa: BLE001 - qui traduciamo ogni errore
        if isinstance(err, SystemExit):
            return int(err.code or 0)
        print(format_runtime_error(err, compiled, pseudo), file=sys.stderr)
        return 1


def _source_line(err: BaseException, compiled: Compiled, pseudo: str) -> int:
    line = 0
    for frame, lineno in traceback.walk_tb(err.__traceback__):
        if frame.f_code.co_filename == pseudo:
            # cerca la riga python mappata più vicina all'indietro
            for py in range(lineno, 0, -1):
                if py in compiled.linemap:
                    line = compiled.linemap[py]
                    break
    return line


def translate_exception(err: BaseException) -> tuple[str, str]:
    if isinstance(err, TokynRuntimeError):
        return err.message, err.hint
    if isinstance(err, KeyError):
        return f"la chiave {err.args[0]!r} non esiste nel dizionario", "Controlla il nome della chiave, oppure usa d.get(chiave)."
    if isinstance(err, IndexError):
        return "posizione fuori dalla lista", "Controlla la lunghezza con len(lista) prima di leggere un elemento."
    if isinstance(err, EOFError):
        return ("il programma aspetta un input (input()) ma non ne ha ricevuti",
                "Per provarlo senza tastiera passa le risposte una per riga, es.: "
                "printf 'ciao\\nesci\\n' | tokyn run file.tokyn --mock")
    if isinstance(err, ZeroDivisionError):
        return "divisione per zero", ""
    if isinstance(err, FileNotFoundError):
        return f"file non trovato: {err.filename}", ""
    if isinstance(err, ValueError):
        return f"valore non valido: {err}", ""
    if isinstance(err, TypeError):
        return f"tipo di dato non valido: {err}", "Controlla i tipi dei valori usati in questa riga (es. testo + numero)."
    if isinstance(err, AttributeError):
        return f"attributo inesistente: {err}", ""
    if isinstance(err, ModuleNotFoundError):
        return f"modulo Python non installato: {err.name}", f"Installalo con: pip install {err.name}"
    return f"{type(err).__name__}: {err}", ""


def format_runtime_error(err: BaseException, compiled: Compiled, pseudo: str) -> str:
    line = getattr(err, "line", 0) or _source_line(err, compiled, pseudo)
    message, hint = translate_exception(err)
    out = [f"{compiled.filename}:{line} errore di esecuzione: {message}"]
    src = compiled.source.splitlines()
    if 1 <= line <= len(src):
        out.append(f"{line:>4} | {src[line - 1].rstrip()}")
    if hint:
        out.append(f"     → {hint}")
    return "\n".join(out)
