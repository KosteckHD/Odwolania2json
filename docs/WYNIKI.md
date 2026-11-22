# Wyniki testów jakości

Wersja: gałąź `main` (wdrażana na serwer oceny). Model: **Qwen3.5 9B** (open source, Apache 2.0)
przez HostYourAI B.V. (przetwarzanie w UE), bez trybu „myślenia”, temperatura 0.

## Jak liczymy

- **Miara jak u UZP:** F1 pól. Wartość zgodna = TP, błędna = FP, brak wartości przy wypełnionym wzorcu = FN,
  wartość tam, gdzie wzorzec ma `null` = FP. Długie teksty (nazwy stron, nazwa kancelarii pełnomocnika,
  tytuł zamówienia i przelewu) zgodne od 80% podobieństwa; listy porównywane po treści; rachunek bez względu
  na przedrostek „PL” (błąd części wzorców treningowych potwierdzony przez UZP). Ewaluator: `evaluation/evaluate.py`.
- **Podział danych UZP** (`evaluation/manifest.json`): sprawy 01–42 = zbiór roboczy (na nim szukaliśmy błędów),
  43–54 = walidacja (decyzja, czy zmiana zostaje), 55–60 = test (sprawdzian na koniec, nieużywany przy poprawkach).
  Negatywy (dokumenty spoza trzech klas) są w zbiorze roboczym i walidacyjnym.
- **„Inny układ”:** dane UZP pochodzą z jednego generatora, a w realnych sprawach układ pism jest różny.
  Skrypt `evaluation/layout_variants.py` przepisuje 15 odwołań z tymi samymi danymi w 7 innych układach
  (inne etykiety, kolejność sekcji, kancelaria w stopce lub przy podpisie, data przy podpisie, inne sformułowanie
  zaskarżonej czynności, konsorcjum z liderem opisanym inaczej) — razem 30 dokumentów.

## Wynik końcowy

| Zbiór | Dokumenty | F1 | TP / FP / FN | Odwołanie | Pełnomocnictwo | Przelew | Negatywy |
|---|---|---|---|---|---|---|---|
| **test UZP** | 18 | **1,0000** | 206 / 0 / 0 | 1,000 | 1,000 | 1,000 | — |
| **walidacja UZP** | 43 | **1,0000** | 426 / 0 / 0 | 1,000 | 1,000 | 1,000 | 7/7 `{}` |
| roboczy UZP | 135 | 1,0000 | 1400 / 0 / 0 | 1,000 | 1,000 | 1,000 | 9/9 `{}` |
| **inny układ** | 30 odwołań | **1,0000** | 606 / 0 / 0 | 1,000 | — | — | — |
| skany UZP (`dane/skany`) | 30 | ok. 0,97 | — | — | — | — | — |
| **prawdziwe odwołania** z internetu | 16 | **0,951** | 234 / 13 / 11 | 0,951 | — | — | — |

Klasyfikacja (odwołanie / pełnomocnictwo / przelew / spoza klas) bezbłędna na wszystkich zbiorach.
Skany czyta ten sam model z obrazu strony (`SCAN_MODE=image`: F1 0,9718; przepisywanie tekstu: 0,9643);
bez tego skany dawały 0 pól, bo zwykły OCR wymagał programu `tesseract`.

## Prawdziwe dokumenty

Dane UZP są syntetyczne, więc sprawdziliśmy też publiczne dokumenty z internetu (wzorce wypełnione ręcznie):
- **16 prawdziwych odwołań do KIO** (2020–2024, różne kancelarie, jeden skan): klasyfikacja 16/16, **F1 0,951**
  (przed poprawkami 0,9125; poprawki nie zmieniły wyników na danych UZP). Słabsze miejsca: data i rodzaj zaskarżonej
  czynności w długich pismach.
- **Nowy typ dokumentu bez zmiany kodu:** `orzeczenie_kio` (dwa pliki: YAML + schemat) na 40 orzeczeniach KIO z 2026 r.:
  **F1 1,0000** po dopisaniu trzech zdań wskazówek (pierwsza wersja 0,989). Typ nie jest częścią wersji do oceny,
  bo w danych UZP postanowienia KIO są dokumentami spoza klas.

Szczegóły: [eksperymenty/prawdziwe-dane.md](eksperymenty/prawdziwe-dane.md).

## Jak do tego doszliśmy (walidacja UZP)

| Etap | F1 walidacja | Odwołanie | Co się zmieniło |
|---|---|---|---|
| punkt wyjścia | 0,9680 | 0,946 | jeden prompt, wszystkie schematy w jednym zapytaniu |
| runda 1 | 0,9976 | 0,996 | definicje pól pełnomocnika i czynności w prompcie; reguły po modelu tylko dla pustych pól (`postprocess:` w YAML); skany przez model; plik wyniku dla każdego PDF-u (wynik awaryjny z reguł) |
| **runda 2** | **1,0000** | **1,000** | prompt opisuje rolę pola zamiast konkretnej etykiety, konsorcjum = jeden odwołujący (lider); reguła powodu odwołania z tekstu zaskarżonej czynności |

Na danych, których nie używaliśmy przy poprawkach: **test UZP 0,9951 → 1,0000**, **inny układ 0,9743 → 1,0000**.

## Metoda pracy

Rundy po 5 równoległych agentów; każdy z inną rodziną zmian (prompt, wejście i podział zadania, warstwa po modelu,
ustawienia wywołania, skany i odporność), z własnym dziennikiem prób i wspólną tabelą wyników. Zmiana zostawała
tylko, gdy F1 rósł ponad szum na zbiorze roboczym **i** nie spadał na walidacji (żaden typ dokumentu). Odrzucone
m.in.: tryb „myślenia” (gorsze daty i powody, kilkadziesiąt razy wolniej), głosowanie z 3 odpowiedzi (zamienia
braki na błędy), dwa kroki klasyfikacja → ekstrakcja (niższe F1), drzewo decyzji powodu bez reguły konsorcjum
(spadek na walidacji). Dzienniki prób: [eksperymenty/](eksperymenty/).

## Czas i koszt

- Ok. 7 s na dokument (jedno zapytanie; odwołanie ok. 15 tys. tokenów wejścia). 150 PDF ok. 17–18 min jedno po drugim,
  szybciej przy `LLM_CONCURRENCY=3` z `.env.example` — przy limicie UZP 45 min.
- Chwilowe błędy dostawcy (429, 504) są ponawiane; po wyczerpaniu ponowień plik dostaje wynik z reguł YAML,
  więc każdy PDF ma plik wyniku.
- Punktacja za model: Qwen3.5 9B (9–9,7B parametrów z enkoderem obrazu) = przedział >8–14B, jeden model.

## Ograniczenia

- Dane UZP są syntetyczne i z jednego generatora; 1,0000 na nich nie oznacza braku błędów na realnych pismach
  (na 16 prawdziwych odwołaniach: 0,951).
  Zestaw „inny układ” sprawdza odporność na etykiety i kolejność, ale ma czysty tekst i krótkie uzasadnienia.
- Model jest dostępny przez API (wymóg UZP), więc wynik zależy też od dostępności dostawcy; stąd ponowienia i wynik awaryjny.
- Reguła powodu odwołania nadpisuje model tylko przy zgodnych fragmentach tekstu; przy innym sformułowaniu zostaje odpowiedź modelu.
