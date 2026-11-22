from pathlib import Path

import pytest

from kio_extract.contracts import ConfigurationError, DocumentConfig, ExtractedDocument, FieldRule, PageText
from kio_extract.normalization import normalize_date
from kio_extract.postprocess import postprocess, validate_postprocess


SCHEMA = {
    "type": "object",
    "properties": {
        "sprawa": {"type": "object", "properties": {
            "powod_id": {"type": ["integer", "null"]},
            "powod_opis": {"type": ["string", "null"]},
            "dzien": {"type": ["string", "null"]},
            "numer": {"type": ["string", "null"]},
        }},
        "strony": {"type": "array", "items": {"type": "object", "properties": {
            "osoba": {"type": ["string", "null"]},
            "kancelaria": {"type": ["string", "null"]},
            "mail": {"type": ["string", "null"]},
        }}},
    },
}
RULES = {
    "fill_missing": [
        {"field": "strony[].kancelaria", "pattern": r"(?i)adres:\s*(?P<value>Kancelaria[^,\n]+)",
         "requires": ["strony[].osoba"]},
        {"field": "strony[].mail", "pattern": r"(?i)adres:[^@]{0,200}?(?<![\w.])(?P<value>[\w.]+@[\w-]+(?:\.[\w-]+)+)",
         "requires": ["strony[].osoba"]},
        {"field": "sprawa.dzien", "pattern": r"w dniu (?P<value>[0-9]{1,2} \w+ [0-9]{4})", "normalize": "iso_date"},
    ],
    "snap_to_text": ["strony[].osoba"],
    "derive": [{"field": "sprawa.powod_opis", "source": "sprawa.powod_id", "option": "powody"}],
}
OPTIONS = {"powody": {"1": "Odrzucenie oferty", "2": "Wybór oferty"}}


def config(rules=RULES, fields=None):
    return DocumentConfig("test", SCHEMA, fields=fields or {}, options=OPTIONS,
                          postprocess=validate_postprocess(rules, SCHEMA, OPTIONS))


def document(*pages):
    return ExtractedDocument(Path("x.pdf"), tuple(PageText(i + 1, text) for i, text in enumerate(pages)))


def data(**overrides):
    value = {"sprawa": {"powod_id": None, "powod_opis": None, "dzien": None, "numer": None},
             "strony": [{"osoba": "Jan Nowak", "kancelaria": None, "mail": None}]}
    for key, item in overrides.items():
        value[key] = item
    return value


TEXT = "kontakt@urzad.example\nreprezentowana przez: adw. Jan Nowak\nadres: Kancelaria Nowak sp.k., ul. Polna 1\ntel. 000, biuro@nowak.example"


def test_fill_missing_uses_unique_match_and_never_overwrites_model():
    result = postprocess(data(), document(TEXT), config())
    assert result["strony"][0] == {"osoba": "Jan Nowak", "kancelaria": "Kancelaria Nowak sp.k.", "mail": "biuro@nowak.example"}
    model = data(strony=[{"osoba": "Jan Nowak", "kancelaria": "Inna", "mail": "a@b.example"}])
    assert postprocess(model, document(TEXT), config())["strony"][0]["kancelaria"] == "Inna"


def test_fill_missing_skips_when_required_field_missing_or_list_ambiguous():
    no_person = postprocess(data(strony=[{"osoba": None, "kancelaria": None, "mail": None}]), document(TEXT), config())
    assert no_person["strony"][0]["kancelaria"] is None
    two = [{"osoba": "Jan Nowak", "kancelaria": None, "mail": None}, {"osoba": "Ewa Lis", "kancelaria": None, "mail": None}]
    assert all(item["kancelaria"] is None for item in postprocess(data(strony=two), document(TEXT), config())["strony"])
    assert postprocess(data(strony=[]), document(TEXT), config())["strony"] == []


def test_fill_missing_skips_conflicting_matches():
    text = TEXT + "\nadres: Kancelaria Inna, ul. Leśna 2"
    assert postprocess(data(), document(text), config())["strony"][0]["kancelaria"] is None


