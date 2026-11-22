"""Przebieg na skanach UZP (dane/skany/<grupa>/<nr>/<nr>.pdf + wzorcowy <nr>.json obok) i F1 jak w evaluate.py.

Przykład (Qwen3.5 9B w HostYourAI, klucz z QWEN_API_KEY w .env, po 3 skany z każdej grupy):
    .venv/Scripts/python.exe evaluation/scan_experiment.py --name skany-probka --ids 0001,0002,0003 \
        --skany C:/.../dane/skany --key-from QWEN_API_KEY \
        --set LLM_BASE_URL=https://hostyourai.com/api/v1 --set LLM_MODEL=Qwen/Qwen3.5-9B \
        --set "LLM_EXTRA_BODY={\"chat_template_kwargs\":{\"enable_thinking\":false}}" --set SCAN_MODE=transcribe

Wyniki: .local/skany/<nazwa>/ (wejście, wyjście CLI, raport przebiegu, raport F1). Klucz API nie jest wypisywany.
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
GROUPS = {"odwolania": "odwolanie", "pelnomocnictwa": "pelnomocnictwo", "potwierdzenia": "przelew"}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True)
    parser.add_argument("--skany", type=Path, required=True, help="Katalog dane/skany z repozytorium UZP")
    parser.add_argument("--ids", default="0001,0002,0003", help="Numery skanów (w każdej grupie)")
    parser.add_argument("--key-from", default=None)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--set", action="append", default=[], metavar="ZMIENNA=WARTOŚĆ")
    args = parser.parse_args()

    run = ROOT / ".local" / "skany" / args.name
    if run.exists():
        shutil.rmtree(run)
    documents = []
    for group, kind in GROUPS.items():
        for number in args.ids.split(","):
            target = run / "input" / group / number
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(args.skany / group / number / f"{number}.pdf", target / f"{number}.pdf")
            path = f"{group}/{number}/{number}.json"
            documents.append({"split": "skany", "type": kind, "prediction": path, "reference": path})
    (run / "manifest.json").write_text(json.dumps({"documents": documents}, indent=1), encoding="utf-8")

    env = os.environ.copy()
    if args.key_from:
        key = (dotenv_values(args.env_file).get(args.key_from) or "").strip()
        if not key:
            sys.exit(f"Brak {args.key_from} w .env")
        env["LLM_API_KEY"] = key
    for item in args.set:
        name, _, value = item.partition("=")
        env[name] = value
    env["PYTHONIOENCODING"] = "utf-8"

    started = time.monotonic()
    completed = subprocess.run([sys.executable, str(ROOT / "main.py"), "--llm", "--input", str(run / "input"),
                                "--output", str(run / "output"), "--report", str(run / "run.json")],
                               env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = time.monotonic() - started
    (run / "cli.log").write_text(completed.stdout + "\n--- stderr ---\n" + completed.stderr, encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "evaluation" / "evaluate.py"), "--manifest", str(run / "manifest.json"),
                    "--data", str(args.skany), "--predictions", str(run / "output"), "--split", "skany",
                    "--output", str(run / "eval.json"), "--run-report", str(run / "run.json")], check=True)
    report = json.loads((run / "eval.json").read_text(encoding="utf-8"))
    overall = report["overall"]
    types = " ".join(f"{kind}={value['f1']:.3f}" for kind, value in report["types"].items() if value["f1"] is not None)
    print(f"{args.name}: F1={overall['f1']:.4f} (TP {overall['tp']}, FP {overall['fp']}, FN {overall['fn']}) {types}")
    print(f"  czas {elapsed:.0f} s, błędy {report['errors']}")
    for entry in json.loads((run / "run.json").read_text(encoding="utf-8"))["documents"]:
        print(f"  {entry['source']:32s} {entry['status']:7s} {entry.get('fallback') or entry.get('code') or ''}"
              f" {entry['duration_seconds']:.0f} s")


if __name__ == "__main__":
    main()
