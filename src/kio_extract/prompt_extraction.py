import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .contracts import (
    ClassificationResult,
    DocumentConfig,
    DocumentError,
    ExtractedDocument,
    JsonObject,
    LLMClient,
)


class PromptExtractor:
    def __init__(self, client: LLMClient, configs: tuple[DocumentConfig, ...], prompt_path: Path):
        self.client = client
        context = {
            config.doc_type: {"schema": config.schema, "options": dict(config.options)}
            for config in configs
        }
        prompt = prompt_path.read_text(encoding="utf-8")
        self.instructions = prompt + "\n\n## Schematy danych i opcje klas\n" + json.dumps(context, ensure_ascii=False)
        self.response_schema: JsonObject = {
            "type": "object",
            "required": ["typ", "dane"],
            "additionalProperties": False,
            "properties": {"typ": {"enum": [*context, "unknown"]}, "dane": {}},
            "if": {"properties": {"typ": {"const": "unknown"}}},
            "then": {"properties": {"dane": {"type": "null"}}},
            "else": {"properties": {"dane": {"type": "object"}}},
        }
        self.validator = Draft202012Validator(self.response_schema)

    def extract(self, document: ExtractedDocument) -> tuple[ClassificationResult, JsonObject | None]:
        text = json.dumps(
            {"strony": [{"numer": page.page_number, "tekst": page.text} for page in document.pages]},
            ensure_ascii=False,
        )
        response = self.client.extract_json(instructions=self.instructions, text=text, schema=self.response_schema)
        if not self.validator.is_valid(response):
            raise DocumentError("invalid_output", "Odpowiedź LLM ma nieprawidłowy format klasy lub danych")
        return ClassificationResult(response["typ"], "llm"), response["dane"]
