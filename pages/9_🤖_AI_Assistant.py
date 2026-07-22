"""
pages/10_🤖_AI_Assistant.py

AI-powered SOC Investigation Assistant — ISRO SOC Analytics Platform.

Provides a conversational interface for investigating security incidents.
Operates exclusively on the current session batch — no additional ES queries.

Two modes:
  🤖 LLM Mode        — Powered by Google Gemini or OpenAI (if API key configured)
  🔧 Deterministic   — Always available; structured answers from computed analytics
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List

import streamlit as st

from config import settings, get_logger
from core.investigation_assistant import InvestigationAssistant, LLMProvider, SessionContext

logger = get_logger(__name__)

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{settings.app_title} | AI Assistant",
    page_icon="🤖",
    layout="wide",
)

# ─── Styles ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.block-container { padding-top: 1rem !important; max-width: 100% !important; }

/* Chat bubbles */
.chat-user {
    background: #1F3B5E; border: 1px solid #58A6FF40;
    border-radius: 12px 12px 4px 12px; padding: .85rem 1.1rem;
    margin: .4rem 0; max-width: 82%; margin-left: auto;
    color: #E6EDF3; font-size: .9rem; line-height: 1.55;
}
.chat-assistant {
    background: #161B22; border: 1px solid #30363D;
    border-radius: 12px 12px 12px 4px; padding: .85rem 1.1rem;
    margin: .4rem 0; max-width: 88%;
    color: #E6EDF3; font-size: .9rem; line-height: 1.55;
}
.chat-label-user { text-align:right; font-size:.7rem; color:#58A6FF; font-weight:600;
                    text-transform:uppercase; letter-spacing:.5px; margin-bottom:.15rem; }
.chat-label-asst { font-size:.7rem; color:#3FB950; font-weight:600;
                    text-transform:uppercase; letter-spacing:.5px; margin-bottom:.15rem; }

/* Mode badge */
.mode-badge {
    display:inline-flex; align-items:center; gap:.35rem;
    padding:.3rem .85rem; border-radius:20px; font-size:.75rem;
    font-weight:600; letter-spacing:.4px;
}
.mode-llm  { background:rgba(88,166,255,.15); color:#58A6FF; border:1px solid #58A6FF40; }
.mode-det  { background:rgba(63,185,80,.15);  color:#3FB950; border:1px solid #3FB95040; }

/* Quick action buttons */
.stButton > button {
    width:100%; text-align:left !important; padding:.55rem .85rem;
    background:#161B22; border:1px solid #30363D; border-radius:8px;
    color:#C9D1D9; font-size:.82rem; transition:all .15s ease;
}
.stButton > button:hover {
    background:#1F2937; border-color:#58A6FF60; color:#E6EDF3;
    transform:translateX(2px);
}

/* Context panel */
.ctx-box {
    background:#0D1117; border:1px solid #21262D; border-radius:10px;
    padding:.9rem 1.1rem; font-size:.8rem; color:#8B949E;
    font-family:'JetBrains Mono', monospace; line-height:1.6;
    white-space:pre-wrap; max-height:320px; overflow-y:auto;
}

/* Status dot */
.status-ok  { color:#3FB950; font-weight:700; }
.status-na  { color:#8B949E; }
.status-err { color:#F85149; font-weight:700; }

/* Divider */
hr { border-color:#21262D !important; margin:.6rem 0 !important; }

.sec { font-size:.72rem; font-weight:600; color:#8B949E; text-transform:uppercase;
       letter-spacing:.7px; border-bottom:1px solid #21262D;
       padding-bottom:.25rem; margin-bottom:.6rem; }
</style>
""", unsafe_allow_html=True)

# ─── Session state initialisation ─────────────────────────────────────────────
if "ai_chat_history" not in st.session_state:
    st.session_state["ai_chat_history"] = []

if "ai_ctx_built" not in st.session_state:
    st.session_state["ai_ctx_built"] = False

