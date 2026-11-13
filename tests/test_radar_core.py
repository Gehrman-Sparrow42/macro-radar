"""Unit and integration tests for vendored radar_core inside YATIRIM_RADARI (isolated temp SQLite DBs)."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RADAR_CORE_ROOT = PROJECT_ROOT / "radar_core"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import radar_core.core.database as db  # noqa: E402
from radar_core.config.settings import Settings  # noqa: E402
from radar_core.core.llm_engine import LLMEngine  # noqa: E402
from radar_core.core.models import (  # noqa: E402
    AnalysisResult,
    RawData,
    RawItem,
    StructuredAnalysisOutput,
)
from radar_core.dashboard.helpers import (  # noqa: E402
    filter_results_by_sources,
    format_created_at,
    get_llm_status_caption,
    render_action_pill_html,
    render_intel_card_html,
    safe_http_url,
)
from radar_core.pipelines.dummy_pipeline import (  # noqa: E402
    DummyPipeline,
    FinanceRadarPipeline,
    MarketRadarPipeline,
)


@pytest.fixture()
def temp_db(tmp_path):
    """Initialize an isolated temporary SQLite database and restore _engine afterward."""
    prev_engine = db._engine
    db_file = tmp_path / "test_radar.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    db.init_db(db_url=db_url)
    yield db_url
    db._engine = prev_engine


def test_settings_defaults_no_hardcoded_secrets_and_anchored_sqlite(tmp_path, monkeypatch):
    """Settings defaults must not contain hardcoded API keys and default SQLite URL must anchor to radar_core."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    s = Settings(_env_file=None)
    assert s.GEMINI_API_KEY == ""
    assert s.OPENAI_API_KEY == ""
    assert s.DATABASE_URL.startswith("sqlite:///")
    db_path = Path(s.DATABASE_URL.replace("sqlite:///", ""))
    assert db_path.is_absolute()
    assert db_path.parent == RADAR_CORE_ROOT


def test_dashboard_xss_escaping_and_url_allowlist():
    """Untrusted HTML/JS in fields and non-http(s) URLs must be escaped or blocked."""
    analysis = AnalysisResult(
        raw_data_id=1,
        pipeline_type="dummy<script>",
        severity="CRITICAL",
        summary_title='<img src=x onerror="alert(1)">',
        detailed_reasoning="details",
        action_items=['<svg onload="alert(2)">'],
        created_at=None,
    )
    raw = RawData(
        id=1,
        source_name="<script>evil()</script>",
        url="javascript:alert(document.cookie)",
        title="Raw Title",
        content_text="Content",
        content_hash="abc123",
    )

    card_html = render_intel_card_html(analysis, raw)
    assert "<script>" not in card_html
    assert "<img " not in card_html
    assert "javascript:" not in card_html
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in card_html
    assert "&lt;script&gt;evil()&lt;/script&gt;" in card_html
    assert "Unknown" in card_html

    pill_html = render_action_pill_html(1, analysis.action_items[0])
    assert "<svg" not in pill_html
    assert "&lt;svg onload=&quot;alert(2)&quot;&gt;" in pill_html

    assert safe_http_url("https://example.com/news?a=1") == "https://example.com/news?a=1"
    assert safe_http_url("http://localhost:8000/item") == "http://localhost:8000/item"
    assert safe_http_url("javascript:alert(1)") is None
    assert safe_http_url("data:text/html,<script>alert(1)</script>") is None
    assert format_created_at(datetime(2026, 5, 1, 12, 30, tzinfo=timezone.utc)) == "2026-05-01 12:30 UTC"


def test_dashboard_sidebar_llm_status_and_empty_source_filter():
    """Sidebar LLM status checks either Gemini or OpenAI key; empty source filter yields empty results."""
    assert "OpenAI" in get_llm_status_caption(
        SimpleNamespace(GEMINI_API_KEY="", OPENAI_API_KEY="sk-test", DEFAULT_MODEL="m", OPENAI_MODEL_FAST="gpt-4o-mini")
    )
    assert "Gemini" in get_llm_status_caption(
        SimpleNamespace(GEMINI_API_KEY="gem-test", OPENAI_API_KEY="", DEFAULT_MODEL="m", OPENAI_MODEL_FAST="gpt-4o-mini")
    )
    assert "Heuristic Mode" in get_llm_status_caption(
        SimpleNamespace(GEMINI_API_KEY="", OPENAI_API_KEY="", DEFAULT_MODEL="m", OPENAI_MODEL_FAST="gpt-4o-mini")
    )

    rows = [
        (SimpleNamespace(id=1), SimpleNamespace(source_name="HackerNews_Best")),
        (SimpleNamespace(id=2), SimpleNamespace(source_name="FederalReserve_Press")),
    ]
    assert filter_results_by_sources(rows, ["HackerNews_Best", "FederalReserve_Press"], []) == []
    assert (
        len(filter_results_by_sources(rows, ["HackerNews_Best", "FederalReserve_Press"], ["HackerNews_Best"])) == 1
    )


