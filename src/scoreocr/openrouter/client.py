"""An OpenRouter client shaped like `anthropic.Anthropic` from the caller's side.

`Interpreter` only ever calls `client.messages.create(**anthropic_kwargs)` and
reads `.content` / `.stop_reason` / `.usage` off the result, so satisfying that
surface is enough to run the whole pipeline on any OpenRouter model. The kwarg
and response translation lives in `scoreocr.openrouter.translate`.
"""

import os
import random
import time

import httpx

from scoreocr.openrouter.translate import (
    OpenRouterError, from_chat_response, to_chat_request,
)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-opus-4.5"
# Vision + reasoning over a full page can legitimately run for minutes.
DEFAULT_TIMEOUT = httpx.Timeout(600.0, connect=15.0)
DEFAULT_MAX_RETRIES = 3
MAX_BACKOFF_SECONDS = 30.0
_RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504, 524}


class OpenRouterClient:
    """Minimal Anthropic-shaped client backed by OpenRouter chat completions."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL,
                 base_url: str | None = None, timeout=DEFAULT_TIMEOUT,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 http_client: httpx.Client | None = None):
        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key and http_client is None:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add "
                "your key, or export OPENROUTER_API_KEY in your shell."
            )
        self.model = model
        self.max_retries = max(0, max_retries)
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            base_url=base_url or os.environ.get("OPENROUTER_BASE_URL") or DEFAULT_BASE_URL,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                # Optional OpenRouter attribution headers; they show up on the
                # dashboard and cost nothing.
                "X-Title": "scoreocr",
            },
        )
        # Interpreter reaches for `client.messages.create(...)`.
        self.messages = self

    def create(self, **kwargs):
        body = to_chat_request(kwargs, default_model=self.model)
        return from_chat_response(self._post(body))

    def _post(self, body: dict) -> dict:
        last_error: OpenRouterError | None = None
        for attempt in range(self.max_retries + 1):
            delay = _backoff(attempt)
            try:
                response = self._http.post("/chat/completions", json=body)
            except httpx.RequestError as exc:
                last_error = OpenRouterError(f"request to OpenRouter failed: {exc}")
            else:
                if response.status_code < 400:
                    payload = _decode(response)
                    # OpenRouter reports many upstream failures — rate limits and
                    # overloads included — as HTTP 200 with an error object, so
                    # status alone would let the most common transient failure
                    # skip the retry path entirely.
                    code = _payload_error_code(payload)
                    if code is None:
                        return payload
                    last_error = OpenRouterError(
                        f"OpenRouter returned an error payload: {str(payload)[:500]}")
                    if code not in _RETRY_STATUS:
                        raise last_error
                else:
                    last_error = OpenRouterError(
                        f"OpenRouter returned HTTP {response.status_code}: "
                        f"{response.text[:500]}"
                    )
                    if response.status_code not in _RETRY_STATUS:
                        raise last_error
                    delay = _retry_after(response, delay)
            if attempt == self.max_retries:
                break
            time.sleep(delay)
        raise last_error

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def _backoff(attempt: int) -> float:
    """Exponential backoff with jitter.

    The interpret stage runs four workers against one client, so a rate limit
    usually hits all four at once. Without jitter they would sleep identical
    intervals and retry in lockstep, re-tripping the limit every round.
    """
    return min(2.0 ** attempt, MAX_BACKOFF_SECONDS) * random.uniform(0.5, 1.5)


def _payload_error_code(payload: dict) -> int | None:
    """Return the status-like code from a 200-with-error body, else None."""
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    if isinstance(code, bool):
        return -1
    if isinstance(code, int):
        return code
    if isinstance(code, str) and code.lstrip("-").isdigit():
        return int(code)
    return -1  # An error with no usable code: real, but not retryable.


def _decode(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise OpenRouterError(
            f"OpenRouter returned non-JSON body: {response.text[:500]}"
        ) from exc
    if not isinstance(payload, dict):
        raise OpenRouterError(f"unexpected OpenRouter payload: {str(payload)[:500]}")
    return payload


def _retry_after(response: httpx.Response, fallback: float) -> float:
    raw = response.headers.get("retry-after")
    if not raw:
        return fallback
    try:
        return min(max(float(raw), 0.0), MAX_BACKOFF_SECONDS)
    except ValueError:
        # Retry-After may be an HTTP date; backing off normally is close enough.
        return fallback
