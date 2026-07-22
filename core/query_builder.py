"""
core/query_builder.py

Elasticsearch Query DSL builder for the ISRO SOC Analytics platform.

All methods return fully-formed query bodies (dicts) that can be passed
directly to ElasticsearchClient.search() or .aggregate().

Design notes:
  - Aggregation-first: all analytics methods use size=0
  - Time ranges are always anchored to @timestamp
  - Filter composition supports AND chaining
  - Never constructs queries that could return more than MAX_SAFE_SIZE hits

Usage:
    from core import query_builder as qb

    body = qb.event_volume_over_time(
        time_field="@timestamp",
        from_dt="2026-06-01T00:00:00Z",
        to_dt="2026-06-30T23:59:59Z",
        interval="1d",
    )
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from config import get_logger

logger = get_logger(__name__)


class QueryBuilder:
    """
    Stateless factory for Elasticsearch Query DSL bodies.

    All methods return ``dict`` objects — no state is held between calls.
    """

    # ─── Base building blocks ─────────────────────────────────────────────────

    @staticmethod
    def match_all() -> Dict[str, Any]:
        """Return a match_all query."""
        return {"match_all": {}}

    @staticmethod
    def time_range_filter(
        time_field: str,
        from_dt: str | datetime,
        to_dt: str | datetime,
    ) -> Dict[str, Any]:
        """
        Return a range filter clause for a time field.

        Args:
            time_field: ES field name (e.g. "@timestamp").
            from_dt:    ISO-8601 string or datetime (inclusive lower bound).
            to_dt:      ISO-8601 string or datetime (inclusive upper bound).
        """
        gte = from_dt.isoformat() if isinstance(from_dt, datetime) else from_dt
        lte = to_dt.isoformat() if isinstance(to_dt, datetime) else to_dt
        return {"range": {time_field: {"gte": gte, "lte": lte}}}

    @staticmethod
    def term_filter(field: str, value: Any) -> Dict[str, Any]:
        """Exact-match filter for a keyword field."""
        return {"term": {field: value}}

    @staticmethod
    def terms_filter(field: str, values: List[Any]) -> Dict[str, Any]:
        """Match any of a list of values."""
        return {"terms": {field: values}}

    @staticmethod
    def match_filter(field: str, value: str) -> Dict[str, Any]:
        """Full-text match filter."""
        return {"match": {field: value}}

    @staticmethod
    def wildcard_filter(field: str, pattern: str) -> Dict[str, Any]:
        """Wildcard filter (use sparingly — slow on large datasets)."""
        return {"wildcard": {field: {"value": pattern}}}

    @staticmethod
    def exists_filter(field: str) -> Dict[str, Any]:
        """Filter for documents where a field exists."""
        return {"exists": {"field": field}}

    @staticmethod
    def bool_query(
        must: Optional[List[Dict]] = None,
        filter: Optional[List[Dict]] = None,
        should: Optional[List[Dict]] = None,
        must_not: Optional[List[Dict]] = None,
        minimum_should_match: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Compose a bool query from filter lists.

        Filter clauses are preferred over must for performance (cached).
        """
        q: Dict[str, Any] = {"bool": {}}
        if must:
            q["bool"]["must"] = must
        if filter:
            q["bool"]["filter"] = filter
        if should:
            q["bool"]["should"] = should
            if minimum_should_match is not None:
                q["bool"]["minimum_should_match"] = minimum_should_match
        if must_not:
            q["bool"]["must_not"] = must_not
        return q

    # ─── Aggregation builders ─────────────────────────────────────────────────

    @staticmethod
    def date_histogram_agg(
        agg_name: str,
        time_field: str,
        calendar_interval: str = "1d",
        sub_aggs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Date histogram aggregation.

        Args:
            agg_name:          Name for this aggregation.
            time_field:        ES datetime field.
            calendar_interval: e.g. "1h", "1d", "1w".
            sub_aggs:          Optional nested aggregations.
        """
        agg: Dict[str, Any] = {
            "date_histogram": {
                "field": time_field,
                "calendar_interval": calendar_interval,
                "min_doc_count": 0,
            }
        }
        if sub_aggs:
            agg["aggs"] = sub_aggs
        return {agg_name: agg}

    @staticmethod
    def terms_agg(
        agg_name: str,
        field: str,
        size: int = 20,
        order_by: str = "_count",
        order_dir: str = "desc",
        sub_aggs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Terms aggregation (top-N by count).

        Args:
            agg_name:  Name for this aggregation.
            field:     Keyword field to aggregate on.
            size:      Maximum number of buckets to return.
            order_by:  Sort field ("_count" or a sub-aggregation key).
            order_dir: "asc" or "desc".
            sub_aggs:  Optional nested aggregations.
        """
        agg: Dict[str, Any] = {
            "terms": {
                "field": field,
                "size": size,
                "order": {order_by: order_dir},
            }
        }
        if sub_aggs:
            agg["aggs"] = sub_aggs
        return {agg_name: agg}

    @staticmethod
    def cardinality_agg(
        agg_name: str,
        field: str,
        precision_threshold: int = 3000,
    ) -> Dict[str, Any]:
        """
        Cardinality (approximate unique count) aggregation.

        Args:
            agg_name:            Name for this aggregation.
            field:               Field to count unique values of.
            precision_threshold: Higher = more accurate but more memory.
        """
        return {
            agg_name: {
                "cardinality": {
                    "field": field,
                    "precision_threshold": precision_threshold,
                }
            }
        }

    @staticmethod
    def value_count_agg(agg_name: str, field: str) -> Dict[str, Any]:
        """Count non-null values of a field."""
        return {agg_name: {"value_count": {"field": field}}}

    @staticmethod
    def avg_agg(agg_name: str, field: str) -> Dict[str, Any]:
        """Average metric aggregation."""
        return {agg_name: {"avg": {"field": field}}}

    @staticmethod
    def percentiles_agg(
        agg_name: str,
        field: str,
        percents: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Percentiles aggregation."""
        return {
            agg_name: {
                "percentiles": {
                    "field": field,
                    "percents": percents or [50, 75, 90, 95, 99],
                }
            }
        }

    @staticmethod
    def merge_aggs(*agg_dicts: Dict[str, Any]) -> Dict[str, Any]:
        """Merge multiple aggregation dicts into a single ``aggs`` dict."""
        merged: Dict[str, Any] = {}
        for agg in agg_dicts:
            merged.update(agg)
        return merged

    # ─── High-level query templates ───────────────────────────────────────────

    def event_volume_over_time(
        self,
        time_field: str,
        from_dt: str | datetime,
        to_dt: str | datetime,
        interval: str = "1h",
        extra_filters: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Event count bucketed by time interval.

        Returns a query body with size=0 and a date_histogram aggregation.
        Suitable for plotting event volume trend lines.
        """
        filters: List[Dict[str, Any]] = [self.time_range_filter(time_field, from_dt, to_dt)]
        if extra_filters:
            filters.extend(extra_filters)

        return {
            "size": 0,
            "query": self.bool_query(filter=filters),
            "aggs": self.date_histogram_agg(
                "events_over_time", time_field, calendar_interval=interval
            ),
        }

    def top_terms(
        self,
        field: str,
        time_field: str,
        from_dt: str | datetime,
        to_dt: str | datetime,
        top_n: int = 20,
        extra_filters: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Top-N values for a keyword field within a time range.

        Returns a query body with size=0 and a terms aggregation.
        """
        filters: List[Dict[str, Any]] = [self.time_range_filter(time_field, from_dt, to_dt)]
        if extra_filters:
            filters.extend(extra_filters)

        return {
            "size": 0,
            "query": self.bool_query(filter=filters),
            "aggs": self.terms_agg("top_values", field, size=top_n),
        }

    def total_event_count(
        self,
        time_field: str,
        from_dt: str | datetime,
        to_dt: str | datetime,
        extra_filters: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Count total events in a time window (uses value_count, not count API).
        Prefer ElasticsearchClient.count() for simple counts.
        """
        filters: List[Dict[str, Any]] = [self.time_range_filter(time_field, from_dt, to_dt)]
        if extra_filters:
            filters.extend(extra_filters)

        return {
            "size": 0,
            "query": self.bool_query(filter=filters),
            "aggs": self.value_count_agg("total_events", time_field),
        }

    def severity_distribution(
        self,
        severity_field: str,
        time_field: str,
        from_dt: str | datetime,
        to_dt: str | datetime,
        extra_filters: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Distribution of events by severity level.
        """
        filters: List[Dict[str, Any]] = [self.time_range_filter(time_field, from_dt, to_dt)]
        if extra_filters:
            filters.extend(extra_filters)

        return {
            "size": 0,
            "query": self.bool_query(filter=filters),
            "aggs": self.terms_agg("severity_dist", severity_field, size=50),
        }

    def source_ip_top_talkers(
        self,
        src_ip_field: str,
        time_field: str,
        from_dt: str | datetime,
        to_dt: str | datetime,
        top_n: int = 20,
        extra_filters: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Top source IPs by event count."""
        return self.top_terms(
            field=src_ip_field,
            time_field=time_field,
            from_dt=from_dt,
            to_dt=to_dt,
            top_n=top_n,
            extra_filters=extra_filters,
        )

    def multi_metric_dashboard(
        self,
        time_field: str,
        from_dt: str | datetime,
        to_dt: str | datetime,
        interval: str = "1h",
        severity_field: str = "event.severity",
        src_ip_field: str = "source.ip",
        extra_filters: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Single aggregation query that returns multiple metrics for the overview dashboard.

        Combines:
          - events_over_time (date_histogram)
          - severity_distribution (terms)
          - top_source_ips (terms)
          - unique_source_ips (cardinality)
        """
        filters: List[Dict[str, Any]] = [self.time_range_filter(time_field, from_dt, to_dt)]
        if extra_filters:
            filters.extend(extra_filters)

        aggs = self.merge_aggs(
            self.date_histogram_agg("events_over_time", time_field, calendar_interval=interval),
            self.terms_agg("severity_dist", severity_field, size=20),
            self.terms_agg("top_src_ips", src_ip_field, size=15),
            self.cardinality_agg("unique_src_ips", src_ip_field),
        )

        return {
            "size": 0,
            "query": self.bool_query(filter=filters),
            "aggs": aggs,
        }

    def enterprise_dashboard_searches(
        self,
        time_field: str,
        from_dt: str,
        to_dt: str,
        interval: str = "1h",
        hostname_field: str = "host.name",
        username_field: str = "user.name",
        src_ip_field: str = "source.ip",
        dst_ip_field: str = "destination.ip",
        severity_field: str = "event.severity",
        category_field: str = "event.category",
        outcome_field: str = "event.outcome",
        event_id_field: str = "event.id",
        extra_filters: Optional[List[Dict]] = None,
        top_n: int = 15,
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Build a list of (header, body) tuples for a single msearch round-trip.

        Indices in the returned list:
            0  KPI bundle     — cardinalities for hosts/users/src_ips/dst_ips
            1  Event trend    — date_histogram with severity sub-agg
            2  Top hosts      — terms agg on hostname_field
            3  Top users      — terms agg on username_field
            4  Top src IPs    — terms agg on src_ip_field
            5  Top dst IPs    — terms agg on dst_ip_field
            6  Severity dist  — terms agg on severity_field
            7  Category dist  — terms agg on category_field
            8  Outcome dist   — terms agg on outcome_field
            9  Top event IDs  — terms agg on event_id_field

        All bodies use size=0 — zero raw documents are downloaded.

        Args:
            time_field:      Timestamp field name.
            from_dt:         ISO-8601 range start (inclusive).
            to_dt:           ISO-8601 range end (inclusive).
            interval:        Calendar interval for the date histogram (e.g. "1h", "1d").
            hostname_field:  ECS host name keyword field.
            username_field:  ECS user name keyword field.
            src_ip_field:    Source IP keyword field.
            dst_ip_field:    Destination IP keyword field.
            severity_field:  Severity keyword field.
            category_field:  Event category keyword field.
            outcome_field:   Event outcome keyword field.
            event_id_field:  Event ID keyword field.
            extra_filters:   Additional ES filter clauses (e.g. keyword query_string).
            top_n:           How many buckets to return from each terms aggregation.

        Returns:
            List of (header_dict, body_dict) tuples for msearch.
        """
        base_filters: List[Dict[str, Any]] = [
            self.time_range_filter(time_field, from_dt, to_dt)
        ]
        if extra_filters:
            base_filters.extend(extra_filters)

        base_query = self.bool_query(filter=base_filters)
        H: Dict[str, Any] = {}  # empty header — caller supplies default index

        # ── 0: KPI bundle ─────────────────────────────────────────────────────
        kpi_body: Dict[str, Any] = {
            "size": 0,
            "track_total_hits": True,
            "query": base_query,
            "aggs": self.merge_aggs(
                self.cardinality_agg("unique_hosts",   hostname_field),
                self.cardinality_agg("unique_users",   username_field),
                self.cardinality_agg("unique_src_ips", src_ip_field),
                self.cardinality_agg("unique_dst_ips", dst_ip_field),
            ),
        }

        # ── 1: Event trend with severity sub-agg ──────────────────────────────
        trend_body: Dict[str, Any] = {
            "size": 0,
            "query": base_query,
            "aggs": self.date_histogram_agg(
                "events_over_time",
                time_field,
                calendar_interval=interval,
                sub_aggs=self.terms_agg("by_severity", severity_field, size=10),
            ),
        }

        # ── 2–9: Top-N terms aggregations ─────────────────────────────────────
        def _terms_body(field: str) -> Dict[str, Any]:
            return {
                "size": 0,
                "query": base_query,
                "aggs": self.terms_agg("top_values", field, size=top_n),
            }

        return [
            (H, kpi_body),                          # 0
            (H, trend_body),                        # 1
            (H, _terms_body(hostname_field)),       # 2
            (H, _terms_body(username_field)),       # 3
            (H, _terms_body(src_ip_field)),         # 4
            (H, _terms_body(dst_ip_field)),         # 5
            (H, _terms_body(severity_field)),       # 6
            (H, _terms_body(category_field)),       # 7
            (H, _terms_body(outcome_field)),        # 8
            (H, _terms_body(event_id_field)),       # 9
        ]

    def sigma_rule_match(
        self,
        rule_query: Dict[str, Any],
        time_field: str,
        from_dt: str | datetime,
        to_dt: str | datetime,
        bucket_interval: str = "1h",
    ) -> Dict[str, Any]:
        """
        Wrap a Sigma-generated query with time filtering and a count bucketed by time.

        Args:
            rule_query:      The ES query dict from pySigma backend.
            time_field:      Timestamp field.
            from_dt / to_dt: Time range.
            bucket_interval: Histogram interval for hit counts over time.
        """
        time_filter = self.time_range_filter(time_field, from_dt, to_dt)
        combined_query = self.bool_query(
            filter=[time_filter],
            must=[rule_query] if rule_query else None,
        )

        return {
            "size": 0,
            "query": combined_query,
            "aggs": self.date_histogram_agg(
                "matches_over_time", time_field, calendar_interval=bucket_interval
            ),
        }
