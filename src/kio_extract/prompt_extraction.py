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
            "properties": {
                "typ": {"enum": [*context, "unknown"]},
                "dane": {"anyOf": [*[config.schema for config in configs], {"type": "null"}]},
            },
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
        instructions = self.instructions
        first_usage = None
        for attempt in range(2):
            try:
                response = self.client.extract_json(
                    instructions=instructions, text=text, schema=self.response_schema
                )
            except DocumentError as exc:
                if attempt or exc.code not in ("llm_json", "llm_incomplete"):
                    raise
                first_usage = getattr(self.client, "last_usage", None)
                instructions = self._retry_instructions(
                    instructions, "odpowiedź była niekompletnym lub nieprawidłowym JSON-em"
                )
                continue
            if self.validator.is_valid(response):
                self._add_usage(first_usage)
                return ClassificationResult(response["typ"], "llm"), response["dane"]
            if attempt:
                raise DocumentError("invalid_output", "Odpowiedź LLM ma nieprawidłowy format klasy lub danych")
            first_usage = getattr(self.client, "last_usage", None)
            error = next(self.validator.iter_errors(response))
            location = ".".join(map(str, error.absolute_path)) or "odpowiedź"
            instructions = self._retry_instructions(
                instructions, f"odpowiedź nie spełniła schematu w polu {location}: {error.message}"
            )

        raise DocumentError("invalid_output", "Model dwukrotnie zwrócił nieprawidłową odpowiedź")

    @staticmethod
    def _retry_instructions(instructions: str, reason: str) -> str:
        return instructions + (
            "\n\n## Ponowienie po błędzie walidacji\n"
            "Poprzednia odpowiedź nie przeszła walidacji, ponieważ " + reason + ". "
            "Przeanalizuj ponownie podany tekst źródłowy. Zwróć kompletny obiekt JSON "
            "zgodny z dołączonym schematem. Nie zgaduj brakujących wartości."
        )

    def _add_usage(self, first_usage) -> None:
        if not first_usage:
            return
        current_usage = getattr(self.client, "last_usage", None) or {}
        combined = {
            name: first_usage.get(name, 0) + current_usage.get(name, 0)
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            if name in first_usage or name in current_usage
        }
        if combined:
            self.client.last_usage = combined
