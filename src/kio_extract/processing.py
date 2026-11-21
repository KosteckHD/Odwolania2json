import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from .classifier import classify
from .contracts import DocumentError, ExtractedDocument, OCR, PageText
from .extraction_engine import resolve_extractor
from .pdf_reader import extract_pdf
from .prompt_extraction import PromptExtractor
from .ocr import tesseract_account_fragments, tesseract_ocr
from .normalization import has_valid_polish_bank_checksum, normalize_polish_bank_account, normalize_ted


def recover_transfer_accounts(data, document):
    """Repair an account only from one labelled, checksum-valid source candidate."""
    if not isinstance(data, dict) or not isinstance(data.get("przelew_bankowy"), dict):
        return data
    candidates = {"z_rachunku": set(), "na_rachunek": set()}
    for page in document.pages:
        role = None
        for line in page.text.splitlines():
            folded = line.casefold()
            if re.search(r"\b(dane nadawcy|rachunek nadawcy|dane zleceniodawcy|rachunek zleceniodawcy|z rachunku)\b", folded) or folded.strip().rstrip(':') == 'nadawca':
                role = "z_rachunku"
            elif re.search(r"\b(dane odbiorcy|rachunek odbiorcy|dane beneficjenta|dane kontrahenta|rachunek kontrahenta|na rachunek)\b", folded) or folded.strip().rstrip(':') in ('odbiorca', 'adresat przelewu'):
                role = "na_rachunek"
            elif re.search(r"\b(tytuł|tytułem|kwota|status|data operacji|numer referencyjny|dane zlecenia|szczegóły płatności)\b", folded):
                role = None
            if role:
                for match in re.finditer(r"(?<![0-9])(?:[0-9][\s\u200b-]*){25}[0-9](?![0-9])", line):
                    digits = "".join(c for c in match.group() if c.isascii() and c.isdigit())
                    candidates[role].add(digits)
    transfer = dict(data["przelew_bankowy"])
    for field, values in candidates.items():
        current = transfer.get(field)
        if not isinstance(current, str):
            continue
        compact = normalize_polish_bank_account(current)
        prefix = compact[2:] if compact.upper().startswith("PL") else compact
        if not prefix.isascii() or not prefix.isdigit() or len(prefix) not in (24, 25, 26):
            continue
        if len(prefix) == 26 and has_valid_polish_bank_checksum(prefix):
            continue
        valid_values = {value for value in values if has_valid_polish_bank_checksum(value)}
        if len(prefix) == 24:
            matches = [value for value in valid_values if value[2:] == prefix]
        elif len(prefix) == 25:
            matches = [value for value in valid_values if value.startswith(prefix)]
        else:
            matches = [value for value in valid_values if sum(a != b for a, b in zip(value, prefix)) == 1]
        if (len(valid_values) == 1 and len(matches) == 1
                and all(value == matches[0] or (len(prefix) == 26 and value == prefix) for value in values)):
            transfer[field] = matches[0]
    return {**data, "przelew_bankowy": transfer}


def needs_account_recovery(data):
    transfer = data.get("przelew_bankowy") if isinstance(data, dict) else None
    if not isinstance(transfer, dict):
        return False
    for field in ("z_rachunku", "na_rachunek"):
        value = transfer.get(field)
        if not isinstance(value, str):
            continue
        compact = normalize_polish_bank_account(value)
        digits = compact[2:] if compact.upper().startswith("PL") else compact
        if digits.isascii() and digits.isdigit() and (
            len(digits) in (24, 25) or (len(digits) == 26 and not has_valid_polish_bank_checksum(digits))
        ):
            return True
    return False


def add_account_fragments(document):
    pages = list(document.pages)
    by_number = {page.page_number: index for index, page in enumerate(pages)}
    for page_number in document.ocr_pages:
        try:
            fragments = tesseract_account_fragments(document.source_path, page_number)
        except DocumentError:
            continue
        lines = []
        for role, values in fragments.items():
            heading = "Dane nadawcy" if role == "z_rachunku" else "Dane odbiorcy"
            lines.extend([heading, *values])
        if lines and page_number in by_number:
            index = by_number[page_number]
            page = pages[index]
            pages[index] = PageText(page_number, page.text + "\n" + "\n".join(lines))
    return ExtractedDocument(document.source_path, tuple(pages), document.used_ocr,
                             document.pages_needing_ocr, document.ocr_pages)


def recover_repeated_transfer_title(data, document):
    """Restore a repeated reference line only when the source boundaries are unambiguous."""
    if not isinstance(data, dict) or not isinstance(data.get("przelew_bankowy"), dict):
        return data
    transfer = data["przelew_bankowy"]
    title = transfer.get("tytul")
    if not isinstance(title, str) or not title.strip():
        return data
    candidates = []
    for page in document.pages:
        lines = [" ".join(line.split()) for line in page.text.splitlines()]
        for index, line in enumerate(lines):
            if line.casefold().rstrip(":") not in ("tytuł przelewu", "tytuł operacji"):
                continue
            for end in range(index + 2, min(index + 12, len(lines) - 1)):
                if lines[end].casefold().rstrip(":") in ("status", "kwota", "data operacji", "odbiorca", "nadawca"):
                    break
                if lines[end].casefold().rstrip(":") not in ("numer referencyjny", "nr referencyjny"):
                    continue
                parts = [part for part in lines[index + 1:end] if part]
                reference = lines[end + 1]
                if len(parts) >= 2 and parts[-1] == reference and " ".join(parts[:-1]) == " ".join(title.split()):
                    candidates.append(" ".join(parts))
                break
    if len(candidates) == 1:
        return {**data, "przelew_bankowy": {**transfer, "tytul": candidates[0]}}
    return data


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
    return value


class DocumentProcessor:
    def __init__(self, configs, prompt_path: Path, client=None, ocr: OCR | None = None):
        self.configs = configs
        self.ocr = ocr if ocr is not None else tesseract_ocr
        self.prompted = PromptExtractor(client, tuple(configs.values()), prompt_path) if client else None
        self.extractors = {} if client else {key: resolve_extractor(config) for key, config in configs.items()}
        self.validators = {
            key: Draft202012Validator(config.schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
            for key, config in configs.items()
        }

    def process(self, path: Path):
        document = extract_pdf(path, self.ocr)
        if document.pages_needing_ocr:
            pages = ", ".join(map(str, document.pages_needing_ocr))
            raise DocumentError("ocr_required", f"Strony wymagające OCR: {pages}")
        if self.prompted:
            classification, data = self.prompted.extract(document)
        else:
            classification = classify(document, tuple(self.configs.values()))
            config = self.configs.get(classification.doc_type)
            data = self.extractors[config.doc_type](document, config).data if config else None
        if classification.doc_type != "unknown":
            data = normalize_result(data, self.configs[classification.doc_type].schema)
            if classification.doc_type == "przelew":
                account_document = add_account_fragments(document) if needs_account_recovery(data) and document.ocr_pages else document
                data = recover_transfer_accounts(data, account_document)
                data = recover_repeated_transfer_title(data, document)
            error = next(self.validators[classification.doc_type].iter_errors(data), None)
            if error is not None:
                raise DocumentError("invalid_output", f"Naruszono schemat ({error.validator})")
            try:
                json.dumps(data, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise DocumentError("invalid_output", "Wynik zawiera nieprawidłowe wartości JSON") from exc
        return classification, data
