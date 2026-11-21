import os

from ..contracts import ConfigurationError
from .anthropic import AnthropicClient
from .chat import ChatClient


def client_from_environment():
    provider = os.getenv("LLM_PROVIDER", "chat").strip().lower()
    if provider == "anthropic":
        return AnthropicClient.from_environment()
    if provider == "chat":
        model = os.getenv("LLM_MODEL", "").strip().lower()
        if model.startswith("claude-") and not (model.startswith("claude-sonnet-") or model.startswith("claude-haiku-")):
            raise ConfigurationError("Dozwolone są modele Claude Sonnet i Haiku")
        return ChatClient.from_environment()
    raise ConfigurationError("Nieznany LLM_PROVIDER")
