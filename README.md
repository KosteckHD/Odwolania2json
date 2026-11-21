# Odwołania2JSON

Odwołania2JSON przetwarza sprawy KIO partiami. W trybie konkursowym jeden [system prompt](prompts/system_pl.md) prowadzi model przez klasyfikację i ekstrakcję w jednym wywołaniu na PDF. CLI odczytuje tekst, dołącza aktualne schematy i słownik powodów odwołania, waliduje odpowiedź, a do `output/` zapisuje pola UZP. Tryb regułowy służy jako lokalna baza porównawcza.

## Uruchomienie

Wymagany jest Python 3.13 lub nowszy. Utwórz środowisko i zainstaluj zależności.

```powershell
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe main.py
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m pytest -q
```

Na Linuksie używaj `python3.13 -m venv .venv` i `.venv/bin/python`. Umieść np. `pismo.pdf` pod `input/case1/`. Wynik pojawi się w `output/case1/pismo.json`. Argumenty `--input` i `--output` wybierają inne katalogi. `--negative-output empty_object` zmienia domyślny wynik o długości 0 bajtów na `{}`. CLI zgłasza strony wymagające OCR i przechodzi do następnego pliku. Uruchomienie na świeżym `output/` ułatwia oddzielenie bieżących wyników od poprzednich przebiegów.

## Tryb LLM

