"""Runtime di Tokyn: tipi strutturati, strumenti, agenti e funzioni di base.

Il codice Python generato dal compilatore importa questo modulo.
"""

from __future__ import annotations

import datetime as _dt
import email.utils as _eutils
import json as _json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time as _time
import http.client as _httpc
import urllib.error as _urlerr
import urllib.request as _urlreq

from .errors import TokynRuntimeError
from .lingua import tr

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


def convert(value, spec: _Spec, where: str | None = None):
    """Valida e converte un valore (es. arrivato dall'IA) secondo il tipo dichiarato."""
    where = tr("valore", "value") if where is None else where
    k = spec.kind
    if k == "any":
        return value
    if k == "str":
        if not isinstance(value, str):
            raise ValueError(tr(f"{where}: atteso un testo, ricevuto {value!r}", f"{where}: expected a text, got {value!r}"))
        return value
    if k == "int":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
            raise ValueError(tr(f"{where}: atteso un numero intero, ricevuto {value!r}", f"{where}: expected a whole number, got {value!r}"))
        return int(value)
    if k == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(tr(f"{where}: atteso un numero, ricevuto {value!r}", f"{where}: expected a number, got {value!r}"))
        return float(value)
    if k == "bool":
        if not isinstance(value, bool):
            raise ValueError(tr(f"{where}: atteso True/False, ricevuto {value!r}", f"{where}: expected True/False, got {value!r}"))
        return value
    if k == "dict":
        if not isinstance(value, dict):
            raise ValueError(tr(f"{where}: atteso un oggetto, ricevuto {value!r}", f"{where}: expected an object, got {value!r}"))
        return value
    if k == "enum":
        if value not in spec.arg:
            raise ValueError(tr(f"{where}: {value!r} non è tra i valori possibili {list(spec.arg)}",
                                f"{where}: {value!r} is not one of the possible values {list(spec.arg)}"))
        return value
    if k == "list":
        if not isinstance(value, list):
            raise ValueError(tr(f"{where}: attesa una lista, ricevuto {value!r}", f"{where}: expected a list, got {value!r}"))
        return [convert(v, spec.arg, f"{where}[{i}]") for i, v in enumerate(value)]
    if k == "ref":
        cls = _TYPES[spec.arg]
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise ValueError(tr(f"{where}: atteso un oggetto {spec.arg}, ricevuto {value!r}",
                                f"{where}: expected a {spec.arg} object, got {value!r}"))
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
                raise TokynRuntimeError(tr(f'manca il campo "{fname}" per creare {name}', f'missing field "{fname}" to create {name}'))
            object.__setattr__(self, fname, convert(kwargs.pop(fname), spec, f"{name}.{fname}"))
        if kwargs:
            extra = ", ".join(kwargs)
            raise TokynRuntimeError(tr(f"{name} non ha i campi: {extra}", f"{name} has no fields: {extra}"))

    def __setattr__(self, key, value):
        if key not in fields:
            raise TokynRuntimeError(tr(f'{name} non ha il campo "{key}"', f'{name} has no field "{key}"'))
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
            raise ValueError(tr(f"{where}: campi sconosciuti {unknown}", f"{where}: unknown fields {unknown}"))
        obj = cls.__new__(cls)
        for fname, (spec, _d) in fields.items():
            if fname not in data:
                raise ValueError(tr(f'{where}: manca il campo "{fname}"', f'{where}: missing field "{fname}"'))
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
        ricordo = None  # con gli altri fornitori la risposta da ricordare porta anche i campi nascosti
        if _use_mock(self.model):
            answer, final_text = _mock_answer(self, text)
        elif _fornitore(self.model):
            answer, final_text, ricordo = _chiedi_chat(self, text, self._history)
        elif _backend() == "claude-code":
            answer, final_text = _claude_code_ask(self, text, self._history)
        else:
            answer, final_text = self._run(list(self._history) + [{"role": "user", "content": text}])
        if self.memory:
            self._history += [
                {"role": "user", "content": text},
                ricordo or {"role": "assistant", "content": final_text or "(nessuna risposta)"},
            ]
        return answer

    def ask_all(self, texts):
        """Come un ciclo di ask, ma con la Batch API: costa la metà e restituisce le risposte nello stesso ordine.

        È più lento (di solito minuti) e non usa la memoria: ogni testo è una richiesta a sé.
        Con gli altri fornitori (e con Claude Code) è un ciclo di ask senza memoria.
        """
        if isinstance(texts, (str, dict)) or not hasattr(texts, "__iter__"):
            raise TokynRuntimeError(tr(f"{self.name}.ask_all vuole una lista di testi", f"{self.name}.ask_all takes a list of texts"),
                                    hint=tr(f"Per un testo solo usa {self.name}.ask(testo).", f"For a single text use {self.name}.ask(text)."))
        texts = [str(t) for t in texts]
        if _use_mock(self.model):
            return [_mock_answer(self, t)[0] for t in texts]
        if _fornitore(self.model):  # gli altri fornitori non hanno la Batch API di Anthropic: una richiesta alla volta
            return [_chiedi_chat(self, t, [])[0] for t in texts]
        if _backend() == "claude-code":  # la Batch API c'è solo con la chiave: una richiesta alla volta
            return [_claude_code_ask(self, t, [])[0] for t in texts]
        return self._run_batch(texts) if texts else []

    def _system(self, final_tool=None):
        """Le istruzioni per l'IA; final_tool dice se l'output arriva con lo strumento `rispondi` (di solito si sa da solo)."""
        system = self.instructions
        if final_tool is None:
            final_tool = self.output is not None and not self._native_output
        if final_tool:
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
                tr(f"l'IA ha rifiutato la richiesta dell'agente {self.name}", f"the AI refused agent {self.name}'s request")
                + (tr(f" (categoria: {category})", f" (category: {category})") if category else ""),
                hint=tr("Riformula le instructions o il testo della richiesta.", "Rephrase the instructions or the text of the request."))
        stop = getattr(response, "stop_reason", None)
        if stop == "model_context_window_exceeded":
            raise TokynRuntimeError(tr(f"la conversazione dell'agente {self.name} non sta più nel contesto del modello",
                                       f"agent {self.name}'s conversation no longer fits in the model's context"),
                                    hint=tr("Usa Agente.reset() più spesso, memory: False o testi più corti.",
                                            "Use Agent.reset() more often, memory: False or shorter texts."))
        if stop == "max_tokens":  # anche gli strumenti avrebbero un input troncato: non si eseguono
            thinking_only = not any(getattr(b, "type", "") in ("text", "tool_use") for b in response.content)
            raise TokynRuntimeError(
                tr(f"la risposta dell'agente {self.name} è stata interrotta perché troppo lunga",
                   f"agent {self.name}'s answer was cut off because it was too long"),
                hint=tr("Usa un effort più basso.", "Use a lower effort.") if thinking_only
                else tr("Chiedi nelle instructions una risposta più breve.", "Ask for a shorter answer in the instructions."))
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
            tr(f"l'agente {self.name} non ha finito entro {self.max_steps} passaggi",
               f"agent {self.name} did not finish within {self.max_steps} steps"),
            hint=tr("Aumenta max_steps nell'agente o rendi le instructions più precise.",
                    "Raise max_steps in the agent or make the instructions more precise."),
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
            raise TokynRuntimeError(tr(
                f"{self.name}.ask_all: {len(failures)} testi su {len(texts)} senza risposta; il primo è testi[{first}] "
                f"({texts[int(first)][:40]!r}): {failures[first].message}",
                f"{self.name}.ask_all: {len(failures)} of {len(texts)} texts got no answer; the first is texts[{first}] "
                f"({texts[int(first)][:40]!r}): {failures[first].message}"), hint=failures[first].hint)
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
            print(tr(f"[tokyn] {agent_name}.ask_all: {done}/{total} risposte pronte…",
                     f"[tokyn] {agent_name}.ask_all: {done}/{total} answers ready…"), file=sys.stderr, flush=True)
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
    report = tr(f"token: {u['input']} in ingresso, {u['output']} in uscita, {u['cache_lette']} letti dalla cache, "
                f"{u['cache_scritte']} scritti in cache ({u['chiamate']} chiamate, {u['chiamate_batch']} nella Batch API a metà prezzo)",
                f"tokens: {u['input']} input, {u['output']} output, {u['cache_lette']} read from the cache, "
                f"{u['cache_scritte']} written to the cache ({u['chiamate']} call{'' if u['chiamate'] == 1 else 's'}, "
                f"{u['chiamate_batch']} in the Batch API at half price)")
    if u["fallback"]:
        report += tr(f"; {u['fallback']} risposte da un modello di riserva dopo un rifiuto",
                     f"; {u['fallback']} answer{'' if u['fallback'] == 1 else 's'} from a fallback model after a refusal")
    if _USO_FORNITORI:
        others = ", ".join(f"{nome} {n}" for nome, n in _USO_FORNITORI.items())
        report += tr(f"; chiamate ad altri fornitori: {others}", f"; calls to other providers: {others}")
    if u["chiamate_claude_code"]:
        report += tr(f"; {u['chiamate_claude_code']} tramite Claude Code "
                     f"(valore indicativo a prezzi API: ${u['costo_claude_code']:.4f})",
                     f"; {u['chiamate_claude_code']} through Claude Code "
                     f"(rough value at API prices: ${u['costo_claude_code']:.4f})")
    return report


