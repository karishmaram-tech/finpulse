"""
FinPulse – Resilience Utilities
----------------------------------
Decorators that add retry-with-backoff and timeout protection
around flaky external calls (LLM provider, YFinance), so a single
transient failure (rate limit, network blip) doesn't crash a run.
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    Retry a function call with exponential backoff on failure.

    Args:
        max_retries: Maximum number of attempts before giving up.
        base_delay:  Initial delay in seconds; doubles each retry.
        exceptions:  Exception types that trigger a retry.

    Returns:
        Decorated function that retries transparently and logs each attempt.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt == max_retries:
                        logger.error(
                            "%s | FAILED after %d attempts | %s",
                            func.__name__,
                            attempt,
                            exc,
                        )
                        raise
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "%s | attempt %d/%d failed (%s) | retrying in %.1fs",
                        func.__name__,
                        attempt,
                        max_retries,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
            # Unreachable, but keeps type checkers happy
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


class EnvironmentValidationError(RuntimeError):
    """Raised when a required environment variable is missing or invalid."""


class ToolExecutionError(RuntimeError):
    """Raised when a tool call fails after exhausting retries."""
