# Tablica zadań

Główna ścieżka wykorzystuje jeden [system prompt](../prompts/system_pl.md) i jedno wywołanie LLM na PDF. Backend odpowiada za jakość ekstrakcji wszystkich klas. Frontend przejmuje obsługę plików i prezentację wyników. Łączy je [kontrakt HTTP](INTERFACES.md#api-dla-frontendu).

| ID | Zadanie | Osoba | Priorytet | Status | Zależności | Kryterium akceptacji |
| --- | --- | --- | --- | --- | --- | --- |
| BE01 | CLI, schematy, prompt i adapter LLM | Backend | P0 | DONE | — | Test potwierdza jedno żądanie na PDF, walidację odpowiedzi i zapis w schemacie UZP. |
| BE02 | Wspólny procesor i endpoint dla panelu | Backend | P0 | DONE | BE01 | CLI i `POST /api/extract` współdzielą ekstrakcję oraz walidację; API zachowuje kolejność, częściowe awarie i aktywne typy. Test API, test przeglądarki i uruchomienie Compose przechodzą. |
| BE03 | Próba Sonnet i weryfikacja docelowego LLM | Backend | P0 | IN PROGRESS | BE01, U06 | Ministral 3 8B/14B jest dostępny w UE; licencje kart modeli to Apache 2.0. Techniczny smoke 8B przeszedł. Pełne porównanie 220 plików przerwano po HTTP 429; nie ma wyboru modelu na podstawie F1. |
| BE04 | Ewaluacja i poprawki prompta | Backend | P0 | IN PROGRESS | BE03 | Zmierzono 12 spraw walidacyjnych i syntetyczny negatyw, lokalny F1 0,9859; porównano historyczne modele na małych próbkach, dodano regresje prompta i manifest 30 skanów. Pełne porównanie konkursowe i test 55–60 pozostają do wykonania. |
| BE05 | OCR na CPU | Backend | P0 | IN PROGRESS | BE01 | Pomiar 30 skanów UZP daje odczyt 238/266 pól; obsłużono adaptacyjne progowanie i dodano ponowny OCR wycinka rachunku z kontrolą NRB. Dalsza ocena wycinka na skanach jest opisana w `docs/SKANY.md`. |
| BE06 | Uruchomienie i wydanie | Backend | P0 | DONE | BE02, BE04, BE05 | Czysta kopia zbudowała obraz i uruchomiła API z montowaną konfiguracją klas. Wspólny start, panel i API opisano w README oraz `docs/DEMO.md`; wynik benchmarku modelu pozostaje osobnym blokerem BE03/BE04. |
| FE01 | Wybór wielu PDF-ów i lista wyników na atrapie | Frontend | P0 | DONE | Przykładowa odpowiedź | Testy i próba w przeglądarce potwierdzają statusy `ok`, `unknown` i `error` dla wielu plików. |
| FE02 | Podgląd i pobranie JSON | Frontend | P0 | DONE | FE01 | Widok JSON i pobranie danych dokumentu są sprawdzone; formularze są wyświetlane obok podglądu PDF. |
| FE03 | Integracja z API | Frontend | P0 | DONE | FE01, BE02 | Wysłanie wielu plików, błędy HTTP, częściowa awaria i obsługa anulowania mają testy; API zweryfikowano w przeglądarce. |
| FE04 | Test wspólny i demo | Frontend | P0 | DONE | FE02, FE03 | Przygotowano scenariusz pokazu i zrzuty; interfejs zintegrowano z API i sprawdzono na PDF-ach syntetycznych. |
| FE05 | Pobranie wyników jako ZIP | Frontend | P1 | DONE | FE04 | ZIP zachowuje nazwy, ścieżki sprawy i pusty wynik dla dokumentu `unknown`; potwierdzone testami. |

U01–U08 są śledzone w [pytaniach do mentora](OPEN_QUESTIONS.md). Zadanie zależne od nieuzyskanej decyzji przechodzi w `BLOCKED` z opisem warunku wznowienia.

Szczegółowe kroki i testy BE01–BE06 są w [instrukcji dla agenta backendu](prompts/BACKEND.md).
