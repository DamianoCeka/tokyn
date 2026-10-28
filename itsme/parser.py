"""Parser di Itsme con messaggi d'errore di sintassi comprensibili."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from lark import Lark, Token, Tree
from lark.exceptions import (
    UnexpectedCharacters,
    UnexpectedEOF,
    UnexpectedInput,
    UnexpectedToken,
)
from lark.indenter import DedentError, Indenter

from .errors import Diagnostic, ItsmeError


class ItsmeIndenter(Indenter):
    NL_type = "_NL"
    OPEN_PAREN_types = ["LPAR", "LSQB", "LBRACE"]
    CLOSE_PAREN_types = ["RPAR", "RSQB", "RBRACE"]
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 4


@lru_cache(maxsize=1)
def _parser() -> Lark:
    grammar = (Path(__file__).parent / "grammar.lark").read_text(encoding="utf-8")
    return Lark(
        grammar,
        parser="lalr",
        postlex=ItsmeIndenter(),
        propagate_positions=True,
        maybe_placeholders=True,
        start=["start", "expr"],
    )


# Costrutti Python che Itsme non ha, con l'alternativa da usare.
UNSUPPORTED = {
    "while": "Itsme ha un solo ciclo: usa `for i in range(n):` oppure `for x in lista:`.",
    "class": "Per i dati usa `type Nome:` con i campi; per l'IA usa `agent Nome:`.",
    "lambda": "Definisci una funzione con `def`.",
    "try": "In v0.1 non c'è try/except: il runtime gestisce i retry delle chiamate IA e mostra errori chiari.",
    "except": "In v0.1 non c'è try/except.",
    "with": "In v0.1 non c'è `with`: usa read_file(percorso) e write_file(percorso, testo).",
    "async": "Non serve async: le chiamate agli agenti sono gestite dal runtime.",
    "await": "Non serve await: chiama direttamente `Agente.ask(testo)`.",
    "yield": "Restituisci una lista con `return`.",
    "global": "Le variabili globali sono costanti: definiscile in cima al file.",
    "match": "Usa `if` / `elif` / `else`.",
}

TOKEN_LABELS = {
    "COLON": "':'",
    "LPAR": "'('",
    "RPAR": "')'",
    "LSQB": "'['",
    "RSQB": "']'",
    "LBRACE": "'{'",
    "RBRACE": "'}'",
    "COMMA": "','",
    "EQUAL": "'='",
    "DOT": "'.'",
    "NAME": "un nome",
    "STRING": "una stringa",
    "FSTRING": "una f-string",
    "NUMBER": "un numero",
    "_NL": "fine riga",
    "_INDENT": "un blocco indentato",
    "_DEDENT": "fine del blocco",
    "$END": "fine del file",
    "MORETHAN": "'>'",
    "RARROW": "'->'",
}


def _label(tok_type: str) -> str:
    if tok_type in TOKEN_LABELS:
        return TOKEN_LABELS[tok_type]
    if tok_type.isupper() and tok_type.isalpha():
        return f"'{tok_type.lower()}'"
    return tok_type


def _token_text(tok: Token) -> str:
    if tok.type == "_NL":
        return "fine riga"
    if tok.type == "_INDENT":
        return "indentazione"
    if tok.type == "_DEDENT":
        return "fine del blocco"
    if tok.type == "$END":
        return "fine del file"
    return str(tok)


def _syntax_diagnostic(err: UnexpectedInput, source: str) -> Diagnostic:
    line = getattr(err, "line", 0) or 0
    column = getattr(err, "column", 0) or 0

    if isinstance(err, UnexpectedCharacters):
        ch = source[err.pos_in_stream] if err.pos_in_stream < len(source) else "?"
        hint = ""
        if ch == "\t":
            hint = "Usa spazi per l'indentazione (4 per livello)."
        elif ch in "@$`;":
            hint = f"Il carattere '{ch}' non fa parte di Itsme."
        return Diagnostic("E001", f"carattere non valido '{ch}'", line, column, 1, hint)

    if isinstance(err, UnexpectedToken):
        tok = err.token
        if tok.type != "$END":
            line, column = tok.line or line, tok.column or column
        expected = set(err.expected or [])
        text = _token_text(tok)
        length = max(1, len(str(tok))) if tok.type not in ("_NL", "_INDENT", "_DEDENT", "$END") else 1

        src_lines = source.splitlines()

        if "COLON" in expected and tok.type == "_NL":
            return Diagnostic("E003", "manca ':' alla fine della riga", line, column, 1,
                              "Le righe con def, if, elif, else, for, agent, type e main finiscono con ':'.")
        if "_INDENT" in expected or _after_colon_without_block(src_lines, line):
            return Diagnostic("E004", "manca il blocco indentato", line, 1, 1,
                              "Dopo una riga che finisce con ':' serve almeno una riga indentata di 4 spazi. Se il blocco è vuoto scrivi `pass`.")
        if tok.type == "_INDENT":
            line = _next_code_line(src_lines, line)
            return Diagnostic("E005", "indentazione inattesa", line, 1, 1,
                              "Questa riga è più indentata del necessario: allineala con la riga precedente.")
        if tok.type == "EQUAL" and "COLON" in expected:
            return Diagnostic("E006", "nei blocchi agent e type si usa ':' e non '='", line, column, 1,
                              "Esempio: `instructions: \"...\"`.")
        if tok.type in ("$END", "_DEDENT", "_NL"):
            closing = _unclosed_bracket(source, line, column)
            hint = f"Manca {closing} per chiudere la parentesi aperta." if closing else ""
            return Diagnostic("E007", f"la riga finisce in modo incompleto (trovato: {text})", line, column, 1, hint)

        labels = sorted({_label(e) for e in expected if not e.startswith("__")})
        shown = ", ".join(labels[:8]) + (", …" if len(labels) > 8 else "")
        hint = f"Qui mi aspettavo: {shown}." if labels else ""
        if tok.type == "STRING" and "COMMA" in expected:
            hint = "Forse manca una ',' tra due elementi."
        return Diagnostic("E008", f"simbolo inatteso `{text}`", line, column, length, hint)

    if isinstance(err, UnexpectedEOF):
        return Diagnostic("E007", "il file finisce in modo incompleto", line, column, 1,
                          "Controlla parentesi e stringhe non chiuse.")

    return Diagnostic("E000", f"errore di sintassi: {err}", line, column, 1)


def _code_lines(src_lines):
    for i, raw in enumerate(src_lines, 1):
        s = raw.strip()
        if s and not s.startswith("#"):
            yield i, raw


def _indent(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" \t"))


def _after_colon_without_block(src_lines, line: int) -> bool:
    prev = None
    for i, raw in _code_lines(src_lines):
        if i >= line:
            if prev is None or i != line:
                return False
            return prev[1].rstrip().endswith(":") and _indent(raw) <= _indent(prev[1])
        prev = (i, raw)
    return False


def _next_code_line(src_lines, line: int) -> int:
    for i, _ in _code_lines(src_lines):
        if i > line:
            return i
    return line


def _unclosed_bracket(source: str, line: int, column: int) -> str:
    """Trova la parentesi rimasta aperta prima della posizione dell'errore."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = []
    lines = source.splitlines(keepends=True)
    upto = sum(len(l) for l in lines[: max(0, line - 1)]) + max(0, column - 1)
    i, quote = 0, None
    text = source[:upto] if upto > 0 else source
    while i < len(text):
        c = text[i]
        if quote:
            if text.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
            if c == "\\":
                i += 2
                continue
        elif c == "#":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif text.startswith('"""', i) or text.startswith("'''", i):
            quote = text[i:i + 3]
            i += 3
            continue
        elif c in "\"'":
            quote = c
        elif c in pairs:
            stack.append(c)
        elif c in pairs.values() and stack:
            stack.pop()
        i += 1
    return f"'{pairs[stack[-1]]}'" if stack else ""


