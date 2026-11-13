"""Comprehensive tests for YATIRIM_RADARI security, performance, TLS, and ported radar_core fixes."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import radar_core.core.database as db
from radar_core.core.llm_engine import LLMEngine
from radar_core.core.models import (
    AnalysisResult,
    RawData,
    RawItem,
    StructuredAnalysisOutput,
)
from radar_core.dashboard.helpers import (
    filter_results_by_sources,
    render_intel_card_html,
    safe_http_url,
)
from radar_core.pipelines.dummy_pipeline import DummyPipeline, FinanceRadarPipeline
from radar_macro import portfolio, server
from radar_macro.fetchers.turkish_fetcher import TurkishOfficialFetcher
from radar_macro.pipeline import MacroImpactPipeline


@pytest.fixture()
def isolated_macro_db(tmp_path):
    """Point radar_core.core.database._engine to a temporary SQLite DB for each test."""
    prev_engine = db._engine
    db_path = tmp_path / "test_macro.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    db.init_db(db_url=db_url)
    portfolio.clear_portfolio_ai_cache()
    yield db_url
    portfolio.clear_portfolio_ai_cache()
    db._engine = prev_engine


def test_frontend_js_xss_helpers_and_no_raw_innerhtml_sinks():
    """Verify app.js escapeHtml/sanitizeUrl behavior in Node and ensure dynamic innerHTML fields are escaped."""
    app_js_path = PROJECT_ROOT / "radar_macro" / "web" / "js" / "app.js"
    js_src = app_js_path.read_text(encoding="utf-8")

    # Extract escapeHtml and sanitizeUrl functions and run them in Node
    app_js_literal = json.dumps(str(app_js_path))
    script = f"""
import {{ readFileSync }} from "node:fs";
const document = {{ addEventListener: () => {{}} }};
const src = readFileSync({app_js_literal}, "utf8");
const cleaned = src
  .replace(/^import\\s+.*$/gm, "")
  .replace(/export\\s+function\\s+/g, "function ");
