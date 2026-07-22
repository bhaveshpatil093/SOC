"""
pages/1_📊_Overview.py

Enterprise SOC Dashboard — ISRO SOC Analytics Platform

All statistics are driven by Elasticsearch aggregations (size=0).
Zero raw documents are downloaded; the msearch() round-trip fetches
10 parallel aggregations in a single network call.

Performance notes:
  - @st.cache_data(ttl=300) on the single fetch function.
  - Cache key includes index, time range, and keyword filter.
  - Tab switching is instant — no re-fetch.
  - 🔄 Refresh button clears the cache for the current params.

Session-state integration:
  - Reads threat_results, sigma_report, ml_scored_df if already computed.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import settings, get_logger
from core import get_es_client, query_builder
from utils import TimeUtils, DataUtils

logger = get_logger(__name__)

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{settings.app_title} | SOC Dashboard",
    page_icon="📊",
    layout="wide",
)

# ─── Global Styles ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.block-container { padding-top: 1rem !important; max-width: 100% !important; }

/* KPI cards */
.kpi-row  { display:flex; gap:.85rem; flex-wrap:wrap; margin-bottom:1.2rem; }
.kpi-card {
    background:#161B22; border:1px solid #30363D; border-radius:14px;
    padding:1.1rem 1.4rem; flex:1; min-width:140px; position:relative;
    transition: box-shadow 0.2s ease;
}
.kpi-card:hover { box-shadow: 0 0 0 1px #58A6FF40; }
.kpi-accent { position:absolute; top:0; left:0; width:100%; height:3px; border-radius:14px 14px 0 0; }
.kpi-label { font-size:.68rem; color:#8B949E; text-transform:uppercase; letter-spacing:.7px; margin-bottom:.25rem; }
.kpi-value { font-size:1.85rem; font-weight:800; color:#E6EDF3; line-height:1.1; }
.kpi-sub   { font-size:.72rem; color:#6E7681; margin-top:.25rem; }

/* Section headers */
.sec { font-size:.75rem; font-weight:600; color:#8B949E; text-transform:uppercase;
       letter-spacing:.8px; border-bottom:1px solid #21262D; padding-bottom:.3rem; margin-bottom:.75rem; }

/* Alert badges */
.badge-crit { background:rgba(248,81,73,.15); color:#F85149; border-radius:6px;
              padding:2px 8px; font-size:.72rem; font-weight:600; }
.badge-high { background:rgba(210,153,34,.15); color:#D29922; border-radius:6px;
              padding:2px 8px; font-size:.72rem; font-weight:600; }
.badge-med  { background:rgba(88,166,255,.15); color:#58A6FF; border-radius:6px;
              padding:2px 8px; font-size:.72rem; font-weight:600; }
.badge-low  { background:rgba(63,185,80,.15); color:#3FB950; border-radius:6px;
              padding:2px 8px; font-size:.72rem; font-weight:600; }

/* Offline banner */
.offline-banner {
    background:#161B22; border:1px dashed #30363D; border-radius:14px;
    padding:3rem; text-align:center; margin-top:1.5rem;
}

/* Divider */
.divider { border-color:#21262D; margin:.6rem 0; }
</style>
""", unsafe_allow_html=True)

# ─── Severity palette ──────────────────────────────────────────────────────────
SEV_COLORS: Dict[str, str] = {
    "critical":      "#F85149",
    "high":          "#D29922",
    "medium":        "#58A6FF",
    "low":           "#3FB950",
    "informational": "#8B949E",
    "info":          "#8B949E",
    "unknown":       "#6E7681",
}

RISK_COLORS: Dict[str, str] = {
    "Critical": "#F85149",
    "High":     "#D29922",
    "Medium":   "#58A6FF",
    "Low":      "#3FB950",
    "Info":     "#8B949E",
}

