# file: phoneint/cache.py
"""
Optional SQLite TTL cache.

This cache is intended to reduce repeated external calls (search/reputation).
It stores JSON-serializable values keyed by a stable string.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, TypeVar

from phoneint.reputation.adapter import ReputationAdapter, SearchResult

T = TypeVar("T")


def make_cache_key(namespace: str, *parts: str) -> str:
    """
    Make a stable cache key.

    Keys are hashed to keep them short even for long query strings.
    """

    raw = "|".join((namespace, *parts)).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"{namespace}:{digest}"


@dataclass(frozen=True, slots=True)
class CacheStats:
    hits: int = 0
    misses: int = 0


class SQLiteTTLCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON cache(expires_at);")

    def get(self, key: str) -> Any | None:
        now = int(time.time())
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value_json, expires_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            value_json, expires_at = row
            if int(expires_at) <= now:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                return None
            return json.loads(value_json)

    def set(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        expires_at = int(time.time()) + int(ttl_seconds)
        value_json = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache(key, value_json, expires_at) VALUES (?, ?, ?)",
                (key, value_json, int(expires_at)),
            )

    def delete_expired(self) -> int:
        now = int(time.time())
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM cache WHERE expires_at <= ?", (now,))
            return int(cur.rowcount or 0)


def _search_result_from_dict(obj: dict[str, Any]) -> SearchResult:
    ts_raw = obj.get("timestamp") or ""
    ts: datetime
    if isinstance(ts_raw, str) and ts_raw:
        try:
            ts = datetime.fromisoformat(ts_raw)
        except ValueError:
            ts = datetime.now(tz=timezone.utc)
    else:
        ts = datetime.now(tz=timezone.utc)

    return SearchResult(
        title=str(obj.get("title") or ""),
        url=str(obj.get("url") or ""),
        snippet=str(obj.get("snippet") or ""),
        timestamp=ts,
        source=str(obj.get("source") or ""),
    )


class CachedReputationAdapter(ReputationAdapter):
    """
    Adapter wrapper that caches results in SQLite.

    Cached values are stored as JSON (list[dict]) and reconstructed into
    `SearchResult` objects on cache hits.
    """

    def __init__(
        self, adapter: ReputationAdapter, *, cache: SQLiteTTLCache, ttl_seconds: int = 3600
    ) -> None:
        self._adapter = adapter
        self._cache = cache
        self._ttl = ttl_seconds
        self.name = getattr(adapter, "name", adapter.__class__.__name__)

    async def check(self, e164: str, *, limit: int = 5) -> list[SearchResult]:
        key = make_cache_key("reputation", self.name, e164, str(limit))
        cached = await asyncio.to_thread(self._cache.get, key)
        if isinstance(cached, list):
            out: list[SearchResult] = []
            for item in cached:
                if isinstance(item, dict):
                    out.append(_search_result_from_dict(item))
            return out

        results = await self._adapter.check(e164, limit=limit)
        await asyncio.to_thread(
            self._cache.set, key, [r.to_dict() for r in results], ttl_seconds=self._ttl
        )
        return results


class AsyncKeyValueCache(Protocol):
    async def get(self, key: str) -> Any | None:  # pragma: no cover - helper protocol
        raise NotImplementedError

    async def set(
        self, key: str, value: Any, *, ttl_seconds: int
    ) -> None:  # pragma: no cover - helper protocol
        raise NotImplementedError


R = TypeVar("R")


def ttl_cache_async(
    cache: SQLiteTTLCache | None,
    *,
    ttl_seconds: int,
    key_fn: Callable[..., str],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for caching async function results into SQLiteTTLCache.

    This is a low-level helper; prefer `CachedReputationAdapter` for adapter calls.
    The wrapped function must return JSON-serializable values.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if cache is None:
                return await func(*args, **kwargs)
            key = key_fn(*args, **kwargs)
            cached = cache.get(key)
            if cached is not None:
                return cached
            value = await func(*args, **kwargs)
            try:
                cache.set(key, value, ttl_seconds=ttl_seconds)
            except TypeError:
                # Not JSON-serializable; skip caching rather than failing the call.
                pass
            return value

        return wrapper

    return decorator
