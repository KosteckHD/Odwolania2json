# Pokaz dla jury: scenariusz na 3–4 minuty

Scenariusz pokazu Odwołania2JSON w finale HackNation 2026 (wyzwanie UZP „Odwołania2json”). Każdy krok mówi, co klikamy, co mówimy i za które kryterium zbiera punkty. Zrzuty są w [`docs/demo/`](demo/). Zrobiono je 21.11.2026 na prawdziwym API (`start.bat`, model testowy `claude-haiku-5-5`) na sprawie `przyklad_01` z danych UZP i jednym negatywie. Wyjątek: zrzut 10 (błąd OCR) pochodzi z atrapy.

Szkic slajdów: [`docs/SLAJDY.md`](SLAJDY.md).

## Kryteria, pod które gramy

Według [README UZP](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026) finał to **50% F1** i **50% elastyczności**. Uzupełnienia od UZP z 21.11 są w drugiej tabeli.

| Kryterium | Punkty | Co pokazujemy |
| --- | --- | --- |
| F1 (50%) | – | UZP liczy go na ukrytym zbiorze z plików `output/`. Na scenie pokazujemy tylko lokalne pomiary i nazywamy je lokalnymi. |
| Moc modelu (mniejszy model = więcej punktów) | 1–20 | Jedno wywołanie modelu na PDF, walidacja schematem. Nazwa modelu i czas są w podsumowaniu sprawy. Docelowy otwarty model w UE jest **do potwierdzenia**. |
| Nowe typy dokumentów bez przebudowy systemu | 1–20 | Lista typów z backendu (`GET /api/document-types`), kreator „Dodaj typ dokumentu” (YAML + JSON Schema), przykład `examples/fourth_class`. |
| Inne funkcje, np. GUI | 1–10 | Panel: rubryki obok PDF-u, wstawianie zaznaczenia, znacznik poprawek, kopia robocza, ZIP, folder sprawy, atrapa. |
| Premiowane: transparentność ekstrakcji | – | PDF obok danych, „brak w dokumencie”, model i czas przebiegu, walidacja schematem, oznaczone ręczne poprawki. |

Ustalenia UZP z 21.11.2026, które zmieniają to, co mówimy:

| Ustalenie | Co z tego wynika na pokazie |
| --- | --- |
| Model musi być otwarty i hostowany przez firmę z UE z polityką prywatności | Claude nie może być modelem zgłoszenia. Na pokazie mówimy wprost, że to model testowy, a docelowy jest do potwierdzenia. |
| Klucz API podaje się w formularzu zgłoszenia | Klucz trzymamy w `.env`, nigdy na ekranie ani w repozytorium. |
| Plik spoza klas → JSON `{}` | Negatyw dostaje `{}`, co widać w panelu i w ZIP-ie. |
| Imiona i nazwiska w mianowniku | Panel podpowiada „(w mianowniku)” przy polach z nazwiskami. |
| F1 z regułą 80% dla długich tekstów, listy porównywane po treści | Nie obiecujemy liczby F1; podajemy lokalne pomiary. |
| Wynik liczony z plików `output/`, poprawki w panelu nie wpływają na F1, GUI to do 10 pkt | Poprawki pokazujemy jako narzędzie urzędnika, a nie jako sposób na lepsze F1. |

## Role

- **Prowadzący (mówi):** do uzupełnienia.
- **Operator (klika):** do uzupełnienia. Operator nie mówi, prowadzący nie dotyka myszy.

## Start

W katalogu repozytorium jedna komenda:

```powershell
.\start.bat
```

`start.bat` uruchamia API razem z panelem pod `http://127.0.0.1:8000/` i otwiera przeglądarkę, gdy serwer odpowiada. Bez `.venv` wypisuje dwie komendy instalacji i kończy pracę. Bez `.env` ostrzega, że API działa w trybie regułowym, bez modelu. Inny port: najpierw `set PORT=8080` w `cmd`, potem `start.bat`.

## Scenariusz (ok. 3:45)

Czasy są orientacyjne. Pliki do wgrania: `odwolanie.pdf`, `pelnomocnictwo.pdf`, `potwierdzenie_przelewu.pdf` z `dane/przyklad_01` repozytorium UZP i `2025_BZP 00143067_01.pdf` z `dane/negatywne` (ogłoszenie BZP, 3 strony). To dane treningowe UZP, nie ukryty zbiór.

### 0:00–0:20 · Problem (slajd 1)

