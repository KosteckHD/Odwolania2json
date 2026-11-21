# Odwołania2JSON

Fundament aplikacji konkursowej HackNation 2026, która przetwarza sprawy KIO partiami na CPU. CLI odczytuje PDF-y, klasyfikuje treść i waliduje JSON przed zapisem. Strategia startowa wyciąga etykietowaną datę operacji i kwotę przelewu oraz tworzy struktury dla pozostałych klas. Pełne ekstraktory, OCR, evaluator i Compose są na tablicy zadań.

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

Strategia konfigurowalna przyjmuje YAML w `configs/documents/` i JSON Schema w `schemas/`. Dodanie klasy z istniejącą strategią regex nie wymaga zmiany Pythona. Własne zestawy można przekazać przez `--configs` i `--schemas`. Format konfiguracji i przykład testu opisuje [kontrakt](docs/INTERFACES.md).

Zależności wykonawcze działają lokalnie na CPU. Ich licencje to BSD-3-Clause dla `pypdf` oraz MIT dla PyYAML i `jsonschema`. [pypdf](https://pypi.org/project/pypdf/6.18.0/), [PyYAML](https://pypi.org/project/PyYAML/6.0.3/), [jsonschema](https://pypi.org/project/jsonschema/4.26.0/)

## Start zespołu

- [Podział A/B/C, własność plików i zależności](docs/WORK_SPLIT_3.md)
- [Harmonogram 22 godzin i integracja](docs/INTEGRATION_PLAN.md)
- [Tablica zadań](docs/WORKBOARD.md)
- [Zweryfikowane wymagania i pytania do UZP](docs/OPEN_QUESTIONS.md)
- Prompty startowe [A](docs/prompts/A_CORE.md), [B](docs/prompts/B_ODWOLANIE.md) i [C](docs/prompts/C_PELNOMOCNICTWO_PRZELEW.md)