# ======================================================================= Claude Code
#
# Senza chiave API gli agenti rispondono con il Claude Code di chi programma (`claude -p`): niente chiave,
# usa il suo account. Gli strumenti arrivano a Claude Code tramite un piccolo server MCP che passa ogni
# chiamata al programma Tokyn, così vengono eseguiti nel suo processo e vedono le stesse variabili.

CLAUDE_CODE_MODELS = {"claude": "sonnet", "claude-sonnet": "sonnet", "claude-opus": "opus", "claude-haiku": "haiku"}

# Il ponte MCP è un file vero del pacchetto, ponte_mcp.py, che Claude Code avvia con Python. Nei programmi autonomi
# (tokyn build --standalone) il ponte è incluso nel programma, che qui imposta il comando per avviarlo:
# [python, programma.py, "--tokyn-ponte"]. Al comando si aggiunge il percorso di tools.json.
_PONTE: list | None = None


def _comando_ponte() -> list:
    if _PONTE is not None:
        return list(_PONTE)
    qui = globals().get("__file__")  # manca quando il runtime è incluso in un programma autonomo
    percorso = os.path.join(os.path.dirname(os.path.abspath(qui)), "ponte_mcp.py") if qui else ""
    if not os.path.isfile(percorso):
        raise TokynRuntimeError(tr("manca il ponte MCP di Tokyn (ponte_mcp.py) che serve agli strumenti con Claude Code",
                                   "Tokyn's MCP bridge (ponte_mcp.py), needed for tools with Claude Code, is missing"),
                                hint=tr("Reinstalla Tokyn (un programma autonomo va avviato dal suo file .py), "
                                        "oppure imposta ANTHROPIC_API_KEY per usare l'API.",
                                        "Reinstall Tokyn (run a standalone program from its .py file), "
                                        "or set ANTHROPIC_API_KEY to use the API."))
    return [sys.executable, percorso]


_AVVISO_CLAUDE_CODE = []


