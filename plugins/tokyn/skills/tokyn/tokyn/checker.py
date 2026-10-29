"""Controlli statici di Tokyn.

Obiettivo: trovare prima dell'esecuzione tutti gli errori che un'IA (o una persona)
fa più spesso, e spiegare esattamente come correggerli.
"""

from __future__ import annotations

import ast
import re
import warnings
from dataclasses import dataclass, field

from lark import Token, Tree

from .errors import Diagnostic, did_you_mean, suggest
from .lingua import tr
from .parser import parse_expr

# ---------------------------------------------------------------- tipi statici

ANY = ("any",)
STR = ("str",)
INT = ("int",)
FLOAT = ("float",)
BOOL = ("bool",)
NONE = ("none",)
DICT = ("dict",)


def LIST(elem=ANY):
    return ("list", elem)


PRIMITIVES = {"str": STR, "int": INT, "float": FLOAT, "bool": BOOL, "dict": DICT}

AGENT_FIELDS = {
    "model": "nome del modello: \"claude\", \"claude-opus\", \"claude-haiku\", \"mock\" o un id completo",
    "instructions": "le istruzioni (system prompt) dell'agente",
    "tools": "lista di funzioni (def) o di altri agenti che l'agente può usare",
    "output": "nome di un `type`: l'agente risponde con dati strutturati invece che testo",
    "memory": "True per ricordare la conversazione tra una ask e l'altra",
    "max_steps": "numero massimo di passaggi (chiamate a strumenti) per ogni ask",
    "effort": "quanto ragiona l'IA: \"low\", \"medium\", \"high\", \"xhigh\" o \"max\"",
}

AGENT_METHODS = {"ask": (1, 1), "ask_all": (1, 1), "reset": (0, 0)}
EFFORTS = ("low", "medium", "high", "xhigh", "max")

# nome -> (min argomenti posizionali, max o None, tipo restituito)
BUILTINS = {
    "print": (0, None, NONE),
    "len": (1, 1, INT),
    "str": (0, 1, STR),
    "int": (0, 2, INT),
    "float": (0, 1, FLOAT),
    "bool": (0, 1, BOOL),
    "list": (0, 1, LIST()),
    "dict": (0, None, DICT),
    "range": (1, 3, LIST(INT)),
    "enumerate": (1, 2, LIST()),
    "zip": (1, None, LIST()),
    "sum": (1, 2, ANY),
    "min": (1, None, ANY),
    "max": (1, None, ANY),
    "sorted": (1, 1, LIST()),
    "reversed": (1, 1, LIST()),
    "abs": (1, 1, ANY),
    "round": (1, 2, ANY),
    "any": (1, 1, BOOL),
    "all": (1, 1, BOOL),
    "input": (0, 1, STR),
    "read_file": (1, 2, STR),
    "write_file": (2, 2, NONE),
    "append_file": (2, 2, NONE),
    "http_get": (1, 2, STR),
    "http_post": (2, 3, STR),
    "json_parse": (1, 2, ANY),
    "to_number": (1, 2, ANY),
    "json_dump": (1, 1, STR),
    "env": (1, 2, STR),
    "now": (0, 0, STR),
    "sleep": (1, 1, NONE),
}

STR_METHODS = {m for m in dir(str) if not m.startswith("_")}
LIST_METHODS = {m for m in dir(list) if not m.startswith("_")}
DICT_METHODS = {m for m in dir(dict) if not m.startswith("_")}

PREC = {"or_": 1, "and_": 2, "not_": 3, "comparison": 4, "arith": 5, "term": 6, "unary": 7, "pow": 7.5}


def type_name(t) -> str:
    kind = t[0]
    if kind == "list":
        return f"list[{type_name(t[1])}]"
    if kind == "record":
        return t[1]
    if kind == "enum":
        return " | ".join(f'"{v}"' for v in t[1])
    if kind == "agent":
        return f"agent {t[1]}"
    if kind == "func":
        return tr(f"funzione {t[1]}", f"function {t[1]}")
    if kind == "typeobj":
        return f"type {t[1]}"
    return kind


# ---------------------------------------------------------------- simboli


@dataclass
class TypeInfo:
    name: str
    fields: dict  # nome -> tipo statico
    line: int


@dataclass
class FuncInfo:
    name: str
    params: list  # [(nome, tipo|None, ha_default)]
    returns: tuple
    docstring: str | None
    node: Tree
    line: int


@dataclass
class AgentInfo:
    name: str
    output: str | None
    node: Tree
    line: int
    fields: dict = field(default_factory=dict)
    agent_tools: list = field(default_factory=list)  # altri agenti a cui delega


@dataclass
class Program:
    """Risultato del controllo: usato anche dal generatore di codice."""

    types: dict = field(default_factory=dict)
    funcs: dict = field(default_factory=dict)
    agents: dict = field(default_factory=dict)
    consts: dict = field(default_factory=dict)
    imports: dict = field(default_factory=dict)
    main: Tree | None = None
    tool_funcs: set = field(default_factory=set)


def tok_text(tok) -> str:
    return str(tok)


def pos(node) -> tuple[int, int, int]:
    if isinstance(node, Token):
        return node.line or 0, node.column or 0, max(1, len(str(node)))
    meta = getattr(node, "meta", None)
    if meta is not None and not getattr(meta, "empty", True):
        length = 1
        if getattr(meta, "end_line", None) == meta.line:
            length = max(1, meta.end_column - meta.column)
        return meta.line, meta.column, length
    for child in getattr(node, "children", []):
        if child is not None:
            p = pos(child)
            if p[0]:
                return p
    return 0, 0, 1


def type_name_token(tree: Tree, type_name: str):
    """Il nome di un type nella sua definizione, per posizionare l'errore."""
    for node in tree.children:
        if isinstance(node, Tree) and node.data == "type_def" and str(node.children[0]) == type_name:
            return node.children[0]
    return None


def string_value(tok: Token) -> str:
    try:
        with warnings.catch_warnings():  # es. "\d" in una descrizione: resta com'è, senza avvisi di Python
            warnings.simplefilter("ignore")
            return ast.literal_eval(str(tok))
    except (ValueError, SyntaxError):
        return str(tok).strip("\"'")


