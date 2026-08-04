"""
core/feature_engineering/ip_features.py

Extracts IP Behaviour metrics:
- New IP detection
- Rare IP frequency
- Multiple users from same IP
- IP entropy
- External vs Internal IP
- Impossible travel placeholder

Why it is useful:
Identifies C2 beacons (rare IP frequency), lateral movement (multiple users from same IP), 
and data exfiltration/scanning (entropy across ports).

Mathematical formula:
- IP Entropy = -Sum(p_i * log(p_i)) across destination ports/IPs.

Computational complexity:
- O(N) for subnet checks and Set lookups. 
"""

import pandas as pd
import numpy as np
import ipaddress
from scipy.stats import entropy
from .base import BaseFeatureExtractor, FeatureContext

class IPFeatureExtractor(BaseFeatureExtractor):
    
    SRC_IP_ALIASES = ["source.ip", "src_ip", "source_ip"]
    USER_ALIASES = ["user.name", "user_name", "username"]
    DST_PORT_ALIASES = ["destination.port", "dst_port", "port"]
    
    def fit_transform(self, df: pd.DataFrame, context: FeatureContext) -> pd.DataFrame:
        src_ip_col = self._resolve_col(df, self.SRC_IP_ALIASES)
        if not src_ip_col:
            return df
            
        result = df.copy()
        
        # State tracking
        if "seen_ips" not in context.state:
            context.state["seen_ips"] = set()
            
        # 1. New IP detection
        valid_ips = df[src_ip_col].dropna().unique()
        new_ips = set(valid_ips) - context.state["seen_ips"]
        result[f"{self.FEAT_PREFIX}ip_is_new"] = result[src_ip_col].apply(
            lambda ip: 1.0 if ip in new_ips else 0.0
        )
        context.state["seen_ips"].update(valid_ips)
        
        # 2. Rare IP frequency (Inverse Frequency)
        # Using batch frequency as a proxy
        ip_counts = df[src_ip_col].value_counts(normalize=True)
        result[f"{self.FEAT_PREFIX}ip_rarity"] = 1.0 - result[src_ip_col].map(ip_counts).fillna(0)
        
        # 3. Multiple users from same IP
        user_col = self._resolve_col(df, self.USER_ALIASES)
        if user_col:
            users_per_ip = df.groupby(src_ip_col)[user_col].transform('nunique')
            result[f"{self.FEAT_PREFIX}ip_unique_users"] = users_per_ip
            
        # 4. External vs Internal IP
        def is_private(ip: str) -> float:
            if not isinstance(ip, str): return np.nan
            try:
                # Handle possible list/array formats if flattened poorly
                ip_str = ip.split("/")[0].strip()
                return 1.0 if ipaddress.ip_address(ip_str).is_private else 0.0
            except ValueError:
                return np.nan
                
        result[f"{self.FEAT_PREFIX}ip_is_private"] = result[src_ip_col].apply(is_private)
        
        # 5. IP Entropy (Entropy of destination ports accessed by this IP)
        dst_port_col = self._resolve_col(df, self.DST_PORT_ALIASES)
        if dst_port_col:
            # Calculate entropy of destination ports per source IP
            def calc_entropy(x):
                counts = x.value_counts()
                return entropy(counts) if len(counts) > 1 else 0.0
                
            port_entropy = df.groupby(src_ip_col)[dst_port_col].transform(calc_entropy)
            result[f"{self.FEAT_PREFIX}ip_port_entropy"] = port_entropy
            
        # 6. Impossible travel placeholder
        # In a real scenario, this requires GeoIP mapping. Placeholder for API consistency.
        result[f"{self.FEAT_PREFIX}ip_impossible_travel"] = 0.0
        
        return result
