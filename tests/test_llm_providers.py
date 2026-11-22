import json
from types import SimpleNamespace

import pytest

from kio_extract.contracts import ConfigurationError, DocumentError
from kio_extract.providers import anthropic


def test_anthropic_sends_one_request_and_parses_json(monkeypatch):
    calls = []

    class Connection:
        def __init__(self, host, port, timeout):
            assert host == "example.com" and timeout == 90.0

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
