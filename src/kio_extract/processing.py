import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .classifier import classify
from .contracts import ClassificationResult, DocumentError, ExtractedDocument, OCR, PageText
from .evidence import locate_evidence, mark_ocr
from .extraction_engine import resolve_extractor
from .pdf_reader import _has_text, extract_pdf
from .prompt_extraction import PromptExtractor
from .ocr import tesseract_ocr
from .normalization import normalize_bzp, normalize_polish_bank_account, normalize_ted
from .vision import ScanSettings, render_pages, resolve_engine, select_pages, transcribe_pages


# Błędy zapytania do modelu, po których wynik powstaje regułami z YAML (a gdy typ nierozpoznany: {}).
FALLBACK_CODES = frozenset({"llm_connect", "llm_http", "llm_rate_limit", "llm_json", "llm_incomplete", "invalid_output"})


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
    def __init__(self, configs, prompt_path: Path, client=None, ocr: OCR | None = None,
                 scan: ScanSettings | None = None):
        self.configs = configs
        self.prompt_path = prompt_path
        self.client = client
        self.scan = scan if scan is not None else ScanSettings.from_environment()
        # OCR podany z zewnątrz (testy) działa jak dawniej; inaczej silnik z SCAN_OCR
        self.scan_engine = "custom" if ocr is not None else resolve_engine(self.scan, client)
        self.ocr = ocr if ocr is not None else (tesseract_ocr if self.scan_engine == "tesseract" else None)
        self.prompted = PromptExtractor(client, tuple(configs.values()), prompt_path) if client else None
        # ekstraktory regułowe także przy modelu: wynik awaryjny, gdy zapytanie do modelu zawiedzie
        self.extractors = {key: resolve_extractor(config) for key, config in configs.items()}
        self.validators = {
            key: Draft202012Validator(config.schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
            for key, config in configs.items()
        }

    def with_configs(self, configs):
        """Nowy procesor z tym samym modelem i OCR, ale innym zestawem typów dokumentów."""
        ocr = self.ocr if self.scan_engine == "custom" else None
        return DocumentProcessor(configs, self.prompt_path, self.client, ocr, self.scan)

    def process(self, path: Path):
        classification, data, _ = self.process_with_evidence(path)
        return classification, data

    def _read_scans(self, path: Path, document: ExtractedDocument):
        """Strony bez tekstu przez model: przepisany tekst (transcribe) albo obrazy do ekstrakcji (image)."""
        if not document.pages_needing_ocr or self.scan_engine != "llm":
            return document, ()
        chosen = select_pages(document.pages_needing_ocr, self.scan.max_pages)
        images = render_pages(path, chosen, self.scan)
        skipped = ()   # strony poza limitem SCAN_MAX_PAGES model pomija świadomie
        if self.scan.mode == "image":
            return ExtractedDocument(path, document.pages, document.used_ocr, skipped, document.ocr_pages), tuple(images)
        workers = getattr(getattr(self.client, "rate_limit", None), "concurrency", 1)
        texts = {number: text for number, text in transcribe_pages(self.client, images, workers).items() if _has_text(text)}
        pages = tuple(PageText(page.page_number, texts.get(page.page_number, page.text)) for page in document.pages)
        ocr_pages = tuple(sorted({*document.ocr_pages, *texts}))
        return ExtractedDocument(path, pages, bool(ocr_pages), skipped, ocr_pages), ()

    @staticmethod
    def _require_text(document: ExtractedDocument, images=()):
        if document.pages_needing_ocr and not images and not any(_has_text(page.text) for page in document.pages):
            pages = ", ".join(map(str, document.pages_needing_ocr))
            raise DocumentError("ocr_required", f"Strony wymagające OCR: {pages}")

    def _rules(self, document: ExtractedDocument):
        classification = classify(document, tuple(self.configs.values()))
        config = self.configs.get(classification.doc_type)
        result = self.extractors[config.doc_type](document, config) if config else None
        data, evidence = (result.data, result.evidence) if result else (None, ())
        return classification, data, evidence

    def _finish(self, document, classification, data, evidence, from_llm: bool):
        if classification.doc_type != "unknown":
            data = normalize_result(data, self.configs[classification.doc_type].schema)
            error = next(self.validators[classification.doc_type].iter_errors(data), None)
            if error is not None:
                raise DocumentError("invalid_output", f"Naruszono schemat ({error.validator})")
            try:
                json.dumps(data, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise DocumentError("invalid_output", "Wynik zawiera nieprawidłowe wartości JSON") from exc
            if from_llm:
                schema = self.configs[classification.doc_type].schema
                evidence = locate_evidence(document, data, schema, "llm+search")
        return classification, data, mark_ocr(evidence, document.ocr_pages)

    def process_with_evidence(self, path: Path):
        """Jak `process`, plus źródła pól (`Evidence`) dla API; CLI ich nie zapisuje."""
        document = extract_pdf(path, self.ocr)
        if not self.prompted:
            self._require_text(document)
            return self._finish(document, *self._rules(document), from_llm=False)
        try:
            document, images = self._read_scans(path, document)
            self._require_text(document, images)
            classification, data = self.prompted.extract(document, images)
            return self._finish(document, classification, data, (), from_llm=True)
        except DocumentError as exc:
            if exc.code not in FALLBACK_CODES:
                raise
            # wynik awaryjny: klasyfikacja i ekstrakcja regułowa z YAML na tekście, który mamy
            self._require_text(document)
            classification, data, evidence = self._rules(document)
            classification = ClassificationResult(classification.doc_type, f"fallback:{exc.code}")
            return self._finish(document, classification, data, evidence, from_llm=False)
