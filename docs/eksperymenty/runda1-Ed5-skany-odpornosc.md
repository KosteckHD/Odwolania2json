Agent Ed5 (dawniej A5)

# Dziennik A5: skany, negatywy i odporność

Gałąź robocza agenta A5, start z `985c2c5` (fix/zgodnosc-uzp). Model: Qwen/Qwen3.5-9B w HostYourAI,
bez myślenia. Od połowy pracy limity koordynatora: `LLM_CONCURRENCY=1`, `LLM_REQUEST_INTERVAL_SECONDS=6`,
`LLM_MAX_429_RETRIES=10`, `LLM_MAX_RETRY_WAIT_SECONDS=180` (czasy niżej są zawyżone przez ten odstęp 6 s).

## Ustalenia wstępne

- Tesseract nie jest zainstalowany na tej maszynie (tak jak u jury), więc bazowo każdy z 30 skanów UZP
  kończył się `ocr_required` bez pliku wyniku: 0 pól ze skanów.
- Wbrew założeniu zadania skany UZP **mają wzorcowe JSON-y** (`dane/skany/<grupa>/<nr>/<nr>.json`),
  więc oprócz oglądania stron liczę F1 tym samym `evaluation/evaluate.py` (manifest budowany w locie).
  Wszystkie 30 skanów jest w całości bez warstwy tekstowej (pełnomocnictwa i potwierdzenia: 1 strona,
  odwołania: 4–7 stron, A4/Letter).
- Próba HostYourAI (1 zapytanie, potwierdzenie 0001, render 893×1264, JPEG 80, 136 KB): obrazy są
  przyjmowane w formacie OpenAI (`image_url` z data URL). **Obraz w skali szarości daje HTTP 400**
  („mean must have 1 elements…”), trzeba wysyłać RGB. Czas 13 s, 1120 tokenów obrazu, przepisany
  tekst praktycznie bezbłędny (numery rachunków, kwota, data, tytuł).
- Na oglądanych stronach (odwołanie 0001 str. 1 i 5, pełnomocnictwo 0002, potwierdzenie 0003): dane stron,
  zamawiający, numer postępowania, data i miejscowość są na str. 1 odwołania; podpis pełnomocnika i
  załączniki na ostatniej stronie. Stąd domyślny wybór stron: pierwsze 3 + ostatnia (`SCAN_MAX_PAGES=4`).

## Zmiany

1. `src/kio_extract/vision.py` (nowy): render strony pypdfium2 → JPEG RGB (skala 1.5, jakość 80, pusta
   strona pomijana), wybór stron, ustawienia `SCAN_OCR` / `SCAN_MODE` / `SCAN_MAX_PAGES` / `SCAN_SCALE` /
   `SCAN_JPEG_QUALITY`, równoległy odczyt stron z sumowaniem zużycia tokenów.
2. `providers/chat.py`: wspólne `_complete`, `transcribe_image` (OCR tym samym modelem, `max_tokens=3000`,
   odpowiedź ucięta też przyjmowana), `extract_json(..., images=)` dla trybu (b). Zużycie tokenów sumowane
   w obrębie dokumentu (OCR + ekstrakcja).
3. `processing.py`: skany przez model (domyślnie, gdy model obsługuje obrazy; Tesseract tylko gdy
   `SCAN_OCR=tesseract` albo tryb regułowy i program jest w PATH); dokument z częścią stron bez tekstu
   idzie dalej z tym, co jest (dawniej cały dokument padał na `ocr_required`); **wynik awaryjny**: po
   `llm_connect`, `llm_http`, `llm_rate_limit`, `llm_json`, `llm_incomplete`, `invalid_output`
   klasyfikacja i ekstrakcja regułowa z YAML na dostępnym tekście (także przepisanym ze skanu), a dla
   nierozpoznanego typu `{}`. Powód w klasyfikacji: `fallback:<kod>`.
