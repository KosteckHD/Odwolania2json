@echo off
rem Odwolania2JSON: przetwarza PDF-y z input\<sprawa>\ do output\<sprawa>\<nazwa>.json (tryb oceny UZP).
rem Model jezykowy wlacza sie sam, gdy plik .env zawiera konfiguracje (skopiuj .env.example jako .env i wpisz API_KEY).
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Brak srodowiska Pythona .venv w %CD%
  echo Zainstaluj je raz, wymagany Python 3.13 lub nowszy:
  echo.
  echo   py -3.13 -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  exit /b 1
)
if not exist ".env" echo Uwaga: brak pliku .env. Skopiuj .env.example jako .env i wpisz API_KEY, inaczej dziala tryb regulowy.
".venv\Scripts\python.exe" main.py %*
exit /b %errorlevel%
