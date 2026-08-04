"""
core/feature_engineering/time_features.py

Extracts Time Features:
- Hour of day
- Weekend
- Night activity
- Time since previous event
- Event burst score

Why it is useful:
Attackers often operate outside business hours or script automated bursts.

Mathematical formula:
- Time since previous = T_i - T_{i-1} per entity.
"""

import pandas as pd
import numpy as np
from .base import BaseFeatureExtractor, FeatureContext

class TimeFeatureExtractor(BaseFeatureExtractor):
    
    TIMESTAMP_ALIASES = ["@timestamp", "timestamp", "TimeGenerated"]
    USER_ALIASES = ["user.name", "user_name", "username"]
    
    def fit_transform(self, df: pd.DataFrame, context: FeatureContext) -> pd.DataFrame:
        ts_col = self._resolve_col(df, self.TIMESTAMP_ALIASES)
        if not ts_col:
            return df
            
        result = df.copy()
        
        # Ensure datetime
        ts = pd.to_datetime(result[ts_col], errors="coerce", utc=True)
        
        # 1. Hour of day (normalized 0-1)
        result[f"{self.FEAT_PREFIX}time_hour"] = ts.dt.hour / 24.0
        
        # 2. Weekend flag (5 = Sat, 6 = Sun)
        result[f"{self.FEAT_PREFIX}time_is_weekend"] = ts.dt.dayofweek.isin([5, 6]).astype(float)
        
        # 3. Night activity (e.g. 10 PM to 5 AM)
        result[f"{self.FEAT_PREFIX}time_is_night"] = ts.dt.hour.isin([22, 23, 0, 1, 2, 3, 4, 5]).astype(float)
        
        # 4. Time since previous event (per user)
        user_col = self._resolve_col(df, self.USER_ALIASES)
        if user_col:
            # Sort by user and time to calculate diffs
            # Note: This is an approximation within the batch for scaling reasons.
            # To be fully historically accurate across batches, we would store the 
            # last seen timestamp per user in `context.state`.
            temp = pd.DataFrame({'user': result[user_col], 'ts': ts})
            temp['ts_num'] = temp['ts'].astype(np.int64) / 10**9 # seconds
            
            # Group by user and find diff
            temp['diff'] = temp.groupby('user')['ts_num'].diff().fillna(0)
            
            # Cap at 1 hour (3600 seconds) to avoid extreme outliers
            temp['diff'] = temp['diff'].clip(lower=0, upper=3600)
            
            result[f"{self.FEAT_PREFIX}time_since_last_event"] = temp['diff']
            
        # 5. Event burst score (Rolling density placeholder)
        # Detailed burst scoring requires statistical EWMA which will be handled in Statistical features
        
        return result