const fn = new Function("document", cleaned + "; return {{ escapeHtml, sanitizeUrl }};");
const {{ escapeHtml, sanitizeUrl }} = fn(document);
console.log(JSON.stringify({{
  escaped: escapeHtml('<img src=x onerror="alert(1)"> & \\'test\\''),
  jsUrl: sanitizeUrl('javascript:alert(1)'),
  dataUrl: sanitizeUrl('data:text/html,<script>alert(1)</script>'),
  httpsUrl: sanitizeUrl('https://www.tcmb.gov.tr/duyuru'),
  httpUrl: sanitizeUrl('http://127.0.0.1:8503/test'),
}}));
"""

    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    out = json.loads(proc.stdout)
    assert out["escaped"] == "&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &#39;test&#39;"
    assert out["jsUrl"] == "#"
    assert out["dataUrl"] == "#"
    assert out["httpsUrl"] == "https://www.tcmb.gov.tr/duyuru"
    assert out["httpUrl"] == "http://127.0.0.1:8503/test"

    # Verify dangerous raw interpolations are gone from app.js
    for forbidden in [
        "${item.title}",
        "${item.simple_summary}",
        "${item.rotation_summary}",
        "${item.rotation_rationale}",
        "${item.source_name}",
        "${item.url}",
        "${act.headline}",
        "${act.instruction}",
        "${act.rationale}",
        "${d.regime_narrative}",
        "${msg}",
    ]:
        assert forbidden not in js_src


def test_cors_restricts_remote_origins_and_allows_localhost(isolated_macro_db):
    """CORS must allow localhost/127.0.0.1 and reject arbitrary external origins."""
    client = TestClient(server.app)

    evil_resp = client.get("/api/metrics", headers={"Origin": "https://evil.example"})
    assert evil_resp.status_code == 200
    assert "access-control-allow-origin" not in evil_resp.headers

    local_resp = client.get("/api/metrics", headers={"Origin": "http://127.0.0.1:8503"})
    assert local_resp.status_code == 200
    assert local_resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:8503"
    assert local_resp.headers.get("access-control-allow-credentials") is None


def test_settings_endpoints_mask_secrets_and_block_unauthorized_mutations(isolated_macro_db):
    """POST /api/settings must mask keys and reject unauthorized/cross-origin/proxied writes."""
    client = TestClient(server.app)

    get_resp = client.get("/api/settings")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert "local_token" in data
    assert "GEMINI_API_KEY" not in data
    assert "OPENAI_API_KEY" not in data
    token = data["local_token"]

    # 1. Missing token and missing loopback Origin -> 403
    unauth = client.post("/api/settings", json={"gemini_model": "gemini-2.0-flash"})
    assert unauth.status_code == 403

    # 2. Cross-origin Origin -> 403 even with token
    evil = client.post(
        "/api/settings",
        json={"gemini_model": "gemini-2.0-flash"},
        headers={"Origin": "https://evil.com", "X-Radar-Local-Token": token},
    )
    assert evil.status_code == 403

    # 3. Proxied X-Forwarded-For -> 403
    proxied = client.post(
        "/api/settings",
        json={"gemini_model": "gemini-2.0-flash"},
        headers={"X-Forwarded-For": "203.0.113.10", "X-Radar-Local-Token": token},
    )
    assert proxied.status_code == 403

    # 4. Authorized local token succeeds without exposing raw secret
    with patch.object(server, "_save_env_updates") as mock_save:
        ok = client.post(
            "/api/settings",
            json={"gemini_api_key": "AIzaSySecretKey123456789", "gemini_model": "gemini-2.0-flash"},
            headers={"X-Radar-Local-Token": token},
        )
        assert ok.status_code == 200
        mock_save.assert_called_once()
        body = ok.json()
        assert "AIzaSySecretKey123456789" not in json.dumps(body)
        assert "local_token" not in body["current"]


def test_turkish_fetcher_enforces_tls_verification_and_dynamic_spk_year():
    """TurkishOfficialFetcher must call requests.get with verify=True and current year SPK URL."""
    fetcher = TurkishOfficialFetcher()
    fake_resp = SimpleNamespace(status_code=200, text="<html></html>", encoding="utf-8")

    with patch("radar_macro.fetchers.turkish_fetcher.requests.get", return_value=fake_resp) as mock_get:
        resp = fetcher._get("https://www.tcmb.gov.tr/")
        assert resp is fake_resp
        assert mock_get.call_args.kwargs["verify"] is True

        fetcher._fetch_spk("SPK_Bulletins", limit=5)
        spk_url = mock_get.call_args_list[-1].args[0]
        assert f"{datetime.now(timezone.utc).year}-yili-spk-bultenleri" in spk_url


def test_get_portfolio_is_non_blocking_and_caches_explicit_refresh(isolated_macro_db):
    """GET /api/portfolio must not trigger synchronous LLM calls unless refresh_ai=true."""
    client = TestClient(server.app)

    mock_output = StructuredAnalysisOutput(
        severity="INFO",
        summary_title="Taktiksel Ozeti",
        detailed_reasoning="Detayli WACC ve reel faiz teknik analizi aciklamasi burada.",
        action_items=["Mevduat agirligini koru"],
        metrics={
            "simple_summary": "Yüksek TL faiz ortamında dengeli ve defansif kalınmalıdır.",
            "technical_analysis": "WACC ve TCMB politika faizi dengesi uzun vadeli tahvil ve PPF lehine çalışmaktadır.",
        },
    )

    with (
        patch.object(portfolio, "get_macro_settings", return_value=SimpleNamespace(DATABASE_URL=isolated_macro_db)),
        patch("radar_core.core.llm_engine.LLMEngine.analyze_structured", return_value=mock_output) as mock_llm,
    ):
        # Default GET must NOT call LLM
        r1 = client.get("/api/portfolio")
        assert r1.status_code == 200
        assert mock_llm.call_count == 0
        assert r1.json()["ai_review_cached"] is False

    # Exercise compute_tactical_copilot directly with mocked LLMEngine
    fake_engine = MagicMock()
    fake_engine.openai_api_key = "sk-test"
    fake_engine.gemini_api_key = ""
    fake_engine.analyze_structured.return_value = mock_output

    with patch("radar_core.core.llm_engine.LLMEngine", return_value=fake_engine):
        # Default GET /api/portfolio -> no LLM call
        res_default = client.get("/api/portfolio")
        assert res_default.status_code == 200
        assert fake_engine.analyze_structured.call_count == 0

        # Explicit refresh_ai=true -> 1 LLM call, populated in cache
        res_refresh = client.get("/api/portfolio?refresh_ai=true")
        assert res_refresh.status_code == 200
        assert fake_engine.analyze_structured.call_count == 1
        assert "dengeli ve defansif" in res_refresh.json()["rationale"]["simple"]

        # Subsequent GET /api/portfolio -> serves cached AI review with 0 new LLM calls
        res_cached = client.get("/api/portfolio")
        assert res_cached.status_code == 200
        assert fake_engine.analyze_structured.call_count == 1
        assert res_cached.json()["ai_review_cached"] is True
        assert "dengeli ve defansif" in res_cached.json()["rationale"]["simple"]


def test_ported_radar_core_fixes_in_yatirim_radari(isolated_macro_db):
    """Verify source scoping, single-pass prompts, retry backoff, and dashboard escaping in vendored radar_core."""
    with db.get_session() as session:
        db.save_raw_item(
            session,
            RawItem(
                source_name="HackerNews_Best",
                url="https://news.ycombinator.com/item?id=10",
                title="HN item",
                content_text="Developer saas launch product tool growth with sufficient length for prefilter.",
            ),
        )
        db.save_raw_item(
            session,
            RawItem(
                source_name="TCMB_Basin_Duyurulari",
                url="https://www.tcmb.gov.tr/1",
                title="TCMB faiz",
                content_text="TCMB politika faizi ve enflasyon karari aciklandi, zorunlu karsilik duzenlemesi.",
            ),
        )

    macro = MacroImpactPipeline(db_url=isolated_macro_db, api_key="")
    macro.llm_engine = LLMEngine(gemini_api_key="", openai_api_key="")
    m_stats = macro.process_queue(batch_size=10)
    assert m_stats["evaluated"] == 1

    # HackerNews_Best remains untouched for DummyPipeline
    dummy = DummyPipeline()
    dummy.llm_engine = LLMEngine(gemini_api_key="", openai_api_key="")
    d_stats = dummy.process_queue(batch_size=10)
    assert d_stats["evaluated"] == 1

    # Single-pass prompt formatting in MacroImpactPipeline and FinanceRadarPipeline
    raw = RawData(
        source_name="TCMB",
        url="https://www.tcmb.gov.tr/{content}",
        title="Duyuru {content}",
        content_text="GERCEK_ICERIK",
        content_hash="h1",
    )
    rendered_macro = macro.build_prompt(raw)
    assert "Duyuru {content}" in rendered_macro
    assert rendered_macro.count("GERCEK_ICERIK") == 1
    assert "Duyuru {content}" in FinanceRadarPipeline().build_prompt(raw)

    # Vendored dashboard XSS helpers
    card = render_intel_card_html(
        AnalysisResult(raw_data_id=1, pipeline_type="macro", severity="INFO", summary_title="<script>x</script>", detailed_reasoning="ok", created_at=None),
        RawData(id=1, source_name="src", url="javascript:alert(1)", title="t", content_text="c", content_hash="h"),
    )
    assert "<script>" not in card
    assert "javascript:" not in card
    assert safe_http_url("javascript:alert(1)") is None
    assert filter_results_by_sources([(1, SimpleNamespace(source_name="A"))], ["A"], []) == []


def test_default_port_updated_to_8503():
    """Run_Terminal.bat and radar_macro/run.py must default to port 8503."""
    bat = (PROJECT_ROOT / "Run_Terminal.bat").read_text(encoding="utf-8")
    run_py = (PROJECT_ROOT / "radar_macro" / "run.py").read_text(encoding="utf-8")
    assert "--port 8503" in bat
    assert "8501" not in bat
    assert "port: int = 8503" in run_py
    assert "default=8503" in run_py
