"""
core/log_retriever.py

Scalable, memory-safe log retrieval engine for the ISRO SOC Analytics platform.

Design:
  - LogFilter dataclass encapsulates all user-specified filter criteria
  - LogRetriever.build_query() converts filters → safe ES DSL
  - search_after is the default pagination strategy (preferred over scroll)
    because it is stateless, more stable, and works on 2.77B-doc datasets
  - Scroll API is available as a fallback for compatibility
  - Hard limits prevent memory exhaustion:
      page_size   ≤ MAX_PAGE_SIZE  (hard cap)
      max_docs    ≤ RETRIEVAL_MAX_DOCS (configurable, default 10 000)
      export_cap  ≤ RETRIEVAL_EXPORT_CAP (configurable, default 50 000)
  - Page results are cached in the caller's session state by this module's
    helpers; LogRetriever itself is stateless per-call

Public surface:
    LogFilter       — filter configuration dataclass
    PageResult      — single-page result dataclass
    LogRetriever    — query builder + page fetcher + export streamer
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Tuple

from config import settings, get_logger
from core.elasticsearch_client import (
    ElasticsearchClient,
    ESClientError,
    ESSafetyError,
    ESQueryError,
    MAX_SAFE_SIZE,
)
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

    All string filter fields default to "" (not applied) — the retriever
    ignores empty-string filters when building the query.
    """

    # ── Time range (required for every query) ─────────────────────────────
    from_dt: str = ""      # ISO-8601 / ES date-math e.g. "now-1h"
    to_dt:   str = ""      # ISO-8601 / ES date-math e.g. "now"

    # ── Exact-match / term filters ────────────────────────────────────────
    hostname:   str = ""   # Maps to es_hostname_field
    username:   str = ""   # Maps to es_username_field
    source_ip:  str = ""   # Supports CIDR e.g. "192.168.1.0/24" and wildcard "*"
    dest_ip:    str = ""   # Same as source_ip
    event_id:   str = ""   # Maps to es_event_id_field

    # ── Multi-value filters (terms queries) ───────────────────────────────
    severity_levels:  List[str] = field(default_factory=list)
    event_categories: List[str] = field(default_factory=list)

    # ── Custom DSL (overrides all above field filters if non-empty) ───────
    # Must be a valid JSON string containing an ES ``query`` dict.
    # The time range filter is still applied on top.
    custom_query_json: str = ""

    # ── Field name overrides (defaults pulled from settings) ──────────────
    time_field:     str = field(default_factory=lambda: settings.es_time_field)
    hostname_field: str = field(default_factory=lambda: settings.es_hostname_field)
    username_field: str = field(default_factory=lambda: settings.es_username_field)
    src_ip_field:   str = field(default_factory=lambda: settings.es_src_ip_field)
    dst_ip_field:   str = field(default_factory=lambda: settings.es_dst_ip_field)
    event_id_field: str = field(default_factory=lambda: settings.es_event_id_field)
    severity_field: str = field(default_factory=lambda: settings.es_severity_field)
    category_field: str = field(default_factory=lambda: settings.es_category_field)

    # ── Retrieval settings ────────────────────────────────────────────────
    page_size:       int       = field(default_factory=lambda: settings.retrieval_page_size)
    sort_order:      str       = "desc"
    selected_fields: List[str] = field(default_factory=list)   # empty = all fields
    use_scroll:      bool      = False    # True → Scroll API fallback

    # ─────────────────────────────────────────────────────────────────────

    def cache_key(self) -> str:
        """
        Return an 8-char hex digest uniquely identifying this filter config.
        Used to invalidate cached pages when the filter changes.
        """
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
        """Return number of non-empty filter fields (excluding time range)."""
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
        """Return a one-line human-readable summary of active filters."""
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
    """
    Holds the result of a single search_after / scroll page.
    """
    page_num:     int
    hits:         List[Dict[str, Any]]          # List of raw ES hit dicts
    flat_rows:    List[Dict[str, Any]]          # Flattened _source rows (for tables)
    cursor:       Optional[List[Any]]           # search_after cursor for next page
    total_hits:   int                           # ES total.value
    elapsed_ms:   float                         # Wall-clock time for this page
    has_next:     bool
    query_body:   Dict[str, Any]               # The exact DSL body sent
    method:       str = "search_after"          # "search_after" | "scroll"
    error:        Optional[str] = None


# ─── LogRetriever ─────────────────────────────────────────────────────────────

