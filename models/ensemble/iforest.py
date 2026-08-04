"""
models/ensemble/iforest.py

Isolation Forest Anomaly Detector.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from sklearn.ensemble import IsolationForest

from .base import BaseDetector, DetectionResult

class IsolationForestDetector(BaseDetector):
    def __init__(self, max_history: int = 10000, contamination: float = 0.05):
        super().__init__(max_history)
        self.model = IsolationForest(
            contamination=contamination, 
            random_state=42, 
            n_estimators=100
        )
        self.is_fitted = False
        
    def fit(self, X: pd.DataFrame) -> None:
        # Buffer historical data
        X_hist = self._update_history(X)
        
        # Fit Isolation Forest on the combined history
        self.model.fit(X_hist)
        self.is_fitted = True

    def predict(self, X: pd.DataFrame) -> DetectionResult:
        if not self.is_fitted:
            self.fit(X)
            
        # raw_scores: Path length score. Lower is more anomalous. 
        # sklearn's score_samples returns negative anomaly score.
        # Smaller values (more negative) -> more anomalous.
        raw_scores = self.model.score_samples(X)
        
        # Convert to confidence (0 to 1), where 1 = Highly anomalous
        # score_samples generally ranges from -1.0 to 0.0. 
        # We can map -1.0 -> 1.0 (Anomalous) and 0.0 -> 0.0 (Normal)
        confidence = np.clip(-raw_scores, 0, 1)
        
        # Binary prediction (-1 for outlier, 1 for inlier)
        preds = self.model.predict(X)
        anomaly = preds == -1
        
        explanations = self.explain(X)
        
        return DetectionResult(
            raw_scores=pd.Series(raw_scores, index=X.index),
            confidence=pd.Series(confidence, index=X.index),
            anomaly=pd.Series(anomaly, index=X.index),
            explanations=explanations
        )

    def explain(self, X: pd.DataFrame) -> List[Dict[str, Any]]:
        # SHAP could be used here. For simplicity and performance, 
        # we return basic explanations.
        explanations = []
        for _ in range(len(X)):
            explanations.append({
                "model": "Isolation Forest",
                "reason": "Anomalies are isolated quickly (short path length) in random tree partitions."
            })
        return explanations