# ---------------------------------------------------------------- checker


class Checker:
    def __init__(self, tree: Tree):
        self.tree = tree
        self.diags: list[Diagnostic] = []
        self.prog = Program()
        self.global_names: dict[str, tuple] = {}

    # -- utilità
    def error(self, code, message, node, hint=""):
        line, col, length = pos(node)
        self.diags.append(Diagnostic(code, message, line, col, length, hint))

    def warn(self, code, message, node, hint=""):
        line, col, length = pos(node)
        self.diags.append(Diagnostic(code, message, line, col, length, hint, severity="avviso"))

    # -- ingresso
    def run(self) -> tuple[Program, list[Diagnostic]]:
        self.collect()
        self.check_types()
        self.check_agents()
        self.check_agent_cycles()
        self.check_funcs()
        self.check_consts()
        self.check_main()
        self.diags.sort(key=lambda d: (d.line, d.column))
        return self.prog, self.diags

    # ------------------------------------------------------------ raccolta
    def declare(self, name_tok: Token, kind: tuple):
        name = str(name_tok)
        if name in self.global_names:
            self.error("E101", tr(f'"{name}" è già definito', f'"{name}" is already defined'), name_tok,
                       tr("Ogni funzione, agente, type e costante deve avere un nome diverso.",
                          "Every function, agent, type and constant needs a different name."))
            return False
        if name in BUILTINS and kind[0] != "module":
            self.error("E102", tr(f'"{name}" è il nome di una funzione già presente in Tokyn',
                                  f'"{name}" is the name of a function built into Tokyn'), name_tok,
                       tr("Scegli un altro nome.", "Choose another name."))
            return False
        self.global_names[name] = kind
        return True

    def collect(self):
        mains = []
        for node in self.tree.children:
            if not isinstance(node, Tree):
                continue
            kind = node.data
            if kind == "import_plain":
                dotted, alias = node.children
                name_tok = alias if alias is not None else dotted.children[0]
                if self.declare(name_tok, ("module",)):
                    self.prog.imports[str(name_tok)] = node
            elif kind == "import_from":
                for imp in node.children[1:]:
                    tok = imp.children[1] if imp.children[1] is not None else imp.children[0]
                    if self.declare(tok, ANY):
                        self.prog.imports[str(tok)] = node
            elif kind == "type_def":
                name_tok = node.children[0]
                if self.declare(name_tok, ("typeobj", str(name_tok))):
                    self.prog.types[str(name_tok)] = TypeInfo(str(name_tok), {}, name_tok.line)
            elif kind == "def_stmt":
                name_tok = node.children[0]
                if self.declare(name_tok, ("func", str(name_tok))):
                    self.prog.funcs[str(name_tok)] = FuncInfo(str(name_tok), [], ANY, None, node, name_tok.line)
            elif kind == "agent_def":
                name_tok = node.children[0]
                if self.declare(name_tok, ("agent", str(name_tok))):
                    self.prog.agents[str(name_tok)] = AgentInfo(str(name_tok), None, node, name_tok.line)
            elif kind == "const_def":
                name_tok = node.children[0]
                if self.declare(name_tok, ANY):
                    self.prog.consts[str(name_tok)] = node
            elif kind == "main_def":
                mains.append(node)

        if len(mains) > 1:
            self.error("E103", tr("c'è più di un blocco main", "there is more than one main block"), mains[1],
                       tr("Un file può avere un solo `main:`.", "A file can have only one `main:`."))
        if mains:
            self.prog.main = mains[0]

        # firme delle funzioni (servono prima di controllare i corpi)
        for info in self.prog.funcs.values():
            self.read_signature(info)

    # ------------------------------------------------------------ tipi
    def resolve_type(self, texpr: Tree, allow_literals=True):
        atoms = texpr.children
        if len(atoms) > 1 or atoms[0].data == "type_literal":
            values = []
            for atom in atoms:
                if atom.data != "type_literal":
                    self.error("E111", tr("un'unione con '|' può contenere solo stringhe tra virgolette",
                                          "a union with '|' can only contain quoted strings"), atom,
                               tr('Esempio: categoria: "tecnico" | "commerciale" | "altro"',
                                  'Example: category: "technical" | "sales" | "other"'))
                    return ANY
                values.append(string_value(atom.children[0]))
            if not allow_literals:
                return STR
            if len(set(values)) != len(values):
                self.error("E112", tr("valori ripetuti nell'unione", "repeated values in the union"), texpr)
            return ("enum", tuple(values))

        name_tok, inner = atoms[0].children
        name = str(name_tok)
        if name == "list":
            if inner is None:
                return LIST()
            return LIST(self.resolve_type(inner))
        if inner is not None:
            self.error("E113", tr(f"solo list accetta un tipo tra [ ], non {name}", f"only list takes a type in [ ], not {name}"),
                       atoms[0], tr("Esempio: list[str]", "Example: list[str]"))
        if name in PRIMITIVES:
            return PRIMITIVES[name]
        if name in self.prog.types:
            return ("record", name)
        known = list(PRIMITIVES) + ["list"] + list(self.prog.types)
        hint = did_you_mean(name, known, tr("Tipi disponibili", "Available types"))
        if name in ("string", "integer", "number", "boolean", "String", "Int", "Bool"):
            hint = tr(f"{hint}. I tipi base sono str, int, float, bool.", f"{hint}. The basic types are str, int, float, bool.")
        self.error("E110", tr(f'tipo "{name}" sconosciuto', f'unknown type "{name}"'), name_tok, hint)
        return ANY

    def check_types(self):
        for node in self.tree.children:
            if not (isinstance(node, Tree) and node.data == "type_def"):
                continue
            info = self.prog.types.get(str(node.children[0]))
            if info is None:
                continue
            for fd in node.children[1:]:
                fname, texpr, _desc = fd.children
                if str(fname) in info.fields:
                    self.error("E114", tr(f'il campo "{fname}" è ripetuto', f'the field "{fname}" is repeated'), fname)
                    continue
                info.fields[str(fname)] = self.resolve_type(texpr)
        self.check_recursive_types()

    def check_recursive_types(self):
        def refs(t):
            if t[0] == "record":
                return {t[1]}
            return refs(t[1]) if t[0] == "list" else set()

        def reaches(start, target, seen):
            for t in self.prog.types[start].fields.values():
                for name in refs(t):
                    if name == target or (name not in seen and reaches(name, target, seen | {name})):
                        return True
            return False

        for name, info in self.prog.types.items():
            if reaches(name, name, {name}):
                self.error("E115", tr(f'il type "{name}" contiene se stesso, anche passando da altri type',
                                      f'the type "{name}" contains itself, directly or through other types'),
                           type_name_token(self.tree, name),
                           tr("I type non possono essere ricorsivi: collega gli elementi con un nome o un id (str), oppure usa dict.",
                              "Types cannot be recursive: link the items by a name or an id (str), or use dict."))

    # ------------------------------------------------------------ funzioni
    def read_signature(self, info: FuncInfo):
        name_tok, params, ret, suite = info.node.children
        seen = set()
        default_seen = False
        if params is not None:
            for p in params.children:
                if p is None:
                    continue
                pname, ptype, pdefault = p.children
                if str(pname) in seen:
                    self.error("E120", tr(f'parametro "{pname}" ripetuto', f'repeated parameter "{pname}"'), pname)
                seen.add(str(pname))
                if pdefault is None and default_seen:
                    self.error("E123", tr("i parametri senza valore predefinito vanno prima di quelli con valore predefinito",
                                          "parameters without a default value go before those with one"), pname)
                default_seen = default_seen or pdefault is not None
                info.params.append((str(pname), ptype, pdefault is not None))
        info.returns = self.resolve_type(ret) if ret is not None else ANY
        first = suite.children[0] if suite.children else None
        if (isinstance(first, Tree) and first.data == "expr_stmt"
                and isinstance(first.children[0], Tree) and first.children[0].data == "string"):
            info.docstring = string_value(first.children[0].children[0]).strip()

    def check_funcs(self):
        for name, info in self.prog.funcs.items():
            name_tok, params, ret, suite = info.node.children
            scope = Scope(self, kind="def", func=info)
            resolved = []
            for pname, ptype, has_default in info.params:
                t = self.resolve_type(ptype) if ptype is not None else ANY
                resolved.append((pname, t, has_default))
                scope.define(pname, t)
            info.params = resolved
            defaults = Scope(self, kind="default")
            defaults.before_line = info.line
            for p in (params.children if params is not None else []):
                if p is not None and p.children[2] is not None:
                    self.infer(p.children[2], defaults)
            if name in self.prog.tool_funcs:
                if not info.docstring:
                    self.error("E122", tr(f'la funzione "{name}" è uno strumento di un agente ma non ha descrizione',
                                          f'the function "{name}" is an agent tool but has no description'), name_tok,
                               tr('Aggiungi come prima riga del corpo una stringa che spiega cosa fa, es. """Cerca un cliente per email."""',
                                  'Add as the first line of the body a string that says what it does, e.g. """Finds a customer by email."""'))
                missing = [p for p, t, _ in resolved if t == ANY]
                if params is not None:
                    for p in params.children:
                        if p is not None and p.children[1] is None:
                            self.error("E121", tr(f'il parametro "{p.children[0]}" di "{name}" non ha un tipo',
                                                  f'the parameter "{p.children[0]}" of "{name}" has no type'), p.children[0],
                                       tr("Gli strumenti degli agenti devono dichiarare il tipo di ogni parametro, es. email: str",
                                          "Agent tools must declare the type of every parameter, e.g. email: str"))
            scope.collect_assigned(suite)
            self.check_block(suite, scope, in_loop=False)

    def check_agent_cycles(self):
        state = {}

        def visit(name, path):
            state[name] = "aperto"
            for dep in self.prog.agents[name].agent_tools:
                if state.get(dep) == "aperto":
                    cycle = path[path.index(dep):] + [name, dep]
                    self.error("E144", tr("gli agenti si delegano a vicenda: ", "the agents delegate to each other: ") + " → ".join(cycle),
                               self.prog.agents[name].node.children[0],
                               tr("Un agente non può delegare a chi delega (anche indirettamente) a lui: togline uno dai tools.",
                                  "An agent cannot delegate to an agent that delegates (even indirectly) back to it: "
                                  "remove one of them from tools."))
                elif dep not in state:
                    visit(dep, path + [name])
            state[name] = "chiuso"

        for name in self.prog.agents:
            if name not in state:
                visit(name, [])

    def definition_line(self, name):
        """Riga in cui è definita una costante o una funzione (contano solo queste per l'ordine)."""
        if name in self.prog.consts:
            return self.prog.consts[name].meta.line
        if name in self.prog.funcs:
            return self.prog.funcs[name].line
        return None

    # ------------------------------------------------------------ costanti
    def check_consts(self):
        scope = Scope(self, kind="const")
        for name, node in self.prog.consts.items():
            scope.before_line = node.meta.line
            t = self.infer(node.children[1], scope)
            self.global_names[name] = t

    # ------------------------------------------------------------ agenti
    def check_agents(self):
        for name, info in self.prog.agents.items():
            node = info.node
            fields = {}
            for af in node.children[1:]:
                fname_tok, value = af.children
                fname = str(fname_tok)
                if fname not in AGENT_FIELDS:
                    self.error("E130", tr(f'"{fname}" non è un campo valido per un agente', f'"{fname}" is not a valid agent field'),
                               fname_tok, did_you_mean(fname, AGENT_FIELDS, tr("Campi validi", "Valid fields")))
                    continue
                if fname in fields:
                    self.error("E137", tr(f'il campo "{fname}" è ripetuto', f'the field "{fname}" is repeated'), fname_tok)
                    continue
                fields[fname] = (fname_tok, value)
            info.fields = fields

            if "instructions" not in fields:
                self.error("E131", tr(f'l\'agente "{name}" non ha instructions', f'the agent "{name}" has no instructions'),
                           node.children[0],
                           tr('Aggiungi una riga come: instructions: "Sei un assistente che..."',
                              'Add a line like: instructions: "You are an assistant that..."'))

            if "tools" in fields:
                tok, value = fields["tools"]
                if not (isinstance(value, Tree) and value.data == "list"):
                    self.error("E132", tr("tools deve essere una lista di nomi", "tools must be a list of names"), value,
                               tr("Esempio: tools: [cerca_faq, prenota]", "Example: tools: [search_faq, book]"))
                else:
                    available = [n for n in self.prog.funcs] + [a for a in self.prog.agents if a != name]
                    for item in value.children:
                        if item is None:
                            continue
                        if not (isinstance(item, Tree) and item.data == "name"):
                            self.error("E132", tr("ogni elemento di tools deve essere il nome di una funzione o di un agente",
                                                  "every item in tools must be the name of a function or an agent"), item)
                            continue
                        tname = str(item.children[0])
                        if tname == name:
                            self.error("E138", tr("un agente non può usare se stesso come strumento",
                                                  "an agent cannot use itself as a tool"), item)
                        elif tname in self.prog.funcs:
                            self.prog.tool_funcs.add(tname)
                        elif tname in self.prog.agents:
                            info.agent_tools.append(tname)
                        else:
                            self.error("E133", tr(f'lo strumento "{tname}" non esiste', f'the tool "{tname}" does not exist'), item,
                                       did_you_mean(tname, available, tr("Strumenti disponibili", "Available tools"))
                                       or tr("Definisci una funzione con `def` e mettila nella lista.",
                                             "Define a function with `def` and put it in the list."))

            if "output" in fields:
                tok, value = fields["output"]
                if not (isinstance(value, Tree) and value.data == "name"):
                    self.error("E134", tr("output deve essere il nome di un type", "output must be the name of a type"), value,
                               tr("Esempio: output: Ticket", "Example: output: Ticket"))
                else:
                    oname = str(value.children[0])
                    if oname in self.prog.types:
                        info.output = oname
                    else:
                        self.error("E134", tr(f'il type "{oname}" non esiste', f'the type "{oname}" does not exist'), value,
                                   did_you_mean(oname, self.prog.types, tr("Type definiti", "Defined types"))
                                   or tr(f"Definiscilo con `type {oname}:` e i suoi campi.", f"Define it with `type {oname}:` and its fields."))

            if "memory" in fields:
                tok, value = fields["memory"]
                if not (isinstance(value, Tree) and value.data in ("true", "false")):
                    self.error("E135", tr("memory deve essere True o False", "memory must be True or False"), value)

            if "max_steps" in fields:
                tok, value = fields["max_steps"]
                if not (isinstance(value, Tree) and value.data == "number" and "." not in str(value.children[0])):
                    self.error("E136", tr("max_steps deve essere un numero intero", "max_steps must be a whole number"), value,
                               tr("Esempio: max_steps: 8", "Example: max_steps: 8"))

            if "effort" in fields:
                tok, value = fields["effort"]
                if not (isinstance(value, Tree) and value.data == "string" and string_value(value.children[0]) in EFFORTS):
                    self.error("E145", tr("effort deve essere uno tra ", "effort must be one of ") + ", ".join(f'"{e}"' for e in EFFORTS),
                               value, tr('Esempio: effort: "low" per classificare o estrarre (costa meno).',
                                         'Example: effort: "low" to classify or extract (it costs less).'))

            const_scope = Scope(self, kind="agent")
            for fname in ("model", "instructions"):
                if fname in fields:
                    t = self.infer(fields[fname][1], const_scope)
                    if t not in (STR, ANY):
                        self.error("E139", tr(f"{fname} deve essere un testo", f"{fname} must be a text"), fields[fname][1],
                                   tr('Usa una stringa tra virgolette, es. model: "claude"', 'Use a quoted string, e.g. model: "claude"'))

    # ------------------------------------------------------------ main
    def check_main(self):
        if self.prog.main is None:
            first = next((c for c in self.tree.children if isinstance(c, Tree)), None)
            self.diags.append(Diagnostic("W001", tr("il file non ha un blocco main: eseguendolo non succede niente",
                                                    "the file has no main block: running it does nothing"),
                                         1, 1, 1, tr("Aggiungi in fondo: main:\n    ...", "Add at the end: main:\n    ..."),
                                         severity="avviso"))
            return
        suite = self.prog.main.children[0]
        scope = Scope(self, kind="main")
        scope.collect_assigned(suite)
        self.check_block(suite, scope, in_loop=False)

    # ------------------------------------------------------------ istruzioni
    def check_block(self, suite: Tree, scope: "Scope", in_loop: bool):
        for i, stmt in enumerate(suite.children):
            self.check_stmt(stmt, scope, in_loop, first=(i == 0))

    def check_stmt(self, stmt, scope, in_loop, first=False):
        kind = stmt.data
        if kind == "assign":
            target, value = stmt.children
            t = self.infer(value, scope)
            self.check_target(target, scope, t, augmented=False)
        elif kind == "aug_assign":
            target, op, value = stmt.children
            self.infer(value, scope)
            self.check_target(target, scope, ANY, augmented=True)
        elif kind == "return_stmt":
            if stmt.children[0] is not None:
                self.infer(stmt.children[0], scope)
        elif kind == "expr_stmt":
            expr = stmt.children[0]
            if first and isinstance(expr, Tree) and expr.data == "string":
                return  # descrizione (docstring)
            self.infer(expr, scope)
        elif kind in ("break_stmt", "continue_stmt"):
            if not in_loop:
                word = "break" if kind == "break_stmt" else "continue"
                self.error("E150", tr(f"`{word}` si può usare solo dentro un ciclo for", f"`{word}` can only be used inside a for loop"), stmt)
        elif kind == "if_stmt":
            cond, suite, *rest = stmt.children
            self.infer(cond, scope)
            self.check_block(suite, scope, in_loop)
            for clause in rest:
                if clause is None:
                    continue
                if clause.data == "elif_clause":
                    self.infer(clause.children[0], scope)
                    self.check_block(clause.children[1], scope, in_loop)
                else:
                    self.check_block(clause.children[0], scope, in_loop)
        elif kind == "for_stmt":
            target, iterable, suite = stmt.children
            it = self.infer(iterable, scope)
            names = target.children
            elem = it[1] if it[0] == "list" else ANY
            if it[0] in ("record", "agent", "func", "typeobj") or it in (INT, FLOAT, BOOL, NONE):
                self.error("E151", tr(f"non si può fare un ciclo su un valore di tipo {type_name(it)}",
                                      f"cannot loop over a value of type {type_name(it)}"), iterable,
                           tr("Per ripetere n volte usa `for i in range(n):`.", "To repeat n times use `for i in range(n):`.")
                           if it in (INT, FLOAT) else "")
            if it == STR:
                elem = STR
            for n in names:
                scope.define(str(n), elem if len(names) == 1 else ANY, n)
            self.check_block(suite, scope, in_loop=True)
        elif kind == "pass_stmt":
            pass

    def check_target(self, target, scope, value_type, augmented):
        if isinstance(target, Tree) and target.data == "name":
            name_tok = target.children[0]
            name = str(name_tok)
            g = self.global_names.get(name)
            if g is not None and scope.kind in ("def", "main") and not scope.has_local(name):
                if name in self.prog.consts:
                    self.error("E142", tr(f'"{name}" è una costante e non si può modificare', f'"{name}" is a constant and cannot be changed'),
                               name_tok, tr("Usa un'altra variabile, es. " + f"{name.lower()}_nuovo = ...",
                                            f"Use another variable, e.g. {name.lower()}_new = ..."))
                    return
                kind = tr({"agent": "un agente", "func": "una funzione", "typeobj": "un type", "module": "un modulo importato"},
                          {"agent": "an agent", "func": "a function", "typeobj": "a type", "module": "an imported module"}).get(g[0])
                if kind:
                    self.error("E141", tr(f'"{name}" è {kind}: non puoi usarlo come variabile', f'"{name}" is {kind}: you cannot use it as a variable'),
                               name_tok, tr("Scegli un altro nome.", "Choose another name."))
                    return
            if name in BUILTINS and not scope.has_local(name):
                self.error("E141", tr(f'"{name}" è una funzione di Tokyn: non puoi usarlo come variabile',
                                      f'"{name}" is a Tokyn function: you cannot use it as a variable'),
                           name_tok, tr("Scegli un altro nome.", "Choose another name."))
                return
            if augmented:
                if scope.lookup(name) is None:
                    self.error("E160", tr(f'la variabile "{name}" non è definita', f'the variable "{name}" is not defined'), name_tok,
                               tr(f"Prima di usare {name} += ... assegnale un valore, es. {name} = 0",
                                  f"Before using {name} += ... give it a value, e.g. {name} = 0"))
                return
            scope.define(name, value_type, name_tok)
        elif isinstance(target, Tree) and target.data in ("getattr", "getitem"):
            obj_t = self.infer(target.children[0], scope)
            if target.data == "getattr" and obj_t[0] == "record":
                self.check_field(obj_t[1], target.children[1])
            elif target.data == "getattr" and obj_t[0] == "agent":
                self.error("E170", tr("non si possono modificare i campi di un agente durante l'esecuzione",
                                      "an agent's fields cannot be changed while the program runs"), target)
            elif target.data == "getitem":
                self.infer(target.children[1], scope)
        else:
            self.error("E140", tr("a sinistra di '=' ci vuole un nome di variabile", "the left side of '=' must be a variable name"), target,
                       tr("Esempio: risultato = Agente.ask(testo). Per confrontare usa '=='.",
                          "Example: result = Agent.ask(text). To compare use '=='."))

    # ------------------------------------------------------------ espressioni
    def check_field(self, record_name, attr_tok):
        info = self.prog.types[record_name]
        fname = str(attr_tok)
        if fname not in info.fields:
            self.error("E171", tr(f'il type "{record_name}" non ha il campo "{fname}"', f'the type "{record_name}" has no field "{fname}"'),
                       attr_tok, did_you_mean(fname, info.fields, tr("Campi", "Fields")))
            return ANY
        return info.fields[fname]

    def infer(self, node, scope) -> tuple:
        if node is None:
            return NONE
        if isinstance(node, Token):
            return ANY
        kind = node.data
        method = getattr(self, f"infer_{kind}", None)
        if method is None:
            for child in node.children:
                if isinstance(child, Tree):
                    self.infer(child, scope)
            return ANY
        return method(node, scope)

    def infer_name(self, node, scope):
        name_tok = node.children[0]
        name = str(name_tok)
        t = scope.lookup(name)
        if t is not None:
            self.check_order(name_tok, scope)
            if scope.kind == "const" and t[0] == "agent":
                self.error("E191", tr("le costanti non possono usare agenti", "constants cannot use agents"), name_tok,
                           tr("Usa l'agente dentro main o dentro una funzione.", "Use the agent inside main or inside a function."))
            return t
        if scope.assigned_later(name):
            self.error("E161", tr(f'la variabile "{name}" è usata prima di ricevere un valore',
                                  f'the variable "{name}" is used before it gets a value'), name_tok,
                       tr(f"Assegna {name} = ... prima di questa riga.", f"Assign {name} = ... before this line."))
            return ANY
        candidates = scope.visible_names()
        hint = did_you_mean(name, candidates)
        if name in ("true", "false", "null", "none", "nil"):
            hint = tr("In Tokyn si scrive True, False e None con l'iniziale maiuscola.",
                      "In Tokyn True, False and None are written with a capital letter.")
        elif name in ("self", "this"):
            hint = tr("Tokyn non ha classi: usa le variabili direttamente.", "Tokyn has no classes: use the variables directly.")
        self.error("E160", tr(f'il nome "{name}" non è definito', f'the name "{name}" is not defined'), name_tok, hint)
        return ANY

    def check_order(self, name_tok, scope):
        """Costanti e valori predefiniti si calcolano subito: possono usare solo ciò che è scritto prima."""
        name = str(name_tok)
        line = self.definition_line(name) if scope.before_line and not scope.has_local(name) else None
        if line and line > scope.before_line:
            self.error("E162", tr(f'"{name}" è definita più sotto (riga {line}): qui si può usare solo ciò che è scritto prima',
                                  f'"{name}" is defined further down (line {line}): here you can only use what is written before'),
                       name_tok, tr(f"Sposta la definizione di {name} sopra la riga {scope.before_line}.",
                                    f"Move the definition of {name} above line {scope.before_line}."))

    def infer_number(self, node, scope):
        return FLOAT if any(c in str(node.children[0]) for c in ".eE") else INT

    def infer_string(self, node, scope):
        return STR

    def infer_true(self, node, scope):
        return BOOL

    infer_false = infer_true

    def infer_none(self, node, scope):
        return NONE

    def infer_fstring(self, node, scope):
        tok = node.children[0]
        raw = str(tok)
        body_start = 4 if raw[1:4] in ('"""', "'''") else 2
        body = raw[body_start: len(raw) - (body_start - 1)]
        for offset, inner in _fstring_parts(body):
            text = inner.strip()
            if not text:
                self.diags.append(Diagnostic("E192", tr("graffe vuote {} nella f-string", "empty braces {} in the f-string"),
                                             tok.line, tok.column + body_start + offset, 2,
                                             tr("Metti un'espressione tra le graffe oppure scrivi {{ }} per una graffa letterale.",
                                                "Put an expression between the braces, or write {{ }} for a literal brace.")))
                continue
            try:
                sub = parse_expr(text)
            except Exception:
                self.diags.append(Diagnostic("E193", tr(f"espressione non valida nella f-string: {{{text}}}",
                                                        f"invalid expression in the f-string: {{{text}}}"),
                                             tok.line, tok.column + body_start + offset, len(text) + 2))
                continue
            _shift_positions(sub, tok.line, tok.column + body_start + offset + 1 + (len(inner) - len(inner.lstrip())))
            self.infer(sub, scope)
        return STR

    def infer_list(self, node, scope):
        items = [c for c in node.children if c is not None]
        types = [self.infer(c, scope) for c in items]
        if types and all(t == types[0] for t in types):
            return LIST(types[0] if types[0][0] != "enum" else STR)
        return LIST()

    def infer_dict(self, node, scope):
        for item in node.children:
            if item is None:
                continue
            self.infer(item.children[0], scope)
            self.infer(item.children[1], scope)
        return DICT

    def infer_not_(self, node, scope):
        self.infer(node.children[0], scope)
        return BOOL

    def infer_and_(self, node, scope):
        for c in node.children:
            self.infer(c, scope)
        return ANY

    infer_or_ = infer_and_

    def infer_unary(self, node, scope):
        t = self.infer(node.children[1], scope)
        return t if t in (INT, FLOAT) else ANY

    def infer_arith(self, node, scope):
        types = [self.infer(c, scope) for c in node.children if isinstance(c, Tree)]
        if all(t == STR for t in types):
            return STR
        if all(t in (INT, FLOAT) for t in types):
            return FLOAT if FLOAT in types else INT
        if any(t == STR for t in types) and any(t in (INT, FLOAT) for t in types):
            self.error("E194", tr("non si può sommare un testo con un numero", "cannot add a text and a number"), node,
                       tr("Converti il numero con str(...) oppure usa una f-string: f\"totale: {n}\"",
                          "Convert the number with str(...) or use an f-string: f\"total: {n}\""))
        return ANY

    def infer_term(self, node, scope):
        types = [self.infer(c, scope) for c in node.children if isinstance(c, Tree)]
        ops = [str(c) for c in node.children if isinstance(c, Token)]
        if all(t in (INT, FLOAT) for t in types):
            return FLOAT if (FLOAT in types or "/" in ops) else INT
        return ANY

    def infer_comparison(self, node, scope):
        operands = [c for c in node.children if not (isinstance(c, Tree) and c.data == "comp_op")]
        ops = [" ".join(str(t) for t in c.children) for c in node.children if isinstance(c, Tree) and c.data == "comp_op"]
        types = [self.infer(c, scope) for c in operands]
        for i, op in enumerate(ops):
            left, right = operands[i], operands[i + 1]
            lt, rt = types[i], types[i + 1]
            if op in ("==", "!="):
                self.check_enum_value(lt, right)
                self.check_enum_value(rt, left)
            elif op in ("in", "not in") and isinstance(right, Tree) and right.data == "list":
                for item in right.children:
                    if item is not None:
                        self.check_enum_value(lt, item)
        return BOOL

    def check_enum_value(self, t, other):
        if t[0] != "enum":
            return
        if isinstance(other, Tree) and other.data == "string":
            value = string_value(other.children[0])
            if value not in t[1]:
                best = suggest(value, t[1])
                hint = ((tr(f'Forse intendevi "{best}"? ', f'Did you mean "{best}"? ') if best else "")
                        + tr("Valori possibili: ", "Possible values: ") + ", ".join(f'"{v}"' for v in t[1]))
                self.error("E190", tr(f'"{value}" non è uno dei valori possibili', f'"{value}" is not one of the possible values'),
                           other, hint)

    def infer_getitem(self, node, scope):
        obj = self.infer(node.children[0], scope)
        self.infer(node.children[1], scope)
        if obj[0] == "list":
            return obj[1]
        if obj == STR:
            return STR
        if obj[0] == "record":
            self.error("E172", tr("i campi di un type si leggono con il punto, non con [ ]", "the fields of a type are read with a dot, not with [ ]"),
                       node, tr(f"Esempio: valore.campo invece di valore[\"campo\"]", "Example: value.field instead of value[\"field\"]"))
        return ANY

    def infer_pow(self, node, scope):
        types = [self.infer(c, scope) for c in node.children if isinstance(c, Tree)]
        if all(t in (INT, FLOAT) for t in types):
            return FLOAT if FLOAT in types else INT
        return ANY

    def infer_slice(self, node, scope):
        obj = self.infer(node.children[0], scope)
        for bound in node.children[1:]:
            if bound is not None and self.infer(bound, scope) not in (INT, ANY):
                self.error("E176", tr("gli estremi di una slice devono essere numeri interi", "the bounds of a slice must be whole numbers"),
                           bound, tr("Esempio: testo[:200], lista[1:], lista[-3:]", "Example: text[:200], items[1:], items[-3:]"))
        if obj[0] == "list" or obj == STR:
            return obj
        if obj[0] == "record":
            self.error("E172", tr("i campi di un type si leggono con il punto, non con [ ]", "the fields of a type are read with a dot, not with [ ]"),
                       node, tr(f"Esempio: valore.campo invece di valore[\"campo\"]", "Example: value.field instead of value[\"field\"]"))
        return ANY

    def infer_getattr(self, node, scope):
        obj_node, attr = node.children
        obj = self.infer(obj_node, scope)
        a = str(attr)
        if obj[0] == "record":
            return self.check_field(obj[1], attr)
        if obj[0] == "agent":
            if a == "name":
                return STR
            if a not in AGENT_METHODS:
                self.error("E170", tr(f'gli agenti non hanno ".{a}"', f'agents have no ".{a}"'), attr,
                           tr("Un agente ha solo .ask(testo), che restituisce la risposta, .ask_all(testi), che risponde a una lista "
                              "a metà prezzo, e .reset(), che cancella la memoria.",
                              "An agent has only .ask(text), which returns the answer, .ask_all(texts), which answers a list "
                              "at half price, and .reset(), which clears the memory."))
            return ANY
        if obj[0] == "typeobj":
            self.error("E173", tr(f'"{obj[1]}" è un type: per crearne uno usa {obj[1]}(campo=valore, ...)',
                                  f'"{obj[1]}" is a type: to create one use {obj[1]}(field=value, ...)'), attr)
            return ANY
        if obj[0] == "func":
            self.error("E174", tr(f'"{obj[1]}" è una funzione: va chiamata con le parentesi',
                                  f'"{obj[1]}" is a function: call it with parentheses'), attr)
            return ANY
        method_sets = {STR: STR_METHODS, DICT: DICT_METHODS}
        if obj in method_sets or obj[0] == "list" or obj[0] == "enum":
            methods = LIST_METHODS if obj[0] == "list" else method_sets.get(obj, STR_METHODS)
            if a not in methods:
                self.error("E175", tr(f'il tipo {type_name(obj)} non ha ".{a}"', f'the type {type_name(obj)} has no ".{a}"'),
                           attr, did_you_mean(a, methods))
            return ANY
        return ANY

    def infer_call(self, node, scope):
        callee, args = node.children
        arg_list = [a for a in (args.children if args is not None else []) if a is not None]
        positional = [a for a in arg_list if not (isinstance(a, Tree) and a.data == "kwarg")]
        kwargs = [a for a in arg_list if isinstance(a, Tree) and a.data == "kwarg"]

        def infer_args():
            types = [self.infer(a, scope) for a in positional]
            for k in kwargs:
                self.infer(k.children[1], scope)
            return types

        # metodo di un agente: Agente.ask(...)
        if isinstance(callee, Tree) and callee.data == "getattr":
            obj = self.infer(callee.children[0], scope)
            method = str(callee.children[1])
            if obj[0] == "agent":
                arg_types = infer_args()
                if method == "ask_all" and arg_types and arg_types[0][0] in ("str", "int", "float", "bool", "dict", "record"):
                    self.error("E186", tr(f".ask_all() vuole una lista di testi, non {type_name(arg_types[0])}",
                                          f".ask_all() takes a list of texts, not {type_name(arg_types[0])}"), positional[0],
                               tr(f"Per un testo solo usa {obj[1]}.ask(testo).", f"For a single text use {obj[1]}.ask(text)."))
                if method not in AGENT_METHODS:
                    self.error("E170", tr(f'gli agenti non hanno ".{method}"', f'agents have no ".{method}"'), callee.children[1],
                               tr("Un agente ha solo .ask(testo), .ask_all(lista_di_testi) e .reset().",
                                  "An agent has only .ask(text), .ask_all(list_of_texts) and .reset()."))
                    return ANY
                lo, hi = AGENT_METHODS[method]
                if kwargs or not (lo <= len(positional) <= hi):
                    expected = tr({"ask": "un solo argomento: il testo da chiedere",
                                   "ask_all": "un solo argomento: la lista dei testi"}.get(method, "nessun argomento"),
                                  {"ask": "a single argument: the text to ask",
                                   "ask_all": "a single argument: the list of texts"}.get(method, "no arguments"))
                    self.error("E186", tr(f".{method}() vuole {expected}", f".{method}() takes {expected}"), node,
                               tr({"ask": f'Esempio: {obj[1]}.ask("...")', "ask_all": f"Esempio: {obj[1]}.ask_all(testi)"}.get(method, ""),
                                  {"ask": f'Example: {obj[1]}.ask("...")', "ask_all": f"Example: {obj[1]}.ask_all(texts)"}.get(method, "")))
                if method in ("ask", "ask_all"):
                    agent = self.prog.agents.get(obj[1])
                    answer = ("record", agent.output) if agent is not None and agent.output else STR
                    return answer if method == "ask" else LIST(answer)
                return NONE
            # altri metodi: controlla l'attributo come getattr
            self.infer_getattr(callee, scope) if obj[0] in ("record", "typeobj", "func") or obj in (STR, DICT) or obj[0] in ("list", "enum") else None
            infer_args()
            return ANY

        if isinstance(callee, Tree) and callee.data == "name":
            name = str(callee.children[0])
            t = scope.lookup(name)
            if t is not None:
                self.check_order(callee.children[0], scope)
            if t is None:
                self.infer_name(callee, scope)
                infer_args()
                return ANY
            infer_args()
            if t[0] == "agent":
                self.error("E187", tr(f'"{name}" è un agente: si usa con {name}.ask(testo)',
                                      f'"{name}" is an agent: use it with {name}.ask(text)'), callee)
                return ANY
            if t[0] == "typeobj":
                return self.check_constructor(name, node, positional, kwargs, scope)
            if t[0] == "func" and not scope.has_local(name):
                return self.check_func_call(self.prog.funcs[name], node, positional, kwargs)
            if name in BUILTINS and not scope.has_local(name):
                lo, hi, ret = BUILTINS[name]
                n = len(positional)
                if n < lo or (hi is not None and n > hi):
                    if hi is None:
                        want = tr(f"almeno {lo}", f"at least {lo}")
                    elif lo == hi:
                        want = str(lo)
                    else:
                        want = tr(f"da {lo} a {hi}", f"from {lo} to {hi}")
                    self.error("E180", tr(f"{name}() vuole {want} argomenti, ne ha ricevuti {n}",
                                          f"{name}() takes {want} argument{'' if want == '1' else 's'}, it got {n}"), node)
                return ret
            return ANY

        self.infer(callee, scope)
        infer_args()
        return ANY

    def check_func_call(self, info: FuncInfo, node, positional, kwargs):
        params = info.params
        names = [p[0] for p in params]
        if len(positional) > len(params):
            self.error("E180", tr(f'{info.name}() vuole al massimo {len(params)} argomenti, ne ha ricevuti {len(positional)}',
                                  f'{info.name}() takes at most {len(params)} argument{"" if len(params) == 1 else "s"}, '
                                  f'it got {len(positional)}'), node,
                       tr(f"Parametri: {', '.join(names) or 'nessuno'}", f"Parameters: {', '.join(names) or 'none'}"))
            return info.returns
        given = set(names[: len(positional)])
        for k in kwargs:
            kname = str(k.children[0])
            if kname not in names:
                self.error("E181", tr(f'{info.name}() non ha un parametro "{kname}"', f'{info.name}() has no parameter "{kname}"'),
                           k.children[0], did_you_mean(kname, names, tr("Parametri", "Parameters")))
            elif kname in given:
                self.error("E181", tr(f'il parametro "{kname}" è passato due volte', f'the parameter "{kname}" is passed twice'),
                           k.children[0])
            given.add(kname)
        missing = [p[0] for p in params if not p[2] and p[0] not in given]
        if missing:
            self.error("E180", tr(f"{info.name}() senza il parametro obbligatorio: {', '.join(missing)}",
                                  f"{info.name}() is missing the required parameter: {', '.join(missing)}"), node)
        return info.returns

    def check_constructor(self, tname, node, positional, kwargs, scope):
        info = self.prog.types[tname]
        if positional:
            self.error("E182", tr(f"per creare un {tname} indica il nome di ogni campo", f"to create a {tname} give the name of every field"),
                       node, tr(f"Esempio: {tname}(", f"Example: {tname}(") + ", ".join(f"{f}=..." for f in info.fields) + ")")
        seen = set()
        for k in kwargs:
            kname = str(k.children[0])
            if kname not in info.fields:
                self.error("E183", tr(f'il type "{tname}" non ha il campo "{kname}"', f'the type "{tname}" has no field "{kname}"'),
                           k.children[0], did_you_mean(kname, info.fields, tr("Campi", "Fields")))
                continue
            seen.add(kname)
            self.check_enum_value(info.fields[kname], k.children[1])
        missing = [f for f in info.fields if f not in seen]
        if missing and not positional:
            self.error("E184", tr(f"mancano dei campi per creare {tname}: {', '.join(missing)}",
                                  f"missing fields to create {tname}: {', '.join(missing)}"), node)
        return ("record", tname)


