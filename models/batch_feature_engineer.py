"""
models/batch_feature_engineer.py

Security-domain feature engineering for the ML anomaly detection pipeline.

Operates exclusively on a single retrieved batch (pandas DataFrame) — never
on the full 2.77-billion-log dataset. All features are derived locally.

Feature Groups
--------------
1. Temporal       — hour, day_of_week, is_night, is_weekend, is_business_hours
2. Volume         — event counts per entity (host, user, src_ip) within the batch
3. Diversity      — unique-value counts (unique_dst_ips per src_ip, etc.)
4. Rarity         — inverse-frequency scores (rare events score higher)
5. Behavioural    — failure ratios, severity proportions
6. Network        — src-IP class, private/public, port-based flags
7. Rolling        — 3-point rolling mean / std of batch-level event count

Usage
-----
    from models.batch_feature_engineer import BatchFeatureEngineer
    import pandas as pd

    # df is the cleaned_df from PreprocessingPipeline.run()
    engineer = BatchFeatureEngineer()
    feature_df, feature_cols = engineer.transform(df)
"""

from __future__ import annotations

import ipaddress
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import settings, get_logger

logger = get_logger(__name__)

# Feature column prefix — all engineered columns use this so they're easy to filter
ML_FEAT_PREFIX = "_ml_"

# ─── Configurable field name resolution ───────────────────────────────────────

_FIELD_ALIASES: Dict[str, List[str]] = {
    "timestamp":    [settings.es_time_field, "@timestamp"],
    "hostname":     [settings.es_hostname_field, "host.name", "host_name", "hostname"],
    "username":     [settings.es_username_field, "user.name", "user_name", "username"],
    "src_ip":       [settings.es_src_ip_field, "source.ip", "src_ip", "source_ip"],
    "dst_ip":       [settings.es_dst_ip_field, "destination.ip", "dst_ip", "dest_ip"],
    "event_id":     [settings.es_event_id_field, "event.id", "event_id", "EventID"],
    "severity":     [settings.es_severity_field, "event.severity", "severity", "log.level"],
    "category":     [settings.es_category_field, "event.category", "category"],
    "outcome":      ["event.outcome", "outcome", "event_outcome"],
    "dst_port":     ["destination.port", "dst_port", "port"],
    "bytes_sent":   ["network.bytes", "source.bytes", "bytes_sent"],
    "process_name": ["process.name", "process_name", "Image"],
}


def _resolve(df: pd.DataFrame, logical_name: str) -> Optional[str]:
    """Return the first DataFrame column matching any alias for *logical_name*."""
    for candidate in _FIELD_ALIASES.get(logical_name, []):
        if candidate in df.columns:
            return candidate
        # Try dot-notation replaced with underscore
        alt = candidate.replace(".", "_")
        if alt in df.columns:
            return alt
    return None


def _safe_str(series: pd.Series) -> pd.Series:
    """Cast series to string, treating NaN as empty string."""
    return series.fillna("").astype(str)


# ─── IP helpers ───────────────────────────────────────────────────────────────

def _is_private(ip: Any) -> float:
    if not ip or (isinstance(ip, float) and np.isnan(ip)):
        return np.nan
    try:
        return float(ipaddress.ip_address(str(ip).split("/")[0].strip()).is_private)
    except ValueError:
        return np.nan


def _first_octet(ip: Any) -> float:
    if not ip or (isinstance(ip, float) and np.isnan(ip)):
        return np.nan
    try:
        return float(str(ip).split(".")[0].strip())
    except (ValueError, IndexError):
        return np.nan


# ─── BatchFeatureEngineer ─────────────────────────────────────────────────────

