---
name: Odwołania2JSON · Druk urzędowy
description: Panel ekstrakcji jako druk urzędowy wypełniany przez system. Formularz w kolorze druku, dane w czerni.
colors:
  paper: "#FAF1EC"
  paper-deep: "#F3E2D9"
  sheet: "#FFFFFF"
  form: "#9A3218"
  form-soft: "#A65741"
  rule: "#E6B4A3"
  rule-soft: "#F2D9CF"
  rule-field: "#C77C64"
  brand: "#8C2A15"
  brand-hover: "#74220F"
  ink: "#1B1C20"
  ink-soft: "#55504D"
  ok: "#1D6B42"
  ok-bg: "#E4F2E9"
  warn: "#775000"
  warn-bg: "#FBEFD2"
  bad: "#A11D1D"
  bad-bg: "#FBE6E4"
typography:
  caption:
    fontFamily: Public Sans
    fontSize: 12px
    fontWeight: 500
  small:
    fontFamily: Public Sans
    fontSize: 13px
    fontWeight: 400
  label:
    fontFamily: Public Sans
    fontSize: 13.5px
    fontWeight: 400
  ui:
    fontFamily: Public Sans
    fontSize: 14px
    fontWeight: 500
  body:
    fontFamily: Public Sans
    fontSize: 15px
    fontWeight: 400
  value:
    fontFamily: Public Sans
    fontSize: 15.5px
    fontWeight: 500
  lead:
    fontFamily: Public Sans
    fontSize: 16px
    fontWeight: 400
  title:
    fontFamily: Public Sans
    fontSize: 17px
    fontWeight: 600
  heading:
    fontFamily: Public Sans
    fontSize: 18px
    fontWeight: 600
  display:
    fontFamily: Public Sans
    fontSize: 22px
    fontWeight: 600
rounded:
  none: 0px
spacing:
  cell: 22px
  row: 34px
---

# Druk urzędowy

## Zasada

Wszystko, co jest formularzem (rubryki, kratki, etykiety, numery pól), ma kolor druku: `form` i `rule` na białym arkuszu albo łososiowym papierze. Wszystko, co system wyciągnął z dokumentu, jest wpisane czernią (`ink`). Użytkownik od razu widzi, co jest szablonem, a co danymi.

## Kolor

Papier (`paper`) to tło aplikacji, biały arkusz (`sheet`) to obszar dokumentu. Czerwień `brand` niesie pasek nawigacji i główne przyciski (biel na niej ma 8,2:1). Statusy: zielony `ok` dla rozpoznanych, bursztyn `warn` dla nierozpoznanych, czerwień `bad` dla błędów. Płaskie kolory i linie 1 px, bez cieni, gradientów i zaokrągleń (także szuflada menu, strona PDF i przycisk „Wstaw”: zamiast cienia linia 1 px). Obramowania rubryk, kratek i pól kreatora mają `rule-field` (3,2:1 na bieli). Paski przewijania są cienkie, w kolorze `rule-field`. Podpowiedzi i informacje (np. kod błędu) są w `ink-soft`; czerwień druku zostaje dla etykiet formularza, czerwień `bad` dla błędów. Czerwień tylko tam, gdzie niesie znaczenie: menu, główna akcja, etykiety formularza.

## Typografia

Jeden krój: Public Sans (OFL, w `fonts/`), neutralny krój zaprojektowany dla serwisów administracji publicznej. Wagi 400–600 (także znak „O2J”), nagłówki 600, bez wersalików, łamane `text-wrap: balance`. Skala rozmiarów jest w nagłówku pliku; nowych rozmiarów spoza niej nie dodajemy. Cyfry tabelaryczne w całej aplikacji. JSON w systemowym kroju monospace.

## Kratki

Identyfikatory (NIP, KRS, REGON, PESEL), daty i numery rachunków są wpisane w kratki po jednym znaku, jak w blankiecie przelewu. Daty mają przerwy RRRR MM DD, rachunki NRB 2 + grupy po 4. Pole bez danych ma kratki zakreskowane i dopisek „brak w dokumencie”; pusta zwykła rubryka jest zakreskowana tak samo. Pola tak/nie to kwadraty z „X”. Czytnik ekranu dostaje pełną wartość jako tekst.

## Układ

Dwa ekrany sprawy. Menu wysuwane z boku jest na każdym ekranie bez zmian (☰ w górnym pasku: nowa sprawa, instrukcja, typy dokumentów z kreatorem, źródło wyników API albo dane przykładowe; zamykanie kliknięciem obok, wyborem albo Esc).