4. `cli.py`: raport przebiegu ma pole `fallback`; dokument z błędem (np. nieczytelny PDF, skan bez OCR)
   dostaje plik jak negatyw (`{}`, raport `status: error`, `written: negative`), więc **plik powstaje dla
   każdego PDF-u**; `--on-error skip` przywraca stare zachowanie. Podsumowanie: `awaryjne=…`, `z plikiem {}`.
5. `prompt_extraction.py`: tylko przekazanie obrazów (`images=`) do klienta, treść promptu bez zmian.
6. Testy `tests/test_scans.py` (bez sieci, podstawiony klient / połączenie) i aktualizacja 3 testów
   end-to-end pod nowe zachowanie (plik dla każdego PDF-u).

## Próby

| # | nazwa | zbiór | ustawienia | F1 | czas | uwagi |
|---|-------|-------|------------|----|------|-------|
| 0 | e00-baseline (main) | development 135 | bez zmian | 0,9744 | 301 s | 3× llm_connect bez pliku; skany: 0 pól (ocr_required) |
| 1 | s1-transcribe | skany 0001–0003 ×3 grupy (9) | `SCAN_MODE=transcribe` | 0,9885 (TP 86, FP 1, FN 1) | 437 s | odwołanie ~100 s (4 strony OCR + ekstrakcja), reszta ~20 s |
| 2 | s2-image | te same 9 | `SCAN_MODE=image` | 0,9885 (TP 86, FP 2, FN 0) | 84 s | 1 zapytanie na dokument; 6–15 s/dok. |
| 3 | s3-image-reszta | skany 0004–0010 ×3 (21) | `SCAN_MODE=image` | 0,9650 (TP 207, FP 10, FN 5) | 218 s | bez błędów API |
| 4 | s4-transcribe-reszta | te same 21 | `SCAN_MODE=transcribe` | 0,8878 (nieważny) | ~25 min | 4 dok. bez OCR przez błędy API (przeciążenie, 5 agentów naraz) → `{}`; na 17 udanych bez błędów cyfr |
| 5 | s5-transcribe-powtorka | 0004, 0009, 0010 ×3 (9) | `SCAN_MODE=transcribe` | nieważny (3× `llm_http`) | ~10 min | **ścieżka awaryjna zadziałała na żywo**: po `llm_http` w ekstrakcji wynik z reguł YAML na przepisanym tekście skanu (odwołanie 0009 rozpoznane regułami, 2 pełnomocnictwa z pustymi listami) |
| 6 | A5-skany-awaryjny | development 135 | domyślne (transcribe), cherry-pick `aa76b7f`, konk. 1, odstęp 4 s | **0,9811** (TP 1353, FP 12, FN 40) | 1704 s | 0 błędów, 0 wyników awaryjnych; odwołanie 0,973, pełnomocnictwo 0,995, przelew 0,992 |
| 7 | Ed5-skany-30-transcribe | wszystkie 30 skanów | domyślne (transcribe), konk. 1, odstęp 5 s | **0,9643** (TP 297, FP 16, FN 6) | 2053 s | 0 błędów; odwołanie 0,958, pełnomocnictwo 0,967, przelew 0,981; odwołanie 100–200 s, 1 strona 15–80 s |

Pierwsze podejście do próby 6 (konk. 2, odstęp 3 s) przerwałem po kilku minutach na prośbę koordynatora
(zmiana limitów i cherry-pick), bez wyniku.

### Zbiór roboczy (próba 6) i negatywy

- F1 0,9744 → **0,9811**. Ścieżka tekstowa się nie zmieniła (żaden PDF zbioru roboczego nie ma stron bez
  tekstu, więc OCR modelem się nie włącza; refaktor `ChatClient` wysyła to samo ciało zapytania).
  Zysk to głównie brak utraconych plików: w bazowym 3 dokumenty bez wyniku (`llm_connect`), tu 0 błędów.
  Najsłabsze pola bez zmian: `pelnomocnik.nazwa` (FN 23), `pelnomocnik.mail` (FN 11),
  `prowadzacy_postepowanie` (FP 5) – to sprawa promptu/warstwy po modelu (A1/A3).
