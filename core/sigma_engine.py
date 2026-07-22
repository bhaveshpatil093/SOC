"""
core/sigma_engine.py

Sigma Detection Engine for batch-scoped execution.

Evaluates Sigma rules dynamically against a specifically retrieved batch of logs
by utilizing Elasticsearch's _msearch API with _id filtering. This ensures 100%
accuracy based on Elasticsearch's evaluation logic, without loading or scanning
data outside the provided batch.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

import pandas as pd

from config import get_logger, settings
from core.elasticsearch_client import ElasticsearchClient
from utils.sigma_utils import SigmaRuleInfo

logger = get_logger(__name__)


@dataclass
class DetectionMatch:
    """Represents a single log that matched one or more Sigma rules."""
    doc_id: str
    doc_index: str
    raw_source: Dict[str, Any]
    matched_rules: List[SigmaRuleInfo] = field(default_factory=list)


@dataclass
class DetectionReport:
    """Summary of a Sigma batch evaluation execution."""
    input_hits: int = 0
    matched_hits: int = 0
    total_rule_triggers: int = 0
    elapsed_ms: float = 0.0

    # Rule-level stats
    triggered_rules: List[SigmaRuleInfo] = field(default_factory=list)
    rule_trigger_counts: Dict[str, int] = field(default_factory=dict)
    
    # Enrichments
    severity_distribution: Dict[str, int] = field(default_factory=dict)
    mitre_tactics: Dict[str, int] = field(default_factory=dict)
    affected_hosts: Dict[str, int] = field(default_factory=dict)
    affected_users: Dict[str, int] = field(default_factory=dict)

    # Detailed matches
    matches: List[DetectionMatch] = field(default_factory=list)


class SigmaDetectionEngine:
    """
    Executes Sigma rules against batches of pre-retrieved logs.
    """

    def __init__(self, es_client: ElasticsearchClient):
        self.es = es_client

    def evaluate_batch(
        self,
        batch_hits: List[Dict[str, Any]],
        rules: List[SigmaRuleInfo]
    ) -> DetectionReport:
        """
        Evaluate a list of rules against a specific batch of hits.

        Args:
            batch_hits: List of ES hits (must contain _id and _index).
            rules: List of convertible SigmaRuleInfo objects.

        Returns:
            DetectionReport with detailed statistics and matches.
        """
        t0 = time.monotonic()
        report = DetectionReport(input_hits=len(batch_hits))
        
        if not batch_hits or not rules:
            return report

        # 1. Filter to convertible rules
        active_rules = [r for r in rules if r.is_convertible and r.es_query]
        if not active_rules:
            logger.warning("No convertible rules provided to evaluate_batch.")
            return report

        # 2. Extract batch _ids grouped by index (in case batch spans indices)
        index_to_ids = defaultdict(list)
        hit_map = {}  # _id -> full hit dict
        
        for hit in batch_hits:
            doc_id = hit.get("_id")
            doc_index = hit.get("_index", settings.es_index_pattern)
            if doc_id:
                index_to_ids[doc_index].append(doc_id)
                hit_map[doc_id] = hit

        if not hit_map:
            logger.warning("Batch hits did not contain _id fields.")
            return report

        # 3. Construct _msearch payload
        msearch_body = []
        # Mapping from msearch response index to (doc_index, rule)
        request_map: List[Tuple[str, SigmaRuleInfo]] = []

        for doc_index, doc_ids in index_to_ids.items():
            for rule in active_rules:
                req_head = {"index": doc_index}
                req_body = {
                    "query": {
                        "bool": {
                            "filter": [{"terms": {"_id": doc_ids}}],
                            "must": [rule.es_query]
                        }
                    },
                    "_source": False,  # We only need _id, we already have the source
                    "size": len(doc_ids)
                }
                msearch_body.append(req_head)
                msearch_body.append(req_body)
                request_map.append((doc_index, rule))

        # 4. Execute _msearch
        try:
            msearch_res = self.es.client.msearch(body=msearch_body)
        except Exception as exc:
            logger.error("Sigma batch evaluation msearch failed: %s", exc)
            return report
            
        responses = msearch_res.get("responses", [])
        
        # 5. Process responses
        # Map of doc_id -> set of matched rule_ids
        match_registry = defaultdict(set)
        rule_map = {r.rule_id: r for r in active_rules}
        
        for idx, res in enumerate(responses):
            doc_index, rule = request_map[idx]
            
            if "error" in res:
                logger.warning(f"Error evaluating rule {rule.title}: {res['error']}")
                continue
                
            hits = res.get("hits", {}).get("hits", [])
            for h in hits:
                doc_id = h.get("_id")
                if doc_id:
                    match_registry[doc_id].add(rule.rule_id)
                    report.total_rule_triggers += 1
                    report.rule_trigger_counts[rule.rule_id] = report.rule_trigger_counts.get(rule.rule_id, 0) + 1

        # 6. Build the Detection Report
        report.matched_hits = len(match_registry)
        
        # Identify triggered rules
        triggered_rule_ids = set(report.rule_trigger_counts.keys())
        report.triggered_rules = [rule_map[rid] for rid in triggered_rule_ids]
        
        # Aggregate stats
        for doc_id, matched_rule_ids in match_registry.items():
            hit = hit_map[doc_id]
            source = hit.get("_source", {})
            
            matched_rule_objs = [rule_map[rid] for rid in matched_rule_ids]
            report.matches.append(DetectionMatch(
                doc_id=doc_id,
                doc_index=hit.get("_index", ""),
                raw_source=source,
                matched_rules=matched_rule_objs
            ))
            
            # Severity (take max severity of matched rules)
            severities = [r.severity for r in matched_rule_objs]
            # Simple priority order
            priority = {"critical": 4, "high": 3, "medium": 2, "low": 1, "informational": 0, "unknown": -1}
            max_sev = max(severities, key=lambda s: priority.get(s.lower(), -1))
            report.severity_distribution[max_sev] = report.severity_distribution.get(max_sev, 0) + 1
            
            # MITRE tags
            for r in matched_rule_objs:
                for tag in r.tags:
                    if tag.startswith("attack."):
                        tactic = tag.replace("attack.", "")
                        report.mitre_tactics[tactic] = report.mitre_tactics.get(tactic, 0) + 1
                        
            # Host/User enrichment
            host = self._extract_field(source, settings.es_hostname_field)
            user = self._extract_field(source, settings.es_username_field)
            if host:
                report.affected_hosts[host] = report.affected_hosts.get(host, 0) + 1
            if user:
                report.affected_users[user] = report.affected_users.get(user, 0) + 1

        report.elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        return report

    def _extract_field(self, source: Dict[str, Any], field_path: str) -> Any:
        """Helper to extract a nested field from a dict using dot notation."""
        parts = field_path.split(".")
        val = source
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return None
        return str(val) if val is not None else None
