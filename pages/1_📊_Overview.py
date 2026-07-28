"""
pages/1_📊_Overview.py

ISRO SOC Analytics Dashboard — Local Data Mode
All data sourced from data/data.xlsx, analysed locally via ML.
No Elasticsearch required.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import settings, get_logger
from core.local_data_client import get_local_data_client

logger = get_logger(__name__)

st.set_page_config(
    page_title=f"{settings.app_title} | Dashboard",
    page_icon=":material/analytics:",
    layout="wide",
)

# ─── Data Source Selection & Upload ────────────────────────────────────────────
from pathlib import Path

DATA_DIR = Path("data")
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Find primary platform file (data.xlsx / data.csv / data.parquet)
_primary_file = None
for ext in ("xlsx", "csv", "parquet"):
    candidate = DATA_DIR / f"data.{ext}"
    if candidate.exists():
        _primary_file = candidate
        break
# Fallback: first file in data/ that isn't in uploads/
if _primary_file is None:
    for ext in ("xlsx", "csv", "parquet"):
        for f in sorted(DATA_DIR.glob(f"*.{ext}")):
            _primary_file = f
            break
        if _primary_file:
            break

with st.sidebar:
    st.subheader("Data Source", anchor=False)

    # ── Upload Section ──
    uploaded_file = st.file_uploader(
        "Upload telemetry (CSV / XLSX / Parquet)",
        type=["csv", "xlsx", "parquet"],
        key="data_uploader",
    )
    if uploaded_file is not None:
        if st.session_state.get("last_uploaded_id") != uploaded_file.file_id:
            save_path = UPLOAD_DIR / uploaded_file.name
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.session_state["last_uploaded_id"] = uploaded_file.file_id
            st.session_state["uploaded_file_name"] = uploaded_file.name
            st.cache_resource.clear()
            st.rerun()

    # ── Source Toggle ──
    uploaded_name = st.session_state.get("uploaded_file_name")
    uploaded_files = sorted(UPLOAD_DIR.glob("*"))
    uploaded_files = [f for f in uploaded_files if f.is_file() and f.suffix in (".xlsx", ".csv", ".parquet")]

    source_options = {}
    if _primary_file:
        source_options[f"📦 Platform Data ({_primary_file.name})"] = str(_primary_file)
    for uf in uploaded_files:
        source_options[f"📤 Uploaded: {uf.name}"] = str(uf)

    if len(source_options) > 1:
        selected_label = st.radio(
            "Select data source",
            list(source_options.keys()),
            index=len(source_options) - 1 if uploaded_name else 0,
            key="data_source_radio",
        )
        selected_path = source_options[selected_label]
    elif source_options:
        selected_label = list(source_options.keys())[0]
        selected_path = list(source_options.values())[0]
        st.caption(f"Active: {selected_label}")
    else:
        st.error("No data files found. Upload a file to begin.")
        st.stop()

    st.divider()

# ─── Dark Plotly base matching config.toml ──────────────────────────────────────
def _dark(height: int = 300, **kw) -> dict:
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E6EDF3", family="Inter", size=11),
        margin=dict(l=10, r=10, t=35, b=10),
        height=height,
    )
    base.update(kw)
    return base

THREAT_COLORS = {
    "Critical":    "#F85149",
    "High Threat": "#D29922",
    "Suspicious":  "#BC8CFF",
    "Normal":      "#3FB950",
}

def hex_to_rgba(h: str, alpha: float) -> str:
    h = h.lstrip("#")
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{alpha})"

# ─── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading and analysing local dataset..."):
    client = get_local_data_client(path_key=selected_path)
    A = client.get_analytics()

if "error" in A:
    st.error(f"Analytics failed: {A['error']}", icon=":material/error:")
    st.stop()

df_scored = A.get("scored_df", pd.DataFrame())
cols      = A.get("columns", {})

# ─── Header ────────────────────────────────────────────────────────────────────
st.title("SOC Analytics Dashboard")
data_name = Path(selected_path).name
st.caption(
    f"Analysing **{data_name}** • "
    f"**{A['total_logs']:,}** events • "
    "Isolation Forest + Rule-based Engine"
)

# ─── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filters")

    if cols.get("host") and cols["host"] in df_scored.columns:
        all_hosts = ["All"] + sorted(df_scored[cols["host"]].dropna().unique().tolist())
        sel_host = st.selectbox("Filter host", all_hosts)
    else:
        sel_host = "All"

    if cols.get("user") and cols["user"] in df_scored.columns:
        all_users = ["All"] + sorted(df_scored[cols["user"]].dropna().unique().tolist())
        sel_user = st.selectbox("Filter user", all_users)
    else:
        sel_user = "All"

    sel_threat = st.multiselect(
        "Threat level",
        ["Critical", "High Threat", "Suspicious", "Normal"],
        default=["Critical", "High Threat", "Suspicious", "Normal"],
    )

    st.space("medium")
    if st.button("Refresh Analysis", use_container_width=True, type="primary"):
        st.cache_resource.clear()
        st.rerun()

# Apply filters
df_view = df_scored.copy()
if sel_host != "All" and cols.get("host") and cols["host"] in df_view.columns:
    df_view = df_view[df_view[cols["host"]] == sel_host]
if sel_user != "All" and cols.get("user") and cols["user"] in df_view.columns:
    df_view = df_view[df_view[cols["user"]] == sel_user]
if sel_threat:
    df_view = df_view[df_view["threat_level"].isin(sel_threat)]

n_crit  = int((df_view["threat_level"] == "Critical").sum())
n_high  = int((df_view["threat_level"] == "High Threat").sum())
n_susp  = int((df_view["threat_level"] == "Suspicious").sum())
n_norm  = int((df_view["threat_level"] == "Normal").sum())
n_anom  = int(df_view["is_anomaly"].sum())

# ─── KPI Banner ────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    with st.container(border=True):
        st.metric("Total Events", f"{len(df_view):,}", help="in current filter")
with c2:
    with st.container(border=True):
        st.metric("Critical", f"{n_crit:,}", delta="Immediate action", delta_color="off")
with c3:
    with st.container(border=True):
        st.metric("High Threat", f"{n_high:,}", delta="Investigate", delta_color="off")
with c4:
    with st.container(border=True):
        st.metric("Suspicious", f"{n_susp:,}", delta="Monitor", delta_color="off")

c5, c6, c7 = st.columns(3)
with c5:
    with st.container(border=True):
        st.metric("ML Anomalies", f"{n_anom:,}", delta=f"{A['anomaly_rate']:.1f}% of dataset", delta_color="off")
with c6:
    with st.container(border=True):
        st.metric("Unique Hosts", f"{A['unique_hosts']}")
with c7:
    with st.container(border=True):
        st.metric("Unique Users", f"{A['unique_users']}")

st.space("small")

# ─── Tabs ──────────────────────────────────────────────────────────────────────
tab_over, tab_threats, tab_anom, tab_patterns, tab_identity, tab_code, tab_files, tab_ip, tab_telemetry, tab_events = st.tabs([
    ":material/home: Overview",
    ":material/warning: Threats",
    ":material/smart_toy: Anomalies",
    ":material/hub: Patterns",
    ":material/person: Identity",
    ":material/code: Code Integrity",
    ":material/folder: File Activity",
    ":material/wifi: IP Monitoring",
    ":material/search: Deep Telemetry",
    ":material/table_rows: Events",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_over:
    col_timeline, col_threat_donut = st.columns([3, 1])

    # Timeline
    with col_timeline:
        st.subheader("Event volume over time", anchor=False)
        tl = A.get("timeline", pd.DataFrame())
        if not tl.empty:
            fig_tl = go.Figure(go.Scatter(
                x=tl["timestamp"], y=tl["count"],
                fill="tozeroy",
                line=dict(color="#58A6FF", width=2),
                fillcolor="rgba(88,166,255,0.18)",
                hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>Events: %{y:,}<extra></extra>",
            ))
            fig_tl.update_layout(
                **_dark(height=280),
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor="#30363D", title="Events"),
            )
            st.plotly_chart(fig_tl, use_container_width=True)

    # Threat donut
    with col_threat_donut:
        st.subheader("Threat distribution", anchor=False)
        ts = A.get("threat_summary", pd.DataFrame())
        if not ts.empty:
            colors = [THREAT_COLORS.get(v, "#8B949E") for v in ts["threat_level"]]
            fig_td = go.Figure(go.Pie(
                labels=ts["threat_level"], values=ts["count"],
                hole=0.62,
                marker=dict(colors=colors, line=dict(color="#0D1117", width=2)),
                textposition="outside", textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>%{value:,}<extra></extra>",
            ))
            total = ts["count"].sum()
            fig_td.update_layout(
                **_dark(height=280), showlegend=False,
                annotations=[dict(text=f"<b>{total:,}</b><br><span style='color:#8B949E'>events</span>",
                                  x=0.5, y=0.5, font_size=13, showarrow=False)],
            )
            st.plotly_chart(fig_td, use_container_width=True)

    st.space("small")
    # Event categories + actions
    col_cat, col_act = st.columns(2)
    with col_cat:
        with st.container(border=True):
            st.subheader("Event categories", anchor=False)
            cat_df = A.get("top_categories", pd.DataFrame())
            if not cat_df.empty:
                fig_cat = go.Figure(go.Bar(
                    x=cat_df["count"], y=cat_df["value"],
                    orientation="h",
                    marker=dict(color=cat_df["count"], colorscale=[[0,"#1F3B5E"],[1,"#58A6FF"]]),
                    hovertemplate="<b>%{y}</b><br>%{x:,}<extra></extra>",
                ))
                fig_cat.update_layout(**_dark(height=280),
                                      xaxis=dict(title="Events", gridcolor="#30363D"),
                                      yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_cat, use_container_width=True)

    with col_act:
        with st.container(border=True):
            st.subheader("Event actions", anchor=False)
            act_df = A.get("top_actions", pd.DataFrame())
            if not act_df.empty:
                fig_act = go.Figure(go.Bar(
                    x=act_df["count"], y=act_df["value"],
                    orientation="h",
                    marker=dict(color=act_df["count"], colorscale=[[0,"#1F3B5E"],[1,"#BC8CFF"]]),
                    hovertemplate="<b>%{y}</b><br>%{x:,}<extra></extra>",
                ))
                fig_act.update_layout(**_dark(height=280),
                                      xaxis=dict(title="Events", gridcolor="#30363D"),
                                      yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_act, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — THREATS
# ══════════════════════════════════════════════════════════════════════════════
with tab_threats:
    col_th_chart, col_th_host = st.columns([2, 1])

    with col_th_chart:
        st.subheader("Threat level over time", anchor=False)
        ts_col = cols.get("ts")
        if ts_col and ts_col in df_view.columns and not df_view.empty:
            tl_threat = (
                df_view.set_index(ts_col)
                .groupby([pd.Grouper(freq="1h"), "threat_level"])
                .size().unstack(fill_value=0).reset_index()
            )
            fig_th_tl = go.Figure()
            for level, color in THREAT_COLORS.items():
                if level in tl_threat.columns:
                    fig_th_tl.add_trace(go.Scatter(
                        x=tl_threat[ts_col], y=tl_threat[level],
                        name=level, stackgroup="one",
                        line=dict(color=color, width=0.8),
                        fillcolor=hex_to_rgba(color, 0.5) if color.startswith("#") else color,
                    ))
            fig_th_tl.update_layout(**_dark(height=280), hovermode="x unified",
                                    xaxis=dict(showgrid=False),
                                    yaxis=dict(gridcolor="#30363D"))
            st.plotly_chart(fig_th_tl, use_container_width=True)
        else:
            st.info("No timestamp data for timeline.")

    with col_th_host:
        st.subheader("Threats by host", anchor=False)
        h_anom = A.get("host_anomalies", pd.DataFrame())
        if not h_anom.empty:
            host_col_name = h_anom.columns[0]
            fig_hth = go.Figure(go.Bar(
                x=h_anom["anomaly_count"], y=h_anom[host_col_name],
                orientation="h",
                marker=dict(color=h_anom["anomaly_count"],
                            colorscale=[[0,"#D29922"],[1,"#F85149"]]),
                hovertemplate="<b>%{y}</b><br>Anomalies: %{x}<extra></extra>",
            ))
            fig_hth.update_layout(**_dark(height=280),
                                  xaxis=dict(title="Anomaly Count", gridcolor="#30363D"),
                                  yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_hth, use_container_width=True)
            
    # ── Threat Analysis Deep Dive ─────────────────────────────────
    crit_df = A.get("critical_events", pd.DataFrame())
    if not crit_df.empty:
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.subheader("Processes weaponized by Threats", anchor=False)
                proc_col = cols.get("process")
                if proc_col and proc_col in crit_df.columns:
                    p_counts = crit_df[proc_col].value_counts().reset_index()
                    p_counts.columns = ["Process", "Count"]
                    fig_tp = px.treemap(p_counts.head(20), path=["Process"], values="Count", color="Count",
                                        color_continuous_scale=[[0,"#58A6FF"],[1,"#F85149"]])
                    fig_tp.update_layout(**_dark(height=280), coloraxis_showscale=False)
                    st.plotly_chart(fig_tp, use_container_width=True)
                else:
                    st.info("No process data in threats.")
        with c2:
            with st.container(border=True):
                st.subheader("Top Malicious Commands", anchor=False)
                cmd_col = cols.get("cmd")
                if cmd_col and cmd_col in crit_df.columns:
                    cmd_counts = crit_df[cmd_col].dropna().value_counts().reset_index()
                    cmd_counts.columns = ["Command", "Count"]
                    cmd_counts = cmd_counts[cmd_counts["Command"].str.strip() != ""]
                    if not cmd_counts.empty:
                        st.dataframe(cmd_counts.head(10), hide_index=True, use_container_width=True, height=280)
                    else:
                        st.info("No suspicious commands detected.")
                else:
                    st.info("No command line data in threats.")

    with st.container(border=True):
        st.subheader("Critical & high-threat events", anchor=False)
        crit_df = A.get("critical_events", pd.DataFrame())
        if not crit_df.empty:
            def _style_threat(val):
                if val == "Critical":   return "color:#F85149;font-weight:700"
                if val == "High Threat": return "color:#D29922;font-weight:700"
                return ""
            display_crit = crit_df.copy()
            if "@timestamp" in display_crit.columns:
                display_crit["@timestamp"] = display_crit["@timestamp"].astype(str).str[:19]
            st.dataframe(
                display_crit.style.map(_style_threat, subset=["threat_level"]),
                use_container_width=True, hide_index=True, height=380,
            )
            csv = crit_df.to_csv(index=False).encode()
            st.download_button("Download Critical Events CSV", csv, "critical_events.csv", "text/csv")
        else:
            st.success("No critical events in current filter.", icon=":material/check_circle:")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ANOMALIES (ML)
# ══════════════════════════════════════════════════════════════════════════════
with tab_anom:
    col_ah, col_ab = st.columns([1, 2])

    with col_ah:
        st.subheader("Anomaly score distribution", anchor=False)
        if not df_view.empty:
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Histogram(
                x=df_view[~df_view["is_anomaly"]]["anomaly_score"],
                name="Normal", marker_color="#58A6FF", opacity=0.75, nbinsx=40,
            ))
            fig_hist.add_trace(go.Histogram(
                x=df_view[df_view["is_anomaly"]]["anomaly_score"],
                name="Anomaly", marker_color="#F85149", opacity=0.85, nbinsx=40,
            ))
            fig_hist.update_layout(
                barmode="overlay", **_dark(height=300),
                xaxis=dict(title="Anomaly Score", gridcolor="#30363D"),
                yaxis=dict(title="Count", gridcolor="#30363D"),
                legend=dict(orientation="h", y=1.05),
            )
            st.plotly_chart(fig_hist, use_container_width=True)

    # ── Explainable AI (SHAP) ─────────────────────────────────────
    st.divider()
    with st.container(border=True):
        st.subheader("Explainable AI (SHAP)", anchor=False)
        st.markdown("Understand *why* the Machine Learning engine flagged an event as anomalous. SHAP values mathematically calculate the contribution of each individual feature to the final anomaly score (positive values push the score higher/more anomalous).")
        
        shap_values = A.get("shap_values")
        shap_indices = A.get("shap_indices")
        shap_base = A.get("shap_base_value")
        shap_feats = A.get("shap_feature_names")
        
        if shap_values is not None and shap_indices is not None and len(shap_indices) > 0:
            options = []
            for i, idx in enumerate(shap_indices):
                if idx in df_view.index:
                    row = df_view.loc[idx]
                    host = row.get("host.name") or row.get("host.hostname") or "unknown"
                    score = row.get("anomaly_score", 0.0)
                    options.append((i, idx, f"Rank {i+1} | Score: {score:.3f} | Host: {host} (Log ID: {idx})"))
                    
            if options:
                selected = st.selectbox("Select Anomaly to Explain:", options, format_func=lambda x: x[2])
                
                if selected:
                    i_relative = selected[0]
                    idx = selected[1]
                    
                    import shap
                    import matplotlib.pyplot as plt
                    
                    # Temporarily force matplotlib defaults for dark mode BEFORE plotting
                    with plt.rc_context({
                        'text.color': '#A1B0C4',
                        'axes.labelcolor': '#A1B0C4',
                        'xtick.color': '#A1B0C4',
                        'ytick.color': '#A1B0C4',
                        'axes.edgecolor': '#1a2d45',
                        'figure.facecolor': '#091322',
                        'axes.facecolor': '#091322'
                    }):
                        # Create Explanation object for waterfall plot
                        # Note: For Isolation Forest, lower values indicate anomaly, so we invert SHAP values for intuitive display
                        # where positive values = more anomalous.
                        exp = shap.Explanation(
                            values=-shap_values[i_relative], 
                            base_values=-shap_base,
                            feature_names=shap_feats
                        )
                        
                        fig, ax = plt.subplots(figsize=(10, 5))
                        shap.plots.waterfall(exp, show=False)
                        
                        # SHAP specifically hardcodes some text elements to black/gray, so we override them manually as well:
                        for text in ax.texts:
                            text.set_color('#E6EDF3')
                        for label in ax.get_yticklabels():
                            label.set_color('#A1B0C4')
                        for label in ax.get_xticklabels():
                            label.set_color('#A1B0C4')
                            
                        st.pyplot(fig, clear_figure=True)
                    
                    with st.expander("💡 How to read this SHAP graph?", expanded=True):
                        st.markdown("""
                        **SHAP (SHapley Additive exPlanations)** breaks down exactly how the Machine Learning model reached its final anomaly score for this specific event.
                        
                        - **The Base Value ($E[f(X)]$):** Shown at the bottom, this is the average anomaly score across the dataset. 
                        - **The Red Bars (Positive Values):** These features pushed the anomaly score **higher** (making the event more suspicious). The length of the bar shows the magnitude of its impact.
                        - **The Blue Bars (Negative Values):** These features pushed the score **lower** (making the event appear more normal).
                        - **The Final Value ($f(x)$):** Shown at the top right, this is the actual anomaly score assigned to this event by the AI.
                        
                        *For example: If `proc_rarity` has a large red bar, it means this event was flagged heavily because the process running is extremely rare in your environment.*
                        """)
            else:
                st.info("Top anomalous events have been filtered out by the current sidebar settings.")
        else:
            st.warning("SHAP values not available. The ML pipeline may have failed to compute them.")

    with col_ab:
        st.subheader("Anomaly score per host", anchor=False)
        host_col_k = cols.get("host")
        if host_col_k and host_col_k in df_view.columns:
            top_hosts_list = df_view[host_col_k].value_counts().head(12).index.tolist()
            sub = df_view[df_view[host_col_k].isin(top_hosts_list)]
            fig_box = go.Figure()
            for h in top_hosts_list:
                s = sub[sub[host_col_k] == h]["anomaly_score"]
                has_a = sub[sub[host_col_k] == h]["is_anomaly"].any()
                fig_box.add_trace(go.Box(
                    y=s, name=str(h)[:20],
                    marker_color="#F85149" if has_a else "#58A6FF",
                    boxpoints="outliers", line_width=1,
                ))
            fig_box.update_layout(
                **_dark(height=300), showlegend=False,
                xaxis=dict(tickangle=-30),
                yaxis=dict(title="Anomaly Score", gridcolor="#30363D"),
            )
            st.plotly_chart(fig_box, use_container_width=True)
        else:
            st.info("No host column found.")

    with st.container(border=True):
        st.subheader("Top anomalous events (ML flagged)", anchor=False)
        anom_df = A.get("anomaly_events", pd.DataFrame())
        if not anom_df.empty:
            display_anom = anom_df.copy()
            if "@timestamp" in display_anom.columns:
                display_anom["@timestamp"] = display_anom["@timestamp"].astype(str).str[:19]
            st.dataframe(display_anom, use_container_width=True, hide_index=True, height=380)
            csv = anom_df.to_csv(index=False).encode()
            st.download_button("Download Anomalies CSV", csv, "anomalies.csv", "text/csv")

    st.subheader("Threshold sensitivity", anchor=False)
    if not df_view.empty:
        sens = []
        for t in [0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]:
            n = int((df_view["anomaly_score"] >= t).sum())
            sens.append({"Threshold": t, "Flagged": n, "Flagged %": f"{n/max(len(df_view),1)*100:.1f}%"})
        st.dataframe(pd.DataFrame(sens), hide_index=True, use_container_width=True, height=200)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — PATTERNS
# ══════════════════════════════════════════════════════════════════════════════
with tab_patterns:
    col_p1, col_p2 = st.columns(2)

    with col_p1:
        with st.container(border=True):
            st.subheader("Process parent → child relationships", anchor=False)
            pt = A.get("process_tree", pd.DataFrame())
            if not pt.empty:
                fig_pt = go.Figure(go.Bar(
                    x=pt["count"],
                    y=pt[pt.columns[0]] + " → " + pt[pt.columns[1]],
                    orientation="h",
                    marker=dict(color=pt["count"], colorscale=[[0,"#1F3B5E"],[0.5,"#BC8CFF"],[1,"#F85149"]]),
                    hovertemplate="<b>%{y}</b><br>Occurrences: %{x:,}<extra></extra>",
                ))
                fig_pt.update_layout(
                    **_dark(height=400),
                    xaxis=dict(title="Count", gridcolor="#30363D"),
                    yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
                )
                st.plotly_chart(fig_pt, use_container_width=True)
                st.dataframe(pt.rename(columns={pt.columns[0]: "Parent", pt.columns[1]: "Child"}),
                             hide_index=True, use_container_width=True, height=250)

    with col_p2:
        with st.container(border=True):
            st.subheader("Top executable paths", anchor=False)
            exe_df = A.get("top_executables", pd.DataFrame())
            if not exe_df.empty:
                fig_exe = go.Figure(go.Bar(
                    x=exe_df["count"],
                    y=exe_df["value"].str[-50:],
                    orientation="h",
                    marker=dict(color=exe_df["count"], colorscale=[[0,"#1F3B5E"],[1,"#56D364"]]),
                    hovertemplate="<b>%{y}</b><br>%{x:,}<extra></extra>",
                ))
                fig_exe.update_layout(
                    **_dark(height=400),
                    xaxis=dict(title="Count", gridcolor="#30363D"),
                    yaxis=dict(autorange="reversed", tickfont=dict(size=9)),
                )
                st.plotly_chart(fig_exe, use_container_width=True)

    with st.container(border=True):
        st.subheader("Top processes", anchor=False)
        proc_df = A.get("top_processes", pd.DataFrame())
        if not proc_df.empty:
            fig_proc = px.treemap(
                proc_df.head(20), path=["value"], values="count",
                color="count",
                color_continuous_scale=[[0,"#1F3B5E"],[0.5,"#58A6FF"],[1,"#F85149"]],
            )
            fig_proc.update_traces(
                hovertemplate="<b>%{label}</b><br>Count: %{value:,}<extra></extra>",
                textinfo="label+value",
            )
            fig_proc.update_layout(**_dark(height=320), coloraxis_showscale=False)
            st.plotly_chart(fig_proc, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — IDENTITY
# ══════════════════════════════════════════════════════════════════════════════
with tab_identity:
    col_u1, col_u2 = st.columns(2)

    with col_u1:
        with st.container(border=True):
            st.subheader("Top users by event volume", anchor=False)
            user_df = A.get("top_users", pd.DataFrame())
            if not user_df.empty:
                fig_usr = go.Figure(go.Bar(
                    x=user_df["count"], y=user_df["value"],
                    orientation="h",
                    marker=dict(color=user_df["count"], colorscale=[[0,"#1F3B5E"],[1,"#D29922"]]),
                    hovertemplate="<b>%{y}</b><br>%{x:,}<extra></extra>",
                ))
                fig_usr.update_layout(**_dark(height=320),
                                      xaxis=dict(gridcolor="#30363D"),
                                      yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_usr, use_container_width=True)

    with col_u2:
        with st.container(border=True):
            st.subheader("Anomalies per user", anchor=False)
            user_anom = A.get("user_anomalies", pd.DataFrame())
            if not user_anom.empty:
                user_col_n = user_anom.columns[0]
                fig_ua = go.Figure(go.Bar(
                    x=user_anom["anomaly_count"], y=user_anom[user_col_n],
                    orientation="h",
                    marker=dict(color=user_anom["anomaly_count"],
                                colorscale=[[0,"#D29922"],[1,"#F85149"]]),
                ))
                fig_ua.update_layout(**_dark(height=320),
                                     xaxis=dict(title="Anomaly Count", gridcolor="#30363D"),
                                     yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_ua, use_container_width=True)
                
    with st.container(border=True):
        st.subheader("User → Process Activity (Sankey)", anchor=False)
        up = A.get("user_process_matrix", pd.DataFrame())
        if not up.empty:
            user_col_n = up.columns[0]
            proc_col_n = up.columns[1]
            
            # Build Sankey Diagram
            all_nodes = list(pd.concat([up[user_col_n], up[proc_col_n]]).unique())
            node_dict = {node: i for i, node in enumerate(all_nodes)}
            
            sources = up[user_col_n].map(node_dict).tolist()
            targets = up[proc_col_n].map(node_dict).tolist()
            values = up["count"].tolist()
            
            fig_sk = go.Figure(data=[go.Sankey(
                node = dict(
                  pad = 15, thickness = 20,
                  line = dict(color = "black", width = 0.5),
                  label = all_nodes,
                  color = "#58A6FF"
                ),
                link = dict(
                  source = sources, target = targets, value = values,
                  color = "rgba(88,166,255,0.2)"
                ))])
            fig_sk.update_layout(**_dark(height=400), font_size=11)
            st.plotly_chart(fig_sk, use_container_width=True)

    with st.container(border=True):
        st.subheader("User–process activity matrix", anchor=False)
        up = A.get("user_process_matrix", pd.DataFrame())
        if not up.empty:
            user_col_n = up.columns[0]
            proc_col_n = up.columns[1]
            pivot = up.pivot_table(index=user_col_n, columns=proc_col_n, values="count", fill_value=0)
            fig_heat = go.Figure(go.Heatmap(
                z=pivot.values,
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale=[[0,"#0D1117"],[0.3,"#1F3B5E"],[0.7,"#58A6FF"],[1,"#F85149"]],
                hovertemplate="<b>User: %{y}</b><br>Process: %{x}<br>Count: %{z}<extra></extra>",
            ))
            fig_heat.update_layout(
                **_dark(height=max(250, len(pivot)*28)),
                xaxis=dict(tickangle=-40, tickfont=dict(size=9)),
                yaxis=dict(tickfont=dict(size=10)),
            )
            st.plotly_chart(fig_heat, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — CODE INTEGRITY
# ══════════════════════════════════════════════════════════════════════════════
with tab_code:
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        with st.container(border=True):
            st.subheader("Process Code Signatures", anchor=False)
            sig_trust = A.get("code_signature_trust", pd.DataFrame())
            if not sig_trust.empty:
                colors_trust = ["#58A6FF" if "true" in str(s).lower() else "#F85149" for s in sig_trust["status"]]
                fig_trust = go.Figure(go.Pie(
                    labels=sig_trust["status"].astype(str), values=sig_trust["count"],
                    hole=0.6,
                    marker=dict(colors=colors_trust, line=dict(color="#0D1117", width=2)),
                    textposition="inside", textinfo="label+percent"
                ))
                fig_trust.update_layout(**_dark(height=280), showlegend=False)
                st.plotly_chart(fig_trust, use_container_width=True)
            else:
                st.info("No code signature trust data.")
    with col_c2:
        with st.container(border=True):
            st.subheader("Top SHA256 Hashes", anchor=False)
            sha = A.get("top_sha256", pd.DataFrame())
            if not sha.empty:
                fig_sha = go.Figure(go.Bar(
                    x=sha["count"], y=sha["value"].str[:16] + "...",
                    orientation="h",
                    marker=dict(color=sha["count"], colorscale=[[0,"#1F3B5E"],[1,"#BC8CFF"]]),
                    hovertemplate="<b>Hash: %{y}</b><br>Count: %{x}<extra></extra>",
                ))
                fig_sha.update_layout(**_dark(height=280),
                                      xaxis=dict(gridcolor="#30363D"),
                                      yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_sha, use_container_width=True)
            else:
                st.info("No SHA256 data found.")
    
    with st.container(border=True):
        st.subheader("Top MD5 Hashes", anchor=False)
        md5 = A.get("top_md5", pd.DataFrame())
        if not md5.empty:
            st.dataframe(md5, use_container_width=True, hide_index=True)
        else:
            st.info("No MD5 data found.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — FILE ACTIVITY
# ══════════════════════════════════════════════════════════════════════════════
with tab_files:
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        with st.container(border=True):
            st.subheader("Top Modified File Extensions", anchor=False)
            exts = A.get("top_file_exts", pd.DataFrame())
            if not exts.empty:
                fig_ext = go.Figure(go.Bar(
                    x=exts["count"], y=exts["value"],
                    orientation="h",
                    marker=dict(color=exts["count"], colorscale=[[0,"#1F3B5E"],[1,"#56D364"]]),
                ))
                fig_ext.update_layout(**_dark(height=300), yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_ext, use_container_width=True)
            else:
                st.info("No file extension data.")
    with col_f2:
        with st.container(border=True):
            st.subheader("Top File Names", anchor=False)
            fnames = A.get("top_file_names", pd.DataFrame())
            if not fnames.empty:
                fig_fn = go.Figure(go.Bar(
                    x=fnames["count"], y=fnames["value"],
                    orientation="h",
                    marker=dict(color=fnames["count"], colorscale=[[0,"#1F3B5E"],[1,"#D29922"]]),
                ))
                fig_fn.update_layout(**_dark(height=300), yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_fn, use_container_width=True)
            else:
                st.info("No file name data.")

    with st.container(border=True):
        st.subheader("Top File Paths Targeted", anchor=False)
        fpaths = A.get("top_file_paths", pd.DataFrame())
        if not fpaths.empty:
            st.dataframe(fpaths, use_container_width=True, hide_index=True, height=250)
        else:
            st.info("No file path data.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — IP MONITORING
# ══════════════════════════════════════════════════════════════════════════════
with tab_ip:
    col_ipt, col_ipr = st.columns([2, 1])
    
    with col_ipt:
        st.subheader("IP Activity over time", anchor=False)
        ip_tl = A.get("ip_timeline", pd.DataFrame())
        if not ip_tl.empty:
            fig_ipt = go.Figure(go.Scatter(
                x=ip_tl["hour"], y=ip_tl["count"],
                fill="tozeroy",
                line=dict(color="#BC8CFF", width=2),
                fillcolor="rgba(188,140,255,0.18)",
                hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>IP Events: %{y:,}<extra></extra>",
            ))
            fig_ipt.update_layout(
                **_dark(height=300),
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor="#30363D", title="Log Volume"),
            )
            st.plotly_chart(fig_ipt, use_container_width=True)
        else:
            st.info("No timeline data available for IP addresses.")
            
        st.subheader("High Threat & Anomalous IPs", anchor=False)
        anom_ips = A.get("anomalous_ips", pd.DataFrame())
        if not anom_ips.empty:
            def _style_anom_ip(val):
                if val == "Critical": return "color:#F85149;font-weight:700"
                if val == "High Threat": return "color:#D29922;font-weight:700"
                return ""
            st.dataframe(
                anom_ips.style.map(_style_anom_ip, subset=["threat_level"]),
                use_container_width=True, hide_index=True, height=250
            )
        else:
            st.success("No anomalous or threat IP activity detected.", icon=":material/check_circle:")
            
    with col_ipr:
        st.subheader("Top Active Host IPs", anchor=False)
        top_host_ips = A.get("top_host_ips", pd.DataFrame())
        if not top_host_ips.empty:
            fig_h_ip = px.bar(
                top_host_ips.sort_values("count", ascending=True),
                x="count", y="ip", orientation="h",
                color_discrete_sequence=["#58A6FF"]
            )
            fig_h_ip.update_layout(**_dark(height=250))
            st.plotly_chart(fig_h_ip, use_container_width=True)
        else:
            st.info("No Host IP data.")
            
        st.subheader("Top Event IPs", anchor=False)
        top_evt_ips = A.get("top_event_ips", pd.DataFrame())
        if not top_evt_ips.empty:
            fig_e_ip = px.bar(
                top_evt_ips.sort_values("count", ascending=True),
                x="count", y="ip", orientation="h",
                color_discrete_sequence=["#3FB950"]
            )
            fig_e_ip.update_layout(**_dark(height=250))
            st.plotly_chart(fig_e_ip, use_container_width=True)
        else:
            st.info("No secondary Event/Source IP data found in logs.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 9 — DEEP TELEMETRY EXPLORER (ALL 235 COLUMNS)
# ══════════════════════════════════════════════════════════════════════════════
with tab_telemetry:
    schema = A.get("schema", {})
    ns_groups = schema.get("namespace_groups", {})
    col_profiles = schema.get("column_profiles", {})
    total_cols = schema.get("total_columns", 0)

    st.subheader(f"Deep Telemetry Explorer — {total_cols} parameters profiled", anchor=False)
    st.caption("Every column from the dataset is automatically categorized, profiled, and inspectable below.")

    # ── Summary KPIs ─────────────────────────────────────────────
    n_high_fill = sum(1 for p in col_profiles.values() if p["fill_pct"] >= 80)
    n_low_fill = sum(1 for p in col_profiles.values() if 0 < p["fill_pct"] < 20)
    n_empty = sum(1 for p in col_profiles.values() if p["fill_pct"] == 0)
    n_namespaces = len(ns_groups)

    km1, km2, km3, km4 = st.columns(4)
    with km1:
        with st.container(border=True):
            st.metric("Total Parameters", f"{total_cols}")
    with km2:
        with st.container(border=True):
            st.metric("High Fill (≥80%)", f"{n_high_fill}")
    with km3:
        with st.container(border=True):
            st.metric("Sparse (<20%)", f"{n_low_fill}")
    with km4:
        with st.container(border=True):
            st.metric("Empty Columns", f"{n_empty}")

    st.space("small")

    # ── Fill-rate overview chart ──────────────────────────────────
    with st.container(border=True):
        st.subheader("Fill rate by namespace", anchor=False)
        ns_fill_data = []
        for ns, ns_cols in ns_groups.items():
            fills = [col_profiles[c]["fill_pct"] for c in ns_cols if c in col_profiles]
            avg_fill = sum(fills) / len(fills) if fills else 0
            ns_fill_data.append({"Namespace": ns, "Columns": len(ns_cols), "Avg Fill %": round(avg_fill, 1)})
        ns_fill_df = pd.DataFrame(ns_fill_data)
        if not ns_fill_df.empty:
            fig_nf = go.Figure(go.Bar(
                x=ns_fill_df["Avg Fill %"], y=ns_fill_df["Namespace"],
                orientation="h",
                text=[f"{v}% ({c} cols)" for v, c in zip(ns_fill_df["Avg Fill %"], ns_fill_df["Columns"])],
                textposition="auto",
                marker=dict(
                    color=ns_fill_df["Avg Fill %"],
                    colorscale=[[0,"#F85149"],[0.5,"#D29922"],[1,"#3FB950"]],
                ),
            ))
            fig_nf.update_layout(**_dark(height=max(200, len(ns_fill_df)*32)),
                                 xaxis=dict(title="Average Fill Rate %", range=[0, 100], gridcolor="#30363D"),
                                 yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_nf, use_container_width=True)

    st.space("small")

    # ── Namespace expanders with per-column profiles ─────────────
    _NS_LABELS = {
        "process": ":material/memory: Process Telemetry",
        "event": ":material/event: Event Metadata",
        "host": ":material/dns: Host Information",
        "file": ":material/description: File Activity",
        "user": ":material/person: User / Identity",
        "agent": ":material/smart_toy: Agent Metadata",
        "ecs": ":material/schema: ECS Fields",
        "data_stream": ":material/stream: Data Stream",
        "elastic": ":material/cloud: Elastic Metadata",
        "Effective_process": ":material/verified: Effective Process",
        "_root": ":material/data_object: Root-level Fields",
    }

    for ns, ns_cols in ns_groups.items():
        label = _NS_LABELS.get(ns, f":material/category: {ns}")
        with st.expander(f"{label}  —  **{len(ns_cols)} columns**", expanded=False):
            rows = []
            for c in ns_cols:
                p = col_profiles.get(c, {})
                top_val = p.get("top5", [{}])[0].get("value", "—") if p.get("top5") else "—"
                rows.append({
                    "Column": c,
                    "Type": p.get("dtype", "?"),
                    "Non-Null": f"{p.get('non_null', 0):,}",
                    "Fill %": p.get("fill_pct", 0),
                    "Unique": f"{p.get('unique', 0):,}",
                    "Most Common Value": top_val[:60],
                })
            profile_df = pd.DataFrame(rows)

            def _fill_color(val):
                if isinstance(val, (int, float)):
                    if val >= 80: return "color:#3FB950"
                    if val >= 40: return "color:#D29922"
                    if val > 0:   return "color:#F85149"
                return "color:#8B949E"

            st.dataframe(
                profile_df.style.map(_fill_color, subset=["Fill %"]),
                use_container_width=True, hide_index=True,
                height=min(600, max(150, len(rows) * 38)),
            )

            # Per-column deep-dive selector
            sel_col = st.selectbox(f"Inspect column values", ns_cols, key=f"inspect_{ns}")
            if sel_col:
                p = col_profiles.get(sel_col, {})
                ic1, ic2, ic3 = st.columns(3)
                with ic1:
                    st.metric("Non-null", f"{p.get('non_null', 0):,}")
                with ic2:
                    st.metric("Fill Rate", f"{p.get('fill_pct', 0)}%")
                with ic3:
                    st.metric("Unique Values", f"{p.get('unique', 0):,}")

                top5 = p.get("top5", [])
                if top5:
                    t5_df = pd.DataFrame(top5)
                    t5_df.columns = ["Value", "Count"]
                    col_v1, col_v2 = st.columns([1, 2])
                    with col_v1:
                        st.dataframe(t5_df, hide_index=True, use_container_width=True)
                    with col_v2:
                        fig_t5 = go.Figure(go.Bar(
                            x=t5_df["Count"], y=t5_df["Value"].str[:40],
                            orientation="h",
                            marker=dict(color="#58A6FF"),
                        ))
                        fig_t5.update_layout(**_dark(height=180),
                                             yaxis=dict(autorange="reversed"),
                                             xaxis=dict(gridcolor="#30363D"))
                        st.plotly_chart(fig_t5, use_container_width=True, key=f"t5_chart_{ns}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 9 — EVENTS TABLE (ALL 235 COLUMNS)
# ══════════════════════════════════════════════════════════════════════════════
with tab_events:
    st.subheader("Full event browser — all parameters", anchor=False)

    all_available = [c for c in df_view.columns if c not in ("is_anomaly",)]

    # Preset column groups for quick selection
    preset_key = ["@timestamp", cols.get("host"), cols.get("user"), cols.get("process"),
                  cols.get("action"), cols.get("cmd"), "anomaly_score", "threat_level"]
    preset_key = [c for c in preset_key if c and c in df_view.columns]

    view_mode = st.radio("Column view", ["Key columns", "All 235 columns", "Custom selection"],
                         horizontal=True, key="ev_view_mode")

    if view_mode == "Key columns":
        show = preset_key
    elif view_mode == "All 235 columns":
        show = all_available
    else:
        show = st.multiselect("Select columns", all_available, default=preset_key, key="ev_custom_cols")

    display_ev = df_view[show].copy() if show else df_view.copy()
    if "@timestamp" in display_ev.columns:
        display_ev["@timestamp"] = display_ev["@timestamp"].astype(str).str[:19]
    if "anomaly_score" in display_ev.columns:
        display_ev = display_ev.sort_values("anomaly_score", ascending=False)

    def _col_style(val):
        if val == "Critical":    return "color:#F85149;font-weight:700"
        if val == "High Threat": return "color:#D29922;font-weight:700"
        if val == "Suspicious":  return "color:#BC8CFF"
        return ""

    cell_count = display_ev.shape[0] * display_ev.shape[1]
    if "threat_level" in display_ev.columns and cell_count < 250_000:
        styled_ev = display_ev.style.map(_col_style, subset=["threat_level"])
        st.dataframe(styled_ev, use_container_width=True, hide_index=True, height=600)
    else:
        st.dataframe(display_ev, use_container_width=True, hide_index=True, height=600)

    st.caption(f"Showing **{len(show)}** of **{len(all_available)}** columns • **{len(display_ev):,}** rows")

    csv = display_ev.to_csv(index=False).encode()
    st.download_button(
        f"Download {len(display_ev):,} Events CSV",
        csv, "filtered_events.csv", "text/csv",
    )
