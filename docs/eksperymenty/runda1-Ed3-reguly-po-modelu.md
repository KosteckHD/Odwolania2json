Agent Ed3 (dawniej A3)

# Dziennik eksperymentów A3 — warstwa po modelu

Gałąź: `worktree-agent-ad6111bf3b6216995` (od `985c2c5`, fix/zgodnosc-uzp). Model Qwen3.5 9B (HostYourAI), bez myślenia,
podział `development` (135 PDF). Metryka: F1 pól wg zasad UZP (`evaluation/evaluate.py`).

## Mechanizm

Nowy moduł `src/kio_extract/postprocess.py`, wywoływany w `processing.py` tuż po odpowiedzi modelu (przed
normalizacją `x-normalizer` i walidacją schematu). Nie zna typów dokumentów — wszystko steruje sekcja
`postprocess:` w YAML klasy (walidowana przy wczytaniu konfiguracji, ścieżki sprawdzane względem schematu):

- `fill_missing` — gdy model zwrócił `null`, a reguła regex (grupa `value`, normalizator jak w `fields:`)
  daje w tekście PDF jedną, niesprzeczną wartość, wpisz ją. Nigdy nie nadpisuje wartości modelu; ścieżki z `[]`
  tylko przy liście z dokładnie jednym elementem (nie tworzy podmiotów); `requires` = pola, które muszą być
  niepuste (np. osoba pełnomocnika). Reguły `fields:` (tryb bez modelu) dla pól skalarnych też działają jako `fill_missing`.
- `snap_to_text` — imiona i nazwiska jak w dokumencie: gdy wartości modelu nie ma w tekście, a jest dokładnie
  jeden wariant pisowni (diakrytyki poza ostatnią literą, końcówka rodzaju -ski/-ska, -cki/-cka, -dzki/-dzka,
  -er/-ra), wpisz wariant z dokumentu. Odmiana przez przypadki (zmiana ostatniej litery, „Anną”) nie jest ruszana.
- `derive` — pole ze słownika w `options` (opis powodu z `czynnosc_powod_id`).

Dodatkowo `normalize_date` (normalizator `iso_date`) rozumie daty słowne „27 października 2026 (r./roku)”.

Pomiar offline: zapisane `output/` przebiegu → `postprocess` + normalizacja → ewaluacja (bez nowych wywołań modelu).

## Próby

| # | nazwa | zmiana | F1 | odwolanie | pelnomocnictwo | przelew | decyzja |
|---|-------|--------|----|-----------|----------------|---------|---------|
| 1 | A3-baseline | brak zmian (985c2c5), limity 1 / 6 s | 0,9770 (TP 1340, FP 10, FN 53) | 0,973 | 0,975 | 0,994 | punkt odniesienia; 1× llm_http (przyklad_41/pelnomocnictwo), więc formalnie nieważny — porównania robione offline na tych samych odpowiedziach |
| 2 | offline: fill_missing kancelaria + mail | `Odwolujacy[].pelnomocnik.nazwa/mail` z „adres do korespondencji:” | — | — | — | — | nazwa TP 20→42, FN 22→0; mail TP 28→42, FN 14→0; FP 0→0. Zostaje |
| 3 | offline: fill_missing numer transakcji | etykiety Nr ref./Numer referencyjny/Numer transakcji/Identyfikator operacji | — | — | — | 1,000 | TP 39→42, FN 3→0, FP 0. Zostaje |
| 4 | offline: fill_missing dzień czynności | „Zamawiający w dniu <data>” (tylko jedna data w dokumencie), daty słowne w `iso_date` | — | — | — | — | TP 40→42, FN 2→0, FP 0. Zostaje |
| 5 | offline: snap_to_text imion | pełnomocnicy, podpisujący, mocodawca, pełnomocnik odwołania | — | — | 0,980 | — | `pelnomocnicy[].imie_nazwisko` FP 3→0, TP 62→65 („Zawadzka”→„Zawadzki”, „Aleksander”→„Aleksandra”, „Szymański”→„Szymanski” — wzorzec = pisownia dokumentu). Zostaje |
| 6 | offline: derive opisu powodu | `czynnosc_opis` ze słownika wg `czynnosc_powod_id` | — | — | — | — | bez zmiany F1 (model już spójny; błędy opisu wynikają z błędnego id 11 zamiast 8). Zostaje jako gwarancja spójności 1:1 |
| 7 | offline: null_when_single prowadzący | `Zamawiajacy[].prowadzacy_postepowanie` = null przy jednym zamawiającym | — | — | — | — | FP 3→0 (we wzorcach 1/0 tylko przy dwóch zamawiających). Zostaje |
| — | **offline razem (na A3-baseline)** | 2–7 | **0,9943** (TP 1384, FP 4, FN 12) | 0,998 | 0,980 | 1,000 | +44 TP, −6 FP, żadne pole nie traci. Na e00-baseline (inne odpowiedzi modelu): 0,9744 → 0,9914 |
| 8 | A3-postprocess | pełny przebieg z 2–6 (bez 7), limity 1 / 6 s | 0,9153 | 0,906 | 0,912 | 0,950 | **nieważny**: 19× llm_http (504 dostawcy) = brakujące pliki. Na dokumentach bez błędu reguły dały 0 FP; offline z 7: FP 8→6 |
| 9 | **A3-postprocess-v2** | 2–7 + cherry-pick `aa76b7f` (ponawianie 5xx), limity 1 / 4 s | **0,9986 (TP 1396, FP 4, FN 0)** | 0,998 | 1,000 | 1,000 | **ważny (0 błędów)**. Zostaje. Jedyne błędy: `czynnosc_powod_id`/`czynnosc_opis` FP 2+2 (model wybiera 11 „OPZ” zamiast 8 „zaniechanie wykluczenia” w przyklad_27/31) |

## Podsumowanie

- Najlepszy wariant: wszystkie reguły 2–7 (commit `5fc3319`). Pełny przebieg 0,9986 vs baseline 0,9770 (offline na tych
  samych odpowiedziach co baseline: 0,9770 → 0,9943). Żadna klasa nie spada.
- Nie robione / bez efektu: filtr dosłowności i sumy kontrolne NIP/REGON/PESEL/rachunku — w baseline FP na tych polach = 0
  (sumy kontrolne we wzorcach są poprawne), więc nie ma czego zyskać, a zerowanie niesie ryzyko FN. Porządki (białe znaki,
  deduplikacja, e-maile) — brak błędów tego typu w zbiorze, nie dodane.
- Pozostały błąd (powód 8 vs 11) to decyzja modelu, nie do bezpiecznego poprawienia regułą bez nadpisywania modelu — zadanie dla promptu (A1).
- Uwagi dla integracji: zmiany są w `processing.py` (jedno wywołanie `postprocess` w gałęzi z modelem), `contracts.py`
  (pole `DocumentConfig.postprocess`), `schema_registry.py` (walidacja sekcji), `normalization.py` (daty słowne), YAML-e.
  Reguły regex wypełniają tylko pola, które model zostawił puste, więc lepszy prompt (A1) i reguły się sumują.
  `evaluation/experiment.py`: poprawka zapisu do `--results` z kolumną agenta (osobny commit, do pominięcia, jeśli ktoś zrobił to samo).
