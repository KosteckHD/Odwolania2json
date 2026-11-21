import json
from pathlib import Path
from types import SimpleNamespace

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from kio_extract.cli import main
from kio_extract.pdf_reader import extract_pdf
from kio_extract.providers import chat
from kio_extract.providers.rate_limit import RequestCoordinator


def create_pdf(path: Path, lines: tuple[str, ...] = ()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with PdfWriter() as writer:
        page = writer.add_blank_page(width=595, height=842)
        if lines:
            name = NameObject
            page[name("/Resources")] = DictionaryObject({name("/Font"): DictionaryObject({
                name("/F1"): DictionaryObject({name("/Type"): name("/Font"), name("/Subtype"): name("/Type1"),
                                               name("/BaseFont"): name("/Helvetica")}),
            })})
            content = "\n".join(f"({line}) Tj T*" for line in lines)
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 14 TL 40 780 Td\n{content}\nET".encode("ascii"))
            page.replace_contents(stream)
        writer.write(path)


def test_batch_writes_schema_output_and_preserves_names(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source = input_dir / "case1" / "nested" / "losowa.nazwa.PDF"
    positive = ("Potwierdzenie wykonania przelewu", "Data operacji: 03.02.2026", "Kwota: 1 234,50 PLN")
    create_pdf(source, positive)
    create_pdf(input_dir / "case1" / "odwolanie.pdf", ("To jest instrukcja obslugi urzadzenia biurowego.",))
    (input_dir / "case1" / "ignore.txt").touch()

    args = ["--input", str(input_dir), "--output", str(output_dir)]
    assert main(args) == 0
    result_path = output_dir / "case1" / "nested" / "losowa.nazwa.json"
    data = json.loads(result_path.read_bytes())
    assert data == {"przelew_bankowy": {
        "data_operacji": "2026-02-03", "kwota": 1234.5, "na_rachunek": None,
        "numer_transakcji": None, "tytul": None, "z_rachunku": None,
    }}
    negative = output_dir / "case1" / "odwolanie.json"
    assert negative.read_bytes() == b""
    assert len(list(output_dir.rglob("*.json"))) == 2
    first_run = result_path.read_bytes()

    assert main([*args, "--negative-output", "empty_object"]) == 0
    assert result_path.read_bytes() == first_run
    assert json.loads(negative.read_bytes()) == {}


def test_unreadable_files_continue_batch_and_ocr_is_injectable(tmp_path, capsys):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    source = input_dir / "case1" / "a_scan.pdf"
    create_pdf(source)
    (source.parent / "b_corrupt.pdf").write_bytes(b"This is not a PDF")
    create_pdf(source.parent / "c_negative.pdf", ("To jest instrukcja obslugi urzadzenia biurowego.",))

    calls = []

    def ocr(path, page_number):
        calls.append((path, page_number))
        return "Tekst odzyskany ze skanu"

    assert extract_pdf(source).pages_needing_ocr == (1,)
    recovered = extract_pdf(source, ocr=ocr)
    assert calls == [(source, 1)]
    assert recovered.used_ocr and recovered.pages_needing_ocr == ()

    assert main(["--input", str(input_dir), "--output", str(output_dir)]) == 1
    errors = capsys.readouterr().err
    assert "ocr_required" in errors and "pdf_read" in errors
    assert list((output_dir / "case1").iterdir()) == [output_dir / "case1" / "c_negative.json"]


def test_llm_batch_separates_instructions_and_checks_schema(tmp_path, monkeypatch, capsys):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    create_pdf(input_dir / "case1" / "a_odwolanie.pdf", ("Dokument testowy potwierdza wplate na rachunek.",))
    create_pdf(input_dir / "case1" / "b_przelew.pdf", ("Dokument nie dotyczy zadnego wniosku.",))
    create_pdf(input_dir / "case1" / "c_wadliwy.pdf", ("To jest transakcja o niepoprawnej odpowiedzi.",))

    payment = {"przelew_bankowy": {
        "data_operacji": "2026-02-03", "kwota": 50.0, "na_rachunek": "PL00123456789012345678901234",
        "numer_transakcji": None, "tytul": None, "z_rachunku": None,
    }}
    answers = iter([
        {"typ": "przelew", "dane": payment},
        {"typ": "unknown", "dane": None},
        {"typ": "przelew", "dane": {"przelew_bankowy": {"kwota": "brak danych"}}},
        {"typ": "przelew", "dane": {"przelew_bankowy": {"kwota": "brak danych"}}},
    ])
    requests = []

    class FakeConnection:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("localhost", 8765, 60)

        def request(self, method, path, *, body, headers):
            assert (method, path) == ("POST", "/v1/chat/completions")
            requests.append(json.loads(body))

        def getresponse(self):
            result = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(next(answers))}}]}
            return SimpleNamespace(status=200, read=lambda: json.dumps(result).encode("utf-8"))

        def close(self):
            pass

    monkeypatch.setattr(chat, "HTTPConnection", FakeConnection)
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8765/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    assert main(["--llm", "--input", str(input_dir), "--output", str(output_dir)]) == 1
    assert len(requests) == 4
    assert requests[0]["response_format"] == {"type": "json_object"}
    system, user = requests[0]["messages"]
    assert system["role"] == "system"
    assert "czynnosc_powod_opisy" in system["content"]
    assert "przelew_bankowy" in system["content"]
    assert "Dokument testowy" not in system["content"]
    assert user["role"] == "user"
    assert "potwierdza wplate" in json.loads(user["content"])["strony"][0]["tekst"]
    assert "a_odwolanie.pdf" not in user["content"]
    expected_payment = {"przelew_bankowy": {**payment["przelew_bankowy"], "na_rachunek": "00123456789012345678901234"}}
    assert json.loads((output_dir / "case1" / "a_odwolanie.json").read_bytes()) == expected_payment
    assert (output_dir / "case1" / "b_przelew.json").read_bytes() == b""
    assert not (output_dir / "case1" / "c_wadliwy.json").exists()
    assert "invalid_output" in capsys.readouterr().err


