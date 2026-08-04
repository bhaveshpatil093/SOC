"""
models/ensemble/frequency.py

Frequency Rarity Anomaly Detector.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any

from .base import BaseDetector, DetectionResult

class FrequencyDetector(BaseDetector):
    def __init__(self, max_history: int = 0, num_bins: int = 50):
        super().__init__(max_history)
        self.num_bins = num_bins
        # Store histogram frequencies per feature column
        self.histograms = {}
        
    def fit(self, X: pd.DataFrame) -> None:
        # For numeric features, we discretize and count frequencies
        # Simple implementation: use np.histogram on each column
        X_arr = X.to_numpy()
        for i in range(X_arr.shape[1]):
            col_data = X_arr[:, i]
            counts, bin_edges = np.histogram(col_data, bins=self.num_bins, density=True)
            # We don't do perfect incremental updating here for simplicity,
            # but we could blend old and new histograms.
            self.histograms[i] = (counts, bin_edges)

    def predict(self, X: pd.DataFrame) -> DetectionResult:
        if not self.histograms:
            self.fit(X)
            
        X_arr = X.to_numpy()
        rarity_scores = np.zeros(X_arr.shape)
        
        # Map values to their bin probabilities
        for i in range(X_arr.shape[1]):
            if i in self.histograms:
                counts, bin_edges = self.histograms[i]
                # Find which bin each value falls into
                bin_indices = np.digitize(X_arr[:, i], bin_edges) - 1
                bin_indices = np.clip(bin_indices, 0, len(counts) - 1)
                
                # Probability = counts[bin_index]. We want rarity, so 1 - prob (normalized)
                # To be precise mathematically: score = -log(prob)
                probs = counts[bin_indices] + 1e-9
                rarity_scores[:, i] = -np.log(probs)
                
        # Aggregate rarity across features (e.g., max or mean rarity)
        raw_scores = np.mean(rarity_scores, axis=1)
        
        # Convert to confidence. Range depends on data, typically [0, 10]
        confidence = np.clip(raw_scores / 10.0, 0, 1)
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
                "model": "Frequency Rarity",
                "reason": "Evaluates the historical frequency of feature values. High scores indicate extremely rare numerical values."
            })
        return explanations
