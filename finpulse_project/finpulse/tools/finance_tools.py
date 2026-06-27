"""
FinPulse – Validated Finance Tools
------------------------------------
Wraps raw YFinance calls with:
  1. Input sanitisation
  2. Output validation via Pydantic models
  3. TTL cache for price lookups
  4. Structured error handling with typed fallbacks
  5. Execution-time logging for performance visibility

These functions are registered with the agno FinanceAgent as tools.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import yfinance as yf
from pydantic import ValidationError

from finpulse.models.schemas import AnalystRating, CompanyInfo, NewsItem, StockPrice
from finpulse.utils.cache import PriceCache
from finpulse.utils.resilience import retry_with_backoff

logger = logging.getLogger(__name__)

# Module-level cache instance (shared across all tool calls in the process)
_price_cache = PriceCache(ttl_seconds=300, max_entries=256)

# yfinance raises generic Exceptions on rate limits / network errors,
# so we retry any exception up to 3 times with exponential backoff.
_resilient = retry_with_backoff(max_retries=3, base_delay=0.5, exceptions=(Exception,))


def _record_tool_metric(tool_name: str, outcome: str) -> None:
    """Best-effort Prometheus counter increment; never raises (metrics optional)."""
    try:
        from finpulse.core.metrics import TOOL_EXECUTIONS_TOTAL

        TOOL_EXECUTIONS_TOTAL.labels(tool_name=tool_name, outcome=outcome).inc()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ticker_obj(symbol: str, timeout: int = 10) -> yf.Ticker:
    """Return a yfinance Ticker, raising ValueError on blank input."""
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Ticker symbol must not be empty.")
    return yf.Ticker(symbol)


@_resilient
def _fetch_fast_info(symbol: str) -> Any:
    """Resilient wrapper around yfinance's fast_info property (rate-limit prone)."""
    return _ticker_obj(symbol).fast_info


@_resilient
def _fetch_full_info(symbol: str) -> dict[str, Any]:
    """Resilient wrapper around yfinance's full info dict (rate-limit prone)."""
    return _ticker_obj(symbol).info


@_resilient
def _fetch_recommendations(symbol: str) -> Any:
    """Resilient wrapper around yfinance's recommendations summary."""
    return _ticker_obj(symbol).recommendations_summary


@_resilient
def _fetch_news(symbol: str) -> list[dict[str, Any]]:
    """Resilient wrapper around yfinance's news list."""
    return _ticker_obj(symbol).news or []


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def get_stock_price(ticker: str) -> dict[str, Any]:
    """
    Fetch and validate the current stock price for *ticker*.
    Results are cached for 5 minutes to avoid redundant API calls.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").

    Returns:
        Validated StockPrice dict, or an error dict on failure.
    """
    symbol = ticker.strip().upper()
    t0 = time.perf_counter()

    # --- Cache hit ---
    cached_price = _price_cache.get(symbol)
    if cached_price is not None:
        logger.info("get_stock_price | CACHE HIT | %s = $%.2f", symbol, cached_price)
        return StockPrice(ticker=symbol, price=cached_price).model_dump()

    # --- Live fetch (resilient: retries on rate-limit / network errors) ---
    try:
        info: Any = _fetch_fast_info(symbol)
        raw_price: float | None = getattr(info, "last_price", None)

        if raw_price is None:
            raise ValueError(f"YFinance returned no price for {symbol}.")

        validated = StockPrice(ticker=symbol, price=float(raw_price))
        _price_cache.set(symbol, validated.price)

        elapsed = time.perf_counter() - t0
        logger.info(
            "get_stock_price | LIVE FETCH | %s = $%.2f | %.3fs",
            symbol,
            validated.price,
            elapsed,
        )
        _record_tool_metric("get_stock_price", "success")
        return validated.model_dump()

    except ValidationError as exc:
        logger.error("get_stock_price | VALIDATION ERROR | %s | %s", symbol, exc)
        _record_tool_metric("get_stock_price", "error")
        return {"error": "invalid_data", "detail": str(exc), "ticker": symbol}
    except Exception as exc:
        logger.error("get_stock_price | FETCH ERROR | %s | %s", symbol, exc)
        _record_tool_metric("get_stock_price", "error")
        return {"error": "fetch_failed", "detail": str(exc), "ticker": symbol}


