# Kontrakt modułów

```text
PDF → ExtractedDocument → konfiguracja klasy → Extractor → ExtractionResult
                                                       → walidacja → JSON
```

Punktem odniesienia jest [contracts.py](../src/kio_extract/contracts.py). Zmiana kontraktu wymaga wspólnego uzgodnienia A, B i C oraz aktualizacji testów zgodności. Schematy opisują payload, który trafia do `output/`. `evidence` pozostaje w pamięci w obecnej wersji.

| Symbol | Pola i semantyka |
| --- | --- |
| `PageText` | `page_number: int` od 1. `text: str` w kolejności czytania zwróconej przez parser, z podziałem wierszy. |
| `ExtractedDocument` | `source_path: Path`, `pages: tuple[PageText, ...]` w kolejności PDF, `used_ocr: bool = False`, `pages_needing_ocr: tuple[int, ...] = ()`. Ścieżka służy do I/O i diagnozy. |
| `DocumentConfig` | `doc_type`, roboczy `schema` JSON Schema, `positive_patterns`, `negative_patterns`, `minimum_matches`, `fields`, dowolne `options` należące do typu oraz opcjonalny `extractor`. |
| `ClassificationResult` | `doc_type: str` dopuszcza nowe klasy i zastrzeżone `unknown`. `reason` to `matched`, `no_match` lub `ambiguous`. |
| `ExtractionResult` | `data: JsonObject`, `evidence: tuple[Evidence, ...] = ()`. Typy JSON to obiekty, listy, tekst, liczby skończone, bool i `None`. |
| `Evidence` | `field_path: str` w formie `Odwolujacy.0.krs`, `page_number: int`, `method: str` opisująca pochodzenie, np. `regex`. Ścieżki odpowiadają wynikowym pozycjom list od zera. |
| `OCR` | Callable `(source_path: Path, page_number: int) -> str`. Adapter docelowy powinien zgłaszać `DocumentError("ocr_failed", ...)` przy nieodwracalnej awarii. Parser oznacza strony z mniej niż 12 znakami alfanumerycznymi. |
| `LLMClient` | `extract_json(*, instructions: str, text: str, schema: JsonObject) -> JsonObject`. Tekst to fragment PDF. A dostarcza adapter. Reguły działają z `llm=None`. |

Specjalizowany moduł eksportuje funkcję o tej sygnaturze. Funkcja dostaje jeden dokument i zwraca kompletną strukturę JSON dla jego klasy. Role i powiązania ocenia właściciel klasy.

```python
def extract(
    document: ExtractedDocument,
    config: DocumentConfig,
    llm: LLMClient | None = None,
) -> ExtractionResult:
    ...
```

W każdym YAML `schema` wskazuje nazwę pliku z katalogu `schemas/`. `classification.positive_patterns` to lista regexów. Każdy dopasowany wzorzec daje punkt, liczony raz na pierwszych trzech stronach. `negative_patterns` zawetuje klasę. Próg i remis ograniczają false positive. `fields` pozwala dodać ekstrakcję skalarów bez modułu Pythona. Klucz pola to ścieżka z kropkami, `pattern` zawiera grupę `(?P<value>...)`, a `normalize` to `text`, `digits`, `iso_date` lub `amount`. Sprzeczne wartości z kilku trafień pozostają `null`. Nieobsadzone listy są puste. W przypadku tablic podmiotów i relacji użyj strategii specjalizowanej (`extractor: kio_extract.document_types.<typ>:extract`).

`normalize_date`, `normalize_amount`, `normalize_digits` i `normalize_text` przyjmują `str` i zwracają znormalizowaną wartość lub `None`. `normalize_digits` zachowuje zera wiodące. Właściciel klasy rozpoznaje typ identyfikatora i jego długość, nadaje rolę i stosuje semantyczne reguły pola. B korzysta z `config.options["czynnosc_powod_opisy"]` z kluczami tekstowymi `"1"`–`"12"`.

## Uruchomienie ekstraktora w izolacji

```python
import json
from pathlib import Path

from kio_extract.contracts import DocumentConfig, ExtractedDocument, PageText

schema = json.loads(Path("schemas/odwolanie.schema.json").read_text(encoding="utf-8"))
text = Path("tests/fixtures/contract_samples/odwolanie.txt").read_text(encoding="utf-8")
document = ExtractedDocument(Path("test.pdf"), (PageText(1, text),))
config = DocumentConfig("odwolanie", schema)


class StubLLM:
    def __init__(self, result):
        self.result = result

    def extract_json(self, *, instructions, text, schema):
        return self.result


# Ekstraktor modułu można wywołać na document i config z llm=None lub StubLLM(...).
```

Do testu odwołania wymagającego słownika wczytaj swój YAML przez `load_configs` lub wstrzyknij `options` w `DocumentConfig`. Syntetyczne próbki i test atrapy są w [testach kontraktu](../tests/test_contracts.py). Testy modułowe importują swój ekstraktor i kontrakty, a `pytest` dodaje `src/` do ścieżki.

## Wyniki i błędy

| Rodzaj | Format i odpowiedzialność |
| --- | --- |
| Brak pola | Właściciel modułu zwraca `None` lub pustą listę tam, gdzie pozwala schemat roboczy. A waliduje przed serializacją. |
| Negatyw lub nierozstrzygnięta klasa | Klasyfikator zwraca `unknown`. CLI zapisuje plik w wybranym trybie negatywnym. |
| Błąd jednego dokumentu | `DocumentError(code, message)` z komunikatem bez tekstu źródłowego i identyfikatorów. CLI raportuje ścieżkę i kod na stderr, kontynuuje i zwraca 1 po batchu. Obsługiwane kody obejmują `pdf_read`, `pdf_encrypted`, `ocr_required`, `invalid_output`, `output_write`. |
| Nieprawidłowa konfiguracja | `ConfigurationError` zatrzymuje batch przed zapisem. Kod CLI 2. Poprawnie zakończony batch ma kod 0. |

Klienta LLM testuj atrapą. W środowisku docelowym A obsługuje timeout, błędy dostawcy i ograniczone ponawianie. B i C dostarczają reguły awaryjne dla swoich klas. Przy niedostępnej możliwości wspólnej B/C dodają atrapę w swoich testach i zgłaszają potrzebę A.
