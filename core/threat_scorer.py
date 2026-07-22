"""
core/threat_scorer.py

Unified Threat Scoring Engine.

Combines Sigma rule severities, ML anomaly scores, and behavioral context
into a normalized 0-100 threat score. Generates human-readable explanations
for why an event was flagged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from config import get_logger
from core.sigma_engine import DetectionReport

logger = get_logger(__name__)


@dataclass
class ThreatContext:
    """Represents a unified scored event."""
    doc_id: str
    timestamp: str
    threat_score: int
    risk_level: str  # Critical, High, Medium, Low, Info
    explanation: str
    sigma_score: int = 0
    ml_score: int = 0
    ml_raw: float = 0.0
    sigma_matches: List[str] = field(default_factory=list)
    raw_source: Dict[str, Any] = field(default_factory=dict)


class ThreatScoringEngine:
    """
    Combines rule-based and ML detections into a unified score.
    """

    def __init__(self, ml_threshold: float = 0.7):
        """
        Args:
            ml_threshold: Minimum ML anomaly score to contribute significantly.
        """
        self.ml_threshold = ml_threshold
        # Sigma severity weights
        self.sigma_weights = {
            "critical": 80,
            "high": 60,
            "medium": 40,
            "low": 20,
            "informational": 10,
            "unknown": 0
        }

    def score_batch(
        self,
        raw_hits: List[Dict[str, Any]],
        sigma_report: DetectionReport,
        ml_scored_df: pd.DataFrame
    ) -> List[ThreatContext]:
        """
        Generates unified threat scores for a batch.

        Assumes ml_scored_df aligns 1:1 with raw_hits OR ml_scored_df contains
        an '_id' column.

        Args:
            raw_hits: Original ES hits.
            sigma_report: Sigma detection results for the batch.
            ml_scored_df: Dataframe with 'anomaly_score' and ideally '_id'.

        Returns:
            List of ThreatContext objects, sorted by descending threat score.
        """
        # 1. Map Sigma matches by _id
        sigma_map = {}
        for match in sigma_report.matches:
            sigma_map[match.doc_id] = match

        # 2. Extract ML scores
        ml_map = {}
        if "_id" in ml_scored_df.columns:
            for _, row in ml_scored_df.iterrows():
                ml_map[row["_id"]] = float(row.get("anomaly_score", 0.0))
        else:
            # Fallback: assume 1:1 alignment
            if len(ml_scored_df) == len(raw_hits):
                for idx, row in ml_scored_df.iterrows():
                    doc_id = raw_hits[idx].get("_id")
                    ml_map[doc_id] = float(row.get("anomaly_score", 0.0))
            else:
                logger.warning("ml_scored_df does not have _id and row counts do not match raw_hits.")

        # 3. Calculate scores
        results: List[ThreatContext] = []
        
        for hit in raw_hits:
            doc_id = hit.get("_id", "unknown")
            source = hit.get("_source", {})
            timestamp = source.get("@timestamp", "N/A")

            ml_raw = ml_map.get(doc_id, 0.0)
            sigma_match = sigma_map.get(doc_id)
            
            # Compute Sigma component
            s_score = 0
            s_matches = []
            if sigma_match and sigma_match.matched_rules:
                # Take highest severity rule
                severities = [r.severity.lower() for r in sigma_match.matched_rules]
                max_sev = max(severities, key=lambda s: self.sigma_weights.get(s, 0))
                s_score = self.sigma_weights.get(max_sev, 0)
                s_matches = [r.title for r in sigma_match.matched_rules]

            # Compute ML component
            # ML contributes 0-40 points if above threshold, maxing out at 1.0
            m_score = 0
            if ml_raw >= self.ml_threshold:
                # Scale threshold..1.0 to 0..40
                pct_above = (ml_raw - self.ml_threshold) / (1.0 - self.ml_threshold + 1e-9)
                m_score = int(pct_above * 40)
                
            # Combine and cap at 100
            total_score = min(100, s_score + m_score)
            
            # Risk level
            if total_score >= 80:
                risk = "Critical"
            elif total_score >= 60:
                risk = "High"
            elif total_score >= 40:
                risk = "Medium"
            elif total_score >= 20:
                risk = "Low"
            else:
                risk = "Info"

            # Skip events that scored 0 if we only want flagged ones,
            # but let's keep everything > 0 for investigation.
            if total_score > 0:
                explanation = self._generate_explanation(s_score, s_matches, m_score, ml_raw, total_score)
                results.append(
                    ThreatContext(
                        doc_id=doc_id,
                        timestamp=timestamp,
                        threat_score=total_score,
                        risk_level=risk,
                        explanation=explanation,
                        sigma_score=s_score,
                        ml_score=m_score,
                        ml_raw=ml_raw,
                        sigma_matches=s_matches,
                        raw_source=source
                    )
                )

        # Sort highest threat first
        results.sort(key=lambda x: x.threat_score, reverse=True)
        return results

    def _generate_explanation(
        self, s_score: int, s_matches: List[str], m_score: int, ml_raw: float, total: int
    ) -> str:
        """Rule-based natural language explainer."""
        parts = []
        if s_score > 0:
            sev_str = "Critical" if s_score == 80 else "High" if s_score == 60 else "Medium" if s_score == 40 else "Low"
            rules_str = ", ".join(s_matches)
            parts.append(f"matched {sev_str}-severity Sigma rules ({rules_str}) contributing {s_score} pts")
            
        if m_score > 0:
            parts.append(f"exhibited high behavioral anomaly (score: {ml_raw:.2f}) contributing {m_score} pts")
            
        if not parts:
            return "No significant threat detected."
            
        reason = " and ".join(parts)
        return f"Flagged with score {total}/100 because the event {reason}."
