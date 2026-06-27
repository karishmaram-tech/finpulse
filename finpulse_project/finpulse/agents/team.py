"""
FinPulse – Agent Definitions
------------------------------
Each agent is constructed in its own factory function so it can be
unit-tested, mocked, or swapped independently.  The team coordinator
is assembled from those agents in build_team().

Agent roster:
  • WebResearchAgent  – DuckDuckGo-powered internet research
  • MarketDataAgent   – YFinance financial data with validated tools
  • FinPulseTeam      – Coordinator that routes and synthesises both
"""

from __future__ import annotations

import logging

from agno.agent import Agent
from agno.models.groq import Groq
from agno.team import Team
from agno.tools.duckduckgo import DuckDuckGoTools

from finpulse.config.settings import Settings
from finpulse.tools.finance_tools import (
    get_analyst_recommendations,
    get_company_info,
    get_company_news,
    get_stock_price,
)

logger = logging.getLogger(__name__)


def build_web_agent(settings: Settings) -> Agent:
    """
    Construct the WebResearchAgent.

    Responsible for:
      - Real-time internet searches via DuckDuckGo
      - Breaking financial news retrieval
      - General company background research

    Args:
        settings: Validated application settings.

    Returns:
        Configured agno Agent instance.
    """
    logger.info("Building WebResearchAgent | model=%s", settings.model_id)
    return Agent(
        name="WebResearchAgent",
        id="web-research-agent",
        role=(
            "Search the internet for real-time financial news, "
            "company announcements, and market developments."
        ),
        model=Groq(id=settings.model_id),
        tools=[DuckDuckGoTools()],
        instructions=[
            "Always cite the source URL when referencing an article.",
            "Prioritise news from the last 7 days.",
            "Return results in clear markdown with bullet points.",
        ],
        add_history_to_context=True,
        markdown=True,
    )


def build_market_data_agent(settings: Settings) -> Agent:
    """
    Construct the MarketDataAgent.

    Responsible for:
      - Live stock price lookups (cache-backed)
      - Analyst recommendation summaries
      - Company fundamentals and metadata
      - Recent earnings/news from YFinance

    Args:
        settings: Validated application settings.

    Returns:
        Configured agno Agent instance.
    """
    logger.info("Building MarketDataAgent | model=%s", settings.model_id)
    return Agent(
        name="MarketDataAgent",
        id="market-data-agent",
        role=(
            "Retrieve validated financial data: stock prices, "
            "analyst ratings, company fundamentals, and earnings news."
        ),
        model=Groq(id=settings.model_id),
        tools=[
            get_stock_price,
            get_analyst_recommendations,
            get_company_info,
            get_company_news,
        ],
        instructions=[
            "Always present numerical data in markdown tables.",
            "Include the data timestamp or note if it may be delayed.",
            "If a ticker returns an error, say so clearly — never fabricate prices.",
            "Round prices to 2 decimal places.",
        ],
        add_history_to_context=True,
        markdown=True,
    )


def build_team(settings: Settings) -> Team:
    """
    Assemble the FinPulse coordinator team from its member agents.

    The coordinator routes each user query to the most appropriate
    member(s), then synthesises a unified response.

    Args:
        settings: Validated application settings.

    Returns:
        Configured agno Team instance.
    """
    web_agent = build_web_agent(settings)
    market_agent = build_market_data_agent(settings)

    logger.info(
        "Assembling FinPulse team | members=[%s, %s] | model=%s",
        web_agent.name,
        market_agent.name,
        settings.model_id,
    )

    return Team(
        name="FinPulse Intelligence Team",
        id="finpulse-team",
        model=Groq(id=settings.model_id),
        members=[web_agent, market_agent],
        instructions=[
            "For stock prices, analyst ratings, or company data → delegate to MarketDataAgent.",
            "For news, recent events, or web research → delegate to WebResearchAgent.",
            "For questions combining both data and news → delegate to both in parallel.",
            "Synthesise member responses into a single, well-structured answer.",
            "Never expose internal agent IDs or delegation details to the user.",
        ],
        markdown=True,
    )
