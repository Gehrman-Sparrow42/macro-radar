"""Radar Core Streamlit Dashboard for real-time intelligence feeds, metrics, and pipeline controls."""

import os
from pathlib import Path
import sys

# Ensure repository root is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
PARENT_OF_PROJECT = PROJECT_ROOT.parent
if str(PARENT_OF_PROJECT) not in sys.path:
    sys.path.insert(0, str(PARENT_OF_PROJECT))

import streamlit as st
from radar_core.config.settings import get_settings
from radar_core.core.database import (
    get_analysis_results,
    get_metrics_summary,
    get_session,
    init_db,
)
from radar_core.pipelines.dummy_pipeline import get_pipeline

# Configure Streamlit page
st.set_page_config(
    page_title="Radar Core Intelligence",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern dark-mode responsive cards and badges
st.markdown(
    """
    <style>
    /* Metric Card Styling */
    .metric-container {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .metric-label {
        color: #94a3b8;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }

    /* Severity Badges */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-right: 8px;
    }
    .badge-critical {
        background-color: rgba(239, 68, 68, 0.2);
        color: #fca5a5;
        border: 1px solid rgba(239, 68, 68, 0.5);
    }
    .badge-opportunity {
        background-color: rgba(16, 185, 129, 0.2);
        color: #6ee7b7;
        border: 1px solid rgba(16, 185, 129, 0.5);
    }
    .badge-warning {
        background-color: rgba(245, 158, 11, 0.2);
        color: #fcd34d;
        border: 1px solid rgba(245, 158, 11, 0.5);
    }
    .badge-info {
        background-color: rgba(59, 130, 246, 0.2);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.5);
    }
    .badge-pipeline {
        background-color: rgba(148, 163, 184, 0.15);
        color: #cbd5e1;
        border: 1px solid rgba(148, 163, 184, 0.3);
    }

    /* Intelligence Card */
    .intel-card {
        background-color: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .intel-card:hover {
        border-color: rgba(99, 102, 241, 0.4);
    }
    .intel-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #f8fafc;
        margin-top: 8px;
        margin-bottom: 8px;
    }
    .intel-meta {
        font-size: 0.8rem;
        color: #94a3b8;
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 10px;
    }
    .action-pill {
        background: rgba(99, 102, 241, 0.15);
        border-left: 3px solid #6366f1;
        padding: 8px 14px;
        border-radius: 4px;
        margin-top: 6px;
        font-size: 0.9rem;
        color: #e0e7ff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize database schema safely
init_db()
settings = get_settings()


# ---------------------------------------------------------------------------
# Sidebar Controls & Filters
# ---------------------------------------------------------------------------
st.sidebar.title("📡 Radar Control")
st.sidebar.caption("Macro Intelligence & Market Discovery")

st.sidebar.divider()

# Pipeline Execution Panel
st.sidebar.subheader("🚀 Trigger Pipeline")
selected_pipeline_name = st.sidebar.selectbox(
    "Select Target Pipeline",
    options=["dummy", "finance", "market"],
    index=0,
    help="Select which specialized radar pipeline to trigger on-demand.",
)
batch_limit = st.sidebar.slider(
    "Ingestion Batch Limit",
    min_value=1,
    max_value=20,
    value=5,
    help="Maximum items to ingest from each configured source feed.",
)

if st.sidebar.button("Run Pipeline On-Demand", type="primary", use_container_width=True):
    with st.spinner(f"Executing {selected_pipeline_name.upper()} pipeline..."):
        try:
            pipeline = get_pipeline(selected_pipeline_name)
            sources = getattr(pipeline, "get_default_sources", lambda: [])()
            # Adjust limit in source configs
            for src in sources:
                src["limit"] = batch_limit

            stats = pipeline.run(source_configs=sources, batch_size=batch_limit)
            st.sidebar.success(
                f"Completed: Fetched {stats['ingestion'].get('total_fetched', 0)}, "
                f"New {stats['ingestion'].get('new_saved', 0)}, "
                f"Analyzed {stats['processing'].get('analyzed', 0)}"
            )
            st.rerun()
        except Exception as err:
            st.sidebar.error(f"Pipeline execution error: {err}")

st.sidebar.divider()

# Filters Panel
st.sidebar.subheader("🔍 Filters")

search_term = st.sidebar.text_input(
    "Search Intelligence",
    value="",
    placeholder="Search headline, text, reasoning...",
)

severity_filter = st.sidebar.multiselect(
    "Severity Level",
    options=["CRITICAL", "OPPORTUNITY", "WARNING", "INFO"],
    default=["CRITICAL", "OPPORTUNITY", "WARNING", "INFO"],
)

pipeline_filter = st.sidebar.selectbox(
    "Pipeline Filter",
    options=["All Pipelines", "finance", "market", "dummy"],
    index=0,
)

# Load metrics for sidebar stats
with get_session() as session:
    metrics = get_metrics_summary(session)

available_sources = list(metrics.get("sources", {}).keys())
source_filter = st.sidebar.multiselect(
    "Source Feed Filter",
    options=available_sources,
    default=available_sources,
)

st.sidebar.divider()

# Telemetry & Telemetry Summary
st.sidebar.subheader("📊 System Stats")
st.sidebar.metric("Total Ingested", metrics["total_raw"])
st.sidebar.metric("Queue Pending", metrics["total_pending"])
st.sidebar.caption(f"DB: `{settings.DATABASE_URL}`")
if settings.GEMINI_API_KEY:
    st.sidebar.caption(f"LLM: `{settings.DEFAULT_MODEL}` (Active)")
else:
    st.sidebar.caption("LLM: Heuristic Mode (No API Key set)")


# ---------------------------------------------------------------------------
# Main Dashboard View
# ---------------------------------------------------------------------------
st.title("📡 Radar Core Intelligence Feed")
st.caption("Cross-Platform Strategic Risk & Market Opportunity Radar")

# Top Metric Cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label">Total Analyzed</div>
            <div class="metric-value" style="color: #60a5fa;">{metrics["total_analyses"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label">Critical Warnings</div>
            <div class="metric-value" style="color: #f87171;">{metrics["critical_count"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label">Open Opportunities</div>
            <div class="metric-value" style="color: #34d399;">{metrics["opportunity_count"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        f"""
        <div class="metric-container">
            <div class="metric-label">Pending Ingestion Queue</div>
            <div class="metric-value" style="color: #fbbf24;">{metrics["total_pending"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)

# Fetch Filtered Records
chosen_pipeline = None if pipeline_filter == "All Pipelines" else pipeline_filter

with get_session() as session:
    results = get_analysis_results(
        session=session,
        pipeline_type=chosen_pipeline,
        severity=severity_filter if severity_filter else None,
        search_term=search_term,
        limit=100,
    )

# Filter by selected sources
if source_filter:
    results = [res for res in results if res[1].source_name in source_filter]

# Display Feed
if not results:
    st.info(
        "No intelligence items match the active filters, or the database is currently empty. "
        "Click 'Run Pipeline On-Demand' in the sidebar to ingest and analyze real-time feeds!"
    )
else:
    st.subheader(f"Recent Intelligence Findings ({len(results)} items)")

    for analysis, raw in results:
        sev_class = f"badge-{analysis.severity.lower()}"
        created_str = analysis.created_at.strftime("%Y-%m-%d %H:%M UTC")

        with st.container():
            # Card Header
            st.markdown(
                f"""
                <div class="intel-card">
                    <div>
                        <span class="badge {sev_class}">{analysis.severity}</span>
                        <span class="badge badge-pipeline">{analysis.pipeline_type.upper()}</span>
                        <span style="color: #94a3b8; font-size: 0.85rem; font-weight: 500;">{raw.source_name}</span>
                    </div>
                    <div class="intel-title">{analysis.summary_title}</div>
                    <div class="intel-meta">
                        <span>🕒 {created_str}</span>
                        <span>🔗 <a href="{raw.url}" target="_blank" style="color: #818cf8; text-decoration: none;">Source Link</a></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Interactive Expander for Chain of Reasoning, Action Items, and Raw Data
            with st.expander("🔍 Chain of Reasoning, Action Items & Raw Text"):
                r_col1, r_col2 = st.columns([2, 1])

                with r_col1:
                    st.markdown("#### 🧠 Analytical Reasoning")
                    st.write(analysis.detailed_reasoning)

                    if analysis.action_items:
                        st.markdown("#### ⚡ Recommended Action Items")
                        for idx, action in enumerate(analysis.action_items, 1):
                            st.markdown(
                                f"""<div class="action-pill"><b>{idx}.</b> {action}</div>""",
                                unsafe_allow_html=True,
                            )

                with r_col2:
                    st.markdown("#### 📈 Signal Metrics")
                    if analysis.metrics:
                        for k, v in analysis.metrics.items():
                            st.write(f"**{k.replace('_', ' ').title()}**: `{v}`")
                    else:
                        st.caption("No numerical metrics recorded.")

                    st.markdown("#### 📄 Ingested Document")
                    st.write(f"**Original Title:** {raw.title}")
                    st.write(f"**Content Hash:** `{raw.content_hash[:12]}...`")

                st.markdown("#### 📝 Raw Extracted Content")
                st.text_area(
                    "Raw Content Snippet",
                    value=raw.content_text,
                    height=180,
                    key=f"raw_text_{analysis.id}",
                    disabled=True,
                )

            st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)
