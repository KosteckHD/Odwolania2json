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

Menu wysuwane z boku na każdym ekranie (przycisk ☰ w górnym pasku, zamykanie kliknięciem obok, wyborem albo Esc), górny pasek z trzema krokami, kolumna „Dokumenty sprawy” (264–320 px, rośnie z oknem) i arkusz wybranego dokumentu. Rubryki układają się w dwie kolumny od ok. 480 px szerokości panelu. Poniżej 1180 px arkusz schodzi pod listę. Na komputerze kolumnę „Dokumenty sprawy” można zwinąć do paska numerów dokumentów (kolor statusu na dolnej krawędzi, kwadracik = poprawiony), żeby rubryki i PDF miały więcej miejsca. W oknach niższych niż 820 px górny pasek i nagłówek arkusza są niższe.

## Hierarchia akcji

W kolumnie „Dokumenty sprawy” jest jedna wypełniona akcja naraz. Przed przetworzeniem: „Przetwórz N plików”. Po przetworzeniu: „Pobierz ZIP (N plików)” na górze kolumny, pod nim niższe obrysowane „Ponów błędne (N)” i „Przetwórz ponownie”. Gdy są ręczne poprawki, „Przetwórz ponownie” wymaga drugiego kliknięcia i mówi, ile poprawek usunie. Nagłówek arkusza ma tę samą wysokość we wszystkich stanach (wiersz informacji jest zawsze), więc pasek PDF nie skacze przy zmianie dokumentu. Ikony paska PDF to te same rysowane symbole SVG co reszta panelu, nie znaki Unicode.

## Ruch

Przejścia 150–220 ms. Jeden moment: po odpowiedzi API kratki wypełniają się znak po znaku (14 ms na znak). Przy `prefers-reduced-motion` ruch jest wyłączony.