def test_llm_batch_recovers_from_429_and_saves_every_document(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    for index in range(5):
        create_pdf(input_dir / "case1" / f"{index}.pdf", ("Dokument testowy dla procesu ekstrakcji.",))
    statuses = iter([429, 200, 200, 429, 200, 200, 200])
    attempts = []

    class FakeConnection:
        def __init__(self, host, port, timeout):
            self.status = next(statuses)

        def request(self, method, path, *, body, headers):
            attempts.append(self.status)

        def getresponse(self):
            payload = {"choices": [{"finish_reason": "stop", "message": {"content": '{"typ":"unknown","dane":null}'}}]}
            return SimpleNamespace(status=self.status, getheader=lambda _: "0", read=lambda: json.dumps(payload).encode())

        def close(self):
            pass

    monkeypatch.setattr(chat, "HTTPConnection", FakeConnection)
    monkeypatch.setattr(chat, "coordinator", RequestCoordinator())
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:8765/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_REQUEST_INTERVAL_SECONDS", "0")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    assert main(["--llm", "--input", str(input_dir), "--output", str(output_dir)]) == 0
    assert attempts == [429, 200, 200, 429, 200, 200, 200]
    assert len(list(output_dir.rglob("*.json"))) == 5


def test_run_report_marks_failures_and_tracks_saved_bytes(tmp_path):
    import hashlib

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    report = tmp_path / "reports" / "run.json"
    create_pdf(input_dir / "case" / "a.pdf", ("Potwierdzenie wykonania przelewu", "Kwota: 50,00 PLN"))
    (input_dir / "case" / "b.pdf").write_bytes(b"invalid pdf")
    old_result = output_dir / "case" / "b.json"
    old_result.parent.mkdir(parents=True)
    old_result.write_text('{"old": true}', encoding="utf-8")
    assert main(["--input", str(input_dir), "--output", str(output_dir), "--report", str(report)]) == 1
    first, second = json.loads(report.read_bytes())["documents"]
    assert first["status"] == "ok"
    assert first["sha256"] == hashlib.sha256((output_dir / first["output"]).read_bytes()).hexdigest()
    assert second["status"] == "error" and second["code"] == "pdf_read"
    assert old_result.read_text(encoding="utf-8") == '{"old": true}'
