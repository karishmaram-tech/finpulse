"""Unit tests for finpulse.models.schemas validation rules."""

import pytest
from pydantic import ValidationError

from finpulse.models.schemas import AgentQuery, CompanyInfo, StockPrice


def test_stock_price_normalises_ticker_case():
    sp = StockPrice(ticker="aapl", price=100.0)
    assert sp.ticker == "AAPL"


def test_stock_price_rejects_negative_price():
    with pytest.raises(ValidationError):
        StockPrice(ticker="AAPL", price=-10.0)


def test_stock_price_rejects_zero_price():
    with pytest.raises(ValidationError):
        StockPrice(ticker="AAPL", price=0.0)


def test_stock_price_rounds_to_four_decimals():
    sp = StockPrice(ticker="AAPL", price=298.456789)
    assert sp.price == 298.4568


def test_company_info_normalises_ticker():
    info = CompanyInfo(ticker="msft")
    assert info.ticker == "MSFT"


def test_agent_query_strips_whitespace():
    q = AgentQuery(message="   hello world   ")
    assert q.message == "hello world"


def test_agent_query_rejects_empty_message():
    with pytest.raises(ValidationError):
        AgentQuery(message="")
