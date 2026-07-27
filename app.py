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
    page_title=f"ISRO SOC | Home",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": f"**ISRO SOC Analytics** — Aerospace-Grade Security Analytics\n\nDataset: June 2026",
    },
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Google Font import ── */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

    /* ── Global overrides ── */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif !important;
    }
    
    /* Global Background to Deep Space Blue */
    .stApp {
        background-color: #050b14 !important;
    }

    /* ── Remove default padding ── */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }

    /* ── Sidebar styling ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #050b14 0%, #08111e 100%) !important;
        border-right: 1px solid #1a2d45 !important;
    }

    /* ── Metric card styling ── */
    [data-testid="metric-container"] {
        background: #091322 !important;
        border: 1px solid #1a2d45 !important;
        border-radius: 12px !important;
        padding: 1.2rem !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4) !important;
    }

    /* ── Status indicator badge ── */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.8px;
        text-transform: uppercase;
    }
    .status-green  { background: rgba(63,185,80,0.15);  color: #3FB950; border: 1px solid #3FB950; }
    .status-yellow { background: rgba(210,153,34,0.15); color: #D29922; border: 1px solid #D29922; }
    .status-red    { background: rgba(248,81,73,0.15);  color: #F85149; border: 1px solid #F85149; }
    .status-grey   { background: rgba(139,148,158,0.15); color: #8B949E; border: 1px solid #8B949E; }

    /* ── Feature card grid ── */
    .feature-card {
        background: linear-gradient(145deg, #091322, #0d1a2f);
        border: 1px solid #1a2d45;
        border-radius: 16px;
        padding: 1.5rem;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        height: 100%;
        position: relative;
        overflow: hidden;
    }
    .feature-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, #FF9933 0%, #2972B7 100%);
        opacity: 0;
        transition: opacity 0.3s;
    }
    .feature-card:hover {
        border-color: #2972B7;
        box-shadow: 0 10px 30px rgba(41, 114, 183, 0.15);
        transform: translateY(-4px);
    }
    .feature-card:hover::before {
        opacity: 1;
    }
    .feature-icon {
        font-size: 2.2rem;
        margin-bottom: 0.8rem;
        display: inline-block;
        padding: 12px;
        background: rgba(41, 114, 183, 0.1);
        border-radius: 12px;
        color: #2972B7;
    }
    .feature-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #E6EDF3;
        margin-bottom: 0.5rem;
        letter-spacing: 0.3px;
    }
    .feature-desc {
        font-size: 0.85rem;
        color: #A1B0C4;
        line-height: 1.6;
    }

    /* ── Hero section ── */
    .hero-container {
        background: linear-gradient(135deg, rgba(8, 16, 26, 0.9) 0%, rgba(13, 26, 47, 0.9) 100%);
        border: 1px solid #1a2d45;
        border-radius: 20px;
        padding: 3rem 2.5rem;
        margin-bottom: 2.5rem;
        position: relative;
        overflow: hidden;
        box-shadow: inset 0 0 40px rgba(0,0,0,0.5);
    }
    .hero-container::after {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: url('data:image/svg+xml;utf8,<svg width="20" height="20" xmlns="http://www.w3.org/2000/svg"><circle cx="2" cy="2" r="1" fill="rgba(255,255,255,0.03)"/></svg>');
        pointer-events: none;
    }
    .hero-container::before {
        content: '';
        position: absolute;
        top: -30%;
        right: -10%;
        width: 600px;
        height: 600px;
        background: radial-gradient(circle, rgba(41,114,183,0.1) 0%, transparent 60%);
        pointer-events: none;
    }
    .hero-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        background: rgba(255, 153, 51, 0.1);
        border: 1px solid rgba(255, 153, 51, 0.3);
        color: #FF9933;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-bottom: 1rem;
    }
    .hero-title {
        font-size: 3rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        background: linear-gradient(135deg, #FFFFFF 0%, #B0C4DE 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        line-height: 1.2;
    }
    .hero-title span {
        background: linear-gradient(135deg, #FF9933 0%, #F5B041 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        color: #A1B0C4;
        font-weight: 400;
        margin-bottom: 2rem;
        max-width: 700px;
        line-height: 1.6;
    }
    .hero-stats-wrapper {
        display: flex;
        gap: 3rem;
        flex-wrap: wrap;
    }
    .hero-stat {
        display: flex;
        flex-direction: column;
        border-left: 3px solid #2972B7;
        padding-left: 1rem;
    }
    .hero-stat strong {
        color: #FFFFFF;
        font-size: 1.7rem;
        font-weight: 800;
        line-height: 1.2;
    }
    .hero-stat span {
        font-size: 0.8rem;
        color: #8B949E;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
        margin-top: 0.2rem;
    }

    /* ── Divider ── */
    .custom-divider {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #1a2d45, transparent);
        margin: 2rem 0;
    }

    /* ── Headers ── */
    h1, h2, h3, h4 {
        color: #E6EDF3 !important;
        font-weight: 700 !important;
    }

    /* ── Alert banner ── */
    .alert-banner {
        background: rgba(248,81,73,0.1);
        border: 1px solid rgba(248,81,73,0.3);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        font-size: 0.9rem;
        color: #F85149;
    }
    .info-banner {
        background: rgba(41,114,183,0.1);
        border: 1px solid rgba(41,114,183,0.3);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        font-size: 0.9rem;
        color: #79C0FF;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Data Initialisation ──────────────────────────────────────────────────────
from core.local_data_client import get_local_data_client
local_client = get_local_data_client()
df = local_client.get_dataframe()
data_source = local_client.data_path if local_client.data_path else "Primary Data (data.xlsx)"

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div style='text-align: center; margin-bottom: 1.5rem;'>
            <h1 style='color:#FFFFFF; font-weight:800; margin:0; font-size:2rem; letter-spacing:1px;'>
                ISRO<span style='color:#FF9933;'>.</span>SOC
            </h1>
            <p style='color:#8B949E; font-size:0.8rem; margin:0; text-transform:uppercase; letter-spacing:2px; font-weight:600;'>
                Command Center
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown("<hr style='border-color:#1a2d45; margin:1rem 0;'>", unsafe_allow_html=True)
    
    if st.button("🔄 Force Clear Cache", help="Clears the ML pipeline cache and forces a full re-computation of anomalies and SHAP values.", use_container_width=True):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

    # Local data status indicator
    st.markdown("**SYSTEM STATUS**")
    if not df.empty:
        st.markdown(
            "<div style='margin-top:0.5rem;'><span class='status-badge status-green'>● TELEMETRY ACTIVE</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='margin-top:0.5rem;'><span class='status-badge status-red'>● TELEMETRY OFFLINE</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border-color:#1a2d45; margin:1rem 0;'>", unsafe_allow_html=True)

    # Dataset info
    st.markdown("**CURRENT DATASET**")
    st.markdown(
        f"""
        <div style='background: #091322; border: 1px solid #1a2d45; border-radius: 8px; padding: 10px; margin-top: 0.5rem;'>
            <p style='color:#8B949E; font-size:0.75rem; margin:0; text-transform:uppercase; font-weight:600;'>Source</p>
            <p style='color:#79C0FF; font-size:0.85rem; margin:0 0 10px 0; word-break: break-all;'>{data_source}</p>
            <p style='color:#8B949E; font-size:0.75rem; margin:0; text-transform:uppercase; font-weight:600;'>Volume</p>
            <p style='color:#FFFFFF; font-size:1.1rem; margin:0; font-weight:700;'>{len(df):,}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<hr style='border-color:#1a2d45; margin:1rem 0;'>", unsafe_allow_html=True)

    # Navigation hint
    st.markdown(
        "<p style='color:#8B949E; font-size:0.8rem; text-align:center;'>Initiate sub-modules using the navigation panel.</p>",
        unsafe_allow_html=True,
    )

# ─── Hero Section ─────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="hero-container">
        <div class="hero-badge">AEROSPACE-GRADE SECURITY</div>
        <div class="hero-title">ISRO Security Operations<br><span>Analytics Platform</span></div>
        <div class="hero-subtitle">
            Next-generation threat intelligence and log telemetry analysis. Engineered for high-speed, 
            memory-safe execution with advanced ML-powered anomaly detection.
        </div>
        <div class="hero-stats-wrapper">
            <div class="hero-stat">
                <strong>{len(df):,}</strong>
                <span>Events Processed</span>
            </div>
            <div class="hero-stat">
                <strong>In-Memory</strong>
                <span>Architecture</span>
            </div>
            <div class="hero-stat">
                <strong>Local ML</strong>
                <span>Anomaly Engine</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Configuration validation warning ─────────────────────────────────────────
config_errors = settings.validate()
if config_errors:
    st.markdown(
        "<div class='alert-banner'>⚠️ <strong>CONFIGURATION FAULT DETECTED:</strong><br>"
        + "<br>".join(f"• {e}" for e in config_errors)
        + "<br><br>Please rectify the <code>.env</code> file configuration and reboot the system.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("")

# ─── Quick-Start Info ─────────────────────────────────────────────────────────
if not config_errors:
    st.markdown(
        "<div class='info-banner'>🛰️ <strong>SYSTEM READY:</strong> Core analytics modules are fully initialized. Awaiting operator input.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

# ─── Platform Features Grid ───────────────────────────────────────────────────
st.markdown("<h3 style='margin-bottom: 1.5rem;'>Mission Critical Modules</h3>", unsafe_allow_html=True)

features = [
    {
        "icon": "🛰️",
        "title": "Command Dashboard",
        "desc": "Real-time telemetry, threat severity breakdown, and high-level KPI metrics generated from internal log structures.",
        "page": "pages/1_📊_Overview.py",
    },
    {
        "icon": "🧠",
        "title": "ML Anomaly Engine",
        "desc": "Advanced unsupervised machine learning (Isolation Forest) profiling unusual access and behavioral patterns across the network.",
        "page": "pages/1_📊_Overview.py",
    },
    {
        "icon": "⚙️",
        "title": "System Parameters",
        "desc": "Calibrate data sources, review application parameters, and manage operational thresholds for the platform.",
        "page": "pages/2_⚙️_Settings.py",
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

# ─── Architecture Note ────────────────────────────────────────────────────────
st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])
with col1:
    st.markdown("<h3 style='margin-bottom: 1rem;'>Architectural Overview</h3>", unsafe_allow_html=True)
    arch_points = [
        ("🔒 Data Sovereignty", "Absolute local execution. No external network dependencies ensuring maximum security."),
        ("⚡ High-Velocity Vectors", "Pandas-driven vectorized computations for instantaneous memory dataset queries."),
        ("💾 Direct-to-Memory", "Bypasses traditional databases; data is mapped directly into RAM from local storage."),
        ("🧩 Modular Extensibility", "Plug-and-play architecture allows rapid deployment of new analytical models."),
    ]
    for icon_label, desc in arch_points:
        st.markdown(
            f"<div style='margin-bottom: 0.8rem; display: flex; align-items: flex-start;'>"
            f"<div style='color:#FF9933; font-weight:700; width: 160px; font-size: 0.9rem; flex-shrink: 0;'>{icon_label}</div>"
            f"<div style='color:#A1B0C4; font-size: 0.9rem;'>{desc}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

with col2:
    st.markdown("<h3 style='margin-bottom: 1rem;'>Environment State</h3>", unsafe_allow_html=True)
    
    stream_name = data_source.name if hasattr(data_source, "name") else str(data_source).split("/")[-1]
    
    info_items = {
        "Deployment Tier": settings.app_env.title(),
        "Active Stream": stream_name,
        "Buffer Size": f"{len(df):,} events",
        "Diagnostics Level": settings.log_level,
    }

    
    html = "<div style='background: #091322; border: 1px solid #1a2d45; border-radius: 12px; padding: 1.25rem;'>"
    for k, v in info_items.items():
        html += f"""
            <div style='margin-bottom: 0.75rem; border-bottom: 1px solid rgba(26,45,69,0.5); padding-bottom: 0.5rem;'>
                <div style='color:#8B949E; font-size:0.75rem; text-transform:uppercase; font-weight:600; margin-bottom:0.2rem;'>{k}</div>
                <div style='color:#E6EDF3; font-size:0.95rem; font-family: monospace;'>{v}</div>
            </div>
        """
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<hr class='custom-divider'>", unsafe_allow_html=True)
st.markdown(
    """
    <div style='text-align:center; color:#8B949E; font-size:0.85rem; display:flex; justify-content:center; align-items:center; gap: 15px;'>
        <span>Indian Space Research Organisation (ISRO)</span>
        <span style='color:#30363D;'>|</span>
        <span>Internal SOC Analytics Platform</span>
        <span style='color:#30363D;'>|</span>
        <span style='color:#79C0FF; font-family:monospace;'>v2.0.0 (Local Engine)</span>
    </div>
    """,
    unsafe_allow_html=True,
)
