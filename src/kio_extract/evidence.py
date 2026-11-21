"""Źródła pól (`Evidence`) dla wyniku, którego model nie opisał numerami stron.

Model LLM zwraca same wartości. Strona jest przypisywana deterministycznie: backend szuka
znormalizowanej wartości w tekście kolejnych stron i bierze pierwszą, na której ją znalazł.
Wartość, której nie da się znaleźć (np. opis streszczony przez model albo kod z listy), nie
dostaje źródła. Funkcje nie zmieniają danych, więc wynik zapisywany do `output/` jest ten sam.
"""
import re
from collections.abc import Iterator
from dataclasses import replace
from datetime import date

from .contracts import Evidence, ExtractedDocument, JsonObject, JsonValue


MIN_COMPACT_LENGTH = 4
MONTHS = (
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
)
TED = re.compile(r"([0-9]{6})-([0-9]{4})")


class _Page:
    """Tekst strony w dwóch postaciach: małe litery oraz same znaki alfanumeryczne."""

    def __init__(self, text: str):
        self.raw = text.lower()
        chars, positions = [], []
        for index, char in enumerate(self.raw):
            if char.isalnum():
                chars.append(char)
                positions.append(index)
        self.compact = "".join(chars)
        self.positions = positions

    def _separated(self, start: int, end: int) -> bool:
        """Trafienie nie skleja się z sąsiednią cyfrą ani literą (np. `1.05` w `11.05`)."""
        before = self.raw[self.positions[start] - 1] if self.positions[start] > 0 else " "
        after_index = self.positions[end - 1] + 1
        after = self.raw[after_index] if after_index < len(self.raw) else " "
        first, last = self.compact[start], self.compact[end - 1]
        return not (
            (before.isdigit() and first.isdigit()) or (before.isalpha() and first.isalpha())
            or (after.isdigit() and last.isdigit()) or (after.isalpha() and last.isalpha())
        )

    def contains(self, needle: str | re.Pattern[str], raw: bool = False) -> bool:
        if raw:
            return bool(needle.search(self.raw))
        if isinstance(needle, re.Pattern):
            return any(self._separated(m.start(), m.end()) for m in needle.finditer(self.compact))
        start = self.compact.find(needle)
        while start != -1:
            if self._separated(start, start + len(needle)):
                return True
            start = self.compact.find(needle, start + 1)
        return False


def _compact(text: str) -> str:
    return "".join(char for char in text.lower() if char.isalnum())


def _date_variants(value: str) -> list[str]:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return []
    days = {f"{parsed.day:02d}", str(parsed.day)}
    months = {f"{parsed.month:02d}", str(parsed.month), _compact(MONTHS[parsed.month - 1])}
    variants = [f"{day}{month}{parsed.year}" for day in days for month in months]
    return [f"{parsed.year}{parsed.month:02d}{parsed.day:02d}", *variants]


def _amount_pattern(value: float) -> re.Pattern[str] | None:
    whole, _, cents = f"{abs(value):.2f}".partition(".")
    if abs(abs(value) - float(f"{abs(value):.2f}")) > 1e-9:
        return None
    groups = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    number = r"[  .]?".join(groups)
    integral = rf"|{number}(?:[  ]*(?:zł|pln))" if cents == "00" else ""
    # bez cyfry tuż przed kwotą ani przed separatorem tysięcy („500,00” nie trafia w „7 500,00”)
    return re.compile(rf"(?<![0-9])(?<![0-9][  .])(?:{number}[,.]{cents}(?![0-9]){integral})")


def _needles(value: JsonValue, schema: JsonObject) -> list[tuple[str | re.Pattern[str], bool]]:
    """Postacie wartości do wyszukania; `True` oznacza wzorzec na surowym tekście strony."""
    if isinstance(value, float) or ("number" in _types(schema) and isinstance(value, int)):
        pattern = _amount_pattern(float(value))
        return [(pattern, True)] if pattern else []
    if isinstance(value, int):
        texts = [str(value)]
        if isinstance(schema.get("maximum"), int):
            texts.append(str(value).zfill(len(str(schema["maximum"]))))
    elif isinstance(value, str):
        texts = [_compact(value), *_date_variants(value.strip())]
        if match := TED.fullmatch(value.strip()):
            number, year = match.groups()
            return [(re.compile(rf"{year}s[0-9]{{1,3}}{number}"), False)] + [(t, False) for t in texts if t]
    else:
        return []
    return [(text, False) for text in dict.fromkeys(texts) if len(text) >= MIN_COMPACT_LENGTH]


def _types(schema: JsonObject) -> set[str]:
    kind = schema.get("type", [])
    return {kind} if isinstance(kind, str) else set(kind)


def _leaves(value: JsonValue, schema: JsonObject, path: tuple[str, ...] = ()) -> Iterator[tuple[str, JsonValue, JsonObject]]:
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key, item in value.items():
            yield from _leaves(item, properties.get(key, {}), (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _leaves(item, schema.get("items", {}), (*path, str(index)))
    elif value is not None and not isinstance(value, bool) and "enum" not in schema:
        yield ".".join(path), value, schema


def locate_evidence(
    document: ExtractedDocument, data: JsonObject | None, schema: JsonObject, method: str
) -> tuple[Evidence, ...]:
    """Evidence dla liści `data` znalezionych w tekście stron; `method` np. `llm+search`."""
    if not data:
        return ()
    pages = [(page.page_number, _Page(page.text)) for page in document.pages]
    evidence = []
    for field_path, value, field_schema in _leaves(data, schema):
        needles = _needles(value, field_schema)
        found = next((number for number, page in pages
                      if any(page.contains(needle, raw) for needle, raw in needles)), None)
        if found is not None:
            evidence.append(Evidence(field_path, found, method))
    return tuple(evidence)


def mark_ocr(evidence: tuple[Evidence, ...], ocr_pages: tuple[int, ...]) -> tuple[Evidence, ...]:
    """Dopisuje `ocr+` do metody, gdy tekst strony pochodzi z OCR."""
    return tuple(replace(item, method=f"ocr+{item.method}") if item.page_number in ocr_pages else item
                 for item in evidence)
