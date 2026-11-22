# Odwołania2JSON

Odwołania2JSON przetwarza sprawy KIO partiami. W trybie konkursowym jeden [system prompt](prompts/system_pl.md) prowadzi model przez klasyfikację i ekstrakcję w jednym wywołaniu na PDF. CLI odczytuje tekst, dołącza aktualne schematy i słownik powodów odwołania, waliduje odpowiedź, a do `output/` zapisuje pola UZP. Tryb regułowy służy jako lokalna baza porównawcza.

## Szybki start dla oceniających

Na serwerze oceny (Azure VM) projekt leży w `/opt/solution`, a komenda oceny jest w [RUN.md](RUN.md) (`docker compose run --rm batch`). Instrukcja wdrożenia: [deploy/VM.md](deploy/VM.md).

1. Python 3.13+: `py -3.13 -m venv .venv`, potem `.venv\Scripts\python.exe -m pip install -r requirements.txt` (Linux: `python3.13 -m venv .venv` i `.venv/bin/python -m pip install -r requirements.txt`).
2. Skopiuj `.env.example` jako `.env` i wklej klucz API z formularza zgłoszenia po `API_KEY=`. Model i adres są już wpisane: Qwen3.5 9B (Apache 2.0) w IONOS AI Model Hub, serwery w UE.
3. Umieść PDF-y w `input\<sprawa>\` i uruchom `przetworz.bat` (Linux: `./przetworz.sh`). Wyniki pojawią się w `output\<sprawa>\<nazwa pliku>.json`; dokument spoza trzech klas dostaje plik z samym `{}`.

Ten sam program uruchamia `python main.py`; `--rules` wymusza tryb bez modelu, a `--input` / `--output` wskazują inne katalogi. Panel WWW do przeglądania i poprawiania wyników startuje przez `start.bat` (sekcja „Panel WWW”).

## Uruchomienie

Wymagany jest Python 3.13 lub nowszy. Utwórz środowisko i zainstaluj zależności.

```powershell
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe main.py
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m pytest -q
```

Na Linuksie używaj `python3.13 -m venv .venv` i `.venv/bin/python`. Umieść np. `pismo.pdf` pod `input/case1/`. Wynik pojawi się w `output/case1/pismo.json`. Argumenty `--input` i `--output` wybierają inne katalogi. Dokument spoza obsługiwanych klas dostaje plik o tej samej nazwie z samym `{}` (wymóg UZP); `--negative-output empty_file` zapisuje zamiast tego pusty plik. CLI zgłasza dokumenty, których nie udało się odczytać, zapisuje dla nich `{}` i przechodzi do następnego pliku. Uruchomienie na świeżym `output/` ułatwia oddzielenie bieżących wyników od poprzednich przebiegów.

## Panel WWW

Panel do przetwarzania spraw w przeglądarce jest serwowany przez to samo API, pod jednym adresem. Po jednorazowej instalacji `.venv` (sekcja „Uruchomienie”) uruchom w katalogu repozytorium:

```powershell
.\start.bat
```

Skrypt startuje serwer na http://127.0.0.1:8000/ i otwiera tam przeglądarkę. Ctrl+C zatrzymuje serwer. Inny port ustawia zmienna `PORT`, a `NO_BROWSER=1` wyłącza otwieranie przeglądarki. Na Linuksie i macOS służy do tego `./start.sh`. Gdy `.env` zawiera konfigurację modelu, API korzysta z LLM, a panel pokazuje nazwę modelu przy wyniku. Bez niej działa tryb regułowy. Ten sam serwer wystawia `docker compose up --build api`. Opis panelu jest w [frontend/README.md](frontend/README.md). Nowy typ dokumentu administrator dodaje w panelu (menu ☰ → „Typy dokumentów”): kreator zapisuje YAML i schemat na serwerze, który od razu zaczyna go rozpoznawać, bez restartu ([docs/ADD_DOCUMENT_TYPE.md](docs/ADD_DOCUMENT_TYPE.md)).

## Tryb LLM

Ustaw `LLM_BASE_URL` na bazę zgodnego API Chat Completions, np. adres zakończony `/v1`, `LLM_MODEL` na nazwę obsługiwaną przez ten endpoint i `LLM_API_KEY` w środowisku procesu lub w lokalnym `.env`. Obsługiwana jest także nazwa `API_KEY`. Zmienne procesu mają pierwszeństwo przed `.env`. Endpoint Chat Completions musi obsługiwać `response_format: json_object`. Wywołanie `--llm` przesyła tekst stron PDF do skonfigurowanego API. Do danych konkursowych wybierz otwarty model i zweryfikuj, że firma oraz serwery API są w UE/EOG. [Wymagania UZP](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026#6-spos%C3%B3b-testowania-i-walidacji)

```powershell
.venv/Scripts/python.exe main.py --llm --input ./input --output ./output
```

Model dostaje instrukcje i schematy w wiadomości `system`, a tekst stron w `user`. Zwraca `typ` i `dane`. Dla `unknown` CLI stosuje tryb wyniku negatywnego, a dla rozpoznanej klasy zapisuje zwalidowane `dane`. Do porównania wersji użyj `--prompt ścieżka.md` i oddzielnych katalogów `--output` przy tym samym modelu i zbiorze. Reguły klasy można dopisać w jej YAML jako `options.llm_instructions`.

Przy dużych zbiorach żądania w jednym procesie są szeregowane i domyślnie dzieli je co najmniej sekunda. Odpowiedź HTTP 429 powoduje ponowienie, z uwzględnieniem nagłówka `Retry-After` albo rosnącego czasu oczekiwania. Tempo i limity ustawiają zmienne `LLM_REQUEST_INTERVAL_SECONDS` (domyślnie `1`), `LLM_MAX_429_RETRIES` (`4`) oraz `LLM_MAX_RETRY_WAIT_SECONDS` (`60`). Ostatni parametr ogranicza pojedyncze oczekiwanie. Po wyczerpaniu ponowień dokument otrzymuje błąd `llm_rate_limit`, a batch przechodzi do następnego pliku. Ponowienia 429 mogą zwiększyć liczbę żądań na PDF.

Odstęp dopasuj do limitów żądań oraz tokenów konkretnego konta i modelu. Koordynacja obejmuje wątki jednego procesu. Jednoczesne osobne procesy CLI, pracownicy serwera lub instancje kontenerów mają oddzielne limity, więc dla wspólnego klucza należy uwzględnić ich łączny ruch.

Do natywnego Claude Messages ustaw `LLM_PROVIDER=anthropic`, `LLM_BASE_URL=https://api.anthropic.com/v1`, identyfikator Sonnet w `LLM_MODEL` oraz klucz w `LLM_API_KEY` lub `API_KEY`. Adapter używa strukturalnej koperty JSON, a pełny schemat dokumentu waliduje lokalnie. Próby deweloperskie Claude Sonnet na danych syntetycznych zostały wykonane. Warunki UZP dotyczące otwartego modelu oraz lokalizacji dostawcy i serwerów opisano w dokumentacji projektu.

