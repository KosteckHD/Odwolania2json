# Skany: jak backend je czyta i ile z nich odczytuje

Stan kodu: `ed2d2bd` („first backend version”). Pomiar z 21.11.2026.

## Ścieżka skanu w backendzie

Model nie dostaje obrazu strony. Gdy strona PDF nie ma warstwy tekstu (mniej niż 12 znaków alfanumerycznych), `pdf_reader.extract_pdf` wywołuje `ocr.tesseract_ocr`: pypdfium2 renderuje stronę w skali 2, Tesseract czyta ją z językiem `pol`, a do modelu trafia sam tekst (`providers/chat.py`, `providers/anthropic.py`: `"content": text`). Jakość ekstrakcji ze skanu zależy więc najpierw od Tesseracta.

**Ryzyko na etap 1:** Tesseract to program spoza `pip`. Instaluje go tylko obraz Dockera (`tesseract-ocr tesseract-ocr-pol` w `Dockerfile`). Uruchomienie „Python 3.13 + `requirements.txt`” bez Tesseracta w `PATH` kończy każdy skan błędem `ocr_required` i plik nie dostaje wyniku. UZP opublikowało 21.11 katalog `dane/skany/` (30 skanów bez warstwy tekstu), więc ukryty zbiór testowy prawdopodobnie też zawiera skany. Instrukcja dla jury musi to rozstrzygnąć: Docker albo instalacja Tesseracta z `pol`.

## Zestawy testowe

1. **Skany UZP** (`dane/skany/` z repozytorium UZP, commit `eb1ab44`): 10 odwołań (4–7 stron), 10 pełnomocnictw, 10 potwierdzeń przelewu, każdy ze wzorcowym JSON-em. Wyglądają jak skaner biurowy: lekki przekos, kropki, ciemny brzeg, ślady zagięcia.
2. **Brudne skany** z [`evaluation/dirty_scans.py`](../../evaluation/dirty_scans.py), zrobione z 9 PDF-ów ze spraw UZP 01–03 (część rozwojowa; sprawy 55–60 zostają nietknięte). Cztery poziomy:

| Poziom | Rozdzielczość | Obrót | Pozostałe zniekształcenia |
| --- | ---: | ---: | --- |
| lekki | 200 dpi | do 0,5° | papier, podpis, lekki szum, JPEG 80 |
| średni | 150 dpi | do 1,5° | + pieczątka na tekście, zagięcie, nierówne światło, rozmycie, JPEG 45 |
| mocny | 120 dpi | do 3° | jak średni, mocniej: cień, rozmycie, szum, JPEG 25 |
| faks | 100 dpi | do 0,8° | czarno-biały próg, kropki, smugi z podajnika |

Podgląd: [skan UZP](demo/13-skan-uzp-odwolanie.jpg) i [brudny skan, poziom średni](demo/12-brudny-skan-sredni.jpg). Skany UZP wyglądają mniej więcej jak poziom „średni”. „Mocny” i „faks” są od nich trudniejsze i pokazują zapas.

Sztucznie zabrudzony PDF nie zastępuje wydrukowanej i zeskanowanej kartki. Pozwala za to zobaczyć, przy jakim poziomie zniekształceń odczyt zaczyna się psuć, i powtarzać pomiar po każdej zmianie.

## Metoda

[`evaluation/ocr_quality.py`](../../evaluation/ocr_quality.py) przepuszcza każdy skan przez `extract_pdf` z `tesseract_ocr`, czyli dokładnie przez kod backendu, i sprawdza, czy wartości pól ze wzorcowego JSON-a dają się znaleźć w tekście po OCR. Wartości porównujemy bez spacji, interpunkcji i wielkości liter; daty także jako DD.MM.RRRR i „D miesiąca RRRR”. Pola słownikowe i 0/1 pomijamy. Model językowy nie bierze udziału, więc to **nie jest F1 ekstrakcji**, tylko górna granica tego, co model może przeczytać. Część błędów OCR model może poprawić sam, np. oczywiste „@” w adresie e-mail.

Przy brudnych skanach mianownikiem są wartości, które da się znaleźć w warstwie tekstu oryginału; CER i WER liczymy względem tej warstwy. Skany UZP nie mają oryginału z tekstem, więc tam mianownikiem są wszystkie wartości wzorca (co najmniej 4 znaki po normalizacji). Część z nich może nie występować w treści dosłownie, więc ten wynik jest zaniżony.

## Wyniki

