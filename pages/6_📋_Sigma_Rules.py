"""
pages/5_📋_Sigma_Rules.py

Sigma Detection Engine Dashboard.

Uploads and manages Sigma rules, evaluates them against the currently
retrieved batch of logs using the core.sigma_engine, and displays
detailed threat hunting metrics including MITRE ATT&CK mappings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import settings, get_logger
from core import get_es_client
from core.sigma_engine import SigmaDetectionEngine, DetectionReport
from utils import SigmaUtils

logger = get_logger(__name__)

st.set_page_config(
    page_title=f"{settings.app_title} | Sigma Engine",
    page_icon="📋",
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
    padding: 1rem 1.25rem; min-width: 160px; flex: 1;
}
.kpi-label { font-size: 0.7rem; color: #8B949E; text-transform: uppercase; letter-spacing: 0.6px; }
.kpi-value { font-size: 1.75rem; font-weight: 700; color: #E6EDF3; margin-top: 0.1rem; }
.kpi-sub   { font-size: 0.75rem; color: #8B949E; margin-top: 0.1rem; }

.kpi-red    { border-top: 3px solid #F85149; }
.kpi-yellow { border-top: 3px solid #D29922; }
.kpi-purple { border-top: 3px solid #BC8CFF; }
.kpi-blue   { border-top: 3px solid #58A6FF; }

.sec { font-size:0.78rem; font-weight:600; color:#8B949E; text-transform:uppercase;
       letter-spacing:0.8px; padding-bottom:0.25rem; border-bottom:1px solid #30363D;
       margin-bottom:0.6rem; }
</style>
""", unsafe_allow_html=True)

