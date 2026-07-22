"""
pages/8_📥_Log_Retrieval.py

Intelligent Log Retrieval — ISRO SOC Analytics Platform

Scalable, memory-safe log retrieval with configurable filters, real-time
progress, search_after pagination, and CSV export.

Never attempts to load more than page_size documents per request, regardless
of total dataset size (2.77 billion logs in June 2026).
"""

from __future__ import annotations

import io
import json
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import settings, get_logger
from core import get_es_client
from core.log_retriever import LogFilter, LogRetriever, PageResult, MAX_PAGE_SIZE
from core.elasticsearch_client import ESClientError, ESQueryError
from utils.time_utils import TimeUtils
from utils.data_utils import DataUtils

logger = get_logger(__name__)

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{settings.app_title} | Log Retrieval",
    page_icon="📥",
    layout="wide",
)

# ─── Session State Keys ───────────────────────────────────────────────────────
_SK_FILTER_KEY  = "lr_filter_key"      # Current filter cache key (for invalidation)
_SK_TOTAL_HITS  = "lr_total_hits"      # int
_SK_COUNT_MS    = "lr_count_ms"        # float
_SK_PAGES       = "lr_pages"           # Dict[int, PageResult]
_SK_CURSORS     = "lr_cursors"         # Dict[int, Optional[List]]
_SK_CUR_PAGE    = "lr_current_page"    # int (0-indexed)
_SK_COLUMNS     = "lr_selected_cols"   # List[str]
_SK_EXPORT_DF   = "lr_export_df"       # Optional[pd.DataFrame]

MAX_CACHED_PAGES = 20   # Drop oldest beyond this to save memory

# ─── Styles ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.block-container { padding-top: 1.25rem !important; }