def test_fill_missing_normalizes_polish_dates_and_uses_scalar_field_rules():
    rules = {"numer": FieldRule(r"(?im)^nr ref\.?\s*(?P<value>[A-Z0-9]+)$")}
    fields = {"sprawa.numer": rules["numer"]}
    result = postprocess(data(), document("Zamawiający w dniu 27 października 2026 roku", "Nr ref.\nCEN123"), config(fields=fields))
    assert result["sprawa"]["dzien"] == "2026-10-27"
    assert result["sprawa"]["numer"] == "CEN123"


def test_snap_to_text_restores_document_spelling_only_for_safe_variants():
    cases = {
        ("Dorota Zawadzka", "ustanawiam adw. Dorota Zawadzki"): "Dorota Zawadzki",
        ("Aleksander Jabłończyk", "adw. Aleksandra Jabłończyk"): "Aleksandra Jabłończyk",
        ("Klaudia Szymański", "adw. Klaudia Szymanski"): "Klaudia Szymanski",
        # odmiana przez przypadki (ostatnia litera) zostaje w mianowniku od modelu
        ("Anna Nowak", "pełnomocnikiem Anną Nowak"): "Anna Nowak",
        # wartość obecna w tekście: bez zmian
        ("Jan Kowalski", "Jan Kowalski oraz Jan Kowalska"): "Jan Kowalski",
        # dwa różne warianty: niejednoznaczne, bez zmian
        ("Jan Kowalsky", "Jan Kowalski i Jan Kowalska"): "Jan Kowalsky",
    }
    for (model, text), expected in cases.items():
        value = data(strony=[{"osoba": model, "kancelaria": "K", "mail": "m@x.example"}])
        assert postprocess(value, document(text), config())["strony"][0]["osoba"] == expected, model


def test_derive_sets_description_from_dictionary():
    value = data(sprawa={"powod_id": 2, "powod_opis": "Wybor ofert", "dzien": None, "numer": None})
    assert postprocess(value, document(""), config())["sprawa"]["powod_opis"] == "Wybór oferty"
    value = data(sprawa={"powod_id": None, "powod_opis": "coś", "dzien": None, "numer": None})
    assert postprocess(value, document(""), config())["sprawa"]["powod_opis"] is None


def test_null_when_single_clears_field_only_for_one_element_lists():
    rules = {"null_when_single": ["strony[].mail"]}
    one = data(strony=[{"osoba": "A", "kancelaria": None, "mail": "a@x.example"}])
    assert postprocess(one, document(""), config(rules))["strony"][0]["mail"] is None
    two = [{"osoba": "A", "kancelaria": None, "mail": "a@x.example"}, {"osoba": "B", "kancelaria": None, "mail": "b@x.example"}]
    assert [s["mail"] for s in postprocess(data(strony=two), document(""), config(rules))["strony"]] == ["a@x.example", "b@x.example"]
    with pytest.raises(ConfigurationError):
        validate_postprocess({"null_when_single": ["sprawa.numer"]}, SCHEMA, OPTIONS)


def test_postprocess_ignores_non_objects():
    assert postprocess(None, document(""), config()) is None


@pytest.mark.parametrize("rules", [
    {"nieznane": []},
    {"fill_missing": [{"field": "strony[].brak", "pattern": "(?P<value>x)"}]},
    {"fill_missing": [{"field": "strony", "pattern": "(?P<value>x)"}]},
    {"fill_missing": [{"field": "sprawa.numer", "pattern": "x"}]},
    {"fill_missing": [{"field": "sprawa.numer", "pattern": "(?P<value>x)", "normalize": "zle"}]},
    {"snap_to_text": ["sprawa.brak"]},
    {"derive": [{"field": "sprawa.powod_opis", "source": "sprawa.powod_id", "option": "brak"}]},
])
def test_invalid_postprocess_configuration_is_rejected(rules):
    with pytest.raises(ConfigurationError):
        validate_postprocess(rules, SCHEMA, OPTIONS)


def test_normalize_date_accepts_polish_month_names():
    assert normalize_date("3 marca 2026") == "2026-03-03"
    assert normalize_date("27 października\n2026 r.") == "2026-10-27"
    assert normalize_date("31 lutego 2026") is None
    assert normalize_date("3 marzec 2026") is None


def test_repository_configs_load_with_postprocess():
    from kio_extract.schema_registry import load_configs
    root = Path(__file__).resolve().parents[1]
    configs = load_configs(root / "configs" / "documents", root / "schemas")
    assert configs["odwolanie"].postprocess["derive"]
    assert configs["przelew"].postprocess["fill_missing"]
