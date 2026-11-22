# Ed3 (runda 2): reguły powodu czynności w warstwie po modelu

Baza: `b667a09` (scalona runda 1). Gałąź: `feat/f1-r2-Ed3`.

## Pomysł
`czynnosc_powod_id` to jedyne pole, na którym runda 1 jeszcze traciła punkty. Odwołanie zwykle nazywa
zaskarżoną czynność w kilku stałych miejscach; deterministyczna reguła może je odczytać i poprawić model,
ale tylko gdy jest niemal pewna.

Mechanizm ogólny, w YAML: `postprocess.classify_by_patterns` (`src/kio_extract/postprocess.py`):
- `segments`: wzorce z grupą `segment`; każdy daje najwyżej jeden fragment (pierwsze trafienie),
- `classes`: lista `{value, patterns}`; kolejność = pierwszeństwo, trafienie wycina dopasowany tekst
  (np. „zaniechanie odrzucenia” zabiera „odrzucenia”, więc nie liczy się jako „odrzucenie oferty”),
- fragment głosuje tylko przy dokładnie jednej klasie; wartość ustalana tylko, gdy wszystkie głosy są
  zgodne i jest ich co najmniej `min_votes`; `mode: override` (popraw model) albo `fill` (tylko null),
- działa przed `derive`, więc `czynnosc_opis` idzie za poprawionym identyfikatorem.

Fragmenty dla odwołania: zdanie „Zamawiający w dniu <data> …” (do końca zdania), pierwszy punkt
„polegających na: 1) …”, „Zarzut nr 1 – …” (do „tj.”/„:”/„;”), „zarzucam Zamawiającemu: 1) …”.
Klasy: 12 kategorii słownika, wzorce na rdzenie słów (bez wartości z danych).

## Pomiar offline
Teksty PDF z `dane/`, wzorzec odpowiedzi z plików `.json`; reguły stroiłem tylko na development
i walidacji, test (13 odwołań) sprawdziłem raz na końcu jako niezależną kontrolę trafności reguły.

Trafność samej reguły (gdy rozstrzyga):

| podział | rozstrzyga | dobrze | źle |
|---|---|---|---|
| development (35) | 35 | 35 | 0 |
| walidacja (12) | 12 | 12 | 0 |
| test (13, bez strojenia) | 13 | 13 | 0 |

Pierwsza wersja miała 2 błędy na development („zmodyfikował treść SWZ” → 4 zamiast 5: wzorzec znał
tylko „treści”); poprawione przez `treś(?:ć|ci)`.

Na zapisanych odpowiedziach modelu z rundy 1: development 35/35 → 35/35 (bez zmian),
walidacja 11/12 → 12/12 (`przyklad_47`: model 2 „wybór oferty”, reguła 8 „zaniechanie wykluczenia”,
trzy zgodne fragmenty).

Na wszystkich 30 zarchiwizowanych przebiegach (runda 1 i wcześniejsze, różne prompty i ustawienia,
tylko development+walidacja): model mylił powód 48 razy.

| min_votes | naprawione | zepsute |
|---|---|---|
| 1 | 48 | 0 |
| 2 | 3 | 0 |

Typowe błędy modelu na development to „11 (OPZ)” zamiast 8/4/1/9 w dokumentach, w których jedynym
fragmentem jest zdanie „Zamawiający w dniu …”; wymaganie dwóch fragmentów ich nie łapie. Dlatego
`min_votes: 1`, ale przy kilku fragmentach muszą być zgodne (sprzeczność = zostaje model).

## Pełne przebiegi (Qwen3.5 9B, HostYourAI, bez myślenia, tempo jak w rundzie 1)

| przebieg | podział | F1 | TP | FP | FN | odwolanie | pelnomocnictwo | przelew | błędy API |
|---|---|---|---|---|---|---|---|---|---|
| r1-merged-dev (baza) | development | 1,0000 | 1400 | 0 | 0 | 1,000 | 1,000 | 1,000 | 0 |
| r2-Ed3-powod-regula | development | 1,0000 | 1400 | 0 | 0 | 1,000 | 1,000 | 1,000 | 0 |
| r1-merged-val (baza) | walidacja | 0,9976 | 424 | 2 | 0 | 0,996 | 1,000 | 1,000 | 0 |
| r2-Ed3-powod-regula-val | walidacja | **1,0000** | 426 | 0 | 0 | **1,000** | 1,000 | 1,000 | 0 |

Warunek spełniony: odwołania rosną (walidacja 0,996 → 1,000), pełnomocnictwa, przelewy i negatywy bez
zmian; development bez regresji. Zużyte 2 z 4 pełnych przebiegów.

## Ryzyka i uwagi
- Przy `min_votes: 1` dokument z jednym rozpoznanym fragmentem (samo zdanie „Zamawiający w dniu …”)
  nadpisuje model. Offline to 0 szkód na 30 przebiegach i 13/13 na teście, ale u jury zdanie
  „Zamawiający w dniu …” może opisywać wcześniejsze zdarzenie (np. publikację SWZ). Ostrożniejsza
  opcja: `min_votes: 2` (naprawia tylko układ „polegających na: 1) …” + „Zarzut nr 1 – …”).
- Wzorce klas są na rdzenie słów; nowe sformułowania bez trafienia = brak głosu = zostaje model.
