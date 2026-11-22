"""Skany bez warstwy tekstowej: render strony do obrazu i odczyt przez ten sam model (bez Tesseracta).

Ustawienia (zmienne środowiskowe):
- SCAN_OCR: `auto` (domyślnie: model, gdy jest skonfigurowany i obsługuje obrazy, inaczej Tesseract),
  `llm`, `tesseract`, `none`.
- SCAN_MODE: `transcribe` (domyślnie: model przepisuje tekst strony, potem zwykła ścieżka tekstowa)
  albo `image` (obrazy stron idą od razu do zapytania ekstrakcji).
- SCAN_MAX_PAGES: ile stron skanu odczytać (domyślnie 4: pierwsze trzy i ostatnia, tam są strony,
  data, podpis pełnomocnika); 0 = wszystkie.
- SCAN_SCALE: skala renderu (1 = 72 dpi, domyślnie 1.5), SCAN_JPEG_QUALITY (domyślnie 80).
"""
import base64
import io
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pypdfium2

from .contracts import ConfigurationError, DocumentError

_pdfium_lock = threading.Lock()

TRANSCRIBE_INSTRUCTIONS = (
    "Jesteś narzędziem OCR. Przepisz dokładnie cały tekst widoczny na obrazie strony dokumentu, "
    "zachowując kolejność czytania, podział na wiersze, polskie znaki, cyfry, numery rachunków, "
    "identyfikatory i adresy e-mail dokładnie jak w dokumencie. Tabele przepisz wierszami. "
    "Pomiń pieczątki i podpisy odręczne, chyba że zawierają czytelny tekst. "
    "Nie dodawaj komentarzy, opisów ani formatowania Markdown. Gdy strona jest pusta, zwróć pusty tekst."
)


@dataclass(frozen=True)
class ScanSettings:
    ocr: str = "auto"
    mode: str = "transcribe"
    max_pages: int = 4
    scale: float = 1.5
    jpeg_quality: int = 80

    @classmethod
    def from_environment(cls) -> "ScanSettings":
        try:
            settings = cls(
                os.getenv("SCAN_OCR", "auto").strip().lower() or "auto",
                os.getenv("SCAN_MODE", "transcribe").strip().lower() or "transcribe",
                int(os.getenv("SCAN_MAX_PAGES", "4")),
                float(os.getenv("SCAN_SCALE", "1.5")),
                int(os.getenv("SCAN_JPEG_QUALITY", "80")),
            )
        except ValueError as exc:
            raise ConfigurationError("Nieprawidłowa konfiguracja odczytu skanów (SCAN_*)") from exc
        if (settings.ocr not in {"auto", "llm", "tesseract", "none"} or settings.mode not in {"transcribe", "image"}
                or settings.max_pages < 0 or not 0.5 <= settings.scale <= 4 or not 30 <= settings.jpeg_quality <= 95):
            raise ConfigurationError("Nieprawidłowa konfiguracja odczytu skanów (SCAN_*)")
        return settings


def select_pages(pages: tuple[int, ...], limit: int) -> tuple[int, ...]:
    """Pierwsze `limit - 1` stron i ostatnia (podpis, załączniki); 0 = wszystkie."""
    if limit == 0 or len(pages) <= limit:
        return pages
    if limit == 1:
        return pages[:1]
    return (*pages[:limit - 1], pages[-1])


def render_page_jpeg(path: Path, page_number: int, scale: float = 1.5, quality: int = 80) -> bytes | None:
    """Strona jako JPEG RGB (model odrzuca obrazy w skali szarości); None dla pustej strony."""
    try:
        with _pdfium_lock:
            with pypdfium2.PdfDocument(path) as document:
                page = document[page_number - 1]
                try:
                    bitmap = page.render(scale=scale)
                    try:
                        image = bitmap.to_pil().convert("RGB")
                    finally:
                        bitmap.close()
                finally:
                    page.close()
    except (OSError, RuntimeError, ValueError, IndexError) as exc:
        raise DocumentError("ocr_failed", "Nie udało się wyrenderować strony skanu") from exc
    if image.convert("L").getextrema()[0] >= 250:
        return None
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def data_url(image: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")


def supports_images(client) -> bool:
    return client is not None and callable(getattr(client, "transcribe_image", None))


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def resolve_engine(settings: ScanSettings, client) -> str:
    """Silnik OCR dla skanów: `llm`, `tesseract` albo `none`."""
    if settings.ocr == "auto":
        if supports_images(client):
            return "llm"
        return "tesseract" if tesseract_available() else "none"
    if settings.ocr == "llm" and not supports_images(client):
        raise ConfigurationError("SCAN_OCR=llm wymaga modelu obsługującego obrazy")
    return settings.ocr


def render_pages(path: Path, pages: tuple[int, ...], settings: ScanSettings) -> list[tuple[int, bytes]]:
    rendered = [(number, render_page_jpeg(path, number, settings.scale, settings.jpeg_quality)) for number in pages]
    return [(number, image) for number, image in rendered if image is not None]


def transcribe_pages(client, images: list[tuple[int, bytes]], workers: int) -> dict[int, str]:
    """Tekst stron przepisany przez model; zapytania równolegle (limit i tak pilnuje koordynator)."""
    tracks_usage = hasattr(client, "last_usage")
    caller_usage = dict(client.last_usage or {}) if tracks_usage else {}

    def one(item):
        number, image = item
        if tracks_usage:
            client.last_usage = None
        try:
            text = client.transcribe_image(instructions=TRANSCRIBE_INSTRUCTIONS, image=image)
        except DocumentError as exc:
            text = exc   # jedna nieudana strona nie przekreśla pozostałych
        return number, text, (client.last_usage or {}) if tracks_usage else {}

    if len(images) <= 1:
        results = list(map(one, images))
    else:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(images)))) as pool:
            results = list(pool.map(one, images))
    if tracks_usage:
        # zużycie tokenów jest per wątek: sumujemy odczyt stron do licznika dokumentu
        for _, _, usage in results:
            for key, value in usage.items():
                caller_usage[key] = caller_usage.get(key, 0) + value
        client.last_usage = caller_usage or None
    texts = {number: text for number, text, _ in results if isinstance(text, str)}
    failures = [text for _, text, _ in results if isinstance(text, DocumentError)]
    if failures and not texts:
        raise failures[0]
    return texts
