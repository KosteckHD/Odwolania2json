from collections import Counter
import hashlib

import json

from evaluation.evaluate import compare, evaluate, metrics


def total_of(counts):
    total = Counter()
    for item in counts.values():
        total.update(item)
    return total


def test_list_matching_prevents_mixing_parties():
    expected = [{"nip": "001", "nazwa": "A"}, {"nip": "002", "nazwa": "B"}]
    reordered = [{"nip": "002", "nazwa": "B"}, {"nip": "001", "nazwa": "A"}]
    assert all(counts["fp"] == counts["fn"] == 0 for counts in compare(expected, reordered).values())
    swapped = [{"nip": "002", "nazwa": "A"}, {"nip": "001", "nazwa": "B"}]
    names = compare(expected, swapped)["[].nazwa"]
    # UZP: błędna wartość to jeden FP
    assert names["tp"] == 0 and names["fp"] == 2 and names["fn"] == 0
    strict = compare(expected, swapped, mode="strict")["[].nazwa"]
    assert strict["tp"] == 0 and strict["fp"] == strict["fn"] == 2


def test_missing_and_wrong_values_count_false_negatives_and_positives():
    expected, predicted = {"x": "001", "amount": 5}, {"x": "1", "amount": None}
    # UZP: wartość błędna (x) = FP, brak wartości (amount) = FN
    assert metrics(total_of(compare(expected, predicted))) == {"tp": 0, "fp": 1, "fn": 1, "f1": 0.0}
    assert metrics(total_of(compare(expected, predicted, mode="strict"))) == {"tp": 0, "fp": 1, "fn": 2, "f1": 0.0}
    # wartość tam, gdzie wzorzec ma null, to FP
    assert metrics(total_of(compare({"x": None}, {"x": "5"}))) == {"tp": 0, "fp": 1, "fn": 0, "f1": 0.0}


def test_long_strings_count_from_80_percent_similarity():
    expected = {"ZamowieniePubliczne": {"tytul": "Budowa drogi gminnej w miejscowości Kowale"},
                "przelew_bankowy": {"tytul": "WPIS OD ODWOŁANIA, ZAM: GMINA KOWALE"}}
    close = {"ZamowieniePubliczne": {"tytul": "Budowa drogi gminnej w miejscowosci Kowale."},
             "przelew_bankowy": {"tytul": "Wpis od odwołania zam: Gmina Kowale"}}
    assert total_of(compare(expected, close))["tp"] == 2
    far = {"ZamowieniePubliczne": {"tytul": "Dostawa sprzętu komputerowego"}, "przelew_bankowy": {"tytul": "Opłata"}}
    assert total_of(compare(expected, far)) == Counter({"fp": 2})
    # krótkie pola (np. numer postępowania) dalej wymagają pełnej zgodności
    assert compare({"a": {"numer": "ZP.1.2025"}}, {"a": {"numer": "ZP.1.2026"}})["a.numer"]["fp"] == 1


def test_account_prefix_and_pesel_type_do_not_change_the_score():
    expected = {"przelew_bankowy": {"na_rachunek": "60101010100081362231000000"}, "pesel": 85071204278}
    predicted = {"przelew_bankowy": {"na_rachunek": "PL60101010100081362231000000"}, "pesel": "85071204278"}
    assert total_of(compare(expected, predicted)) == Counter({"tp": 2})


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
