#!/usr/bin/env bash
# Przygotowanie serwera oceny (Ubuntu 24.04, Docker + Compose v2) — uruchom raz, jako swoje konto, w /opt/solution:
#   cd /opt/solution && bash deploy/vm-setup.sh
# Robi: sprawdza strukturę katalogów i .env, buduje obraz Dockera, uruchamia panel WWW w tle i robi próbę na pliku testowym.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

echo "== Katalog projektu: $ROOT"
[ "$ROOT" = "/opt/solution" ] || echo "UWAGA: oceniający szukają rozwiązania w /opt/solution (teraz: $ROOT)."
for f in RUN.md compose.yaml Dockerfile main.py requirements.txt; do
  [ -f "$f" ] || { echo "BRAK pliku $f — repozytorium musi leżeć bezpośrednio w /opt/solution"; exit 1; }
done
mkdir -p input output

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Utworzono .env z .env.example — wpisz klucz w wierszu LLM_API_KEY= i uruchom skrypt ponownie."
  exit 1
fi
if ! grep -Eq '^(LLM_API_KEY|API_KEY)=.+' .env; then
  echo "W .env brakuje klucza (LLM_API_KEY=...). Uzupełnij i uruchom ponownie."
  exit 1
fi
chmod 600 .env

echo "== Budowanie obrazu Dockera (zależności pobierane teraz, nie w czasie oceny)"
docker compose build batch

echo "== Panel WWW w tle (port 8000, restart: unless-stopped)"
docker compose up -d api

echo "== Próba: jeden PDF testowy w katalogu tymczasowym (input/ i output/ zostają nietknięte)"
TMP="$(mktemp -d)"
mkdir -p "$TMP/input/proba" "$TMP/output"
cp frontend/mock/pdf/potwierdzenie_przelewu.pdf "$TMP/input/proba/"
docker compose run --rm -v "$TMP/input:/app/input:ro" -v "$TMP/output:/app/output" batch
echo "-- wynik:"
cat "$TMP/output/proba/potwierdzenie_przelewu.json"; echo
rm -rf "$TMP" 2>/dev/null || sudo rm -rf "$TMP"

echo "== Gotowe. Test jak u oceniających: bash deploy/vm-test.sh <katalog z PDF-ami>"
