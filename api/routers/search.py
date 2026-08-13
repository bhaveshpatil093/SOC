from fastapi import APIRouter, Query
from typing import Optional
import pandas as pd
from api.services.data_service import get_analytics_data

router = APIRouter(prefix="/api/v1/search", tags=["search"])

@router.get("/")
def global_search(q: str = Query(..., min_length=2)):
    """
    Search across entities and specific alerts.
    Returns categorized suggestions.
    """
    data = get_analytics_data()
    df = data.get("scored_df", pd.DataFrame())
    if df.empty:
        return []

    q_lower = q.lower()
    results = []
    
    # helper for fast unique search
    def search_col(col_name, entity_type):
        if col_name in df.columns:
            uniques = df[col_name].dropna().unique()
            matches = [str(u) for u in uniques if q_lower in str(u).lower()]
            for m in matches[:5]:  # Limit to top 5 per category
                results.append({"type": entity_type, "value": m, "label": m})

    search_col("user.name", "User")
    search_col("host.hostname", "Host")
    search_col("source.ip", "Source IP")
    search_col("destination.ip", "Destination IP")
    search_col("process.name", "Process")
    
    if "sigma_rule" in df.columns:
        search_col("sigma_rule", "Sigma Rule")
        
    if "mitre_technique" in df.columns:
        search_col("mitre_technique", "MITRE Technique")

    # Sort results to have a nice consistent list
    return sorted(results, key=lambda x: (x["type"], x["label"]))
