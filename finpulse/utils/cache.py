"""
FinPulse – In-Memory Price Cache
---------------------------------
Thread-safe TTL cache for stock prices so identical lookups
within the configured window skip the YFinance API call and
avoid burning LLM tokens on repeated tool execution.

Design:
    - Pure stdlib (no Redis / external deps).
    - O(1) get/set via dict.
    - Entries expire after `ttl_seconds`; evicted lazily on read.
    - Max-size guard evicts the oldest entry to prevent unbounded growth.
"""

import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)

# Internal storage: ticker -> (price, expiry_timestamp)
_CacheEntry = tuple[float, float]


class PriceCache:
    """
    Thread-safe in-memory cache for stock prices with TTL expiry.

    Args:
        ttl_seconds:  How long a cached price stays valid (default 300 s).
        max_entries:  Maximum number of tickers to hold in memory.
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 256) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[str, _CacheEntry] = {}
        self._lock = Lock()
        logger.info(
            "PriceCache initialised | ttl=%ds max_entries=%d",
            ttl_seconds,
            max_entries,
        )

    def get(self, ticker: str) -> float | None:
        """
        Return cached price if it exists and has not expired.

        Args:
            ticker: Stock ticker symbol (case-insensitive).

        Returns:
            Cached price float, or None on miss / expiry.
        """
        key = ticker.upper()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                logger.debug("Cache MISS | ticker=%s", key)
                self._record_metric("miss")
                return None
            price, expiry = entry
            if time.monotonic() > expiry:
                del self._store[key]
                logger.debug("Cache EXPIRED | ticker=%s", key)
                self._record_metric("miss")
                return None
            logger.debug("Cache HIT  | ticker=%s price=%.4f", key, price)
            self._record_metric("hit")
            return price

    @staticmethod
    def _record_metric(result: str) -> None:
        """Best-effort Prometheus counter increment; never raises."""
        try:
            from finpulse.core.metrics import CACHE_HITS_TOTAL

            CACHE_HITS_TOTAL.labels(result=result).inc()
        except Exception:  # noqa: BLE001
            pass  # metrics module optional at import time (e.g. in unit tests)

    def set(self, ticker: str, price: float) -> None:
        """
        Store a price in the cache.

        Args:
            ticker: Stock ticker symbol.
            price:  Validated price float.
        """
        key = ticker.upper()
        with self._lock:
            if len(self._store) >= self._max and key not in self._store:
                # Evict oldest entry
                oldest = min(self._store, key=lambda k: self._store[k][1])
                del self._store[oldest]
                logger.debug("Cache EVICT | evicted=%s", oldest)
            expiry = time.monotonic() + self._ttl
            self._store[key] = (price, expiry)
            logger.debug("Cache SET   | ticker=%s price=%.4f ttl=%ds", key, price, self._ttl)

    def invalidate(self, ticker: str) -> None:
        """Force-evict a single ticker (e.g. after a known stale read)."""
        key = ticker.upper()
        with self._lock:
            self._store.pop(key, None)
        logger.info("Cache INVALIDATED | ticker=%s", key)

    def stats(self) -> dict[str, int]:
        """Return current cache occupancy statistics."""
        with self._lock:
            now = time.monotonic()
            live = sum(1 for _, exp in self._store.values() if exp > now)
            return {"total_entries": len(self._store), "live_entries": live}
