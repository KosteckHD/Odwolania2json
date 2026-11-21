# Tablica zadań

Główna ścieżka wykorzystuje jeden [system prompt](../prompts/system_pl.md) i jedno wywołanie LLM na PDF. Backend odpowiada za jakość ekstrakcji wszystkich klas. Frontend przejmuje obsługę plików i prezentację wyników. Łączy je [kontrakt HTTP](INTERFACES.md#api-dla-frontendu).

| ID | Zadanie | Osoba | Priorytet | Status | Zależności | Kryterium akceptacji |
| --- | --- | --- | --- | --- | --- | --- |
| BE01 | CLI, schematy, prompt i adapter LLM | Backend | P0 | DONE | — | Test potwierdza jedno żądanie na PDF, walidację odpowiedzi i zapis w schemacie UZP. |
| BE02 | Wspólny procesor i endpoint dla panelu | Backend | P0 | IN PROGRESS | BE01 | CLI i `POST /api/extract` współdzielą ekstrakcję i walidację. API zachowuje kolejność i obsługuje częściową awarię. Pozostaje próba z frontendem. |
| BE03 | Próba Sonnet i weryfikacja docelowego LLM | Backend | P0 | IN PROGRESS | BE01, U06 | Sonnet odpowiedział na syntetyczny PDF oraz próbki UZP. Pozostaje weryfikacja konfiguracji konkursowej zgodnie z U06. |
| BE04 | Ewaluacja i poprawki prompta | Backend | P0 | IN PROGRESS | BE03 | Zmierzono 12 spraw walidacyjnych i jeden syntetyczny negatyw, lokalny F1 0,9859; porównano modele na 9 PDF i dodano 5 syntetycznych regresji prompta. Pozostaje szerszy test negatywów i próba konkursowego modelu na zbiorze końcowym. |
| BE05 | OCR na CPU | Backend | P0 | IN PROGRESS | BE01 | Skan UZP, dokument mieszany i całkowicie biała strona przeszły przez renderer w kontenerze. Pozostaje pomiar na szerszym zbiorze. |
| BE06 | Uruchomienie i wydanie | Backend | P0 | IN PROGRESS | BE02, BE04, BE05 | Obraz zbudowano od podstaw, batch przetworzył skan i negatyw UZP. Pozostaje próba docelowego LLM i wspólny test z panelem. |
| FE01 | Wybór wielu PDF-ów i lista wyników na atrapie | Frontend | P0 | TODO | Przykładowa odpowiedź | Panel pokazuje stan oczekiwania oraz `ok`, `unknown` i `error` per dokument. |
| FE02 | Podgląd i pobranie JSON | Frontend | P0 | TODO | FE01 | Pobranie rozpoznanego pliku zachowuje nazwę i zawiera tylko jego `data`. |
| FE03 | Integracja z API | Frontend | P0 | TODO | FE01, BE02 | Wysłanie kilku plików, obsługa błędu HTTP i częściowej awarii, ponowienie. |
| FE04 | Test wspólny i demo | Frontend | P0 | TODO | FE02, FE03 | Scenariusz od wgrania rzeczywistych PDF-ów do pobrania wyników i krótka instrukcja panelu. |
| FE05 | Pobranie wyników jako ZIP | Frontend | P1 | TODO | FE04 | Jedno pobranie wszystkich poprawnych wyników. |

U01–U07 są śledzone w [pytaniach do mentora](OPEN_QUESTIONS.md). Zadanie zależne od nieuzyskanej decyzji przechodzi w `BLOCKED` z opisem warunku wznowienia.

Szczegółowe kroki i testy BE01–BE06 są w [instrukcji dla agenta backendu](prompts/BACKEND.md).
