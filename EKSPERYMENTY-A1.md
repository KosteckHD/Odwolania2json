Agent Ed1 (dawniej A1)

# Dziennik eksperymentów A1 — prompt i przykłady

Rodzina zmian: wyłącznie treść promptu (`prompts/system_pl.md`, warianty w `prompts/experiments/a1-*.md`).
Kod, wywołanie modelu, podział na kroki i warstwa po modelu bez zmian.

Model: Qwen/Qwen3.5-9B (HostYourAI), myślenie wyłączone, temperatura 0.
Zbiór: podział `development` z `evaluation/manifest.json` (135 PDF). Ustawienia limitu od koordynatora:
`LLM_CONCURRENCY=1, LLM_REQUEST_INTERVAL_SECONDS=6, LLM_MAX_429_RETRIES=10, LLM_MAX_RETRY_WAIT_SECONDS=180`.
Przebiegi z błędami `llm_rate_limit` / `llm_connect` / `llm_http` są nieważne do porównań.

## Analiza błędów punktu wyjścia (przebieg `e00-baseline`)

Przegląd wyjść względem wzorców (tylko `development`):

- `Odwolujacy[].pelnomocnik.nazwa` (FN 24) i `.mail` (FN 12): we wszystkich odwołaniach kancelaria stoi w wierszu
  „adres do korespondencji: Kancelaria …, ul. …”, a e-mail w następnym wierszu z telefonem. Model raz ją bierze,
  raz zwraca `null` przy identycznym układzie. Prawdopodobna przyczyna: zdanie promptu „Nie przypisuj danych
  kancelarii…” (dotyczyło nazwy odwołującego, model stosował je też do pełnomocnika).
- `pelnomocnicy[].imie_nazwisko` (FP 4): model „poprawia” imiona już podane w mianowniku: „Aleksandra” → „Aleksander”
  (bierze za dopełniacz), „Dorota Zawadzki” → „Zawadzka”, „Szymanski” → „Szymański”. Wzorzec trzyma pisownię dokumentu.
- `numer_transakcji` (FN 4): identyfikator stoi pod etykietą „Nr ref.” / „Numer referencyjny” i powtarza się w tytule;
  model zwraca `null`.
- `czynnosc_powod_id`/`czynnosc_opis`/`czynnosc_dzien` (2 dokumenty): zaskarżona czynność jest w zdaniu
  „Zamawiający w dniu … nie wykluczył…” (→ 8), a prompt kazał patrzeć na treść pierwszego zarzutu (tam OPZ → model 11).
- `Zamawiajacy[].prowadzacy_postepowanie` (FP 2): jeden zamawiający, model daje `1`, wzorzec `null`.

## Próby

| nazwa | zmiana | F1 | odwolanie | pelnomocnictwo | przelew | decyzja |
|---|---|---|---|---|---|---|
| A1-baseline | prompt bez zmian (`a1-baseline.md` = `system_pl.md` z 985c2c5) | 0,9804 (TP 1349, FP 10, FN 44) | 0,972 | 0,995 | 0,990 | punkt odniesienia, bez błędów przetwarzania. Szum między baseline'ami agentów (ten sam prompt): 0,9770–0,9815 |
| A1-e1-pelnomocnik | definicje `pelnomocnik.imie_nazwisko/nazwa/mail` + syntetyczny przykład; zakaz „danych kancelarii” zawężony do nazwy i identyfikatorów odwołującego | 0,9285 — **NIEWAŻNY** (14× `llm_http` 504, brak 14 plików) | — | — | — | powtórzony jako r2. Na 121 wspólnych dokumentach: baseline 0,9822 → E1 0,9951; `pelnomocnik.nazwa` FN 21→0, `mail` FN 10→0 |
| A1-e1-pelnomocnik-r2 | to samo co E1, po cherry-picku ponawiania 5xx (aa76b7f) | **0,9950** (TP 1388, FP 6, FN 8) | 0,995 | 0,997 | 0,992 | **zostaje** (w `system_pl.md`): +0,0146 ponad szum; `pelnomocnik.nazwa` FN 24→0, `mail` FN 13→0, żadna klasa nie spadła. Zostały: numer_transakcji FN 4, czynność 2 dok., prowadzący FP 2, imiona FP 2 |
| Ed1-e2-pola | na E1: (a) imiona już w mianowniku przepisywać litera w literę (bez zmiany rodzaju, końcówki, polskich znaków; przykłady syntetyczne); (b) zaskarżona czynność = zdanie „Zamawiający w dniu … odrzucił/nie wykluczył/…”, zarzuty tylko tłem + drzewo decyzji czasownik → `czynnosc_powod_id`; (c) `prowadzacy_postepowanie` = `null` przy jednym zamawiającym; (d) `numer_transakcji` z etykiet „Nr ref.”, „Numer referencyjny”… także gdy powtarza się w tytule | **1,0000** (TP 1400, FP 0, FN 0) | 1,000 | 1,000 | 1,000 | **zostaje** (w `system_pl.md`). Wszystkie 14 pozostałych błędów usunięte, nic nie spadło. Uwaga: 1,0 na development to górna granica — reguły są ogólne (etykiety, czasowniki), ale prawdziwą miarą będzie validation/test |
| Ed1-e3-yaml | treść E2 bez zmian, ale sekcje „Odwołanie / Pełnomocnictwo / Potwierdzenie przelewu” przeniesione z promptu do `options.llm_instructions` w YAML klas (prompt: tylko reguły wspólne + odesłanie do `llm_instructions`) | 1,0000 (TP 1400, FP 0, FN 0) | 1,000 | 1,000 | 1,000 | **cofnięte z głównej wersji** (brak wzrostu — reguła „tylko gdy F1 rośnie”), zachowane jako wariant `prompts/experiments/a1-e3-yaml.md` + `prompts/experiments/a1-e3-configs/`. Wniosek: reguły klasy w YAML działają tak samo dobrze jak w prompcie, więc nowy typ dokumentu może dostać pełne reguły samą konfiguracją |

## Czego nie sprawdziłem i dlaczego

Limit dostawcy (koordynator: 1 zapytanie naraz, 4–6 s odstępu) wydłużył przebieg do ok. 30–36 min, więc z listy pomysłów
zrobiłem tylko te z największym zyskiem. Po E2 zbiór development ma F1 = 1,0, więc dalsze warianty (prompt po angielsku,
krótszy prompt) nie mogłyby pokazać poprawy na tym zbiorze — tylko ewentualny spadek; bez validation nie da się ocenić
ich wpływu na uogólnianie. Pomysł 4 (drzewo decyzji dla `czynnosc_powod_id`) jest częścią E2.

## Przebiegi nieważne / incydenty

- Pierwszy `A1-baseline` (concurrency 3) przerwany na prośbę koordynatora (limit). Uwaga: osierocony proces `main.py`
  dokończył go w tle i pisał do tego samego katalogu wyjścia; ważny `A1-baseline` (concurrency 1) nadpisał wszystkie 135 plików, bez błędów.
- Wspólny katalog scratchpad agentów: inny agent nadpisał mój skrypt uruchomieniowy, przez co jedna próba „A1-baseline”
  wystartowała w worktree A2 i padła na ewaluacji (bez wpływu na wyniki; od tej pory skrypty w osobnym podkatalogu).
- `A1-e1-pelnomocnik`: 14× `llm_http` (504) → nieważny, powtórzony jako `-r2` po cherry-picku aa76b7f.
- `Ed1-e2-pola` pierwsze podejście (concurrency 2) przerwane przed końcem, żeby wziąć ponawianie 5xx; liczy się pełny przebieg.
