"""Parser di Tokyn con messaggi d'errore di sintassi comprensibili."""

from __future__ import annotations

import re
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

from .errors import Diagnostic, TokynError
from .lingua import tr


class TokynIndenter(Indenter):
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
        postlex=TokynIndenter(),
        propagate_positions=True,
        maybe_placeholders=True,
        start=["start", "expr"],
    )


# Costrutti Python che Tokyn non ha, con l'alternativa da usare (in italiano e in inglese).
UNSUPPORTED = {
    "while": ("Tokyn ha un solo ciclo: usa `for i in range(n):` oppure `for x in lista:`.",
              "Tokyn has only one loop: use `for i in range(n):` or `for x in items:`."),
    "class": ("Per i dati usa `type Nome:` con i campi; per l'IA usa `agent Nome:`.",
              "For data use `type Name:` with its fields; for AI use `agent Name:`."),
    "lambda": ("Definisci una funzione con `def`.", "Define a function with `def`."),
    "try": ("In v0.1 non c'è try/except: il runtime gestisce i retry delle chiamate IA e mostra errori chiari.",
            "v0.1 has no try/except: the runtime retries the AI calls and shows clear errors."),
    "except": ("In v0.1 non c'è try/except.", "v0.1 has no try/except."),
    "with": ("In v0.1 non c'è `with`: usa read_file(percorso) e write_file(percorso, testo).",
             "v0.1 has no `with`: use read_file(path) and write_file(path, text)."),
    "async": ("Non serve async: le chiamate agli agenti sono gestite dal runtime.",
              "No need for async: the runtime handles the calls to agents."),
    "await": ("Non serve await: chiama direttamente `Agente.ask(testo)`.",
              "No need for await: call `Agent.ask(text)` directly."),
    "yield": ("Restituisci una lista con `return`.", "Return a list with `return`."),
    "global": ("Le variabili globali sono costanti: definiscile in cima al file.",
               "Global variables are constants: define them at the top of the file."),
    "match": ("Usa `if` / `elif` / `else`.", "Use `if` / `elif` / `else`."),
    "nonlocal": ("Le variabili di una funzione restano locali: restituisci il valore con `return`.",
                 "A function's variables stay local: return the value with `return`."),
    "del": ("Usa `d.pop(chiave)` per un dizionario e `lista.pop(i)` per una lista.",
            "Use `d.pop(key)` for a dict and `items.pop(i)` for a list."),
    "raise": ("Non si sollevano errori: in uno strumento restituisci un messaggio di errore come testo (l'IA lo legge), altrove stampalo e usa `return`.",
              "There are no exceptions to raise: in a tool return an error message as text (the AI reads it), elsewhere print it and use `return`."),
    "assert": ("Usa `if condizione:` con un messaggio e `return`.", "Use `if condition:` with a message and `return`."),
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
    "NAME": ("un nome", "a name"),
    "STRING": ("una stringa", "a string"),
    "FSTRING": ("una f-string", "an f-string"),
    "NUMBER": ("un numero", "a number"),
    "_NL": ("fine riga", "end of line"),
    "_INDENT": ("un blocco indentato", "an indented block"),
    "_DEDENT": ("fine del blocco", "end of block"),
    "$END": ("fine del file", "end of file"),
    "MORETHAN": "'>'",
    "RARROW": "'->'",
}


def _label(tok_type: str) -> str:
    if tok_type in TOKEN_LABELS:
        label = TOKEN_LABELS[tok_type]
        return tr(*label) if isinstance(label, tuple) else label
    if tok_type.isupper() and tok_type.isalpha():
        return f"'{tok_type.lower()}'"
    return tok_type


def _token_text(tok: Token) -> str:
    if tok.type == "_NL":
        return tr("fine riga", "end of line")
    if tok.type == "_INDENT":
        return tr("indentazione", "indentation")
    if tok.type == "_DEDENT":
        return tr("fine del blocco", "end of block")
    if tok.type == "$END":
        return tr("fine del file", "end of file")
    return str(tok)


