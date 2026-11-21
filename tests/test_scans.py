"""Skany przez model (obrazy stron) i wynik awaryjny po błędzie modelu; bez sieci."""
import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject

from kio_extract.cli import main
from kio_extract.contracts import DocumentError
from kio_extract.processing import DocumentProcessor
from kio_extract.providers import chat
from kio_extract.schema_registry import load_configs
from kio_extract.vision import ScanSettings, render_page_jpeg, select_pages
from test_end_to_end import create_pdf

ROOT = Path(__file__).resolve().parents[1]
PAYMENT_TEXT = "Potwierdzenie wykonania przelewu\nData operacji: 03.02.2026\nKwota: 1 234,50 PLN"


def create_scan(path: Path, pages: int = 1) -> None:
    """PDF bez warstwy tekstowej, ale z treścią graficzną (jak skan)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with PdfWriter() as writer:
        for _ in range(pages):
            page = writer.add_blank_page(width=595, height=842)
            stream = DecodedStreamObject()
            stream.set_data(b"0 0 0 rg 60 700 300 40 re f 60 600 200 20 re f")
            page.replace_contents(stream)
        writer.write(path)


class FakeClient:
    def __init__(self, answer=None, error=None, page_text=PAYMENT_TEXT):
        self.answer, self.error, self.page_text = answer, error, page_text
        self.transcribed, self.requests = [], []
        self.rate_limit = SimpleNamespace(concurrency=2)
        self.last_usage = None

    def transcribe_image(self, *, instructions, image):
        assert image.startswith(b"\xff\xd8")   # JPEG
        self.transcribed.append(image)
        return self.page_text

    def extract_json(self, *, instructions, text, schema, images=()):
        self.requests.append((json.loads(text), images))
        if self.error:
            raise DocumentError(self.error, "test")
        return self.answer


def processor(client, **scan):
    configs = load_configs(ROOT / "configs" / "documents", ROOT / "schemas")
    return DocumentProcessor(configs, ROOT / "prompts" / "system_pl.md", client, scan=ScanSettings(**{"ocr": "llm", **scan}))


def payment(amount=1234.5):
    return {"przelew_bankowy": {"data_operacji": "2026-02-03", "kwota": amount, "na_rachunek": None,
                                "numer_transakcji": None, "tytul": None, "z_rachunku": None}}


def test_select_pages_keeps_first_pages_and_last():
    assert select_pages((1, 2, 3, 4, 5, 6, 7), 4) == (1, 2, 3, 7)
    assert select_pages((1, 2), 4) == (1, 2)
    assert select_pages((1, 2, 3), 0) == (1, 2, 3)
    assert select_pages((1, 2, 3), 1) == (1,)


def test_blank_page_is_not_sent_to_model(tmp_path):
    blank = tmp_path / "blank.pdf"
    create_pdf(blank)
    assert render_page_jpeg(blank, 1) is None
    scan = tmp_path / "scan.pdf"
    create_scan(scan)
    assert render_page_jpeg(scan, 1).startswith(b"\xff\xd8")


def test_scan_is_transcribed_by_model_then_extracted_from_text(tmp_path):
    scan = tmp_path / "scan.pdf"
    create_scan(scan, pages=6)
    client = FakeClient(answer={"typ": "przelew", "dane": payment()})
    classification, data, evidence = processor(client, max_pages=3).process_with_evidence(scan)
    assert (classification.doc_type, data) == ("przelew", payment())
    assert len(client.transcribed) == 3   # strony 1, 2 i ostatnia
    pages, images = client.requests[0]
    assert images == ()
    assert [page["numer"] for page in pages["strony"] if page["tekst"]] == [1, 2, 6]
    assert all(item.method.startswith("ocr+") for item in evidence)


def test_scan_images_go_straight_to_extraction_in_image_mode(tmp_path):
    scan = tmp_path / "scan.pdf"
    create_scan(scan, pages=2)
    client = FakeClient(answer={"typ": "przelew", "dane": payment()})
    classification, data = processor(client, mode="image").process(scan)
    assert classification.doc_type == "przelew"
    assert client.transcribed == []
    _, images = client.requests[0]
    assert [number for number, _ in images] == [1, 2]


@pytest.mark.parametrize("code", ["llm_connect", "llm_json", "invalid_output", "llm_rate_limit"])
def test_model_failure_falls_back_to_yaml_rules(tmp_path, code):
    source = tmp_path / "przelew.pdf"
    create_pdf(source, tuple(PAYMENT_TEXT.splitlines()))
    classification, data = processor(FakeClient(error=code)).process(source)
    assert classification == type(classification)("przelew", f"fallback:{code}")
    assert data == payment()


def test_model_failure_on_unrecognised_document_gives_negative(tmp_path):
    source = tmp_path / "inny.pdf"
    create_pdf(source, ("To jest instrukcja obslugi urzadzenia biurowego.",))
    classification, data = processor(FakeClient(error="llm_connect")).process(source)
    assert (classification.doc_type, data) == ("unknown", None)


def test_model_failure_on_scan_uses_transcribed_text_for_rules(tmp_path):
    scan = tmp_path / "scan.pdf"
    create_scan(scan)
    classification, data = processor(FakeClient(error="llm_connect")).process(scan)
    assert classification.reason == "fallback:llm_connect" and data == payment()


def test_cli_writes_file_for_every_pdf_when_model_is_unreachable(tmp_path, monkeypatch, capsys):
    input_dir, output_dir, report = tmp_path / "input", tmp_path / "output", tmp_path / "run.json"
    create_pdf(input_dir / "przelew.pdf", tuple(PAYMENT_TEXT.splitlines()))
    create_pdf(input_dir / "inny.pdf", ("To jest instrukcja obslugi urzadzenia biurowego.",))
    create_scan(input_dir / "skan.pdf")

    class DeadConnection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            raise ConnectionResetError("test")

        def close(self):
            pass

    monkeypatch.setattr(chat, "HTTPConnection", DeadConnection)
    monkeypatch.setattr("kio_extract.providers.rate_limit.time.sleep", lambda _: None)
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8765/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_REQUEST_INTERVAL_SECONDS", "0")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert main(["--llm", "--input", str(input_dir), "--output", str(output_dir), "--report", str(report)]) == 1
    assert json.loads((output_dir / "przelew.json").read_bytes()) == payment()
    assert json.loads((output_dir / "inny.json").read_bytes()) == {}
    assert json.loads((output_dir / "skan.json").read_bytes()) == {}
    entries = {entry["source"]: entry for entry in json.loads(report.read_bytes())["documents"]}
    assert entries["przelew.pdf"]["fallback"] == "llm_connect"
    assert entries["skan.pdf"]["written"] == "negative"   # OCR modelem zawiódł, tekstu brak
    assert "awaryjne=2" in capsys.readouterr().out


def test_chat_client_sends_page_image_as_data_url(monkeypatch):
    requests = []

    class FakeConnection:
        def __init__(self, host, port, timeout):
            pass

        def request(self, method, path, *, body, headers):
            requests.append(json.loads(body))

        def getresponse(self):
            result = {"choices": [{"finish_reason": "length", "message": {"content": " Tekst strony "}}],
                      "usage": {"prompt_tokens": 1100, "completion_tokens": 20, "total_tokens": 1120}}
            return SimpleNamespace(status=200, read=lambda: json.dumps(result).encode("utf-8"))

        def close(self):
            pass

    monkeypatch.setattr(chat, "HTTPConnection", FakeConnection)
    monkeypatch.setenv("LLM_REQUEST_INTERVAL_SECONDS", "0")
    client = chat.ChatClient("http://localhost:8765/v1", "test-model", "", {"chat_template_kwargs": {"enable_thinking": False}})
    assert client.transcribe_image(instructions="Przepisz", image=b"\xff\xd8abc") == "Tekst strony"
    body = requests[0]
    text, image = body["messages"][0]["content"]
    assert text == {"type": "text", "text": "Przepisz"}
    assert image["image_url"]["url"] == "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8abc").decode()
    assert body["chat_template_kwargs"] == {"enable_thinking": False} and "response_format" not in body
    assert client.last_usage["prompt_tokens"] == 1100
