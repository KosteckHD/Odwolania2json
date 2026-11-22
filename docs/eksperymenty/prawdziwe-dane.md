# Test na prawdziwych dokumentach z internetu

Dane UZP są syntetyczne, więc sprawdziliśmy KIOdczyt na publicznych dokumentach, których nie widział przy poprawkach.
Wzorce (ground truth) wypełnione ręcznie z tekstu PDF, bez użycia KIOdczyt. Miara jak u UZP (`evaluation/evaluate.py`).
Model: Qwen3.5 9B (HostYourAI, UE), ta sama konfiguracja co na serwerze oceny.

## Krok 1: prawdziwe odwołania (znane typy, nowe pliki)

16 odwołań do KIO z lat 2020–2024 opublikowanych przez zamawiających (różne kancelarie i układy, długie
uzasadnienia, jeden skan) + 1 plik, który okazał się stroną HTML z rozszerzeniem `.pdf`.

| | F1 | TP / FP / FN |
|---|---|---|
| wszystkie pola | **0,9125** | 219 / 16 / 26 |
| bez pola `prowadzacy_postepowanie`* | **0,944** | 219 / 16 / 10 |

\* Przy kilku zamawiających wzorzec ma 0, a model zostawia `null` (tak jak w 57 z 63 wzorców UZP) — różnica konwencji, nie odczytu.

- **Klasyfikacja 16/16** (wszystkie jako odwołanie), plik HTML nie wywraca przebiegu.
- Bezbłędne lub prawie: strony (nazwy, NIP, REGON, KRS, adresy), tytuł zamówienia, numer TED, kwoty.
- Błędy: data zaskarżonej czynności przy długich pismach (4× brak), powód odwołania tam, gdzie nawet etykietujący
  wahał się między „SWZ” a „OPZ” (3), stary format numeru BZP (`594737-N-2020`) zamieniany na nowy (3),
  pełnomocnik będący pracownikiem firmy (1 dokument), pisownia jednego nazwiska bez polskich znaków (1).

### Poprawki po teście (gałąź `fix/prawdziwe-dane`)

Ogólne reguły w `postprocess:` (YAML), bez dopasowania do konkretnych plików:
- pisownia nazwiska z dokumentu nie bierze słów z adresów e-mail (wcześniej „anna szymanska” z `anna.szymanska@…`),
- `require_in_text`: numer BZP musi stać w piśmie (model przerabiał stary numer `594737-N-2020` na `2020/BZP00594737`),
- `null_if_text_matches` i normalizacja TED: stary krajowy numer `NNNNNN-N-RRRR` to nie numer TED,
- `default_when_multiple`: przy kilku zamawiających brak wskazania prowadzącego = 0 (konwencja wzorców UZP: 1 i 0).

| | F1 przed | F1 po |
|---|---|---|
| prawdziwe odwołania (16) | 0,9125 | **0,951** |
| walidacja UZP (43) | 1,0000 | 1,0000 |
| test UZP (18) | 1,0000 | 1,0000 |
| roboczy UZP (135) | 1,0000 | 1,0000 |
| inny układ (30) | 1,0000 | 1,0000 |

Zostaje (bez poprawek, bo to ocena treści, a nie formatu): data i rodzaj zaskarżonej czynności przy długich pismach
(SWZ / OPZ / zmiana SWZ — tu wahał się też etykietujący) oraz pełnomocnik będący pracownikiem firmy.
Uwaga: 16 odwołań posłużyło teraz do szukania błędów, więc 0,951 to wynik na zbiorze roboczym, nie niezależny test.

## Krok 2: nowy typ dokumentu dodany bez zmiany kodu

Typ `orzeczenie_kio` (wyrok / postanowienie KIO: sygnatura, rodzaj, data, przewodniczący, odwołujący, zamawiający,
rozstrzygnięcie) — dwa pliki: YAML + schemat JSON. 40 orzeczeń KIO z 2026 r. z bazy UZP.

| Wersja konfiguracji | F1 (UZP, nazwy od 80%) | F1 ścisły | Błędy |
|---|---|---|---|
| pierwsza | 0,9892 | 0,9071 | 6 nazw (konsorcja z adresami, skrócone nazwy działalności) |
| po dopisaniu 3 zdań wskazówek w YAML | **1,0000** | 0,9536 | 0 |

Sygnatura, rodzaj, data, przewodniczący i rozstrzygnięcie: 40/40 od pierwszej wersji.

**Regresja:** walidacja UZP z czterema typami = 0,9919 (wcześniej 1,0000) — postanowienie KIO, które w danych UZP jest
dokumentem spoza klas (`{}`), zostało rozpoznane jako nowy typ. Dlatego `orzeczenie_kio` nie jest częścią wersji
wdrożonej do oceny; to pokaz rozszerzalności. Dodanie typu zmienia zakres „dokumentów spoza klas”.

## Jak powtórzyć

Typy z innego katalogu: `main.py --configs <katalog> --schemas <katalog>`; ewaluator bierze listę typów ze schematów
(`evaluate.py --schemas`, `experiment.py --schemas`).
