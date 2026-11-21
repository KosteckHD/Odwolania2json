import json
import os
import re
from http.client import HTTPSConnection
from urllib.parse import urlsplit

from ..contracts import ConfigurationError, DocumentError
from .rate_limit import RateLimitSettings, coordinator


class AnthropicClient:
    def __init__(self, base_url, model, api_key):
        url = urlsplit(base_url)
        if url.scheme != "https" or not url.hostname or url.username or url.query or url.fragment:
            raise ConfigurationError("Nieprawidłowy adres Claude API")
        if not re.fullmatch(r"claude-(?:sonnet|haiku)-[a-z0-9.-]+", model) or not api_key:
            raise ConfigurationError("Skonfiguruj model Sonnet lub Haiku oraz klucz API")
        self.host, self.port = url.hostname, url.port
        self.path = url.path.rstrip("/") + "/messages"
        self.model, self.key = model, api_key
        self.rate_limit = RateLimitSettings.from_environment()
        self.last_usage = None

    @classmethod
    def from_environment(cls):
        return cls(os.getenv("LLM_BASE_URL", "").strip(), os.getenv("LLM_MODEL", "").strip(),
                   (os.getenv("LLM_API_KEY") or os.getenv("API_KEY", "")).strip())

    def extract_json(self, *, instructions, text, schema):
        self.last_usage = None
        transport = {
            "type": "object",
            "properties": {"typ": schema["properties"]["typ"], "dane": {"type": ["string", "null"]}},
            "required": ["typ", "dane"],
            "additionalProperties": False,
        }
        encoding_instruction = (
            "\nFormat transportowy odpowiedzi: dla rozpoznanej klasy pole dane jest napisem zawierającym "
            "kompletny obiekt JSON zgodny ze schematem. Dla klasy unknown pole dane to wartość JSON null. "
            "Po odkodowaniu dane muszą odpowiadać schematowi."
        )
        body = json.dumps({"model": self.model, "max_tokens": 4096,
                           "system": instructions + "\n" + json.dumps(schema, ensure_ascii=False) + encoding_instruction,
                           "messages": [{"role": "user", "content": text}],
                           "output_config": {"format": {"type": "json_schema", "schema": transport}}},
                          ensure_ascii=False).encode("utf-8")
        try:
            payload = json.loads(coordinator.post(HTTPSConnection, self.host, self.port, self.path, body,
                                 {"content-type": "application/json", "x-api-key": self.key,
                                  "anthropic-version": "2023-06-01"}, self.rate_limit))
        except ValueError as exc:
            raise DocumentError("llm_json", "Nieprawidłowa odpowiedź API LLM") from exc
        usage = payload.get("usage") if isinstance(payload, dict) else None
        if isinstance(usage, dict):
            self.last_usage = {key: usage[key] for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
                               if isinstance(usage.get(key), int)}
        try:
            if payload["stop_reason"] != "end_turn":
                raise DocumentError("llm_incomplete", "API LLM nie ukończyło odpowiedzi")
            content = "".join(block["text"] for block in payload["content"] if block["type"] == "text")
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("expected object")
            if result["dane"] is not None:
                result["dane"] = json.loads(result["dane"])
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise DocumentError("llm_json", "API LLM zwróciło nieprawidłowy JSON") from exc
