# KIOdczyt (Odwołania2JSON) — uruchomienie oceny

Komenda (z katalogu `/opt/solution`, z uprawnieniami administratora):

```bash
docker compose run --rm batch
```

- Przetwarza wszystkie pliki PDF z `/opt/solution/input` (także w podkatalogach, np. `input/<sprawa>/*.pdf`)
  i zapisuje wyniki do `/opt/solution/output` z tą samą strukturą: `output/<sprawa>/<nazwa pliku>.json`.
- Nie wymaga interakcji i kończy się sama po przetworzeniu wszystkich plików.
- Dokument spoza trzech klas (odwołanie, pełnomocnictwo, potwierdzenie przelewu) dostaje plik z samym `{}`.
  Każdy PDF dostaje plik wyniku, także przy chwilowym błędzie usługi modelu (wtedy wynik z reguł).
- Obraz Dockera `kiodczyt:latest` jest zbudowany na serwerze wcześniej; jeśli by go brakowało,
  komenda zbuduje go sama (potrzebny internet, ok. 2–3 min).

## Usługi zewnętrzne i klucz API

- **Model językowy:** Qwen3.5 9B (open source, licencja Apache 2.0, 9B parametrów),
  dostarczany przez **HostYourAI B.V.** (Holandia) przez API zgodne z OpenAI; przetwarzanie w centrach danych w UE.
- **Klucz API i konfiguracja** są w pliku `/opt/solution/.env` (wzór bez klucza: `.env.example`). W kodzie nie ma kluczy.
- **OCR:** skany czyta ten sam model z obrazu strony (bez dodatkowego modelu). Bez usługi modelu działa
  tryb regułowy z konfiguracji YAML.

## Panel WWW (opcjonalnie, do obejrzenia wyników)

Panel do przeglądania i poprawiania wyników działa w tle pod `http://<adres-serwera>:8000/`
(usługa `api` w `compose.yaml`, startuje sama po restarcie serwera). Nie jest potrzebny do oceny.
