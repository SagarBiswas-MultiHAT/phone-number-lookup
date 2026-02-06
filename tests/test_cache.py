# file: tests/test_cache.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from phoneint.cache import CachedReputationAdapter, SQLiteTTLCache, make_cache_key
from phoneint.reputation.adapter import ReputationAdapter, SearchResult


def test_sqlite_ttl_cache_expires(monkeypatch, tmp_path: Path) -> None:
    cache = SQLiteTTLCache(tmp_path / "cache.sqlite3")
    key = make_cache_key("unit", "k1")

    # Freeze time for deterministic TTL behavior.
    now = 1_700_000_000
    monkeypatch.setattr("phoneint.cache.time.time", lambda: now)
    cache.set(key, {"ok": True}, ttl_seconds=10)
    assert cache.get(key) == {"ok": True}

    monkeypatch.setattr("phoneint.cache.time.time", lambda: now + 11)
    assert cache.get(key) is None


class _StubAdapter(ReputationAdapter):
    name = "stub"

    def __init__(self) -> None:
        self.calls = 0

    async def check(self, e164: str, *, limit: int = 5) -> list[SearchResult]:
        self.calls += 1
        ts = datetime.now(tz=timezone.utc)
        return [
            SearchResult(
                title="hit",
                url="https://example.invalid",
                snippet=e164,
                timestamp=ts,
                source=self.name,
            )
        ]


async def test_cached_reputation_adapter_hits_cache(tmp_path: Path) -> None:
    cache = SQLiteTTLCache(tmp_path / "cache.sqlite3")
    stub = _StubAdapter()
    cached = CachedReputationAdapter(stub, cache=cache, ttl_seconds=3600)

    r1 = await cached.check("+16502530000")
    r2 = await cached.check("+16502530000")
    assert stub.calls == 1
    assert r1 and r2
    assert r1[0].snippet == r2[0].snippet
