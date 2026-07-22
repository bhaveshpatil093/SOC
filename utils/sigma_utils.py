"""
utils/sigma_utils.py

pySigma integration helpers for the ISRO SOC Analytics platform.

Provides:
  - Loading Sigma rules from YAML files
  - Converting Sigma rules to Elasticsearch Query DSL
  - Rule validation and metadata extraction

Usage:
    from utils import SigmaUtils

    rules = SigmaUtils.load_rules_from_dir(Path("rules/"))
    es_query = SigmaUtils.rule_to_es_query(rule)
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import get_logger

logger = get_logger(__name__)


class SigmaRuleInfo:
    """Lightweight metadata container for a loaded Sigma rule."""

    def __init__(
        self,
        title: str,
        rule_id: str,
        description: str,
        severity: str,
        status: str,
        tags: List[str],
        source_path: Optional[Path],
        raw_yaml: str,
        es_query: Optional[Dict[str, Any]] = None,
        conversion_error: Optional[str] = None,
    ) -> None:
        self.title = title
        self.rule_id = rule_id
        self.description = description
        self.severity = severity
        self.status = status
        self.tags = tags
        self.source_path = source_path
        self.raw_yaml = raw_yaml
        self.es_query = es_query
        self.conversion_error = conversion_error

    @property
    def is_convertible(self) -> bool:
        return self.es_query is not None and self.conversion_error is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "id": self.rule_id,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "tags": ", ".join(self.tags),
            "source": str(self.source_path) if self.source_path else "",
            "convertible": self.is_convertible,
            "conversion_error": self.conversion_error or "",
        }


class SigmaUtils:
    """
    Utilities for loading, validating, and converting Sigma rules.

    pySigma and the Elasticsearch backend are imported lazily so the app
    can start even if those optional packages are not installed.
    """

    _sigma_available: Optional[bool] = None  # cached availability check

    @classmethod
    def is_sigma_available(cls) -> bool:
        """Check whether pySigma and its ES backend are installed."""
        if cls._sigma_available is not None:
            return cls._sigma_available
        try:
            import sigma  # noqa: F401
            from sigma.backends.elasticsearch import LuceneBackend  # noqa: F401
            cls._sigma_available = True
        except ImportError:
            cls._sigma_available = False
            logger.warning(
                "pySigma or pysigma-backend-elasticsearch is not installed. "
                "Sigma rule features will be disabled."
            )
        return cls._sigma_available

    @classmethod
    def load_rule_from_yaml(cls, yaml_content: str, source_path: Optional[Path] = None) -> SigmaRuleInfo:
        """
        Parse a YAML string as a Sigma rule.

        Args:
            yaml_content: Raw YAML text of the rule.
            source_path:  Optional path for error messages.

        Returns:
            SigmaRuleInfo with metadata and optional ES query.
        """
        title = "Unknown"
        rule_id = ""
        description = ""
        severity = "unknown"
        status = "unknown"
        tags: List[str] = []
        es_query: Optional[Dict[str, Any]] = None
        conversion_error: Optional[str] = None

        try:
            import yaml
            data = yaml.safe_load(yaml_content)
            if not isinstance(data, dict):
                raise ValueError("Rule YAML must be a mapping")

            title = data.get("title", "Unknown")
            rule_id = str(data.get("id", ""))
            description = data.get("description", "")
            severity = data.get("level", "unknown")
            status = data.get("status", "unknown")
            tags = data.get("tags", []) or []
        except Exception as exc:
            logger.warning("YAML parse error for %s: %s", source_path, exc)
            conversion_error = f"YAML parse error: {exc}"

        # Attempt ES conversion
        if cls.is_sigma_available() and conversion_error is None:
            es_query, conversion_error = cls._convert_to_es(yaml_content)

        return SigmaRuleInfo(
            title=title,
            rule_id=rule_id,
            description=description,
            severity=severity,
            status=status,
            tags=tags,
            source_path=source_path,
            raw_yaml=yaml_content,
            es_query=es_query,
            conversion_error=conversion_error,
        )

    @classmethod
    def load_rules_from_dir(cls, rules_dir: Path) -> List[SigmaRuleInfo]:
        """
        Load all .yml / .yaml Sigma rules from a directory (non-recursive).

        Args:
            rules_dir: Path to directory containing Sigma rule YAML files.

        Returns:
            List of SigmaRuleInfo objects.
        """
        rules: List[SigmaRuleInfo] = []
        if not rules_dir.exists():
            logger.info("Rules directory does not exist: %s", rules_dir)
            return rules

        for rule_file in sorted(rules_dir.glob("*.y*ml")):
            try:
                yaml_content = rule_file.read_text(encoding="utf-8")
                rule = cls.load_rule_from_yaml(yaml_content, source_path=rule_file)
                rules.append(rule)
                logger.debug("Loaded Sigma rule: %s (%s)", rule.title, rule_file.name)
            except Exception as exc:
                logger.error("Failed to load rule %s: %s", rule_file, exc)

        logger.info("Loaded %d Sigma rules from %s", len(rules), rules_dir)
        return rules

    @classmethod
    def rule_to_es_query(cls, rule: SigmaRuleInfo) -> Optional[Dict[str, Any]]:
        """
        Return the ES query dict from a SigmaRuleInfo.

        Returns None if the rule was not successfully converted.
        """
        return rule.es_query

    @classmethod
    def _convert_to_es(cls, yaml_content: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Internal: convert Sigma YAML to ES Lucene query dict.

        Returns:
            (es_query_dict, error_string) — one of these will be None.
        """
        try:
            from sigma.collection import SigmaCollection
            from sigma.backends.elasticsearch import LuceneBackend

            collection = SigmaCollection.from_yaml(yaml_content)
            backend = LuceneBackend()
            queries = backend.convert(collection)

            if queries:
                # LuceneBackend returns Lucene query strings; wrap in query_string
                lucene_str = queries[0] if isinstance(queries[0], str) else str(queries[0])
                es_query = {"query_string": {"query": lucene_str, "default_field": "*"}}
                return es_query, None
            else:
                return None, "Backend produced no output"

        except Exception as exc:
            tb = traceback.format_exc()
            logger.debug("Sigma conversion traceback:\n%s", tb)
            return None, f"Conversion error: {exc}"

    @staticmethod
    def rules_to_dataframe(rules: List[SigmaRuleInfo]) -> "pd.DataFrame":  # noqa: F821
        """Convert a list of SigmaRuleInfo objects to a Pandas DataFrame."""
        import pandas as pd
        return pd.DataFrame([r.to_dict() for r in rules])
