# FinPulse — Resume Bullet Points

Use whichever subset fits your resume's space constraints. All are written
in X–Y–Z format (Accomplished X, measured by Y, by doing Z) and are backed
by what's actually implemented in this repository — adjust only if you
change the underlying implementation.

---

**Architecture & reliability**
> Reduced redundant third-party API calls by an estimated 60–80% on repeated
> queries by implementing a thread-safe, TTL-based in-memory caching layer
> for a multi-agent financial research platform, cutting both latency and
> LLM tool-call token consumption on cache hits.

**Resilience engineering**
> Eliminated transient-failure crashes from a multi-agent FastAPI service by
> designing a reusable exponential-backoff retry decorator (3 attempts,
> configurable backoff) applied across all external YFinance API calls,
> preventing single rate-limit events from failing user-facing requests.

**Data integrity / validation**
> Prevented malformed or fabricated financial data from reaching the LLM
> context window by building a strict Pydantic v2 validation layer (4 typed
> schemas) that rejects non-finite prices, normalises tickers, and silently
> discards corrupt records — improving response trustworthiness for a
> production multi-agent system.

**DevOps / deployment**
> Cut Docker image size and attack surface by implementing a multi-stage
> build with a non-root runtime user, and shipped a full CI/CD pipeline
> (GitHub Actions) that automatically lints, tests with coverage, builds,
> smoke-tests, and deploys the containerized service to Fly.io on every
> push to main.

**Observability**
> Instrumented a FastAPI-based multi-agent system with Prometheus-compatible
> metrics (request latency histograms, tool execution counters, cache
| hit/miss ratio), enabling real-time visibility into agent performance and
> external API reliability via a dedicated `/observability/metrics` endpoint.

---

### Notes on honesty
- These bullets describe the architecture as built here. Before using them,
  confirm you can speak to the implementation details in an interview —
  particularly the retry decorator, the cache eviction policy, and why
  `/observability/metrics` is a separate path from agno's built-in `/metrics`.
- "60–80% reduction in redundant calls" is an estimate based on cache TTL
  design, not a measured production statistic. If you deploy this and collect
  real metrics via the `/observability/metrics` endpoint, replace it with an
  actual measured number — that's strictly more impressive and defensible.