# ---------------------------------------------------------------- scope


class Scope:
    def __init__(self, checker: Checker, kind: str, func: FuncInfo | None = None):
        self.checker = checker
        self.kind = kind
        self.func = func
        self.locals: dict[str, tuple] = {}
        self.pending: set[str] = set()
        self.before_line: int | None = None  # costanti e valori predefiniti: solo nomi definiti prima

    def define(self, name, t, tok=None):
        self.locals[name] = t
        self.pending.discard(name)

    def has_local(self, name):
        return name in self.locals

    def lookup(self, name):
        if name in self.locals:
            return self.locals[name]
        if name in self.checker.global_names:
            if self.kind == "const" and name in self.checker.prog.consts:
                # solo costanti già valutate (quelle prima)
                return self.checker.global_names[name]
            return self.checker.global_names[name]
        if name in BUILTINS:
            return ("builtin", name)
        return None

    def assigned_later(self, name):
        return name in self.pending

    def visible_names(self):
        return set(self.locals) | set(self.checker.global_names) | set(BUILTINS)

    def collect_assigned(self, suite: Tree):
        for sub in suite.iter_subtrees():
            if sub.data == "assign":
                target = sub.children[0]
                if isinstance(target, Tree) and target.data == "name":
                    name = str(target.children[0])
                    if name not in self.locals:
                        self.pending.add(name)
            elif sub.data == "for_target":
                for n in sub.children:
                    if str(n) not in self.locals:
                        self.pending.add(str(n))


