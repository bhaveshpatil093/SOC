"""
core/local_data_client.py

Single source of truth for the local data pipeline.
Loads the dataset file, flattens all nested fields, runs the full
ML + threat-detection pipeline, and caches results.

Designed to scale to millions of logs:
  - Vectorised flattening via .apply() instead of iterrows()
  - Sampled Isolation Forest training (max 50k samples) with full-set scoring
  - File-modification-time based cache invalidation for real-time updates
  - Sampled schema profiling to avoid OOM on wide datasets
"""

from __future__ import annotations

import ast
import hashlib
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st

from config import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

# ─────────────────────────────────────────────────────────────────
# Auto-detect data file (xlsx, csv, parquet)
# ─────────────────────────────────────────────────────────────────
def _find_data_file() -> Path:
    """Find the primary data file in data/. Supports xlsx, csv, parquet."""
    for ext in ("xlsx", "csv", "parquet"):
        candidates = sorted(DATA_DIR.glob(f"*.{ext}"))
        if candidates:
            # prefer 'data.*' if it exists, otherwise first file
            for c in candidates:
                if c.stem.lower() == "data":
                    return c
            return candidates[0]
    raise FileNotFoundError(f"No data file (xlsx/csv/parquet) found in {DATA_DIR}")


def _file_fingerprint(path: Path) -> str:
    """Return a fingerprint based on file path + modification time + size."""
    stat = path.stat()
    raw = f"{path}:{stat.st_mtime}:{stat.st_size}"
    return hashlib.md5(raw.encode()).hexdigest()


import json

# ─────────────────────────────────────────────────────────────────
# Safe dict parser
# ─────────────────────────────────────────────────────────────────
def _safe_eval(val: Any) -> Dict[str, Any]:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return {}
    if isinstance(val, dict):
        return val
    
    val_str = str(val)
    # Try json.loads first (much faster than ast.literal_eval for millions of rows)
    try:
        # Sometimes Python dict strings use single quotes, json needs double quotes
        # A quick heuristic to replace single quotes with double quotes for valid JSON
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
# Main loader  (vectorised — handles millions of rows)
# ─────────────────────────────────────────────────────────────────
DICT_COLS = {"agent", "process", "ecs", "data_stream", "elastic",
             "host", "event", "user", "file", "Effective_process"}

MAX_ROWS = 250_000

def _load_and_flatten(path: Path) -> pd.DataFrame:
    logger.info("Loading %s", path)
    t0 = time.monotonic()

    ext = path.suffix.lower()
    if ext == ".xlsx":
        # Calamine engine is 5-10x faster than openpyxl for massive files
        raw = pd.read_excel(path, engine="calamine")
    elif ext == ".csv":
        raw = pd.read_csv(path, low_memory=False)
    elif ext == ".parquet":
        raw = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
        
    if len(raw) > MAX_ROWS:
        logger.warning(f"File exceeds {MAX_ROWS} rows. Sampling for memory stability.")
        if "@timestamp" in raw.columns:
            # Sort and take the most recent logs if timestamp is available at root
            raw["@timestamp"] = pd.to_datetime(raw["@timestamp"], errors="coerce", utc=True)
            raw = raw.sort_values("@timestamp").tail(MAX_ROWS).reset_index(drop=True)
        else:
            # Otherwise, just randomly sample
            raw = raw.sample(n=MAX_ROWS, random_state=42).reset_index(drop=True)

    logger.info("Read %d rows, %d raw cols in %.1fs", len(raw), len(raw.columns),
                time.monotonic() - t0)

    # ── Vectorised flattening ────────────────────────────────────
    t1 = time.monotonic()
    present_dict_cols = [c for c in raw.columns if c in DICT_COLS]
    scalar_cols = [c for c in raw.columns if c not in DICT_COLS]

    parts: List[pd.DataFrame] = [raw[scalar_cols].copy()]

    for col in present_dict_cols:
        flat_part = _flatten_col(raw[col], col)
        parts.append(flat_part)

    df = pd.concat(parts, axis=1)

    # Timestamp (ensure it is parsed if it wasn't already in the sampling block)
    if "@timestamp" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["@timestamp"]):
        df["@timestamp"] = pd.to_datetime(df["@timestamp"], errors="coerce", utc=True)

    elapsed = time.monotonic() - t0
    logger.info("Loaded & flattened %d rows, %d cols in %.1fs", len(df), len(df.columns), elapsed)
    return df