API uruchom przez `.venv/Scripts/python.exe -m uvicorn --app-dir src kio_extract.api:create_app --factory --host 127.0.0.1 --port 8000`. Gdy `LLM_MODEL` jest ustawiony, API korzysta z LLM. W innym przypadku działa tryb regułowy. `POST /api/extract` przyjmuje pola `files` według [kontraktu](docs/INTERFACES.md#api-dla-frontendu).

Do integracji frontendu na syntetycznych PDF-ach uruchom `.venv/Scripts/python.exe tests/support/fake_llm_server.py` w osobnym terminalu. W terminalu API ustaw `$env:LLM_PROVIDER='chat'`, `$env:LLM_BASE_URL='http://127.0.0.1:8765/v1'` i `$env:LLM_MODEL='fixture'`, a następnie uruchom API podaną komendą. Atrapa rozpoznaje syntetyczny tekst potwierdzenia przelewu i zwraca puste pola zgodne ze schematem.

Skany (strony bez warstwy tekstowej) nie wymagają dodatkowych programów: pypdfium2 renderuje stronę do JPEG, a ten sam model (Qwen3.5 9B jest multimodalny) przepisuje jej tekst, który idzie dalej zwykłą ścieżką tekstową. Ustawienia: `SCAN_OCR` (`auto` domyślnie: model, gdy jest skonfigurowany, inaczej Tesseract, jeśli jest w `PATH`; także `llm`, `tesseract`, `none`), `SCAN_MODE` (`transcribe` domyślnie albo `image`: obrazy stron od razu w zapytaniu ekstrakcji), `SCAN_MAX_PAGES` (domyślnie 4: pierwsze trzy strony i ostatnia; 0 = wszystkie), `SCAN_SCALE` (1.5) i `SCAN_JPEG_QUALITY` (80). Tryb regułowy korzysta z Tesseracta (z danymi `pol`), gdy jest zainstalowany.

Plik wyniku powstaje dla każdego PDF-u. Gdy zapytanie do modelu ostatecznie zawiedzie (połączenie, limit, niepoprawny JSON lub schemat), wynik powstaje regułami z `configs/documents` (raport przebiegu: pole `fallback`), a dokument nierozpoznany dostaje `{}`. Nieczytelny PDF również dostaje `{}` (raport: `status: error`, `written: negative`); `--on-error skip` przywraca pomijanie pliku.

## Lokalny pomiar

Manifest `evaluation/manifest.json` zawiera podział spraw UZP 01–42 na rozwój, 43–54 na walidację oraz 55–60 na końcowy test. Ewaluator porównuje wcześniej zapisane wyniki i nie wywołuje modelu. Przyjmuje lokalną kopię danych UZP oraz katalog wynikowy o takiej samej strukturze jak katalog danych.

Wyniki eksperymentów i ograniczenia pomiaru opisuje [porównanie modeli](docs/MODEL_COMPARISON.md). Przykładowy sposób rozszerzenia konfiguracji opisuje [instrukcja dodania klasy](docs/ADD_DOCUMENT_TYPE.md).

```powershell
.venv/Scripts/python.exe evaluation/evaluate.py --manifest evaluation/manifest.json --data .local/uzp-reference/dane --predictions .local/batch-uzp --split validation --output artifacts/baseline.json
```

Raport opisuje lokalny micro-F1, wyniki według pól i klas, macierz klasyfikacji oraz błędy. W obrębie list obiektów dopasowuje jednoznaczne identyfikatory, a pozostałe wartości porównuje jako wielozbiory. Ta metryka służy do porównywania wersji projektu.

Wynik pomiaru LLM można opatrzyć argumentami `--model`, `--revision` i `--prompt-version`, aby kolejne raporty wskazywały użyty model oraz wersję kodu i prompta.

Przy ponawianiu przetwarzania użyj opcji CLI `--report artifacts/run.json`, a następnie przekaż evaluatorowi `--run-report artifacts/run.json`. Raport przechowuje status i skrót zapisanego pliku. Evaluator traktuje błąd dokumentu, brak wpisu oraz zmieniony wynik jako błąd, również gdy w `output/` znajduje się plik z wcześniejszego przebiegu. Raport powstaje po zakończeniu batcha, dlatego dla każdego nowego uruchomienia używaj odrębnej ścieżki raportu.

Kontenery można uruchomić przez `docker compose run --build --rm batch` lub `docker compose up --build api`. Obraz instaluje Tesseract i pakiet języka polskiego. Batch korzysta z LLM, gdy środowisko go konfiguruje (np. plik `.env`); `--rules` wymusza tryb regułowy.

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
