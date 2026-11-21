# Integracja i harmonogram

| Czas od startu | A | B | C | Bramka |
| --- | --- | --- | --- | --- |
| 0–1 h | Audyt, kontrakt do 0:45, wspólna baza, trzy gałęzie, fixture i atrapa | Zaimportować API, przeczytać wzorzec i zbudować fixtures odwołania | Zaimportować API i przygotować osobne fixtures dla obu klas | Każdy uruchamia test w izolacji, format API zamrożony na fazę 1 |
| 1–6 h | CLI, tekst PDF, YAML, klasyfikator, walidacja ścieżek | Pierwsze pola nagłówka, role i zamówienie | Pierwszy ekstraktor przelewu i pełnomocnictwa | Jedna tekstowa sprawa end-to-end, plus negatyw, pokazana wspólnie do 6 h |
| 6–11 h | OCR, rejestracja trzech strategii, evaluator | Pierwszy zarzut, identyfikatory, konsorcja, BZP i TED | Rachunki i kwoty, relacje i podpisujący, test PESEL | Trzy klasy mają ścisłą strukturę, działają skany, pierwszy raport lokalny |
| 11–16 h | Poprawki klasyfikacji i OCR, kontrola czasu. Adapter API po weryfikacji | Naprawić najczęstsze błędy przypisania i zarzutów | Naprawić najczęstsze błędy bankowe i podmiotowe | Porównanie z tym samym zbiorem walidacji, bez regresji krytycznych |
| 16–19 h | Compose, clean install, CPU bez GPU i limit 16 GB, demo czwartej klasy | Sprawy odłożone, regresje typów i zagnieżdżeń | Sprawy odłożone, skany z różnymi układami banków | Wersja uruchamialna przez jury i instrukcja bez założeń o środowisku |
| 19–22 h | Zamrożenie funkcji, finalny test, licencje, README i demo | Kontrola końcowych wyników odwołań | Kontrola końcowych wyników obu własnych klas | Gotowy link zgłoszenia i instrukcja, komplet wyników przykładu |

## Kolejność i Git

1. A przygotowuje wspólny commit z `contracts.py`, registry, schematami, dokumentacją i fixtures. `main` przyjmuje go przez pierwszy PR. Wszystkie trzy gałęzie mogą startować równocześnie z tego samego commita, również gdy review fundamentu trwa.
2. Właściciele pracują na `feat/core-engine`, `feat/odwolanie-extraction` i `feat/pelnomocnictwo-przelew`. Osobny klon lub worktree jest opcjonalny.
3. B i C rejestrują swój moduł przez `extractor:` w swoim YAML, kiedy pojawi się implementacja i przejdą jej testy wejścia/wyjścia. A wykorzystuje domyślną strategię YAML do etapu integracji. Małe PR-y łącz w kolejności gotowości, z integracją w 6, 11 i 16 h.
4. A integruje. Nagłówek PR podaje właściciela, zmianę zachowania, komendę testu i wynik. A sprawdza `python -m pytest -q` i E2E po połączeniu. Własność plików obowiązuje także przy poprawkach review.
5. Konflikt przekazuje się właścicielowi pliku. Przy zmianie wspólnego API A uzgadnia z B/C jedną zmianę kontraktu, testy i kolejność wdrożenia. Synchronizacja przez merge z `main`, bez force push i przepisywania współdzielonej historii.

## Kontrole odbioru

| Kontrola | Wykonanie |
| --- | --- |
| Kompatybilność modułów | `python -m pytest -q tests/test_contracts.py`. Fixture tekstowa, wczytanie każdego schematu, atrapa ekstraktora, wynik tylko z polami schematu. |
| Ekstrakcja B i C | `python -m pytest -q tests/test_odwolanie.py` oraz `python -m pytest -q tests/test_pelnomocnictwo.py tests/test_przelew.py` po dodaniu modułów. Jedna strategia ma działać samodzielnie bez parsera lub API. |
| Batch | `python -m pytest -q`, następnie nowy `output/` i realna sprawa. Sprawdzić PDF tekstowy oraz obrazowy, negatyw, losową nazwę, zagnieżdżone sprawy, ponowienie i typy. |
| Wydanie | Świeża instalacja Python 3.13+ i `docker compose run --build --rm batch` po dostarczeniu Compose. Potwierdzić obsługę CPU, limit pamięci, instrukcję i zależności. |

## Lokalna ewaluacja

Przed dostrajaniem A zapisuje podział całych spraw, np. 01–42 rozwój, 43–54 walidacja, 55–60 test końcowy. Oddzielnie zamraża przypadki negatywne, grupując kopie PDF po hashu, żeby odpowiedniki z katalogu spraw i `negatywne/` trafiały do tego samego zbioru. Etykiety oficjalne są jawne i służą do lokalnej weryfikacji. Walidacja zespołu oraz test końcowy mają określone zasady użycia.

Evaluator dopasowuje PDF do etykiety po sprawie i jawnej mapie nazw, z `potwierdzenie_przelewu.pdf` → `przelew.json`. Traktuje puste pliki jako `unknown`, a brak pliku lub nadmiarowy plik jako błąd. Skalary porównuje według ścieżki i typu, agreguje wielozbiory, ignoruje robocze `null` i puste napisy jako brak danych. Dla list dopasowuje obiekty po identyfikatorze lub jednoznacznej nazwie przed oceną pól. Gdy brakuje klucza łączenia, raportuje przypadek i stosuje udokumentowaną regułę porównania, zachowując duplikaty.

Raport zawiera TP, FP, FN i `2TP/(2TP+FP+FN)` globalnie, per typ i per pole, liczbę etykiet, macierz klas, negatywne FP, błędy OCR/schematu, czas i szczyt pamięci. Zapisuj do `artifacts/`. Porównuj kolejne wersje na tym samym podziale. Algorytm oficjalnej punktacji pozostaje pytaniem U02. Przy sprzecznościach etykiet zachowuj bazę i dołącz osobną notatkę, żeby raporty były porównywalne.

## Próba fundamentu na danych UZP

Python 3.13.16 ukończył `python -m pytest -q` z wynikiem 8 zaliczonych testów. Batch na 196 PDF-ach zestawu UZP wygenerował 193 pliki i zwrócił kod 1 z powodu trzech negatywów wymagających OCR. Klasyfikacja według etykiet treningowych rozpoznała 60 z 60 odwołań, 58 z 60 pełnomocnictw i 54 z 60 przelewów. Pozostałe 8 dokumentów tych klas otrzymało `unknown`. Każdy z 13 czytelnych negatywów dostał pusty plik. Przetwarzanie przykładu 07 dało datę przelewu zgodną z referencją. Strategia przelewu uzupełniła co najmniej jedno pole w 5 plikach. To pomiar uruchomienia i pokrycia na zbiorze treningowym. Pomiar jakości ekstrakcji na zamrożonym podziale pozostaje w A05.

Po umieszczeniu lokalnej kopii repozytorium UZP w `.local/uzp-reference` polecenie użyte do próby to:

```powershell
.venv/Scripts/python.exe main.py --input .local/uzp-reference/dane --output .local/batch-uzp
```
