"""
pages/4_🤖_ML_Anomaly.py

ML Anomaly Detection Dashboard — ISRO SOC Analytics Platform

Batch-scoped unsupervised anomaly detection using Isolation Forest / LOF.
Works exclusively on the currently retrieved log batch — never loads the
full 2.77B-log dataset into memory.

Tabs
----
  🚀 Train & Score   — Configure, train, and score the current batch
  📊 Score Analysis  — Anomaly score distribution, threshold analysis
  🚨 Suspicious Logs — Ranked table of flagged events with feature breakdown
  ⚙️ Feature Explorer — Inspect engineered feature distributions
  💾 Model Manager   — Save / load / inspect persisted models
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import settings, get_logger
from core.preprocessing import PreprocessingPipeline, PipelineConfig, ORIGINAL_COL
from models import AnomalyDetector, BatchFeatureEngineer, ML_FEAT_PREFIX
from utils.data_utils import DataUtils

logger = get_logger(__name__)

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{settings.app_title} | ML Anomaly",
    page_icon="🤖",
    layout="wide",
)

# ─── Global Styles ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.block-container { padding-top: 1.25rem !important; }

.kpi-row { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.kpi-card {
    background: #161B22; border: 1px solid #30363D; border-radius: 12px;
    padding: 1rem 1.25rem; min-width: 150px; flex: 1;
}
.kpi-label { font-size: 0.7rem; color: #8B949E; text-transform: uppercase; letter-spacing: 0.6px; }
.kpi-value { font-size: 1.75rem; font-weight: 700; color: #E6EDF3; margin-top: 0.1rem; }
.kpi-sub   { font-size: 0.75rem; color: #8B949E; margin-top: 0.1rem; }
.kpi-red    { border-top: 3px solid #F85149; }
.kpi-yellow { border-top: 3px solid #D29922; }
.kpi-green  { border-top: 3px solid #3FB950; }
.kpi-blue   { border-top: 3px solid #58A6FF; }
.kpi-purple { border-top: 3px solid #BC8CFF; }

.sec { font-size:0.78rem; font-weight:600; color:#8B949E; text-transform:uppercase;
       letter-spacing:0.8px; padding-bottom:0.25rem; border-bottom:1px solid #30363D;
       margin-bottom:0.6rem; }

.badge {
    display:inline-block; border-radius:8px; padding:1px 8px;
    font-size:0.72rem; font-weight:600; margin:1px;
}
.badge-red    { background:rgba(248,81,73,.15);  color:#F85149; }
.badge-yellow { background:rgba(210,153,34,.15); color:#D29922; }
.badge-green  { background:rgba(63,185,80,.15);  color:#3FB950; }
.badge-purple { background:rgba(188,140,255,.15);color:#BC8CFF; }
.badge-grey   { background:rgba(139,148,158,.1); color:#8B949E; }
</style>
""", unsafe_allow_html=True)


