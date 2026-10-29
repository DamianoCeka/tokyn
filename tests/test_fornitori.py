"""Agenti con altri fornitori (model "fornitore:modello"): un finto server compatibile con OpenAI, in locale."""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tokyn.compiler import check_source, compile_source

import tokyn.runtime as rt


class _FakeOpenAI:
    """Server HTTP locale: restituisce le risposte preparate e registra ogni richiesta (corpo e intestazioni)."""

    def __init__(self):
        self.replies = []
        self.requests = []
        self.handler = None  # se c'è, dà la risposta in base al corpo della richiesta (le richieste possono arrivare insieme)
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
                fake.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                status, data, headers = fake.handler(body) if fake.handler else fake.replies.pop(0)
                payload = (data if isinstance(data, str) else json.dumps(data)).encode("utf-8")
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, args=(0.02,), daemon=True).start()

    def reply(self, *replies):
        for r in replies:
            self.replies.append(r if isinstance(r, tuple) else (200, r, {}))
        return self

    def bodies(self):
        return [r["body"] for r in self.requests]


def _chat(content=None, calls=None, finish=None, usage=None, **extra):
    msg = {"role": "assistant", "content": content, **extra}
    if calls:
        msg["tool_calls"] = calls
    return {"id": "x", "choices": [{"index": 0, "message": msg, "finish_reason": finish or ("tool_calls" if calls else "stop")}],
            "usage": usage or {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}}


def _call(id, name, **args):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


@pytest.fixture
def server(monkeypatch):
    """Tutti i fornitori puntano al finto server, con le chiavi impostate; niente attese tra un tentativo e l'altro."""
    fake = _FakeOpenAI()
    for nome, conf in rt.FORNITORI.items():
        if conf["url"]:
            monkeypatch.setitem(rt.FORNITORI, nome, dict(conf, url=fake.url))
        if conf["chiave"]:
            monkeypatch.setenv(conf["chiave"], "k-" + nome)
    monkeypatch.setenv("TOKYN_OPENAI_BASE_URL", fake.url)
    monkeypatch.delenv("TOKYN_MOCK", raising=False)
    sleeps = []
    monkeypatch.setattr(rt._time, "sleep", sleeps.append)
    fake.sleeps = sleeps
    yield fake
    fake.server.shutdown()
    fake.server.server_close()


def _agents(src):
    ns = {"__name__": "x"}
    exec(compile_source(src).python, ns)
    return ns


METEO = '''
type Meteo:
    citta: str
    gradi: int

def meteo(citta: str) -> str:
    """Restituisce la temperatura di una città."""
    return f"{citta}: 18 gradi"

def ora(citta: str) -> str:
    """Restituisce l'ora di una città."""
    return f"{citta}: 12:00"

agent A:
    model: "MODEL"
    instructions: "Dimmi il meteo."
    tools: [meteo, ora]
    output: Meteo
'''


def test_plain_answer_and_request_shape(server, monkeypatch):
    for key in ("chiamate", "input", "output", "cache_lette"):
        monkeypatch.setitem(rt._USAGE, key, 0)
    monkeypatch.setattr(rt, "_USO_FORNITORI", {})
    server.reply(_chat("Ciao!", usage={"prompt_tokens": 100, "completion_tokens": 7,
                                       "prompt_tokens_details": {"cached_tokens": 40}}))
    ns = _agents('agent A:\n    model: "openai:gpt-5.6-luna"\n    instructions: "Saluta."\n    effort: "xhigh"\n')
    assert ns["A"].ask("ciao") == "Ciao!"
    req = server.requests[0]
    assert req["path"] == "/v1/chat/completions" and req["headers"]["Authorization"] == "Bearer k-openai"
    body = req["body"]
    assert body["model"] == "gpt-5.6-luna" and body["max_completion_tokens"] == rt.MAX_TOKENS
    assert body["messages"] == [{"role": "system", "content": "Saluta."}, {"role": "user", "content": "ciao"}]
    assert body["reasoning_effort"] == "high"
    assert not {"temperature", "max_tokens", "tools", "response_format", "stop"} & set(body)
    assert (rt._USAGE["chiamate"], rt._USAGE["input"], rt._USAGE["output"], rt._USAGE["cache_lette"]) == (1, 60, 7, 40)
    assert "chiamate ad altri fornitori: openai 1" in rt.usage_report()