# ─────────────────────────────────────────────────────────────────
# Schema Profiler — profiles every column (sampled for speed)
# ─────────────────────────────────────────────────────────────────
_NAMESPACE_ORDER = [
    "process", "event", "host", "file", "user", "agent",
    "ecs", "data_stream", "elastic", "Effective_process",
]

PROFILE_SAMPLE_SIZE = 50_000  # sample for profiling on large datasets


def _profile_schema(df: pd.DataFrame) -> Dict[str, Any]:
    total = len(df)
    all_cols = sorted(df.columns.tolist())

    # use a sample for profiling if dataset is large
    if total > PROFILE_SAMPLE_SIZE:
        sample = df.sample(PROFILE_SAMPLE_SIZE, random_state=42)
    else:
        sample = df

    # group by namespace prefix
    groups: Dict[str, list] = {}
    for col in all_cols:
        prefix = col.split(".")[0] if "." in col else "_root"
        groups.setdefault(prefix, []).append(col)

    ordered: Dict[str, list] = {}
    for ns in _NAMESPACE_ORDER:
        if ns in groups:
            ordered[ns] = groups.pop(ns)
    for ns in sorted(groups.keys()):
        ordered[ns] = groups[ns]

    # per-column profile (vectorised on sample)
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
        "all_columns":     all_cols,
        "namespace_groups": ordered,
        "column_profiles":  profiles,
        "total_columns":    len(all_cols),
    }


# ─────────────────────────────────────────────────────────────────
# ML / Threat Analytics  (scales to millions via sampling)
# ─────────────────────────────────────────────────────────────────
ML_TRAIN_SAMPLE = 50_000   # train Isolation Forest on this many rows max