Tesseract 5.4.0, `pol` z tessdata_fast, Windows, 4 dokumenty równolegle. Jeden przebieg.

| Zestaw | PDF / strony | Strony nieodczytane | Odczyt pól | CER | Czas OCR na stronę |
| --- | --- | ---: | ---: | ---: | ---: |
| Skany UZP | 30 / 72 | 0 | 238 / 266 (89,5%) | – | 2,1 s |
| Brudne: lekki | 9 / 12 | 0 | 81 / 85 (95,3%) | 0,156 | 2,1 s |
| Brudne: średni | 9 / 12 | 1 | 74 / 85 (87,1%) | 0,218 | 2,1 s |
| Brudne: mocny | 9 / 12 | 7 | 8 / 85 (9,4%) | 0,967 | 1,2 s |
| Brudne: faks | 9 / 12 | 0 | 64 / 85 (75,3%) | 0,237 | 1,5 s |

Raporty szczegółowe z listą nieodczytanych wartości powstają w `.local/ocr-raporty/` (poza repozytorium).

Co z tego wynika:

- **Skany UZP czyta się dobrze.** Wszystkie strony mają tekst. Brakujące wartości to głównie nazwy z „Sp. z o.o.” (Tesseract czyta `0.0.`) i adresy e-mail (`@` jako `G`, `Q` albo `©`). To błędy, które model może poprawić sam, więc wynik ekstrakcji może być wyższy niż odczyt pól. Nie sprawdzaliśmy tego, bo pomiar nie wywołuje modelu.
- **Czas:** samo OCR odwołania (4–7 stron) to 10–17 s, pełnomocnictwa i przelewu 1–2 s, bez czasu modelu.
- **Poziom „mocny” to zero-jedynkowa porażka, a nie stopniowe pogorszenie.** Strona czytelna dla człowieka (szare tło, cień) wychodzi z Tesseracta pusta. Na jednej takiej stronie (przelew ze sprawy 01) domyślny próg dał 0 linii z tekstem, a `-c thresholding_method=2` (próg lokalny Sauvoli z Tesseracta 5) odczytał nagłówek, tytuł i numer transakcji. Sprawdzone na jednej stronie, nie na całym zbiorze.

## Do przekazania backendowi

To nie jest zadanie frontu; zapisane, żeby nie zginęło.

1. Na komputerze jury musi być Tesseract z `pol` (Docker albo instrukcja instalacji). Bez niego każdy skan dostaje `ocr_required`.
2. Do rozważenia: `thresholding_method=2` w wywołaniu Tesseracta (`ocr.py`) dla skanów z szarym tłem. Wymaga pomiaru na skanach UZP, żeby nie pogorszyć dobrych przypadków.

## Co to znaczy dla panelu

- Skan nie ma warstwy tekstu w podglądzie PDF, więc **wstawianie zaznaczenia z PDF-u nie działa na skanach**: urzędnik wpisuje wartość ręcznie. Panel mówi to wprost nad podglądem („Ta strona to skan bez warstwy tekstu: wartości trzeba wpisać ręcznie”).
- Odwołanie ze skanu przetwarza się dłużej (samo OCR 10–17 s), a komunikat panelu po 8 s („To trwa dłużej niż zwykle…”) pojawi się przy każdym zeskanowanym odwołaniu.
- Bez Tesseracta skan wraca jako błąd `ocr_required` i panel pokazuje go przy pliku, a reszta sprawy przechodzi ([zrzut 10](demo/10-blad-ocr.png)).

## Powtórzenie pomiaru

Potrzebny jest Tesseract z językiem `pol` (Windows: `winget install UB-Mannheim.TesseractOCR`, potem `pol.traineddata` z [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast), ten sam wariant co pakiet Debiana w obrazie Dockera). Dane UZP pobieramy do `.local/` (katalog jest w `.gitignore`).

```powershell
.venv/Scripts/python.exe evaluation/dirty_scans.py --input .local/uzp-dane --output .local/brudne-skany
.venv/Scripts/python.exe evaluation/ocr_quality.py --scans .local/brudne-skany/sredni --reference .local/uzp-dane --label sredni --tessdata .local/tessdata --output .local/ocr-raporty/sredni.json
.venv/Scripts/python.exe evaluation/ocr_quality.py --scans .local/uzp-skany --label skany-uzp --tessdata .local/tessdata --output .local/ocr-raporty/skany-uzp.json
```

`--tesseract-dir "C:/Program Files/Tesseract-OCR"` podaje katalog programu, gdy nie ma go w `PATH`.
