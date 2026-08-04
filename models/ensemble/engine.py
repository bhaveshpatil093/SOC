"""
models/ensemble/engine.py

Ensemble Detection Engine.
Combines multiple anomaly detection models using weighted confidence.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List

from .base import BaseDetector, DetectionResult
from .iforest import IsolationForestDetector
from .lof import LOFDetector
from .ocsvm import OCSVMDetector
from .autoencoder import AutoencoderDetector
from .statistical import StatisticalDetector
from .rolling import RollingDetector
from .frequency import FrequencyDetector

class EnsembleDetectionEngine:
    def __init__(self, weights: Dict[str, float] = None):
        """
        Args:
            weights: Dictionary mapping model names to their percentage weight (0 to 1).
        """
        # Default weights if not provided
        self.weights = weights or {
            "Isolation Forest": 0.25,
            "Autoencoder": 0.20,
            "LOF": 0.15,
            "One-Class SVM": 0.10,
            "Statistical": 0.10,
            "Frequency": 0.10,
            "Rolling": 0.10
        }
        
        # Initialize models
        self.models: Dict[str, BaseDetector] = {
            "Isolation Forest": IsolationForestDetector(),
            "Autoencoder": AutoencoderDetector(),
            "LOF": LOFDetector(),
            "One-Class SVM": OCSVMDetector(),
            "Statistical": StatisticalDetector(),
            "Frequency": FrequencyDetector(),
            "Rolling": RollingDetector()
        }

    def fit(self, X: pd.DataFrame) -> None:
        """Fit all models incrementally on the batch X."""
        for name, model in self.models.items():
            model.fit(X)

    def predict(self, X: pd.DataFrame) -> Dict[str, Any]:
        """
        Predicts anomalies using all models and combines them using weighted confidence.
        
        Returns:
            Dictionary matching the requested schema.
        """
        if X.empty:
            return {
                "raw_scores": {},
                "weighted_score": pd.Series(dtype=float),
                "confidence": pd.Series(dtype=float),
                "anomaly": pd.Series(dtype=bool),
                "model_explanations": []
            }
            
        n_samples = len(X)
        raw_scores = {}
        weighted_conf_sum = np.zeros(n_samples)
        total_weight = 0.0
        
        # Format expects explanations to be a list per sample, but our models output a list per sample.
        # We'll aggregate them into a master list per sample.
        master_explanations = [[] for _ in range(n_samples)]
        
        for name, model in self.models.items():
            # Skip if weight is 0
            weight = self.weights.get(name, 0.0)
            if weight == 0.0:
                continue
                
            res: DetectionResult = model.predict(X)
            
            raw_scores[name] = res.raw_scores.tolist()
            weighted_conf_sum += (res.confidence.to_numpy() * weight)
            total_weight += weight
            
            # Aggregate explanations
            for i in range(n_samples):
                master_explanations[i].append(res.explanations[i])
                
        # Calculate final weighted confidence (normalize by total weight)
        if total_weight > 0:
            final_confidence = weighted_conf_sum / total_weight
        else:
            final_confidence = weighted_conf_sum
            
        # Determine anomaly threshold (e.g. final confidence > 0.6)
        final_anomaly = final_confidence > 0.6
        
        return {
            "raw_scores": raw_scores,
            "weighted_score": pd.Series(final_confidence, index=X.index).tolist(), # Same as confidence
            "confidence": pd.Series(final_confidence, index=X.index).tolist(),
            "anomaly": pd.Series(final_anomaly, index=X.index).tolist(),
            "model_explanations": master_explanations
        }
