from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol


type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type Normalizer = Literal["text", "digits", "iso_date", "amount"]


@dataclass(frozen=True, slots=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    source_path: Path
    pages: tuple[PageText, ...]
    used_ocr: bool = False
    pages_needing_ocr: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Evidence:
    field_path: str
    page_number: int
    method: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    data: JsonObject
    evidence: tuple[Evidence, ...] = ()


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    doc_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class FieldRule:
    pattern: str
    normalize: Normalizer = "text"


@dataclass(frozen=True, slots=True)
class DocumentConfig:
    doc_type: str
    schema: JsonObject
    positive_patterns: tuple[str, ...] = ()
    negative_patterns: tuple[str, ...] = ()
    minimum_matches: int = 1
    fields: Mapping[str, FieldRule] = field(default_factory=dict)
    options: Mapping[str, JsonValue] = field(default_factory=dict)
    extractor: str | None = None


class LLMClient(Protocol):
    def extract_json(self, *, instructions: str, text: str, schema: JsonObject) -> JsonObject: ...


class Extractor(Protocol):
    def __call__(
        self, document: ExtractedDocument, config: DocumentConfig, llm: LLMClient | None = None
    ) -> ExtractionResult: ...


class OCR(Protocol):
    def __call__(self, source_path: Path, page_number: int) -> str | None: ...


class DocumentError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class ConfigurationError(Exception):
    """Invalid application or document configuration."""
