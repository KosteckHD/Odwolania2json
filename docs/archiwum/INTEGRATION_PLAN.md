# Integracja i harmonogram

| Czas od startu | Backend | Frontend | Bramka |
| --- | --- | --- | --- |
| 0–1 h | Uzgodnienie kontraktu, przykład odpowiedzi i weryfikacja warunków dostępu do LLM | Szkic jednego ekranu i uruchomienie atrapy z przykładową odpowiedzią | Obie strony pracują na tym samym kontrakcie |
| 1–6 h | Endpoint HTTP wykorzystujący istniejący pipeline. Testowy dostawca LLM do integracji | Wybór kilku PDF-ów, stan przetwarzania, lista wyników i pierwsze połączenie z API | Jedna sprawa przechodzi przez UI i backend z kontrolowaną odpowiedzią modelu |
| 6–11 h | Test na docelowym modelu, pierwszy lokalny pomiar F1 i regresje dla trzech klas | Podgląd i pobranie JSON, negatywy, częściowe błędy, ponowienie | Rzeczywista sprawa od PDF do JSON i pierwsza baza porównawcza jakości |
| 11–16 h | OCR na CPU i poprawki prompta według błędów z walidacji | Próby skanów, błędów i wolnego API, obsługa z klawiatury | Odbiór skanu oraz powtórny pomiar na tym samym zbiorze |
| 16–19 h | Czysty start CLI i API, limity, licencje, Compose | Integracja docelowa, instrukcja panelu i próba demo | Wspólna próba na rzeczywistych PDF-ach i gotowa instrukcja |
| 19–22 h | Końcowy test i zapis modelu, metryk i ograniczeń | Końcowy test pobierania i demo | Gotowy przebieg do zgłoszenia i prezentacji |

## Plan implementacji backendu

Gałąź robocza to `feat/core-engine`. Budżet jednej osoby wynosi 18 godzin pracy w 22-godzinnym oknie. Harmonogram poniżej uzupełnia zadania BE02–BE06 z [tablicy](WORKBOARD.md).

Agent wdrażający dostaje szczegółową specyfikację BE01–BE06, testy i zasady wyboru profilu Sonnet lub konkursowego. [Instrukcja wdrożenia backendu](prompts/BACKEND.md)

**Stan wyjściowy.** CLI czyta PDF, uruchamia [wspólny prompt](../../prompts/system_pl.md) przez klienta Chat Completions i waliduje wynik. Tryb regułowy jest dostępny lokalnie. Konfiguracja procesu i walidacja są obecnie w `cli.py`. Parser ma punkt wpięcia OCR i zgłasza `ocr_required`, gdy strona pozostaje bez czytelnego tekstu. Do zrobienia są warstwa HTTP, działający OCR, próba na docelowym LLM i evaluator. Na starcie 9 testów przechodzi na Pythonie 3.13.16.

### 0–1 h · Kontrakt i dostęp do dostawcy (1 h pracy)

