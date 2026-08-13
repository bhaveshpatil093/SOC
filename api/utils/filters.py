import pandas as pd
from typing import Dict, Any

def apply_global_filters(df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
    """
    Applies global search/filter parameters to the scored_df in-place (or rather, returns a filtered copy).
    """
    if df.empty:
        return df

    filtered_df = df.copy()

    # Time filters
    start_time = filters.get("start_time")
    end_time = filters.get("end_time")
    if start_time and "@timestamp" in filtered_df.columns:
        filtered_df = filtered_df[pd.to_datetime(filtered_df["@timestamp"]) >= pd.to_datetime(start_time)]
    if end_time and "@timestamp" in filtered_df.columns:
        filtered_df = filtered_df[pd.to_datetime(filtered_df["@timestamp"]) <= pd.to_datetime(end_time)]

    # Entity filters
    user = filters.get("user")
    if user and "user.name" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["user.name"] == user]

    host = filters.get("host")
    if host and "host.hostname" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["host.hostname"] == host]

    source_ip = filters.get("source_ip")
    if source_ip and "source.ip" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["source.ip"] == source_ip]

    dest_ip = filters.get("dest_ip")
    if dest_ip and "destination.ip" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["destination.ip"] == dest_ip]

    # Category / String match filters
    event_category = filters.get("event_category")
    if event_category and "event.category" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["event.category"].str.contains(event_category, case=False, na=False)]

    sigma_rule = filters.get("sigma_rule")
    if sigma_rule and "sigma_rule" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["sigma_rule"] == sigma_rule]

    mitre = filters.get("mitre_technique")
    if mitre and "mitre_technique" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["mitre_technique"].str.contains(mitre, case=False, na=False)]

    # Severity / Threat Filtering (assuming severity corresponds to threat level or anomaly score)
    severity = filters.get("severity")
    if severity:
        if severity.lower() == "critical" and "threat_level" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["threat_level"] == "Critical"]
        elif severity.lower() == "high" and "threat_level" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["threat_level"] == "High Threat"]
        # Can add medium/low logic if needed

    return filtered_df
