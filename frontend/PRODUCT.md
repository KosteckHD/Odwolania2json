# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Pracownik Urzędu Zamówień Publicznych, który przyjmuje sprawy odwoławcze KIO. Dostaje sprawę jako zestaw PDF-ów (odwołanie, pełnomocnictwo, potwierdzenie przelewu, czasem inne pisma), wgrywa je razem, sprawdza, co system rozpoznał i wyciągnął, i pobiera JSON-y do dalszych systemów urzędu.

Drugi odbiorca: jury HackNation 2026 (wyzwanie UZP „Odwołania2json”), które ocenia, czy prototyp nadaje się na pilotaż w urzędzie.

## Product Purpose

Odwołania2JSON zamienia wielodokumentową sprawę odwoławczą w ustrukturyzowane dane: dla każdego PDF-u rozpoznaje typ dokumentu i zwraca JSON w kanonicznym formacie UZP. Panel WWW jest interfejsem do tego samego przetwarzania, które wykonuje CLI (`input/` → `output/`).

Sukces panelu: urzędnik wgrywa pliki jednej sprawy, widzi czytelny wynik i status każdego pliku, może sprawdzić dane i pobrać poprawny JSON.

## Positioning

Jedno wywołanie modelu na PDF robi klasyfikację i ekstrakcję naraz, a wynik jest walidowany schematem klasy przed zapisem. Typy dokumentów są opisane w YAML i JSON Schema, więc nową klasę dodaje się bez zmiany kodu. Całość działa lokalnie na CPU z otwartych komponentów; model językowy jest dostępny przez API w UE/EOG.

## Operating Context

- Jednostką pracy jest sprawa: kilka PDF-ów wgrywanych jednym żądaniem, w kolejności wybranej przez użytkownika.
- Dokumenty są cyfrowe albo skanowane (skan wymaga OCR).
- Każdy plik kończy z jednym z trzech statusów: `ok` (typ `odwolanie`, `pelnomocnictwo` lub `przelew` plus dane), `unknown` (dokument spoza klas) albo `error` (komunikat i kod, np. `ocr_required`).
- Dane zawierają identyfikatory urzędowe i finansowe: KRS, NIP, REGON, PESEL, numery BZP i TED, numery rachunków, kwoty, daty.
- Pobierany plik to `<nazwa>.json` i zawiera wyłącznie pole `data` danego dokumentu.

## Capabilities and Constraints

- Kontrakt HTTP: `POST /api/extract`, `multipart/form-data`, każdy PDF jako osobne pole `files`; odpowiedź `{"documents":[...]}` w kolejności plików (szczegóły: `docs/INTERFACES.md`).
- Błąd jednego pliku nie ukrywa pozostałych wyników. HTTP 400 to puste lub błędne żądanie, 5xx to awaria całego żądania.
- Panel ma tryb atrapy działający bez backendu i bez LLM (`frontend/mock/extract-response.json`).
- Stos frontu: statyczny HTML, CSS i JavaScript bez kroku budowania i bez zależności. Jury instaluje tylko Pythona 3.13 i `requirements.txt`.
- Wyłącznie komponenty open source. Uruchomienie lokalne (on-premise) bez GPU, więc fonty i zasoby muszą być w repozytorium, nie z CDN.
- Język interfejsu: polski.
- Własność plików frontu: tylko katalog `frontend/`.
- Nieustalone: czy backend serwuje `frontend/` pod `/` na tym samym porcie co API. API nie zwraca źródła pola ani poziomu pewności, więc panel ich nie pokazuje.

## Brand Commitments

Nazwa: Odwołania2JSON. Logo, kolorów i nazwy zespołu na razie nie ma; mogą dojść później.

## Evidence on Hand

- Wzorce JSON organizatora dla trzech klas i słownik powodów odwołania (repozytorium UZP `hacknation-2026`, katalog `oczekiwane-json`).
- Syntetyczna odpowiedź API z trzema statusami: `docs/fixtures/extract-response.json`.
- Zbiór treningowy UZP: 60 syntetycznych spraw i dokumenty negatywne.
- Brak: wyników F1 na docelowym modelu, logotypu, zrzutów z realnego użycia, opinii użytkowników. Tych rzeczy nie wolno zmyślać w interfejsie.

## Product Principles

1. Dane są święte: panel pokazuje dokładnie to, co zwróciło API, a pobrany plik jest zgodny z formatem UZP co do znaku.
2. Każdy plik ma własny los: status, typ i błąd są zawsze przypisane do konkretnego PDF-u.
3. Uczciwe stany: „nie rozpoznano” i „błąd” są pełnoprawnymi wynikami z jasnym komunikatem, a nie ukrytą porażką.
4. Zero tarcia przy uruchomieniu: działa lokalnie, bez instalowania czegokolwiek poza backendem.

## Accessibility & Inclusion

Zespół wymaga pełnej obsługi z klawiatury (zadanie FE04). Jako cel przyjęto WCAG 2.1 AA, typowy dla serwisów administracji publicznej; to założenie do potwierdzenia z UZP.
