# Panel Odwołania2JSON

Panel WWW do przetwarzania jednej sprawy odwoławczej KIO. Użytkownik wgrywa PDF-y sprawy (odwołanie, pełnomocnictwo, potwierdzenie przelewu, inne pisma), a backend dla każdego pliku zwraca status (`ok`, `unknown`, `error`), typ dokumentu i dane w formacie UZP. W panelu można sprawdzić i poprawić rubryki obok podglądu PDF-u. Wartość da się wstawić, zaznaczając tekst w dokumencie. Na koniec pobiera się JSON pojedynczego pliku albo ZIP całej sprawy.

To statyczny HTML/CSS/JS: bez budowania i bez zależności. Kontrakt z backendem opisuje [docs/INTERFACES.md](../docs/INTERFACES.md#api-dla-frontendu).

## Uruchomienie

### Z atrapą (bez backendu)

```
python -m http.server 5500 -d frontend
```

Otwórz <http://localhost:5500/?mock=1>. Atrapa nie wysyła plików. Wpis dla każdego pliku dobiera z [mock/extract-response.json](mock/extract-response.json) po nazwie pliku, np. `odwolanie…` → odwołanie, `skan…` → błąd OCR, `ogloszenie…` → `unknown`. Tryb można też przełączyć w panelu (pole „Źródło wyników”).

### Z API backendu

Panel wysyła `POST /api/extract` pod adres względny, więc musi być serwowany z tego samego hosta i portu co API. Backend uruchamia się tak (szczegóły w [README.md](../README.md)):

```
.venv/Scripts/python.exe -m uvicorn --app-dir src kio_extract.api:create_app --factory --host 127.0.0.1 --port 8000
```

Obecnie `kio_extract.api` nie serwuje jeszcze katalogu `frontend/`. Propozycja, żeby backend udostępniał go pod `/` na tym samym porcie, jest w [API-PROPOZYCJE.md](API-PROPOZYCJE.md#4-serwowanie-panelu). Po jej wdrożeniu wystarczy otworzyć <http://127.0.0.1:8000/>. Lista typów (`GET /api/document-types`) jest opcjonalna: jeśli jej brak, panel pokazuje typy z `fields.js`.

## Testy

Testy używają wbudowanego `node:test` (Node 22 lub nowszy) i nie wymagają instalowania pakietów. Uruchamia się je z katalogu głównego repo:

```
node --test frontend/tests/
```

| Plik | Co sprawdza |
| --- | --- |
| `tests/parse.test.mjs` | wyłuskiwanie wartości z zaznaczonego tekstu: identyfikatory, daty, kwoty, kod powodu, tekst bez etykiety |
| `tests/api.test.mjs` | `buildForm`, `parseDocuments`, `extractWithApi` (200, 400, 5xx, błąd sieci, przerwanie, z podstawionym `fetchImpl`), `pickMockEntry`, `extractWithMock` |
| `tests/zip.test.mjs` | `crc32` (wektor `123456789`), struktura ZIP z `zipStore`: sygnatury, nazwy, treść, CRC |
| `tests/fixture.test.mjs` | spójność atrapy z `fields.js`: wszystkie trzy statusy, każde pole wpisu `ok` ma rubrykę i odwrotnie |

`tests/index.js` pozwala podać sam katalog: od Node 21 argumenty `--test` są wzorcami glob, a katalog jest ładowany jak moduł. Pojedynczy plik uruchomisz tak: `node --test frontend/tests/parse.test.mjs`.

## Struktura

| Plik | Rola |
| --- | --- |
| `index.html`, `styles.css` | układ i wygląd panelu (zasady w [DESIGN.md](DESIGN.md)) |
| `app.js` | stan, renderowanie listy plików i rubryk, edycja, wstawianie z PDF-u, pobieranie |
| `api.js` | klient `POST /api/extract`, opcjonalne `GET /api/document-types`, atrapa |
| `fields.js` | opis rubryk dla typów `odwolanie`, `pelnomocnictwo`, `przelew` (`DOC_TYPES`). Inne typy wyświetlają się z kluczy JSON |
| `parse.js` | czyste funkcje zamieniające tekst na wartość rubryki |
| `pdfview.js` | podgląd PDF-u z warstwą tekstu (PDF.js z `vendor/pdfjs`) |
| `zip.js` | ZIP bez kompresji do pobrania całej sprawy |
| `mock/` | próbka odpowiedzi API i testowe PDF-y |
| `tests/` | testy `node:test` |
| `PRODUCT.md`, `DESIGN.md`, `API-PROPOZYCJE.md` | kontekst produktu, zasady wyglądu, propozycje zmian API |

## Testowe PDF-y

Syntetyczne pliki w [mock/pdf/](mock/pdf/). W trybie atrapy nazwa pliku wybiera odpowiedź:

| Plik | Wynik w atrapie |
| --- | --- |
| `odwolanie.pdf` | `ok`, odwołanie |
| `pelnomocnictwo.pdf` | `ok`, pełnomocnictwo |
| `potwierdzenie_przelewu.pdf` | `ok`, potwierdzenie przelewu |
| `ogloszenie_bzp.pdf` | `unknown`, dokument spoza klas |
| `skan_pisma.pdf` | `error`, `ocr_required` |

## Ograniczenia

- Skan bez warstwy tekstu da się tylko obejrzeć. Zaznaczanie nie działa, więc wartości trzeba wpisać ręcznie. Panel pokazuje wtedy komunikat.
- Podgląd z zaznaczaniem tekstu (PDF.js) jest sprawdzany w Chrome i Edge. W innych przeglądarkach panel może pokazać zwykły podgląd bez zaznaczania.
- Atrapa nie czyta treści PDF-ów, tylko dobiera gotowy wpis po nazwie pliku.
- Panel nie zapisuje poprawek na serwerze. Poprawione dane trafiają tylko do pobranego JSON-a lub ZIP-a.
