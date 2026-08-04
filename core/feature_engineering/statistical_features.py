"""
core/feature_engineering/statistical_features.py

Extracts Statistical Features across numerical columns:
- Rolling averages
- Rolling standard deviation
- Z-score
- Exponential moving averages

Why it is useful:
Provides baseline deviation metrics for any continuous feature.

Mathematical formula:
- Z-Score = (X - mu) / sigma
- EMA = alpha * X_t + (1 - alpha) * EMA_{t-1}

Computational complexity:
- O(N) using Pandas highly optimized C-backed routines.
"""

import pandas as pd
import numpy as np
from .base import BaseFeatureExtractor, FeatureContext

class StatisticalFeatureExtractor(BaseFeatureExtractor):
    
    def fit_transform(self, df: pd.DataFrame, context: FeatureContext) -> pd.DataFrame:
        result = df.copy()
        
        # We target specific numeric features we want to apply stats to.
        # E.g., time_since_last_event, network bytes if available.
        # Here we demonstrate on a volume proxy: event count per host
        
        HOST_ALIASES = ["host.name", "host_name", "hostname"]
        host_col = self._resolve_col(df, HOST_ALIASES)
        
        if host_col:
            # Add a local counter
            result['__tmp_count'] = 1
            
            # Group by host and use rolling/EWM on the counts
            # Since this is a batch, we'll calculate rolling statistics sequentially within the batch.
            # To scale properly across millions, 'context' would store the previous EMA and variance per host.
            
            grouped = result.groupby(host_col)['__tmp_count']
            
            # Simple cumulative sum as a proxy for time-series volume
            cumsum = grouped.cumsum()
            
            # EMA of the volume
            # span=10 means an alpha of 2/(10+1) = 0.1818
            ema = cumsum.ewm(span=10, min_periods=1, adjust=False).mean()
            result[f"{self.FEAT_PREFIX}stat_host_volume_ema"] = ema
            
            # Rolling Std Dev
            # min_periods=2 to avoid NaN on first event
            roll_std = cumsum.rolling(window=10, min_periods=2).std().fillna(0)
            result[f"{self.FEAT_PREFIX}stat_host_volume_std"] = roll_std
            
            # Z-Score approximation
            # (Current Volume - EMA) / (Std Dev + epsilon)
            result[f"{self.FEAT_PREFIX}stat_host_volume_zscore"] = (cumsum - ema) / (roll_std + 1e-9)
            
            result = result.drop(columns=['__tmp_count'])
            
        return result
