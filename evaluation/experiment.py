"""Jeden eksperyment: podzbiór danych UZP z manifestu -> CLI -> ewaluacja F1 (zasady UZP) -> wiersz w tabeli wyników.

Przykład (Qwen3.5 9B w HostYourAI, klucz z QWEN_API_KEY w .env):
    .venv/Scripts/python.exe evaluation/experiment.py --name baseline --split development \
        --data C:/.../hacknation-2026/dane --key-from QWEN_API_KEY \
        --set LLM_BASE_URL=https://hostyourai.com/api/v1 --set LLM_MODEL=Qwen/Qwen3.5-9B

Wyniki trafiają do .local/experiments/<nazwa>/ (wyjście CLI, raport przebiegu, raport F1)
oraz do .local/experiments/results.tsv. Klucz API nigdy nie jest wypisywany.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local" / "experiments"
ALIASES = {"potwierdzenie_przelewu": ("przelew",), "przelew": ("potwierdzenie_przelewu",)}


def build_input(manifest, data_dir, split, target):
    """Kopie PDF-ów danego podziału pod nazwami z manifestu (wynik ma nazwę oczekiwaną przez ewaluator)."""
    if target.exists():
        shutil.rmtree(target)
    count = 0
    for item in manifest["documents"]:
        if item["split"] != split:
            continue
        prediction = Path(item["prediction"])
        folder = data_dir / prediction.parent
        candidates = [prediction.stem, *ALIASES.get(prediction.stem, ())]
        source = next((folder / f"{stem}.pdf" for stem in candidates if (folder / f"{stem}.pdf").is_file()), None)
        if source is None:
            raise FileNotFoundError(f"Brak PDF dla {item['prediction']}")
        destination = target / prediction.with_suffix(".pdf")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        count += 1
    return count


def usage_totals(run_report):
    totals = {"prompt_tokens": 0, "completion_tokens": 0}
    for entry in run_report.get("documents", []):
        for key in totals:
            totals[key] += (entry.get("usage") or {}).get(key, 0)
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True)
    parser.add_argument("--split", default="development", choices=("development", "validation", "test"))
    parser.add_argument("--data", type=Path, required=True, help="Katalog dane/ z repozytorium UZP")
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation" / "manifest.json")
    parser.add_argument("--prompt", type=Path, default=ROOT / "prompts" / "system_pl.md")
    parser.add_argument("--configs", type=Path, default=ROOT / "configs" / "documents")
    parser.add_argument("--schemas", type=Path, default=ROOT / "schemas")
    parser.add_argument("--key-from", default=None, help="Nazwa zmiennej w .env z kluczem API (np. QWEN_API_KEY)")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env", help="Plik .env z kluczem (np. z głównej kopii repo)")
    parser.add_argument("--set", action="append", default=[], metavar="ZMIENNA=WARTOŚĆ",
                        help="Zmienna środowiskowa dla przebiegu (np. LLM_EXTRA_BODY=...)")
    parser.add_argument("--note", default="")
    parser.add_argument("--results", type=Path, default=WORK / "results.tsv",
                        help="Wspólna tabela wyników (np. w głównej kopii repo, żeby agenci widzieli swoje próby)")
    parser.add_argument("--agent", default="main", help="Kto robi eksperyment (kolumna w tabeli)")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    run_dir = WORK / args.name
    input_dir = WORK / f"_input-{args.split}"
    output_dir = run_dir / "output"
    if not input_dir.exists():
        print(f"Przygotowanie wejścia {args.split}: {build_input(manifest, args.data, args.split, input_dir)} PDF")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    if args.key_from:
        key = (dotenv_values(args.env_file).get(args.key_from) or "").strip()
        if not key:
            sys.exit(f"Brak {args.key_from} w .env")
        env["LLM_API_KEY"] = key
    for item in args.set:
        name, _, value = item.partition("=")
        env[name] = value
    env.setdefault("LLM_CONCURRENCY", "6")
    env.setdefault("LLM_REQUEST_INTERVAL_SECONDS", "0.15")

    started = time.monotonic()
    command = [sys.executable, str(ROOT / "main.py"), "--llm", "--input", str(input_dir), "--output", str(output_dir),
               "--prompt", str(args.prompt), "--configs", str(args.configs), "--schemas", str(args.schemas),
               "--report", str(run_dir / "run.json")]
    completed = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = time.monotonic() - started
    (run_dir / "cli.log").write_text(completed.stdout + "\n--- stderr ---\n" + completed.stderr, encoding="utf-8")

    evaluation = subprocess.run([sys.executable, str(ROOT / "evaluation" / "evaluate.py"), "--manifest", str(args.manifest),
                                 "--data", str(args.data), "--predictions", str(output_dir), "--split", args.split,
                                 "--output", str(run_dir / "eval.json"), "--run-report", str(run_dir / "run.json"),
                                 "--model", env.get("LLM_MODEL", "?"), "--prompt-version", args.prompt.name],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
    if evaluation.returncode:
        sys.exit(f"Ewaluacja nie powiodła się: {evaluation.stderr}")
    report = json.loads((run_dir / "eval.json").read_text(encoding="utf-8"))
    run_report = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    tokens = usage_totals(run_report)
    overall = report["overall"]
    types = " ".join(f"{kind}={value['f1']:.3f}" for kind, value in report["types"].items() if value["f1"] is not None)
    errors = report["errors"]
    print(f"{args.name}: F1={overall['f1']:.4f} (TP {overall['tp']}, FP {overall['fp']}, FN {overall['fn']}) {types}")
    print(f"  czas {elapsed:.0f} s, tokeny wej/wyj {tokens['prompt_tokens']}/{tokens['completion_tokens']}, błędy {errors}")
    worst = sorted((f for f in report["fields"] if f["f1"] is not None and (f["fp"] or f["fn"])),
                   key=lambda f: -(f["fp"] + f["fn"]))[:12]
    for field in worst:
        print(f"  {field['type']:15s} {field['field']:45s} F1={field['f1']:.2f} TP {field['tp']:3d} FP {field['fp']:3d} FN {field['fn']:3d}")

    table = args.results
    table.parent.mkdir(parents=True, exist_ok=True)
    if not table.exists():
        table.write_text("agent\tnazwa\tpodział\tF1\tTP\tFP\tFN\ttypy\tczas_s\ttokeny_wej\ttokeny_wyj\tbłędy\tnotatka\n", encoding="utf-8")
    with table.open("a", encoding="utf-8") as stream:
        stream.write(f"{args.agent}\t{args.name}\t{args.split}\t{overall['f1']:.4f}\t{overall['tp']}\t{overall['fp']}\t{overall['fn']}\t{types}"
                     f"\t{elapsed:.0f}\t{tokens['prompt_tokens']}\t{tokens['completion_tokens']}\t{json.dumps(errors)}\t{args.note}\n")


if __name__ == "__main__":
    main()