def _backend() -> str:
    """Chi risponde agli agenti: l'API se c'è la chiave, altrimenti Claude Code se è installato. Se Claude Code è
    scelto da solo (non con TOKYN_BACKEND), avvisa una volta: per le regole di Anthropic l'abbonamento serve all'uso
    normale e personale di Claude Code, quindi va bene per provare i propri programmi, non per prodotti o per altri."""
    choice = os.environ.get("TOKYN_BACKEND", "").strip().lower()
    if choice in ("api", "claude-code"):
        return choice
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "api"
    if not shutil.which("claude"):
        return "api"
    if not _AVVISO_CLAUDE_CODE:
        _AVVISO_CLAUDE_CODE.append(True)
        print(tr("Tokyn: senza chiave API gli agenti rispondono con il tuo Claude Code e usano il tuo abbonamento. Va bene "
                 "per provare i tuoi programmi; un prodotto o un programma usato da altre persone deve usare una chiave "
                 "dell'API di Anthropic (https://code.claude.com/docs/en/legal-and-compliance).",
                 "Tokyn: without an API key the agents answer through your Claude Code and use your subscription. That is "
                 "fine for trying your own programs; a product, or a program other people use, must use an Anthropic API "
                 "key (https://code.claude.com/docs/en/legal-and-compliance)."), file=sys.stderr)
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
            ponte = _comando_ponte()
            server = _ToolServer(agent)
            # solo dati: gli strumenti, la porta e il token per il ponte (il codice del ponte è già un file)
            workdir = tempfile.mkdtemp(prefix="tokyn-")
            tools_path = os.path.join(workdir, "tools.json")
            with open(tools_path, "w", encoding="utf-8") as f:
                f.write(_json.dumps({"port": server.port, "token": server.token, "tools": [
                    {"name": s["name"], "description": s["description"], "inputSchema": s["input_schema"]}
                    for s in (_tool_schema(t) for t in agent.tools)]}))
            mcp = {"mcpServers": {"tokyn": {"command": ponte[0], "args": ponte[1:] + [tools_path]}}}
            cmd += ["--mcp-config", _json.dumps(mcp), "--allowedTools", "mcp__tokyn"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except FileNotFoundError:
            raise TokynRuntimeError(tr("Claude Code non è installato (manca il comando `claude`)",
                                       "Claude Code is not installed (the `claude` command is missing)"),
                                    hint=tr("Installa Claude Code, oppure imposta ANTHROPIC_API_KEY per usare l'API.",
                                            "Install Claude Code, or set ANTHROPIC_API_KEY to use the API.")) from None
        except subprocess.TimeoutExpired:
            raise TokynRuntimeError(tr(f"Claude Code non ha risposto entro 15 minuti per l'agente {agent.name}",
                                       f"Claude Code did not answer within 15 minutes for agent {agent.name}")) from None
    finally:
        if server is not None:
            server.close()
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)
    try:
        result = _json.loads(proc.stdout)
    except ValueError:
        detail = (proc.stderr or proc.stdout).strip()[:300]
        raise TokynRuntimeError(tr(f"Claude Code non ha risposto per l'agente {agent.name}: {detail}",
                                   f"Claude Code did not answer for agent {agent.name}: {detail}"),
                                hint=tr("Controlla di aver fatto il login: apri `claude` una volta e segui le istruzioni.",
                                        "Check that you are logged in: open `claude` once and follow the instructions.")) from None
    _count_claude_code(result)
    if result.get("is_error") or result.get("subtype") != "success" or result.get("stop_reason") == "refusal":
        raise TokynRuntimeError(tr(f"Claude Code ha dato un errore per l'agente {agent.name}: ",
                                   f"Claude Code returned an error for agent {agent.name}: ")
                                + f"{result.get('result') or result.get('subtype')}")
    if agent.output is None:
        answer = (result.get("result") or "").strip()
        return answer, answer
    data = result.get("structured_output")
    try:
        if data is None:
            data = _json.loads(result.get("result") or "")
        return agent.output._from_dict(data, agent.output.__name__), _json.dumps(data, ensure_ascii=False)
    except ValueError as err:
        raise TokynRuntimeError(tr(f"la risposta dell'agente {agent.name} non è nel formato richiesto: {err}",
                                   f"agent {agent.name}'s answer is not in the requested format: {err}")) from None


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
            tr("manca la chiave ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY is not set"),
            hint=tr("Impostala come variabile d'ambiente, oppure installa Claude Code (Tokyn lo usa da solo quando manca "
                    "la chiave), oppure prova il programma senza IA con: tokyn run file.tokyn --mock",
                    "Set it as an environment variable, or install Claude Code (Tokyn uses it on its own when the key "
                    "is missing), or try the program without AI with: tokyn run file.tokyn --mock"),
        )
    try:
        import anthropic
    except ImportError:
        raise TokynRuntimeError(tr("manca il pacchetto anthropic", "the anthropic package is missing"),
                                hint=tr("Installa il pacchetto Python anthropic.", "Install the anthropic Python package.")) from None
    version = getattr(anthropic, "__version__", "")
    if _sdk_too_old(version):  # prima della 0.108 l'SDK rifiuta `fallbacks` con un TypeError a ogni chiamata
        raise TokynRuntimeError(tr(f"il pacchetto anthropic è troppo vecchio ({version}): Tokyn vuole la 0.108 o successiva",
                                   f"the anthropic package is too old ({version}): Tokyn needs 0.108 or newer"),
                                hint=tr("Aggiorna il pacchetto Python anthropic alla versione 0.108 o successiva.",
                                        "Upgrade the anthropic Python package to version 0.108 or newer."))
    _CLIENT = anthropic.Anthropic()
    return _CLIENT


