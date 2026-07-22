"""
pages/6_⚙️_Settings.py

Settings & Configuration — Elasticsearch connection test, index configuration,
cache management, and application diagnostics.
"""

from __future__ import annotations

import streamlit as st

from config import settings, get_logger
from core import get_es_client, get_cache

logger = get_logger(__name__)

st.set_page_config(
    page_title=f"{settings.app_title} | Settings",
    page_icon="⚙️",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .block-container { padding-top: 1.5rem !important; }
    .config-table td { padding: 4px 12px; font-size: 0.85rem; }
    .config-table td:first-child { color: #8B949E; white-space: nowrap; }
    .config-table td:last-child { color: #79C0FF; font-family: monospace; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("## ⚙️ Settings & Diagnostics")
st.markdown(
    "<p style='color:#8B949E; margin-top:-0.5rem;'>"
    "Manage your Elasticsearch connection, index configuration, and cache.</p>",
    unsafe_allow_html=True,
)

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_conn, tab_config, tab_cache, tab_logs = st.tabs(
    ["🔌 Connection", "📋 Configuration", "💾 Cache", "📜 App Logs"]
)

# ─── Connection Tab ───────────────────────────────────────────────────────────
with tab_conn:
    st.markdown("### Elasticsearch Connection Test")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(
            f"""
            | Field | Value |
            |-------|-------|
            | Host | `{settings.es_scheme}://{settings.es_host}:{settings.es_port}` |
            | Username | `{settings.es_username or '⚠️ Not set'}` |
            | Password | `{'*' * 8 if settings.es_password else '⚠️ Not set'}` |
            | Index Pattern | `{settings.es_index_pattern}` |
            | CA Cert | `{settings.es_ca_cert or 'None (verify_certs=False)'}` |
            """
        )

    with col2:
        test_btn = st.button("🔌 Test Connection", type="primary", use_container_width=True)

    if test_btn:
        with st.spinner("Connecting to Elasticsearch..."):
            client = get_es_client()
            health = client.health_check()
            st.session_state["es_health"] = health

    if "es_health" in st.session_state:
        health = st.session_state["es_health"]
        if health.get("connected"):
            status_colour = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(
                health.get("status", ""), "⚪"
            )
            st.success(
                f"✅ **Connected** — Cluster: `{health['cluster_name']}` | "
                f"Status: {status_colour} `{health['status']}` | "
                f"Nodes: `{health['node_count']}` | "
                f"Latency: `{health['response_time_ms']}ms`"
            )
        else:
            st.error(f"❌ **Connection failed:** {health.get('error')}")

    st.markdown("---")
    st.markdown("#### Index Mapping Inspector")
    inspect_btn = st.button("🔍 Inspect Index Mapping", use_container_width=False)
    if inspect_btn:
        with st.spinner("Fetching index mapping..."):
            try:
                client = get_es_client()
                mapping = client.get_index_mapping(settings.es_index_pattern)
                if mapping:
                    import pandas as pd
                    mapping_df = pd.DataFrame(
                        [{"Field": k, "Type": v} for k, v in sorted(mapping.items())]
                    )
                    st.dataframe(mapping_df, use_container_width=True, height=400)
                    st.caption(f"{len(mapping)} fields found in index mapping")
                else:
                    st.warning("No mapping returned. Check the index pattern.")
            except Exception as e:
                st.error(f"Mapping fetch failed: {e}")

# ─── Configuration Tab ────────────────────────────────────────────────────────
with tab_config:
    st.markdown("### Current Configuration")
    st.caption("All values are read from environment variables / `.env` file. Restart the app after changes.")

    config_data = {
        "App Title": settings.app_title,
        "Environment": settings.app_env,
        "Log Level": settings.log_level,
        "ES Host": settings.es_host,
        "ES Port": str(settings.es_port),
        "ES Scheme": settings.es_scheme,
        "ES Username": settings.es_username or "(not set)",
        "ES Index Pattern": settings.es_index_pattern,
        "Batch Size": f"{settings.batch_size:,}",
        "Scroll Keep-Alive": settings.scroll_keepalive,
        "Cache TTL": f"{settings.cache_ttl_seconds}s",
        "Joblib Cache Dir": str(settings.joblib_cache_dir),
        "Model Save Dir": str(settings.model_save_dir),
        "Project Root": str(settings.project_root),
    }

    rows = "\n".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>"
        for k, v in config_data.items()
    )
    st.markdown(
        f"<table class='config-table'><tbody>{rows}</tbody></table>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("### Configuration Validation")
    errors = settings.validate()
    if errors:
        for err in errors:
            st.error(f"❌ {err}")
        st.info("Edit your `.env` file to fix these issues, then restart the app.")
    else:
        st.success("✅ All required configuration values are present.")

# ─── Cache Tab ────────────────────────────────────────────────────────────────
with tab_cache:
    st.markdown("### Cache Management")

    cache = get_cache()
    cache_size = cache.cache_size_mb()

    col_c1, col_c2, col_c3 = st.columns(3)
    col_c1.metric("Disk Cache Size", f"{cache_size} MB")
    col_c2.metric("Cache TTL", f"{settings.cache_ttl_seconds}s")
    col_c3.metric("Cache Dir", settings.joblib_cache_dir.name)

    st.markdown("---")
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("🗑️ Clear Disk Cache (Joblib)", use_container_width=True):
            cache.clear_disk_cache()
            st.success("Disk cache cleared.")

    with col_btn2:
        if st.button("🔄 Clear Streamlit Cache", use_container_width=True):
            st.cache_data.clear()
            st.success("Streamlit in-memory cache cleared.")

    st.markdown("---")
    st.markdown("#### Cache Configuration Tips")
    st.markdown(
        """
        - **Cache TTL** (`CACHE_TTL_SECONDS`): How long aggregation results are cached in the Streamlit session.
          Shorter = fresher data, more ES queries. Default: 300s.
        - **Disk cache** (joblib): Persists across Streamlit restarts. Used for ML model outputs.
          Clear when data freshness is critical.
        - **Streamlit cache**: Cleared automatically when the app restarts or TTL expires.
        """
    )

# ─── App Logs Tab ─────────────────────────────────────────────────────────────
with tab_logs:
    st.markdown("### Application Logs")
    log_file = settings.logs_dir / "isro_soc.log"

    if log_file.exists():
        col_l1, col_l2 = st.columns([2, 1])
        with col_l1:
            n_lines = st.slider("Lines to display", 20, 500, 100, step=20)
        with col_l2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()

        try:
            lines = log_file.read_text(encoding="utf-8").splitlines()
            last_lines = "\n".join(lines[-n_lines:])
            st.code(last_lines, language=None)
        except Exception as e:
            st.error(f"Could not read log file: {e}")
    else:
        st.info(f"Log file not found at: `{log_file}`\nLogs will appear here after the first write.")
