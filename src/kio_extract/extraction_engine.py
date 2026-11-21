import re
from importlib import import_module

from .contracts import (
    ConfigurationError,
    DocumentConfig,
    Evidence,
    ExtractedDocument,
    ExtractionResult,
    Extractor,
    JsonObject,
    JsonValue,
    LLMClient,
)
from .normalization import NORMALIZERS


def _empty_value(schema: JsonObject) -> JsonValue:
    if schema.get("type") == "object":
        return {key: _empty_value(child) for key, child in schema.get("properties", {}).items()}
    if schema.get("type") == "array":
        return []
    return None


def extract_configured(
    document: ExtractedDocument, config: DocumentConfig, llm: LLMClient | None = None
) -> ExtractionResult:
    data = _empty_value(config.schema)
    evidence = []
    for field_path, rule in config.fields.items():
        pattern = re.compile(rule.pattern)
        normalize = NORMALIZERS[rule.normalize]
        matches = []
        for page in document.pages:
            for match in pattern.finditer(page.text):
                raw = match.group("value")
                if raw is not None and (value := normalize(raw)) is not None:
                    matches.append((value, page.page_number))
        if not matches:
            continue
        value, page_number = matches[0]
        if any(candidate != value for candidate, _ in matches[1:]):
            continue
        parent = data
        keys = field_path.split(".")
        for key in keys[:-1]:
            parent = parent[key]
        parent[keys[-1]] = value
        evidence.append(Evidence(field_path, page_number, "regex"))
    return ExtractionResult(data, tuple(evidence))


def resolve_extractor(config: DocumentConfig) -> Extractor:
    if config.extractor is None:
        return extract_configured
    module, function = config.extractor.split(":", 1)
    try:
        extractor = getattr(import_module(module), function)
    except (ImportError, AttributeError) as exc:
        raise ConfigurationError(f"Nie można załadować ekstraktora {config.extractor}") from exc
    if not callable(extractor):
        raise ConfigurationError(f"Ekstraktor {config.extractor} musi być funkcją")
    return extractor