- **Negatywy**: wszystkie 9 (5 w `negatywne/` i 4 w katalogach przykładów) dostały `{}`, w tym 2 długie,
  które w bazowym kończyły się zerwanym połączeniem. `negative_false_positives = 0`.
- **Żaden prawdziwy dokument nie wypadł jako unknown**: macierz klasyfikacji 42/42 odwołań, 42/42
  pełnomocnictw, 42/42 przelewów, 9/9 unknown.

### Porównanie trybów (a) transcribe i (b) image

Błędy na skanach (pomijam dopisywanie „PL” do rachunku, które ewaluator ignoruje i które pochodzi z
normalizacji po modelu, nie z odczytu):

- **image**: gubienie cyfr w długich identyfikatorach, typowe dla małego modelu czytającego obraz
  wprost podczas wypełniania JSON-a: KRS pełnomocnictwa 0001 `999102252` (wzorzec `9991022552`),
  NIP odwołania 0006 `999178572` (`9991785572`), KRS pełnomocnictwa 0006 `999783010` (`9997873010`),
  rachunki potwierdzeń 0001 i 0006 (o jedną cyfrę za krótkie), BZP odwołania 0005 bez `/03`.
  Do tego tytuły przelewów bez polskich znaków (w granicy 80% podobieństwa, więc bez kary).
- **transcribe**: na tych samych dokumentach wszystkie te identyfikatory poprawne. Pozostałe błędy są
  wspólne dla obu trybów i wynikają z czytelności skanu albo z decyzji modelu, nie z OCR:
  „Dorota Szule” zamiast „Szulc”, „Kubik” zamiast „Kubiak”, „Dębicy” zamiast „Dębnicy”,
  `pelnomocnik.nazwa` (kancelaria) pusta w części odwołań (to samo zdarza się na PDF-ach tekstowych,
  sprawa promptu), „Aleksander” zamiast „Aleksandra” (odmiana do mianownika).
- Czas: image ~7 s (1 strona) i ~14 s (odwołanie), transcribe ~20 s i ~100–150 s przy limicie 1 zapytanie
  naraz co 6 s (przy równoległości 3 strony odwołania idą naraz, więc realnie ~30–40 s).
- Tokeny: image ~9,5 tys. wejścia na odwołanie, transcribe ~14 tys. (+ ~3 tys. wyjścia OCR).

**Decyzja (po próbach 1–4): domyślnie `transcribe`.** Identyfikatory (NIP, KRS, REGON, PESEL, rachunki)
to najwięcej pól i klucze dopasowania list w ocenie UZP; gubienie w nich cyfr kosztuje więcej niż czas.
`image` zostaje jako opcja (`SCAN_MODE=image`) na wypadek limitu czasu.

### Pełny przebieg na 30 skanach (próba 7) i rewizja decyzji

- transcribe, 30 skanów: **F1 0,9643** (TP 297, FP 16, FN 6). Dla porównania image (próby 2+3, te same 30
  skanów): TP 293, FP 12, FN 5 → **F1 0,9718**. Różnica to ~5 pól na 30 dokumentów, czyli w granicach szumu
  modelu: 6 z 16 FP transcribe to jedno odwołanie (0007), w którym model w ekstrakcji zdublował
  odwołującego (drugi wpis z tymi samymi danymi); w próbie 4 to samo odwołanie wyszło bez tego błędu, więc
  to niedeterminizm ekstrakcji, nie OCR. Bez tego przypadku transcribe ≈ 0,974.
- transcribe znów bez ani jednego błędu cyfr w identyfikatorach; image miał ich 6 na 30 dokumentów.
  Pozostałe błędy wspólne: `pelnomocnik.nazwa` puste (6/10 odwołań, prompt), `prowadzacy_postepowanie`
  = 1 zamiast null (3×, prompt), kolejność/odmiana nazwisk, „skarbowea”, „Dębicy”, zgubiony numer
  CEN na końcu tytułu (długie stringi i tak w progu 80%).
