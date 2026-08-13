from fastapi import APIRouter
import pandas as pd
from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records

router = APIRouter(prefix="/api/v1/behavior", tags=["behavior"])

@router.get("/overview")
def get_behavior_overview():
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    anomaly_rate = data.get("anomaly_rate", 0.0)
    normal_pct = max(0.0, 100.0 - anomaly_rate)
    
    unique_hosts = data.get("unique_hosts", 0)
    unique_users = data.get("unique_users", 0)
    unique_processes = data.get("unique_processes", 0)
    entities_modeled = unique_hosts + unique_users + unique_processes
    
    deviations = data.get("n_anomalies", 0)
    
    return {
        "normalActivityPct": normal_pct,
        "baselineCoverage": 100, # Assuming 100% since isolation forest uses all numerical features
        "entitiesModeled": entities_modeled,
        "deviations": deviations
    }

@router.get("/temporal")
def get_behavior_temporal():
    data = get_analytics_data()
    if "error" in data:
        return {"hourly": [], "daily": []}
        
    df_scored = data.get("scored_df", pd.DataFrame())
    if df_scored.empty or "hour" not in df_scored.columns or "day_of_week" not in df_scored.columns:
        return {"hourly": [], "daily": []}
        
    # Group by hour for 24h heatmap
    hourly_df = df_scored.groupby("hour").size().reset_index(name="activity")
    
    # Group by day for June distribution
    daily_df = df_scored.groupby("day_of_week").size().reset_index(name="activity")
    
    # Map day_of_week to actual names for frontend convenience
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily_df["day_name"] = daily_df["day_of_week"].apply(lambda x: days[int(x)] if pd.notnull(x) and 0 <= int(x) < 7 else "Unknown")
    
    return {
        "hourly": _safe_records(hourly_df),
        "daily": _safe_records(daily_df)
    }

@router.get("/users")
def get_behavior_users():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    top_users_df = data.get("top_users", pd.DataFrame())
    user_anom_df = data.get("user_anomalies", pd.DataFrame())
    
    if top_users_df.empty:
        return []
        
    # Convert string dict to actual dict safely
    if not isinstance(top_users_df, pd.DataFrame):
        return []
        
    merged = top_users_df.copy()
    
    # Check if user_anomalies has 'user.name'
    user_col = "user.name"
    if not user_anom_df.empty and user_col in user_anom_df.columns:
        # top_users uses 'value' instead of 'user.name'
        if "value" in merged.columns:
            merged = pd.merge(merged, user_anom_df, left_on="value", right_on=user_col, how="left")
            merged["anomaly_count"] = merged["anomaly_count"].fillna(0)
            merged["deviation_score"] = (merged["anomaly_count"] / merged["count"] * 100).fillna(0).round(1)
            
    return _safe_records(merged)

@router.get("/hosts")
def get_behavior_hosts():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    top_hosts_df = data.get("top_hosts", pd.DataFrame())
    host_anom_df = data.get("host_anomalies", pd.DataFrame())
    
    if top_hosts_df.empty or not isinstance(top_hosts_df, pd.DataFrame):
        return []
        
    merged = top_hosts_df.copy()
    host_col = "host.hostname"
    if not host_anom_df.empty and host_col in host_anom_df.columns:
        if "value" in merged.columns:
            merged = pd.merge(merged, host_anom_df, left_on="value", right_on=host_col, how="left")
            merged["anomaly_count"] = merged["anomaly_count"].fillna(0)
            merged["deviation_score"] = (merged["anomaly_count"] / merged["count"] * 100).fillna(0).round(1)
            
    return _safe_records(merged)

@router.get("/processes")
def get_behavior_processes():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    # Use top_processes for base
    top_proc_df = data.get("top_processes", pd.DataFrame())
    
    # Calculate some rarity score metric.
    # In local_data_client, proc_rarity is 1 / (count + 1). We'll scale it to 0-100.
    if isinstance(top_proc_df, pd.DataFrame) and not top_proc_df.empty and "count" in top_proc_df.columns:
        top_proc_df = top_proc_df.copy()
        top_proc_df["rarity_score"] = (100 / (top_proc_df["count"] + 1)).round(2)
        return _safe_records(top_proc_df)
    return []

@router.get("/network")
def get_behavior_network():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    # Merge anomalous_ips with top IPs
    anom_ips_df = data.get("anomalous_ips", pd.DataFrame())
    if isinstance(anom_ips_df, pd.DataFrame) and not anom_ips_df.empty:
        return _safe_records(anom_ips_df)
        
    return []

@router.get("/deviations")
def get_behavior_deviations():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    anom_events_df = data.get("anomaly_events", pd.DataFrame())
    if isinstance(anom_events_df, pd.DataFrame) and not anom_events_df.empty:
        if "@timestamp" in anom_events_df.columns:
            anom_events_df["@timestamp"] = anom_events_df["@timestamp"].astype(str)
        # Limit to 100 for the frontend table
        return _safe_records(anom_events_df.head(100))
        
    return []
