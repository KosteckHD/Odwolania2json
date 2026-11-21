import argparse
import sys
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from .classifier import classify
from .contracts import ConfigurationError, DocumentError, JsonObject
from .extraction_engine import resolve_extractor
from .filesystem import output_paths
from .output import write_result
from .pdf_reader import extract_pdf
from .schema_registry import load_configs


ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Przetwarza PDF-y spraw KIO do plików JSON.")
    parser.add_argument("--input", type=Path, default=ROOT / "input")
    parser.add_argument("--output", type=Path, default=ROOT / "output")
    parser.add_argument("--configs", type=Path, default=ROOT / "configs" / "documents")
    parser.add_argument("--schemas", type=Path, default=ROOT / "schemas")
    parser.add_argument("--negative-output", choices=("empty_file", "empty_object"), default="empty_file")
    args = parser.parse_args(argv)

    try:
        input_dir = args.input.resolve()
        output_dir = args.output.resolve()
        configs = load_configs(args.configs, args.schemas)
        extractors = {key: resolve_extractor(config) for key, config in configs.items()}
        validators = {
            key: Draft202012Validator(config.schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
            for key, config in configs.items()
        }
        jobs = output_paths(input_dir, output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    except (ConfigurationError, OSError) as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 2

    all_configs = tuple(configs.values())
    counts: Counter[str] = Counter()
    failures = 0
    for source, destination in jobs:
        name = source.relative_to(input_dir)
        try:
            document = extract_pdf(source)
            if document.pages_needing_ocr:
                pages = ", ".join(map(str, document.pages_needing_ocr))
                raise DocumentError("ocr_required", f"Strony wymagające OCR: {pages}")
            classification = classify(document, all_configs)
            kind = classification.doc_type
            data: JsonObject | None = None
            if kind != "unknown":
                data = extractors[kind](document, configs[kind]).data
                error = next(validators[kind].iter_errors(data), None)
                if error is not None:
                    raise DocumentError("invalid_output", f"Naruszono schemat ({error.validator})")
            write_result(destination, data, args.negative_output)
        except DocumentError as exc:
            print(f"{name}: {exc.code}: {exc}", file=sys.stderr)
            failures += 1
            continue
        except (OSError, ValueError):
            print(f"{name}: output_write: błąd danych lub zapisu wyniku", file=sys.stderr)
            failures += 1
            continue
        counts[kind] += 1
        print(f"{name}: {kind} ({classification.reason})")

    classes = ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items())) or "brak wyników"
    print(f"PDF={len(jobs)}, zapisano={sum(counts.values())}, błędy={failures}; {classes}")
    return 1 if failures else 0
