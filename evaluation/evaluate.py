"""Compare saved predictions with explicitly listed reference documents."""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CLASSES = ("odwolanie", "pelnomocnictwo", "przelew")
IDENTIFIERS = ("krs", "nip", "regon", "pesel", "nazwa", "imie_nazwisko")
# Zasady oceny UZP (Discord, 21.11):
# - „długie stringi” liczone jako zgodne przy co najmniej 80% podobieństwa,
# - błędna wartość to jeden FP (nie FP + FN), brak wartości przy wypełnionym wzorcu to FN,
# - rachunek: numer jak w dokumencie; brak „PL” w części wzorców treningowych to błąd wzorca.
LONG_STRINGS = {"Odwolujacy[].nazwa", "Zamawiajacy[].nazwa", "Odwolujacy[].pelnomocnik.nazwa",
                "przelew_bankowy.tytul", "ZamowieniePubliczne.tytul"}
LONG_STRING_THRESHOLD = 0.8
ACCOUNT_FIELDS = ("na_rachunek", "z_rachunku")


def identities(value):
    if not isinstance(value, dict):
        return {}
    fields = value.get("data", value)
    if not isinstance(fields, dict):
        return {}
    return {key: str(fields[key]).strip().casefold() for key in IDENTIFIERS
            if fields.get(key) is not None and str(fields[key]).strip()}


