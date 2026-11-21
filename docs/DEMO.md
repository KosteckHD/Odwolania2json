# Pokaz dla jury: scenariusz na 3–4 minuty

Scenariusz pokazu Odwołania2JSON w finale HackNation 2026 (wyzwanie UZP „Odwołania2json”). Każdy krok mówi, co klikamy, co mówimy i za które kryterium oceny zbiera punkty. Zrzuty ekranu są w [`docs/demo/`](demo/). Zrobiono je na atrapie (`?mock=1`), więc pokazują dane przykładowe, a nie wynik modelu.

Szkic slajdów: [`docs/SLAJDY.md`](SLAJDY.md).

## Kryteria, pod które gramy

Według [README UZP](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026) finał to **50% F1** i **50% elastyczności**. Elastyczność składa się z trzech części:

| Kryterium | Punkty | Co pokazujemy |
| --- | --- | --- |
| Moc modelu (mniejszy model = więcej punktów) | 1–20 | Profil Mistral EU i wyłącznie potwierdzone wyniki z `docs/MODEL_COMPARISON.md` |
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

**Mówimy (w czasie oczekiwania):** „Zwykle jeden PDF oznacza jedno wywołanie modelu, które naraz klasyfikuje i wyciąga dane. Jeśli odpowiedź jest niepoprawnym JSON-em albo nie przechodzi walidacji, system robi jedno ponowienie. Wynik przechodzi walidację JSON Schema danej klasy, zanim trafi do urzędnika.”

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

**Klikamy:** menu „Typy dokumentów” ([11-typy-dokumentow.png](demo/11-typy-dokumentow.png)) → „+ Dodaj typ dokumentu” → „Wypełnij przykładem”. Pokazujemy wygenerowane YAML i JSON Schema, po czym wracamy do nowej sprawy i wgrywamy `examples/fourth_class/samples/potwierdzenie_odbioru.pdf` oraz `podobne-pismo.pdf`.

**Mówimy:** „Typ dokumentu to dwa pliki: YAML z opisem i JSON Schema z polami. Kreator przygotowuje pliki bez ręcznego pisania kodu. Profil API wczytał je razem z trzema klasami UZP. Zgodny PDF zwraca numer i datę, a podobne pismo »Potwierdzenie nadania« zostaje `unknown`. Panel pobiera listę klas z backendu i pokazuje nowe pola.”

Wynik tej demonstracji sprawdzono przez rzeczywiste API na dwóch syntetycznych PDF-ach w trybie regułowym, bez wywołania modelu: pozytywny PDF poprawnie zwrócił `PO-2026-0314` i datę `2026-11-20`, a podobny negatyw otrzymał `unknown`. To potwierdza konfigurację i obsługę klas, ale nie jakość LLM. Lista typów pochodzi z `GET /api/document-types`.

### 3:15–3:45 · Jakość, koszt, co dalej (slajdy 6–7)

**Mówimy:** liczby z [`docs/MODEL_COMPARISON.md`](MODEL_COMPARISON.md), zawsze z dopiskiem „lokalnie, na syntetycznych danych UZP”. Porównanie Ministral 3 8B/14B jeszcze nie ma wyniku: EU API zwróciło HTTP 429. Nie podajemy benchmarku ani nie nazywamy 8B zwycięzcą. Następnie: stan pilotażu w urzędzie.

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

Uruchom panel i API pod tym samym adresem przypiętym profilem EU:

```powershell
.venv/Scripts/python.exe start_jury.py
```

Skrypt jawnie ustawia `https://api.eu.mistral.ai/v1` i przypięty identyfikator `ministral-8b-2512`; klucz pobiera z `MISTRA_API_KEY` lub `.env`. Kandydat przeszedł kontrolę dostępności i krótki techniczny smoke, ale nie pełne porównanie jakości. Do czasu odblokowania limitu 429 nie przedstawiamy go jako wybranego modelu konkursowego. Na pokaz bierzemy sprawę z danych treningowych UZP (np. `przyklad_01`), nie z ukrytego zbioru.

