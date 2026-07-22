"""
core/preprocessing.py

Batch-scoped data preparation pipeline for the ISRO SOC Analytics platform.

Design Principles:
  - Operates ONLY on retrieved batches — never on the full dataset
  - Stateless: accepts a batch, returns a PipelineResult, stores no state
  - Preserves original flattened data alongside the cleaned copy
  - Engineered features are prefixed with ``_feat_`` for easy identification
  - Every stage is timed; quality metrics capture exactly what changed

Pipeline Stages:
  1. Flatten      — Extract + flatten ES _source dicts → DataFrame
  2. Drop meta    — Remove ES internal fields (_id, _index, _score, _type)
  3. Timestamps   — Parse time_field → UTC datetime; add _dt column
  4. Missing      — Compute null stats; apply strategy (drop/fill/flag)
  5. Standardise  — Apply user-supplied field rename map
  6. Deduplicate  — Remove exact duplicates within the batch
  7. Features     — Derive time, IP, and frequency features

Public surface:
    PipelineConfig     — configuration dataclass
    BatchQualityReport — quality metrics dataclass
    PipelineResult     — container for original/cleaned/feature DataFrames
    PreprocessingPipeline — stateless pipeline executor
"""

from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import settings, get_logger
from utils.data_utils import DataUtils
from utils.time_utils import TimeUtils

logger = get_logger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
FEAT_PREFIX   = "_feat_"       # All engineered feature columns carry this prefix
ORIGINAL_COL  = "_raw_source"  # Column preserving the original _source dict
_META_FIELDS  = frozenset({"_id", "_index", "_score", "_type", "_routing"})

# Numeric field name patterns (heuristics for auto-casting)
_NUMERIC_PATTERNS = (
    "port", "count", "bytes", "size", "duration", "latency",
    "pid", "code", "status", "severity", "score", "num",
)


# ─── Configuration ────────────────────────────────────────────────────────────

@dataclass
class PipelineConfig:
    """
    Configuration object for a single pipeline run.

    All parameters have sensible defaults that work out-of-the-box with
    Elastic Common Schema (ECS) field names.
    """

    # ── Timestamp ─────────────────────────────────────────────────────────
    time_field: str = field(default_factory=lambda: settings.es_time_field)

    # ── Missing value strategy ─────────────────────────────────────────────
    #   "flag"         — leave NaN as-is  (recommended — preserves information)
    #   "fill_default" — replace NaN with fill_string / fill_numeric
    #   "drop"         — drop rows with any NaN
    missing_strategy: str = "flag"
    fill_string: str = "<missing>"
    fill_numeric: float = 0.0

    # Columns with null% above this threshold are DROPPED entirely
    max_null_pct: float = 0.95   # 95% null → drop column

    # ── Deduplication ──────────────────────────────────────────────────────
    dedup_enabled: bool = True
    # If empty, all non-metadata columns are used as the composite key
    dedup_key_fields: List[str] = field(default_factory=list)

    # ── Field standardisation ──────────────────────────────────────────────
    # Map old_name → new_name for any fields that differ from ECS
    field_rename_map: Dict[str, str] = field(default_factory=dict)
    drop_metadata_fields: bool = True   # Remove ES _id, _index, _score

    # ── Feature engineering toggles ────────────────────────────────────────
    extract_time_features:      bool = True
    extract_ip_features:        bool = True
    extract_frequency_features: bool = True

    # ── Output options ─────────────────────────────────────────────────────
    keep_original: bool = True   # Preserve raw _source dict in ORIGINAL_COL


# ─── Quality Report ───────────────────────────────────────────────────────────

