# Kontrakt frontend–backend

## API dla frontendu

Planowany endpoint `POST /api/extract` przyjmuje `multipart/form-data`. Jedno żądanie odpowiada jednej sprawie. Każdy PDF to osobne pole `files`, dodane w kolejności wybranej przez użytkownika. Serwer zwraca jeden wpis na plik w tej samej kolejności, więc pozycja wpisu pozwala rozróżnić również pliki o tej samej nazwie.

Odpowiedź HTTP 200 ma postać obiektu `{"documents":[...]}`. `filename` to nazwa pliku wejściowego bez ścieżki. Każdy wpis ma `status`, `type` i `data`.

| `status` | `type` | `data` | Zachowanie UI |
| --- | --- | --- | --- |
| `ok` | `odwolanie`, `pelnomocnictwo` lub `przelew` | Zwalidowany obiekt UZP. | Pokazuje klasę, podgląd i pobranie `data` jako `<nazwa>.json`. |
| `unknown` | `unknown` | `null` | Pokazuje „Nie rozpoznano typu dokumentu”. |
| `error` | `null` | `null` | Wyświetla komunikat z `error.message`. `error` zawiera również maszynowy `code`. |

Błąd pojedynczego PDF-u pozostaje w `documents` z `status: "error"`. Puste lub niepoprawne żądanie zwraca HTTP 400 i `{"error":{"code":"invalid_request","message":"Wybierz co najmniej jeden plik PDF."}}`. Awaria całego żądania zwraca kod 5xx. Sekret LLM jest po stronie backendu. Pełną [syntetyczną odpowiedź](fixtures/extract-response.json) można od razu użyć w atrapie klienta.

Odpowiedź zawiera też `meta.model`, czyli nazwę modelu LLM albo `null` w trybie regułowym. `GET /api/document-types` zwraca `{"types":[{"doc_type":"przelew","fields":["przelew_bankowy.kwota", ...]}]}` z klas w `configs/documents/`; pola list mają w ścieżce `[]`. Każdy wpis ma też `label` z `options.label` (albo `null`) i pełny `schema` klasy, z którego panel buduje formularz także dla klas dodanych w kreatorze (etykiety z `description`, `format: date`, `boolean`, tablice). `POST /api/document-types` z JSON-em `{"yaml": "...", "schema": "..."}` dodaje klasę z kreatora panelu: `201` i `{"doc_type", "label", "files"}` po zapisie, `400 invalid_config` z opisem błędu walidacji, `409 type_exists`, `413 too_large` (limit 64 KB na plik), `403 type_upload_disabled` przy `ALLOW_TYPE_UPLOAD=0`. Szczegóły w [ADD_DOCUMENT_TYPE.md](ADD_DOCUMENT_TYPE.md). Ten sam serwer pod `/` serwuje panel z katalogu `frontend/`.

## Wewnętrzne kontrakty backendu

```text
PDF → ExtractedDocument → konfiguracja klasy → Extractor → ExtractionResult
                                                       → walidacja → JSON
```

Punktem odniesienia jest [contracts.py](../src/kio_extract/contracts.py). Schematy opisują payload, który trafia do `output/` i do `data` w odpowiedzi HTTP. Główny tryb uruchamia [wspólny system prompt](../prompts/system_pl.md) na każdym PDF-ie. `evidence` pozostaje w pamięci w obecnej wersji. Zmianę formatu HTTP uzgadniają obie osoby i weryfikują na wspólnej próbce.