Z testu zespołu z modelem Haiku na `przyklad_01` (wynik nie jest zapisany w repozytorium): pełnomocnictwo 10/10 pól zgodnych ze wzorcem, przelew 6/6, odwołanie 16/22; czas całej sprawy 16,8 s. Oczekiwanie na scenie trwa więc kilkanaście sekund, a nie 1,4 s jak na atrapie. Tekst do kroku „Przetworzenie” jest dobrany tak, żeby wypełnić ten czas.

### Osobny profil pokazu czwartej klasy

Przed pokazem przygotuj zestaw trzech klas UZP i demonstracyjnej czwartej klasy. Pliki przykładowe są tymi samymi plikami YAML i JSON Schema, które generuje kreator. Zmiany konfiguracji działają po restarcie API.

```powershell
New-Item -ItemType Directory -Force .local/demo-configs, .local/demo-schemas | Out-Null
Copy-Item configs/documents/*.yaml .local/demo-configs/
Copy-Item schemas/*.json .local/demo-schemas/
Copy-Item examples/fourth_class/configs/*.yaml .local/demo-configs/
Copy-Item examples/fourth_class/schemas/*.json .local/demo-schemas/
$env:KIO_CONFIGS_DIR = (Resolve-Path .local/demo-configs).Path
$env:KIO_SCHEMAS_DIR = (Resolve-Path .local/demo-schemas).Path
```

Do prezentacji samego kreatora uruchom atrapę WWW w osobnym terminalu: `python -m http.server 5500 -d frontend`, a potem otwórz `http://localhost:5500/?mock=1`. Wypełnij formularz i obejrzyj oba pliki. Następnie przejdź do API profilu z czwartą klasą pod `http://127.0.0.1:8000/` i wgraj przykładowe PDF-y. Ten profil jest deterministycznym sprawdzeniem konfiguracji i odrzucenia negatywu, bez wywołania modelu:

```powershell
.venv/Scripts/python.exe start_jury.py --rules
```

Nazwij ten krok testem klasyfikacji i ekstrakcji regułowej. Nie przedstawiaj go jako odpowiedzi LLM. Gdy limit Mistral jest dostępny, przetwarzanie modelowe uruchamiaj osobno przez `start_jury.py`.

## Przed wejściem na scenę

**Dzień wcześniej**

- [ ] Po zdjęciu limitu wykonane porównanie Ministral 3 8B/14B i potwierdzone warunki licencji modelu oraz przetwarzania w UE/EOG. Do tego czasu nie deklarujemy zwycięskiego modelu.
- [ ] Rozstrzygnięty wariant A albo B. Wariant A uruchamia `start_jury.py`; panel i API działają pod jednym adresem.
- [ ] Jedna pełna próba z zegarkiem: mieścimy się w 3:45.
- [ ] Liczby na slajdzie 6 zgadzają się z `docs/MODEL_COMPARISON.md` (albo z nowym pomiarem na modelu docelowym).
- [ ] Jeśli pokazujemy skan: Tesseract + `pol` zainstalowane, skan UZP przetestowany na żywo.

**15 minut przed**

- [ ] Laptop podłączony do zasilania, tryb „nie przeszkadzać”, wyłączone powiadomienia i synchronizacja.
- [ ] Przeglądarka w trybie gościa, bez zakładek i rozszerzeń, powiększenie 100%, okno na pełny ekran (zrzuty mają 1440×900).
- [ ] Serwer atrapy uruchomiony (`python -m http.server 5500 -d frontend`), karta `http://localhost:5500/?mock=1` otwarta, nawet jeśli gramy wariant A.
- [ ] Wariant A: API wstało, profil EU ustawiony, jedna próbna sprawa przeszła w ostatnich 15 minutach. Klucza API nie pokazujemy na ekranie.
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
