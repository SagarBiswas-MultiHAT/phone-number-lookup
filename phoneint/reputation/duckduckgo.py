# file: phoneint/reputation/duckduckgo.py
"""
DuckDuckGo adapter using the public Instant Answer API.

This is intentionally limited: the Instant Answer API is not a full web search
API. It can still provide helpful, ToS-friendly context without HTML scraping.

Reference:
    https://duckduckgo.com/api
"""

from __future__ import annotations

from typing import Any, Iterable

import httpx

from phoneint.net.http import HttpClientConfig, PerHostRateLimiter, get_json
from phoneint.reputation.adapter import SearchAdapter, SearchResult, now_utc


def _iter_topic_items(related_topics: Any) -> Iterable[dict[str, Any]]:
    # DuckDuckGo returns either:
    # - a list of objects with FirstURL/Text
    # - or a list of groups with a "Topics" list.
    if not isinstance(related_topics, list):
        return

    for item in related_topics:
        if not isinstance(item, dict):
            continue
        if "Topics" in item and isinstance(item["Topics"], list):
            for sub in item["Topics"]:
                if isinstance(sub, dict):
                    yield sub
        else:
            yield item


class DuckDuckGoInstantAnswerAdapter(SearchAdapter):
    name = "duckduckgo"
    _API_URL = "https://api.duckduckgo.com/"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        http_config: HttpClientConfig,
        rate_limiter: PerHostRateLimiter | None = None,
    ) -> None:
        self._client = client
        self._http_config = http_config
        self._rate_limiter = rate_limiter

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        data = await get_json(
            self._client,
            self._API_URL,
            config=self._http_config,
            rate_limiter=self._rate_limiter,
            params=params,
        )

        results: list[SearchResult] = []
        ts = now_utc()

        abstract_url = data.get("AbstractURL")
        abstract_text = data.get("AbstractText")
        if (
            isinstance(abstract_url, str)
            and abstract_url
            and isinstance(abstract_text, str)
            and abstract_text
        ):
            results.append(
                SearchResult(
                    title=abstract_text[:120],
                    url=abstract_url,
                    snippet=abstract_text,
                    timestamp=ts,
                    source=self.name,
                )
            )

        # "Results" is usually small but sometimes includes useful links.
        raw_results = data.get("Results")
        if isinstance(raw_results, list):
            for item in raw_results:
                if not isinstance(item, dict):
                    continue
                url = item.get("FirstURL")
                text = item.get("Text")
                if isinstance(url, str) and url and isinstance(text, str) and text:
                    results.append(
                        SearchResult(
                            title=text[:120],
                            url=url,
                            snippet=text,
                            timestamp=ts,
                            source=self.name,
                        )
                    )
                    if len(results) >= limit:
                        return results[:limit]

        related = data.get("RelatedTopics")
        for item in _iter_topic_items(related):
            url = item.get("FirstURL")
            text = item.get("Text")
            if isinstance(url, str) and url and isinstance(text, str) and text:
                results.append(
                    SearchResult(
                        title=text[:120],
                        url=url,
                        snippet=text,
                        timestamp=ts,
                        source=self.name,
                    )
                )
                if len(results) >= limit:
                    break

        return results[:limit]
