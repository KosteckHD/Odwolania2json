import json
from types import SimpleNamespace

import pytest

from kio_extract.contracts import ConfigurationError, DocumentError
from kio_extract.providers import anthropic


def test_anthropic_sends_one_request_and_parses_json(monkeypatch):
    calls = []

    class Connection:
        def __init__(self, host, port, timeout):
            assert host == "example.com" and timeout == 60

        def request(self, method, path, *, body, headers):
            calls.append((method, path, json.loads(body), headers))

        def getresponse(self):
            payload = {"stop_reason": "end_turn", "content": [{"type": "text", "text": '{"typ":"unknown","dane":"null"}'}]}
            return SimpleNamespace(status=200, read=lambda: json.dumps(payload).encode())

        def close(self):
            pass

    monkeypatch.setattr(anthropic, "HTTPSConnection", Connection)
    client = anthropic.AnthropicClient("https://example.com/v1", "claude-sonnet-test", "test-key")
    schema = {"type": "object", "properties": {"typ": {"enum": ["unknown"]}, "value": {"type": "integer", "minimum": 1}},
              "additionalProperties": False, "if": {"type": "object"}}
    assert client.extract_json(instructions="system", text="pages", schema=schema) == {"typ": "unknown", "dane": None}
    assert len(calls) == 1
    assert calls[0][1] == "/v1/messages"
    assert calls[0][2]["messages"][0]["content"] == "pages"
    transported = calls[0][2]["output_config"]["format"]["schema"]
    assert transported["properties"]["dane"] == {"type": ["string", "null"]}
    assert calls[0][3]["x-api-key"] == "test-key"


def test_anthropic_rejects_opus_before_network():
    with pytest.raises(ConfigurationError):
        anthropic.AnthropicClient("https://example.com/v1", "claude-opus-test", "test-key")


def test_embedded_json_repairs_only_escaped_whitespace_between_tokens():
    assert anthropic.parse_embedded_json(r'{"a":1,\n"b":"literal\\nvalue"}') == {"a": 1, "b": r"literal\nvalue"}
    assert anthropic.parse_embedded_json(r'{"a":[1,\t2]}') == {"a": [1, 2]}
    with pytest.raises(json.JSONDecodeError):
        anthropic.parse_embedded_json(r'{"a":\q1}')
    with pytest.raises(json.JSONDecodeError):
        anthropic.parse_embedded_json(r'{"a":1,\n')


def test_structured_transport_restores_omitted_nullable_fields():
    schema = {"type": "object", "required": ["a", "b", "list"], "properties": {
        "a": {"type": ["string", "null"]}, "b": {"enum": ["x", None]},
        "list": {"type": "array", "items": {"type": "object", "required": ["c"],
                                              "properties": {"c": {"type": ["integer", "null"]}}}}
    }}
    value = {"a": "ok", "list": [{}]}
    assert anthropic.restore_nullable_fields(value, schema) == {"a": "ok", "b": None, "list": [{"c": None}]}
    assert anthropic.restore_nullable_fields({}, {"required": ["name"], "properties": {"name": {"type": "string"}}}) == {}


def test_structured_transport_drops_unsupported_bounds_but_keeps_names():
    data = {"type": "object", "properties": {"type": {"type": ["integer", "null"], "minimum": 0}},
            "required": ["type"], "additionalProperties": False}
    schema = {"properties": {"typ": {"enum": ["a", "unknown"]},
                              "dane": {"anyOf": [data, {"type": "null"}]}}}
    transport = anthropic.structured_transport_schema(schema)
    field = transport["properties"]["dane"]["anyOf"][0]["properties"]["type"]
    assert field == {"type": ["integer", "null"]}


def test_structured_transport_handles_direct_object_and_nulls(monkeypatch):
    monkeypatch.setenv("LLM_ANTHROPIC_STRUCTURED_OBJECT", "1")
    sent = []
    def post(*args):
        sent.append(json.loads(args[4]))
        result = {"typ": "example", "dane": {"number": 42}}
        return json.dumps({"stop_reason": "end_turn", "content": [
            {"type": "text", "text": json.dumps(result)}]}).encode()
    monkeypatch.setattr(anthropic.coordinator, "post", post)
    data_schema = {"type": "object", "required": ["number", "missing"], "additionalProperties": False,
                   "properties": {"number": {"type": "integer"}, "missing": {"enum": ["yes", None]}}}
    schema = {"properties": {"typ": {"enum": ["example", "unknown"]},
                              "dane": {"anyOf": [data_schema, {"type": "null"}]}}}
    client = anthropic.AnthropicClient("https://example.com/v1", "claude-haiku-test", "test-key")
    assert client.extract_json(instructions="test", text="synthetic", schema=schema) == {
        "typ": "example", "dane": {"number": 42, "missing": None}}
    assert "anyOf" in sent[0]["output_config"]["format"]["schema"]["properties"]["dane"]
