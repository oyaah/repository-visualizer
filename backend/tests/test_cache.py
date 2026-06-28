from __future__ import annotations

from app.cache import SummaryCache
from app.ai import cache_key


def test_summary_cache_round_trip(tmp_path) -> None:
    cache = SummaryCache(tmp_path / "cache.sqlite")
    key = cache_key("a.py", "hash", "gpt-test")
    assert cache.get(key) is None
    cache.set(key, "a.py", "hash", "v1", "gpt-test", "Summary")
    entry = cache.get(key)
    assert entry is not None
    assert entry.summary == "Summary"
    assert entry.content_hash == "hash"