**Ekran 1 (wgrywanie i przetwarzanie).** Jedna kolumna na środku (do 640 px): krótki nagłówek „Dokumenty sprawy”, pole przeciągania z „Wybierz pliki” i „Wybierz folder” w zwykłej skali tekstu, lista dodanych plików (nr, nazwa, rozmiar, ×), przycisk „Przetwórz N plików”. W trakcie: „Przetwarzanie…”, „Anuluj” i status przy każdym pliku. Kroki 1–2–3 w górnym pasku są tylko tutaj. Pytanie „Przywrócić poprawki?” pojawia się nad listą.

**Ekran 2 (wynik).** Górny pasek: ☰, znak O2J, „Sprawa: …”, dyskretny znacznik „Dane przykładowe” w trybie atrapy i po prawej jedyny przycisk pobierania „Pobierz ▾”. Główny klik pobiera ZIP sprawy, rozwinięcie daje „ZIP całej sprawy” i „JSON tego dokumentu” oraz informację o niepobranych poprawkach. Drugi pasek: „Dokumenty 5 · 1 błąd ▾” (informacja o błędach i nierozpoznanych widoczna także przy zamkniętym panelu), pośrodku „‹ nazwa.pdf · 1 z 5 ›”, po prawej „16/22 pól · N poprawek” i „⋯ Opcje dokumentu” (przetwórz ten plik ponownie, ukryj/pokaż PDF). Panele otwierają się pod swoim przyciskiem, nie z boku; Esc i kliknięcie obok zamykają je, fokus wraca do przycisku. Panel „Dokumenty” ma listę plików ze statusami, „Ponów błędne”, „Przetwórz ponownie”, podsumowanie typów i dodawanie plików lub folderu (nowe pliki zaczynają nową sprawę). Pod paskami dwie kolumny: formularz | PDF, z przeciąganym podziałem i niezależnym przewijaniem. Nagłówek kolumny formularza (typ dokumentu i „Formularz / JSON”) zostaje widoczny przy przewijaniu. Strony, zoom i ⤢ są w pasku podglądu.

Rubryki układają się w dwie kolumny od ok. 480 px szerokości kolumny formularza, w trzy na szerokich ekranach. Poniżej 1180 px strona przewija się zwyczajnie, a PDF schodzi pod formularz; drugi pasek przykleja się do góry. Na telefonie drugi pasek ma dwa wiersze („Dokumenty ▾” i ⋯, potem ‹ nazwa › i wypełnienie), a „Pobierz ▾” zostaje przy prawej krawędzi. W oknach niższych niż 820 px oba paski są niższe.

## Statusy i dopiski

Status pliku to zawsze tekst z małą ikoną (✓ rozpoznany, ? nie rozpoznano, ! błąd, kółko w trakcie), bez kolorowego tła; kolor ma tylko ikona. Dopiski przy etykiecie rubryki są drobne i szare: „poprawione · cofnij”, „brak w dokumencie”, „str. N · metoda” (gdy API zwraca evidence), „w mianowniku”. Bez ramek wokół etykiety z wartością i bez kart wokół pól.

## Hierarchia akcji

Na każdym ekranie jest jedna wypełniona akcja: „Przetwórz N plików” na ekranie 1, „Pobierz” na ekranie 2. Ponawianie i przetwarzanie od nowa są obrysowane i schowane w panelu „Dokumenty”. Gdy są ręczne poprawki, „Przetwórz ponownie” i „Przetwórz ten plik ponownie” wymagają drugiego kliknięcia i mówią, ile poprawek usuną.

## Wstawianie z PDF-u

Po zaznaczeniu tekstu w podglądzie pojawia się przycisk „Wstaw do: <rubryka>” przy lewej krawędzi podglądu, na wysokości zaznaczenia, i cienka strzałka w kolorze `brand` od zaznaczenia do przycisku (gdy zaznaczenie leży przy krawędzi, przycisk schodzi pod nie, a strzałka idzie w dół). Położenie liczy `layout.js` (`insertPlacement`). Ikony pasków to rysowane symbole SVG, nie znaki Unicode.

## Ruch

Przejścia 150–220 ms. Jeden moment: po odpowiedzi API kratki wypełniają się znak po znaku (14 ms na znak). Przy `prefers-reduced-motion` ruch jest wyłączony.
