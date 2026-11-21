import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, File, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .contracts import DocumentError
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


def schema_fields(schema, prefix=""):
    """Return leaf paths such as `Odwolujacy[].krs` for the configuration panel."""
    if schema.get("type") == "array" or "items" in schema:
        return schema_fields(schema.get("items", {}), prefix + "[]")
    properties = schema.get("properties")
    if not properties:
        return [prefix] if prefix else []
    return [path for key, value in properties.items()
            for path in schema_fields(value, f"{prefix}.{key}" if prefix else key)]


def create_app(processor=None, frontend_dir=FRONTEND):
    app = FastAPI()
    if processor is None:
        load_dotenv(ROOT / ".env", override=False)
        configs_dir = Path(os.getenv("KIO_CONFIGS_DIR", str(ROOT / "configs/documents")))
        schemas_dir = Path(os.getenv("KIO_SCHEMAS_DIR", str(ROOT / "schemas")))
        prompt_path = Path(os.getenv("KIO_PROMPT_PATH", str(ROOT / "prompts/system_pl.md")))
        configs = load_configs(configs_dir, schemas_dir)
        llm_configured = any(os.getenv(name) for name in ("LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "API_KEY"))
        client = client_from_environment() if llm_configured else None
        processor = DocumentProcessor(configs, prompt_path, client)
    llm = getattr(getattr(processor, "prompted", None), "client", None)
    model = getattr(llm, "model", None)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(status_code=400, content={"error": {
            "code": "invalid_request", "message": "Wybierz co najmniej jeden plik PDF."
        }})

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
                    classification, data = processor.process(path)
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
        configs = getattr(processor, "configs", {})
        return {"types": [{"doc_type": key,
                           "label": getattr(config, "options", {}).get("label"),
                           "fields": schema_fields(config.schema)}
                          for key, config in configs.items()]}

    if frontend_dir and Path(frontend_dir).is_dir():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app
