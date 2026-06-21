"""
FinPulse – Configuration & Environment Settings
------------------------------------------------
Centralises all environment variable loading, validation,
and runtime constants so every other module imports from
one place and fails loudly on misconfiguration.
"""

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # Reads .env into os.environ if present; no-op otherwise

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration loaded from environment variables."""

    # --- LLM ---
    groq_api_key: str
    model_id: str = "llama-3.3-70b-versatile"

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 7777
    reload: bool = False

    # --- Cache ---
    price_cache_ttl_seconds: int = 300  # 5 minutes
    cache_max_entries: int = 256

    # --- Database ---
    database_url: str = "sqlite:///finpulse.db"

    # --- Logging ---
    log_level: str = "INFO"
    log_format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # --- Resilience ---
    llm_timeout_seconds: int = 30
    yfinance_timeout_seconds: int = 10
    max_retries: int = 3


def load_settings() -> Settings:
    """
    Load and validate application settings from environment variables.

    Raises:
        EnvironmentError: If a required variable is missing.

    Returns:
        Settings: Validated, frozen settings object.
    """
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise OSError("GROQ_API_KEY is not set. Export it with: export GROQ_API_KEY='gsk_...'")

    settings = Settings(
        groq_api_key=groq_api_key,
        model_id=os.getenv("FINPULSE_MODEL_ID", "llama-3.3-70b-versatile"),
        host=os.getenv("FINPULSE_HOST", "127.0.0.1"),
        # Render (and most PaaS platforms) inject PORT at runtime and require
        # the app to bind to it — it takes priority over our own FINPULSE_PORT.
        port=int(os.getenv("PORT") or os.getenv("FINPULSE_PORT", "7777")),
        reload=os.getenv("FINPULSE_RELOAD", "false").lower() == "true",
        price_cache_ttl_seconds=int(os.getenv("FINPULSE_CACHE_TTL", "300")),
        log_level=os.getenv("FINPULSE_LOG_LEVEL", "INFO"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///finpulse.db"),
    )

    logger.info(
        "Settings loaded | model=%s host=%s port=%d cache_ttl=%ds",
        settings.model_id,
        settings.host,
        settings.port,
        settings.price_cache_ttl_seconds,
    )
    return settings
