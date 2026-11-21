import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .classifier import classify
from .contracts import DocumentError, OCR
from .evidence import locate_evidence, mark_ocr
from .extraction_engine import resolve_extractor
from .pdf_reader import extract_pdf
from .prompt_extraction import PromptExtractor
from .ocr import tesseract_ocr
from .normalization import normalize_bzp, normalize_polish_bank_account, normalize_ted


def normalize_result(value, schema):
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        return {key: normalize_result(item, properties.get(key, {})) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_result(item, schema.get("items", {})) for item in value]
    if isinstance(value, str) and schema.get("x-normalizer") == "polish_bank_account":
        return normalize_polish_bank_account(value)
    if isinstance(value, str) and schema.get("x-normalizer") == "ted":
        return normalize_ted(value)
    if isinstance(value, str) and schema.get("x-normalizer") == "bzp":
        return normalize_bzp(value)
    return value


class DocumentProcessor:
    def __init__(self, configs, prompt_path: Path, client=None, ocr: OCR | None = None):
        self.configs = configs
        self.prompt_path = prompt_path
        self.client = client
        self.ocr = ocr if ocr is not None else tesseract_ocr
        self.prompted = PromptExtractor(client, tuple(configs.values()), prompt_path) if client else None
        self.extractors = {} if client else {key: resolve_extractor(config) for key, config in configs.items()}
        self.validators = {
            key: Draft202012Validator(config.schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
            for key, config in configs.items()
        }

    def with_configs(self, configs):
        """Nowy procesor z tym samym modelem i OCR, ale innym zestawem typów dokumentów."""
        return DocumentProcessor(configs, self.prompt_path, self.client, self.ocr)

    def process(self, path: Path):
        classification, data, _ = self.process_with_evidence(path)
        return classification, data

    def process_with_evidence(self, path: Path):
        """Jak `process`, plus źródła pól (`Evidence`) dla API; CLI ich nie zapisuje."""
        document = extract_pdf(path, self.ocr)
        if document.pages_needing_ocr:
            pages = ", ".join(map(str, document.pages_needing_ocr))
            raise DocumentError("ocr_required", f"Strony wymagające OCR: {pages}")
        if self.prompted:
            classification, data = self.prompted.extract(document)
            evidence = ()
        else:
            classification = classify(document, tuple(self.configs.values()))
            config = self.configs.get(classification.doc_type)
            result = self.extractors[config.doc_type](document, config) if config else None
            data, evidence = (result.data, result.evidence) if result else (None, ())
        if classification.doc_type != "unknown":
            data = normalize_result(data, self.configs[classification.doc_type].schema)
            error = next(self.validators[classification.doc_type].iter_errors(data), None)
            if error is not None:
                raise DocumentError("invalid_output", f"Naruszono schemat ({error.validator})")
            try:
                json.dumps(data, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise DocumentError("invalid_output", "Wynik zawiera nieprawidłowe wartości JSON") from exc
            if self.prompted:
                schema = self.configs[classification.doc_type].schema
                evidence = locate_evidence(document, data, schema, "llm+search")
        return classification, data, mark_ocr(evidence, document.ocr_pages)
