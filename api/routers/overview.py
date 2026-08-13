from fastapi import APIRouter
import pandas as pd
from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records

router = APIRouter(prefix="/api/v1/overview", tags=["overview"])

@router.get("/kpis")
def get_kpis():
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    total_events = data.get("total_logs", 0)
    anomalies = data.get("n_anomalies", 0)
    unique_hosts = data.get("unique_hosts", 0)
    unique_users = data.get("unique_users", 0)
    
    threat_summary_df = data.get("threat_summary", pd.DataFrame())
    high_critical = 0
    if not threat_summary_df.empty:
        mask = threat_summary_df["threat_level"].isin(["High Threat", "Critical"])
        high_critical = int(threat_summary_df[mask]["count"].sum())
        
    anomaly_rate = data.get("anomaly_rate", 0.0)
    critical_ratio = (high_critical / total_events) if total_events > 0 else 0
    calculated_score = min(100, max(0, int((anomaly_rate * 2.5) + (critical_ratio * 2000))))
    if calculated_score == 0 and anomalies > 0:
        calculated_score = 15
        
    classification = "Low"
    if calculated_score > 75: classification = "Critical"
    elif calculated_score > 50: classification = "High"
    elif calculated_score > 25: classification = "Medium"

    return {
        "kpis": {
            "totalEvents": total_events,
            "eventsAnalyzed": total_events,
            "anomaliesDetected": anomalies,
            "highCriticalThreats": high_critical,
            "affectedHosts": unique_hosts,
            "affectedUsers": unique_users
        },
        "riskScore": {
            "score": calculated_score,
            "classification": classification
        }
    }

@router.get("/timeline")
def get_timeline():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    timeline_df = data.get("timeline", pd.DataFrame())
    anomaly_rate = data.get("anomaly_rate", 0.0)
    
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
    
    return timeline_data

@router.get("/anomalies")
def get_anomaly_distribution():
    data = get_analytics_data()
    if "error" in data:
        return []
    threat_summary_df = data.get("threat_summary", pd.DataFrame())
    return _safe_records(threat_summary_df) if isinstance(threat_summary_df, pd.DataFrame) and not threat_summary_df.empty else []

@router.get("/entities")
def get_entities():
    data = get_analytics_data()
    if "error" in data:
        return {"topHosts": [], "topUsers": []}
        
    host_anomalies_df = data.get("host_anomalies", pd.DataFrame())
    top_hosts = _safe_records(host_anomalies_df.head(5)) if isinstance(host_anomalies_df, pd.DataFrame) and not host_anomalies_df.empty else []
    
    user_anomalies_df = data.get("user_anomalies", pd.DataFrame())
    top_users = _safe_records(user_anomalies_df.head(5)) if isinstance(user_anomalies_df, pd.DataFrame) and not user_anomalies_df.empty else []
    
    return {
        "topHosts": top_hosts,
        "topUsers": top_users
    }

@router.get("/events/recent")
def get_recent_events():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    crit_events_df = data.get("critical_events", pd.DataFrame())
    if isinstance(crit_events_df, pd.DataFrame) and not crit_events_df.empty:
        if "@timestamp" in crit_events_df.columns:
            crit_events_df["@timestamp"] = crit_events_df["@timestamp"].astype(str)
        return _safe_records(crit_events_df.head(10))
    
    return []