def _sdk_too_old(version: str) -> bool:
    """True per le versioni dell'SDK anthropic precedenti alla 0.108 (la minima in pyproject.toml)."""
    try:
        major, minor = (int(p) for p in str(version).split(".")[:2])
    except ValueError:  # versione mancante o non numerica: si prova lo stesso
        return False
    return (major, minor) < (0, 108)


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
                    raise TokynRuntimeError(tr("la chiave ANTHROPIC_API_KEY non è valida", "ANTHROPIC_API_KEY is not valid")) from None
                if name == "NotFoundError":
                    raise TokynRuntimeError(tr(f"modello non trovato per l'agente {agent_name}", f"model not found for agent {agent_name}"),
                                            hint=tr('Usa model: "claude", "claude-opus" o "claude-haiku".',
                                                    'Use model: "claude", "claude-opus" or "claude-haiku".')) from None
                failure = TokynRuntimeError(tr(f"chiamata all'IA fallita per l'agente {agent_name}: {err}",
                                               f"AI call failed for agent {agent_name}: {err}"))
                failure.bad_request = name == "BadRequestError"
                raise failure from None
            _time.sleep(delay)
            delay *= 2


# ======================================================================= altri fornitori
#
# Con model "fornitore:modello" (es. "openai:gpt-5.6-luna") l'agente usa l'API Chat Completions compatibile con
# OpenAI, chiamata con urllib: nessuna dipendenza in più, anche nei file autonomi. Si comporta come un agente Claude
# (istruzioni, strumenti, passaggi, output validati e ritentati, memoria); le differenze tra i fornitori vengono
# dalla loro documentazione, letta il 2026-10-29.

_ALTO = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}

# url: indirizzo dell'API; chiave: variabile con la chiave (None: non serve); max: il campo del limite di token;
# formato: output strutturati con schema rigido ("json_schema") o solo JSON libero ("json_object");
# effort: valore di reasoning_effort per ogni effort di Tokyn (senza, l'effort si ignora);
# strict: strumenti con schema rigido; campi_standard: l'API rifiuta i campi in più nei messaggi rimandati.
FORNITORI = {
    "openai": {"url": "https://api.openai.com/v1", "chiave": "OPENAI_API_KEY", "max": "max_completion_tokens",
               "formato": "json_schema", "effort": _ALTO, "strict": True},
    "gemini": {"url": "https://generativelanguage.googleapis.com/v1beta/openai", "chiave": "GEMINI_API_KEY",
               "max": "max_tokens", "formato": "json_schema", "effort": _ALTO},
    "mistral": {"url": "https://api.mistral.ai/v1", "chiave": "MISTRAL_API_KEY", "max": "max_tokens",
                "formato": "json_schema", "effort": {"high": "high", "xhigh": "high", "max": "high"},
                "campi_standard": True},
    "deepseek": {"url": "https://api.deepseek.com", "chiave": "DEEPSEEK_API_KEY", "max": "max_tokens",
                 "formato": "json_object",
                 "effort": {"low": "low", "medium": "high", "high": "high", "xhigh": "max", "max": "max"}},
    "groq": {"url": "https://api.groq.com/openai/v1", "chiave": "GROQ_API_KEY", "max": "max_completion_tokens",
             "formato": "json_object", "effort": _ALTO, "campi_standard": True},
    "openrouter": {"url": "https://openrouter.ai/api/v1", "chiave": "OPENROUTER_API_KEY", "max": "max_tokens",
                   "formato": "json_schema"},
    "xai": {"url": "https://api.x.ai/v1", "chiave": "XAI_API_KEY", "max": "max_completion_tokens", "formato": "json_schema"},
    "ollama": {"url": "http://localhost:11434/v1", "chiave": None, "max": "max_tokens", "formato": "json_schema"},
    # qualunque altro server compatibile: indirizzo in TOKYN_OPENAI_BASE_URL, chiave facoltativa
    "openai-compatible": {"url": None, "chiave": "TOKYN_OPENAI_API_KEY", "max": "max_tokens", "formato": "json_schema",
                          "chiave_facoltativa": True},
}
GROQ_STRICT = ("gpt-oss-20b", "gpt-oss-120b", "qwen3.8-27b", "muse-spark-open")  # schema rigido, ma senza strumenti
_RITENTA = (408, 429, 498)  # più i 5xx, tranne 501 (il server non sa fare la richiesta: riprovare non serve)
_SENZA_CREDITO = ("insufficient_quota", "credit_balance", "spend_limit", "usage_limit_exceeded", "billing_hard_limit")
_INTERROTTE = ("error", "insufficient_system_resource", "aborted")  # finish_reason di un server che non ha finito
_SOLO_IN_RISPOSTA = ("refusal", "annotations", "audio", "function_call")
_USO_FORNITORI: dict[str, int] = {}


def dividi_modello(model):
    """("fornitore", "modello") per model "fornitore:modello", None per i modelli Claude.

    Il prefisso conta solo se ha la forma di un nome (minuscole, cifre e trattini): un id come
    "anthropic.claude-...-v1:0" resta un id di Claude, e così un ARN di Bedrock ("arn:aws:bedrock:...")."""
    if not isinstance(model, str) or ":" not in model:
        return None
    prefisso, modello = model.split(":", 1)
    if not re.fullmatch(r"[a-z][a-z0-9-]*", prefisso) or prefisso == "arn":
        return None
    return prefisso, modello


def aiuto_fornitori() -> str:
    nomi = ", ".join(FORNITORI)
    return tr(f'Scrivi model: "fornitore:modello" con uno tra {nomi} (es. "openai:gpt-5.6-luna"), '
              'oppure un modello Claude: "claude", "claude-opus", "claude-haiku".',
              f'Write model: "provider:model" with one of {nomi} (e.g. "openai:gpt-5.6-luna"), '
              'or a Claude model: "claude", "claude-opus", "claude-haiku".')


