from collections import Counter
import hashlib

import json

from evaluation.evaluate import compare, evaluate, metrics
from evaluation.create_manifest import scan_documents


def test_scan_manifest_keeps_identical_names_in_distinct_classes(tmp_path):
    for category in ("odwolania", "pelnomocnictwa", "potwierdzenia"):
        scan = tmp_path / "skany" / category / "0001" / "0001.pdf"
        scan.parent.mkdir(parents=True)
        scan.touch()
        scan.with_suffix(".json").write_text("{}", encoding="utf-8")

    entries = list(scan_documents(tmp_path))
    assert {entry["type"] for entry in entries} == {"odwolanie", "pelnomocnictwo", "przelew"}
    assert len({entry["prediction"] for entry in entries}) == 3
    assert all(entry["split"] == "scans" and (tmp_path / entry["reference"]).is_file() for entry in entries)


def test_list_matching_prevents_mixing_parties():
    expected = [{"nip": "001", "nazwa": "A"}, {"nip": "002", "nazwa": "B"}]
    reordered = [{"nip": "002", "nazwa": "B"}, {"nip": "001", "nazwa": "A"}]
    assert all(counts["fp"] == counts["fn"] == 0 for counts in compare(expected, reordered).values())
    swapped = [{"nip": "002", "nazwa": "A"}, {"nip": "001", "nazwa": "B"}]
    names = compare(expected, swapped)["[].nazwa"]
    assert names["tp"] == 0 and names["fp"] == names["fn"] == 2


def test_missing_and_wrong_values_count_false_negatives_and_positives():
    counts = compare({"x": "001", "amount": 5}, {"x": "1", "amount": None})
    total = Counter()
    for item in counts.values():
        total.update(item)
    assert metrics(total) == {"tp": 0, "fp": 1, "fn": 2, "f1": 0.0}


def test_match_by_shared_identifier_and_equal_json_numbers():
    expected = [{"krs": "0001", "nip": "123", "nazwa": "A", "kwota": 10.0}]
    predicted = [{"krs": None, "nip": "123", "nazwa": "A", "kwota": 10}]
    counts = compare(expected, predicted)
    assert counts["[].nip"]["tp"] == 1
    assert counts["[].kwota"]["tp"] == 1
    assert counts["[].krs"]["fn"] == 1


def test_report_prevents_stale_and_modified_outputs_from_scoring(tmp_path):
    reference = {"przelew_bankowy": {"data_operacji": None, "kwota": 50, "na_rachunek": None,
                                    "numer_transakcji": None, "tytul": None, "z_rachunku": None}}
    data = tmp_path / "data"
    predictions = tmp_path / "predictions"
    data.mkdir()
    predictions.mkdir()
    (data / "reference.json").write_text(json.dumps(reference), encoding="utf-8")
    (predictions / "result.json").write_text(json.dumps(reference), encoding="utf-8")
    manifest = {"documents": [{"split": "validation", "type": "przelew", "reference": "reference.json",
                               "prediction": "result.json"}]}
    failed = {"documents": [{"output": "result.json", "status": "error", "code": "llm_rate_limit"}]}
    report = evaluate(manifest, data, predictions, "validation", run_report=failed)
    assert report["overall"]["tp"] == 0 and report["overall"]["fn"] == 1
    assert report["errors"]["processing_llm_rate_limit"] == 1

    modified = {"documents": [{"output": "result.json", "status": "ok", "sha256": "incorrect"}]}
    report = evaluate(manifest, data, predictions, "validation", run_report=modified)
    assert report["errors"]["output_changed"] == 1 and report["overall"]["tp"] == 0

    report = evaluate(manifest, data, predictions, "validation", run_report={"documents": []})
    assert report["errors"]["not_processed"] == 1 and report["overall"]["fn"] == 1

    digest = hashlib.sha256((predictions / "result.json").read_bytes()).hexdigest()
    valid = {"documents": [{"output": "result.json", "status": "ok", "sha256": digest}]}
    report = evaluate(manifest, data, predictions, "validation", run_report=valid)
    assert report["overall"]["tp"] == 1 and report["overall"]["f1"] == 1.0