# ─── Dark Plotly base ─────────────────────────────────────────────────────────
def _dark(height: int = 300, **kw) -> dict:
    base = dict(
        paper_bgcolor="#161B22", plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3", family="Inter", size=11),
        margin=dict(l=10, r=10, t=35, b=10),
        height=height,
    )
    base.update(kw)
    return base


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 📊 {settings.app_title}")
    st.markdown("<hr style='border-color:#21262D;margin:.5rem 0'>", unsafe_allow_html=True)

    st.markdown("#### ⏱ Time Range")
    presets = TimeUtils.available_presets()
    preset_keys = list(presets.keys())
    selected_preset = st.selectbox("Preset", preset_keys, index=min(3, len(preset_keys) - 1))
    from_iso, to_iso = presets[selected_preset]()

    use_custom = st.checkbox("Custom range", value=False)
    if use_custom:
        col_f, col_t = st.columns(2)
        with col_f:
            from_date = st.date_input("From", value=_dt.date.today() - _dt.timedelta(days=1))
        with col_t:
            to_date = st.date_input("To", value=_dt.date.today())
        from_iso = f"{from_date}T00:00:00Z"
        to_iso   = f"{to_date}T23:59:59Z"

    st.caption(f"From: `{from_iso[:19]}`")
    st.caption(f"To:   `{to_iso[:19]}`")

    st.markdown("<hr style='border-color:#21262D;margin:.5rem 0'>", unsafe_allow_html=True)
    st.markdown("#### 🔍 Search Filter")
    keyword_filter = st.text_input(
        "Keyword (Lucene)",
        placeholder='e.g.  "user.name:admin"',
        help="Appended as a query_string filter. Use Lucene syntax.",
    )

    st.markdown("<hr style='border-color:#21262D;margin:.5rem 0'>", unsafe_allow_html=True)
    st.markdown("#### ⚙️ Index & Fields")
    idx_pattern   = st.text_input("Index pattern",   value=settings.es_index_pattern)
    time_field    = st.text_input("Timestamp field",  value=settings.es_time_field)
    hostname_fld  = st.text_input("Hostname field",   value=settings.es_hostname_field)
    username_fld  = st.text_input("Username field",   value=settings.es_username_field)
    src_ip_fld    = st.text_input("Source IP field",  value=settings.es_src_ip_field)
    dst_ip_fld    = st.text_input("Dest IP field",    value=settings.es_dst_ip_field)
    severity_fld  = st.text_input("Severity field",   value=settings.es_severity_field)
    category_fld  = st.text_input("Category field",   value=settings.es_category_field)
    top_n         = st.slider("Top-N per chart", 5, 25, 15)

    st.markdown("<hr style='border-color:#21262D;margin:.5rem 0'>", unsafe_allow_html=True)
    cache_ttl  = st.slider("Cache TTL (s)", 60, 1800, settings.cache_ttl_seconds, step=60)
    refresh_btn = st.button("🔄 Refresh Dashboard", use_container_width=True)


# ─── Computed params ──────────────────────────────────────────────────────────
interval = TimeUtils.auto_interval(from_iso, to_iso)

extra_filters: List[Dict[str, Any]] = []
if keyword_filter.strip():
    extra_filters.append({"query_string": {"query": keyword_filter.strip(), "lenient": True}})


# ─── Data fetch (single msearch round-trip) ──────────────────────────────────
@st.cache_data(ttl=cache_ttl, show_spinner=False)
def _fetch_dashboard(
    _index: str,
    _from: str, _to: str,
    _interval: str,
    _time_field: str,
    _hostname_fld: str, _username_fld: str,
    _src_ip_fld: str, _dst_ip_fld: str,
    _severity_fld: str, _category_fld: str,
    _keyword: str,
    _top_n: int,
) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
    """
    Execute a 10-query msearch in one round-trip.

    Returns (responses_list, total_hits, error_str).
    """
    client = get_es_client()
    extra: List[Dict[str, Any]] = []
    if _keyword:
        extra.append({"query_string": {"query": _keyword, "lenient": True}})

    searches = query_builder.enterprise_dashboard_searches(
        time_field=_time_field,
        from_dt=_from,
        to_dt=_to,
        interval=_interval,
        hostname_field=_hostname_fld,
        username_field=_username_fld,
        src_ip_field=_src_ip_fld,
        dst_ip_field=_dst_ip_fld,
        severity_field=_severity_fld,
        category_field=_category_fld,
        outcome_field="event.outcome",
        event_id_field="event.id",
        extra_filters=extra or None,
        top_n=_top_n,
    )
    try:
        responses = client.msearch(searches, index=_index)
        # Extract total hits from KPI response
        kpi_resp = responses[0] if responses else {}
        hits_obj = kpi_resp.get("hits", {}).get("total", {})
        total = hits_obj.get("value", 0) if isinstance(hits_obj, dict) else int(hits_obj or 0)
        return responses, total, None
    except Exception as exc:
        logger.error("Enterprise dashboard msearch failed: %s", exc)
        return [], 0, str(exc)



# Clear cache if refresh requested
if refresh_btn:
    st.cache_data.clear()
    st.rerun()

with st.spinner("⚡ Fetching 10 aggregations in one msearch call…"):
    _resp_holder = _fetch_dashboard(
        idx_pattern,
        from_iso, to_iso,
        interval,
        time_field,
        hostname_fld, username_fld,
        src_ip_fld, dst_ip_fld,
        severity_fld, category_fld,
        keyword_filter.strip(),
        top_n,
    )