def _unsupported_scan(source: str) -> list[Diagnostic]:
    """Trova costrutti Python non presenti in Itsme prima del parsing."""
    import re

    found = []
    for i, raw in enumerate(source.splitlines(), 1):
        stripped = raw.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"(\w+)\b(?!\s*[=.(\[,)])", stripped)
        word = m.group(1) if m else ""
        if word in UNSUPPORTED and word not in ("lambda", "await"):
            col = len(raw) - len(stripped) + 1
            found.append(Diagnostic("E002", f"`{word}` non esiste in Itsme", i, col, len(word), UNSUPPORTED[word]))
            continue
        for kw in ("lambda", "await"):
            m2 = re.search(rf"\b{kw}\b(?!\s*[=.(\[,)])", raw)
            if m2 and not _inside_string(raw, m2.start()):
                found.append(Diagnostic("E002", f"`{kw}` non esiste in Itsme", i, m2.start() + 1, len(kw), UNSUPPORTED[kw]))
    return found


def _inside_string(raw: str, pos: int) -> bool:
    quote = None
    for c in raw[:pos]:
        if quote:
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "#":
            return True
    return quote is not None


def parse(source: str, filename: str = "<itsme>") -> Tree:
    if not source.endswith("\n"):
        source += "\n"
    unsupported = _unsupported_scan(source)
    if unsupported:
        raise ItsmeError(unsupported, source, filename)
    try:
        return _parser().parse(source, start="start")
    except UnexpectedInput as err:
        raise ItsmeError([_syntax_diagnostic(err, source)], source, filename) from None
    except DedentError as err:
        line = _dedent_line(str(err), source)
        raise ItsmeError(
            [Diagnostic("E009", "indentazione non coerente", line, 1, 1,
                        "Ogni livello di blocco deve avere la stessa indentazione (4 spazi). Non mescolare tab e spazi.")],
            source, filename,
        ) from None


def _dedent_line(msg: str, source: str) -> int:
    # Lark non dà la riga: cerco la prima riga con indentazione non multipla di 4.
    for i, raw in enumerate(source.splitlines(), 1):
        stripped = raw.lstrip(" ")
        if stripped and not stripped.startswith("#"):
            indent = len(raw) - len(stripped)
            if indent % 4:
                return i
    return 0


def parse_expr(text: str) -> Tree:
    """Analizza una singola espressione (usato per le f-string)."""
    return _parser().parse(text, start="expr")
