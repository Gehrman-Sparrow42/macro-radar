"""Abstract BasePipeline orchestrating the fetch -> deduplicate -> prefilter -> analyze -> persist cycle."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from radar_core.core.database import (
    get_session,
    get_unprocessed_raw_data,
    mark_as_processed,
    save_analysis_result,
    save_raw_item,
)
from radar_core.core.fetchers.base import FetcherRegistry
from radar_core.core.llm_engine import LLMEngine
from radar_core.core.models import (
    AnalysisResult,
    RawData,
    StructuredAnalysisOutput,
)

logger = logging.getLogger("radar_core.pipeline")


class BasePipeline(ABC):
    """Template Method pipeline orchestrating the end-to-end Radar workflow."""

    def __init__(
        self,
        pipeline_name: str,
        llm_engine: LLMEngine | None = None,
        include_keywords: list[str] | None = None,
        exclude_keywords: list[str] | None = None,
        min_content_length: int = 60,
    ):
        self.pipeline_name = pipeline_name
        self.llm_engine = llm_engine or LLMEngine()
        self.include_keywords = include_keywords
        self.exclude_keywords = exclude_keywords
        self.min_content_length = min_content_length

    # -----------------------------------------------------------------------
    # Step 1: Ingestion & Deduplication
    # -----------------------------------------------------------------------
    def ingest(self, source_configs: list[dict[str, Any]]) -> dict[str, int]:
        """
        Execute ingestion strategies for all provided source configurations.
        Persists novel items and ignores duplicates via SHA-256 content hashing.
        """
        stats = {"total_fetched": 0, "new_saved": 0, "duplicates_skipped": 0}

        with get_session() as session:
            for config in source_configs:
                strategy = config.get("strategy", "rss")
                try:
                    fetcher = FetcherRegistry.get_fetcher(strategy)
                    raw_items = fetcher.fetch(config)
                    stats["total_fetched"] += len(raw_items)

                    for item in raw_items:
                        _, is_new = save_raw_item(session, item)
                        if is_new:
                            stats["new_saved"] += 1
                        else:
                            stats["duplicates_skipped"] += 1

                except Exception as exc:
                    logger.error(
                        "Error running fetcher '%s' for source '%s': %s",
                        strategy,
                        config.get("source_name", "unknown"),
                        exc,
                    )

        logger.info(
            "Ingestion completed for [%s]: Fetched=%d, New=%d, Duplicates=%d",
            self.pipeline_name,
            stats["total_fetched"],
            stats["new_saved"],
            stats["duplicates_skipped"],
        )
        return stats

    # -----------------------------------------------------------------------
    # Step 2: Prompt Construction (Subclass Specific)
    # -----------------------------------------------------------------------
    @abstractmethod
    def build_prompt(self, raw_data: RawData) -> str:
        """Construct downstream-specific LLM analysis prompt."""
        pass

    # -----------------------------------------------------------------------
    # Step 3: Analysis & Processing
    # -----------------------------------------------------------------------
    def process_queue(self, batch_size: int = 20) -> dict[str, int]:
        """
        Process pending unprocessed RawData items through pre-filter and LLM extraction.
        """
        stats = {"evaluated": 0, "analyzed": 0, "prefiltered_skipped": 0, "errors": 0}

        with get_session() as session:
            unprocessed_items = get_unprocessed_raw_data(session, limit=batch_size)

            for item in unprocessed_items:
                stats["evaluated"] += 1

                # Zero-cost pre-filter hook
                should_run, reason = self.llm_engine.pre_filter(
                    text=item.content_text,
                    include_keywords=self.include_keywords,
                    exclude_keywords=self.exclude_keywords,
                    min_length=self.min_content_length,
                )

                if not should_run:
                    logger.info("Pre-filter skipped item [id=%d, title=%s]: %s", item.id, item.title[:30], reason)
                    mark_as_processed(session, item.id)
                    stats["prefiltered_skipped"] += 1
                    continue

                # Run LLM extraction
                try:
                    prompt = self.build_prompt(item)
                    structured_output = self._run_llm_analysis(item, prompt)

                    # Persist AnalysisResult
                    analysis_record = AnalysisResult(
                        raw_data_id=item.id,
                        pipeline_type=self.pipeline_name,
                        severity=structured_output.severity,
                        summary_title=structured_output.summary_title,
                        detailed_reasoning=structured_output.detailed_reasoning,
                        action_items=structured_output.action_items,
                        metrics=structured_output.metrics,
                    )
                    save_analysis_result(session, analysis_record)
                    mark_as_processed(session, item.id)
                    stats["analyzed"] += 1

                except Exception as exc:
                    logger.error("Failed LLM analysis for item [id=%d]: %s", item.id, exc)
                    stats["errors"] += 1

        logger.info(
            "Processing queue completed for [%s]: Evaluated=%d, Analyzed=%d, Skipped=%d, Errors=%d",
            self.pipeline_name,
            stats["evaluated"],
            stats["analyzed"],
            stats["prefiltered_skipped"],
            stats["errors"],
        )
        return stats

    def _run_llm_analysis(self, item: RawData, prompt: str) -> StructuredAnalysisOutput:
        """
        Execute structured LLM analysis. Provides heuristic fallback if API key is unconfigured.
        """
        if not (getattr(self.llm_engine, "gemini_api_key", None) or getattr(self.llm_engine, "openai_api_key", None)):
            logger.warning("No LLM API keys detected. Utilizing heuristic analytical fallback.")
            return self._heuristic_fallback_analysis(item)

        try:
            return self.llm_engine.analyze_structured(
                prompt=prompt,
                response_schema=StructuredAnalysisOutput,
                task_type="news_analysis",
            )
        except Exception as exc:
            logger.warning("LLM extraction failed (%s). Falling back to dual-layer heuristic analysis.", exc)
            return self._heuristic_fallback_analysis(item)

    def _heuristic_fallback_analysis(self, item: RawData) -> StructuredAnalysisOutput:
        """Heuristic offline analysis generator for local testing without active API credits."""
        lower_txt = (item.title + " " + item.content_text).lower()

        # Determine severity heuristic
        if any(w in lower_txt for w in ["crisis", "emergency", "breach", "sanction", "critical", "default", "collapse"]):
            sev = "CRITICAL"
        elif any(w in lower_txt for w in ["opportunity", "saas", "launch", "revenue", "growth", "arbitrage", "hack"]):
            sev = "OPPORTUNITY"
        elif any(w in lower_txt for w in ["risk", "warning", "rate hike", "inflation", "investigation", "slowdown"]):
            sev = "WARNING"
        else:
            sev = "INFO"

        summary = f"Signal: {item.title[:100]}"
        reasoning = (
            f"Automated heuristic assessment of incoming item from source '{item.source_name}'. "
            f"Identified topical signals relevant to {self.pipeline_name.upper()} radar. "
            f"Content snippet: {item.content_text[:250]}..."
        )

        actions = [
            f"Review full briefing on {item.source_name}",
            "Validate signal against secondary market or regulatory indicators",
            "Update portfolio or product monitoring watchlist",
        ]

        metrics = {
            "relevance_score": 82,
            "urgency": "Medium" if sev in ["WARNING", "OPPORTUNITY"] else ("High" if sev == "CRITICAL" else "Low"),
            "tags": [self.pipeline_name, item.source_name.lower(), sev.lower()],
            "mode": "heuristic_fallback_no_api_key",
        }

        return StructuredAnalysisOutput(
            severity=sev,
            summary_title=summary,
            detailed_reasoning=reasoning,
            action_items=actions,
            metrics=metrics,
        )

    # -----------------------------------------------------------------------
    # Unified Execution Method
    # -----------------------------------------------------------------------
    def run(
        self,
        source_configs: list[dict[str, Any]] | None = None,
        batch_size: int = 20,
    ) -> dict[str, Any]:
        """Run full cycle: Ingestion followed by processing."""
        ingest_stats = {}
        if source_configs:
            ingest_stats = self.ingest(source_configs)

        process_stats = self.process_queue(batch_size=batch_size)
        return {"ingestion": ingest_stats, "processing": process_stats}
