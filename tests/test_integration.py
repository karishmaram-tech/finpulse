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
    def test_get_stock_price_returns_validated_schema(self):
        mock_info = MagicMock()
        mock_info.last_price = 298.50
        with patch("finpulse.tools.finance_tools._fetch_fast_info", return_value=mock_info):
            from finpulse.tools.finance_tools import get_stock_price
            result = get_stock_price("AAPL")
        assert result["ticker"] == "AAPL"
        assert result["price"] == 298.50
        assert result["currency"] == "USD"
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
        with patch("finpulse.tools.finance_tools._fetch_fast_info", side_effect=Exception("network error")):
            result = get_stock_price("AAPL")
        assert "error" in result
        assert result["ticker"] == "AAPL"

    def test_get_stock_price_uses_cache_on_second_call(self):
        mock_info = MagicMock()
        mock_info.last_price = 200.0
        with patch("finpulse.tools.finance_tools._fetch_fast_info", return_value=mock_info) as mock_fetch:
            from finpulse.tools.finance_tools import _price_cache, get_stock_price
            _price_cache.invalidate("TSLA")
            get_stock_price("TSLA")
            get_stock_price("TSLA")
        assert mock_fetch.call_count == 1


class TestSettingsIntegration:
    def test_settings_loads_from_env(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test", "FINPULSE_PORT": "8888"}):
            from finpulse.config.settings import load_settings
            settings = load_settings()
        assert settings.groq_api_key == "gsk_test"
        assert settings.port == 8888

    def test_settings_render_port_takes_priority(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test", "PORT": "10000", "FINPULSE_PORT": "7777"}):
            from finpulse.config.settings import load_settings
            settings = load_settings()
        assert settings.port == 10000

    def test_settings_raises_on_missing_groq_key(self):
        env = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            from finpulse.config.settings import load_settings
            with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
                load_settings()


class TestAppIntegration:
    def test_app_creates_successfully(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_dummy"}):
            from finpulse.core.app import create_app
            app = create_app()
        assert app is not None

    def test_app_has_observability_metrics_route(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_dummy"}):
            from finpulse.core.app import create_app
            app = create_app()
            paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/observability/metrics" in paths

    def test_metrics_endpoint_returns_prometheus_format(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_dummy"}):
            from fastapi.testclient import TestClient
            from finpulse.core.app import create_app
            app = create_app()
            client = TestClient(app)
            resp = client.get("/observability/metrics")
        assert resp.status_code == 200
        assert "python_" in resp.text