responses, total_events, fetch_error = _resp_holder

def _safe_agg(idx: int) -> Dict[str, Any]:
    """Safely extract aggregations from one msearch response."""
    if not responses or idx >= len(responses):
        return {}
    r = responses[idx]
    return r.get("aggregations", r.get("aggs", {}))

def _terms_df(idx: int) -> pd.DataFrame:
    return DataUtils.terms_to_df(_safe_agg(idx).get("top_values", {}))

# ─── Parse KPI metrics ───────────────────────────────────────────────────────
kpi_aggs       = _safe_agg(0)
unique_hosts   = DataUtils.cardinality_value(kpi_aggs.get("unique_hosts",   {}))
unique_users   = DataUtils.cardinality_value(kpi_aggs.get("unique_users",   {}))
unique_src_ips = DataUtils.cardinality_value(kpi_aggs.get("unique_src_ips", {}))
unique_dst_ips = DataUtils.cardinality_value(kpi_aggs.get("unique_dst_ips", {}))

# ─── Parse chart data ────────────────────────────────────────────────────────
trend_df    = DataUtils.date_histogram_with_sub_agg_to_df(
                  _safe_agg(1).get("events_over_time", {}), sub_agg_name="by_severity")
host_df     = _terms_df(2)
user_df     = _terms_df(3)
src_ip_df   = _terms_df(4)
dst_ip_df   = _terms_df(5)
severity_df = _terms_df(6)
category_df = _terms_df(7)
outcome_df  = _terms_df(8)
eventid_df  = _terms_df(9)


# ─── Header ──────────────────────────────────────────────────────────────────
c_title, c_status = st.columns([5, 1])
with c_title:
    st.markdown("## 📊 SOC Operations Dashboard")
    st.markdown(
        f"<p style='color:#8B949E;margin-top:-.5rem;font-size:.85rem;'>"
        f"Data range: <b>{from_iso[:10]}</b> → <b>{to_iso[:10]}</b> "
        f"&nbsp;·&nbsp; Index: <code>{idx_pattern}</code> "
        f"&nbsp;·&nbsp; Interval: <code>{interval}</code> "
        f"&nbsp;·&nbsp; Cache TTL: {cache_ttl}s</p>",
        unsafe_allow_html=True,
    )
with c_status:
    if fetch_error:
        st.error("⚠️ ES Error")
    else:
        st.success("✅ Live")

