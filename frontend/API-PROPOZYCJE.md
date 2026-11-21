# Propozycje rozszerzeń API dla panelu (do uzgodnienia z backendem)

Wszystkie pola są **opcjonalne**. Panel działa bez nich, a gdy backend je zwróci, pokazuje je automatycznie. Celują w kryteria UZP: transparentność ekstrakcji, łatwe dodawanie typów dokumentów i „inne ciekawe funkcje (GUI)”.

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

## 2. `meta` w odpowiedzi (jaki model, jak szybko)

```json
{ "documents": [ ... ], "meta": { "model": "Bielik-11B-v2.3" } }
```

Panel pokazuje w „Wyniku sprawy” wiersz „Przebieg: model … · czas … s”. Czas mierzy sam panel.

## 3. `GET /api/document-types` (rozszerzalność)

Lista klas z `configs/documents/*.yaml`, żeby widok „Typy dokumentów” pokazywał to, co naprawdę jest skonfigurowane:

```json
{
  "types": [
    { "doc_type": "odwolanie", "label": "Odwołanie", "fields": ["OdwolanieKIO.data", "Odwolujacy[].krs"] }
  ]
}
```

`fields` może być listą ścieżek ze schematu albo obiektów `{ "label": "..." }`. Nowy typ dodany przez YAML pojawi się w panelu bez zmian w kodzie frontu. Typ nieznany panelowi wyświetla się z kluczy JSON.

## 4. Serwowanie panelu

Proponuję, żeby serwer HTTP backendu serwował katalog `frontend/` pod `/`, na tym samym porcie co `/api/...`. Wtedy jury odpala jedną komendę i otwiera przeglądarkę, bez CORS.