# ---------------------------------------------------------------- f-string


def _fstring_parts(body: str):
    """Restituisce (offset, testo) per ogni {espressione} della f-string."""
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c == "{":
            if i + 1 < n and body[i + 1] == "{":
                i += 2
                continue
            depth, j = 1, i + 1
            while j < n and depth:
                if body[j] in "{[(":
                    depth += 1
                elif body[j] in "}])":
                    depth -= 1
                j += 1
            inner = body[i + 1: j - 1]
            # rimuove conversione e formato: {x!r} {x:.2f}
            d, cut = 0, len(inner)
            for k, ch in enumerate(inner):
                if ch in "([{":
                    d += 1
                elif ch in ")]}":
                    d -= 1
                elif d == 0 and ch in ":!" and not inner[k:k + 2] == "!=":
                    cut = k
                    break
            yield i, inner[:cut]
            i = j
        elif c == "}" and i + 1 < n and body[i + 1] == "}":
            i += 2
        else:
            i += 1


def _shift_positions(tree: Tree, line: int, col: int):
    for t in tree.iter_subtrees():
        for c in t.children:
            if isinstance(c, Token) and c.line == 1:
                c.line = line
                c.column = (c.column or 1) + col - 1
        if not t.meta.empty and getattr(t.meta, "line", None) == 1:
            t.meta.line = line
            t.meta.column = t.meta.column + col - 1
            if getattr(t.meta, "end_line", None) == 1:
                t.meta.end_line = line
                t.meta.end_column = t.meta.end_column + col - 1


def check(tree: Tree) -> tuple[Program, list[Diagnostic]]:
    return Checker(tree).run()
