"""
utils/data_utils.py

Safe parsers for Elasticsearch aggregation results and data sanitizers.

These utilities bridge the gap between raw ES response dicts and
Pandas DataFrames ready for display or visualisation.

Usage:
    from utils import DataUtils

    df = DataUtils.date_histogram_to_df(aggs["events_over_time"])
    df = DataUtils.terms_to_df(aggs["top_src_ips"])
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from config import get_logger

logger = get_logger(__name__)


class DataUtils:
    """Static utility methods for ES result parsing and data cleaning."""

    # ─── Aggregation parsers ──────────────────────────────────────────────────

    @staticmethod
    def date_histogram_to_df(
        agg: Dict[str, Any],
        time_col: str = "timestamp",
        count_col: str = "count",
    ) -> pd.DataFrame:
        """
        Parse a date_histogram aggregation result into a DataFrame.

        Args:
            agg:       The value of aggs["<agg_name>"] from an ES response.
            time_col:  Name for the timestamp column.
            count_col: Name for the doc_count column.

        Returns:
            DataFrame with columns [time_col, count_col].
            Returns empty DataFrame on parse failure.
        """
        try:
            buckets = agg.get("buckets", [])
            rows = [
                {
                    time_col: pd.to_datetime(b["key_as_string"]),
                    count_col: b["doc_count"],
                }
                for b in buckets
            ]
            df = pd.DataFrame(rows)
            if not df.empty:
                df[time_col] = pd.to_datetime(df[time_col], utc=True)
            return df
        except Exception as exc:
            logger.warning("date_histogram_to_df parse error: %s", exc)
            return pd.DataFrame(columns=[time_col, count_col])

    @staticmethod
    def date_histogram_with_sub_agg_to_df(
        agg: Dict[str, Any],
        sub_agg_name: str = "by_severity",
        time_col: str = "timestamp",
        count_col: str = "total",
    ) -> pd.DataFrame:
        """
        Parse a date_histogram with a nested terms sub-aggregation into a
        wide-format DataFrame.

        Produces one column per sub-agg bucket key (e.g. one per severity
        level), plus a ``total`` column from the outer bucket doc_count.

        Args:
            agg:          The outer date_histogram agg result dict.
            sub_agg_name: Key inside each histogram bucket for the sub-agg.
            time_col:     Column name for the timestamp.
            count_col:    Column name for the outer doc_count.

        Returns:
            Wide DataFrame: [time_col, count_col, <sub-bucket-key>, ...]
        """
        try:
            rows = []
            for b in agg.get("buckets", []):
                row: Dict[str, Any] = {
                    time_col: pd.to_datetime(b["key_as_string"]),
                    count_col: b["doc_count"],
                }
                sub = b.get(sub_agg_name, {})
                for sb in sub.get("buckets", []):
                    row[sb.get("key_as_string", str(sb["key"]))] = sb["doc_count"]
                rows.append(row)
            df = pd.DataFrame(rows)
            if not df.empty:
                df[time_col] = pd.to_datetime(df[time_col], utc=True)
            return df
        except Exception as exc:
            logger.warning("date_histogram_with_sub_agg_to_df parse error: %s", exc)
            return pd.DataFrame(columns=[time_col, count_col])

    @staticmethod
    def terms_to_df(
        agg: Dict[str, Any],
        key_col: str = "value",
        count_col: str = "count",
    ) -> pd.DataFrame:
        """
        Parse a terms aggregation result into a DataFrame.

        Args:
            agg:       The value of aggs["<agg_name>"] from an ES response.
            key_col:   Name for the bucket key column.
            count_col: Name for the doc_count column.

        Returns:
            DataFrame with columns [key_col, count_col], sorted by count desc.
        """
        try:
            buckets = agg.get("buckets", [])
            rows = [
                {key_col: b.get("key_as_string", b["key"]), count_col: b["doc_count"]}
                for b in buckets
            ]
            df = pd.DataFrame(rows)
            if not df.empty:
                df = df.sort_values(count_col, ascending=False).reset_index(drop=True)
            return df
        except Exception as exc:
            logger.warning("terms_to_df parse error: %s", exc)
            return pd.DataFrame(columns=[key_col, count_col])

    @staticmethod
    def cardinality_value(agg: Dict[str, Any]) -> int:
        """Extract the integer value from a cardinality aggregation result."""
        try:
            return int(agg.get("value", 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def single_value(agg: Dict[str, Any]) -> float:
        """Extract a numeric value from any single-value metric aggregation."""
        try:
            v = agg.get("value", 0.0)
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def percentiles_to_dict(agg: Dict[str, Any]) -> Dict[str, float]:
        """
        Parse a percentiles aggregation into a clean dict.

        Returns:
            Dict like {"50.0": 123.4, "95.0": 456.7, ...}
        """
        try:
            values = agg.get("values", {})
            return {k: (float(v) if v is not None else 0.0) for k, v in values.items()}
        except Exception:
            return {}

    @staticmethod
    def hits_to_df(hits: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Flatten a list of ES hit dicts into a DataFrame.

        Each hit's ``_source`` is flattened, with ``_id`` and ``_index`` added.
        Nested objects become dot-notation columns.

        Args:
            hits: List of ES hit dicts (from response["hits"]["hits"]).

        Returns:
            Flat DataFrame.
        """
        rows = []
        for hit in hits:
            row = {"_id": hit.get("_id"), "_index": hit.get("_index")}
            source = hit.get("_source", {})
            flat_source = DataUtils.flatten_dict(source)
            row.update(flat_source)
            rows.append(row)
        return pd.DataFrame(rows)

    # ─── Data cleaning ────────────────────────────────────────────────────────

    @staticmethod
    def flatten_dict(
        d: Dict[str, Any],
        sep: str = ".",
        prefix: str = "",
        max_depth: int = 5,
    ) -> Dict[str, Any]:
        """
        Recursively flatten a nested dict using dot-notation keys.

        Args:
            d:         Input dict.
            sep:       Separator between key levels.
            prefix:    Key prefix (used in recursion).
            max_depth: Max recursion depth to prevent infinite loops.

        Returns:
            Flat dict with dot-notation keys.
        """
        result: Dict[str, Any] = {}
        if max_depth <= 0:
            return {prefix: str(d)} if prefix else {}

        for key, value in d.items():
            full_key = f"{prefix}{sep}{key}" if prefix else key
            if isinstance(value, dict) and value:
                result.update(
                    DataUtils.flatten_dict(value, sep=sep, prefix=full_key, max_depth=max_depth - 1)
                )
            elif isinstance(value, list):
                # Convert small lists to string; skip large arrays
                if len(value) <= 5:
                    result[full_key] = ", ".join(str(v) for v in value)
                else:
                    result[full_key] = f"[{len(value)} items]"
            else:
                result[full_key] = value
        return result

    @staticmethod
    def sanitize_df(df: pd.DataFrame, max_rows: int = 10_000) -> pd.DataFrame:
        """
        Safety check for DataFrames — cap rows, replace NaN/Inf.

        Args:
            df:       Input DataFrame.
            max_rows: Maximum rows to keep.

        Returns:
            Sanitized DataFrame.
        """
        if len(df) > max_rows:
            logger.warning(
                "DataFrame truncated from %d to %d rows for memory safety.", len(df), max_rows
            )
            df = df.head(max_rows)

        # Replace infinite values
        df = df.replace([np.inf, -np.inf], np.nan)
        return df

    @staticmethod
    def format_large_number(n: int | float) -> str:
        """
        Format a large number into a human-readable string.

        Examples: 2_770_000_000 → "2.77B", 1_500_000 → "1.50M"
        """
        n = float(n)
        if abs(n) >= 1e9:
            return f"{n / 1e9:.2f}B"
        elif abs(n) >= 1e6:
            return f"{n / 1e6:.2f}M"
        elif abs(n) >= 1e3:
            return f"{n / 1e3:.1f}K"
        return f"{int(n):,}"

    @staticmethod
    def safe_percentage(part: float, total: float) -> float:
        """Return part/total as a percentage, returning 0.0 if total is zero."""
        if total == 0:
            return 0.0
        return round((part / total) * 100, 2)

    @staticmethod
    def infer_severity_colour(severity: str) -> str:
        """
        Map a severity string to a CSS hex colour.
        Returns a default colour for unknown severities.
        """
        mapping = {
            "critical": "#FF4B4B",
            "high": "#FF8C00",
            "medium": "#FFD700",
            "low": "#00C851",
            "info": "#17A2B8",
            "informational": "#17A2B8",
            "unknown": "#6C757D",
        }
        return mapping.get(severity.lower(), "#6C757D")
