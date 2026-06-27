"""
FinPulse – Type-Safe Data Models
----------------------------------
Pydantic v2 models that define the shape of every data payload
flowing between tools, agents, and the API layer.
Strict validation here means bad data is caught at the boundary,
not silently passed downstream to the LLM.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Tool output models
# ---------------------------------------------------------------------------


class StockPrice(BaseModel):
    """Validated output from the get_current_stock_price tool."""

    ticker: str = Field(..., min_length=1, max_length=10)
    price: float = Field(..., gt=0.0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    source: str = Field(default="yfinance")

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("price")
    @classmethod
    def price_is_finite(cls, v: float) -> float:
        import math

        if not math.isfinite(v):
            raise ValueError(f"Price must be a finite number, got {v}")
        return round(v, 4)


class AnalystRating(BaseModel):
    """Single analyst recommendation entry."""

    period: str
    strong_buy: int = Field(default=0, ge=0)
    buy: int = Field(default=0, ge=0)
    hold: int = Field(default=0, ge=0)
    sell: int = Field(default=0, ge=0)
    strong_sell: int = Field(default=0, ge=0)


class CompanyInfo(BaseModel):
    """Core company metadata returned by the finance tool."""

    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = Field(default=None, ge=0)
    description: str | None = None

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, v: str) -> str:
        return v.upper().strip()


class NewsItem(BaseModel):
    """Single news article from the finance tool."""

    title: str
    publisher: str | None = None
    link: str | None = None
    summary: str | None = None


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------


class AgentQuery(BaseModel):
    """Incoming query to any FinPulse agent endpoint."""

    message: str = Field(..., min_length=1, max_length=2048)
    session_id: str | None = None
    stream: bool = False

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        return v.strip()


class AgentResponse(BaseModel):
    """Standardised response envelope returned to callers."""

    run_id: str
    status: str
    content: str
    model: str | None = None
    duration_seconds: float | None = None
    cached: bool = False