**Mówimy:** „Urzędnik UZP dostaje sprawę odwoławczą jako kilka PDF-ów: odwołanie, pełnomocnictwo, potwierdzenie przelewu, a czasem zupełnie inne pismo. Dziś przepisuje z nich ręcznie kilkadziesiąt pól: daty, KRS, NIP, numery BZP i TED, rachunki. Odwołania2JSON robi to za niego i oddaje JSON w formacie UZP.”

### 0:20–0:40 · Wgranie sprawy · *GUI*

**Klikamy:** panel jest już otwarty na pustej sprawie ([01-start.png](demo/01-start.png)). „Wybierz pliki z dysku” → cztery pliki ([02-wgrane-pliki.png](demo/02-wgrane-pliki.png)). Albo „Folder sprawy”, jeśli mamy folder z tymi czterema plikami.

**Mówimy:** „Wgrywamy całą sprawę naraz, tak jak przychodzi do urzędu. Nazwy plików nie mają znaczenia, bo typ rozpoznajemy po treści. Czwarty plik to ogłoszenie BZP, czyli dokument spoza naszych klas.”

### 0:40–1:05 · Przetworzenie · *Moc modelu, F1*

**Klikamy:** „Przetwórz 4 pliki” ([03-przetwarzanie.png](demo/03-przetwarzanie.png)). Widać „Anuluj” i status „Przetwarzanie…” przy każdym pliku.

**Mówimy (w czasie oczekiwania):** „Każdy PDF to jedno wywołanie modelu, które naraz klasyfikuje dokument i wyciąga dane. Wynik przechodzi walidację JSON Schema swojej klasy, zanim trafi do urzędnika. Dzięki temu wystarcza mały model. Dziś na scenie działa model testowy; w zgłoszeniu będzie otwarty model hostowany w UE, tak jak wymaga UZP.”

Czas: w próbie z 21.11 cała sprawa zajęła **15,9 s** (4 pliki, `claude-haiku-5-5`). We wcześniejszym teście zespołu `przyklad_01` trwał 16,8 s, a `przyklad_04` 19,9 s (4/4 typy rozpoznane). Tekst wyżej wypełnia ok. 15–20 s. Na innym modelu czas będzie inny.

### 1:05–1:35 · Wynik sprawy · *Transparentność*

**Klikamy:** nic. Panel sam otwiera pierwszy rozpoznany dokument ([04-wynik-odwolanie.png](demo/04-wynik-odwolanie.png)). Pokazujemy palcem listę po lewej, „Wynik sprawy” i wiersz „Przebieg”.

**Mówimy:** „Każdy plik ma własny status: trzy dokumenty rozpoznane i ogłoszenie BZP jako »Nie rozpoznano«. W podsumowaniu widać, który model to przetworzył i ile to trwało. Po prawej jest oryginał, po lewej rubryki. Puste pole jest zakreskowane i podpisane »brak w dokumencie«, więc widać, czego model nie znalazł, zamiast zgadywać.”

Na zrzucie: „Przebieg: model: claude-haiku-5-5 · 15,9 s”. Liczniki przy plikach (np. „14/22 pól”) to **pola wypełnione**, a nie zgodne ze wzorcem; nie nazywamy ich trafnością.

Znaczniki źródła (z której strony PDF pochodzi wartość): **nie pokazujemy**. API ich dziś nie zwraca (`/api/extract` oddaje `filename`, `status`, `type`, `data` i `meta.model`). Jeśli wejdą przed finałem, dopisać tu krok. Do uzupełnienia.

### 1:35–2:10 · Poprawka z PDF-u · *GUI, transparentność*

**Klikamy:** rubryka „3. Dzień zaskarżonej czynności” (model zostawił ją pustą) → w PDF-ie zaznaczamy „20 marca 2026” w zdaniu „Zamawiający w dniu 20 marca 2026 roku unieważnił postępowanie” → „Wstaw do: Dzień zaskarżonej czynności” ([05-zaznaczenie-w-pdf.png](demo/05-zaznaczenie-w-pdf.png)). W kratkach pojawia się 2026-03-20 ze znacznikiem „poprawione” i „cofnij” ([06-reczna-poprawka.png](demo/06-reczna-poprawka.png)).

**Mówimy:** „Model nie wpisał daty zaskarżonej czynności. Urzędnik nie przepisuje: zaznacza tekst w PDF-ie, a panel zamienia »20 marca 2026« na datę w formacie UZP. Każda ręczna zmiana jest oznaczona, można ją cofnąć, a licznik pokazuje, ile pól poprawiono. Wynik konkursowy liczy się z plików z przetwarzania, więc to narzędzie dla urzędnika, a nie sposób na F1.”

