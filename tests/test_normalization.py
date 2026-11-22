from kio_extract.normalization import normalize_bzp, normalize_polish_bank_account, normalize_ted


def test_bank_account_keeps_document_form_without_spaces():
    # UZP 21.11: numer jak w dokumencie, także z przedrostkiem „PL”; zera wiodące zostają
    account = "00123456789012345678901234"
    assert normalize_polish_bank_account("PL" + account) == "PL" + account
    assert normalize_polish_bank_account("pl00 1234 5678 9012 3456 7890 1234") == "PL" + account
    assert normalize_polish_bank_account("00 1234 5678 9012 3456 7890 1234") == account
    assert normalize_polish_bank_account("DE" + account) == "DE" + account
    assert normalize_polish_bank_account("PL123") == "PL123"


def test_bzp_number_matches_reference_format():
    assert normalize_bzp("2025/BZP 00143067/01") == "2025/BZP00143067/01"
    assert normalize_bzp("2025 / bzp 00518466") == "2025/BZP00518466"
    assert normalize_bzp("2025/BZP00518466") == "2025/BZP00518466"
    assert normalize_bzp("BZP 00518466") == "BZP 00518466"
    assert normalize_bzp("2025/BZP 0051846") == "2025/BZP 0051846"


def test_ted_normalization_ignores_newlines_and_preserves_number():
    assert normalize_ted("2026/S\n160-999682") == "999682-2026"
    assert normalize_ted("2026/S 061-999408") == "999408-2026"
    assert normalize_ted("2026-S086-999073") == "999073-2026"
    assert normalize_ted("2026-086-999073") == "2026-086-999073"
    assert normalize_ted("160999682-2026") == "160999682-2026"
    assert normalize_ted("123456-2026") == "123456-2026"


def test_ted_normalization_rejects_old_national_notice_number():
    assert normalize_ted("594737-N-2020") is None
    assert normalize_ted("594737 - N - 2020") is None
