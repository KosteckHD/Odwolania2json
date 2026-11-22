import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import NamedTemporaryFile

from .contracts import ConfigurationError, DocumentError
from .filesystem import output_paths
from .output import write_result
from .processing import DocumentProcessor
from .providers.config import client_from_environment
from .schema_registry import load_configs


ROOT = Path(__file__).resolve().parents[2]
LLM_SETTINGS = ("LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "API_KEY")


def llm_configured() -> bool:
    """Ta sama reguła co w API: model działa, gdy ustawiono którąkolwiek zmienną LLM."""
    return any(os.getenv(name, "").strip() for name in LLM_SETTINGS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Przetwarza PDF-y spraw KIO do plików JSON.")
    parser.add_argument("--input", type=Path, default=ROOT / "input")
    parser.add_argument("--output", type=Path, default=ROOT / "output")
    parser.add_argument("--configs", type=Path, default=ROOT / "configs" / "documents")
    parser.add_argument("--schemas", type=Path, default=ROOT / "schemas")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--llm", action="store_true",
                      help="Wymuś model językowy (domyślnie włączony, gdy .env lub środowisko go konfiguruje)")
    mode.add_argument("--rules", action="store_true", help="Tryb regułowy, bez modelu językowego")
    parser.add_argument("--prompt", type=Path, default=ROOT / "prompts" / "system_pl.md", help="Plik prompta trybu LLM")
    parser.add_argument("--negative-output", choices=("empty_object", "empty_file"), default="empty_object",
                        help="Wynik dla dokumentu spoza klas: plik z {} (domyślnie, wymóg UZP) albo pusty plik")
    parser.add_argument("--on-error", choices=("negative", "skip"), default="negative",
                        help="Dokument z błędem (np. nieczytelny PDF): zapisz wynik jak dla negatywu (domyślnie, "
                             "plik powstaje dla każdego PDF-u) albo pomiń plik")
    parser.add_argument("--report", type=Path, help="Zapisz raport bieżącego przebiegu poza katalogami input/output")
    args = parser.parse_args(argv)

    try:
        input_dir = args.input.resolve()
        output_dir = args.output.resolve()
        report_path = args.report.resolve() if args.report else None
        if report_path and (report_path.is_relative_to(input_dir) or report_path.is_relative_to(output_dir)):
            raise ConfigurationError("Raport musi znajdować się poza katalogami input i output")
        configs = load_configs(args.configs, args.schemas)
        use_llm = args.llm or (not args.rules and llm_configured())
        client = client_from_environment() if use_llm else None
        print(f"Tryb: {'model językowy ' + getattr(client, 'model', '') if client else 'regułowy (bez modelu)'}", file=sys.stderr)
        processor = DocumentProcessor(configs, args.prompt, client=client)
        jobs = output_paths(input_dir, output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    except (ConfigurationError, OSError) as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 2

    def process_one(source, destination):
        """Jeden PDF: wynik zapisany od razu po przetworzeniu (przy limicie czasu zostaje to, co gotowe)."""
        name = source.relative_to(input_dir)
        started = time.monotonic()
        output = destination.relative_to(output_dir).as_posix()
        if client is not None and hasattr(client, "last_usage"):
            client.last_usage = None
        try:
            classification, data = processor.process(source)
            kind = classification.doc_type
            write_result(destination, data, args.negative_output)
            digest = hashlib.sha256(destination.read_bytes()).hexdigest() if report_path else None
        except DocumentError as exc:
            entry = {"source": name.as_posix(), "output": output, "status": "error", "code": exc.code,
                     "duration_seconds": round(time.monotonic() - started, 3)}
            if args.on_error == "negative":
                # plik wyniku powstaje zawsze: brak pliku to utrata wszystkich pól, {} co najwyżej tyle samo
                try:
                    write_result(destination, None, args.negative_output)
                    entry["written"] = "negative"
                except OSError:
                    pass
            usage = getattr(client, "last_usage", None)
            if usage:
                entry["usage"] = usage
            return None, entry, f"{name}: {exc.code}: {exc}"
        except (OSError, ValueError):
            return None, {"source": name.as_posix(), "output": output, "status": "error", "code": "output_write",
                          "duration_seconds": round(time.monotonic() - started, 3)},                 f"{name}: output_write: błąd danych lub zapisu wyniku"
        entry = {"source": name.as_posix(), "output": output, "status": "unknown" if kind == "unknown" else "ok",
                 "type": kind, "sha256": digest, "duration_seconds": round(time.monotonic() - started, 3)}
        if classification.reason.startswith("fallback:"):
            entry["fallback"] = classification.reason.partition(":")[2]
        usage = getattr(client, "last_usage", None)
        if usage:
            entry["usage"] = usage
        return kind, entry, f"{name}: {kind} ({classification.reason})"

    counts: Counter[str] = Counter()
    failures = 0
    fallbacks = 0
    results = [None] * len(jobs)
    # z modelem PDF-y idą równolegle (LLM_CONCURRENCY), bez modelu po kolei
    workers = getattr(getattr(client, "rate_limit", None), "concurrency", 1) if client is not None else 1
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(process_one, source, destination): index for index, (source, destination) in enumerate(jobs)}
        for future in as_completed(futures):
            kind, entry, line = future.result()
            results[futures[future]] = entry
            if kind is None:
                failures += 1
                print(line, file=sys.stderr)
            else:
                counts[kind] += 1
                if "fallback" in entry:
                    fallbacks += 1
                    print(f"{line}: wynik awaryjny z reguł po błędzie modelu", file=sys.stderr)
                print(line)

    classes = ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items())) or "brak wyników"
    written = sum(1 for entry in results if entry and entry.get("written"))
    print(f"PDF={len(jobs)}, zapisano={sum(counts.values())}, awaryjne={fallbacks}, błędy={failures}"
          f" (z plikiem {{}}: {written}); {classes}")
    if report_path:
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=report_path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    stream.write((json.dumps({"documents": results}, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
                    stream.close()
                    temporary.replace(report_path)
                finally:
                    stream.close()
                    temporary.unlink(missing_ok=True)
        except OSError:
            print("Nie udało się zapisać raportu przebiegu", file=sys.stderr)
            return 1
    return 1 if failures else 0
