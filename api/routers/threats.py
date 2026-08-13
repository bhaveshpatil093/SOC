from fastapi import APIRouter, Request
import pandas as pd
from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records
from api.utils.filters import apply_global_filters
from api.utils.pagination import paginate_dataframe
from api.utils.cache import cache_response
import hashlib

router = APIRouter(prefix="/api/v1/threats", tags=["threats"])

@router.get("/overview")
@cache_response()
def get_threat_overview(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty or "threat_score" not in df.columns:
        return {
            "critical": 0, "high": 0, "medium": 0, "hosts": 0, "users": 0
        }
        
    critical = int(df[df["threat_level"] == "Critical"].shape[0])
    high = int(df[df["threat_level"] == "High Threat"].shape[0])
    medium = int(df[(df["threat_score"] > 0) & (~df["threat_level"].isin(["Critical", "High Threat"]))].shape[0])
    
    threat_df = df[df["threat_score"] > 0]
    hosts = int(threat_df["host.hostname"].nunique()) if "host.hostname" in threat_df.columns else 0
    users = int(threat_df["user.name"].nunique()) if "user.name" in threat_df.columns else 0
    
    return {
        "critical": critical,
        "high": high,
        "medium": medium,
        "hosts": hosts,
        "users": users
    }

@router.get("/distribution")
@cache_response()
def get_threat_distribution(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty or "threat_level" not in df.columns:
        return []
        
    summary = df[df["threat_score"] > 0].groupby("threat_level").size().reset_index(name="count")
    return _safe_records(summary)

@router.get("/timeline")
@cache_response()
def get_threat_timeline(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty or "@timestamp" not in df.columns:
        return []
        
    threats = df[df["threat_score"] > 0].copy()
    if threats.empty:
        return []
        
    threats["hour_block"] = pd.to_datetime(threats["@timestamp"]).dt.floor("h")
    grouped = threats.groupby(["hour_block", "threat_level"]).size().reset_index(name="count")
    grouped["timestamp"] = grouped["hour_block"].astype(str)
    
    return _safe_records(grouped[["timestamp", "threat_level", "count"]])

@router.get("/entities")
@cache_response()
def get_threat_entities(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return {"users": [], "hosts": [], "ips": []}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty:
        return {"users": [], "hosts": [], "ips": []}
        
    threats = df[df["threat_score"] > 0]
    
    top_users = []
    if "user.name" in threats.columns:
        top_users = _safe_records(threats.groupby("user.name").agg(threat_count=("threat_score", "count")).reset_index().rename(columns={"user.name": "value"}).sort_values("threat_count", ascending=False).head(5))
        
    top_hosts = []
    if "host.hostname" in threats.columns:
        top_hosts = _safe_records(threats.groupby("host.hostname").agg(threat_count=("threat_score", "count")).reset_index().rename(columns={"host.hostname": "value"}).sort_values("threat_count", ascending=False).head(5))
        
    top_ips = []
    if "source.ip" in threats.columns:
        top_ips = _safe_records(threats.groupby("source.ip").agg(threat_count=("threat_score", "count")).reset_index().rename(columns={"source.ip": "value"}).sort_values("threat_count", ascending=False).head(5))
        
    return {
        "users": top_users,
        "hosts": top_hosts,
        "ips": top_ips
    }

@router.get("/feed")
def get_threat_feed(request: Request, page: int = 1, limit: int = 50, sort_by: str = "threat_score", sort_desc: bool = True):
    data = get_analytics_data()
    if "error" in data:
        return {"data": [], "total": 0, "page": page, "limit": limit, "total_pages": 0}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty or "threat_score" not in df.columns:
        return {"data": [], "total": 0, "page": page, "limit": limit, "total_pages": 0}
        
    threats = df[df["threat_score"] > 0]
    
    # Paginate
    paginated = paginate_dataframe(threats, page, limit, sort_by, sort_desc)
    current_df = paginated["data"]
    
    if current_df.empty:
        paginated["data"] = []
        return paginated
    
    if not current_df.empty:
        if "@timestamp" in current_df.columns:
            current_df = current_df.copy()
            current_df["@timestamp"] = current_df["@timestamp"].astype(str)
            
    events_list = _safe_records(current_df)
    
    # Add _id for investigation state tracking
    for evt in events_list:
        ts = str(evt.get("@timestamp", ""))
        user = str(evt.get("user.name", ""))
        host = str(evt.get("host.hostname", ""))
        score = str(evt.get("threat_score", ""))
        raw = f"{ts}{user}{host}{score}"
        evt["_id"] = hashlib.md5(raw.encode()).hexdigest()
        
    paginated["data"] = events_list
    return paginated
