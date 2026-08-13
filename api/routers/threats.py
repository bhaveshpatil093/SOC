from fastapi import APIRouter
import pandas as pd
from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records

router = APIRouter(prefix="/api/v1/threats", tags=["threats"])

@router.get("/overview")
def get_threats_overview():
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    threat_summary_df = data.get("threat_summary", pd.DataFrame())
    
    critical = 0
    high = 0
    medium = 0 # In local_data_client, "Suspicious" acts as medium
    
    if not threat_summary_df.empty:
        critical = int(threat_summary_df[threat_summary_df["threat_level"] == "Critical"]["count"].sum())
        high = int(threat_summary_df[threat_summary_df["threat_level"] == "High Threat"]["count"].sum())
        medium = int(threat_summary_df[threat_summary_df["threat_level"] == "Suspicious"]["count"].sum())
        
    # Get affected hosts and users (only those involved in Critical/High/Suspicious events)
    df_scored = data.get("scored_df", pd.DataFrame())
    affected_hosts = 0
    affected_users = 0
    
    if not df_scored.empty and "threat_level" in df_scored.columns:
        threat_mask = df_scored["threat_level"].isin(["Critical", "High Threat", "Suspicious"])
        if "host.hostname" in df_scored.columns:
            affected_hosts = df_scored[threat_mask]["host.hostname"].nunique()
        if "user.name" in df_scored.columns:
            affected_users = df_scored[threat_mask]["user.name"].nunique()
            
    return {
        "criticalThreats": critical,
        "highThreats": high,
        "mediumThreats": medium,
        "affectedHosts": affected_hosts,
        "affectedUsers": affected_users
    }

@router.get("/distribution")
def get_threats_distribution():
    data = get_analytics_data()
    if "error" in data:
        return []
    threat_summary_df = data.get("threat_summary", pd.DataFrame())
    if threat_summary_df.empty:
        return []
        
    # Filter out 'Normal'
    dist_df = threat_summary_df[threat_summary_df["threat_level"] != "Normal"]
    return _safe_records(dist_df)

@router.get("/timeline")
def get_threats_timeline():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df_scored = data.get("scored_df", pd.DataFrame())
    if df_scored.empty or "hour" not in df_scored.columns or "threat_level" not in df_scored.columns:
        return []
        
    threat_mask = df_scored["threat_level"].isin(["Critical", "High Threat", "Suspicious"])
    threat_df = df_scored[threat_mask]
    
    if threat_df.empty:
        return []
        
    # Group by hour and threat_level
    timeline_df = threat_df.groupby(["hour", "threat_level"]).size().unstack(fill_value=0).reset_index()
    
    # Ensure all columns exist
    for col in ["Critical", "High Threat", "Suspicious"]:
        if col not in timeline_df.columns:
            timeline_df[col] = 0
            
    return _safe_records(timeline_df)

@router.get("/entities")
def get_threats_entities():
    data = get_analytics_data()
    if "error" in data:
        return {"hosts": [], "users": [], "sourceIps": [], "destIps": []}
        
    df_scored = data.get("scored_df", pd.DataFrame())
    if df_scored.empty or "threat_level" not in df_scored.columns:
        return {"hosts": [], "users": [], "sourceIps": [], "destIps": []}
        
    threat_mask = df_scored["threat_level"].isin(["Critical", "High Threat", "Suspicious"])
    threat_df = df_scored[threat_mask]
    
    hosts = []
    if "host.hostname" in threat_df.columns:
        host_agg = threat_df.groupby("host.hostname").size().reset_index(name="count").sort_values("count", ascending=False).head(5)
        hosts = _safe_records(host_agg)
        
    users = []
    if "user.name" in threat_df.columns:
        user_agg = threat_df.groupby("user.name").size().reset_index(name="count").sort_values("count", ascending=False).head(5)
        users = _safe_records(user_agg)
        
    source_ips = []
    if "source.ip" in threat_df.columns:
        sip_agg = threat_df.groupby("source.ip").size().reset_index(name="count").sort_values("count", ascending=False).head(5)
        source_ips = _safe_records(sip_agg)
        
    dest_ips = []
    if "destination.ip" in threat_df.columns:
        dip_agg = threat_df.groupby("destination.ip").size().reset_index(name="count").sort_values("count", ascending=False).head(5)
        dest_ips = _safe_records(dip_agg)
        
    return {
        "hosts": hosts,
        "users": users,
        "sourceIps": source_ips,
        "destIps": dest_ips
    }

@router.get("/events")
def get_threats_events():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    crit_df = data.get("critical_events", pd.DataFrame())
    susp_df = data.get("suspicious_events", pd.DataFrame())
    
    if crit_df.empty and susp_df.empty:
        return []
        
    combined = pd.concat([crit_df, susp_df]).sort_values("anomaly_score", ascending=False).head(200)
    
    if "@timestamp" in combined.columns:
        combined["@timestamp"] = combined["@timestamp"].astype(str)
        
    # Check for MITRE/Sigma
    # For now, local_data_client doesn't inject it, but we make sure the payload is safe
    events_list = _safe_records(combined)
    
    # Add _id for investigation state tracking
    import hashlib
    for evt in events_list:
        ts = str(evt.get("@timestamp", ""))
        user = str(evt.get("user.name", ""))
        host = str(evt.get("host.hostname", ""))
        score = str(evt.get("threat_score", ""))
        raw = f"{ts}{user}{host}{score}"
        evt["_id"] = hashlib.md5(raw.encode()).hexdigest()
        
    return events_list
