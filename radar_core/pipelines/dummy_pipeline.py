"""Concrete pipeline implementations: DummyPipeline, FinanceRadarPipeline, and MarketRadarPipeline."""

import logging
from pathlib import Path
from typing import Any

from radar_core.core.models import RawData
from radar_core.pipelines.base_pipeline import BasePipeline

logger = logging.getLogger("radar_core.pipelines.concrete")

# Locate prompts directory relative to this file
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt_template(filename: str = "dummy_analysis.txt") -> str:
    """Load text prompt template from prompts directory."""
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        "Analyze the following intelligence item:\n"
        "SOURCE: {source}\nURL: {url}\nTITLE: {title}\n\nCONTENT:\n{content}\n\n"
        "Provide structured assessment with severity, summary_title, detailed_reasoning, action_items, and metrics."
    )


class DummyPipeline(BasePipeline):
    """
    Test and demonstration pipeline showcasing end-to-end ingestion, deduplication,
    and structured LLM extraction.
    """

    def __init__(self):
        super().__init__(
            pipeline_name="dummy",
            min_content_length=40,
        )
        self.prompt_template = _load_prompt_template("dummy_analysis.txt")

    def build_prompt(self, raw_data: RawData) -> str:
        prompt = self.prompt_template
        prompt = prompt.replace("{source}", str(raw_data.source_name))
        prompt = prompt.replace("{url}", str(raw_data.url))
        prompt = prompt.replace("{title}", str(raw_data.title))
        prompt = prompt.replace("{content}", str(raw_data.content_text[:4000]))
        return prompt

    @classmethod
    def get_default_sources(cls) -> list[dict[str, Any]]:
        """Return sample source feeds for testing."""
        return [
            {
                "strategy": "rss",
                "source_name": "HackerNews_Best",
                "url": "https://news.ycombinator.com/rss",
                "limit": 5,
            },
            {
                "strategy": "rss",
                "source_name": "TechCrunch_Startups",
                "url": "https://techcrunch.com/category/startups/feed/",
                "limit": 5,
            },
        ]


class FinanceRadarPipeline(BasePipeline):
    """
    Macro & Regulatory Impact Intelligence Radar tracking central banks,
    official gazettes, and monetary policy shifts.
    """

    def __init__(self):
        super().__init__(
            pipeline_name="finance",
            include_keywords=["interest", "rate", "inflation", "central bank", "regulation", "treasury", "yield", "policy", "debt", "tariff", "liquidity"],
            min_content_length=50,
        )
        self.prompt_template = _load_prompt_template("dummy_analysis.txt")

    def build_prompt(self, raw_data: RawData) -> str:
        macro_instructions = (
            "You are a Macro Risk & Portfolio Strategist. Evaluate the regulatory impact, "
            "monetary policy trajectory, and systemic portfolio risks of this item.\n\n"
        )
        prompt = self.prompt_template
        prompt = prompt.replace("{source}", str(raw_data.source_name))
        prompt = prompt.replace("{url}", str(raw_data.url))
        prompt = prompt.replace("{title}", str(raw_data.title))
        prompt = prompt.replace("{content}", str(raw_data.content_text[:4000]))
        return macro_instructions + prompt

    @classmethod
    def get_default_sources(cls) -> list[dict[str, Any]]:
        return [
            {
                "strategy": "rss",
                "source_name": "ECB_Press",
                "url": "https://www.ecb.europa.eu/rss/press.html",
                "limit": 5,
            },
            {
                "strategy": "rss",
                "source_name": "FederalReserve_Press",
                "url": "https://www.federalreserve.gov/feeds/press_all.xml",
                "limit": 5,
            },
        ]


class MarketRadarPipeline(BasePipeline):
    """
    Market Opportunity & Micro-SaaS Radar discovering high-potential software niches,
    arbitrage opportunities, and developer pain points.
    """

    def __init__(self):
        super().__init__(
            pipeline_name="market",
            include_keywords=["saas", "launch", "tool", "ai", "product", "open source", "developer", "revenue", "micro", "startup", "growth"],
            min_content_length=50,
        )
        self.prompt_template = _load_prompt_template("dummy_analysis.txt")

    def build_prompt(self, raw_data: RawData) -> str:
        opportunity_instructions = (
            "You are a Micro-SaaS Venture Builder & Product Discovery Lead. "
            "Identify viable niche tools, unmet user needs, tech stacks, and monetization potential.\n\n"
        )
        prompt = self.prompt_template
        prompt = prompt.replace("{source}", str(raw_data.source_name))
        prompt = prompt.replace("{url}", str(raw_data.url))
        prompt = prompt.replace("{title}", str(raw_data.title))
        prompt = prompt.replace("{content}", str(raw_data.content_text[:4000]))
        return opportunity_instructions + prompt

    @classmethod
    def get_default_sources(cls) -> list[dict[str, Any]]:
        return [
            {
                "strategy": "rss",
                "source_name": "ProductHunt_Frontpage",
                "url": "https://www.producthunt.com/feed",
                "limit": 5,
            },
            {
                "strategy": "rss",
                "source_name": "HackerNews_ShowHN",
                "url": "https://hnrss.org/show",
                "limit": 5,
            },
        ]


def get_pipeline(pipeline_name: str) -> BasePipeline:
    """Pipeline factory returning configured pipeline instance by name."""
    name = pipeline_name.lower().strip()
    if name == "dummy":
        return DummyPipeline()
    elif name == "finance":
        return FinanceRadarPipeline()
    elif name == "market":
        return MarketRadarPipeline()
    else:
        raise ValueError(f"Unknown pipeline: '{pipeline_name}'. Supported: ['dummy', 'finance', 'market']")
