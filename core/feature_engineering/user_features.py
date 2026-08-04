"""
core/feature_engineering/user_features.py

Extracts User Behaviour metrics:
- New user detection
- Login frequency
- Failed login ratio
- Number of unique hosts accessed
- Privilege escalation indicators
- User activity burst detection

Why it is useful:
Detects compromised accounts (high failure ratio, unusual bursts) and insider threats 
(privilege escalation, lateral movement across many hosts).

Mathematical formula:
- Failed login ratio = N_failed / (N_success + N_failed)
- Activity Burst = Count(events)_{batch} / Average(Count(events))_{historical}

Computational complexity:
- O(N log N) for grouping and aggregations. Highly scalable via pandas vectorized `.groupby()`.
"""

import pandas as pd
import numpy as np
from typing import List
from .base import BaseFeatureExtractor, FeatureContext

class UserFeatureExtractor(BaseFeatureExtractor):
    
    USER_ALIASES = ["user.name", "user_name", "username"]
    HOST_ALIASES = ["host.name", "host_name", "hostname"]
    OUTCOME_ALIASES = ["event.outcome", "outcome", "event_outcome"]
    ACTION_ALIASES = ["event.action", "action"]
    
    def fit_transform(self, df: pd.DataFrame, context: FeatureContext) -> pd.DataFrame:
        user_col = self._resolve_col(df, self.USER_ALIASES)
        if not user_col:
            return df
            
        result = df.copy()
        
        # State tracking
        if "seen_users" not in context.state:
            context.state["seen_users"] = set()
        if "user_event_counts" not in context.state:
            context.state["user_event_counts"] = {}
            
        # 1. New user detection
        unique_users = df[user_col].dropna().unique()
        new_users = set(unique_users) - context.state["seen_users"]
        result[f"{self.FEAT_PREFIX}user_is_new"] = result[user_col].apply(
            lambda u: 1.0 if u in new_users else 0.0
        )
        context.state["seen_users"].update(unique_users)
        
        # Update historical counts for Burst detection
        batch_counts = df[user_col].value_counts().to_dict()
        for u, count in batch_counts.items():
            context.state["user_event_counts"][u] = context.state["user_event_counts"].get(u, 0) + count
            
        # 2. User activity burst detection (Batch count / Historical average proxy)
        # Using a simplified historical fraction for burstiness
        result[f"{self.FEAT_PREFIX}user_burst_score"] = result[user_col].map(
            lambda u: batch_counts.get(u, 1) / max(1, context.state["user_event_counts"].get(u, 1))
        )
        
        # 3. Failed login ratio (per user in the current batch)
        outcome_col = self._resolve_col(df, self.OUTCOME_ALIASES)
        if outcome_col:
            # Assume outcome contains strings like 'failure' or 'success'
            failures = (df[outcome_col].astype(str).str.lower() == 'failure').astype(int)
            user_failures = failures.groupby(df[user_col]).transform('sum')
            user_totals = df.groupby(user_col)[user_col].transform('count')
            result[f"{self.FEAT_PREFIX}user_failed_login_ratio"] = user_failures / np.maximum(1, user_totals)
        
        # 4. Number of unique hosts accessed
        host_col = self._resolve_col(df, self.HOST_ALIASES)
        if host_col:
            unique_hosts = df.groupby(user_col)[host_col].transform('nunique')
            result[f"{self.FEAT_PREFIX}user_unique_hosts_accessed"] = unique_hosts
            
        # 5. Privilege escalation indicators
        # Simple heuristic: users who run commands like 'sudo' or 'su' or act as 'root'
        # If event.action contains escalation keywords
        action_col = self._resolve_col(df, self.ACTION_ALIASES)
        if action_col:
            is_priv_esc = df[action_col].astype(str).str.lower().isin(["sudo", "su", "elevated", "privilege_escalation"])
            result[f"{self.FEAT_PREFIX}user_priv_escalation_flag"] = is_priv_esc.astype(float)

        return result
