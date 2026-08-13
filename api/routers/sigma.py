from fastapi import APIRouter
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List

from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records
from utils.sigma_utils import SigmaUtils, SigmaRuleInfo

router = APIRouter(prefix="/api/v1/sigma", tags=["sigma"])

# Caching loaded rules
_cached_rules: List[SigmaRuleInfo] = []
def get_sigma_rules():
    global _cached_rules
    if not _cached_rules:
        root_dir = Path(__file__).parent.parent.parent
        rules_dir = root_dir / "rules"
        if rules_dir.exists():
            _cached_rules = SigmaUtils.load_rules_from_dir(rules_dir)
    return _cached_rules

def _evaluate_rules_locally(df: pd.DataFrame, rules: List[SigmaRuleInfo]):
    """
    Mock Sigma engine for local pandas dataframes based on YAML selection logic.
    Supports basic mapping of event.category, process.name, event.outcome.
    """
    results = []
    
    if df.empty:
        return results

    for rule in rules:
        # Very basic local python matching of Sigma logic
        # Read the raw_yaml manually to extract selection criteria since es_query isn't executable here
        import yaml
        try:
            r_dict = yaml.safe_load(rule.raw_yaml)
            selection = r_dict.get("detection", {}).get("selection", {})
        except Exception:
            selection = {}

        # Create boolean mask
        mask = pd.Series([True] * len(df), index=df.index)
        
        for key, val in selection.items():
            if key in df.columns:
                if isinstance(val, list):
                    mask = mask & df[key].isin(val)
                else:
                    mask = mask & (df[key] == val)
            else:
                # If field not in df, we can't match it, so false
                mask = mask & False

        # Additional condition check (just a crude hack for the example rules)
        if "filter_bytes" in r_dict.get("detection", {}):
            if "network.bytes" in df.columns:
                # hardcoded for Large Network Transfer
                mask = mask & (df["network.bytes"] > 1000000)

        matched_df = df[mask]
        
        if not matched_df.empty:
            for idx, row in matched_df.iterrows():
                results.append({
                    "rule": rule,
                    "event": row.to_dict()
                })
                
    return results

def get_sigma_execution_results():
    data = get_analytics_data()
    df_scored = data.get("scored_df", pd.DataFrame())
    rules = get_sigma_rules()
    
    # Run evaluation
    matches = _evaluate_rules_locally(df_scored, rules)
    return rules, matches

@router.get("/overview")
def get_sigma_overview():
    rules, matches = get_sigma_execution_results()
    
    unique_detections = len(matches)
    triggered_rules = len(set([m["rule"].rule_id for m in matches]))
    
    critical = 0
    high = 0
    for m in matches:
        if m["rule"].severity.lower() == "critical":
            critical += 1
        elif m["rule"].severity.lower() == "high":
            high += 1
            
    return {
        "totalRulesEvaluated": len(rules),
        "rulesTriggered": triggered_rules,
        "uniqueDetections": unique_detections,
        "criticalDetections": critical,
        "highDetections": high
    }

@router.get("/rules")
def get_sigma_rules_api():
    rules, matches = get_sigma_execution_results()
    
    rule_stats = {}
    for r in rules:
        mitre = [t for t in r.tags if t.startswith("attack.t")]
        rule_stats[r.rule_id] = {
            "id": r.rule_id,
            "title": r.title,
            "description": r.description,
            "severity": r.severity,
            "status": r.status,
            "mitre_technique": mitre[0].replace("attack.", "").upper() if mitre else None,
            "matches": 0,
            "last_match": None,
            "raw_yaml": r.raw_yaml,
            "affected_users": set(),
            "affected_hosts": set(),
            "first_seen": None
        }
        
    for m in matches:
        rid = m["rule"].rule_id
        rule_stats[rid]["matches"] += 1
        
        timestamp = m["event"].get("@timestamp")
        user = m["event"].get("user.name")
        host = m["event"].get("host.hostname")
        
        if timestamp:
            if not rule_stats[rid]["first_seen"] or timestamp < rule_stats[rid]["first_seen"]:
                rule_stats[rid]["first_seen"] = timestamp
            if not rule_stats[rid]["last_match"] or timestamp > rule_stats[rid]["last_match"]:
                rule_stats[rid]["last_match"] = timestamp
                
        if user and pd.notna(user):
            rule_stats[rid]["affected_users"].add(user)
        if host and pd.notna(host):
            rule_stats[rid]["affected_hosts"].add(host)
            
    # Serialize sets
    results = []
    for stat in rule_stats.values():
        stat["affected_users"] = list(stat["affected_users"])
        stat["affected_hosts"] = list(stat["affected_hosts"])
        results.append(stat)
        
    return results

@router.get("/coverage")
def get_sigma_coverage():
    rules, matches = get_sigma_execution_results()
    
    coverage = {}
    for r in rules:
        categories = [t for t in r.tags if not t.startswith("attack.t")]
        cat = categories[0].replace("attack.", "").title() if categories else "Other"
        
        if cat not in coverage:
            coverage[cat] = {"category": cat, "rules": 0, "detections": 0}
            
        coverage[cat]["rules"] += 1
        
    for m in matches:
        categories = [t for t in m["rule"].tags if not t.startswith("attack.t")]
        cat = categories[0].replace("attack.", "").title() if categories else "Other"
        coverage[cat]["detections"] += 1
        
    return list(coverage.values())