@dataclass
class BatchQualityReport:
    """
    Data quality metrics captured for a single preprocessed batch.

    Every numeric metric is produced by the pipeline automatically;
    this dataclass serves as a read-only summary for the UI layer.
    """

    # Size
    input_count:      int = 0
    output_count:     int = 0
    duplicates_removed: int = 0

    # Field coverage
    total_fields:      int = 0
    null_counts:       Dict[str, int]   = field(default_factory=dict)
    null_pct:          Dict[str, float] = field(default_factory=dict)
    fully_null_fields: List[str]        = field(default_factory=list)
    high_null_fields:  List[str]        = field(default_factory=list)
    dropped_columns:   List[str]        = field(default_factory=list)

    # Type handling
    timestamp_normalized:  int = 0
    timestamp_parse_errors: int = 0
    numeric_coercions:     Dict[str, int] = field(default_factory=dict)

    # Features
    features_added: List[str] = field(default_factory=list)

    # Performance
    elapsed_ms:    float             = 0.0
    stage_timings: Dict[str, float]  = field(default_factory=dict)

    # ── Derived properties ─────────────────────────────────────────────────

    @property
    def rows_dropped(self) -> int:
        return max(0, self.input_count - self.output_count)

    @property
    def retention_rate(self) -> float:
        """Percentage of input rows retained after cleaning (0–100)."""
        if self.input_count == 0:
            return 100.0
        return round(self.output_count / self.input_count * 100, 1)

    @property
    def coverage_score(self) -> float:
        """Average field coverage across all fields (0–100). Higher is better."""
        if not self.null_pct:
            return 100.0
        return round(100.0 - sum(self.null_pct.values()) / len(self.null_pct) * 100, 1)

    @property
    def dedup_rate(self) -> float:
        """Percentage of rows that were duplicates (0–100)."""
        if self.input_count == 0:
            return 0.0
        return round(self.duplicates_removed / self.input_count * 100, 1)


