"""
pages/7_🔌_ES_Diagnostics.py

Elasticsearch Integration & Diagnostics — ISRO SOC Analytics Platform

Displays connection status, cluster information, available indices,
node topology, field mapping explorer, and query performance diagnostics.

No credentials are exposed in the UI. All sensitive configuration
is read from .env and masked before display.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import settings, get_logger
from core import get_es_client, DiagnosticsEngine
from core.elasticsearch_client import ESClientError
from utils.data_utils import DataUtils

logger = get_logger(__name__)

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{settings.app_title} | ES Diagnostics",
    page_icon="🔌",
    layout="wide",
)

# ─── Styles ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.block-container { padding-top: 1.5rem !important; }

/* ── Test result card ── */
.test-card {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.6rem;
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
}
.test-icon { font-size: 1.25rem; min-width: 1.5rem; }
.test-body { flex: 1; }
.test-title { font-weight: 600; font-size: 0.9rem; color: #E6EDF3; margin-bottom: 0.1rem; }
.test-detail { font-size: 0.8rem; color: #8B949E; }
.test-pass  { border-left: 3px solid #3FB950; }
.test-fail  { border-left: 3px solid #F85149; }
.test-warn  { border-left: 3px solid #D29922; }
.test-skip  { border-left: 3px solid #6C757D; }

/* ── Health badge ── */
.health-green  { color: #3FB950; font-weight: 700; }
.health-yellow { color: #D29922; font-weight: 700; }
.health-red    { color: #F85149; font-weight: 700; }
.health-grey   { color: #8B949E; }

/* ── Stat row ── */
.stat-row {
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
    margin-bottom: 1rem;
}
.stat-item {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 10px;
    padding: 0.75rem 1.25rem;
    min-width: 150px;
}
.stat-label { font-size: 0.72rem; color: #8B949E; letter-spacing: 0.5px; text-transform: uppercase; }
.stat-value { font-size: 1.4rem; font-weight: 700; color: #E6EDF3; margin-top: 0.15rem; }
.stat-sub   { font-size: 0.75rem; color: #58A6FF; margin-top: 0.1rem; }

/* ── Metric container ── */
[data-testid="metric-container"] {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 12px;
    padding: 1rem;
}

/* ── Code pill ── */
.code-pill {
    display: inline-block;
    background: rgba(88,166,255,0.1);
    border: 1px solid rgba(88,166,255,0.2);
    color: #79C0FF;
    font-family: monospace;
    font-size: 0.78rem;
    padding: 1px 7px;
    border-radius: 4px;
}
</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 🔌 Elasticsearch Integration & Diagnostics")
st.markdown(
    "<p style='color:#8B949E; margin-top:-0.5rem;'>"
    "Connection status, cluster topology, index browser, and field mapping explorer. "
    "No credentials are displayed.</p>",
    unsafe_allow_html=True,
)

# ─── Helper: Health colour ────────────────────────────────────────────────────
def _health_colour(status: str) -> str:
    return {"green": "health-green", "yellow": "health-yellow", "red": "health-red"}.get(
        status.lower(), "health-grey"
    )

def _health_icon(status: str) -> str:
    return {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⚪"}.get(status.lower(), "⚪")

def _test_card(title: str, detail: str, passed: Optional[bool], extra: str = "") -> None:
    if passed is None:
        cls, icon = "test-skip", "⏭️"
    elif passed:
        cls, icon = "test-pass", "✅"
    else:
        cls, icon = "test-fail", "❌"
    st.markdown(
        f"""<div class="test-card {cls}">
            <div class="test-icon">{icon}</div>
            <div class="test-body">
                <div class="test-title">{title}</div>
                <div class="test-detail">{detail}</div>
                {"<div class='test-detail' style='color:#58A6FF;margin-top:2px;'>" + extra + "</div>" if extra else ""}
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

