# Pokaz dla jury: scenariusz na 3–4 minuty

Scenariusz pokazu Odwołania2JSON w finale HackNation 2026 (wyzwanie UZP „Odwołania2json”). Każdy krok mówi, co klikamy, co mówimy i za które kryterium oceny zbiera punkty. Zrzuty ekranu są w [`docs/demo/`](demo/). Zrobiono je na atrapie (`?mock=1`), więc pokazują dane przykładowe, a nie wynik modelu.

Szkic slajdów: [`docs/SLAJDY.md`](SLAJDY.md).

## Kryteria, pod które gramy

Według [README UZP](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026) finał to **50% F1** i **50% elastyczności**. Elastyczność składa się z trzech części:

| Kryterium | Punkty | Co pokazujemy |
| --- | --- | --- |
| Moc modelu (mniejszy model = więcej punktów) | 1–20 | Jedno wywołanie modelu na PDF, mały model, liczby z `docs/MODEL_COMPARISON.md` |
| Nowe typy dokumentów bez przebudowy systemu | 1–20 | YAML + JSON Schema, widok „Typy dokumentów”, przykład `examples/fourth_class` |
| Inne funkcje, np. GUI | 1–10 | Panel: rubryki obok PDF-u, wstawianie zaznaczenia, znacznik poprawek, ZIP, folder sprawy |
| Premiowane: transparentność ekstrakcji | – | Podgląd PDF obok danych, „brak w dokumencie”, liczniki pól, walidacja schematem, oznaczone ręczne poprawki |
| F1 (50%) | – | Liczymy go na ukrytym zbiorze UZP, więc na scenie pokazujemy tylko lokalne pomiary i nazywamy je lokalnymi |

## Role

- **Prowadzący (mówi):** do uzupełnienia.
- **Operator (klika):** do uzupełnienia. Operator nie mówi, prowadzący nie dotyka myszy.

## Scenariusz (ok. 3:45)

Czasy są orientacyjne. Wersja z modelem (wariant A) i z atrapą (wariant B, plan B) różnią się tylko źródłem wyników, a kliknięcia są te same.

### 0:00–0:25 · Problem (slajd 1)

**Mówimy:** „Urzędnik UZP dostaje sprawę odwoławczą jako kilka PDF-ów: odwołanie, pełnomocnictwo, potwierdzenie przelewu, czasem skan albo zupełnie inne pismo. Dziś przepisuje z nich ręcznie kilkadziesiąt pól: daty, KRS, NIP, numery BZP i TED, rachunki. Odwołania2JSON robi to za niego i oddaje JSON w formacie UZP.”

### 0:25–0:50 · Wgranie sprawy · *Inne funkcje (GUI)*

**Klikamy:** panel jest otwarty na pustej sprawie ([01-start.png](demo/01-start.png)). „Folder sprawy” → wybieramy folder sprawy. Na atrapie zamiast tego „Wybierz pliki z dysku” → pięć plików z `frontend/mock/pdf/` ([02-wgrane-pliki.png](demo/02-wgrane-pliki.png)).

**Mówimy:** „Wgrywamy całą sprawę naraz, tak jak przychodzi do urzędu. Nazwy plików nie mają znaczenia: typ rozpoznajemy po treści.”

### 0:50–1:15 · Przetworzenie · *Moc modelu, F1*

**Klikamy:** „Przetwórz 5 plików” ([03-przetwarzanie.png](demo/03-przetwarzanie.png)).

**Mówimy (w czasie oczekiwania):** „Każdy PDF to jedno wywołanie modelu, które naraz klasyfikuje i wyciąga dane. Wynik przechodzi walidację JSON Schema danej klasy, zanim trafi do urzędnika. Dzięki temu wystarcza mały model.”

Na atrapie wynik pojawia się po 1,4 s, bo tyle wynosi sztuczne opóźnienie. **Nie podajemy tej liczby jako szybkości systemu.**

