#!/usr/bin/env sh
# Odwolania2JSON: uruchamia API i panel WWW pod jednym adresem, potem otwiera przeglądarkę.
cd "$(dirname "$0")" || exit 1
PORT="${PORT:-8000}"
URL="http://127.0.0.1:$PORT/"
PYTHON=.venv/bin/python
if [ ! -x "$PYTHON" ]; then
  echo "Brak środowiska Pythona .venv. Zainstaluj je raz (Python 3.13 lub nowszy):"
  echo "  python3.13 -m venv .venv"
  echo "  .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi
[ -f .env ] || echo "Uwaga: brak pliku .env, więc API działa w trybie regułowym, bez modelu językowego."
echo "Panel i API: $URL   (Ctrl+C zatrzymuje serwer)"
if [ -z "$NO_BROWSER" ]; then
  (
    for _ in $(seq 60); do
      if "$PYTHON" -c "import urllib.request; urllib.request.urlopen('$URL', timeout=2)" 2>/dev/null; then
        if command -v xdg-open >/dev/null; then xdg-open "$URL"; elif command -v open >/dev/null; then open "$URL"; fi
        break
      fi
      sleep 1
    done
  ) >/dev/null 2>&1 &
fi
exec "$PYTHON" -m uvicorn --app-dir src kio_extract.api:create_app --factory --host 127.0.0.1 --port "$PORT"
