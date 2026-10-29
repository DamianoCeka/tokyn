"""Runtime di Tokyn: tipi strutturati, strumenti, agenti e funzioni di base.

Il codice Python generato dal compilatore importa questo modulo.
"""

from __future__ import annotations

import datetime as _dt
import json as _json
import os
import textwrap
import time as _time
import urllib.request as _urlreq

from .errors import TokynRuntimeError

DEFAULT_MODELS = {
    "claude": "claude-sonnet-5-5",
    "claude-sonnet": "claude-sonnet-5-5",
    "claude-opus": "claude-opus-5-5",
    "claude-haiku": "claude-haiku-5-5",
}
FINAL_TOOL = "rispondi"

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


def _tool_schema(obj) -> dict:
    if isinstance(obj, Agent):
        return {
            "name": obj.name,
            "description": f"Chiede all'agente {obj.name}. " + obj.instructions[:300],
            "input_schema": {
                "type": "object",
                "properties": {"richiesta": {"type": "string", "description": "il testo da passare all'agente"}},
                "required": ["richiesta"],
            },
        }
    meta = obj.__tokyn_tool__
    return {
        "name": meta["name"],
        "description": meta["description"],
        "input_schema": {
            "type": "object",
            "properties": {p: json_schema(s) for p, s in meta["params"].items()},
            "required": list(meta["params"]),
        },
    }


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
    return result if isinstance(result, str) else _json.dumps(result, ensure_ascii=False)


# ======================================================================= agenti


class Agent:
    def __init__(self, name, instructions, model="claude", tools=(), output=None, memory=False, max_steps=10):
        self.name = name
        self.instructions = textwrap.dedent(str(instructions)).strip()
        self.model = model
        self.tools = list(tools)
        self.output = output
        self.memory = memory
        self.max_steps = max_steps
        self._history: list[dict] = []
        self._tools_by_name = {(t.name if isinstance(t, Agent) else t.__tokyn_tool__["name"]): t for t in self.tools}

    def __repr__(self):
        return f"<agent {self.name}>"

    def reset(self):
        self._history = []

    # ---------------------------------------------------------------- ask
    def ask(self, text):
        text = str(text)
        if _use_mock(self.model):
            answer, final_text = _mock_answer(self, text)
        else:
            answer, final_text = self._ask_anthropic(text)
        if self.memory:
            self._history += [
                {"role": "user", "content": text},
                {"role": "assistant", "content": final_text or "(nessuna risposta)"},
            ]
        return answer

    def _system(self):
        system = self.instructions
        if self.output is not None:
            system += (
                f"\n\nQuando hai finito, chiama sempre lo strumento `{FINAL_TOOL}` con la risposta finale "
                "nel formato richiesto. Non rispondere solo con testo."
            )
        return system

    def _ask_anthropic(self, text):
        client = _client()
        model = DEFAULT_MODELS.get(self.model, self.model)
        tools = [_tool_schema(t) for t in self.tools]
        if self.output is not None:
            tools.append({
                "name": FINAL_TOOL,
                "description": "Consegna la risposta finale nel formato richiesto.",
                "input_schema": self.output.__tokyn_schema__(),
            })
        messages = list(self._history) + [{"role": "user", "content": text}]
        for _step in range(self.max_steps):
            kwargs = dict(model=model, max_tokens=4096, system=self._system(), messages=messages)
            if tools:
                kwargs["tools"] = tools
            response = _with_retry(lambda: client.messages.create(**kwargs), self.name)
            messages.append({"role": "assistant", "content": response.content})
            uses = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
            texts = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()

            if not uses:
                if self.output is None:
                    return texts, texts
                messages.append({"role": "user", "content": f"Ora chiama lo strumento `{FINAL_TOOL}` con la risposta finale."})
                continue

            results = []
            for use in uses:
                if use.name == FINAL_TOOL and self.output is not None:
                    try:
                        value = self.output._from_dict(dict(use.input), self.output.__name__)
                        return value, _json.dumps(to_plain(value), ensure_ascii=False)
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

        raise TokynRuntimeError(
            f"l'agente {self.name} non ha finito entro {self.max_steps} passaggi",
            hint="Aumenta max_steps nell'agente o rendi le instructions più precise.",
        )


def _use_mock(model) -> bool:
    return model == "mock" or os.environ.get("TOKYN_MOCK") == "1"


