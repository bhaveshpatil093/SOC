"""
models/ensemble/base.py

Base classes and interfaces for the Ensemble Anomaly Detection Engine.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Union
import pandas as pd
import numpy as np

@dataclass
class DetectionResult:
    """Standardized output from any individual anomaly detection model."""
    raw_scores: pd.Series      # The mathematical score from the model
    confidence: pd.Series      # Normalized 0.0 - 1.0 confidence of being anomalous
    anomaly: pd.Series         # Boolean Series indicating if it is an anomaly
    explanations: List[Dict[str, Any]] # Human-readable or feature-importance explanations


class BaseDetector(ABC):
    """
    Abstract interface that all ensemble detectors must implement.
    """
    
    def __init__(self, max_history: int = 10000):
        """
        Args:
            max_history: Max number of historical samples to retain for retraining or rolling analysis.
        """
        self.max_history = max_history
        # X_history holds numerical feature arrays
        self.X_history: Union[np.ndarray, None] = None
        
    def _update_history(self, X: pd.DataFrame) -> np.ndarray:
        """Appends to history buffer and truncates to max_history."""
        arr = X.to_numpy()
        if self.X_history is None:
            self.X_history = arr
        else:
            self.X_history = np.vstack([self.X_history, arr])
            
        if len(self.X_history) > self.max_history:
            self.X_history = self.X_history[-self.max_history:]
            
        return self.X_history

    @abstractmethod
    def fit(self, X: pd.DataFrame) -> None:
        """Train or update the model with new data X."""
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> DetectionResult:
        """Score the data and return a standard DetectionResult."""
        pass
        
    def predict_proba(self, X: pd.DataFrame) -> pd.Series:
        """Helper to return only confidence scores (0.0 to 1.0)."""
        return self.predict(X).confidence

    @abstractmethod
    def explain(self, X: pd.DataFrame) -> List[Dict[str, Any]]:
        """Return a feature-attribution or mathematical explanation for the predictions."""
        pass