def _run_analytics(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Runs feature engineering, Isolation Forest anomaly detection,
    and rule-based threat classification. Returns a results dict.
    """
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import LabelEncoder

    results: Dict[str, Any] = {}
    n = len(df)
    results["total_logs"] = n

    # ── Identify key columns ──────────────────────────────────────
    host_col    = next((c for c in ["host.hostname", "host.name", "agent.hostname"] if c in df.columns), None)
    user_col    = next((c for c in ["user.name"]  if c in df.columns), None)
    action_col  = next((c for c in ["event.action"]  if c in df.columns), None)
    cat_col     = next((c for c in ["event.category"] if c in df.columns), None)
    proc_col    = next((c for c in ["process.name"]   if c in df.columns), None)
    cmd_col     = next((c for c in ["process.command_line"] if c in df.columns), None)
    parent_cmd_col = next((c for c in ["process.parent.command_line"] if c in df.columns), None)
    exe_col     = next((c for c in ["process.executable"]   if c in df.columns), None)
    parent_col  = next((c for c in ["process.parent.name"]  if c in df.columns), None)
    ts_col      = "@timestamp" if "@timestamp" in df.columns else None

    file_name_col = next((c for c in ["file.name"] if c in df.columns), None)
    file_ext_col = next((c for c in ["file.extension"] if c in df.columns), None)
    file_path_col = next((c for c in ["file.path"] if c in df.columns), None)
    file_size_col = next((c for c in ["file.size"] if c in df.columns), None)

    hash_md5 = next((c for c in ["process.hash.md5"] if c in df.columns), None)
    hash_sha256 = next((c for c in ["process.hash.sha256"] if c in df.columns), None)
    hash_imp = next((c for c in ["process.pe.imphash"] if c in df.columns), None)
    code_sig_trust = next((c for c in ["process.code_signature.trusted"] if c in df.columns), None)
    code_sig_status = next((c for c in ["process.code_signature.status"] if c in df.columns), None)
    args_count = next((c for c in ["process.args_count"] if c in df.columns), None)

    results["columns"] = {
        "host": host_col, "user": user_col, "action": action_col,
        "category": cat_col, "process": proc_col, "cmd": cmd_col,
        "exe": exe_col, "parent": parent_col, "ts": ts_col,
        "hash_sha256": hash_sha256, "code_sig": code_sig_trust,
        "file_name": file_name_col, "parent_cmd": parent_cmd_col
    }

    # ── KPIs ─────────────────────────────────────────────────────
    results["unique_hosts"]    = df[host_col].nunique()  if host_col else 0
    results["unique_users"]    = df[user_col].nunique()  if user_col else 0
    results["unique_processes"] = df[proc_col].nunique() if proc_col else 0

    # ── Event distributions ───────────────────────────────────────
    def top_terms(col, n=15):
        if not col or col not in df.columns:
            return pd.DataFrame(columns=["value", "count"])
        s = df[col].dropna().astype(str)
        s = s.str.strip("[]'\"").str.split("', '").explode().str.strip("'\" ")
        counts = s.value_counts().head(n).reset_index()
        counts.columns = ["value", "count"]
        return counts

    results["top_hosts"]     = top_terms(host_col)
    results["top_users"]     = top_terms(user_col)
    results["top_processes"] = top_terms(proc_col)
    results["top_actions"]   = top_terms(action_col)
    results["top_categories"] = top_terms(cat_col)
    results["top_executables"] = top_terms(exe_col)
    results["top_parents"]   = top_terms(parent_col)

    results["top_file_names"] = top_terms(file_name_col)
    results["top_file_exts"]  = top_terms(file_ext_col)
    results["top_file_paths"] = top_terms(file_path_col)

    results["top_md5"] = top_terms(hash_md5)
    results["top_sha256"] = top_terms(hash_sha256)
    results["top_imphash"] = top_terms(hash_imp)

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

    # ── Timeline ─────────────────────────────────────────────────
    if ts_col:
        # auto-pick resolution based on time range
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
        feat_df["hour"]         = df[ts_col].dt.hour.fillna(12)
        feat_df["day_of_week"]  = df[ts_col].dt.dayofweek.fillna(0)
        feat_df["is_night"]     = ((feat_df["hour"] < 6) | (feat_df["hour"] >= 22)).astype(int)
        feat_df["is_weekend"]   = (feat_df["day_of_week"] >= 5).astype(int)
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

    # Score the entire dataset
    scores = iso.score_samples(X)
    preds = iso.predict(X)
    anomaly_score = 1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)

    df_scored = df.copy()
    df_scored["anomaly_score"] = anomaly_score
    df_scored["is_anomaly"]    = preds == -1

    results["n_anomalies"]  = int((preds == -1).sum())
    results["anomaly_rate"] = round(results["n_anomalies"] / n * 100, 2)

    # ── Explainable AI (SHAP) for top anomalies ───────────────────
    try:
        import shap
        top_k = min(500, n)
        # Get indices of top k anomalies (highest anomaly score)
        top_indices = np.argsort(anomaly_score)[-top_k:][::-1]
        X_top = X[top_indices]
        
        explainer = shap.TreeExplainer(iso)
        shap_values = explainer.shap_values(X_top)
        
        results["shap_values"] = shap_values
        # expected_value might be a list or a single float
        expected_val = explainer.expected_value
        if isinstance(expected_val, list) or isinstance(expected_val, np.ndarray):
            expected_val = expected_val[0]
            
        results["shap_base_value"] = expected_val
        results["shap_feature_names"] = feat_cols
        results["shap_indices"] = df.index[top_indices]  # Store original dataframe index
    except Exception as e:
        logger.error(f"Failed to compute SHAP: {e}")
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
    results["scored_df"] = df_scored

    # ── Threat summary ────────────────────────────────────────────
    threat_counts = df_scored["threat_level"].value_counts().reset_index()
    threat_counts.columns = ["threat_level", "count"]
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

    # ── IP Monitoring / Network ──────────────────────────────────
    host_ip_col = next((c for c in ["host.ip"] if c in df.columns), None)
    event_ip_col = next((c for c in ["event.ip", "source.ip", "destination.ip"] if c in df.columns), None)
    
    # 1. Parse IPs (filter out loopbacks)
    if host_ip_col:
        s_ip = df[host_ip_col].dropna().astype(str).str.split(", ").explode()
        s_ip = s_ip[~s_ip.isin(["127.0.0.1", "::1"])]
        top_host_ips = s_ip.value_counts().head(10).reset_index()
        top_host_ips.columns = ["ip", "count"]
        results["top_host_ips"] = top_host_ips
    else:
        results["top_host_ips"] = pd.DataFrame()
        
    if event_ip_col:
        s_eip = df[event_ip_col].dropna().astype(str).str.split(", ").explode()
        s_eip = s_eip[~s_eip.isin(["127.0.0.1", "::1"])]
        top_event_ips = s_eip.value_counts().head(10).reset_index()
        top_event_ips.columns = ["ip", "count"]
        results["top_event_ips"] = top_event_ips
    else:
        results["top_event_ips"] = pd.DataFrame()

    # 2. IP Timeline
    if ts_col and host_ip_col:
        df_ip_time = df[[ts_col, host_ip_col]].dropna().copy()
        df_ip_time["hour"] = df_ip_time[ts_col].dt.floor("h")
        ip_timeline = df_ip_time.groupby("hour").size().reset_index(name="count")
        results["ip_timeline"] = ip_timeline
    else:
        results["ip_timeline"] = pd.DataFrame()

    # 3. Anomalous IPs
    if host_ip_col:
        anom_ips = df_scored[df_scored["is_anomaly"]][["threat_level", host_ip_col]].dropna()
        anom_ips = anom_ips.assign(ip=anom_ips[host_ip_col].str.split(", ")).explode("ip")
        anom_ips = anom_ips[~anom_ips["ip"].isin(["127.0.0.1", "::1"])]
        anom_ip_summary = anom_ips.groupby(["ip", "threat_level"]).size().reset_index(name="count")
        anom_ip_summary = anom_ip_summary.sort_values("count", ascending=False).head(20)
        results["anomalous_ips"] = anom_ip_summary
    else:
        results["anomalous_ips"] = pd.DataFrame()
        results["user_process_matrix"] = pd.DataFrame()

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
    show_cols = [c for c in ["@timestamp", host_col, user_col, proc_col, parent_col, action_col, cmd_col, parent_cmd_col, hash_sha256, code_sig_trust, file_name_col, "anomaly_score", "threat_level"] if c and c in df_scored.columns]
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

    logger.info("Analytics complete — %d anomalies, %d critical",
                results["n_anomalies"],
                len(results["critical_events"]))

    # ── Full schema profiler (all columns) ────────────────────────
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
        self._file_fp: Optional[str] = None
        self._data_path: Optional[Path] = None

    @classmethod
    def get_instance(cls) -> "LocalDataClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def data_path(self) -> Path:
        if self._data_path is None:
            self._data_path = _find_data_file()
        return self._data_path

    @data_path.setter
    def data_path(self, path: Path):
        """Set an explicit data path (e.g. user-uploaded file)."""
        self._data_path = path

    def _check_stale(self) -> bool:
        """Return True if the data file has changed since last load."""
        try:
            current_fp = _file_fingerprint(self.data_path)
        except FileNotFoundError:
            return True
        if self._file_fp is None or self._file_fp != current_fp:
            return True
        return False

    def reload(self):
        """Force reload of data and analytics."""
        self._df = None
        self._analytics = None
        self._file_fp = None
        self._data_path = None

    def get_dataframe(self) -> pd.DataFrame:
        if self._df is None or self._check_stale():
            try:
                path = self.data_path
                self._df = _load_and_flatten(path)
                self._file_fp = _file_fingerprint(path)
            except Exception as exc:
                logger.error("Failed to load data: %s", exc)
                self._df = pd.DataFrame()
        return self._df

    def get_analytics(self) -> Dict[str, Any]:
        if self._analytics is None or self._check_stale() or "shap_values" not in self._analytics:
            df = self.get_dataframe()
            if df.empty:
                self._analytics = {"error": "No data loaded"}
            else:
                try:
                    self._analytics = _run_analytics(df)
                except Exception as exc:
                    logger.error("Analytics failed: %s", exc, exc_info=True)
                    self._analytics = {"error": str(exc)}
        return self._analytics


def _get_file_fingerprint() -> str:
    """Helper for Streamlit cache hash — changes when the data file changes."""
    try:
        path = _find_data_file()
        return _file_fingerprint(path)
    except FileNotFoundError:
        return "no-file"


@st.cache_resource(show_spinner="Loading and analysing logs…")
def get_local_data_client(path_key: str = "") -> LocalDataClient:
    """Streamlit-cached singleton, keyed on the chosen file path."""
    client = LocalDataClient()
    if path_key:
        client.data_path = Path(path_key)
    client.get_analytics()   # pre-warm
    return client