def get_analyst_recommendations(ticker: str) -> list[dict[str, Any]]:
    """
    Retrieve analyst recommendation trends for *ticker*.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        List of validated AnalystRating dicts (most recent first),
        or a single-item error list on failure.
    """
    symbol = ticker.strip().upper()
    t0 = time.perf_counter()
    try:
        recs = _fetch_recommendations(symbol)

        if recs is None or recs.empty:
            logger.warning("get_analyst_recommendations | EMPTY | %s", symbol)
            return [{"warning": "no_data", "ticker": symbol}]

        results: list[dict[str, Any]] = []
        for _, row in recs.head(4).iterrows():
            try:
                rating = AnalystRating(
                    period=str(row.get("period", "unknown")),
                    strong_buy=int(row.get("strongBuy", 0)),
                    buy=int(row.get("buy", 0)),
                    hold=int(row.get("hold", 0)),
                    sell=int(row.get("sell", 0)),
                    strong_sell=int(row.get("strongSell", 0)),
                )
                results.append(rating.model_dump())
            except ValidationError as exc:
                logger.warning("get_analyst_recommendations | ROW SKIP | %s", exc)

        elapsed = time.perf_counter() - t0
        logger.info(
            "get_analyst_recommendations | %s | %d rows | %.3fs",
            symbol,
            len(results),
            elapsed,
        )
        _record_tool_metric("get_analyst_recommendations", "success")
        return results

    except Exception as exc:
        logger.error("get_analyst_recommendations | ERROR | %s | %s", symbol, exc)
        _record_tool_metric("get_analyst_recommendations", "error")
        return [{"error": "fetch_failed", "detail": str(exc), "ticker": symbol}]


def get_company_info(ticker: str) -> dict[str, Any]:
    """
    Fetch and validate core company metadata for *ticker*.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        Validated CompanyInfo dict, or an error dict on failure.
    """
    symbol = ticker.strip().upper()
    t0 = time.perf_counter()
    try:
        info: dict[str, Any] = _fetch_full_info(symbol)

        validated = CompanyInfo(
            ticker=symbol,
            name=info.get("longName"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            market_cap=info.get("marketCap"),
            description=(info.get("longBusinessSummary") or "")[:500],
        )

        elapsed = time.perf_counter() - t0
        logger.info("get_company_info | %s | %.3fs", symbol, elapsed)
        _record_tool_metric("get_company_info", "success")
        return validated.model_dump()

    except ValidationError as exc:
        logger.error("get_company_info | VALIDATION ERROR | %s | %s", symbol, exc)
        _record_tool_metric("get_company_info", "error")
        return {"error": "invalid_data", "detail": str(exc), "ticker": symbol}
    except Exception as exc:
        logger.error("get_company_info | ERROR | %s | %s", symbol, exc)
        _record_tool_metric("get_company_info", "error")
        return {"error": "fetch_failed", "detail": str(exc), "ticker": symbol}


def get_company_news(ticker: str, max_items: int = 5) -> list[dict[str, Any]]:
    """
    Retrieve recent news headlines for *ticker*.

    Args:
        ticker:    Stock ticker symbol.
        max_items: Maximum number of articles to return.

    Returns:
        List of validated NewsItem dicts, or a single-item error list.
    """
    symbol = ticker.strip().upper()
    t0 = time.perf_counter()
    try:
        raw_news = _fetch_news(symbol)

        results: list[dict[str, Any]] = []
        for article in raw_news[:max_items]:
            try:
                item = NewsItem(
                    title=article.get("title", "No title"),
                    publisher=article.get("publisher"),
                    link=article.get("link"),
                    summary=article.get("summary"),
                )
                results.append(item.model_dump())
            except ValidationError as exc:
                logger.warning("get_company_news | ITEM SKIP | %s", exc)

        elapsed = time.perf_counter() - t0
        logger.info(
            "get_company_news | %s | %d articles | %.3fs",
            symbol,
            len(results),
            elapsed,
        )
        _record_tool_metric("get_company_news", "success")
        return results

    except Exception as exc:
        logger.error("get_company_news | ERROR | %s | %s", symbol, exc)
        _record_tool_metric("get_company_news", "error")
        return [{"error": "fetch_failed", "detail": str(exc), "ticker": symbol}]
