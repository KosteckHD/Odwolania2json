#!/usr/bin/env bash
# Test dokładnie tak, jak zrobią to oceniający (VM.md, pkt 4):
#   cd /opt/solution && bash deploy/vm-test.sh /ścieżka/do/sprawy-z-pdfami [nazwa-sprawy]
# Kopiuje PDF-y do input/<nazwa>, czyści output/, uruchamia komendę z RUN.md (z sudo), pokazuje wyniki,
# a na końcu usuwa testowe pliki z input/ i output/ (katalogi zostają puste, jak przed oceną).
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${1:?Podaj katalog z przykładowymi PDF-ami}"
NAME="${2:-test-sprawa}"

COMMAND="$(awk '/^```bash/{f=1;next} /^```/{if(f){exit}} f' RUN.md | head -1)"
echo "== Komenda z RUN.md: $COMMAND"

sudo rm -rf output/* "input/$NAME"
mkdir -p "input/$NAME"
cp "$SRC"/*.pdf "input/$NAME/"
echo "== PDF-y w input/$NAME: $(ls "input/$NAME" | wc -l)"

START=$(date +%s)
sudo bash -c "cd /opt/solution 2>/dev/null || cd '$(pwd)'; $COMMAND"
echo "== Czas: $(( $(date +%s) - START )) s"

echo "== Wyniki w output/:"
find output -name '*.json' | sort | while read -r f; do echo "--- $f"; head -c 600 "$f"; echo; done

read -r -p "Usunąć pliki testowe z input/ i output/? [T/n] " ans || ans=T
if [ "${ans:-T}" != "n" ]; then sudo rm -rf output/* "input/$NAME"; echo "Wyczyszczone."; fi
