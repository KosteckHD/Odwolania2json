from kio_extract.normalization import normalize_polish_bank_account, normalize_ted


def test_polish_iban_is_normalized_without_losing_leading_zeroes():
    account = "00123456789012345678901234"
    assert normalize_polish_bank_account("PL" + account) == account
    assert normalize_polish_bank_account("PL00 1234 5678 9012 3456 7890 1234") == account
    assert normalize_polish_bank_account("DE" + account) == "DE" + account
    assert normalize_polish_bank_account("PL123") == "PL123"


def test_ted_normalization_ignores_newlines_and_preserves_number():
    assert normalize_ted("2026/S\n160-999682") == "999682-2026"
    assert normalize_ted("2026/S 061-999408") == "999408-2026"
    assert normalize_ted("2026-S086-999073") == "999073-2026"
    assert normalize_ted("2026-086-999073") == "2026-086-999073"
    assert normalize_ted("160999682-2026") == "160999682-2026"
    assert normalize_ted("123456-2026") == "123456-2026"
