import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, File, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .contracts import DocumentError
from .processing import DocumentProcessor
from .providers.config import client_from_environment
from .schema_registry import load_configs


ROOT = Path(__file__).resolve().parents[2]
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


def create_app(processor=None):
    app = FastAPI()
    if processor is None:
        load_dotenv(ROOT / ".env", override=False)
        configs = load_configs(ROOT / "configs/documents", ROOT / "schemas")
        llm_configured = any(os.getenv(name) for name in ("LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "API_KEY"))
        client = client_from_environment() if llm_configured else None
        processor = DocumentProcessor(configs, ROOT / "prompts/system_pl.md", client)

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
        return {"documents": documents}

    return app
