# Integracja i harmonogram

| Czas od startu | Backend | Frontend | Bramka |
| --- | --- | --- | --- |
| 0–1 h | Uzgodnienie kontraktu, przykład odpowiedzi i weryfikacja warunków dostępu do LLM | Szkic jednego ekranu i uruchomienie atrapy z przykładową odpowiedzią | Obie strony pracują na tym samym kontrakcie |
| 1–6 h | Endpoint HTTP wykorzystujący istniejący pipeline. Testowy dostawca LLM do integracji | Wybór kilku PDF-ów, stan przetwarzania, lista wyników i pierwsze połączenie z API | Jedna sprawa przechodzi przez UI i backend z kontrolowaną odpowiedzią modelu |
| 6–11 h | Test na docelowym modelu, pierwszy lokalny pomiar F1 i regresje dla trzech klas | Podgląd i pobranie JSON, negatywy, częściowe błędy, ponowienie | Rzeczywista sprawa od PDF do JSON i pierwsza baza porównawcza jakości |
| 11–16 h | OCR na CPU i poprawki prompta według błędów z walidacji | Próby skanów, błędów i wolnego API, obsługa z klawiatury | Odbiór skanu oraz powtórny pomiar na tym samym zbiorze |
| 16–19 h | Czysty start CLI i API, limity, licencje, Compose | Integracja docelowa, instrukcja panelu i próba demo | Wspólna próba na rzeczywistych PDF-ach i gotowa instrukcja |
| 19–22 h | Końcowy test i zapis modelu, metryk i ograniczeń | Końcowy test pobierania i demo | Gotowy przebieg do zgłoszenia i prezentacji |

## Kolejność i Git

1. Backend pracuje na `feat/core-engine`. Dla frontendu zaplanowana jest gałąź `feat/frontend` ze wspólnej bazy zawierającej [kontrakt](INTERFACES.md) i [próbkę](fixtures/extract-response.json).
2. Frontend zaczyna na atrapie. Backend podłącza endpoint do tego samego przepływu ekstrakcji i walidacji co CLI. Adapter LLM można zastąpić atrapą podczas pierwszego spięcia.
3. Zmiany API uzgadniają obie osoby oraz aktualizują próbkę i testy. Właściciel roli poprawia konflikty w swoich plikach. Małe PR-y integrują przy bramkach 6, 11 i 19 h.

## Kontrole odbioru

| Kontrola | Wykonanie |
| --- | --- |
| Backend i CLI | `python -m pytest -q`, następnie rzeczywista sprawa na docelowym modelu. Sprawdzić trzy klasy, negatyw, skan, uszkodzony PDF i zgodność wyników ze schematem. |
| Frontend i API | Atrapa oraz rzeczywiste żądanie `POST /api/extract` z kilkoma PDF-ami. Sprawdzić dobrą odpowiedź, częściowy błąd, puste żądanie oraz pobranie dokładnego `data` jako JSON. |
| Wydanie | Świeża instalacja Python 3.13+, jedna próba CLI i przeglądarki oraz test Compose po jego dostarczeniu. Potwierdzić obsługę CPU, limit pamięci i instrukcję startu. |

## Lokalna ewaluacja

Przed dostrajaniem backend zapisuje podział całych spraw, np. 01–42 rozwój, 43–54 walidacja, 55–60 test końcowy. Oddzielnie zamraża przypadki negatywne, grupując kopie PDF po hashu, żeby odpowiedniki z katalogu spraw i `negatywne/` trafiały do tego samego zbioru. Etykiety oficjalne są jawne i służą do lokalnej weryfikacji.

Evaluator dopasowuje PDF do etykiety po sprawie i jawnej mapie nazw, z `potwierdzenie_przelewu.pdf` → `przelew.json`. Traktuje puste pliki jako `unknown`, a brak pliku lub nadmiarowy plik jako błąd. Skalary porównuje według ścieżki i typu, agreguje wielozbiory, ignoruje robocze `null` i puste napisy jako brak danych. Dla list dopasowuje obiekty po identyfikatorze lub jednoznacznej nazwie przed oceną pól. Gdy brakuje klucza łączenia, raportuje przypadek i stosuje udokumentowaną regułę porównania, zachowując duplikaty.

Raport zawiera TP, FP, FN i `2TP/(2TP+FP+FN)` globalnie, per typ i per pole, liczbę etykiet, macierz klas, negatywne FP, błędy OCR/schematu, czas i szczyt pamięci. Zapisuj do `artifacts/`. Porównuj kolejne wersje na tym samym podziale. Algorytm oficjalnej punktacji pozostaje pytaniem U02. Przy sprzecznościach etykiet zachowuj bazę i dołącz osobną notatkę, żeby raporty były porównywalne.

## Próba fundamentu na danych UZP

Pierwsza próba trybu regułowego na 196 PDF-ach UZP wygenerowała 193 pliki i zwróciła kod 1 z powodu trzech negatywów wymagających OCR. Rozpoznano 60 z 60 odwołań, 58 z 60 pełnomocnictw i 54 z 60 przelewów. Pozostałe 8 dokumentów tych klas otrzymało `unknown`. Każdy z 13 czytelnych negatywów dostał pusty plik. Wynik przykładu 07 zawierał datę przelewu zgodną z referencją. To baza z danych treningowych. Pomiar jakości ekstrakcji LLM na zamrożonym podziale jest zadaniem BE04.

Polecenie użyte do próby zakłada lokalną kopię UZP w `.local/uzp-reference`.

```powershell
.venv/Scripts/python.exe main.py --input .local/uzp-reference/dane --output .local/batch-uzp
```
