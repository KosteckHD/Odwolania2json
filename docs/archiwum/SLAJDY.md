# Szkic slajdów dla jury

Siedem slajdów do pokazu z [`docs/DEMO.md`](DEMO.md). Ten sam szkic jest złożony jako deck: [Odwołania2JSON – pitch dla jury](https://claude.ai/artifact/8LMCpKNd6DeYBGvRYi8EnP). Deck jest prywatny, dopóki właściciel nie udostępni go przez menu Share; eksport do PPTX i PDF jest w decku. Wszystkie liczby pochodzą z repozytorium albo z próby na prawdziwym API z 21.11.2026 (źródło przy każdym slajdzie). Brakujące dane są oznaczone **do uzupełnienia**. Nie wpisujemy w ich miejsce szacunków.

Styl: jak panel ([`frontend/DESIGN.md`](../../frontend/DESIGN.md)), czyli łososiowy papier `#FAF1EC`, czerwień druku `#9A3218` na etykietach, dane czernią, krój Public Sans, bez cieni i gradientów.

---

## 1. Problem

**Tytuł:** Sprawa odwoławcza to kilka PDF-ów i kilkadziesiąt pól do przepisania

- Do UZP wpływa sprawa jako zestaw PDF-ów: odwołanie, pełnomocnictwo, potwierdzenie przelewu, czasem skan albo inne pismo.
- Same pola UZP: 22 w odwołaniu, 8 w pełnomocnictwie, 6 w przelewie (schematy w `schemas/`, ta sama lista w widoku „Typy dokumentów” z backendu).
- Dane wrażliwe na błąd: KRS, NIP, REGON, PESEL, numery BZP i TED, rachunki, kwoty, daty.
- Ile czasu urzędnik spędza dziś na jednej sprawie: **do uzupełnienia** (nie mamy tej liczby od UZP).

**Notatka dla mówiącego:** jedno zdanie o urzędniku, bez statystyk, których nie mamy.

Źródło liczby pól: `schemas/*.schema.json`, `GET /api/document-types` ([zrzut 11](demo/11-typy-dokumentow.png)).

---

## 2. Rozwiązanie

**Tytuł:** Odwołania2JSON: PDF-y sprawy wchodzą, JSON w formacie UZP wychodzi

- Rozpoznaje typ każdego PDF-u po treści, a nie po nazwie pliku.
- Zapisuje `output/<sprawa>/<plik>.json` w formacie UZP. Dokument spoza klas dostaje JSON `{}` (ustalenie UZP z 21.11).
- Dwa wejścia do tego samego przetwarzania: CLI (`main.py`, `input/` → `output/`) i panel WWW dla urzędnika.
- Jedna komenda na start: `start.bat` uruchamia API i panel pod `http://127.0.0.1:8000/`.
- Komponenty open source; model językowy przez API zgodne z Chat Completions, konfigurowany w `.env`.

**Obraz:** [zrzut 04](demo/04-wynik-odwolanie.png): rubryki obok PDF-u, wynik sprawy, „Przebieg: model · czas”.

---

## 3. Jak to działa

**Tytuł:** Jedno wywołanie modelu na dokument, potem walidacja schematem

Schemat przepływu (od lewej):

1. **PDF** → odczyt tekstu (`pypdf`); strony bez warstwy tekstu → OCR (Tesseract, `pol`).
2. **Jedno wywołanie LLM** dostaje system prompt, schematy klas i słownik powodów odwołania; zwraca `typ` i `dane`.
3. **Walidacja JSON Schema** klasy i normalizacja (np. format TED).
4. **Wynik:** JSON dla klasy, `{}` dla dokumentu spoza klas, błąd z kodem (np. `ocr_required`) bez zatrzymywania reszty sprawy.

Pod spodem:

- Ograniczanie tempa i ponawianie po HTTP 429 (`LLM_REQUEST_INTERVAL_SECONDS`, `LLM_MAX_429_RETRIES`).
- Raport przebiegu (`--report`) i lokalny ewaluator F1 z podziałem na pola i klasy (`evaluation/evaluate.py`).
- Tryb regułowy jako lokalna baza porównawcza, Docker Compose z Tesseractem.

Źródło: `README.md`.

---

## 4. Panel dla urzędnika

**Tytuł:** Urzędnik sprawdza, a nie przepisuje

- Wgranie plików albo całego folderu sprawy; status każdego pliku: rozpoznany / nie rozpoznano / błąd. „Anuluj” w trakcie, „Ponów błędne” po błędach.
- W podsumowaniu sprawy nazwa modelu i czas przebiegu (np. „model: claude-haiku-5-5 · 15,9 s”).
- Rubryki obok podglądu PDF; identyfikatory i daty w kratkach jak na blankiecie. Puste pole zakreskowane, z dopiskiem „brak w dokumencie”.
- Zaznaczenie tekstu w PDF-ie wstawia do rubryki samą wartość: „20 marca 2026” → 2026-03-20. Działa też z klawiatury (Alt+↓).
- Ręczna zmiana oznaczona jako „poprawione”, z cofnięciem i licznikiem poprawek. Kopia robocza w przeglądarce i pytanie „Przywrócić poprawki?” po ponownym wgraniu sprawy; ostrzeżenie przy wyjściu z niepobranymi poprawkami.
- Podpowiedź „(w mianowniku)” przy polach z imionami i nazwiskami (ustalenie UZP).
- ZIP z wynikami, `{}` dla dokumentów spoza klas. Zwijana lista plików. Tryb atrapy (`?mock=1`) działa bez modelu.
- Statyczny HTML/CSS/JS bez budowania i bez CDN; fonty i PDF.js w repozytorium.

**Obrazy:** [zrzut 05](demo/05-zaznaczenie-w-pdf.png) i [zrzut 06](demo/06-reczna-poprawka.png), oba z prawdziwego API.

**Uczciwie:** poprawki w panelu nie zmieniają F1, które UZP liczy z plików `output/`. Panel to narzędzie urzędnika.

**Kryterium:** inne funkcje (do 10 pkt), transparentność ekstrakcji.

---

## 5. Nowy typ dokumentu bez zmiany kodu

**Tytuł:** Nowa klasa to dwa pliki konfiguracyjne, a kreator robi je z formularza

Lewa kolumna, YAML z kreatora (`configs/documents/potwierdzenie_odbioru.yaml`, przykład „Wypełnij przykładem”):

```yaml
id: potwierdzenie_odbioru
schema: potwierdzenie_odbioru.schema.json
classification:
  positive_patterns:
    - '(?i)Potwierdzenie\s+odbioru'
  minimum_matches: 1
options:
  label: "Potwierdzenie odbioru"
  llm_instructions: "Potwierdzenie odbioru dokumentów z nagłówkiem POTWIERDZENIE ODBIORU. ..."
```

Prawa kolumna, krótko:

- Kreator „Dodaj typ dokumentu” w widoku administratora: nazwa, frazy rozpoznające, pola, wskazówki dla modelu → YAML i JSON Schema do pobrania ([zrzut 15](demo/15-kreator-pola.png), [zrzut 16](demo/16-kreator-pliki.png)).
- Lista typów pochodzi z backendu (`GET /api/document-types`), więc nowy typ pojawia się w panelu po restarcie API.
- Bez zmian w prompcie systemowym i w kodzie procesora. Własne zestawy przez `--configs` i `--schemas`.
- Test: Sonnet na syntetycznym PDF-ie czwartej klasy (`examples/fourth_class`) zwrócił `numer: ABC-123` i `data: 2026-11-15`. To demonstracja rozszerzalności, a nie miara jakości.

**Uczciwie:** pliki z kreatora przechodzą `load_configs` backendu; ekstrakcji modelem na typie z kreatora nie mierzyliśmy.

Źródło: `docs/ADD_DOCUMENT_TYPE.md`, `frontend/wizard.js`. **Kryterium:** nowe typy dokumentów (1–20 pkt).

---

## 6. Jakość i koszt modelu

**Tytuł:** Mały model, jedno wywołanie na PDF

Tabela: lokalny F1 na syntetycznych danych UZP (nie oficjalny wynik konkursu).

| Pomiar | Model | Dokumenty | Lokalny F1 | Tokeny wejścia / wyjścia |
| --- | --- | --- | ---: | --- |
| Walidacja (12 spraw + negatyw) | Claude Sonnet 4.6 | 37 PDF | 0,9859 | – |
| Sprawy 46–48, prompt v1 | Claude Haiku 4.5 | 9 PDF | 0,9864 | 89 278 / 2 557 |
| 3 pierwsze sprawy rozwojowe, prompt v2 | Claude Haiku 4.5 | 9 PDF | 0,9146 | 56 101 / 2 215 |
| 3 pierwsze sprawy rozwojowe, prompt v2 | Claude Sonnet 4.6 | 9 PDF | 0,9796 | 56 110 / 2 208 |

Pod tabelą, drobnym drukiem:

- Klasyfikacja: 37/37 (walidacja, Sonnet), 9/9 (sprawy 46–48, Haiku).
- Próba na prawdziwym API z panelu, 21.11.2026, `claude-haiku-5-5`, `przyklad_01` + negatyw BZP: 4/4 pliki poprawnie sklasyfikowane, pola zgodne ze wzorcem: pełnomocnictwo 10/10, przelew 6/6, odwołanie 16/22; 15,9 s na całą sprawę. Wcześniejszy test zespołu na tej sprawie dał te same zgodności i 16,8 s; `przyklad_04`: 4/4 typy w 19,9 s.
- Ok. 9,9 tys. tokenów wejścia na PDF (89 278 / 9 w sprawach 46–48).
- **Model docelowy:** według UZP (21.11) otwarty i hostowany przez firmę z UE z polityką prywatności; klucz API podajemy w formularzu zgłoszenia. **Do uzupełnienia:** nazwa, liczba parametrów, licencja, dostawca, F1 na tym modelu. Modele Claude nie są otwarte, więc są tylko punktem odniesienia, nie modelem zgłoszenia.
- **Koszt na sprawę w zł:** do uzupełnienia według cennika wybranego dostawcy (mamy tokeny, nie mamy ceny).

**Notatka dla mówiącego:** mówimy „lokalnie, na syntetycznych danych UZP, małe próbki”. UZP liczy F1 z regułą 80% dla długich tekstów i porównuje listy po treści, więc nasze liczby nie są tym samym co wynik konkursu. Wynik Haiku 0,9898 z promptu `haiku-v1` pomijamy, bo prompt stroiono na tej samej próbce.

Źródło: `docs/MODEL_COMPARISON.md`, próba z 21.11 opisana w `docs/DEMO.md`. **Kryterium:** moc modelu (1–20 pkt), F1 (50%).

---

## 7. Co dalej

**Tytuł:** Od prototypu do pilotażu w UZP

- Wybór i pomiar otwartego modelu hostowanego w UE, potem jeden pomiar na odłożonych sprawach 55–60 (`evaluation/manifest.json`).
- Skany: testy OCR na prawdziwie wydrukowanych i zeskanowanych pismach, przypadki wielostronicowe, więcej negatywów.
- Źródło wartości i pewność pola w odpowiedzi API, żeby panel wskazywał, skąd wzięła się wartość. Dziś `/api/extract` ich nie zwraca.
- Typ z kreatora wgrywany do backendu bez ręcznego kopiowania plików i restartu.
- Pilotaż z urzędnikami UZP: **do uzupełnienia** (zakres, liczba spraw, termin).

**Zamknięcie (jedno zdanie):** „Urzędnik sprawdza dane obok oryginału zamiast je przepisywać, a nowy typ pisma to dwa pliki konfiguracyjne z kreatora.”

---

## Do uzupełnienia przed finałem

| Co | Slajd | Kto |
| --- | --- | --- |
| Model docelowy: nazwa, liczba parametrów, licencja, dostawca z UE i polityka prywatności | 6, 7, DEMO | backend |
| Lokalny F1, tokeny i czas sprawy na modelu docelowym | 6 | backend |
| Koszt jednej sprawy w zł | 6 | backend |
| Decyzja: na scenie model docelowy czy testowy z komentarzem | DEMO | zespół |
| Znaczniki źródła wartości w API i panelu (jeśli zdążą przed finałem) | 4, 7, DEMO | backend + frontend |
| Czas pracy urzędnika nad sprawą dziś (jeśli UZP poda) | 1 | zespół |
| Test OCR na prawdziwym skanie z Tesseractem w `PATH` | 7, DEMO | zespół |
| Edge na komputerze pokazowym (sprawdzony tylko Chrome 157) | DEMO | zespół |
| Plan pilotażu | 7 | zespół |
| Nazwa zespołu, logo, role na scenie | 1, DEMO | zespół |
