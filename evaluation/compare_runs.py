"""Stabilność: porównanie dwóch przebiegów pole po polu (model przy temperaturze 0 nie jest w pełni deterministyczny).

    .venv/Scripts/python.exe evaluation/compare_runs.py A/output B/output [--reference dane/] [--type odwolanie]
    .venv/Scripts/python.exe evaluation/compare_runs.py rawA rawB --raw   # zrzuty LLM_RAW_DUMP_DIR (przed regułami)

Wypisuje pola o różnych wartościach (z wartością wzorcową, jeśli podano --reference) i licznik różnic na pole.
Kolejność kluczy nie ma znaczenia; listy porównywane są po pozycji; pliki obecne tylko w jednym przebiegu są pomijane.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path


def flat(value, path=""):
    out = {}
    if isinstance(value, dict):
        for key, item in value.items():
            out.update(flat(item, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        out[f"{path}#len"] = len(value)
        for index, item in enumerate(value):
            out.update(flat(item, f"{path}[{index}]"))
    else:
        out[path] = value
    return out


def documents(folder: Path, raw: bool, kind: str | None):
    """{(sprawa, plik): dane} z katalogu wyjścia CLI albo ze zrzutu surowych odpowiedzi."""
    found = {}
    for path in sorted(folder.glob("*.json" if raw else "*/*.json")):
        case, name = path.stem.split("__", 1) if raw else (path.parent.name, path.stem)
        if kind and name != kind:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        found[(case, name)] = data.get("dane") if raw and isinstance(data, dict) else data
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--reference", type=Path, help="Katalog dane/ z wzorcami (<sprawa>/<plik>.json)")
    parser.add_argument("--type", dest="kind", help="Tylko pliki o tej nazwie, np. odwolanie")
    parser.add_argument("--raw", action="store_true", help="Katalogi to zrzuty LLM_RAW_DUMP_DIR")
    args = parser.parse_args()

    first, second = documents(args.first, args.raw, args.kind), documents(args.second, args.raw, args.kind)
    per_field, changed = Counter(), 0
    common = sorted(set(first) & set(second))
    missing = len(set(first) ^ set(second))
    for key in common:
        a, b = flat(first.get(key) or {}), flat(second.get(key) or {})
        reference = {}
        if args.reference and (path := args.reference / key[0] / f"{key[1]}.json").is_file():
            reference = flat(json.loads(path.read_text(encoding="utf-8")))
        diffs = [field for field in sorted(set(a) | set(b)) if a.get(field) != b.get(field)]
        changed += bool(diffs)
        for field in diffs:
            per_field[re.sub(r"\[\d+\]", "[]", f"{key[1]}:{field}")] += 1
            print(f"{key[0]}/{key[1]} {field}: A={a.get(field)!r} B={b.get(field)!r} wzorzec={reference.get(field, '-')!r}")
    print(f"\ndokumenty z różnicą: {changed}/{len(common)}, różnych pól: {sum(per_field.values())}"
          + (f" (pominięte, tylko w jednym przebiegu: {missing})" if missing else ""))
    for field, count in per_field.most_common():
        print(f"  {count:3d} {field}")


if __name__ == "__main__":
    main()
