# ISRO SOC Analytics — Security Analytics Platform

> A production-quality, large-scale, fully air-gapped security analytics platform built on Python and Streamlit — designed to handle massive volumes of security logs locally using an in-memory vectorized engine and Explainable AI (XAI).

---

## Architecture Overview

```
app.py                  # Streamlit entry point
pages/                  # Multi-page Streamlit dashboard (Overview, Settings, SOC-GPT, Documentation)
config/                 # Centralized settings & logging
core/                   # Data extraction, LLM client, and caching logic
utils/                  # Shared utilities (time, data, charts)
models/                 # ML anomaly detection (Isolation Forest) & Batch Feature Engineering
```

## Core Features
1. **Air-Gapped & Local Data Engine:** Reads massive log files (CSV, Parquet, XLSX) completely locally using chunking and advanced vectorization (`pandas` + `python-calamine`). The data never leaves the system.
2. **Explainable AI (XAI):** Uses Unsupervised **Isolation Forest** to catch zero-day threats, paired with **SHAP** (SHapley Additive exPlanations) to explain exactly why an event was flagged as anomalous.
3. **Deterministic Threat Synthesis:** Identifies malicious payloads using Regex matching (e.g., Base64, IPs) and LOLBin tracking, correlating them with ML scores to assign threat severities (CRITICAL, HIGH, SUSPICIOUS).
4. **Local SOC-GPT Assistant:** Employs a hardware-accelerated local LLM (Llama 3.2 1B Instruct via `llama-cpp-python` and Metal GPU) to converse with the analyst. It dynamically injects the platform's architectural context and telemetry data to answer complex security queries instantly.

## Quick Start

### 1. Clone & create virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```
*(Note for macOS users: `llama-cpp-python` will automatically utilize Metal acceleration if available for the local SOC-GPT model).*

### 3. Provide Data
Ensure your telemetry data (e.g., `june_logs.csv` or `data_backup.xlsx`) is placed in the `data/` directory.

### 4. Run the application
```bash
streamlit run app.py
```

## Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Memory Safety** | CSVs can be streamed via `chunksize` and sampled to handle files much larger than system RAM. |
| **Air-Gapped Intelligence** | The SOC-GPT is a local quantized model downloaded via HuggingFace Hub, running directly on device hardware. |
| **Explainability** | SHAP waterfall plots instantly identify the exact feature contributing to high anomaly scores. |
| **Caching** | `@st.cache_resource` and `@st.cache_data` heavily optimize parsing and ML model training to run instantly on refreshes. |

## Technology Stack

- **Streamlit** — Interactive UI framework
- **Pandas & python-calamine** — Fast vectorized data extraction and flattening
- **Scikit-learn** — Isolation Forest anomaly detection
- **SHAP & Matplotlib** — ML model explainability & visualization
- **Plotly** — Interactive dashboard graphs
- **Llama-cpp-python** — Local GPU-accelerated LLM runtime for SOC-GPT
- **Joblib** — ML model persistence
