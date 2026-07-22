"""
core/elasticsearch_client.py

Production-grade Elasticsearch 9.4.1 client wrapper for the ISRO SOC Analytics platform.

Design principles:
  - Read-only credentials from settings (never writes to ES)
  - Connection pooling via the official elasticsearch-py 9.4.1 client
  - Three-tier exception hierarchy: connectivity → auth → application errors
  - Hard safety limit: refuses queries with size > MAX_SAFE_SIZE
  - All public methods are fully typed and return plain Python dicts/generators
  - Retry logic with exponential backoff (tenacity) on transient failures
  - Request timing logged at DEBUG level for performance monitoring

Public API surface:
  Connectivity  : ping, validate_credentials, health_check
  Cluster       : get_cluster_info, get_cluster_stats, get_node_info
  Indices       : list_indices, get_index_stats, get_index_mapping, get_field_capabilities
  Search        : search, aggregate, count, msearch, validate_query
  Streaming     : scroll_search, search_after

Usage:
    from core import get_es_client
    client = get_es_client()
    health = client.health_check()
    indices = client.list_indices()
    aggs = client.aggregate(index="security-logs-2026.06.*", body={...})
"""

from __future__ import annotations

import time
from typing import Any, Dict, Generator, List, Optional, Tuple
import logging

from elasticsearch import Elasticsearch, NotFoundError, TransportError
try:
    from elasticsearch import ConnectionError as ESConnectionError
    from elasticsearch import ConnectionTimeout
    from elasticsearch import AuthenticationException, AuthorizationException
    from elasticsearch import BadRequestError
except ImportError:
    # Fallback for slightly different package layouts
    from elastic_transport import ConnectionError as ESConnectionError  # type: ignore
    ConnectionTimeout = ESConnectionError  # type: ignore
    AuthenticationException = Exception  # type: ignore
    AuthorizationException = Exception  # type: ignore
    BadRequestError = Exception  # type: ignore

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError,
)

from config import settings, get_logger

logger = get_logger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_SAFE_SIZE: int = 5_000          # Hard cap on search hits returned
DEFAULT_REQUEST_TIMEOUT: int = 30   # Seconds — standard queries
AGG_REQUEST_TIMEOUT: int = 120      # Seconds — heavy aggregations on 2.77B docs
PING_TIMEOUT: int = 5               # Seconds — fast connectivity check
CAT_TIMEOUT: int = 15               # Seconds — cat API calls


# ─── Custom Exception Hierarchy ───────────────────────────────────────────────

class ESClientError(Exception):
    """Base class for all ISRO SOC ES client errors."""


class ESConnectivityError(ESClientError):
    """Cannot reach the Elasticsearch host (network, DNS, TLS)."""


class ESAuthError(ESClientError):
    """Authentication or authorisation failed (401 / 403)."""


class ESSafetyError(ESClientError):
    """Request blocked by a safety rule (e.g. size > MAX_SAFE_SIZE)."""


class ESQueryError(ESClientError):
    """Elasticsearch rejected the query (4xx, bad DSL)."""


# Backwards-compatibility alias used by Prompt-1 code
ElasticsearchClientError = ESClientError


# ─── Main Client ──────────────────────────────────────────────────────────────

