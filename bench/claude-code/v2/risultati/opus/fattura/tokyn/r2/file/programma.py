# Generato da Tokyn 0.1.0 a partire da programma.tokyn.
# Non modificare questo file: modifica il sorgente .tokyn e ricompila.
# File autonomo: il runtime di Tokyn è incluso qui sotto, serve solo `pip install anthropic`.
import types as __types
__rt = __types.ModuleType('tokyn_runtime')
exec(compile(r'''"""Runtime di Tokyn: tipi strutturati, strumenti, agenti e funzioni di base.

Il codice Python generato dal compilatore importa questo modulo.
"""

from __future__ import annotations

import datetime as _dt
import json as _json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time as _time
import urllib.request as _urlreq

class TokynRuntimeError(Exception):
    """Errore durante l'esecuzione, già tradotto in un messaggio chiaro."""

    def __init__(self, message: str, line: int = 0, hint: str = ""):
        self.message = message
        self.line = line
        self.hint = hint
        self.bad_request = False  # l'API ha rifiutato i parametri della richiesta (errore 400)
        super().__init__(message)

DEFAULT_MODELS = {
    "claude": "claude-sonnet-5-5",
    "claude-sonnet": "claude-sonnet-5-5",
    "claude-opus": "claude-opus-5-5",
    "claude-haiku": "claude-haiku-5-5",
}
FINAL_TOOL = "rispondi"
EFFORTS = ("low", "medium", "high", "xhigh", "max")
MAX_TOKENS = 16000  # il thinking è sempre attivo sui modelli attuali e conta nei token della risposta
# Se l'IA rifiuta una richiesta, l'API la riprova da sola su un altro modello (Claude API; Haiku non lo prevede).
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5", "claude-fable-5-1"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_TYPES: dict[str, type] = {}


# ======================================================================= tipi


class _Spec:
    def __init__(self, kind, arg=None):
        self.kind = kind
        self.arg = arg

    def __repr__(self):
        return f"T.{self.kind}({self.arg!r})" if self.arg is not None else f"T.{self.kind}"


class T:
    STR = _Spec("str")
    INT = _Spec("int")
    FLOAT = _Spec("float")
    BOOL = _Spec("bool")
    DICT = _Spec("dict")
    ANY = _Spec("any")

    @staticmethod
    def list(of):
        return _Spec("list", of)

    @staticmethod
    def enum(*values):
        return _Spec("enum", tuple(values))

    @staticmethod
    def ref(name):
        return _Spec("ref", name)


def json_schema(spec: _Spec, description: str | None = None) -> dict:
    k = spec.kind
    if k == "str":
        s = {"type": "string"}
    elif k == "int":
        s = {"type": "integer"}
    elif k == "float":
        s = {"type": "number"}
    elif k == "bool":
        s = {"type": "boolean"}
    elif k == "dict":
        s = {"type": "object"}
    elif k == "list":
        s = {"type": "array", "items": json_schema(spec.arg)}
    elif k == "enum":
        s = {"type": "string", "enum": list(spec.arg)}
    elif k == "ref":
        s = _TYPES[spec.arg].__tokyn_schema__()
    else:
        s = {}
    if description:
        s = dict(s, description=description)
    return s


def convert(value, spec: _Spec, where: str = "valore"):
    """Valida e converte un valore (es. arrivato dall'IA) secondo il tipo dichiarato."""
    k = spec.kind
    if k == "any":
        return value
    if k == "str":
        if not isinstance(value, str):
            raise ValueError(f"{where}: atteso un testo, ricevuto {value!r}")
        return value
    if k == "int":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
            raise ValueError(f"{where}: atteso un numero intero, ricevuto {value!r}")
        return int(value)
    if k == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{where}: atteso un numero, ricevuto {value!r}")
        return float(value)
    if k == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{where}: atteso True/False, ricevuto {value!r}")
        return value
    if k == "dict":
        if not isinstance(value, dict):
            raise ValueError(f"{where}: atteso un oggetto, ricevuto {value!r}")
        return value
    if k == "enum":
        if value not in spec.arg:
            raise ValueError(f"{where}: {value!r} non è tra i valori possibili {list(spec.arg)}")
        return value
    if k == "list":
        if not isinstance(value, list):
            raise ValueError(f"{where}: attesa una lista, ricevuto {value!r}")
        return [convert(v, spec.arg, f"{where}[{i}]") for i, v in enumerate(value)]
    if k == "ref":
        cls = _TYPES[spec.arg]
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise ValueError(f"{where}: atteso un oggetto {spec.arg}, ricevuto {value!r}")
        return cls._from_dict(value, where)
    return value


def to_plain(value):
    """Converte record e liste in dati JSON."""
    if hasattr(value, "__tokyn_fields__"):
        return {k: to_plain(getattr(value, k)) for k in value.__tokyn_fields__}
    if isinstance(value, list):
        return [to_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    return value


def make_type(name: str, fields: dict) -> type:
    """Crea la classe Python per un `type` di Tokyn. fields: nome -> (spec, descrizione)."""

    def __init__(self, **kwargs):
        for fname, (spec, _d) in fields.items():
            if fname not in kwargs:
                raise TokynRuntimeError(f'manca il campo "{fname}" per creare {name}')
            object.__setattr__(self, fname, convert(kwargs.pop(fname), spec, f"{name}.{fname}"))
        if kwargs:
            extra = ", ".join(kwargs)
            raise TokynRuntimeError(f"{name} non ha i campi: {extra}")

    def __setattr__(self, key, value):
        if key not in fields:
            raise TokynRuntimeError(f'{name} non ha il campo "{key}"')
        object.__setattr__(self, key, convert(value, fields[key][0], f"{name}.{key}"))

    def __repr__(self):
        inner = ", ".join(f"{k}={getattr(self, k)!r}" for k in fields)
        return f"{name}({inner})"

    def __eq__(self, other):
        return type(other) is type(self) and to_plain(self) == to_plain(other)

    @classmethod
    def _from_dict(cls, data: dict, where: str = name):
        unknown = [k for k in data if k not in fields]
        if unknown:
            raise ValueError(f"{where}: campi sconosciuti {unknown}")
        obj = cls.__new__(cls)
        for fname, (spec, _d) in fields.items():
            if fname not in data:
                raise ValueError(f'{where}: manca il campo "{fname}"')
            object.__setattr__(obj, fname, convert(data[fname], spec, f"{where}.{fname}"))
        return obj

    @classmethod
    def __tokyn_schema__(cls):
        return {
            "type": "object",
            "properties": {k: json_schema(s, d) for k, (s, d) in fields.items()},
            "required": list(fields),
            "additionalProperties": False,
        }

    cls = type(name, (), {
        "__init__": __init__,
        "__setattr__": __setattr__,
        "__repr__": __repr__,
        "__str__": __repr__,
        "__eq__": __eq__,
        "__hash__": None,
        "_from_dict": _from_dict,
        "__tokyn_schema__": __tokyn_schema__,
        "__tokyn_fields__": tuple(fields),
        "__tokyn_specs__": {k: s for k, (s, _d) in fields.items()},
        "to_dict": lambda self: to_plain(self),
    })
    _TYPES[name] = cls
    return cls


# ======================================================================= strumenti


def tool(name: str, description: str | None, params: dict, returns: _Spec):
    """Decoratore applicato a ogni `def`: la rende usabile come strumento da un agente."""

    def deco(fn):
        fn.__tokyn_tool__ = {
            "name": name,
            "description": description or name,
            "params": params,
            "returns": returns,
        }
        return fn

    return deco


def strict_ok(spec: _Spec, seen=()) -> bool:
    """Gli schemi rigidi (strict, output strutturati) vogliono oggetti con campi noti: niente `dict` liberi né ricorsione."""
    k = spec.kind
    if k in ("dict", "any"):
        return False
    if k == "list":
        return strict_ok(spec.arg, seen)
    if k == "ref":
        if spec.arg in seen:
            return False
        return all(strict_ok(s, seen + (spec.arg,)) for s in _TYPES[spec.arg].__tokyn_specs__.values())
    return True


def _tool_schema(obj) -> dict:
    if isinstance(obj, Agent):
        return {
            "name": obj.name,
            "description": f"Chiede all'agente {obj.name}. " + obj.instructions[:300],
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {"richiesta": {"type": "string", "description": "il testo da passare all'agente"}},
                "required": ["richiesta"],
                "additionalProperties": False,
            },
        }
    meta = obj.__tokyn_tool__
    schema = {
        "name": meta["name"],
        "description": meta["description"],
        "input_schema": {
            "type": "object",
            "properties": {p: json_schema(s) for p, s in meta["params"].items()},
            "required": list(meta["params"]),
            "additionalProperties": False,
        },
    }
    if all(strict_ok(s) for s in meta["params"].values()):
        schema["strict"] = True  # l'IA non può passare argomenti che non rispettano i tipi
    return schema


def _call_tool(obj, args: dict):
    if isinstance(obj, Agent):
        result = obj.ask(str(args.get("richiesta", "")))
    else:
        meta = obj.__tokyn_tool__
        converted = {}
        for p, spec in meta["params"].items():
            if p in args:
                converted[p] = convert(args[p], spec, p)
        result = obj(**converted)
    result = to_plain(result)
    return result if isinstance(result, str) else _json.dumps(result, ensure_ascii=False, default=str)


# ======================================================================= agenti


class Agent:
    def __init__(self, name, instructions, model="claude", tools=(), output=None, memory=False, max_steps=10, effort=None):
        self.name = name
        self.instructions = textwrap.dedent(str(instructions)).strip()
        self.model = model
        self.tools = list(tools)
        self.output = output
        self.memory = memory
        self.max_steps = max_steps
        self.effort = effort
        self._history: list[dict] = []
        self._mock_calls = 0
        self._tools_by_name = {(t.name if isinstance(t, Agent) else t.__tokyn_tool__["name"]): t for t in self.tools}
        # Output strutturati nativi dell'API quando lo schema lo permette, altrimenti lo strumento `rispondi`.
        self._native_output = output is not None and strict_ok(T.ref(output.__name__))

    def __repr__(self):
        return f"<agent {self.name}>"

    def reset(self):
        self._history = []

    # ---------------------------------------------------------------- ask
    def ask(self, text):
        text = str(text)
        if _use_mock(self.model):
            answer, final_text = _mock_answer(self, text)
        elif _backend() == "claude-code":
            answer, final_text = _claude_code_ask(self, text, self._history)
        else:
            answer, final_text = self._run(list(self._history) + [{"role": "user", "content": text}])
        if self.memory:
            self._history += [
                {"role": "user", "content": text},
                {"role": "assistant", "content": final_text or "(nessuna risposta)"},
            ]
        return answer

    def ask_all(self, texts):
        """Come un ciclo di ask, ma con la Batch API: costa la metà e restituisce le risposte nello stesso ordine.

        È più lento (di solito minuti) e non usa la memoria: ogni testo è una richiesta a sé.
        """
        if isinstance(texts, (str, dict)) or not hasattr(texts, "__iter__"):
            raise TokynRuntimeError(f"{self.name}.ask_all vuole una lista di testi",
                                    hint=f"Per un testo solo usa {self.name}.ask(testo).")
        texts = [str(t) for t in texts]
        if _use_mock(self.model):
            return [_mock_answer(self, t)[0] for t in texts]
        if _backend() == "claude-code":  # la Batch API c'è solo con la chiave: una richiesta alla volta
            return [_claude_code_ask(self, t, [])[0] for t in texts]
        return self._run_batch(texts) if texts else []

    def _system(self):
        system = self.instructions
        if self.output is not None and not self._native_output:
            system += (
                f"\n\nQuando hai finito, chiama sempre lo strumento `{FINAL_TOOL}` con la risposta finale "
                "nel formato richiesto. Non rispondere solo con testo."
            )
        return system

    def _request(self, messages):
        """Parametri di una chiamata all'IA, uguali per la chiamata normale e per la Batch API."""
        params = dict(
            model=DEFAULT_MODELS.get(self.model, self.model),
            max_tokens=MAX_TOKENS,
            # istruzioni e strumenti non cambiano: un punto di cache fisso, più la cache automatica della conversazione
            system=[{"type": "text", "text": self._system(), "cache_control": {"type": "ephemeral"}}],
            cache_control={"type": "ephemeral"},
            messages=messages,
        )
        tools = [_tool_schema(t) for t in self.tools]
        output_config = {"effort": self.effort} if self.effort else {}
        if self.output is not None:
            if self._native_output:
                output_config["format"] = {"type": "json_schema", "schema": self.output.__tokyn_schema__()}
            else:
                tools.append({
                    "name": FINAL_TOOL,
                    "description": "Consegna la risposta finale nel formato richiesto.",
                    "input_schema": self.output.__tokyn_schema__(),
                })
        if tools:
            params["tools"] = tools
        if output_config:
            params["output_config"] = output_config
        return params

    def _step(self, response, messages, batch=False):
        """Elabora una risposta dell'IA: esegue gli strumenti richiesti o riconosce la risposta finale.

        Restituisce (finito, valore, testo da ricordare); se non ha finito, `messages` è pronto per il passaggio dopo.
        """
        _count_usage(response, batch)
        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise TokynRuntimeError(
                f"l'IA ha rifiutato la richiesta dell'agente {self.name}" + (f" (categoria: {category})" if category else ""),
                hint="Riformula le instructions o il testo della richiesta.")
        stop = getattr(response, "stop_reason", None)
        if stop == "model_context_window_exceeded":
            raise TokynRuntimeError(f"la conversazione dell'agente {self.name} non sta più nel contesto del modello",
                                    hint="Usa Agente.reset() più spesso, memory: False o testi più corti.")
        if stop == "max_tokens":  # anche gli strumenti avrebbero un input troncato: non si eseguono
            thinking_only = not any(getattr(b, "type", "") in ("text", "tool_use") for b in response.content)
            raise TokynRuntimeError(
                f"la risposta dell'agente {self.name} è stata interrotta perché troppo lunga",
                hint="Usa un effort più basso." if thinking_only else "Chiedi nelle instructions una risposta più breve.")
        messages.append({"role": "assistant", "content": [_plain(b) for b in response.content]})
        uses = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
        texts = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()

        if not uses:
            if self.output is None:
                return True, texts, texts
            if self._native_output:
                try:
                    return True, self.output._from_dict(_json.loads(texts), self.output.__name__), texts
                except ValueError as err:  # anche JSON non valido
                    messages.append({"role": "user", "content": f"La risposta non è nel formato richiesto ({err}). "
                                                                 "Rispondi di nuovo solo con il JSON richiesto."})
                    return False, None, None
            messages.append({"role": "user", "content": f"Ora chiama lo strumento `{FINAL_TOOL}` con la risposta finale."})
            return False, None, None

        results = []
        for use in uses:
            if use.name == FINAL_TOOL and self.output is not None and not self._native_output:
                try:
                    value = self.output._from_dict(dict(use.input), self.output.__name__)
                    return True, value, _json.dumps(to_plain(value), ensure_ascii=False)
                except ValueError as err:
                    results.append({"type": "tool_result", "tool_use_id": use.id, "is_error": True,
                                    "content": f"Formato non valido: {err}. Riprova."})
                continue
            target = self._tools_by_name.get(use.name)
            if target is None:
                results.append({"type": "tool_result", "tool_use_id": use.id, "is_error": True,
                                "content": f"Lo strumento {use.name} non esiste."})
                continue
            try:
                content = _call_tool(target, dict(use.input))
                results.append({"type": "tool_result", "tool_use_id": use.id, "content": content})
            except Exception as err:  # l'errore torna all'IA, che può correggersi
                results.append({"type": "tool_result", "tool_use_id": use.id, "is_error": True,
                                "content": f"Errore: {err}"})
        messages.append({"role": "user", "content": results})
        return False, None, None

    def _too_many_steps(self):
        return TokynRuntimeError(
            f"l'agente {self.name} non ha finito entro {self.max_steps} passaggi",
            hint="Aumenta max_steps nell'agente o rendi le instructions più precise.",
        )

    def _run(self, messages, steps_done=0):
        for _step in range(steps_done, self.max_steps):
            done, value, final_text = self._step(_create(self._request(messages), self.name), messages)
            if done:
                return value, final_text
        raise self._too_many_steps()

    def _run_batch(self, texts):
        """Un batch per ogni passaggio: i testi che chiedono strumenti proseguono nel batch successivo."""
        client = _client()
        pending = {str(i): [{"role": "user", "content": t}] for i, t in enumerate(texts)}
        answers, failures = {}, {}
        for step in range(self.max_steps):
            if not pending:
                break
            requests = [{"custom_id": cid, "params": self._request(msgs)} for cid, msgs in pending.items()]
            batch = _with_retry(lambda: client.messages.batches.create(requests=requests), self.name)
            batch = _wait_batch(client, batch, self.name)
            retry = []
            for entry in client.messages.batches.results(batch.id):
                cid = entry.custom_id
                message = entry.result.message if entry.result.type == "succeeded" else None
                if message is None or getattr(message, "stop_reason", None) == "refusal":
                    # errore, scadenza o rifiuto: si riprova con la chiamata normale (che ha anche i fallback)
                    retry.append(cid)
                    continue
                try:
                    done, value, _ = self._step(message, pending[cid], batch=True)
                except TokynRuntimeError as err:
                    failures[cid] = err
                    del pending[cid]
                    continue
                if done:
                    answers[cid] = value
                    del pending[cid]
            for cid in sorted(retry, key=int):  # nell'ordine della lista
                try:
                    answers[cid], _ = self._run(pending.pop(cid), steps_done=step)
                except TokynRuntimeError as err:
                    failures[cid] = err
        for cid in pending:
            failures[cid] = self._too_many_steps()
        if failures:
            first = min(failures, key=int)
            raise TokynRuntimeError(
                f"{self.name}.ask_all: {len(failures)} testi su {len(texts)} senza risposta; il primo è testi[{first}] "
                f"({texts[int(first)][:40]!r}): {failures[first].message}", hint=failures[first].hint)
        return [answers[str(i)] for i in range(len(texts))]


def _plain(block):
    """Blocchi della risposta come dati semplici, da rimandare tali e quali all'API (anche dentro un batch)."""
    return block.to_dict() if hasattr(block, "to_dict") else block


def _wait_batch(client, batch, agent_name):
    delay = 5.0
    reported = None
    while batch.processing_status != "ended":
        counts = batch.request_counts
        done = counts.succeeded + counts.errored + counts.canceled + counts.expired
        total = done + counts.processing
        if done != reported:
            print(f"[tokyn] {agent_name}.ask_all: {done}/{total} risposte pronte…", file=sys.stderr, flush=True)
            reported = done
        _time.sleep(delay)
        delay = min(delay * 1.5, 60.0)
        batch = _with_retry(lambda: client.messages.batches.retrieve(batch.id), agent_name)
    return batch


_USAGE = {"chiamate": 0, "chiamate_batch": 0, "chiamate_claude_code": 0, "costo_claude_code": 0.0, "fallback": 0,
          "input": 0, "output": 0, "cache_lette": 0, "cache_scritte": 0}


def _count_usage(response, batch=False):
    _USAGE["chiamate_batch" if batch else "chiamate"] += 1
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    # con un fallback lato server ogni tentativo si paga: usage.iterations li elenca tutti
    parts = getattr(usage, "iterations", None) or [usage]
    _USAGE["fallback"] += sum(1 for p in parts if getattr(p, "type", "") == "fallback_message")
    for part in parts:
        _USAGE["input"] += getattr(part, "input_tokens", 0) or 0
        _USAGE["output"] += getattr(part, "output_tokens", 0) or 0
        _USAGE["cache_lette"] += getattr(part, "cache_read_input_tokens", 0) or 0
        _USAGE["cache_scritte"] += getattr(part, "cache_creation_input_tokens", 0) or 0


def usage_report() -> str:
    u = _USAGE
    report = (f"token: {u['input']} in ingresso, {u['output']} in uscita, {u['cache_lette']} letti dalla cache, "
              f"{u['cache_scritte']} scritti in cache ({u['chiamate']} chiamate, {u['chiamate_batch']} nella Batch API a metà prezzo)")
    if u["fallback"]:
        report += f"; {u['fallback']} risposte da un modello di riserva dopo un rifiuto"
    if u["chiamate_claude_code"]:
        report += (f"; {u['chiamate_claude_code']} tramite Claude Code "
                   f"(valore indicativo a prezzi API: ${u['costo_claude_code']:.4f})")
    return report


# ======================================================================= Claude Code
#
# Senza chiave API gli agenti rispondono con il Claude Code di chi programma (`claude -p`): niente chiave,
# usa il suo account. Gli strumenti arrivano a Claude Code tramite un piccolo server MCP che passa ogni
# chiamata al programma Tokyn, così vengono eseguiti nel suo processo e vedono le stesse variabili.

CLAUDE_CODE_MODELS = {"claude": "sonnet", "claude-sonnet": "sonnet", "claude-opus": "opus", "claude-haiku": "haiku"}

# Server MCP minimo, senza dipendenze, avviato da Claude Code: legge le richieste JSON-RPC da stdin.
_BRIDGE = r"""
import json, socket, sys

cfg = json.load(open(sys.argv[1], encoding="utf-8"))


def reply(rid, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": rid}
    msg.update({"error": error} if error else {"result": result})
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    if not line.strip():
        continue
    req = json.loads(line)
    rid, method = req.get("id"), req.get("method")
    if rid is None:
        continue
    if method == "initialize":
        version = req.get("params", {}).get("protocolVersion", "2025-06-18")
        reply(rid, {"protocolVersion": version, "capabilities": {"tools": {}},
                    "serverInfo": {"name": "tokyn", "version": "1"}})
    elif method == "tools/list":
        reply(rid, {"tools": cfg["tools"]})
    elif method == "tools/call":
        with socket.create_connection(("127.0.0.1", cfg["port"])) as conn:
            conn.sendall((json.dumps({"token": cfg["token"], "call": req["params"]}) + "\n").encode("utf-8"))
            answer = json.loads(conn.makefile(encoding="utf-8").readline())
        reply(rid, {"content": [{"type": "text", "text": answer["text"]}], "isError": answer["error"]})
    elif method == "ping":
        reply(rid, {})
    else:
        reply(rid, error={"code": -32601, "message": "metodo sconosciuto: " + str(method)})
"""


_AVVISO_CLAUDE_CODE = []


def _backend() -> str:
    """Chi risponde agli agenti: l'API se c'è la chiave, altrimenti Claude Code se è installato. Se Claude Code è
    scelto da solo (non con TOKYN_BACKEND), avvisa una volta: per le regole di Anthropic l'abbonamento serve a usare
    Claude Code di persona, quindi va bene per provare un programma, non per farlo girare da solo o per altri."""
    choice = os.environ.get("TOKYN_BACKEND", "").strip().lower()
    if choice in ("api", "claude-code"):
        return choice
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "api"
    if not shutil.which("claude"):
        return "api"
    if not _AVVISO_CLAUDE_CODE:
        _AVVISO_CLAUDE_CODE.append(True)
        print("Tokyn: senza chiave API gli agenti rispondono con il tuo Claude Code. Va bene per provare il programma; "
              "se deve girare da solo o per altre persone serve una chiave dell'API di Anthropic "
              "(https://code.claude.com/docs/en/legal-and-compliance).", file=sys.stderr)
    return "claude-code"


class _ToolServer:
    """Esegue nel processo del programma gli strumenti che Claude Code chiama tramite il ponte MCP."""

    def __init__(self, agent):
        self.agent = agent
        self.token = secrets.token_hex(16)  # solo il ponte di questa chiamata può usare gli strumenti
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen()
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:  # server chiuso a fine chiamata
                return
            with conn:
                request = _json.loads(conn.makefile(encoding="utf-8").readline() or "{}")
                if request.get("token") != self.token:
                    continue
                call = request.get("call", {})
                target = self.agent._tools_by_name.get(call.get("name"))
                try:
                    if target is None:
                        raise ValueError(f"lo strumento {call.get('name')} non esiste")
                    text, error = _call_tool(target, call.get("arguments") or {}), False
                except Exception as err:  # l'errore torna all'IA, che può correggersi
                    text, error = f"Errore: {err}", True
                conn.sendall((_json.dumps({"text": text, "error": error}) + "\n").encode("utf-8"))

    def close(self):
        self.sock.close()


def _claude_code_ask(agent, text, history):
    prompt = text
    if history:  # la memoria: domande e risposte precedenti
        lines = [("Utente: " if m["role"] == "user" else "Tu: ") + str(m["content"]) for m in history]
        prompt = "Conversazione finora:\n" + "\n".join(lines) + "\n\nNuovo messaggio:\n" + text
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--no-session-persistence",
           "--system-prompt", agent.instructions, "--model", CLAUDE_CODE_MODELS.get(agent.model, agent.model),
           # niente strumenti, impostazioni, hook e comandi di Claude Code: solo l'agente Tokyn
           "--tools", "", "--setting-sources", "", "--disable-slash-commands", "--strict-mcp-config"]
    if agent.effort:
        cmd += ["--effort", agent.effort]
    if agent.output is not None:
        cmd += ["--json-schema", _json.dumps(agent.output.__tokyn_schema__())]
    server = workdir = None
    try:
        if agent.tools:
            server = _ToolServer(agent)
            workdir = tempfile.mkdtemp(prefix="tokyn-")
            files = {
                "bridge.py": _BRIDGE,
                "tools.json": _json.dumps({"port": server.port, "token": server.token, "tools": [
                    {"name": s["name"], "description": s["description"], "inputSchema": s["input_schema"]}
                    for s in (_tool_schema(t) for t in agent.tools)]}),
            }
            for name, content in files.items():
                with open(os.path.join(workdir, name), "w", encoding="utf-8") as f:
                    f.write(content)
            mcp = {"mcpServers": {"tokyn": {"command": sys.executable, "args": [
                os.path.join(workdir, "bridge.py"), os.path.join(workdir, "tools.json")]}}}
            cmd += ["--mcp-config", _json.dumps(mcp), "--allowedTools", "mcp__tokyn"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except FileNotFoundError:
            raise TokynRuntimeError("Claude Code non è installato (manca il comando `claude`)",
                                    hint="Installa Claude Code, oppure imposta ANTHROPIC_API_KEY per usare l'API.") from None
        except subprocess.TimeoutExpired:
            raise TokynRuntimeError(f"Claude Code non ha risposto entro 15 minuti per l'agente {agent.name}") from None
    finally:
        if server is not None:
            server.close()
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)
    try:
        result = _json.loads(proc.stdout)
    except ValueError:
        detail = (proc.stderr or proc.stdout).strip()[:300]
        raise TokynRuntimeError(f"Claude Code non ha risposto per l'agente {agent.name}: {detail}",
                                hint="Controlla di aver fatto il login: apri `claude` una volta e segui le istruzioni.") from None
    _count_claude_code(result)
    if result.get("is_error") or result.get("subtype") != "success" or result.get("stop_reason") == "refusal":
        raise TokynRuntimeError(f"Claude Code ha dato un errore per l'agente {agent.name}: "
                                f"{result.get('result') or result.get('subtype')}")
    if agent.output is None:
        answer = (result.get("result") or "").strip()
        return answer, answer
    data = result.get("structured_output")
    try:
        if data is None:
            data = _json.loads(result.get("result") or "")
        return agent.output._from_dict(data, agent.output.__name__), _json.dumps(data, ensure_ascii=False)
    except ValueError as err:
        raise TokynRuntimeError(f"la risposta dell'agente {agent.name} non è nel formato richiesto: {err}") from None


def _count_claude_code(result):
    usage = result.get("usage") or {}
    _USAGE["chiamate_claude_code"] += 1
    _USAGE["input"] += usage.get("input_tokens") or 0
    _USAGE["output"] += usage.get("output_tokens") or 0
    _USAGE["cache_lette"] += usage.get("cache_read_input_tokens") or 0
    _USAGE["cache_scritte"] += usage.get("cache_creation_input_tokens") or 0
    _USAGE["costo_claude_code"] += result.get("total_cost_usd") or 0


def _use_mock(model) -> bool:
    return model == "mock" or os.environ.get("TOKYN_MOCK") == "1"


_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise TokynRuntimeError(
            "manca la chiave ANTHROPIC_API_KEY",
            hint="Impostala come variabile d'ambiente, oppure installa Claude Code (Tokyn lo usa da solo quando manca "
                 "la chiave), oppure prova il programma senza IA con: tokyn run file.tokyn --mock",
        )
    try:
        import anthropic
    except ImportError:
        raise TokynRuntimeError("manca il pacchetto anthropic", hint="Installa con: pip install anthropic") from None
    _CLIENT = anthropic.Anthropic()
    return _CLIENT


_FALLBACKS = {"attivi": True}


def _create(params, agent_name):
    """Una chiamata all'IA. Sui modelli che lo prevedono chiede all'API di riprovare su un altro modello se rifiuta."""
    client = _client()
    if _FALLBACKS["attivi"] and params["model"] in FALLBACK_MODELS:
        try:
            return _with_retry(lambda: client.beta.messages.create(**params, betas=[FALLBACK_BETA], fallbacks="default"),
                               agent_name)
        except TokynRuntimeError as err:
            if not (err.bad_request and "fallback" in err.message.lower()):
                raise
            _FALLBACKS["attivi"] = False  # l'API non accetta i fallback per questa chiave: si prosegue senza
    return _with_retry(lambda: client.messages.create(**params), agent_name)


def _with_retry(fn, agent_name, attempts=3):
    delay = 2.0
    for i in range(attempts):
        try:
            return fn()
        except Exception as err:
            name = type(err).__name__
            retryable = (name in ("RateLimitError", "APIConnectionError", "APITimeoutError")
                         or (getattr(err, "status_code", 0) or 0) >= 500)
            if not retryable or i == attempts - 1:
                if name == "AuthenticationError":
                    raise TokynRuntimeError("la chiave ANTHROPIC_API_KEY non è valida") from None
                if name == "NotFoundError":
                    raise TokynRuntimeError(f"modello non trovato per l'agente {agent_name}",
                                            hint='Usa model: "claude", "claude-opus" o "claude-haiku".') from None
                failure = TokynRuntimeError(f"chiamata all'IA fallita per l'agente {agent_name}: {err}")
                failure.bad_request = name == "BadRequestError"
                raise failure from None
            _time.sleep(delay)
            delay *= 2


# ======================================================================= mock


def _example(spec: _Spec, field: str = "", n: int = 0):
    """Valore finto per un campo. n (numero della chiamata) fa variare scelte e bool tra una ask e l'altra."""
    k = spec.kind
    if k == "str":
        return f"esempio {field}".strip()
    if k == "int":
        return 1
    if k == "float":
        return 1.0
    if k == "bool":
        return n % 2 == 0
    if k == "dict":
        return {}
    if k == "enum":
        return spec.arg[n % len(spec.arg)]
    if k == "list":
        return [_example(spec.arg, field, n), _example(spec.arg, field, n + 1)]
    if k == "ref":
        cls = _TYPES[spec.arg]
        return {f: _example(cls.__tokyn_specs__[f], f, n) for f in cls.__tokyn_fields__}
    return None


def _mock_answer(agent: Agent, text: str):
    """Risposta finta e prevedibile: permette di provare un programma senza API key."""
    n = agent._mock_calls
    agent._mock_calls += 1
    if agent.output is not None:
        cls = agent.output
        data = {f: _example(cls.__tokyn_specs__[f], f, n) for f in cls.__tokyn_fields__}
        value = cls._from_dict(data)
        return value, _json.dumps(data, ensure_ascii=False)
    short = text if len(text) <= 60 else text[:57] + "..."
    answer = f"[mock {agent.name}] risposta a: {short}"
    return answer, answer


# ======================================================================= funzioni di base


_NO_DEFAULT = object()


def read_file(path, default=_NO_DEFAULT):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, ValueError) as err:  # file mancante, cartella, permessi, testo non UTF-8
        if default is not _NO_DEFAULT:
            return default
        message = f'il file "{path}" non esiste' if isinstance(err, FileNotFoundError) else f'impossibile leggere "{path}": {err}'
        raise TokynRuntimeError(message, hint=f'Se può mancare, dai un valore di riserva: read_file("{path}", "")') from None


def write_file(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(text))


def append_file(path, text):
    with open(path, "a", encoding="utf-8") as f:
        f.write(str(text))


def _http(call, url, default, body=None):
    headers = {"User-Agent": "tokyn/0.1"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    try:
        req = _urlreq.Request(str(url), data=body, headers=headers, method="POST" if body is not None else "GET")
        with _urlreq.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as err:  # rete, HTTP 4xx/5xx, timeout, indirizzo non valido
        if default is not _NO_DEFAULT:
            return default
        reason = getattr(err, "reason", None) or err
        raise TokynRuntimeError(f"{call} fallita per {url}: {reason}",
                                hint=f"Se può fallire, dai un valore di riserva come ultimo argomento: {call}(..., \"\")") from None


def http_get(url, default=_NO_DEFAULT):
    return _http("http_get", url, default)


def http_post(url, data, default=_NO_DEFAULT):
    body = data if isinstance(data, str) else _json.dumps(to_plain(data))
    return _http("http_post", url, default, body.encode("utf-8"))


def json_parse(text, default=_NO_DEFAULT):
    try:
        return _json.loads(text)
    except (ValueError, TypeError) as err:
        if default is not _NO_DEFAULT:
            return default
        detail = f"{err.msg}, riga {err.lineno}" if isinstance(err, _json.JSONDecodeError) else str(err)
        raise TokynRuntimeError(f"il testo non è JSON valido ({detail})",
                                hint="Se può non esserlo, dai un valore di riserva: json_parse(testo, {})") from None


def to_number(text, default=_NO_DEFAULT):
    """Da testo a numero: "42" -> 42, "4,50" -> 4.5, "1.234,56" -> 1234.56. Se non è un numero restituisce default."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return text
    s = str(text).strip().replace(" ", "")
    if "," in s and "." in s:  # separatore delle migliaia: vale quello che viene prima
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif s.count(",") > 1 or s.count(".") > 1:  # "1.234.567": solo migliaia
        s = s.replace(",", "").replace(".", "")
    else:
        s = s.replace(",", ".")
    try:
        return int(s)
    except ValueError:
        pass
    try:
        value = float(s)
        if value == value and value not in (float("inf"), float("-inf")):  # niente "nan" o "inf"
            return value
    except ValueError:
        pass
    if default is not _NO_DEFAULT:
        return default
    raise TokynRuntimeError(f"{text!r} non è un numero",
                            hint="Se può non esserlo, dai un valore di riserva: to_number(testo, 0)")


def json_dump(value):
    return _json.dumps(to_plain(value), ensure_ascii=False, indent=2, default=str)


def env(name, default=_NO_DEFAULT):
    value = os.environ.get(name, default)
    if value is _NO_DEFAULT:
        raise TokynRuntimeError(f'la variabile d\'ambiente "{name}" non è impostata',
                                hint=f'Impostala, oppure dai un valore di riserva: env("{name}", "...")')
    return value


def now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def sleep(seconds):
    _time.sleep(seconds)


def run_main(main):
    main()
''', 'tokyn_runtime', 'exec'), __rt.__dict__)
read_file, write_file, append_file, http_get, http_post, json_parse, json_dump, env, now, sleep, to_number = __rt.read_file, __rt.write_file, __rt.append_file, __rt.http_get, __rt.http_post, __rt.json_parse, __rt.json_dump, __rt.env, __rt.now, __rt.sleep, __rt.to_number
from decimal import Decimal, ROUND_HALF_UP