def test_pipeline_source_scoping_prevents_cross_pipeline_starvation(temp_db):
    """FinanceRadarPipeline must not consume or mark DummyPipeline raw items as processed."""
    with db.get_session() as session:
        db.save_raw_item(
            session,
            RawItem(
                source_name="HackerNews_Best",
                url="https://news.ycombinator.com/item?id=1",
                title="HN startup launch",
                content_text="A new developer tool launch with open source saas revenue growth and more text.",
            ),
        )
        db.save_raw_item(
            session,
            RawItem(
                source_name="FederalReserve_Press",
                url="https://www.federalreserve.gov/newsevents/pressreleases/1.htm",
                title="Fed interest rate policy",
                content_text="Federal Reserve central bank interest rate inflation monetary policy statement text.",
            ),
        )

    fin = FinanceRadarPipeline()
    fin.llm_engine = LLMEngine(gemini_api_key="", openai_api_key="")
    fin_stats = fin.process_queue(batch_size=10)
    assert fin_stats["evaluated"] == 1
    assert fin_stats["analyzed"] == 1

    with db.get_session() as session:
        remaining = db.get_unprocessed_raw_data(session, limit=10)
        assert len(remaining) == 1
        assert remaining[0].source_name == "HackerNews_Best"

    dummy = DummyPipeline()
    dummy.llm_engine = LLMEngine(gemini_api_key="", openai_api_key="")
    dummy_stats = dummy.process_queue(batch_size=10)
    assert dummy_stats["evaluated"] == 1
    assert dummy_stats["analyzed"] == 1


def test_pipeline_llm_error_falls_back_to_heuristic(temp_db):
    """If LLM provider raises during process_queue, BasePipeline falls back to heuristic and marks item processed."""
    with db.get_session() as session:
        db.save_raw_item(
            session,
            RawItem(
                source_name="HackerNews_Best",
                url="https://news.ycombinator.com/item?id=2",
                title="Market opportunity launch",
                content_text="Startup launch with developer tooling and revenue growth opportunity across markets.",
            ),
        )

    dummy = DummyPipeline()
    dummy.llm_engine = MagicMock()
    dummy.llm_engine.gemini_api_key = "fake-gem"
    dummy.llm_engine.openai_api_key = ""
    dummy.llm_engine.pre_filter.return_value = (True, "ok")
    dummy.llm_engine.analyze_structured.side_effect = RuntimeError("API outage")

    stats = dummy.process_queue(batch_size=5)
    assert stats["analyzed"] == 1
    assert stats["errors"] == 0

    with db.get_session() as session:
        assert db.get_unprocessed_raw_data(session, limit=10) == []
        analyses = db.get_analysis_results(session)
        assert len(analyses) == 1
        assert analyses[0][0].metrics["mode"] == "heuristic_fallback_no_api_key"


def test_llm_engine_retries_backoff_and_reasoning_params():
    """LLMEngine retries MAX_RETRIES times with BACKOFF_FACTOR before failover and configures reasoning params."""
    engine = LLMEngine(
        gemini_api_key="gem-key",
        openai_api_key="oa-key",
        openai_model_reasoning="o3-mini",
        max_retries=3,
        backoff_factor=0.5,
    )

    sample_out = StructuredAnalysisOutput(
        severity="INFO",
        summary_title="Test title",
        detailed_reasoning="Test reasoning",
        action_items=["Act"],
        metrics={"relevance_score": 80},
    )

    with (
        patch.object(engine, "_call_openai", side_effect=[RuntimeError("429"), RuntimeError("503"), sample_out]) as mock_oa,
        patch("radar_core.core.llm_engine.time.sleep") as mock_sleep,
    ):
        res = engine.analyze_structured("prompt", task_type="news_analysis")
        assert res.summary_title == "Test title"
        assert mock_oa.call_count == 3
        assert [c.args[0] for c in mock_sleep.call_args_list] == [0.5, 1.0]

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=sample_out.model_dump_json()))]
    )
    engine._openai_client = fake_openai
    engine._call_openai("prompt", StructuredAnalysisOutput, None, 0.2, "o3-mini")

    kwargs = fake_openai.chat.completions.create.call_args.kwargs
    assert "temperature" not in kwargs
    assert kwargs["max_completion_tokens"] == 4000
    assert kwargs["reasoning_effort"] == "low"
    assert kwargs["messages"][0]["role"] == "developer"


def test_single_pass_prompt_formatting():
    """Placeholder tokens inside raw_data title/url must not be substituted by later replacements."""
    raw = RawData(
        source_name="TestSource",
        url="https://example.com/{content}",
        title="Malicious {content} and {url}",
        content_text="REAL_ARTICLE_BODY",
        content_hash="hash1",
    )
    for pipe in (DummyPipeline(), FinanceRadarPipeline(), MarketRadarPipeline()):
        pipe.llm_engine = LLMEngine(gemini_api_key="", openai_api_key="")
        rendered = pipe.build_prompt(raw)
        assert "TITLE: Malicious {content} and {url}" in rendered
        assert "URL: https://example.com/{content}" in rendered
        assert rendered.count("REAL_ARTICLE_BODY") == 1
