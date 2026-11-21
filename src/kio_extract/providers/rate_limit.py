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

    @classmethod
    def from_environment(cls):
        try:
            interval = float(os.getenv("LLM_REQUEST_INTERVAL_SECONDS", "1"))
            retries = int(os.getenv("LLM_MAX_429_RETRIES", "4"))
            max_wait = float(os.getenv("LLM_MAX_RETRY_WAIT_SECONDS", "60"))
            if not math.isfinite(interval) or not math.isfinite(max_wait) or interval < 0 or max_wait < 0 or retries < 0:
                raise ValueError
        except ValueError as exc:
            raise ConfigurationError("Nieprawidłowa konfiguracja limitów żądań LLM") from exc
        return cls(interval, retries, max_wait)


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
    def __init__(self):
        self.lock = threading.Lock()
        self.next_request = 0.0

    def post(self, connection_factory, host, port, path, body, headers, settings):
        # The same lock covers requests and rate-limit waits from all clients in this process.
        with self.lock:
            for attempt in range(settings.retries + 1):
                delay = max(0.0, self.next_request - time.monotonic())
                if delay > settings.max_wait:
                    raise DocumentError("llm_rate_limit", "Przekroczono maksymalny czas oczekiwania na limit API")
                if delay:
                    time.sleep(delay)
                connection = connection_factory(host, port, timeout=60)
                try:
                    self.next_request = time.monotonic() + settings.interval
                    connection.request("POST", path, body=body, headers=headers)
                    response = connection.getresponse()
                    status = response.status
                    retry_after = response.getheader("Retry-After") if status == 429 else None
                    payload = response.read() if status == 200 else b""
                except (OSError, HTTPException) as exc:
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
                self.next_request = max(self.next_request, time.monotonic() + wait)
                if attempt == settings.retries or wait > settings.max_wait:
                    raise DocumentError("llm_rate_limit", "Dostawca ograniczył liczbę żądań LLM")


coordinator = RequestCoordinator()