### 1:15–1:50 · Wynik sprawy i statusy · *Transparentność*

**Klikamy:** nic. Panel sam otwiera pierwszy rozpoznany dokument ([04-wynik-odwolanie.png](demo/04-wynik-odwolanie.png)). Pokazujemy palcem listę po lewej i „Wynik sprawy”.

**Mówimy:** „Każdy plik ma własny status: trzy dokumenty rozpoznane, jedno ogłoszenie BZP, które nie jest żadną z klas, i jeden skan, który wymaga OCR. Błąd jednego pliku nie blokuje reszty sprawy. Po prawej jest oryginał, po lewej rubryki. Puste pole jest zakreskowane i podpisane »brak w dokumencie«, więc widać, czego model nie znalazł, zamiast zgadywać.”

### 1:50–2:25 · Poprawka z PDF-u · *Inne funkcje, transparentność*

**Klikamy:** rubryka „Numer KRS” odwołującego → zaznaczamy w PDF-ie linię „KRS: 0000 054 588” → „Wstaw do: Numer KRS” ([05-zaznaczenie-w-pdf.png](demo/05-zaznaczenie-w-pdf.png)). Potem w „Zamawiający” zaznaczamy krzyżyk „Prowadzi postępowanie” ([06-reczna-poprawka.png](demo/06-reczna-poprawka.png)).

**Mówimy:** „Jeśli model się pomyli, urzędnik nie przepisuje. Zaznacza tekst w PDF-ie, a panel wyłuskuje samą wartość, tu 10 cyfr KRS bez etykiety i spacji. Każda ręczna zmiana jest oznaczona jako »poprawione«, można ją cofnąć, a licznik pokazuje, ile pól poprawiono.”

### 2:25–2:45 · Pobranie · *zgodność z formatem UZP*

**Klikamy:** „JSON” w przełączniku ([07-widok-json.png](demo/07-widok-json.png)) → „Pobierz wyniki (ZIP, 4 pliki)”.

**Mówimy:** „ZIP ma układ `output/<sprawa>/`, którego wymaga UZP: JSON dla każdego rozpoznanego dokumentu, pusty plik dla dokumentu spoza klas, a skan z błędem nie dostaje pliku, tak samo jak w CLI.”

Sprawdzone na atrapie: ZIP `sprawa.zip` zawiera `odwolanie.json`, `pelnomocnictwo.json`, `potwierdzenie_przelewu.json` i pusty `ogloszenie_bzp.json` (0 bajtów).

### 2:45–3:15 · Nowy typ dokumentu · *Nowe typy (1–20 pkt)*

**Klikamy:** menu „Typy dokumentów” ([11-typy-dokumentow.png](demo/11-typy-dokumentow.png)). Potem slajd 5 z dwoma plikami `examples/fourth_class/`.

**Mówimy:** „Typ dokumentu to dwa pliki: YAML z opisem dla modelu i JSON Schema z polami. Nie trzeba zmieniać ani prompta systemowego, ani kodu. Przykład: dodaliśmy »potwierdzenie odbioru« i model zwrócił numer i datę z syntetycznego PDF-u. Panel pokazuje pola nieznanego mu typu automatycznie.”

Uczciwie: przykładowa czwarta klasa była testowana z Sonnetem na jednym syntetycznym PDF-ie. Na atrapie widok typów pokazuje typy wbudowane w panel, bo backend nie ma jeszcze `GET /api/document-types`.

### 3:15–3:45 · Jakość, koszt, co dalej (slajdy 6–7)

**Mówimy:** liczby z [`docs/MODEL_COMPARISON.md`](MODEL_COMPARISON.md), zawsze z dopiskiem „lokalnie, na syntetycznych danych UZP”. Następnie: docelowy model otwarty w UE/EOG (do uzupełnienia) i pilotaż w urzędzie.

