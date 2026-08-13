from fastapi import APIRouter
import pandas as pd
import numpy as np
from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records
import json

router = APIRouter(prefix="/api/v1/anomalies", tags=["anomalies"])

@router.get("/overview")
def get_anomalies_overview():
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    total_anomalies = data.get("n_anomalies", 0)
    score_bins = data.get("score_bins", ([], []))
    
    distribution = []
    if len(score_bins) == 2:
        counts = score_bins[0]
        edges = score_bins[1]
        for i in range(len(counts)):
            distribution.append({
                "range": f"{int(edges[i]*100)}-{int(edges[i+1]*100)}",
                "count": int(counts[i])
            })
            
    return {
        "totalAnomalies": total_anomalies,
        "distribution": distribution
    }

@router.get("/severity")
def get_anomalies_severity():
    data = get_analytics_data()
    if "error" in data:
        return []
    threat_summary_df = data.get("threat_summary", pd.DataFrame())
    return _safe_records(threat_summary_df) if isinstance(threat_summary_df, pd.DataFrame) and not threat_summary_df.empty else []

@router.get("/timeline")
def get_anomalies_timeline():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df_scored = data.get("scored_df", pd.DataFrame())
    if df_scored.empty or "hour" not in df_scored.columns:
        return []
        
    # Group anomalies by hour
    anom_df = df_scored[df_scored["is_anomaly"]]
    if anom_df.empty:
        return []
        
    timeline_df = anom_df.groupby("hour").size().reset_index(name="count")
    return _safe_records(timeline_df)

@router.get("/heatmap")
def get_anomalies_heatmap():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df_scored = data.get("scored_df", pd.DataFrame())
    if df_scored.empty or "hour" not in df_scored.columns or "threat_level" not in df_scored.columns:
        return []
        
    anom_df = df_scored[df_scored["is_anomaly"]]
    if anom_df.empty:
        return []
        
    heatmap_df = anom_df.groupby(["hour", "threat_level"]).size().reset_index(name="count")
    return _safe_records(heatmap_df)

@router.get("/entities")
def get_anomalies_entities():
    data = get_analytics_data()
    if "error" in data:
        return {"users": [], "hosts": []}
        
    df_scored = data.get("scored_df", pd.DataFrame())
    if df_scored.empty:
        return {"users": [], "hosts": []}
        
    anom_df = df_scored[df_scored["is_anomaly"]]
    
    users = []
    if "user.name" in anom_df.columns:
        user_agg = anom_df.groupby("user.name").agg(
            anomaly_count=("is_anomaly", "size"),
            max_score=("anomaly_score", "max")
        ).reset_index()
        user_agg["risk_level"] = user_agg["max_score"].apply(lambda x: "Critical" if x > 0.8 else ("High" if x > 0.6 else "Medium"))
        user_agg = user_agg.sort_values("anomaly_count", ascending=False).head(10)
        users = _safe_records(user_agg)
        
    hosts = []
    if "host.hostname" in anom_df.columns:
        host_agg = anom_df.groupby("host.hostname").agg(
            anomaly_count=("is_anomaly", "size"),
            max_score=("anomaly_score", "max")
        ).reset_index()
        host_agg["risk_level"] = host_agg["max_score"].apply(lambda x: "Critical" if x > 0.8 else ("High" if x > 0.6 else "Medium"))
        host_agg = host_agg.sort_values("anomaly_count", ascending=False).head(10)
        hosts = _safe_records(host_agg)
        
    return {"users": users, "hosts": hosts}

@router.get("/events")
def get_anomalies_events():
    data = get_analytics_data()
    if "error" in data:
        return []
        
    anom_events_df = data.get("anomaly_events", pd.DataFrame())
    if not isinstance(anom_events_df, pd.DataFrame) or anom_events_df.empty:
        return []
        
    anom_events_df = anom_events_df.head(100).copy()
    if "@timestamp" in anom_events_df.columns:
        anom_events_df["@timestamp"] = anom_events_df["@timestamp"].astype(str)
        
    records = _safe_records(anom_events_df)
    
    # SHAP integration
    shap_values = data.get("shap_values")
    shap_feature_names = data.get("shap_feature_names")
    shap_indices = data.get("shap_indices")
    
    if shap_values is not None and shap_feature_names is not None and shap_indices is not None:
        # Convert shap_indices to a list or array for easy lookup
        idx_list = list(shap_indices)
        
        for r in records:
            # We need to find if this record's original index is in shap_indices
            # The records from _safe_records don't have the index, but we can iterate over the df
            pass
            
    # To properly map SHAP, let's iterate rows with indices
    enriched_records = []
    for idx, row in anom_events_df.iterrows():
        rec = row.to_dict()
        for k, v in rec.items():
            if pd.isna(v): rec[k] = None
            elif isinstance(v, (np.int64, np.int32)): rec[k] = int(v)
            elif isinstance(v, (np.float64, np.float32)): rec[k] = float(v)
            
        rec["reasons"] = []
        if shap_values is not None and shap_indices is not None:
            try:
                # Find position in shap_indices
                pos = list(shap_indices).index(idx)
                if isinstance(shap_values, list): # For some tree explainers
                    sv = shap_values[1][pos] if len(shap_values) > 1 else shap_values[0][pos]
                else:
                    sv = shap_values[pos]
                
                # Get top 3 features by absolute SHAP value
                top_3_idx = np.argsort(np.abs(sv))[-3:][::-1]
                for i in top_3_idx:
                    feat_name = shap_feature_names[i]
                    impact = float(sv[i])
                    if abs(impact) > 0.01:
                        rec["reasons"].append({"feature": feat_name, "impact": round(impact, 3)})
            except ValueError:
                # Index not in top K SHAP computed
                pass
                
        if not rec["reasons"]:
            rec["reasons"].append({"feature": "Multiple statistical deviations", "impact": round(rec.get("anomaly_score", 0), 2)})
            
        enriched_records.append(rec)
        
    return enriched_records
