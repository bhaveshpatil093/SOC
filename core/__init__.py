"""
core/__init__.py

Core layer — local-data-only mode.
All Elasticsearch references removed.
"""

from core.log_retriever import LogRetriever, LogFilter
from core.preprocessing import (
    PreprocessingPipeline,
    PipelineConfig,
    PipelineResult,
    BatchQualityReport,
)
from core.sigma_engine import SigmaDetectionEngine, DetectionReport
from core.threat_scorer import ThreatScoringEngine, ThreatContext
from core.local_data_client import get_local_data_client, _get_file_fingerprint


def get_es_client():
    """Stub — Elasticsearch removed. Returns None."""
    return None


def get_cache():
    """Stub — returns None."""
    return None


__all__ = [
    "LogRetriever",
    "LogFilter",
    "get_es_client",
    "get_cache",
    "get_local_data_client",
    "_get_file_fingerprint",
]
