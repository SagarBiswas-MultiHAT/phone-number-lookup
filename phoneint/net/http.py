# file: phoneint/net/http.py
"""
Async HTTP utilities (httpx) with retries, exponential backoff, and per-host rate limiting.

All network calls in phoneint should be async and cancellable to avoid GUI freezes.
"""

from __future__ import annotations

import asyncio
import random
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, cast
from urllib.parse import urlparse

import httpx


def _host_for_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or parsed.path  # path fallback for odd URLs


class PerHostRateLimiter:
    """
    Simple per-host leaky-bucket limiter.

    This enforces a minimum interval between requests to the same host.
    """

    def __init__(self, *, rate_per_second: float = 1.0) -> None:
        self._min_interval = 0.0 if rate_per_second <= 0 else (1.0 / rate_per_second)
        self._locks: dict[str, asyncio.Lock] = {}
        self._next_allowed: dict[str, float] = {}

    async def wait(self, host: str) -> None:
        if self._min_interval <= 0:
            return

        lock = self._locks.get(host)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[host] = lock

        async with lock:
            now = time.monotonic()
            next_allowed = self._next_allowed.get(host, now)
            if next_allowed > now:
                await asyncio.sleep(next_allowed - now)
                now = next_allowed
            self._next_allowed[host] = now + self._min_interval


@dataclass(frozen=True, slots=True)
class HttpClientConfig:
    timeout_seconds: float = 10.0
    max_retries: int = 2
    backoff_base_seconds: float = 0.5
    backoff_max_seconds: float = 8.0
    rate_limit_per_host_per_second: float = 1.0
    user_agent: str = "phoneint/0.1 (+https://example.invalid; lawful OSINT only)"


@asynccontextmanager
async def build_async_client(config: HttpClientConfig) -> AsyncIterator[httpx.AsyncClient]:
    timeout = httpx.Timeout(config.timeout_seconds)
    headers = {"User-Agent": config.user_agent}
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        yield client


def _compute_backoff(attempt: int, *, base: float, cap: float) -> float:
    # Full jitter around exponential backoff.
    raw = min(cap, base * (2**attempt))
    return float(raw * random.uniform(0.8, 1.2))


async def request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    config: HttpClientConfig,
    rate_limiter: PerHostRateLimiter | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """
    Make an HTTP request with retries and backoff.

    Retries on:
    - network/transport errors
    - HTTP 429 and 5xx responses
    """

    if config.max_retries < 0:
        raise ValueError("max_retries must be >= 0")

    host = _host_for_url(url)
    last_exc: Exception | None = None

    for attempt in range(config.max_retries + 1):
        if rate_limiter is not None:
            await rate_limiter.wait(host)

        try:
            resp = await client.request(method, url, **kwargs)
        except asyncio.CancelledError:
            raise
        except httpx.TransportError as exc:
            last_exc = exc
            if attempt >= config.max_retries:
                raise
            await asyncio.sleep(
                _compute_backoff(
                    attempt, base=config.backoff_base_seconds, cap=config.backoff_max_seconds
                )
            )
            continue

        if resp.status_code in (429, 500, 502, 503, 504):
            if attempt >= config.max_retries:
                resp.raise_for_status()
                return resp

            retry_after = resp.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    sleep_for = float(retry_after)
                except ValueError:
                    sleep_for = _compute_backoff(
                        attempt, base=config.backoff_base_seconds, cap=config.backoff_max_seconds
                    )
            else:
                sleep_for = _compute_backoff(
                    attempt, base=config.backoff_base_seconds, cap=config.backoff_max_seconds
                )

            # Ensure the response body is drained so the connection can be reused.
            try:
                await resp.aread()
            except Exception:
                pass

            await asyncio.sleep(sleep_for)
            continue

        resp.raise_for_status()
        return resp

    # Should be unreachable.
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("request_with_retries: exhausted attempts without a response")


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    config: HttpClientConfig,
    rate_limiter: PerHostRateLimiter | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """GET JSON from a URL using `request_with_retries`."""

    resp = await request_with_retries(
        client, "GET", url, config=config, rate_limiter=rate_limiter, params=params
    )
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object at the top level")
    return cast(dict[str, Any], data)
