"""
core/local_data_client.py

Single source of truth for the local data pipeline.
Supports:
  - Multi-file Parquet datasets (91 files, ~90M logs)
  - Single-file CSV / XLSX / Parquet (backwards compat)

Architecture for large Parquet datasets:
  1. PyArrow Dataset scanner computes full-dataset aggregations
     (total rows, unique counts, top-N distributions, timeline)
     without loading everything into memory.
  2. A stratified sample (default 500K rows) is loaded into pandas
     for ML (Isolation Forest), SHAP, and rule-based threat tagging.
  3. Analytics results merge full-dataset KPIs with sample-based
     anomaly detection for accurate dashboard rendering.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import streamlit as st

from config import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

# ─────────────────────────────────────────────────────────────────
# Column alias mapping (old dot-notation → new underscore-separated)
# This lets _run_analytics() work with BOTH schema conventions.
# ─────────────────────────────────────────────────────────────────
COLUMN_ALIASES: Dict[str, List[str]] = {
    # Timestamp
    "@timestamp":                   ["timestamp", "@timestamp"],
    # Host
    "host.hostname":                ["host_hostname", "host.hostname"],
    "host.name":                    ["host_name", "host.name"],
    "host.ip":                      ["host_ip", "host.ip"],
    "agent.hostname":               ["agent_hostname", "agent.hostname"],
    # User
    "user.name":                    ["user_name", "user.name"],
    # Event
    "event.action":                 ["event_action", "event.action"],
    "event.category":               ["event_category", "event.category"],
    "event.id":                     ["event_id", "event.id"],
    # Process
    "process.name":                 ["process_name", "process.name"],
    "process.pid":                  ["process_pid", "process.pid"],
    "process.executable":           ["process_executable", "process.executable"],
    "process.command_line":         ["process_command_line", "process.command_line"],
    "process.args_count":           ["process_args_count", "process.args_count"],
    "process.parent.name":          ["process_parent_name", "process.parent.name"],
    "process.parent.command_line":  ["process_parent_command_line", "process.parent.command_line"],
    # Hashes & signatures
    "process.hash.md5":             ["process_md5", "process.hash.md5"],
    "process.hash.sha256":          ["process_sha256", "process.hash.sha256"],
    "process.pe.imphash":           ["process_imphash", "process.pe.imphash"],
    "process.code_signature.trusted": ["process_signature_trusted", "process.code_signature.trusted"],
    "process.code_signature.status":  ["process_signature_status", "process.code_signature.status"],
    # File
    "file.name":                    ["file_name", "file.name"],
    "file.extension":               ["file_extension", "file.extension"],
    "file.path":                    ["file_path", "file.path"],
    "file.size":                    ["file_size", "file.size"],
    # Network
    "source.ip":                    ["source_ip", "source.ip"],
    "destination.ip":               ["destination_ip", "destination.ip"],
}


def _resolve_col(df_columns, canonical_name: str) -> Optional[str]:
    """
    Resolve a canonical column name to the actual column name present
    in the DataFrame.  Tries the canonical name, then all known aliases.
    Returns None if no match found.
    """
    if canonical_name in df_columns:
        return canonical_name
    aliases = COLUMN_ALIASES.get(canonical_name, [])
    for alias in aliases:
        if alias in df_columns:
            return alias
    # Also try a reverse lookup — maybe the caller passed an alias
    for _canonical, _aliases in COLUMN_ALIASES.items():
        if canonical_name in _aliases:
            if _canonical in df_columns:
                return _canonical
            for a in _aliases:
                if a in df_columns:
                    return a
    return None


# ─────────────────────────────────────────────────────────────────
# Data source detection
# ─────────────────────────────────────────────────────────────────
def _find_data_source() -> Tuple[Path, bool]:
    """
    Find the primary data source.
    Returns (path, is_dataset):
      - (directory_path, True)  if data/ contains multiple .parquet files
      - (file_path, False)      if data/ contains a single data file
    """
    # 1. Check for multi-parquet dataset (≥2 parquet files in data/)
    parquet_files = sorted(DATA_DIR.glob("*.parquet"))
    if len(parquet_files) >= 2:
        logger.info("Detected parquet dataset with %d files in %s", len(parquet_files), DATA_DIR)
        return DATA_DIR, True

    # 2. Fall back to single-file detection (original behavior)
    for ext in ("xlsx", "csv", "parquet"):
        candidates = sorted(DATA_DIR.glob(f"*.{ext}"))
        if candidates:
            for c in candidates:
                if c.stem.lower() == "data":
                    return c, False
            return candidates[0], False

    raise FileNotFoundError(f"No data files (xlsx/csv/parquet) found in {DATA_DIR}")


def _source_fingerprint(path: Path, is_dataset: bool) -> str:
    """Return a fingerprint for cache invalidation."""
    if is_dataset:
        parquet_files = sorted(path.glob("*.parquet"))
        n_files = len(parquet_files)
        total_size = sum(f.stat().st_size for f in parquet_files)
        latest_mtime = max(f.stat().st_mtime for f in parquet_files)
        raw = f"dataset:{path}:{n_files}:{total_size}:{latest_mtime}"
    else:
        stat = path.stat()
        raw = f"file:{path}:{stat.st_mtime}:{stat.st_size}"
    return hashlib.md5(raw.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────
# Legacy helpers (for single-file CSV/XLSX with nested dict columns)
# ─────────────────────────────────────────────────────────────────
DICT_COLS = {"agent", "process", "ecs", "data_stream", "elastic",
             "host", "event", "user", "file", "Effective_process"}


def _safe_eval(val: Any) -> Dict[str, Any]:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return {}
    if isinstance(val, dict):
        return val
    val_str = str(val)
    try:
        if "'" in val_str and '"' not in val_str:
            clean_str = val_str.replace("'", '"')
            result = json.loads(clean_str)
        else:
            result = json.loads(val_str)
        return result if isinstance(result, dict) else {}
    except Exception:
        pass
    try:
        result = ast.literal_eval(val_str)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def _flatten(d: Dict, prefix: str = "", sep: str = ".") -> Dict:
    """Recursively flatten a nested dict."""
    out = {}
    for k, v in d.items():
        key = f"{prefix}{sep}{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key, sep))
        elif isinstance(v, list):
            out[key] = ", ".join(str(x) for x in v) if v else ""
        else:
            out[key] = v
    return out


def _flatten_col(series: pd.Series, col_name: str) -> pd.DataFrame:
    """Vectorised flatten of a single dict-string column into multiple columns."""
    parsed = series.apply(_safe_eval)
    flattened = parsed.apply(lambda d: _flatten(d, prefix=col_name) if d else {})
    return pd.DataFrame(flattened.tolist(), index=series.index)


# ─────────────────────────────────────────────────────────────────
# Multi-Parquet Dataset Loader (PyArrow)
# ─────────────────────────────────────────────────────────────────
SAMPLE_SIZE = 500_000       # Rows to sample for ML/anomaly detection
MAX_ROWS_SINGLE = 250_000   # Cap for single-file mode (legacy)


def _load_parquet_dataset(data_dir: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load a multi-parquet dataset using PyArrow Dataset.
    Returns:
      - sample_df: A pandas DataFrame with SAMPLE_SIZE rows for ML
      - full_stats: Pre-computed aggregations over the FULL dataset
    """
    t0 = time.monotonic()

    # Open the dataset lazily — use explicit file list to avoid
    # picking up non-parquet files from subdirectories (e.g. uploads/)
    parquet_files = sorted(data_dir.glob("*.parquet"))
    dataset = ds.dataset(parquet_files, format="parquet")
    schema = dataset.schema

    logger.info("Opened parquet dataset: %d files, %d columns",
                len(parquet_files), len(schema))

    # ── Full-dataset row count ───────────────────────────────────
    total_rows = dataset.count_rows()
    logger.info("Total rows across all files: %d", total_rows)

    full_stats: Dict[str, Any] = {
        "dataset_total_rows": total_rows,
        "dataset_num_files": len(list(data_dir.glob("*.parquet"))),
    }

    # ── Resolve key column names from schema ─────────────────────
    all_col_names = set(schema.names)

    ts_col   = _resolve_col(all_col_names, "@timestamp")
    host_col = _resolve_col(all_col_names, "host.hostname") or _resolve_col(all_col_names, "host.name")
    user_col = _resolve_col(all_col_names, "user.name")
    action_col = _resolve_col(all_col_names, "event.action")
    cat_col  = _resolve_col(all_col_names, "event.category")
    proc_col = _resolve_col(all_col_names, "process.name")
    exe_col  = _resolve_col(all_col_names, "process.executable")
    parent_col = _resolve_col(all_col_names, "process.parent.name")
    cmd_col  = _resolve_col(all_col_names, "process.command_line")
    parent_cmd_col = _resolve_col(all_col_names, "process.parent.command_line")
    hash_sha256 = _resolve_col(all_col_names, "process.hash.sha256")
    code_sig_trust = _resolve_col(all_col_names, "process.code_signature.trusted")
    code_sig_status = _resolve_col(all_col_names, "process.code_signature.status")
    file_name_col = _resolve_col(all_col_names, "file.name")
    file_ext_col = _resolve_col(all_col_names, "file.extension")
    file_path_col = _resolve_col(all_col_names, "file.path")
    file_size_col = _resolve_col(all_col_names, "file.size")
    hash_md5 = _resolve_col(all_col_names, "process.hash.md5")
    hash_imp = _resolve_col(all_col_names, "process.pe.imphash")
    host_ip_col = _resolve_col(all_col_names, "host.ip")
    source_ip_col = _resolve_col(all_col_names, "source.ip")
    dest_ip_col = _resolve_col(all_col_names, "destination.ip")

    # ── Full-dataset unique counts (via scanner) ─────────────────
    def _count_unique(col_name: Optional[str]) -> int:
        if not col_name or col_name not in all_col_names:
            return 0
        try:
            table = dataset.to_table(columns=[col_name])
            return pc.count_distinct(table.column(col_name), mode="only_valid").as_py()
        except Exception as e:
            logger.warning("Failed to count unique %s: %s", col_name, e)
            return 0

    full_stats["unique_hosts"] = _count_unique(host_col)
    full_stats["unique_users"] = _count_unique(user_col)
    full_stats["unique_processes"] = _count_unique(proc_col)

    logger.info("Unique counts: hosts=%d, users=%d, processes=%d",
                full_stats["unique_hosts"], full_stats["unique_users"],
                full_stats["unique_processes"])

    # ── Full-dataset top-N distributions ─────────────────────────
    def _top_terms_full(col_name: Optional[str], n: int = 15) -> pd.DataFrame:
        if not col_name or col_name not in all_col_names:
            return pd.DataFrame(columns=["value", "count"])
        try:
            table = dataset.to_table(columns=[col_name])
            col_data = table.column(col_name)
            # Drop nulls
            col_data = pc.drop_null(col_data)
            vc = col_data.value_counts()
            # vc is a StructArray with 'values' and 'counts'
            values = vc.field("values").to_pylist()
            counts = vc.field("counts").to_pylist()
            df_vc = pd.DataFrame({"value": values, "count": counts})
            df_vc = df_vc.sort_values("count", ascending=False).head(n).reset_index(drop=True)
            # Ensure value column is string
            df_vc["value"] = df_vc["value"].astype(str)
            return df_vc
        except Exception as e:
            logger.warning("Failed to get top terms for %s: %s", col_name, e)
            return pd.DataFrame(columns=["value", "count"])

    full_stats["top_hosts"] = _top_terms_full(host_col)
    full_stats["top_users"] = _top_terms_full(user_col)
    full_stats["top_processes"] = _top_terms_full(proc_col)
    full_stats["top_actions"] = _top_terms_full(action_col)
    full_stats["top_categories"] = _top_terms_full(cat_col)
    full_stats["top_executables"] = _top_terms_full(exe_col)
    full_stats["top_parents"] = _top_terms_full(parent_col)
    full_stats["top_file_names"] = _top_terms_full(file_name_col)
    full_stats["top_file_exts"] = _top_terms_full(file_ext_col)
    full_stats["top_file_paths"] = _top_terms_full(file_path_col)
    full_stats["top_md5"] = _top_terms_full(hash_md5)
    full_stats["top_sha256"] = _top_terms_full(hash_sha256)
    full_stats["top_imphash"] = _top_terms_full(hash_imp)

    # Code signature distributions (full dataset)
    if code_sig_trust and code_sig_trust in all_col_names:
        trust_df = _top_terms_full(code_sig_trust, n=10)
        trust_df.columns = ["status", "count"]
        full_stats["code_signature_trust"] = trust_df
    else:
        full_stats["code_signature_trust"] = pd.DataFrame()

    if code_sig_status and code_sig_status in all_col_names:
        sig_df = _top_terms_full(code_sig_status, n=10)
        sig_df.columns = ["status", "count"]
        full_stats["code_signature_status"] = sig_df
    else:
        full_stats["code_signature_status"] = pd.DataFrame()

    # ── Full-dataset timeline ────────────────────────────────────
    if ts_col and ts_col in all_col_names:
        try:
            # Sample timestamps for timeline (loading all 90M is too much RAM)
            # Use a random subset of files for speed
            if total_rows > 5_000_000:
                sample_frac = min(2_000_000 / total_rows, 1.0)
                ts_table = dataset.to_table(columns=[ts_col])
                ts_pd = ts_table.to_pandas().sample(frac=sample_frac, random_state=42)
            else:
                ts_pd = dataset.to_table(columns=[ts_col]).to_pandas()

            ts_pd.columns = ["ts"]
            # Use pandas to_datetime — handles variable fractional seconds gracefully
            ts_pd["ts"] = pd.to_datetime(ts_pd["ts"], errors="coerce", utc=True)
            ts_pd = ts_pd.dropna(subset=["ts"])

            if len(ts_pd) > 1:
                ts_min = ts_pd["ts"].min()
                ts_max = ts_pd["ts"].max()
                span = (ts_max - ts_min).total_seconds()
                if span > 86400 * 30:
                    freq = "1D"
                elif span > 86400 * 2:
                    freq = "1h"
                else:
                    freq = "10min"

                timeline = ts_pd.set_index("ts").resample(freq).size().reset_index()
                timeline.columns = ["timestamp", "count"]

                # Scale counts back up if we sampled
                if total_rows > 5_000_000:
                    scale_factor = total_rows / len(ts_pd)
                    timeline["count"] = (timeline["count"] * scale_factor).astype(int)

                full_stats["timeline"] = timeline
                full_stats["timeline_freq"] = freq
            else:
                full_stats["timeline"] = pd.DataFrame()
                full_stats["timeline_freq"] = "1h"
        except Exception as e:
            logger.warning("Failed to build full-dataset timeline: %s", e)
            full_stats["timeline"] = pd.DataFrame()
            full_stats["timeline_freq"] = "1h"
    else:
        full_stats["timeline"] = pd.DataFrame()
        full_stats["timeline_freq"] = "1h"

    # ── Host IP distributions (full dataset) ─────────────────────
    if host_ip_col and host_ip_col in all_col_names:
        ip_df = _top_terms_full(host_ip_col, n=20)
        # Filter out loopbacks
        ip_df = ip_df[~ip_df["value"].isin(["127.0.0.1", "::1"])]
        full_stats["top_host_ips"] = ip_df.head(10).reset_index(drop=True)
    else:
        full_stats["top_host_ips"] = pd.DataFrame()

    event_ip_col = source_ip_col or dest_ip_col
    if event_ip_col and event_ip_col in all_col_names:
        eip_df = _top_terms_full(event_ip_col, n=20)
        eip_df = eip_df[~eip_df["value"].isin(["127.0.0.1", "::1"])]
        full_stats["top_event_ips"] = eip_df.head(10).reset_index(drop=True)
    else:
        full_stats["top_event_ips"] = pd.DataFrame()

    # ── Sample for ML ────────────────────────────────────────────
    t_sample = time.monotonic()
    if total_rows <= SAMPLE_SIZE:
        logger.info("Dataset fits in memory (%d rows), loading all.", total_rows)
        sample_df = dataset.to_table().to_pandas()
    else:
        # Stratified sampling: take proportional rows from each file
        parquet_files = sorted(data_dir.glob("*.parquet"))
        n_files = len(parquet_files)
        rows_per_file = SAMPLE_SIZE // n_files
        remainder = SAMPLE_SIZE % n_files

        chunks = []
        for i, pf in enumerate(parquet_files):
            n_take = rows_per_file + (1 if i < remainder else 0)
            try:
                pf_table = pq.read_table(pf)
                file_rows = pf_table.num_rows
                if file_rows <= n_take:
                    chunks.append(pf_table.to_pandas())
                else:
                    # Random sample from this file
                    indices = np.random.RandomState(42 + i).choice(file_rows, size=n_take, replace=False)
                    indices.sort()
                    chunks.append(pf_table.take(indices).to_pandas())
            except Exception as e:
                logger.warning("Failed to sample from %s: %s", pf.name, e)

        sample_df = pd.concat(chunks, ignore_index=True)
        logger.info("Sampled %d rows from %d files in %.1fs",
                     len(sample_df), n_files, time.monotonic() - t_sample)

    # Parse timestamp in sample
    if ts_col and ts_col in sample_df.columns:
        sample_df[ts_col] = pd.to_datetime(sample_df[ts_col], errors="coerce", utc=True)

    elapsed = time.monotonic() - t0
    logger.info("Parquet dataset loaded: %d total rows, %d sample rows, "
                "%d cols in %.1fs", total_rows, len(sample_df),
                len(sample_df.columns), elapsed)

    return sample_df, full_stats