Ustaw `LLM_BASE_URL` na bazę zgodnego API Chat Completions, np. adres zakończony `/v1`, `LLM_MODEL` na nazwę obsługiwaną przez ten endpoint i `LLM_API_KEY` w środowisku procesu lub w lokalnym `.env`. Obsługiwana jest także nazwa `API_KEY`. Zmienne procesu mają pierwszeństwo przed `.env`. Zwykłe endpointy używają `response_format: json_object`; regionalne endpointy Mistral korzystają z wymuszonego JSON Schema, a wynik jest dodatkowo walidowany lokalnie. Wywołanie `--llm` przesyła tekst stron PDF do skonfigurowanego API. Według FAQ przekazanego przez użytkownika konfiguracja konkursowa wymaga modelu open source dostępnego do lokalnej instalacji, bez ograniczeń użytkowania i opłat licencyjnych, oraz usługodawcy i serwerów API w UE. Organizator wymaga przekazania klucza do prób. [Wymagania UZP](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026#6-spos%C3%B3b-testowania-i-walidacji)

```powershell
.venv/Scripts/python.exe main.py --llm --input ./input --output ./output
```

Model dostaje instrukcje i schematy w wiadomości `system`, a tekst stron w `user`. Zwraca `typ` i `dane`. Dla `unknown` CLI stosuje tryb wyniku negatywnego, a dla rozpoznanej klasy zapisuje zwalidowane `dane`. Do porównania wersji użyj `--prompt ścieżka.md` i oddzielnych katalogów `--output` przy tym samym modelu i zbiorze. Reguły klasy można dopisać w jej YAML jako `options.llm_instructions`.

Domyślny prompt wymaga mianownika we wszystkich polach `imie_nazwisko`. Nazwy podmiotów i pełne firmy przedsiębiorców zachowują pisownię źródła.

Regresje `nominative_appeal_representative` i `nominative_authorization_roles` w `evaluation/prompt_cases.json` sprawdzają zapis danych osób. Skrypt `evaluation/prompt_regression.py` przyjmuje powtarzany argument `--case` i wysyła wybrane syntetyczne przykłady do skonfigurowanego API.

Przy dużych zbiorach żądania w jednym procesie są szeregowane i domyślnie dzieli je co najmniej sekunda. Odpowiedź HTTP 429 powoduje ponowienie, z uwzględnieniem nagłówka `Retry-After` albo rosnącego czasu oczekiwania. Tempo i limity ustawiają zmienne `LLM_REQUEST_INTERVAL_SECONDS` (domyślnie `1`), `LLM_MAX_429_RETRIES` (`4`) oraz `LLM_MAX_RETRY_WAIT_SECONDS` (`60`). Ostatni parametr ogranicza pojedyncze oczekiwanie. Po wyczerpaniu ponowień dokument otrzymuje błąd `llm_rate_limit`, a batch przechodzi do następnego pliku. Ponowienia 429 mogą zwiększyć liczbę żądań na PDF.

Odstęp dopasuj do limitów żądań oraz tokenów konkretnego konta i modelu. Koordynacja obejmuje wątki jednego procesu. Jednoczesne osobne procesy CLI, pracownicy serwera lub instancje kontenerów mają oddzielne limity, więc dla wspólnego klucza należy uwzględnić ich łączny ruch.

Do natywnego Claude Messages ustaw `LLM_PROVIDER=anthropic`, `LLM_BASE_URL=https://api.anthropic.com/v1`, identyfikator Sonnet w `LLM_MODEL` oraz klucz w `LLM_API_KEY` lub `API_KEY`. Adapter używa strukturalnej koperty JSON, a pełny schemat dokumentu waliduje lokalnie. Próby deweloperskie Claude Sonnet na danych syntetycznych zostały wykonane. Warunki UZP dotyczące otwartego modelu oraz lokalizacji dostawcy i serwerów opisano w dokumentacji projektu.

API uruchom przez `.venv/Scripts/python.exe -m uvicorn --app-dir src kio_extract.api:create_app --factory --host 127.0.0.1 --port 8000`. Gdy `LLM_MODEL` jest ustawiony, API korzysta z LLM. W innym przypadku działa tryb regułowy. `POST /api/extract` przyjmuje pola `files` według [kontraktu](docs/INTERFACES.md#api-dla-frontendu).

API przyjmuje opcjonalne zmienne `KIO_CONFIGS_DIR`, `KIO_SCHEMAS_DIR` i `KIO_PROMPT_PATH`. Wskaż katalogi zawierające kompletny zestaw klas oraz schematów, aby dodać klasę bez modyfikacji kodu. Compose montuje `./configs/documents` i `./schemas` jako katalogi tylko do odczytu; własny pełny zestaw podaj przez `KIO_CONFIGS_HOST_DIR` i `KIO_SCHEMAS_HOST_DIR`. Compose przekazuje klucz z `LLM_API_KEY`, `MISTRA_API_KEY` lub `API_KEY`; dla Mistral ustaw `LLM_BASE_URL=https://api.eu.mistral.ai/v1` i `LLM_MODEL` w środowisku lub `.env`. [Instrukcja dodawania klasy](docs/ADD_DOCUMENT_TYPE.md).

Do pokazu z przypiętym kandydatem Mistral EU (Ministral 3 8B, `ministral-8b-2512`) uruchom `.venv/Scripts/python.exe start_jury.py`. Skrypt wymaga `MISTRA_API_KEY` w środowisku lub lokalnym `.env`, ustawia regionalny endpoint i nie przełączy się po cichu na tryb regułowy. To profil pokazu, nie wybrany model końcowy: pełne porównanie jakości 8B/14B oczekuje na zwolnienie limitu API.

Do integracji frontendu na syntetycznych PDF-ach uruchom `.venv/Scripts/python.exe tests/support/fake_llm_server.py` w osobnym terminalu. W terminalu API ustaw `$env:LLM_PROVIDER='chat'`, `$env:LLM_BASE_URL='http://127.0.0.1:8765/v1'` i `$env:LLM_MODEL='fixture'`, a następnie uruchom API podaną komendą. Atrapa rozpoznaje syntetyczny tekst potwierdzenia przelewu i zwraca puste pola zgodne ze schematem.

OCR wymaga programu Tesseract dostępnego w `PATH` oraz danych językowych `pol`. Strony bez wystarczającej warstwy tekstowej są renderowane przez pypdfium2 i przekazywane do OCR.

## Lokalny pomiar

Manifest `evaluation/manifest.json` zawiera podział spraw UZP 01–42 na rozwój, 43–54 na walidację oraz 55–60 na końcowy test. Ewaluator porównuje wcześniej zapisane wyniki i nie wywołuje modelu. Przyjmuje lokalną kopię danych UZP oraz katalog wynikowy o takiej samej strukturze jak katalog danych.

Wyniki eksperymentów i ograniczenia pomiaru opisuje [porównanie modeli](docs/MODEL_COMPARISON.md). Przykładowy sposób rozszerzenia konfiguracji opisuje [instrukcja dodania klasy](docs/ADD_DOCUMENT_TYPE.md).

```powershell
.venv/Scripts/python.exe evaluation/evaluate.py --manifest evaluation/manifest.json --data .local/uzp-reference/dane --predictions .local/batch-uzp --split validation --output artifacts/baseline.json
```

Raport opisuje lokalny micro-F1, wyniki według pól i klas, macierz klasyfikacji oraz błędy. W obrębie list obiektów dopasowuje jednoznaczne identyfikatory, a pozostałe wartości porównuje jako wielozbiory. Ta metryka służy do porównywania wersji projektu.

Manifest `evaluation/manifest_scans.json` obejmuje 30 opublikowanych przez UZP par PDF i JSON. Zachowaj strukturę `dane/skany/<kategoria>/<numer>/` z [zestawu skanów UZP](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/tree/84cc976f0a9af5cee14f131c795f929134ca0fda/dane/skany). Uruchom backend na katalogu `dane` zawierającym skany i użyj `--split scans` z osobnym manifestem:

```powershell
docker build -t odwolania2json-scan-check .
$scanRoot = (Resolve-Path '.local/uzp-scans').Path
docker run --rm --network none --mount "type=bind,source=$scanRoot,target=/data" odwolania2json-scan-check python main.py --input /data/dane --output /data/rules-output --report /data/rules-run.json
.venv/Scripts/python.exe evaluation/evaluate.py --manifest evaluation/manifest_scans.json --data .local/uzp-scans/dane --predictions .local/uzp-scans/rules-output --split scans --run-report .local/uzp-scans/rules-run.json --output artifacts/uzp-scans-rules.json
```

Wynik pomiaru LLM można opatrzyć argumentami `--model`, `--revision` i `--prompt-version`, aby kolejne raporty wskazywały użyty model oraz wersję kodu i prompta.

Przy ponawianiu przetwarzania użyj opcji CLI `--report artifacts/run.json`, a następnie przekaż evaluatorowi `--run-report artifacts/run.json`. Raport przechowuje status i skrót zapisanego pliku. Evaluator traktuje błąd dokumentu, brak wpisu oraz zmieniony wynik jako błąd, również gdy w `output/` znajduje się plik z wcześniejszego przebiegu. Raport powstaje po zakończeniu batcha, dlatego dla każdego nowego uruchomienia używaj odrębnej ścieżki raportu.

Kontenery można uruchomić przez `docker compose run --build --rm batch` lub `docker compose up --build api`. Obraz instaluje Tesseract i pakiet języka polskiego. Przetwarzanie batcha przez LLM wymaga argumentu `--llm`, np. `docker compose run --build --rm batch python main.py --llm`. Dla dodatkowej klasy ustaw hostowe katalogi zawierające komplet YAML-i i schematów, np. `$env:KIO_CONFIGS_HOST_DIR='.local/demo-configs'` i `$env:KIO_SCHEMAS_HOST_DIR='.local/demo-schemas'`, przed `docker compose up --build api`.

## Tryb regułowy

Strategia konfigurowalna przyjmuje YAML w `configs/documents/` i JSON Schema w `schemas/`. Dodanie klasy z istniejącą strategią regex nie wymaga zmiany Pythona. Własne zestawy można przekazać przez `--configs` i `--schemas`. Format konfiguracji i przykład testu opisuje [kontrakt](docs/INTERFACES.md).

Zależności wykonawcze działają lokalnie na CPU. Ich licencje to BSD-3-Clause dla `pypdf` oraz MIT dla PyYAML i `jsonschema`. [pypdf](https://pypi.org/project/pypdf/6.18.0/), [PyYAML](https://pypi.org/project/PyYAML/6.0.3/), [jsonschema](https://pypi.org/project/jsonschema/4.26.0/)

## Start zespołu

- [Podział frontend/backend, własność plików i zależności](docs/WORK_SPLIT_2.md)
- [Kontrakt API](docs/INTERFACES.md#api-dla-frontendu) i [przykładowa odpowiedź do atrapy](docs/fixtures/extract-response.json)
- [Harmonogram 22 godzin i integracja](docs/INTEGRATION_PLAN.md)
- [Tablica zadań](docs/WORKBOARD.md)
- [Zweryfikowane wymagania i pytania do UZP](docs/OPEN_QUESTIONS.md)
- Prompty startowe dla [frontendu](docs/prompts/FRONTEND.md) i [backendu](docs/prompts/BACKEND.md)
