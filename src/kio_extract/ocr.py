import os
import shutil
import subprocess
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

import pypdfium2

from .contracts import DocumentError


_pdfium_lock = threading.Lock()


def tesseract_ocr(path: Path, page_number: int) -> str | None:
    executable = shutil.which("tesseract")
    if executable is None:
        raise DocumentError("ocr_required", "Brak programu Tesseract OCR")
    try:
        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "page.png"
            with _pdfium_lock:
                with pypdfium2.PdfDocument(path) as document:
                    page = document[page_number - 1]
                    try:
                        bitmap = page.render(scale=2)
                        try:
                            image = bitmap.to_pil()
                            if image.convert("L").getextrema() == (255, 255):
                                return None
                            image.save(image_path)
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
            environment = os.environ.copy()
            environment.setdefault("OMP_THREAD_LIMIT", "1")
            result = subprocess.run([executable, str(image_path), "stdout", "-l", "pol"],
                                    capture_output=True, timeout=60, check=True, env=environment)
            return result.stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError, UnicodeError, RuntimeError, ValueError) as exc:
        raise DocumentError("ocr_failed", "Nie udało się odczytać strony przez OCR") from exc
