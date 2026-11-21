import csv
import io
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

import pypdfium2

from .contracts import DocumentError
from .normalization import has_valid_polish_bank_checksum


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
            text = result.stdout.decode("utf-8")
            if sum(character.isalnum() for character in text) < 12:
                alternate = subprocess.run([executable, str(image_path), "stdout", "-l", "pol",
                                            "-c", "thresholding_method=2"],
                                           capture_output=True, timeout=60, check=True, env=environment)
                recovered = alternate.stdout.decode("utf-8")
                if sum(character.isalnum() for character in recovered) > sum(character.isalnum() for character in text):
                    text = recovered
            return text
    except (OSError, subprocess.SubprocessError, UnicodeError, RuntimeError, ValueError) as exc:
        raise DocumentError("ocr_failed", "Nie udało się odczytać strony przez OCR") from exc


def tesseract_account_fragments(path: Path, page_number: int) -> dict[str, tuple[str, ...]]:
    """Re-OCR only account-like lines on an OCR page, grouped by sender/recipient."""
    executable = shutil.which("tesseract")
    if executable is None:
        return {}
    try:
        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "page.png"
            with _pdfium_lock:
                with pypdfium2.PdfDocument(path) as document:
                    page = document[page_number - 1]
                    try:
                        bitmap = page.render(scale=3)
                        try:
                            image = bitmap.to_pil()
                            if image.convert("L").getextrema() == (255, 255):
                                return {}
                            image.save(image_path)
                        finally:
                            bitmap.close()
                    finally:
                        page.close()

            environment = os.environ.copy()
            environment.setdefault("OMP_THREAD_LIMIT", "1")
            result = subprocess.run(
                [executable, str(image_path), "stdout", "-l", "pol", "tsv"],
                capture_output=True, timeout=60, check=True, env=environment,
            )
            lines = {}
            reader = csv.DictReader(io.StringIO(result.stdout.decode("utf-8")), delimiter="\t")
            for row in reader:
                if row.get("level") != "5" or not row.get("text", "").strip():
                    continue
                key = (row["block_num"], row["par_num"], row["line_num"])
                line = lines.setdefault(key, {"words": [], "box": None})
                line["words"].append(row["text"].strip())
                left, top = int(row["left"]), int(row["top"])
                right, bottom = left + int(row["width"]), top + int(row["height"])
                if line["box"] is None:
                    line["box"] = [left, top, right, bottom]
                else:
                    box = line["box"]
                    box[:] = [min(box[0], left), min(box[1], top), max(box[2], right), max(box[3], bottom)]

            supplemental = {"z_rachunku": [], "na_rachunku": []}
            role = None
            for line in lines.values():
                text = " ".join(line["words"])
                folded = text.casefold()
                if re.search(r"\b(dane nadawcy|rachunek nadawcy|dane zleceniodawcy|rachunek zleceniodawcy|z rachunku)\b", folded):
                    role = "z_rachunku"
                elif re.search(r"\b(dane odbiorcy|rachunek odbiorcy|dane beneficjenta|dane kontrahenta|rachunek kontrahenta|na rachunek)\b", folded):
                    role = "na_rachunku"
                elif re.search(r"\b(dane zlecenia|szczegóły płatności|tytuł|numer referencyjny)\b", folded):
                    role = None
                if not role or sum(character.isdigit() for character in text) < 20:
                    continue

                left, top, right, bottom = line["box"]
                margin_x, margin_y = 12, 8
                crop = image.crop((max(0, left - margin_x), max(0, top - margin_y),
                                   min(image.width, right + margin_x), min(image.height, bottom + margin_y)))
                crop_path = Path(directory) / f"account-{page_number}-{len(supplemental[role])}.png"
                crop.save(crop_path)
                recovered = subprocess.run(
                    [executable, str(crop_path), "stdout", "-l", "pol", "--psm", "7",
                     "-c", "tessedit_char_whitelist=0123456789"],
                    capture_output=True, timeout=30, check=True, env=environment,
                ).stdout.decode("utf-8")
                digits = "".join(character for character in recovered if character.isascii() and character.isdigit())
                if 26 <= len(digits) <= 32:
                    valid = {digits[index:index + 26] for index in range(len(digits) - 25)
                             if has_valid_polish_bank_checksum(digits[index:index + 26])}
                    if len(valid) == 1:
                        supplemental[role].append(valid.pop())

            return {role: tuple(values) for role, values in supplemental.items() if values}
    except (OSError, subprocess.SubprocessError, UnicodeError, RuntimeError, ValueError, KeyError) as exc:
        raise DocumentError("ocr_failed", "Nie udało się ponownie odczytać fragmentu rachunku") from exc
