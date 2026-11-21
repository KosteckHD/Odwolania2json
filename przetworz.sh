#!/usr/bin/env sh
# Odwolania2JSON: przetwarza PDF-y z input/<sprawa>/ do output/<sprawa>/<nazwa>.json (tryb oceny UZP).
# Model językowy włącza się sam, gdy .env zawiera konfigurację (skopiuj .env.example jako .env i wpisz API_KEY).
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Brak .venv. Zainstaluj raz (Python 3.13+):"
  echo "  python3.13 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi
[ -f .env ] || echo "Uwaga: brak pliku .env. Skopiuj .env.example jako .env i wpisz API_KEY, inaczej działa tryb regułowy."
exec .venv/bin/python main.py "$@"
