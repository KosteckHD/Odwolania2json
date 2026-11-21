import json
import os
import re
from http.client import HTTPSConnection
from urllib.parse import urlsplit

from ..contracts import ConfigurationError, DocumentError
from .rate_limit import RateLimitSettings, coordinator


def parse_embedded_json(value):
    """Allow escaped whitespace between JSON tokens, never inside strings."""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        if not isinstance(value, str):
            raise
    output = []
    inside_string = False
    escaped = False
    index = 0
    while index < len(value):
        character = value[index]
        if inside_string:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                inside_string = False
        elif character == '"':
            inside_string = True
            output.append(character)
        elif character == "\\" and index + 1 < len(value) and value[index + 1] in "nrt":
            output.append(" ")
            index += 1
        else:
            output.append(character)
        index += 1
    return json.loads("".join(output))


def structured_transport_schema(schema):
    """Restrict the transport grammar; full constraints are checked locally."""
    nullable_unions = 0

    def simplify(node, preserve_nullable=False):
        nonlocal nullable_unions
        if isinstance(node, list):
            return [simplify(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = {}
        for key in ("type", "properties", "items", "required", "additionalProperties", "enum", "anyOf", "format"):
            if key not in node:
                continue
            result[key] = ({name: simplify(value, preserve_nullable=(name == "pesel")) for name, value in node[key].items()}
                           if key == "properties" else simplify(node[key]))
        has_nullable_type = isinstance(result.get("type"), list) and "null" in result["type"]
        if has_nullable_type and len(result["type"]) == 2 and (nullable_unions < 11 or preserve_nullable):
            nullable_unions += 1
        elif has_nullable_type and len(result["type"]) == 2:
            result["type"] = next(item for item in result["type"] if item != "null")
        if "enum" in result and None in result["enum"] and not (
                isinstance(result.get("type"), list) and "null" in result["type"]):
            result["enum"] = [item for item in result["enum"] if item is not None]
        if "properties" in result and "required" in result:
            def nullable(value):
                return (isinstance(value.get("type"), list) and "null" in value["type"] or
                        None in value.get("enum", []))
            result["required"] = [key for key in result["required"]
                                  if not (nullable(node["properties"].get(key, {})) and
                                          not nullable(result["properties"].get(key, {})))]
        return result

    return {"type": "object", "additionalProperties": False, "required": ["typ", "dane"],
            "properties": {"typ": simplify(schema["properties"]["typ"]),
                           "dane": simplify(schema["properties"]["dane"])}}


def restore_nullable_fields(value, schema):
    if isinstance(value, list):
        return [restore_nullable_fields(item, schema.get("items", {})) for item in value]
    if not isinstance(value, dict):
        return value
    props = schema.get("properties", {})
    result = {key: restore_nullable_fields(item, props.get(key, {})) for key, item in value.items()}
    for key in schema.get("required", []):
        definition = props.get(key, {})
        if key not in result and ((isinstance(definition.get("type"), list) and "null" in definition["type"])
                                  or None in definition.get("enum", [])):
            result[key] = None
    return result


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
        direct_object = os.getenv("LLM_ANTHROPIC_STRUCTURED_OBJECT", "0") == "1"
        transport = structured_transport_schema(schema) if direct_object else {
            "type": "object",
            "properties": {"typ": schema["properties"]["typ"], "dane": {"type": ["string", "null"]}},
            "required": ["typ", "dane"],
            "additionalProperties": False,
        }
        encoding_instruction = "" if direct_object else (
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
        except (KeyError, TypeError, ValueError) as exc:
            raise DocumentError("llm_json", "Nieprawidłowa zewnętrzna koperta odpowiedzi LLM") from exc
        try:
            if result["dane"] is not None and not direct_object:
                result["dane"] = parse_embedded_json(result["dane"])
            elif result["dane"] is not None and direct_object:
                kinds = schema["properties"]["typ"]["enum"]
                schemas = schema["properties"]["dane"]["anyOf"]
                result["dane"] = restore_nullable_fields(result["dane"], schemas[kinds.index(result["typ"])])
        except (KeyError, TypeError, ValueError) as exc:
            raise DocumentError("llm_json", "Nieprawidłowe pole dane w kopercie odpowiedzi LLM") from exc
        return result
