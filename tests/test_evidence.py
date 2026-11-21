import json
from pathlib import Path

from fastapi.testclient import TestClient

from kio_extract.api import create_app
from kio_extract.cli import main
from kio_extract.contracts import Evidence, ExtractedDocument, PageText
from kio_extract.evidence import locate_evidence, mark_ocr
from kio_extract.processing import DocumentProcessor
from kio_extract.schema_registry import load_configs
from test_end_to_end import create_pdf


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = load_configs(ROOT / "configs/documents", ROOT / "schemas")
PROMPT = ROOT / "prompts/system_pl.md"
PRZELEW = ("Potwierdzenie wykonania przelewu", "Data operacji: 03.02.2026", "Kwota: 50,00 PLN")
LLM_PRZELEW = {"typ": "przelew", "dane": {"przelew_bankowy": {
    "data_operacji": "2026-02-03", "kwota": 50.0, "na_rachunek": None,
    "numer_transakcji": None, "tytul": "Oplata za odwolanie", "z_rachunku": None,
}}}


class StubLLM:
    model = "stub"

    def __init__(self, response):
        self.response = response

    def extract_json(self, *, instructions, text, schema):
        return json.loads(json.dumps(self.response))


def odwolanie_document():
    return ExtractedDocument(Path("odwolanie.pdf"), (
        PageText(1, "ODWOŁANIE\nZamawiający: Gmina Przykładowo\nOgłoszenie 2024/S 123-123456\n"
                    "Wiadomość z dnia 11.05.2024"),
        PageText(2, "Odwołujący: „Budex” Sp. z o.o.\nNIP: 123-456-78-90\nWarszawa, 10 maja 2024 r.\n"
                    "Wpis 7 500,00 zł"),
    ))


def test_values_are_found_on_their_pages_without_changing_data():
    schema = CONFIGS["odwolanie"].schema
    data = {
        "OdwolanieKIO": {"data": "2024-05-10", "czynnosc_dzien": None, "czynnosc_powod_id": 2,
                         "czynnosc_opis": "Streszczenie, którego nie ma w tekście", "miejscowosc": "Warszawa"},
        "Odwolujacy": [{"krs": None, "nazwa": "Budex Sp. z o.o.", "nip": "1234567890", "regon": None,
                        "przez-pelnomocnika": 0,
                        "pelnomocnik": {"imie_nazwisko": None, "nazwa": None, "mail": None}}],
        "Zamawiajacy": [{"krs": None, "nazwa": "Gmina Przykładowo", "nip": None, "regon": None,
                         "prowadzacy_postepowanie": 1}],
        "ZamowieniePubliczne": {"numer_bzp": None, "numer_postepowania": None,
                                "numer_ted": "123456-2024", "tytul": None},
    }
    before = json.dumps(data)
    evidence = locate_evidence(odwolanie_document(), data, schema, "llm+search")
    assert json.dumps(data) == before
    assert {item.field_path: item.page_number for item in evidence} == {
        "OdwolanieKIO.data": 2,          # „10 maja 2024”, nie „11.05.2024” ze strony 1
        "OdwolanieKIO.miejscowosc": 2,
        "Odwolujacy.0.nazwa": 2,
        "Odwolujacy.0.nip": 2,           # NIP z myślnikami w tekście
        "Zamawiajacy.0.nazwa": 1,
        "ZamowieniePubliczne.numer_ted": 1,
    }
    assert {item.method for item in evidence} == {"llm+search"}


def test_amounts_and_short_values():
    document = odwolanie_document()
    schema = {"type": "object", "properties": {
        "kwota": {"type": ["number", "null"]}, "inna": {"type": ["number", "null"]},
        "kod": {"type": ["integer", "null"]}, "pesel": {"type": "integer", "maximum": 99999999999},
    }}
    evidence = locate_evidence(document, {"kwota": 7500.0, "inna": 500.0, "kod": 2, "pesel": None}, schema, "llm")
    assert evidence == (Evidence("kwota", 2, "llm"),)
    pesel = ExtractedDocument(Path("p.pdf"), (PageText(1, "PESEL 01234567890"),))
    assert locate_evidence(pesel, {"pesel": 1234567890}, schema, "llm") == (Evidence("pesel", 1, "llm"),)


