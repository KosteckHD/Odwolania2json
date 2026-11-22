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


CLASSIFY = {
    "classify_by_patterns": [{
        "field": "sprawa.powod_id",
        "segments": [r"(?i)w dniu \d+ (?P<segment>[^.]+)\.", r"(?i)zarzut 1: (?P<segment>[^;]+);"],
        "classes": [
            {"value": 7, "patterns": [r"(?i)zaniechani\w* odrzucenia"]},
            {"value": 1, "patterns": [r"(?i)odrzuc\w*"]},
            {"value": 2, "patterns": [r"(?i)wyb[oó]r\w*"]},
        ],
    }],
    "derive": [{"field": "sprawa.powod_opis", "source": "sprawa.powod_id", "option": "powody"}],
}


def powod(text, model=2, rules=CLASSIFY):
    value = data(sprawa={"powod_id": model, "powod_opis": None, "dzien": None, "numer": None})
    return postprocess(value, document(text), config(rules))["sprawa"]


def test_classify_overrides_model_when_segments_agree_and_derive_follows():
    result = powod("Zamawiający w dniu 5 odrzucił ofertę. Zarzut 1: odrzucenia oferty;")
    assert result == {"powod_id": 1, "powod_opis": "Odrzucenie oferty", "dzien": None, "numer": None}


def test_classify_earlier_class_consumes_words_of_later_one():
    assert powod("w dniu 5 zaniechania odrzucenia oferty.", model=1)["powod_id"] == 7


def test_classify_keeps_model_on_conflict_ambiguity_or_no_match():
    assert powod("w dniu 5 odrzucił ofertę. Zarzut 1: wyboru oferty;", model=None)["powod_id"] is None
    assert powod("w dniu 5 odrzucił ofertę i dokonał wyboru.", model=2)["powod_id"] == 2
    assert powod("Zwykły tekst bez czynności.", model=2)["powod_id"] == 2


def test_classify_min_votes_and_fill_mode():
    rules = {**CLASSIFY, "classify_by_patterns": [{**CLASSIFY["classify_by_patterns"][0], "min_votes": 2}]}
    assert powod("w dniu 5 odrzucił ofertę.", rules=rules)["powod_id"] == 2
    assert powod("w dniu 5 odrzucił ofertę. Zarzut 1: odrzucenia;", rules=rules)["powod_id"] == 1
    fill = {**CLASSIFY, "classify_by_patterns": [{**CLASSIFY["classify_by_patterns"][0], "mode": "fill"}]}
    assert powod("w dniu 5 odrzucił ofertę.", rules=fill)["powod_id"] == 2
    assert powod("w dniu 5 odrzucił ofertę.", model=None, rules=fill)["powod_id"] == 1


@pytest.mark.parametrize("rule", [
    {"field": "sprawa.powod_id", "segments": ["(?P<x>a)"], "classes": [{"value": 1, "patterns": ["a"]}]},
    {"field": "sprawa.powod_id", "segments": ["(?P<segment>a)"], "classes": []},
    {"field": "sprawa.powod_id", "segments": ["(?P<segment>a)"], "classes": [{"value": 1}]},
    {"field": "sprawa.powod_id", "segments": ["(?P<segment>a)"], "classes": [{"value": 1, "patterns": ["a"]}], "mode": "zle"},
    {"field": "sprawa.powod_id", "segments": ["(?P<segment>a)"], "classes": [{"value": 1, "patterns": ["a"]}], "min_votes": 0},
    {"field": "strony", "segments": ["(?P<segment>a)"], "classes": [{"value": 1, "patterns": ["a"]}]},
])
def test_invalid_classify_configuration_is_rejected(rule):
    with pytest.raises(ConfigurationError):
        validate_postprocess({"classify_by_patterns": [rule]}, SCHEMA, OPTIONS)


@pytest.mark.parametrize(("text", "model", "expected"), [
    # Pierwszy punkt listy, zdanie o czynności i pierwszy zarzut zgodne: reguła poprawia model.
    ("wnoszę odwołanie wobec czynności i zaniechań Zamawiającego, polegających na: 1) zaniechaniu "
     "wykluczenia wykonawcy X sp. z o.o.; 2) wyborze oferty X jako najkorzystniejszej; Zamawiający w dniu "
     "3 marca 2026 roku przekazał informację o wyniku postępowania. Zarzut nr 1 – zaniechania wykluczenia "
     "wykonawcy, tj. naruszenie art. 109 Pzp;", 2, 8),
    ("Zamawiający w dniu 4 kwietnia 2026 roku zmodyfikował treść Specyfikacji Warunków Zamówienia. Dalej.", 4, 5),
    ("Zamawiający w dniu 9 marca 2026 roku przekazał wykonawcom odpowiedzi i wyjaśnienia do treści SWZ. Dalej.", 4, 6),
    ("Zamawiający w dniu 2 sierpnia 2026 roku zaniechał unieważnienia postępowania. Dalej.", 9, 10),
    ("Zamawiający w dniu 2 sierpnia 2026 roku nie odrzucił oferty wykonawcy X. Dalej.", 1, 7),
    # Sprzeczne fragmenty (pierwszy punkt: odrzucenie, zdanie: wybór) — zostaje model.
    ("polegających na: 1) odrzuceniu oferty Odwołującego; Zamawiający w dniu 1 maja 2026 r. dokonał wyboru "
     "oferty najkorzystniejszej. Dalej.", 11, 11),
    # Zdanie bez rozpoznawalnej czynności — zostaje model.
    ("Zamawiający w dniu 1 maja 2026 r. wszczął postępowanie. Dalej.", 3, 3),
])
def test_repository_powod_rule(text, model, expected):
    from kio_extract.schema_registry import load_configs
    root = Path(__file__).resolve().parents[1]
    odwolanie = load_configs(root / "configs" / "documents", root / "schemas")["odwolanie"]
    value = {"OdwolanieKIO": {"data": None, "czynnosc_dzien": None, "czynnosc_powod_id": model,
                              "czynnosc_opis": None, "miejscowosc": None}}
    result = postprocess(value, document(text), odwolanie)["OdwolanieKIO"]
    assert result["czynnosc_powod_id"] == expected
    assert result["czynnosc_opis"] == odwolanie.options["czynnosc_powod_opisy"][str(expected)]