# ─── Pipeline Result ──────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """
    Complete output of a pipeline run.

    Three DataFrames are produced:
    - ``original_df``  — flattened raw ES _source (never mutated)
    - ``cleaned_df``   — after all cleaning stages (no features)
    - ``features_df``  — cleaned_df + all engineered _feat_* columns
    """

    original_df:  pd.DataFrame   # Flattened _source, untouched
    cleaned_df:   pd.DataFrame   # After cleaning (no features)
    features_df:  pd.DataFrame   # cleaned + feature columns
    quality:      BatchQualityReport
    config:       PipelineConfig

    @property
    def feature_columns(self) -> List[str]:
        return [c for c in self.features_df.columns if c.startswith(FEAT_PREFIX)]

    @property
    def n_features(self) -> int:
        return len(self.feature_columns)

    @property
    def has_features(self) -> bool:
        return self.n_features > 0


# ─── Pipeline ─────────────────────────────────────────────────────────────────

class PreprocessingPipeline:
    """
    Stateless batch preprocessing pipeline.

    Usage:
        pipeline = PreprocessingPipeline()
        result   = pipeline.run(raw_hits, config=PipelineConfig())
    """

    def run(
        self,
        raw_hits: List[Dict[str, Any]],
        config: Optional[PipelineConfig] = None,
    ) -> PipelineResult:
        """
        Execute the full preprocessing pipeline on one batch of raw ES hits.

        Args:
            raw_hits: List of ES hit dicts (from search response["hits"]["hits"]).
            config:   Pipeline configuration (uses defaults if None).

        Returns:
            PipelineResult with original_df, cleaned_df, features_df, and quality.
        """
        cfg = config or PipelineConfig()
        quality = BatchQualityReport(input_count=len(raw_hits))
        t0 = time.monotonic()
        stages: Dict[str, float] = {}

        # ── Stage 1: Flatten ──────────────────────────────────────────────────
        ts = time.monotonic()
        original_df = self._flatten_hits(raw_hits, cfg)
        quality.total_fields = len(original_df.columns)
        stages["1_flatten"] = round((time.monotonic() - ts) * 1000, 1)

        df = original_df.copy()

        # ── Stage 2: Drop ES metadata ─────────────────────────────────────────
        if cfg.drop_metadata_fields:
            ts = time.monotonic()
            drop = [c for c in df.columns if c in _META_FIELDS]
            df = df.drop(columns=drop, errors="ignore")
            stages["2_drop_meta"] = round((time.monotonic() - ts) * 1000, 1)

        # ── Stage 3: Normalise timestamps ─────────────────────────────────────
        ts = time.monotonic()
        df, ts_ok, ts_err = self._normalize_timestamps(df, cfg)
        quality.timestamp_normalized = ts_ok
        quality.timestamp_parse_errors = ts_err
        stages["3_timestamps"] = round((time.monotonic() - ts) * 1000, 1)

        # ── Stage 4: Numeric coercion ─────────────────────────────────────────
        ts = time.monotonic()
        df, coercions = self._coerce_numerics(df)
        quality.numeric_coercions = coercions
        stages["4_numerics"] = round((time.monotonic() - ts) * 1000, 1)

        # ── Stage 5: Handle missing values ────────────────────────────────────
        ts = time.monotonic()
        df, null_counts, null_pct, dropped_cols = self._handle_missing(df, cfg)
        quality.null_counts      = null_counts
        quality.null_pct         = null_pct
        quality.fully_null_fields = [f for f, p in null_pct.items() if p >= 1.0]
        quality.high_null_fields  = [f for f, p in null_pct.items() if 0.5 <= p < 1.0]
        quality.dropped_columns   = dropped_cols
        stages["5_missing"] = round((time.monotonic() - ts) * 1000, 1)

        # ── Stage 6: Standardise field names ─────────────────────────────────
        ts = time.monotonic()
        df = self._standardize_fields(df, cfg)
        stages["6_standardise"] = round((time.monotonic() - ts) * 1000, 1)

        # ── Stage 7: Deduplication ────────────────────────────────────────────
        ts = time.monotonic()
        df, n_dupes = self._deduplicate(df, cfg)
        quality.duplicates_removed = n_dupes
        stages["7_dedup"] = round((time.monotonic() - ts) * 1000, 1)

        cleaned_df = df.copy()
        quality.output_count = len(cleaned_df)

        # ── Stage 8: Feature engineering ──────────────────────────────────────
        ts = time.monotonic()
        features_df, feat_cols = self._engineer_features(cleaned_df, cfg)
        quality.features_added = feat_cols
        stages["8_features"] = round((time.monotonic() - ts) * 1000, 1)

        # ── Finalize ──────────────────────────────────────────────────────────
        quality.elapsed_ms    = round((time.monotonic() - t0) * 1000, 1)
        quality.stage_timings = stages

        logger.info(
            "Pipeline: %d → %d rows | %d dupes | %d features | %.1f ms",
            quality.input_count, quality.output_count,
            quality.duplicates_removed, len(feat_cols), quality.elapsed_ms,
        )

        return PipelineResult(
            original_df=original_df,
            cleaned_df=cleaned_df,
            features_df=features_df,
            quality=quality,
            config=cfg,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Stage Implementations
    # ──────────────────────────────────────────────────────────────────────────

    def _flatten_hits(
        self,
        hits: List[Dict[str, Any]],
        cfg: PipelineConfig,
    ) -> pd.DataFrame:
        """Extract and flatten ES _source from each hit into a flat dict row."""
        rows = []
        for hit in hits:
            source = hit.get("_source", hit)  # accept plain dicts or ES hit dicts
            flat = DataUtils.flatten_dict(source)
            if cfg.keep_original:
                flat[ORIGINAL_COL] = source
            rows.append(flat)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def _normalize_timestamps(
        self,
        df: pd.DataFrame,
        cfg: PipelineConfig,
    ) -> Tuple[pd.DataFrame, int, int]:
        """
        Parse cfg.time_field → UTC Timestamp; add a ``{time_field}_dt`` column.
        Original string column is preserved unchanged.
        """
        tf = cfg.time_field
        if tf not in df.columns:
            return df, 0, 0

        parsed: List[Optional[pd.Timestamp]] = []
        errors = 0

        for val in df[tf]:
            if pd.isna(val) or str(val).strip() == "":
                parsed.append(pd.NaT)
                errors += 1
                continue
            try:
                dt = TimeUtils.parse_any(str(val))
                parsed.append(pd.Timestamp(dt))
            except Exception:
                parsed.append(pd.NaT)
                errors += 1

        dt_col = f"{tf}_dt"
        df[dt_col] = parsed
        ok = int(df[dt_col].notna().sum())
        return df, ok, errors

    def _coerce_numerics(
        self,
        df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """
        Attempt to coerce object columns whose name suggests a numeric value
        (port, bytes, pid, …) using ``pd.to_numeric``.
        """
        coercions: Dict[str, int] = {}
        for col in df.select_dtypes(include="object").columns:
            col_lower = col.lower()
            if any(p in col_lower for p in _NUMERIC_PATTERNS):
                before_nulls = df[col].isna().sum()
                converted = pd.to_numeric(df[col], errors="coerce")
                if converted.notna().sum() > 0:
                    after_nulls = converted.isna().sum()
                    coerced = int(df[col].notna().sum() - (after_nulls - before_nulls))
                    if coerced > 0:
                        df[col] = converted
                        coercions[col] = coerced
        return df, coercions

    def _handle_missing(
        self,
        df: pd.DataFrame,
        cfg: PipelineConfig,
    ) -> Tuple[pd.DataFrame, Dict[str, int], Dict[str, float], List[str]]:
        """
        1. Compute null counts and percentages before any dropping.
        2. Drop columns where null% >= max_null_pct.
        3. Apply missing_strategy to remaining nulls.
        """
        if df.empty:
            return df, {}, {}, []

        n = len(df)
        null_counts_raw = df.isna().sum().to_dict()
        null_pct_raw = {col: round(cnt / n, 4) for col, cnt in null_counts_raw.items()}

        # Drop columns exceeding threshold (exclude the ORIGINAL_COL)
        drop_cols = [
            c for c, p in null_pct_raw.items()
            if p >= cfg.max_null_pct and c != ORIGINAL_COL
        ]
        df = df.drop(columns=drop_cols, errors="ignore")

        # Apply strategy to remaining nulls
        if cfg.missing_strategy == "drop":
            non_orig = [c for c in df.columns if c != ORIGINAL_COL]
            df = df.dropna(subset=non_orig)
        elif cfg.missing_strategy == "fill_default":
            str_cols = df.select_dtypes(include="object").columns.tolist()
            num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            # Don't fill the preserved raw dict column
            fill_str = [c for c in str_cols if c != ORIGINAL_COL]
            df[fill_str] = df[fill_str].fillna(cfg.fill_string)
            df[num_cols] = df[num_cols].fillna(cfg.fill_numeric)
        # "flag" → leave NaN unchanged

        df = df.reset_index(drop=True)
        return df, null_counts_raw, null_pct_raw, drop_cols

    def _standardize_fields(self, df: pd.DataFrame, cfg: PipelineConfig) -> pd.DataFrame:
        """Rename columns according to the user-supplied rename map."""
        if cfg.field_rename_map:
            rename = {k: v for k, v in cfg.field_rename_map.items() if k in df.columns}
            if rename:
                df = df.rename(columns=rename)
        return df

    def _deduplicate(
        self,
        df: pd.DataFrame,
        cfg: PipelineConfig,
    ) -> Tuple[pd.DataFrame, int]:
        """
        Remove exact-duplicate rows within the batch.

        Uses cfg.dedup_key_fields if set, otherwise uses all non-metadata
        columns as the composite key.
        """
        if not cfg.dedup_enabled or df.empty:
            return df, 0

        if cfg.dedup_key_fields:
            key_cols = [c for c in cfg.dedup_key_fields if c in df.columns]
        else:
            key_cols = [c for c in df.columns if c != ORIGINAL_COL]

        if not key_cols:
            return df, 0

        # Can only dedup on hashable (non-dict, non-list) columns
        safe_keys = []
        for c in key_cols:
            try:
                df[c].apply(hash)
                safe_keys.append(c)
            except TypeError:
                pass

        if not safe_keys:
            return df, 0

        before = len(df)
        df = df.drop_duplicates(subset=safe_keys, keep="first").reset_index(drop=True)
        return df, before - len(df)

    def _engineer_features(
        self,
        df: pd.DataFrame,
        cfg: PipelineConfig,
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Derive features from existing columns and add them to a copy of df.

        All new columns are prefixed with FEAT_PREFIX (``_feat_``).
        """
        if df.empty:
            return df.copy(), []

        result = df.copy()
        feat_cols: List[str] = []

        # ── Time features ─────────────────────────────────────────────────────
        if cfg.extract_time_features:
            dt_col = f"{cfg.time_field}_dt"
            if dt_col in result.columns:
                ts = pd.to_datetime(result[dt_col], errors="coerce", utc=True)
                _add_feat(result, feat_cols, f"{FEAT_PREFIX}hour",              ts.dt.hour)
                _add_feat(result, feat_cols, f"{FEAT_PREFIX}day_of_week",       ts.dt.dayofweek)
                _add_feat(result, feat_cols, f"{FEAT_PREFIX}day_of_month",      ts.dt.day)
                _add_feat(result, feat_cols, f"{FEAT_PREFIX}month",             ts.dt.month)
                _add_feat(result, feat_cols, f"{FEAT_PREFIX}is_weekend",        ts.dt.dayofweek.isin([5, 6]))
                _add_feat(result, feat_cols, f"{FEAT_PREFIX}is_business_hours", ts.dt.hour.between(9, 17))
                _add_feat(result, feat_cols, f"{FEAT_PREFIX}is_night",          ts.dt.hour.lt(6) | ts.dt.hour.ge(22))

        # ── IP features ───────────────────────────────────────────────────────
        if cfg.extract_ip_features:
            for raw_field, label in [
                (settings.es_src_ip_field, "src_ip"),
                (settings.es_dst_ip_field, "dst_ip"),
            ]:
                col = _find_col(result, raw_field)
                if col:
                    _add_feat(result, feat_cols,
                              f"{FEAT_PREFIX}{label}_is_private",
                              result[col].apply(_is_private_ip))
                    _add_feat(result, feat_cols,
                              f"{FEAT_PREFIX}{label}_class",
                              result[col].apply(_ip_class))
                    _add_feat(result, feat_cols,
                              f"{FEAT_PREFIX}{label}_first_octet",
                              result[col].apply(_first_octet))

        # ── Frequency features ────────────────────────────────────────────────
        if cfg.extract_frequency_features:
            for raw_field, label in [
                (settings.es_hostname_field, "hostname"),
                (settings.es_username_field, "username"),
                (settings.es_src_ip_field,   "src_ip"),
            ]:
                col = _find_col(result, raw_field)
                if col:
                    freq_col = f"{FEAT_PREFIX}{label}_batch_freq"
                    freq_map = result[col].value_counts()
                    _add_feat(result, feat_cols, freq_col, result[col].map(freq_map))

        logger.debug("Feature engineering added %d columns", len(feat_cols))
        return result, feat_cols


