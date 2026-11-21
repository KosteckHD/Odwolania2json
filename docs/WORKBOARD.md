# Tablica zadań

Główna ścieżka wykorzystuje jeden [system prompt](../prompts/system_pl.md) i jedno wywołanie LLM na PDF. Backend odpowiada za jakość ekstrakcji wszystkich klas. Frontend przejmuje obsługę plików i prezentację wyników. Łączy je [kontrakt HTTP](INTERFACES.md#api-dla-frontendu).

| ID | Zadanie | Osoba | Priorytet | Status | Zależności | Kryterium akceptacji |
| --- | --- | --- | --- | --- | --- | --- |
| BE01 | CLI, schematy, prompt i adapter LLM | Backend | P0 | DONE | — | Test potwierdza jedno żądanie na PDF, walidację odpowiedzi i zapis w schemacie UZP. |
| BE02 | Endpoint dla panelu | Backend | P0 | TODO | BE01 | `POST /api/extract` zwraca wynik każdego PDF-u w kolejności wejścia i obsługuje częściową awarię. |
| BE03 | Test docelowego LLM | Backend | P0 | TODO | BE01, U06 | Zweryfikowana licencja i lokalizacja API. Jedna rzeczywista sprawa przechodzi od PDF do JSON. |
| BE04 | Ewaluacja i poprawki prompta | Backend | P0 | TODO | BE03 | Lokalny F1 według klasy i pola. Regresje dla pierwszego zarzutu, ról osób, kierunku rachunku i negatywów. |
| BE05 | OCR na CPU | Backend | P0 | TODO | BE01 | Skan i dokument mieszany przechodzą test na CPU. |
| BE06 | Uruchomienie i wydanie | Backend | P0 | TODO | BE02, BE04, BE05 | Czysta instalacja, instrukcja startu, Compose i wspólny test z panelem. |
| FE01 | Wybór wielu PDF-ów i lista wyników na atrapie | Frontend | P0 | TODO | Przykładowa odpowiedź | Panel pokazuje stan oczekiwania oraz `ok`, `unknown` i `error` per dokument. |
| FE02 | Podgląd i pobranie JSON | Frontend | P0 | TODO | FE01 | Pobranie rozpoznanego pliku zachowuje nazwę i zawiera tylko jego `data`. |
| FE03 | Integracja z API | Frontend | P0 | TODO | FE01, BE02 | Wysłanie kilku plików, obsługa błędu HTTP i częściowej awarii, ponowienie. |
| FE04 | Test wspólny i demo | Frontend | P0 | TODO | FE02, FE03 | Scenariusz od wgrania rzeczywistych PDF-ów do pobrania wyników i krótka instrukcja panelu. |
| FE05 | Pobranie wyników jako ZIP | Frontend | P1 | TODO | FE04 | Jedno pobranie wszystkich poprawnych wyników. |

U01–U07 są śledzone w [pytaniach do mentora](OPEN_QUESTIONS.md). Zadanie zależne od nieuzyskanej decyzji przechodzi w `BLOCKED` z opisem warunku wznowienia.
