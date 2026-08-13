from fastapi import APIRouter, Request
import pandas as pd
from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records
from api.utils.filters import apply_global_filters

router = APIRouter(prefix="/api/v1/behavior", tags=["behavior"])

@router.get("/overview")
def get_behavior_overview(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    total = len(df)
    deviations = int((df["anomaly_score"] > 0).sum()) if "anomaly_score" in df.columns else 0
    anomaly_rate = (deviations / total * 100) if total > 0 else 0.0
    normal_pct = max(0.0, 100.0 - anomaly_rate)
    
    unique_hosts = int(df["host.hostname"].nunique()) if "host.hostname" in df.columns else 0
    unique_users = int(df["user.name"].nunique()) if "user.name" in df.columns else 0
    unique_processes = int(df["process.name"].nunique()) if "process.name" in df.columns else 0
    entities_modeled = unique_hosts + unique_users + unique_processes
    
    return {
        "normalActivityPct": normal_pct,
        "baselineCoverage": 100, 
        "entitiesModeled": entities_modeled,
        "deviations": deviations
    }

@router.get("/temporal")
def get_behavior_temporal(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return {"hourly": [], "daily": []}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty or "hour" not in df.columns or "day_of_week" not in df.columns:
        return {"hourly": [], "daily": []}
        
    hourly_df = df.groupby("hour").size().reset_index(name="activity")
    daily_df = df.groupby("day_of_week").size().reset_index(name="activity")
    
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily_df["day_name"] = daily_df["day_of_week"].apply(lambda x: days[int(x)] if pd.notnull(x) and 0 <= int(x) < 7 else "Unknown")
    
    return {
        "hourly": _safe_records(hourly_df),
        "daily": _safe_records(daily_df)
    }

@router.get("/users")
def get_behavior_users(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    if df.empty or "user.name" not in df.columns:
        return []
        
    user_counts = df.groupby("user.name").size().reset_index(name="count")
    user_anoms = df[df["anomaly_score"] > 0].groupby("user.name").size().reset_index(name="anomaly_count")
    
    merged = pd.merge(user_counts, user_anoms, on="user.name", how="left")
    merged["anomaly_count"] = merged["anomaly_count"].fillna(0)
    merged["deviation_score"] = (merged["anomaly_count"] / merged["count"] * 100).fillna(0).round(1)
    merged = merged.rename(columns={"user.name": "value"}).sort_values("count", ascending=False).head(50)
            
    return _safe_records(merged)

@router.get("/hosts")
def get_behavior_hosts(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    if df.empty or "host.hostname" not in df.columns:
        return []
        
    host_counts = df.groupby("host.hostname").size().reset_index(name="count")
    host_anoms = df[df["anomaly_score"] > 0].groupby("host.hostname").size().reset_index(name="anomaly_count")
    
    merged = pd.merge(host_counts, host_anoms, on="host.hostname", how="left")
    merged["anomaly_count"] = merged["anomaly_count"].fillna(0)
    merged["deviation_score"] = (merged["anomaly_count"] / merged["count"] * 100).fillna(0).round(1)
    merged = merged.rename(columns={"host.hostname": "value"}).sort_values("count", ascending=False).head(50)
            
    return _safe_records(merged)

@router.get("/processes")
def get_behavior_processes(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    if df.empty or "process.name" not in df.columns:
        return []
        
    proc_counts = df.groupby("process.name").size().reset_index(name="count")
    proc_counts["rarity_score"] = (100 / (proc_counts["count"] + 1)).round(2)
    proc_counts = proc_counts.rename(columns={"process.name": "value"}).sort_values("count", ascending=False).head(50)
    return _safe_records(proc_counts)

@router.get("/network")
def get_behavior_network(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    if df.empty or "source.ip" not in df.columns:
        return []
        
    net = df[df["anomaly_score"] > 0].groupby("source.ip").size().reset_index(name="count").sort_values("count", ascending=False).head(50)
    net = net.rename(columns={"source.ip": "value"})
    return _safe_records(net)

@router.get("/deviations")
def get_behavior_deviations(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    if df.empty:
        return []
        
    anom_events_df = df[df["anomaly_score"] > 0].sort_values("anomaly_score", ascending=False).head(100)
    if not anom_events_df.empty and "@timestamp" in anom_events_df.columns:
        anom_events_df["@timestamp"] = anom_events_df["@timestamp"].astype(str)
    return _safe_records(anom_events_df)
