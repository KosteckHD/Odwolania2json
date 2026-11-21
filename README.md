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

Ustaw `LLM_BASE_URL` na bazę zgodnego API Chat Completions, np. adres zakończony `/v1`, `LLM_MODEL` na nazwę obsługiwaną przez ten endpoint i `LLM_API_KEY` w środowisku procesu. Endpoint musi obsługiwać `response_format: json_object`. Wywołanie `--llm` przesyła tekst stron PDF do skonfigurowanego API. Do danych konkursowych wybierz otwarty model i zweryfikuj, że firma oraz serwery API są w UE/EOG. [Wymagania UZP](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026#6-spos%C3%B3b-testowania-i-walidacji)

```powershell
.venv/Scripts/python.exe main.py --llm --input ./input --output ./output
```

Model dostaje instrukcje i schematy w wiadomości `system`, a tekst stron w `user`. Zwraca `typ` i `dane`. Dla `unknown` CLI stosuje tryb wyniku negatywnego, a dla rozpoznanej klasy zapisuje zwalidowane `dane`. Do porównania wersji użyj `--prompt ścieżka.md` i oddzielnych katalogów `--output` przy tym samym modelu i zbiorze. Reguły klasy można dopisać w jej YAML jako `options.llm_instructions`.

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
