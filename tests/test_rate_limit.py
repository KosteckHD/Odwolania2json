from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace

import pytest

from kio_extract.contracts import ConfigurationError, DocumentError
from kio_extract.providers import rate_limit
from kio_extract.providers.rate_limit import RateLimitSettings, RequestCoordinator, retry_after_seconds


class Clock:
    def __init__(self):
        self.value = 100.0
        self.waits = []

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.value += seconds


def connections(statuses, retry_after=None):
    events = []
    responses = iter(statuses)

    class Connection:
        def __init__(self, host, port, timeout):
            self.status = next(responses)

        def request(self, method, path, *, body, headers):
            events.append((method, path, body))

        def getresponse(self):
            return SimpleNamespace(status=self.status, read=lambda: b"{}", getheader=lambda _: retry_after)

        def close(self):
            pass

    return Connection, events


def test_retry_after_then_success_and_pacing(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(rate_limit, "time", clock)
    coordinator = RequestCoordinator()
    factory, calls = connections([429, 200, 200], "3")
    settings = RateLimitSettings(interval=1, retries=4, max_wait=10)
    for _ in range(2):
        assert coordinator.post(factory, "host", None, "/v1", b"data", {}, settings) == b"{}"
    assert len(calls) == 3
    assert clock.waits == [3, 1]


def test_exhaustion_and_long_retry_after_do_not_retry_early(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(rate_limit, "time", clock)
    coordinator = RequestCoordinator()
    factory, calls = connections([429, 429], "2")
    with pytest.raises(DocumentError, match="ograniczył") as error:
        coordinator.post(factory, "host", None, "/", b"", {}, RateLimitSettings(0, 1, 10))
    assert error.value.code == "llm_rate_limit" and len(calls) == 2
    factory, calls = connections([429], "120")
    with pytest.raises(DocumentError) as error:
        coordinator.post(factory, "host", None, "/", b"", {}, RateLimitSettings(0, 4, 10))
    assert error.value.code == "llm_rate_limit" and len(calls) == 1
    factory, calls = connections([200])
    with pytest.raises(DocumentError):
        coordinator.post(factory, "host", None, "/", b"", {}, RateLimitSettings(0, 4, 10))
    assert not calls


def test_exponential_backoff_and_non_429_errors(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(rate_limit, "time", clock)
    factory, calls = connections([429, 429, 200])
    assert RequestCoordinator().post(factory, "host", None, "/", b"", {}, RateLimitSettings(0, 3, 10)) == b"{}"
    assert clock.waits == [1, 2] and len(calls) == 3
    factory, calls = connections([401])
    with pytest.raises(DocumentError) as error:
        RequestCoordinator().post(factory, "host", None, "/", b"", {}, RateLimitSettings(0, 3, 10))
    assert error.value.code == "llm_http" and len(calls) == 1


def test_retry_after_date_and_invalid_settings(monkeypatch):
    header = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30), usegmt=True)
    assert 28 <= retry_after_seconds(header) <= 30
    assert retry_after_seconds("invalid") is None
    monkeypatch.setenv("LLM_REQUEST_INTERVAL_SECONDS", "nan")
    with pytest.raises(ConfigurationError):
        RateLimitSettings.from_environment()


def test_concurrent_requests_share_one_coordinator(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(rate_limit, "time", clock)
    coordinator = RequestCoordinator()
    factory, calls = connections([200] * 8)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: coordinator.post(factory, "host", None, "/", b"", {},
                                                           RateLimitSettings(1, 0, 10)), range(8)))
    assert len(results) == len(calls) == 8
    assert clock.waits == [1] * 7


def test_concurrency_allows_parallel_requests_and_limits_them():
    import threading
    import time as clock
    from kio_extract.providers.rate_limit import RateLimitSettings, RequestCoordinator

    active, peak = 0, 0
    guard = threading.Lock()

    class SlowConnection:
        def __init__(self, host, port, timeout):
            pass

        def request(self, method, path, body, headers):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)

        def getresponse(self):
            clock.sleep(0.2)
            nonlocal active
            with guard:
                active -= 1
            return type("R", (), {"status": 200, "getheader": lambda self, name: None, "read": lambda self: b"{}"})()

        def close(self):
            pass

    def run(concurrency):
        nonlocal peak
        peak = 0
        coordinator = RequestCoordinator()
        settings = RateLimitSettings(interval=0, retries=0, max_wait=1, concurrency=concurrency)
        threads = [threading.Thread(target=coordinator.post, args=(SlowConnection, "h", 1, "/", b"", {}, settings))
                   for _ in range(6)]
        started = clock.monotonic()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return clock.monotonic() - started, peak

    elapsed, most = run(3)
    assert most == 3 and elapsed < 0.9
    elapsed, most = run(1)
    assert most == 1 and elapsed >= 1.1