# ─── Offline state ────────────────────────────────────────────────────────────
if fetch_error:
    st.markdown(f"""
    <div class="offline-banner">
        <div style="font-size:2.5rem;margin-bottom:.75rem;">🔌</div>
        <div style="font-weight:700;font-size:1.1rem;color:#E6EDF3;margin-bottom:.5rem;">
            Elasticsearch Unreachable</div>
        <div style="color:#8B949E;font-size:.9rem;max-width:500px;margin:auto;">
            {fetch_error}<br><br>
            Check your connection settings in <b>⚙️ Settings</b> or use the
            <b>🔌 ES Diagnostics</b> page.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ─── KPI Banner ───────────────────────────────────────────────────────────────
fmt = DataUtils.format_large_number

# Pull session-state threat/sigma/ml summaries
threat_results = st.session_state.get("threat_results", [])
n_threats  = len([r for r in threat_results if getattr(r, "threat_score", 0) >= 60])
n_critical = len([r for r in threat_results if getattr(r, "risk_level", "") == "Critical"])

st.markdown(f"""
<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-accent" style="background:linear-gradient(90deg,#58A6FF,#1F3B5E)"></div>
    <div class="kpi-label">Total Events</div>
    <div class="kpi-value">{fmt(total_events)}</div>
    <div class="kpi-sub">{from_iso[:10]} → {to_iso[:10]}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-accent" style="background:#3FB950"></div>
    <div class="kpi-label">Unique Hosts</div>
    <div class="kpi-value">{fmt(unique_hosts)}</div>
    <div class="kpi-sub">Distinct endpoints</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-accent" style="background:#BC8CFF"></div>
    <div class="kpi-label">Unique Users</div>
    <div class="kpi-value">{fmt(unique_users)}</div>
    <div class="kpi-sub">Active identities</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-accent" style="background:#58A6FF"></div>
    <div class="kpi-label">Unique Src IPs</div>
    <div class="kpi-value">{fmt(unique_src_ips)}</div>
    <div class="kpi-sub">Distinct source addresses</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-accent" style="background:#56D364"></div>
    <div class="kpi-label">Unique Dst IPs</div>
    <div class="kpi-value">{fmt(unique_dst_ips)}</div>
    <div class="kpi-sub">Distinct dest addresses</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-accent" style="background:{'#F85149' if n_critical else '#D29922' if n_threats else '#30363D'}"></div>
    <div class="kpi-label">High+ Threats</div>
    <div class="kpi-value" style="color:{'#F85149' if n_critical else '#D29922' if n_threats else '#8B949E'}">{n_threats}</div>
    <div class="kpi-sub">{n_critical} Critical &nbsp;|&nbsp; from session</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ─── Main Tabs ────────────────────────────────────────────────────────────────
tab_overview, tab_network, tab_identity, tab_categories, tab_alerts = st.tabs([
    "🏠 Overview",
    "🌐 Network",
    "👤 Identity",
    "📋 Categories",
    "🚨 Alerts",
])


# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Overview
# ══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    col_trend, col_sev = st.columns([3, 1])

    # ── Event trend (stacked area by severity) ────────────────────────────────
    with col_trend:
        st.markdown('<div class="sec">Event Volume Over Time</div>', unsafe_allow_html=True)
        if not trend_df.empty and "timestamp" in trend_df.columns:
            sev_cols = [c for c in trend_df.columns
                        if c not in ("timestamp", "total") and pd.api.types.is_numeric_dtype(trend_df[c])]

            fig_trend = go.Figure()
            if sev_cols:
                # Stacked area — one trace per severity
                for sev in sev_cols:
                    color = SEV_COLORS.get(sev.lower(), "#8B949E")
                    fig_trend.add_trace(go.Scatter(
                        x=trend_df["timestamp"],
                        y=trend_df[sev].fillna(0),
                        name=sev.capitalize(),
                        stackgroup="one",
                        fill="tonexty",
                        line=dict(color=color, width=0.8),
                        fillcolor=color.replace("#", "rgba(") + ",0.55)" if color.startswith("#") else color,
                        hovertemplate=f"<b>{sev.capitalize()}</b><br>%{{x|%Y-%m-%d %H:%M}}<br>Count: %{{y:,}}<extra></extra>",
                    ))
            else:
                # Fallback: total only
                fig_trend.add_trace(go.Scatter(
                    x=trend_df["timestamp"],
                    y=trend_df["total"].fillna(0),
                    name="Total",
                    fill="tozeroy",
                    line=dict(color="#58A6FF", width=1.5),
                    fillcolor="rgba(88,166,255,0.2)",
                ))

            fig_trend.update_layout(
                **_dark(height=320),
                hovermode="x unified",
                xaxis=dict(showgrid=False, title=None),
                yaxis=dict(showgrid=True, gridcolor="#21262D", title="Event count"),
                legend=dict(orientation="h", y=1.08, x=0),
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("No timeline data for the selected range.")

    # ── Severity donut ────────────────────────────────────────────────────────
    with col_sev:
        st.markdown('<div class="sec">Severity Distribution</div>', unsafe_allow_html=True)
        if not severity_df.empty:
            colors = [SEV_COLORS.get(v.lower(), "#8B949E") for v in severity_df["value"]]
            fig_sev = go.Figure(go.Pie(
                labels=severity_df["value"].str.capitalize(),
                values=severity_df["count"],
                hole=0.62,
                marker=dict(colors=colors, line=dict(color="#0D1117", width=2)),
                textposition="outside",
                textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>%{value:,} events (%{percent})<extra></extra>",
            ))
            total_events_sev = severity_df["count"].sum()
            fig_sev.update_layout(
                **_dark(height=320),
                showlegend=False,
                annotations=[dict(
                    text=f"<b>{DataUtils.format_large_number(total_events_sev)}</b><br><span style='color:#8B949E'>events</span>",
                    x=0.5, y=0.5, font_size=15, showarrow=False,
                )],
            )
            st.plotly_chart(fig_sev, use_container_width=True)
        else:
            st.info("No severity data.")

    # ── Outcome summary row ───────────────────────────────────────────────────
    if not outcome_df.empty:
        st.markdown('<div class="sec" style="margin-top:.75rem;">Event Outcomes</div>', unsafe_allow_html=True)
        outcome_cols = st.columns(min(len(outcome_df), 5))
        for i, row in outcome_df.iterrows():
            if i >= 5:
                break
            outcome_name = str(row["value"]).capitalize()
            outcome_clr = "#3FB950" if "success" in outcome_name.lower() else "#F85149" if "fail" in outcome_name.lower() else "#8B949E"
            with outcome_cols[i]:
                st.markdown(f"""
                <div class="kpi-card" style="text-align:center; min-width:80px; padding:.75rem;">
                  <div class="kpi-label">{outcome_name}</div>
                  <div class="kpi-value" style="font-size:1.3rem;color:{outcome_clr}">{DataUtils.format_large_number(row['count'])}</div>
                </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Network
# ══════════════════════════════════════════════════════════════════════════════
with tab_network:
    col_src, col_dst = st.columns(2)

    def _horiz_bar(df: pd.DataFrame, title: str, color: str = "#58A6FF", height: int = 350) -> go.Figure:
        """Build a horizontal bar chart from a terms DataFrame."""
        if df.empty:
            return None
        # Truncate labels to 40 chars
        labels = df["value"].astype(str).str[:40]
        fig = go.Figure(go.Bar(
            x=df["count"],
            y=labels,
            orientation="h",
            marker=dict(
                color=df["count"],
                colorscale=[[0, "#1F3B5E"], [0.6, color], [1.0, "#F85149"]],
                showscale=False,
            ),
            hovertemplate="<b>%{y}</b><br>Events: %{x:,}<extra></extra>",
        ))
        fig.update_layout(
            title=dict(text=title, font=dict(size=12, color="#8B949E")),
            **_dark(height=height),
            xaxis=dict(title="Event Count", showgrid=True, gridcolor="#21262D"),
            yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
        )
        return fig

    with col_src:
        st.markdown('<div class="sec">Top Source IPs</div>', unsafe_allow_html=True)
        fig = _horiz_bar(src_ip_df.head(top_n), "Top Source IPs", color="#58A6FF")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No source IP data for the selected range.")

    with col_dst:
        st.markdown('<div class="sec">Top Destination IPs</div>', unsafe_allow_html=True)
        fig = _horiz_bar(dst_ip_df.head(top_n), "Top Destination IPs", color="#BC8CFF")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No destination IP data for the selected range.")

    # ── Top Event IDs ─────────────────────────────────────────────────────────
    st.markdown("<hr style='border-color:#21262D;margin:.5rem 0'>", unsafe_allow_html=True)
    st.markdown('<div class="sec">Top Event IDs / Types</div>', unsafe_allow_html=True)
    if not eventid_df.empty:
        col_ev_chart, col_ev_table = st.columns([2, 1])
        with col_ev_chart:
            fig_ev = _horiz_bar(eventid_df.head(10), "Top 10 Event IDs", color="#56D364", height=280)
            if fig_ev:
                st.plotly_chart(fig_ev, use_container_width=True)
        with col_ev_table:
            st.dataframe(
                eventid_df.head(15).rename(columns={"value": "Event ID", "count": "Count"}),
                hide_index=True, use_container_width=True, height=260,
            )
    else:
        st.info("No event ID data available.")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Identity
# ══════════════════════════════════════════════════════════════════════════════
with tab_identity:
    col_hosts, col_users = st.columns(2)

    with col_hosts:
        st.markdown('<div class="sec">Top Hosts by Event Volume</div>', unsafe_allow_html=True)
        fig = _horiz_bar(host_df.head(top_n), "Top Hosts", color="#3FB950")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No host data for the selected range.")

    with col_users:
        st.markdown('<div class="sec">Top Users by Event Volume</div>', unsafe_allow_html=True)
        fig = _horiz_bar(user_df.head(top_n), "Top Users", color="#D29922")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No user data for the selected range.")

    # ── Outcome breakdown ─────────────────────────────────────────────────────
    st.markdown("<hr style='border-color:#21262D;margin:.5rem 0'>", unsafe_allow_html=True)
    col_out_chart, col_out_table = st.columns([1, 2])

    with col_out_chart:
        st.markdown('<div class="sec">Outcome Distribution</div>', unsafe_allow_html=True)
        if not outcome_df.empty:
            out_colors = [
                "#3FB950" if "success" in str(v).lower()
                else "#F85149" if "fail" in str(v).lower()
                else "#8B949E"
                for v in outcome_df["value"]
            ]
            fig_out = go.Figure(go.Pie(
                labels=outcome_df["value"].str.capitalize(),
                values=outcome_df["count"],
                hole=0.55,
                marker=dict(colors=out_colors, line=dict(color="#0D1117", width=2)),
                hovertemplate="<b>%{label}</b><br>%{value:,}<extra></extra>",
            ))
            fig_out.update_layout(**_dark(height=260), showlegend=True,
                                  legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig_out, use_container_width=True)
        else:
            st.info("No outcome data.")

    with col_out_table:
        # Combined host+user top table
        st.markdown('<div class="sec">Host + User Summary Table</div>', unsafe_allow_html=True)
        if not host_df.empty or not user_df.empty:
            combined_rows = []
            for _, row in host_df.head(8).iterrows():
                combined_rows.append({"Type": "Host", "Entity": row["value"], "Events": row["count"]})
            for _, row in user_df.head(8).iterrows():
                combined_rows.append({"Type": "User", "Entity": row["value"], "Events": row["count"]})
            comb_df = pd.DataFrame(combined_rows).sort_values("Events", ascending=False)
            st.dataframe(comb_df, hide_index=True, use_container_width=True, height=240)
        else:
            st.info("No identity data.")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 4 — Categories
# ══════════════════════════════════════════════════════════════════════════════
with tab_categories:
    col_cat, col_sev2 = st.columns([3, 2])

    with col_cat:
        st.markdown('<div class="sec">Event Categories</div>', unsafe_allow_html=True)
        if not category_df.empty:
            # Treemap
            fig_tree = px.treemap(
                category_df.head(20),
                path=["value"],
                values="count",
                color="count",
                color_continuous_scale=[[0, "#1F3B5E"], [0.5, "#58A6FF"], [1, "#F85149"]],
            )
            fig_tree.update_traces(
                hovertemplate="<b>%{label}</b><br>Events: %{value:,}<extra></extra>",
                textinfo="label+value",
            )
            fig_tree.update_layout(**_dark(height=340), coloraxis_showscale=False)
            st.plotly_chart(fig_tree, use_container_width=True)
        else:
            st.info("No category data for the selected range.")

    with col_sev2:
        st.markdown('<div class="sec">Severity × Category Heatmap</div>', unsafe_allow_html=True)
        # We only have top-level terms, so show a simple stacked bars
        if not severity_df.empty and not category_df.empty:
            # Side-by-side horizontal bars for categories
            fig_sev_bar = go.Figure(go.Bar(
                x=severity_df["count"],
                y=severity_df["value"].str.capitalize(),
                orientation="h",
                marker=dict(
                    color=[SEV_COLORS.get(v.lower(), "#8B949E") for v in severity_df["value"]],
                ),
                hovertemplate="<b>%{y}</b><br>%{x:,}<extra></extra>",
            ))
            fig_sev_bar.update_layout(
                **_dark(height=340),
                xaxis=dict(title="Events", showgrid=True, gridcolor="#21262D"),
                yaxis=dict(autorange="reversed"),
                showlegend=False,
            )
            st.plotly_chart(fig_sev_bar, use_container_width=True)
        else:
            st.info("No severity data.")

    # ── Category table ────────────────────────────────────────────────────────
    if not category_df.empty:
        st.markdown("<hr style='border-color:#21262D;margin:.5rem 0'>", unsafe_allow_html=True)
        st.markdown('<div class="sec">Full Category Breakdown</div>', unsafe_allow_html=True)
        cat_display = category_df.rename(columns={"value": "Category", "count": "Events"}).copy()
        cat_display["% of Total"] = cat_display["Events"].apply(
            lambda x: DataUtils.safe_percentage(x, cat_display["Events"].sum())
        ).apply(lambda x: f"{x:.1f}%")
        st.dataframe(cat_display, hide_index=True, use_container_width=True, height=220)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 5 — Alerts (session-state integration)
# ══════════════════════════════════════════════════════════════════════════════
with tab_alerts:
    st.markdown('<div class="sec">🚨 Threat Intelligence Summary</div>', unsafe_allow_html=True)

    has_threats = bool(threat_results)
    has_sigma   = "sigma_report" in st.session_state
    has_ml      = "ml_scored_df" in st.session_state or "ml_summary" in st.session_state

    if not (has_threats or has_sigma or has_ml):
        st.markdown("""
        <div class="offline-banner" style="padding:2rem;">
          <div style="font-size:2rem;margin-bottom:.5rem;">🔬</div>
          <div style="font-weight:600;color:#E6EDF3;margin-bottom:.4rem;">
              No Detection Engine Results Yet</div>
          <div style="color:#8B949E;font-size:.88rem;">
              Run the detection engines first:<br>
              <b>📥 Log Retrieval</b> → <b>📋 Sigma Rules</b> → <b>🤖 ML Anomaly</b> → <b>🎯 Threat Scoring</b>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # ── Threat Score KPIs ─────────────────────────────────────────────────
        if has_threats:
            n_info  = len([r for r in threat_results if getattr(r, "risk_level", "") == "Info"])
            n_low   = len([r for r in threat_results if getattr(r, "risk_level", "") == "Low"])
            n_med   = len([r for r in threat_results if getattr(r, "risk_level", "") == "Medium"])
            n_high  = len([r for r in threat_results if getattr(r, "risk_level", "") == "High"])
            n_crit  = len([r for r in threat_results if getattr(r, "risk_level", "") == "Critical"])

            st.markdown(f"""
            <div class="kpi-row">
              <div class="kpi-card"><div class="kpi-accent" style="background:#F85149"></div>
                <div class="kpi-label">Critical</div>
                <div class="kpi-value" style="color:#F85149">{n_crit}</div></div>
              <div class="kpi-card"><div class="kpi-accent" style="background:#D29922"></div>
                <div class="kpi-label">High</div>
                <div class="kpi-value" style="color:#D29922">{n_high}</div></div>
              <div class="kpi-card"><div class="kpi-accent" style="background:#58A6FF"></div>
                <div class="kpi-label">Medium</div>
                <div class="kpi-value" style="color:#58A6FF">{n_med}</div></div>
              <div class="kpi-card"><div class="kpi-accent" style="background:#3FB950"></div>
                <div class="kpi-label">Low</div>
                <div class="kpi-value" style="color:#3FB950">{n_low}</div></div>
              <div class="kpi-card"><div class="kpi-accent" style="background:#8B949E"></div>
                <div class="kpi-label">Info</div>
                <div class="kpi-value" style="color:#8B949E">{n_info}</div></div>
            </div>
            """, unsafe_allow_html=True)

            # Threat level donut + score histogram
            col_tdist, col_thist = st.columns(2)
            with col_tdist:
                st.markdown('<div class="sec">Threat Level Distribution</div>', unsafe_allow_html=True)
                risk_counts = {}
                for r in threat_results:
                    lvl = getattr(r, "risk_level", "Info")
                    risk_counts[lvl] = risk_counts.get(lvl, 0) + 1
                fig_rdist = go.Figure(go.Pie(
                    labels=list(risk_counts.keys()),
                    values=list(risk_counts.values()),
                    hole=0.6,
                    marker=dict(
                        colors=[RISK_COLORS.get(k, "#8B949E") for k in risk_counts],
                        line=dict(color="#0D1117", width=2),
                    ),
                    hovertemplate="<b>%{label}</b><br>%{value}<extra></extra>",
                ))
                fig_rdist.update_layout(**_dark(height=260), showlegend=True,
                                        legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(fig_rdist, use_container_width=True)

            with col_thist:
                st.markdown('<div class="sec">Threat Score Distribution</div>', unsafe_allow_html=True)
                scores = [getattr(r, "threat_score", 0) for r in threat_results]
                fig_thist = go.Figure(go.Histogram(
                    x=scores,
                    nbinsx=20,
                    marker=dict(
                        color=scores,
                        colorscale=[[0, "#1F3B5E"], [0.5, "#D29922"], [1, "#F85149"]],
                        showscale=False,
                    ),
                ))
                fig_thist.update_layout(
                    **_dark(height=260),
                    xaxis=dict(title="Threat Score (0-100)", showgrid=True, gridcolor="#21262D"),
                    yaxis=dict(title="Count", showgrid=True, gridcolor="#21262D"),
                )
                st.plotly_chart(fig_thist, use_container_width=True)

            # ── Top Alerts Table ──────────────────────────────────────────────
            st.markdown("<hr style='border-color:#21262D;margin:.5rem 0'>", unsafe_allow_html=True)
            st.markdown('<div class="sec">Top Alerts — Ranked by Threat Score</div>', unsafe_allow_html=True)
            top_alerts = sorted(threat_results, key=lambda r: getattr(r, "threat_score", 0), reverse=True)[:25]
            alert_rows = []
            for r in top_alerts:
                alert_rows.append({
                    "Score":       getattr(r, "threat_score", 0),
                    "Risk Level":  getattr(r, "risk_level", "?"),
                    "Timestamp":   getattr(r, "timestamp", "N/A"),
                    "Doc ID":      getattr(r, "doc_id", "?"),
                    "Sigma Rules": ", ".join(getattr(r, "sigma_matches", [])) or "—",
                    "ML Score":    f"{getattr(r, 'ml_raw', 0.0):.3f}",
                })
            alert_df = pd.DataFrame(alert_rows)

            def _colour_risk(val):
                mapping = {
                    "Critical": "color:#F85149;font-weight:bold",
                    "High":     "color:#D29922;font-weight:bold",
                    "Medium":   "color:#58A6FF",
                    "Low":      "color:#3FB950",
                }
                return mapping.get(str(val), "")

            styled = alert_df.style.applymap(_colour_risk, subset=["Risk Level"])
            st.dataframe(styled, hide_index=True, use_container_width=True, height=360)

            # Expandable explanations for top 5
            st.markdown('<div class="sec" style="margin-top:.75rem;">Top 5 Alert Explanations</div>',
                        unsafe_allow_html=True)
            for r in top_alerts[:5]:
                explanation = getattr(r, "explanation", "No explanation available.")
                risk        = getattr(r, "risk_level", "Info")
                score       = getattr(r, "threat_score", 0)
                clr = RISK_COLORS.get(risk, "#8B949E")
                with st.expander(
                    f"{'🔴' if risk=='Critical' else '🟠' if risk=='High' else '🟡' if risk=='Medium' else '🟢'} "
                    f"**{risk}** (score {score}/100) — {getattr(r, 'doc_id', '?')}"
                ):
                    st.markdown(
                        f"<div style='border-left:3px solid {clr};padding-left:.75rem;'>"
                        f"{explanation}</div>",
                        unsafe_allow_html=True,
                    )
                    if hasattr(r, "raw_source") and r.raw_source:
                        with st.expander("Raw event data"):
                            st.json(r.raw_source)

        # ── ML Summary ────────────────────────────────────────────────────────
        ml_summary = st.session_state.get("ml_summary")
        if ml_summary:
            st.markdown("<hr style='border-color:#21262D;margin:.5rem 0'>", unsafe_allow_html=True)
            st.markdown('<div class="sec">🤖 ML Anomaly Summary (Current Batch)</div>', unsafe_allow_html=True)
            ml_cols = st.columns(4)
            ml_fields = [
                ("Total Logs",      "n_total",          "#58A6FF"),
                ("Anomalies",       "n_anomalies",      "#F85149"),
                ("Anomaly Rate",    "anomaly_rate_pct", "#D29922"),
                ("Max Score",       "max_score",        "#BC8CFF"),
            ]
            for col, (label, key, color) in zip(ml_cols, ml_fields):
                val = ml_summary.get(key, 0)
                display = f"{val:.1f}%" if key == "anomaly_rate_pct" else str(val)
                with col:
                    st.markdown(f"""
                    <div class="kpi-card" style="text-align:center;">
                      <div class="kpi-label">{label}</div>
                      <div class="kpi-value" style="color:{color};font-size:1.4rem;">{display}</div>
                    </div>""", unsafe_allow_html=True)

        # ── Sigma Summary ─────────────────────────────────────────────────────
        sigma_report = st.session_state.get("sigma_report")
        if sigma_report:
            st.markdown("<hr style='border-color:#21262D;margin:.5rem 0'>", unsafe_allow_html=True)
            st.markdown('<div class="sec">📋 Sigma Detection Summary (Current Batch)</div>',
                        unsafe_allow_html=True)
            s_col1, s_col2 = st.columns(2)
            with s_col1:
                matched_hits = getattr(sigma_report, "matched_hits", len(getattr(sigma_report, "matches", [])))
                total_triggers = getattr(sigma_report, "total_rule_triggers", 0)
                st.markdown(f"""
                <div class="kpi-row">
                  <div class="kpi-card">
                    <div class="kpi-label">Matched Events</div>
                    <div class="kpi-value" style="color:#F85149">{matched_hits}</div></div>
                  <div class="kpi-card">
                    <div class="kpi-label">Rule Triggers</div>
                    <div class="kpi-value" style="color:#D29922">{total_triggers}</div></div>
                </div>""", unsafe_allow_html=True)
            with s_col2:
                triggered_rules = getattr(sigma_report, "triggered_rules", [])
                if triggered_rules:
                    rules_df = pd.DataFrame([{
                        "Rule":     getattr(r, "title", "?"),
                        "Severity": getattr(r, "severity", "?"),
                        "Hits":     sigma_report.rule_trigger_counts.get(getattr(r, "rule_id", ""), 0)
                    } for r in triggered_rules[:10]])
                    st.dataframe(rules_df, hide_index=True, use_container_width=True, height=200)


# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<hr style='border-color:#21262D;margin-top:2rem;'>", unsafe_allow_html=True)
st.caption(
    f"ISRO SOC Analytics · {settings.app_title} · "
    f"Index: {idx_pattern} · "
    f"Total events: {DataUtils.format_large_number(total_events)} · "
    f"Interval: {interval} · Cache TTL: {cache_ttl}s"
)
