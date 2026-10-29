"""Traduce un programma Tokyn già controllato in codice Python."""

from __future__ import annotations

import inspect
from pathlib import Path

from lark import Token, Tree

from . import __version__
from .checker import BUILTINS, PREC, Program, string_value
from .errors import TokynRuntimeError

RUNTIME_BUILTINS = [
    "read_file", "write_file", "append_file", "http_get", "http_post",
    "json_parse", "json_dump", "env", "now", "sleep",
]


def standalone_runtime() -> str:
    """Il sorgente del runtime senza import relativi, da includere in un file autonomo."""
    src = (Path(__file__).parent / "runtime.py").read_text(encoding="utf-8")
    src = src.replace("from .errors import TokynRuntimeError\n", inspect.getsource(TokynRuntimeError), 1)
    if "from ." in src or "'''" in src:
        raise ValueError("runtime.py non si può includere: contiene import relativi o '''")
    return src


class CodeGen:
    def __init__(self, tree: Tree, prog: Program, filename: str, standalone: bool = False):
        self.tree = tree
        self.prog = prog
        self.filename = filename
        self.standalone = standalone
        self.lines: list[str] = []
        self.py_line = 0  # ultima riga python scritta (un testo può contenere più righe)
        self.linemap: dict[int, int] = {}  # riga python -> riga tokyn

    def emit(self, text: str, indent: int = 0, src_line: int | None = None):
        self.lines.append("    " * indent + text)
        if src_line:
            self.linemap[self.py_line + 1] = src_line
        self.py_line += text.count("\n") + 1

    # ------------------------------------------------------------ programma
    def generate(self) -> tuple[str, dict[int, int]]:
        self.emit(f"# Generato da Tokyn {__version__} a partire da {self.filename}.")
        self.emit("# Non modificare questo file: modifica il sorgente .tokyn e ricompila.")
        if self.standalone:
            self.emit("# File autonomo: il runtime di Tokyn è incluso qui sotto, serve solo `pip install anthropic`.")
            self.emit("import types as __types")
            self.emit("__rt = __types.ModuleType('tokyn_runtime')")
            self.emit(f"exec(compile(r'''{standalone_runtime()}''', 'tokyn_runtime', 'exec'), __rt.__dict__)")
            self.emit(", ".join(RUNTIME_BUILTINS) + " = " + ", ".join(f"__rt.{b}" for b in RUNTIME_BUILTINS))
        else:
            self.emit("from tokyn import runtime as __rt")
            self.emit("from tokyn.runtime import " + ", ".join(RUNTIME_BUILTINS))
        nodes = [c for c in self.tree.children if isinstance(c, Tree)]

        for n in nodes:
            if n.data == "import_plain":
                dotted, alias = n.children
                mod = ".".join(str(t) for t in dotted.children)
                self.emit(f"import {mod}" + (f" as {alias}" if alias is not None else ""), src_line=n.meta.line)
            elif n.data == "import_from":
                dotted, *names = n.children
                mod = ".".join(str(t) for t in dotted.children)
                items = [str(a) + (f" as {b}" if b is not None else "") for a, b in (x.children for x in names)]
                self.emit(f"from {mod} import {', '.join(items)}", src_line=n.meta.line)
        self.emit("")

        for n in nodes:
            if n.data == "type_def":
                self.gen_type(n)
        # costanti e funzioni nell'ordine del file, come in Python (il checker lo verifica)
        for n in nodes:
            if n.data == "def_stmt":
                self.gen_def(n)
            elif n.data == "const_def":
                name, value = n.children
                self.emit(f"{name} = {self.expr(value)}", src_line=n.meta.line)
                self.emit("")
        for name in self.agent_order():
            self.gen_agent(self.prog.agents[name].node)

        main = self.prog.main
        self.emit("def __tokyn_main__():", src_line=main.meta.line if main is not None else None)
        if main is not None:
            self.gen_suite(main.children[0], 1)
        else:
            self.emit("pass", 1)
        self.emit("")
        self.emit("if __name__ == \"__main__\":")
        self.emit("__rt.run_main(__tokyn_main__)", 1)
        return "\n".join(self.lines) + "\n", self.linemap

    # ------------------------------------------------------------ dichiarazioni
    def typespec(self, texpr: Tree) -> str:
        atoms = texpr.children
        if len(atoms) > 1 or atoms[0].data == "type_literal":
            values = [repr(string_value(a.children[0])) for a in atoms if a.data == "type_literal"]
            return f"__rt.T.enum({', '.join(values)})"
        name_tok, inner = atoms[0].children
        name = str(name_tok)
        if name == "list":
            return f"__rt.T.list({self.typespec(inner) if inner is not None else '__rt.T.ANY'})"
        if name in ("str", "int", "float", "bool", "dict"):
            return f"__rt.T.{name.upper()}"
        return f"__rt.T.ref({name!r})"

    def gen_type(self, n: Tree):
        name = str(n.children[0])
        self.emit(f"{name} = __rt.make_type({name!r}, {{", src_line=n.meta.line)
        for fd in n.children[1:]:
            fname, texpr, desc = fd.children
            d = repr(string_value(desc)) if desc is not None else "None"
            self.emit(f"{str(fname)!r}: ({self.typespec(texpr)}, {d}),", 1, src_line=fd.meta.line)
        self.emit("})")
        self.emit("")

    def gen_def(self, n: Tree):
        name, params, ret, suite = n.children
        info = self.prog.funcs.get(str(name))
        specs, plist = [], []
        if params is not None:
            for p in params.children:
                if p is None:
                    continue
                pname, ptype, pdefault = p.children
                specs.append(f"{str(pname)!r}: {self.typespec(ptype) if ptype is not None else '__rt.T.ANY'}")
                plist.append(str(pname) + (f"={self.expr(pdefault)}" if pdefault is not None else ""))
        doc = info.docstring if info is not None else None
        ret_spec = self.typespec(ret) if ret is not None else "__rt.T.ANY"
        self.emit(f"@__rt.tool({str(name)!r}, {doc!r}, {{{', '.join(specs)}}}, {ret_spec})", src_line=n.meta.line)
        self.emit(f"def {name}({', '.join(plist)}):", src_line=n.meta.line)
        self.gen_suite(suite, 1)
        self.emit("")

    def agent_order(self) -> list[str]:
        """Ogni agente dopo quelli a cui delega, così esistono già quando viene creato."""
        order: list[str] = []
        seen: set[str] = set()

        def visit(name):
            if name in seen:
                return
            seen.add(name)  # prima delle dipendenze: un ciclo (segnalato dal checker) non va in loop
            for dep in self.prog.agents[name].agent_tools:
                visit(dep)
            order.append(name)

        for name in self.prog.agents:
            visit(name)
        return order

    def gen_agent(self, n: Tree):
        name = str(n.children[0])
        fields = {str(af.children[0]): af.children[1] for af in n.children[1:]}
        parts = [f"name={name!r}"]
        for key in ("model", "instructions", "tools", "output", "memory", "max_steps"):
            if key in fields:
                parts.append(f"{key}={self.expr(fields[key])}")
        self.emit(f"{name} = __rt.Agent(", src_line=n.meta.line)
        for p in parts:
            self.emit(p + ",", 1, src_line=n.meta.line)
        self.emit(")")
        self.emit("")

    # ------------------------------------------------------------ istruzioni
    def gen_suite(self, suite: Tree, indent: int):
        if not suite.children:
            self.emit("pass", indent)
        for stmt in suite.children:
            self.gen_stmt(stmt, indent)

    def gen_stmt(self, s: Tree, ind: int):
        line = s.meta.line if not s.meta.empty else None
        k = s.data
        if k == "assign":
            self.emit(f"{self.expr(s.children[0])} = {self.expr(s.children[1])}", ind, line)
        elif k == "aug_assign":
            self.emit(f"{self.expr(s.children[0])} {s.children[1]} {self.expr(s.children[2])}", ind, line)
        elif k == "return_stmt":
            v = s.children[0]
            self.emit("return" + (f" {self.expr(v)}" if v is not None else ""), ind, line)
        elif k == "expr_stmt":
            self.emit(self.expr(s.children[0]), ind, line)
        elif k == "pass_stmt":
            self.emit("pass", ind, line)
        elif k == "break_stmt":
            self.emit("break", ind, line)
        elif k == "continue_stmt":
            self.emit("continue", ind, line)
        elif k == "if_stmt":
            cond, suite, *rest = s.children
            self.emit(f"if {self.expr(cond)}:", ind, line)
            self.gen_suite(suite, ind + 1)
            for clause in rest:
                if clause is None:
                    continue
                if clause.data == "elif_clause":
                    self.emit(f"elif {self.expr(clause.children[0])}:", ind, clause.meta.line)
                    self.gen_suite(clause.children[1], ind + 1)
                else:
                    self.emit("else:", ind, clause.meta.line)
                    self.gen_suite(clause.children[0], ind + 1)
        elif k == "for_stmt":
            target, it, suite = s.children
            names = ", ".join(str(t) for t in target.children)
            self.emit(f"for {names} in {self.expr(it)}:", ind, line)
            self.gen_suite(suite, ind + 1)
        else:
            raise ValueError(f"istruzione sconosciuta: {k}")

    # ------------------------------------------------------------ espressioni
    def wrap(self, child, parent_prec: int, strict: bool = False) -> str:
        code = self.expr(child)
        cp = PREC.get(child.data, 99) if isinstance(child, Tree) else 99
        if cp < parent_prec or (strict and cp == parent_prec):
            return f"({code})"
        return code

    def expr(self, e) -> str:
        if isinstance(e, Token):
            return str(e)
        k = e.data
        c = e.children
        if k == "name":
            return str(c[0])
        if k in ("number", "string", "fstring"):
            return str(c[0])
        if k == "true":
            return "True"
        if k == "false":
            return "False"
        if k == "none":
            return "None"
        if k == "list":
            return "[" + ", ".join(self.expr(x) for x in c if x is not None) + "]"
        if k == "dict":
            items = [f"{self.expr(i.children[0])}: {self.expr(i.children[1])}" for i in c if i is not None]
            return "{" + ", ".join(items) + "}"
        if k == "or_":
            return " or ".join(self.wrap(x, 1, strict=True) for x in c)
        if k == "and_":
            return " and ".join(self.wrap(x, 2, strict=True) for x in c)
        if k == "not_":
            return "not " + self.wrap(c[0], 3)
        if k == "comparison":
            out = []
            for x in c:
                if isinstance(x, Tree) and x.data == "comp_op":
                    out.append(" ".join(str(t) for t in x.children))
                else:
                    out.append(self.wrap(x, 4, strict=True))
            return " ".join(out)
        if k in ("arith", "term"):
            prec = PREC[k]
            out = []
            for i, x in enumerate(c):
                if isinstance(x, Token):
                    out.append(str(x))
                else:
                    out.append(self.wrap(x, prec, strict=i > 0))
            return " ".join(out)
        if k == "unary":
            return f"{c[0]}{self.wrap(c[1], 7)}"
        if k == "call":
            fn, args = c
            arg_code = []
            if args is not None:
                for a in args.children:
                    if a is None:
                        continue
                    if isinstance(a, Tree) and a.data == "kwarg":
                        arg_code.append(f"{a.children[0]}={self.expr(a.children[1])}")
                    else:
                        arg_code.append(self.expr(a))
            return f"{self.wrap(fn, 8)}({', '.join(arg_code)})"
        if k == "getattr":
            return f"{self.wrap(c[0], 8)}.{c[1]}"
        if k == "getitem":
            return f"{self.wrap(c[0], 8)}[{self.expr(c[1])}]"
        if k == "slice":
            lo, hi, step = (self.expr(x) if x is not None else "" for x in c[1:])
            return f"{self.wrap(c[0], 8)}[{lo}:{hi}" + (f":{step}]" if step else "]")
        if k == "pow":
            return f"{self.wrap(c[0], 8)} ** {self.wrap(c[2], 7)}"
        raise ValueError(f"espressione sconosciuta: {k}")


def generate(tree: Tree, prog: Program, filename: str, standalone: bool = False) -> tuple[str, dict[int, int]]:
    return CodeGen(tree, prog, filename, standalone).generate()