class BatchFeatureEngineer:
    """
    Derives security-specific numeric features from a single log batch DataFrame.

    The transformer is stateless — it does not retain any state between calls,
    making it safe for repeated batch processing without memory accumulation.

    Parameters
    ----------
    min_rows : int
        Minimum number of rows required to run the transform.
        Raises ValueError if the batch is smaller than this.
    """

    def __init__(self, min_rows: int = 5) -> None:
        self.min_rows = min_rows

    def transform(
        self,
        df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Run the full feature engineering pipeline on *df*.

        Args:
            df: Cleaned log DataFrame (output of PreprocessingPipeline).

        Returns:
            (feature_df, feature_cols)
            - feature_df   : Input df with all ML_FEAT_* columns appended.
            - feature_cols : Names of newly added feature columns (all numeric,
                             suitable for direct use with AnomalyDetector.fit()).

        Raises:
            ValueError: If df has fewer rows than min_rows.
        """
        if len(df) < self.min_rows:
            raise ValueError(
                f"Batch too small for feature engineering: {len(df)} rows "
                f"(minimum {self.min_rows})."
            )

        result = df.copy()
        added: List[str] = []

        # Resolve columns once
        ts_col      = _resolve(result, "timestamp")
        host_col    = _resolve(result, "hostname")
        user_col    = _resolve(result, "username")
        src_col     = _resolve(result, "src_ip")
        dst_col     = _resolve(result, "dst_ip")
        sev_col     = _resolve(result, "severity")
        cat_col     = _resolve(result, "category")
        outcome_col = _resolve(result, "outcome")
        port_col    = _resolve(result, "dst_port")
        bytes_col   = _resolve(result, "bytes_sent")
        proc_col    = _resolve(result, "process_name")

        # ── Group 1: Temporal features ────────────────────────────────────────
        if ts_col:
            ts = pd.to_datetime(result[ts_col], errors="coerce", utc=True)
            added += self._add(result, f"{ML_FEAT_PREFIX}hour",               ts.dt.hour)
            added += self._add(result, f"{ML_FEAT_PREFIX}day_of_week",        ts.dt.dayofweek)
            added += self._add(result, f"{ML_FEAT_PREFIX}is_night",           (ts.dt.hour < 6) | (ts.dt.hour >= 22))
            added += self._add(result, f"{ML_FEAT_PREFIX}is_weekend",         ts.dt.dayofweek.isin([5, 6]))
            added += self._add(result, f"{ML_FEAT_PREFIX}is_business_hours",  ts.dt.hour.between(9, 17))
        else:
            # Placeholder zeros so the feature matrix is always the same width
            for name in ["hour", "day_of_week", "is_night", "is_weekend", "is_business_hours"]:
                added += self._add(result, f"{ML_FEAT_PREFIX}{name}", 0)

        # ── Group 2: Entity-level event frequency (volume) ────────────────────
        for field_col, label in [
            (host_col, "host"),
            (user_col, "user"),
            (src_col,  "src_ip"),
        ]:
            if field_col:
                freq = result[field_col].map(result[field_col].value_counts(normalize=False))
                added += self._add(result, f"{ML_FEAT_PREFIX}{label}_event_count", freq)
            else:
                added += self._add(result, f"{ML_FEAT_PREFIX}{label}_event_count", 0)

        # ── Group 3: Entity diversity features ────────────────────────────────
        # Unique destination IPs per source IP — high diversity = potential scan
        if src_col and dst_col:
            unique_dst_per_src = (
                result.groupby(src_col)[dst_col]
                .transform("nunique")
            )
            added += self._add(result, f"{ML_FEAT_PREFIX}src_unique_dst_ips", unique_dst_per_src)
        else:
            added += self._add(result, f"{ML_FEAT_PREFIX}src_unique_dst_ips", 0)

        # Unique users per host — high counts suggest lateral movement / shared host anomaly
        if host_col and user_col:
            unique_user_per_host = (
                result.groupby(host_col)[user_col]
                .transform("nunique")
            )
            added += self._add(result, f"{ML_FEAT_PREFIX}host_unique_users", unique_user_per_host)
        else:
            added += self._add(result, f"{ML_FEAT_PREFIX}host_unique_users", 0)

        # ── Group 4: Rarity score ─────────────────────────────────────────────
        # Rarity = 1 / frequency (normalised). Rare events get higher scores.
        if src_col:
            freq_norm = result[src_col].map(
                result[src_col].value_counts(normalize=True)
            )
            rarity = 1.0 / (freq_norm.clip(lower=1e-9))
            # Normalise rarity to 0-1 range within this batch
            rarity_norm = (rarity - rarity.min()) / (rarity.max() - rarity.min() + 1e-9)
            added += self._add(result, f"{ML_FEAT_PREFIX}src_ip_rarity", rarity_norm)
        else:
            added += self._add(result, f"{ML_FEAT_PREFIX}src_ip_rarity", 0)

        # ── Group 5: Behavioural / outcome features ───────────────────────────
        if outcome_col:
            is_fail = _safe_str(result[outcome_col]).str.lower().isin(
                ["failure", "fail", "failed", "error", "denied", "reject"]
            ).astype(float)
            added += self._add(result, f"{ML_FEAT_PREFIX}is_failure", is_fail)

            # Failure ratio per source IP (if available)
            if src_col:
                result["_tmp_fail"] = is_fail
                fail_ratio = result.groupby(src_col)["_tmp_fail"].transform("mean")
                added += self._add(result, f"{ML_FEAT_PREFIX}src_failure_ratio", fail_ratio)
                result.drop(columns=["_tmp_fail"], inplace=True)
            else:
                added += self._add(result, f"{ML_FEAT_PREFIX}src_failure_ratio", 0)
        else:
            added += self._add(result, f"{ML_FEAT_PREFIX}is_failure", 0)
            added += self._add(result, f"{ML_FEAT_PREFIX}src_failure_ratio", 0)

        # ── Group 6: Severity encoding ────────────────────────────────────────
        _SEV_MAP = {
            "critical": 4, "high": 3, "medium": 2, "low": 1,
            "informational": 0, "info": 0, "debug": -1, "unknown": 1,
            "4": 4, "3": 3, "2": 2, "1": 1, "0": 0,
        }
        if sev_col:
            sev_num = _safe_str(result[sev_col]).str.lower().map(_SEV_MAP).fillna(1)
            added += self._add(result, f"{ML_FEAT_PREFIX}severity_score", sev_num)
        else:
            added += self._add(result, f"{ML_FEAT_PREFIX}severity_score", 0)

        # ── Group 7: Network features ─────────────────────────────────────────
        if src_col:
            added += self._add(result, f"{ML_FEAT_PREFIX}src_is_private",
                               result[src_col].apply(_is_private))
            added += self._add(result, f"{ML_FEAT_PREFIX}src_first_octet",
                               result[src_col].apply(_first_octet))
        else:
            added += self._add(result, f"{ML_FEAT_PREFIX}src_is_private",   np.nan)
            added += self._add(result, f"{ML_FEAT_PREFIX}src_first_octet",  np.nan)

        # Privileged port flag (src or dst port < 1024)
        if port_col:
            port_num = pd.to_numeric(result[port_col], errors="coerce")
            added += self._add(result, f"{ML_FEAT_PREFIX}dst_privileged_port",
                               (port_num < 1024).astype(float))
        else:
            added += self._add(result, f"{ML_FEAT_PREFIX}dst_privileged_port", 0)

        # ── Group 8: Byte volume features ─────────────────────────────────────
        if bytes_col:
            byte_num = pd.to_numeric(result[bytes_col], errors="coerce").fillna(0)
            byte_log = np.log1p(byte_num)
            added += self._add(result, f"{ML_FEAT_PREFIX}bytes_log", byte_log)

            # Per-src_ip total bytes in batch (if src_col available)
            if src_col:
                result["_tmp_bytes"] = byte_num
                src_total_bytes = result.groupby(src_col)["_tmp_bytes"].transform("sum")
                added += self._add(result, f"{ML_FEAT_PREFIX}src_total_bytes_log",
                                   np.log1p(src_total_bytes))
                result.drop(columns=["_tmp_bytes"], inplace=True)
            else:
                added += self._add(result, f"{ML_FEAT_PREFIX}src_total_bytes_log", 0)
        else:
            added += self._add(result, f"{ML_FEAT_PREFIX}bytes_log",            0)
            added += self._add(result, f"{ML_FEAT_PREFIX}src_total_bytes_log",  0)

        # ── Finalize: fill any remaining NaN in ML features with median ───────
        ml_cols = [c for c in added if c in result.columns]
        for col in ml_cols:
            if result[col].isna().any():
                median = result[col].median()
                result[col] = result[col].fillna(median if not np.isnan(median) else 0.0)
            # Ensure float64 for sklearn
            result[col] = result[col].astype(float)

        # Deduplicate (shouldn't happen, but guard)
        ml_cols = list(dict.fromkeys(ml_cols))

        logger.info(
            "BatchFeatureEngineer: %d rows → %d ML features derived",
            len(df), len(ml_cols),
        )
        return result, ml_cols

    # ─── Private helper ───────────────────────────────────────────────────────

    @staticmethod
    def _add(df: pd.DataFrame, name: str, values: Any) -> List[str]:
        """Assign *values* to df[name] in-place; return [name] on success."""
        try:
            df[name] = values
            return [name]
        except Exception as exc:
            logger.warning("Feature %r skipped: %s", name, exc)
            return []

    # ─── Utility: describe features ───────────────────────────────────────────

    @staticmethod
    def describe_features(df: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
        """Return a concise summary DataFrame for *feature_cols*."""
        rows = []
        for col in feature_cols:
            if col not in df.columns:
                continue
            s = df[col]
            rows.append({
                "Feature": col.replace(ML_FEAT_PREFIX, ""),
                "Mean":    round(float(s.mean()), 4),
                "Std":     round(float(s.std()),  4),
                "Min":     round(float(s.min()),  4),
                "Max":     round(float(s.max()),  4),
                "Null %":  round(float(s.isna().mean()) * 100, 1),
            })
        return pd.DataFrame(rows)
