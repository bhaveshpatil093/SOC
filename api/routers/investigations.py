from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Dict, List, Optional
import pandas as pd
from api.services.data_service import get_analytics_data
from api.routers.analytics import _safe_records

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])

# Lightweight in-memory state tracking for event investigations
_investigation_state: Dict[str, str] = {}

class StatusUpdate(BaseModel):
    status: str

@router.get("/{event_id}/status")
def get_status(event_id: str):
    return {"status": _investigation_state.get(event_id, "Open")}

@router.post("/{event_id}/status")
def update_status(event_id: str, payload: StatusUpdate):
    _investigation_state[event_id] = payload.status
    return {"status": payload.status}

@router.get("/timeline")
def get_entity_timeline(
    host: Optional[str] = Query(None),
    user: Optional[str] = Query(None),
    limit: int = 10
):
    """
    Returns a small chronological slice of events for a given host or user
    to provide context during an investigation.
    """
    data = get_analytics_data()
    if "error" in data:
        return []
        
    df = data.get("scored_df", pd.DataFrame())
    if df.empty:
        return []
        
    mask = pd.Series([False] * len(df), index=df.index)
    
    if host and "host.hostname" in df.columns:
        mask = mask | (df["host.hostname"] == host)
    if user and "user.name" in df.columns:
        mask = mask | (df["user.name"] == user)
        
    if not mask.any():
        return []
        
    # Get the events matching the entity
    entity_events = df[mask].sort_values("@timestamp", ascending=False).head(limit)
    
    # Cast timestamp
    if "@timestamp" in entity_events.columns:
        entity_events["@timestamp"] = entity_events["@timestamp"].astype(str)
        
    return _safe_records(entity_events)