Wartość 2026-03-20 zgadza się z wzorcem UZP (`czynnosc_dzien` w `przyklad_01/odwolanie.json`). Z klawiatury: Alt+↓ w rubryce, strzałki wybierają wiersz, Enter wstawia.

### 2:10–2:30 · JSON i pobranie · *zgodność z formatem UZP*

**Klikamy:** „JSON” w przełączniku ([07-widok-json.png](demo/07-widok-json.png)). Potem plik 4, ogłoszenie BZP ([09-nie-rozpoznano.png](demo/09-nie-rozpoznano.png)). Na koniec „Pobierz wyniki (ZIP, 4 pliki)”.

**Mówimy:** „Każdy rozpoznany dokument dostaje JSON w formacie UZP. Dokument spoza klas dostaje plik z samym `{}`, tak jak ustaliło UZP. Wszystko schodzi jednym ZIP-em.”

Sprawdzone 21.11: `sprawa.zip` zawiera `sprawa/odwolanie.json`, `sprawa/pelnomocnictwo.json`, `sprawa/potwierdzenie_przelewu.json` i `sprawa/2025_BZP 00143067_01.json` z treścią `{}`.

### 2:30–2:40 · Kopia robocza (opcjonalnie, gdy mamy zapas) · *GUI*

**Klikamy:** odświeżamy stronę i wgrywamy te same cztery pliki. Panel pyta „Przywrócić poprawki?” ([14-przywroc-poprawki.png](demo/14-przywroc-poprawki.png)) → „Przywróć”. Wyniki i poprawka wracają bez ponownego wywołania modelu, a w „Przebieg” pojawia się „przywrócono z kopii”.

**Mówimy:** „Praca urzędnika nie ginie po zamknięciu karty. Kopia zostaje tylko w tej przeglądarce.”

### 2:40–3:15 · Nowy typ dokumentu · *Nowe typy (1–20 pkt)*

**Klikamy:** menu → „Typy dokumentów” ([11-typy-dokumentow.png](demo/11-typy-dokumentow.png)). Nad listą: „Lista z konfiguracji backendu (configs/documents)”. Potem „+ Dodaj typ dokumentu” → „Wypełnij przykładem” ([15-kreator-pola.png](demo/15-kreator-pola.png)) → przewijamy do „Pliki do pobrania” ([16-kreator-pliki.png](demo/16-kreator-pliki.png)).

**Mówimy:** „Lista typów pochodzi z backendu: tyle pól, ile ma schemat. Nowy typ to dwa pliki, YAML z opisem dla modelu i JSON Schema z polami. Kreator przygotowuje oba z formularza: nazwa, frazy rozpoznające, pola i wskazówki dla modelu. Nie trzeba zmieniać prompta systemowego ani kodu. Panel pokaże pola nowego typu automatycznie.”

Uczciwie, jeśli ktoś zapyta:

- Kreator **pobiera** pliki. Trzeba je skopiować do `configs/documents/` i `schemas/` i uruchomić API ponownie, bo konfiguracja wczytuje się przy starcie.
- Pliki z kreatora przechodzą `load_configs` backendu (sprawdzone w sesji kreatora). Pełnej ekstrakcji modelem na typie z kreatora na scenie nie pokazujemy.
- Przykładową czwartą klasę (`examples/fourth_class`) testowano z Sonnetem na jednym syntetycznym PDF-ie: zwrócił `numer: ABC-123` i `data: 2026-11-15`. To demonstracja rozszerzalności, a nie miara jakości.

### 3:15–3:45 · Jakość, model, co dalej (slajdy 6–7)

**Mówimy:** liczby z [`docs/MODEL_COMPARISON.md`](MODEL_COMPARISON.md), zawsze z dopiskiem „lokalnie, na syntetycznych danych UZP”. Do tego wynik z tej sprawy: pełnomocnictwo 10/10 pól zgodnych ze wzorcem, przelew 6/6, odwołanie 16/22. Na koniec: docelowy otwarty model w UE (**do potwierdzenia**) i pilotaż w urzędzie.

### Opcjonalnie (+30 s) · Skan · *F1 na skanach, transparentność*

Szczegóły i pomiary: [`docs/SKANY.md`](SKANY.md).

