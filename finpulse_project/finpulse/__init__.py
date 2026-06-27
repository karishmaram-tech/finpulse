"""
FinPulse Intelligence Platform
--------------------------------
A modular, production-grade multi-agent financial research system
built on agno + Groq, with validated tools, TTL caching, structured
logging, and resilient external-API handling.

Modules:
    config   - environment & settings management
    utils    - logging, caching, retry/resilience helpers
    models   - Pydantic schemas for type-safe data contracts
    tools    - validated, cached, resilient finance tool functions
    agents   - agent and team factory functions
    core     - FastAPI application assembly (execution layer)
"""

__version__ = "1.0.0"
