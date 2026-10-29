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


def test_skill_reference_is_valid(capsys, monkeypatch):
    import io
    skill = (ROOT / "skill" / "tokyn" / "SKILL.md").read_text(encoding="utf-8")
    start = skill.index("```\nimport math") + 4
    src = skill[start:skill.index("```", start)]
    monkeypatch.setattr(sys, "stdin", io.StringIO("il pc non parte\n"))
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
'''
    rc, out, err = run(src, capsys)
    assert rc == 0, err
    assert out.strip() == "tecnico True 1"


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
    ('main:\n    s = "abc"\n    print(s["a":])\n', "E176"),
    # costrutti Python che Tokyn non ha: errore mirato con l'alternativa
    ("main:\n    ys = [x * 2 for x in [1, 2]]\n", "E002"),
    ('main:\n    x = 1\n    y = "a" if x > 0 else "b"\n', "E002"),
    ("main:\n    x = None\n    if x is None:\n        pass\n", "E002"),
    ("main:\n    a, b = [1, 2]\n", "E002"),
    ("def f():\n    return 1, 2\n", "E002"),
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


def test_missing_api_key(capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("TOKYN_MOCK", raising=False)
    import tokyn.runtime as rt
    monkeypatch.setattr(rt, "_CLIENT", None)
    src = 'agent A:\n    instructions: "i"\nmain:\n    print(A.ask("x"))\n'
    rc = run_source(src, "test.tokyn", mock=False)
    err = capsys.readouterr().err
    assert rc == 1 and "ANTHROPIC_API_KEY" in err and "--mock" in err


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


class _FakeClient:
    """Simula l'API: prima chiama uno strumento, poi sbaglia il formato, poi risponde bene."""

    def __init__(self):
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(dict(kwargs, messages=list(kwargs["messages"])))
        n = len(self.calls)
        if n == 1:
            return _Block(content=[_Block(type="tool_use", id="t1", name="meteo", input={"citta": "Padova"})])
        if n == 2:
            return _Block(content=[_Block(type="tool_use", id="t2", name="rispondi", input={"citta": "Padova", "gradi": "tanti"})])
        return _Block(content=[_Block(type="tool_use", id="t3", name="rispondi", input={"citta": "Padova", "gradi": 18})])


def test_agent_loop_with_fake_api(monkeypatch):
    import tokyn.runtime as rt
    src = '''
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
    ns = {"__name__": "x"}
    exec(compile_source(src).python, ns)
    fake = _FakeClient()
    monkeypatch.setattr(rt, "_CLIENT", fake)
    monkeypatch.delenv("TOKYN_MOCK", raising=False)
    result = ns["A"].ask("Che tempo fa a Padova?")
    assert (result.citta, result.gradi) == ("Padova", 18)
    # lo strumento è stato eseguito e il risultato è tornato all'IA
    second = fake.calls[1]["messages"][-1]["content"][0]
    assert second["content"] == "Padova: 18 gradi"
    # l'output non valido è stato rimandato all'IA come errore
    third = fake.calls[2]["messages"][-1]["content"][0]
    assert third["is_error"] and "gradi" in third["content"]
    assert fake.calls[0]["model"] == "claude-sonnet-5-5"
    assert [t["name"] for t in fake.calls[0]["tools"]] == ["meteo", "rispondi"]


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
