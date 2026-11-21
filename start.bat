@echo off
rem Odwolania2JSON: uruchamia API i panel WWW pod jednym adresem, potem otwiera przegladarke.
rem Inny port: najpierw set PORT=8080, potem start.bat
setlocal
cd /d "%~dp0"
if not defined PORT set "PORT=8000"
set "URL=http://127.0.0.1:%PORT%/"

if not exist ".venv\Scripts\python.exe" (
  echo Brak srodowiska Pythona .venv w %CD%
  echo Zainstaluj je raz, wymagany Python 3.13 lub nowszy:
  echo.
  echo   py -3.13 -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  echo Potem uruchom start.bat ponownie.
  pause
  exit /b 1
)
if not exist ".env" echo Uwaga: brak pliku .env, wiec API dziala w trybie regulowym, bez modelu jezykowego.

echo Panel i API: %URL%   (Ctrl+C zatrzymuje serwer)
if not defined NO_BROWSER start "" /b powershell -NoProfile -Command "for ($i = 0; $i -lt 60; $i++) { try { Invoke-WebRequest -UseBasicParsing '%URL%' -TimeoutSec 2 | Out-Null; Start-Process '%URL%'; break } catch { Start-Sleep 1 } }"
".venv\Scripts\python.exe" -m uvicorn --app-dir src kio_extract.api:create_app --factory --host 127.0.0.1 --port %PORT%
if errorlevel 1 (
  echo Serwer zakonczyl sie bledem. Jesli port %PORT% jest zajety, wpisz set PORT=8080 i uruchom start.bat ponownie.
  pause
)
