import io
import importlib.util
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kio_extract.api import create_app
from kio_extract.contracts import ClassificationResult, ConfigurationError, DocumentError
from kio_extract.processing import DocumentProcessor
from kio_extract.providers.chat import ChatClient
from kio_extract.schema_registry import load_configs
from test_end_to_end import create_pdf


class FakeProcessor:
    def process(self, path):
        content = path.read_bytes()
        if content == b"broken":
            raise DocumentError("pdf_read", "details")
        if content == b"unknown":
            return ClassificationResult("unknown", "test"), None
        return ClassificationResult("przelew", "test"), {"przelew_bankowy": {"kwota": 10}}


def test_multiple_files_keep_order_and_isolate_errors():
    client = TestClient(create_app(FakeProcessor()))
    response = client.post("/api/extract", files=[
        ("files", ("same.pdf", io.BytesIO(b"ok"), "application/pdf")),
        ("files", ("same.pdf", io.BytesIO(b"broken"), "application/pdf")),
        ("files", ("other.pdf", io.BytesIO(b"unknown"), "application/pdf")),
    ])
    assert response.status_code == 200
    entries = response.json()["documents"]
    assert [entry["status"] for entry in entries] == ["ok", "error", "unknown"]
    assert [entry["filename"] for entry in entries] == ["same.pdf", "same.pdf", "other.pdf"]
    assert entries[1]["error"]["code"] == "pdf_read"
    assert entries[1]["error"]["message"] == "Nie udało się odczytać pliku PDF."
    assert "details" not in json.dumps(entries)


def test_empty_upload_is_bad_request():
    response = TestClient(create_app(FakeProcessor())).post("/api/extract")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_incomplete_llm_configuration_cannot_silently_use_rules(monkeypatch):
    monkeypatch.setattr("kio_extract.api.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:8765/v1")
    monkeypatch.setenv("LLM_PROVIDER", "chat")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        create_app()


def test_real_pdf_flows_through_processor_and_api(tmp_path):
    root = Path(__file__).resolve().parents[1]
    pdf = tmp_path / "input.pdf"
    create_pdf(pdf, ("Potwierdzenie wykonania przelewu", "Data operacji: 03.02.2026", "Kwota: 50,00 PLN"))
    processor = DocumentProcessor(load_configs(root / "configs/documents", root / "schemas"), root / "prompts/system_pl.md")
    client = TestClient(create_app(processor))
    response = client.post("/api/extract", files=[("files", ("test.pdf", pdf.read_bytes(), "application/pdf"))])
    assert response.status_code == 200
    result = response.json()["documents"][0]
    assert result["status"] == "ok" and result["type"] == "przelew"
    assert result["data"]["przelew_bankowy"]["kwota"] == 50


def test_api_with_local_fake_llm_and_real_pdf(tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("fake_llm_server", root / "tests/support/fake_llm_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        pdf = tmp_path / "input.pdf"
        create_pdf(pdf, ("Potwierdzenie wykonania przelewu", "Kwota: 50,00 PLN"))
        llm = ChatClient(f"http://127.0.0.1:{server.server_port}/v1", "fixture", "")
        configs = load_configs(root / "configs/documents", root / "schemas")
        processor = DocumentProcessor(configs, root / "prompts/system_pl.md", client=llm)
        response = TestClient(create_app(processor)).post(
            "/api/extract", files=[("files", ("test.pdf", pdf.read_bytes(), "application/pdf"))]
        )
        assert response.status_code == 200
        result = response.json()["documents"][0]
        assert result["status"] == "ok" and result["type"] == "przelew"
        assert set(result["data"]["przelew_bankowy"]) == {
            "data_operacji", "kwota", "na_rachunek", "numer_transakcji", "tytul", "z_rachunku"
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
