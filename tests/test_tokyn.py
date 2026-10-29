import os
import subprocess
import sys
from pathlib import Path

import pytest

from tokyn.compiler import check_source, compile_source, run_source

ROOT = Path(__file__).resolve().parent.parent


def codes(source):
    return [d.code for d in check_source(source).diagnostics if d.severity == "errore"]


def run(source, capsys, mock=True):
    rc = run_source(source, "test.tokyn", mock=mock)
    out = capsys.readouterr()
    return rc, out.out, out.err


# ------------------------------------------------------------ programmi validi

def test_examples_are_valid():
    for path in sorted((ROOT / "examples").glob("*.tokyn")):
        result = check_source(path.read_text(encoding="utf-8"), str(path))
        assert result.ok, f"{path.name}: {[d.to_dict() for d in result.diagnostics]}"


@pytest.mark.parametrize("plugin,answers", [("tokyn", "il pc non parte\nesci\n"), ("tokyn-en", "the pc won't start\nquit\n")])
def test_skill_reference_is_valid(capsys, monkeypatch, plugin, answers):
    import io
    skill = (ROOT / "plugins" / plugin / "skills" / "tokyn" / "SKILL.md").read_text(encoding="utf-8")
    start = skill.index("```\nimport math") + 4
    src = skill[start:skill.index("```", start)]
    monkeypatch.setattr(sys, "stdin", io.StringIO(answers))
    rc, _, err = run(src, capsys)
    assert rc == 0, err


def test_hello(capsys):
    rc, out, _ = run('main:\n    print("ciao")\n', capsys)
    assert rc == 0 and out == "ciao\n"


def test_logic_and_loops(capsys):
    src = '''
def somma(numeri: list[int]) -> int:
    """Somma una lista."""
    totale = 0
    for n in numeri:
        if n < 0:
            continue
        totale += n
    return totale

main:
    print(somma([1, 2, -5, 3]))
    for i, v in enumerate(["a", "b"]):
        print(f"{i}={v.upper()}")
    print(2 * (3 + 4), 10 - (2 - 1), not (1 > 2))
'''
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert out.split("\n")[:4] == ["6", "0=A", "1=B", "14 9 True"]


def test_structured_output_mock(capsys):
    src = '''
type Ticket:
    categoria: "tecnico" | "altro"
    urgente: bool
    tag: list[str]

agent A:
    model: "mock"
    instructions: "Classifica."
    output: Ticket

main:
    t = A.ask("aiuto")
    print(t.categoria, t.urgente, len(t.tag))
    t = A.ask("ancora")
    print(t.categoria, t.urgente)
'''
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    # le liste hanno 2 elementi e le scelte cambiano da una ask all'altra, così si provano più rami
    assert out.split("\n")[:2] == ["tecnico True 2", "altro False"]


def test_type_constructor_and_json(capsys):
    src = '''
type Persona:
    nome: str
    eta: int

main:
    p = Persona(nome="Anna", eta=30)
    p.eta = 31
    print(json_dump(p))
'''
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert '"eta": 31' in out


def test_slices(capsys):
    src = 'main:\n    s = "buongiorno"\n    xs = [1, 2, 3, 4]\n    print(s[:4], s[-4:], xs[1:3], len(xs[2:]), s[:2].upper())\n'
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert out.strip() == "buon orno [2, 3] 2 BU"


def test_python_operators(capsys):
    src = (
        "from os import path as p\n\n"
        "main:\n"
        "    x = 7\n"
        "    x //= 2\n"
        "    x %= 2\n"
        "    print(x, 2 ** 3, -2 ** 2, 2 ** -1, (1 + 1) ** 2)\n"
        '    print("abc"[::-1], [1, 2, 3, 4][::2], p.join("a", "b"))\n'
        "    import_re = 0\n"
    )
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert out.split("\n")[:2] == ["1 8 -4 0.5 4", "cba [1, 3] a/b"]


def test_raw_strings_and_descriptions_with_accents(capsys):
    src = 'import re\n\ntype T:\n    a: str "perché\\nsì"\n\nmain:\n    print(re.findall(r"\\d+", "a1b22"))\n'
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert out.strip() == "['1', '22']"
    import tokyn.runtime as rt
    exec(compile_source(src).python, {"__name__": "x"})
    assert rt._TYPES["T"].__tokyn_schema__()["properties"]["a"]["description"] == "perché\nsì"


def test_order_of_constants_functions_and_agents(capsys):
    src = (
        "LIMITE = 3\n"
        "def f(n=LIMITE) -> int:\n    return n * DOPPIO\n"
        "DOPPIO = 2\n"
        "VALORE = f()\n\n"
        'agent Capo:\n    model: "mock"\n    instructions: "c"\n    tools: [Tecnico]\n\n'
        'agent Tecnico:\n    model: "mock"\n    instructions: "t"\n\n'
        "main:\n    print(VALORE, Capo.ask(\"x\"))\n"
    )
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert out.startswith("6 [mock Capo]")


def test_text_in_triple_quotes_is_not_code():
    src = 'agent A:\n    instructions: """\n        while you wait, try this:\n        def ...\n    """\n'
    assert codes(src) == []
    # un """ in un commento o in una stringa normale non deve confondere il riconoscimento del testo
    src = '# le istruzioni vanno tra """\nX = \'"""\'\nagent A:\n    instructions: """\n        del documento\n        def inisci\n    """\n'
    assert codes(src) == []


def test_fstring_hint_only_for_real_fstrings():
    assert codes('main:\n    d = {"pdf": {"estensione" ".pdf"}}\n') == ["E008"]


def test_no_python_warnings_for_escapes_in_text():
    import warnings
    src = 'type R:\n    s: str "come \\d+"\n\ndef f(t: str) -> str:\n    """Cerca \\d+."""\n    return t\n'
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert check_source(src).ok
    assert not [w for w in caught if issubclass(w.category, SyntaxWarning)]


def test_to_number(capsys):
    src = ('main:\n    print(to_number("42") + 1, to_number("4,50"), to_number("1.234.567"), to_number("abc", 0))\n'
           '    print(to_number("n/d"))\n')
    rc, out, err = run(src, capsys)
    assert rc == 1 and out.split("\n")[0] == "43 4.5 1234567 0"
    assert "test.tokyn:3" in err and "to_number(testo, 0)" in err


