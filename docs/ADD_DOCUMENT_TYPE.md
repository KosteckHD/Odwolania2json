# Dodanie klasy dokumentu

## Z panelu WWW (bez edycji plików)

W panelu: menu ☰ → „Typy dokumentów” → „+ Dodaj typ dokumentu”. Kreator przygotowuje YAML i schemat, a przycisk „Dodaj do systemu” wysyła je do `POST /api/document-types`. Serwer:

- sprawdza cały zestaw (dotychczasowe klasy + nowa) funkcją `load_configs`, czyli tymi samymi regułami co przy starcie; przy błędzie niczego nie zapisuje i zwraca opis problemu,
- odrzuca istniejący identyfikator (`409`), klucz `extractor` (kod Pythona dodaje się tylko w repozytorium) i schemat o innej nazwie niż `<id>.schema.json`,
- zapisuje `configs/documents/<id>.yaml` i `schemas/<id>.schema.json` i od następnego żądania używa nowej klasy, bez restartu; CLI widzi ją przy kolejnym uruchomieniu.

Zapis z panelu wyłącza zmienna `ALLOW_TYPE_UPLOAD=0` (np. na serwerze współdzielonym). Kreator zawsze pozwala też pobrać oba pliki i dodać je ręcznie, jak poniżej.

## Ręcznie

Przykład [potwierdzenia odbioru](../examples/fourth_class/) pokazuje klasę demonstracyjną. Nie jest ona częścią kontraktu UZP. Zawiera konfigurację klasy i schemat JSON; nie wymaga dopisywania klasy do prompta systemowego ani kodu procesora.

1. Zdefiniuj identyfikator klasy, schemat i znaczenie pól w plikach analogicznych do przykładowych. W `llm_instructions` opisz sposób rozpoznania dokumentu oraz reguły wypełniania pól; schemat określa format wyniku. Wzorce `classification` są używane w trybie bez LLM, więc ich również nie pomijaj.
2. Przygotuj zestaw konfiguracji zawierający wszystkie potrzebne klasy oraz odpowiadające im schematy. Przykład w PowerShell, z katalogu projektu:

```powershell
New-Item -ItemType Directory -Force .local/demo-configs, .local/demo-schemas | Out-Null
Copy-Item configs/documents/*.yaml .local/demo-configs/
Copy-Item schemas/*.json .local/demo-schemas/
Copy-Item examples/fourth_class/configs/*.yaml .local/demo-configs/
Copy-Item examples/fourth_class/schemas/*.json .local/demo-schemas/
.venv/Scripts/python.exe main.py --llm --configs .local/demo-configs --schemas .local/demo-schemas --input .local/demo-input --output .local/demo-output
```

3. Umieść w katalogu wejściowym syntetyczne przykłady nowej klasy, dokumenty innych klas oraz negatywy. Sprawdź klasyfikację, wymagane pola, błędne i brakujące wartości, a także czy poprzednie klasy nadal działają. Dane wysyłane do modelu muszą być odpowiednie dla wybranego dostawcy.
4. Dodaj przypadki do manifestu i ewaluacji. Dopiero po uzgodnieniu schematu i integracji wprowadzaj nową klasę do właściwego API i kontraktu UZP.

Przykład przetestowano z Sonnetem na syntetycznym PDF: wynik zawierał `numer: ABC-123` i `data: 2026-11-15`. To demonstracja rozszerzalności, nie miara jakości dla rzeczywistych dokumentów.