### Opcjonalnie (+30 s) · Skan · *F1 na skanach, transparentność*

Szczegóły i pomiary: [`docs/SKANY.md`](SKANY.md).

- Materiał: skan z `dane/skany/` repozytorium UZP (np. pełnomocnictwo albo przelew, bo OCR zajmuje 1–2 s; odwołanie ze skanu to 10–17 s samego OCR). Na tych skanach w tekście po OCR jest 238 z 266 wartości pól (89,5%). Model w tym pomiarze nie brał udziału.
- Warunek: Tesseract z `pol` na komputerze z backendem (albo Docker). Bez niego skan dostaje błąd `ocr_required` ([10-blad-ocr.png](demo/10-blad-ocr.png)).
- Na scenie mówimy: „Skan nie ma tekstu, więc przed modelem czyta go OCR. Wynik sprawdzamy obok oryginału.” Zaznaczania tekstu w PDF-ie na skanie nie pokazujemy, bo skan nie ma warstwy tekstu; panel mówi to nad podglądem.
- Jeśli OCR nie działa, mówimy: „Skan bez warstwy tekstu dostaje jasny błąd, a reszta sprawy przechodzi”, i pokazujemy zrzut 10.

## Plan B: API albo model nie działa

Panel ma tryb atrapy, który działa bez backendu, bez LLM i bez internetu. Odpowiedzi pochodzą wtedy z `frontend/mock/extract-response.json` i są dobierane po nazwie pliku.

1. W terminalu, z katalogu repozytorium:

   ```powershell
   python -m http.server 5500 -d frontend
   ```

2. W przeglądarce otwieramy `http://localhost:5500/?mock=1`. W prawym górnym rogu widać żółtą etykietę „Dane przykładowe”.
3. Wgrywamy pięć plików z `frontend/mock/pdf/`: `odwolanie.pdf`, `pelnomocnictwo.pdf`, `potwierdzenie_przelewu.pdf`, `ogloszenie_bzp.pdf`, `skan_pisma.pdf`. Dalej idziemy według scenariusza.
4. **Mówimy otwarcie:** „Pokazujemy panel na danych przykładowych; wyniki modelu są na slajdzie 6.” Nie udajemy, że to wynik na żywo.

Ostatnia deska ratunku, gdy nie działa nawet przeglądarka: zrzuty z `docs/demo/` w kolejności 01 → 11 jako slajdy.

## Wariant A: z prawdziwym modelem

**Do uzupełnienia przed finałem.** W tej wersji panel wysyła żądanie pod względny adres `/api/extract`, a API (`src/kio_extract/api.py`) nie serwuje katalogu `frontend/`. Panel otwarty z `http.server` na porcie 5500 nie trafi więc do API na porcie 8000. Potrzebne jest jedno z dwóch: API serwujące `frontend/` pod `/` albo proxy. Tak samo opisuje to `frontend/PRODUCT.md` („Nieustalone: czy backend serwuje `frontend/`…”).

Kiedy to zadziała:

```powershell
.venv/Scripts/python.exe -m uvicorn --app-dir src kio_extract.api:create_app --factory --host 127.0.0.1 --port 8000
```

Ustawiamy `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL` i `LLM_API_KEY` w `.env` (szczegóły w `README.md`, „Tryb LLM”). Bez `LLM_MODEL` API działa w trybie regułowym. Na pokaz bierzemy sprawę z danych treningowych UZP (np. `przyklad_01`), nie z ukrytego zbioru.

Z testu zespołu z modelem Haiku na `przyklad_01` (wynik nie jest zapisany w repozytorium): pełnomocnictwo 10/10 pól zgodnych ze wzorcem, przelew 6/6, odwołanie 16/22; czas całej sprawy 16,8 s. Oczekiwanie na scenie trwa więc kilkanaście sekund, a nie 1,4 s jak na atrapie. Tekst do kroku „Przetworzenie” jest dobrany tak, żeby wypełnić ten czas.

