# FinPulse Intelligence Platform

![CI](https://github.com/karishmaram-tech/finpulse/actions/workflows/deploy.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Docker](https://img.shields.io/badge/docker-multi--stage-blue.svg)
![Deploy](https://img.shields.io/badge/deploy-Render-purple.svg)


ðŸ”— **[Live API](https://finpulse-intelligence-c819.onrender.com)** Â· ðŸ–¥ï¸ **[Live Dashboard](https://karishmaram-tech.github.io/finpulse/)**

> Free-tier hosting: the API sleeps after 15 min idle â€” first request may take 30-60s to wake up.


A production-deployed, modular multi-agent financial research system. Built on [agno](https://github.com/agno-agi/agno) and Groq's `llama-3.3-70b-versatile`, FinPulse coordinates specialized agents to deliver validated market data, analyst sentiment, and real-time financial news â€” with the engineering discipline (typed contracts, caching, retries, observability, CI/CD) of a real production service, not a wrapper script.

---

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full request-lifecycle diagram (Client â†’ FastAPI â†’ TTL Cache â†’ Agno Agents â†’ Resilient Tools â†’ External APIs â†’ Postgres).

```
finpulse/
â”œâ”€â”€ agents/team.py          # Agent + Team factory functions
â”œâ”€â”€ config/settings.py      # Environment loading & validation
â”œâ”€â”€ core/
â”‚   â”œâ”€â”€ app.py               # Execution layer â€” wires everything into FastAPI
â”‚   â”œâ”€â”€ metrics.py           # Prometheus middleware + /observability/metrics
â”‚   â””â”€â”€ persistence.py       # PostgreSQL run-history persistence
â”œâ”€â”€ models/schemas.py        # Pydantic v2 data contracts
â”œâ”€â”€ tools/finance_tools.py   # Validated, cached, resilient YFinance tools
â””â”€â”€ utils/
    â”œâ”€â”€ cache.py              # Thread-safe in-memory TTL cache
    â”œâ”€â”€ logging_config.py     # Structured logging setup
    â””â”€â”€ resilience.py         # Retry-with-backoff decorator
tests/                        # pytest unit tests (cache, schemas, resilience)
.github/workflows/deploy.yml  # CI/CD: lint â†’ test â†’ build â†’ deploy
Dockerfile                    # Multi-stage, non-root production image
fly.toml                      # Fly.io infrastructure-as-code
docs/
â”œâ”€â”€ ARCHITECTURE.md            # Full request-lifecycle diagram
â””â”€â”€ RESUME_BULLETS.md          # X-Y-Z resume bullet reference
main.py
requirements.txt
requirements-dev.txt
```

---

## Agent roster

- **WebResearchAgent** â€” DuckDuckGo-powered search for breaking news and company announcements
- **MarketDataAgent** â€” validated YFinance tool calls for prices, analyst ratings, fundamentals, and news
- **FinPulse Intelligence Team** â€” coordinator that routes each query to the right agent(s) and synthesises a unified answer

---

## Engineering highlights

**Resilience.** `utils/resilience.py`'s `retry_with_backoff` decorator wraps every YFinance call. Transient rate limits or network blips retry up to 3 times with exponential backoff before surfacing an error.

**Caching.** `utils/cache.py` is a thread-safe, TTL-based in-memory cache. Identical stock price lookups within a 5-minute window are served from memory, skipping the YFinance round-trip.

**Validation.** `models/schemas.py` defines strict Pydantic models for every tool output â€” non-finite prices are rejected, tickers normalised, malformed rows skipped rather than corrupting the response.

**Structured logging.** Every settings load, agent build, cache hit/miss, retry attempt, and tool execution time is logged through Python's `logging` module â€” zero `print()` statements.

**Persistence.** `core/persistence.py` stores every agent/team run (status, duration, token counts, errors) in PostgreSQL, replacing volatile in-memory history with queryable analytics data. Falls back to local SQLite when `DATABASE_URL` is unset, so local dev needs zero setup.

**Observability.** `core/metrics.py` exposes Prometheus-format metrics at `/observability/metrics` â€” HTTP request latency histograms (by path/method/status), in-flight request count, agent run duration, tool execution outcomes, and cache hit/miss ratio.

**Containerization.** The `Dockerfile` is a multi-stage build: dependencies compile in a `builder` stage, only the resulting wheels ship to a slim `runtime` stage that runs as a dedicated non-root user with no shell.

**CI/CD.** `.github/workflows/deploy.yml` runs on every push to `main`: ruff lint + format check â†’ pytest with coverage â†’ Docker build + container boot smoke-test â†’ `flyctl deploy`. Each stage gates the next.

---

## Getting started (local)

### 1. Clone and install

```bash
git clone <your-repo-url>
cd finpulse
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your Groq key (get one free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=gsk_your_key_here
```

`DATABASE_URL` is optional â€” omit it to use a local SQLite file automatically.

### 3. Run

```bash
python main.py
```

The server starts on `http://127.0.0.1:7777`. Interactive API docs: `http://127.0.0.1:7777/docs`. Prometheus metrics: `http://127.0.0.1:7777/observability/metrics`.

### 4. Query an agent directly

```bash
curl -X POST "http://127.0.0.1:7777/agents/market-data-agent/runs" \
  -d "message=What is the current stock price of AAPL?" \
  -d "stream=false"
```

### 5. Query the full team

```bash
curl -X POST "http://127.0.0.1:7777/teams/finpulse-team/runs" \
  -d "message=Compare Apple and Tesla, including recent news" \
  -d "stream=false"
```

---

## Running tests & linting

```bash
pip install -r requirements-dev.txt
ruff check finpulse/ main.py tests/
ruff format --check finpulse/ main.py tests/
pytest tests/ -v --cov=finpulse
```

---

## Deploying to production

### Render.com (recommended â€” free tier, no credit card required)

1. Push this repo to GitHub (see steps above).
2. Go to [render.com](https://render.com) and sign up (no card needed for the free tier).
3. Click **New â†’ Blueprint**, connect your GitHub repo. Render auto-detects `render.yaml`.
4. In the service settings, add your secret environment variable:
   - `GROQ_API_KEY` â†’ your Groq key
5. Click **Apply** â€” Render builds the Dockerfile and deploys.

**Note:** the free tier sleeps after 15 minutes of inactivity and takes ~30-60s to wake up on the next request â€” fine for a portfolio demo, not for production traffic. Render auto-deploys on every push to `main` once connected.

### Docker (local build/run, or any container host)

```bash
docker build -t finpulse .
docker run -p 7777:7777 \
  -e GROQ_API_KEY=gsk_your_key \
  -e DATABASE_URL=postgresql+psycopg://user:pass@host:5432/finpulse \
  finpulse
```

---

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Groq API key |
| `DATABASE_URL` | `sqlite:///finpulse.db` | PostgreSQL or SQLite connection string |
| `FINPULSE_MODEL_ID` | `llama-3.3-70b-versatile` | LLM used by all agents |
| `FINPULSE_HOST` | `127.0.0.1` | Bind address |
| `FINPULSE_PORT` | `7777` | Bind port |
| `FINPULSE_RELOAD` | `false` | Enable uvicorn auto-reload (dev only) |
| `FINPULSE_CACHE_TTL` | `300` | Price cache time-to-live, in seconds |
| `FINPULSE_LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Extending FinPulse

- **New data source** â†’ add a validated tool function in `tools/`, define its Pydantic schema in `models/schemas.py`, register it on an agent in `agents/team.py`.
- **New agent** â†’ write a `build_*_agent(settings)` factory in `agents/team.py`, add it to `build_team()`'s member list and to `core/app.py`'s `AgentOS(agents=[...])` call.
- **New metric** â†’ add a `Counter`/`Histogram` in `core/metrics.py`, increment it where the event occurs (mirrors the pattern in `utils/cache.py` and `tools/finance_tools.py`).

---

## License

MIT

