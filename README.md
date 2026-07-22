# ISRO SOC Analytics — Security Analytics Platform

> A production-quality, large-scale security analytics platform built on Python, Streamlit, and Elasticsearch — designed to handle billions of security logs without loading them into memory.

---

## Architecture Overview

```
app.py                  # Streamlit entry point (Home page)
pages/                  # Multi-page Streamlit pages
config/                 # Centralized settings & logging
core/                   # ES client, query builder, cache manager
utils/                  # Shared utilities (time, data, charts, sigma)
models/                 # ML anomaly detection wrappers
rules/                  # Sigma rule storage
```

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

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your Elasticsearch credentials
```

### 4. Run the application
```bash
bash run.sh
# or directly:
streamlit run app.py
```

## Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Memory safety** | All analytics use ES aggregations — never full log scans |
| **Scalability** | Batch processing via `search_after` for exports |
| **Resilience** | Exponential backoff retry on ES connection failures |
| **Caching** | `st.cache_data` (in-memory) + `joblib` (disk) for aggregations |
| **Modularity** | Each page is self-contained; core layer is shared |
| **Security** | Read-only ES credentials; secrets in `.env` only |

## Environment Variables

See [`.env.example`](.env.example) for all configuration options.

## Pages / Workflow

| Step | Page | Description |
|------|------|-------------|
| 0 | **🏠 Home** | Platform overview & architecture diagram |
| 1 | **📊 Overview** | High-level SOC KPI dashboard — volume, top sources, severity |
| 2 | **⚙️ Settings** | Configure Elasticsearch connection and cache policies |
| 3 | **🔌 ES Diagnostics** | Verify cluster health, indices, and aggregations |
| 4 | **📥 Log Retrieval** | Execute safe, paginated log queries via `search_after` |
| 5 | **🧹 Data Pipeline** | Clean, normalize, and extract features from retrieved logs |
| 6 | **📋 Sigma Rules** | Execute Sigma detections locally on the retrieved batch |
| 7 | **🤖 ML Anomaly** | Flag behavioural outliers using Isolation Forest / LOF |
| 8 | **🎯 Threat Scoring** | Correlate Sigma & ML findings into unified alert scores |
| 9 | **🤖 AI Assistant** | Investigate results via a deterministic or LLM-powered conversational agent |
| 10 | **🔍 Threat Hunter** | (Legacy) Free-form query builder with timeline |
| 11 | **🚨 Alerts** | (Legacy) Alert correlation & triage |


## Technology Stack

- **Streamlit** — UI framework
- **Elasticsearch 9.4.1** — Log storage & aggregation engine
- **Pandas / NumPy** — Aggregation result processing
- **Plotly** — Interactive visualisations
- **Scikit-learn** — Anomaly detection models
- **pySigma** — Sigma rule engine
- **Joblib** — Caching & model persistence
- **Tenacity** — Retry logic with exponential backoff

## Dataset

- **Volume**: ~2.77 billion logs
- **Period**: June 2026
- **Access**: Read-only Elasticsearch cluster
- **Index pattern**: Configurable (default: `security-logs-2026.06.*`)