def _fornitore(model):
    """Il fornitore di un agente con model "fornitore:modello"; None per Claude."""
    parti = dividi_modello(model)
    if parti is None:
        return None
    if parti[0] not in FORNITORI:
        raise TokynRuntimeError(tr(f'fornitore sconosciuto "{parti[0]}" in model "{model}"',
                                   f'unknown provider "{parti[0]}" in model "{model}"'), hint=aiuto_fornitori())
    return parti[0]


def _chiedi_chat(agent, text, history):
    """Una ask con un altro fornitore: restituisce (valore, testo da ricordare, messaggio da ricordare)."""
    nome = _fornitore(agent.model)
    modello = agent.model.split(":", 1)[1]
    url, chiave = _indirizzo_e_chiave(agent, nome)
    modo = _modo_output(agent, nome, modello)
    messages = list(history) + [{"role": "user", "content": text}]
    for _passo in range(agent.max_steps):
        risposta = _post_chat(url, chiave, _richiesta_chat(agent, nome, modello, modo, messages), agent.name, nome)
        fatto, valore, finale, ricordo = _passo_chat(agent, nome, modo, risposta, messages)
        if fatto:
            return valore, finale, ricordo
    raise agent._too_many_steps()


def _indirizzo_e_chiave(agent, nome):
    conf = FORNITORI[nome]
    url = conf["url"]
    if url is None:
        url = os.environ.get("TOKYN_OPENAI_BASE_URL", "").strip()
        if not url:
            raise TokynRuntimeError(
                tr(f"manca TOKYN_OPENAI_BASE_URL per l'agente {agent.name} (model \"{agent.model}\")",
                   f"TOKYN_OPENAI_BASE_URL is not set for agent {agent.name} (model \"{agent.model}\")"),
                hint=tr("Impostala con l'indirizzo dell'API, es. http://localhost:8000/v1 (la chiave, se serve, va in "
                        "TOKYN_OPENAI_API_KEY), oppure prova il programma senza IA con: tokyn run file.tokyn --mock",
                        "Set it to the address of the API, e.g. http://localhost:8000/v1 (the key, if needed, goes in "
                        "TOKYN_OPENAI_API_KEY), or try the program without AI with: tokyn run file.tokyn --mock"))
        if not re.match(r"https?://", url):  # senza http:// urllib non sa che fare: meglio dirlo subito
            raise TokynRuntimeError(
                tr(f'TOKYN_OPENAI_BASE_URL non è un indirizzo web: "{url}"', f'TOKYN_OPENAI_BASE_URL is not a web address: "{url}"'),
                hint=tr("Scrivilo con http:// o https://, es. http://localhost:8000/v1",
                        "Write it with http:// or https://, e.g. http://localhost:8000/v1"))
    var = conf["chiave"]
    chiave = os.environ.get(var, "").strip() if var else ""
    if not chiave and var and not conf.get("chiave_facoltativa"):
        raise TokynRuntimeError(
            tr(f"manca la chiave {var} per l'agente {agent.name} (model \"{agent.model}\")",
               f"{var} is not set for agent {agent.name} (model \"{agent.model}\")"),
            hint=tr(f"Impostala come variabile d'ambiente con la tua chiave di {nome}, oppure prova il programma senza IA "
                    "con: tokyn run file.tokyn --mock",
                    f"Set it as an environment variable with your {nome} key, or try the program without AI with: "
                    "tokyn run file.tokyn --mock"))
    return url, chiave or "tokyn"  # Ollama e i server locali vogliono una chiave qualsiasi


def _modo_output(agent, nome, modello):
    """Come arriva l'output strutturato: "json_schema" (schema rigido dell'API), "json_object" (JSON libero, con lo
    schema nelle istruzioni) o "strumento" (lo strumento `rispondi`, come con Claude). None senza output."""
    if agent.output is None:
        return None
    if not agent._native_output:  # dict liberi o ricorsione: niente schema rigido
        return "strumento"
    formato = FORNITORI[nome]["formato"]
    if nome == "groq" and modello.split("/")[-1] in GROQ_STRICT and not agent.tools:
        formato = "json_schema"
    if formato == "json_object" and agent.tools:  # JSON libero insieme agli strumenti: non documentato, meglio `rispondi`
        return "strumento"
    return formato


def _strumento_chat(schema, nome):
    funzione = {"name": schema["name"], "description": schema["description"], "parameters": schema["input_schema"]}
    if FORNITORI[nome].get("strict") and schema.get("strict"):
        funzione["strict"] = True
    return {"type": "function", "function": funzione}


def _richiesta_chat(agent, nome, modello, modo, messages):
    """Il corpo della richiesta. Niente temperature, stop o penalità: diversi modelli che ragionano li rifiutano."""
    conf = FORNITORI[nome]
    system = agent._system(final_tool=modo == "strumento")
    schema = agent.output.__tokyn_schema__() if agent.output is not None else None
    if modo == "json_object":  # la parola JSON serve anche a DeepSeek per accettare il formato
        system += ("\n\nRispondi solo con un oggetto JSON che rispetta questo schema JSON:\n"
                   + _json.dumps(schema, ensure_ascii=False))
    body = {"model": modello, "messages": [{"role": "system", "content": system}] + messages, conf["max"]: MAX_TOKENS}
    tools = [_strumento_chat(_tool_schema(t), nome) for t in agent.tools]
    if modo == "strumento":
        tools.append(_strumento_chat({"name": FINAL_TOOL, "description": "Consegna la risposta finale nel formato richiesto.",
                                      "input_schema": schema}, nome))
    if tools:
        body["tools"] = tools
    if modo == "json_schema":
        body["response_format"] = {"type": "json_schema", "json_schema": {
            "name": re.sub(r"[^A-Za-z0-9_-]", "_", agent.output.__name__)[:64], "schema": schema, "strict": True}}
    elif modo == "json_object":
        body["response_format"] = {"type": "json_object"}
    effort = conf.get("effort", {}).get(agent.effort) if agent.effort else None
    if effort:
        body["reasoning_effort"] = effort
    if nome == "openrouter" and (tools or modo):  # solo i server che rispettano strumenti e formato
        body["provider"] = {"require_parameters": True}
    return body