- Materiał: skan z `dane/skany/` repozytorium UZP (pełnomocnictwo albo przelew, bo OCR zajmuje 1–2 s; odwołanie to 10–17 s samego OCR). Na tych skanach w tekście po OCR jest 238 z 266 wartości pól (89,5%). Model w tym pomiarze nie brał udziału.
- Warunek: Tesseract z `pol` widoczny dla backendu (w `PATH`) albo Docker. Na komputerze, na którym robiono zrzuty, Tesseract nie jest w `PATH`, a lokalna kopia danych UZP nie ma katalogu `skany/`. Dlatego skanu nie przeszliśmy na prawdziwym API.
- Bez Tesseracta skan dostaje błąd `ocr_required` ([10-blad-ocr.png](demo/10-blad-ocr.png), zrzut z atrapy), a reszta sprawy przechodzi. Wtedy mówimy: „Skan bez warstwy tekstu dostaje jasny błąd, a reszta sprawy przechodzi. Błędne pliki można ponowić przyciskiem »Ponów błędne«.”

## Plan B: model albo internet nie działa

Panel ma tryb atrapy, który działa bez modelu i bez internetu. Odpowiedzi pochodzą wtedy z `frontend/mock/extract-response.json` i są dobierane po nazwie pliku.

1. Jeśli `start.bat` działa, otwieramy `http://127.0.0.1:8000/?mock=1`. W prawym górnym rogu pojawia się żółta etykieta „Dane przykładowe”. To samo daje przełącznik „Źródło wyników” w menu.
2. Jeśli nie wstaje nawet API, w terminalu z katalogu repozytorium:

   ```powershell
   python -m http.server 5500 -d frontend
   ```

   i w przeglądarce `http://localhost:5500/?mock=1`.
3. Wgrywamy pięć plików z `frontend/mock/pdf/`: `odwolanie.pdf`, `pelnomocnictwo.pdf`, `potwierdzenie_przelewu.pdf`, `ogloszenie_bzp.pdf`, `skan_pisma.pdf`. Dalej idziemy według scenariusza; na atrapie poprawiamy KRS zamiast daty, bo dane są inne.
4. **Mówimy otwarcie:** „Pokazujemy panel na danych przykładowych; wynik modelu jest na slajdzie 6.” Nie udajemy, że to wynik na żywo. Atrapa ma sztuczne opóźnienie 1,4 s, więc tej liczby nie podajemy jako szybkości.

Ostatnia deska ratunku, gdy nie działa nawet przeglądarka: zrzuty z `docs/demo/` w kolejności 01 → 09, 11, 15, 16 jako slajdy.

## Przed wejściem na scenę

**Dzień wcześniej**

- [ ] Wybrany model docelowy: otwarty, hostowany przez firmę z UE z polityką prywatności. **Do potwierdzenia.** Ustalić, czy na scenie gramy na nim, czy na modelu testowym z uczciwym komentarzem.
- [ ] Jedna pełna próba z zegarkiem na prawdziwym API: mieścimy się w 3:45.
- [ ] Liczby na slajdzie 6 zgadzają się z `docs/MODEL_COMPARISON.md` albo z nowym pomiarem na modelu docelowym.
- [ ] Jeśli pokazujemy skan: Tesseract + `pol` w `PATH`, skan UZP przetestowany na żywo.
- [ ] Folder z czterema plikami sprawy (`przyklad_01` + negatyw) skopiowany lokalnie, z czytelnymi nazwami.

**15 minut przed**

- [ ] `.venv` istnieje: `.venv\Scripts\python.exe` w katalogu repozytorium (inaczej `start.bat` kończy pracę z instrukcją instalacji).
- [ ] `.env` w katalogu repozytorium z `LLM_MODEL`, `LLM_BASE_URL`, `LLM_PROVIDER` i kluczem (`LLM_API_KEY` albo `API_KEY`). **Pliku nie otwieramy na projektorze.** Bez `LLM_MODEL` API działa w trybie regułowym.
- [ ] Port 8000 wolny. Jeśli zajęty: `set PORT=8080`, potem `start.bat`, i adres `http://127.0.0.1:8080/`.
- [ ] Przeglądarka: Chrome (sprawdzony, wersja 157) albo Edge (na komputerze testowym nie sprawdzony). Tryb gościa, bez rozszerzeń, powiększenie 100%, okno co najmniej 1366×768 (zrzuty mają 1440×900).
- [ ] Internet działa (API modelu). Jedna próbna sprawa przeszła w ostatnich 15 minutach, „Przebieg” pokazuje właściwy model.
- [ ] **Kopia robocza z próby:** jeśli w próbie były poprawki na tych samych plikach, panel zapyta „Przywrócić poprawki?”. Przed wejściem: „Nie, odrzuć” albo „Nowa sprawa” w menu, żeby pokaz zaczął się od pustej sprawy. Krok 2:30 korzysta z kopii zrobionej już na scenie.
- [ ] Karta z atrapą (`?mock=1`) otwarta w tle jako plan B.
- [ ] Laptop na zasilaniu, „nie przeszkadzać”, powiadomienia i synchronizacja wyłączone.
- [ ] Slajdy na drugim ekranie albo w drugiej karcie, przełączanie przećwiczone.
- [ ] Projektor: rozdzielczość, kontrast łososiowego tła, czytelność kratek.

