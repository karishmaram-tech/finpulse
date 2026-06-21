"""
FinPulse – Logging Configuration
---------------------------------
Configures the root logger once at startup so every module
that calls logging.getLogger(__name__) inherits the format.
"""

import logging
import sys


def configure_logging(level: str = "INFO", fmt: str | None = None) -> None:
    """
    Configure root logger with a consistent format.

    Args:
        level: Logging level string (DEBUG / INFO / WARNING / ERROR).
        fmt:   Optional custom format string.
    """
    format_str = fmt or "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=format_str,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "openai", "groq", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("finpulse").info("Logging configured | level=%s", level.upper())
