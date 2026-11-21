# Dodanie klasy dokumentu

Przykład [potwierdzenia odbioru](../examples/fourth_class/) pokazuje klasę demonstracyjną wygenerowaną przez kreator w panelu. Nie jest częścią kontraktu UZP. Zawiera konfigurację YAML, JSON Schema i dwa syntetyczne PDF-y: zgodny dokument oraz podobne pismo, które ma zostać odrzucone. Nie wymaga dopisywania klasy do prompta systemowego ani kodu procesora.

1. Zdefiniuj identyfikator klasy, schemat i znaczenie pól w plikach analogicznych do przykładowych. W `llm_instructions` opisz sposób rozpoznania dokumentu oraz reguły wypełniania pól; schemat określa format wyniku. Wzorce `classification` są używane w trybie bez LLM, więc ich również nie pomijaj.
2. Przygotuj zestaw konfiguracji zawierający wszystkie potrzebne klasy oraz odpowiadające im schematy. Przykład w PowerShell, z katalogu projektu:

```powershell
New-Item -ItemType Directory -Force .local/demo-configs, .local/demo-schemas | Out-Null
Copy-Item configs/documents/*.yaml .local/demo-configs/
Copy-Item schemas/*.json .local/demo-schemas/
Copy-Item examples/fourth_class/configs/*.yaml .local/demo-configs/
Copy-Item examples/fourth_class/schemas/*.json .local/demo-schemas/
New-Item -ItemType Directory -Force .local/demo-input | Out-Null
Copy-Item examples/fourth_class/samples/*.pdf .local/demo-input/
.venv/Scripts/python.exe main.py --configs .local/demo-configs --schemas .local/demo-schemas --input .local/demo-input --output .local/demo-output
Get-Content .local/demo-output/potwierdzenie_odbioru.json
Get-Content .local/demo-output/podobne-pismo.json
```

3. Umieść w katalogu wejściowym syntetyczne przykłady nowej klasy, dokumenty innych klas oraz negatywy. Sprawdź klasyfikację, wymagane pola, błędne i brakujące wartości, a także czy poprzednie klasy nadal działają. Dane wysyłane do modelu muszą być odpowiednie dla wybranego dostawcy. W przykładzie pozytywny PDF zwraca `numer: PO-2026-0314` i `data_odbioru: 2026-11-20`; podobny nagłówek „POTWIERDZENIE NADANIA” ma status `unknown`.
4. Dodaj przypadki do manifestu i ewaluacji. Dopiero po uzgodnieniu schematu i integracji wprowadzaj nową klasę do właściwego API i kontraktu UZP.

API może korzystać z tego samego zestawu bez zmian w kodzie. W terminalu serwera ustaw ścieżki do przygotowanych katalogów i uruchom API:

```powershell
$env:KIO_CONFIGS_DIR = (Resolve-Path .local/demo-configs).Path
$env:KIO_SCHEMAS_DIR = (Resolve-Path .local/demo-schemas).Path
$env:LLM_MODEL = ""
$env:LLM_BASE_URL = ""
$env:LLM_API_KEY = ""
$env:API_KEY = ""
.venv/Scripts/python.exe -m uvicorn --app-dir src kio_extract.api:create_app --factory --host 127.0.0.1 --port 8000
```

Panel otwiera się pod `http://127.0.0.1:8000/`; karta „Typy dokumentów” pobiera aktywną listę z API. Taki profil testuje generowanie plików, konfigurację, walidację, ekstrakcję regułową oraz odrzucenie podobnego negatywu bez wywoływania dostawcy. Do próby z modelem uruchom `.venv/Scripts/python.exe start_jury.py`, który przypina endpoint EU i model kandydujący 8B. Opcjonalna zmienna `KIO_PROMPT_PATH` wskazuje plik prompta dla API. W kontenerze ścieżki muszą wskazywać pliki dostępne wewnątrz kontenera. Zmiany konfiguracji są wczytywane przy uruchomieniu procesu, więc po ich zmianie uruchom API ponownie.

Przykład przetestowano przez API na dwóch syntetycznych PDF-ach z konfiguracją wygenerowaną przez ten sam kreator: pozytywny dokument zwrócił numer i datę, a podobny negatyw został odrzucony. Jest to test rozszerzalności oraz ekstrakcji regułowej, nie miara jakości modelu ani rzeczywistych dokumentów.