# ─────────────────────────────────────────────────────────────────
# Single-file loader (legacy — CSV / XLSX / single Parquet)
# ─────────────────────────────────────────────────────────────────
def _load_single_file(path: Path) -> pd.DataFrame:
    """Load a single data file (CSV, XLSX, or Parquet)."""
    logger.info("Loading single file: %s", path)
    t0 = time.monotonic()

    ext = path.suffix.lower()
    if ext == ".xlsx":
        raw = pd.read_excel(path, engine="calamine")
    elif ext == ".csv":
        file_size_gb = os.path.getsize(path) / (1024**3)
        if file_size_gb > 0.5:
            logger.warning("CSV file is massive (%.1f GB). Sampling %d rows.",
                           file_size_gb, MAX_ROWS_SINGLE)
            cols = ['agent', 'process', '@timestamp', 'ecs', 'data_stream',
                    'elastic', 'host', 'event', 'message', 'user', 'file',
                    'Effective_process']
            raw = pd.read_csv(
                path, nrows=MAX_ROWS_SINGLE, skiprows=1, header=None,
                on_bad_lines="skip", engine="c", usecols=range(12), names=cols
            )
        else:
            raw = pd.read_csv(path, low_memory=False, on_bad_lines="skip", engine="c")
    elif ext == ".parquet":
        raw = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    if len(raw) > MAX_ROWS_SINGLE:
        logger.warning("File exceeds %d rows. Sampling.", MAX_ROWS_SINGLE)
        if "@timestamp" in raw.columns:
            raw["@timestamp"] = pd.to_datetime(raw["@timestamp"], errors="coerce", utc=True)
            raw = raw.sort_values("@timestamp").tail(MAX_ROWS_SINGLE).reset_index(drop=True)
        else:
            raw = raw.sample(n=MAX_ROWS_SINGLE, random_state=42).reset_index(drop=True)

    logger.info("Read %d rows, %d raw cols in %.1fs",
                len(raw), len(raw.columns), time.monotonic() - t0)

    # ── Flatten nested dict columns (only for CSV/XLSX) ──────────
    t1 = time.monotonic()
    present_dict_cols = [c for c in raw.columns if c in DICT_COLS]

    if present_dict_cols:
        scalar_cols = [c for c in raw.columns if c not in DICT_COLS]
        parts: List[pd.DataFrame] = [raw[scalar_cols].copy()]
        for col in present_dict_cols:
            flat_part = _flatten_col(raw[col], col)
            parts.append(flat_part)
        df = pd.concat(parts, axis=1)
    else:
        df = raw

    # Timestamp
    ts_col = _resolve_col(set(df.columns), "@timestamp")
    if ts_col and not pd.api.types.is_datetime64_any_dtype(df[ts_col]):
        df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)

    elapsed = time.monotonic() - t0
    logger.info("Loaded & flattened %d rows, %d cols in %.1fs",
                len(df), len(df.columns), elapsed)
    return df


