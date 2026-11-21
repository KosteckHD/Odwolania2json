import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from kio_extract.contracts import DocumentError
from kio_extract.ocr import tesseract_account_fragments, tesseract_ocr
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
        return SimpleNamespace(stdout="Zażółć gęślą jaźń".encode("utf-8"))

    monkeypatch.setattr("kio_extract.ocr.shutil.which", lambda _: "tesseract")
    monkeypatch.setattr("kio_extract.ocr.subprocess.run", run)
    assert tesseract_ocr(pdf, 1) == "Zażółć gęślą jaźń"
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


def test_ocr_retries_empty_page_with_adaptive_threshold(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    create_pdf(pdf, ("Test dokumentu i renderowania.",))
    monkeypatch.setattr("kio_extract.ocr.shutil.which", lambda _: "tesseract")
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=b"" if len(calls) == 1 else b"Recovered document text")
    monkeypatch.setattr("kio_extract.ocr.subprocess.run", run)
    assert tesseract_ocr(pdf, 1) == "Recovered document text"
    assert calls[1][-2:] == ["-c", "thresholding_method=2"]


def test_account_ocr_crops_role_labeled_number_and_checks_checksum(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    create_pdf(pdf, ("A page with enough visible text to render.",))
    account = "61109010140000071219812874"
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t40\t50\t60\t12\t90\tDane\n"
        "5\t1\t1\t1\t1\t2\t105\t50\t70\t12\t90\tnadawcy\n"
        f"5\t1\t1\t1\t2\t1\t40\t80\t230\t12\t90\t{account}\n"
        "5\t1\t1\t1\t3\t1\t40\t110\t60\t12\t90\tDane\n"
        "5\t1\t1\t1\t3\t2\t105\t110\t70\t12\t90\todbiorcy\n"
        f"5\t1\t1\t1\t4\t1\t40\t140\t230\t12\t90\t{account}\n"
    ).encode()
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[-1] == "tsv":
            return SimpleNamespace(stdout=tsv)
        assert Path(args[1]).read_bytes().startswith(b"\x89PNG")
        assert "--psm" in args and "7" in args
        return SimpleNamespace(stdout=account.encode())

    monkeypatch.setattr("kio_extract.ocr.shutil.which", lambda _: "tesseract")
    monkeypatch.setattr("kio_extract.ocr.subprocess.run", run)

    assert tesseract_account_fragments(pdf, 1) == {
        "z_rachunku": (account,), "na_rachunku": (account,)}
    assert len(calls) == 3


def test_account_ocr_accepts_one_checksum_valid_window(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    create_pdf(pdf, ("A page with enough visible text to render.",))
    account = "61109010140000071219812874"
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t40\t50\t60\t12\t90\tDane\n"
        "5\t1\t1\t1\t1\t2\t105\t50\t70\t12\t90\tnadawcy\n"
        f"5\t1\t1\t1\t2\t1\t40\t80\t230\t12\t90\t{account}\n"
    ).encode()
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[-1] == "tsv":
            return SimpleNamespace(stdout=tsv)
        return SimpleNamespace(stdout=("9" + account).encode())

    monkeypatch.setattr("kio_extract.ocr.shutil.which", lambda _: "tesseract")
    monkeypatch.setattr("kio_extract.ocr.subprocess.run", run)

    assert tesseract_account_fragments(pdf, 1) == {"z_rachunku": (account,)}
    assert len(calls) == 2


def test_extract_pdf_records_pages_processed_by_ocr(tmp_path):
    from kio_extract.pdf_reader import extract_pdf

    pdf = tmp_path / "scan.pdf"
    create_pdf(pdf, ("short",))
    result = extract_pdf(pdf, lambda _path, _page: "Recovered page text with enough characters.")

    assert result.used_ocr
    assert result.ocr_pages == (1,)
