"""
pages/3_🚨_Alerts.py

Alert Correlation & Triage — event counts by severity and category
using ES aggregations. Provides a triage workspace with session-state
status tracking.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from config import settings, get_logger
from core import get_es_client, query_builder
from utils import TimeUtils, DataUtils, ChartUtils

logger = get_logger(__name__)

st.set_page_config(
    page_title=f"{settings.app_title} | Alerts",
    page_icon="🚨",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .block-container { padding-top: 1.5rem !important; }
    [data-testid="metric-container"] {
        background: #161B22; border: 1px solid #30363D; border-radius: 12px; padding: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("## 🚨 Alert Correlation & Triage")
st.markdown(
    "<p style='color:#8B949E; margin-top:-0.5rem;'>Aggregate and triage security alerts from the Elasticsearch dataset.</p>",
    unsafe_allow_html=True,
)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⏱️ Time Range")
    presets = TimeUtils.available_presets()
    preset = st.selectbox("Preset", list(presets.keys()), index=3)
    from_iso, to_iso = presets[preset]()

    st.markdown("### ⚙️ Fields")
    time_field = st.text_input("Timestamp field", value="@timestamp")
    severity_field = st.text_input("Severity field", value="event.severity")
    category_field = st.text_input("Category field", value="event.category")
    rule_field = st.text_input("Rule/Alert field", value="rule.name")

# ─── Fetch aggregations ───────────────────────────────────────────────────────
@st.cache_data(ttl=settings.cache_ttl_seconds, show_spinner=False)
def fetch_alert_aggs(index, from_iso, to_iso, time_field, severity_field, category_field, rule_field, interval):
    client = get_es_client()
    body = {
        "size": 0,
        "query": query_builder.bool_query(
            filter=[query_builder.time_range_filter(time_field, from_iso, to_iso)]
        ),
        "aggs": query_builder.merge_aggs(
            query_builder.date_histogram_agg("alerts_timeline", time_field, calendar_interval=interval),
            query_builder.terms_agg("by_severity", severity_field, size=20),
            query_builder.terms_agg("by_category", category_field, size=20),
            query_builder.terms_agg("by_rule", rule_field, size=30),
        ),
    }
    try:
        aggs = client.aggregate(index=index, body=body)
        total = client.count(
            index=index,
            query={"range": {time_field: {"gte": from_iso, "lte": to_iso}}}
        )
        return aggs, total, None
    except Exception as e:
        return {}, 0, str(e)

interval = TimeUtils.auto_interval(from_iso, to_iso)
with st.spinner("Loading alert aggregations..."):
    aggs, total, error = fetch_alert_aggs(
        settings.es_index_pattern, from_iso, to_iso,
        time_field, severity_field, category_field, rule_field, interval
    )

if error:
    st.error(f"❌ {error}")
    st.stop()

# ─── Parse ────────────────────────────────────────────────────────────────────
timeline_df = DataUtils.date_histogram_to_df(aggs.get("alerts_timeline", {}))
severity_df = DataUtils.terms_to_df(aggs.get("by_severity", {}))
category_df = DataUtils.terms_to_df(aggs.get("by_category", {}))
rule_df = DataUtils.terms_to_df(aggs.get("by_rule", {}))

# ─── KPIs ─────────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Alerts", DataUtils.format_large_number(total))
k2.metric("Severity Buckets", len(severity_df))
k3.metric("Categories", len(category_df))
k4.metric("Unique Rules", len(rule_df))

st.markdown("<hr style='border-color:#30363D;'>", unsafe_allow_html=True)

# ─── Charts ───────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 2])
with col1:
    fig = ChartUtils.event_volume_chart(timeline_df, title="Alert Volume Over Time", colour="#F85149", height=300)
    st.plotly_chart(fig, use_container_width=True)
with col2:
    fig_sev = ChartUtils.severity_donut(severity_df, title="Alert Severity Distribution", height=300)
    st.plotly_chart(fig_sev, use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    fig_cat = ChartUtils.horizontal_bar_chart(category_df, title="Top Alert Categories", height=350, colour="#D29922")
    st.plotly_chart(fig_cat, use_container_width=True)
with col4:
    fig_rule = ChartUtils.horizontal_bar_chart(rule_df, title="Top Triggered Rules", height=350, colour="#BC8CFF")
    st.plotly_chart(fig_rule, use_container_width=True)

# ─── Triage Workspace ─────────────────────────────────────────────────────────
st.markdown("### 📋 Triage Workspace")
st.caption("Use this workspace to track investigation status for top triggered rules.")

if not rule_df.empty:
    if "triage_status" not in st.session_state:
        st.session_state["triage_status"] = {}

    status_options = ["🔴 Open", "🟡 Investigating", "🟢 Resolved", "⚪ Dismissed"]
    triage_data = []
    for _, row in rule_df.head(15).iterrows():
        rule_name = str(row["value"])
        current = st.session_state["triage_status"].get(rule_name, "🔴 Open")
        triage_data.append({
            "Rule": rule_name,
            "Hits": int(row["count"]),
            "Status": current,
        })

    triage_df = pd.DataFrame(triage_data)
    edited = st.data_editor(
        triage_df,
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=status_options),
            "Hits": st.column_config.NumberColumn("Hits", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
    )

    # Persist edits
    for _, row in edited.iterrows():
        st.session_state["triage_status"][row["Rule"]] = row["Status"]
else:
    st.info("No rule data available for triage workspace.")
