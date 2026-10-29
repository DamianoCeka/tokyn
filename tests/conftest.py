import pytest


@pytest.fixture(autouse=True)
def _italian_messages(monkeypatch):
    """I test leggono i messaggi in italiano: la lingua non deve dipendere da quella del sistema che li esegue."""
    from tokyn import lingua
    monkeypatch.setenv("TOKYN_LANG", "it")
    monkeypatch.setitem(lingua._SCELTA, "opzione", None)
    monkeypatch.setitem(lingua._SCELTA, "plugin", None)


@pytest.fixture(autouse=True)
def _api_backend_in_tests(request, monkeypatch):
    """I test usano client finti dell'API: non devono mai passare da Claude Code anche se `claude` è installato."""
    if request.module.__name__.endswith("test_live"):
        return
    monkeypatch.setenv("TOKYN_BACKEND", "api")
