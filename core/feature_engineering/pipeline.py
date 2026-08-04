"""
core/feature_engineering/pipeline.py

The main orchestration module for the Cybersecurity Feature Engineering Pipeline.

This combines all individual feature extractors (User, IP, Host, Process, Time, Event, Stats)
and runs them sequentially on a DataFrame, updating the global FeatureContext.
"""

import pandas as pd
from typing import List, Tuple
from pathlib import Path

from .base import FeatureContext, BaseFeatureExtractor
from .user_features import UserFeatureExtractor
from .ip_features import IPFeatureExtractor
from .host_features import HostFeatureExtractor
from .process_features import ProcessFeatureExtractor
from .time_features import TimeFeatureExtractor
from .event_features import EventFeatureExtractor
from .statistical_features import StatisticalFeatureExtractor

class FeatureEngineeringPipeline:
    
    def __init__(self, context_path: str = None):
        """
        Initializes the pipeline with all extractors.
        If context_path is provided, loads historical state from disk.
        """
        self.extractors: List[BaseFeatureExtractor] = [
            TimeFeatureExtractor(),
            UserFeatureExtractor(),
            IPFeatureExtractor(),
            HostFeatureExtractor(),
            ProcessFeatureExtractor(),
            EventFeatureExtractor(),
            StatisticalFeatureExtractor()
        ]
        
        self.context_path = Path(context_path) if context_path else None
        
        if self.context_path and self.context_path.exists():
            self.context = FeatureContext.load(self.context_path)
        else:
            self.context = FeatureContext()

    def run(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """
        Runs the full feature engineering pipeline.
        
        Args:
            df: The raw or preprocessed pandas DataFrame of logs.
            
        Returns:
            Tuple containing:
            1. The original DataFrame with engineered features appended.
            2. A list of exactly which columns are the new ML features.
        """
        if df.empty:
            return df, []
            
        result = df.copy()
        
        # Execute each extractor sequentially
        for extractor in self.extractors:
            result = extractor.fit_transform(result, self.context)
            
        # Collect all new ML features (those prefixed with BaseFeatureExtractor.FEAT_PREFIX)
        ml_cols = [col for col in result.columns if col.startswith(BaseFeatureExtractor.FEAT_PREFIX)]
        
        # Ensure all ML features are numeric and NaN values are filled safely
        for col in ml_cols:
            result[col] = pd.to_numeric(result[col], errors='coerce').fillna(0.0)
            
        # Persist context if path is set
        if self.context_path:
            self.context.save(self.context_path)
            
        return result, ml_cols
