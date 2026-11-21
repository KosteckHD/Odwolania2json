# Tablica zadań

| ID | Zadanie | Osoba | Priorytet | Status | Zależności | Kryterium akceptacji |
| --- | --- | --- | --- | --- | --- | --- |
| A01 | Audyt UZP i kontrakty | A | P0 | DONE | — | README, regulamin, pliki i rozbieżności mają źródła, a testy sprawdzają DTO. |
| A02 | CLI, registry, schematy, fixtures | A | P0 | DONE | A01 | Tekstowy PDF przechodzi do JSON, schemat odrzuca nadmiarowe klucze, czwarta klasa działa z samej konfiguracji. |
| A03 | Bazowa klasyfikacja i regresja na danych | A | P0 | IN PROGRESS | A02 | Macierz klas i fałszywe pozytywy znane na stałym podziale. Negatyw i myląca nazwa w regresji. |
| A04 | OCR na CPU | A | P0 | TODO | A02 | Strona obrazowa i mieszana odzyskuje tekst, adapter zachowuje kolejność i limit czasu. |
| A05 | Integracja modułów i lokalny evaluator | A | P0 | TODO | A02, B01, C01, C02 | Jedna sprawa do 6 h. Raport dla trzech klas i pól do 11 h. |
| A06 | Compose, limity i wydanie | A | P0 | TODO | A03, A04, A05, B04, C03 | Clean install, wynik na CPU z limitem 16 GB, licencje, komenda startu i demo czwartej klasy. |
| A07 | Adapter LLM | A | P1 | TODO | A05, U06 | Weryfikacja modelu i regionu, timeout, brak kluczy w logach, test z atrapą. |
| B01 | Ekstraktor odwołania i testy tekstowe | B | P0 | TODO | A01 | Nagłówek i podstawowe dane w zgodnej strukturze, samodzielny `pytest`. |
| B02 | Podmioty i zamówienie | B | P0 | TODO | B01 | Właściwy lider i pełnomocnik, oddzielne BZP/TED, identyfikatory jako tekst. |
| B03 | Pierwszy zarzut | B | P0 | TODO | B01 | Drugi zarzut daje inny rodzaj zdarzenia, lecz nie wpływa na datę, ID i opis pierwszego. |
| B04 | Regresja i walidacja spraw | B | P0 | TODO | B02, B03, A05 | Zamrożony zbiór, wyniki per pole i lista naprawionych błędów. |
| B05 | Ekstrakcja semantyczna zarzutów | B | P1 | TODO | B04, A07 | Poprawa na tym samym zbiorze, udokumentowany fallback. |
| C01 | Przelew na fixture i warianty bankowe | C | P0 | TODO | A01 | Role rachunków, kwota, daty, tytuł i ID przy wariantach układu. |
| C02 | Pełnomocnictwo i relacje | C | P0 | TODO | A01 | Dwa typy mocodawcy, właściwi podpisujący, pełnomocnicy i PESEL. |
| C03 | Regresja i walidacja spraw | C | P0 | TODO | C01, C02, A05 | Testy obu klas niezależne, porównanie błędów per pole. |
| C04 | Dalsze układy lub odmiana nazwisk | C | P1 | TODO | C03 | Poprawa na zamrożonym zbiorze. |

U01–U07 są śledzone w [pytaniach do mentora](OPEN_QUESTIONS.md). Podzadanie przechodzi w `BLOCKED`, jeśli brakuje decyzji potrzebnej do jego odbioru. Właściciel zapisuje wtedy warunek wznowienia i kontynuuje niezależne zadania.
