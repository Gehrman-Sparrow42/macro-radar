"""Macro & Regulatory Impact Intelligence Dashboard - Financial Terminal UI."""

import os
from pathlib import Path
import sys

# Ensure repository root and radar_core are in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
TOOLS_ROOT = PROJECT_ROOT.parent

for p in [str(PROJECT_ROOT), str(TOOLS_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st
from radar_core.core.database import (
    get_analysis_results,
    get_engine,
    get_metrics_summary,
    get_session,
    init_db,
)
from radar_macro.config.settings import get_macro_settings
from radar_macro.config.sources import get_active_macro_sources
from radar_macro.pipeline import MacroImpactPipeline

# Streamlit terminal setup
st.set_page_config(
    page_title="Macro & Regulatory Impact Radar",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Connect to isolated Macro database
macro_settings = get_macro_settings()
get_engine(db_url=macro_settings.DATABASE_URL)
init_db(db_url=macro_settings.DATABASE_URL)

# Terminal Styling (Dark-mode, Bloomberg/Institutional aesthetic)
st.markdown(
    """
    <style>
    /* Terminal Metric Box */
    .terminal-metric {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.85) 100%);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .metric-sublabel {
        font-size: 0.78rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
        margin-bottom: 4px;
    }

    /* Stance & Policy Badges */
    .stance-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-right: 6px;
    }
    .stance-hawkish {
        background: rgba(239, 68, 68, 0.18);
        color: #fca5a5;
        border: 1px solid rgba(239, 68, 68, 0.45);
    }
    .stance-dovish {
        background: rgba(16, 185, 129, 0.18);
        color: #6ee7b7;
        border: 1px solid rgba(16, 185, 129, 0.45);
    }
    .stance-pivot {
        background: rgba(168, 85, 247, 0.18);
        color: #d8b4fe;
        border: 1px solid rgba(168, 85, 247, 0.45);
    }
    .stance-neutral {
        background: rgba(148, 163, 184, 0.18);
        color: #cbd5e1;
        border: 1px solid rgba(148, 163, 184, 0.35);
    }

    /* Asset Impact Tag */
    .asset-tag {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .asset-bullish { color: #34d399; }
    .asset-bearish { color: #f87171; }
    .asset-neutral { color: #94a3b8; }

    /* Decree Card */
    .macro-card {
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 14px;
        transition: border-color 0.2s ease;
    }
    .macro-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
    }
    .macro-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #f1f5f9;
        margin-top: 8px;
        margin-bottom: 6px;
    }
    .macro-meta {
        font-size: 0.82rem;
        color: #64748b;
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 8px;
    }
    .hedge-action {
        background: rgba(30, 58, 138, 0.25);
        border-left: 3px solid #3b82f6;
        padding: 8px 12px;
        border-radius: 4px;
        margin-top: 6px;
        font-size: 0.88rem;
        color: #bfdbfe;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Sidebar: Ingestion Controls & Filters
# ---------------------------------------------------------------------------
st.sidebar.markdown("## 🏛️ Macro Terminal")
st.sidebar.caption("Central Banks • Official Gazettes • Portfolio Protection")
st.sidebar.divider()

# Ingestion Trigger
st.sidebar.subheader("⚡ Macro Ingestion")
selected_category = st.sidebar.selectbox(
    "Target Scope",
    options=["All Categories", "Central Bank", "Securities Regulator", "Fiscal & Sovereign", "Commodities & Derivatives"],
    index=0,
)
batch_size = st.sidebar.slider("Feeds Ingestion Depth", min_value=2, max_value=20, value=6)

if st.sidebar.button("Run Macro Ingestion Cycle", type="primary", use_container_width=True):
    with st.spinner("Tracking central bank releases and regulatory decrees..."):
        try:
            pipeline = MacroImpactPipeline()
            cat = None if selected_category == "All Categories" else selected_category
            sources = pipeline.get_sources(category=cat)
            for s in sources:
                s["limit"] = batch_size

            stats = pipeline.run(source_configs=sources, batch_size=batch_size * 2)
            ing = stats.get("ingestion", {})
            proc = stats.get("processing", {})
            st.sidebar.success(
                f"Sync Complete: {ing.get('new_saved', 0)} new items saved, "
                f"{proc.get('analyzed', 0)} analyzed, {ing.get('duplicates_skipped', 0)} duplicates ignored."
            )
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"Ingestion failed: {exc}")

st.sidebar.divider()

# Stance & Severity Filters
st.sidebar.subheader("🔍 Intelligence Filters")
search_query = st.sidebar.text_input("Search Decrees & Speeches", placeholder="Yields, CPI, Powell, ECB, SEC...")

policy_filter = st.sidebar.multiselect(
    "Policy Stance",
    options=["HAWKISH", "DOVISH", "PIVOT", "NEUTRAL"],
    default=["HAWKISH", "DOVISH", "PIVOT", "NEUTRAL"],
)

severity_filter = st.sidebar.multiselect(
    "Risk Severity",
    options=["CRITICAL", "WARNING", "OPPORTUNITY", "INFO"],
    default=["CRITICAL", "WARNING", "OPPORTUNITY", "INFO"],
)

# Load database metrics
with get_session() as session:
    metrics = get_metrics_summary(session)

st.sidebar.divider()
st.sidebar.subheader("📈 Telemetry")
st.sidebar.caption(f"Database: `{macro_settings.DATABASE_URL}`")
st.sidebar.caption(f"Total Decrees Ingested: **{metrics['total_raw']}**")
st.sidebar.caption(f"Total Policy Analyses: **{metrics['total_analyses']}**")


# ---------------------------------------------------------------------------
# Main View: Top Stance & Risk Barometer
# ---------------------------------------------------------------------------
st.title("🏛️ Macro & Regulatory Impact Intelligence Radar")
st.caption("Institutional-grade surveillance of monetary policy, sovereign debt, and regulatory risk")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(
        f"""
        <div class="terminal-metric">
            <div class="metric-sublabel">Critical Macro Alerts</div>
            <div class="metric-value" style="color: #ef4444;">{metrics['critical_count']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div class="terminal-metric">
            <div class="metric-sublabel">Total Policy Signals</div>
            <div class="metric-value" style="color: #60a5fa;">{metrics['total_analyses']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div class="terminal-metric">
            <div class="metric-sublabel">Cautionary Warnings</div>
            <div class="metric-value" style="color: #f59e0b;">{metrics['warning_count']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        f"""
        <div class="terminal-metric">
            <div class="metric-sublabel">Monitored Sources</div>
            <div class="metric-value" style="color: #10b981;">{len(get_active_macro_sources())}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Query & Render Filtered Findings
# ---------------------------------------------------------------------------
with get_session() as session:
    results = get_analysis_results(
        session=session,
        pipeline_type="macro_regulatory",
        severity=severity_filter if severity_filter else None,
        search_term=search_query,
        limit=100,
    )

# Filter by Policy Stance if specified in metrics
if policy_filter:
    filtered_results = []
    for analysis, raw in results:
        m = analysis.metrics or {}
        item_stance = m.get("policy_stance", "NEUTRAL").upper()
        if item_stance in policy_filter:
            filtered_results.append((analysis, raw))
    results = filtered_results

if not results:
    st.info(
        "No macro intelligence findings match current filters. "
        "Click 'Run Macro Ingestion Cycle' in the sidebar to ingest and analyze real-time feeds!"
    )
else:
    st.subheader(f"Active Macro Bulletins & Decrees ({len(results)} items)")

    for analysis, raw in results:
        meta = analysis.metrics or {}
        stance = meta.get("policy_stance", "NEUTRAL").upper()
        urgency = meta.get("regulatory_urgency", "MONITORING")
        asset_impact = meta.get("asset_impact", {})
        created_time = analysis.created_at.strftime("%Y-%m-%d %H:%M UTC")

        stance_class = f"stance-{stance.lower()}"

        # Card Container
        st.markdown(
            f"""
            <div class="macro-card">
                <div>
                    <span class="stance-badge {stance_class}">{stance}</span>
                    <span class="stance-badge stance-neutral">{urgency.replace('_', ' ')}</span>
                    <span style="color: #94a3b8; font-weight: 600; font-size: 0.85rem;">{raw.source_name}</span>
                </div>
                <div class="macro-title">{analysis.summary_title}</div>
                <div class="macro-meta">
                    <span>🕒 {created_time}</span>
                    <span>🔗 <a href="{raw.url}" target="_blank" style="color: #818cf8; text-decoration: none;">Original Source Release</a></span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Institutional Deep-Dive Expander
        with st.expander("📊 Portfolio Hedging Playbook, Asset Class Impact & Raw Text"):
            c_left, c_right = st.columns([2, 1])

            with c_left:
                st.markdown("#### 🧠 Economic Mechanism & Chain of Reasoning")
                st.write(analysis.detailed_reasoning)

                if analysis.action_items:
                    st.markdown("#### 🛡️ Portfolio Hedging & Positioning Playbook")
                    for idx, action in enumerate(analysis.action_items, 1):
                        st.markdown(
                            f"""<div class="hedge-action"><b>{idx}.</b> {action}</div>""",
                            unsafe_allow_html=True,
                        )

            with c_right:
                st.markdown("#### 🌐 Directional Asset Class Bias")
                if asset_impact and isinstance(asset_impact, dict):
                    for asset, direction in asset_impact.items():
                        dir_lower = str(direction).lower()
                        color_class = "asset-bullish" if "bull" in dir_lower else ("asset-bearish" if "bear" in dir_lower else "asset-neutral")
                        st.markdown(
                            f"""<div class="asset-tag"><span class="{color_class}">●</span> <b>{asset}:</b> <span class="{color_class}">{direction}</span></div>""",
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption("No directional bias recorded.")

                st.markdown("#### 📋 Regulatory Urgency")
                st.code(urgency)
                st.caption(f"SHA-256 Hash: `{raw.content_hash[:16]}...`")

            st.markdown("#### 📄 Original Official Document / Speech Text")
            st.text_area(
                "Document Text",
                value=raw.content_text,
                height=180,
                key=f"macro_doc_{analysis.id}",
                disabled=True,
            )

        st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)
