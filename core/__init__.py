"""
core/__init__.py

Exposes the primary singleton objects from the core layer so callers
can use short imports:

    from core import es_client, query_builder, cache
"""

from core.elasticsearch_client import ElasticsearchClient
from core.query_builder import QueryBuilder
from core.cache_manager import CacheManager
from core.es_diagnostics import DiagnosticsEngine
from core.log_retriever import LogRetriever, LogFilter
from core.preprocessing import (
    PreprocessingPipeline,
    PipelineConfig,
    PipelineResult,
    BatchQualityReport,
)
from core.sigma_engine import SigmaDetectionEngine, DetectionReport
from core.threat_scorer import ThreatScoringEngine, ThreatContext

# Lazy singletons — instantiated on first import
_es_client_instance: ElasticsearchClient | None = None
_cache_instance: CacheManager | None = None


def get_es_client() -> ElasticsearchClient:
    """Return the application-wide Elasticsearch client (singleton)."""
    global _es_client_instance
    if _es_client_instance is None:
        _es_client_instance = ElasticsearchClient()
    return _es_client_instance


def get_cache() -> CacheManager:
    """Return the application-wide cache manager (singleton)."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager()
    return _cache_instance


query_builder = QueryBuilder()

__all__ = [
    "ElasticsearchClient",
    "QueryBuilder",
    "CacheManager",
    "DiagnosticsEngine",
    "LogRetriever",
    "LogFilter",
    "get_es_client",
    "get_cache",
    "query_builder",
]
