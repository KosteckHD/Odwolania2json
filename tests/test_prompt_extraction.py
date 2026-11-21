import json
from pathlib import Path

import pytest

from kio_extract.contracts import DocumentError, ExtractedDocument, PageText
from kio_extract.processing import DocumentProcessor
from kio_extract.providers.chat import ChatClient
from kio_extract.providers.rate_limit import coordinator
from kio_extract.schema_registry import load_configs


ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = {"typ": "unknown", "dane": None}


class ScriptedClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.last_usage = None
        self.instructions = []

    def extract_json(self, *, instructions, text, schema):
        self.instructions.append(instructions)
        response = next(self.responses)
        self.last_usage = {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
        if isinstance(response, Exception):
            raise response
        return response


def extractor(client):
    configs = load_configs(ROOT / "configs/documents", ROOT / "schemas")
    return DocumentProcessor(configs, ROOT / "prompts/system_pl.md", client=client).prompted


def document():
    return ExtractedDocument(Path("synthetic.pdf"), (PageText(1, "Synthetic content"),))


def test_retries_once_after_output_fails_schema_validation(tmp_path):
    client = ScriptedClient([{"typ": "not-a-document-class", "dane": None}, UNKNOWN])

    classification, data = extractor(client).extract(document())

    assert classification.doc_type == "unknown"
    assert data is None
    assert len(client.instructions) == 2
    assert "nie spełniła schematu" in client.instructions[1]
    assert client.last_usage == {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}


def test_retries_once_after_invalid_json_response():
    client = ScriptedClient([DocumentError("llm_json", "invalid output"), UNKNOWN])

    classification, _ = extractor(client).extract(document())

    assert classification.doc_type == "unknown"
    assert len(client.instructions) == 2
    assert "nieprawidłowym JSON-em" in client.instructions[1]
    assert client.last_usage == {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}


def test_does_not_retry_provider_errors():
    client = ScriptedClient([DocumentError("llm_rate_limit", "rate limited"), UNKNOWN])

    with pytest.raises(DocumentError, match="rate limited"):
        extractor(client).extract(document())

    assert len(client.instructions) == 1


def test_invalid_second_response_stops_after_one_retry():
    client = ScriptedClient([
        {"typ": "not-a-document-class", "dane": None},
        {"typ": "also-not-a-document-class", "dane": None},
        UNKNOWN,
    ])

    with pytest.raises(DocumentError) as error:
        extractor(client).extract(document())

    assert error.value.code == "invalid_output"
    assert len(client.instructions) == 2


@pytest.mark.parametrize("hostname", ["api.mistral.ai", "api.eu.mistral.ai", "api.us.mistral.ai"])
def test_mistral_provider_sends_strict_json_schema(monkeypatch, hostname):
    body = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(UNKNOWN)}}]}
    request = {}

    def respond(*args):
        request.update(json.loads(args[4]))
        return json.dumps(body).encode()

    monkeypatch.setattr(coordinator, "post", respond)
    client = ChatClient(f"https://{hostname}/v1", "ministral-8b-2512", "test-key")

    assert client.extract_json(instructions="JSON output", text="synthetic", schema=extractor(ScriptedClient([UNKNOWN])).response_schema) == UNKNOWN

    response_format = request["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    schema = response_format["json_schema"]["schema"]
    assert "if" not in schema and "then" not in schema
    assert "anyOf" in schema["properties"]["dane"]


def test_other_chat_providers_keep_json_object_mode(monkeypatch):
    body = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(UNKNOWN)}}]}
    request = {}
    monkeypatch.setattr(coordinator, "post", lambda *args: (request.update(json.loads(args[4])) or json.dumps(body).encode()))
    client = ChatClient("https://api.example.com/v1", "fixture", "test-key")

    assert client.extract_json(
        instructions="JSON output", text="synthetic", schema=extractor(ScriptedClient([UNKNOWN])).response_schema
    ) == UNKNOWN
    assert request["response_format"] == {"type": "json_object"}