1. Z frontendem potwierdź `POST /api/extract`, nazwy statusów oraz przekazywanie plików przez `multipart/form-data`. Przekaż [przykładową odpowiedź](fixtures/extract-response.json), w tym częściową awarię. Zmiana formatu wymaga wspólnej decyzji. [Kontrakt HTTP](INTERFACES.md#api-dla-frontendu)
2. Zacznij weryfikację dostawcy od razu. Sprawdź licencję konkretnego modelu, siedzibę firmy, region serwerów obsługujących wybrany endpoint oraz dostępność klucza. Pierwsza próba używa syntetycznego tekstu i sprawdza `system`, `user`, odpowiedź JSON oraz limit wejścia zgodnie z protokołem dostawcy. Dane konkursowe wymagają kwalifikowanego profilu. [Warunki UZP i pytanie U06](OPEN_QUESTIONS.md)

### Do 6 h · Wspólne przetwarzanie i integracja HTTP (3 h pracy)

1. Wydziel z `cli.py` procesor jednego PDF-u w `src/kio_extract/processing.py`. Proponowany interfejs `process(path: Path) -> tuple[ClassificationResult, JsonObject | None]` zwraca klasę i zwalidowane dane lub zgłasza `DocumentError`. Procesor ładuje konfiguracje, prompt, strategie i walidatory raz na uruchomienie. Dla każdego PDF-u używa `extract_pdf` z opcjonalnym OCR, a następnie `PromptExtractor` lub istniejącej strategii regułowej. CLI nadal odpowiada za ścieżki, zapis atomowy, tryb pliku negatywnego i kody wyjścia 0/1/2.
2. Dodaj `src/kio_extract/api.py` jako cienką warstwę HTTP. Proponowany stos to FastAPI z `UploadFile`, `python-multipart` i Uvicorn. Przetwarzaj pliki kolejno, używając osobnych plików tymczasowych pod nazwami generowanymi przez serwer. Nazwa wejściowa służy do prezentacji. Zwalniaj uchwyty i usuwaj pliki tymczasowe również po błędzie. [FastAPI i przesyłanie plików](https://fastapi.tiangolo.com/tutorial/request-files/)
3. Mapuj poprawny payload na `ok`, negatyw na `unknown`, a `DocumentError` na `error` w pozycji danego PDF-u. Zachowaj kolejność także przy powtarzających się nazwach. Wadliwy formularz ma zwrócić uzgodniony HTTP 400, a awaria całego żądania kod 5xx. Przy poprawnym formularzu odpowiedź HTTP 200 zawiera wynik każdego pliku. Dla statusu `ok` pole `data` musi odpowiadać zawartości wynikowego JSON-u z CLI przy tej samej odpowiedzi modelu.
4. Przekaż frontendowi adres lokalnego API i polecenie startu z atrapą klienta LLM. Atrapa zwraca deterministyczne odpowiedzi dla syntetycznych PDF-ów. Dodaj `tests/test_api.py` i uruchom `python -m pytest -q`. Bramka to jedno żądanie z poprawnym PDF-em, negatywem i uszkodzonym PDF-em. Wyniki pozostają w kolejności, a następny plik nadal jest przetwarzany po błędzie.

### Do 11 h · Docelowy model i pierwszy pomiar (4 h pracy)

1. Użyj istniejących `LLM_BASE_URL`, `LLM_MODEL` i `LLM_API_KEY` oraz jawnego wyboru protokołu `LLM_PROVIDER`. Próbę Sonnet przeprowadź na danych syntetycznych. Potwierdź jedno żądanie dostawcy na każdy czytelny PDF. Każda odpowiedź przechodzi walidację koperty `typ`/`dane` oraz schematu wybranej klasy. Osobno próbkuj poprawne dokumenty wszystkich trzech klas, negatyw i materiał wymagający OCR. Zapisz model, region, wersję prompta i wyniki testu bez klucza oraz treści PDF w logach.
2. Zamroź listy spraw i negatywów przed pierwszym strojeniem. Użyj trwałego manifestu z identyfikatorami spraw i jawnym mapowaniem nazw. Próbki negatywne grupuj według skrótu zawartości. Uruchom najpierw krótką próbę na wszystkich klasach, a po niej pierwszy pomiar na uzgodnionym zbiorze walidacyjnym. Przypadki `ocr_required` wlicz do błędów przetwarzania.
3. Dodaj `evaluation/` z prostym przebiegiem po zapisanych wynikach. Zgodnie z [metodyką](#lokalna-ewaluacja) raportuj macierz pomyłek, lokalny micro-F1 globalnie, według klasy i pola, skuteczność na negatywach oraz błędy techniczne. Brak wyniku daje FN dla pól, które miały się pojawić. Raportuj osobno liczbę plików, na których model zwrócił niezgodny JSON. Bramka to powtarzalny raport wersji bazowej w `artifacts/`.

### Do 19 h · OCR, poprawki jakości i uruchomienie (7 h pracy)

1. Do 16 h podłącz adapter OCR do istniejącego kontraktu `OCR(path, page_number)`. Proponowany zestaw to `pypdfium2` do renderowania stron i Tesseract z językiem polskim do rozpoznania tekstu. Renderuj tylko strony wymagające OCR, jedna po drugiej. Sprawdź wykrywanie pustych stron, limity czasu i zachowanie kolejności. Zweryfikuj rzeczywisty skan, mieszany PDF i brak działającego OCR. Przetwarzanie skanu z odzyskanym tekstem nadal wysyła jedno żądanie LLM. Dostęp do PDFium pomiędzy żądaniami musi być szeregowy lub izolowany procesowo, ponieważ biblioteka nie obsługuje równoległych wywołań z wielu wątków. [Dokumentacja pypdfium2](https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading) · [Dokumentacja Tesseract](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)
2. Do 16 h wybierz z raportu najczęstsze FP/FN. Dodaj regresje, w których drugi zarzut sugeruje inny powód, podpisujący różni się od pełnomocnika, a etykiety rachunków występują w innym układzie. Dodaj do prompta lub `options.llm_instructions` jedną zmianę na próbę. Porównaj ze stałą bazą na tym samym modelu i zbiorze. Zachowaj wersję, która poprawia problem bez wzrostu krytycznych błędów klasyfikacji, przypisania ról lub schematu.
3. Do 19 h opisz uruchomienie CLI i API, konfigurację OCR, zmienne środowiskowe i adres dla frontendu. Przeprowadź czystą instalację, test Compose, próbę API z panelem i przebieg CLI na CPU. Używaj świeżego katalogu wyjściowego przy pomiarach. Bramka to skan i PDF tekstowy przetworzone na zgodne JSON-y, sprawdzone po obu stronach integracji.

### Do 22 h · Wspólna próba i zamknięcie (3 h pracy)

1. Zamroź model i prompt. Wspólnie z frontendem uruchom jedną rzeczywistą sprawę przez CLI oraz panel. Sprawdź pobranie samych danych UZP, nazwę pliku, kolejność wpisów i zachowanie przy częściowej awarii.
2. Uruchom końcowe `python -m pytest -q` i zrób ostatni pomiar na odłożonym zestawie. Zapisz identyfikator modelu, commit, wersję prompta, podział danych, lokalny F1, wyniki dla negatywów i główne ograniczenia. Sekret LLM pozostaje wyłącznie w środowisku procesu backendu. [Pytania otwarte U01–U07](OPEN_QUESTIONS.md)

### Kryteria odbioru i zależności

| Sprawdzenie | Oczekiwany wynik |
| --- | --- |
| Trzy klasy | Pozytywne odpowiedzi atrapy LLM mapują się na poprawne schematy. Porównaj dokładny payload CLI i API. Niedozwolone klucze i zły typ pola muszą dać `invalid_output`. |
| Negatyw i kolejność | Rozpoznany negatyw ma `unknown`. Plik negatywny z CLI respektuje wybrany tryb. Odpowiedź po błędzie utrzymuje pozycje, w tym przy dwóch identycznych nazwach. |
| Błędy OCR i LLM | Nieudany odczyt OCR, timeout lub odpowiedź niebędąca JSON-em daje błąd konkretnego PDF-u. Kolejne PDF-y są przetwarzane. Test atrapy liczy żądania i potwierdza, że niedający się odczytać PDF nie jest wysyłany do LLM. |
| Brak kwalifikowanego dostawcy | Integracja API i frontendu oraz testy lokalne korzystają z atrapy. Zadanie BE03 i pomiar jakości na docelowym modelu pozostają zablokowane do czasu potwierdzenia dostępu. |
| OCR na konkretnym systemie | Sprawdź dostępność pakietu językowego `pol` oraz renderera przed etapem integracji. Brak OCR na jednym środowisku ma czytelny komunikat. Odbiór skanów przeprowadź na odtwarzalnym środowisku z działającym OCR. |

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

### Próbka Claude Sonnet

Na `claude-sonnet-4-6` wykonano próbę dziewięciu dokumentów z trzech spraw rozwojowych. Wszystkie sklasyfikowano poprawnie. Lokalny micro-F1 wyniósł 0,959 przed normalizacją polskich IBAN-ów i 1,0 po przeliczeniu zapisanych odpowiedzi. Normalizacja usuwa przedrostek `PL` wyłącznie przy dokładnie 26 cyfrach rachunku. Test ponownie wykorzystał odpowiedzi bez wywołania modelu.

Osobna próba objęła sprawy walidacyjne 43–45 oraz syntetyczny negatyw utworzony na potrzeby testu. Każdy z 10 PDF-ów dostał właściwą klasę, a lokalny micro-F1 dla pól wyniósł 0,9604. Cztery rozbieżności dotyczą opisu czynności, numeru TED, PESEL i tytułu przelewu. W przypadku PESEL wzorzec podaje liczbę, a etykieta przypadku 43 zapisuje te same cyfry jako tekst. Opis czynności jest objęty pytaniem U03. Wynik dotyczy małej próbki, a model i endpoint Sonnet wymagają odrębnego potwierdzenia zgodności konkursowej. [Pytania do mentora](OPEN_QUESTIONS.md)

Po potwierdzeniu przez użytkownika, że dokumenty ze spraw 46–54 są syntetyczne i mogą być wysłane do Anthropic, przetworzono pozostałe 27 PDF-ów. Połączony pomiar obejmuje sprawy 43–54, czyli po 12 dokumentów każdej z trzech klas, oraz jeden oddzielny syntetyczny negatyw. Łączny lokalny micro-F1 wyniósł **0,9859** przy 420 TP, 6 FP i 6 FN. F1 wyniósł 0,9878 dla odwołań, 0,9908 dla pełnomocnictw oraz 0,9722 dla przelewów. Wszystkie 37 plików miało poprawnie rozpoznaną klasę, w tym jeden negatyw. Raport nie wykazał błędów technicznych. Najczęstsze różnice dotyczą numeru TED i tytułu przelewu, a pojedyncze opisów czynności i typu PESEL.

Raporty lokalne znajdują się w `artifacts/sonnet-development.json`, `artifacts/sonnet-development-normalized.json`, `artifacts/sonnet-validation.json` i `artifacts/sonnet-validation-full.json`. Ostatni raport ma sprawdzone sumy wyników z dwóch przebiegów. To wynik lokalnej metody na syntetycznych danych treningowych, a test negatywny obejmuje jeden dokument. Próba konkursowa nadal zależy od ustalenia zgodności modelu oraz endpointu z wymaganiami UZP.

Pierwsza próba trybu regułowego na 196 PDF-ach UZP wygenerowała 193 pliki i zwróciła kod 1 z powodu trzech negatywów wymagających OCR. Rozpoznano 60 z 60 odwołań, 58 z 60 pełnomocnictw i 54 z 60 przelewów. Pozostałe 8 dokumentów tych klas otrzymało `unknown`. Każdy z 13 czytelnych negatywów dostał pusty plik. Wynik przykładu 07 zawierał datę przelewu zgodną z referencją. To baza z danych treningowych. Pomiar jakości ekstrakcji LLM na zamrożonym podziale jest zadaniem BE04.

Polecenie użyte do próby zakłada lokalną kopię UZP w `.local/uzp-reference`.

```powershell
.venv/Scripts/python.exe main.py --input .local/uzp-reference/dane --output .local/batch-uzp
```
