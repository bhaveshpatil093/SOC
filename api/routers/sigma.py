from fastapi import APIRouter, Request
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List

from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records
from api.utils.filters import apply_global_filters
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
            import hashlib
            for idx, row in matched_df.iterrows():
                row_dict = row.to_dict()
                ts = str(row_dict.get("@timestamp", ""))
                user = str(row_dict.get("user.name", ""))
                host = str(row_dict.get("host.hostname", ""))
                rule_id = str(rule.rule_id)
                raw = f"{ts}{user}{host}{rule_id}"
                row_dict["_id"] = hashlib.md5(raw.encode()).hexdigest()
                
                results.append({
                    "rule": rule,
                    "event": row_dict
                })
                
    return results

@router.get("/events")
def get_sigma_events(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    sigma_matches = data.get("sigma_matches", pd.DataFrame())
    if sigma_matches.empty:
        return []
        
    sigma_matches = apply_global_filters(sigma_matches, dict(request.query_params))
        
    if "@timestamp" in sigma_matches.columns:
        sigma_matches["@timestamp"] = sigma_matches["@timestamp"].astype(str)
        
    sigma_matches["threat_score"] = 95.0
    
    events_list = _safe_records(sigma_matches.head(100))
    
    import hashlib
    for evt in events_list:
        ts = str(evt.get("@timestamp", ""))
        user = str(evt.get("user.name", ""))
        host = str(evt.get("host.hostname", ""))
        rule = str(evt.get("sigma_rule", ""))
        raw = f"{ts}{user}{host}{rule}"
        evt["_id"] = hashlib.md5(raw.encode()).hexdigest()
        
    return events_list

@router.get("/overview")
def get_sigma_overview(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    # Check if sigma matches were precomputed in scored_df, else fallback to standard
    sigma_matches = data.get("sigma_matches", pd.DataFrame())
    
    if not sigma_matches.empty:
        # We must filter the sigma_matches just like scored_df
        sigma_matches = apply_global_filters(sigma_matches, dict(request.query_params))
        
    rules_evaluated = 120 # static demo number
    
    if sigma_matches.empty:
        return {
            "rulesEvaluated": rules_evaluated,
            "rulesTriggered": 0,
            "uniqueDetections": 0,
            "criticalDetections": 0,
            "highDetections": 0
        }
        
    rules_triggered = int(sigma_matches["sigma_rule"].nunique()) if "sigma_rule" in sigma_matches.columns else 0
    unique_detections = len(sigma_matches)
    
    critical = 0
    high = 0
    if "threat_level" in sigma_matches.columns:
        critical = int((sigma_matches["threat_level"] == "Critical").sum())
        high = int((sigma_matches["threat_level"] == "High Threat").sum())
        
    return {
        "rulesEvaluated": rules_evaluated,
        "rulesTriggered": rules_triggered,
        "uniqueDetections": unique_detections,
        "criticalDetections": critical,
        "highDetections": high
    }

@router.get("/rules")
def get_sigma_rules_api():
    def get_sigma_execution_results():
        data = get_analytics_data()
        df_scored = data.get("scored_df", pd.DataFrame())
        rules = get_sigma_rules()
        
        # Run evaluation
        matches = _evaluate_rules_locally(df_scored, rules)
        return rules, matches
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
def get_sigma_coverage(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    sigma_matches = data.get("sigma_matches", pd.DataFrame())
    if sigma_matches.empty:
        return []
        
    sigma_matches = apply_global_filters(sigma_matches, dict(request.query_params))
        
    categories = {
        "Execution": 15,
        "Defense Evasion": 12,
        "Privilege Escalation": 8,
        "Credential Access": 10,
        "Discovery": 20,
        "Lateral Movement": 5,
        "Command and Control": 7
    }
    
    records = []
    for cat, rules in categories.items():
        # randomize active slightly based on matches
        active = min(rules, int(len(sigma_matches) * 0.05) + rules // 2)
        records.append({
            "category": cat,
            "rules": rules,
            "active": active
        })
        
    return records
