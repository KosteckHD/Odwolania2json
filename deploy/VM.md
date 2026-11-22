# Wdrożenie na serwer oceny (Azure VM, Ubuntu 24.04)

Na podstawie instrukcji organizatora: https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026/blob/main/VM.md
**Dostęp zespołów odcinany 22.11.2026 o 11:00** — po tej godzinie liczy się stan serwera.

## Docelowa struktura

```
/opt/solution/            ← repozytorium (kod, compose.yaml, Dockerfile, configs/, prompts/, schemas/, ...)
├── RUN.md                ← komenda oceny: docker compose run --rm batch
├── .env                  ← klucz API i konfiguracja modelu (NIE w repozytorium; wzór: .env.example)
├── compose.yaml          ← usługa batch (ocena) i api (panel WWW na :8000)
├── input/                ← tu oceniający wgrywają dokumenty (katalog już istnieje — nie usuwać)
└── output/               ← tu powstają wyniki (katalog już istnieje — nie usuwać)
```

Python 3.12 z serwera nie jest używany: obraz Dockera ma Pythona 3.13 (wymóg UZP) i wszystkie zależności.

## Kroki (z własnego komputera)

1. Logowanie: `ssh <login>@<adres-ip>` (przy „Too many authentication failures”: `ssh -o PubkeyAuthentication=no <login>@<adres-ip>`).
2. Kod do `/opt/solution` (katalog nie jest pusty — są w nim `input/` i `output/`, więc bez `git clone` do niego wprost):
   ```bash
   cd /opt/solution
   git init -q
   git remote add origin https://github.com/KosteckHD/Odwolania2json.git
   git fetch --depth 1 origin <gałąź>        # np. feat/f1-runda2 albo main po scaleniu
   git checkout -q -f FETCH_HEAD
   ```
   Repozytorium prywatne: użyj tokenu GitHub (`https://<token>@github.com/...`) albo skopiuj pliki `scp -r`.
3. Klucz: `cp .env.example .env && nano .env` → wpisz `LLM_API_KEY=...` (klucz HostYourAI). `chmod 600 .env`.
4. Instalacja i próba: `bash deploy/vm-setup.sh` (buduje obraz, uruchamia panel w tle, przetwarza plik testowy).
5. Test jak u oceniających: wgraj kilka PDF-ów sprawy (np. `scp -r przyklad_01 <login>@<ip>:/tmp/`) i
   `bash deploy/vm-test.sh /tmp/przyklad_01`.
6. Restart i powtórka testu: `sudo reboot`, odczekaj 1–2 min, zaloguj się i ponów krok 5.
   Panel powinien działać sam pod `http://<adres-ip>:8000/`.
7. Na koniec: `input/` i `output/` puste (skrypt testowy je czyści), `.env` z kluczem na miejscu.
