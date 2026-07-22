"""
app.py — ISRO SOC Analytics Platform

Main entry point. Renders the Home page and initialises all application
singletons (logging, settings, directories) on first load.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

# ─── Bootstrap (must run before any other imports) ────────────────────────────
from config import settings, get_logger
from config.logging_config import configure_logging

# Initialise logging with log dir from settings
settings.ensure_directories()
configure_logging(log_level=settings.log_level, logs_dir=settings.logs_dir)
logger = get_logger(__name__)
logger.info("ISRO SOC Analytics starting — env=%s", settings.app_env)

# ─── Streamlit page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{settings.app_title} | Home",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": f"**{settings.app_title}** — AI-driven Security Analytics\n\nDataset: June 2026 (~2.77B logs)",
    },
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Google Font import ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Global overrides ── */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }

    /* ── Remove default padding ── */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }

    /* ── Sidebar styling ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0D1117 0%, #161B22 100%);
        border-right: 1px solid #30363D;
    }

    /* ── Metric card styling ── */
    [data-testid="metric-container"] {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    }

    /* ── Status indicator badge ── */
    .status-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .status-green  { background: rgba(63,185,80,0.15);  color: #3FB950; border: 1px solid #3FB950; }
    .status-yellow { background: rgba(210,153,34,0.15); color: #D29922; border: 1px solid #D29922; }
    .status-red    { background: rgba(248,81,73,0.15);  color: #F85149; border: 1px solid #F85149; }
    .status-grey   { background: rgba(139,148,158,0.15); color: #8B949E; border: 1px solid #8B949E; }

    /* ── Feature card grid ── */
    .feature-card {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 1.25rem;
        transition: border-color 0.2s, box-shadow 0.2s;
        height: 100%;
    }
    .feature-card:hover {
        border-color: #58A6FF;
        box-shadow: 0 0 20px rgba(88,166,255,0.1);
    }
    .feature-icon {
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    .feature-title {
        font-size: 1rem;
        font-weight: 600;
        color: #E6EDF3;
        margin-bottom: 0.25rem;
    }
    .feature-desc {
        font-size: 0.82rem;
        color: #8B949E;
        line-height: 1.5;
    }

    /* ── Hero section ── */
    .hero-container {
        background: linear-gradient(135deg, #0D1117 0%, #1A1F2E 50%, #0D1117 100%);
        border: 1px solid #30363D;
        border-radius: 16px;
        padding: 2.5rem 2rem;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
    }
    .hero-container::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(88,166,255,0.05) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #58A6FF 0%, #BC8CFF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
    }
    .hero-subtitle {
        font-size: 1rem;
        color: #8B949E;
        font-weight: 400;
        margin-bottom: 1.5rem;
    }
    .hero-stat {
        display: inline-block;
        margin-right: 2rem;
        font-size: 0.85rem;
        color: #8B949E;
    }
    .hero-stat strong {
        color: #E6EDF3;
        display: block;
        font-size: 1.3rem;
        font-weight: 700;
    }

    /* ── Divider ── */
    .custom-divider {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #30363D, transparent);
        margin: 1.5rem 0;
    }

    /* ── Alert banner ── */
    .alert-banner {
        background: rgba(248,81,73,0.1);
        border: 1px solid rgba(248,81,73,0.3);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-size: 0.85rem;
        color: #F85149;
    }
    .info-banner {
        background: rgba(88,166,255,0.08);
        border: 1px solid rgba(88,166,255,0.2);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-size: 0.85rem;
        color: #79C0FF;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h2 style='color:#E6EDF3; font-weight:700; margin-bottom:0.25rem;'>🛡️ ISRO SOC</h2>"
        "<p style='color:#8B949E; font-size:0.8rem; margin-top:0;'>Security Analytics Platform</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:#30363D; margin:0.75rem 0;'>", unsafe_allow_html=True)

    # Connection status indicator (lazy — doesn't connect until Settings is opened)
    st.markdown("**Connection Status**")
    if "es_health" in st.session_state:
        health = st.session_state["es_health"]
        css_class = "status-green" if health.get("connected") else "status-red"
        label = "Connected" if health.get("connected") else "Disconnected"
        st.markdown(
            f"<span class='status-badge {css_class}'>{label}</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<span class='status-badge status-grey'>Not checked</span>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border-color:#30363D; margin:0.75rem 0;'>", unsafe_allow_html=True)

    # Dataset info
    st.markdown("**Dataset**")
    st.markdown(
        "<p style='color:#8B949E; font-size:0.8rem; margin:0;'>"
        f"Index: <code style='color:#79C0FF;'>{settings.es_index_pattern}</code><br>"
        f"Period: June 2026<br>"
        f"Volume: ~2.77B logs"
        "</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<hr style='border-color:#30363D; margin:0.75rem 0;'>", unsafe_allow_html=True)

    # Navigation hint
    st.markdown(
        "<p style='color:#8B949E; font-size:0.78rem;'>Use the pages above to navigate the platform.</p>",
        unsafe_allow_html=True,
    )

# ─── Hero Section ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero-container">
        <div class="hero-title">🛡️ ISRO SOC Analytics</div>
        <div class="hero-subtitle">
            AI-driven threat detection and log analysis for large-scale security operations
        </div>
        <div>
            <span class="hero-stat"><strong>2.77B</strong> Log Events</span>
            <span class="hero-stat"><strong>June 2026</strong> Dataset</span>
            <span class="hero-stat"><strong>Real-time</strong> ES Aggregations</span>
            <span class="hero-stat"><strong>ML-powered</strong> Anomaly Detection</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Configuration validation warning ─────────────────────────────────────────
config_errors = settings.validate()
if config_errors:
    st.markdown(
        "<div class='alert-banner'>⚠️ <strong>Configuration incomplete:</strong> "
        + " · ".join(config_errors)
        + " — please update your <code>.env</code> file and restart.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("")

# ─── Quick-Start Info ─────────────────────────────────────────────────────────
if not config_errors:
    st.markdown(
        "<div class='info-banner'>✅ Configuration loaded — go to <strong>⚙️ Settings</strong> to test your Elasticsearch connection.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("")

# ─── Platform Features Grid ───────────────────────────────────────────────────
st.markdown("### Platform Modules")

features = [
    {
        "icon": "📊",
        "title": "1. Overview Dashboard",
        "desc": "KPI metrics, event volume trends, severity distribution, and top source IPs — all via ES aggregations.",
        "page": "pages/1_📊_Overview.py",
    },
    {
        "icon": "⚙️",
        "title": "2. Settings",
        "desc": "Configure Elasticsearch connection, index patterns, cache TTL, and test connectivity.",
        "page": "pages/2_⚙️_Settings.py",
    },
    {
        "icon": "🔌",
        "title": "3. ES Diagnostics",
        "desc": "Cluster health, index inspection, and mapping validation.",
        "page": "pages/3_🔌_ES_Diagnostics.py",
    },
    {
        "icon": "📥",
        "title": "4. Log Retrieval",
        "desc": "Batch log extraction using search_after pagination for memory safety.",
        "page": "pages/4_📥_Log_Retrieval.py",
    },
    {
        "icon": "🧹",
        "title": "5. Data Pipeline",
        "desc": "Feature engineering, data cleaning, and log normalization.",
        "page": "pages/5_🧹_Data_Pipeline.py",
    },
    {
        "icon": "📋",
        "title": "6. Sigma Rules",
        "desc": "Upload and manage Sigma detection rules. Live matching against the ES dataset with hit counts.",
        "page": "pages/6_📋_Sigma_Rules.py",
    },
    {
        "icon": "🤖",
        "title": "7. ML Anomaly Detection",
        "desc": "Isolation Forest and LOF models trained on aggregated metrics. Flags unusual activity patterns.",
        "page": "pages/7_🤖_ML_Anomaly.py",
    },
    {
        "icon": "🎯",
        "title": "8. Threat Scoring",
        "desc": "Unified threat engine combining Sigma severity and ML anomaly scores.",
        "page": "pages/8_🎯_Threat_Scoring.py",
    },
    {
        "icon": "🤖",
        "title": "9. AI Assistant",
        "desc": "Conversational investigation assistant powered by LLMs or deterministic fallback.",
        "page": "pages/9_🤖_AI_Assistant.py",
    }
]

cols = st.columns(3)
for i, feat in enumerate(features):
    with cols[i % 3]:
        st.markdown(
            f"""
            <div class="feature-card">
                <div class="feature-icon">{feat['icon']}</div>
                <div class="feature-title">{feat['title']}</div>
                <div class="feature-desc">{feat['desc']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("")  # spacing

# ─── Architecture Note ────────────────────────────────────────────────────────
st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])
with col1:
    st.markdown("### Architecture Highlights")
    arch_points = [
        ("🔒 Memory-safe", "All analytics use ES aggregations. Raw log scans are never performed."),
        ("⚡ Aggregation-first", "date_histogram, terms, cardinality — sub-second answers from 2.77B docs."),
        ("🔄 Batch processing", "search_after pagination for exports — never loads all data into memory."),
        ("💾 Two-tier caching", "st.cache_data (in-session) + joblib disk cache (across restarts)."),
        ("🔁 Retry logic", "Exponential backoff on transient ES errors via tenacity."),
        ("🧩 Modular pages", "Each analytics page is independent — extend without rewriting core."),
    ]
    for icon_label, desc in arch_points:
        st.markdown(
            f"<p style='margin:0.4rem 0; font-size:0.88rem;'>"
            f"<strong style='color:#58A6FF;'>{icon_label}</strong> "
            f"<span style='color:#8B949E;'>— {desc}</span></p>",
            unsafe_allow_html=True,
        )

with col2:
    st.markdown("### System Info")
    info_items = {
        "App Environment": settings.app_env.title(),
        "ES Host": f"{settings.es_scheme}://{settings.es_host}:{settings.es_port}",
        "Index Pattern": settings.es_index_pattern,
        "Batch Size": f"{settings.batch_size:,}",
        "Cache TTL": f"{settings.cache_ttl_seconds}s",
        "Log Level": settings.log_level,
    }
    for k, v in info_items.items():
        st.markdown(
            f"<p style='margin:0.3rem 0; font-size:0.82rem;'>"
            f"<span style='color:#8B949E;'>{k}:</span> "
            f"<code style='color:#79C0FF; font-size:0.8rem;'>{v}</code></p>",
            unsafe_allow_html=True,
        )

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center; color:#8B949E; font-size:0.78rem;'>"
    "ISRO SOC Analytics Platform &nbsp;·&nbsp; Built with Streamlit + Elasticsearch 9.4.1"
    "</p>",
    unsafe_allow_html=True,
)