def test_cli_usage_report(tmp_path):
    f = tmp_path / "a.tokyn"
    f.write_text('agent A:\n    instructions: "i"\n\nmain:\n    print(A.ask("x"))\n', encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "tokyn", "run", str(f), "--mock", "--usage"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and "token:" in r.stderr and "Batch API" in r.stderr


def test_number_formats(capsys):
    rc, out, err = run("main:\n    x = 1_000 + 1\n    print(x, 2.5e3, 1e-3)\n", capsys)
    assert rc == 0, err
    assert out.strip() == "1001 2500.0 0.001"


def test_defaults_for_missing_file_and_network(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = 'main:\n    print(read_file("manca.txt", "vuoto"))\n    print(http_get("http://127.0.0.1:9/x", "giu"))\n'
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert out.split() == ["vuoto", "giu"]
    rc, _, err = run('main:\n    print(http_get("http://127.0.0.1:9/x"))\n', capsys)
    assert rc == 1 and "test.tokyn:2" in err and "http_get(..., \"\")" in err
    # il valore di riserva copre ogni errore: indirizzo non valido, cartella al posto di un file, JSON rotto
    src = ('main:\n    print(http_get("www.senza-schema.it", "a"), http_post("", {}, "b"), read_file(".", "c"))\n'
           '    print(json_parse("non json", {}), json_parse(\'{"k": 1}\', {}))\n')
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert out.split("\n")[:2] == ["a b c", "{} {'k': 1}"]


def test_python_interop(capsys):
    src = 'import math\nfrom statistics import mean\n\nmain:\n    print(math.sqrt(16), mean([1, 3]))\n'
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert out.strip() == "4.0 2"


def test_agent_as_tool_and_constants(capsys):
    src = '''
PROMPT = "Sei un traduttore."

agent Traduttore:
    model: "mock"
    instructions: PROMPT

agent Capo:
    model: "mock"
    instructions: "Coordina."
    tools: [Traduttore]

main:
    print(Capo.ask("traduci ciao"))
'''
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert "[mock Capo]" in out


# ------------------------------------------------------------ errori statici

@pytest.mark.parametrize("src,code", [
    ("main:\n    while True:\n        pass\n", "E002"),
    ("def f(x)\n    pass\n", "E003"),
    ("main:\nprint(1)\n", "E004"),
    ("main:\n    x = 1\n        y = 2\n", "E005"),
    ('agent A:\n    model = "x"\n', "E006"),
    ("main:\n    print(len([1, 2)\n", "E008"),
    ("def f():\n    pass\ndef f():\n    pass\n", "E101"),
    ("type T:\n    x: string\n", "E110"),
    ('type T:\n    x: "a" | int\n', "E111"),
    ('def f(x):\n    return x\nagent A:\n    instructions: "i"\n    tools: [f]\n', "E121"),
    ('def f(x: str):\n    return x\nagent A:\n    instructions: "i"\n    tools: [f]\n', "E122"),
    ('agent A:\n    instruction: "i"\n', "E130"),
    ('agent A:\n    model: "claude"\n', "E131"),
    ('agent A:\n    instructions: "i"\n    tools: [nessuno]\n', "E133"),
    ('agent A:\n    instructions: "i"\n    output: Nulla\n', "E134"),
    ('agent A:\n    instructions: "i"\n    memory: "si"\n', "E135"),
    ('X = 1\nmain:\n    X = 2\n', "E142"),
    ("main:\n    break\n", "E150"),
    ("main:\n    print(nome)\n", "E160"),
    ("main:\n    print(x)\n    x = 1\n", "E161"),
    ('agent A:\n    instructions: "i"\nmain:\n    A.run("x")\n', "E170"),
    ('type T:\n    a: str\nmain:\n    t = T(a="x")\n    print(t.b)\n', "E171"),
    ('main:\n    x = "a"\n    x.uppper()\n', "E175"),
    ("def f(a: int):\n    return a\nmain:\n    f(1, 2)\n", "E180"),
    ("def f(a: int):\n    return a\nmain:\n    f(b=1)\n", "E181"),
    ('type T:\n    a: str\nmain:\n    t = T("x")\n', "E182"),
    ('type T:\n    a: str\nmain:\n    t = T(a="x", b=1)\n', "E183"),
    ('type T:\n    a: str\n    b: int\nmain:\n    t = T(a="x")\n', "E184"),
    ('agent A:\n    instructions: "i"\nmain:\n    A.ask()\n', "E186"),
    ('agent A:\n    instructions: "i"\nmain:\n    A("x")\n', "E187"),
    ('type T:\n    c: "a" | "b"\nagent A:\n    instructions: "i"\n    output: T\nmain:\n    t = A.ask("x")\n    if t.c == "z":\n        pass\n', "E190"),
    ('main:\n    print(f"{nome}")\n', "E160"),
    ('main:\n    x = "a" + 1\n', "E194"),
    ('agent A:\n    instructions: "i"\n    effort: "poco"\n', "E145"),
    ('agent A:\n    instructions: "i"\nmain:\n    A.ask_all()\n', "E186"),
    ('agent A:\n    instructions: "i"\nmain:\n    A.ask_all("un testo solo")\n', "E186"),
    ("type N:\n    figli: list[N]\n", "E115"),
    ("type A:\n    b: B\ntype B:\n    a: list[A]\n", "E115"),
    ("main:\n    x = 1\n    if x == 1: print(x)\n", "E002"),
    ("type T:\n    p: 1 | 2 | 3\n", "E002"),
    ('main:\n    s = "abc"\n    print(s["a":])\n', "E176"),
    # costrutti Python che Tokyn non ha: errore mirato con l'alternativa
    ("main:\n    ys = [x * 2 for x in [1, 2]]\n", "E002"),
    ('main:\n    x = 1\n    y = "a" if x > 0 else "b"\n', "E002"),
    ("main:\n    x = None\n    if x is None:\n        pass\n", "E002"),
    ("main:\n    a, b = [1, 2]\n", "E002"),
    ("def f():\n    return 1, 2\n", "E002"),
    ("main:\n    print((1, 2))\n", "E002"),
    ("main:\n    print({1, 2})\n", "E002"),
    ('main:\n    d = {"a": 1}\n    del d["a"]\n', "E002"),
    ('main:\n    raise ValueError("x")\n', "E002"),
    ("main:\n    assert True\n", "E002"),
    ("main:\n    def g():\n        return 1\n", "E002"),
    ("A = B + 1\nB = 2\n", "E162"),
    ("A = f()\ndef f() -> int:\n    return 1\n", "E162"),
    ("def f(n=LIMITE):\n    return n\nLIMITE = 5\n", "E162"),
    ('agent A:\n    instructions: "a"\n    tools: [B]\nagent B:\n    instructions: "b"\n    tools: [A]\n', "E144"),
    ('main:\n    d = {"k": 1}\n    print(f"{d["k"]}")\n', "E002"),
])
def test_static_errors(src, code):
    assert code in codes(src)


def test_python_idiom_hint():
    d = check_source("main:\n    ys = [x * 2 for x in [1, 2]]\n").diagnostics[0]
    assert "comprehension" in d.message and ".append(" in d.hint


def test_else_if_is_not_a_ternary():
    src = "main:\n    x = 1\n    if x:\n        pass\n    else if x:\n        pass\n"
    assert codes(src) == ["E008"]


def test_suggestions_present():
    src = 'agent A:\n    instructions: "i"\n    tools: [cerca]\ndef cerca_faq(q: str) -> str:\n    """x"""\n    return q\n'
    d = [d for d in check_source(src).diagnostics if d.code == "E133"][0]
    assert 'Forse intendevi "cerca_faq"' in d.hint


def test_error_positions():
    d = check_source("main:\n    print(nome)\n").diagnostics[0]
    assert (d.line, d.column) == (2, 11)


def test_missing_main_is_warning():
    result = check_source('agent A:\n    instructions: "i"\n')
    assert result.ok
    assert result.diagnostics[0].code == "W001"


# ------------------------------------------------------------ errori di esecuzione

def test_runtime_error_maps_to_source_line(capsys):
    src = 'main:\n    x = [1, 2]\n    print(x[5])\n'
    rc, _, err = run(src, capsys)
    assert rc == 1
    assert "test.tokyn:3" in err and "posizione fuori dalla lista" in err


def test_runtime_error_line_after_multiline_string(capsys):
    src = 'agent A:\n    model: "mock"\n    instructions: """\n        Riga uno.\n        Riga due.\n    """\n\nmain:\n    x = [1]\n    print(x[3])\n'
    rc, _, err = run(src, capsys)
    assert rc == 1 and "test.tokyn:10" in err


def test_missing_input_explains_how_to_pass_it(capsys, monkeypatch):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    rc, _, err = run('main:\n    x = input("> ")\n    print(x)\n', capsys)
    assert rc == 1 and "test.tokyn:2" in err and "printf" in err


def test_tool_results_and_env_defaults(monkeypatch):
    import datetime
    import tokyn.runtime as rt
    fn = rt.tool("quando", "Quando.", {}, rt.T.ANY)(lambda: {"il": datetime.date(2026, 1, 2)})
    assert rt._call_tool(fn, {}) == '{"il": "2026-01-02"}'
    monkeypatch.delenv("TOKYN_NON_ESISTE", raising=False)
    assert rt.env("TOKYN_NON_ESISTE", None) is None
    with pytest.raises(rt.TokynRuntimeError):
        rt.env("TOKYN_NON_ESISTE")


def test_missing_api_key(capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("TOKYN_MOCK", raising=False)
    import tokyn.runtime as rt
    monkeypatch.setattr(rt, "_CLIENT", None)
    src = 'agent A:\n    instructions: "i"\nmain:\n    print(A.ask("x"))\n'
    rc = run_source(src, "test.tokyn", mock=False)
    err = capsys.readouterr().err
    assert rc == 1 and "ANTHROPIC_API_KEY" in err and "--mock" in err


def test_old_anthropic_sdk_is_reported(monkeypatch):
    """Prima della 0.108 l'SDK non accetta `fallbacks`: meglio dirlo subito che fallire a ogni chiamata."""
    import types
    import tokyn.runtime as rt
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("TOKYN_LANG", "en")
    monkeypatch.setattr(rt, "_CLIENT", None)
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(__version__="0.107.1", Anthropic=object))
    with pytest.raises(rt.TokynRuntimeError) as err:
        rt._client()
    assert "too old (0.107.1)" in err.value.message and '0.108' in err.value.hint
    assert [rt._sdk_too_old(v) for v in ("0.40.0", "0.108.0", "0.125.0", "1.0.0", "2.3.0", "", "dev")] == \
        [True, False, False, False, False, False, False]


# ------------------------------------------------------------ strumenti e schema

def test_tool_schema_and_validation():
    src = '''
type Prodotto:
    nome: str
    prezzo: float

def cerca(q: str, limite: int) -> list[Prodotto]:
    """Cerca prodotti."""
    return [Prodotto(nome=q, prezzo=1.5)]

agent A:
    model: "mock"
    instructions: "i"
    tools: [cerca]
'''
    compiled = compile_source(src)
    ns = {"__name__": "x"}
    exec(compiled.python, ns)
    import tokyn.runtime as rt
    schema = rt._tool_schema(ns["cerca"])
    assert schema["input_schema"]["properties"]["limite"] == {"type": "integer"}
    assert rt._call_tool(ns["cerca"], {"q": "pane", "limite": 3}) == '[{"nome": "pane", "prezzo": 1.5}]'
    with pytest.raises(ValueError):
        rt._call_tool(ns["cerca"], {"q": "pane", "limite": "tre"})


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _reply(*content, stop="end_turn", usage=None):
    return _Block(content=list(content), stop_reason=stop, usage=usage)


def _text(t):
    return _Block(type="text", text=t)


def _use(id, name, **inp):
    return _Block(type="tool_use", id=id, name=name, input=inp)


class _FakeClient:
    """Simula l'API: restituisce le risposte preparate e registra i parametri di ogni chiamata."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.messages = self
        self.beta = self

    def create(self, **kwargs):
        self.calls.append(dict(kwargs, messages=list(kwargs["messages"])))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


METEO = '''
type Meteo:
    citta: str
    gradi: int

def meteo(citta: str) -> str:
    """Restituisce la temperatura di una città."""
    return f"{citta}: 18 gradi"

agent A:
    instructions: "Dimmi il meteo."
    tools: [meteo]
    output: Meteo
'''


def _agents(src, monkeypatch, fake):
    import tokyn.runtime as rt
    ns = {"__name__": "x"}
    exec(compile_source(src).python, ns)
    monkeypatch.setattr(rt, "_CLIENT", fake)
    monkeypatch.setitem(rt._FALLBACKS, "attivi", True)
    monkeypatch.delenv("TOKYN_MOCK", raising=False)
    return ns


def test_agent_loop_with_fake_api(monkeypatch):
    fake = _FakeClient(
        _reply(_use("t1", "meteo", citta="Padova"), stop="tool_use"),
        _reply(_text('{"citta": "Padova", "gradi": "tanti"}')),
        _reply(_text('{"citta": "Padova", "gradi": 18}')),
    )
    ns = _agents(METEO, monkeypatch, fake)
    result = ns["A"].ask("Che tempo fa a Padova?")
    assert (result.citta, result.gradi) == ("Padova", 18)
    # lo strumento è stato eseguito e il risultato è tornato all'IA
    assert fake.calls[1]["messages"][-1]["content"][0]["content"] == "Padova: 18 gradi"
    # una risposta non valida viene rimandata all'IA con l'errore
    assert "gradi" in fake.calls[2]["messages"][-1]["content"]
    first = fake.calls[0]
    assert first["model"] == "claude-sonnet-5-5" and first["max_tokens"] == 16000
    # output strutturati nativi: niente strumento `rispondi`, schema nell'output_config
    assert [t["name"] for t in first["tools"]] == ["meteo"] and first["tools"][0]["strict"] is True
    assert first["output_config"]["format"]["schema"]["required"] == ["citta", "gradi"]
    # caching: istruzioni e strumenti fissi, più la cache automatica della conversazione
    assert first["system"][0]["cache_control"] == {"type": "ephemeral"} and first["cache_control"] == {"type": "ephemeral"}
    assert first["fallbacks"] == "default" and first["betas"] == ["server-side-fallback-2026-07-01"]


def test_free_dict_output_falls_back_to_answer_tool(monkeypatch):
    src = 'type R:\n    dati: dict\n\nagent A:\n    instructions: "i"\n    model: "claude-haiku"\n    output: R\n'
    fake = _FakeClient(_reply(_use("t1", "rispondi", dati={"k": 1}), stop="tool_use"))
    ns = _agents(src, monkeypatch, fake)
    assert ns["A"].ask("x").dati == {"k": 1}
    call = fake.calls[0]
    assert [t["name"] for t in call["tools"]] == ["rispondi"] and "output_config" not in call
    assert "fallbacks" not in call  # Haiku non ha i fallback lato server


def test_fallbacks_are_dropped_if_the_api_rejects_them(monkeypatch):
    BadRequestError = type("BadRequestError", (Exception,), {})
    src = 'agent A:\n    instructions: "i"\n    effort: "low"\n'
    fake = _FakeClient(BadRequestError("fallbacks non supportati"), _reply(_text("uno")), _reply(_text("due")))
    ns = _agents(src, monkeypatch, fake)
    assert [ns["A"].ask("x"), ns["A"].ask("y")] == ["uno", "due"]
    assert ["fallbacks" in c for c in fake.calls] == [True, False, False]
    assert fake.calls[1]["output_config"] == {"effort": "low"}


def test_truncated_answers_never_run_tools(monkeypatch):
    import tokyn.runtime as rt
    fake = _FakeClient(_reply(_use("t1", "meteo", citta="Pad"), stop="max_tokens"))
    ns = _agents(METEO, monkeypatch, fake)
    with pytest.raises(rt.TokynRuntimeError, match="troppo lunga"):
        ns["A"].ask("x")
    assert len(fake.calls) == 1  # lo strumento non è stato eseguito e il risultato non è tornato all'IA
    fake = _FakeClient(_reply(_text("La risposta comple"), stop="model_context_window_exceeded"))
    ns = _agents(METEO, monkeypatch, fake)
    with pytest.raises(rt.TokynRuntimeError, match="contesto"):
        ns["A"].ask("x")


def test_unrelated_bad_requests_keep_fallbacks(monkeypatch):
    import tokyn.runtime as rt
    BadRequestError = type("BadRequestError", (Exception,), {})
    fake = _FakeClient(BadRequestError("prompt is too long"), _reply(_text("ok")))
    ns = _agents('agent A:\n    instructions: "i"\n', monkeypatch, fake)
    with pytest.raises(rt.TokynRuntimeError, match="prompt is too long"):
        ns["A"].ask("x")
    assert ns["A"].ask("y") == "ok" and rt._FALLBACKS["attivi"] and len(fake.calls) == 2


def test_server_errors_are_retried(monkeypatch):
    import tokyn.runtime as rt
    monkeypatch.setattr(rt._time, "sleep", lambda s: None)
    Unavailable = type("ServiceUnavailableError", (Exception,), {"status_code": 503})
    fake = _FakeClient(Unavailable("503"), _reply(_text("ok")))
    ns = _agents('agent A:\n    instructions: "i"\n', monkeypatch, fake)
    assert ns["A"].ask("x") == "ok"


def test_usage_counts_every_fallback_attempt(monkeypatch):
    import tokyn.runtime as rt
    for key in rt._USAGE:
        monkeypatch.setitem(rt._USAGE, key, 0)
    usage = _Block(input_tokens=5, output_tokens=1, iterations=[
        _Block(type="message", input_tokens=100, output_tokens=0),
        _Block(type="fallback_message", input_tokens=100, output_tokens=20)])
    fake = _FakeClient(_reply(_text("ok"), usage=usage))
    ns = _agents('agent A:\n    instructions: "i"\n', monkeypatch, fake)
    ns["A"].ask("x")
    assert (rt._USAGE["input"], rt._USAGE["output"], rt._USAGE["fallback"]) == (200, 20, 1)
    assert "modello di riserva" in rt.usage_report()


class _FakeBatches:
    """Simula la Batch API: ogni batch risponde con le risposte preparate per custom_id, in ordine sparso."""

    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.created = []
        self.retrieves = 0

    def create(self, requests):
        # copia, come fa l'SDK quando invia la richiesta: dopo i messaggi continuano a crescere
        self.created.append([dict(r, params=dict(r["params"], messages=list(r["params"]["messages"]))) for r in requests])
        return _Block(id=f"b{len(self.created)}", processing_status="in_progress",
                      request_counts=_Block(succeeded=0, errored=0, canceled=0, expired=0, processing=len(requests)))

    def retrieve(self, batch_id):
        self.retrieves += 1
        return _Block(id=batch_id, processing_status="ended")

    def results(self, batch_id):
        replies = self.rounds.pop(0)
        for cid in sorted(replies, reverse=True):
            reply = replies[cid]
            if reply is None:
                yield _Block(custom_id=cid, result=_Block(type="errored"))
            else:
                yield _Block(custom_id=cid, result=_Block(type="succeeded", message=reply))


def test_ask_all_uses_the_batch_api(monkeypatch, capsys):
    import tokyn.runtime as rt
    monkeypatch.setattr(rt._time, "sleep", lambda s: None)
    usage = _Block(input_tokens=100, output_tokens=10, cache_read_input_tokens=80, cache_creation_input_tokens=0)
    batches = _FakeBatches([
        {"0": _reply(_use("t1", "meteo", citta="Roma"), stop="tool_use"),
         "1": _reply(_text('{"citta": "Bari", "gradi": 20}'), usage=usage),
         "2": None},
        {"0": _reply(_text('{"citta": "Roma", "gradi": 22}'))},
    ])
    fake = _FakeClient(_reply(_text('{"citta": "Lecce", "gradi": 25}')))  # chiamata normale per l'errore nel batch
    fake.batches = batches
    ns = _agents(METEO, monkeypatch, fake)
    before = dict(rt._USAGE)
    result = ns["A"].ask_all(["Roma?", "Bari?", "Lecce?"])
    assert [(r.citta, r.gradi) for r in result] == [("Roma", 22), ("Bari", 20), ("Lecce", 25)]
    # due turni di batch: il secondo solo per il testo che aveva chiesto uno strumento
    assert [[r["custom_id"] for r in reqs] for reqs in batches.created] == [["0", "1", "2"], ["0"]]
    params = batches.created[0][0]["params"]
    assert "fallbacks" not in params and params["output_config"]["format"]["type"] == "json_schema"
    assert batches.created[1][0]["params"]["messages"][-1]["content"][0]["content"] == "Roma: 18 gradi"
    assert "risposte pronte" in capsys.readouterr().err
    assert rt._USAGE["chiamate_batch"] - before["chiamate_batch"] == 3
    assert rt._USAGE["cache_lette"] - before["cache_lette"] == 80


def test_ask_all_retries_refusals_and_reports_failures(monkeypatch):
    import tokyn.runtime as rt
    monkeypatch.setattr(rt._time, "sleep", lambda s: None)
    refused = _reply(_text(""), stop="refusal")
    batches = _FakeBatches([{"0": _reply(_text("uno")), "1": refused, "2": refused}])
    # il rifiuto nel batch si riprova con la chiamata normale: il testo 1 ora va, il testo 2 viene rifiutato di nuovo
    fake = _FakeClient(_reply(_text("due")), refused)
    fake.batches = batches
    ns = _agents('agent A:\n    instructions: "i"\n', monkeypatch, fake)
    with pytest.raises(rt.TokynRuntimeError, match=r"1 testi su 3 senza risposta; il primo è testi\[2\]"):
        ns["A"].ask_all(["a", "b", "c"])
    assert all("fallbacks" in c for c in fake.calls)  # la ripresa usa i fallback, che il batch non ammette


def test_ask_all_in_mock_and_types(capsys):
    src = (
        'type T:\n    c: "a" | "b"\n\nagent A:\n    model: "mock"\n    instructions: "i"\n    output: T\n\n'
        'main:\n    for t in A.ask_all(["x", "y"]):\n        print(t.c)\n'
    )
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert out.split() == ["a", "b"]
    assert "E171" in codes(src.replace("print(t.c)", "print(t.nessuno)"))


def test_cli_check_json(tmp_path):
    f = tmp_path / "a.tokyn"
    f.write_text("main:\n    print(x)\n")
    r = subprocess.run([sys.executable, "-m", "tokyn", "check", "--json", str(f)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 1
    assert '"code": "E160"' in r.stdout


# ------------------------------------------------------------ distribuzione

def _lark_only_env():
    """Ambiente in cui Python vede lark ma non il pacchetto tokyn installato."""
    import lark
    return dict(os.environ, PYTHONPATH=str(Path(lark.__file__).resolve().parent.parent), TOKYN_MOCK="1")


def test_build_standalone_runs_without_tokyn(tmp_path):
    src = 'type T:\n    a: str\n\nagent A:\n    instructions: "i"\n    output: T\n\nmain:\n    print(A.ask("x").a, read_file != None)\n'
    py = tmp_path / "prog.py"
    py.write_text(compile_source(src, "prog.tokyn", standalone=True).python, encoding="utf-8")
    # -S: niente site-packages, quindi né tokyn né lark né anthropic
    r = subprocess.run([sys.executable, "-S", str(py)], capture_output=True, text=True, cwd=tmp_path,
                       env=dict(os.environ, TOKYN_MOCK="1", PYTHONPATH=""))
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "esempio a True"


def test_plugins_are_up_to_date():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_skill.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_skill_bundle_works_from_any_folder(tmp_path):
    import zipfile
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_skill.py"), str(tmp_path / "skill.zip")],
                   check=True, capture_output=True)
    zipfile.ZipFile(tmp_path / "skill.zip").extractall(tmp_path / "skills")
    cli = tmp_path / "skills" / "tokyn" / "tokyn_cli.py"
    work = tmp_path / "lavoro"
    work.mkdir()
    (work / "a.tokyn").write_text('main:\n    print("ciao " + input())\n', encoding="utf-8")
    env = _lark_only_env()
    r = subprocess.run([sys.executable, "-S", str(cli), "check", "--json", "a.tokyn"],
                       capture_output=True, text=True, cwd=work, env=env)
    assert r.returncode == 0 and '"ok": true' in r.stdout, r.stdout + r.stderr
    r = subprocess.run([sys.executable, "-S", str(cli), "run", "a.tokyn", "--mock"],
                       input="mondo\n", capture_output=True, text=True, cwd=work, env=env)
    assert r.returncode == 0 and r.stdout.strip() == "ciao mondo", r.stderr


# ------------------------------------------------------------ Claude Code al posto dell'API

FAKE_CLAUDE = r'''#!/usr/bin/env python3
"""Finto `claude -p`: fa da client MCP verso il ponte di Tokyn e risponde come Claude Code (--output-format json)."""
import json, os, subprocess, sys

args = sys.argv[1:]
opt = lambda name: args[args.index(name) + 1] if name in args else None
with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
tool_text = ""
if opt("--mcp-config"):
    server = json.loads(opt("--mcp-config"))["mcpServers"]["tokyn"]
    bridge = subprocess.Popen([server["command"], *server["args"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    def rpc(rid, method, params):
        bridge.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n")
        bridge.stdin.flush()
        return json.loads(bridge.stdout.readline())["result"]
    rpc(1, "initialize", {"protocolVersion": "2025-06-18"})
    tool = rpc(2, "tools/list", {})["tools"][0]
    result = rpc(3, "tools/call", {"name": tool["name"], "arguments": {k: "Padova" for k in tool["inputSchema"]["properties"]}})
    tool_text = result["content"][0]["text"]
    bridge.stdin.close()
    bridge.wait()
out = {"type": "result", "subtype": "success", "is_error": False, "stop_reason": "end_turn",
       "usage": {"input_tokens": 3, "output_tokens": 5}, "total_cost_usd": 0.001}
schema = opt("--json-schema")
if schema:
    props = json.loads(schema)["properties"]
    out["structured_output"] = {k: (p["enum"][0] if "enum" in p else 18 if p["type"] == "integer" else tool_text)
                                for k, p in props.items()}
    out["result"] = json.dumps(out["structured_output"])
else:
    out["result"] = f"risposta a: {args[args.index('-p') + 1]}"
print(json.dumps(out))
'''


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    exe.write_text(FAKE_CLAUDE.replace("#!/usr/bin/env python3", f"#!{sys.executable}"), encoding="utf-8")
    exe.chmod(0o755)
    log = tmp_path / "claude.log"
    log.write_text("", encoding="utf-8")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.delenv("TOKYN_BACKEND", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TOKYN_MOCK", raising=False)
    import json
    return lambda: [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def test_claude_code_is_used_without_api_key(fake_claude, capsys):
    import tokyn.runtime as rt
    assert rt._backend() == "claude-code"
    src = ('agent A:\n    model: "claude-haiku"\n    instructions: "Rispondi breve."\n    effort: "low"\n    memory: True\n\n'
           'main:\n    print(A.ask("ciao"))\n    print(A.ask("e poi?"))\n')
    rc, out, err = run(src, capsys, mock=False)
    assert rc == 0, err
    assert out.splitlines()[0] == "risposta a: ciao"
    first, second = fake_claude()
    for flag, value in [("--model", "haiku"), ("--effort", "low"), ("--system-prompt", "Rispondi breve."),
                        ("--tools", ""), ("--setting-sources", ""), ("--output-format", "json")]:
        assert first[first.index(flag) + 1] == value
    # la memoria passa la conversazione precedente nel testo della richiesta
    assert "Utente: ciao" in second[second.index("-p") + 1] and "Nuovo messaggio:\ne poi?" in second[second.index("-p") + 1]


def test_claude_code_tools_run_inside_the_program(fake_claude, capsys):
    src = '''
CHIAMATE = []

type Meteo:
    citta: str
    gradi: int
    cielo: "nuvoloso" | "sereno"

def meteo(citta: str) -> str:
    """Restituisce il meteo di una città."""
    CHIAMATE.append(citta)
    return citta

agent A:
    instructions: "Usa lo strumento."
    tools: [meteo]
    output: Meteo

main:
    m = A.ask("Padova?")
    print(m.citta, m.gradi, m.cielo, CHIAMATE)
'''
    rc, out, err = run(src, capsys, mock=False)
    assert rc == 0, err
    # lo strumento è stato chiamato tramite il ponte MCP e ha modificato la lista del programma
    assert out.strip() == "Padova 18 nuvoloso ['Padova']"
    call = fake_claude()[0]
    assert call[call.index("--allowedTools") + 1] == "mcp__tokyn" and "--json-schema" in call


def test_backend_choice(monkeypatch, tmp_path):
    import tokyn.runtime as rt
    monkeypatch.delenv("TOKYN_BACKEND", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert rt._backend() == "api"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))  # niente `claude`
    assert rt._backend() == "api"
    monkeypatch.setenv("TOKYN_BACKEND", "claude-code")
    assert rt._backend() == "claude-code"


def test_claude_code_chosen_automatically_warns_once(fake_claude, monkeypatch, capsys):
    import tokyn.runtime as rt
    monkeypatch.setattr(rt, "_AVVISO_CLAUDE_CODE", [])
    monkeypatch.setenv("TOKYN_BACKEND", "claude-code")  # scelto da chi lo usa: nessun avviso
    rt._backend()
    assert capsys.readouterr().err == ""
    monkeypatch.delenv("TOKYN_BACKEND")
    assert rt._backend() == "claude-code" and rt._backend() == "claude-code"
    err = capsys.readouterr().err
    assert err.count("Tokyn: senza chiave API") == 1 and "legal-and-compliance" in err


# ------------------------------------------------------------ lingua dei messaggi

def _no_language_env(monkeypatch):
    for name in ("TOKYN_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)


def test_language_selection_rules(monkeypatch):
    import locale
    from tokyn import lingua
    _no_language_env(monkeypatch)
    monkeypatch.setattr(locale, "getlocale", lambda *a: ("Italian_Italy", "1252"))
    assert lingua.lingua() == "it"  # senza variabili decide la lingua del sistema operativo (es. Windows)
    monkeypatch.setattr(locale, "getlocale", lambda *a: (None, None))
    assert lingua.lingua() == "en"  # nessuna indicazione: inglese
    monkeypatch.setenv("LANG", "it_IT.UTF-8")
    assert lingua.lingua() == "it"
    monkeypatch.setenv("LC_MESSAGES", "en_US.UTF-8")  # LC_ALL, LC_MESSAGES, LANG: decide la prima impostata
    assert lingua.lingua() == "en"
    monkeypatch.setenv("LC_ALL", "it_CH.UTF-8")
    assert lingua.lingua() == "it"
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    assert lingua.lingua() == "en"
    lingua.imposta_plugin("it")  # la lingua del plugin prende il posto di quella del sistema
    assert lingua.lingua() == "it"
    lingua.imposta_opzione("en")  # --lang vince sul plugin
    assert lingua.lingua() == "en"
    monkeypatch.setenv("TOKYN_LANG", "it")  # TOKYN_LANG vince su tutto
    assert lingua.lingua() == "it"
    monkeypatch.setenv("TOKYN_LANG", "fr")  # un valore che non conosciamo non conta
    assert lingua.lingua() == "en"
    lingua.imposta_opzione(None)
    assert lingua.lingua() == "it" and lingua.tr("ciao", "hello") == "ciao"


BROKEN = ('type Order:\n    item: str\n    price: float\n\nagent Helper:\n    instruction: "Help."\n\n'
          'main:\n    o = Order(item="pen", price=1.5)\n    print(o.prize)\n    print(missing)\n    total = "Total: " + 5\n')


def _cli(args, env_extra, cwd=ROOT, stdin=None, cmd=None):
    env = {k: v for k, v in os.environ.items() if k not in ("TOKYN_LANG", "LC_ALL", "LC_MESSAGES", "LANG")}
    env.update(env_extra)
    return subprocess.run(cmd or [sys.executable, "-m", "tokyn", *args], capture_output=True, text=True,
                          cwd=cwd, env=env, input=stdin)


def test_cli_lang_flag(tmp_path):
    f = tmp_path / "bad.tokyn"
    f.write_text(BROKEN, encoding="utf-8")
    italian = _cli(["check", str(f)], {"LANG": "it_IT.UTF-8"}).stdout
    assert "errore E130" in italian and "5 errori" in italian
    for args in (["check", "--lang", "en", str(f)], ["--lang", "en", "check", str(f)], ["check", "--lang=en", str(f)]):
        r = _cli(args, {"LANG": "it_IT.UTF-8"})
        assert r.returncode == 1 and "error E130" in r.stdout and "5 errors" in r.stdout, args
    assert "errore E130" in _cli(["check", "--lang", "en", str(f)], {"TOKYN_LANG": "it"}).stdout  # TOKYN_LANG vince
    assert "errore E130" in _cli(["check", "--lang", "it", str(f)], {"LANG": "en_US.UTF-8"}).stdout
    r = _cli(["check", "--lang", "fr", str(f)], {})
    assert r.returncode == 2 and "invalid choice" in r.stderr
    assert "check one or more files" in _cli(["--lang", "en", "--help"], {"LANG": "it_IT.UTF-8"}).stdout
    assert "controlla uno o più file" in _cli(["--help"], {"LANG": "it_IT.UTF-8"}).stdout


@pytest.mark.parametrize("plugin,own,other", [("tokyn", "it", "en"), ("tokyn-en", "en", "it")])
def test_plugin_launcher_speaks_its_language(tmp_path, plugin, own, other):
    launcher = ROOT / "plugins" / plugin / "skills" / "tokyn" / "tokyn_cli.py"
    assert f'LINGUA = "{own}"' in launcher.read_text(encoding="utf-8")  # scritto da build_skill.py
    f = tmp_path / "bad.tokyn"
    f.write_text(BROKEN, encoding="utf-8")
    word = {"it": "errore E130", "en": "error E130"}
    cmd = [sys.executable, "-S", str(launcher), "check", str(f)]
    locale = {"it": "it_IT.UTF-8", "en": "en_US.UTF-8"}
    env = {"PYTHONPATH": _lark_only_env()["PYTHONPATH"]}
    # la lingua del sistema non conta: il plugin parla sempre la sua lingua...
    for lang in ("it", "en"):
        assert word[own] in _cli([], dict(env, LANG=locale[lang]), cmd=cmd).stdout
    # ...a meno che non si imposti TOKYN_LANG
    assert word[other] in _cli([], dict(env, TOKYN_LANG=other, LANG=locale[own]), cmd=cmd).stdout
    # anche il messaggio del lanciatore quando mancano sia lark sia la sua copia nella Skill
    import shutil
    skill = tmp_path / "skill"
    shutil.copytree(launcher.parent, skill, ignore=shutil.ignore_patterns("vendor", "__pycache__"))
    r = _cli([], {"PYTHONPATH": "", "LANG": locale[other]}, cmd=[sys.executable, "-I", "-S", str(skill / "tokyn_cli.py"), "check", str(f)])
    assert r.returncode == 1 and {"it": "manca la libreria lark", "en": "the lark library is missing"}[own] in r.stderr


@pytest.mark.parametrize("plugin", ["tokyn", "tokyn-en"])
def test_plugin_launcher_works_without_lark_installed(tmp_path, plugin):
    """Senza lark installato il lanciatore usa la copia inclusa nella Skill: niente `pip install`."""
    skill = ROOT / "plugins" / plugin / "skills" / "tokyn"
    # -I -S: niente PYTHONPATH né site-packages, quindi Python vede solo la libreria standard
    hidden = subprocess.run([sys.executable, "-I", "-S", "-c", "import lark"], capture_output=True, text=True)
    if hidden.returncode == 0:
        pytest.skip("lark è nella libreria standard di questo Python: non si può nascondere")
    cmd = [sys.executable, "-I", "-S", str(skill / "tokyn_cli.py")]
    (tmp_path / "a.tokyn").write_text('import lark\n\nmain:\n    print(lark.__file__)\n    print("ciao " + input())\n',
                                      encoding="utf-8")
    r = subprocess.run(cmd + ["check", "a.tokyn"], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and "ok" in r.stdout, r.stdout + r.stderr
    r = subprocess.run(cmd + ["run", "a.tokyn", "--mock"], input="mondo\n", capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    used, greeting = r.stdout.strip().splitlines()
    assert Path(used).resolve().is_relative_to((skill / "vendor" / "lark").resolve()) and greeting == "ciao mondo"
    # la copia di lark ha la sua licenza, e nessun file del plugin supera i 256 KiB
    assert "Permission is hereby granted" in (skill / "vendor" / "lark" / "LICENSE").read_text(encoding="utf-8")
    big = [str(p) for p in (ROOT / "plugins" / plugin).rglob("*") if p.is_file() and p.stat().st_size >= 256 * 1024]
    assert not big, big


def test_build_skill_copies_the_english_spec():
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_skill", ROOT / "scripts" / "build_skill.py")
    build_skill = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_skill)
    for lang in ("it", "en"):
        assert {"tokyn/SPEC.md", "tokyn/SPEC.en.md", "tokyn/lingua.py"} <= set(build_skill.copies(lang))
    launcher = build_skill.content("en", build_skill.LAUNCHER).decode("utf-8")
    assert 'LINGUA = "en"' in launcher and 'LINGUA = "it"' not in launcher


def _italian_fragments():
    """Le parti fisse dei messaggi italiani: il primo argomento di ogni tr("italiano", "english") del compilatore."""
    import ast
    import re
    from tokyn.parser import TOKEN_LABELS, UNSUPPORTED
    texts = []
    for path in (ROOT / "tokyn").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "tr" and len(node.args) == 2:
                english = [n.value for n in ast.walk(node.args[1]) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                texts += [(n.value, english) for n in ast.walk(node.args[0]) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    texts += [(it, [en]) for it, en in list(UNSUPPORTED.values()) + [v for v in TOKEN_LABELS.values() if isinstance(v, tuple)]]
    fragments = set()
    for it, english in texts:
        for piece in re.split(r"[\n`\"']", it):
            piece = piece.strip()
            if len(piece) >= 6 and not any(piece in en for en in english):
                fragments.add(piece)
    return fragments


def test_english_messages(monkeypatch, capsys, tmp_path):
    """Un campione di ogni categoria (parser, checker, esecuzione, riga di comando): in inglese e senza italiano."""
    import io
    import re
    import tokyn.runtime as rt
    from tokyn.errors import diagnostics_json, format_diagnostics
    monkeypatch.setenv("TOKYN_LANG", "en")
    out = []

    def check(src):
        r = check_source(src, "t.tokyn")
        out.append(format_diagnostics(r.diagnostics, r.source, "t.tokyn"))
        return out[-1]

    # parser
    assert "`while` does not exist in Tokyn" in check("main:\n    while True:\n        pass\n")
    assert "missing ':' at the end of the line" in check("def f(x)\n    pass\n")
    assert "missing indented block" in check("main:\nprint(1)\n")
    assert "Missing ')' to close the open bracket" in check("main:\n    print(len([1, 2])\n")
    assert "comprehensions `[... for x in ...]` do not exist" in check("main:\n    ys = [x * 2 for x in [1, 2]]\n")
    assert "Expected here: ':', end of line." in check('agent A:\n    instructions "x"\n')
    # checker: il programma rotto di prima, più un avviso
    text = check(BROKEN)
    for expected in ['error E130: "instruction" is not a valid agent field', '→ Did you mean "instructions"?',
                     'error E131: the agent "Helper" has no instructions', 'the type "Order" has no field "prize"',
                     'the name "missing" is not defined', "cannot add a text to a number", "5 errors"]:
        assert expected in text
    assert "1 warning" in check('agent A:\n    instructions: "i"\n')
    r = check_source('agent A:\n    instructions: "i"\n')
    assert '"severity": "warning"' in diagnostics_json(r.diagnostics, "t.tokyn")
    # esecuzione
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    for src, expected in [("main:\n    x = [1]\n    print(x[3])\n", "t.tokyn:3 runtime error: index out of range"),
                          ('main:\n    print(read_file("missing.txt"))\n', 'the file "missing.txt" does not exist'),
                          ('main:\n    print(to_number("n/a"))\n', "If it may not be a number, give a fallback value: to_number(text, 0)"),
                          ("main:\n    x = input()\n", "input() got no line")]:
        assert run_source(src, "t.tokyn", mock=True) == 1
        err = capsys.readouterr().err
        assert expected in err, err
        out.append(err)
    fake = _FakeClient(_reply(_text("..."), stop="max_tokens"))
    ns = _agents('agent A:\n    instructions: "i"\n', monkeypatch, fake)
    with pytest.raises(rt.TokynRuntimeError) as info:
        ns["A"].ask("x")
    assert info.value.message == "agent A's answer was cut off because it was too long"
    out += [info.value.message, info.value.hint, rt.usage_report()]
    monkeypatch.setattr(rt, "_AVVISO_CLAUDE_CODE", [])
    monkeypatch.delenv("TOKYN_BACKEND")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(rt.shutil, "which", lambda name: "/usr/bin/claude")
    assert rt._backend() == "claude-code"
    notice = capsys.readouterr().err
    assert "without an API key the agents answer through your Claude Code" in notice
    out.append(notice)
    # riga di comando
    (tmp_path / "bad.tokyn").write_text(BROKEN, encoding="utf-8")
    (tmp_path / "ok.tokyn").write_text('main:\n    print("hi")\n', encoding="utf-8")
    env = {"TOKYN_LANG": "en", "PYTHONPATH": str(ROOT)}
    for args, expected in [(["check", "nope.tokyn"], 'error: the file "nope.tokyn" does not exist'),
                           (["build", "ok.tokyn"], "wrote ok.py"),
                           (["build", "bad.tokyn"], "5 errors"),
                           (["new", "hello"], "created hello.tokyn. Try it with: tokyn run hello.tokyn --mock"),
                           (["new", "hello"], 'error: "hello.tokyn" already exists'),
                           (["run", "ok.tokyn", "--mock", "--usage"], "tokens: 0 input"),
                           (["--help"], "Tokyn: the language for AI agents."),
                           (["run", "--help"], "fake answers, without calling the AI")]:
        r = _cli(args, env, cwd=tmp_path)
        assert expected in r.stdout + r.stderr, (args, r.stdout, r.stderr)
        out.append(r.stdout + r.stderr)
    assert 'instructions: "Answer in English' in (tmp_path / "hello.tokyn").read_text(encoding="utf-8")
    spec = _cli(["spec"], env).stdout
    assert spec.startswith("# Tokyn v0.1 — Specification")
    assert _cli(["spec"], {"TOKYN_LANG": "it"}).stdout.startswith("# Tokyn v0.1 — Specifica")

    italian = _italian_fragments()
    assert len(italian) > 200
    for text in out:
        found = [f for f in italian if f in text]
        words = re.findall(r"\b(errore|errori|avviso|esecuzione|manca|riga|esiste|oppure|intendevi|valore|chiave)\b", text)
        assert not found and not words, (found, words, text)


def test_standalone_program_speaks_the_language(tmp_path):
    src = 'main:\n    print(read_file("missing.txt"))\n'
    py = tmp_path / "prog.py"
    py.write_text(compile_source(src, "prog.tokyn", standalone=True).python, encoding="utf-8")
    for lang, expected in [("en", 'the file "missing.txt" does not exist'), ("it", 'il file "missing.txt" non esiste')]:
        r = _cli([], {"TOKYN_LANG": lang, "PYTHONPATH": ""}, cwd=tmp_path, cmd=[sys.executable, "-S", str(py)])
        assert r.returncode == 1 and expected in r.stderr, r.stderr


def test_english_mock_answers_generated_header_and_argument_counts(monkeypatch, capsys):
    """In inglese anche le risposte finte, l'intestazione del Python generato e il conteggio degli argomenti."""
    src = ('type Card:\n    name: str\n    n: int\n\nagent A:\n    instructions: "i"\n    output: Card\n\n'
           'agent B:\n    instructions: "i"\n\nmain:\n    print(A.ask("hi"))\n    print(B.ask("hi"))\n')
    for lang, expected in [("en", "Card(name='example name', n=1)\n[mock B] answer to: hi\n"),
                           ("it", "Card(name='esempio name', n=1)\n[mock B] risposta a: hi\n")]:
        monkeypatch.setenv("TOKYN_LANG", lang)
        rc, out, err = run(src, capsys)
        assert rc == 0 and out == expected, (out, err)
        header = compile_source(src, "p.tokyn", standalone=True).python.splitlines()[:3]
        assert header[0].startswith({"en": "# Generated by Tokyn", "it": "# Generato da Tokyn"}[lang]), header
        assert {"en": "Standalone file", "it": "File autonomo"}[lang] in header[2]
    monkeypatch.setenv("TOKYN_LANG", "en")
    calls = ('def f(a: int, b: int) -> int:\n    return a\n\n'
             'main:\n    print(len())\n    print(min())\n    print(read_file())\n    print(range())\n    print(f())\n')
    messages = [d.message for d in check_source(calls, "t.tokyn").diagnostics]
    assert messages == ["len() takes 1 argument, got 0", "min() takes at least 1 argument, got 0",
                        "read_file() takes 1 or 2 arguments, got 0", "range() takes 1 to 3 arguments, got 0",
                        "f() is missing the required parameters: a, b"], messages
