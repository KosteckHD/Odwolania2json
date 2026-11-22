import json
import os
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


def _dump_raw(document: ExtractedDocument, response: object) -> None:
    """Diagnostyka: surowa odpowiedź modelu (przed regułami `postprocess:`) do katalogu z LLM_RAW_DUMP_DIR.
    Służy do pomiaru stabilności modelu między przebiegami; domyślnie wyłączona."""
    target = os.getenv("LLM_RAW_DUMP_DIR", "").strip()
    if not target:
        return
    source = document.source_path
    name = f"{source.parent.name}__{source.stem}.json"
    path = Path(target) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")


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
            "properties": {
                "typ": {"enum": [*context, "unknown"]},
                "dane": {"anyOf": [*[config.schema for config in configs], {"type": "null"}]},
            },
            "if": {"properties": {"typ": {"const": "unknown"}}},
            "then": {"properties": {"dane": {"type": "null"}}},
            "else": {"properties": {"dane": {"type": "object"}}},
        }
        self.validator = Draft202012Validator(self.response_schema)

    def extract(self, document: ExtractedDocument, images=()) -> tuple[ClassificationResult, JsonObject | None]:
        text = json.dumps(
            {"strony": [{"numer": page.page_number, "tekst": page.text} for page in document.pages]},
            ensure_ascii=False,
        )
        extra = {"images": tuple(images)} if images else {}   # skany przy SCAN_MODE=image
        response = self.client.extract_json(instructions=self.instructions, text=text, schema=self.response_schema,
                                            **extra)
        _dump_raw(document, response)
        if not self.validator.is_valid(response):
            raise DocumentError("invalid_output", "Odpowiedź LLM ma nieprawidłowy format klasy lub danych")
        return ClassificationResult(response["typ"], "llm"), response["dane"]
