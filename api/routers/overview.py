from fastapi import APIRouter, Request
import pandas as pd
from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records
from api.utils.filters import apply_global_filters

router = APIRouter(prefix="/api/v1/overview", tags=["overview"])

@router.get("/kpis")
def get_kpis(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    total_events = len(df)
    anomalies = int((df["anomaly_score"] > 0).sum()) if "anomaly_score" in df.columns else 0
    unique_hosts = int(df["host.hostname"].nunique()) if "host.hostname" in df.columns else 0
    unique_users = int(df["user.name"].nunique()) if "user.name" in df.columns else 0
    
    high_critical = 0
    if "threat_level" in df.columns:
        high_critical = int(df["threat_level"].isin(["High Threat", "Critical"]).sum())
        
    anomaly_rate = (anomalies / total_events * 100) if total_events > 0 else 0.0
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
def get_timeline(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    timeline_data = []
    if not df.empty and "@timestamp" in df.columns:
        # Group by hour for timeline
        df["hour_block"] = pd.to_datetime(df["@timestamp"]).dt.floor("h")
        grouped = df.groupby("hour_block").agg(
            events=("@timestamp", "count"),
            anomalies=("anomaly_score", lambda x: (x > 0).sum()),
            threats=("threat_score", lambda x: (x > 0).sum())
        ).reset_index()
        
        grouped["timestamp"] = grouped["hour_block"].astype(str)
        timeline_data = _safe_records(grouped[["timestamp", "events", "anomalies", "threats"]])
    
    return timeline_data

@router.get("/anomalies")
def get_anomaly_distribution(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty or "threat_level" not in df.columns:
        return []
        
    summary = df[df["anomaly_score"] > 0].groupby("threat_level").size().reset_index(name="count")
    return _safe_records(summary)

@router.get("/entities")
def get_entities(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return {"topHosts": [], "topUsers": []}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty:
        return {"topHosts": [], "topUsers": []}
        
    anoms = df[df["anomaly_score"] > 0]
    
    top_hosts = []
    if "host.hostname" in anoms.columns:
        top_hosts = _safe_records(anoms.groupby("host.hostname").agg(count=("anomaly_score", "count")).reset_index().rename(columns={"host.hostname": "value"}).sort_values("count", ascending=False).head(5))
        
    top_users = []
    if "user.name" in anoms.columns:
        top_users = _safe_records(anoms.groupby("user.name").agg(count=("anomaly_score", "count")).reset_index().rename(columns={"user.name": "value"}).sort_values("count", ascending=False).head(5))
    
    return {
        "topHosts": top_hosts,
        "topUsers": top_users
    }

@router.get("/events/recent")
def get_recent_events(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty or "threat_score" not in df.columns:
        return []
        
    crit_events_df = df[df["threat_score"] > 0].sort_values("threat_score", ascending=False).head(10)
    
    if not crit_events_df.empty:
        if "@timestamp" in crit_events_df.columns:
            crit_events_df["@timestamp"] = crit_events_df["@timestamp"].astype(str)
        return _safe_records(crit_events_df)
    
    return []
