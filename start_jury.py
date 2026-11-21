"""Start the panel with the pinned Ministral 3 8B EU profile."""
import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env", override=False)

parser = argparse.ArgumentParser(description="Uruchamia panel z profilem konkursowym Mistral EU.")
parser.add_argument("--rules", action="store_true", help="awaryjny, deterministyczny tryb demonstracyjny bez LLM")
args = parser.parse_args()

if args.rules:
    os.environ.update({"LLM_PROVIDER": "", "LLM_BASE_URL": "", "LLM_MODEL": "", "LLM_API_KEY": "", "API_KEY": ""})
    print("Profil pokazu: tryb regułowy bez wywołań LLM")
else:
    api_key = (os.getenv("MISTRA_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("Brak klucza. Ustaw MISTRA_API_KEY w środowisku lub lokalnym pliku .env.")

    # This entry point pins the regional endpoint and model so the jury command
    # cannot silently fall back to the rule-based mode or a global endpoint.
    os.environ.update({
        "LLM_PROVIDER": "chat",
        "LLM_BASE_URL": "https://api.eu.mistral.ai/v1",
        "LLM_MODEL": "ministral-8b-2512",
        "LLM_API_KEY": api_key,
    })
    print("Profil pokazu: Mistral EU / Ministral 3 8B (ministral-8b-2512)")

print("Panel i API: http://127.0.0.1:8000/   (Ctrl+C zatrzymuje serwer)")

import uvicorn

uvicorn.run("kio_extract.api:create_app", factory=True, host="127.0.0.1", port=8000)