# ─── Dark Plotly layout ───────────────────────────────────────────────────────
def _dark(**kw) -> dict:
    base = dict(
        paper_bgcolor="#161B22", plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3", family="Inter", size=11),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    base.update(kw)
    return base


# ─── Session state keys ───────────────────────────────────────────────────────
_SK_SCORED_DF  = "ml_scored_df"
_SK_FEAT_COLS  = "ml_feat_cols"
_SK_DETECTOR   = "ml_detector"
_SK_SUMMARY    = "ml_summary"
_SK_FEAT_DF    = "ml_feat_df"   # feature_df before scoring (has _ml_* cols)


# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 🤖 ML Anomaly Detection")
st.markdown(
    "<p style='color:#8B949E;margin-top:-0.5rem;'>"
    "Batch-scoped unsupervised anomaly detection using Isolation Forest / LOF. "
    "Operates on retrieved log batches — never loads the full dataset.</p>",
    unsafe_allow_html=True,
)

# ─── Sidebar: Model Configuration ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🤖 Model Configuration")

    algorithm = st.selectbox(
        "Algorithm",
        ["isolation_forest", "local_outlier_factor"],
        index=0,
        help="Isolation Forest is faster and works better with high-dimensional data. "
             "LOF is more sensitive to local density changes.",
    )
    contamination = st.slider(
        "Contamination (expected anomaly %)",
        min_value=1, max_value=30, value=5, step=1,
        help="Approximate percentage of anomalous events expected in the batch.",
    ) / 100.0

    n_estimators = st.slider(
        "N Estimators (IF only)",
        min_value=50, max_value=500, value=100, step=50,
        help="Number of trees in the Isolation Forest.",
    )
    n_neighbors = st.slider(
        "N Neighbors (LOF only)",
        min_value=5, max_value=50, value=20, step=5,
        help="Number of neighbors for Local Outlier Factor.",
    )

    st.markdown("<hr style='border-color:#30363D;margin:0.5rem 0;'>", unsafe_allow_html=True)
    st.markdown("### ⚙️ Preprocessing")

    run_preprocessing = st.checkbox(
        "Auto-preprocess batch before training",
        value=True,
        help="Run the cleaning pipeline on the retrieved batch before feature engineering.",
    )
    missing_strategy = st.selectbox(
        "Missing value strategy",
        ["flag (keep NaN)", "fill_default"],
        index=0,
    )
    strategy_map = {"flag (keep NaN)": "flag", "fill_default": "fill_default"}

    st.markdown("<hr style='border-color:#30363D;margin:0.5rem 0;'>", unsafe_allow_html=True)
    st.markdown("### 🎛️ Score Threshold")
    custom_threshold = st.slider(
        "Anomaly score threshold (0–1)",
        min_value=0.0, max_value=1.0, value=0.7, step=0.05,
        help="Events with anomaly_score ≥ this threshold are highlighted as suspicious.",
    )


# ─── Resolve batch data ────────────────────────────────────────────────────────
lr_pages = st.session_state.get("lr_pages", {})
raw_hits: List[Dict[str, Any]] = []
for page in sorted(lr_pages.values(), key=lambda p: getattr(p, "page_num", 0)):
    raw_hits.extend(page.hits)
    if len(raw_hits) >= 5000:
        raw_hits = raw_hits[:5000]
        break

# Status banner
c_status, c_run = st.columns([4, 1])
with c_status:
    if raw_hits:
        st.info(
            f"📦 Batch ready: **{len(raw_hits):,}** logs cached from Log Retrieval page. "
            f"Ready to train."
        )
    else:
        st.warning(
            "📥 No batch data found. Navigate to **📥 Log Retrieval** and fetch logs first, "
            "or use the 🕑 aggregation-based model below."
        )
with c_run:
    train_btn = st.button(
        "🚀 Train & Score",
        type="primary",
        use_container_width=True,
        disabled=not raw_hits,
        help="Run feature engineering → train model → score every log in the batch.",
    )

# ─── Training execution ────────────────────────────────────────────────────────
if train_btn and raw_hits:
    # Step 1: Preprocessing
    with st.spinner("⚙️ Preprocessing batch..."):
        if run_preprocessing:
            cfg = PipelineConfig(
                missing_strategy=strategy_map.get(missing_strategy, "flag"),
                keep_original=False,
            )
            pipeline = PreprocessingPipeline()
            pp_result = pipeline.run(raw_hits, config=cfg)
            working_df = pp_result.cleaned_df
        else:
            # Minimal flatten only
            from utils.data_utils import DataUtils
            rows = [DataUtils.flatten_dict(h.get("_source", {})) for h in raw_hits]
            working_df = pd.DataFrame(rows)

    # Step 2: Feature Engineering
    with st.spinner("⚙️ Engineering security features..."):
        engineer = BatchFeatureEngineer(min_rows=10)
        try:
            feat_df, feat_cols = engineer.transform(working_df)
        except ValueError as exc:
            st.error(f"Feature engineering failed: {exc}")
            st.stop()

    st.session_state[_SK_FEAT_DF]   = feat_df
    st.session_state[_SK_FEAT_COLS] = feat_cols

    # Step 3: Train + Score
    if not feat_cols:
        st.error("No numeric features could be derived from the batch. "
                 "Ensure the logs contain standard ECS fields.")
        st.stop()

    with st.spinner(f"🤖 Training {algorithm} on {len(feat_df):,} samples × {len(feat_cols)} features..."):
        detector = AnomalyDetector(
            algorithm=algorithm,
            contamination=contamination,
            n_estimators=n_estimators,
            n_neighbors=n_neighbors,
        )
        try:
            detector.fit(feat_df, feature_cols=feat_cols)
            scored_df, summary = detector.score_batch(feat_df, feature_cols=feat_cols)
        except Exception as exc:
            st.error(f"Training/scoring failed: {exc}")
            logger.error("ML pipeline error: %s", exc, exc_info=True)
            st.stop()

    st.session_state[_SK_SCORED_DF] = scored_df
    st.session_state[_SK_DETECTOR]  = detector
    st.session_state[_SK_SUMMARY]   = summary
    st.success(
        f"✅ Done — {summary['n_anomalies']:,} anomalies flagged in {summary['n_total']:,} logs "
        f"({summary['anomaly_rate_pct']:.1f}%) | Features: {len(feat_cols)}"
    )

# ─── Retrieve state ────────────────────────────────────────────────────────────
scored_df: Optional[pd.DataFrame]  = st.session_state.get(_SK_SCORED_DF)
feat_cols: Optional[List[str]]     = st.session_state.get(_SK_FEAT_COLS)
detector: Optional[AnomalyDetector] = st.session_state.get(_SK_DETECTOR)
summary: Optional[Dict[str, Any]]  = st.session_state.get(_SK_SUMMARY)
feat_df: Optional[pd.DataFrame]    = st.session_state.get(_SK_FEAT_DF)

if scored_df is None:
    st.markdown(
        """<div style="background:#161B22;border:1px dashed #30363D;border-radius:12px;
        padding:2.5rem;text-align:center;margin-top:1.5rem;">
        <div style="font-size:2.5rem;margin-bottom:0.5rem;">🤖</div>
        <div style="font-weight:600;color:#E6EDF3;margin-bottom:0.4rem;">
            Configure the model and click 🚀 Train &amp; Score</div>
        <div style="color:#8B949E;font-size:0.85rem;">
            First retrieve logs on the 📥 Log Retrieval page,<br>
            then return here to train and score the batch.</div>
        </div>""",
        unsafe_allow_html=True,
    )
    st.stop()

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_score, tab_dist, tab_suspicious, tab_features, tab_model = st.tabs([
    "📊 Score Analysis",
    "📈 Distribution",
    "🚨 Suspicious Logs",
    "⚙️ Feature Explorer",
    "💾 Model Manager",
])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Score Analysis
# ══════════════════════════════════════════════════════════════════════════════
with tab_score:
    n_total    = summary["n_total"]
    n_anom     = summary["n_anomalies"]
    n_thresh   = int((scored_df["anomaly_score"] >= custom_threshold).sum())

    rate_colour = "kpi-red" if summary["anomaly_rate_pct"] > 10 else "kpi-yellow"

    st.markdown(
        f"""<div class="kpi-row">
        <div class="kpi-card kpi-blue">
            <div class="kpi-label">Batch Size</div>
            <div class="kpi-value">{n_total:,}</div>
            <div class="kpi-sub">Log events scored</div>
        </div>
        <div class="kpi-card {rate_colour}">
            <div class="kpi-label">Model Anomalies</div>
            <div class="kpi-value">{n_anom:,}</div>
            <div class="kpi-sub">Rate: {summary['anomaly_rate_pct']:.1f}%</div>
        </div>
        <div class="kpi-card kpi-red">
            <div class="kpi-label">Above Threshold</div>
            <div class="kpi-value">{n_thresh:,}</div>
            <div class="kpi-sub">Score ≥ {custom_threshold:.2f}</div>
        </div>
        <div class="kpi-card kpi-purple">
            <div class="kpi-label">Features Used</div>
            <div class="kpi-value">{len(feat_cols)}</div>
            <div class="kpi-sub">_ml_* columns</div>
        </div>
        <div class="kpi-card kpi-blue">
            <div class="kpi-label">Mean Score</div>
            <div class="kpi-value">{summary['mean_score']:.3f}</div>
            <div class="kpi-sub">Max: {summary['max_score']:.3f}</div>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("<hr style='border-color:#30363D;'>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)

    # Anomaly score histogram
    with col_a:
        st.markdown('<div class="sec">Anomaly Score Distribution</div>', unsafe_allow_html=True)
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Histogram(
            x=scored_df[scored_df["is_anomaly"] == False]["anomaly_score"],
            name="Normal",
            marker_color="#58A6FF",
            opacity=0.75,
            nbinsx=50,
        ))
        fig_hist.add_trace(go.Histogram(
            x=scored_df[scored_df["is_anomaly"] == True]["anomaly_score"],
            name="Anomaly",
            marker_color="#F85149",
            opacity=0.85,
            nbinsx=50,
        ))
        fig_hist.add_vline(
            x=custom_threshold,
            line_dash="dash",
            line_color="#D29922",
            annotation_text=f"Threshold {custom_threshold:.2f}",
            annotation_font_color="#D29922",
        )
        fig_hist.update_layout(
            barmode="overlay",
            **_dark(height=300),
            xaxis=dict(title="Anomaly Score (0=normal, 1=anomalous)", showgrid=True, gridcolor="#30363D"),
            yaxis=dict(title="Count", showgrid=True, gridcolor="#30363D"),
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    # Score over time (if timestamp available)
    with col_b:
        st.markdown('<div class="sec">Score Over Time</div>', unsafe_allow_html=True)
        ts_col_candidates = [settings.es_time_field, "@timestamp", f"{settings.es_time_field}_dt"]
        ts_col = next((c for c in ts_col_candidates if c in scored_df.columns), None)

        if ts_col:
            tmp = scored_df[[ts_col, "anomaly_score", "is_anomaly"]].copy()
            tmp["_ts"] = pd.to_datetime(tmp[ts_col], errors="coerce", utc=True)
            tmp = tmp.dropna(subset=["_ts"]).sort_values("_ts")

            fig_ts = go.Figure()
            fig_ts.add_trace(go.Scatter(
                x=tmp[~tmp["is_anomaly"]]["_ts"],
                y=tmp[~tmp["is_anomaly"]]["anomaly_score"],
                mode="markers",
                name="Normal",
                marker=dict(color="#58A6FF", size=4, opacity=0.6),
            ))
            fig_ts.add_trace(go.Scatter(
                x=tmp[tmp["is_anomaly"]]["_ts"],
                y=tmp[tmp["is_anomaly"]]["anomaly_score"],
                mode="markers",
                name="Anomaly",
                marker=dict(color="#F85149", size=7, symbol="diamond"),
            ))
            fig_ts.add_hline(
                y=custom_threshold,
                line_dash="dash",
                line_color="#D29922",
            )
            fig_ts.update_layout(
                **_dark(height=300),
                xaxis=dict(title=None, showgrid=False),
                yaxis=dict(title="Anomaly Score", range=[0, 1.05], gridcolor="#30363D"),
                legend=dict(orientation="h", y=1.05),
            )
            st.plotly_chart(fig_ts, use_container_width=True)
        else:
            st.info("No timestamp field found in the batch for timeline visualisation.")

    # Threshold sensitivity table
    st.markdown('<div class="sec" style="margin-top:0.75rem;">🎚 Threshold Sensitivity</div>',
                unsafe_allow_html=True)
    thresholds = [0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
    sensitivity_rows = []
    for t in thresholds:
        n = int((scored_df["anomaly_score"] >= t).sum())
        sensitivity_rows.append({
            "Threshold": t,
            "Flagged Events": n,
            "Flagged %": round(n / max(len(scored_df), 1) * 100, 2),
        })
    sens_df = pd.DataFrame(sensitivity_rows)
    st.dataframe(sens_df, hide_index=True, use_container_width=True, height=200)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Score Distribution
# ══════════════════════════════════════════════════════════════════════════════
with tab_dist:
    st.markdown('<div class="sec">Anomaly Score Box Plot per Entity</div>', unsafe_allow_html=True)

    # Find grouping column
    host_candidates = [settings.es_hostname_field, "host.name", "host_name", "hostname"]
    grp_col = next((c for c in host_candidates if c in scored_df.columns), None)

    if grp_col:
        top_hosts = scored_df[grp_col].value_counts().head(15).index.tolist()
        subset = scored_df[scored_df[grp_col].isin(top_hosts)].copy()
        fig_box = go.Figure()
        for host in top_hosts:
            s = subset[subset[grp_col] == host]["anomaly_score"]
            has_anom = subset[subset[grp_col] == host]["is_anomaly"].any()
            fig_box.add_trace(go.Box(
                y=s,
                name=str(host),
                marker_color="#F85149" if has_anom else "#58A6FF",
                boxpoints="outliers",
            ))
        fig_box.update_layout(
            **_dark(height=370),
            xaxis=dict(title="Host", tickangle=-30),
            yaxis=dict(title="Anomaly Score", range=[0, 1.1], gridcolor="#30363D"),
            showlegend=False,
        )
        st.plotly_chart(fig_box, use_container_width=True)
    else:
        st.info("No hostname field found for entity grouping.")

    # Scatter: top 2 features coloured by anomaly
    st.markdown('<div class="sec" style="margin-top:0.75rem;">🔵 Feature Scatter (Top 2 Features)</div>',
                unsafe_allow_html=True)
    if feat_cols and len(feat_cols) >= 2:
        f1, f2 = feat_cols[0], feat_cols[1]
        fig_sc = go.Figure()
        for label, colour, marker in [
            (False, "#58A6FF", "circle"),
            (True,  "#F85149", "diamond"),
        ]:
            mask = scored_df["is_anomaly"] == label
            fig_sc.add_trace(go.Scatter(
                x=scored_df[mask][f1] if f1 in scored_df.columns else [],
                y=scored_df[mask][f2] if f2 in scored_df.columns else [],
                mode="markers",
                name="Anomaly" if label else "Normal",
                marker=dict(color=colour, size=5 if not label else 9, symbol=marker, opacity=0.7),
            ))
        fig_sc.update_layout(
            **_dark(height=340),
            xaxis=dict(title=f1.replace(ML_FEAT_PREFIX, ""), showgrid=True, gridcolor="#30363D"),
            yaxis=dict(title=f2.replace(ML_FEAT_PREFIX, ""), showgrid=True, gridcolor="#30363D"),
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig_sc, use_container_width=True)

    # Top-N feature correlation with anomaly label
    st.markdown('<div class="sec" style="margin-top:0.75rem;">📊 Feature Anomaly Correlation</div>',
                unsafe_allow_html=True)
    if feat_cols:
        corr_rows = []
        for fc in feat_cols:
            if fc in scored_df.columns:
                try:
                    corr = float(scored_df[fc].corr(scored_df["anomaly_score"].astype(float)))
                    corr_rows.append({"Feature": fc.replace(ML_FEAT_PREFIX, ""),
                                      "Correlation with Anomaly Score": round(corr, 4)})
                except Exception:
                    pass
        if corr_rows:
            corr_df = pd.DataFrame(corr_rows).sort_values(
                "Correlation with Anomaly Score", key=abs, ascending=False
            )
            fig_corr = go.Figure(go.Bar(
                x=corr_df["Correlation with Anomaly Score"],
                y=corr_df["Feature"],
                orientation="h",
                marker=dict(
                    color=corr_df["Correlation with Anomaly Score"],
                    colorscale=[[0, "#1F3B5E"], [0.5, "#30363D"], [1, "#F85149"]],
                    cmid=0,
                ),
            ))
            fig_corr.update_layout(
                **_dark(height=max(250, len(corr_df) * 22)),
                xaxis=dict(title="Pearson r", showgrid=True, gridcolor="#30363D"),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_corr, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Suspicious Logs
# ══════════════════════════════════════════════════════════════════════════════
with tab_suspicious:
    # Apply threshold
    suspicious = scored_df[scored_df["anomaly_score"] >= custom_threshold].copy()
    suspicious = suspicious.sort_values("anomaly_score", ascending=False).reset_index(drop=True)

    st.markdown(
        f'<div class="sec">🚨 Suspicious Events (score ≥ {custom_threshold:.2f}) — '
        f'{len(suspicious):,} events</div>',
        unsafe_allow_html=True,
    )

    if suspicious.empty:
        st.success(f"No events exceed threshold {custom_threshold:.2f}. Try lowering the threshold.")
    else:
        # Build display columns (non-feature original fields + score)
        disp_candidates = [
            settings.es_time_field,
            f"{settings.es_time_field}_dt",
            settings.es_hostname_field, "host.name",
            settings.es_username_field, "user.name",
            settings.es_src_ip_field, "source.ip",
            settings.es_event_id_field, "event.id",
            settings.es_severity_field, "event.severity",
            settings.es_category_field, "event.category",
            "anomaly_score",
            "is_anomaly",
        ]
        disp_cols = [c for c in disp_candidates if c in suspicious.columns]
        if not disp_cols:
            disp_cols = [c for c in suspicious.columns
                         if not c.startswith(ML_FEAT_PREFIX) and c != ORIGINAL_COL][:12]
            disp_cols = disp_cols + ["anomaly_score", "is_anomaly"]

        disp_cols = list(dict.fromkeys([c for c in disp_cols if c in suspicious.columns]))

        def _score_colour(val):
            if isinstance(val, float):
                if val >= 0.9: return "color:#F85149;font-weight:bold"
                if val >= 0.7: return "color:#D29922;font-weight:bold"
                return "color:#3FB950"
            return ""

        styled = suspicious[disp_cols].style.applymap(_score_colour, subset=["anomaly_score"])
        st.dataframe(styled, use_container_width=True, hide_index=True, height=420)

        # Feature breakdown for top anomaly
        st.markdown('<div class="sec" style="margin-top:0.75rem;">🔬 Top Anomaly Feature Breakdown</div>',
                    unsafe_allow_html=True)
        top_row = suspicious.iloc[0]
        if feat_cols:
            feat_vals = {
                fc.replace(ML_FEAT_PREFIX, ""): round(float(top_row[fc]), 4)
                for fc in feat_cols if fc in top_row.index
            }
            feat_vals_df = pd.DataFrame(
                list(feat_vals.items()), columns=["Feature", "Value"]
            ).sort_values("Value", ascending=False)

            fig_feat = go.Figure(go.Bar(
                x=feat_vals_df["Value"],
                y=feat_vals_df["Feature"],
                orientation="h",
                marker=dict(
                    color=feat_vals_df["Value"],
                    colorscale=[[0, "#1F3B5E"], [1, "#F85149"]],
                ),
            ))
            fig_feat.update_layout(
                title=f"Feature values for top anomaly (score={top_row['anomaly_score']:.3f})",
                **_dark(height=max(250, len(feat_vals_df) * 22)),
                xaxis=dict(title="Value", showgrid=True, gridcolor="#30363D"),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_feat, use_container_width=True)

        # CSV export
        export_cols = [c for c in disp_cols + (feat_cols or []) if c in suspicious.columns]
        csv_bytes = suspicious[export_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇ Download suspicious events CSV",
            data=csv_bytes,
            file_name="isro_soc_suspicious_events.csv",
            mime="text/csv",
        )


# ══════════════════════════════════════════════════════════════════════════════
# Tab 4 — Feature Explorer
# ══════════════════════════════════════════════════════════════════════════════
with tab_features:
    st.markdown('<div class="sec">⚙️ Engineered Feature Statistics</div>', unsafe_allow_html=True)

    if feat_cols and feat_df is not None:
        desc = BatchFeatureEngineer.describe_features(feat_df, feat_cols)
        st.dataframe(desc, hide_index=True, use_container_width=True, height=320)

        st.markdown('<div class="sec" style="margin-top:0.75rem;">📊 Feature Distribution</div>',
                    unsafe_allow_html=True)

        chosen_feat = st.selectbox(
            "Select feature",
            options=[fc.replace(ML_FEAT_PREFIX, "") for fc in feat_cols],
            key="feat_explorer_select",
        )
        full_feat_name = ML_FEAT_PREFIX + chosen_feat

        if full_feat_name in scored_df.columns:
            fig_fdist = go.Figure()
            for label, colour, name in [
                (False, "#58A6FF", "Normal"),
                (True,  "#F85149", "Anomaly"),
            ]:
                vals = scored_df[scored_df["is_anomaly"] == label][full_feat_name].dropna()
                fig_fdist.add_trace(go.Violin(
                    y=vals, name=name,
                    line_color=colour, fillcolor=colour,
                    opacity=0.6, box_visible=True, meanline_visible=True,
                ))
            fig_fdist.update_layout(
                **_dark(height=320),
                violinmode="overlay",
                yaxis=dict(title=chosen_feat, gridcolor="#30363D"),
            )
            st.plotly_chart(fig_fdist, use_container_width=True)

        # Feature name legend
        st.markdown('<div class="sec" style="margin-top:0.75rem;">📖 Feature Legend</div>',
                    unsafe_allow_html=True)
        legend = {
            "hour":                  "Hour of day (0–23)",
            "day_of_week":           "Day of week (0=Mon, 6=Sun)",
            "is_night":              "Event occurred 22:00–05:59 UTC (1=yes)",
            "is_weekend":            "Event occurred Sat/Sun (1=yes)",
            "is_business_hours":     "Event occurred 09:00–17:00 UTC (1=yes)",
            "host_event_count":      "How many times this host appears in the batch",
            "user_event_count":      "How many times this user appears in the batch",
            "src_ip_event_count":    "How many times this source IP appears in the batch",
            "src_unique_dst_ips":    "Unique destination IPs per source IP (high = scan indicator)",
            "host_unique_users":     "Unique users per host (high = potential lateral movement)",
            "src_ip_rarity":         "Normalised rarity score (1 = most rare source IP in batch)",
            "is_failure":            "Event outcome is a failure (1=yes)",
            "src_failure_ratio":     "Failure rate for this source IP within the batch",
            "severity_score":        "Encoded severity (critical=4, high=3, medium=2, low=1)",
            "src_is_private":        "Source IP is RFC-1918 private (1=yes)",
            "src_first_octet":       "First octet of source IP",
            "dst_privileged_port":   "Destination port < 1024 (privileged)",
            "bytes_log":             "Log₁ of bytes transferred",
            "src_total_bytes_log":   "Log₁ of total bytes sent by this source IP in the batch",
        }
        leg_df = pd.DataFrame(
            [(k, v) for k, v in legend.items() if ML_FEAT_PREFIX + k in feat_cols],
            columns=["Feature", "Description"],
        )
        st.dataframe(leg_df, hide_index=True, use_container_width=True)

    else:
        st.info("Train the model first to see feature explorer.")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 5 — Model Manager
# ══════════════════════════════════════════════════════════════════════════════
with tab_model:
    st.markdown('<div class="sec">💾 Model Persistence</div>', unsafe_allow_html=True)

    save_name = st.text_input(
        "Model name (filename stem)",
        value="anomaly_detector",
        placeholder="anomaly_detector",
    )

    col_save, col_load, col_pfit = st.columns(3)
    with col_save:
        if st.button("💾 Save Model", use_container_width=True):
            if detector and detector.is_fitted:
                try:
                    path = detector.save(save_name)
                    st.success(f"Saved → `{path}`")
                except Exception as exc:
                    st.error(f"Save failed: {exc}")
            else:
                st.warning("Train a model first.")

    with col_load:
        if st.button("📂 Load Model", use_container_width=True):
            try:
                loaded = AnomalyDetector.load(save_name)
                st.session_state[_SK_DETECTOR] = loaded
                st.success(f"Loaded `{save_name}` — {loaded.algorithm}, "
                           f"{loaded._total_samples_seen:,} samples seen")
            except FileNotFoundError:
                st.error(f"No saved model named `{save_name}` found.")
            except Exception as exc:
                st.error(f"Load failed: {exc}")

    with col_pfit:
        if st.button("♻️ Partial Fit (new batch)", use_container_width=True,
                     help="Update the model with the current batch WITHOUT resetting weights."):
            if detector and detector.is_fitted and feat_df is not None and feat_cols:
                with st.spinner("Running partial_fit..."):
                    try:
                        detector.partial_fit(feat_df, feat_cols)
                        st.session_state[_SK_DETECTOR] = detector
                        st.success(
                            f"partial_fit complete — {detector._total_samples_seen:,} total samples seen "
                            f"across {len(detector._train_history)} batches"
                        )
                    except Exception as exc:
                        st.error(f"partial_fit failed: {exc}")
            else:
                st.warning("Train a model first and ensure a feature batch is available.")

    # Model info panel
    if detector:
        info = detector.model_info
        st.markdown('<div class="sec" style="margin-top:1rem;">ℹ️ Active Model Info</div>',
                    unsafe_allow_html=True)
        info_df = pd.DataFrame(list(info.items()), columns=["Property", "Value"])
        st.dataframe(info_df, hide_index=True, use_container_width=True, height=250)

        # Training history
        if detector._train_history:
            st.markdown('<div class="sec" style="margin-top:0.75rem;">📋 Training History</div>',
                        unsafe_allow_html=True)
            hist_df = pd.DataFrame(detector._train_history)
            st.dataframe(hist_df, hide_index=True, use_container_width=True, height=180)

    # Saved models on disk
    st.markdown('<div class="sec" style="margin-top:0.75rem;">🗂️ Saved Models on Disk</div>',
                unsafe_allow_html=True)
    model_dir = settings.model_save_dir
    if model_dir.exists():
        model_files = list(model_dir.glob("*.joblib"))
        if model_files:
            saved_rows = []
            for mf in model_files:
                stat = mf.stat()
                saved_rows.append({
                    "Name": mf.stem,
                    "File": mf.name,
                    "Size (KB)": round(stat.st_size / 1024, 1),
                })
            st.dataframe(
                pd.DataFrame(saved_rows), hide_index=True, use_container_width=True, height=180
            )
        else:
            st.info("No saved models found. Save a trained model above.")
    else:
        st.info(f"Model save directory not found: `{model_dir}`")


# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<hr style='border-color:#30363D;margin-top:2rem;'>", unsafe_allow_html=True)
if summary:
    st.caption(
        f"ML Anomaly · {summary['n_total']:,} logs · {summary['n_anomalies']} anomalies "
        f"({summary['anomaly_rate_pct']:.1f}%) · {len(feat_cols or [])} features · "
        f"{detector.algorithm if detector else 'N/A'}"
    )
