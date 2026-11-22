"""Deterministyczne poprawki wyniku modelu, sterowane sekcją `postprocess:` w YAML klasy.

Krok działa po odpowiedzi modelu, a przed normalizacją pól i walidacją schematu. Nie zna
konkretnych typów dokumentów: wszystko, co robi, wynika z konfiguracji.

    postprocess:
      fill_missing:              # uzupełnij null wartością znalezioną regułą w tekście PDF
        - field: Odwolujacy[].pelnomocnik.nazwa
          pattern: '...(?P<value>...)...'
          normalize: text        # jak w `fields:` (text, digits, iso_date, amount)
          requires: ['Odwolujacy[].pelnomocnik.imie_nazwisko']
      snap_to_text:              # imiona/nazwiska w pisowni z dokumentu
        - 'pelnomocnicy[].imie_nazwisko'
      null_when_single:          # pole ważne tylko przy kilku elementach listy
        - 'Zamawiajacy[].prowadzacy_postepowanie'
      classify_by_patterns:      # wartość kategorii z fragmentów tekstu (tylko przy zgodzie fragmentów)
        - field: OdwolanieKIO.czynnosc_powod_id
          segments: ['...(?P<segment>...)...']   # skąd brać fragmenty (pierwsze trafienie każdego)
          classes:                              # kolejność = pierwszeństwo
            - {value: 7, patterns: ['zaniechania odrzucenia']}
            - {value: 1, patterns: ['odrzucenia oferty']}
          min_votes: 2           # ilu zgodnych fragmentów trzeba, by nadpisać model
          mode: override         # override (popraw model) albo fill (tylko gdy null)
      derive:                    # pole wyliczone ze słownika w `options`
        - field: OdwolanieKIO.czynnosc_opis
          source: OdwolanieKIO.czynnosc_powod_id
          option: czynnosc_powod_opisy

Zasady `fill_missing` (ostrożne, bo zła wartość to FP, a null przy pustym wzorcu nic nie kosztuje):
- działa tylko, gdy model zwrócił null (nigdy nie nadpisuje wartości modelu),
- wszystkie trafienia reguły w dokumencie muszą dać tę samą wartość po normalizacji,
- ścieżka z `[]` jest uzupełniana tylko, gdy lista ma dokładnie jeden element
  (przy kilku podmiotach nie wiadomo, do którego należy wartość); pustych list nie tworzy,
- `requires`: pola, które muszą być niepuste (w tym samym elemencie listy), np. osoba pełnomocnika.
Zasady `classify_by_patterns` (reguła ma pierwszeństwo przed modelem tylko, gdy jest niemal pewna):
- każdy wzorzec z `segments` wyznacza co najwyżej jeden fragment (pierwsze trafienie, grupa `segment`),
- we fragmencie klasy sprawdzane są po kolei, a trafienie wycina dopasowany tekst, więc wcześniejsza
  klasa („zaniechanie odrzucenia”) zabiera słowa późniejszej („odrzucenie”),
- fragment głosuje tylko, gdy pasuje do dokładnie jednej klasy; wynik jest ustalany tylko, gdy
  wszystkie głosujące fragmenty są zgodne i jest ich co najmniej `min_votes`; inaczej zostaje model.
Reguły `fields:` (tryb bez modelu) dla pól skalarnych bez list działają tu jako `fill_missing`.
"""
import re
from collections.abc import Mapping

from .contracts import ConfigurationError, DocumentConfig, ExtractedDocument, JsonObject, JsonValue
from .normalization import NORMALIZERS


def _split(path: str) -> list[str]:
    return path.split(".")


def schema_leaf(schema: JsonObject, path: str) -> JsonObject | None:
    """Schemat pola dla ścieżki z kropkami; `klucz[]` schodzi do elementów listy."""
    node = schema
    for part in _split(path):
        is_list = part.endswith("[]")
        node = node.get("properties", {}).get(part.removesuffix("[]"))
        if not isinstance(node, dict):
            return None
        if is_list:
            if node.get("type") != "array":
                return None
            node = node.get("items", {})
    return node


def _resolve(data: JsonValue, path: str) -> tuple[dict, str] | None:
    """(obiekt-rodzic, klucz) dla ścieżki; listy muszą mieć dokładnie jeden element."""
    parts = _split(path)
    node = data
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        key = part.removesuffix("[]")
        if not isinstance(node, dict) or key not in node:
            return None
        if last and not part.endswith("[]"):
            return node, key
        node = node[key]
        if part.endswith("[]"):
            if not isinstance(node, list) or len(node) != 1:
                return None
            node = node[0]
    return None


def _get(data: JsonValue, path: str) -> JsonValue:
    resolved = _resolve(data, path)
    return resolved[0].get(resolved[1]) if resolved else None


def _unique_match(pattern: re.Pattern[str], normalize, text: str) -> JsonValue:
    values = []
    for match in pattern.finditer(text):
        raw = match.group("value")
        if raw is not None and (value := normalize(raw)) is not None:
            values.append(value)
    if values and all(value == values[0] for value in values):
        return values[0]
    return None


