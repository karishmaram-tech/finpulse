"""
FinPulse – Persistence Layer
-------------------------------
PostgreSQL-backed storage for agent run history, replacing the
default volatile in-memory session store. Falls back gracefully
to SQLite for local development when DATABASE_URL is unset.

This module owns:
  - SQLAlchemy engine/session setup
  - The AgentRun ORM model (one row per agent/team execution)
  - A lightweight repository function to persist run metadata
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all FinPulse ORM models."""


class AgentRun(Base):
    """
    Persisted record of a single agent or team execution.

    Captures enough metadata to power historical analytics
    (latency trends, error rates, most-queried tickers) without
    storing full conversation payloads.
    """

    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    entity_type = Column(String(16), nullable=False)  # "agent" | "team"
    entity_id = Column(String(64), nullable=False, index=True)
    status = Column(String(16), nullable=False)  # COMPLETED | ERROR
    model_id = Column(String(64), nullable=True)
    input_message = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)


def build_engine(database_url: str):
    """
    Create a SQLAlchemy engine for the given connection string.

    Args:
        database_url: PostgreSQL URL (postgresql+psycopg://...) or
                       SQLite fallback (sqlite:///finpulse.db).

    Returns:
        Configured SQLAlchemy Engine.
    """
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(
        database_url,
        pool_pre_ping=True,  # detect stale connections before using them
        pool_size=5,
        max_overflow=10,
        connect_args=connect_args,
    )
    logger.info(
        "Database engine created | dialect=%s",
        engine.dialect.name,
    )
    return engine


def init_db(engine) -> None:
    """Create all tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema verified/initialised")


def get_session_factory(engine) -> sessionmaker:
    """Return a configured sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def record_run(
    session: Session,
    *,
    run_id: str,
    entity_type: str,
    entity_id: str,
    status: str,
    model_id: str | None = None,
    input_message: str | None = None,
    duration_seconds: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_detail: str | None = None,
) -> None:
    """
    Persist a single agent/team run to the database.

    Designed to be called from FastAPI middleware after each
    /agents/*/runs or /teams/*/runs request completes, so failures
    here must never raise — they are logged and swallowed to avoid
    breaking the user-facing request.

    Args:
        session: Active SQLAlchemy session.
        run_id: Unique run identifier from agno.
        entity_type: "agent" or "team".
        entity_id: The agent_id or team_id that handled the run.
        status: "COMPLETED" or "ERROR".
        model_id: LLM model used.
        input_message: The user's original query (truncated upstream if huge).
        duration_seconds: Wall-clock run duration.
        input_tokens: Prompt tokens consumed.
        output_tokens: Completion tokens generated.
        error_detail: Error message, if status == "ERROR".
    """
    try:
        row = AgentRun(
            run_id=run_id,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            model_id=model_id,
            input_message=(input_message or "")[:2000],
            duration_seconds=duration_seconds,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error_detail=(error_detail or "")[:2000] if error_detail else None,
        )
        session.add(row)
        session.commit()
        logger.debug("Run persisted | run_id=%s entity=%s status=%s", run_id, entity_id, status)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.error("Failed to persist run | run_id=%s | %s", run_id, exc)