# ─────────────────────────────────────────────────────────────────
# Schema Profiler — profiles every column (sampled for speed)
# ─────────────────────────────────────────────────────────────────
_NAMESPACE_ORDER = [
    "process", "event", "host", "file", "user", "agent",
    "ecs", "data_stream", "elastic", "Effective_process",
]

PROFILE_SAMPLE_SIZE = 50_000


def _profile_schema(df: pd.DataFrame) -> Dict[str, Any]:
    total = len(df)
    all_cols = sorted(df.columns.tolist())

    if total > PROFILE_SAMPLE_SIZE:
        sample = df.sample(PROFILE_SAMPLE_SIZE, random_state=42)
    else:
        sample = df

    # group by namespace prefix (handle both dot and underscore separators)
    groups: Dict[str, list] = {}
    for col in all_cols:
        if "." in col:
            prefix = col.split(".")[0]
        elif "_" in col:
            prefix = col.split("_")[0]
        else:
            prefix = "_root"
        groups.setdefault(prefix, []).append(col)

    ordered: Dict[str, list] = {}
    for ns in _NAMESPACE_ORDER:
        if ns in groups:
            ordered[ns] = groups.pop(ns)
    for ns in sorted(groups.keys()):
        ordered[ns] = groups[ns]

    non_null_full = df.count()
    nunique = sample.nunique(dropna=True)

    profiles: Dict[str, Dict] = {}
    for col in all_cols:
        nn = int(non_null_full.get(col, 0))
        nu = int(nunique.get(col, 0))
        fill = round(nn / total * 100, 1) if total else 0.0

        if nn > 0 and nu > 0:
            vc = sample[col].dropna().astype(str).value_counts().head(5)
            top5 = [{"value": str(v)[:80], "count": int(c)} for v, c in vc.items()]
        else:
            top5 = []

        profiles[col] = {
            "dtype":    str(df[col].dtype),
            "non_null": nn,
            "fill_pct": fill,
            "unique":   nu,
            "top5":     top5,
        }

    return {
        "all_columns":      all_cols,
        "namespace_groups":  ordered,
        "column_profiles":   profiles,
        "total_columns":     len(all_cols),
    }


