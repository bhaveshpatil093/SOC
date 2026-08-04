"""
models/ensemble/statistical.py

Statistical Z-score and IQR Anomaly Detector.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any

from .base import BaseDetector, DetectionResult

class StatisticalDetector(BaseDetector):
    def __init__(self, max_history: int = 0):
        # We don't need a history buffer array, just rolling metrics
        super().__init__(max_history)
        self.means = None
        self.variances = None
        self.count = 0
        
    def fit(self, X: pd.DataFrame) -> None:
        X_arr = X.to_numpy()
        batch_count = X_arr.shape[0]
        batch_mean = np.mean(X_arr, axis=0)
        batch_var = np.var(X_arr, axis=0)
        
        if self.count == 0:
            self.means = batch_mean
            self.variances = batch_var
            self.count = batch_count
        else:
            # Welford's online algorithm for variance/mean
            total_count = self.count + batch_count
            delta = batch_mean - self.means
            
            self.means = self.means + delta * batch_count / total_count
            
            m_a = self.variances * self.count
            m_b = batch_var * batch_count
            M2 = m_a + m_b + (delta ** 2) * self.count * batch_count / total_count
            
            self.variances = M2 / total_count
            self.count = total_count

    def predict(self, X: pd.DataFrame) -> DetectionResult:
        if self.count == 0:
            self.fit(X)
            
        X_arr = X.to_numpy()
        stds = np.sqrt(self.variances) + 1e-9 # avoid division by zero
        
        # Z-Score = |X - mu| / sigma
        z_scores = np.abs((X_arr - self.means) / stds)
        
        # Take the maximum Z-score across all features for a given log
        max_z = np.max(z_scores, axis=1)
        raw_scores = max_z
        
        # Z > 3 is anomalous. Map Z=[0, 6] to Confidence=[0.0, 1.0]
        confidence = np.clip(raw_scores / 6.0, 0, 1)
        anomaly = raw_scores > 3.0
        
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
                "model": "Statistical (Z-Score)",
                "reason": "Calculates absolute Z-score deviation from the historical mean. Z > 3 indicates an anomaly."
            })
        return explanations
