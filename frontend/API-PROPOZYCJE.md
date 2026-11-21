# API panelu: stan i propozycja dowodów źródłowych

Panel i API działają pod jednym adresem. Backend zwraca model przebiegu (`meta.model`) i listę aktywnych klas (`GET /api/document-types`), które panel odczytuje automatycznie. Pozostającym rozszerzeniem jest dowód źródłowy pola: numer strony i fragment tekstu PDF. To wspiera transparentność ekstrakcji.

## 1. `evidence` przy dokumencie (transparentność)

Backend ma już `Evidence` w `contracts.py`. Wystarczy dołączyć je do wpisu w `POST /api/extract`:

```json
{
  "filename": "odwolanie.pdf",
  "status": "ok",
  "type": "odwolanie",
  "data": { "...": "..." },
  "evidence": [
    { "field_path": "Odwolujacy.0.krs", "page_number": 1, "method": "regex" },
    { "field_path": "OdwolanieKIO.czynnosc_powod_id", "page_number": 2, "method": "llm" }
  ]
}
```

Panel pokazuje przy rubryce znacznik „str. 1 · regex”. Ścieżki jak w kontrakcie: kropki, indeksy list od zera.

## 2. `meta` w odpowiedzi (wdrożone: jaki model)

```json
{ "documents": [ ... ], "meta": { "model": "Bielik-11B-v2.3" } }
```

API zwraca `meta.model`; panel może wyświetlić identyfikator modelu. Czas przetwarzania nie jest jeszcze osobnym polem metadanych.

## 3. `GET /api/document-types` (wdrożone: rozszerzalność)

Lista klas z `configs/documents/*.yaml`, żeby widok „Typy dokumentów” pokazywał to, co naprawdę jest skonfigurowane:

```json
{
  "types": [
    { "doc_type": "odwolanie", "label": "Odwołanie", "fields": ["OdwolanieKIO.data", "Odwolujacy[].krs"] }
  ]
}
```

`fields` może być listą ścieżek ze schematu albo obiektów `{ "label": "..." }`. Nowy typ dodany przez YAML pojawi się w panelu bez zmian w kodzie frontu. Typ nieznany panelowi wyświetla się z kluczy JSON.

## 4. Serwowanie panelu (wdrożone)

Serwer HTTP backendu serwuje katalog `frontend/` pod `/`, na tym samym porcie co `/api/...`. Jury uruchamia jedną komendę i otwiera przeglądarkę, bez CORS.
