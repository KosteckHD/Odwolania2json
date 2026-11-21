# Prompt startowy · Frontend

Pracujesz nad frontendem Odwołania2JSON w dwuosobowym zespole HackNation 2026. Twoim wynikiem jest prosty panel do wgrania PDF-ów jednej sprawy, sprawdzenia odpowiedzi i pobrania JSON. Pracuj na proponowanej gałęzi `feat/frontend`. Masz własność `frontend/`, w tym klienta HTTP, atrapy, testów UI i instrukcji uruchomienia panelu. Przeczytaj `docs/WORK_SPLIT_2.md`, `docs/INTERFACES.md`, `docs/INTEGRATION_PLAN.md` i `docs/WORKBOARD.md`.

1. P0 do 6 h. Zbuduj jeden ekran demonstracyjny z wyborem kilku PDF-ów, stanem przetwarzania i wynikami poszczególnych dokumentów. Zacznij od danych z `docs/fixtures/extract-response.json`. Sprawdź poprawny wynik, negatyw i błąd w jednym wsadzie.
2. P0 do 11 h. Podłącz `POST /api/extract`. Wyświetl nazwę pliku, rozpoznaną klasę i status. Dodaj podgląd i pobranie JSON dla rozpoznanego dokumentu. Błędy mają informować, którego PDF-u dotyczą, a pozostałe wyniki wciąż są dostępne.
3. P0 do 19 h. Sprawdź przebieg z klawiatury, pusty wybór, ponowne wysłanie po błędzie i zachowanie podczas wolnej odpowiedzi. Przećwicz scenariusz od plików do pobrania wyników na rzeczywistej sprawie. Opcjonalny ZIP trafia do P1.
4. Do 22 h przygotuj krótkie demo. Interfejs wywołuje API backendu, które obsługuje ekstrakcję i dostęp do modelu.

Testy obejmują wysłanie plików jako osobnych pól `files` i obsługę trzech statusów odpowiedzi. Zmiany formatu HTTP uzgadniaj z backendem. Atrapa ma pozostać dostępna do pracy i testów bez dostawcy LLM.