# ─── Sidebar controls ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔌 Connection Config")
    st.markdown(
        f"<p style='color:#8B949E;font-size:0.8rem;margin:0;'>"
        f"Host: <span class='code-pill'>{settings.es_host}:{settings.es_port}</span><br>"
        f"Scheme: <span class='code-pill'>{settings.es_scheme}</span><br>"
        f"User: <span class='code-pill'>{settings.es_username or '(not set)'}</span><br>"
        f"Index: <span class='code-pill'>{settings.es_index_pattern}</span>"
        f"</p>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:#30363D;margin:0.75rem 0;'>", unsafe_allow_html=True)

    run_tests = st.button("▶ Run Diagnostics", type="primary", use_container_width=True)
    auto_refresh = st.checkbox("Auto-test on page load", value=True)

    st.markdown("<hr style='border-color:#30363D;margin:0.75rem 0;'>", unsafe_allow_html=True)
    st.markdown("### 🔍 Index Browser")
    index_pattern = st.text_input("Browse pattern", value="*")
    include_hidden = st.checkbox("Include system indices", value=False)

# ─── Run tests ────────────────────────────────────────────────────────────────
if run_tests or (auto_refresh and "diag_results" not in st.session_state):
    with st.spinner("Running diagnostics against Elasticsearch..."):
        try:
            client = get_es_client()
            engine = DiagnosticsEngine(client)
            diag = engine.full_report()
            st.session_state["diag_results"] = diag
            st.session_state["diag_engine"] = engine
        except Exception as exc:
            st.error(f"❌ Diagnostics engine failed to initialise: {exc}")
            st.session_state["diag_results"] = None

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_conn, tab_cluster, tab_indices, tab_fields, tab_perf = st.tabs([
    "🔌 Connection",
    "🖥️ Cluster",
    "📂 Index Browser",
    "🗂️ Field Explorer",
    "⚡ Performance",
])

diag: Dict[str, Any] = st.session_state.get("diag_results") or {}

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Connection
# ══════════════════════════════════════════════════════════════════════════════
with tab_conn:
    st.markdown("### Connection Diagnostic Suite")
    if not diag:
        st.info("Click **▶ Run Diagnostics** in the sidebar to test connectivity.")
    else:
        conn = diag.get("connectivity", {})

        # Ping test
        ping = conn.get("ping", {})
        _test_card(
            "TCP Connectivity (Ping)",
            ping.get("detail", ""),
            ping.get("passed"),
            extra=f"Latency: {ping.get('latency_ms', '—')} ms" if ping.get("passed") else "",
        )

        # Auth test
        auth = conn.get("auth", {})
        _test_card(
            "Authentication",
            auth.get("detail", "Not tested"),
            auth.get("passed"),
        )

        # Health test
        health = conn.get("health", {})
        status_icon = _health_icon(health.get("status", ""))
        _test_card(
            "Cluster Health",
            health.get("detail", "Not tested"),
            health.get("passed"),
            extra=f"Response time: {health.get('response_time_ms', '—')} ms" if health.get("passed") else "",
        )

        # Index list test
        idx_list = conn.get("index_list", {})
        _test_card(
            "Index Accessibility",
            idx_list.get("detail", "Not tested"),
            idx_list.get("passed"),
        )

        # Target index test
        target = conn.get("target_index", {})
        doc_count = target.get("doc_count", 0)
        _test_card(
            f"Target Index  (`{settings.es_index_pattern}`)",
            target.get("detail", "Not tested"),
            target.get("passed"),
            extra=f"Total documents: {DataUtils.format_large_number(doc_count)}" if target.get("passed") else "",
        )

        # Overall verdict
        all_passed = all(
            v.get("passed", False)
            for v in conn.values()
            if isinstance(v, dict) and "passed" in v
        )
        st.markdown("")
        if all_passed:
            st.success("✅ **All connectivity tests passed.** Elasticsearch is fully accessible.")
        else:
            failed = [
                k.replace("_", " ").title()
                for k, v in conn.items()
                if isinstance(v, dict) and not v.get("passed", True)
            ]
            st.error(f"❌ **{len(failed)} test(s) failed:** {', '.join(failed)}")

# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Cluster
# ══════════════════════════════════════════════════════════════════════════════
with tab_cluster:
    st.markdown("### Cluster Overview")
    if not diag:
        st.info("Run diagnostics to see cluster info.")
    else:
        cluster = diag.get("cluster", {})
        info = cluster.get("info", {})
        stats = cluster.get("stats", {})
        health = cluster.get("health", {})

        if info.get("error") or stats.get("error"):
            st.error(f"Could not fetch cluster info: {info.get('error') or stats.get('error')}")
        else:
            # Cluster identity bar
            st.markdown(
                f"""<div class="stat-row">
                    <div class="stat-item">
                        <div class="stat-label">Cluster Name</div>
                        <div class="stat-value" style="font-size:1rem">{info.get('cluster_name') or '—'}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">ES Version</div>
                        <div class="stat-value" style="font-size:1rem">{info.get('es_version') or '—'}</div>
                        <div class="stat-sub">Lucene {info.get('lucene_version') or '—'}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Health Status</div>
                        <div class="stat-value {_health_colour(health.get('status',''))}">
                            {_health_icon(health.get('status','unknown'))} {health.get('status','—').upper()}
                        </div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Nodes</div>
                        <div class="stat-value">{health.get('node_count', 0)}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Build Type</div>
                        <div class="stat-value" style="font-size:1rem">{info.get('build_type') or '—'}</div>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

            st.markdown("<hr style='border-color:#30363D;'>", unsafe_allow_html=True)

            # Stats metrics
            st.markdown("#### Storage & Data")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total Indices", f"{stats.get('indices_count', 0):,}")
            k2.metric("Total Documents", DataUtils.format_large_number(stats.get("total_docs", 0)))
            k3.metric("Store Size", stats.get("store_size_human") or
                      DataUtils.format_large_number(stats.get("store_size_bytes", 0)))
            k4.metric("Segments", f"{stats.get('segment_count', 0):,}")

            st.markdown("#### Shards")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Active Shards", f"{health.get('active_shards', 0):,}")
            s2.metric("Primary Shards", f"{health.get('active_primary_shards', 0):,}")
            s3.metric("Unassigned", f"{health.get('unassigned_shards', 0):,}")
            s4.metric("Response Time", f"{health.get('response_time_ms', '—')} ms")

            st.markdown("<hr style='border-color:#30363D;'>", unsafe_allow_html=True)

            # Node table
            st.markdown("#### Node Topology")
            if "diag_engine" in st.session_state:
                with st.spinner("Loading node info..."):
                    node_df = st.session_state["diag_engine"].node_report()
                if not node_df.empty:
                    display_cols = [c for c in ["name", "ip", "roles", "es_version", "os_name", "heap_max_mb", "jvm_version"]
                                    if c in node_df.columns]
                    st.dataframe(node_df[display_cols], use_container_width=True, hide_index=True)
                else:
                    st.info("No node info available (may require node monitoring privileges).")

# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Index Browser
# ══════════════════════════════════════════════════════════════════════════════
with tab_indices:
    st.markdown("### Index Browser")
    st.caption(f"Pattern: `{index_pattern}` — click column headers to sort")

    @st.cache_data(ttl=60, show_spinner=False)
    def _load_indices(pattern, hidden):
        try:
            client = get_es_client()
            engine = DiagnosticsEngine(client)
            return engine.index_report(pattern=pattern, include_hidden=hidden), None
        except Exception as e:
            return pd.DataFrame(), str(e)

    with st.spinner("Fetching index list..."):
        idx_df, idx_err = _load_indices(index_pattern, include_hidden)

    if idx_err:
        st.error(f"❌ {idx_err}")
    elif idx_df.empty:
        st.warning("No indices found matching the pattern.")
    else:
        # Summary KPIs
        ik1, ik2, ik3 = st.columns(3)
        ik1.metric("Total Indices", len(idx_df))
        ik2.metric("Total Documents", DataUtils.format_large_number(int(idx_df["docs_count"].sum())))
        green_pct = round(
            len(idx_df[idx_df["health"] == "green"]) / len(idx_df) * 100
        ) if len(idx_df) > 0 else 0
        ik3.metric("Healthy (Green)", f"{green_pct}%")

        st.markdown("")

        # Filter by health
        health_filter = st.multiselect(
            "Filter by health",
            options=sorted(idx_df["health"].unique()),
            default=sorted(idx_df["health"].unique()),
        )
        filtered_df = idx_df[idx_df["health"].isin(health_filter)].copy()

        # Colour-coded health column
        def _colour_health(val):
            colours = {"green": "#3FB950", "yellow": "#D29922", "red": "#F85149"}
            c = colours.get(str(val).lower(), "#8B949E")
            return f"color: {c}; font-weight: 600;"

        styled = filtered_df[
            ["name", "health", "status", "docs_count", "store_size", "primary_shards", "replica_shards"]
        ].rename(columns={
            "name": "Index", "health": "Health", "status": "Status",
            "docs_count": "Docs", "store_size": "Size",
            "primary_shards": "Pri", "replica_shards": "Rep",
        })

        st.dataframe(
            styled.style.applymap(_colour_health, subset=["Health"]),
            use_container_width=True,
            height=450,
            hide_index=True,
        )

        # Download CSV
        csv = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download Index List (CSV)", data=csv, file_name="indices.csv", mime="text/csv")

        # Health distribution donut (Plotly)
        if len(idx_df) > 0:
            st.markdown("#### Health Distribution")
            health_counts = idx_df["health"].value_counts().reset_index()
            health_counts.columns = ["health", "count"]
            colour_map = {"green": "#3FB950", "yellow": "#D29922", "red": "#F85149", "unknown": "#6C757D"}
            colours = [colour_map.get(h, "#6C757D") for h in health_counts["health"]]

            fig = go.Figure(go.Pie(
                labels=health_counts["health"],
                values=health_counts["count"],
                hole=0.55,
                marker=dict(colors=colours, line=dict(color="#161B22", width=2)),
                textinfo="label+value",
                textfont=dict(color="#E6EDF3", size=12),
                hovertemplate="%{label}: %{value} indices<extra></extra>",
            ))
            fig.update_layout(
                height=280,
                paper_bgcolor="#161B22",
                plot_bgcolor="#161B22",
                font=dict(color="#E6EDF3", family="Inter"),
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=True,
                legend=dict(bgcolor="#161B22", bordercolor="#30363D", borderwidth=1),
            )
            col_donut, col_spacer = st.columns([1, 2])
            with col_donut:
                st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 4 — Field Explorer
# ══════════════════════════════════════════════════════════════════════════════
with tab_fields:
    st.markdown("### Field Mapping Explorer")

    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        explore_index = st.text_input(
            "Index to explore",
            value=settings.es_index_pattern,
            key="field_explore_index",
        )
    with col_f2:
        type_filter = st.selectbox(
            "Filter by type",
            options=["All types", "keyword", "text", "long", "integer", "double", "float",
                     "date", "boolean", "ip", "geo_point", "nested", "object"],
        )

    load_fields = st.button("🔍 Load Field Mapping", key="load_fields_btn")

    if load_fields or "field_df" in st.session_state:
        if load_fields:
            with st.spinner(f"Loading field mappings for `{explore_index}`..."):
                try:
                    engine = DiagnosticsEngine(get_es_client())
                    f_filter = None if type_filter == "All types" else type_filter
                    field_df = engine.field_report(index=explore_index, type_filter=f_filter)
                    st.session_state["field_df"] = field_df
                    st.session_state["field_df_index"] = explore_index
                except Exception as exc:
                    st.error(f"❌ {exc}")
                    field_df = pd.DataFrame()
                    st.session_state.pop("field_df", None)
        else:
            field_df = st.session_state.get("field_df", pd.DataFrame())

        if not field_df.empty:
            st.caption(
                f"Index: `{st.session_state.get('field_df_index', explore_index)}` — "
                f"{len(field_df)} fields"
            )

            # Search filter
            search_term = st.text_input("🔎 Search fields", placeholder="e.g. source.ip", key="field_search")
            if search_term:
                field_df = field_df[field_df["field"].str.contains(search_term, case=False, na=False)]

            # Type distribution bar chart
            if "type" in field_df.columns and len(field_df) > 0:
                type_dist = field_df["type"].value_counts().reset_index()
                type_dist.columns = ["type", "count"]

                fig2 = go.Figure(go.Bar(
                    x=type_dist["count"],
                    y=type_dist["type"],
                    orientation="h",
                    marker=dict(
                        color=type_dist["count"],
                        colorscale=[[0, "#1F3B5E"], [1, "#58A6FF"]],
                    ),
                    hovertemplate="%{y}: %{x} fields<extra></extra>",
                ))
                fig2.update_layout(
                    title="Field Type Distribution",
                    height=max(200, 30 * len(type_dist)),
                    paper_bgcolor="#161B22",
                    plot_bgcolor="#161B22",
                    font=dict(color="#E6EDF3", family="Inter", size=11),
                    xaxis=dict(showgrid=True, gridcolor="#30363D"),
                    yaxis=dict(showgrid=False),
                    margin=dict(l=20, r=20, t=40, b=20),
                )
                col_bar, col_tbl = st.columns([1, 2])
                with col_bar:
                    st.plotly_chart(fig2, use_container_width=True)
                with col_tbl:
                    display_cols = [c for c in ["field", "type", "aggregatable", "searchable"] if c in field_df.columns]
                    st.dataframe(field_df[display_cols], use_container_width=True, height=350, hide_index=True)
            else:
                st.dataframe(field_df, use_container_width=True, height=400, hide_index=True)

            # Download
            csv_f = field_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇ Download Field List (CSV)", data=csv_f, file_name="field_mapping.csv", mime="text/csv")
        elif load_fields:
            st.warning("No fields returned. Check the index name and permissions.")

# ══════════════════════════════════════════════════════════════════════════════
# Tab 5 — Performance
# ══════════════════════════════════════════════════════════════════════════════
with tab_perf:
    st.markdown("### Query Performance Diagnostics")

    if not diag:
        st.info("Run diagnostics to see performance metrics.")
    else:
        # Latency from diagnostic run
        lat = diag.get("latency", {})
        target_info = diag.get("target_index", {})
        target_stats = target_info.get("stats", {})

        st.markdown("#### Target Index Stats")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Documents", DataUtils.format_large_number(target_stats.get("docs_count", 0)))
        p2.metric("Store Size", target_stats.get("store_size_human") or "—")
        p3.metric("Segments", f"{target_stats.get('segments_count', 0):,}")
        p4.metric("Search Queries", DataUtils.format_large_number(target_stats.get("search_total", 0)))

        st.markdown("<hr style='border-color:#30363D;'>", unsafe_allow_html=True)

        st.markdown("#### Latency Benchmark (count query, 3 runs)")
        if lat.get("error"):
            st.error(f"Latency test failed: {lat['error']}")
        elif lat.get("avg_ms") is not None:
            l1, l2, l3, l4 = st.columns(4)
            l1.metric("Min Latency", f"{lat['min_ms']} ms")
            l2.metric("Avg Latency", f"{lat['avg_ms']} ms")
            l3.metric("Max Latency", f"{lat['max_ms']} ms")
            l4.metric("Runs", lat.get("runs", 0))

            # Latency gauge
            avg_ms = lat["avg_ms"]
            colour = "#3FB950" if avg_ms < 100 else "#D29922" if avg_ms < 500 else "#F85149"
            st.markdown(
                f"""<div style="margin-top:0.75rem;background:#161B22;border:1px solid #30363D;
                border-radius:10px;padding:1rem;">
                <div style="font-size:0.8rem;color:#8B949E;margin-bottom:0.5rem;">
                    Avg Latency Rating
                </div>
                <div style="background:#0D1117;border-radius:6px;height:12px;overflow:hidden;">
                    <div style="background:{colour};width:{min(avg_ms/10, 100):.0f}%;
                    height:100%;border-radius:6px;transition:width 0.5s;"></div>
                </div>
                <div style="font-size:0.78rem;color:{colour};margin-top:0.4rem;">
                    {'Excellent (< 100ms)' if avg_ms < 100 else 'Acceptable (< 500ms)' if avg_ms < 500 else 'Slow (> 500ms)'}
                </div></div>""",
                unsafe_allow_html=True,
            )
        else:
            st.info("No latency data. Run diagnostics first.")

        st.markdown("<hr style='border-color:#30363D;'>", unsafe_allow_html=True)

        # Live latency test
        st.markdown("#### Live Latency Test")
        c1, c2 = st.columns([2, 1])
        with c1:
            bench_index = st.text_input("Benchmark against index", value=settings.es_index_pattern, key="bench_idx")
        with c2:
            bench_runs = st.slider("Runs", min_value=1, max_value=10, value=3, key="bench_runs")

        if st.button("⚡ Run Latency Test"):
            with st.spinner(f"Running {bench_runs} count queries against `{bench_index}`..."):
                try:
                    engine = DiagnosticsEngine(get_es_client())
                    result = engine.measure_query_latency(bench_index, n_runs=bench_runs)
                    if result.get("error"):
                        st.error(result["error"])
                    else:
                        r1, r2, r3 = st.columns(3)
                        r1.metric("Min", f"{result['min_ms']} ms")
                        r2.metric("Avg", f"{result['avg_ms']} ms")
                        r3.metric("Max", f"{result['max_ms']} ms")
                except Exception as exc:
                    st.error(f"Latency test failed: {exc}")

        st.markdown("<hr style='border-color:#30363D;'>", unsafe_allow_html=True)

        # Field type summary for target index
        st.markdown("#### Target Index Field Type Summary")
        type_summary = diag.get("target_index", {}).get("field_type_summary", {})
        if type_summary:
            ts_df = pd.DataFrame([
                {"Field Type": k, "Count": v}
                for k, v in type_summary.items()
            ])
            fig3 = go.Figure(go.Bar(
                x=ts_df["Count"],
                y=ts_df["Field Type"],
                orientation="h",
                marker=dict(color="#BC8CFF"),
                hovertemplate="%{y}: %{x}<extra></extra>",
            ))
            fig3.update_layout(
                height=max(200, 30 * len(ts_df)),
                paper_bgcolor="#161B22",
                plot_bgcolor="#161B22",
                font=dict(color="#E6EDF3", family="Inter", size=11),
                xaxis=dict(showgrid=True, gridcolor="#30363D"),
                yaxis=dict(showgrid=False),
                margin=dict(l=20, r=20, t=20, b=20),
            )
            col_ts, _ = st.columns([1, 1])
            with col_ts:
                st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No field type data available. Run diagnostics to populate.")

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<hr style='border-color:#30363D;margin-top:2rem;'>", unsafe_allow_html=True)
st.caption(
    f"ES Diagnostics · Target: `{settings.es_index_pattern}` · "
    f"Timeout: {settings.cache_ttl_seconds}s cache TTL"
)
