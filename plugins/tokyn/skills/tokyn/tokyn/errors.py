"""Errori di Tokyn: pensati per essere letti e corretti da persone e da IA."""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field

from .lingua import tr


@dataclass
class Diagnostic:
    code: str
    message: str
    line: int = 0
    column: int = 0
    length: int = 1
    hint: str = ""
    severity: str = "errore"  # "errore" | "avviso"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": gravita(self.severity),
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "hint": self.hint,
        }


class TokynError(Exception):
    """Uno o più errori di compilazione."""

    def __init__(self, diagnostics: list[Diagnostic], source: str = "", filename: str = "<tokyn>"):
        self.diagnostics = diagnostics
        self.source = source
        self.filename = filename
        super().__init__(format_diagnostics(diagnostics, source, filename))


class TokynRuntimeError(Exception):
    """Errore durante l'esecuzione, già tradotto in un messaggio chiaro."""

    def __init__(self, message: str, line: int = 0, hint: str = ""):
        self.message = message
        self.line = line
        self.hint = hint
        self.bad_request = False  # l'API ha rifiutato i parametri della richiesta (errore 400)
        super().__init__(message)


def gravita(severity: str) -> str:
    """La gravità come si mostra: "errore" e "avviso" restano tali nel codice, in inglese diventano error e warning."""
    return tr(severity, {"errore": "error", "avviso": "warning"}.get(severity, severity))


def suggest(name: str, candidates) -> str | None:
    """Restituisce il candidato più simile, se abbastanza vicino."""
    matches = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.6)
    return matches[0] if matches else None


def did_you_mean(name: str, candidates, label: str = "") -> str:
    candidates = sorted(set(candidates))
    best = suggest(name, candidates)
    parts = []
    if best:
        parts.append(tr(f'Forse intendevi "{best}"?', f'Did you mean "{best}"?'))
    if candidates and label:
        shown = ", ".join(candidates[:12])
        if len(candidates) > 12:
            shown += ", …"
        parts.append(f"{label}: {shown}")
    return " ".join(parts)


def format_diagnostics(diagnostics: list[Diagnostic], source: str, filename: str) -> str:
    lines = source.splitlines()
    out = []
    for d in diagnostics:
        out.append(f"{filename}:{d.line}:{d.column} {gravita(d.severity)} {d.code}: {d.message}")
        if 1 <= d.line <= len(lines):
            src = lines[d.line - 1].rstrip()
            gutter = f"{d.line:>4} | "
            out.append(gutter + src)
            if d.column >= 1:
                pad = " " * (len(gutter) - 2) + "| " + " " * (d.column - 1)
                out.append(pad + "^" * max(1, min(d.length, max(1, len(src) - d.column + 1))))
        if d.hint:
            out.append(f"     → {d.hint}")
        out.append("")
    errors = sum(1 for d in diagnostics if d.severity == "errore")
    warnings = len(diagnostics) - errors
    summary = tr(f"{errors} errori" if errors != 1 else "1 errore", f"{errors} errors" if errors != 1 else "1 error")
    if warnings:
        summary += tr(f", {warnings} avvisi" if warnings != 1 else ", 1 avviso",
                      f", {warnings} warnings" if warnings != 1 else ", 1 warning")
    out.append(summary)
    return "\n".join(out)


def diagnostics_json(diagnostics: list[Diagnostic], filename: str) -> str:
    return json.dumps(
        {
            "file": filename,
            "ok": not any(d.severity == "errore" for d in diagnostics),
            "diagnostics": [d.to_dict() for d in diagnostics],
        },
        ensure_ascii=False,
        indent=2,
    )
