import os
import re
import shutil
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from fastapi import Body, FastAPI, File, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .contracts import ConfigurationError, DocumentError
from .processing import DocumentProcessor
from .providers.config import client_from_environment
from .schema_registry import load_configs


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
ERROR_MESSAGES = {
    "pdf_read": "Nie udało się odczytać pliku PDF.",
    "pdf_encrypted": "Plik PDF wymaga hasła.",
    "ocr_required": "Dokument wymaga odczytu OCR.",
    "ocr_failed": "Nie udało się odczytać strony przez OCR.",
    "invalid_output": "Wynik nie odpowiada schematowi dokumentu.",
    "llm_connect": "Nie udało się połączyć z usługą modelu.",
    "llm_http": "Usługa modelu zwróciła błąd.",
    "llm_rate_limit": "Przekroczono limit żądań usługi modelu. Spróbuj ponownie później.",
    "llm_incomplete": "Model nie ukończył odpowiedzi.",
    "llm_json": "Model zwrócił nieprawidłowy JSON.",
}
TYPE_FILE_LIMIT = 64 * 1024
TYPE_ID = re.compile(r"[a-z][a-z0-9_]*")


def schema_fields(schema, prefix=""):
    """Ścieżki pól liściowych schematu, np. `Odwolujacy[].krs`."""
    if schema.get("type") == "array" or "items" in schema:
        return schema_fields(schema.get("items", {}), prefix + "[]")
    properties = schema.get("properties")
    if not properties:
        return [prefix] if prefix else []
    return [path for key, value in properties.items()
            for path in schema_fields(value, f"{prefix}.{key}" if prefix else key)]


