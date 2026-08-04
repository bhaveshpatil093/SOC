"""
models/ensemble/autoencoder.py

Autoencoder Reconstruction Error Anomaly Detector.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from sklearn.neural_network import MLPRegressor

from .base import BaseDetector, DetectionResult

class AutoencoderDetector(BaseDetector):
    def __init__(self, max_history: int = 10000, hidden_layer_sizes: tuple = (16, 8, 16)):
        super().__init__(max_history)
        self.model = MLPRegressor(
            hidden_layer_sizes=hidden_layer_sizes,
            activation='relu',
            solver='adam',
            random_state=42,
            max_iter=1,  # We manually iterate in partial_fit
            warm_start=True
        )
        self.is_fitted = False
        
    def fit(self, X: pd.DataFrame) -> None:
        # Convert to numpy and fillna to handle missing values
        X_arr = np.nan_to_num(X.to_numpy(), nan=0.0)
        
        # Neural networks expect target y = X for autoencoders
        # We use partial_fit to continuously update the weights online
        self.model.partial_fit(X_arr, X_arr)
        self.is_fitted = True

    def predict(self, X: pd.DataFrame) -> DetectionResult:
        if not self.is_fitted:
            self.fit(X)
            
        X_arr = np.nan_to_num(X.to_numpy(), nan=0.0)
        
        # Reconstruct X
        X_pred = self.model.predict(X_arr)
        
        # Calculate Mean Squared Error per sample
        mse = np.mean(np.power(X_arr - X_pred, 2), axis=1)
        raw_scores = mse
        
        # Convert absolute MSE to confidence (0 to 1) using exponential decay
        # Lambda parameter controls how quickly confidence reaches 1
        # Assumes normalized input data
        lambda_param = 0.5
        confidence = 1.0 - np.exp(-lambda_param * raw_scores)
        
        # Define anomaly threshold (e.g. confidence > 0.8)
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
                "model": "Autoencoder",
                "reason": "Calculates reconstruction error (MSE) through a bottleneck neural network. High MSE indicates the event pattern is unrecognized."
            })
        return explanations
