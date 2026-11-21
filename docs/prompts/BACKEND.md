# Prompt startowy · Backend

Pracujesz nad backendem Odwołania2JSON w dwuosobowym zespole HackNation 2026. Twoim wynikiem jest przetworzenie sprawy KIO na pliki JSON zgodne z UZP przez CLI i API. Pracuj na `feat/core-engine`. Masz własność `main.py`, `src/kio_extract/`, `prompts/`, `configs/`, `schemas/`, testów Pythona, ewaluacji i uruchomienia backendu. Przeczytaj `docs/WORK_SPLIT_2.md`, `docs/INTERFACES.md`, `docs/INTEGRATION_PLAN.md`, `docs/WORKBOARD.md` i `docs/OPEN_QUESTIONS.md`.

1. P0 do 6 h. Udostępnij `POST /api/extract` według kontraktu w `docs/INTERFACES.md`. Rozdziel część wspólną przetwarzania od kodu wejścia CLI i HTTP. Daj frontendowi działającą integrację z testowym dostawcą. Testuj zestaw, w którym jeden dokument ma błąd.
2. P0 do 11 h. Uruchom jedno wywołanie LLM na PDF na zweryfikowanym otwartym modelu z API UE/EOG. Waliduj `dane` według schematu klasy. Zmierz klasyfikację i lokalny F1 według pola na stałym podziale spraw. Sprawdź negatywy i skany wymagające OCR.
3. P0 do 19 h. Doskonal wspólny prompt na podstawie FP/FN, zwłaszcza pierwszego zarzutu, relacji osób i kierunku rachunków. Podłącz OCR dla skanów. Utrzymaj działające CLI i przygotuj instrukcję uruchomienia z API i frontendem.
4. Do 22 h przeprowadź z frontendem próbę na rzeczywistej sprawie. Zapisz użyty model, lokalny wynik i ograniczenia. Sekret dostawcy pozostaje w otoczeniu procesu backendu.

Uruchamiaj `python -m pytest -q`. Testy obejmują trzy klasy, negatyw, błąd OCR lub modelu, zachowanie kolejności i schemat payloadu UZP. Frontend może pracować w tym czasie na `docs/fixtures/extract-response.json`. Zmiany formatu HTTP uzgadniaj z jego właścicielem.