class LogRetriever:
    """
    Stateless log retrieval engine.

    All methods accept a LogFilter and an ElasticsearchClient, returning
    structured results without storing any state internally.
    """

    def __init__(self, client: ElasticsearchClient, index: str) -> None:
        self._client = client
        self._index = index

    # ──────────────────────────────────────────────────────────────────────────
    # Query Building
    # ──────────────────────────────────────────────────────────────────────────

    def build_query(
        self,
        f: LogFilter,
        cursor: Optional[List[Any]] = None,
        size_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Build a complete ES search body from a LogFilter.

        Args:
            f:             Filter configuration.
            cursor:        search_after cursor values (None for first page).
            size_override: Override page_size (e.g. for count-only = 0).

        Returns:
            A dict suitable for passing to ElasticsearchClient.search().
        """
        size = min(size_override if size_override is not None else f.page_size, MAX_PAGE_SIZE)

        # ── Build query clause ────────────────────────────────────────────────
        if f.custom_query_json.strip():
            # User-supplied DSL — wrap in bool must so we can still apply time range
            try:
                user_q = json.loads(f.custom_query_json)
            except json.JSONDecodeError as exc:
                raise ESQueryError(f"Invalid custom query JSON: {exc}") from exc
            base_query: Dict[str, Any] = {
                "bool": {
                    "must": [user_q],
                    "filter": self._time_range_clause(f),
                }
            }
        else:
            # Structured filter query
            filters = self._time_range_clause(f)
            filters.extend(self._term_filters(f))
            base_query = {"bool": {"filter": filters}} if filters else {"match_all": {}}

        # ── Assemble body ─────────────────────────────────────────────────────
        body: Dict[str, Any] = {
            "size": size,
            "sort": [
                {f.time_field: {"order": f.sort_order}},
                {SORT_TIE_BREAKER: {"order": "asc"}},   # deterministic tie-breaker
            ],
            "query": base_query,
            "track_total_hits": True,
        }

        # Field projection
        if f.selected_fields:
            body["_source"] = f.selected_fields

        # search_after cursor
        if cursor:
            body["search_after"] = cursor

        return body

    def _time_range_clause(self, f: LogFilter) -> List[Dict[str, Any]]:
        """Return a list with the time-range filter (may be empty if no dates set)."""
        if not f.from_dt or not f.to_dt:
            return []
        return [{"range": {f.time_field: {"gte": f.from_dt, "lte": f.to_dt}}}]

    def _term_filters(self, f: LogFilter) -> List[Dict[str, Any]]:
        """Return a list of term/terms/wildcard filters from the LogFilter."""
        clauses: List[Dict[str, Any]] = []

        # Exact-match fields
        if f.hostname:  clauses.append(_exact_or_wildcard(f.hostname_field, f.hostname))
        if f.username:  clauses.append(_exact_or_wildcard(f.username_field, f.username))
        if f.event_id:  clauses.append(_exact_or_wildcard(f.event_id_field, f.event_id))

        # IP fields (support CIDR / prefix wildcard)
        if f.source_ip: clauses.append(_ip_filter(f.src_ip_field, f.source_ip))
        if f.dest_ip:   clauses.append(_ip_filter(f.dst_ip_field, f.dest_ip))

        # Multi-value
        if f.severity_levels:  clauses.append({"terms": {f.severity_field: f.severity_levels}})
        if f.event_categories: clauses.append({"terms": {f.category_field: f.event_categories}})

        return clauses

    # ──────────────────────────────────────────────────────────────────────────
    # Count
    # ──────────────────────────────────────────────────────────────────────────

    def count(self, f: LogFilter) -> Tuple[int, float]:
        """
        Run a count query and return (total_hits, elapsed_ms).

        Uses size=0 aggregation to avoid loading any hits.
        Fast even on 2.77B-doc indices.
        """
        body = self.build_query(f, size_override=0)
        # Remove sort (not needed for count-only)
        body.pop("sort", None)
        body.pop("search_after", None)

        t0 = time.monotonic()
        try:
            resp = self._client.search(
                index=self._index,
                body=body,
                enforce_size_limit=False,  # size=0 is always safe
                track_total_hits=True,
            )
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            total = resp.get("hits", {}).get("total", {})
            if isinstance(total, dict):
                count = total.get("value", 0)
            else:
                count = int(total)
            logger.info("Count query: %d matches in %.1f ms | %s", count, elapsed_ms, f.summary())
            return count, elapsed_ms
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            logger.error("Count query failed: %s", exc)
            raise ESClientError(f"Count failed: {exc}") from exc

    # ──────────────────────────────────────────────────────────────────────────
    # Page Fetch (search_after preferred)
    # ──────────────────────────────────────────────────────────────────────────

    def fetch_page(
        self,
        f: LogFilter,
        cursor: Optional[List[Any]] = None,
        page_num: int = 0,
    ) -> PageResult:
        """
        Fetch a single page of results using search_after (or scroll fallback).

        Args:
            f:        Filter configuration.
            cursor:   search_after cursor from the previous page (None = first page).
            page_num: Current page index (0-based), used only for the PageResult.

        Returns:
            PageResult with hits, flat_rows, cursor for next page, and metadata.
        """
        if f.use_scroll:
            return self._fetch_page_scroll(f, page_num)

        query_body = self.build_query(f, cursor=cursor)
        t0 = time.monotonic()

        try:
            resp = self._client.search(
                index=self._index,
                body=query_body,
                enforce_size_limit=False,  # page_size is already bounded
                track_total_hits=True,
            )
        except Exception as exc:
            return PageResult(
                page_num=page_num, hits=[], flat_rows=[], cursor=None,
                total_hits=0, elapsed_ms=0.0, has_next=False,
                query_body=query_body, error=str(exc),
            )

        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        hits = resp.get("hits", {}).get("hits", [])
        total_obj = resp.get("hits", {}).get("total", {})
        total_hits = total_obj.get("value", 0) if isinstance(total_obj, dict) else int(total_obj)

        next_cursor: Optional[List[Any]] = None
        if hits:
            next_cursor = hits[-1].get("sort")

        flat_rows = [DataUtils.flatten_dict(h.get("_source", {})) for h in hits]
        has_next = bool(next_cursor) and len(hits) == f.page_size

        logger.info(
            "Page %d: %d hits, total=%d, latency=%.1fms",
            page_num, len(hits), total_hits, elapsed_ms,
        )

        return PageResult(
            page_num=page_num,
            hits=hits,
            flat_rows=flat_rows,
            cursor=next_cursor,
            total_hits=total_hits,
            elapsed_ms=elapsed_ms,
            has_next=has_next,
            query_body=query_body,
            method="search_after",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Scroll fallback (stateful — returns only one page at a time)
    # ──────────────────────────────────────────────────────────────────────────

    def _fetch_page_scroll(self, f: LogFilter, page_num: int) -> PageResult:
        """
        Scroll-API fallback. Opens a new scroll context for the first page.

        ⚠ Scroll is stateful on the ES server.  This implementation uses the
        scroll generator for the first page only (it's consumed immediately).
        For multi-page scroll navigation, use the full stream_export instead.
        """
        query_body = self.build_query(f, cursor=None)
        t0 = time.monotonic()

        gen = self._client.scroll_search(
            index=self._index,
            body=query_body,
            batch_size=f.page_size,
            max_docs=f.page_size,
        )
        try:
            hits = next(gen, [])
        except Exception as exc:
            return PageResult(
                page_num=page_num, hits=[], flat_rows=[], cursor=None,
                total_hits=0, elapsed_ms=0.0, has_next=False,
                query_body=query_body, method="scroll", error=str(exc),
            )

        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        flat_rows = [DataUtils.flatten_dict(h.get("_source", {})) for h in hits]

        return PageResult(
            page_num=page_num,
            hits=hits,
            flat_rows=flat_rows,
            cursor=None,   # Scroll doesn't expose a search_after-style cursor
            total_hits=len(hits),
            elapsed_ms=elapsed_ms,
            has_next=False,
            query_body=query_body,
            method="scroll",
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Export Stream (search_after generator, capped)
    # ──────────────────────────────────────────────────────────────────────────

    def stream_export(
        self,
        f: LogFilter,
        max_docs: Optional[int] = None,
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Generator that yields batches of flat-row dicts for CSV export.

        Memory-safe: never holds more than one batch in memory.
        Caps at ``max_docs`` (defaults to RETRIEVAL_EXPORT_CAP from settings).

        Args:
            f:        Filter configuration.
            max_docs: Hard ceiling on total exported documents.

        Yields:
            List[Dict] — each dict is a flattened _source row.
        """
        cap = min(max_docs or settings.retrieval_export_cap, MAX_EXPORT_DOCS)
        total_yielded = 0
        cursor: Optional[List[Any]] = None

        while total_yielded < cap:
            remaining = cap - total_yielded
            batch_size = min(f.page_size, remaining, MAX_PAGE_SIZE)

            query_body = self.build_query(f, cursor=cursor, size_override=batch_size)

            try:
                resp = self._client.search(
                    index=self._index,
                    body=query_body,
                    enforce_size_limit=False,
                )
            except Exception as exc:
                logger.error("stream_export error at doc %d: %s", total_yielded, exc)
                break

            hits = resp.get("hits", {}).get("hits", [])
            if not hits:
                break

            flat_rows = [DataUtils.flatten_dict(h.get("_source", {})) for h in hits]
            yield flat_rows

            total_yielded += len(hits)
            cursor = hits[-1].get("sort")
            if not cursor or len(hits) < batch_size:
                break   # Last page reached

        logger.info("stream_export: yielded %d docs (cap=%d)", total_yielded, cap)


# ─── Module-level helpers ──────────────────────────────────────────────────────

def _exact_or_wildcard(field_name: str, value: str) -> Dict[str, Any]:
    """
    Return a ``term`` or ``wildcard`` clause depending on whether
    the value contains wildcard characters.
    """
    if "*" in value or "?" in value:
        return {"wildcard": {field_name: {"value": value, "case_insensitive": True}}}
    return {"term": {field_name: value}}


def _ip_filter(field_name: str, value: str) -> Dict[str, Any]:
    """
    Return the appropriate ES filter for an IP value.
    Supports:
      - Exact IP:         "192.168.1.5"
      - CIDR:             "10.0.0.0/8"
      - Wildcard prefix:  "10.0.0.*"
    """
    if "/" in value:
        # CIDR notation — ES ip field type handles this natively via term
        return {"term": {field_name: value}}
    if "*" in value or "?" in value:
        return {"wildcard": {field_name: {"value": value}}}
    return {"term": {field_name: value}}
