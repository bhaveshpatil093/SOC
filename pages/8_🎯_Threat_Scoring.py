"""
pages/6_🎯_Threat_Scoring.py

Unified Threat Scoring Dashboard.

Combines Sigma rule severities, ML anomaly scores, and behavioral context
into a normalized threat score. Explains alerts in natural language.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import settings, get_logger
from core import get_es_client
from core.preprocessing import PreprocessingPipeline, PipelineConfig
from core.sigma_engine import SigmaDetectionEngine
from core.threat_scorer import ThreatScoringEngine, ThreatContext
from models import AnomalyDetector, BatchFeatureEngineer
from utils import SigmaUtils

logger = get_logger(__name__)

st.set_page_config(
    page_title=f"{settings.app_title} | Threat Scoring",
    page_icon="🎯",
    layout="wide",
)

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

.sec { font-size:0.78rem; font-weight:600; color:#8B949E; text-transform:uppercase;
       letter-spacing:0.8px; padding-bottom:0.25rem; border-bottom:1px solid #30363D;
       margin-bottom:0.6rem; }

.alert-card {
    background: #0D1117; border: 1px solid #30363D; border-left: 4px solid #8B949E;
    border-radius: 8px; padding: 1rem; margin-bottom: 1rem;
}
.alert-card.critical { border-left-color: #F85149; }
.alert-card.high     { border-left-color: #D29922; }
.alert-card.medium   { border-left-color: #D29922; }
.alert-card.low      { border-left-color: #3FB950; }
.alert-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 0.25rem; }
.alert-score { font-size: 1.25rem; font-weight: 700; }
.alert-reason { font-size: 0.9rem; color: #8B949E; margin-top: 0.5rem; }
</style>
""", unsafe_allow_html=True)


