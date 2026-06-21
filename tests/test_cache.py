"""Unit tests for finpulse.utils.cache.PriceCache."""

import time

from finpulse.utils.cache import PriceCache


def test_set_then_get_returns_value():
    cache = PriceCache(ttl_seconds=60, max_entries=10)
    cache.set("AAPL", 298.50)
    assert cache.get("AAPL") == 298.50


def test_get_is_case_insensitive():
    cache = PriceCache(ttl_seconds=60, max_entries=10)
    cache.set("aapl", 100.0)
    assert cache.get("AAPL") == 100.0


def test_miss_returns_none():
    cache = PriceCache(ttl_seconds=60, max_entries=10)
    assert cache.get("MISSING") is None


def test_entry_expires_after_ttl():
    cache = PriceCache(ttl_seconds=0, max_entries=10)
    cache.set("AAPL", 100.0)
    time.sleep(0.05)
    assert cache.get("AAPL") is None


def test_max_entries_evicts_oldest():
    cache = PriceCache(ttl_seconds=60, max_entries=2)
    cache.set("A", 1.0)
    time.sleep(0.01)
    cache.set("B", 2.0)
    time.sleep(0.01)
    cache.set("C", 3.0)  # should evict A
    stats = cache.stats()
    assert stats["total_entries"] == 2


def test_invalidate_removes_entry():
    cache = PriceCache(ttl_seconds=60, max_entries=10)
    cache.set("AAPL", 100.0)
    cache.invalidate("AAPL")
    assert cache.get("AAPL") is None
