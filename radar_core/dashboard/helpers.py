"""HTML sanitization, filtering, and formatting helpers for the radar_core Streamlit dashboard."""

import html
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

ALLOWED_SEVERITY_CLASSES = frozenset({"critical", "opportunity", "warning", "info"})


def escape_html(value: Any) -> str:
    """Escape untrusted text for safe HTML interpolation."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def safe_http_url(url: Any) -> str | None:
    """Return a trimmed http/https URL if valid and safe, otherwise None."""
    if not url or not isinstance(url, str):
        return None
    candidate = url.strip()
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def format_created_at(created_at: datetime | None) -> str:
    """Format analysis creation timestamp safely when created_at is None."""
    if created_at is None:
        return "Unknown"
    return created_at.strftime("%Y-%m-%d %H:%M UTC")


def get_llm_status_caption(settings: Any) -> str:
    """Build sidebar LLM status caption checking both Gemini and OpenAI API keys."""
    has_gemini = bool(getattr(settings, "GEMINI_API_KEY", ""))
    has_openai = bool(getattr(settings, "OPENAI_API_KEY", ""))
    if has_gemini and has_openai:
        return f"LLM: `{settings.DEFAULT_MODEL}` + OpenAI (Active)"
    if has_gemini:
        return f"LLM: `{settings.DEFAULT_MODEL}` (Active - Gemini)"
    if has_openai:
        return f"LLM: `{getattr(settings, 'OPENAI_MODEL_FAST', 'gpt-4o-mini')}` (Active - OpenAI)"
    return "LLM: Heuristic Mode (No API Key set)"


def filter_results_by_sources(
    results: list[tuple[Any, Any]],
    available_sources: list[str],
    selected_sources: list[str],
) -> list[tuple[Any, Any]]:
    """Filter joined analysis results by selected sources, returning [] when all chips are cleared."""
    if not available_sources:
        return []
    allowed = set(selected_sources)
    return [res for res in results if res[1].source_name in allowed]


def render_intel_card_html(analysis: Any, raw: Any) -> str:
    """Render an intelligence summary card with strict HTML escaping and URL scheme allowlisting."""
    raw_severity = str(getattr(analysis, "severity", "INFO") or "INFO")
    sev_slug = raw_severity.lower()
    if sev_slug not in ALLOWED_SEVERITY_CLASSES:
        sev_slug = "info"
    sev_class = f"badge-{sev_slug}"

    severity_html = escape_html(raw_severity)
    pipeline_html = escape_html(str(getattr(analysis, "pipeline_type", "") or "").upper())
    source_html = escape_html(getattr(raw, "source_name", ""))
    title_html = escape_html(getattr(analysis, "summary_title", ""))
    created_html = escape_html(format_created_at(getattr(analysis, "created_at", None)))

    safe_url = safe_http_url(getattr(raw, "url", None))
    if safe_url:
        link_html = (
            f'<a href="{escape_html(safe_url)}" target="_blank" rel="noopener noreferrer" '
            f'style="color: #818cf8; text-decoration: none;">Source Link</a>'
        )
    else:
        link_html = '<span style="color: #64748b;">Source Link Unavailable</span>'

    return f"""
                <div class="intel-card">
                    <div>
                        <span class="badge {sev_class}">{severity_html}</span>
                        <span class="badge badge-pipeline">{pipeline_html}</span>
                        <span style="color: #94a3b8; font-size: 0.85rem; font-weight: 500;">{source_html}</span>
                    </div>
                    <div class="intel-title">{title_html}</div>
                    <div class="intel-meta">
                        <span>🕒 {created_html}</span>
                        <span>🔗 {link_html}</span>
                    </div>
                </div>
                """


def render_action_pill_html(idx: int, action: Any) -> str:
    """Render a single escaped action-item pill."""
    return f'<div class="action-pill"><b>{int(idx)}.</b> {escape_html(action)}</div>'
