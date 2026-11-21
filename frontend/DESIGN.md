---
name: Odwołania2JSON · Druk urzędowy
description: Panel ekstrakcji jako druk urzędowy wypełniany przez system. Formularz w kolorze druku, dane w czerni.
colors:
  paper: "#FAF1EC"
  paper-deep: "#F3E2D9"
  sheet: "#FFFFFF"
  form: "#9A3218"
  rule: "#E6B4A3"
  rule-soft: "#F2D9CF"
  brand: "#8C2A15"
  brand-deep: "#74220F"
  ink: "#15171C"
  ink-soft: "#4B4440"
  ok: "#17673D"
  ok-bg: "#DCF0E3"
  warn: "#6E4600"
  warn-bg: "#FCE9BC"
typography:
  body:
    fontFamily: Public Sans
    fontSize: 16px
    fontWeight: 400
  value:
    fontFamily: Public Sans
    fontSize: 17px
    fontWeight: 600
  heading:
    fontFamily: Public Sans
    fontSize: 20px
    fontWeight: 600
rounded:
  none: 0px
spacing:
  cell: 28px
---

# Druk urzędowy

## Zasada

Wszystko, co jest formularzem (rubryki, kratki, etykiety, numery pól), ma kolor druku: `form` i `rule` na białym arkuszu albo łososiowym papierze. Wszystko, co system wyciągnął z dokumentu, jest wpisane czernią (`ink`). Użytkownik od razu widzi, co jest szablonem, a co danymi.

## Kolor

Papier (`paper`) to tło aplikacji, biały arkusz (`sheet`) to obszar dokumentu. Czerwień `brand` niesie pasek nawigacji i główne przyciski (biel na niej ma 8,2:1). Statusy: zielony `ok` dla rozpoznanych, bursztyn `warn` dla nierozpoznanych, czerń dla błędów. Płaskie kolory i linie 1 px, bez cieni, gradientów i zaokrągleń. Czerwień tylko tam, gdzie niesie znaczenie: menu, główna akcja, etykiety formularza.

## Typografia

Jeden krój: Public Sans (OFL, w `fonts/`), neutralny krój zaprojektowany dla serwisów administracji publicznej. Wagi 400–600, nagłówki 600, bez wersalików. Cyfry tabelaryczne w całej aplikacji. JSON w systemowym kroju monospace.

## Kratki

Identyfikatory (NIP, KRS, REGON, PESEL), daty i numery rachunków są wpisane w kratki po jednym znaku, jak w blankiecie przelewu. Daty mają przerwy RRRR MM DD, rachunki NRB 2 + grupy po 4. Pole bez danych ma kratki zakreskowane i dopisek „brak w dokumencie”. Pola tak/nie to kwadraty z „X”. Czytnik ekranu dostaje pełną wartość jako tekst.

## Układ

Menu wysuwane z boku na każdym ekranie (przycisk ☰ w górnym pasku, zamykanie kliknięciem obok, wyborem albo Esc), górny pasek z trzema krokami, kolumna „Dokumenty sprawy” i arkusz wybranego dokumentu. Poniżej 1180 px arkusz schodzi pod listę.

## Ruch

Przejścia 150–220 ms. Jeden moment: po odpowiedzi API kratki wypełniają się znak po znaku (14 ms na znak). Przy `prefers-reduced-motion` ruch jest wyłączony.
