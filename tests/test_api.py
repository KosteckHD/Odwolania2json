import io
import importlib.util
import json
import shutil
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
        assert response.json()["meta"] == {"model": "fixture"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_panel_is_served_next_to_api():
    client = TestClient(create_app(FakeProcessor()))
    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert page.content == (Path(__file__).resolve().parents[1] / "frontend/index.html").read_bytes()
    assert client.get("/api.js").status_code == 200
    response = client.post("/api/extract", files=[("files", ("a.pdf", io.BytesIO(b"ok"), "application/pdf"))])
    assert response.status_code == 200
    assert response.json()["documents"][0]["status"] == "ok"


def test_api_works_without_panel_directory(tmp_path):
    client = TestClient(create_app(FakeProcessor(), frontend_dir=tmp_path / "missing"))
    assert client.get("/").status_code == 404
    response = client.post("/api/extract", files=[("files", ("a.pdf", io.BytesIO(b"ok"), "application/pdf"))])
    assert response.status_code == 200


def test_meta_model_is_empty_without_llm():
    response = TestClient(create_app(FakeProcessor())).post(
        "/api/extract", files=[("files", ("a.pdf", io.BytesIO(b"ok"), "application/pdf"))])
    assert response.json()["meta"] == {"model": None}


def test_document_types_list_configured_schemas():
    root = Path(__file__).resolve().parents[1]
    processor = DocumentProcessor(load_configs(root / "configs/documents", root / "schemas"), root / "prompts/system_pl.md")
    response = TestClient(create_app(processor)).get("/api/document-types")
    assert response.status_code == 200
    types = {entry["doc_type"]: entry["fields"] for entry in response.json()["types"]}
    assert set(types) == {"odwolanie", "pelnomocnictwo", "przelew"}
    assert "przelew_bankowy.kwota" in types["przelew"]
    assert any(path.startswith("Odwolujacy[].") for path in types["odwolanie"])
    schemas = {entry["doc_type"]: entry["schema"] for entry in response.json()["types"]}
    assert schemas["przelew"] == processor.configs["przelew"].schema


NEW_TYPE_YAML = """id: potwierdzenie_odbioru
schema: potwierdzenie_odbioru.schema.json
classification:
  positive_patterns:
    - '(?i)Potwierdzenie\\s+odbioru'
  minimum_matches: 1
fields:
  numer:
    pattern: '(?im)Numer\\s+potwierdzenia\\s*[:.]?\\s*(?P<value>\\S[^\\r\\n]*?)[ \\t\\r]*$'
    normalize: text
options:
  label: "Potwierdzenie odbioru"
  llm_instructions: "Dokument typu „Potwierdzenie odbioru”."
"""
NEW_TYPE_SCHEMA = json.dumps({
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["numer"],
    "properties": {"numer": {"type": ["string", "null"], "description": "Numer potwierdzenia"}},
})


def type_app(tmp_path):
    """API na kopii konfiguracji repo w katalogu tymczasowym, bez modelu (odczyt regułami)."""
    root = Path(__file__).resolve().parents[1]
    config_dir, schema_dir = tmp_path / "configs", tmp_path / "schemas"
    shutil.copytree(root / "configs/documents", config_dir)
    shutil.copytree(root / "schemas", schema_dir)
    processor = DocumentProcessor(load_configs(config_dir, schema_dir), root / "prompts/system_pl.md")
    app = create_app(processor, frontend_dir=None, config_dir=config_dir, schema_dir=schema_dir)
    return TestClient(app), config_dir, schema_dir


def test_new_type_is_saved_validated_and_used_without_restart(tmp_path):
    client, config_dir, schema_dir = type_app(tmp_path)
    response = client.post("/api/document-types", json={"yaml": NEW_TYPE_YAML, "schema": NEW_TYPE_SCHEMA})
    assert response.status_code == 201
    assert response.json() == {
        "doc_type": "potwierdzenie_odbioru", "label": "Potwierdzenie odbioru",
        "files": ["configs/documents/potwierdzenie_odbioru.yaml", "schemas/potwierdzenie_odbioru.schema.json"],
    }
    assert (config_dir / "potwierdzenie_odbioru.yaml").read_text(encoding="utf-8") == NEW_TYPE_YAML
    assert json.loads((schema_dir / "potwierdzenie_odbioru.schema.json").read_text(encoding="utf-8"))["required"] == ["numer"]
    assert "potwierdzenie_odbioru" in load_configs(config_dir, schema_dir)

    types = {entry["doc_type"]: entry for entry in client.get("/api/document-types").json()["types"]}
    assert types["potwierdzenie_odbioru"]["label"] == "Potwierdzenie odbioru"
    assert types["potwierdzenie_odbioru"]["fields"] == ["numer"]
    assert types["potwierdzenie_odbioru"]["schema"]["properties"]["numer"]["description"] == "Numer potwierdzenia"

    pdf = tmp_path / "odbior.pdf"
    create_pdf(pdf, ("Potwierdzenie odbioru", "Numer potwierdzenia: PO/7/2026"))
    result = client.post("/api/extract", files=[("files", ("odbior.pdf", pdf.read_bytes(), "application/pdf"))]).json()
    assert result["documents"][0]["type"] == "potwierdzenie_odbioru"
    assert result["documents"][0]["data"] == {"numer": "PO/7/2026"}


def test_existing_type_is_not_overwritten(tmp_path):
    client, config_dir, _ = type_app(tmp_path)
    before = (config_dir / "przelew.yaml").read_bytes()
    clash = NEW_TYPE_YAML.replace("potwierdzenie_odbioru", "przelew")
    response = client.post("/api/document-types", json={"yaml": clash, "schema": NEW_TYPE_SCHEMA})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "type_exists"
    assert (config_dir / "przelew.yaml").read_bytes() == before


@pytest.mark.parametrize(("yaml_text", "schema_text", "fragment"), [
    (NEW_TYPE_YAML.replace("Potwierdzenie\\s+odbioru'", "(niezamknięty'"), NEW_TYPE_SCHEMA, "potwierdzenie_odbioru.yaml"),
    (NEW_TYPE_YAML, "{ to nie jest JSON", "potwierdzenie_odbioru.yaml"),
    (NEW_TYPE_YAML.replace("  numer:", "  brak_w_schemacie:"), NEW_TYPE_SCHEMA, "poza schematem"),
    (NEW_TYPE_YAML + "extractor: os:system\n", NEW_TYPE_SCHEMA, "extractor"),
    (NEW_TYPE_YAML.replace("schema: potwierdzenie_odbioru", "schema: ../przelew"), NEW_TYPE_SCHEMA, "schema"),
    (NEW_TYPE_YAML.replace("id: potwierdzenie_odbioru", "id: unknown"), NEW_TYPE_SCHEMA, "id"),
    ("id: [", NEW_TYPE_SCHEMA, "składni"),
])
def test_invalid_type_is_rejected_and_nothing_is_written(tmp_path, yaml_text, schema_text, fragment):
    client, config_dir, schema_dir = type_app(tmp_path)
    before = sorted(p.name for p in (*config_dir.iterdir(), *schema_dir.iterdir()))
    response = client.post("/api/document-types", json={"yaml": yaml_text, "schema": schema_text})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_config"
    assert fragment in response.json()["error"]["message"]
    assert sorted(p.name for p in (*config_dir.iterdir(), *schema_dir.iterdir())) == before
    assert {e["doc_type"] for e in client.get("/api/document-types").json()["types"]} == {"odwolanie", "pelnomocnictwo", "przelew"}


def test_type_upload_can_be_disabled(tmp_path, monkeypatch):
    client, config_dir, _ = type_app(tmp_path)
    monkeypatch.setenv("ALLOW_TYPE_UPLOAD", "0")
    response = client.post("/api/document-types", json={"yaml": NEW_TYPE_YAML, "schema": NEW_TYPE_SCHEMA})
    assert response.status_code == 403
    assert not (config_dir / "potwierdzenie_odbioru.yaml").exists()


def test_type_upload_request_errors(tmp_path):
    client, _, _ = type_app(tmp_path)
    assert client.post("/api/document-types", json={"yaml": NEW_TYPE_YAML}).status_code == 400
    response = client.post("/api/document-types", content=b"nie json", headers={"content-type": "application/json"})
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Wyślij treść pliku YAML i schematu JSON."
    big = client.post("/api/document-types", json={"yaml": NEW_TYPE_YAML + "#" * 70_000, "schema": NEW_TYPE_SCHEMA})
    assert big.status_code == 413
    fake = TestClient(create_app(FakeProcessor(), frontend_dir=None))
    assert fake.post("/api/document-types", json={"yaml": NEW_TYPE_YAML, "schema": NEW_TYPE_SCHEMA}).status_code == 501
