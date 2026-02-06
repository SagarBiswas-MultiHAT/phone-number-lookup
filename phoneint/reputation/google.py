# file: phoneint/reputation/google.py
"""
Google Custom Search adapter (requires user-provided API key).

This module intentionally does NOT ship with any API keys.

To use:
1. Create a Google Cloud project and enable "Custom Search API".
2. Create an API key and a Custom Search Engine (CX).
3. Put them in `.env` or environment variables:
   - `GCS_API_KEY=...`
   - `GCS_CX=...`

Legal/ethics:
    Always follow Google's terms, rate limits, and applicable laws. Do not use
    this tool for harassment, stalking, or privacy violations.
"""

from __future__ import annotations

from typing import Any

import httpx

from phoneint.net.http import HttpClientConfig, PerHostRateLimiter, get_json
from phoneint.reputation.adapter import SearchAdapter, SearchResult, now_utc


class GoogleCustomSearchAdapter(SearchAdapter):
    name = "google"
    _API_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        http_config: HttpClientConfig,
        api_key: str | None,
        cx: str | None,
        rate_limiter: PerHostRateLimiter | None = None,
    ) -> None:
        if not api_key or not cx:
            raise RuntimeError(
                "Google Custom Search requires configuration. Set `GCS_API_KEY` and `GCS_CX` "
                "in your environment or .env, and ensure you comply with Google's terms."
            )
        self._client = client
        self._http_config = http_config
        self._rate_limiter = rate_limiter
        self._api_key = api_key
        self._cx = cx

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        params = {
            "key": self._api_key,
            "cx": self._cx,
            "q": query,
            "num": max(1, min(int(limit), 10)),
        }
        data = await get_json(
            self._client,
            self._API_URL,
            config=self._http_config,
            rate_limiter=self._rate_limiter,
            params=params,
        )

        items = data.get("items")
        if not isinstance(items, list):
            return []

        ts = now_utc()
        out: list[SearchResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or ""
            link = item.get("link") or ""
            snippet = item.get("snippet") or ""
            if (
                not isinstance(title, str)
                or not isinstance(link, str)
                or not isinstance(snippet, str)
            ):
                continue
            out.append(
                SearchResult(title=title, url=link, snippet=snippet, timestamp=ts, source=self.name)
            )
            if len(out) >= limit:
                break
        return out