def _post_chat(url, chiave, body, agent_name, nome, attempts=5):
    """Una chiamata a /chat/completions. Riprova su limiti di frequenza, server occupati e risposte interrotte,
    rispettando Retry-After; non riprova se manca il credito o la richiesta è sbagliata."""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {chiave}", "User-Agent": "tokyn/0.1"}
    if nome == "openrouter":
        headers["X-OpenRouter-Title"] = "Tokyn"
    data = _json.dumps(body, ensure_ascii=False).encode("utf-8")
    delay = 2.0
    for i in range(attempts):
        last = i == attempts - 1
        wait = delay
        try:
            req = _urlreq.Request(url.rstrip("/") + "/chat/completions", data=data, headers=headers, method="POST")
            with _urlreq.urlopen(req, timeout=900) as r:  # i modelli che ragionano possono metterci minuti
                text = r.read().decode("utf-8", errors="replace")
        except _urlerr.HTTPError as err:
            try:
                text = err.read().decode("utf-8", errors="replace")
            except Exception:  # corpo illeggibile: basta il codice
                text = ""
            message, code = _errore_api(text)
            after = _retry_after(err.headers)
            # OpenRouter: un 402 per il budget delle richieste in corso passa da solo, e allora manda Retry-After
            in_flight = err.code == 402 and "openrouter_in_flight_budget" in text and after is not None
            no_credit = not in_flight and (err.code == 402 or any(s in (code + " " + message).lower() for s in _SENZA_CREDITO))
            if no_credit or not (in_flight or _ritentabile(err.code)) or last:
                raise _errore_http(err.code, message, no_credit, agent_name, nome, body["model"]) from None
            wait = delay if after is None else after
        except (OSError, _httpc.HTTPException) as err:  # rete, connessione rifiutata, timeout
            if last:
                hint = (tr(f"Avvia Ollama e scarica il modello: ollama pull {body['model']}",
                           f"Start Ollama and download the model: ollama pull {body['model']}") if nome == "ollama"
                        else tr("Controlla TOKYN_OPENAI_BASE_URL.", "Check TOKYN_OPENAI_BASE_URL.") if nome == "openai-compatible"
                        else tr("Controlla la connessione a internet.", "Check the internet connection."))
                shown = re.sub(r"//[^/@]*@", "//", url)  # utente e password nell'indirizzo non si stampano
                raise TokynRuntimeError(tr(f"impossibile raggiungere {nome} ({shown}) per l'agente {agent_name}: "
                                           f"{getattr(err, 'reason', None) or err}",
                                           f"cannot reach {nome} ({shown}) for agent {agent_name}: "
                                           f"{getattr(err, 'reason', None) or err}"), hint=hint) from None
        else:
            try:
                response = _json.loads(text)  # le righe vuote mandate durante l'attesa (DeepSeek) non danno fastidio
            except ValueError:
                raise TokynRuntimeError(tr(f"{nome} non ha risposto in JSON per l'agente {agent_name}: {text.strip()[:200]}",
                                           f"{nome} did not answer in JSON for agent {agent_name}: {text.strip()[:200]}"),
                                        hint=tr("Controlla l'indirizzo dell'API.", "Check the address of the API.")) from None
            choices = response.get("choices") if isinstance(response, dict) else None
            if not (isinstance(choices, list) and choices and isinstance(choices[0], dict)):
                # errore arrivato dopo l'inizio della risposta (OpenRouter): HTTP 200 con `error`, a volte col suo codice
                message, code = _errore_api(text)
                status = next((int(c) for c in code.split() if c.isdigit()), 200)
                no_credit = status == 402 or any(s in (code + " " + message).lower() for s in _SENZA_CREDITO)
                if no_credit or last or (400 <= status < 500 and not _ritentabile(status)):
                    raise _errore_http(status, message or tr("risposta senza choices", "answer without choices"),
                                       no_credit, agent_name, nome, body["model"])
            elif (choices[0] or {}).get("finish_reason") in _INTERROTTE and not last:
                _conta_uso_chat(nome, response.get("usage"))  # si paga anche il tentativo interrotto
            else:
                return response
        _time.sleep(min(wait, 60.0))
        delay *= 2


def _ritentabile(status):
    return status in _RITENTA or (status >= 500 and status != 501)


def _retry_after(headers):
    """I secondi da aspettare secondo Retry-After (un numero o una data HTTP); None se manca o non si capisce."""
    try:
        value = str(headers.get("Retry-After") or "").strip()
    except AttributeError:
        return None
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (_eutils.parsedate_to_datetime(value) - _dt.datetime.now(_dt.timezone.utc)).total_seconds()
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
    return max(0.0, seconds) if seconds == seconds else None  # NaN: come se mancasse


def _errore_api(text):
    """Messaggio e codice di un errore, nelle forme dei vari fornitori."""
    try:
        data = _json.loads(text)
    except ValueError:
        return text.strip()[:300], ""
    if isinstance(data, list) and data:  # Gemini a volte manda una lista
        data = data[0]
    if not isinstance(data, dict):
        return str(data)[:300], ""
    err = data.get("error", data)
    if not isinstance(err, dict):
        return str(err)[:300], ""
    message = err.get("message") or err.get("detail") or data.get("message") or data.get("detail") or ""
    code = " ".join(str(err[k]) for k in ("code", "type", "status") if err.get(k) is not None)
    return str(message)[:300], code


