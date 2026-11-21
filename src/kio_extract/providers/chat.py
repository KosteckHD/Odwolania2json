import json
import os
import threading
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlsplit

from ..contracts import ConfigurationError, DocumentError, JsonObject
from ..vision import data_url
from .rate_limit import RateLimitSettings, coordinator


RESERVED_BODY_KEYS = {"model", "messages", "response_format"}
TRANSCRIBE_MAX_TOKENS = 3000


def extra_body_from_environment() -> dict:
    """Dodatkowe pola zapytania z LLM_EXTRA_BODY (JSON), np. {"reasoning_effort": "none"} dla IONOS."""
    raw = os.getenv("LLM_EXTRA_BODY", "").strip()
    if not raw:
        return {}
    try:
        extra = json.loads(raw)
    except ValueError as exc:
        raise ConfigurationError("LLM_EXTRA_BODY musi być obiektem JSON") from exc
    if not isinstance(extra, dict) or RESERVED_BODY_KEYS & extra.keys():
        raise ConfigurationError("LLM_EXTRA_BODY musi być obiektem JSON bez pól model, messages i response_format")
    return extra


class ChatClient:
    @property
    def last_usage(self):
        return getattr(self._local, "usage", None)

    @last_usage.setter
    def last_usage(self, value):
        self._local.usage = value

    def __init__(self, base_url: str, model: str, api_key: str, extra_body: dict | None = None):
        try:
            url = urlsplit(base_url)
            hostname, port = url.hostname, url.port
        except ValueError as exc:
            raise ConfigurationError("Nieprawidłowy adres LLM_BASE_URL") from exc
        loopback = hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not hostname or url.username is not None or url.query or url.fragment
            or (url.scheme != "https" and not (url.scheme == "http" and loopback))
        ):
            raise ConfigurationError("LLM_BASE_URL wymaga HTTPS lub lokalnego adresu pętli zwrotnej")
        if not model or (not api_key and not loopback):
            raise ConfigurationError("Ustaw LLM_MODEL i klucz LLM_API_KEY dla zdalnego API")
        self.hostname = hostname
        self.port = port
        self.connection = HTTPSConnection if url.scheme == "https" else HTTPConnection
        self.path = url.path.rstrip("/") + "/chat/completions"
        self._local = threading.local()   # zużycie tokenów osobno dla każdego wątku CLI
        self.model = model
        self.extra_body = dict(extra_body or {})
        self.rate_limit = RateLimitSettings.from_environment()
        self.last_usage = None
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    @classmethod
    def from_environment(cls) -> "ChatClient":
        return cls(
            os.getenv("LLM_BASE_URL", "").strip(),
            os.getenv("LLM_MODEL", "").strip(),
            (os.getenv("LLM_API_KEY") or os.getenv("API_KEY", "")).strip(),
            extra_body_from_environment(),
        )

    def _complete(self, messages: list, **options) -> dict:
        """Jedno zapytanie /chat/completions; zwraca pierwszy wybór, zużycie tokenów sumuje w wątku."""
        body = json.dumps({"model": self.model, "messages": messages, "temperature": 0, **options, **self.extra_body},
                          ensure_ascii=False).encode("utf-8")
        payload = coordinator.post(self.connection, self.hostname, self.port, self.path, body, self.headers, self.rate_limit)
        try:
            response = json.loads(payload)
            if not isinstance(response, dict):
                raise TypeError("expected object")
            usage = response.get("usage")
            if isinstance(usage, dict):
                previous = self.last_usage or {}
                self.last_usage = {key: previous.get(key, 0) + usage[key]
                                   for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                                   if isinstance(usage.get(key), int)}
            choice = response["choices"][0]
            if not isinstance(choice, dict) or not isinstance(choice["message"], dict):
                raise TypeError("expected object")
            return choice
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise DocumentError("llm_json", "API LLM zwróciło nieprawidłowy JSON") from exc

    def extract_json(self, *, instructions: str, text: str, schema: JsonObject,
                     images: tuple[tuple[int, bytes], ...] = ()) -> JsonObject:
        system = instructions + "\n\n## Schemat odpowiedzi\n" + json.dumps(schema, ensure_ascii=False)
        content = text
        if images:
            # skany przy SCAN_MODE=image: obrazy stron po tekście, każdy opisany numerem strony
            content = [{"type": "text", "text": text}]
            for number, image in images:
                content.append({"type": "text", "text": f"Strona {number} (skan, tekst tylko na obrazie):"})
                content.append({"type": "image_url", "image_url": {"url": data_url(image)}})
        choice = self._complete([{"role": "system", "content": system}, {"role": "user", "content": content}],
                                response_format={"type": "json_object"})
        if choice.get("finish_reason") != "stop":
            raise DocumentError("llm_incomplete", "API LLM nie ukończyło odpowiedzi JSON")
        try:
            result = json.loads(choice["message"]["content"])
        except (ValueError, KeyError, TypeError) as exc:
            raise DocumentError("llm_json", "API LLM zwróciło nieprawidłowy JSON") from exc
        if not isinstance(result, dict):
            raise DocumentError("llm_json", "Odpowiedź LLM musi być obiektem JSON")
        return result

    def transcribe_image(self, *, instructions: str, image: bytes) -> str:
        """OCR tym samym modelem: tekst strony z obrazu JPEG (odpowiedź uciętą limitem też bierzemy)."""
        content = [{"type": "text", "text": instructions}, {"type": "image_url", "image_url": {"url": data_url(image)}}]
        choice = self._complete([{"role": "user", "content": content}], max_tokens=TRANSCRIBE_MAX_TOKENS)
        text = choice["message"].get("content")
        if not isinstance(text, str):
            raise DocumentError("llm_json", "API LLM nie zwróciło tekstu strony")
        return text.strip()