# ─── Build assistant (once per session state hash) ───────────────────────────
@st.cache_resource(show_spinner=False)
def _build_assistant(
    _n_raw: int, _has_ml: bool, _has_sigma: bool, _has_threats: bool
) -> InvestigationAssistant:
    """
    Cache key = inventory of what's loaded.
    Rebuilt automatically when the user runs a new analysis.
    """
    ctx = SessionContext.from_session_state(dict(st.session_state))
    return InvestigationAssistant(ctx)


# Derive cache keys from current session inventory
_lr_pages    = st.session_state.get("lr_pages", {})
_n_raw       = sum(len(getattr(p, "hits", [])) for p in _lr_pages.values())
_has_ml      = "ml_summary" in st.session_state
_has_sigma   = "sigma_report" in st.session_state
_has_threats = "threat_results" in st.session_state

assistant: InvestigationAssistant = _build_assistant(
    _n_raw, _has_ml, _has_sigma, _has_threats
)
ctx: SessionContext = assistant.ctx

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 🤖 AI Assistant")
    st.markdown("<hr>", unsafe_allow_html=True)

    # Mode indicator
    if assistant.is_llm_mode:
        provider_label = f"Gemini ({settings.gemini_model})" if assistant.provider == LLMProvider.GEMINI \
                         else f"OpenAI ({settings.openai_model})"
        st.markdown(
            f'<div class="mode-badge mode-llm">🤖 LLM · {provider_label}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="mode-badge mode-det">🔧 Deterministic Fallback</div>',
            unsafe_allow_html=True,
        )
    st.caption("_Add `GEMINI_API_KEY` or `OPENAI_API_KEY` to `.env` to enable LLM mode._")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="sec">📦 Session Inventory</div>', unsafe_allow_html=True)

    def _dot(ok: bool, label: str, detail: str = "") -> None:
        cls   = "status-ok" if ok else "status-na"
        icon  = "✓" if ok else "○"
        extra = f" <span style='color:#8B949E;font-size:.75rem;'>({detail})</span>" if detail else ""
        st.markdown(f'<span class="{cls}">{icon}</span> {label}{extra}', unsafe_allow_html=True)

    _dot(ctx.has_data,    "Log Batch",    f"{_n_raw:,} logs" if ctx.has_data else "")
    _dot(ctx.has_sigma,   "Sigma Rules",
         f"{ctx.sigma_report.matched_hits} matches" if ctx.has_sigma else "")
    _dot(ctx.has_ml,      "ML Anomaly",
         f"{ctx.ml_summary.get('n_anomalies', 0)} flagged" if ctx.has_ml else "")  # type: ignore[union-attr]
    _dot(ctx.has_threats, "Threat Scores",
         f"{len(ctx.threat_results)} alerts" if ctx.has_threats else "")

    if not ctx.has_data:
        st.info("📥 No data. Run **Log Retrieval** first, then the detection engines.")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="sec">⚡ Quick Actions</div>', unsafe_allow_html=True)

    QUICK = [
        ("📋 Summarize investigation",      "Summarize the current investigation"),
        ("🚨 List critical threats",         "What are the critical threat alerts?"),
        ("📋 Explain Sigma detections",      "Explain the Sigma rule detections"),
        ("🤖 Analyse ML anomalies",          "Analyse the ML anomaly detection results"),
        ("👤 Top suspicious users",          "Who are the most suspicious users?"),
        ("🌐 Top source IPs",               "Show me the top source IPs"),
        ("🎯 MITRE ATT&CK mapping",         "Map the detections to MITRE ATT&CK tactics"),
        ("🔍 Explain top threat",            "Explain why the top threat was flagged"),
        ("💡 What can you help with?",       "Help"),
    ]

    for label, prompt in QUICK:
        if st.button(label, key=f"qa_{label}", use_container_width=True):
            st.session_state["ai_chat_history"].append(
                {"role": "user", "content": prompt}
            )
            with st.spinner("Thinking…"):
                response = assistant.answer(prompt)
            st.session_state["ai_chat_history"].append(
                {"role": "assistant", "content": response}
            )
            st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # Clear + Download
    col_clr, col_dl = st.columns(2)
    with col_clr:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state["ai_chat_history"] = []
            st.rerun()
    with col_dl:
        report_md = assistant.generate_report(st.session_state["ai_chat_history"])
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M")
        st.download_button(
            "⬇️ Report",
            data=report_md,
            file_name=f"soc_investigation_{ts}.md",
            mime="text/markdown",
            use_container_width=True,
        )


