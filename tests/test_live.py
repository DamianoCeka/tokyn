"""Prove con modelli veri: costano pochi centesimi e partono solo se richieste.

Uso:  ANTHROPIC_API_KEY=... pytest tests/test_live.py -v      prove con l'API di Anthropic
      TOKYN_LIVE_BATCH=1 ...                                  anche la Batch API (può richiedere minuti)
      TOKYN_LIVE_CLAUDE=1 pytest tests/test_live.py -v        prova con Claude Code (`claude` con login fatto)
"""

import os
import shutil

import pytest

from tokyn.compiler import compile_source

needs_api = pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="serve ANTHROPIC_API_KEY")


def agents(src, backend="api"):
    import tokyn.runtime as rt
    rt._CLIENT = None
    os.environ.pop("TOKYN_MOCK", None)
    os.environ["TOKYN_BACKEND"] = backend
    ns = {"__name__": "live"}
    exec(compile_source(src, "live.tokyn").python, ns)
    return ns, rt


@needs_api
def test_plain_answer():
    ns, _ = agents('agent A:\n    model: "claude-haiku"\n    instructions: "Rispondi con una sola parola."\n')
    answer = ns["A"].ask("Di che colore è il cielo sereno?")
    assert isinstance(answer, str) and answer.strip()


@needs_api
def test_structured_output_with_strict_tool_on_default_model():
    src = '''
type Meteo:
    citta: str
    gradi: int "temperatura in gradi"
    cielo: "sereno" | "nuvoloso" | "pioggia"

def meteo(citta: str) -> str:
    """Restituisce il meteo attuale di una città."""
    return f"{citta}: 18 gradi, nuvoloso"

agent A:
    instructions: "Usa lo strumento meteo e riporta il risultato."
    tools: [meteo]
    output: Meteo
'''
    ns, rt = agents(src)
    result = ns["A"].ask("Che tempo fa a Padova?")
    assert (result.citta, result.gradi, result.cielo) == ("Padova", 18, "nuvoloso")
    # i fallback lato server sono stati accettati dall'API (altrimenti il runtime li avrebbe disattivati)
    assert rt._FALLBACKS["attivi"]


@needs_api
def test_prompt_caching_between_calls():
    regole = "\n".join(f"- Regola {i}: rispondi in modo breve e preciso, senza saluti." for i in range(80))
    src = f'REGOLE = """{regole}"""\n\nagent A:\n    model: "claude-haiku"\n    instructions: REGOLE\n'
    ns, rt = agents(src)
    ns["A"].ask("Quanto fa 2 + 2?")
    before = rt._USAGE["cache_lette"]
    ns["A"].ask("Quanto fa 3 + 3?")
    assert rt._USAGE["cache_lette"] > before, rt.usage_report()


@needs_api
def test_free_dict_output_and_effort():
    src = '''
type Estratto:
    nome: str
    extra: dict "altri dati trovati, chiave -> valore"

agent A:
    model: "claude-haiku"
    instructions: "Estrai i dati dal testo."
    effort: "low"
    output: Estratto
'''
    ns, _ = agents(src)
    result = ns["A"].ask("Mario Rossi, 42 anni, abita a Torino.")
    assert "Mario" in result.nome and isinstance(result.extra, dict)


@needs_api
@pytest.mark.skipif(not os.environ.get("TOKYN_LIVE_BATCH"), reason="Batch API: imposta TOKYN_LIVE_BATCH=1")
def test_ask_all_with_batch_api():
    src = '''
type Sentimento:
    valore: "positivo" | "negativo"

agent A:
    model: "claude-haiku"
    instructions: "Classifica il sentimento della recensione."
    effort: "low"
    output: Sentimento
'''
    ns, _ = agents(src)
    results = ns["A"].ask_all(["Fantastico, lo ricomprerei!", "Si è rotto dopo un giorno."])
    assert [r.valore for r in results] == ["positivo", "negativo"]


@pytest.mark.skipif(not (os.environ.get("TOKYN_LIVE_CLAUDE") and shutil.which("claude")),
                    reason="Claude Code: imposta TOKYN_LIVE_CLAUDE=1 (serve `claude` con login fatto)")
def test_claude_code_backend():
    src = '''
CHIAMATE = []

type Meteo:
    citta: str
    gradi: int
    cielo: "sereno" | "nuvoloso" | "pioggia"

def meteo(citta: str) -> str:
    """Restituisce il meteo attuale di una città."""
    CHIAMATE.append(citta)
    return f"{citta}: 18 gradi, nuvoloso"

agent A:
    model: "claude-haiku"
    instructions: "Usa sempre lo strumento meteo per rispondere."
    tools: [meteo]
    output: Meteo

agent Breve:
    model: "claude-haiku"
    instructions: "Rispondi con una sola parola."
    memory: True
'''
    ns, _ = agents(src, backend="claude-code")
    m = ns["A"].ask("Che tempo fa a Padova?")
    assert (m.citta, m.gradi, m.cielo) == ("Padova", 18, "nuvoloso") and ns["CHIAMATE"] == ["Padova"]
    ns["Breve"].ask("Il mio colore preferito è il verde. Rispondi: ok")
    assert "verde" in ns["Breve"].ask("Qual è il mio colore preferito?").lower()