def test_ocr_pages_are_marked():
    evidence = (Evidence("a", 1, "regex"), Evidence("b", 2, "llm+search"))
    assert mark_ocr(evidence, (2,)) == (Evidence("a", 1, "regex"), Evidence("b", 2, "ocr+llm+search"))


def test_api_returns_rule_evidence(tmp_path):
    pdf = tmp_path / "input.pdf"
    create_pdf(pdf, PRZELEW)
    response = TestClient(create_app(DocumentProcessor(CONFIGS, PROMPT))).post(
        "/api/extract", files=[("files", ("test.pdf", pdf.read_bytes(), "application/pdf"))])
    result = response.json()["documents"][0]
    assert result["status"] == "ok"
    assert result["evidence"] == [
        {"field_path": "przelew_bankowy.data_operacji", "page_number": 1, "method": "regex"},
        {"field_path": "przelew_bankowy.kwota", "page_number": 1, "method": "regex"},
    ]


def test_api_returns_llm_evidence_and_same_data_as_process(tmp_path):
    pdf = tmp_path / "input.pdf"
    create_pdf(pdf, (*PRZELEW, "Tytul: Oplata za odwolanie"))
    processor = DocumentProcessor(CONFIGS, PROMPT, client=StubLLM(LLM_PRZELEW))
    result = TestClient(create_app(processor)).post(
        "/api/extract", files=[("files", ("test.pdf", pdf.read_bytes(), "application/pdf"))]).json()["documents"][0]
    assert result["data"] == processor.process(pdf)[1] == LLM_PRZELEW["dane"]
    assert {item["field_path"]: (item["page_number"], item["method"]) for item in result["evidence"]} == {
        "przelew_bankowy.data_operacji": (1, "llm+search"),
        "przelew_bankowy.kwota": (1, "llm+search"),
        "przelew_bankowy.tytul": (1, "llm+search"),
    }


def test_unknown_and_empty_evidence(tmp_path):
    pdf = tmp_path / "input.pdf"
    create_pdf(pdf, ("To jest instrukcja obslugi urzadzenia biurowego.",))
    unknown = DocumentProcessor(CONFIGS, PROMPT, client=StubLLM({"typ": "unknown", "dane": None}))
    entry = TestClient(create_app(unknown)).post(
        "/api/extract", files=[("files", ("a.pdf", pdf.read_bytes(), "application/pdf"))]).json()["documents"][0]
    assert entry["status"] == "unknown" and "evidence" not in entry
    empty = {"typ": "przelew", "dane": {"przelew_bankowy": dict.fromkeys(LLM_PRZELEW["dane"]["przelew_bankowy"])}}
    entry = TestClient(create_app(DocumentProcessor(CONFIGS, PROMPT, client=StubLLM(empty)))).post(
        "/api/extract", files=[("files", ("a.pdf", pdf.read_bytes(), "application/pdf"))]).json()["documents"][0]
    assert entry["status"] == "ok" and entry["evidence"] == []


def test_ocr_page_evidence_through_processor(tmp_path):
    pdf = tmp_path / "scan.pdf"
    create_pdf(pdf)
    processor = DocumentProcessor(CONFIGS, PROMPT, ocr=lambda path, page: "\n".join(PRZELEW))
    classification, data, evidence = processor.process_with_evidence(pdf)
    assert classification.doc_type == "przelew"
    assert {item.method for item in evidence} == {"ocr+regex"}


def test_cli_output_bytes_are_unchanged(tmp_path):
    input_dir, output_dir = tmp_path / "input", tmp_path / "output"
    create_pdf(input_dir / "sprawa" / "przelew.pdf", PRZELEW)
    assert main(["--input", str(input_dir), "--output", str(output_dir)]) == 0
    expected = (
        '{\n  "przelew_bankowy": {\n    "data_operacji": "2026-02-03",\n    "kwota": 50.0,\n'
        '    "na_rachunek": null,\n    "numer_transakcji": null,\n    "tytul": null,\n'
        '    "z_rachunku": null\n  }\n}\n'
    )
    assert (output_dir / "sprawa" / "przelew.json").read_text(encoding="utf-8") == expected
