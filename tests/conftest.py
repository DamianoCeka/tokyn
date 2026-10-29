import pytest


@pytest.fixture(autouse=True)
def _api_backend_in_tests(request, monkeypatch):
    """I test usano client finti dell'API: non devono mai passare da Claude Code anche se `claude` è installato."""
    if request.module.__name__.endswith("test_live"):
        return
    monkeypatch.setenv("TOKYN_BACKEND", "api")
