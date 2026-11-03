"""The only place that sends HTTP requests to model providers: timeouts, retries, error mapping."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .types import ProviderError

TIMEOUT = httpx.Timeout(300.0, connect=15.0)
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 4
MAX_RETRY_WAIT = 60.0  # never sleep longer than this between retries, whatever the server asks


def post_json(provider: str, url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    """POST JSON and return the decoded response, retrying rate limits and server errors."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = httpx.post(url, json=body, headers=headers, timeout=TIMEOUT)
        except httpx.HTTPError as exc:
            if attempt == MAX_RETRIES:
                raise ProviderError(provider, f"network error: {exc}") from exc
            time.sleep(2 ** (attempt + 1))
            continue
        if response.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
            time.sleep(retry_wait(response.headers.get("retry-after"), attempt))
            continue
        if response.status_code >= 400:
            raise ProviderError(provider, f"HTTP {response.status_code}: {response.text[:800]}", response.status_code)
        return _decode(provider, response)
    raise AssertionError("unreachable")


def get_json(provider: str, url: str, headers: dict[str, str], params: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        response = httpx.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ProviderError(provider, f"GET {url} failed: {exc}") from exc
    return _decode(provider, response)


def retry_wait(header: str | None, attempt: int) -> float:
    """Seconds to wait before a retry: the server's Retry-After (seconds or an HTTP date), capped at
    MAX_RETRY_WAIT, or exponential backoff when the header is missing or unreadable."""
    backoff = float(2 ** (attempt + 1))
    if not header:
        return backoff
    try:
        seconds = float(header)
    except ValueError:
        try:
            when = parsedate_to_datetime(header)
        except (TypeError, ValueError):
            return backoff
        seconds = (when if when.tzinfo else when.replace(tzinfo=UTC)).timestamp() - datetime.now(UTC).timestamp()
    return min(max(seconds, 0.0), MAX_RETRY_WAIT)


def _decode(provider: str, response: httpx.Response) -> dict[str, Any]:
    """The reply as a JSON object, or a ProviderError that shows what came back instead (e.g. an HTML page)."""
    try:
        data = response.json()
    except ValueError:
        raise ProviderError(provider, f"HTTP {response.status_code}, but the reply was not JSON: "
                                      f"{response.text[:200]!r}", response.status_code) from None
    if not isinstance(data, dict):
        raise ProviderError(provider, f"the reply was JSON but not an object: {str(data)[:200]}", response.status_code)
    return data
