"""
core/feature_engineering/event_features.py

Extracts Event Features:
- Event category rarity
- Event outcome ratio
- Authentication failures
- File modification count
- Network connection count

Why it is useful:
Detects brute-forcing, ransomware (file mods), and scanning (network connections).

Mathematical formula:
- Category Rarity = 1 - P(category)
"""

import pandas as pd
from .base import BaseFeatureExtractor, FeatureContext

class EventFeatureExtractor(BaseFeatureExtractor):
    
    CATEGORY_ALIASES = ["event.category", "category"]
    ACTION_ALIASES = ["event.action", "action"]
    OUTCOME_ALIASES = ["event.outcome", "outcome"]
    
    def fit_transform(self, df: pd.DataFrame, context: FeatureContext) -> pd.DataFrame:
        result = df.copy()
        
        category_col = self._resolve_col(df, self.CATEGORY_ALIASES)
        action_col = self._resolve_col(df, self.ACTION_ALIASES)
        outcome_col = self._resolve_col(df, self.OUTCOME_ALIASES)
        
        if category_col:
            # 1. Event category rarity
            cat_freq = df[category_col].value_counts(normalize=True)
            result[f"{self.FEAT_PREFIX}event_category_rarity"] = 1.0 - result[category_col].map(cat_freq).fillna(0)
            
            # File modification and Network flags based on category
            cats = df[category_col].astype(str).str.lower()
            if isinstance(cats.iloc[0], str) or isinstance(cats.iloc[0], list):
                # Handle ECS array-like string representation if present
                is_file = cats.str.contains('file')
                is_network = cats.str.contains('network')
                
                result[f"{self.FEAT_PREFIX}event_is_file_mod"] = is_file.astype(float)
                result[f"{self.FEAT_PREFIX}event_is_network"] = is_network.astype(float)
        
        if action_col and outcome_col:
            # Authentication failures
            actions = df[action_col].astype(str).str.lower()
            outcomes = df[outcome_col].astype(str).str.lower()
            
            is_auth = actions.str.contains('auth|login|logon')
            is_fail = outcomes.str.contains('fail')
            
            result[f"{self.FEAT_PREFIX}event_is_auth_failure"] = (is_auth & is_fail).astype(float)
            
        return result
