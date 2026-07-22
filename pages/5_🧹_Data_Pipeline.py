"""
pages/9_🧹_Data_Pipeline.py

Data Preparation Pipeline — ISRO SOC Analytics Platform

Provides a rich UI for running the preprocessing pipeline on any batch of
logs retrieved from the Log Retrieval page or fetched ad hoc.

Displays:
  - 5-tab result view: Quality | Exploration | Cleaned Data | Features | Export
  - Stage-by-stage timing waterfall
  - Null coverage heatmap
  - Value distribution plots
  - Feature column distributions

Memory-safe: never loads more than one page (up to 1 000 docs) at a time.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from config import settings, get_logger
from core import get_es_client
from core.log_retriever import LogRetriever, LogFilter, PageResult
from core.preprocessing import (
    PreprocessingPipeline,
    PipelineConfig,
    PipelineResult,
    BatchQualityReport,
    FEAT_PREFIX,
    ORIGINAL_COL,
)
from utils.data_utils import DataUtils

logger = get_logger(__name__)

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{settings.app_title} | Data Pipeline",
    page_icon="🧹",
    layout="wide",
)

# ─── Session State Keys ───────────────────────────────────────────────────────
_SK_RESULT   = "pp_result"    # PipelineResult
_SK_CONFIG   = "pp_config"    # PipelineConfig used
_SK_RAW_HITS = "pp_raw_hits"  # List[Dict] — source data for this run

# ─── Styles ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.block-container { padding-top: 1.25rem !important; }

/* ── KPI card ── */
.kpi-row { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.kpi-card {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    min-width: 160px;
    flex: 1;
}
.kpi-label { font-size: 0.7rem; color: #8B949E; text-transform: uppercase; letter-spacing: 0.6px; }
.kpi-value { font-size: 1.75rem; font-weight: 700; color: #E6EDF3; margin-top: 0.1rem; }
.kpi-sub   { font-size: 0.75rem; color: #8B949E; margin-top: 0.1rem; }
.kpi-green  { border-top: 3px solid #3FB950; }
.kpi-blue   { border-top: 3px solid #58A6FF; }
.kpi-yellow { border-top: 3px solid #D29922; }
.kpi-purple { border-top: 3px solid #BC8CFF; }
.kpi-red    { border-top: 3px solid #F85149; }

/* ── Section heading ── */
.sec { font-size:0.78rem; font-weight:600; color:#8B949E; text-transform:uppercase;
       letter-spacing:0.8px; padding-bottom:0.25rem; border-bottom:1px solid #30363D;
       margin-bottom:0.6rem; }

/* ── Inline badge ── */
.badge {
    display:inline-block; border-radius:8px; padding:1px 8px;
    font-size:0.72rem; font-weight:600; margin:1px;
}
.badge-green  { background:rgba(63,185,80,.15);  color:#3FB950; }
.badge-yellow { background:rgba(210,153,34,.15); color:#D29922; }
.badge-red    { background:rgba(248,81,73,.15);  color:#F85149; }
.badge-blue   { background:rgba(88,166,255,.15); color:#58A6FF; }
.badge-grey   { background:rgba(139,148,158,.1); color:#8B949E; }

/* ── Stage bar ── */
.stage-bar { margin:4px 0; }
.stage-label { font-size:0.72rem; color:#8B949E; width:130px; display:inline-block; }
.stage-fill  { display:inline-block; height:10px; border-radius:4px; background:#58A6FF; }

[data-testid="metric-container"] {
    background: #161B22; border: 1px solid #30363D; border-radius: 12px; padding:0.9rem;
}
</style>
""", unsafe_allow_html=True)