def test_tool_loop_with_two_tools_and_native_schema(server):
    server.reply(
        _chat(None, [_call("c1", "meteo", citta="Padova"), _call("c2", "ora", citta="Padova")]),
        _chat('{"citta": "Padova", "gradi": 18}'),
    )
    ns = _agents(METEO.replace("MODEL", "openai:gpt-5.6-terra"))
    result = ns["A"].ask("Che tempo fa a Padova?")
    assert (result.citta, result.gradi) == ("Padova", 18)
    first, second = server.bodies()
    tools = {t["function"]["name"]: t for t in first["tools"]}
    assert set(tools) == {"meteo", "ora"} and tools["meteo"]["type"] == "function"
    assert tools["meteo"]["function"]["strict"] is True
    assert tools["meteo"]["function"]["parameters"]["required"] == ["citta"]
    fmt = first["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["name"] == "Meteo" and fmt["json_schema"]["schema"]["required"] == ["citta", "gradi"]
    # i due risultati tornano all'IA, uno per chiamata, dopo il messaggio con le chiamate
    assert second["messages"][-3]["tool_calls"][1]["id"] == "c2"
    assert second["messages"][-2:] == [{"role": "tool", "tool_call_id": "c1", "content": "Padova: 18 gradi"},
                                       {"role": "tool", "tool_call_id": "c2", "content": "Padova: 12:00"}]


def test_invalid_json_is_sent_back_and_retried(server):
    server.reply(_chat('{"citta": "Padova", "gradi": "tanti"}'), _chat('```json\n{"citta": "Padova", "gradi": 18}\n```'))
    ns = _agents(METEO.replace("MODEL", "gemini:gemini-3.8-flash"))
    assert ns["A"].ask("x").gradi == 18
    retry = server.bodies()[1]["messages"]
    assert retry[-2]["content"] == '{"citta": "Padova", "gradi": "tanti"}'
    assert retry[-1]["role"] == "user" and "gradi" in retry[-1]["content"] and "JSON" in retry[-1]["content"]
    assert "max_tokens" in server.bodies()[0] and "max_completion_tokens" not in server.bodies()[0]


def test_json_object_fallback_without_schema_support(server):
    src = 'type R:\n    voto: int\n\nagent A:\n    model: "deepseek:deepseek-flash"\n    instructions: "Dai un voto."\n    output: R\n'
    server.reply(_chat('{"voto": 4}'))
    assert _agents(src)["A"].ask("bello").voto == 4
    body = server.bodies()[0]
    assert body["response_format"] == {"type": "json_object"} and "tools" not in body
    assert '"voto"' in body["messages"][0]["content"] and "JSON" in body["messages"][0]["content"]


def test_answer_tool_fallback_with_tools_or_free_dicts(server):
    # Groq: schema rigido solo senza strumenti; qui c'è uno strumento, quindi lo strumento `rispondi`
    server.reply(_chat("Ci penso."), _chat(None, [_call("c1", "rispondi", citta="Roma", gradi="x")]),
                 _chat(None, [_call("c2", "rispondi", citta="Roma", gradi=20)]))
    ns = _agents(METEO.replace("MODEL", "groq:openai/gpt-oss-120b"))
    assert ns["A"].ask("Roma?").gradi == 20
    first, second, third = server.bodies()
    assert "response_format" not in first and first["tools"][-1]["function"]["name"] == "rispondi"
    assert "rispondi" in first["messages"][0]["content"] and "strict" not in first["tools"][0]["function"]
    assert second["messages"][-1] == {"role": "user", "content": "Ora chiama lo strumento `rispondi` con la risposta finale."}
    assert third["messages"][-1]["role"] == "tool" and "Formato non valido" in third["messages"][-1]["content"]
    # senza strumenti, sui modelli che lo permettono, lo schema rigido
    server.reply(_chat('{"voto": 4}'))
    _agents('type R:\n    voto: int\n\nagent B:\n    model: "groq:openai/gpt-oss-120b"\n    instructions: "i"\n    output: R\n')["B"].ask("x")
    assert server.bodies()[-1]["response_format"]["type"] == "json_schema"
    # un dict libero non entra in uno schema rigido: strumento `rispondi` anche con OpenAI
    server.reply(_chat(None, [_call("c1", "rispondi", dati={"k": 1})]))
    ns = _agents('type R:\n    dati: dict\n\nagent C:\n    model: "openai:gpt-5.6-luna"\n    instructions: "i"\n    output: R\n')
    assert ns["C"].ask("x").dati == {"k": 1}
    assert "response_format" not in server.bodies()[-1]


def test_memory_reset_and_ask_all(server, monkeypatch):
    server.reply(_chat("Piacere, Ada."), _chat("Ti chiami Ada."), _chat("Non lo so."), _chat("uno"), _chat("due"))
    ns = _agents('agent A:\n    model: "mistral:mistral-small-2603"\n    instructions: "i"\n    memory: True\n')
    a = ns["A"]
    a.ask("Sono Ada.")
    a.ask("Come mi chiamo?")
    assert server.bodies()[1]["messages"][1:] == [
        {"role": "user", "content": "Sono Ada."}, {"role": "assistant", "content": "Piacere, Ada."},
        {"role": "user", "content": "Come mi chiamo?"}]
    a.reset()
    a.ask("Come mi chiamo?")
    assert len(server.bodies()[2]["messages"]) == 2
    monkeypatch.setenv("TOKYN_PARALLELO", "1")  # le risposte preparate arrivano in ordine solo una alla volta
    assert a.ask_all(["a", "b"]) == ["uno", "due"]  # senza la memoria
    assert [len(b["messages"]) for b in server.bodies()[3:]] == [2, 2]


def test_refusal_length_and_content_filter_errors(server):
    ns = _agents(METEO.replace("MODEL", "openai:gpt-5.6-luna"))
    server.reply(_chat(None, refusal="Non posso aiutarti con questo."))
    with pytest.raises(rt.TokynRuntimeError, match="rifiutato.*Non posso aiutarti"):
        ns["A"].ask("x")
    server.reply(_chat(None, [_call("c1", "meteo", citta="Pad")], finish="length"))
    with pytest.raises(rt.TokynRuntimeError, match="troppo lunga"):
        ns["A"].ask("x")
    server.reply(_chat("", finish="content_filter"))
    with pytest.raises(rt.TokynRuntimeError, match="filtro dei contenuti"):
        ns["A"].ask("x")
    assert len(server.requests) == 3  # lo strumento con l'input troncato non è stato eseguito


def test_rate_limits_are_retried_honouring_retry_after(server):
    server.reply((429, {"error": {"message": "Rate limit reached", "code": "rate_limit_exceeded"}}, {"Retry-After": "3"}),
                 (503, {"error": {"message": "overloaded"}}, {}),
                 _chat("ok", finish="insufficient_system_resource"),  # interrotta: si riprova
                 _chat("ok"))
    ns = _agents('agent A:\n    model: "xai:grok-4.3"\n    instructions: "i"\n')
    assert ns["A"].ask("x") == "ok"
    assert server.sleeps == [3.0, 4.0, 8.0] and len(server.requests) == 4


def test_billing_and_bad_requests_are_not_retried(server):
    ns = _agents('agent A:\n    model: "openai:gpt-5.6-luna"\n    instructions: "i"\n')
    server.reply((429, {"error": {"message": "You exceeded your current quota", "code": "insufficient_quota"}}, {}))
    with pytest.raises(rt.TokynRuntimeError, match="credito o quota esauriti") as err:
        ns["A"].ask("x")
    assert "openai" in err.value.hint
    server.reply((400, {"error": {"message": "Unsupported parameter: 'foo'"}}, {}))
    with pytest.raises(rt.TokynRuntimeError, match="Unsupported parameter") as err:
        ns["A"].ask("x")
    assert err.value.bad_request
    server.reply((401, {"error": {"message": "Incorrect API key"}}, {}))
    with pytest.raises(rt.TokynRuntimeError, match="Incorrect API key") as err:
        ns["A"].ask("x")
    assert "OPENAI_API_KEY" in err.value.hint
    server.reply((404, {"error": "model 'qwen3.8' not found"}, {}))
    with pytest.raises(rt.TokynRuntimeError, match="non trovato") as err:
        _agents('agent B:\n    model: "ollama:qwen3.8"\n    instructions: "i"\n')["B"].ask("x")
    assert err.value.hint == "Scarica il modello qwen3.8 con Ollama."
    assert server.sleeps == [] and len(server.requests) == 4


def test_missing_key_or_address(server, monkeypatch, capsys):
    from tokyn.compiler import run_source
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    src = 'agent A:\n    model: "deepseek:deepseek-flash"\n    instructions: "i"\nmain:\n    print(A.ask("x"))\n'
    assert run_source(src, "t.tokyn") == 1
    err = capsys.readouterr().err
    assert "manca la chiave DEEPSEEK_API_KEY per l'agente A" in err and "--mock" in err
    monkeypatch.setenv("TOKYN_LANG", "en")
    assert run_source(src, "t.tokyn") == 1
    assert "DEEPSEEK_API_KEY is not set for agent A" in capsys.readouterr().err
    monkeypatch.delenv("TOKYN_OPENAI_BASE_URL")
    with pytest.raises(rt.TokynRuntimeError, match="TOKYN_OPENAI_BASE_URL"):
        _agents('agent B:\n    model: "openai-compatible:m"\n    instructions: "i"\n')["B"].ask("x")
    assert server.requests == []
    # in mock non serve nessuna chiave, con ogni fornitore
    assert run_source(src, "t.tokyn", mock=True) == 0
    assert "[mock A] answer to: x" in capsys.readouterr().out


def test_local_servers_get_a_placeholder_key(server, monkeypatch):
    monkeypatch.delenv("TOKYN_OPENAI_API_KEY", raising=False)
    server.reply(_chat("a"), _chat("b"))
    assert _agents('agent A:\n    model: "ollama:qwen3.8"\n    instructions: "i"\n')["A"].ask("x") == "a"
    assert _agents('agent B:\n    model: "openai-compatible:m"\n    instructions: "i"\n')["B"].ask("x") == "b"
    assert [r["headers"]["Authorization"] for r in server.requests] == ["Bearer tokyn", "Bearer tokyn"]


def test_deepseek_reasoning_content_round_trip(server):
    server.reply(
        _chat("", [_call("c1", "meteo", citta="Bari")], reasoning_content="Serve il meteo."),
        _chat("A Bari 18 gradi.", reasoning_content="Ho il dato."),
        _chat("Prego.", reasoning_content="Ringrazia."),
    )
    src = METEO.replace("MODEL", "deepseek:deepseek-flash").replace("    output: Meteo\n", "    memory: True\n    effort: \"medium\"\n")
    a = _agents(src)["A"]
    assert a.ask("Meteo a Bari?") == "A Bari 18 gradi."
    a.ask("Grazie")
    second, third = server.bodies()[1:]
    assert second["messages"][2]["reasoning_content"] == "Serve il meteo."
    assert second["messages"][2]["tool_calls"][0]["id"] == "c1"
    assert second["reasoning_effort"] == "high" and "strict" not in second["tools"][0]["function"]
    # la memoria tiene il reasoning_content del turno precedente: DeepSeek lo vuole con gli strumenti
    assert third["messages"][2] == {"role": "assistant", "content": "A Bari 18 gradi.", "reasoning_content": "Ho il dato."}


def test_hidden_fields_kept_except_where_rejected(server):
    gemini_call = dict(_call("c1", "meteo", citta="Pisa"), extra_content={"google": {"thought_signature": "sig"}})
    server.reply(_chat(None, [gemini_call]), _chat("ok"))
    _agents(METEO.replace("MODEL", "gemini:gemini-3.8-flash").replace("    output: Meteo\n", ""))["A"].ask("x")
    sent = server.bodies()[1]["messages"][2]
    assert sent["tool_calls"][0]["extra_content"] == {"google": {"thought_signature": "sig"}} and "refusal" not in sent
    # Mistral: il testo arriva a pezzi mentre ragiona, e i messaggi rimandati hanno solo i campi standard
    chunks = [{"type": "thinking", "thinking": [{"type": "text", "text": "hmm"}]}, {"type": "text", "text": "Fa caldo."}]
    server.reply(_chat(None, [dict(_call("abcdefghi", "meteo", citta="Pisa"), index=0, extra="x")], other="y"),
                 _chat(chunks))
    ns = _agents(METEO.replace("MODEL", "mistral:mistral-medium-3-5").replace("    output: Meteo\n", '    effort: "low"\n'))
    assert ns["A"].ask("x") == "Fa caldo."
    sent = server.bodies()[-1]["messages"][2]
    assert sent == {"role": "assistant", "content": None, "tool_calls": [
        {"id": "abcdefghi", "type": "function", "function": {"name": "meteo", "arguments": '{"citta": "Pisa"}'}}]}
    assert "reasoning_effort" not in server.bodies()[-1]  # Mistral: solo "high"


def test_openrouter_requires_the_parameters(server):
    server.reply(_chat('{"citta": "Pisa", "gradi": 1}'))
    _agents(METEO.replace("MODEL", "openrouter:google/gemini-3.8-flash"))["A"].ask("x")
    req = server.requests[0]
    assert req["body"]["provider"] == {"require_parameters": True} and req["body"]["model"] == "google/gemini-3.8-flash"
    assert req["headers"]["X-Openrouter-Title"] == "Tokyn" and "max_tokens" in req["body"]


def test_standalone_build_talks_to_providers_without_anthropic(server, tmp_path):
    server.reply(_chat("ciao dal server"))
    src = 'agent A:\n    model: "openai-compatible:locale"\n    instructions: "i"\nmain:\n    print(A.ask("x"))\n'
    py = tmp_path / "prog.py"
    py.write_text(compile_source(src, "prog.tokyn", standalone=True).python, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("TOKYN_MOCK", "HTTP_PROXY", "http_proxy")}
    r = subprocess.run([sys.executable, "-S", str(py)], capture_output=True, text=True, cwd=tmp_path,
                       env=dict(env, PYTHONPATH="", NO_PROXY="127.0.0.1", no_proxy="127.0.0.1"))
    assert r.returncode == 0 and r.stdout.strip() == "ciao dal server", r.stderr


@pytest.mark.parametrize("model,code", [
    ("openai:gpt-5.6-luna", None), ("gemini:gemini-3.8-flash", None), ("groq:openai/gpt-oss-120b", None),
    ("openrouter:google/gemini-3.8-flash", None), ("ollama:gpt-oss:20b", None), ("openai-compatible:qwen", None),
    ("claude-opus", None), ("anthropic.claude-sonnet-5-5-v1:0", None),
    ("arn:aws:bedrock:us-east-1:123:inference-profile/x", None),
    ("opneai:gpt-5.6-luna", "E146"), ("anthropic:claude", "E146"), ("mistral:", "E146"), ("OpenAI:gpt-5.6-luna", "E146"),
])
def test_checker_accepts_known_providers(model, code):
    diags = [d for d in check_source(f'agent A:\n    model: "{model}"\n    instructions: "i"\n').diagnostics
             if d.severity == "errore"]
    assert [d.code for d in diags] == ([code] if code else [])
    if model.lower().startswith(("opneai", "openai")) and code:
        assert 'Forse intendevi "openai"?' in diags[0].hint and "deepseek" in diags[0].hint


def test_unknown_provider_at_runtime(monkeypatch):
    monkeypatch.delenv("TOKYN_MOCK", raising=False)
    agent = rt.Agent("A", "i", model="nuovo:modello")
    with pytest.raises(rt.TokynRuntimeError, match='fornitore sconosciuto "nuovo"'):
        agent.ask("x")


def test_malformed_answers_do_not_crash(server):
    ns = _agents(METEO.replace("MODEL", "openai:gpt-5.6-luna").replace("    output: Meteo\n", ""))
    # choices che non sono una lista di oggetti: si riprova, poi un errore chiaro
    server.reply(*[{"choices": {"a": 1}}] * 4, {"choices": ["x"]})
    with pytest.raises(rt.TokynRuntimeError, match="senza choices"):
        ns["A"].ask("x")
    # message e function non oggetti, usage con valori strani: nessun crash
    server.reply({"choices": [{"message": {"tool_calls": [{"id": "a", "function": "meteo"}]}, "finish_reason": "tool_calls"}],
                  "usage": {"prompt_tokens": "tanti", "prompt_tokens_details": None}},
                 {"choices": [{"message": "ciao", "finish_reason": "stop"}]})
    assert ns["A"].ask("x") == ""
    assert server.bodies()[-1]["messages"][-1] == {"role": "tool", "tool_call_id": "a", "content": "Lo strumento None non esiste."}


def test_retry_rules_from_the_providers_docs(server, monkeypatch):
    ns = _agents('agent A:\n    model: "openrouter:openai/gpt-5.6-luna"\n    instructions: "i"\n')
    # 501: riprovare non serve; un 4xx dentro un HTTP 200 nemmeno
    server.reply((501, "<html>Not Implemented</html>", {}))
    with pytest.raises(rt.TokynRuntimeError, match="501"):
        ns["A"].ask("x")
    server.reply({"error": {"message": "Invalid tool schema", "code": 400}})
    with pytest.raises(rt.TokynRuntimeError, match="Invalid tool schema") as err:
        ns["A"].ask("x")
    assert err.value.bad_request and server.sleeps == []
    # OpenRouter: il 402 del budget delle richieste in corso si riprova (con Retry-After); Retry-After come data HTTP
    server.reply((402, {"error": {"message": "busy", "metadata": {"limit_source": "openrouter_in_flight_budget"}}},
                   {"Retry-After": "1"}),
                 (429, "{}", {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}),
                 _chat("ok"))
    assert ns["A"].ask("x") == "ok"
    assert server.sleeps == [1.0, 0.0]
    # un 402 qualsiasi resta credito esaurito
    server.reply((402, {"error": {"message": "Insufficient credits"}}, {"Retry-After": "1"}))
    with pytest.raises(rt.TokynRuntimeError, match="credito o quota esauriti"):
        ns["A"].ask("x")


def test_base_url_without_scheme(server, monkeypatch):
    monkeypatch.setenv("TOKYN_OPENAI_BASE_URL", "localhost:8000/v1")
    with pytest.raises(rt.TokynRuntimeError, match="non è un indirizzo web"):
        _agents('agent A:\n    model: "openai-compatible:m"\n    instructions: "i"\n')["A"].ask("x")
    assert server.requests == [] and server.sleeps == []


class _Contatore:
    """Conta le richieste in corso nello stesso momento sul finto server."""

    def __init__(self):
        self.lock = threading.Lock()
        self.attive = 0
        self.massimo = 0

    def __enter__(self):
        with self.lock:
            self.attive += 1
            self.massimo = max(self.massimo, self.attive)

    def __exit__(self, *exc):
        with self.lock:
            self.attive -= 1


def test_ask_all_sends_requests_in_parallel_in_order(server, monkeypatch):
    for key in ("chiamate", "input", "output"):
        monkeypatch.setitem(rt._USAGE, key, 0)
    monkeypatch.setattr(rt, "_USO_FORNITORI", {})
    contatore = _Contatore()

    def handler(body):
        text = body["messages"][-1]["content"]
        with contatore:
            threading.Event().wait(float(text.split()[1]))  # time.sleep qui è finto: attese diverse per ogni testo
        return 200, _chat(f"risposta a {text}", usage={"prompt_tokens": 10, "completion_tokens": 2}), {}

    server.handler = handler
    texts = [f"t{i} {d}" for i, d in enumerate([0.5, 0.05, 0.3, 0.0, 0.2, 0.1, 0.4, 0.0])]
    ns = _agents('agent A:\n    model: "openai:gpt-5.6-luna"\n    instructions: "i"\n')
    assert ns["A"].ask_all(texts) == [f"risposta a {t}" for t in texts]
    assert 2 <= contatore.massimo <= rt.PARALLELO == 4
    assert all(len(b["messages"]) == 2 for b in server.bodies())  # senza memoria
    assert (rt._USAGE["chiamate"], rt._USAGE["input"], rt._USAGE["output"]) == (8, 80, 16)
    assert rt._USO_FORNITORI == {"openai": 8}

    monkeypatch.setenv("TOKYN_PARALLELO", "2")
    contatore.massimo = 0
    assert ns["A"].ask_all(texts[:5]) == [f"risposta a {t}" for t in texts[:5]]
    assert contatore.massimo == 2


def test_ask_all_reports_every_failed_text(server, monkeypatch):
    def handler(body):
        text = body["messages"][-1]["content"]
        if text.startswith("male"):
            return 400, {"error": {"message": "richiesta sbagliata"}}, {}
        return 200, _chat("ok"), {}

    server.handler = handler
    ns = _agents('agent A:\n    model: "openai:gpt-5.6-luna"\n    instructions: "i"\n')
    texts = ["bene", "male 1", "bene", "male 3", "bene"]
    with pytest.raises(rt.TokynRuntimeError, match=r"2 testi su 5 senza risposta; il primo è testi\[1\] \('male 1'\): "
                                                   r"chiamata a openai fallita.*\(senza risposta: testi\[1\], testi\[3\]\)"):
        ns["A"].ask_all(texts)
    assert len(server.requests) == 5  # le altre richieste sono arrivate fino in fondo
    # un errore di configurazione si dice una volta sola, prima di qualunque richiesta
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(rt.TokynRuntimeError, match="^manca la chiave OPENAI_API_KEY"):
        ns["A"].ask_all(texts)
    assert len(server.requests) == 5


def test_ask_all_system_exit_in_a_thread_is_not_lost(server, monkeypatch):
    # SystemExit in un thread finirebbe nel nulla (e poi un KeyError): ask_all lo fa uscire com'è
    def chiedi(agent, text, history):
        if text == "esci":
            raise SystemExit(3)
        return text.upper(), text, None

    monkeypatch.setattr(rt, "_chiedi_chat", chiedi)
    a = _agents('agent A:\n    model: "openai:gpt-5.6-luna"\n    instructions: "i"\n')["A"]
    assert a.ask_all(["a", "b", "c"]) == ["A", "B", "C"]
    for n in ("1", "4"):
        monkeypatch.setenv("TOKYN_PARALLELO", n)
        with pytest.raises(SystemExit) as err:
            a.ask_all(["a", "esci", "c"])
        assert err.value.code == 3


def test_ask_all_with_no_texts_makes_no_checks(server, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setenv("TOKYN_PARALLELO", "0")
    assert _agents('agent A:\n    model: "openai:gpt-5.6-luna"\n    instructions: "i"\n')["A"].ask_all([]) == []
    assert server.requests == []