Riga = __rt.make_type('Riga', {
    'descrizione': (__rt.T.STR, "descrizione dell'articolo come scritta in fattura"),
    'quantita': (__rt.T.FLOAT, None),
    'prezzo_unitario': (__rt.T.FLOAT, 'prezzo unitario in euro'),
})

Fattura = __rt.make_type('Fattura', {
    'fornitore': (__rt.T.STR, 'ragione sociale di chi emette la fattura, non del cliente'),
    'data': (__rt.T.STR, 'data della fattura nel formato AAAA-MM-GG'),
    'righe': (__rt.T.list(__rt.T.ref('Riga')), "tutte le righe, nell'ordine della fattura"),
    'totale_dichiarato': (__rt.T.FLOAT, 'totale da pagare scritto in fattura, in euro'),
})

@__rt.tool('numero', None, {'x': __rt.T.FLOAT}, __rt.T.ANY)
def numero(x):
    if x == int(x):
        return int(x)
    return x

@__rt.tool('euro', None, {'x': __rt.T.FLOAT}, __rt.T.ANY)
def euro(x):
    return Decimal(str(x))

Lettore = __rt.Agent(
    name='Lettore',
    instructions="""
        Estrai i dati da una fattura di un fornitore in testo semplice.
        Riporta i numeri esattamente come scritti in fattura, convertiti in numeri
        (es. "1.234,50" diventa 1234.5). Non ricalcolare né correggere nulla.
    """,
    output=Fattura,
    effort="low",
)

def __tokyn_main__():
    f = Lettore.ask(read_file("fattura.txt"))
    righe = []
    totale = Decimal("0")
    for r in f.righe:
        totale += euro(r.quantita) * euro(r.prezzo_unitario)
        righe.append({"descrizione": r.descrizione, "quantita": numero(r.quantita), "prezzo_unitario": r.prezzo_unitario})
    calcolato = totale.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    dichiarato = euro(f.totale_dichiarato).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    risultato = {"fornitore": f.fornitore, "data": f.data, "righe": righe, "totale_dichiarato": float(dichiarato), "totale_calcolato": float(calcolato), "totale_corretto": calcolato == dichiarato}
    write_file("risultato.json", json_dump(risultato))
    print(json_dump(risultato))
    if calcolato == dichiarato:
        print("Il totale in fattura è corretto.")
    else:
        print(f"Il totale in fattura NON è corretto: differenza {float(dichiarato - calcolato):.2f} €")

if __name__ == "__main__":
    __rt.run_main(__tokyn_main__)
