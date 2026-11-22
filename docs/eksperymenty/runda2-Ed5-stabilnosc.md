# Runda 2, Ed5: stabilność pól odwołań

Punkt wyjścia: scalona wersja rundy 1 (`b667a09`), Qwen3.5 9B w HostYourAI, bez myślenia, temperatura 0,
konkurencja 1, odstęp 5 s. Wszystkie przebiegi bez błędów API.

## Pomiary (tylko odwołania, własny manifest z wpisami `type=odwolanie`)

| przebieg | podział | F1 odwołań | błędy API | uwagi |
|---|---|---|---|---|
| r1-merged-dev (główna kopia) | development (42) | 1,000* | – | przebieg 1 |
| r2-Ed5-base-odw-dev | development (42) | 1,0000 | 0 | przebieg 2 |
| r2-Ed5-raw1-odw-dev | development (42) | 1,0000 | 0 | przebieg 3, zrzut surowych odpowiedzi |
| r2-Ed5-raw2-odw-dev | development (42) | 1,0000 | 0 | przebieg 4, zrzut surowych odpowiedzi |
| r1-merged-val (główna kopia) | walidacja (12) | 0,996 | 0 | przebieg 1 |
| r2-Ed5-base-odw-val | walidacja (12) | 0,9959 | 0 | przebieg 2 |

\* wynik z wyjścia porównanego pole po polu z przebiegiem 2 (identyczne).

## Mapa niestabilnych pól

Wynik końcowy (po regułach `postprocess:` i normalizacji), pary przebiegów:

- development: 1↔2, 2↔3, 3↔4: **0/42 dokumentów z różnicą, 0 pól**,
- walidacja: 1↔2: **0/12 dokumentów, 0 pól**.

Surowe odpowiedzi modelu (przed regułami, `LLM_RAW_DUMP_DIR`), development 3↔4:

- 0 różnic wartości; w 5/42 dokumentach (przyklad_04, 19, 34, 37, 41) zmienia się tylko **kolejność kluczy**
  w JSON (stąd różnica 1–3 tokenów wyjścia między przebiegami). Niedeterminizm dostawcy istnieje, ale przy
  obecnym prompcie nie zmienia żadnej wartości.
- Surowa odpowiedź różni się od wzorca tylko w `ZamowieniePubliczne.numer_ted` (21 dokumentów; format
  poprawia normalizator `ted`). Reguły `fill_missing` (kancelaria, e-mail, dzień czynności) na development
  w ogóle nie musiały zadziałać: model sam podaje te wartości po doprecyzowaniu promptu w rundzie 1.

Porównanie z rundą 1 (e00-baseline ↔ obecna wersja, 26/41 dokumentów różnych): różnice były w
`pelnomocnik.nazwa` (23), `pelnomocnik.mail` (11), `czynnosc_*` (po 2) i `prowadzacy_postepowanie` (2).
Te pola zostały ustabilizowane w rundzie 1 (prompt Ed1 + reguły Ed3: `null_when_single`, `derive`,
`fill_missing`), więc obecnie nie ma niestabilności do usunięcia.

Jedyny błąd odwołań (walidacja, przyklad_47: powód 2 zamiast 8) jest **stabilny** (ten sam w obu
przebiegach) – to kwestia powodu, czyli zakres Ed1–Ed3, nie stabilności.

## Wnioski

- Nie wprowadzam zmian w prompcie ani regułach: nie ma niestabilnego pola, a twardy warunek (odwołania
  rosną albo są stabilniejsze) nie może zostać spełniony przez żadną zmianę – każda byłaby ryzykiem bez zysku.
- Konsorcjum / dodatkowy odwołujący: w danych (development, walidacja) nie ma wzorca z kilkoma odwołującymi,
  a model w 4 przebiegach ani razu nie dodał drugiego. Reguła „tylko lider” byłaby dopasowaniem do danych
  (ryzyko na teście z prawdziwym wieloma odwołującymi), więc jej nie dodaję.
- Kilku zamawiających (przyklad_42, 51, 59): `prowadzacy_postepowanie` stabilne i poprawne.

## Dodane narzędzia (nie zmieniają wyników)

- `LLM_RAW_DUMP_DIR` (domyślnie wyłączone): zapis surowej odpowiedzi modelu przed regułami do
  `<katalog>/<sprawa>__<plik>.json`; test w `tests/test_contracts.py`.
- `evaluation/compare_runs.py`: porównanie dwóch przebiegów pole po polu (wyjście CLI lub zrzut `--raw`,
  opcjonalnie z wartością wzorcową i filtrem `--type`).
