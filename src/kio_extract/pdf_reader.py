from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from .contracts import OCR, DocumentError, ExtractedDocument, PageText


def _has_text(text: str) -> bool:
    return sum(character.isalnum() for character in text) >= 12


def extract_pdf(path: Path, ocr: OCR | None = None) -> ExtractedDocument:
    try:
        with path.open("rb") as stream:
            reader = PdfReader(stream)
            if reader.is_encrypted and not reader.decrypt(""):
                raise DocumentError("pdf_encrypted", "PDF wymaga hasła")
            pages = [PageText(number, page.extract_text() or "") for number, page in enumerate(reader.pages, 1)]
    except (OSError, PyPdfError, ValueError, NotImplementedError, RecursionError) as exc:
        raise DocumentError("pdf_read", "Nie udało się odczytać PDF") from exc

    if not pages:
        raise DocumentError("pdf_read", "PDF nie zawiera stron")

    pending = []
    ocr_pages = []
    used_ocr = False
    for index, page in enumerate(pages):
        if _has_text(page.text):
            continue
        if ocr is not None:
            recovered = ocr(path, page.page_number)
            if recovered is None:
                continue
            if _has_text(recovered):
                pages[index] = PageText(page.page_number, recovered)
                used_ocr = True
                ocr_pages.append(page.page_number)
                continue
        pending.append(page.page_number)

    return ExtractedDocument(path, tuple(pages), used_ocr, tuple(pending), tuple(ocr_pages))
