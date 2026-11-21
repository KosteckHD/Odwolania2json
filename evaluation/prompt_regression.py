"""Run small synthetic field-level regression cases through the configured LLM."""
import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kio_extract.contracts import DocumentError, ExtractedDocument, PageText
from kio_extract.processing import normalize_result
from kio_extract.prompt_extraction import PromptExtractor
from kio_extract.providers.config import client_from_environment
from kio_extract.schema_registry import load_configs


def lookup(data, path):
    current = data
    try:
        for item in path.split("."):
            current = current[int(item)] if isinstance(current, list) else current[item]
        return current
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=Path, default=ROOT / "prompts/system_pl.md")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    configs = load_configs(ROOT / "configs/documents", ROOT / "schemas")
    client = client_from_environment()
    extractor = PromptExtractor(client, tuple(configs.values()), args.prompt)
    cases = json.loads((ROOT / "evaluation/prompt_cases.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        started = time.monotonic()
        client.last_usage = None
        try:
            doc = ExtractedDocument(Path("synthetic.pdf"), (PageText(1, case["text"]),))
            classification, data = extractor.extract(doc)
            if classification.doc_type != "unknown":
                schema = configs[classification.doc_type].schema
                data = normalize_result(data, schema)
                Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(data)
            checks = {path: lookup(data, path) == value for path, value in case["checks"].items()}
            result = {"id": case["id"], "expected_type": case["type"], "actual_type": classification.doc_type,
                      "checks": checks, "passed": classification.doc_type == case["type"] and all(checks.values())}
        except Exception as exc:
            code = exc.code if isinstance(exc, DocumentError) else type(exc).__name__
            result = {"id": case["id"], "passed": False, "error": code}
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        if client.last_usage:
            result["usage"] = client.last_usage
        results.append(result)
        print(case["id"], "PASS" if result["passed"] else "FAIL", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"cases": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return int(not all(result["passed"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