# ─────────────────────────────────────────────────────────────────
# ML / Threat Analytics  (scales to millions via sampling)
# ─────────────────────────────────────────────────────────────────
ML_TRAIN_SAMPLE = 50_000


def _run_analytics(df: pd.DataFrame,
                   precomputed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Runs feature engineering, Isolation Forest anomaly detection,
    and rule-based threat classification.

    If `precomputed` is provided (from multi-parquet scanner), KPIs
    like total_logs, unique counts, top-N distributions, and timeline
    are taken from there (reflecting the FULL dataset).  ML-based
    analysis runs on the sampled `df`.
    """
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import LabelEncoder

    results: Dict[str, Any] = {}
    n = len(df)
    col_set = set(df.columns)

    # Use full-dataset total if available, otherwise sample size
    results["total_logs"] = precomputed.get("dataset_total_rows", n) if precomputed else n
    results["dataset_num_files"] = precomputed.get("dataset_num_files", 1) if precomputed else 1
    results["sample_size"] = n

    # ── Identify key columns (resolve aliases) ────────────────────
    host_col   = _resolve_col(col_set, "host.hostname") or _resolve_col(col_set, "host.name") or _resolve_col(col_set, "agent.hostname")
    user_col   = _resolve_col(col_set, "user.name")
    action_col = _resolve_col(col_set, "event.action")
    cat_col    = _resolve_col(col_set, "event.category")
    proc_col   = _resolve_col(col_set, "process.name")
    cmd_col    = _resolve_col(col_set, "process.command_line")
    parent_cmd_col = _resolve_col(col_set, "process.parent.command_line")
    exe_col    = _resolve_col(col_set, "process.executable")
    parent_col = _resolve_col(col_set, "process.parent.name")
    ts_col     = _resolve_col(col_set, "@timestamp")

    file_name_col = _resolve_col(col_set, "file.name")
    file_ext_col  = _resolve_col(col_set, "file.extension")
    file_path_col = _resolve_col(col_set, "file.path")
    file_size_col = _resolve_col(col_set, "file.size")

    hash_md5    = _resolve_col(col_set, "process.hash.md5")
    hash_sha256 = _resolve_col(col_set, "process.hash.sha256")
    hash_imp    = _resolve_col(col_set, "process.pe.imphash")
    code_sig_trust  = _resolve_col(col_set, "process.code_signature.trusted")
    code_sig_status = _resolve_col(col_set, "process.code_signature.status")
    args_count  = _resolve_col(col_set, "process.args_count")
    host_ip_col = _resolve_col(col_set, "host.ip")
    event_ip_col = _resolve_col(col_set, "source.ip") or _resolve_col(col_set, "destination.ip")

    results["columns"] = {
        "host": host_col, "user": user_col, "action": action_col,
        "category": cat_col, "process": proc_col, "cmd": cmd_col,
        "exe": exe_col, "parent": parent_col, "ts": ts_col,
        "hash_sha256": hash_sha256, "code_sig": code_sig_trust,
        "file_name": file_name_col, "parent_cmd": parent_cmd_col,
    }

    # ── KPIs (prefer full-dataset stats if available) ─────────────
    if precomputed:
        results["unique_hosts"]     = precomputed.get("unique_hosts", 0)
        results["unique_users"]     = precomputed.get("unique_users", 0)
        results["unique_processes"] = precomputed.get("unique_processes", 0)
    else:
        results["unique_hosts"]     = df[host_col].nunique() if host_col else 0
        results["unique_users"]     = df[user_col].nunique() if user_col else 0
        results["unique_processes"] = df[proc_col].nunique() if proc_col else 0

    # ── Event distributions (prefer full-dataset) ─────────────────
    def top_terms_sample(col, n=15):
        if not col or col not in df.columns:
            return pd.DataFrame(columns=["value", "count"])
        s = df[col].dropna().astype(str)
        s = s.str.strip("[]'\"").str.split("', '").explode().str.strip("'\" ")
        counts = s.value_counts().head(n).reset_index()
        counts.columns = ["value", "count"]
        return counts

    # Use precomputed distributions from full dataset scan if available
    if precomputed:
        results["top_hosts"]       = precomputed.get("top_hosts", pd.DataFrame())
        results["top_users"]       = precomputed.get("top_users", pd.DataFrame())
        results["top_processes"]   = precomputed.get("top_processes", pd.DataFrame())
        results["top_actions"]     = precomputed.get("top_actions", pd.DataFrame())
        results["top_categories"]  = precomputed.get("top_categories", pd.DataFrame())
        results["top_executables"] = precomputed.get("top_executables", pd.DataFrame())
        results["top_parents"]     = precomputed.get("top_parents", pd.DataFrame())
        results["top_file_names"]  = precomputed.get("top_file_names", pd.DataFrame())
        results["top_file_exts"]   = precomputed.get("top_file_exts", pd.DataFrame())
        results["top_file_paths"]  = precomputed.get("top_file_paths", pd.DataFrame())
        results["top_md5"]         = precomputed.get("top_md5", pd.DataFrame())
        results["top_sha256"]      = precomputed.get("top_sha256", pd.DataFrame())
        results["top_imphash"]     = precomputed.get("top_imphash", pd.DataFrame())
        results["code_signature_trust"]  = precomputed.get("code_signature_trust", pd.DataFrame())
        results["code_signature_status"] = precomputed.get("code_signature_status", pd.DataFrame())
        results["top_host_ips"]    = precomputed.get("top_host_ips", pd.DataFrame())
        results["top_event_ips"]   = precomputed.get("top_event_ips", pd.DataFrame())
    else:
        results["top_hosts"]       = top_terms_sample(host_col)
        results["top_users"]       = top_terms_sample(user_col)
        results["top_processes"]   = top_terms_sample(proc_col)
        results["top_actions"]     = top_terms_sample(action_col)
        results["top_categories"]  = top_terms_sample(cat_col)
        results["top_executables"] = top_terms_sample(exe_col)
        results["top_parents"]     = top_terms_sample(parent_col)
        results["top_file_names"]  = top_terms_sample(file_name_col)
        results["top_file_exts"]   = top_terms_sample(file_ext_col)
        results["top_file_paths"]  = top_terms_sample(file_path_col)
        results["top_md5"]         = top_terms_sample(hash_md5)
        results["top_sha256"]      = top_terms_sample(hash_sha256)
        results["top_imphash"]     = top_terms_sample(hash_imp)

        if code_sig_trust and code_sig_trust in df.columns:
            trust_counts = df[code_sig_trust].value_counts().reset_index()
            trust_counts.columns = ["status", "count"]
            results["code_signature_trust"] = trust_counts
        else:
            results["code_signature_trust"] = pd.DataFrame()

        if code_sig_status and code_sig_status in df.columns:
            sig_status = df[code_sig_status].value_counts().reset_index()
            sig_status.columns = ["status", "count"]
            results["code_signature_status"] = sig_status
        else:
            results["code_signature_status"] = pd.DataFrame()

        # Host/event IPs for single-file mode
        if host_ip_col and host_ip_col in df.columns:
            s_ip = df[host_ip_col].dropna().astype(str).str.split(", ").explode()
            s_ip = s_ip[~s_ip.isin(["127.0.0.1", "::1"])]
            top_hip = s_ip.value_counts().head(10).reset_index()
            top_hip.columns = ["ip", "count"]
            results["top_host_ips"] = top_hip
        else:
            results["top_host_ips"] = pd.DataFrame()

        if event_ip_col and event_ip_col in df.columns:
            s_eip = df[event_ip_col].dropna().astype(str).str.split(", ").explode()
            s_eip = s_eip[~s_eip.isin(["127.0.0.1", "::1"])]
            top_eip = s_eip.value_counts().head(10).reset_index()
            top_eip.columns = ["ip", "count"]
            results["top_event_ips"] = top_eip
        else:
            results["top_event_ips"] = pd.DataFrame()

    # ── Timeline (prefer full-dataset) ────────────────────────────
    if precomputed and not precomputed.get("timeline", pd.DataFrame()).empty:
        results["timeline"] = precomputed["timeline"]
        results["timeline_freq"] = precomputed.get("timeline_freq", "1h")
    elif ts_col:
        ts_valid = df[ts_col].dropna()
        if len(ts_valid) > 1:
            span = (ts_valid.max() - ts_valid.min()).total_seconds()
            if span > 86400 * 30:
                freq = "1D"
            elif span > 86400 * 2:
                freq = "1h"
            else:
                freq = "10min"
        else:
            freq = "1h"
        df_ts = df.set_index(ts_col).resample(freq).size().reset_index()
        df_ts.columns = ["timestamp", "count"]
        results["timeline"] = df_ts
        results["timeline_freq"] = freq
    else:
        results["timeline"] = pd.DataFrame()
        results["timeline_freq"] = "1h"

    # ── Feature Engineering ───────────────────────────────────────
    feat_df = pd.DataFrame(index=df.index)

    if ts_col:
        feat_df["hour"]        = df[ts_col].dt.hour.fillna(12)
        feat_df["day_of_week"] = df[ts_col].dt.dayofweek.fillna(0)
        feat_df["is_night"]    = ((feat_df["hour"] < 6) | (feat_df["hour"] >= 22)).astype(int)
        feat_df["is_weekend"]  = (feat_df["day_of_week"] >= 5).astype(int)
    else:
        feat_df["hour"] = feat_df["day_of_week"] = feat_df["is_night"] = feat_df["is_weekend"] = 0

    le = LabelEncoder()
    if host_col and host_col in df.columns:
        feat_df["host_enc"] = le.fit_transform(df[host_col].fillna("unknown"))
        host_counts = df[host_col].map(df[host_col].value_counts())
        feat_df["host_freq"] = host_counts.fillna(0)
    else:
        feat_df["host_enc"] = feat_df["host_freq"] = 0

    if user_col and user_col in df.columns:
        feat_df["user_enc"] = le.fit_transform(df[user_col].fillna("unknown"))
        user_counts = df[user_col].map(df[user_col].value_counts())
        feat_df["user_freq"] = user_counts.fillna(0)
    else:
        feat_df["user_enc"] = feat_df["user_freq"] = 0

    if proc_col and proc_col in df.columns:
        feat_df["proc_enc"] = le.fit_transform(df[proc_col].fillna("unknown"))
        proc_counts = df[proc_col].map(df[proc_col].value_counts())
        feat_df["proc_rarity"] = (1 / (proc_counts + 1)).fillna(0)
    else:
        feat_df["proc_enc"] = feat_df["proc_rarity"] = 0

    if action_col and action_col in df.columns:
        feat_df["action_enc"] = le.fit_transform(df[action_col].fillna("unknown"))
    else:
        feat_df["action_enc"] = 0

    if cmd_col and cmd_col in df.columns:
        feat_df["cmd_len"] = df[cmd_col].fillna("").astype(str).str.len()
    else:
        feat_df["cmd_len"] = 0

    if args_count and args_count in df.columns:
        feat_df["args_count"] = pd.to_numeric(df[args_count], errors="coerce").fillna(0)
    else:
        feat_df["args_count"] = 0

    if file_size_col and file_size_col in df.columns:
        feat_df["file_size"] = pd.to_numeric(df[file_size_col], errors="coerce").fillna(0)
        feat_df["file_size_log"] = np.log1p(feat_df["file_size"])
    else:
        feat_df["file_size_log"] = 0

    feat_cols = feat_df.columns.tolist()

    # ── Isolation Forest (sampled training, full scoring) ─────────
    X = feat_df[feat_cols].fillna(0).values

    if n > ML_TRAIN_SAMPLE:
        logger.info("Sampling %d/%d rows for IF training", ML_TRAIN_SAMPLE, n)
        rng = np.random.RandomState(42)
        train_idx = rng.choice(n, size=ML_TRAIN_SAMPLE, replace=False)
        X_train = X[train_idx]
    else:
        X_train = X

    iso = IsolationForest(n_estimators=200, contamination=0.05, random_state=42, n_jobs=-1)
    iso.fit(X_train)

    scores = iso.score_samples(X)
    preds = iso.predict(X)
    anomaly_score = 1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)

    df_scored = df.copy()
    df_scored["anomaly_score"] = anomaly_score
    df_scored["is_anomaly"]    = preds == -1

    n_anomalies = int((preds == -1).sum())
    results["n_anomalies"]  = n_anomalies
    # Anomaly rate relative to full dataset if available
    total_for_rate = results["total_logs"]
    if precomputed:
        # Scale anomaly count to full dataset estimate
        scale = results["total_logs"] / n if n > 0 else 1
        results["n_anomalies_estimated"] = int(n_anomalies * scale)
        results["anomaly_rate"] = round(n_anomalies / n * 100, 2)
    else:
        results["n_anomalies_estimated"] = n_anomalies
        results["anomaly_rate"] = round(n_anomalies / n * 100, 2) if n > 0 else 0.0

    # ── Explainable AI (SHAP) for top anomalies ───────────────────
    try:
        import shap
        top_k = min(500, n)
        top_indices = np.argsort(anomaly_score)[-top_k:][::-1]
        X_top = X[top_indices]

        explainer = shap.TreeExplainer(iso)
        shap_values = explainer.shap_values(X_top)

        results["shap_values"] = shap_values
        expected_val = explainer.expected_value
        if isinstance(expected_val, (list, np.ndarray)):
            expected_val = expected_val[0]
        results["shap_base_value"] = expected_val
        results["shap_feature_names"] = feat_cols
        results["shap_indices"] = df.index[top_indices]
    except Exception as e:
        logger.error("Failed to compute SHAP: %s", e)
        results["shap_values"] = None

    # ── Rule-based threat tagging ─────────────────────────────────
    suspicious_procs = {
        "powershell.exe", "cmd.exe", "wscript.exe", "cscript.exe",
        "mshta.exe", "rundll32.exe", "regsvr32.exe", "certutil.exe",
        "bitsadmin.exe", "psexec.exe", "wmic.exe", "schtasks.exe",
        "net.exe", "net1.exe", "whoami.exe", "ipconfig.exe",
    }
    privilege_users = {"SYSTEM", "Administrator", "root"}

    threat_flags = pd.Series(["Normal"] * n, index=df.index)

    if proc_col and proc_col in df.columns:
        proc_lower = df[proc_col].fillna("").str.lower()
        susp_mask = proc_lower.isin([p.lower() for p in suspicious_procs])
        threat_flags[susp_mask & df_scored["is_anomaly"]] = "High Threat"
        threat_flags[susp_mask & ~df_scored["is_anomaly"]] = "Suspicious"

    if user_col and user_col in df.columns:
        sys_mask = df[user_col].isin(privilege_users) & df_scored["is_anomaly"]
        threat_flags[sys_mask] = "Critical"

    if cmd_col and cmd_col in df.columns:
        cmd_str = df[cmd_col].fillna("").astype(str).str.lower()
        encoded_mask = cmd_str.str.contains("base64|encodedcommand|-enc |iex |invoke-expression", na=False)
        download_mask = cmd_str.str.contains("wget|curl|downloadstring|bitstransfer", na=False)
        hidden_mask = cmd_str.str.contains("-w hidden|-windowstyle hidden|bypass", na=False)
        threat_flags[encoded_mask | download_mask | hidden_mask] = "Critical"

    df_scored["threat_level"] = threat_flags

    # Calculate continuous threat_score
    conds = [
        df_scored["threat_level"] == "Critical",
        df_scored["threat_level"] == "High Threat",
        df_scored["threat_level"] == "Suspicious",
    ]
    choices = [
        90.0 + df_scored["anomaly_score"] * 10.0,
        70.0 + df_scored["anomaly_score"] * 19.0,
        40.0 + df_scored["anomaly_score"] * 29.0,
    ]
    df_scored["threat_score"] = np.select(conds, choices, default=0.0)
    results["scored_df"] = df_scored

    # ── Threat summary ────────────────────────────────────────────
    threat_counts = df_scored["threat_level"].value_counts().reset_index()
    threat_counts.columns = ["threat_level", "count"]

    # Scale threat counts to full dataset if precomputed
    if precomputed and n > 0:
        scale = results["total_logs"] / n
        threat_counts["count"] = (threat_counts["count"] * scale).astype(int)
    results["threat_summary"] = threat_counts

    # ── Patterns — process trees (parent→child) ───────────────────
    if proc_col and parent_col:
        pairs = df[[parent_col, proc_col]].dropna().astype(str)
        pairs = pairs[pairs[parent_col] != pairs[proc_col]]
        pair_counts = pairs.groupby([parent_col, proc_col]).size().reset_index(name="count")
        pair_counts = pair_counts.sort_values("count", ascending=False).head(25)
        results["process_tree"] = pair_counts
    else:
        results["process_tree"] = pd.DataFrame()

    # ── User activity matrix ─────────────────────────────────────
    if user_col and proc_col:
        user_proc = df.groupby([user_col, proc_col]).size().reset_index(name="count")
        user_proc = user_proc.sort_values("count", ascending=False).head(50)
        results["user_process_matrix"] = user_proc
    else:
        results["user_process_matrix"] = pd.DataFrame()

    # ── IP Monitoring (from sample — anomaly correlation) ─────────
    if not precomputed:
        # Already handled above for single-file mode
        pass

    # IP Timeline
    if ts_col and host_ip_col and host_ip_col in df.columns:
        df_ip_time = df[[ts_col, host_ip_col]].dropna().copy()
        df_ip_time["hour"] = df_ip_time[ts_col].dt.floor("h")
        ip_timeline = df_ip_time.groupby("hour").size().reset_index(name="count")
        results["ip_timeline"] = ip_timeline
    else:
        results["ip_timeline"] = pd.DataFrame()

    # Anomalous IPs
    if host_ip_col and host_ip_col in df_scored.columns:
        anom_ips = df_scored[df_scored["is_anomaly"]][["threat_level", host_ip_col]].dropna()
        if not anom_ips.empty:
            anom_ips = anom_ips.assign(ip=anom_ips[host_ip_col].str.split(", ")).explode("ip")
            anom_ips = anom_ips[~anom_ips["ip"].isin(["127.0.0.1", "::1"])]
            anom_ip_summary = anom_ips.groupby(["ip", "threat_level"]).size().reset_index(name="count")
            anom_ip_summary = anom_ip_summary.sort_values("count", ascending=False).head(20)
            results["anomalous_ips"] = anom_ip_summary
        else:
            results["anomalous_ips"] = pd.DataFrame()
    else:
        results["anomalous_ips"] = pd.DataFrame()

    # ── Anomaly score distribution ────────────────────────────────
    results["score_bins"] = np.histogram(anomaly_score, bins=20)

    # ── Top anomalous hosts / users ──────────────────────────────
    if host_col:
        host_anom = df_scored[df_scored["is_anomaly"]].groupby(host_col).size().reset_index(name="anomaly_count")
        host_anom = host_anom.sort_values("anomaly_count", ascending=False)
        results["host_anomalies"] = host_anom
    else:
        results["host_anomalies"] = pd.DataFrame()

    if user_col:
        user_anom = df_scored[df_scored["is_anomaly"]].groupby(user_col).size().reset_index(name="anomaly_count")
        user_anom = user_anom.sort_values("anomaly_count", ascending=False)
        results["user_anomalies"] = user_anom
    else:
        results["user_anomalies"] = pd.DataFrame()

    # ── Critical events table ─────────────────────────────────────
    show_cols = [c for c in [ts_col, host_col, user_col, proc_col, parent_col,
                             action_col, cmd_col, parent_cmd_col, hash_sha256,
                             code_sig_trust, file_name_col,
                             "anomaly_score", "threat_level"]
                 if c and c in df_scored.columns]
    critical_df = df_scored[df_scored["threat_level"].isin(["Critical", "High Threat"])][show_cols].copy()
    critical_df = critical_df.sort_values("anomaly_score", ascending=False).head(500)
    results["critical_events"] = critical_df

    # ── Suspicious events ─────────────────────────────────────────
    susp_df = df_scored[df_scored["threat_level"] == "Suspicious"][show_cols].copy()
    susp_df = susp_df.sort_values("anomaly_score", ascending=False).head(500)
    results["suspicious_events"] = susp_df

    # ── Anomaly events ────────────────────────────────────────────
    anom_cols = [c for c in show_cols if c in df_scored.columns]
    anom_df = df_scored[df_scored["is_anomaly"]][anom_cols].sort_values("anomaly_score", ascending=False).head(500)
    results["anomaly_events"] = anom_df

    logger.info("Analytics complete — %d anomalies (%.1f%%), %d critical events",
                results["n_anomalies"], results["anomaly_rate"],
                len(results["critical_events"]))

    # ── Full schema profiler ──────────────────────────────────────
    schema = _profile_schema(df_scored)
    results["schema"] = schema
    results["all_columns"] = schema["all_columns"]

    return results


# ─────────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────────
class LocalDataClient:
    """Singleton that holds loaded + analysed data."""
    _instance: Optional["LocalDataClient"] = None

    def __init__(self):
        self._df: Optional[pd.DataFrame] = None
        self._analytics: Optional[Dict[str, Any]] = None
        self._source_fp: Optional[str] = None
        self._data_path: Optional[Path] = None
        self._is_dataset: Optional[bool] = None
        self._precomputed: Optional[Dict[str, Any]] = None

    @classmethod
    def get_instance(cls) -> "LocalDataClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def data_path(self) -> Path:
        if self._data_path is None:
            self._data_path, self._is_dataset = _find_data_source()
        return self._data_path

    @data_path.setter
    def data_path(self, path: Path):
        """Set an explicit data path (file or directory)."""
        self._data_path = path
        self._is_dataset = path.is_dir()

    @property
    def is_dataset(self) -> bool:
        if self._is_dataset is None:
            _ = self.data_path  # triggers detection
        return self._is_dataset

    def _check_stale(self) -> bool:
        """Return True if the data source has changed since last load."""
        try:
            current_fp = _source_fingerprint(self.data_path, self.is_dataset)
        except (FileNotFoundError, StopIteration):
            return True
        if self._source_fp is None or self._source_fp != current_fp:
            return True
        return False

    def reload(self):
        """Force reload of data and analytics."""
        self._df = None
        self._analytics = None
        self._source_fp = None
        self._data_path = None
        self._is_dataset = None
        self._precomputed = None

    def get_dataframe(self) -> pd.DataFrame:
        if self._df is None or self._check_stale():
            try:
                path = self.data_path
                if self.is_dataset:
                    self._df, self._precomputed = _load_parquet_dataset(path)
                else:
                    self._df = _load_single_file(path)
                    self._precomputed = None
                self._source_fp = _source_fingerprint(path, self.is_dataset)
            except Exception as exc:
                logger.error("Failed to load data: %s", exc, exc_info=True)
                self._df = pd.DataFrame()
                self._precomputed = None
        return self._df

    def get_analytics(self) -> Dict[str, Any]:
        if self._analytics is None or self._check_stale() or "shap_values" not in self._analytics:
            df = self.get_dataframe()
            if df.empty:
                self._analytics = {"error": "No data loaded"}
            else:
                try:
                    self._analytics = _run_analytics(df, precomputed=self._precomputed)
                except Exception as exc:
                    logger.error("Analytics failed: %s", exc, exc_info=True)
                    self._analytics = {"error": str(exc)}
        return self._analytics


def _get_file_fingerprint() -> str:
    """Helper for Streamlit cache hash — changes when the data source changes."""
    try:
        path, is_ds = _find_data_source()
        return _source_fingerprint(path, is_ds)
    except FileNotFoundError:
        return "no-file"


@st.cache_resource(show_spinner="Loading and analysing logs…")
def get_local_data_client(path_key: str = "") -> LocalDataClient:
    """Streamlit-cached singleton, keyed on the chosen data source path."""
    client = LocalDataClient()
    if path_key:
        client.data_path = Path(path_key)
    client.get_analytics()   # pre-warm
    return client
