# Podział pracy na trzy osoby

Hackathon trwa 22 godziny zegarowe. Każda osoba ma 18 godzin zaplanowanej pracy i 4 godziny bufora na przerwy, review i regresje. P0 to 49 z 54 zaplanowanych osobogodzin. Prace P1 ruszają po przejściu bramek P0.

| Obszar | Właściciel plików | Zakres odbioru |
| --- | --- | --- |
| A · Core, infrastruktura, integracja | `main.py`, `requirements*.txt`, `pyproject.toml`, `Dockerfile`, `compose.yaml`, `.gitignore`, `README.md`, `.env.example`, `docs/`, `src/kio_extract/*.py`, `src/kio_extract/providers/`, `evaluation/`, `tests/test_end_to_end.py`, `tests/test_contracts.py`, `tests/fixtures/contract_samples/` | Jeden batch na CPU. Wejście, PDF/OCR, klasyfikator, registry, moduły B/C, kontrola schematu i zapis. Raport lokalnej jakości oraz jedna komenda dla jury. |
| B · Odwołania | `configs/documents/odwolanie.yaml`, `schemas/odwolanie.schema.json`, `src/kio_extract/document_types/odwolanie/`, `tests/test_odwolanie.py`, `tests/fixtures/odwolanie/` | Pełna struktura odwołania, strony z poprawnym przypisaniem, pierwszy zarzut i zgodny słownik. Testy działają bez parsera. |
| C · Pełnomocnictwo i przelew | `configs/documents/{pelnomocnictwo,przelew}.yaml`, `schemas/{pelnomocnictwo,przelew}.schema.json`, `src/kio_extract/document_types/{pelnomocnictwo,przelew}/`, `tests/test_{pelnomocnictwo,przelew}.py`, `tests/fixtures/{pelnomocnictwo,przelew}/` | Dwa niezależne ekstraktory. Relacje mocodawców i podpisujących, rachunki i pola przelewu z poprawnymi typami. Każda klasa ma osobne testy. |

Katalog `document_types/` może pozostać przestrzenią nazw bez współdzielonego `__init__.py`. A odpowiada za format YAML i algorytm klasyfikacji. B i C odpowiadają za sygnały w swoich konfiguracjach. Wspólny zestaw regresyjny utrzymuje A z przykładami dostarczonymi przez B i C.

| Osoba | P0 w kolejności | Czas P0 | P1 | Czas P1 |
| --- | --- | ---: | --- | ---: |
| A | Kontrakt, fixtures i Git (1 h), CLI/registry/walidacja (2 h), PDF i klasyfikacja (2 h), OCR CPU (3 h), lokalny evaluator (2,5 h), E2E, Compose, pomiar i wydanie (5,5 h) | 16 h | Adapter LLM po potwierdzeniu warunków, rozszerzona diagnostyka | 2 h |
| B | Fixtures, reguły dat nagłówka i sekcje (3,5 h), strony, konsorcja i pełnomocnik (4 h), zamówienie i BZP/TED (2 h), wydzielenie i mapowanie pierwszego zarzutu (4 h), pomiar i poprawki (3 h) | 16,5 h | Ekstrakcja semantyczna pierwszego zarzutu przez wspólny adapter | 1,5 h |
| C | Fixtures dla obu klas (1,5 h), przelewy z wariantami bankowymi (5 h), mocodawca, pełnomocnicy i podpisujący (6 h), pomiar, typy danych i regresje (4 h) | 16,5 h | Kolejne warianty bankowe lub poprawa rozpoznawania nazwisk | 1,5 h |

Regułowy przebieg P0 zachowuje działanie bez endpointu. OCR CPU i walidacja są w P0, ponieważ dane zawierają dokumenty zeskanowane i ścisły format wynikowy. P1 obejmuje dodatkową ekstrakcję semantyczną i szerszą diagnostykę. Priorytet w poprawkach wyznaczają FP/FN na walidacji z podziałem po sprawach.

## Zależności

| Konsument | Zależność | Jak zacząć od razu | Dostawca i granica | Gdy komponent się opóźni |
| --- | --- | --- | --- | --- |
| B, C | Strony z PDF i OCR | Utworzyć `ExtractedDocument` z plików tekstowych. | A, kontrakt do 0:45, PDF do 4 h, OCR do 11 h | Testy tekstowe idą dalej. A integruje z testowym OCR. |
| A | Strategie B/C | Uruchamia domyślną strategię YAML i testowy callback. | B/C, API do 0:45, pierwsze wersje do 6 h | Przetwarza tekstową sprawę strategią domyślną i uruchamia testy zgodności kontraktu. |
| B, C | Normalizacja i dostęp do LLM | Korzystać z normalizatorów lub testowej atrapy o tym samym API, sprawdzać `llm=None`. | A, kontrakt do 0:45, klient warunkowo do 16 h | Zgłosić brak interfejsu A. Reguły i testy bez sieci pozostają ścieżką główną. |
| A | Etykiety i regresje | Użyć referencji UZP i dodać niezależne fixtures syntetyczne. | B/C, próbki do 6 h, przegląd etykiet do 11 h | Zacząć od jawnie oznaczonych przykładów. Sporne etykiety opisać, zachować stały split. |
| B | Słownik pierwszego zarzutu | Użyć `config.options["czynnosc_powod_opisy"]`. | UZP publikuje słownik, B porównuje dane do 6 h | Niejednoznaczny zarzut daje robocze `null` dla ID i opisu. |
| C | Typ PESEL i rola rachunku | Test tekstowego PESEL w DTO i jawnej konwersji na wyjściu, osobne etykiety obydwu rachunków. | C, A potwierdza typ z mentorem przed 19 h | Utrzymać decyzję roboczą z U05 i zanotować rozbieżność w raporcie. |

Zobacz [kontrakt](INTERFACES.md), [harmonogram](INTEGRATION_PLAN.md) i [tablicę zadań](WORKBOARD.md).