def _dark_layout(**kwargs) -> dict:
    base = dict(
        paper_bgcolor="#161B22", plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3", family="Inter", size=11),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    base.update(kwargs)
    return base

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 📋 Sigma Detection Engine")
st.markdown(
    "<p style='color:#8B949E;margin-top:-0.5rem;'>"
    "Batch-scoped Sigma rule execution. Maps retrieved logs against threat signatures and MITRE ATT&CK tactics.</p>",
    unsafe_allow_html=True,
)

# ─── pySigma Check ────────────────────────────────────────────────────────────
if not SigmaUtils.is_sigma_available():
    st.error("⚠️ **pySigma** is not installed. Sigma detection features are disabled.")
    st.stop()

# ─── Sidebar: Rule Management ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Rule Management")
    
    # Auto-load bundled rules if not present
    if "sigma_rules" not in st.session_state:
        rules_dir = settings.project_root / "rules"
        bundled = SigmaUtils.load_rules_from_dir(rules_dir)
        st.session_state["sigma_rules"] = bundled

    uploaded_files = st.file_uploader(
        "Upload custom Sigma YAML",
        type=["yml", "yaml"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        new_rules = []
        for f in uploaded_files:
            content = f.read().decode("utf-8")
            # Some uploaded files might have multiple documents (YAML streams)
            # PySigma handles this internally, but our load_rule_from_yaml handles one for now.
            # Real implementation could split by '---'
            for doc in content.split("---"):
                doc = doc.strip()
                if doc:
                    rule = SigmaUtils.load_rule_from_yaml(doc, source_path=Path(f.name))
                    new_rules.append(rule)
                    
        existing_ids = {r.rule_id for r in st.session_state["sigma_rules"] if r.rule_id}
        added = [r for r in new_rules if r.rule_id not in existing_ids]
        st.session_state["sigma_rules"].extend(added)
        st.success(f"Added {len(added)} new rule(s).")
        
    all_rules = st.session_state.get("sigma_rules", [])
    convertible = [r for r in all_rules if r.is_convertible]
    
    st.markdown(f"**Loaded Rules:** {len(all_rules)}")
    st.markdown(f"**Active (ES ready):** <span style='color:#3FB950'>{len(convertible)}</span>", unsafe_allow_html=True)
    
    with st.expander("View loaded rules"):
        if convertible:
            df = SigmaUtils.rules_to_dataframe(convertible)
            st.dataframe(df[["title", "severity"]], hide_index=True)

# ─── Data Source & Execution ──────────────────────────────────────────────────
lr_pages = st.session_state.get("lr_pages", {})
batch_hits = []
for page in sorted(lr_pages.values(), key=lambda p: getattr(p, 'page_num', 0)):
    batch_hits.extend(page.hits)
    if len(batch_hits) >= 5000:  # Hard safety cap
        batch_hits = batch_hits[:5000]
        break

col_a, col_b = st.columns([3, 1])
with col_a:
    if not batch_hits:
        st.warning("📥 No batch data found. Please retrieve logs using the Log Retrieval page first.")
    else:
        st.info(f"📦 Batch ready: **{len(batch_hits):,}** logs available for detection engine.")

with col_b:
    run_btn = st.button("▶ Run Detection Engine", type="primary", use_container_width=True, disabled=not batch_hits)

if run_btn and batch_hits:
    if not convertible:
        st.error("No active Sigma rules to evaluate.")
    else:
        with st.spinner("Evaluating Sigma rules against batch..."):
            engine = SigmaDetectionEngine(get_es_client())
            report = engine.evaluate_batch(batch_hits, convertible)
            st.session_state["sigma_report"] = report

report: DetectionReport = st.session_state.get("sigma_report")

if not report:
    st.stop()

# ─── Dashboard KPIs ───────────────────────────────────────────────────────────
st.markdown("<hr style='border-color:#30363D;margin:0.5rem 0;'>", unsafe_allow_html=True)

kpi_match = "kpi-red" if report.matched_hits > 0 else "kpi-blue"
st.markdown(
    f"""<div class="kpi-row">
    <div class="kpi-card kpi-blue">
        <div class="kpi-label">Input Batch</div>
        <div class="kpi-value">{report.input_hits:,}</div>
        <div class="kpi-sub">Logs evaluated</div>
    </div>
    <div class="kpi-card {kpi_match}">
        <div class="kpi-label">Matched Logs</div>
        <div class="kpi-value">{report.matched_hits:,}</div>
        <div class="kpi-sub">Flagged by signatures</div>
    </div>
    <div class="kpi-card kpi-yellow">
        <div class="kpi-label">Rule Triggers</div>
        <div class="kpi-value">{report.total_rule_triggers:,}</div>
        <div class="kpi-sub">Total alerts generated</div>
    </div>
    <div class="kpi-card kpi-purple">
        <div class="kpi-label">MITRE Tactics</div>
        <div class="kpi-value">{len(report.mitre_tactics)}</div>
        <div class="kpi-sub">Unique tactics mapped</div>
    </div>
    <div class="kpi-card kpi-blue">
        <div class="kpi-label">Evaluation Time</div>
        <div class="kpi-value">{report.elapsed_ms:.1f}</div>
        <div class="kpi-sub">milliseconds</div>
    </div>
    </div>""",
    unsafe_allow_html=True,
)

if report.matched_hits == 0:
    st.success("✅ Clean batch. No Sigma rules matched the retrieved logs.")
    st.stop()

# ─── Visualizations ───────────────────────────────────────────────────────────
col_viz1, col_viz2, col_viz3 = st.columns([1.5, 2, 1.5])

with col_viz1:
    st.markdown('<div class="sec">Severity Distribution</div>', unsafe_allow_html=True)
    if report.severity_distribution:
        sev_df = pd.DataFrame(list(report.severity_distribution.items()), columns=["Severity", "Count"])
        sev_colours = {"critical": "#F85149", "high": "#D29922", "medium": "#D29922", "low": "#3FB950", "informational": "#58A6FF", "unknown": "#8B949E"}
        fig_sev = go.Figure(go.Pie(
            labels=sev_df["Severity"].str.title(),
            values=sev_df["Count"],
            hole=0.6,
            marker=dict(colors=[sev_colours.get(s.lower(), "#8B949E") for s in sev_df["Severity"]]),
            textinfo="percent+value"
        ))
        fig_sev.update_layout(**_dark_layout(height=280), showlegend=True, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_sev, use_container_width=True)

with col_viz2:
    st.markdown('<div class="sec">MITRE ATT&CK Tactics</div>', unsafe_allow_html=True)
    if report.mitre_tactics:
        mitre_df = pd.DataFrame(list(report.mitre_tactics.items()), columns=["Tactic", "Count"])
        mitre_df = mitre_df.sort_values("Count", ascending=True)
        fig_mitre = go.Figure(go.Bar(
            x=mitre_df["Count"],
            y=mitre_df["Tactic"].str.replace("_", " ").str.title(),
            orientation="h",
            marker_color="#BC8CFF"
        ))
        fig_mitre.update_layout(**_dark_layout(height=280), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_mitre, use_container_width=True)

with col_viz3:
    st.markdown('<div class="sec">Rule Triggers</div>', unsafe_allow_html=True)
    if report.rule_trigger_counts:
        rule_map = {r.rule_id: r.title for r in report.triggered_rules}
        trig_df = pd.DataFrame([
            {"Rule": rule_map.get(rid, rid), "Count": cnt}
            for rid, cnt in report.rule_trigger_counts.items()
        ]).sort_values("Count", ascending=True).tail(5)
        fig_rules = go.Figure(go.Bar(
            x=trig_df["Count"],
            y=trig_df["Rule"],
            orientation="h",
            marker_color="#F85149"
        ))
        fig_rules.update_layout(**_dark_layout(height=280), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_rules, use_container_width=True)


# ─── Detailed Matches Table ───────────────────────────────────────────────────
st.markdown('<div class="sec" style="margin-top:1rem;">🚨 Matched Logs Details</div>', unsafe_allow_html=True)

if report.matches:
    rows = []
    for m in report.matches:
        timestamp = m.raw_source.get(settings.es_time_field, "N/A")
        rules_csv = ", ".join(r.title for r in m.matched_rules)
        sevs = [r.severity.lower() for r in m.matched_rules]
        max_sev = "critical" if "critical" in sevs else "high" if "high" in sevs else "medium" if "medium" in sevs else "low" if "low" in sevs else "info"
        
        # Flatten raw_source slightly for display
        raw_str = json.dumps(m.raw_source, default=str)[:300] + ("..." if len(json.dumps(m.raw_source, default=str)) > 300 else "")
        
        rows.append({
            "Timestamp": timestamp,
            "Document ID": m.doc_id,
            "Matched Rules": rules_csv,
            "Max Severity": max_sev.title(),
            "Raw Data Snippet": raw_str
        })
        
    matches_df = pd.DataFrame(rows)
    
    def _color_sev(val):
        v = val.lower()
        if v == "critical": return "color: #F85149; font-weight:bold"
        if v == "high": return "color: #D29922; font-weight:bold"
        if v == "medium": return "color: #D29922"
        if v == "low": return "color: #3FB950"
        return ""

    st.dataframe(
        matches_df.style.applymap(_color_sev, subset=["Max Severity"]),
        use_container_width=True,
        hide_index=True,
        height=350
    )
