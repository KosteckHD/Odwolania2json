"""Pomiar jakości OCR na skanach, tą samą ścieżką co backend.

Każdy PDF przechodzi przez kio_extract.pdf_reader.extract_pdf z OCR
kio_extract.ocr.tesseract_ocr (Tesseract, język pol, render strony w skali 2).
Skrypt nie wywołuje modelu językowego, więc nie mierzy F1 ekstrakcji. Mierzy,
czy wartości pól ze wzorcowego JSON-a UZP są w ogóle czytelne w tekście po OCR,
czyli górną granicę tego, co model może z dokumentu wyciągnąć.

Miary:
- odczyt pól: odsetek wartości ze wzorca znalezionych w tekście po OCR. Wartości
  porównujemy po usunięciu spacji, interpunkcji i wielkości liter; daty także w
  postaci DD.MM.RRRR i „D miesiąca RRRR”, kwoty z groszami i bez. Pola
  słownikowe i 0/1 (czynnosc_powod_id, czynnosc_opis, przez-pelnomocnika,
  prowadzacy_postepowanie, typ) pomijamy, bo nie występują dosłownie w treści.
  Przy --reference mianownikiem są tylko wartości znalezione w warstwie tekstu
  oryginału; bez niego wszystkie wartości wzorca z co najmniej 4 znakami.
- CER i WER (tylko z --reference): odległość edycyjna znaków i słów między
  tekstem po OCR a warstwą tekstu oryginału. Inna kolejność bloków na stronie
  też podnosi te liczby.

Wzorzec JSON: plik o tej samej nazwie obok PDF-u albo w --reference
(potwierdzenie_przelewu.pdf -> przelew.json, jak w danych UZP).

Przykłady:
    python evaluation/ocr_quality.py --scans .local/brudne-skany/sredni --reference .local/uzp-dane --label sredni
    python evaluation/ocr_quality.py --scans .local/uzp-skany --label skany-uzp
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kio_extract.contracts import DocumentError  # noqa: E402
from kio_extract.ocr import tesseract_ocr  # noqa: E402
from kio_extract.pdf_reader import extract_pdf  # noqa: E402

SKIP_KEYS = {"czynnosc_powod_id", "czynnosc_opis", "przez-pelnomocnika", "prowadzacy_postepowanie", "typ"}
GOLD_ALIASES = {"potwierdzenie_przelewu": "przelew"}
MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
          "września", "października", "listopada", "grudnia"]
ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def squash(text):
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def leaves(value, path=""):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaves(child, f"{path}[{index}]")
    elif value is not None and not isinstance(value, bool):
        yield path, value


def candidates(path, value):
    key = re.sub(r"\[\d+\]", "", path).split(".")[-1]
    if key in SKIP_KEYS:
        return []
    if isinstance(value, (int, float)):
        forms = [f"{float(value):.2f}"]
        if float(value).is_integer():
            forms.append(str(int(value)))
    elif match := ISO_DATE.match(str(value)):
        y, m, d = (int(x) for x in match.groups())
        try:
            date(y, m, d)
        except ValueError:
            return [squash(value)]
        forms = [str(value), f"{d:02}.{m:02}.{y}", f"{d}.{m:02}.{y}", f"{d} {MONTHS[m - 1]} {y}",
                 f"{d:02} {MONTHS[m - 1]} {y}", f"{d:02}-{m:02}-{y}", f"{d:02}/{m:02}/{y}"]
    else:
        forms = [str(value)]
        if str(value).upper().startswith("PL") and squash(value)[2:].isdigit():
            forms.append(str(value)[2:])
    return [c for c in {squash(f) for f in forms} if len(c) >= 4]


def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def normalize(text):
    return " ".join(text.lower().split())


def page_text(document):
    return "\n".join(page.text for page in document.pages)


def find_gold(pdf, relative, reference):
    stem = GOLD_ALIASES.get(pdf.stem, pdf.stem)
    for folder in ([reference / relative.parent] if reference else []) + [pdf.parent]:
        for name in (f"{pdf.stem}.json", f"{stem}.json"):
            if (folder / name).exists():
                return json.loads((folder / name).read_text(encoding="utf-8"))
    return None


def measure(pdf, scans, reference):
    relative = pdf.relative_to(scans)
    row = {"file": relative.as_posix()}
    started = time.perf_counter()
    try:
        scanned = extract_pdf(pdf, tesseract_ocr)
    except DocumentError as exc:
        row.update(error=exc.code, seconds=round(time.perf_counter() - started, 1))
        return row
    text = page_text(scanned)
    row.update(pages=len(scanned.pages), used_ocr=scanned.used_ocr, pages_unread=list(scanned.pages_needing_ocr),
               seconds=round(time.perf_counter() - started, 1))

    ref_text = None
    if reference and (reference / relative).exists():
        ref_text = page_text(extract_pdf(reference / relative))
        a, b = normalize(ref_text), normalize(text)
        row["cer"] = round(levenshtein(a, b) / max(1, len(a)), 4)
        wa, wb = a.split(), b.split()
        row["wer"] = round(levenshtein(wa, wb) / max(1, len(wa)), 4)

    gold = find_gold(pdf, relative, reference)
    if gold is not None:
        flat_ocr = squash(text)
        flat_ref = squash(ref_text) if ref_text is not None else None
        total, found, missed = 0, 0, []
        for path, value in leaves(gold):
            forms = candidates(path, value)
            if not forms:
                continue
            if flat_ref is not None and not any(f in flat_ref for f in forms):
                continue                                  # wartości nie ma dosłownie nawet w oryginale
            total += 1
            if any(f in flat_ocr for f in forms):
                found += 1
            else:
                missed.append(f"{path}={value}")
        row.update(fields_total=total, fields_found=found, fields_missed=missed)
    return row


def summarize(label, rows):
    ok = [r for r in rows if "error" not in r]
    pages = sum(r["pages"] for r in ok)
    total = sum(r.get("fields_total", 0) for r in ok)
    found = sum(r.get("fields_found", 0) for r in ok)
    cers = [r["cer"] for r in ok if "cer" in r]
    wers = [r["wer"] for r in ok if "wer" in r]
    return {
        "label": label,
        "documents": len(rows),
        "errors": len(rows) - len(ok),
        "pages": pages,
        "pages_unread": sum(len(r["pages_unread"]) for r in ok),
        "fields_found": found,
        "fields_total": total,
        "field_recall": round(found / total, 4) if total else None,
        "cer_mean": round(sum(cers) / len(cers), 4) if cers else None,
        "wer_mean": round(sum(wers) / len(wers), 4) if wers else None,
        "seconds_per_page": round(sum(r["seconds"] for r in ok) / pages, 2) if pages else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scans", type=Path, required=True, help="katalog ze skanami PDF")
    parser.add_argument("--reference", type=Path, help="oryginały z warstwą tekstu i wzorce JSON, w tym samym układzie")
    parser.add_argument("--label", default=None, help="nazwa zestawu w raporcie")
    parser.add_argument("--output", type=Path, help="zapisz raport JSON")
    parser.add_argument("--workers", type=int, default=4, help="równoległe dokumenty (Tesseract działa w osobnych procesach)")
    parser.add_argument("--tesseract-dir", type=Path, help="katalog z tesseract, gdy nie ma go w PATH")
    parser.add_argument("--tessdata", type=Path, help="katalog z pol.traineddata (TESSDATA_PREFIX)")
    args = parser.parse_args()

    if args.tesseract_dir:
        os.environ["PATH"] = f"{args.tesseract_dir}{os.pathsep}{os.environ['PATH']}"
    if args.tessdata:
        os.environ["TESSDATA_PREFIX"] = str(args.tessdata)

    pdfs = sorted(args.scans.rglob("*.pdf"))
    if not pdfs:
        parser.error(f"brak plików PDF w {args.scans}")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda p: measure(p, args.scans, args.reference), pdfs))

    summary = summarize(args.label or args.scans.name, rows)
    report = {"summary": summary, "documents": rows}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for r in rows:
        fields = f"{r['fields_found']}/{r['fields_total']}" if "fields_total" in r else "–"
        extra = r.get("error") or (f"CER {r['cer']:.3f}" if "cer" in r else "")
        print(f"{r['file']:<45} pola {fields:<6} {extra:<12} {r.get('seconds', 0):>5.1f} s"
              + (f"  brak: {'; '.join(r['fields_missed'])}" if r.get("fields_missed") else ""))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
