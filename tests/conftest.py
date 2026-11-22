import pytest


@pytest.fixture(autouse=True)
def no_llm_settings_from_host(monkeypatch):
    """CLI włącza model sam, gdy widzi zmienne LLM, więc testy startują bez nich."""
    for name in ("LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "API_KEY", "LLM_PROVIDER", "LLM_EXTRA_BODY"):
        monkeypatch.delenv(name, raising=False)
