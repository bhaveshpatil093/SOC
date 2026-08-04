"""
core/feature_engineering/base.py

Provides the core dataclasses and abstract base class for all feature extractors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import pandas as pd

@dataclass
class FeatureContext:
    """
    Maintains historical state across batches to allow feature engineering
    to be absolute rather than relative.
    """
    state: Dict[str, Any] = field(default_factory=dict)
    
    def save(self, path: Path) -> None:
        """Persist state to disk for future runs."""
        joblib.dump(self.state, path)
        
    @classmethod
    def load(cls, path: Path) -> 'FeatureContext':
        """Load state from disk, or initialize empty if not found."""
        if path.exists():
            return cls(state=joblib.load(path))
        return cls()


class BaseFeatureExtractor(ABC):
    """
    Abstract base class for all feature engineering components.
    """
    
    # Prefix added to all engineered features
    FEAT_PREFIX = "_ml_"
    
    @abstractmethod
    def fit_transform(self, df: pd.DataFrame, context: FeatureContext) -> pd.DataFrame:
        """
        Calculates features for the dataframe, updating context state as needed.
        Must return the dataframe with new features appended.
        """
        pass
        
    def _resolve_col(self, df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
        """Resolve the active column name in the DataFrame given aliases."""
        for col in aliases:
            if col in df.columns:
                return col
            alt = col.replace(".", "_")
            if alt in df.columns:
                return alt
        return None