class ElasticsearchClient:
    """
    Safety-first, read-only Elasticsearch 9.4.1 client for the ISRO SOC
    Analytics platform.

    The underlying ``elasticsearch.Elasticsearch`` instance is built lazily
    on first use so the Streamlit app can start even when ES is unreachable.
    All methods are safe to call without prior ``ping()``; they will surface
    a structured error dict or raise a typed exception.
    """

    def __init__(self) -> None:
        self._client: Optional[Elasticsearch] = None
        self._connected: bool = False
        self._last_ping_ms: Optional[float] = None
        self._build_error: Optional[str] = None

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _build_client(self) -> Elasticsearch:
        """Construct a configured ``Elasticsearch`` instance."""
        kwargs: Dict[str, Any] = {
            "hosts": [
                {
                    "host": settings.es_host,
                    "port": settings.es_port,
                    "scheme": settings.es_scheme,
                }
            ],
            "http_auth": (settings.es_username, settings.es_password),
            # Connection pool: keep up to 10 connections per host
            "connections_per_node": 10,
            "retry_on_timeout": True,
            "max_retries": 3,
            "request_timeout": DEFAULT_REQUEST_TIMEOUT,
        }

        if settings.es_ca_cert:
            kwargs["ca_certs"] = settings.es_ca_cert
            kwargs["verify_certs"] = True
        else:
            kwargs["verify_certs"] = False
            kwargs["ssl_show_warn"] = False

        logger.debug("Building ES client → %s (verify_certs=%s)", settings.es_url, bool(settings.es_ca_cert))
        return Elasticsearch(**kwargs)

    def _get_client(self) -> Elasticsearch:
        """Return the cached client, building it lazily on first call."""
        if self._client is None:
            try:
                self._client = self._build_client()
                self._build_error = None
            except Exception as exc:
                self._build_error = str(exc)
                logger.error("Failed to build ES client: %s", exc)
                raise ESConnectivityError(f"Cannot build Elasticsearch client: {exc}") from exc
        return self._client

    def reset(self) -> None:
        """
        Discard the cached client and force a rebuild on next use.
        Call this when credentials change at runtime.
        """
        self._client = None
        self._connected = False
        self._last_ping_ms = None
        logger.info("ES client reset — will reconnect on next call.")

    @staticmethod
    def _make_retry(max_attempts: int = 3):
        """
        Tenacity retry decorator for transient network / transport errors.
        Authentication and query errors are NOT retried.
        """
        return retry(
            retry=retry_if_exception_type((ESConnectionError, ConnectionTimeout, TransportError)),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=15),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

    @staticmethod
    def _timed(fn):
        """
        Decorator: measure wall-clock time of a call and log at DEBUG level.
        Returns (result, elapsed_ms).
        """
        def wrapper(*args, **kwargs):
            t0 = time.monotonic()
            result = fn(*args, **kwargs)
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
            return result, elapsed_ms
        return wrapper

    # ──────────────────────────────────────────────────────────────────────────
    # Connectivity Methods
    # ──────────────────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """
        Fast TCP-level connectivity check (no auth required).

        Returns:
            True if the host is reachable, False otherwise.
        """
        try:
            client = self._get_client()
            t0 = time.monotonic()
            reachable = client.ping(request_timeout=PING_TIMEOUT)
            self._last_ping_ms = round((time.monotonic() - t0) * 1000, 1)
            logger.debug("ES ping OK (%.1f ms)", self._last_ping_ms)
            return bool(reachable)
        except Exception as exc:
            logger.debug("ES ping failed: %s", exc)
            return False

    def validate_credentials(self) -> Dict[str, Any]:
        """
        Explicitly test username/password authentication by calling
        the ``/_security/authenticate`` endpoint (or falling back to
        cluster info). Never logs the password.

        Returns:
            Dict with keys:
              - authenticated (bool)
              - username (str)
              - roles (List[str])
              - error (str | None)
        """
        result: Dict[str, Any] = {
            "authenticated": False,
            "username": settings.es_username or "(not set)",
            "roles": [],
            "error": None,
        }
        try:
            client = self._get_client()
            # Try the security authenticate endpoint first (requires X-Pack)
            try:
                auth_resp = client.security.authenticate(request_timeout=10)
                result["authenticated"] = True
                result["username"] = auth_resp.get("username", settings.es_username)
                result["roles"] = list(auth_resp.get("roles", []))
                logger.info(
                    "Credential validation OK — user=%s roles=%s",
                    result["username"],
                    result["roles"],
                )
            except Exception:
                # Fall back: just try a cluster info call
                resp = client.info(request_timeout=10)
                if resp.get("cluster_name") or resp.get("name"):
                    result["authenticated"] = True
                    result["username"] = settings.es_username
                    logger.info("Credential validation OK (via cluster info fallback).")
        except (AuthenticationException,) as exc:
            result["error"] = "Authentication failed (401) — check ES_USERNAME / ES_PASSWORD"
            logger.warning("ES authentication failed: %s", exc)
        except (AuthorizationException,) as exc:
            result["error"] = "Authorization denied (403) — user lacks read permissions"
            logger.warning("ES authorization denied: %s", exc)
        except Exception as exc:
            result["error"] = str(exc)
            logger.warning("Credential validation error: %s", exc)
        return result

    def health_check(self) -> Dict[str, Any]:
        """
        Full cluster health check — returns connectivity, status, node count,
        shard counts, and round-trip latency.

        Returns:
            Dict with keys: connected, status, cluster_name, node_count,
            active_shards, unassigned_shards, response_time_ms, error.
        """
        result: Dict[str, Any] = {
            "connected": False,
            "status": "unknown",
            "cluster_name": "",
            "node_count": 0,
            "active_shards": 0,
            "unassigned_shards": 0,
            "active_primary_shards": 0,
            "response_time_ms": None,
            "error": None,
        }
        try:
            client = self._get_client()
            t0 = time.monotonic()
            health = client.cluster.health(request_timeout=10)
            elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

            result.update({
                "connected": True,
                "status": health.get("status", "unknown"),
                "cluster_name": health.get("cluster_name", ""),
                "node_count": health.get("number_of_nodes", 0),
                "active_shards": health.get("active_shards", 0),
                "unassigned_shards": health.get("unassigned_shards", 0),
                "active_primary_shards": health.get("active_primary_shards", 0),
                "response_time_ms": elapsed_ms,
            })
            self._connected = True
            self._last_ping_ms = elapsed_ms
            logger.info(
                "ES health OK — cluster=%s status=%s nodes=%d latency=%.1fms",
                result["cluster_name"], result["status"],
                result["node_count"], elapsed_ms,
            )
        except (AuthenticationException, AuthorizationException) as exc:
            result["error"] = f"Auth error: {exc}"
            self._connected = False
            logger.warning("ES health check — auth failed: %s", exc)
        except Exception as exc:
            result["error"] = str(exc)
            self._connected = False
            logger.warning("ES health check FAILED: %s", exc)
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Cluster Information
    # ──────────────────────────────────────────────────────────────────────────

    def get_cluster_info(self) -> Dict[str, Any]:
        """
        Retrieve high-level cluster information: name, version, lucene version,
        tagline, and cluster UUID.

        Returns:
            Dict with keys: cluster_name, cluster_uuid, es_version, lucene_version,
            tagline, build_type, error.
        """
        result: Dict[str, Any] = {
            "cluster_name": "",
            "cluster_uuid": "",
            "es_version": "",
            "lucene_version": "",
            "tagline": "",
            "build_type": "",
            "error": None,
        }
        try:
            client = self._get_client()
            resp = client.info(request_timeout=DEFAULT_REQUEST_TIMEOUT)
            version = resp.get("version", {})
            result.update({
                "cluster_name": resp.get("cluster_name", ""),
                "cluster_uuid": resp.get("cluster_uuid", ""),
                "es_version": version.get("number", ""),
                "lucene_version": version.get("lucene_version", ""),
                "tagline": resp.get("tagline", ""),
                "build_type": version.get("build_type", ""),
            })
            logger.debug("Cluster info fetched: %s v%s", result["cluster_name"], result["es_version"])
        except Exception as exc:
            result["error"] = str(exc)
            logger.error("get_cluster_info failed: %s", exc)
        return result

    def get_cluster_stats(self) -> Dict[str, Any]:
        """
        Retrieve aggregate cluster statistics: total indices, total docs,
        store size, node OS/JVM summary, and shard counts.

        Returns:
            Dict with aggregated stats, or error key.
        """
        result: Dict[str, Any] = {
            "indices_count": 0,
            "total_docs": 0,
            "deleted_docs": 0,
            "store_size_bytes": 0,
            "store_size_human": "",
            "node_count": 0,
            "primary_shards": 0,
            "replica_shards": 0,
            "segment_count": 0,
            "error": None,
        }
        try:
            client = self._get_client()
            resp = client.cluster.stats(request_timeout=DEFAULT_REQUEST_TIMEOUT)

            indices = resp.get("indices", {})
            shards = indices.get("shards", {})
            docs = indices.get("docs", {})
            store = indices.get("store", {})
            nodes = resp.get("nodes", {})

            result.update({
                "indices_count": indices.get("count", 0),
                "total_docs": docs.get("count", 0),
                "deleted_docs": docs.get("deleted", 0),
                "store_size_bytes": store.get("size_in_bytes", 0),
                "store_size_human": store.get("size", ""),
                "node_count": nodes.get("count", {}).get("total", 0),
                "primary_shards": shards.get("primaries", 0),
                "replica_shards": shards.get("replication", 0),
                "segment_count": indices.get("segments", {}).get("count", 0),
            })
            logger.debug("Cluster stats: %d indices, %d docs", result["indices_count"], result["total_docs"])
        except Exception as exc:
            result["error"] = str(exc)
            logger.error("get_cluster_stats failed: %s", exc)
        return result

    def get_node_info(self) -> List[Dict[str, Any]]:
        """
        Retrieve per-node information: roles, OS, JVM, ES version, IP.

        Returns:
            List of node dicts. Each dict has: id, name, ip, roles,
            es_version, os_name, jvm_version, heap_max_mb.
        """
        nodes: List[Dict[str, Any]] = []
        try:
            client = self._get_client()
            resp = client.nodes.info(request_timeout=DEFAULT_REQUEST_TIMEOUT)
            raw_nodes = resp.get("nodes", {})
            for node_id, node_data in raw_nodes.items():
                jvm = node_data.get("jvm", {})
                heap_bytes = jvm.get("mem", {}).get("heap_max_in_bytes", 0)
                os_info = node_data.get("os", {})
                nodes.append({
                    "id": node_id[:8],  # truncated for display
                    "name": node_data.get("name", ""),
                    "ip": node_data.get("ip", ""),
                    "host": node_data.get("host", ""),
                    "roles": node_data.get("roles", []),
                    "es_version": node_data.get("version", ""),
                    "os_name": os_info.get("name", ""),
                    "os_arch": os_info.get("arch", ""),
                    "jvm_version": jvm.get("version", ""),
                    "heap_max_mb": round(heap_bytes / (1024 * 1024)) if heap_bytes else 0,
                })
            logger.debug("Node info fetched: %d nodes", len(nodes))
        except Exception as exc:
            logger.error("get_node_info failed: %s", exc)
        return nodes

    # ──────────────────────────────────────────────────────────────────────────
    # Index Management
    # ──────────────────────────────────────────────────────────────────────────

    def list_indices(
        self,
        pattern: str = "*",
        *,
        include_hidden: bool = False,
        sort_by: str = "index",
        min_doc_count: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List Elasticsearch indices matching a pattern with metadata.

        Uses the CAT indices API for efficient retrieval — avoids loading
        the full mapping of every index.

        Args:
            pattern:       Index pattern (default ``*`` = all indices).
            include_hidden: If False (default), excludes ``.`` system indices.
            sort_by:       CAT sort column (e.g. "index", "docs.count", "store.size").
            min_doc_count: If set, filters out indices with fewer docs.

        Returns:
            List of dicts with keys: name, health, status, docs_count,
            deleted_docs, store_size, primary_shards, replica_shards, uuid.
        """
        indices: List[Dict[str, Any]] = []
        try:
            client = self._get_client()

            expand = "open,closed,hidden" if include_hidden else "open,closed"

            resp = client.cat.indices(
                index=pattern,
                format="json",
                h="index,health,status,docs.count,docs.deleted,store.size,pri,rep,uuid",
                s=f"{sort_by}:asc",
                expand_wildcards=expand,
                request_timeout=CAT_TIMEOUT,
            )

            for row in resp:
                # Skip hidden (dot-prefixed) indices unless requested
                name = row.get("index", "")
                if not include_hidden and name.startswith("."):
                    continue

                docs_count = int(row.get("docs.count") or 0)
                if min_doc_count is not None and docs_count < min_doc_count:
                    continue

                indices.append({
                    "name": name,
                    "health": row.get("health", "unknown"),
                    "status": row.get("status", ""),
                    "docs_count": docs_count,
                    "deleted_docs": int(row.get("docs.deleted") or 0),
                    "store_size": row.get("store.size", ""),
                    "primary_shards": int(row.get("pri") or 0),
                    "replica_shards": int(row.get("rep") or 0),
                    "uuid": row.get("uuid", ""),
                })

            logger.info("Listed %d indices (pattern=%r)", len(indices), pattern)
        except Exception as exc:
            logger.error("list_indices failed (pattern=%r): %s", pattern, exc)
        return indices

    def get_index_stats(self, index: str) -> Dict[str, Any]:
        """
        Retrieve detailed statistics for a single index or pattern.

        Returns:
            Dict with keys: docs_count, docs_deleted, store_size_bytes,
            store_size_human, indexing_total, search_total,
            refresh_total, flush_total, segments_count, error.
        """
        result: Dict[str, Any] = {
            "docs_count": 0,
            "docs_deleted": 0,
            "store_size_bytes": 0,
            "store_size_human": "",
            "indexing_total": 0,
            "search_total": 0,
            "search_fetch_total": 0,
            "refresh_total": 0,
            "flush_total": 0,
            "segments_count": 0,
            "error": None,
        }
        try:
            client = self._get_client()
            resp = client.indices.stats(index=index, request_timeout=DEFAULT_REQUEST_TIMEOUT)
            total = resp.get("_all", {}).get("total", {})
            docs = total.get("docs", {})
            store = total.get("store", {})
            indexing = total.get("indexing", {})
            search = total.get("search", {})
            segments = total.get("segments", {})

            result.update({
                "docs_count": docs.get("count", 0),
                "docs_deleted": docs.get("deleted", 0),
                "store_size_bytes": store.get("size_in_bytes", 0),
                "store_size_human": _bytes_to_human(store.get("size_in_bytes", 0)),
                "indexing_total": indexing.get("index_total", 0),
                "search_total": search.get("query_total", 0),
                "search_fetch_total": search.get("fetch_total", 0),
                "refresh_total": total.get("refresh", {}).get("total", 0),
                "flush_total": total.get("flush", {}).get("total", 0),
                "segments_count": segments.get("count", 0),
            })
            logger.debug("Index stats for %s: %d docs", index, result["docs_count"])
        except NotFoundError:
            result["error"] = f"Index not found: {index}"
            logger.warning("get_index_stats: index not found: %s", index)
        except Exception as exc:
            result["error"] = str(exc)
            logger.error("get_index_stats failed for %s: %s", index, exc)
        return result

    def get_index_mapping(
        self,
        index: str,
        *,
        include_raw: bool = False,
    ) -> Dict[str, Any]:
        """
        Retrieve and flatten field mappings for an index or pattern.

        Args:
            index:       ES index name or pattern.
            include_raw: If True, also return the raw mapping under key ``_raw``.

        Returns:
            Dict of ``field_name → ES_type_string``.
            If include_raw=True, also contains ``_raw`` with the full mapping.
        """
        flat: Dict[str, str] = {}
        try:
            client = self._get_client()
            resp = client.indices.get_mapping(index=index, request_timeout=30)
            raw_mapping: Dict[str, Any] = {}
            for _idx, mapping_data in resp.items():
                props = mapping_data.get("mappings", {}).get("properties", {})
                _flatten_mapping(props, flat, prefix="")
                if include_raw:
                    raw_mapping[_idx] = mapping_data.get("mappings", {})

            if include_raw:
                flat["_raw"] = raw_mapping  # type: ignore[assignment]

            logger.debug("Mapping for %s: %d fields", index, len(flat))
        except NotFoundError:
            logger.warning("get_index_mapping: index not found: %s", index)
        except Exception as exc:
            logger.error("get_index_mapping failed for %s: %s", index, exc)
        return flat

    def get_field_capabilities(
        self,
        index: str,
        fields: str = "*",
    ) -> Dict[str, Dict[str, Any]]:
        """
        Use the field_caps API to get field types across multiple indices.

        Unlike get_index_mapping, this works correctly across alias-backed
        indices and returns the union of field types.

        Args:
            index:  Index pattern.
            fields: Comma-separated field list or ``*`` for all.

        Returns:
            Dict of field_name → {type: str, searchable: bool, aggregatable: bool}.
        """
        result: Dict[str, Dict[str, Any]] = {}
        try:
            client = self._get_client()
            resp = client.field_caps(
                index=index,
                fields=fields,
                request_timeout=DEFAULT_REQUEST_TIMEOUT,
            )
            for field_name, type_map in resp.get("fields", {}).items():
                # Take the first type (usually there's only one)
                for es_type, meta in type_map.items():
                    result[field_name] = {
                        "type": es_type,
                        "searchable": meta.get("searchable", False),
                        "aggregatable": meta.get("aggregatable", False),
                        "metadata_field": meta.get("metadata_field", False),
                    }
                    break
            logger.debug("Field capabilities for %s: %d fields", index, len(result))
        except Exception as exc:
            logger.error("get_field_capabilities failed for %s: %s", index, exc)
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Search Methods
    # ──────────────────────────────────────────────────────────────────────────

    def search(
        self,
        index: str,
        body: Dict[str, Any],
        *,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
        enforce_size_limit: bool = True,
        track_total_hits: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a search query with safety checks.

        Args:
            index:              ES index pattern.
            body:               Elasticsearch Query DSL body.
            request_timeout:    Request timeout in seconds.
            enforce_size_limit: Raise ESSafetyError if body["size"] > MAX_SAFE_SIZE.
            track_total_hits:   Set to False to speed up queries where exact
                                count is not needed (ES 7+ behaviour).

        Returns:
            Raw ES response as a dict (hits, aggregations, etc.).

        Raises:
            ESSafetyError: If size limit is exceeded.
            ESQueryError:  If ES rejects the query (bad DSL).
            ESClientError: On unrecoverable transport errors.
        """
        requested_size = body.get("size", 10)
        if enforce_size_limit and requested_size > MAX_SAFE_SIZE:
            raise ESSafetyError(
                f"Requested size={requested_size} exceeds MAX_SAFE_SIZE={MAX_SAFE_SIZE}. "
                "Use aggregations or scroll_search() for large result sets."
            )

        body = dict(body)
        if track_total_hits and "track_total_hits" not in body:
            body["track_total_hits"] = True

        @self._make_retry()
        def _execute() -> Dict[str, Any]:
            client = self._get_client()
            t0 = time.monotonic()
            resp = client.search(index=index, body=body, request_timeout=request_timeout)
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            logger.debug("ES search: index=%s size=%s latency=%.1fms", index, requested_size, elapsed)
            return dict(resp)

        try:
            return _execute()
        except BadRequestError as exc:
            raise ESQueryError(f"Bad query DSL: {exc}") from exc
        except (ESConnectionError, ConnectionTimeout, TransportError) as exc:
            raise ESClientError(f"ES search transport error: {exc}") from exc
        except RetryError as exc:
            raise ESClientError(f"ES search failed after retries: {exc}") from exc

    def aggregate(
        self,
        index: str,
        body: Dict[str, Any],
        *,
        request_timeout: int = AGG_REQUEST_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Execute an aggregation query with size=0 enforced.

        Args:
            index:           ES index pattern.
            body:            Query DSL body (must contain ``aggs`` key).
            request_timeout: Timeout in seconds.

        Returns:
            The ``aggregations`` dict from the ES response.
        """
        body = dict(body)
        body["size"] = 0  # Enforce: we want agg results only, no hits

        @self._make_retry()
        def _execute() -> Dict[str, Any]:
            client = self._get_client()
            t0 = time.monotonic()
            resp = client.search(index=index, body=body, request_timeout=request_timeout)
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            logger.debug("ES aggregate: index=%s latency=%.1fms", index, elapsed)
            return dict(resp).get("aggregations", {})

        try:
            return _execute()
        except BadRequestError as exc:
            raise ESQueryError(f"Bad aggregation DSL: {exc}") from exc
        except (ESConnectionError, ConnectionTimeout, TransportError) as exc:
            raise ESClientError(f"ES aggregate transport error: {exc}") from exc
        except RetryError as exc:
            raise ESClientError(f"ES aggregate failed after retries: {exc}") from exc

    def count(
        self,
        index: str,
        query: Optional[Dict[str, Any]] = None,
        *,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ) -> int:
        """
        Return the document count matching a query.

        Args:
            index:   ES index pattern.
            query:   Optional ``query`` dict (defaults to match_all).

        Returns:
            Integer document count, or 0 on error.
        """
        body: Dict[str, Any] = {"query": query or {"match_all": {}}}

        @self._make_retry()
        def _execute() -> int:
            client = self._get_client()
            resp = client.count(index=index, body=body, request_timeout=request_timeout)
            return int(resp.get("count", 0))

        try:
            return _execute()
        except Exception as exc:
            logger.error("ES count failed for %s: %s", index, exc)
            raise ESClientError(f"ES count failed: {exc}") from exc

    def msearch(
        self,
        searches: List[Tuple[Dict[str, Any], Dict[str, Any]]],
        index: Optional[str] = None,
        *,
        request_timeout: int = AGG_REQUEST_TIMEOUT,
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple search requests in a single round-trip (msearch).

        Args:
            searches: List of (header_dict, body_dict) tuples.
                      header_dict may contain ``index``, ``search_type``, etc.
            index:    Default index if not specified in header.
            request_timeout: Per-request timeout.

        Returns:
            List of individual response dicts (same order as input searches).

        Example:
            results = client.msearch([
                ({"index": "logs-*"}, {"size": 0, "aggs": {...}}),
                ({"index": "logs-*"}, {"size": 0, "aggs": {...}}),
            ])
        """
        if not searches:
            return []

        body_lines: List[Dict[str, Any]] = []
        for header, search_body in searches:
            h = dict(header)
            if index and "index" not in h:
                h["index"] = index
            body_lines.append(h)
            body_lines.append(dict(search_body))

        try:
            client = self._get_client()
            t0 = time.monotonic()
            resp = client.msearch(body=body_lines, request_timeout=request_timeout)
            elapsed = round((time.monotonic() - t0) * 1000, 1)
            logger.debug("msearch: %d queries, latency=%.1fms", len(searches), elapsed)
            return [dict(r) for r in resp.get("responses", [])]
        except Exception as exc:
            logger.error("msearch failed: %s", exc)
            raise ESClientError(f"msearch failed: {exc}") from exc

    def validate_query(
        self,
        index: str,
        query: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate a query DSL without executing it.

        Returns:
            Dict with keys: valid (bool), explanation (str), error (str | None).
        """
        result: Dict[str, Any] = {"valid": False, "explanation": "", "error": None}
        try:
            client = self._get_client()
            resp = client.indices.validate_query(
                index=index,
                body={"query": query},
                explain=True,
                request_timeout=10,
            )
            result["valid"] = bool(resp.get("valid", False))
            result["explanation"] = resp.get("explanations", [{}])[0].get("explanation", "")
            logger.debug("Query validation: valid=%s", result["valid"])
        except Exception as exc:
            result["error"] = str(exc)
            logger.error("validate_query failed: %s", exc)
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Streaming / Pagination Methods
    # ──────────────────────────────────────────────────────────────────────────

    def scroll_search(
        self,
        index: str,
        body: Dict[str, Any],
        *,
        batch_size: Optional[int] = None,
        max_docs: Optional[int] = None,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Memory-safe scroll iterator — yields batches of hit dicts.

        ⚠ Use only for batch exports, NOT for analytics. For analytics,
          always use aggregate() with aggregation DSL.

        Args:
            index:           ES index pattern.
            body:            Query DSL body (size will be overridden).
            batch_size:      Documents per batch (default: settings.batch_size).
            max_docs:        Optional hard ceiling on total documents yielded.
            request_timeout: Per-request timeout.

        Yields:
            List of hit dicts per scroll page.
        """
        _batch_size = batch_size or settings.batch_size
        body = dict(body)
        body["size"] = _batch_size

        client = self._get_client()
        scroll_id: Optional[str] = None
        total_yielded = 0

        try:
            resp = client.search(
                index=index,
                body=body,
                scroll=settings.scroll_keepalive,
                request_timeout=request_timeout,
            )
            scroll_id = resp.get("_scroll_id")
            hits = resp.get("hits", {}).get("hits", [])

            while hits:
                if max_docs is not None:
                    hits = hits[:max_docs - total_yielded]

                yield hits
                total_yielded += len(hits)
                logger.debug("scroll_search: yielded %d docs (total=%d)", len(hits), total_yielded)

                if max_docs is not None and total_yielded >= max_docs:
                    logger.info("scroll_search: max_docs=%d reached.", max_docs)
                    break

                resp = client.scroll(
                    scroll_id=scroll_id,
                    scroll=settings.scroll_keepalive,
                    request_timeout=request_timeout,
                )
                scroll_id = resp.get("_scroll_id")
                hits = resp.get("hits", {}).get("hits", [])

        except Exception as exc:
            logger.error("scroll_search error: %s", exc)
            raise ESClientError(f"scroll_search failed: {exc}") from exc
        finally:
            if scroll_id:
                try:
                    client.clear_scroll(scroll_id=scroll_id)
                    logger.debug("Scroll context cleared.")
                except Exception:
                    pass

    def search_after(
        self,
        index: str,
        body: Dict[str, Any],
        sort_field: str,
        *,
        batch_size: Optional[int] = None,
        max_docs: Optional[int] = None,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Memory-safe search_after iterator (preferred over scroll for deep pagination).

        search_after uses a stateless cursor based on the sort value of the
        last document in the previous page, which is more efficient than
        scroll for large datasets.

        Args:
            index:       ES index pattern.
            body:        Query DSL body (must NOT contain ``from``).
            sort_field:  Primary sort field (e.g. ``@timestamp``).
            batch_size:  Documents per page.
            max_docs:    Optional ceiling on total documents yielded.

        Yields:
            List of hit dicts per page.
        """
        _batch_size = batch_size or settings.batch_size
        body = dict(body)
        body["size"] = _batch_size
        body.setdefault("sort", [{sort_field: {"order": "asc"}}])
        # Remove conflicting keys
        body.pop("from", None)
        body.pop("search_after", None)

        client = self._get_client()
        total_yielded = 0
        cursor: Optional[List[Any]] = None

        while True:
            if cursor is not None:
                body["search_after"] = cursor

            try:
                resp = client.search(index=index, body=body, request_timeout=request_timeout)
            except Exception as exc:
                logger.error("search_after error: %s", exc)
                raise ESClientError(f"search_after failed: {exc}") from exc

            hits = resp.get("hits", {}).get("hits", [])
            if not hits:
                break

            if max_docs is not None:
                hits = hits[:max_docs - total_yielded]

            yield hits
            total_yielded += len(hits)
            logger.debug("search_after: yielded page of %d (total=%d)", len(hits), total_yielded)

            if max_docs is not None and total_yielded >= max_docs:
                break

            cursor = hits[-1].get("sort")
            if not cursor:
                break

    # ──────────────────────────────────────────────────────────────────────────
    # Diagnostic helpers (used by the Diagnostics page)
    # ──────────────────────────────────────────────────────────────────────────

    def run_connectivity_suite(self) -> Dict[str, Any]:
        """
        Run a comprehensive connectivity + auth + search diagnostic suite.

        Returns structured results for each test. Safe to display in UI
        (no credentials included in output).
        """
        results: Dict[str, Any] = {
            "ping": {"passed": False, "latency_ms": None, "detail": ""},
            "auth": {"passed": False, "detail": ""},
            "health": {"passed": False, "status": "unknown", "detail": ""},
            "index_list": {"passed": False, "count": 0, "detail": ""},
            "target_index": {"passed": False, "doc_count": 0, "detail": ""},
        }

        # 1. Ping
        try:
            t0 = time.monotonic()
            reachable = self.ping()
            latency = round((time.monotonic() - t0) * 1000, 1)
            results["ping"] = {
                "passed": reachable,
                "latency_ms": latency,
                "detail": f"Host {settings.es_host}:{settings.es_port} is {'reachable' if reachable else 'unreachable'}",
            }
        except Exception as exc:
            results["ping"]["detail"] = str(exc)

        if not results["ping"]["passed"]:
            for key in ["auth", "health", "index_list", "target_index"]:
                results[key]["detail"] = "Skipped — host unreachable"
            return results

        # 2. Auth
        try:
            auth = self.validate_credentials()
            results["auth"] = {
                "passed": auth["authenticated"],
                "detail": auth.get("error") or f"Authenticated as '{auth['username']}'",
            }
        except Exception as exc:
            results["auth"]["detail"] = str(exc)

        # 3. Cluster health
        try:
            health = self.health_check()
            results["health"] = {
                "passed": health["connected"],
                "status": health.get("status", "unknown"),
                "detail": health.get("error") or f"Cluster status: {health.get('status', 'unknown')}",
                "response_time_ms": health.get("response_time_ms"),
            }
        except Exception as exc:
            results["health"]["detail"] = str(exc)

        # 4. Index list
        try:
            indices = self.list_indices(pattern="*")
            results["index_list"] = {
                "passed": True,
                "count": len(indices),
                "detail": f"Found {len(indices)} accessible indices",
            }
        except Exception as exc:
            results["index_list"]["detail"] = str(exc)

        # 5. Target index
        try:
            cnt = self.count(index=settings.es_index_pattern)
            results["target_index"] = {
                "passed": True,
                "doc_count": cnt,
                "detail": f"Index '{settings.es_index_pattern}' contains {cnt:,} documents",
            }
        except Exception as exc:
            results["target_index"]["detail"] = str(exc)

        return results


# ─── Module-level helpers ─────────────────────────────────────────────────────

def _flatten_mapping(
    props: Dict[str, Any],
    result: Dict[str, str],
    prefix: str,
    max_depth: int = 8,
) -> None:
    """Recursively flatten ES mapping properties into a flat ``field → type`` dict."""
    if max_depth <= 0:
        return
    for field_name, field_data in props.items():
        full_name = f"{prefix}.{field_name}" if prefix else field_name
        field_type = field_data.get("type", "object")
        result[full_name] = field_type
        sub_props = field_data.get("properties", {})
        if sub_props:
            _flatten_mapping(sub_props, result, prefix=full_name, max_depth=max_depth - 1)


def _bytes_to_human(num_bytes: int) -> str:
    """Convert bytes to a human-readable string (KB/MB/GB/TB)."""
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} EB"
