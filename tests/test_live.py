"""Prove con l'API vera di Anthropic: partono solo se c'è ANTHROPIC_API_KEY (costano pochi centesimi).

Uso:  ANTHROPIC_API_KEY=... pytest tests/test_live.py -v
      TOKYN_LIVE_BATCH=1 ...   anche la prova della Batch API, che può richiedere qualche minuto
"""

import os

import pytest

from tokyn.compiler import compile_source

pytestmark = pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="serve ANTHROPIC_API_KEY")


def agents(src):
    import tokyn.runtime as rt
    rt._CLIENT = None
    os.environ.pop("TOKYN_MOCK", None)
    ns = {"__name__": "live"}
    exec(compile_source(src, "live.tokyn").python, ns)
    return ns, rt


def test_plain_answer():
    ns, _ = agents('agent A:\n    model: "claude-haiku"\n    instructions: "Rispondi con una sola parola."\n')
    answer = ns["A"].ask("Di che colore è il cielo sereno?")
    assert isinstance(answer, str) and answer.strip()


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


def test_prompt_caching_between_calls():
    regole = "\n".join(f"- Regola {i}: rispondi in modo breve e preciso, senza saluti." for i in range(80))
    src = f'REGOLE = """{regole}"""\n\nagent A:\n    model: "claude-haiku"\n    instructions: REGOLE\n'
    ns, rt = agents(src)
    ns["A"].ask("Quanto fa 2 + 2?")
    before = rt._USAGE["cache_lette"]
    ns["A"].ask("Quanto fa 3 + 3?")
    assert rt._USAGE["cache_lette"] > before, rt.usage_report()


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
