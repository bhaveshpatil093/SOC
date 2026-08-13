from fastapi import APIRouter
from api.services.data_service import get_analytics_data
import pandas as pd

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

def _safe_records(df: pd.DataFrame):
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    # Fill NaN with None for JSON serialization
    return df.where(pd.notnull(df), None).to_dict(orient="records")

@router.get("/status")
def get_status():
    data = get_analytics_data()
    return {
        "status": "online" if "error" not in data else "error",
        "total_logs": data.get("total_logs", 0),
        "error": data.get("error", None)
    }

@router.get("/metrics")
def get_metrics():
    data = get_analytics_data()
    df_scored = data.get("scored_df", pd.DataFrame())
    if df_scored.empty:
        return {"critical_threats": 0, "high_risk_users": 0, "active_mitre_tactics": 0, "ml_confidence_avg": 0}
    
    critical_threats = len(df_scored[df_scored["Threat Level"] == "Critical"]) if "Threat Level" in df_scored.columns else 0
    high_risk_users = df_scored["user.name"].nunique() if "user.name" in df_scored.columns else 0
    active_mitre_tactics = 0
    if "mitre_tags" in df_scored.columns:
        # Just an approximation
        active_mitre_tactics = df_scored["mitre_tags"].dropna().nunique()
        
    ml_conf = df_scored["ml_confidence"].mean() if "ml_confidence" in df_scored.columns else 0.0
    
    return {
        "critical_threats": critical_threats,
        "high_risk_users": high_risk_users,
        "active_mitre_tactics": active_mitre_tactics,
        "ml_confidence_avg": float(ml_conf)
    }

@router.get("/anomalies/top")
def get_top_anomalies(limit: int = 100):
    data = get_analytics_data()
    df_scored = data.get("scored_df", pd.DataFrame())
    if df_scored.empty or "risk_score" not in df_scored.columns:
        return []
    
    top = df_scored.sort_values("risk_score", ascending=False).head(limit)
    return _safe_records(top)

@router.get("/timeline")
def get_timeline():
    data = get_analytics_data()
    timeline = data.get("timeline", pd.DataFrame())
    if isinstance(timeline, pd.DataFrame) and not timeline.empty:
        # Convert timestamps to string
        if "timestamp" in timeline.columns:
            timeline["timestamp"] = timeline["timestamp"].astype(str)
        return _safe_records(timeline)
    return []

@router.get("/entities")
def get_entities():
    data = get_analytics_data()
    return {
        "top_users": _safe_records(data.get("top_users", pd.DataFrame())),
        "top_hosts": _safe_records(data.get("top_hosts", pd.DataFrame())),
        "top_processes": _safe_records(data.get("top_processes", pd.DataFrame()))
    }

@router.get("/dashboard")
def get_dashboard_summary():
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    # KPIs
    total_events = data.get("total_logs", 0)
    anomalies = data.get("n_anomalies", 0)
    unique_hosts = data.get("unique_hosts", 0)
    unique_users = data.get("unique_users", 0)
    
    threat_summary_df = data.get("threat_summary", pd.DataFrame())
    high_critical = 0
    if not threat_summary_df.empty:
        mask = threat_summary_df["threat_level"].isin(["High Threat", "Critical"])
        high_critical = int(threat_summary_df[mask]["count"].sum())
        
    kpis = {
        "totalEvents": total_events,
        "eventsAnalyzed": total_events,
        "anomaliesDetected": anomalies,
        "highCriticalThreats": high_critical,
        "affectedHosts": unique_hosts,
        "affectedUsers": unique_users
    }
    
    # Risk Score Calculation (0-100)
    anomaly_rate = data.get("anomaly_rate", 0.0)
    critical_ratio = (high_critical / total_events) if total_events > 0 else 0
    calculated_score = min(100, max(0, int((anomaly_rate * 2.5) + (critical_ratio * 2000))))
    if calculated_score == 0 and anomalies > 0:
        calculated_score = 15
        
    classification = "Low"
    if calculated_score > 75: classification = "Critical"
    elif calculated_score > 50: classification = "High"
    elif calculated_score > 25: classification = "Moderate"
    
    risk_score = {
        "score": calculated_score,
        "classification": classification
    }
    
    # Timeline
    timeline_df = data.get("timeline", pd.DataFrame())
    timeline_data = []
    if isinstance(timeline_df, pd.DataFrame) and not timeline_df.empty and "timestamp" in timeline_df.columns:
        timeline_df = timeline_df.copy()
        timeline_df["timestamp"] = timeline_df["timestamp"].astype(str)
        records = _safe_records(timeline_df)
        for r in records:
            r["events"] = r.get("count", 0)
            r["anomalies"] = int(r["events"] * (anomaly_rate / 100))
            r["threats"] = int(r["anomalies"] * 0.1)
        timeline_data = records

    # Anomaly Distribution
    anomaly_dist = _safe_records(threat_summary_df) if isinstance(threat_summary_df, pd.DataFrame) and not threat_summary_df.empty else []
    
    # Top Risky Hosts
    host_anomalies_df = data.get("host_anomalies", pd.DataFrame())
    top_hosts = _safe_records(host_anomalies_df.head(5)) if isinstance(host_anomalies_df, pd.DataFrame) and not host_anomalies_df.empty else []
    
    # Top Risky Users
    user_anomalies_df = data.get("user_anomalies", pd.DataFrame())
    top_users = _safe_records(user_anomalies_df.head(5)) if isinstance(user_anomalies_df, pd.DataFrame) and not user_anomalies_df.empty else []
    
    # Threat Category Distribution
    cat_df = data.get("top_categories", pd.DataFrame())
    categories = _safe_records(cat_df) if isinstance(cat_df, pd.DataFrame) and not cat_df.empty else []
    
    # Recent Critical Events
    crit_events_df = data.get("critical_events", pd.DataFrame())
    if isinstance(crit_events_df, pd.DataFrame) and not crit_events_df.empty:
        if "@timestamp" in crit_events_df.columns:
            crit_events_df["@timestamp"] = crit_events_df["@timestamp"].astype(str)
        recent_critical = _safe_records(crit_events_df.head(10))
    else:
        recent_critical = []
    
    return {
        "kpis": kpis,
        "riskScore": risk_score,
        "timeline": timeline_data,
        "anomalyDistribution": anomaly_dist,
        "topHosts": top_hosts,
        "topUsers": top_users,
        "threatCategories": categories,
        "recentCriticalEvents": recent_critical
    }
