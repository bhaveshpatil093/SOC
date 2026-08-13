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
