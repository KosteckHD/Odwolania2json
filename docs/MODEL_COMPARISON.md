# Porównanie ekstrakcji i kolejny eksperyment

## Pomiary lokalne

Ewaluator liczy lokalny F1 dla pól, a nie oficjalny wynik konkursowy. Zbiór walidacyjny zawiera 12 syntetycznych spraw UZP (36 PDF) i jeden syntetyczny negatyw. Zamrożony punkt odniesienia Sonnet 4.6 osiągnął F1 **0,9859** (TP 420, FP 6, FN 6), klasyfikacja 37/37. Prompt i konfiguracja punktu odniesienia są zapisane lokalnie w `.local/baselines/sonnet-validation-v1`; raport w `artifacts/sonnet-validation-full.json`.

Porównanie dwóch modeli wykonano na tych samych 9 PDF z pierwszych trzech spraw rozwojowych i tej samej eksperymentalnej wersji prompta v2:

| Model | Lokalny F1 | TP / FP / FN | Tokeny wejścia / wyjścia | Suma czasu dokumentów |
| --- | ---: | --- | --- | ---: |
| Claude Sonnet 4.6 | 0,9796 | 96 / 2 / 2 | 56 110 / 2 208 | 42,67 s |
| Claude Haiku 4.5 | 0,9146 | 91 / 10 / 7 | 56 101 / 2 215 | 36,20 s |

Raporty: `artifacts/sonnet-development-v2.json`, `artifacts/haiku-development-v2.json`; szczegółowe raporty wywołań są w `.local/sonnet-development/run-v2.json` i `.local/haiku-development/run-v2.json`. Czas obejmuje także przetwarzanie lokalne i oczekiwanie; nie jest niezależnym benchmarkiem samego API. Obie próby są małe i pojedyncze, a wynik może się zmieniać między wywołaniami.

Kolejny eksperyment na Haiku, z promptem `prompts/experiments/haiku-v1.md`, na tych samych 9 syntetycznych PDF dał F1 **0,9898** (97 / 1 / 1); klasyfikacja 9/9, 58 810 tokenów wejścia, 2 211 wyjścia, suma czasów 37,61 s. Raport: `artifacts/haiku-development-haiku-v1.json`, oryginalny przebieg i wyniki: `.local/haiku-development/run-haiku-v1.json` i `.local/haiku-development/output-haiku-v1`. Prompt był przygotowany na podstawie błędów w tej samej próbce, więc poprawa nie jest niezależnym pomiarem uogólnienia. Po tym przebiegu rozszerzono normalizację TED o jednoznaczny wariant `RRRR-SDDD-NNNNNN`; zapisane wyniki i podane F1 pochodzą sprzed tej zmiany. Pozostałą w tym przebiegu rozbieżność TED normalizator usuwa lokalnie, ale cały eksperyment z nowym normalizatorem nie został powtórzony. Aktywny wspólny prompt pozostaje bez zmiany do czasu weryfikacji na innych przypadkach.

Na trzech innych syntetycznych sprawach 46–48 (9 PDF; klasy odwołanie, pełnomocnictwo i przelew) uruchomiono Haiku kolejno z v1 i nowym `prompts/experiments/haiku-v2.md`. W obu przebiegach: klasyfikacja 9/9, F1 **0,9864** (109 TP, 2 FP, 1 FN), bez błędów przetwarzania. V1: 89 278 tokenów wejściowych, 2 557 wyjściowych, 39,32 s łącznie; v2: 91 933 / 2 557, 41,34 s. Raporty: `artifacts/haiku-validation-46-48-v1.json` oraz `artifacts/haiku-validation-46-48-v2.json`; raporty przebiegów i wyniki w `.local/haiku-validation/`. Nowa wersja nie wykazała poprawy i nie zastępuje v1. Są to pojedyncze przebiegi; sprawa 48 była już wcześniej analizowana w eksperymencie z Sonnetem, więc nie jest w pełni niezależna od prac nad promptem.

Obie wersje wskazały w sprawie 48 datę przekazania kopii odwołania z tabeli zdarzeń jako datę pisma, mimo że brak daty pisma w nagłówku i referencja ma `null`. Obie pominęły też ostatni wiersz tytułu przelewu, który jednocześnie powtórzono w polu numeru referencyjnego, mimo wyraźnej instrukcji w v2. To wskazuje na możliwe przenoszenie informacji między rolami oraz pomijanie powtórzonego tekstu przez model; sam pomiar nie ustala przyczyny wewnętrznej. Następne kroki to osobne syntetyczne regresje dla tych układów, porównanie surowego tekstu PDF i odpowiedzi modelu oraz weryfikacja na dokumentach, których nie użyto przy tworzeniu instrukcji. W tej próbie nie było negatywów ani skanów OCR.

Eksperymentalny prompt v2 nie został przyjęty na podstawie jednego słabszego wyniku. Aktywny prompt z obsługą dodatkowych klas oraz normalizator TED osiągnęły w oddzielnym przebiegu 1,0 (98 / 0 / 0) na tych samych 9 PDF, raport `artifacts/sonnet-development-final.json`. Ponadto 5 syntetycznych przypadków regresyjnych, w tym dwa negatywy, przeszło z Sonnetem (`artifacts/sonnet-regression-v2.json`). Nie należy porównywać tego wyniku bezpośrednio z F1 z 37 dokumentów ani uznawać go za wynik na nieznanym zbiorze.

Liczby parametrów modeli Claude nie zostały tu potwierdzone, a same modele nie są otwartymi modelami konkursowymi. Nie można więc na podstawie tej tabeli przypisać punktów za liczbę parametrów ani stwierdzić zgodności całej konfiguracji z wymaganiami konkursu. Sprawdź aktualny [regulamin UZP](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026) dla docelowego rozwiązania.

## Następny test konkursowy

1. Wybrać dostępny model otwarty o potwierdzonej licencji i liczbie parametrów. Zweryfikować dostawcę, warunki przetwarzania i region z wymaganiami konkursu. [Mistral udostępnia regionalny endpoint UE](https://docs.mistral.ai/inference/regional-inference), ale dostępność konkretnego modelu w regionie należy sprawdzić osobno.
2. Skonfigurować klucz wyłącznie w środowisku backendu. Uruchomić najpierw małą próbę wszystkich klas i negatywów; następnie porównać modele na tych samych sprawach, promptach i schematach. Zachować wersję modelu, konfigurację, tokeny, błędy oraz czasy.
3. Przetestować skany i błędy OCR, przypadki wielostronicowe i dodatkowe negatywy. Dla zbiorów hurtowych pozostawić ograniczanie tempa i ponawianie po 429; monitorować limity żądań i tokenów. Nie zakładać, że jedna przerwa między żądaniami wystarczy dla wszystkich limitów.
4. Po wyborze ustawień wykonać jeden pomiar na odłożonych sprawach końcowych 55–60. Nie stroić prompta na podstawie tego wyniku bez wydzielenia kolejnego niezależnego zbioru.
5. Przeprowadzić wspólną próbę z frontendem, zweryfikować częściowe błędy i pobierane JSON-y, a następnie zapisać model, wynik, koszty oraz ograniczenia. Tokeny pozwalają oszacować koszt według [cennika Anthropic](https://platform.claude.com/docs/en/about-claude/pricing); rzeczywiste rozliczenie może się różnić.
