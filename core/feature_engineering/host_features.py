"""
core/feature_engineering/host_features.py

Extracts Host Behaviour metrics:
- New hostname detection
- Host access frequency
- Rare host access

Why it is useful:
Spots newly infected endpoints or unusual spikes in host telemetry indicating malware execution.

Mathematical formula:
- Host access frequency = Count(events_host) / Total_Events
"""

import pandas as pd
from .base import BaseFeatureExtractor, FeatureContext

class HostFeatureExtractor(BaseFeatureExtractor):
    
    HOST_ALIASES = ["host.name", "host_name", "hostname"]
    
    def fit_transform(self, df: pd.DataFrame, context: FeatureContext) -> pd.DataFrame:
        host_col = self._resolve_col(df, self.HOST_ALIASES)
        if not host_col:
            return df
            
        result = df.copy()
        
        # State tracking
        if "seen_hosts" not in context.state:
            context.state["seen_hosts"] = set()
            
        # 1. New hostname detection
        valid_hosts = df[host_col].dropna().unique()
        new_hosts = set(valid_hosts) - context.state["seen_hosts"]
        result[f"{self.FEAT_PREFIX}host_is_new"] = result[host_col].apply(
            lambda h: 1.0 if h in new_hosts else 0.0
        )
        context.state["seen_hosts"].update(valid_hosts)
        
        # 2. Host access frequency
        host_freq = df[host_col].value_counts(normalize=True)
        result[f"{self.FEAT_PREFIX}host_freq"] = result[host_col].map(host_freq).fillna(0)
        
        # 3. Rare host access
        # Rarity is the inverse of frequency
        result[f"{self.FEAT_PREFIX}host_rarity"] = 1.0 - result[f"{self.FEAT_PREFIX}host_freq"]
        
        return result
