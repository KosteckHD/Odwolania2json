import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from kio_extract.contracts import DocumentError
from kio_extract.ocr import tesseract_ocr
from test_end_to_end import create_pdf


def test_ocr_renders_page_and_releases_temporary_file(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    create_pdf(pdf, ("Test dokumentu i renderowania.",))
    paths = []

    def run(args, **kwargs):
        path = Path(args[1])
        assert path.read_bytes().startswith(b"\x89PNG")
        paths.append(path)
        assert args[2:] == ["stdout", "-l", "pol"]
        return SimpleNamespace(stdout="Zażółć gęślą".encode("utf-8"))

    monkeypatch.setattr("kio_extract.ocr.shutil.which", lambda _: "tesseract")
    monkeypatch.setattr("kio_extract.ocr.subprocess.run", run)
    assert tesseract_ocr(pdf, 1) == "Zażółć gęślą"
    assert not paths[0].exists()


def test_ocr_timeout_is_reported_without_source_text(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    create_pdf(pdf, ("Test dokumentu i renderowania.",))
    monkeypatch.setattr("kio_extract.ocr.shutil.which", lambda _: "tesseract")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("tesseract", 60)

    monkeypatch.setattr("kio_extract.ocr.subprocess.run", timeout)
    with pytest.raises(DocumentError) as error:
        tesseract_ocr(pdf, 1)
    assert error.value.code == "ocr_failed"


def test_visibly_blank_page_does_not_call_tesseract(tmp_path, monkeypatch):
    pdf = tmp_path / "blank.pdf"
    create_pdf(pdf)
    monkeypatch.setattr("kio_extract.ocr.shutil.which", lambda _: "tesseract")

    def unexpected(*args, **kwargs):
        pytest.fail("A white page does not need OCR")

    monkeypatch.setattr("kio_extract.ocr.subprocess.run", unexpected)
    assert tesseract_ocr(pdf, 1) is None