# ─── Module-level helpers ──────────────────────────────────────────────────────

def _add_feat(
    df: pd.DataFrame,
    feat_cols: List[str],
    name: str,
    series: Any,
) -> None:
    """Assign a feature column to df in-place and record its name."""
    try:
        df[name] = series
        feat_cols.append(name)
    except Exception as exc:
        logger.warning("Feature %s skipped: %s", name, exc)


def _find_col(df: pd.DataFrame, field_name: str) -> Optional[str]:
    """
    Locate a column by ECS name (e.g. 'source.ip') or its dot-replaced
    variant ('source_ip') in the DataFrame.
    """
    if field_name in df.columns:
        return field_name
    alt = field_name.replace(".", "_")
    if alt in df.columns:
        return alt
    return None


def _is_private_ip(ip_str: Any) -> Optional[bool]:
    """Return True for RFC-1918 private addresses, False for public, None for invalid."""
    if not ip_str or (isinstance(ip_str, float) and np.isnan(ip_str)):
        return None
    try:
        return ipaddress.ip_address(str(ip_str).split("/")[0].strip()).is_private
    except ValueError:
        return None


def _ip_class(ip_str: Any) -> Optional[str]:
    """Return IANA IP class (A/B/C/D/E) based on the first octet."""
    if not ip_str or (isinstance(ip_str, float) and np.isnan(ip_str)):
        return None
    try:
        first = int(str(ip_str).split(".")[0].split("/")[0].strip())
        if first < 128: return "A"
        if first < 192: return "B"
        if first < 224: return "C"
        if first < 240: return "D"
        return "E"
    except (ValueError, IndexError):
        return None


def _first_octet(ip_str: Any) -> Optional[int]:
    """Return the integer value of the first octet of an IPv4 address."""
    if not ip_str or (isinstance(ip_str, float) and np.isnan(ip_str)):
        return None
    try:
        return int(str(ip_str).split(".")[0].split("/")[0].strip())
    except (ValueError, IndexError):
        return None
