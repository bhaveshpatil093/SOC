"""
models/ensemble/ocsvm.py

One-Class Support Vector Machine (OCSVM) Anomaly Detector.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from sklearn.svm import OneClassSVM

from .base import BaseDetector, DetectionResult

class OCSVMDetector(BaseDetector):
    def __init__(self, max_history: int = 5000, nu: float = 0.05, kernel: str = 'rbf'):
        # OCSVM scales at O(N^2) to O(N^3), so history should be relatively small
        super().__init__(max_history)
        self.model = OneClassSVM(nu=nu, kernel=kernel, gamma='scale')
        self.is_fitted = False
        
    def fit(self, X: pd.DataFrame) -> None:
        X_hist = self._update_history(X)
        self.model.fit(X_hist)
        self.is_fitted = True

    def predict(self, X: pd.DataFrame) -> DetectionResult:
        if not self.is_fitted:
            self.fit(X)
            
        # decision_function returns distance to the separating hyperplane.
        # Positive = normal, Negative = anomaly.
        raw_scores = self.model.decision_function(X)
        
        # Map negative distances to high confidence. 
        # Distance generally in range [-10, 10] depending on gamma.
        # We cap at -5 for 1.0 confidence.
        # Distance 0 -> Confidence 0.5 (On the boundary)
        # Distance > 0 -> Confidence < 0.5
        confidence = np.clip(0.5 - (raw_scores / 10.0), 0, 1)
        
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
                "model": "One-Class SVM",
                "reason": "Evaluates distance from the maximal margin hyperplane in the RBF kernel space. Negative distance = Anomaly."
            })
        return explanations