def scalars(value, path=""):
    result = Counter()
    if isinstance(value, dict):
        for key, item in value.items():
            result.update(scalars(item, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for item in value:
            result.update(scalars(item, path + "[]"))
    elif value is not None and value != "":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric = format(value, ".15g")
            result[(path, "number", numeric)] += 1
        else:
            result[(path, type(value).__name__, json.dumps(value, ensure_ascii=False))] += 1
    return result


def compare(expected, predicted, path="", mode="uzp"):
    """Match list objects by unique identity and compare remaining values as multisets.

    `mode="uzp"` stosuje zasady oceny UZP, `mode="strict"` to dawny ścisły F1 (błąd = FP + FN).
    """
    counts = defaultdict(Counter)
    if isinstance(expected, dict) and isinstance(predicted, dict):
        for key in expected.keys() | predicted.keys():
            child = f"{path}.{key}" if path else key
            merge(counts, compare(expected.get(key), predicted.get(key), child, mode))
    elif isinstance(expected, list) and isinstance(predicted, list):
        left = [identities(item) for item in expected]
        right = [identities(item) for item in predicted]
        matched = set()
        paired = {}
        for field in IDENTIFIERS:
            for index, keys in enumerate(left):
                key = keys.get(field)
                if index in paired or key is None:
                    continue
                candidates = [other for other, values in enumerate(right)
                              if other not in matched and values.get(field) == key]
                if len(candidates) != 1 or sum(values.get(field) == key for values in left) != 1:
                    continue
                other = candidates[0]
                # Reject a name-based match when both records have conflicting identifiers.
                if any(keys.get(k) and right[other].get(k) and keys[k] != right[other][k]
                       for k in ("krs", "nip", "regon", "pesel")):
                    continue
                paired[index] = other
                matched.add(other)
        remaining = []
        for index, item in enumerate(expected):
            if index in paired:
                merge(counts, compare(item, predicted[paired[index]], path + "[]", mode))
            else:
                remaining.append(item)
        merge(counts, compare_multisets(scalars(remaining, path),
                                         scalars([item for index, item in enumerate(predicted) if index not in matched], path),
                                         mode))
    else:
        merge(counts, compare_multisets(scalars(expected, path), scalars(predicted, path), mode))
    return counts


def canonical(path, kind, raw):
    """Postać do porównań: rachunek bez „PL”, PESEL jako 11 cyfr bez względu na typ JSON."""
    field = path.rsplit(".", 1)[-1]
    value = json.loads(raw)
    if field in ACCOUNT_FIELDS and isinstance(value, str):
        compact = re.sub(r"\s", "", value).upper()
        return ("account", compact[2:] if re.fullmatch(r"PL[0-9]{26}", compact) else compact)
    if field == "pesel" and str(value).isdigit():
        return ("pesel", str(value).zfill(11))
    return (kind, raw)


def similar(left, right):
    norm = lambda text: " ".join(str(text).split()).casefold()
    return SequenceMatcher(None, norm(left), norm(right)).ratio() >= LONG_STRING_THRESHOLD


def compare_multisets(expected, predicted, mode="uzp"):
    counts = defaultdict(Counter)
    if mode == "strict":
        for item in expected.keys() | predicted.keys():
            path = item[0]
            common = min(expected[item], predicted[item])
            counts[path].update({"tp": common, "fn": expected[item] - common, "fp": predicted[item] - common})
        return counts
    by_path = defaultdict(lambda: ([], []))
    for side, values in ((0, expected), (1, predicted)):
        for (path, kind, raw), number in values.items():
            by_path[path][side].extend([canonical(path, kind, raw)] * number)
    for path, (left, right) in by_path.items():
        pool = Counter(right)
        unmatched = []
        tp = 0
        for value in left:
            if pool[value]:
                pool[value] -= 1
                tp += 1
            else:
                unmatched.append(value)
        rest = list(pool.elements())
        if path in LONG_STRINGS:
            still = []
            for value in unmatched:
                hit = next((i for i, other in enumerate(rest) if similar(json.loads(value[1]), json.loads(other[1]))), None)
                if hit is None:
                    still.append(value)
                else:
                    rest.pop(hit)
                    tp += 1
            unmatched = still
        # UZP: błędna wartość = FP; brak wartości = FN
        counts[path].update({"tp": tp, "fp": len(rest), "fn": max(0, len(unmatched) - len(rest))})
    return counts


def merge(target, source):
    for key, value in source.items():
        target[key].update(value)


def metrics(counter):
    tp, fp, fn = (counter[key] for key in ("tp", "fp", "fn"))
    denominator = 2 * tp + fp + fn
    return {"tp": tp, "fp": fp, "fn": fn, "f1": 2 * tp / denominator if denominator else None}


def read_json(path):
    text = path.read_text(encoding="utf-8-sig").strip()
    return json.loads(text) if text else None


def evaluate(manifest, data_dir, prediction_dir, split, metadata=None, run_report=None, mode="uzp"):
    schemas = {kind: Draft202012Validator(json.loads((ROOT / "schemas" / f"{kind}.schema.json").read_text(encoding="utf-8")),
                                          format_checker=Draft202012Validator.FORMAT_CHECKER) for kind in CLASSES}
    fields = defaultdict(Counter)
    types = defaultdict(Counter)
    matrix = defaultdict(Counter)
    errors = Counter()
    run_entries = None
    if run_report is not None:
        run_entries = {}
        for entry in run_report["documents"]:
            output = entry["output"]
            if output in run_entries:
                raise ValueError("Raport przebiegu zawiera zduplikowaną ścieżkę wyniku")
            run_entries[output] = entry
    used = {(prediction_dir / item["prediction"]).resolve() for item in manifest["documents"]}
    for item in manifest["documents"]:
        if item["split"] != split:
            continue
        kind = item["type"]
        expected = read_json(data_dir / item["reference"]) if item.get("reference") else None
        path = prediction_dir / item["prediction"]
        predicted = None
        status = "unknown"
        run_entry = run_entries.get(item["prediction"]) if run_entries is not None else None
        if run_entries is not None and run_entry is None:
            status = "not_processed"
        elif run_entry is not None and run_entry["status"] == "error":
            status = "processing_error"
            errors[f"processing_{run_entry.get('code', 'unknown')}"] += 1
        elif not path.is_file():
            status = "missing"
        elif run_entry is not None and hashlib.sha256(path.read_bytes()).hexdigest() != run_entry.get("sha256"):
            status = "output_changed"
        else:
            try:
                predicted = read_json(path)
                if predicted not in (None, {}):
                    matched = [name for name, validator in schemas.items() if validator.is_valid(predicted)]
                    status = matched[0] if len(matched) == 1 else "invalid_schema"
            except (ValueError, OSError):
                status = "invalid_json"
        matrix[kind][status] += 1
        if status in ("missing", "invalid_schema", "invalid_json", "not_processed", "processing_error", "output_changed"):
            errors[status] += 1
        if status not in (*CLASSES, "unknown"):
            predicted = None
        if status == "unknown":
            predicted = None
        differences = compare(expected, predicted, mode=mode)
        for field, values in differences.items():
            fields[(kind, field)].update(values)
            types[kind].update(values)
    extra = sum(path.resolve() not in used for path in prediction_dir.rglob("*.json"))
    total = Counter()
    for counter in types.values():
        total.update(counter)
    return {"split": split, "metadata": metadata or {}, "method": ("UZP rules: wrong value = FP, missing = FN, long strings >= 80% similar, account PL prefix ignored"
                       if mode == "uzp" else "local typed multiset F1; unique list identities matched first"),
            "overall": metrics(total), "types": {key: metrics(value) for key, value in sorted(types.items())},
            "fields": [{"type": kind, "field": field, **metrics(value)} for (kind, field), value in sorted(fields.items())],
            "classification": {key: dict(value) for key, value in sorted(matrix.items())},
            "negative_false_positives": sum(matrix["unknown"][kind] for kind in CLASSES),
            "errors": dict(errors), "extra_files": extra}


def main():
    parser = argparse.ArgumentParser(description="Local field-level F1 for saved outputs.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="unspecified")
    parser.add_argument("--revision", default="unspecified")
    parser.add_argument("--prompt-version", default="unspecified")
    parser.add_argument("--run-report", type=Path, help="Raport CLI z tego samego przebiegu")
    parser.add_argument("--strict", action="store_true", help="Dawny ścisły F1 (błędna wartość = FP + FN, bez podobieństwa tekstu)")
    args = parser.parse_args()
    try:
        manifest = read_json(args.manifest)
        run_report = read_json(args.run_report) if args.run_report else None
        report = evaluate(manifest, args.data, args.predictions, args.split,
                          {"model": args.model, "revision": args.revision, "prompt_version": args.prompt_version}, run_report,
                          mode="strict" if args.strict else "uzp")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Błąd ewaluacji: {exc}", file=sys.stderr)
        return 2
    print(f"Lokalny F1: {report['overall']['f1']}, raport: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
