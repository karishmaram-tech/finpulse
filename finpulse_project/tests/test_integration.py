"""
Integration tests for FinPulse agents and tools.
Groq API calls are mocked so tests run in CI without real credentials.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("GROQ_API_KEY", "gsk_test_mock_key_for_ci")


class TestFinanceToolsIntegration:
    """Integration tests for finance tools with mocked yfinance."""

    def test_get_stock_price_returns_validated_schema(self):
        mock_info = MagicMock()
        mock_info.last_price = 298.50

        with patch("finpulse.tools.finance_tools._fetch_fast_info", return_value=mock_info):
            from finpulse.tools.finance_tools import get_stock_price

            result = get_stock_price("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["price"] == 298.50
        assert result["currency"] == "USD"
        assert result["source"] == "yfinance"
        assert "error" not in result

    def test_get_stock_price_normalises_lowercase_ticker(self):
        mock_info = MagicMock()
        mock_info.last_price = 150.0

        with patch("finpulse.tools.finance_tools._fetch_fast_info", return_value=mock_info):
            from finpulse.tools.finance_tools import get_stock_price

            result = get_stock_price("msft")

        assert result["ticker"] == "MSFT"

    def test_get_stock_price_returns_error_dict_on_failure(self):
        from finpulse.tools.finance_tools import _price_cache, get_stock_price

        _price_cache.invalidate("AAPL")
        with patch(
            "finpulse.tools.finance_tools._fetch_fast_info",
            side_effect=Exception("network error"),
        ):
            result = get_stock_price("AAPL")

        assert "error" in result
        assert result["ticker"] == "AAPL"

    def test_get_stock_price_uses_cache_on_second_call(self):
        mock_info = MagicMock()
        mock_info.last_price = 200.0

        with patch(
            "finpulse.tools.finance_tools._fetch_fast_info", return_value=mock_info
        ) as mock_fetch:
            from finpulse.tools.finance_tools import _price_cache, get_stock_price

            _price_cache.invalidate("TSLA")
            get_stock_price("TSLA")
            get_stock_price("TSLA")

        assert mock_fetch.call_count == 1

    def test_get_company_info_returns_validated_schema(self):
        mock_info = {
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "marketCap": 3_000_000_000_000,
            "longBusinessSummary": "Apple designs consumer electronics.",
        }

        with patch("finpulse.tools.finance_tools._fetch_full_info", return_value=mock_info):
            from finpulse.tools.finance_tools import get_company_info

            result = get_company_info("AAPL")

        assert result["ticker"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["sector"] == "Technology"
        assert "error" not in result

    def test_get_company_news_returns_list(self):
        mock_news = [
            {"title": "Apple hits new high", "publisher": "Reuters", "link": "https://example.com"},
            {
                "title": "iPhone demand strong",
                "publisher": "Bloomberg",
                "link": "https://example.com/2",
            },
        ]

        with patch("finpulse.tools.finance_tools._fetch_news", return_value=mock_news):
            from finpulse.tools.finance_tools import get_company_news

            result = get_company_news("AAPL")

        assert len(result) == 2
        assert result[0]["title"] == "Apple hits new high"

    def test_get_analyst_recommendations_handles_empty_dataframe(self):
        import pandas as pd

        with patch(
            "finpulse.tools.finance_tools._fetch_recommendations",
            return_value=pd.DataFrame(),
        ):
            from finpulse.tools.finance_tools import get_analyst_recommendations

            result = get_analyst_recommendations("AAPL")

        assert len(result) == 1
        assert "warning" in result[0]


class TestSettingsIntegration:
    """Integration tests for settings loading and validation."""

    def test_settings_loads_from_env(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test", "FINPULSE_PORT": "8888"}):
            from finpulse.config.settings import load_settings

            settings = load_settings()

        assert settings.groq_api_key == "gsk_test"
        assert settings.port == 8888

    def test_settings_render_port_takes_priority(self):
        with patch.dict(
            os.environ,
            {"GROQ_API_KEY": "gsk_test", "PORT": "10000", "FINPULSE_PORT": "7777"},
        ):
            from finpulse.config.settings import load_settings

            settings = load_settings()

        assert settings.port == 10000

    def test_settings_raises_on_missing_groq_key(self):
        env = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            from finpulse.config.settings import load_settings

            with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
                load_settings()

    def test_settings_sqlite_fallback_when_no_database_url(self):
        env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        env["GROQ_API_KEY"] = "gsk_test"
        with patch.dict(os.environ, env, clear=True):
            from finpulse.config.settings import load_settings

            settings = load_settings()

        assert "sqlite" in settings.database_url


class TestAppIntegration:
    """Integration tests for the FastAPI application assembly."""

    def test_app_creates_successfully(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_dummy"}):
            from finpulse.core.app import create_app

            app = create_app()

        assert app is not None
        assert hasattr(app, "routes")

    def test_app_has_observability_metrics_route(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_dummy"}):
            from finpulse.core.app import create_app

            app = create_app()
            paths = [r.path for r in app.routes if hasattr(r, "path")]

        assert "/observability/metrics" in paths

    def test_app_db_state_set(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_dummy"}):
            from finpulse.core.app import create_app

            app = create_app()

        assert hasattr(app.state, "db_available")

    def test_metrics_endpoint_returns_prometheus_format(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_dummy"}):
            from fastapi.testclient import TestClient

            from finpulse.core.app import create_app

            app = create_app()
            client = TestClient(app)
            resp = client.get("/observability/metrics")

        assert resp.status_code == 200
        assert "finpulse_" in resp.text or "python_" in resp.text