| Symbol | Pola i semantyka |
| --- | --- |
| `PageText` | `page_number: int` od 1. `text: str` w kolejności czytania zwróconej przez parser, z podziałem wierszy. |
| `ExtractedDocument` | `source_path: Path`, `pages: tuple[PageText, ...]` w kolejności PDF, `used_ocr: bool = False`, `pages_needing_ocr: tuple[int, ...] = ()`. Ścieżka służy do I/O i diagnozy. |
| `DocumentConfig` | `doc_type`, roboczy `schema` JSON Schema, `positive_patterns`, `negative_patterns`, `minimum_matches`, `fields`, dowolne `options` należące do typu oraz opcjonalny `extractor`. |
| `ClassificationResult` | `doc_type: str` dopuszcza nowe klasy i zastrzeżone `unknown`. `reason` to `llm`, `matched`, `no_match` lub `ambiguous`. |
| `ExtractionResult` | `data: JsonObject`, `evidence: tuple[Evidence, ...] = ()`. Typy JSON to obiekty, listy, tekst, liczby skończone, bool i `None`. |
| `Evidence` | `field_path: str` w formie `Odwolujacy.0.krs`, `page_number: int`, `method: str` opisująca pochodzenie, np. `regex`. Ścieżki odpowiadają wynikowym pozycjom list od zera. |
| `OCR` | Callable `(source_path: Path, page_number: int) -> str \| None`. `None` oznacza stronę całkowicie białą, a tekst to wynik OCR. Adapter zgłasza `DocumentError("ocr_failed", ...)` przy awarii. Parser kieruje strony z mniej niż 12 znakami alfanumerycznymi do OCR. |
| `LLMClient` | `extract_json(*, instructions: str, text: str, schema: JsonObject) -> JsonObject`. Backend utrzymuje adapter. Tryb regułowy działa z `llm=None`. |

Opcjonalna strategia regułowa eksportuje funkcję o tej sygnaturze. Funkcja dostaje jeden dokument i zwraca kompletną strukturę JSON dla jego klasy.

```python
def extract(
    document: ExtractedDocument,
    config: DocumentConfig,
    llm: LLMClient | None = None,
) -> ExtractionResult:
    ...
```

W każdym YAML `schema` wskazuje nazwę pliku z katalogu `schemas/`. `classification.positive_patterns` to lista regexów. Każdy dopasowany wzorzec daje punkt, liczony raz na pierwszych trzech stronach. `negative_patterns` zawetuje klasę. Próg i remis ograniczają false positive. `fields` pozwala dodać ekstrakcję skalarów bez modułu Pythona. Klucz pola to ścieżka z kropkami, `pattern` zawiera grupę `(?P<value>...)`, a `normalize` to `text`, `digits`, `iso_date` lub `amount`. Sprzeczne wartości z kilku trafień pozostają `null`. Nieobsadzone listy są puste. W przypadku tablic podmiotów i relacji użyj strategii specjalizowanej (`extractor: kio_extract.document_types.<typ>:extract`).

`normalize_date`, `normalize_amount`, `normalize_digits` i `normalize_text` przyjmują `str` i zwracają znormalizowaną wartość lub `None`. `normalize_digits` zachowuje zera wiodące. Słownik powodów odwołania jest dostępny w `config.options["czynnosc_powod_opisy"]` pod kluczami tekstowymi `"1"`–`"12"`.

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
| Brak pola | Backend przyjmuje `None` lub pustą listę tam, gdzie pozwala schemat roboczy. Waliduje przed serializacją. |
| Negatyw lub nierozstrzygnięta klasa | Klasyfikator zwraca `unknown`. CLI zapisuje plik w wybranym trybie negatywnym. |
| Błąd jednego dokumentu | `DocumentError(code, message)` z komunikatem bez tekstu źródłowego i identyfikatorów. CLI raportuje ścieżkę i kod na stderr, kontynuuje i zwraca 1 po batchu. Obsługiwane kody obejmują `pdf_read`, `pdf_encrypted`, `ocr_required`, `invalid_output`, `output_write` i `llm_rate_limit` po wyczerpaniu ponowień 429. |
| Nieprawidłowa konfiguracja | `ConfigurationError` zatrzymuje batch przed zapisem. Kod CLI 2. Poprawnie zakończony batch ma kod 0. |

W testach backendu zastępuj klienta LLM atrapą. W testach frontendu zastępuj endpoint odpowiedziami zawierającymi trzy statusy oraz błąd całego żądania.