_CLIENT = None


def _client():
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise TokynRuntimeError(
            "manca la chiave ANTHROPIC_API_KEY",
            hint="Impostala come variabile d'ambiente, oppure prova il programma senza IA con: tokyn run file.tokyn --mock",
        )
    try:
        import anthropic
    except ImportError:
        raise TokynRuntimeError("manca il pacchetto anthropic", hint="Installa con: pip install anthropic") from None
    _CLIENT = anthropic.Anthropic()
    return _CLIENT


def _with_retry(fn, agent_name, attempts=3):
    delay = 2.0
    for i in range(attempts):
        try:
            return fn()
        except Exception as err:
            name = type(err).__name__
            retryable = name in ("RateLimitError", "APIConnectionError", "APITimeoutError", "InternalServerError", "OverloadedError")
            if not retryable or i == attempts - 1:
                if name == "AuthenticationError":
                    raise TokynRuntimeError("la chiave ANTHROPIC_API_KEY non è valida") from None
                if name == "NotFoundError":
                    raise TokynRuntimeError(f"modello non trovato per l'agente {agent_name}",
                                            hint='Usa model: "claude", "claude-opus" o "claude-haiku".') from None
                raise TokynRuntimeError(f"chiamata all'IA fallita per l'agente {agent_name}: {err}") from None
            _time.sleep(delay)
            delay *= 2


# ======================================================================= mock


def _example(spec: _Spec, field: str = ""):
    k = spec.kind
    if k == "str":
        return f"esempio {field}".strip()
    if k == "int":
        return 1
    if k == "float":
        return 1.0
    if k == "bool":
        return True
    if k == "dict":
        return {}
    if k == "enum":
        return spec.arg[0]
    if k == "list":
        return [_example(spec.arg, field)]
    if k == "ref":
        cls = _TYPES[spec.arg]
        return {f: _example(cls.__tokyn_specs__[f], f) for f in cls.__tokyn_fields__}
    return None


def _mock_answer(agent: Agent, text: str):
    """Risposta finta e prevedibile: permette di provare un programma senza API key."""
    if agent.output is not None:
        cls = agent.output
        data = {f: _example(cls.__tokyn_specs__[f], f) for f in cls.__tokyn_fields__}
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
    except FileNotFoundError:
        if default is not _NO_DEFAULT:
            return default
        raise TokynRuntimeError(f'il file "{path}" non esiste',
                                hint=f'Se può mancare, dai un valore di riserva: read_file("{path}", "")') from None


def write_file(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(text))


def append_file(path, text):
    with open(path, "a", encoding="utf-8") as f:
        f.write(str(text))


def _http(req, default, call):
    try:
        with _urlreq.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except (OSError, ValueError) as err:  # rete, HTTP 4xx/5xx, timeout, indirizzo non valido
        if default is not _NO_DEFAULT:
            return default
        reason = getattr(err, "reason", None) or err
        raise TokynRuntimeError(f"{call} fallita per {req.full_url}: {reason}",
                                hint=f"Se può fallire, dai un valore di riserva come ultimo argomento: {call}(..., \"\")") from None


def http_get(url, default=_NO_DEFAULT):
    req = _urlreq.Request(str(url), headers={"User-Agent": "tokyn/0.1"})
    return _http(req, default, "http_get")


def http_post(url, data, default=_NO_DEFAULT):
    body = data if isinstance(data, str) else _json.dumps(to_plain(data))
    req = _urlreq.Request(str(url), data=body.encode("utf-8"), method="POST",
                          headers={"User-Agent": "tokyn/0.1", "Content-Type": "application/json"})
    return _http(req, default, "http_post")


def json_parse(text):
    try:
        return _json.loads(text)
    except _json.JSONDecodeError as err:
        raise TokynRuntimeError(f"il testo non è JSON valido ({err.msg}, riga {err.lineno})") from None


def json_dump(value):
    return _json.dumps(to_plain(value), ensure_ascii=False, indent=2)


def env(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        raise TokynRuntimeError(f'la variabile d\'ambiente "{name}" non è impostata',
                                hint=f'Impostala, oppure dai un valore di riserva: env("{name}", "...")')
    return value


def now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def sleep(seconds):
    _time.sleep(seconds)


def run_main(main):
    main()