def _dark(**kw) -> dict:
    base = dict(
        paper_bgcolor="#161B22", plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3", family="Inter", size=11),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    base.update(kw)
    return base


st.markdown("## 🎯 Unified Threat Scoring")
st.markdown(
    "<p style='color:#8B949E;margin-top:-0.5rem;'>"
    "Synthesizes Sigma signatures and ML anomaly scores into prioritized, explainable alerts.</p>",
    unsafe_allow_html=True,
)

# ─── Config Sidebar ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Scoring Config")
    ml_threshold = st.slider(
        "ML Anomaly Threshold",
        min_value=0.0, max_value=1.0, value=0.6, step=0.05,
        help="Minimum ML score before it starts contributing heavily to the threat score."
    )
    
    st.markdown("### 🤖 ML Engine")
    algorithm = st.selectbox("Algorithm", ["isolation_forest", "local_outlier_factor"])
    contamination = st.slider("Contamination", 1, 20, 5) / 100.0


# ─── Load Batch ────────────────────────────────────────────────────────────────
lr_pages = st.session_state.get("lr_pages", {})
raw_hits: List[Dict[str, Any]] = []
for page in sorted(lr_pages.values(), key=lambda p: getattr(p, "page_num", 0)):
    raw_hits.extend(page.hits)
    if len(raw_hits) >= 5000:
        raw_hits = raw_hits[:5000]
        break

c1, c2 = st.columns([4, 1])
with c1:
    if raw_hits:
        st.info(f"📦 Batch ready: **{len(raw_hits):,}** logs available for analysis.")
    else:
        st.warning("📥 No batch data found. Please retrieve logs using the Log Retrieval page.")
with c2:
    run_btn = st.button("▶ Run Unified Engine", type="primary", use_container_width=True, disabled=not raw_hits)

if run_btn and raw_hits:
    with st.spinner("1/3 Running Preprocessing & Feature Engineering..."):
        # We MUST preserve 1:1 mapping and _id column
        cfg = PipelineConfig(
            drop_metadata_fields=False,
            dedup_enabled=False,
            keep_original=True
        )
        pp_result = PreprocessingPipeline().run(raw_hits, config=cfg)
        feat_df, feat_cols = BatchFeatureEngineer(min_rows=1).transform(pp_result.cleaned_df)
    
    with st.spinner("2/3 Running ML Anomaly Detection..."):
        detector = AnomalyDetector(algorithm=algorithm, contamination=contamination)
        try:
            detector.fit(feat_df, feature_cols=feat_cols)
            ml_scored_df, _ = detector.score_batch(feat_df, feature_cols=feat_cols)
        except Exception as e:
            st.error(f"ML Scoring failed: {e}")
            st.stop()
            
    with st.spinner("3/3 Running Sigma Detection..."):
        # Load rules from memory or disk
        if "sigma_rules" not in st.session_state:
            st.session_state["sigma_rules"] = SigmaUtils.load_rules_from_dir(settings.project_root / "rules")
            
        rules = [r for r in st.session_state.get("sigma_rules", []) if r.is_convertible]
        if rules:
            sigma_engine = SigmaDetectionEngine(get_es_client())
            sigma_report = sigma_engine.evaluate_batch(raw_hits, rules)
        else:
            sigma_report = None
            
    with st.spinner("Finalizing Threat Scores..."):
        scorer = ThreatScoringEngine(ml_threshold=ml_threshold)
        results = scorer.score_batch(raw_hits, sigma_report, ml_scored_df)
        st.session_state["threat_results"] = results
        
    st.success("✅ Unified Threat Scoring complete.")


results: Optional[List[ThreatContext]] = st.session_state.get("threat_results")
if not results:
    st.stop()


# ─── Dashboard KPIs ───────────────────────────────────────────────────────────
critical = sum(1 for r in results if r.risk_level == "Critical")
high = sum(1 for r in results if r.risk_level == "High")
medium = sum(1 for r in results if r.risk_level == "Medium")
low = sum(1 for r in results if r.risk_level == "Low")

st.markdown("<hr style='border-color:#30363D;margin:0.5rem 0;'>", unsafe_allow_html=True)
st.markdown(
    f"""<div class="kpi-row">
    <div class="kpi-card kpi-blue">
        <div class="kpi-label">Analyzed Logs</div>
        <div class="kpi-value">{len(results):,}</div>
    </div>
    <div class="kpi-card" style="border-top:3px solid #F85149;">
        <div class="kpi-label">Critical Alerts</div>
        <div class="kpi-value">{critical}</div>
    </div>
    <div class="kpi-card" style="border-top:3px solid #D29922;">
        <div class="kpi-label">High Alerts</div>
        <div class="kpi-value">{high}</div>
    </div>
    <div class="kpi-card" style="border-top:3px solid #D29922;">
        <div class="kpi-label">Medium Alerts</div>
        <div class="kpi-value">{medium}</div>
    </div>
    <div class="kpi-card" style="border-top:3px solid #3FB950;">
        <div class="kpi-label">Low Alerts</div>
        <div class="kpi-value">{low}</div>
    </div>
    </div>""",
    unsafe_allow_html=True,
)


# ─── Visuals ──────────────────────────────────────────────────────────────────
col_viz1, col_viz2 = st.columns(2)

with col_viz1:
    st.markdown('<div class="sec">Threat Level Distribution</div>', unsafe_allow_html=True)
    counts = pd.Series([r.risk_level for r in results]).value_counts()
    colors = {"Critical": "#F85149", "High": "#D29922", "Medium": "#D29922", "Low": "#3FB950", "Info": "#8B949E"}
    fig_pie = go.Figure(go.Pie(
        labels=counts.index,
        values=counts.values,
        hole=0.6,
        marker=dict(colors=[colors.get(l, "#8B949E") for l in counts.index])
    ))
    fig_pie.update_layout(**_dark(height=280), margin=dict(t=10, b=10))
    st.plotly_chart(fig_pie, use_container_width=True)
    
with col_viz2:
    st.markdown('<div class="sec">Top Scoring Entities (Source IP)</div>', unsafe_allow_html=True)
    # Extract source IPs
    src_scores = {}
    for r in results:
        src = r.raw_source.get("source", {}).get("ip") or r.raw_source.get("src_ip", "Unknown")
        src_scores[src] = max(src_scores.get(src, 0), r.threat_score)
        
    src_df = pd.DataFrame(list(src_scores.items()), columns=["Source IP", "Max Threat Score"])
    src_df = src_df.sort_values("Max Threat Score", ascending=True).tail(5)
    
    fig_bar = go.Figure(go.Bar(
        x=src_df["Max Threat Score"],
        y=src_df["Source IP"],
        orientation="h",
        marker=dict(color=src_df["Max Threat Score"], colorscale=[[0, "#30363D"], [1, "#F85149"]])
    ))
    fig_bar.update_layout(**_dark(height=280), margin=dict(t=10, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)


# ─── Alert Feed ───────────────────────────────────────────────────────────────
st.markdown('<div class="sec" style="margin-top:1.5rem;">🚨 Priority Alert Feed & Explainability</div>', unsafe_allow_html=True)

display_results = [r for r in results if r.threat_score > 0][:50] # Show top 50

if not display_results:
    st.success("No threats detected.")
else:
    for idx, r in enumerate(display_results):
        color_class = r.risk_level.lower()
        score_color = "#F85149" if r.threat_score >= 80 else "#D29922" if r.threat_score >= 40 else "#3FB950"
        
        st.markdown(f"""
        <div class="alert-card {color_class}">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div class="alert-title">{r.risk_level} Threat Detected</div>
                <div class="alert-score" style="color:{score_color}">{r.threat_score}/100</div>
            </div>
            <div style="font-size:0.85rem; color:#8B949E; margin-bottom:0.5rem;">
                <b>Time:</b> {r.timestamp} &nbsp;|&nbsp; <b>Doc ID:</b> {r.doc_id}
            </div>
            <div class="alert-reason">
                <b>Explanation:</b> {r.explanation}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander(f"View Raw Data ({r.doc_id})"):
            st.json(r.raw_source)
            
    if len(results) > 50:
        st.info(f"Showing top 50 out of {len([r for r in results if r.threat_score > 0])} threats.")