def _errore_http(status, message, no_credit, agent_name, nome, modello):
    detail = f" ({status}): {message}" if message else f" ({status})"
    var = FORNITORI[nome]["chiave"]
    if no_credit:
        return TokynRuntimeError(tr(f"{nome}: credito o quota esauriti per l'agente {agent_name}{detail}",
                                    f"{nome}: credit or quota used up for agent {agent_name}{detail}"),
                                 hint=tr(f"Controlla il piano e il credito del tuo account {nome}.",
                                         f"Check the plan and the credit of your {nome} account."))
    if status in (401, 403):
        return TokynRuntimeError(tr(f"{nome} ha rifiutato la richiesta dell'agente {agent_name}{detail}",
                                    f"{nome} rejected agent {agent_name}'s request{detail}"),
                                 hint=tr(f"Controlla la chiave in {var}.", f"Check the key in {var}.") if var else "")
    if status == 404:
        return TokynRuntimeError(tr(f'modello "{modello}" non trovato su {nome} per l\'agente {agent_name}{detail}',
                                    f'model "{modello}" not found on {nome} for agent {agent_name}{detail}'),
                                 hint=tr(f"Scaricalo con: ollama pull {modello}", f"Download it with: ollama pull {modello}")
                                 if nome == "ollama" else
                                 tr(f'Controlla il nome del modello dopo "{nome}:" nella documentazione di {nome}.',
                                    f'Check the model name after "{nome}:" in the {nome} documentation.'))
    failure = TokynRuntimeError(tr(f"chiamata a {nome} fallita per l'agente {agent_name}{detail}",
                                   f"call to {nome} failed for agent {agent_name}{detail}"))
    failure.bad_request = status == 400
    return failure


def _passo_chat(agent, nome, modo, response, messages):
    """Come Agent._step, per una risposta Chat Completions: esegue gli strumenti richiesti o riconosce la risposta
    finale. Restituisce (finito, valore, testo da ricordare, messaggio da ricordare)."""
    _conta_uso_chat(nome, response.get("usage"))
    choice = response["choices"][0]  # _post_chat ha già controllato che sia un oggetto
    msg = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    stop = choice.get("finish_reason")
    if msg.get("refusal") or stop == "content_filter":
        reason = msg.get("refusal") or tr("filtro dei contenuti", "content filter")
        raise TokynRuntimeError(tr(f"l'IA ha rifiutato la richiesta dell'agente {agent.name} ({nome}: {reason})",
                                   f"the AI refused agent {agent.name}'s request ({nome}: {reason})"),
                                hint=tr("Riformula le instructions o il testo della richiesta.",
                                        "Rephrase the instructions or the text of the request."))
    if stop in ("length", "model_length"):  # anche gli strumenti avrebbero un input troncato: non si eseguono
        raise TokynRuntimeError(tr(f"la risposta dell'agente {agent.name} è stata interrotta perché troppo lunga",
                                   f"agent {agent.name}'s answer was cut off because it was too long"),
                                hint=tr("Chiedi nelle instructions una risposta più breve, o usa un effort più basso.",
                                        "Ask for a shorter answer in the instructions, or use a lower effort."))
    if stop in _INTERROTTE:
        raise TokynRuntimeError(tr(f"{nome} ha interrotto la risposta dell'agente {agent.name} ({stop})",
                                   f"{nome} stopped agent {agent.name}'s answer ({stop})"),
                                hint=tr("Riprova più tardi.", "Try again later."))
    calls = [dict(c) for c in msg.get("tool_calls") or [] if isinstance(c, dict)]
    for i, call in enumerate(calls):  # id e tipo, se il server non li manda
        call.setdefault("type", "function")
        if not call.get("id"):
            call["id"] = f"call_{len(messages)}_{i}"
    msg = dict(msg, tool_calls=calls) if calls else {k: v for k, v in msg.items() if k != "tool_calls"}
    messages.append(_da_rimandare(msg, nome))
    text = _testo_chat(msg.get("content")).strip()

    if not calls:
        if agent.output is None:
            return True, text, text, _da_ricordare(msg, nome, text)
        if modo != "strumento":
            try:
                value = convert(_json.loads(_senza_recinto(text)), T.ref(agent.output.__name__), agent.output.__name__)
                return True, value, text, _da_ricordare(msg, nome, text)
            except ValueError as err:  # anche JSON non valido o vuoto
                messages.append({"role": "user", "content": f"La risposta non è nel formato richiesto ({err}). "
                                                             "Rispondi di nuovo solo con il JSON richiesto."})
                return False, None, None, None
        messages.append({"role": "user", "content": f"Ora chiama lo strumento `{FINAL_TOOL}` con la risposta finale."})
        return False, None, None, None

    for call in calls:
        function = call.get("function") if isinstance(call.get("function"), dict) else {}
        name = function.get("name")
        try:
            args = function.get("arguments") or {}
            args = _json.loads(args) if isinstance(args, str) else args
            if not isinstance(args, dict):
                raise ValueError(tr("serve un oggetto", "an object is needed"))
        except ValueError as err:
            content = f"Errore: gli argomenti non sono un oggetto JSON valido ({err}). Riprova."
        else:
            if name == FINAL_TOOL and modo == "strumento":
                try:
                    value = convert(args, T.ref(agent.output.__name__), agent.output.__name__)
                    final = _json.dumps(to_plain(value), ensure_ascii=False)
                    return True, value, final, _da_ricordare(msg, nome, final)
                except ValueError as err:
                    content = f"Formato non valido: {err}. Riprova."
            elif name not in agent._tools_by_name:
                content = f"Lo strumento {name} non esiste."
            else:
                try:
                    content = _call_tool(agent._tools_by_name[name], args)
                except Exception as err:  # l'errore torna all'IA, che può correggersi
                    content = f"Errore: {err}"
        messages.append({"role": "tool", "tool_call_id": call["id"], "content": content})
    return False, None, None, None


