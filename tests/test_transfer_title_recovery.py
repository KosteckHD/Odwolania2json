from pathlib import Path

from kio_extract.contracts import ExtractedDocument, PageText
from kio_extract.processing import add_account_fragments, needs_account_recovery, recover_repeated_transfer_title, recover_transfer_accounts
from evaluation.prompt_regression import MISSING, lookup


def document(text):
    return ExtractedDocument(Path("synthetic.pdf"), (PageText(1, text),))


def test_repeated_reference_is_restored_only_from_title_section():
    data = {"przelew_bankowy": {"tytul": "Wpis w sprawie ABC"}}
    text = "Tytuł przelewu\nWpis w sprawie ABC\nNUMER-123\nNumer referencyjny\nNUMER-123\nStatus\nZREALIZOWANO"
    assert recover_repeated_transfer_title(data, document(text))["przelew_bankowy"]["tytul"] == "Wpis w sprawie ABC NUMER-123"
    assert data["przelew_bankowy"]["tytul"] == "Wpis w sprawie ABC"


def test_unrelated_or_ambiguous_reference_does_not_change_title():
    data = {"przelew_bankowy": {"tytul": "Wpis w sprawie ABC"}}
    samples = [
        "Tytuł przelewu\nWpis w sprawie ABC\nNumer referencyjny\nNUMER-123",
        "Tytuł przelewu\nWpis w sprawie ABC\nINNY\nNumer referencyjny\nNUMER-123",
        "Tytuł przelewu\nWpis w sprawie ABC\nNUMER-123\nStatus\nNumer referencyjny\nNUMER-123",
    ]
    for text in samples:
        assert recover_repeated_transfer_title(data, document(text)) == data
    duplicated = "Tytuł przelewu\nWpis w sprawie ABC\nNUMER-123\nNumer referencyjny\nNUMER-123\n"
    assert recover_repeated_transfer_title(data, document(duplicated * 2)) == data


def test_regression_checks_distinguish_missing_from_null():
    assert lookup({"data": {"date": None}}, "data.date") is None
    assert lookup({"data": {}}, "data.date") is MISSING


def test_recovers_truncated_account_from_correct_label():
    source = "Dane nadawcy\nPL62 2170 0008 9152 5017 5661 7062\nDane odbiorcy\n60 1010 1010 0081 3622 3100 0000"
    data = {"przelew_bankowy": {"z_rachunku": "6221700008915250175661706", "na_rachunek": "6010101010008136223100000"}}
    assert recover_transfer_accounts(data, document(source))["przelew_bankowy"] == {
        "z_rachunku": "62217000089152501756617062", "na_rachunek": "60101010100081362231000000"}


def test_never_guesses_missing_or_ambiguous_accounts():
    data = {"przelew_bankowy": {"z_rachunku": "6010101010008136223100000", "na_rachunek": None}}
    texts = ["Dane odbiorcy\n60 1010 1010 0081 3622 3100 0000",
             "Dane nadawcy\n60 1010 1010 0081 3622 3100 0000\n60 1010 1010 0081 3622 3100 0001",
             "Dane nadawcy\n60 1010 1010 0081 3622 3100 1111"]
    for text in texts:
        assert recover_transfer_accounts(data, document(text)) == data


def test_does_not_complete_account_from_ocr_candidate_with_bad_checksum():
    data = {"przelew_bankowy": {"z_rachunku": "6221700008915250175661706", "na_rachunek": None}}
    source = "Dane nadawcy\nPL62 2170 0008 9152 5017 5661 7063"
    assert recover_transfer_accounts(data, document(source)) == data


def test_supplemental_account_ocr_is_added_only_to_pages_ocr_processed(tmp_path, monkeypatch):
    account = "61109010140000071219812874"
    source = ExtractedDocument(
        tmp_path / "scan.pdf",
        (PageText(1, "Page with selectable text."), PageText(2, "Dane nadawcy\n6110901014000007121981287")),
        used_ocr=True,
        ocr_pages=(2,),
    )
    seen_pages = []

    def account_ocr(path, page_number):
        seen_pages.append((path, page_number))
        return {"z_rachunku": (account,)}

    monkeypatch.setattr("kio_extract.processing.tesseract_account_fragments", account_ocr)
    augmented = add_account_fragments(source)
    data = {"przelew_bankowy": {"z_rachunku": account[:-1], "na_rachunek": None}}

    assert seen_pages == [(source.source_path, 2)]
    assert source.pages[1].text == "Dane nadawcy\n6110901014000007121981287"
    assert recover_transfer_accounts(data, augmented)["przelew_bankowy"]["z_rachunku"] == account


def test_recovers_missing_control_digits_only_from_matching_labeled_account():
    data = {"przelew_bankowy": {"z_rachunku": "217000089152501756617062", "na_rachunek": None}}
    result = recover_transfer_accounts(data, document("Nadawca\nPL62 2170 0008 9152 5017 5661 7062"))
    assert result["przelew_bankowy"]["z_rachunku"] == "62217000089152501756617062"
    assert recover_transfer_accounts(data, document("Odbiorca\nPL62 2170 0008 9152 5017 5661 7062")) == data


def test_corrects_one_bad_digit_using_one_valid_source_but_never_overwrites_valid_account():
    good = "78102054608954694416566599"
    bad = "78102054608954694416566590"
    source = document(f"Dane nadawcy\n{bad}\nDane nadawcy\n{good}")
    data = {"przelew_bankowy": {"z_rachunku": bad, "na_rachunek": None}}
    assert recover_transfer_accounts(data, source)["przelew_bankowy"]["z_rachunku"] == good
    valid = {"przelew_bankowy": {"z_rachunku": "61109010140000071219812874", "na_rachunek": None}}
    assert recover_transfer_accounts(valid, source) == valid
    ambiguous = document(f"Dane nadawcy\n{bad}\n{good}\n61109010140000071219812874")
    assert recover_transfer_accounts(data, ambiguous) == data


def test_recovery_is_triggered_for_recipient_with_invalid_checksum():
    data = {"przelew_bankowy": {"z_rachunku": None, "na_rachunek": "25103015089436503556221675"}}
    assert needs_account_recovery(data)
    text = "Dane zleceniodawcy\n11124011119078857050000455\nDane kontrahenta\n25103015089436503556221675\nDane odbiorcy\n25103015089486503556221675"
    assert recover_transfer_accounts(data, document(text))["przelew_bankowy"]["na_rachunek"] == "25103015089486503556221675"
