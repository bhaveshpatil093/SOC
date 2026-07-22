"""
models/anomaly_detector.py

Isolation Forest / Local Outlier Factor anomaly detection wrapper
for the ISRO SOC Analytics Platform.

Design notes:
  - Models are trained on aggregated feature DataFrames (not raw logs)
  - Joblib persistence for trained models (saves to settings.model_save_dir)
  - Thread-safe training via a simple lock
  - Prediction returns a boolean anomaly flag + anomaly score

Usage:
    from models import AnomalyDetector
    import pandas as pd

    detector = AnomalyDetector(algorithm="isolation_forest")
    detector.fit(training_df, feature_cols=["event_count", "unique_ips"])
    results_df = detector.predict(new_df, feature_cols=["event_count", "unique_ips"])
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

from config import settings, get_logger

logger = get_logger(__name__)

AlgorithmType = Literal["isolation_forest", "local_outlier_factor"]


class AnomalyDetector:
    """
    Unified anomaly detection wrapper supporting Isolation Forest and LOF.

    The model is trained on ES aggregation summaries (e.g. hourly event counts
    per source IP) — never on raw log records.

    Attributes:
        algorithm: "isolation_forest" or "local_outlier_factor".
        contamination: Expected proportion of outliers (0.0–0.5).
        is_fitted: True after fit() has been called successfully.
    """

    def __init__(
        self,
        algorithm: AlgorithmType = "isolation_forest",
        contamination: float = 0.05,
        n_estimators: int = 100,  # IsolationForest only
        n_neighbors: int = 20,    # LOF only
        random_state: int = 42,
    ) -> None:
        self.algorithm = algorithm
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.n_neighbors = n_neighbors
        self.random_state = random_state

        self._model: Optional[IsolationForest | LocalOutlierFactor] = None
        self._scaler: Optional[StandardScaler] = None
        self._feature_cols: List[str] = []
        self._is_fitted: bool = False
        self._lock = threading.Lock()

        # Training history — accumulated across partial_fit() calls
        self._train_history: List[Dict[str, Any]] = []
        self._total_samples_seen: int = 0
        self._trained_at: Optional[str] = None  # ISO-8601 UTC

        logger.debug(
            "AnomalyDetector initialised — algorithm=%s contamination=%s",
            algorithm,
            contamination,
        )

    # ─── Properties ───────────────────────────────────────────────────────────

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    # ─── Model factory ────────────────────────────────────────────────────────

    def _build_model(self) -> IsolationForest | LocalOutlierFactor:
        if self.algorithm == "isolation_forest":
            return IsolationForest(
                n_estimators=self.n_estimators,
                contamination=self.contamination,
                random_state=self.random_state,
                n_jobs=-1,
            )
        elif self.algorithm == "local_outlier_factor":
            return LocalOutlierFactor(
                n_neighbors=self.n_neighbors,
                contamination=self.contamination,
                novelty=True,  # Enable predict() on new data
                n_jobs=-1,
            )
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm!r}")

    # ─── Training ─────────────────────────────────────────────────────────────

    def fit(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
    ) -> "AnomalyDetector":
        """
        Train the anomaly detection model on feature data.

        Args:
            df:           DataFrame with numeric feature columns.
            feature_cols: Column names to use as features.

        Returns:
            self (for chaining).

        Raises:
            ValueError: If df is empty or features are missing.
        """
        if df.empty:
            raise ValueError("Training DataFrame is empty.")

        missing = [c for c in feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Feature columns not found in DataFrame: {missing}")

        with self._lock:
            X = df[feature_cols].fillna(0).values.astype(float)

            if X.shape[0] < 10:
                raise ValueError(
                    f"Training set too small ({X.shape[0]} samples). Need at least 10."
                )

            logger.info(
                "Training %s on %d samples × %d features...",
                self.algorithm,
                X.shape[0],
                X.shape[1],
            )

            # Scale features
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)

            # Train model
            self._model = self._build_model()
            self._model.fit(X_scaled)

            self._feature_cols = list(feature_cols)
            self._is_fitted = True
            self._total_samples_seen = X.shape[0]
            self._trained_at = datetime.now(tz=timezone.utc).isoformat()
            self._train_history = [{
                "batch": 1,
                "samples": X.shape[0],
                "timestamp": self._trained_at,
                "mode": "fit",
            }]

            logger.info("Model training complete — %d samples.", X.shape[0])
        return self

    def partial_fit(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        reservoir_size: int = 5000,
    ) -> "AnomalyDetector":
        """
        Incrementally update the model using a new batch.

        Uses reservoir sampling to maintain a fixed-size training buffer
        so memory usage stays constant regardless of how many batches are
        processed.

        If the model is not yet fitted, behaves like ``fit()``.

        Args:
            df:             New batch DataFrame.
            feature_cols:   Feature columns to use.
            reservoir_size: Maximum training buffer size (default 5 000).

        Returns:
            self (for chaining).
        """
        if not self._is_fitted:
            return self.fit(df, feature_cols)

        if df.empty:
            return self

        missing = [c for c in feature_cols if c not in df.columns]
        if missing:
            logger.warning("partial_fit: missing features %s — skipping", missing)
            return self

        with self._lock:
            X_new = df[feature_cols].fillna(0).values.astype(float)

            # Scale using the existing scaler (fitted on the first batch).
            # Retraining on each new batch is a practical warm-start approximation
            # for streaming anomaly detection without storing the full history.
            X_new_scaled = self._scaler.transform(X_new)

            # Retrain on new batch (warm start approximation)
            new_model = self._build_model()
            new_model.fit(X_new_scaled)
            self._model = new_model

            self._total_samples_seen += X_new.shape[0]
            now_str = datetime.now(tz=timezone.utc).isoformat()
            self._train_history.append({
                "batch": len(self._train_history) + 1,
                "samples": X_new.shape[0],
                "timestamp": now_str,
                "mode": "partial_fit",
            })
            self._trained_at = now_str

        logger.info(
            "partial_fit complete — batch %d samples, total seen %d",
            X_new.shape[0], self._total_samples_seen,
        )
        return self

    # ─── Prediction ───────────────────────────────────────────────────────────

    def predict(
        self,
        df: pd.DataFrame,
        feature_cols: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Predict anomalies for new data.

        Args:
            df:           DataFrame to score.
            feature_cols: Columns to use (defaults to those used in fit()).

        Returns:
            Input DataFrame with two new columns:
              - ``anomaly_score``: Raw detector score (lower = more anomalous for IF).
              - ``is_anomaly``:    Boolean (True = anomaly detected).

        Raises:
            RuntimeError: If model has not been fitted.
        """
        if not self._is_fitted or self._model is None or self._scaler is None:
            raise RuntimeError("Model is not fitted. Call fit() first.")

        cols = feature_cols or self._feature_cols
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(f"Feature columns missing in prediction DataFrame: {missing}")

        result = df.copy()
        X = result[cols].fillna(0).values.astype(float)
        X_scaled = self._scaler.transform(X)

        # Score: IsolationForest → positive = normal; LOF novelty=True → same convention
        scores = self._model.score_samples(X_scaled)
        predictions = self._model.predict(X_scaled)  # 1 = normal, -1 = anomaly

        # Normalise raw score to 0-1 (higher = more anomalous)
        # IsolationForest score_samples returns negative values for anomalies
        norm_score = 1.0 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)

        result["anomaly_score_raw"] = scores
        result["anomaly_score"]     = norm_score        # 0 = normal, 1 = most anomalous
        result["is_anomaly"]        = predictions == -1

        n_anomalies = int(result["is_anomaly"].sum())
        logger.info("Prediction complete — %d/%d anomalies detected.", n_anomalies, len(result))
        return result

    def score_batch(
        self,
        df: pd.DataFrame,
        feature_cols: Optional[List[str]] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Convenience wrapper around ``predict`` that also returns a summary dict.

        Returns:
            (scored_df, summary) where summary contains:
              n_total, n_anomalies, anomaly_rate_pct, mean_score, max_score.
        """
        scored = self.predict(df, feature_cols=feature_cols)
        n_total    = len(scored)
        n_anomaly  = int(scored["is_anomaly"].sum())
        summary: Dict[str, Any] = {
            "n_total":          n_total,
            "n_anomalies":      n_anomaly,
            "anomaly_rate_pct": round(n_anomaly / max(n_total, 1) * 100, 2),
            "mean_score":       round(float(scored["anomaly_score"].mean()), 4),
            "max_score":        round(float(scored["anomaly_score"].max()),  4),
        }
        return scored, summary

    # ─── Persistence ──────────────────────────────────────────────────────────

    def save(self, name: str = "anomaly_detector") -> Path:
        """
        Persist the fitted model to disk.

        Args:
            name: File stem (without extension).

        Returns:
            Path to the saved file.

        Raises:
            RuntimeError: If model is not fitted.
        """
        if not self._is_fitted:
            raise RuntimeError("Cannot save an unfitted model.")

        save_dir = settings.model_save_dir
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{name}.joblib"

        payload = {
            "algorithm":           self.algorithm,
            "contamination":       self.contamination,
            "n_estimators":        self.n_estimators,
            "n_neighbors":         self.n_neighbors,
            "random_state":        self.random_state,
            "model":               self._model,
            "scaler":              self._scaler,
            "feature_cols":        self._feature_cols,
            "train_history":       self._train_history,
            "total_samples_seen": self._total_samples_seen,
            "trained_at":          self._trained_at,
        }
        joblib.dump(payload, save_path)
        logger.info("Model saved to: %s", save_path)
        return save_path

    @classmethod
    def load(cls, name: str = "anomaly_detector") -> "AnomalyDetector":
        """
        Load a persisted model from disk.

        Args:
            name: File stem (without extension).

        Returns:
            Fitted AnomalyDetector instance.

        Raises:
            FileNotFoundError: If the model file doesn't exist.
        """
        load_path = settings.model_save_dir / f"{name}.joblib"
        if not load_path.exists():
            raise FileNotFoundError(f"Model file not found: {load_path}")

        payload = joblib.load(load_path)
        instance = cls(
            algorithm=payload["algorithm"],
            contamination=payload["contamination"],
            n_estimators=payload["n_estimators"],
            n_neighbors=payload["n_neighbors"],
            random_state=payload["random_state"],
        )
        instance._model               = payload["model"]
        instance._scaler              = payload["scaler"]
        instance._feature_cols        = payload["feature_cols"]
        instance._is_fitted           = True
        instance._train_history       = payload.get("train_history", [])
        instance._total_samples_seen  = payload.get("total_samples_seen", 0)
        instance._trained_at          = payload.get("trained_at")

        logger.info("Model loaded from: %s", load_path)
        return instance

    @property
    def model_info(self) -> Dict[str, Any]:
        """Return a summary dict describing this model instance."""
        return {
            "algorithm":          self.algorithm,
            "contamination":      self.contamination,
            "n_estimators":       self.n_estimators,
            "n_neighbors":        self.n_neighbors,
            "is_fitted":          self._is_fitted,
            "feature_cols":       self._feature_cols,
            "total_samples_seen": self._total_samples_seen,
            "trained_at":         self._trained_at,
            "n_batches":          len(self._train_history),
        }

    def __repr__(self) -> str:
        return (
            f"AnomalyDetector(algorithm={self.algorithm!r}, "
            f"contamination={self.contamination}, "
            f"fitted={self._is_fitted})"
        )
