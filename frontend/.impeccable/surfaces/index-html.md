---
version: 1
slug: "index-html"
primary_target: "index.html"
related_targets: []
---

# Panel ekstrakcji (frontend/index.html)

Tryb: Operate. Użytkownik: urzędnik UZP przyjmujący sprawę KIO. Zadanie: wgrać PDF-y jednej sprawy, sprawdzić status i dane każdego pliku, pobrać JSON. Drugi odbiorca: jury demo.

Wymóg użytkownika: czytelność i zrozumiałość przed efektem; kto widzi panel pierwszy raz, ma wiedzieć, co zrobić. Zwijany pasek nawigacji. Font maszynowy z szkicu odrzucony.

## Direction contract

THESIS: Panel jest drukiem urzędowym, który system wypełnia za urzędnika. Odrzuca typowy panel SaaS z białymi kartami i ciemnym blokiem JSON.

OWN-WORLD: Łososiowy papier druku (#FBE7DF) i biały arkusz roboczy; rubryki, kratki i etykiety w kolorze druku (czerwień #B3341A na jasnym, ciemniejsza do tekstu); wpisane dane w czerni. Płaskie kolory, cienkie linie rubryk, bez cieni i zaokrągleń. Jeden czytelny krój (Atkinson Hyperlegible Next) z cyframi tabelarycznymi.

STORY: Urzędnik widzi trzy kroki (wgraj, przetwórz, sprawdź i pobierz), wrzuca pliki, widzi los każdego PDF-u, czyta dane w polach z polskimi etykietami i pobiera JSON.

FIRST VIEWPORT: Zwijany czerwony pasek nawigacji po lewej; obok kolumna „Dokumenty sprawy” (strefa wgrywania, przycisk, numerowana lista plików ze statusem); po prawej biały arkusz wybranego dokumentu z numerowanymi rubrykami i identyfikatorami w kratkach; przycisk „Pobierz” w nagłówku arkusza.

FORM: Druk urzędowy, pozycja 4 na liście; seed:5b9ac624a1ec175a. Ruch sygnaturowy: identyfikatory (NIP, KRS, REGON, PESEL, daty, numery) wpisane w kratki znak po znaku jak w blankiecie przelewu.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