def _syntax_diagnostic(err: UnexpectedInput, source: str) -> Diagnostic:
    line = getattr(err, "line", 0) or 0
    column = getattr(err, "column", 0) or 0

    if isinstance(err, UnexpectedCharacters):
        ch = source[err.pos_in_stream] if err.pos_in_stream < len(source) else "?"
        hint = ""
        if ch == "\t":
            hint = tr("Usa spazi per l'indentazione (4 per livello).", "Indent with spaces (4 per level).")
        elif ch in "@$`;":
            hint = tr(f"Il carattere '{ch}' non fa parte di Tokyn.", f"The character '{ch}' is not part of Tokyn.")
        return Diagnostic("E001", tr(f"carattere non valido '{ch}'", f"invalid character '{ch}'"), line, column, 1, hint)

    if isinstance(err, UnexpectedToken):
        tok = err.token
        if tok.type != "$END":
            line, column = tok.line or line, tok.column or column
        expected = set(err.expected or [])
        text = _token_text(tok)
        length = max(1, len(str(tok))) if tok.type not in ("_NL", "_INDENT", "_DEDENT", "$END") else 1

        src_lines = source.splitlines()

        line_text = src_lines[line - 1] if 1 <= line <= len(src_lines) else ""
        idiom = _python_idiom(tok, expected, line_text)
        if idiom:
            return Diagnostic("E002", idiom[0], line, column, length, idiom[1])
        if "COLON" in expected and tok.type == "_NL":
            return Diagnostic("E003", tr("manca ':' alla fine della riga", "missing ':' at the end of the line"), line, column, 1,
                              tr("Le righe con def, if, elif, else, for, agent, type e main finiscono con ':'.",
                                 "Lines with def, if, elif, else, for, agent, type and main end with ':'."))
        if "_INDENT" in expected or _after_colon_without_block(src_lines, line):
            return Diagnostic("E004", tr("manca il blocco indentato", "missing indented block"), line, 1, 1,
                              tr("Dopo una riga che finisce con ':' serve almeno una riga indentata di 4 spazi. Se il blocco è vuoto scrivi `pass`.",
                                 "A line ending with ':' needs at least one line indented by 4 spaces after it. If the block is empty write `pass`."))
        if tok.type == "_INDENT":
            line = _next_code_line(src_lines, line)
            return Diagnostic("E005", tr("indentazione inattesa", "unexpected indentation"), line, 1, 1,
                              tr("Questa riga è più indentata del necessario: allineala con la riga precedente.",
                                 "This line is indented more than needed: align it with the previous line."))
        if tok.type == "EQUAL" and "COLON" in expected:
            return Diagnostic("E006", tr("nei blocchi agent e type si usa ':' e non '='", "agent and type blocks use ':', not '='"),
                              line, column, 1, tr("Esempio: `instructions: \"...\"`.", "Example: `instructions: \"...\"`."))
        if tok.type in ("$END", "_DEDENT", "_NL"):
            closing = _unclosed_bracket(source, line, column)
            hint = tr(f"Manca {closing} per chiudere la parentesi aperta.", f"Missing {closing} to close the open bracket.") if closing else ""
            return Diagnostic("E007", tr(f"la riga finisce in modo incompleto (trovato: {text})", f"incomplete line (found: {text})"),
                              line, column, 1, hint)

        labels = sorted({_label(e) for e in expected if not e.startswith("__")})
        shown = ", ".join(labels[:8]) + (", …" if len(labels) > 8 else "")
        hint = tr(f"Qui mi aspettavo: {shown}.", f"Expected here: {shown}.") if labels else ""
        if tok.type == "STRING" and "COMMA" in expected:
            hint = tr("Forse manca una ',' tra due elementi.", "Maybe a ',' is missing between two items.")
        return Diagnostic("E008", tr(f"simbolo inatteso `{text}`", f"unexpected symbol `{text}`"), line, column, length, hint)

    if isinstance(err, UnexpectedEOF):
        return Diagnostic("E007", tr("il file finisce in modo incompleto", "the file ends before it is complete"), line, column, 1,
                          tr("Controlla parentesi e stringhe non chiuse.", "Check for unclosed brackets and strings."))

    return Diagnostic("E000", tr(f"errore di sintassi: {err}", f"syntax error: {err}"), line, column, 1)