def _testo_chat(content):
    """Il testo della risposta: una stringa, o (Mistral mentre ragiona) una lista di pezzi, di cui conta il testo."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p if isinstance(p, str) else str(p.get("text") or "") for p in content
                       if isinstance(p, str) or (isinstance(p, dict) and p.get("type") == "text"))
    return ""


def _senza_recinto(text):
    """Il JSON senza il recinto ```json ... ``` che alcuni modelli aggiungono."""
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text


def _da_rimandare(msg, nome):
    """Il messaggio dell'IA da rimettere nella conversazione, con i campi nascosti che alcuni fornitori vogliono
    ritrovare (reasoning_content di DeepSeek, firme del ragionamento di Gemini in extra_content, reasoning_details di
    OpenRouter); solo i campi standard dove l'API rifiuta gli altri (Mistral, Groq)."""
    out = {k: v for k, v in msg.items() if v is not None and k not in _SOLO_IN_RISPOSTA}
    out["role"] = "assistant"
    out["content"] = msg.get("content")
    if out["content"] is None and not out.get("tool_calls"):  # una risposta vuota: senza testo né strumenti l'API la rifiuta
        out["content"] = ""
    if FORNITORI[nome].get("campi_standard"):
        out = {k: v for k, v in out.items() if k in ("role", "content", "tool_calls")}
        if "tool_calls" in out:
            out["tool_calls"] = [{"id": c["id"], "type": c["type"],
                                  "function": {k: v for k, v in (c.get("function") or {}).items() if k in ("name", "arguments")}}
                                 for c in out["tool_calls"]]
    return out


def _da_ricordare(msg, nome, text):
    """La risposta finale per la memoria: il testo, più i campi nascosti (DeepSeek vuole il suo reasoning_content
    in ogni turno precedente)."""
    remembered = {k: v for k, v in msg.items() if k != "tool_calls"}
    remembered["content"] = text or "(nessuna risposta)"
    return _da_rimandare(remembered, nome)


def _conta_uso_chat(nome, usage):
    _USAGE["chiamate"] += 1
    _USO_FORNITORI[nome] = _USO_FORNITORI.get(nome, 0) + 1
    if not isinstance(usage, dict):
        return
    details = usage.get("prompt_tokens_details")
    details = details if isinstance(details, dict) else {}

    def num(value):  # un server che manda altro al posto dei numeri non deve fermare il programma
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0

    read = num(details.get("cached_tokens")) or num(usage.get("prompt_cache_hit_tokens"))  # il secondo è di DeepSeek
    _USAGE["input"] += max(0, num(usage.get("prompt_tokens")) - read)  # come con Claude: senza i token dalla cache
    _USAGE["output"] += num(usage.get("completion_tokens"))
    _USAGE["cache_lette"] += read
    _USAGE["cache_scritte"] += num(details.get("cache_write_tokens"))


# ======================================================================= mock


def _example(spec: _Spec, field: str = "", n: int = 0):
    """Valore finto per un campo. n (numero della chiamata) fa variare scelte e bool tra una ask e l'altra."""
    k = spec.kind
    if k == "str":
        return tr(f"esempio {field}", f"example {field}").strip()
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
    answer = tr(f"[mock {agent.name}] risposta a: {short}", f"[mock {agent.name}] answer to: {short}")
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
        message = (tr(f'il file "{path}" non esiste', f'the file "{path}" does not exist') if isinstance(err, FileNotFoundError)
                   else tr(f'impossibile leggere "{path}": {err}', f'cannot read "{path}": {err}'))
        raise TokynRuntimeError(message, hint=tr(f'Se può mancare, dai un valore di riserva: read_file("{path}", "")',
                                                 f'If it can be missing, give a fallback value: read_file("{path}", "")')) from None


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
        raise TokynRuntimeError(tr(f"{call} fallita per {url}: {reason}", f"{call} failed for {url}: {reason}"),
                                hint=tr(f"Se può fallire, dai un valore di riserva come ultimo argomento: {call}(..., \"\")",
                                        f"If it can fail, give a fallback value as the last argument: {call}(..., \"\")")) from None


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
        detail = tr(f"{err.msg}, riga {err.lineno}", f"{err.msg}, line {err.lineno}") if isinstance(err, _json.JSONDecodeError) else str(err)
        raise TokynRuntimeError(tr(f"il testo non è JSON valido ({detail})", f"the text is not valid JSON ({detail})"),
                                hint=tr("Se può non esserlo, dai un valore di riserva: json_parse(testo, {})",
                                        "If it may not be JSON, give a fallback value: json_parse(text, {})")) from None


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
    raise TokynRuntimeError(tr(f"{text!r} non è un numero", f"{text!r} is not a number"),
                            hint=tr("Se può non esserlo, dai un valore di riserva: to_number(testo, 0)",
                                    "If it may not be a number, give a fallback value: to_number(text, 0)"))


def json_dump(value):
    return _json.dumps(to_plain(value), ensure_ascii=False, indent=2, default=str)


def env(name, default=_NO_DEFAULT):
    value = os.environ.get(name, default)
    if value is _NO_DEFAULT:
        raise TokynRuntimeError(tr(f'la variabile d\'ambiente "{name}" non è impostata', f'the environment variable "{name}" is not set'),
                                hint=tr(f'Impostala, oppure dai un valore di riserva: env("{name}", "...")',
                                        f'Set it, or give a fallback value: env("{name}", "...")'))
    return value


def now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def sleep(seconds):
    _time.sleep(seconds)


def run_main(main):
    main()