- Obejrzane strony (odwołanie 0001 str. 1 i 5, pełnomocnictwo 0002, potwierdzenie 0003) zgadzają się z
  wynikiem: te dokumenty mają F1 1,0 poza `pelnomocnik.nazwa` w odwołaniu 0001 (kancelaria jest w nagłówku
  pisma i w „adres do korespondencji”, model jej nie wpisał).
- **Decyzja końcowa: zostaje `transcribe` jako domyślny**, ale to wybór „dokładność identyfikatorów i
  zgodność z dalszą ścieżką tekstową” (poprawki A1/A3 na tekście działają też na skanach), a nie wyraźna
  przewaga F1. `image` jest 5–8× szybszy i tańszy (1 zapytanie, ~9,5 tys. tokenów na odwołanie zamiast
  ~5 zapytań i ~17 tys.). Jeśli jury ma limit czasu, przełączyć `SCAN_MODE=image`.
- Bazowo (bez Tesseracta) te 30 skanów dawało 0 pól; teraz ~96–97% F1.

## Uwagi dla integracji

- Pliki: `src/kio_extract/vision.py` (nowy), `processing.py` (przebudowany `process_with_evidence`:
  `_read_scans`, `_rules`, `_finish`, wynik awaryjny), `providers/chat.py` (`_complete`,
  `transcribe_image`, `images=` w `extract_json`), `prompt_extraction.py` (tylko przekazanie `images`),
  `cli.py` (`--on-error`, pola `fallback`/`written` w raporcie), testy `tests/test_scans.py`.
  Konflikty możliwe z A2 (podział zadania w `processing.py` / `prompt_extraction.py`) i A3 (warstwa po
  modelu w `_finish`): wynik awaryjny opakowuje całą ścieżkę modelu, więc nowa logika A2/A3 powinna trafić
  do środka bloku `try` w `process_with_evidence` albo do `_finish`.
- Zużycie tokenów w raporcie obejmuje teraz OCR stron (sumowane z wątków odczytu).
- Klient Anthropic nie ma `transcribe_image`: przy `LLM_PROVIDER=anthropic` skany idą do Tesseracta, jeśli
  jest, inaczej `{}`.
- `.env.example` wskazuje IONOS; obsługi obrazów dla Qwen3.5 9B w IONOS nie sprawdzałem. Jeśli IONOS
  odrzuci obraz (HTTP 400), skan dostanie `{}` z kodem `llm_http` w raporcie.
- Obraz musi być RGB (skala szarości → HTTP 400 w HostYourAI), co `render_page_jpeg` zapewnia.
- `evaluation/scan_experiment.py`: przebieg i F1 na skanach UZP (wzorce leżą obok PDF-ów).
- Przebieg zbioru roboczego dopisałem ręcznie do wspólnej tabeli `results.tsv` (agent `Ed5`):
  `experiment.py` w tej wersji ignoruje `--results` i `--agent` i pisze do `.local/experiments/results.tsv`
  w kopii roboczej.

### Odporność po próbach 4–5

- Pojedyncza nieudana strona przy OCR nie przekreśla już reszty dokumentu (zostaje tekst stron udanych).
- Skan, którego model nie odczytał, zgłasza w raporcie pierwotny kod błędu modelu (np. `llm_http`), nie
  mylące `ocr_required`, i dostaje `{}`.
- Ponawianie 5xx: najpierw dodałem własne (408/5xx do 3 razy), ale na prośbę koordynatora zastąpiłem je
  wspólną poprawką `aa76b7f` z fix/zgodnosc-uzp (5xx ponawiane jak 429; cherry-pick). Kolejność jest
  właściwa: ponowienia w koordynatorze zapytań, wynik awaryjny dopiero po ich wyczerpaniu.
