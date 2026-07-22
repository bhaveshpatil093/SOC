"""
pages/2_🔍_Threat_Hunter.py

Threat Hunter — free-form query builder with time-range filtering,
field selection, and paginated result display.

All queries use a safety-capped size (MAX_SAFE_SIZE) to prevent
accidental memory exhaustion.
"""

from __future__ import annotations

import json
import streamlit as st
import pandas as pd

from config import settings, get_logger
from core import get_es_client, query_builder
from core.elasticsearch_client import MAX_SAFE_SIZE
from utils import TimeUtils, DataUtils

logger = get_logger(__name__)

st.set_page_config(
    page_title=f"{settings.app_title} | Threat Hunter",
    page_icon="🔍",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
    .block-container { padding-top: 1.5rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("## 🔍 Threat Hunter")
st.markdown(
    "<p style='color:#8B949E; margin-top:-0.5rem;'>Build queries and explore events interactively. "
    "Results are paginated — raw logs are never fully loaded into memory.</p>",
    unsafe_allow_html=True,
)

# ─── Sidebar controls ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⏱️ Time Range")
    presets = TimeUtils.available_presets()
    selected_preset = st.selectbox("Preset", list(presets.keys()), index=3)
    from_iso, to_iso = presets[selected_preset]()

    st.markdown("### 🔧 Query Options")
    time_field = st.text_input("Timestamp field", value="@timestamp")
    result_size = st.slider("Max results", min_value=10, max_value=500, value=100, step=10)
    sort_order = st.selectbox("Sort order", ["Newest first", "Oldest first"])
    sort_dir = "desc" if sort_order == "Newest first" else "asc"

# ─── Query builder UI ─────────────────────────────────────────────────────────
tab_simple, tab_dsl = st.tabs(["🔎 Simple Filter", "🛠️ Raw DSL"])

with tab_simple:
    st.markdown("#### Add Filters")
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        filter_field = st.text_input("Field", value="event.category", key="filter_field")
    with c2:
        filter_value = st.text_input("Value (exact match)", value="", key="filter_value")
    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        add_filter = st.button("＋ Add Filter")

    if "active_filters" not in st.session_state:
        st.session_state["active_filters"] = []

    if add_filter and filter_field and filter_value:
        st.session_state["active_filters"].append({"field": filter_field, "value": filter_value})

    if st.session_state["active_filters"]:
        st.markdown("**Active filters:**")
        for i, f in enumerate(st.session_state["active_filters"]):
            fc1, fc2 = st.columns([4, 1])
            fc1.code(f'{f["field"]} = "{f["value"]}"', language=None)
            if fc2.button("✕", key=f"del_{i}"):
                st.session_state["active_filters"].pop(i)
                st.rerun()

    extra_filters = [
        query_builder.term_filter(f["field"], f["value"])
        for f in st.session_state["active_filters"]
    ]
    search_body = {
        "size": min(result_size, MAX_SAFE_SIZE),
        "sort": [{time_field: {"order": sort_dir}}],
        "query": query_builder.bool_query(
            filter=[query_builder.time_range_filter(time_field, from_iso, to_iso)]
            + extra_filters
        ),
    }

with tab_dsl:
    st.markdown("#### Custom DSL Query Body")
    default_dsl = json.dumps(
        {
            "size": 50,
            "sort": [{time_field: {"order": sort_dir}}],
            "query": {
                "bool": {
                    "filter": [{"range": {time_field: {"gte": from_iso, "lte": to_iso}}}]
                }
            },
        },
        indent=2,
    )
    dsl_input = st.text_area("Query DSL (JSON)", value=default_dsl, height=280)
    try:
        search_body = json.loads(dsl_input)
        st.success("✅ Valid JSON")
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        search_body = None

# ─── Execute query ────────────────────────────────────────────────────────────
run_query = st.button("▶ Run Query", type="primary", use_container_width=False)

if run_query and search_body is not None:
    with st.spinner("Querying Elasticsearch..."):
        try:
            client = get_es_client()
            resp = client.search(
                index=settings.es_index_pattern,
                body=search_body,
                enforce_size_limit=True,
            )
            hits = resp.get("hits", {}).get("hits", [])
            total = resp.get("hits", {}).get("total", {})
            total_value = total.get("value", 0) if isinstance(total, dict) else total

            st.markdown(f"### Results — {DataUtils.format_large_number(total_value)} total matches")
            st.caption(f"Showing {len(hits)} of {total_value:,} matching documents")

            if hits:
                df = DataUtils.hits_to_df(hits)
                df = DataUtils.sanitize_df(df)
                st.dataframe(df, use_container_width=True, height=450)

                # Download button
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇ Download CSV",
                    data=csv,
                    file_name="threat_hunter_results.csv",
                    mime="text/csv",
                )
            else:
                st.info("No documents matched the query.")

        except ValueError as ve:
            st.error(f"Safety limit exceeded: {ve}")
        except Exception as e:
            st.error(f"Query failed: {e}")
            logger.error("Threat Hunter query failed: %s", e)
else:
    st.info("Configure your filters above and click **▶ Run Query** to search.")
