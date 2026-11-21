import json
import os
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlsplit

from ..contracts import ConfigurationError, DocumentError, JsonObject
from .rate_limit import RateLimitSettings, coordinator


def structured_json_schema(schema: JsonObject) -> JsonObject:
    """Trim prompt-only annotations and conditionals for Mistral's strict JSON mode."""
    supported = {
        "type", "properties", "items", "enum", "const", "anyOf", "oneOf", "required",
        "additionalProperties", "format", "description", "title", "minimum", "maximum",
        "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength", "pattern",
        "minItems", "maxItems",
    }
    result = {}
    for key, value in schema.items():
        if key not in supported:
            continue
        if key == "properties" and isinstance(value, dict):
            result[key] = {name: structured_json_schema(child) for name, child in value.items()}
        elif key in {"items"} and isinstance(value, dict):
            result[key] = structured_json_schema(value)
        elif key in {"anyOf", "oneOf"} and isinstance(value, list):
            result[key] = [structured_json_schema(child) for child in value]
        else:
            result[key] = value
    if result.get("type") == "object" and isinstance(result.get("properties"), dict):
        result["required"] = list(result["properties"])
        result["additionalProperties"] = False
    return result


class ChatClient:
    def __init__(self, base_url: str, model: str, api_key: str):
        try:
            url = urlsplit(base_url)
            hostname, port = url.hostname, url.port
        except ValueError as exc:
            raise ConfigurationError("Nieprawidłowy adres LLM_BASE_URL") from exc
        loopback = hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not hostname or url.username is not None or url.query or url.fragment
            or (url.scheme != "https" and not (url.scheme == "http" and loopback))
        ):
            raise ConfigurationError("LLM_BASE_URL wymaga HTTPS lub lokalnego adresu pętli zwrotnej")
        if not model or (not api_key and not loopback):
            raise ConfigurationError("Ustaw LLM_MODEL i klucz LLM_API_KEY dla zdalnego API")
        self.hostname = hostname
        self.port = port
        self.connection = HTTPSConnection if url.scheme == "https" else HTTPConnection
        self.path = url.path.rstrip("/") + "/chat/completions"
        self.model = model
        self.uses_json_schema = hostname.casefold() in {
            "api.mistral.ai", "api.eu.mistral.ai", "api.us.mistral.ai",
        }
        self.rate_limit = RateLimitSettings.from_environment()
        self.last_usage = None
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    @classmethod
    def from_environment(cls) -> "ChatClient":
        return cls(
            os.getenv("LLM_BASE_URL", "").strip(),
            os.getenv("LLM_MODEL", "").strip(),
            (os.getenv("LLM_API_KEY") or os.getenv("API_KEY", "")).strip(),
        )

    def extract_json(self, *, instructions: str, text: str, schema: JsonObject) -> JsonObject:
        self.last_usage = None
        system = instructions + "\n\n## Schemat odpowiedzi\n" + json.dumps(schema, ensure_ascii=False)
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}],
                "response_format": (
                    {"type": "json_schema", "json_schema": {
                        "name": "odwolania2json", "schema": structured_json_schema(schema), "strict": True,
                    }} if self.uses_json_schema else {"type": "json_object"}
                ),
                "temperature": 0,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        payload = coordinator.post(self.connection, self.hostname, self.port, self.path, body, self.headers, self.rate_limit)

        try:
            response = json.loads(payload)
            if not isinstance(response, dict):
                raise TypeError("expected object")
            usage = response.get("usage")
            if isinstance(usage, dict):
                self.last_usage = {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                                   if isinstance(usage.get(key), int)}
            choice = response["choices"][0]
            if choice["finish_reason"] != "stop":
                raise DocumentError("llm_incomplete", "API LLM nie ukończyło odpowiedzi JSON")
            result = json.loads(choice["message"]["content"])
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise DocumentError("llm_json", "API LLM zwróciło nieprawidłowy JSON") from exc
        if not isinstance(result, dict):
            raise DocumentError("llm_json", "Odpowiedź LLM musi być obiektem JSON")
        return result
