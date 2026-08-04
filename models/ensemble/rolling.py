"""
models/ensemble/rolling.py

Rolling Anomaly Detector.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any

from .base import BaseDetector, DetectionResult

class RollingDetector(BaseDetector):
    def __init__(self, max_history: int = 0, short_window: int = 10, long_window: int = 100):
        super().__init__(max_history)
        self.short_window = short_window
        self.long_window = long_window
        # State
        self.recent_data = []

    def fit(self, X: pd.DataFrame) -> None:
        pass

    def predict(self, X: pd.DataFrame) -> DetectionResult:
        X_arr = X.to_numpy()
        raw_scores = np.zeros(X_arr.shape[0])
        
        for i, row in enumerate(X_arr):
            self.recent_data.append(row)
            if len(self.recent_data) > self.long_window:
                self.recent_data.pop(0)
                
            if len(self.recent_data) >= self.short_window:
                hist_arr = np.array(self.recent_data)
                
                # Short term stats
                short_arr = hist_arr[-self.short_window:]
                short_mean = np.mean(short_arr, axis=0)
                
                # Long term stats
                long_mean = np.mean(hist_arr, axis=0)
                long_std = np.std(hist_arr, axis=0) + 1e-9
                
                # Deviation of short-term mean from long-term mean
                deviation = np.abs((short_mean - long_mean) / long_std)
                raw_scores[i] = np.max(deviation)
                
        confidence = np.clip(raw_scores / 5.0, 0, 1)
        anomaly = confidence > 0.8
        
        explanations = self.explain(X)
        
        return DetectionResult(
            raw_scores=pd.Series(raw_scores, index=X.index),
            confidence=pd.Series(confidence, index=X.index),
            anomaly=pd.Series(anomaly, index=X.index),
            explanations=explanations
        )

    def explain(self, X: pd.DataFrame) -> List[Dict[str, Any]]:
        explanations = []
        for _ in range(len(X)):
            explanations.append({
                "model": "Rolling Detector",
                "reason": "Evaluates short-term rolling mean deviation against the long-term historical mean."
            })
        return explanations
