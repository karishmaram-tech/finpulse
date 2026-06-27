"""
FinPulse – Observability & Metrics
--------------------------------------
Prometheus-compatible instrumentation for the FastAPI layer:
  - HTTP request latency histogram, by route and status code
  - In-flight request gauge
  - Agent/team run duration histogram (fed by core/persistence hooks)
  - Tool execution counter (success/failure), fed by tools/finance_tools.py

Exposes a /metrics endpoint in the standard Prometheus text format.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# --- Core HTTP metrics ---
HTTP_REQUEST_DURATION = Histogram(
    "finpulse_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path", "status_code"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)

HTTP_REQUESTS_IN_FLIGHT = Gauge(
    "finpulse_http_requests_in_flight",
    "Number of HTTP requests currently being processed",
)

HTTP_REQUESTS_TOTAL = Counter(
    "finpulse_http_requests_total",
    "Total HTTP requests received",
    ["method", "path", "status_code"],
)

# --- Agent / tool metrics (imported and incremented from tools/agents code) ---
AGENT_RUN_DURATION = Histogram(
    "finpulse_agent_run_duration_seconds",
    "Agent/team run duration in seconds",
    ["entity_type", "entity_id", "status"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60),
)

TOOL_EXECUTIONS_TOTAL = Counter(
    "finpulse_tool_executions_total",
    "Total finance tool executions",
    ["tool_name", "outcome"],  # outcome: success | error | cache_hit
)

CACHE_HITS_TOTAL = Counter(
    "finpulse_cache_hits_total",
    "Price cache hit/miss count",
    ["result"],  # hit | miss
)


def _normalise_path(request: Request) -> str:
    """
    Collapse high-cardinality path params (e.g. /agents/{id}/runs)
    into a templated form so Prometheus labels stay bounded.
    """
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return route.path
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """ASGI middleware recording per-request latency and in-flight count."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        HTTP_REQUESTS_IN_FLIGHT.inc()
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            path = _normalise_path(request)
            HTTP_REQUEST_DURATION.labels(
                method=request.method, path=path, status_code=status_code
            ).observe(duration)
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method, path=path, status_code=status_code
            ).inc()
            HTTP_REQUESTS_IN_FLIGHT.dec()


def get_metrics_payload() -> bytes:
    """Generate the current Prometheus text-format payload synchronously."""
    return bytes(generate_latest())


async def metrics_endpoint() -> Response:
    """FastAPI route handler returning Prometheus-formatted metrics."""
    payload = get_metrics_payload()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST, status_code=200)