def error_response(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def type_upload_allowed():
    """Zapis typów z panelu można wyłączyć zmienną ALLOW_TYPE_UPLOAD=0 (np. na serwerze współdzielonym)."""
    return os.getenv("ALLOW_TYPE_UPLOAD", "1").strip().lower() not in ("0", "false", "no", "off")


def create_app(processor=None, frontend_dir=FRONTEND, config_dir=ROOT / "configs/documents", schema_dir=ROOT / "schemas"):
    app = FastAPI()
    config_dir, schema_dir = Path(config_dir), Path(schema_dir)
    if processor is None:
        load_dotenv(ROOT / ".env", override=False)
        configs = load_configs(config_dir, schema_dir)
        llm_configured = any(os.getenv(name) for name in ("LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "API_KEY"))
        client = client_from_environment() if llm_configured else None
        processor = DocumentProcessor(configs, ROOT / "prompts/system_pl.md", client)
    llm = getattr(getattr(processor, "prompted", None), "client", None)
    model = getattr(llm, "model", None)
    # Procesor podmieniany po dodaniu typu; zamek pilnuje, żeby dwa zapisy nie nadpisały się nawzajem.
    current = {"processor": processor}
    type_lock = threading.Lock()

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        if request.url.path == "/api/document-types":
            return error_response(400, "invalid_request", "Wyślij treść pliku YAML i schematu JSON.")
        return error_response(400, "invalid_request", "Wybierz co najmniej jeden plik PDF.")

    @app.post("/api/extract")
    def extract(files: list[UploadFile] = File(...)):
        documents = []
        with TemporaryDirectory() as directory:
            for index, file in enumerate(files):
                name = (file.filename or "").replace("\\", "/").split("/")[-1]
                path = Path(directory) / f"{index}.pdf"
                try:
                    with path.open("wb") as output:
                        shutil.copyfileobj(file.file, output)
                    classification, data = current["processor"].process(path)
                    kind = classification.doc_type
                    documents.append({"filename": name, "status": "unknown" if kind == "unknown" else "ok", "type": kind, "data": data})
                except DocumentError as exc:
                    documents.append({"filename": name, "status": "error", "type": None, "data": None,
                                      "error": {"code": exc.code, "message": ERROR_MESSAGES.get(
                                          exc.code, "Nie udało się przetworzyć dokumentu.")}})
                finally:
                    file.file.close()
                    path.unlink(missing_ok=True)
        return {"documents": documents, "meta": {"model": model}}

    @app.get("/api/document-types")
    def document_types():
        configs = getattr(current["processor"], "configs", {})
        # `schema` pozwala panelowi zbudować pełny formularz (etykiety z description, daty, tak/nie, listy)
        # także dla typów dodanych w kreatorze, których panel nie zna z góry.
        return {"types": [{"doc_type": key, "label": (config.options or {}).get("label"),
                           "fields": schema_fields(config.schema), "schema": config.schema}
                          for key, config in configs.items()]}

    @app.post("/api/document-types", status_code=201)
    def add_document_type(payload: dict = Body(...)):
        """Zapisuje typ przygotowany w kreatorze panelu: YAML do configs/documents, schemat do schemas.

        Przed zapisem cały zestaw (dotychczasowe typy + nowy) przechodzi przez load_configs,
        czyli te same reguły co przy starcie. Nowy typ działa od następnego żądania, bez restartu.
        """
        if not type_upload_allowed():
            return error_response(403, "type_upload_disabled", "Dodawanie typów z panelu jest wyłączone na tym serwerze.")
        if not hasattr(current["processor"], "with_configs"):
            return error_response(501, "not_supported", "Ten serwer nie obsługuje dodawania typów z panelu.")
        yaml_text, schema_text = payload.get("yaml"), payload.get("schema")
        if not all(isinstance(text, str) and text.strip() for text in (yaml_text, schema_text)):
            return error_response(400, "invalid_request", "Wyślij treść pliku YAML i schematu JSON.")
        if max(len(yaml_text.encode("utf-8")), len(schema_text.encode("utf-8"))) > TYPE_FILE_LIMIT:
            return error_response(413, "too_large", "Plik konfiguracji jest za duży (limit 64 KB).")
        try:
            settings = yaml.safe_load(yaml_text)
        except yaml.YAMLError:
            return error_response(400, "invalid_config", "Plik YAML ma błąd składni.")
        doc_type = settings.get("id") if isinstance(settings, dict) else None
        if not isinstance(doc_type, str) or not TYPE_ID.fullmatch(doc_type) or doc_type == "unknown":
            return error_response(400, "invalid_config", "Identyfikator typu (id): małe litery bez polskich znaków, cyfry i podkreślenie.")
        if "extractor" in settings:
            # Ekstraktor to kod Pythona importowany przy starcie: z panelu przyjmujemy tylko konfigurację.
            return error_response(400, "invalid_config", "Własny ekstraktor (extractor) można dodać tylko w repozytorium, nie z panelu.")
        schema_name = f"{doc_type}.schema.json"
        if settings.get("schema") != schema_name:
            return error_response(400, "invalid_config", f"Pole schema musi mieć wartość {schema_name}.")
        yaml_path, schema_path = config_dir / f"{doc_type}.yaml", schema_dir / schema_name

        with type_lock:
            if doc_type in current["processor"].configs or yaml_path.exists() or schema_path.exists():
                return error_response(409, "type_exists", f"Typ „{doc_type}” już istnieje. Wybierz inny identyfikator.")
            with TemporaryDirectory() as directory:
                trial_configs, trial_schemas = Path(directory, "configs"), Path(directory, "schemas")
                trial_configs.mkdir()
                trial_schemas.mkdir()
                for source in config_dir.glob("*.yaml"):
                    shutil.copy2(source, trial_configs / source.name)
                for source in schema_dir.glob("*.json"):
                    shutil.copy2(source, trial_schemas / source.name)
                (trial_configs / yaml_path.name).write_bytes(yaml_text.encode("utf-8"))
                (trial_schemas / schema_name).write_bytes(schema_text.encode("utf-8"))
                try:
                    configs = load_configs(trial_configs, trial_schemas)
                except ConfigurationError as exc:
                    return error_response(400, "invalid_config", str(exc))
            updated = current["processor"].with_configs(configs)
            schema_path.write_bytes(schema_text.encode("utf-8"))
            yaml_path.write_bytes(yaml_text.encode("utf-8"))
            current["processor"] = updated
        return {"doc_type": doc_type, "label": (configs[doc_type].options or {}).get("label"),
                "files": [f"configs/documents/{yaml_path.name}", f"schemas/{schema_name}"]}

    # Panel WWW pod `/`, montowany po trasach `/api`, żeby ich nie przesłaniał.
    if frontend_dir and Path(frontend_dir).is_dir():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app
