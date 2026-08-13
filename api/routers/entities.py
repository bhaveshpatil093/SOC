from fastapi import APIRouter, Request, Query, HTTPException
from typing import Dict, List, Optional
import pandas as pd
from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records
from api.utils.filters import apply_global_filters

router = APIRouter(prefix="/api/v1/entities", tags=["entities"])

# Cache for entity search to avoid recalculating heavy groupbys on every keystroke
_cached_search_results = []

def generate_entity_search_cache(df: pd.DataFrame):
    results = []
    
    def process_field(field_name, entity_type):
        if field_name not in df.columns:
            return
            
        group = df.groupby(field_name).agg(
            event_count=("@timestamp", "count"),
            first_seen=("@timestamp", "min"),
            last_seen=("@timestamp", "max"),
            anomaly_count=("anomaly_score", lambda x: (x > 0).sum()),
            threat_count=("threat_score", lambda x: (x > 0).sum())
        ).reset_index()
        
        for _, row in group.iterrows():
            val = str(row[field_name])
            if val and val != "nan" and val != "None":
                results.append({
                    "id": f"{entity_type}_{val}",
                    "name": val,
                    "type": entity_type,
                    "event_count": int(row["event_count"]),
                    "first_seen": str(row["first_seen"]),
                    "last_seen": str(row["last_seen"]),
                    "anomaly_count": int(row["anomaly_count"]),
                    "threat_count": int(row["threat_count"]),
                    "risk_score": round(min(100, (row["anomaly_count"] * 2) + (row["threat_count"] * 10)), 1)
                })

    process_field("user.name", "User")
    process_field("host.hostname", "Host")
    process_field("source.ip", "Source IP")
    process_field("process.name", "Process")
    
    return sorted(results, key=lambda x: x["risk_score"], reverse=True)

@router.get("/search")
def search_entities(request: Request, type: str = "All"):
    """
    Returns a unified catalog of all entities in the network.
    """
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    df = apply_global_filters(df, dict(request.query_params))
    
    if df.empty:
        return []
        
    # Build dynamic entities catalog (expensive but fully dynamic)
    results = generate_entity_search_cache(df)
    
    if type and type.lower() != "all":
        results = [r for r in results if r["type"].lower() == type.lower()]
        
    return results[:100]  # Limit output for performance

@router.get("/profile")
def get_entity_profile(request: Request, name: str, type: str):
    data = get_analytics_data()
    if "error" in data:
        return {"error": data["error"]}
        
    df = data.get("scored_df", pd.DataFrame())
    # we DO NOT filter the dataframe purely yet, because we need to filter for THIS specific entity
    # However, we DO want to apply OTHER global filters (like date ranges)
    global_filters = dict(request.query_params)
    global_filters.pop("name", None) # remove just in case
    global_filters.pop("type", None)
    
    df = apply_global_filters(df, global_filters)
    
    if df.empty:
        return {"error": "Dataset empty"}
        
    field_map = {
        "User": "user.name",
        "Host": "host.hostname",
        "Source IP": "source.ip",
        "Process": "process.name"
    }
    
    field = field_map.get(type)
    if not field or field not in df.columns:
        raise HTTPException(status_code=400, detail="Invalid entity type")
        
    mask = df[field] == name
    entity_df = df[mask]
    
    if entity_df.empty:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    profile = {
        "name": name,
        "type": type,
        "event_count": len(entity_df),
        "first_seen": str(entity_df["@timestamp"].min()),
        "last_seen": str(entity_df["@timestamp"].max()),
        "anomaly_count": int((entity_df["anomaly_score"] > 0).sum()),
        "threat_count": int((entity_df["threat_score"] > 0).sum()),
        "related": {}
    }
    
    # Generate relation stats dynamically
    if type == "User":
        if "hour" in entity_df.columns:
            profile["related"]["login_hours"] = entity_df.groupby("hour").size().reset_index(name="count").to_dict("records")
        if "source.ip" in entity_df.columns:
            profile["related"]["source_ips"] = entity_df["source.ip"].dropna().unique().tolist()
        if "host.hostname" in entity_df.columns:
            profile["related"]["hosts"] = entity_df["host.hostname"].dropna().unique().tolist()
            
    elif type == "Host":
        if "@timestamp" in entity_df.columns:
            # Group by day
            entity_df["date"] = pd.to_datetime(entity_df["@timestamp"]).dt.date
            profile["related"]["activity_timeline"] = entity_df.groupby("date").size().reset_index(name="count").to_dict("records")
            # Convert date back to string for json
            for r in profile["related"]["activity_timeline"]:
                r["date"] = str(r["date"])
                
        if "user.name" in entity_df.columns:
            profile["related"]["users"] = entity_df["user.name"].dropna().unique().tolist()
        if "process.name" in entity_df.columns:
            profile["related"]["processes"] = entity_df["process.name"].dropna().unique().tolist()[:50]
            
    elif type == "Source IP":
        if "destination.ip" in entity_df.columns:
            profile["related"]["destinations"] = entity_df["destination.ip"].dropna().unique().tolist()
        if "host.hostname" in entity_df.columns:
            profile["related"]["hosts"] = entity_df["host.hostname"].dropna().unique().tolist()
            
    elif type == "Process":
        profile["related"]["rarity_score"] = round(100 / (len(entity_df) + 1), 2)
        if "user.name" in entity_df.columns:
            profile["related"]["users"] = entity_df["user.name"].dropna().unique().tolist()
        if "host.hostname" in entity_df.columns:
            profile["related"]["hosts"] = entity_df["host.hostname"].dropna().unique().tolist()
            
    # Inject recent anomalies/threats for this entity
    anomalies = entity_df[entity_df["anomaly_score"] > 0].sort_values("anomaly_score", ascending=False).head(10)
    threats = entity_df[entity_df["threat_score"] > 0].sort_values("threat_score", ascending=False).head(10)
    
    # Inject _id into these payloads for the Drawer
    import hashlib
    def safe_extract(d):
        recs = _safe_records(d)
        for evt in recs:
            ts = str(evt.get("@timestamp", ""))
            usr = str(evt.get("user.name", ""))
            hst = str(evt.get("host.hostname", ""))
            score = str(evt.get("anomaly_score", evt.get("threat_score", "")))
            evt["_id"] = hashlib.md5(f"{ts}{usr}{hst}{score}".encode()).hexdigest()
        return recs

    profile["recent_anomalies"] = safe_extract(anomalies)
    profile["recent_threats"] = safe_extract(threats)
    
    return profile
