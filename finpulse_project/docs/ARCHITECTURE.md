# FinPulse — Technical Architecture Blueprint

## Request Lifecycle

```
┌──────────┐     HTTPS      ┌─────────────────────────────────────────────────┐
│  Client  │ ─────────────▶ │                FastAPI (AgentOS)                 │
│ (cURL /  │                │  ┌─────────────────────────────────────────┐    │
│  React / │ ◀───────────── │  │  MetricsMiddleware                       │    │
│  Browser)│   JSON / SSE   │  │  • records request latency (Histogram)   │    │
└──────────┘                │  │  • increments in-flight gauge            │    │
                             │  └──────────────────┬────────────────────┘    │
                             │                     ▼                          │
                             │  ┌─────────────────────────────────────────┐  │
                             │  │  Route: /agents/{id}/runs                │  │
                             │  │         /teams/{id}/runs                 │  │
                             │  └──────────────────┬────────────────────┘  │
                             └─────────────────────┼──────────────────────┘
                                                    ▼
                             ┌──────────────────────────────────────────────┐
                             │              Agno Agent / Team                │
                             │   FinPulse Intelligence Team (coordinator)    │
                             │   ┌────────────────┐   ┌────────────────┐    │
                             │   │ WebResearch    │   │ MarketData     │    │
                             │   │ Agent          │   │ Agent          │    │
                             │   │ (DuckDuckGo)   │   │ (validated     │    │
                             │   │                │   │  YFinance      │    │
                             │   │                │   │  tools)        │    │
                             │   └────────────────┘   └───────┬────────┘    │
                             └────────────────────────────────┼─────────────┘
                                                                ▼
                             ┌──────────────────────────────────────────────┐
                             │           TTL Price Cache (in-memory)         │
                             │   • 5-min TTL per ticker                      │
                             │   • thread-safe dict + lock                   │
                             │   • HIT → return cached price (skip below)    │
                             │   • MISS → continue to live fetch             │
                             └───────────────────┬────────────────────────┘
                                          (on MISS)│
                                                    ▼
                             ┌──────────────────────────────────────────────┐
                             │       Resilient Tool Layer (retry+backoff)    │
                             │   • get_stock_price                           │
                             │   • get_analyst_recommendations               │
                             │   • get_company_info                          │
                             │   • get_company_news                          │
                             │   retry_with_backoff(max=3, exponential)      │
                             └───────────────────┬────────────────────────┘
                                                    ▼
                             ┌──────────────────────────────────────────────┐
                             │             External APIs                     │
                             │   YFinance  •  DuckDuckGo  •  Groq LLM API    │
                             └───────────────────┬────────────────────────┘
                                                    ▼
                             ┌──────────────────────────────────────────────┐
                             │        Pydantic Validation Layer              │
                             │   StockPrice / CompanyInfo / AnalystRating /  │
                             │   NewsItem — rejects malformed or non-finite  │
                             │   data before it reaches the LLM context      │
                             └───────────────────┬────────────────────────┘
                                                    ▼
                             ┌──────────────────────────────────────────────┐
                             │     PostgreSQL — agent_runs (persistence)     │
                             │   run_id, entity_id, status, duration,        │
                             │   tokens, error_detail, created_at            │
                             │   → powers historical analytics queries       │
                             └──────────────────────────────────────────────┘

                             Cross-cutting: /observability/metrics (Prometheus)
                             exposes HTTP latency, agent run duration, tool
                             execution outcomes, and cache hit/miss ratio.
```

## Layer Responsibilities

| Layer | Module | Responsibility |
|---|---|---|
| Ingress | FastAPI / AgentOS | Routes `/agents/{id}/runs` and `/teams/{id}/runs`; CORS; OpenAPI docs |
| Observability | `core/metrics.py` | Prometheus histograms/counters for latency, tool outcomes, cache hit rate |
| Orchestration | `agents/team.py` | Routes queries to WebResearchAgent or MarketDataAgent; synthesises responses |
| Caching | `utils/cache.py` | Thread-safe TTL cache — short-circuits repeated price lookups |
| Resilience | `utils/resilience.py` | Exponential-backoff retry around all external YFinance calls |
| Validation | `models/schemas.py` | Pydantic v2 contracts reject malformed tool output before LLM consumption |
| Persistence | `core/persistence.py` | PostgreSQL-backed `agent_runs` table for historical query/metric analysis |
| Config | `config/settings.py` | Single source of environment truth; fails loudly on missing secrets |

## Deployment Topology

```
GitHub (main branch)
        │  push
        ▼
GitHub Actions (.github/workflows/deploy.yml)
        │
        ├─▶ lint (ruff check + format --check)
        ├─▶ test (pytest + coverage)
        └─▶ build (multi-stage Docker build, smoke-test container boot)
                       │
                       │  (Render auto-deploys on push to main
                       │   once connected via render.yaml — separate
                       │   from this CI gate, configured in dashboard)
                       ▼
              Render.com (render.yaml)
              ┌─────────────────────────┐
              │ FinPulse container       │
              │ (non-root, free tier,    │
              │  sleeps after 15m idle)  │
              │  :PORT (Render-assigned) │
              └───────────┬─────────────┘
                           │
                  ┌────────┴────────┐
                  ▼                 ▼
            Groq API          SQLite (default) /
         (LLM inference)      Managed Postgres (optional)
```
