# Dodanie klasy dokumentu

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