## Zrzuty ekranu

Prawdziwe API z `start.bat`, model `claude-haiku-5-5`, 21.11.2026; Chrome 157 bez interfejsu, okno 1440×900, skala 1,5. Pliki: `przyklad_01` (3 PDF) + `negatywne/2025_BZP 00143067_01.pdf`.

| Plik | Moment |
| --- | --- |
| [01-start.png](demo/01-start.png) | Pusta sprawa, trzy kroki |
| [02-wgrane-pliki.png](demo/02-wgrane-pliki.png) | Cztery pliki na liście, podgląd odwołania |
| [03-przetwarzanie.png](demo/03-przetwarzanie.png) | „Przetwarzanie…” przy każdym pliku, przycisk „Anuluj” |
| [04-wynik-odwolanie.png](demo/04-wynik-odwolanie.png) | Rubryki odwołania obok PDF-u, wynik sprawy, „Przebieg: model: claude-haiku-5-5 · 15,9 s” |
| [05-zaznaczenie-w-pdf.png](demo/05-zaznaczenie-w-pdf.png) | Zaznaczone „20 marca 2026”, przycisk „Wstaw do: Dzień zaskarżonej czynności” |
| [06-reczna-poprawka.png](demo/06-reczna-poprawka.png) | 2026-03-20 w kratkach, „poprawione”, „cofnij”, licznik poprawek, uwaga o niepobranych poprawkach |
| [07-widok-json.png](demo/07-widok-json.png) | Widok JSON odwołania po poprawce |
| [08-przelew.png](demo/08-przelew.png) | Potwierdzenie przelewu: 6/6 pól, rachunki w kratkach |
| [09-nie-rozpoznano.png](demo/09-nie-rozpoznano.png) | Ogłoszenie BZP jako „Nie rozpoznano”, komunikat o pliku `{}` |
| [10-blad-ocr.png](demo/10-blad-ocr.png) | **Atrapa:** skan bez warstwy tekstu, błąd `ocr_required` |
| [11-typy-dokumentow.png](demo/11-typy-dokumentow.png) | „Typy dokumentów” z listą z backendu i przyciskiem „+ Dodaj typ dokumentu” |
| [14-przywroc-poprawki.png](demo/14-przywroc-poprawki.png) | Po odświeżeniu: „Przywrócić poprawki?” |
| [15-kreator-pola.png](demo/15-kreator-pola.png) | Kreator, krok 3–4: pola danych i wskazówki dla modelu (przykład „Potwierdzenie odbioru”) |
| [16-kreator-pliki.png](demo/16-kreator-pliki.png) | Kreator, krok 5: gotowy YAML i JSON Schema |

Numery 12 i 13 to obrazy skanów z [`docs/SKANY.md`](SKANY.md).

Co widać na zrzutach z modelu i jak to czytać:

- Zgodność z wzorcem UZP w tej próbie (liczona po polach, `null` we wzorcu i w wyniku liczy się jako zgodne): pełnomocnictwo 10/10, przelew 6/6, odwołanie 16/22. To ta sama zgodność co we wcześniejszym teście zespołu.
- Odwołanie, pola niezgodne: `czynnosc_dzien`, `czynnosc_powod_id`, `czynnosc_opis` (puste), `pelnomocnik.nazwa` i `pelnomocnik.mail` (puste) oraz `pelnomocnik.imie_nazwisko`, gdzie model wpisał dwie osoby zamiast pierwszej. **Pola 11 nie pokazujemy jako sukcesu.**
- Po ręcznej poprawce daty odwołanie ma w panelu 17/22 zgodnych, ale to nie zmienia F1, które UZP liczy z plików `output/`.
- Wynik modelu może się różnić między przebiegami.