# ─── Helper: Dark Plotly layout ───────────────────────────────────────────────
def _dark_layout(**kwargs) -> dict:
    base = dict(
        paper_bgcolor="#161B22", plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3", family="Inter", size=11),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    base.update(kwargs)
    return base


# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 🧹 Data Preparation Pipeline")
st.markdown(
    "<p style='color:#8B949E;margin-top:-0.5rem;'>"
    "Batch-scoped preprocessing: flatten → clean → deduplicate → feature-engineer. "
    "Operates only on retrieved batches, never on the full 2.77B-log dataset.</p>",
    unsafe_allow_html=True,
)

# ─── Sidebar: Pipeline Configuration ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Pipeline Configuration")

    missing_strategy = st.selectbox(
        "Missing value strategy",
        options=["flag (keep NaN)", "fill_default", "drop rows"],
        index=0,
        help="flag=preserve NaN | fill_default=replace with defaults | drop=remove rows with any NaN",
    )
    strategy_map = {"flag (keep NaN)": "flag", "fill_default": "fill_default", "drop rows": "drop"}
    chosen_strategy = strategy_map[missing_strategy]

    max_null_pct = st.slider(
        "Drop column if null %  ≥",
        min_value=50, max_value=100, value=95, step=5,
        help="Columns where this fraction of values are null will be dropped.",
    )
    dedup_enabled = st.checkbox("Deduplicate rows", value=True)
    extract_time  = st.checkbox("Extract time features", value=True)
    extract_ip    = st.checkbox("Extract IP features", value=True)
    extract_freq  = st.checkbox("Extract frequency features", value=True)
    keep_original = st.checkbox("Preserve raw _source column", value=True)

    st.markdown("<hr style='border-color:#30363D;margin:0.5rem 0;'>", unsafe_allow_html=True)

    with st.expander("🗂️ Custom Field Rename Map"):
        rename_raw = st.text_area(
            "JSON rename map  {old: new}",
            placeholder='{"winlog.event_id": "event.id"}',
            height=80,
        )

    st.markdown("<hr style='border-color:#30363D;margin:0.5rem 0;'>", unsafe_allow_html=True)
    st.markdown("### 📥 Data Source")
    source_mode = st.radio(
        "Source",
        ["From Log Retrieval cache", "Fetch fresh sample from ES"],
        index=0,
    )
    fetch_index  = st.text_input("Index", value=settings.es_index_pattern)
    fetch_n      = st.slider("Sample size (fresh fetch)", 50, 1000, 200, step=50)
    time_preset  = st.selectbox(
        "Time range (fresh fetch)",
        ["Last 1 hour", "Last 6 hours", "Last 24 hours", "Last 7 days", "All of June 2026"],
        index=2,
    )


# ─── Build PipelineConfig ─────────────────────────────────────────────────────
def _build_config() -> PipelineConfig:
    rename_map: Dict[str, str] = {}
    if rename_raw.strip():
        try:
            rename_map = json.loads(rename_raw)
        except json.JSONDecodeError:
            st.warning("⚠️ Invalid JSON in rename map — rename map ignored.")

    return PipelineConfig(
        missing_strategy=chosen_strategy,
        max_null_pct=max_null_pct / 100,
        dedup_enabled=dedup_enabled,
        extract_time_features=extract_time,
        extract_ip_features=extract_ip,
        extract_frequency_features=extract_freq,
        keep_original=keep_original,
        field_rename_map=rename_map,
    )


# ─── Data source resolution ────────────────────────────────────────────────────
def _get_raw_hits() -> List[Dict[str, Any]]:
    """Return raw ES hits from either session cache or a fresh ES query."""
    if source_mode == "From Log Retrieval cache":
        pages: Dict[int, PageResult] = st.session_state.get("lr_pages", {})
        if not pages:
            return []
        # Merge all cached pages (up to 1 000 docs for memory safety)
        merged: List[Dict] = []
        for page in sorted(pages.values(), key=lambda p: p.page_num):
            merged.extend(page.hits)
            if len(merged) >= 1000:
                break
        return merged[:1000]
    else:
        # Fresh sample using the LogRetriever
        from utils.time_utils import TimeUtils
        preset_range = TimeUtils.get_preset_range(time_preset)
        f = LogFilter(
            from_dt=TimeUtils.to_iso(preset_range[0]),
            to_dt=TimeUtils.to_iso(preset_range[1]),
            page_size=fetch_n,
        )
        try:
            retriever = LogRetriever(get_es_client(), fetch_index)
            result = retriever.fetch_page(f, cursor=None, page_num=0)
            return result.hits
        except Exception as exc:
            st.error(f"❌ Fresh fetch failed: {exc}")
            return []


# ─── Run pipeline ─────────────────────────────────────────────────────────────
col_run, col_info = st.columns([1, 4])
with col_run:
    run_clicked = st.button("▶ Run Pipeline", type="primary", use_container_width=True)
with col_info:
    lr_pages = st.session_state.get("lr_pages", {})
    cached_hits = sum(len(p.hits) for p in lr_pages.values())
    if source_mode == "From Log Retrieval cache" and cached_hits:
        st.markdown(
            f"<span style='font-size:0.83rem;color:#8B949E;'>"
            f"📦 Log Retrieval cache: "
            f"<b style='color:#58A6FF;'>{cached_hits:,}</b> hits across "
            f"<b style='color:#58A6FF;'>{len(lr_pages)}</b> page(s) "
            f"(pipeline will use up to 1 000)</span>",
            unsafe_allow_html=True,
        )
    elif source_mode == "From Log Retrieval cache":
        st.markdown(
            "<span style='color:#D29922;font-size:0.83rem;'>"
            "⚠️ No cached data found. Go to the 📥 Log Retrieval page and run a search first, "
            "or switch to 'Fetch fresh sample' mode.</span>",
            unsafe_allow_html=True,
        )

if run_clicked:
    with st.spinner("Resolving data source..."):
        raw_hits = _get_raw_hits()

    if not raw_hits:
        st.error("❌ No data available. Check your source mode or retrieve logs first.")
    else:
        cfg = _build_config()
        pipeline = PreprocessingPipeline()
        with st.spinner(f"Running pipeline on {len(raw_hits):,} records..."):
            result = pipeline.run(raw_hits, config=cfg)
        st.session_state[_SK_RESULT]   = result
        st.session_state[_SK_CONFIG]   = cfg
        st.session_state[_SK_RAW_HITS] = raw_hits
        st.success(
            f"✅ Pipeline complete — "
            f"{result.quality.input_count:,} in → {result.quality.output_count:,} out "
            f"({result.quality.duplicates_removed} dupes removed) "
            f"| {result.quality.elapsed_ms:.0f} ms"
        )

# ─── Results ──────────────────────────────────────────────────────────────────
result: Optional[PipelineResult] = st.session_state.get(_SK_RESULT)

if result is None:
    st.markdown(
        """<div style="background:#161B22;border:1px dashed #30363D;border-radius:12px;
        padding:2.5rem;text-align:center;margin-top:1rem;">
        <div style="font-size:2.5rem;margin-bottom:0.5rem;">🧹</div>
        <div style="font-weight:600;color:#E6EDF3;margin-bottom:0.4rem;">Configure the pipeline and click ▶ Run Pipeline</div>
        <div style="color:#8B949E;font-size:0.85rem;">
            The pipeline operates on one batch at a time.<br>
            First retrieve logs on the 📥 Log Retrieval page, then process them here.
        </div></div>""",
        unsafe_allow_html=True,
    )
    st.stop()

q = result.quality

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_quality, tab_explore, tab_clean, tab_feat, tab_export = st.tabs([
    "📊 Quality Metrics",
    "🔍 Exploration",
    "🧼 Cleaned Data",
    f"⚙️ Features ({result.n_features})",
    "⬇ Export",
])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Quality Metrics
# ══════════════════════════════════════════════════════════════════════════════
with tab_quality:

    # KPI bar
    cov_colour = "kpi-green" if q.coverage_score >= 80 else "kpi-yellow" if q.coverage_score >= 50 else "kpi-red"
    ret_colour = "kpi-green" if q.retention_rate >= 95 else "kpi-yellow"
    st.markdown(
        f"""<div class="kpi-row">
        <div class="kpi-card kpi-blue">
            <div class="kpi-label">Input Records</div>
            <div class="kpi-value">{q.input_count:,}</div>
            <div class="kpi-sub">Raw ES hits</div>
        </div>
        <div class="kpi-card {ret_colour}">
            <div class="kpi-label">Output Records</div>
            <div class="kpi-value">{q.output_count:,}</div>
            <div class="kpi-sub">Retention: {q.retention_rate:.1f}%</div>
        </div>
        <div class="kpi-card kpi-yellow">
            <div class="kpi-label">Duplicates Removed</div>
            <div class="kpi-value">{q.duplicates_removed:,}</div>
            <div class="kpi-sub">{q.dedup_rate:.1f}% of input</div>
        </div>
        <div class="kpi-card {cov_colour}">
            <div class="kpi-label">Coverage Score</div>
            <div class="kpi-value">{q.coverage_score:.1f}%</div>
            <div class="kpi-sub">Avg field coverage</div>
        </div>
        <div class="kpi-card kpi-purple">
            <div class="kpi-label">Features Added</div>
            <div class="kpi-value">{result.n_features}</div>
            <div class="kpi-sub">_feat_* columns</div>
        </div>
        <div class="kpi-card kpi-blue">
            <div class="kpi-label">Pipeline Time</div>
            <div class="kpi-value">{q.elapsed_ms:.0f}</div>
            <div class="kpi-sub">milliseconds</div>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("<hr style='border-color:#30363D;'>", unsafe_allow_html=True)
    col_a, col_b = st.columns([1, 1])

    # ── Stage timing waterfall ────────────────────────────────────────────────
    with col_a:
        st.markdown('<div class="sec">⏱ Stage Timings</div>', unsafe_allow_html=True)
        if q.stage_timings:
            stages_df = pd.DataFrame([
                {"Stage": k.split("_", 1)[1].replace("_", " ").title(), "ms": v}
                for k, v in sorted(q.stage_timings.items())
            ])
            max_ms = stages_df["ms"].max() or 1
            fig_stages = go.Figure(go.Bar(
                x=stages_df["ms"],
                y=stages_df["Stage"],
                orientation="h",
                marker=dict(
                    color=stages_df["ms"],
                    colorscale=[[0, "#1F3B5E"], [1, "#58A6FF"]],
                    showscale=False,
                ),
                text=stages_df["ms"].apply(lambda v: f"{v:.1f}ms"),
                textposition="outside",
                hovertemplate="%{y}: %{x:.1f} ms<extra></extra>",
            ))
            fig_stages.update_layout(
                **_dark_layout(height=260),
                xaxis=dict(showgrid=True, gridcolor="#30363D", title="ms"),
                yaxis=dict(showgrid=False),
            )
            st.plotly_chart(fig_stages, use_container_width=True)

    # ── Type conversions + issues ─────────────────────────────────────────────
    with col_b:
        st.markdown('<div class="sec">🔢 Type Handling</div>', unsafe_allow_html=True)
        tm1, tm2, tm3 = st.columns(3)
        tm1.metric("Timestamps OK",      q.timestamp_normalized)
        tm2.metric("Timestamp Errors",   q.timestamp_parse_errors)
        tm3.metric("Numeric Coercions",  sum(q.numeric_coercions.values()))

        if q.numeric_coercions:
            st.caption("Fields auto-coerced to numeric:")
            nc_df = pd.DataFrame([
                {"Field": k, "Records coerced": v}
                for k, v in q.numeric_coercions.items()
            ])
            st.dataframe(nc_df, hide_index=True, use_container_width=True, height=130)

        if q.dropped_columns:
            st.markdown(
                f"<div class='sec' style='margin-top:0.5rem;'>🗑 Dropped Columns ({len(q.dropped_columns)})</div>",
                unsafe_allow_html=True,
            )
            pills = " ".join(
                f"<span class='badge badge-red'>{c}</span>"
                for c in q.dropped_columns
            )
            st.markdown(pills, unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#30363D;'>", unsafe_allow_html=True)

    # ── Null coverage table ────────────────────────────────────────────────────
    st.markdown('<div class="sec">🔍 Field Coverage Analysis</div>', unsafe_allow_html=True)

    if q.null_pct:
        null_df = pd.DataFrame([
            {
                "Field": k,
                "Null Count": q.null_counts.get(k, 0),
                "Null %": round(v * 100, 1),
                "Coverage %": round((1 - v) * 100, 1),
            }
            for k, v in sorted(q.null_pct.items(), key=lambda x: -x[1])
        ])

        # Coverage bar via progress-column styling
        def _cov_colour(val):
            if val >= 90: return "color: #3FB950; font-weight:600"
            if val >= 50: return "color: #D29922; font-weight:600"
            return "color: #F85149; font-weight:600"

        display_null_df = null_df[["Field", "Null Count", "Null %", "Coverage %"]]
        st.dataframe(
            display_null_df.style.applymap(_cov_colour, subset=["Coverage %"]),
            use_container_width=True,
            height=350,
            hide_index=True,
        )

        # Null heatmap for top-N most-null fields
        st.markdown('<div class="sec" style="margin-top:0.75rem;">🌡 Null Heatmap (top 20 fields by null %)</div>',
                    unsafe_allow_html=True)
        top_null_cols = null_df.nlargest(20, "Null %")["Field"].tolist()
        if top_null_cols and not result.original_df.empty:
            heat_df = result.original_df[
                [c for c in top_null_cols if c in result.original_df.columns]
            ].isna().astype(int)

            # Sample rows for display (max 100)
            display_heat = heat_df.head(100)
            fig_heat = go.Figure(go.Heatmap(
                z=display_heat.values.T.tolist(),
                x=[f"Row {i}" for i in range(len(display_heat))],
                y=display_heat.columns.tolist(),
                colorscale=[[0, "#1A2A1A"], [1, "#F85149"]],
                showscale=False,
                hovertemplate="Field: %{y}<br>Row: %{x}<br>Is Null: %{z}<extra></extra>",
            ))
            fig_heat.update_layout(
                **_dark_layout(height=max(250, 20 * len(top_null_cols))),
                xaxis=dict(showticklabels=False),
                yaxis=dict(showgrid=False, tickfont=dict(size=10)),
            )
            st.plotly_chart(fig_heat, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Exploratory Analysis
# ══════════════════════════════════════════════════════════════════════════════
with tab_explore:
    st.markdown('<div class="sec">🔍 Exploratory Data Analysis</div>', unsafe_allow_html=True)

    if result.cleaned_df.empty:
        st.info("No cleaned data to explore.")
    else:
        cdf = result.cleaned_df

        # ── Timestamp distribution ────────────────────────────────────────────
        dt_col = f"{settings.es_time_field}_dt"
        if dt_col in cdf.columns and cdf[dt_col].notna().any():
            st.markdown('<div class="sec">📅 Event Timeline</div>', unsafe_allow_html=True)
            ts_series = pd.to_datetime(cdf[dt_col], errors="coerce", utc=True)
            ts_df = ts_series.dt.floor("h").value_counts().sort_index().reset_index()
            ts_df.columns = ["hour", "count"]

            fig_ts = go.Figure(go.Bar(
                x=ts_df["hour"], y=ts_df["count"],
                marker=dict(color="#58A6FF"),
                hovertemplate="%{x|%Y-%m-%d %H:%M}: %{y} events<extra></extra>",
            ))
            fig_ts.update_layout(
                **_dark_layout(height=200),
                xaxis=dict(showgrid=False, title=None),
                yaxis=dict(showgrid=True, gridcolor="#30363D", title="Events"),
            )
            st.plotly_chart(fig_ts, use_container_width=True)

        # ── Field distribution explorer ────────────────────────────────────────
        st.markdown('<div class="sec">📊 Field Value Distribution</div>', unsafe_allow_html=True)
        # Only show object/category columns (exclude feature cols and raw col)
        cat_cols = [
            c for c in cdf.select_dtypes(include=["object", "category"]).columns
            if c != ORIGINAL_COL and not c.startswith(FEAT_PREFIX)
        ]

        if cat_cols:
            explore_col = st.selectbox("Select a field to explore", cat_cols, key="explore_col")
            top_n_vals  = st.slider("Top N values", 5, 50, 20, key="explore_topn")

            vc = cdf[explore_col].value_counts().head(top_n_vals).reset_index()
            vc.columns = ["value", "count"]
            vc["pct"] = DataUtils.safe_percentage(vc["count"], vc["count"].sum())

            fig_vc = go.Figure(go.Bar(
                x=vc["count"], y=vc["value"],
                orientation="h",
                marker=dict(
                    color=vc["count"],
                    colorscale=[[0, "#1F3B5E"], [1, "#58A6FF"]],
                ),
                text=vc["count"].apply(lambda v: f"{v:,}"),
                textposition="outside",
                hovertemplate="%{y}: %{x:,} (%{customdata:.1f}%)<extra></extra>",
                customdata=vc["pct"],
            ))
            fig_vc.update_layout(
                title=f"Top {top_n_vals} values for '{explore_col}'",
                **_dark_layout(height=max(250, 22 * top_n_vals)),
                xaxis=dict(showgrid=True, gridcolor="#30363D"),
                yaxis=dict(showgrid=False, autorange="reversed"),
            )
            st.plotly_chart(fig_vc, use_container_width=True)

        # ── Numeric column summary ─────────────────────────────────────────────
        num_cols = [
            c for c in cdf.select_dtypes(include=[np.number]).columns
            if not c.startswith(FEAT_PREFIX)
        ]
        if num_cols:
            st.markdown('<div class="sec" style="margin-top:0.75rem;">🔢 Numeric Column Stats</div>',
                        unsafe_allow_html=True)
            num_stats = cdf[num_cols].describe().T.round(2)
            st.dataframe(num_stats, use_container_width=True, height=250)

        # ── Field cardinality summary ──────────────────────────────────────────
        st.markdown('<div class="sec" style="margin-top:0.75rem;">🎲 Cardinality Summary</div>',
                    unsafe_allow_html=True)
        card_df = pd.DataFrame([
            {
                "Field": c,
                "Type": str(cdf[c].dtype),
                "Unique Values": cdf[c].nunique(),
                "Sample": str(cdf[c].dropna().iloc[0]) if cdf[c].notna().any() else "—",
            }
            for c in cdf.columns if c != ORIGINAL_COL and not c.startswith(FEAT_PREFIX)
        ]).sort_values("Unique Values", ascending=False)
        st.dataframe(card_df, use_container_width=True, height=300, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Cleaned Data Preview
# ══════════════════════════════════════════════════════════════════════════════
with tab_clean:
    st.markdown('<div class="sec">🧼 Cleaned Dataset Preview</div>', unsafe_allow_html=True)

    if result.cleaned_df.empty:
        st.warning("Cleaned DataFrame is empty.")
    else:
        cdf = result.cleaned_df
        display_cols = [c for c in cdf.columns if c != ORIGINAL_COL and not c.startswith(FEAT_PREFIX)]

        # Column selector
        with st.expander("🎛️ Column Selector", expanded=False):
            sel_cols = st.multiselect(
                "Columns to display",
                options=display_cols,
                default=display_cols[:25],
                key="clean_col_sel",
            )
        visible = sel_cols if sel_cols else display_cols[:25]
        visible = [c for c in visible if c in cdf.columns]

        # Stats bar
        cs1, cs2, cs3, cs4 = st.columns(4)
        cs1.metric("Rows", f"{len(cdf):,}")
        cs2.metric("Columns", f"{len(display_cols):,}")
        cs3.metric("Memory", f"{cdf[display_cols].memory_usage(deep=True).sum() / 1024:.0f} KB")
        cs4.metric("Features", f"{result.n_features}")

        st.dataframe(cdf[visible], use_container_width=True, height=450, hide_index=True)

        # Per-field dtype table
        st.markdown('<div class="sec" style="margin-top:0.75rem;">🗂️ Column Schema</div>',
                    unsafe_allow_html=True)
        schema_df = pd.DataFrame([
            {
                "Column": c,
                "dtype": str(cdf[c].dtype),
                "Non-null": cdf[c].notna().sum(),
                "Null %": round(cdf[c].isna().mean() * 100, 1),
                "Unique": cdf[c].nunique(),
            }
            for c in display_cols
        ])
        st.dataframe(schema_df, use_container_width=True, height=300, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 4 — Features
# ══════════════════════════════════════════════════════════════════════════════
with tab_feat:
    st.markdown('<div class="sec">⚙️ Engineered Features</div>', unsafe_allow_html=True)

    if not result.has_features:
        st.info("No features were engineered. Enable feature extraction options in the sidebar.")
    else:
        fdf = result.features_df
        feat_cols = result.feature_columns

        # Feature list badges
        badges = " ".join(
            f"<span class='badge badge-purple'>{c.replace(FEAT_PREFIX,'')}</span>"
            for c in feat_cols
        )
        st.markdown(badges, unsafe_allow_html=True)
        st.markdown("")

        # Group features by category
        time_feats = [c for c in feat_cols if any(x in c for x in ["hour", "day", "month", "weekend", "business", "night"])]
        ip_feats   = [c for c in feat_cols if "ip" in c]
        freq_feats = [c for c in feat_cols if "freq" in c]

        col_tf, col_ipf = st.columns(2)

        with col_tf:
            if time_feats:
                st.markdown('<div class="sec">🕐 Time Features</div>', unsafe_allow_html=True)
                for fc in time_feats:
                    label = fc.replace(FEAT_PREFIX, "").replace("_", " ").title()
                    if fdf[fc].dtype == bool or set(fdf[fc].dropna().unique()).issubset({True, False}):
                        true_pct = fdf[fc].mean() * 100
                        st.markdown(
                            f"<div style='font-size:0.8rem;color:#8B949E;'>{label}</div>"
                            f"<div style='background:#0D1117;border-radius:4px;height:8px;overflow:hidden;margin-bottom:6px;'>"
                            f"<div style='background:#58A6FF;width:{true_pct:.0f}%;height:100%;'></div></div>"
                            f"<div style='font-size:0.75rem;color:#8B949E;margin-bottom:8px;'>{true_pct:.1f}% True</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        vc = fdf[fc].value_counts().head(10).reset_index()
                        vc.columns = ["val", "cnt"]
                        fig = go.Figure(go.Bar(
                            x=vc["val"].astype(str), y=vc["cnt"],
                            marker_color="#58A6FF",
                            hovertemplate="%{x}: %{y}<extra></extra>",
                        ))
                        fig.update_layout(**_dark_layout(height=160), title=label,
                                          xaxis=dict(title=None), yaxis=dict(title="Count"))
                        st.plotly_chart(fig, use_container_width=True)

        with col_ipf:
            if ip_feats:
                st.markdown('<div class="sec">🌐 IP Features</div>', unsafe_allow_html=True)
                for fc in ip_feats:
                    if fdf[fc].notna().sum() == 0:
                        continue
                    label = fc.replace(FEAT_PREFIX, "").replace("_", " ").title()
                    vc = fdf[fc].value_counts().head(10).reset_index()
                    vc.columns = ["val", "cnt"]
                    fig = go.Figure(go.Bar(
                        x=vc["val"].astype(str), y=vc["cnt"],
                        marker_color="#3FB950",
                        hovertemplate="%{x}: %{y}<extra></extra>",
                    ))
                    fig.update_layout(**_dark_layout(height=160), title=label,
                                      xaxis=dict(title=None), yaxis=dict(title="Count"))
                    st.plotly_chart(fig, use_container_width=True)

        if freq_feats:
            st.markdown('<div class="sec" style="margin-top:0.5rem;">📈 Batch Frequency Features</div>',
                        unsafe_allow_html=True)
            fc_cols = st.columns(min(len(freq_feats), 3))
            for i, fc in enumerate(freq_feats):
                with fc_cols[i % len(fc_cols)]:
                    label = fc.replace(FEAT_PREFIX, "").replace("_batch_freq", "").replace("_", " ").title()
                    desc = fdf[fc].describe()
                    st.metric(f"{label} freq — mean", f"{desc.get('mean', 0):.1f}")
                    st.metric("max", f"{desc.get('max', 0):.0f}")

        # Full feature DataFrame preview
        with st.expander("📋 Full Feature DataFrame Preview"):
            st.dataframe(fdf[feat_cols].head(100), use_container_width=True,
                         height=350, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 5 — Export
# ══════════════════════════════════════════════════════════════════════════════
with tab_export:
    st.markdown('<div class="sec">⬇ Export Cleaned Datasets</div>', unsafe_allow_html=True)
    st.caption(
        "Export only includes the current batch. "
        "For large-scale exports, use the 📥 Log Retrieval page."
    )

    def _to_csv(df: pd.DataFrame) -> bytes:
        # Drop ORIGINAL_COL (contains dicts, not serialisable as CSV)
        cols = [c for c in df.columns if c != ORIGINAL_COL]
        return df[cols].to_csv(index=False).encode("utf-8")

    ex1, ex2, ex3 = st.columns(3)

    with ex1:
        st.markdown("#### 🧼 Cleaned Data")
        st.metric("Rows", f"{len(result.cleaned_df):,}")
        st.metric("Columns", f"{len([c for c in result.cleaned_df.columns if c != ORIGINAL_COL]):,}")
        csv_c = _to_csv(result.cleaned_df)
        st.download_button(
            "⬇ Download cleaned.csv",
            data=csv_c,
            file_name="isro_soc_cleaned.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with ex2:
        st.markdown("#### ⚙️ With Features")
        st.metric("Rows", f"{len(result.features_df):,}")
        st.metric("Feature Columns", f"{result.n_features}")
        csv_f = _to_csv(result.features_df)
        st.download_button(
            "⬇ Download features.csv",
            data=csv_f,
            file_name="isro_soc_features.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with ex3:
        st.markdown("#### 🗃️ Raw (Flattened)")
        st.metric("Rows", f"{len(result.original_df):,}")
        st.metric("Columns", f"{len([c for c in result.original_df.columns if c != ORIGINAL_COL]):,}")
        csv_o = _to_csv(result.original_df)
        st.download_button(
            "⬇ Download raw_flat.csv",
            data=csv_o,
            file_name="isro_soc_raw_flat.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("<hr style='border-color:#30363D;margin:1rem 0;'>", unsafe_allow_html=True)
    st.markdown("#### 📋 Quality Report (JSON)")
    qr_dict = {
        "input_count":           q.input_count,
        "output_count":          q.output_count,
        "duplicates_removed":    q.duplicates_removed,
        "retention_rate_pct":    q.retention_rate,
        "coverage_score_pct":    q.coverage_score,
        "timestamp_normalized":  q.timestamp_normalized,
        "timestamp_errors":      q.timestamp_parse_errors,
        "features_added":        q.features_added,
        "dropped_columns":       q.dropped_columns,
        "elapsed_ms":            q.elapsed_ms,
        "stage_timings_ms":      q.stage_timings,
    }
    st.download_button(
        "⬇ Download quality_report.json",
        data=json.dumps(qr_dict, indent=2).encode("utf-8"),
        file_name="isro_soc_quality_report.json",
        mime="application/json",
        use_container_width=False,
    )
    with st.expander("📋 View Quality Report JSON"):
        st.code(json.dumps(qr_dict, indent=2), language="json")

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<hr style='border-color:#30363D;margin-top:2rem;'>", unsafe_allow_html=True)
st.caption(
    f"Data Pipeline · Batch size: {q.input_count:,} → {q.output_count:,} · "
    f"Features: {result.n_features} · Total: {q.elapsed_ms:.0f} ms"
)