def _python_idiom(tok: Token, expected: set, line_text: str) -> tuple[str, str] | None:
    """Riconosce i costrutti Python più comuni che Tokyn non ha e dice cosa scrivere al loro posto."""
    if re.search(r'(?<!\w)f"[^"\n]*\{[^}\n]*"', line_text) or re.search(r"(?<!\w)f'[^'\n]*\{[^}\n]*'", line_text):
        return (tr("dentro una f-string non si possono usare le stesse virgolette della f-string",
                   "inside an f-string you cannot use the same quotes as the f-string"),
                tr("Usa le virgolette dell'altro tipo dentro le graffe, es. f\"{d['chiave']}\".",
                   "Use the other kind of quotes inside the braces, e.g. f\"{d['key']}\"."))
    if expected == {"_NL"} and re.match(r"\s*(if|elif|else|for)\b[^#]*:\s*[^\s#]", line_text):
        return (tr("il blocco va sulla riga dopo i ':'", "the block goes on the line after ':'"),
                tr("Vai a capo dopo ':' e indenta il blocco di 4 spazi.", "Start a new line after ':' and indent the block by 4 spaces."))
    if tok.type == "NUMBER" and {"STRING", "NAME"} <= expected:
        return (tr("le scelte con `|` possono essere solo testi tra virgolette", "choices with `|` can only be quoted texts"),
                tr('Usa "1" | "2" | "3", oppure int con i limiti nella descrizione: priorita: int "da 1 a 3".',
                   'Use "1" | "2" | "3", or int with the limits in the description: priority: int "from 1 to 3".'))
    if tok.type == "FOR":
        return (tr("le comprehension `[... for x in ...]` non esistono in Tokyn",
                   "comprehensions `[... for x in ...]` do not exist in Tokyn"),
                tr("Usa un ciclo: risultato = [], poi `for x in lista:` e dentro `risultato.append(...)`.",
                   "Use a loop: result = [], then `for x in items:` and inside it `result.append(...)`."))
    if tok.type == "IF" and not expected <= {"COLON", "_NL"}:
        return (tr("l'espressione `a if condizione else b` non esiste in Tokyn",
                   "the expression `a if condition else b` does not exist in Tokyn"),
                tr("Scrivi un if/else su più righe che assegna la variabile in entrambi i rami.",
                   "Write an if/else on several lines that assigns the variable in both branches."))
    if tok.type == "NAME" and str(tok) == "is":
        return (tr("`is` non esiste in Tokyn", "`is` does not exist in Tokyn"),
                tr("Usa == e !=, es. `if x == None:` oppure `if x != None:`.", "Use == and !=, e.g. `if x == None:` or `if x != None:`."))
    if tok.type == "COMMA" and "EQUAL" in expected:
        return (tr("l'assegnazione multipla `a, b = ...` non esiste in Tokyn",
                   "multiple assignment `a, b = ...` does not exist in Tokyn"),
                tr("Assegna una variabile alla volta, es. `r = f()`, poi `a = r[0]` e `b = r[1]`.",
                   "Assign one variable at a time, e.g. `r = f()`, then `a = r[0]` and `b = r[1]`."))
    if tok.type == "COMMA" and expected == {"COLON"}:
        return (tr("i set `{a, b}` non esistono in Tokyn", "sets `{a, b}` do not exist in Tokyn"),
                tr("Usa una lista: `[a, b]` (per togliere i doppioni controlla con `in`).",
                   "Use a list: `[a, b]` (to skip duplicates check with `in`)."))
    if tok.type == "COMMA" and expected == {"RPAR"}:
        return (tr("le tuple `(a, b)` non esistono in Tokyn", "tuples `(a, b)` do not exist in Tokyn"),
                tr("Usa una lista: `[a, b]`.", "Use a list: `[a, b]`."))
    if tok.type == "COMMA" and line_text.lstrip().startswith("return "):
        return (tr("una funzione restituisce un solo valore", "a function returns a single value"),
                tr("Per restituirne più di uno usa una lista: `return [a, b]`.", "To return more than one, use a list: `return [a, b]`."))
    return None


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


