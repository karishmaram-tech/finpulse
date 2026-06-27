"""
FinPulse – Execution Layer
-----------------------------
Wires together settings, logging, agents, observability, and the
AgentOS FastAPI app into a single runnable application. This is the
only module that should be invoked directly (`python -m finpulse.core.app`).
"""

from __future__ import annotations

import logging

from agno.os import AgentOS
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finpulse.agents.team import build_market_data_agent, build_team, build_web_agent
from finpulse.config.settings import Settings, load_settings
from finpulse.core.metrics import MetricsMiddleware, metrics_endpoint
from finpulse.core.persistence import build_engine, init_db
from finpulse.utils.logging_config import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Build and return the fully configured FastAPI application.

    Args:
        settings: Optional pre-loaded settings (mainly for testing).
                  If omitted, settings are loaded from the environment.

    Returns:
        FastAPI application instance, ready to be served by uvicorn.
    """
    settings = settings or load_settings()
    configure_logging(level=settings.log_level)

    logger.info("Initialising FinPulse application | version=%s", "1.0.0")

    # --- Database (optional: falls back to SQLite if DATABASE_URL unset) ---
    try:
        engine = build_engine(settings.database_url)
        init_db(engine)
        app_state_db_ok = True
    except Exception as exc:  # noqa: BLE001
        logger.error("Database initialisation failed, continuing without persistence | %s", exc)
        app_state_db_ok = False

    # --- Agents & Team ---
    web_agent = build_web_agent(settings)
    market_agent = build_market_data_agent(settings)
    team = build_team(settings)

    agent_os = AgentOS(
        agents=[market_agent, web_agent],
        teams=[team],
    )
    app = agent_os.get_app()

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Observability: Prometheus middleware + /metrics endpoint ---
    app.add_middleware(MetricsMiddleware)
    app.add_api_route(
        "/observability/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False
    )

    app.state.db_available = app_state_db_ok

    logger.info(
        "FinPulse application ready | agents=2 teams=1 db=%s | host=%s port=%d",
        "connected" if app_state_db_ok else "unavailable",
        settings.host,
        settings.port,
    )
    return app


def main() -> None:
    """Entry point: load settings, build the app, and serve it with uvicorn."""
    settings = load_settings()
    configure_logging(level=settings.log_level)

    app = create_app(settings)

    import uvicorn

    logger.info("Starting FinPulse server | http://%s:%d", settings.host, settings.port)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
