import json
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from kio_extract.cli import main
from kio_extract.pdf_reader import extract_pdf


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