## Przed wejściem na scenę

**Dzień wcześniej**

- [ ] Wybrany i opisany model docelowy: otwarty, dostawca i serwery w UE/EOG (wymóg UZP). Do uzupełnienia.
- [ ] Rozstrzygnięty wariant A albo B. Przy wariancie A panel i API działają pod jednym adresem.
- [ ] Jedna pełna próba z zegarkiem: mieścimy się w 3:45.
- [ ] Liczby na slajdzie 6 zgadzają się z `docs/MODEL_COMPARISON.md` (albo z nowym pomiarem na modelu docelowym).
- [ ] Jeśli pokazujemy skan: Tesseract + `pol` zainstalowane, skan UZP przetestowany na żywo.

**15 minut przed**

- [ ] Laptop podłączony do zasilania, tryb „nie przeszkadzać”, wyłączone powiadomienia i synchronizacja.
- [ ] Przeglądarka w trybie gościa, bez zakładek i rozszerzeń, powiększenie 100%, okno na pełny ekran (zrzuty mają 1440×900).
- [ ] Serwer atrapy uruchomiony (`python -m http.server 5500 -d frontend`), karta `http://localhost:5500/?mock=1` otwarta, nawet jeśli gramy wariant A.
- [ ] Wariant A: API wstało, `.env` ustawiony, jedna próbna sprawa przeszła w ostatnich 15 minutach. Klucza API nie pokazujemy na ekranie.
- [ ] Folder z plikami do wgrania otwarty w oknie wyboru (szybki dostęp), nazwy plików czytelne.
- [ ] Panel na pustej sprawie: „Nowa sprawa” w menu. Pamiętany stan podglądu PDF włączony.
- [ ] Slajdy otwarte w drugiej karcie albo na drugim ekranie, przełączanie przećwiczone.
- [ ] Zrzuty z `docs/demo/` pod ręką jako ostateczny plan B.
- [ ] Projektor: sprawdzona rozdzielczość, kontrast łososiowego tła, czytelność kratek z ostatniego rzędu.

## Zrzuty ekranu

Zrobione na atrapie, okno 1440×900, skala 1,5.

| Plik | Moment |
| --- | --- |
| [01-start.png](demo/01-start.png) | Pusta sprawa, trzy kroki |
| [02-wgrane-pliki.png](demo/02-wgrane-pliki.png) | Pięć plików na liście przed przetworzeniem |
| [03-przetwarzanie.png](demo/03-przetwarzanie.png) | Stan „Przetwarzanie…” |
| [04-wynik-odwolanie.png](demo/04-wynik-odwolanie.png) | Rubryki odwołania obok podglądu PDF, wynik sprawy |
| [05-zaznaczenie-w-pdf.png](demo/05-zaznaczenie-w-pdf.png) | Zaznaczony KRS w PDF-ie, przycisk „Wstaw do: Numer KRS” |
| [06-reczna-poprawka.png](demo/06-reczna-poprawka.png) | Znacznik „poprawione” i licznik poprawek |
| [07-widok-json.png](demo/07-widok-json.png) | Widok JSON odwołania |
| [08-przelew.png](demo/08-przelew.png) | Potwierdzenie przelewu: kwota, rachunki w kratkach |
| [09-nie-rozpoznano.png](demo/09-nie-rozpoznano.png) | Ogłoszenie BZP jako „Nie rozpoznano” |
| [10-blad-ocr.png](demo/10-blad-ocr.png) | Skan bez warstwy tekstu: błąd `ocr_required` |
| [11-typy-dokumentow.png](demo/11-typy-dokumentow.png) | Widok administratora „Typy dokumentów” |

Liczby widoczne na zrzutach (np. „16/22 pól”, „1,4 s”) pochodzą z danych przykładowych i sztucznego opóźnienia atrapy. Nie są wynikiem modelu.