# ─── Main area ────────────────────────────────────────────────────────────────
hdr_col, badge_col = st.columns([5, 1])
with hdr_col:
    st.markdown("## 🤖 AI Investigation Assistant")
    st.markdown(
        "<p style='color:#8B949E;margin-top:-.5rem;font-size:.88rem;'>"
        "Conversational SOC analyst — answers questions from the current batch only.</p>",
        unsafe_allow_html=True,
    )
with badge_col:
    if ctx.has_data:
        st.success("✅ Data ready")
    else:
        st.warning("⚠️ No data")

# ─── Context panel (collapsible) ─────────────────────────────────────────────
with st.expander("📊 Session Context Snapshot", expanded=False):
    st.markdown('<div class="ctx-box">' +
                assistant.get_context_summary().replace("\n", "<br>") +
                '</div>', unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ─── Auto-summary on first load ───────────────────────────────────────────────
chat_history: List[Dict[str, str]] = st.session_state["ai_chat_history"]

if not chat_history and ctx.has_data and not st.session_state.get("ai_ctx_built"):
    with st.spinner("Generating initial investigation summary…"):
        summary = assistant.answer("Summarize the current investigation")
    st.session_state["ai_chat_history"].append(
        {"role": "assistant", "content": summary}
    )
    st.session_state["ai_ctx_built"] = True
    st.rerun()

# ─── Render chat history ──────────────────────────────────────────────────────
chat_container = st.container()

with chat_container:
    for msg in chat_history:
        role    = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            st.markdown('<div class="chat-label-user">You</div>', unsafe_allow_html=True)
            with st.chat_message("user"):
                st.write(content)

        elif role == "assistant":
            st.markdown('<div class="chat-label-asst">🤖 Assistant</div>', unsafe_allow_html=True)
            with st.chat_message("assistant"):
                st.markdown(content)

# ─── Empty state ──────────────────────────────────────────────────────────────
if not chat_history:
    st.markdown("""
    <div style="text-align:center; padding:3.5rem 1rem; color:#8B949E;">
      <div style="font-size:3rem; margin-bottom:.75rem;">🔬</div>
      <div style="font-size:1.05rem; font-weight:600; color:#C9D1D9; margin-bottom:.5rem;">
          Ready to Investigate</div>
      <div style="font-size:.9rem; max-width:460px; margin:auto;">
          Load a log batch from <b>📥 Log Retrieval</b>, run the detection engines,
          then ask me anything about the findings — or use the Quick Actions →
      </div>
    </div>
    """, unsafe_allow_html=True)

# ─── Chat input ───────────────────────────────────────────────────────────────
st.markdown("<hr>", unsafe_allow_html=True)

if user_input := st.chat_input(
    "Ask about the investigation… (e.g. 'Who are the top users?')",
    key="ai_user_input",
):
    # Append user message
    st.session_state["ai_chat_history"].append({"role": "user", "content": user_input})

    # Get response
    with st.spinner("Thinking…"):
        response = assistant.answer(user_input)

    # Append assistant message
    st.session_state["ai_chat_history"].append({"role": "assistant", "content": response})
    st.rerun()

# ─── Keyboard shortcut hint ───────────────────────────────────────────────────
if chat_history:
    n_exchanges = len([m for m in chat_history if m["role"] == "user"])
    st.caption(
        f"_{n_exchanges} question(s) asked this session · "
        f"Mode: {'LLM · ' + assistant.provider.value if assistant.is_llm_mode else 'Deterministic'} · "
        f"Batch: {_n_raw:,} logs_"
    )