def _fill_rules(config: DocumentConfig) -> list[Mapping]:
    rules = [{"field": path, "pattern": rule.pattern, "normalize": rule.normalize}
             for path, rule in config.fields.items() if "[]" not in path]
    rules.extend(config.postprocess.get("fill_missing", []))
    return rules


def fill_missing(data: JsonObject, document: ExtractedDocument, config: DocumentConfig) -> JsonObject:
    text = "\n".join(page.text for page in document.pages)
    for rule in _fill_rules(config):
        resolved = _resolve(data, rule["field"])
        if resolved is None or resolved[0].get(resolved[1]) is not None:
            continue
        if any(_get(data, required) in (None, "", 0) for required in rule.get("requires", ())):
            continue
        value = _unique_match(re.compile(rule["pattern"]), NORMALIZERS[rule.get("normalize", "text")], text)
        if value is not None:
            resolved[0][resolved[1]] = value
    return data


def _slots(node: JsonValue, parts: list[str]):
    """Wszystkie (rodzic, klucz) dla ścieżki, po wszystkich elementach list."""
    if not parts or not isinstance(node, dict):
        return
    part, rest = parts[0], parts[1:]
    key = part.removesuffix("[]")
    if key not in node:
        return
    if not part.endswith("[]"):
        if rest:
            yield from _slots(node[key], rest)
        else:
            yield node, key
        return
    items = node[key] if isinstance(node[key], list) else []
    for index, item in enumerate(items):
        if rest:
            yield from _slots(item, rest)
        else:
            yield items, index


_FOLD = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
# Pary końcówek męska/żeńska (nazwiska przymiotnikowe, część imion).
_GENDER_ENDINGS = (("ski", "ska"), ("cki", "cka"), ("dzki", "dzka"), ("er", "ra"))


def _word_variant(model: str, text: str) -> bool:
    """Słowo z dokumentu to ten sam wyraz w innej pisowni: diakrytyki w środku wyrazu
    (bez ostatniej litery, żeby nie mylić przypadków: „Anną”/„Anna”) albo zamiana rodzaju końcówki."""
    a, b = model.casefold(), text.casefold()
    if a == b:
        return True
    if len(a) == len(b) and a[-1] == b[-1] and a[:-1].translate(_FOLD) == b[:-1].translate(_FOLD):
        return True
    for left, right in _GENDER_ENDINGS:
        for x, y in ((left, right), (right, left)):
            if a.endswith(x) and b.endswith(y) and a[: -len(x)] == b[: -len(y)] and len(a) - len(x) >= 3:
                return True
    return False


_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")


def snap_to_text(data: JsonObject, document: ExtractedDocument, config: DocumentConfig) -> JsonObject:
    """Imiona i nazwiska tak jak w dokumencie: gdy wartości modelu nie ma w tekście, a jest
    dokładnie jeden wariant pisowni (diakrytyki, końcówka rodzaju), wpisz wariant z dokumentu."""
    paths = config.postprocess.get("snap_to_text", [])
    if not paths:
        return data
    text = "\n".join(page.text for page in document.pages)
    words = _WORD.findall(text)
    folded = " ".join(word.casefold() for word in words)
    for path in paths:
        for parent, key in list(_slots(data, _split(path))):
            value = parent[key]
            if not isinstance(value, str):
                continue
            target = _WORD.findall(value)
            if not target or " ".join(t.casefold() for t in target) in folded:
                continue
            size = len(target)
            candidates = {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)
                          if all(_word_variant(t, w) for t, w in zip(target, words[i:i + size]))}
            if len(candidates) == 1:
                parent[key] = candidates.pop()
    return data


def _vote(segment: str, classes: list[Mapping]) -> JsonValue:
    """Klasa fragmentu albo None, gdy pasuje do żadnej lub do kilku klas."""
    found = []
    for item in classes:
        hit = False
        for pattern in item["patterns"]:
            segment, count = re.subn(pattern, " ", segment)
            hit = hit or count > 0
        if hit:
            found.append(item["value"])
    return found[0] if len(found) == 1 else None


def classify_votes(text: str, rule: Mapping) -> list[JsonValue]:
    """Głosy fragmentów tekstu (po jednym na wzorzec segmentu, który coś znalazł)."""
    flat = re.sub(r"\s+", " ", text)
    votes = []
    for pattern in rule["segments"]:
        match = re.search(pattern, flat)
        if match and match.group("segment"):
            vote = _vote(match.group("segment"), rule["classes"])
            if vote is not None:
                votes.append(vote)
    return votes


def classify_by_patterns(data: JsonObject, document: ExtractedDocument, config: DocumentConfig) -> JsonObject:
    rules = config.postprocess.get("classify_by_patterns", [])
    if not rules:
        return data
    text = "\n".join(page.text for page in document.pages)
    for rule in rules:
        resolved = _resolve(data, rule["field"])
        if resolved is None:
            continue
        if rule.get("mode", "override") == "fill" and resolved[0].get(resolved[1]) is not None:
            continue
        votes = classify_votes(text, rule)
        if len(votes) >= rule.get("min_votes", 1) and all(vote == votes[0] for vote in votes):
            resolved[0][resolved[1]] = votes[0]
    return data


