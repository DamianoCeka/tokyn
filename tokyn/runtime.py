"""Runtime di Tokyn: tipi strutturati, strumenti, agenti e funzioni di base.

Il codice Python generato dal compilatore importa questo modulo.
"""

from __future__ import annotations

import datetime as _dt
import json as _json
import os
import sys
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
EFFORTS = ("low", "medium", "high", "xhigh", "max")
MAX_TOKENS = 16000  # il thinking è sempre attivo sui modelli attuali e conta nei token della risposta
# Se l'IA rifiuta una richiesta, l'API la riprova da sola su un altro modello (Claude API; Haiku non lo prevede).
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"}
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
        texts = [str(t) for t in texts]
        if _use_mock(self.model):
            return [_mock_answer(self, t)[0] for t in texts]
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
        messages.append({"role": "assistant", "content": [_plain(b) for b in response.content]})
        uses = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
        texts = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()

        if not uses:
            if getattr(response, "stop_reason", None) == "max_tokens":
                raise TokynRuntimeError(f"la risposta dell'agente {self.name} è stata interrotta perché troppo lunga",
                                        hint="Chiedi nelle instructions una risposta più breve.")
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
        answers = {}
        for step in range(self.max_steps):
            if not pending:
                break
            requests = [{"custom_id": cid, "params": self._request(msgs)} for cid, msgs in pending.items()]
            batch = _with_retry(lambda: client.messages.batches.create(requests=requests), self.name)
            batch = _wait_batch(client, batch, self.name)
            retry = []
            for entry in client.messages.batches.results(batch.id):
                cid = entry.custom_id
                if entry.result.type != "succeeded":
                    retry.append(cid)
                    continue
                done, value, _ = self._step(entry.result.message, pending[cid], batch=True)
                if done:
                    answers[cid] = value
                    del pending[cid]
            for cid in retry:  # errore o scadenza nel batch: si riprova con la chiamata normale
                answers[cid], _ = self._run(pending.pop(cid), steps_done=step)
        if pending:
            raise self._too_many_steps()
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


_USAGE = {"chiamate": 0, "chiamate_batch": 0, "input": 0, "output": 0, "cache_lette": 0, "cache_scritte": 0}


def _count_usage(response, batch=False):
    _USAGE["chiamate_batch" if batch else "chiamate"] += 1
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    _USAGE["input"] += getattr(usage, "input_tokens", 0) or 0
    _USAGE["output"] += getattr(usage, "output_tokens", 0) or 0
    _USAGE["cache_lette"] += getattr(usage, "cache_read_input_tokens", 0) or 0
    _USAGE["cache_scritte"] += getattr(usage, "cache_creation_input_tokens", 0) or 0


def usage_report() -> str:
    u = _USAGE
    return (f"token: {u['input']} in ingresso, {u['output']} in uscita, {u['cache_lette']} letti dalla cache, "
            f"{u['cache_scritte']} scritti in cache ({u['chiamate']} chiamate, {u['chiamate_batch']} nella Batch API a metà prezzo)")


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
            hint="Impostala come variabile d'ambiente, oppure prova il programma senza IA con: tokyn run file.tokyn --mock",
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
            if not err.bad_request:
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
            retryable = name in ("RateLimitError", "APIConnectionError", "APITimeoutError", "InternalServerError", "OverloadedError")
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
