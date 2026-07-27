"""
core/log_retriever.py

Scalable, memory-safe log retrieval engine for the ISRO SOC Analytics platform.
Updated to use local Pandas dataframe (data.xlsx) instead of Elasticsearch.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Tuple

import pandas as pd

from config import settings, get_logger
from core.local_data_client import get_local_data_client
from utils.data_utils import DataUtils

logger = get_logger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_PAGE_SIZE: int = 1_000          # Hard cap per page request
MAX_EXPORT_DOCS: int = 50_000       # Hard cap for CSV exports
SORT_TIE_BREAKER: str = "_id"       # Appended to every sort for deterministic search_after


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class LogFilter:
    """
    Encapsulates all user-specified filter criteria for a log retrieval request.
    """
    from_dt: str = ""
    to_dt:   str = ""
    hostname:   str = ""
    username:   str = ""
    source_ip:  str = ""
    dest_ip:    str = ""
    event_id:   str = ""
    severity_levels:  List[str] = field(default_factory=list)
    event_categories: List[str] = field(default_factory=list)
    custom_query_json: str = ""

    time_field:     str = field(default_factory=lambda: settings.es_time_field)
    hostname_field: str = field(default_factory=lambda: settings.es_hostname_field)
    username_field: str = field(default_factory=lambda: settings.es_username_field)
    src_ip_field:   str = field(default_factory=lambda: settings.es_src_ip_field)
    dst_ip_field:   str = field(default_factory=lambda: settings.es_dst_ip_field)
    event_id_field: str = field(default_factory=lambda: settings.es_event_id_field)
    severity_field: str = field(default_factory=lambda: settings.es_severity_field)
    category_field: str = field(default_factory=lambda: settings.es_category_field)

    page_size:       int       = field(default_factory=lambda: settings.retrieval_page_size)
    sort_order:      str       = "desc"
    selected_fields: List[str] = field(default_factory=list)
    use_scroll:      bool      = False

    def cache_key(self) -> str:
        parts = "|".join([
            self.from_dt, self.to_dt, self.hostname, self.username,
            self.source_ip, self.dest_ip, self.event_id,
            ",".join(sorted(self.severity_levels)),
            ",".join(sorted(self.event_categories)),
            self.custom_query_json,
            self.time_field, self.hostname_field, self.username_field,
            self.src_ip_field, self.dst_ip_field, self.event_id_field,
            self.severity_field, self.category_field,
            str(self.page_size), self.sort_order,
            ",".join(sorted(self.selected_fields)),
        ])
        return hashlib.md5(parts.encode()).hexdigest()[:8]

    def active_filter_count(self) -> int:
        count = 0
        for v in [self.hostname, self.username, self.source_ip, self.dest_ip,
                  self.event_id, self.custom_query_json]:
            if v.strip():
                count += 1
        count += len(self.severity_levels)
        count += len(self.event_categories)
        return count

    def has_time_range(self) -> bool:
        return bool(self.from_dt and self.to_dt)

    def summary(self) -> str:
        parts = [f"time: [{self.from_dt} → {self.to_dt}]"]
        if self.hostname:   parts.append(f"hostname={self.hostname}")
        if self.username:   parts.append(f"user={self.username}")
        if self.source_ip:  parts.append(f"src={self.source_ip}")
        if self.dest_ip:    parts.append(f"dst={self.dest_ip}")
        if self.event_id:   parts.append(f"event.id={self.event_id}")
        if self.severity_levels:  parts.append(f"severity={self.severity_levels}")
        if self.event_categories: parts.append(f"category={self.event_categories}")
        if self.custom_query_json: parts.append("custom_dsl=<set>")
        return " | ".join(parts)


@dataclass
class PageResult:
    page_num:     int
    hits:         List[Dict[str, Any]]
    flat_rows:    List[Dict[str, Any]]
    cursor:       Optional[List[Any]]
    total_hits:   int
    elapsed_ms:   float
    has_next:     bool
    query_body:   Dict[str, Any]
    method:       str = "search_after"
    error:        Optional[str] = None


class LogRetriever:
    """
    Stateless log retrieval engine using local pandas dataframe.
    """

    def __init__(self, client: Any = None, index: str = "") -> None:
        self._index = index
        self._client = get_local_data_client()

    def _apply_filters(self, f: LogFilter, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        # Time filter
        if f.from_dt and f.to_dt and "@timestamp" in df.columns:
            from_ts = pd.to_datetime(f.from_dt, utc=True)
            to_ts = pd.to_datetime(f.to_dt, utc=True)
            df = df[(df["@timestamp"] >= from_ts) & (df["@timestamp"] <= to_ts)]
        
        # Dynamic columns handling
        host_col = next((c for c in [f.hostname_field, "host.name", "host.hostname", "agent.hostname", "host"] if c in df.columns), None)
        user_col = next((c for c in [f.username_field, "user.name", "user", "user.id"] if c in df.columns), None)
        src_ip_col = next((c for c in [f.src_ip_field, "source.ip", "client.ip"] if c in df.columns), None)
        dst_ip_col = next((c for c in [f.dst_ip_field, "destination.ip", "server.ip"] if c in df.columns), None)
        sev_col = next((c for c in [f.severity_field, "event.severity", "log.level"] if c in df.columns), None)
        cat_col = next((c for c in [f.category_field, "event.category", "event.dataset"] if c in df.columns), None)
        event_id_col = next((c for c in [f.event_id_field, "event.id", "event.code"] if c in df.columns), None)

        def _like(col, val):
            if not col or col not in df.columns: return pd.Series(True, index=df.index)
            val = val.replace("*", "").replace("?", "")
            return df[col].astype(str).str.contains(val, case=False, na=False)

        if f.hostname: df = df[_like(host_col, f.hostname)]
        if f.username: df = df[_like(user_col, f.username)]
        if f.source_ip: df = df[_like(src_ip_col, f.source_ip)]
        if f.dest_ip: df = df[_like(dst_ip_col, f.dest_ip)]
        if f.event_id: df = df[_like(event_id_col, f.event_id)]
        
        if f.severity_levels and sev_col:
            df = df[df[sev_col].astype(str).str.lower().isin([s.lower() for s in f.severity_levels])]
            
        if f.event_categories and cat_col:
            df = df[df[cat_col].astype(str).str.lower().isin([c.lower() for c in f.event_categories])]
            
        if f.custom_query_json:
            # crude text search
            df = df[df.apply(lambda row: row.astype(str).str.contains(f.custom_query_json, case=False, na=False).any(), axis=1)]

        return df

    def count(self, f: LogFilter) -> Tuple[int, float]:
        t0 = time.monotonic()
        try:
            df = self._client.get_dataframe()
            filtered = self._apply_filters(f, df)
            count = len(filtered)
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            return count, elapsed_ms
        except Exception as exc:
            raise Exception(f"Count failed: {exc}")

    def fetch_page(
        self,
        f: LogFilter,
        cursor: Optional[List[Any]] = None,
        page_num: int = 0,
    ) -> PageResult:
        t0 = time.monotonic()
        try:
            df = self._client.get_dataframe()
            filtered = self._apply_filters(f, df)
            
            if "@timestamp" in filtered.columns:
                asc = "asc" in f.sort_order.lower()
                filtered = filtered.sort_values(by="@timestamp", ascending=asc)

            total_hits = len(filtered)
            page_size = min(f.page_size, MAX_PAGE_SIZE)
            
            # Simple offset pagination since it's local
            start_idx = page_num * page_size
            end_idx = start_idx + page_size
            
            page_df = filtered.iloc[start_idx:end_idx]
            
            if f.selected_fields:
                valid_cols = [c for c in f.selected_fields if c in page_df.columns]
                if valid_cols:
                    page_df = page_df[valid_cols]

            # Convert to dicts
            flat_rows = page_df.to_dict("records")
            hits = [{"_source": row} for row in flat_rows]
            
            has_next = end_idx < total_hits
            next_cursor = [page_num + 1] if has_next else None

            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

            return PageResult(
                page_num=page_num,
                hits=hits,
                flat_rows=flat_rows,
                cursor=next_cursor,
                total_hits=total_hits,
                elapsed_ms=elapsed_ms,
                has_next=has_next,
                query_body={"local_pandas": True},
                method="search_after",
            )
        except Exception as exc:
            return PageResult(
                page_num=page_num, hits=[], flat_rows=[], cursor=None,
                total_hits=0, elapsed_ms=0.0, has_next=False,
                query_body={"local_pandas": True}, error=str(exc),
            )

    def stream_export(
        self,
        f: LogFilter,
        max_docs: Optional[int] = None,
    ) -> Generator[List[Dict[str, Any]], None, None]:
        cap = min(max_docs or settings.retrieval_export_cap, MAX_EXPORT_DOCS)
        df = self._client.get_dataframe()
        filtered = self._apply_filters(f, df)
        
        if "@timestamp" in filtered.columns:
            asc = "asc" in f.sort_order.lower()
            filtered = filtered.sort_values(by="@timestamp", ascending=asc)

        if len(filtered) > cap:
            filtered = filtered.iloc[:cap]

        if f.selected_fields:
            valid_cols = [c for c in f.selected_fields if c in filtered.columns]
            if valid_cols:
                filtered = filtered[valid_cols]

        batch_size = 1000
        for i in range(0, len(filtered), batch_size):
            yield filtered.iloc[i:i+batch_size].to_dict("records")