def derive(data: JsonObject, config: DocumentConfig) -> JsonObject:
    for rule in config.postprocess.get("derive", []):
        target = _resolve(data, rule["field"])
        if target is None:
            continue
        source = _get(data, rule["source"])
        mapping = config.options.get(rule["option"], {})
        target[0][target[1]] = mapping.get(str(source)) if source is not None else None
    return data


def null_when_single(data: JsonObject, config: DocumentConfig) -> JsonObject:
    """Pole elementu listy, które ma sens tylko przy kilku elementach (np. „prowadzący
    postępowanie” wśród wielu zamawiających): przy jednym elemencie ustaw null."""
    for path in config.postprocess.get("null_when_single", []):
        parts = _split(path)
        last = max(index for index, part in enumerate(parts) if part.endswith("[]"))
        prefix = [*parts[:last], parts[last].removesuffix("[]")]
        for parent, key in list(_slots(data, prefix)):
            items = parent[key]
            if isinstance(items, list) and len(items) == 1:
                for owner, field in list(_slots(items[0], parts[last + 1:])):
                    owner[field] = None
    return data


def postprocess(data: JsonObject | None, document: ExtractedDocument, config: DocumentConfig) -> JsonObject | None:
    if not isinstance(data, dict):
        return data
    data = fill_missing(data, document, config)
    data = snap_to_text(data, document, config)
    data = null_when_single(data, config)
    data = classify_by_patterns(data, document, config)
    return derive(data, config)


def validate_postprocess(raw: object, schema: JsonObject, options: Mapping) -> dict:
    """Sprawdza sekcję `postprocess:` przy wczytywaniu konfiguracji."""
    if raw is None:
        return {}
    allowed = {"fill_missing", "derive", "snap_to_text", "null_when_single", "classify_by_patterns"}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ConfigurationError(
            "postprocess może mieć tylko fill_missing, snap_to_text, null_when_single, classify_by_patterns i derive")

    def scalar(path: str) -> None:
        leaf = schema_leaf(schema, path)
        if leaf is None or leaf.get("type") in ("object", "array"):
            raise ConfigurationError(f"postprocess: ścieżka spoza schematu lub nieskalarna: {path}")

    fills = raw.get("fill_missing", [])
    derives = raw.get("derive", [])
    if not isinstance(fills, list) or not isinstance(derives, list):
        raise ConfigurationError("postprocess: fill_missing i derive muszą być listami")
    for rule in fills:
        scalar(rule["field"])
        if "value" not in re.compile(rule["pattern"]).groupindex:
            raise ConfigurationError(f"postprocess: wzorzec {rule['field']} wymaga grupy value")
        if rule.get("normalize", "text") not in NORMALIZERS:
            raise ConfigurationError(f"postprocess: nieznany normalizator dla {rule['field']}")
        for required in rule.get("requires", ()):
            scalar(required)
    snaps = raw.get("snap_to_text", [])
    if not isinstance(snaps, list):
        raise ConfigurationError("postprocess: snap_to_text musi być listą ścieżek")
    for path in snaps:
        scalar(path)
    singles = raw.get("null_when_single", [])
    if not isinstance(singles, list):
        raise ConfigurationError("postprocess: null_when_single musi być listą ścieżek")
    for path in singles:
        scalar(path)
        if "[]" not in path:
            raise ConfigurationError(f"postprocess: null_when_single wymaga pola elementu listy: {path}")
    classifiers = raw.get("classify_by_patterns", [])
    if not isinstance(classifiers, list):
        raise ConfigurationError("postprocess: classify_by_patterns musi być listą")
    for rule in classifiers:
        scalar(rule["field"])
        segments, classes = rule.get("segments"), rule.get("classes")
        if not isinstance(segments, list) or not segments or not isinstance(classes, list) or not classes:
            raise ConfigurationError(f"postprocess: {rule['field']} wymaga niepustych segments i classes")
        for pattern in segments:
            if "segment" not in re.compile(pattern).groupindex:
                raise ConfigurationError(f"postprocess: segment {rule['field']} wymaga grupy segment")
        for item in classes:
            if not isinstance(item, dict) or "value" not in item or not item.get("patterns"):
                raise ConfigurationError(f"postprocess: klasa {rule['field']} wymaga value i patterns")
            for pattern in item["patterns"]:
                re.compile(pattern)
        if rule.get("mode", "override") not in ("override", "fill"):
            raise ConfigurationError(f"postprocess: tryb {rule['field']} to override albo fill")
        if type(rule.get("min_votes", 1)) is not int or rule.get("min_votes", 1) < 1:
            raise ConfigurationError(f"postprocess: min_votes {rule['field']} musi być liczbą >= 1")
    for rule in derives:
        scalar(rule["field"])
        scalar(rule["source"])
        if not isinstance(options.get(rule["option"]), dict):
            raise ConfigurationError(f"postprocess: brak słownika options.{rule['option']}")
    return raw
