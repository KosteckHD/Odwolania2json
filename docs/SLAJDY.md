# Szkic slajdów dla jury

Siedem slajdów do pokazu z [`docs/DEMO.md`](DEMO.md). Ten sam szkic jest złożony jako deck: [Odwołania2JSON – pitch dla jury](https://claude.ai/artifact/8LMCpKNd6DeYBGvRYi8EnP). Deck jest prywatny, dopóki właściciel nie udostępni go przez menu Share; eksport do PPTX i PDF jest w decku. Wszystkie liczby pochodzą z repozytorium (źródło przy każdym slajdzie). Brakujące dane są oznaczone **do uzupełnienia**. Nie wpisujemy w ich miejsce szacunków.

Styl: jak panel ([`frontend/DESIGN.md`](../frontend/DESIGN.md)), czyli łososiowy papier `#FAF1EC`, czerwień druku `#9A3218` na etykietach, dane czernią, krój Public Sans, bez cieni i gradientów.

---

## 1. Problem

**Tytuł:** Sprawa odwoławcza to kilka PDF-ów i kilkadziesiąt pól do przepisania

- Do UZP wpływa sprawa jako zestaw PDF-ów: odwołanie, pełnomocnictwo, potwierdzenie przelewu, czasem skan albo inne pismo.
- Same pola UZP: 22 w odwołaniu, 8 w pełnomocnictwie, 6 w przelewie (schematy w `schemas/`).
- Dane wrażliwe na błąd: KRS, NIP, REGON, PESEL, numery BZP i TED, rachunki, kwoty, daty.
- Ile czasu urzędnik spędza dziś na jednej sprawie: **do uzupełnienia** (nie mamy tej liczby od UZP).

**Notatka dla mówiącego:** jedno zdanie o urzędniku, bez statystyk, których nie mamy.

Źródło liczby pól: `frontend/fields.js`, `schemas/*.schema.json`, widok „Typy dokumentów” ([zrzut 11](demo/11-typy-dokumentow.png)).

---

## 2. Rozwiązanie

**Tytuł:** Odwołania2JSON: PDF-y sprawy wchodzą, JSON w formacie UZP wychodzi

- Rozpoznaje typ każdego PDF-u po treści, a nie po nazwie pliku.
- Wyciąga dane i zapisuje `output/<sprawa>/<plik>.json` w formacie UZP. Dokument spoza klas dostaje pusty plik.
- Dwa wejścia do tego samego przetwarzania: CLI (`main.py`, `input/` → `output/`) i panel WWW dla urzędnika.
- Działa lokalnie na CPU z komponentów open source; model językowy przez API.

**Obraz:** [zrzut 04](demo/04-wynik-odwolanie.png), czyli rubryki obok PDF-u.

---

## 3. Jak to działa

**Tytuł:** Jedno wywołanie modelu na dokument, potem walidacja schematem

Schemat przepływu (od lewej):

1. **PDF** → odczyt tekstu (`pypdf`); strony bez warstwy tekstu → OCR (Tesseract, `pol`).
2. **Jedno wywołanie LLM** dostaje system prompt, schematy klas i słownik powodów odwołania; zwraca `typ` i `dane`.
3. **Walidacja JSON Schema** klasy i normalizacja (np. format TED).
4. **Wynik:** JSON dla klasy, pusty plik dla `unknown`, błąd z kodem (np. `ocr_required`) bez zatrzymywania reszty sprawy.

Pod spodem:

- Ograniczanie tempa i ponawianie po HTTP 429 (`LLM_REQUEST_INTERVAL_SECONDS`, `LLM_MAX_429_RETRIES`).
- Raport przebiegu (`--report`) i lokalny ewaluator F1 z podziałem na pola i klasy (`evaluation/evaluate.py`).
- Tryb regułowy jako lokalna baza porównawcza, Docker Compose z Tesseractem.

Źródło: `README.md`.

---

## 4. Panel dla urzędnika

**Tytuł:** Urzędnik sprawdza, a nie przepisuje

- Wgranie plików albo całego folderu sprawy, status każdego pliku: rozpoznany / nie rozpoznano / błąd.
- Rubryki obok podglądu PDF; identyfikatory i daty w kratkach jak na blankiecie.
- Puste pole jest widoczne: zakreskowane, z dopiskiem „brak w dokumencie”.
- Zaznaczenie tekstu w PDF-ie wstawia do rubryki samą wartość (np. 10 cyfr KRS z „KRS: 0000 054 588”).
- Każda ręczna zmiana jest oznaczona jako „poprawione”, z możliwością cofnięcia i licznikiem poprawek.
- ZIP z wynikami w układzie `output/<sprawa>/`. Tryb atrapy działa bez backendu.
- Statyczny HTML/CSS/JS bez budowania i bez CDN; fonty i PDF.js w repozytorium.

**Obrazy:** [zrzut 05](demo/05-zaznaczenie-w-pdf.png) i [zrzut 06](demo/06-reczna-poprawka.png).

**Kryterium:** inne funkcje (1–10 pkt), transparentność ekstrakcji.

---

## 5. Nowy typ dokumentu bez zmiany kodu

**Tytuł:** Nowa klasa to dwa pliki konfiguracyjne

Lewa kolumna, YAML (`examples/fourth_class/configs/potwierdzenie.yaml`):

```yaml
id: potwierdzenie
schema: potwierdzenie.schema.json
classification:
  positive_patterns: ['(?i)POTWIERDZENIE ODBIORU']
options:
  llm_instructions: "Potwierdzenie odbioru dokumentów z nagłówkiem POTWIERDZENIE ODBIORU. ..."
```

Prawa kolumna, krótko:

- JSON Schema z polami w `schemas/` (tu `potwierdzenie.schema.json`).
- Bez zmian w prompcie systemowym i kodzie procesora. Własne zestawy przez `--configs` i `--schemas`.
- Panel pokazuje pola nieznanego mu typu automatycznie (grupa ogólna).
- Test: Sonnet na syntetycznym PDF-ie zwrócił `numer: ABC-123` i `data: 2026-11-15`. To demonstracja rozszerzalności, a nie miara jakości.
- Lista typów z backendu (`GET /api/document-types`): **do uzupełnienia**. Dziś panel pokazuje typy, które sam zna.

Źródło: `docs/ADD_DOCUMENT_TYPE.md`. **Kryterium:** nowe typy dokumentów (1–20 pkt).

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
- Sprawa `przyklad_01`, Haiku, test zespołu poza repozytorium: pełnomocnictwo 10/10 pól, przelew 6/6, odwołanie 16/22; 16,8 s na całą sprawę.
- Ok. 9,9 tys. tokenów wejścia na PDF (89 278 / 9 w sprawach 46–48).
- **Model docelowy:** otwarty, dostawca i serwery w UE/EOG. **Do uzupełnienia:** nazwa, liczba parametrów, licencja, F1 na tym modelu. Modele Claude nie są otwarte, więc nie są modelem konkursowym.
- **Koszt na sprawę w zł:** do uzupełnienia według cennika wybranego dostawcy (mamy tokeny, nie mamy ceny).

**Notatka dla mówiącego:** mówimy „lokalnie, na syntetycznych danych UZP, małe próbki”. Nie porównujemy z ukrytym zbiorem. Wynik Haiku 0,9898 z promptu `haiku-v1` pomijamy na slajdzie, bo prompt stroiono na tej samej próbce.

Źródło: `docs/MODEL_COMPARISON.md`. **Kryterium:** moc modelu (1–20 pkt), F1 (50%).

---

## 7. Co dalej

**Tytuł:** Od prototypu do pilotażu w UZP

- Pomiar na modelu docelowym w UE/EOG, a potem jeden pomiar na odłożonych sprawach 55–60 (`evaluation/manifest.json`).
- Skany: testy OCR na prawdziwie wydrukowanych i zeskanowanych pismach, przypadki wielostronicowe, więcej negatywów.
- Panel i API pod jednym adresem; lista typów dokumentów z backendu.
- Źródło wartości i pewność pola w odpowiedzi API, żeby panel mógł wskazać, skąd wzięła się wartość (dziś API ich nie zwraca).
- Pilotaż z urzędnikami UZP: **do uzupełnienia** (zakres, liczba spraw, termin).

**Zamknięcie (jedno zdanie):** „Urzędnik sprawdza dane obok oryginału zamiast je przepisywać, a nowy typ pisma to dwa pliki konfiguracyjne.”

---

## Do uzupełnienia przed finałem

| Co | Slajd | Kto |
| --- | --- | --- |
| Model docelowy: nazwa, liczba parametrów, licencja, dostawca i region UE/EOG | 6, 7 | backend |
| Lokalny F1 i tokeny na modelu docelowym | 6 | backend |
| Koszt jednej sprawy w zł | 6 | backend |
| Czas pracy urzędnika nad sprawą dziś (jeśli UZP poda) | 1 | zespół |
| Panel i API pod jednym adresem (warunek pokazu na żywo z modelem) | 7, DEMO | backend + frontend |
| `GET /api/document-types` | 5 | backend |
| Test OCR na prawdziwym skanie | 7, DEMO | zespół |
| Plan pilotażu | 7 | zespół |
| Nazwa zespołu, logo, role na scenie | 1, DEMO | zespół |