def _lines_inside_strings(source: str) -> set[int]:
    """Righe che iniziano dentro una stringa tra virgolette triple: sono testo, non codice."""
    inside, line, i, quote = set(), 1, 0, None
    while i < len(source):
        c = source[i]
        if c == "\n":
            line += 1
            if quote in ('"""', "'''"):
                inside.add(line)
            elif quote:  # una stringa normale finisce con la riga
                quote = None
            i += 1
            continue
        if quote:
            if c == "\\" and source[i + 1:i + 2] != "\n":
                i += 2
                continue
            if source.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
        elif c == "#":
            while i < len(source) and source[i] != "\n":
                i += 1
            continue
        elif source.startswith('"""', i) or source.startswith("'''", i):
            quote = source[i:i + 3]
            i += 3
            continue
        elif c in "\"'":
            quote = c
        i += 1
    return inside


def _unsupported_scan(source: str) -> list[Diagnostic]:
    """Trova costrutti Python non presenti in Tokyn prima del parsing."""
    found = []
    text_lines = _lines_inside_strings(source)
    for i, raw in enumerate(source.splitlines(), 1):
        stripped = raw.lstrip()
        if i in text_lines or not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("def ") and raw[:1] in (" ", "\t"):
            col = len(raw) - len(stripped) + 1
            found.append(Diagnostic("E002", tr("una `def` dentro un'altra funzione o dentro main non esiste in Tokyn",
                                               "a `def` inside another function or inside main does not exist in Tokyn"), i, col, 3,
                                    tr("Definisci la funzione al livello del file, senza indentazione.",
                                       "Define the function at file level, without indentation.")))
            continue
        m = re.match(r"(\w+)\b(?!\s*[=.(\[,)])", stripped)
        word = m.group(1) if m else ""
        if word in UNSUPPORTED and word not in ("lambda", "await"):
            col = len(raw) - len(stripped) + 1
            found.append(Diagnostic("E002", tr(f"`{word}` non esiste in Tokyn", f"`{word}` does not exist in Tokyn"),
                                    i, col, len(word), tr(*UNSUPPORTED[word])))
            continue
        for kw in ("lambda", "await"):
            m2 = re.search(rf"\b{kw}\b(?!\s*[=.(\[,)])", raw)
            if m2 and not _inside_string(raw, m2.start()):
                found.append(Diagnostic("E002", tr(f"`{kw}` non esiste in Tokyn", f"`{kw}` does not exist in Tokyn"),
                                        i, m2.start() + 1, len(kw), tr(*UNSUPPORTED[kw])))
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


def parse(source: str, filename: str = "<tokyn>") -> Tree:
    if not source.endswith("\n"):
        source += "\n"
    unsupported = _unsupported_scan(source)
    if unsupported:
        raise TokynError(unsupported, source, filename)
    try:
        return _parser().parse(source, start="start")
    except UnexpectedInput as err:
        raise TokynError([_syntax_diagnostic(err, source)], source, filename) from None
    except DedentError as err:
        line = _dedent_line(str(err), source)
        raise TokynError(
            [Diagnostic("E009", tr("indentazione non coerente", "inconsistent indentation"), line, 1, 1,
                        tr("Ogni livello di blocco deve avere la stessa indentazione (4 spazi). Non mescolare tab e spazi.",
                           "Every block level must have the same indentation (4 spaces). Do not mix tabs and spaces."))],
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
