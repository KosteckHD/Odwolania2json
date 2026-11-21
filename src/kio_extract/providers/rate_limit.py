import math
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException

from ..contracts import ConfigurationError, DocumentError


@dataclass(frozen=True)
class RateLimitSettings:
    interval: float = 1.0
    retries: int = 4
    max_wait: float = 60.0
    concurrency: int = 1
    timeout: float = 90.0

    @classmethod
    def from_environment(cls):
        try:
            interval = float(os.getenv("LLM_REQUEST_INTERVAL_SECONDS", "1"))
            retries = int(os.getenv("LLM_MAX_429_RETRIES", "4"))
            max_wait = float(os.getenv("LLM_MAX_RETRY_WAIT_SECONDS", "60"))
            concurrency = int(os.getenv("LLM_CONCURRENCY", "1"))
            timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
            if (not math.isfinite(interval) or not math.isfinite(max_wait) or interval < 0 or max_wait < 0
                    or retries < 0 or not 1 <= concurrency <= 32 or not 1 <= timeout <= 600):
                raise ValueError
        except ValueError as exc:
            raise ConfigurationError("Nieprawidłowa konfiguracja limitów żądań LLM") from exc
        return cls(interval, retries, max_wait, concurrency, timeout)


def retry_after_seconds(value):
    if not value:
        return None
    try:
        seconds = float(value)
        if math.isfinite(seconds) and seconds >= 0:
            return seconds
        return None
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class RequestCoordinator:
    """Odstęp między startami żądań (interval) i limit żądań w toku (concurrency) dla całego procesu."""

    def __init__(self):
        self.lock = threading.Lock()
        self.next_request = 0.0
        self.slots = None
        self.size = 0

    def _slots(self, size):
        with self.lock:
            if self.slots is None or self.size != size:
                self.slots, self.size = threading.BoundedSemaphore(size), size
            return self.slots

    def post(self, connection_factory, host, port, path, body, headers, settings):
        with self._slots(settings.concurrency):
            for attempt in range(settings.retries + 1):
                with self.lock:
                    now = time.monotonic()
                    delay = max(0.0, self.next_request - now)
                    if delay > settings.max_wait:
                        raise DocumentError("llm_rate_limit", "Przekroczono maksymalny czas oczekiwania na limit API")
                    # rezerwacja startu: kolejne żądanie wystartuje najwcześniej po `interval`
                    self.next_request = max(now, self.next_request) + settings.interval
                if delay:
                    time.sleep(delay)
                connection = connection_factory(host, port, timeout=settings.timeout)
                try:
                    connection.request("POST", path, body=body, headers=headers)
                    response = connection.getresponse()
                    status = response.status
                    retry_after = response.getheader("Retry-After") if status == 429 else None
                    payload = response.read() if status == 200 else b""
                except (OSError, HTTPException) as exc:
                    # zerwane połączenie lub przekroczony czas: do 2 ponowień, potem błąd dokumentu
                    if attempt < min(2, settings.retries):
                        time.sleep(min(2 ** attempt, settings.max_wait))
                        continue
                    raise DocumentError("llm_connect", "Brak odpowiedzi ze skonfigurowanego API LLM") from exc
                finally:
                    connection.close()
                if status == 200:
                    return payload
                if status != 429:
                    raise DocumentError("llm_http", f"API LLM zwróciło kod HTTP {status}")
                requested = retry_after_seconds(retry_after)
                backoff = 2 ** min(attempt, 10)
                wait = max(settings.interval, requested if requested is not None else backoff)
                with self.lock:
                    self.next_request = max(self.next_request, time.monotonic() + wait)
                if attempt == settings.retries or wait > settings.max_wait:
                    raise DocumentError("llm_rate_limit", "Dostawca ograniczył liczbę żądań LLM")


coordinator = RequestCoordinator()
