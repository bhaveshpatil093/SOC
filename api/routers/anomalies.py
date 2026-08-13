from fastapi import APIRouter, Request
import pandas as pd
import numpy as np
from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records
from api.utils.filters import apply_global_filters
from api.utils.pagination import paginate_dataframe
from api.utils.cache import cache_response
import json
import hashlib

router = APIRouter(prefix="/api/v1/anomalies", tags=["anomalies"])

@router.get("/overview")
@cache_response()
def get_anomalies_overview(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    total = len(df)
    anomalies = int((df["is_anomaly"] == True).sum()) if "anomaly_score" in df.columns else 0
    anomaly_rate = (anomalies / total * 100) if total > 0 else 0.0
    
    # Calculate unique entities for the filtered dataset
    entities_modeled = 0
    if "user.name" in df.columns: entities_modeled += int(df["user.name"].nunique())
    if "host.hostname" in df.columns: entities_modeled += int(df["host.hostname"].nunique())
    if "process.name" in df.columns: entities_modeled += int(df["process.name"].nunique())
    
    return {
        "totalAnomalies": anomalies,
        "anomalyRate": anomaly_rate,
        "entitiesModeled": entities_modeled
    }

@router.get("/distribution/severity")
@cache_response()
def get_severity_distribution(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty or "threat_level" not in df.columns:
        return []
        
    summary = df[df["is_anomaly"] == True].groupby("threat_level").size().reset_index(name="count")
    return _safe_records(summary)

@router.get("/timeline")
@cache_response()
def get_anomaly_timeline(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty or "@timestamp" not in df.columns:
        return []
        
    anoms = df[df["is_anomaly"] == True].copy()
    if anoms.empty:
        return []
        
    anoms["hour_block"] = pd.to_datetime(anoms["@timestamp"]).dt.floor("h")
    grouped = anoms.groupby("hour_block").size().reset_index(name="count")
    grouped["timestamp"] = grouped["hour_block"].astype(str)
    
    return _safe_records(grouped[["timestamp", "count"]])

@router.get("/entities")
@cache_response()
def get_top_entities(request: Request):
    data = get_analytics_data()
    if "error" in data:
        return {"users": [], "hosts": []}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty:
        return {"users": [], "hosts": []}
        
    anoms = df[df["is_anomaly"] == True]
    
    top_users = []
    if "user.name" in anoms.columns:
        top_users = _safe_records(anoms.groupby("user.name").agg(
            anomaly_count=("anomaly_score", "count"),
            max_score=("anomaly_score", "max")
        ).reset_index().rename(columns={"user.name": "user"}).sort_values("anomaly_count", ascending=False).head(10))
        
    top_hosts = []
    if "host.hostname" in anoms.columns:
        top_hosts = _safe_records(anoms.groupby("host.hostname").agg(
            anomaly_count=("anomaly_score", "count"),
            max_score=("anomaly_score", "max")
        ).reset_index().rename(columns={"host.hostname": "host"}).sort_values("anomaly_count", ascending=False).head(10))
    
    # Assign risk levels
    for u in top_users:
        s = u.get("max_score", 0) * 100
        u["risk_level"] = "Critical" if s > 80 else "High" if s > 60 else "Medium"
    for h in top_hosts:
        s = h.get("max_score", 0) * 100
        h["risk_level"] = "Critical" if s > 80 else "High" if s > 60 else "Medium"
        
    return {
        "users": top_users,
        "hosts": top_hosts
    }

@router.get("/events")
def get_anomaly_events(request: Request, page: int = 1, limit: int = 50, sort_by: str = "anomaly_score", sort_desc: bool = True):
    data = get_analytics_data()
    if "error" in data:
        return {"data": [], "total": 0, "page": page, "limit": limit, "total_pages": 0}
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty or "anomaly_score" not in df.columns:
        return {"data": [], "total": 0, "page": page, "limit": limit, "total_pages": 0}
        
    anomalies_df = df[df["is_anomaly"] == True]
    
    # Paginate
    paginated = paginate_dataframe(anomalies_df, page, limit, sort_by, sort_desc)
    current_df = paginated["data"]
    
    if current_df.empty:
        paginated["data"] = []
        return paginated
        
    if "@timestamp" in current_df.columns:
        current_df = current_df.copy()
        current_df["@timestamp"] = current_df["@timestamp"].astype(str)
        
    enriched_records = []
    shap_vals = data.get("shap_values", None)
    shap_feature_names = data.get("shap_feature_names", [])
    
    for idx, row in current_df.iterrows():
        rec = row.to_dict()
        rec["reasons"] = []
        rec["severity"] = row.get("threat_level", "Medium")
        
        # Try to find corresponding SHAP values
        if shap_vals is not None and isinstance(shap_vals, np.ndarray) and len(shap_feature_names) > 0:
            try:
                sv = shap_vals[idx % len(shap_vals)]
                # Get top 3 features by absolute SHAP value
                top_3_idx = np.argsort(np.abs(sv))[-3:][::-1]
                for i in top_3_idx:
                    feat_name = shap_feature_names[i]
                    impact = float(sv[i])
                    if abs(impact) > 0.01:
                        rec["reasons"].append({"feature": feat_name, "impact": round(impact, 3)})
            except Exception:
                pass
                
        if not rec["reasons"]:
            rec["reasons"].append({"feature": "Multiple statistical deviations", "impact": round(rec.get("anomaly_score", 0), 2)})
            
        enriched_records.append(rec)
        
    # Add _id for investigation state tracking
    for evt in enriched_records:
        ts = str(evt.get("@timestamp", ""))
        user = str(evt.get("user.name", ""))
        host = str(evt.get("host.hostname", ""))
        score = str(evt.get("anomaly_score", ""))
        raw = f"{ts}{user}{host}{score}"
        evt["_id"] = hashlib.md5(raw.encode()).hexdigest()
        
        
    paginated["data"] = _safe_records(enriched_records)
    return paginated
