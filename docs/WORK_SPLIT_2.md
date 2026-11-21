# Podział pracy na dwie osoby

Backend i frontend mają po 18 godzin zaplanowanej pracy w 22-godzinnym oknie. Pozostałe 4 godziny na osobę to bufor na przerwy, integrację i problemy wykryte podczas prób. Wspólny priorytet to pokazanie przepływu od PDF-u do poprawnego JSON-u.

| Rola | Własność plików | Kryterium odbioru |
| --- | --- | --- |
| **Backend** | `main.py`, `src/kio_extract/`, `prompts/system_pl.md`, `configs/`, `schemas/`, `tests/`, `evaluation/`, zależności Pythona i pliki uruchomienia | Jedno wywołanie LLM na PDF, walidacja i zapis w formacie UZP, działające CLI i API dla interfejsu. Raport lokalny obejmuje klasy, pola i negatywy. |
| **Frontend** | `frontend/`, w tym klient API, atrapa, testy i dokumentacja UI | Wczytanie PDF-ów jednej sprawy, czytelny wynik i status per plik, podgląd oraz pobranie JSON. Krótkie demo pełnego przepływu. |

Obie osoby wspólnie zatwierdzają format HTTP i przykładową odpowiedź. Backend utrzymuje [kontrakt API](INTERFACES.md), a frontend może od razu podłączyć [syntetyczną odpowiedź](fixtures/extract-response.json) do swojego widoku. Python i przeglądarka mają oddzielne katalogi testów.

| Rola | Kolejność prac P0 | Budżet | P1 po przejściu odbioru |
| --- | --- | ---: | --- |
| Backend | Kontrakt i endpoint (3 h), rzeczywisty przebieg LLM i poprawki prompta (5 h), OCR dla skanów (3 h), lokalny pomiar i regresje (4 h), uruchomienie i integracja (3 h) | 18 h | Może rozszerzyć diagnostykę i warianty OCR, jeśli zostanie bufor. |
| Frontend | Przepływ na atrapie (4 h), obsługa zestawu PDF-ów i stanów (5 h), podgląd i pobieranie JSON (3 h), połączenie z API (3 h), testy i demo (3 h) | 18 h | Opcjonalne pobranie wyników jako ZIP. |

## Zależności i granice odpowiedzialności

| Konsument | Zależność | Praca równoległa | Przekazanie |
| --- | --- | --- | --- |
| Frontend | Endpoint i poprawne przykłady odpowiedzi | Atrapa z pliku `docs/fixtures/extract-response.json` obsługuje trafienie, negatyw i błąd pojedynczego pliku. | Wspólny kontrakt przed rozpoczęciem. Pierwsza integracja do 6 h. |
| Backend | Otwarte API LLM w UE/EOG i testy na rzeczywistych plikach | Wykorzystuje istniejącą atrapę LLM i testy CLI. Bada oddzielnie trzy klasy i odrzucone dokumenty. | Test na wybranym modelu przed pierwszym pomiarem jakości do 11 h. |
| Obie role | Demo i wykrywanie problemów | Backend uruchamia batch na sprawach, frontend sprawdza dokładnie ten zestaw stanów na atrapie. | Do 19 h wspólna próba na rzeczywistych PDF-ach i instrukcja uruchomienia. |

Szczegóły etapów są w [harmonogramie](INTEGRATION_PLAN.md), a kolejka prac w [tablicy zadań](WORKBOARD.md).