/* ── Results bar ── */
.results-bar {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 10px;
    padding: 0.75rem 1.25rem;
    display: flex;
    gap: 2rem;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 0.75rem;
}
.rb-item { display: flex; flex-direction: column; }
.rb-label { font-size: 0.7rem; color: #8B949E; text-transform: uppercase; letter-spacing: 0.5px; }
.rb-value { font-size: 1.05rem; font-weight: 700; color: #E6EDF3; }
.rb-accent { color: #58A6FF; }
.rb-warn   { color: #D29922; }
.rb-ok     { color: #3FB950; }

/* ── Filter pill ── */
.filter-pill {
    display: inline-block;
    background: rgba(88,166,255,0.12);
    border: 1px solid rgba(88,166,255,0.25);
    color: #79C0FF;
    font-size: 0.75rem;
    padding: 2px 8px;
    border-radius: 12px;
    margin: 2px;
}

/* ── Section heading ── */
.section-heading {
    font-size: 0.8rem;
    font-weight: 600;
    color: #8B949E;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 0.4rem;
    padding-bottom: 0.2rem;
    border-bottom: 1px solid #30363D;
}

/* ── Code pill ── */
.code-pill {
    display: inline-block;
    background: rgba(188,140,255,0.1);
    border: 1px solid rgba(188,140,255,0.2);
    color: #BC8CFF;
    font-family: monospace;
    font-size: 0.78rem;
    padding: 1px 7px;
    border-radius: 4px;
}

/* ── Metric card ── */
[data-testid="metric-container"] {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 12px;
    padding: 0.9rem;
}

/* ── Pagination button row ── */
.pag-row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
    margin: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)


# ─── Utilities ────────────────────────────────────────────────────────────────

def _init_session() -> None:
    """Initialise session state keys if absent."""
    defaults: Dict[str, Any] = {
        _SK_FILTER_KEY: "",
        _SK_TOTAL_HITS: None,
        _SK_COUNT_MS:   None,
        _SK_PAGES:      {},
        _SK_CURSORS:    {0: None},
        _SK_CUR_PAGE:   0,
        _SK_COLUMNS:    [],
        _SK_EXPORT_DF:  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _invalidate_if_changed(new_key: str) -> None:
    """Clear cached pages if filter has changed."""
    if new_key != st.session_state[_SK_FILTER_KEY]:
        st.session_state[_SK_FILTER_KEY] = new_key
        st.session_state[_SK_PAGES]      = {}
        st.session_state[_SK_CURSORS]    = {0: None}
        st.session_state[_SK_CUR_PAGE]   = 0
        st.session_state[_SK_TOTAL_HITS] = None
        st.session_state[_SK_COUNT_MS]   = None
        st.session_state[_SK_COLUMNS]    = []
        st.session_state[_SK_EXPORT_DF]  = None


def _cache_page(result: PageResult) -> None:
    """Store a PageResult in session state, evicting oldest if over limit."""
    pages = st.session_state[_SK_PAGES]
    cur = st.session_state[_SK_CUR_PAGE]

    # Evict distant pages if at memory limit
    if len(pages) >= MAX_CACHED_PAGES:
        candidates = sorted(k for k in pages if abs(k - cur) > 3)
        if candidates:
            del pages[candidates[0]]

    pages[result.page_num] = result

    # Store cursor for the NEXT page
    if result.cursor and not result.error:
        st.session_state[_SK_CURSORS][result.page_num + 1] = result.cursor


def _get_retriever(index: str) -> Optional[LogRetriever]:
    try:
        return LogRetriever(get_es_client(), index)
    except Exception as exc:
        st.error(f"❌ Cannot create retriever: {exc}")
        return None


# ─── Init ─────────────────────────────────────────────────────────────────────
_init_session()

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 📥 Intelligent Log Retrieval")
st.markdown(
    "<p style='color:#8B949E;margin-top:-0.5rem;'>"
    "Memory-safe, paginated retrieval from 2.77 billion logs using configurable filters. "
    "Data is never fully loaded — only <b style='color:#58A6FF'>one page at a time</b>.</p>",
    unsafe_allow_html=True,
)

# ─── Sidebar — Retrieval Options ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Retrieval Options")
    target_index = st.text_input("Index pattern", value=settings.es_index_pattern)
    page_size    = st.slider("Page size (docs)", 10, MAX_PAGE_SIZE, settings.retrieval_page_size, step=10)
    sort_order   = st.radio("Sort order", ["desc ↓ newest first", "asc ↑ oldest first"], index=0)
    use_scroll   = st.checkbox("Use Scroll API (fallback)", value=False,
                               help="Use only if search_after gives inconsistent results.")
    st.markdown("<hr style='border-color:#30363D;margin:0.5rem 0;'>", unsafe_allow_html=True)

    with st.expander("🗂️ Field Name Overrides"):
        f_time     = st.text_input("Timestamp field",   value=settings.es_time_field)
        f_hostname = st.text_input("Hostname field",    value=settings.es_hostname_field)
        f_username = st.text_input("Username field",    value=settings.es_username_field)
        f_src_ip   = st.text_input("Source IP field",  value=settings.es_src_ip_field)
        f_dst_ip   = st.text_input("Dest IP field",    value=settings.es_dst_ip_field)
        f_event_id = st.text_input("Event ID field",   value=settings.es_event_id_field)
        f_severity = st.text_input("Severity field",   value=settings.es_severity_field)
        f_category = st.text_input("Category field",   value=settings.es_category_field)

# ─── Filter Panel ─────────────────────────────────────────────────────────────
with st.form("log_filter_form", clear_on_submit=False):
    st.markdown('<div class="section-heading">🔍 Filter Configuration</div>', unsafe_allow_html=True)

    # Row 1 — Time range
    tr_col1, tr_col2 = st.columns(2)
    with tr_col1:
        now_range = TimeUtils.get_preset_range("Last 24 Hours")
        from_date = st.date_input("From date", value=now_range[0].date() if now_range else None)
        from_time = st.time_input("From time", value=now_range[0].time() if now_range else None)
    with tr_col2:
        to_date = st.date_input("To date", value=now_range[1].date() if now_range else None)
        to_time = st.time_input("To time", value=now_range[1].time() if now_range else None)

    # Quick presets
    preset_opts = TimeUtils.list_presets()
    chosen_preset = st.selectbox("Or use a preset time range", ["Custom"] + preset_opts, index=0)

    st.markdown("<hr style='border-color:#30363D;margin:0.5rem 0;'>", unsafe_allow_html=True)

    # Row 2 — Field filters
    st.markdown('<div class="section-heading">🏷️ Field Filters</div>', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        inp_hostname  = st.text_input("Hostname", placeholder="e.g. server01 or server* (wildcard)")
        inp_source_ip = st.text_input("Source IP", placeholder="e.g. 192.168.1.5 or 10.0.0.0/8")
    with fc2:
        inp_username  = st.text_input("Username", placeholder="e.g. admin or admin*")
        inp_dest_ip   = st.text_input("Destination IP", placeholder="e.g. 10.0.0.1")
    with fc3:
        inp_event_id  = st.text_input("Event ID", placeholder="e.g. 4625 or 4624")

    st.markdown("<hr style='border-color:#30363D;margin:0.5rem 0;'>", unsafe_allow_html=True)

    # Row 3 — Multi-value filters
    st.markdown('<div class="section-heading">🏷️ Multi-value Filters</div>', unsafe_allow_html=True)
    mv1, mv2 = st.columns(2)
    with mv1:
        inp_severity = st.multiselect(
            "Severity levels",
            options=["critical", "high", "medium", "low", "info", "unknown",
                     "0", "1", "2", "3", "4", "5", "6", "7",
                     "emergency", "alert", "error", "warning", "notice", "debug"],
            help="Leave empty to match all severity levels",
        )
    with mv2:
        inp_categories = st.multiselect(
            "Event categories",
            options=["authentication", "authorization", "network", "process",
                     "file", "registry", "malware", "intrusion_detection",
                     "configuration", "driver", "web", "email", "database",
                     "threat", "vulnerability"],
            help="Leave empty to match all categories",
        )

    # Advanced: Custom DSL
    with st.expander("⚗️ Custom Elasticsearch Query (overrides field filters above)"):
        st.caption("Enter a valid JSON ES ``query`` object. Time range is still applied on top.")
        inp_custom_dsl = st.text_area(
            "Custom query JSON",
            placeholder='{"match": {"event.outcome": "failure"}}',
            height=100,
        )

    # Advanced: Field selection
    with st.expander("📋 Select Output Fields (leave empty = all fields)"):
        inp_fields = st.text_area(
            "Field list (one per line)",
            placeholder="@timestamp\nhost.name\nuser.name\nsource.ip",
            height=100,
        )

    # Submission buttons
    st.markdown("")
    btn_col1, btn_col2, btn_col3, _ = st.columns([1, 1, 1, 3])
    with btn_col1:
        submitted_search = st.form_submit_button("▶ Search", type="primary", use_container_width=True)
    with btn_col2:
        submitted_count  = st.form_submit_button("🔢 Count Only", use_container_width=True)
    with btn_col3:
        submitted_clear  = st.form_submit_button("🗑️ Clear", use_container_width=True)

# ─── Build LogFilter from form inputs ─────────────────────────────────────────
def _build_filter() -> LogFilter:
    # Resolve time range
    if chosen_preset and chosen_preset != "Custom":
        preset_range = TimeUtils.get_preset_range(chosen_preset)
        from_iso = TimeUtils.to_iso(preset_range[0]) if preset_range else ""
        to_iso   = TimeUtils.to_iso(preset_range[1]) if preset_range else ""
    else:
        try:
            from_dt_combined = f"{from_date}T{from_time}"
            to_dt_combined   = f"{to_date}T{to_time}"
            from_iso = TimeUtils.to_iso(TimeUtils.parse_any(from_dt_combined))
            to_iso   = TimeUtils.to_iso(TimeUtils.parse_any(to_dt_combined))
        except Exception:
            from_iso = "now-24h"
            to_iso   = "now"

    selected = [f.strip() for f in inp_fields.splitlines() if f.strip()] if inp_fields else []
    sort_dir = "desc" if "desc" in sort_order else "asc"

    return LogFilter(
        from_dt=from_iso, to_dt=to_iso,
        hostname=inp_hostname.strip(),
        username=inp_username.strip(),
        source_ip=inp_source_ip.strip(),
        dest_ip=inp_dest_ip.strip(),
        event_id=inp_event_id.strip(),
        severity_levels=list(inp_severity),
        event_categories=list(inp_categories),
        custom_query_json=inp_custom_dsl.strip(),
        time_field=f_time, hostname_field=f_hostname,
        username_field=f_username, src_ip_field=f_src_ip,
        dst_ip_field=f_dst_ip, event_id_field=f_event_id,
        severity_field=f_severity, category_field=f_category,
        page_size=page_size,
        sort_order=sort_dir,
        selected_fields=selected,
        use_scroll=use_scroll,
    )


current_filter = _build_filter()

# Invalidate cache when filter changes
_invalidate_if_changed(current_filter.cache_key())

# Handle clear
if submitted_clear:
    for k in [_SK_FILTER_KEY, _SK_TOTAL_HITS, _SK_COUNT_MS, _SK_PAGES,
              _SK_CURSORS, _SK_CUR_PAGE, _SK_COLUMNS, _SK_EXPORT_DF]:
        st.session_state.pop(k, None)
    _init_session()
    st.rerun()

# ─── Active filter summary ────────────────────────────────────────────────────
n_active = current_filter.active_filter_count()
if n_active > 0:
    pills_html = ""
    if current_filter.hostname:  pills_html += f'<span class="filter-pill">🖥 {current_filter.hostname}</span>'
    if current_filter.username:  pills_html += f'<span class="filter-pill">👤 {current_filter.username}</span>'
    if current_filter.source_ip: pills_html += f'<span class="filter-pill">⬆ {current_filter.source_ip}</span>'
    if current_filter.dest_ip:   pills_html += f'<span class="filter-pill">⬇ {current_filter.dest_ip}</span>'
    if current_filter.event_id:  pills_html += f'<span class="filter-pill">🆔 {current_filter.event_id}</span>'
    for s in current_filter.severity_levels:
        pills_html += f'<span class="filter-pill">⚠ {s}</span>'
    for c in current_filter.event_categories:
        pills_html += f'<span class="filter-pill">📂 {c}</span>'
    if current_filter.custom_query_json:
        pills_html += '<span class="filter-pill">⚗ custom DSL</span>'
    st.markdown(f"<div style='margin:0.25rem 0 0.5rem;'>{pills_html}</div>", unsafe_allow_html=True)

# ─── Count query ──────────────────────────────────────────────────────────────
if submitted_count or (submitted_search and st.session_state.get(_SK_TOTAL_HITS) is None):
    if not current_filter.has_time_range():
        st.warning("⚠️ Please specify a time range before running a query.")
    else:
        retriever = _get_retriever(target_index)
        if retriever:
            with st.spinner("Counting matching documents..."):
                try:
                    total, elapsed = retriever.count(current_filter)
                    st.session_state[_SK_TOTAL_HITS] = total
                    st.session_state[_SK_COUNT_MS]   = elapsed
                except Exception as exc:
                    st.error(f"❌ Count failed: {exc}")

# ─── Search (fetch first page) ────────────────────────────────────────────────
if submitted_search and current_filter.has_time_range():
    retriever = _get_retriever(target_index)
    if retriever:
        # Fetch page 0
        st.session_state[_SK_CUR_PAGE] = 0
        cursor = st.session_state[_SK_CURSORS].get(0)

        with st.spinner("Fetching first page..."):
            try:
                result = retriever.fetch_page(current_filter, cursor=cursor, page_num=0)
                _cache_page(result)

                # Populate count from total_hits if not already set
                if st.session_state[_SK_TOTAL_HITS] is None:
                    st.session_state[_SK_TOTAL_HITS] = result.total_hits
                    st.session_state[_SK_COUNT_MS]   = result.elapsed_ms

                # Auto-set columns from first page data
                if result.flat_rows and not st.session_state[_SK_COLUMNS]:
                    all_cols = list(result.flat_rows[0].keys())
                    st.session_state[_SK_COLUMNS] = all_cols[:30]  # Default: first 30 cols

                if result.error:
                    st.error(f"❌ {result.error}")
            except Exception as exc:
                st.error(f"❌ Retrieval failed: {exc}")

elif submitted_search and not current_filter.has_time_range():
    st.warning("⚠️ Please specify a time range before searching.")

# ─── Results Area ─────────────────────────────────────────────────────────────
total_hits = st.session_state.get(_SK_TOTAL_HITS)
count_ms   = st.session_state.get(_SK_COUNT_MS)
cur_page   = st.session_state.get(_SK_CUR_PAGE, 0)
pages_dict = st.session_state.get(_SK_PAGES, {})

if total_hits is not None:
    # ── Results metrics bar ───────────────────────────────────────────────────
    total_pages_est = max(1, (total_hits + page_size - 1) // page_size)
    cur_result: Optional[PageResult] = pages_dict.get(cur_page)

    docs_on_page = len(cur_result.flat_rows) if cur_result else 0
    st.markdown(
        f"""<div class="results-bar">
            <div class="rb-item">
                <span class="rb-label">Total Matches</span>
                <span class="rb-value rb-accent">{total_hits:,}</span>
            </div>
            <div class="rb-item">
                <span class="rb-label">Count Time</span>
                <span class="rb-value">{count_ms:.0f} ms</span>
            </div>
            <div class="rb-item">
                <span class="rb-label">Current Page</span>
                <span class="rb-value">{cur_page + 1}</span>
            </div>
            <div class="rb-item">
                <span class="rb-label">Docs on Page</span>
                <span class="rb-value">{docs_on_page}</span>
            </div>
            {"<div class='rb-item'><span class='rb-label'>Page Latency</span>"
             f"<span class='rb-value'>{cur_result.elapsed_ms:.0f} ms</span></div>"
             if cur_result else ""}
            <div class="rb-item">
                <span class="rb-label">Cached Pages</span>
                <span class="rb-value rb-ok">{len(pages_dict)}</span>
            </div>
            <div class="rb-item">
                <span class="rb-label">Active Filters</span>
                <span class="rb-value rb-warn">{n_active}</span>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Pagination controls ───────────────────────────────────────────────────
    st.markdown('<div class="section-heading">📄 Pagination</div>', unsafe_allow_html=True)
    pag1, pag2, pag3, pag4, _ = st.columns([1, 1, 2, 2, 4])

    with pag1:
        prev_disabled = cur_page == 0
        if st.button("◀ Prev", disabled=prev_disabled, use_container_width=True):
            st.session_state[_SK_CUR_PAGE] = max(0, cur_page - 1)
            st.rerun()

    with pag2:
        # Check if next page cursor is available
        has_next = bool(
            (cur_result and cur_result.has_next) or
            (cur_page + 1 in st.session_state[_SK_CURSORS])
        )
        if st.button("Next ▶", disabled=not has_next, use_container_width=True):
            next_p = cur_page + 1

            # Fetch next page if not cached
            if next_p not in pages_dict:
                retriever = _get_retriever(target_index)
                if retriever:
                    next_cursor = st.session_state[_SK_CURSORS].get(next_p)
                    with st.spinner(f"Loading page {next_p + 1}..."):
                        try:
                            result = retriever.fetch_page(current_filter, cursor=next_cursor, page_num=next_p)
                            _cache_page(result)
                        except Exception as exc:
                            st.error(f"❌ {exc}")

            st.session_state[_SK_CUR_PAGE] = next_p
            st.rerun()

    with pag3:
        cached_pages = sorted(pages_dict.keys())
        if cached_pages:
            go_to_page = st.selectbox(
                "Go to page",
                options=[p + 1 for p in cached_pages],
                index=cached_pages.index(cur_page) if cur_page in cached_pages else 0,
                label_visibility="collapsed",
            )
            if go_to_page - 1 != cur_page:
                st.session_state[_SK_CUR_PAGE] = go_to_page - 1
                st.rerun()

    with pag4:
        st.markdown(
            f"<span style='font-size:0.82rem;color:#8B949E;'>"
            f"Page {cur_page + 1} · Est. {total_pages_est:,} total pages · "
            f"Method: <span class='code-pill'>{'scroll' if use_scroll else 'search_after'}</span>"
            f"</span>",
            unsafe_allow_html=True,
        )

    # ── Data table ────────────────────────────────────────────────────────────
    if cur_result and cur_result.flat_rows and not cur_result.error:
        st.markdown('<div class="section-heading">📊 Results — Page ' + str(cur_page + 1) + '</div>',
                    unsafe_allow_html=True)

        all_cols = list(cur_result.flat_rows[0].keys())

        with st.expander("🎛️ Column Selector", expanded=False):
            selected_cols = st.multiselect(
                "Displayed columns",
                options=all_cols,
                default=st.session_state[_SK_COLUMNS] or all_cols[:20],
                key=f"col_sel_{cur_page}",
            )
            if selected_cols:
                st.session_state[_SK_COLUMNS] = selected_cols
        
        display_cols = st.session_state[_SK_COLUMNS] if st.session_state[_SK_COLUMNS] else all_cols[:20]
        # Ensure all display_cols exist in data
        display_cols = [c for c in display_cols if c in all_cols]
        if not display_cols:
            display_cols = all_cols[:20]

        df = pd.DataFrame(cur_result.flat_rows)[display_cols]
        st.dataframe(df, use_container_width=True, height=420, hide_index=True)

        # Page-level quick download
        csv_page = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            f"⬇ Download Page {cur_page + 1} CSV ({docs_on_page} rows)",
            data=csv_page,
            file_name=f"logs_page_{cur_page + 1}.csv",
            mime="text/csv",
        )

    elif cur_result and cur_result.error:
        st.error(f"❌ Page error: {cur_result.error}")
    elif not cur_result and pages_dict:
        st.info("Click **▶ Search** or navigate pages to load data.")

    # ── Bulk export ───────────────────────────────────────────────────────────
    st.markdown("<hr style='border-color:#30363D;margin:1rem 0;'>", unsafe_allow_html=True)
    st.markdown('<div class="section-heading">⬇ Bulk Export</div>', unsafe_allow_html=True)

    export_cap = min(total_hits, settings.retrieval_export_cap)
    exp_c1, exp_c2 = st.columns([2, 3])
    with exp_c1:
        export_limit = st.number_input(
            f"Max docs to export (cap: {settings.retrieval_export_cap:,})",
            min_value=1,
            max_value=export_cap,
            value=min(export_cap, 5_000),
            step=1_000,
        )

    with exp_c2:
        if st.button("🔄 Stream & Export CSV", type="secondary"):
            retriever = _get_retriever(target_index)
            if retriever:
                export_filter = current_filter
                progress_bar = st.progress(0.0, text="Starting export...")
                status_msg   = st.empty()
                all_rows: List[Dict[str, Any]] = []
                retrieved = 0

                t0_export = time.monotonic()
                for batch in retriever.stream_export(export_filter, max_docs=int(export_limit)):
                    all_rows.extend(batch)
                    retrieved += len(batch)
                    pct = min(retrieved / export_limit, 1.0)
                    progress_bar.progress(pct, text=f"Streaming: {retrieved:,} / {export_limit:,} docs...")
                    status_msg.markdown(
                        f"<span style='font-size:0.8rem;color:#8B949E;'>"
                        f"Elapsed: {(time.monotonic() - t0_export):.1f}s</span>",
                        unsafe_allow_html=True,
                    )

                progress_bar.progress(1.0, text="✅ Stream complete!")
                export_df = pd.DataFrame(all_rows)
                st.session_state[_SK_EXPORT_DF] = export_df
                logger.info("Export complete: %d rows", len(all_rows))

    # Show download button if export data is ready
    if st.session_state.get(_SK_EXPORT_DF) is not None:
        exp_df = st.session_state[_SK_EXPORT_DF]
        csv_full = exp_df.to_csv(index=False).encode("utf-8")
        st.success(f"✅ Export ready: **{len(exp_df):,} rows**, {len(csv_full) / 1024:.0f} KB")
        st.download_button(
            "📥 Download Full Export CSV",
            data=csv_full,
            file_name="isro_soc_export.csv",
            mime="text/csv",
        )
        if st.button("🗑️ Clear Export"):
            st.session_state[_SK_EXPORT_DF] = None
            st.rerun()

    # ── Generated Query DSL ───────────────────────────────────────────────────
    st.markdown("<hr style='border-color:#30363D;margin:1rem 0;'>", unsafe_allow_html=True)
    if cur_result:
        with st.expander("🛠️ Generated Elasticsearch Query DSL", expanded=False):
            st.caption("The exact query body sent to Elasticsearch for this page.")
            st.code(
                json.dumps(cur_result.query_body, indent=2, default=str),
                language="json",
            )
    else:
        # Show a preview of what the query would look like
        try:
            retriever_preview = _get_retriever(target_index)
            if retriever_preview:
                preview_body = retriever_preview.build_query(current_filter, cursor=None)
                with st.expander("🛠️ Query Preview (not yet executed)", expanded=False):
                    st.code(json.dumps(preview_body, indent=2, default=str), language="json")
        except Exception:
            pass

else:
    # ── Welcome state (no results yet) ───────────────────────────────────────
    st.markdown("")
    st.markdown(
        """<div style="background:#161B22;border:1px dashed #30363D;border-radius:12px;
        padding:2rem;text-align:center;margin-top:0.5rem;">
        <div style="font-size:2.5rem;margin-bottom:0.5rem;">🔍</div>
        <div style="font-weight:600;font-size:1rem;color:#E6EDF3;margin-bottom:0.5rem;">
            Configure filters and click ▶ Search
        </div>
        <div style="color:#8B949E;font-size:0.85rem;max-width:500px;margin:0 auto;">
            Set a time range and any optional field filters above, then click
            <b>▶ Search</b> to retrieve the first page, or
            <b>🔢 Count Only</b> to see how many documents match
            without loading any data.
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Show query preview in the empty state too
    try:
        retriever_preview = _get_retriever(target_index)
        if retriever_preview and current_filter.has_time_range():
            preview_body = retriever_preview.build_query(current_filter, cursor=None)
            with st.expander("🛠️ Query Preview", expanded=False):
                st.code(json.dumps(preview_body, indent=2, default=str), language="json")
    except Exception:
        pass

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("<hr style='border-color:#30363D;margin-top:2rem;'>", unsafe_allow_html=True)
st.caption(
    f"Log Retrieval · Index: `{target_index}` · "
    f"Max safe size: {MAX_PAGE_SIZE:,} · "
    f"Export cap: {settings.retrieval_export_cap:,}"
)
