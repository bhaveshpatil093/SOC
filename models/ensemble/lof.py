"""
models/ensemble/lof.py

Local Outlier Factor (LOF) Anomaly Detector.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from sklearn.neighbors import LocalOutlierFactor

from .base import BaseDetector, DetectionResult

class LOFDetector(BaseDetector):
    def __init__(self, max_history: int = 5000, n_neighbors: int = 20, contamination: float = 0.05):
        # LOF is O(N^2) for distance computation, so we use a smaller default history.
        super().__init__(max_history)
        # novelty=True allows us to fit on history and predict on new data
        self.model = LocalOutlierFactor(
            n_neighbors=n_neighbors, 
            contamination=contamination, 
            novelty=True
        )
        self.is_fitted = False
        
    def fit(self, X: pd.DataFrame) -> None:
        X_hist = self._update_history(X)
        
        # Fit LOF. Must have at least n_neighbors samples.
        if len(X_hist) >= self.model.n_neighbors:
            self.model.fit(X_hist)
            self.is_fitted = True

    def predict(self, X: pd.DataFrame) -> DetectionResult:
        if not self.is_fitted:
            self.fit(X)
            
        if not self.is_fitted:
            # Fallback if not enough history
            zeros = pd.Series(0.0, index=X.index)
            bools = pd.Series(False, index=X.index)
            return DetectionResult(zeros, zeros, bools, self.explain(X))
            
        # score_samples: Opposite of LOF (higher/closer to 0 is normal, lower/more negative is anomalous)
        raw_scores = self.model.score_samples(X)
        
        # Absolute LOF score is usually > 1 for anomalies. 
        # sklearn score_samples is roughly -LOF.
        # Confidence mapping: if LOF > 1.5, confidence -> high.
        lof_scores = -raw_scores
        # Map LOF [1.0, 3.0] to Confidence [0.0, 1.0]
        confidence = np.clip((lof_scores - 1.0) / 2.0, 0, 1)
        
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
        explanations = []
        for _ in range(len(X)):
            explanations.append({
                "model": "Local Outlier Factor",
                "reason": "Measures local density deviation vs k-nearest neighbors. LOF > 1.5 indicates significant low density."
            })
        return explanations
