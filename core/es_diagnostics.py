"""
core/es_diagnostics.py

Elasticsearch diagnostics helpers for the ISRO SOC Analytics platform.

Provides high-level diagnostic functions that combine multiple ES API
calls into structured summaries suitable for display in the Streamlit
diagnostics page.

All functions are stateless — they accept an ElasticsearchClient instance
and return plain Python dicts / DataFrames.

Usage:
    from core.es_diagnostics import DiagnosticsEngine
    from core import get_es_client

    engine = DiagnosticsEngine(get_es_client())
    report = engine.full_report()
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pandas as pd

from config import get_logger, settings
from core.elasticsearch_client import ElasticsearchClient, _bytes_to_human

logger = get_logger(__name__)


class DiagnosticsEngine:
    """
    Aggregates multiple ES API calls into structured diagnostic reports.

    All report methods are safe to call even when ES is unreachable —
    they return dicts with an ``error`` key in that case.
    """

    def __init__(self, client: ElasticsearchClient) -> None:
        self._client = client

    # ──────────────────────────────────────────────────────────────────────────
    # Individual Reports
    # ──────────────────────────────────────────────────────────────────────────

    def connectivity_report(self) -> Dict[str, Any]:
        """
        Run the full connectivity suite and return a structured report.

        Returns:
            Dict with test results for ping, auth, health, index_list,
            target_index.
        """
        logger.info("Running connectivity diagnostic suite...")
        return self._client.run_connectivity_suite()

    def cluster_report(self) -> Dict[str, Any]:
        """
        Combine cluster info + stats into a single display-ready report.

        Returns:
            Dict with keys: info (cluster_name, es_version, etc.),
            stats (total_docs, store_size, indices_count, etc.),
            health (status, node_count, shards).
        """
        report: Dict[str, Any] = {
            "info": {},
            "stats": {},
            "health": {},
            "error": None,
        }
        try:
            report["info"] = self._client.get_cluster_info()
            report["stats"] = self._client.get_cluster_stats()
            report["health"] = self._client.health_check()
        except Exception as exc:
            report["error"] = str(exc)
            logger.error("cluster_report failed: %s", exc)
        return report

    def index_report(
        self,
        pattern: str = "*",
        include_hidden: bool = False,
    ) -> pd.DataFrame:
        """
        Build a Pandas DataFrame of all matching indices with metadata.

        Columns: name, health, status, docs_count, store_size,
                 primary_shards, replica_shards.

        Args:
            pattern:        Index pattern (default ``*``).
            include_hidden: Include system/hidden indices.

        Returns:
            DataFrame sorted by docs_count descending.
        """
        indices = self._client.list_indices(
            pattern=pattern,
            include_hidden=include_hidden,
        )
        if not indices:
            return pd.DataFrame(columns=[
                "name", "health", "status", "docs_count",
                "store_size", "primary_shards", "replica_shards",
            ])

        df = pd.DataFrame(indices)

        # Enrich with numeric doc counts for sorting
        df["docs_count"] = pd.to_numeric(df["docs_count"], errors="coerce").fillna(0).astype(int)
        df = df.sort_values("docs_count", ascending=False).reset_index(drop=True)
        return df

    def node_report(self) -> pd.DataFrame:
        """
        Build a Pandas DataFrame of node info.

        Columns: name, ip, roles, es_version, os_name, jvm_version, heap_max_mb.
        """
        nodes = self._client.get_node_info()
        if not nodes:
            return pd.DataFrame()

        df = pd.DataFrame(nodes)
        if "roles" in df.columns:
            df["roles"] = df["roles"].apply(lambda r: ", ".join(r) if isinstance(r, list) else str(r))
        return df

    def field_report(
        self,
        index: str,
        type_filter: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Build a DataFrame of field names and types for a given index.

        Args:
            index:       ES index name.
            type_filter: If set, only include fields of this ES type.

        Returns:
            DataFrame with columns: field, type, aggregatable, searchable.
        """
        caps = self._client.get_field_capabilities(index=index)
        if not caps:
            # Fall back to flat mapping
            flat = self._client.get_index_mapping(index=index)
            rows = [{"field": k, "type": v, "aggregatable": None, "searchable": None}
                    for k, v in flat.items() if not k.startswith("_")]
        else:
            rows = [
                {
                    "field": fname,
                    "type": meta.get("type", ""),
                    "aggregatable": meta.get("aggregatable", False),
                    "searchable": meta.get("searchable", False),
                }
                for fname, meta in caps.items()
                if not meta.get("metadata_field", False)
            ]

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        if type_filter:
            df = df[df["type"] == type_filter]

        return df.sort_values("field").reset_index(drop=True)

    def target_index_report(self) -> Dict[str, Any]:
        """
        Diagnostic report specifically for the configured target index pattern.

        Returns summary stats and a sample of the most common field types.
        """
        report: Dict[str, Any] = {
            "index_pattern": settings.es_index_pattern,
            "stats": {},
            "field_type_summary": {},
            "error": None,
        }
        try:
            report["stats"] = self._client.get_index_stats(settings.es_index_pattern)
            # Field type distribution
            caps = self._client.get_field_capabilities(
                index=settings.es_index_pattern, fields="*"
            )
            type_counts: Dict[str, int] = {}
            for meta in caps.values():
                t = meta.get("type", "unknown")
                type_counts[t] = type_counts.get(t, 0) + 1
            report["field_type_summary"] = dict(
                sorted(type_counts.items(), key=lambda x: -x[1])
            )
        except Exception as exc:
            report["error"] = str(exc)
            logger.error("target_index_report failed: %s", exc)
        return report

    def measure_query_latency(
        self,
        index: str,
        n_runs: int = 3,
    ) -> Dict[str, Any]:
        """
        Measure round-trip latency for a simple match_all aggregation.

        Runs n_runs times and returns min/avg/max latency in milliseconds.
        Useful for monitoring query performance.

        Args:
            index:   ES index pattern to query.
            n_runs:  Number of timing runs.

        Returns:
            Dict with min_ms, avg_ms, max_ms, runs.
        """
        times: List[float] = []
        error: Optional[str] = None

        for _ in range(n_runs):
            try:
                t0 = time.monotonic()
                self._client.count(
                    index=index,
                    query={"match_all": {}},
                    request_timeout=10,
                )
                times.append(round((time.monotonic() - t0) * 1000, 1))
            except Exception as exc:
                error = str(exc)
                break

        if not times:
            return {"min_ms": None, "avg_ms": None, "max_ms": None, "runs": 0, "error": error}

        return {
            "min_ms": min(times),
            "avg_ms": round(sum(times) / len(times), 1),
            "max_ms": max(times),
            "runs": len(times),
            "error": None,
        }

    def full_report(self) -> Dict[str, Any]:
        """
        Run all diagnostic sub-reports in sequence.

        Returns:
            Dict with keys: connectivity, cluster, target_index, latency.
        """
        logger.info("Running full diagnostic report...")
        return {
            "connectivity": self.connectivity_report(),
            "cluster": self.cluster_report(),
            "target_index": self.target_index_report(),
            "latency": self.measure_query_latency(settings.es_index_pattern),
        }
