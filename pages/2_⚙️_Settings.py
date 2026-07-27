"""
pages/2_⚙️_Settings.py

Settings & System Info — Local Data Mode
"""

from __future__ import annotations

import streamlit as st
from config import settings, get_logger
from core.local_data_client import get_local_data_client

logger = get_logger(__name__)

st.set_page_config(
    page_title=f"{settings.app_title} | Settings",
    page_icon="⚙️",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html,body,[class*="css"]{ font-family:'Inter',sans-serif!important; }
.block-container{ padding-top:1.5rem!important; }
</style>
""", unsafe_allow_html=True)

st.markdown("## ⚙️ Settings & System Info")
st.markdown(
    "<p style='color:#8B949E;margin-top:-.5rem;'>Local data mode — no Elasticsearch required.</p>",
    unsafe_allow_html=True,
)

# ─── Dataset Status ────────────────────────────────────────────────────────────
st.markdown("### 📁 Dataset")
try:
    client = get_local_data_client()
    df = client.get_dataframe()
    A  = client.get_analytics()
    st.success(f"✅ data.xlsx loaded — **{len(df):,}** rows, **{len(df.columns)}** columns")

    st.markdown("**Column overview:**")
    col_info = pd.DataFrame({"Column": df.columns, "Non-Null": df.notna().sum().values, "Dtype": df.dtypes.values})
    st.dataframe(col_info, hide_index=True, use_container_width=True, height=280)
except Exception as exc:
    st.error(f"❌ Failed to load dataset: {exc}")

import pandas as pd

# ─── App Config ────────────────────────────────────────────────────────────────
st.markdown("### 🛠️ Application Configuration")
config_info = {
    "App Title":      settings.app_title,
    "Environment":    settings.app_env,
    "Log Level":      settings.log_level,
    "Model Save Dir": str(settings.model_save_dir),
    "Data File":      "data/data.xlsx",
}
st.table(pd.DataFrame(list(config_info.items()), columns=["Setting", "Value"]))

# ─── Cache clear ──────────────────────────────────────────────────────────────
st.markdown("### 🔄 Cache Management")
if st.button("🗑️ Clear Analysis Cache & Reload", type="primary"):
    st.cache_resource.clear()
    st.success("Cache cleared — navigate to Dashboard to reload.")
